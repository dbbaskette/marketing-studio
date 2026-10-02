#!/usr/bin/env python3
"""Google Drive transfers through gcloud user login; no OAuth project setup."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile

DRIVE = 'https://www.googleapis.com/drive/v3/'
DOCS = 'https://docs.googleapis.com/v1/documents/'
UPLOAD = 'https://www.googleapis.com/upload/drive/v3/files'
DOC_MIME = 'application/vnd.google-apps.document'
DOCX = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
LIMIT = 20 * 1024 * 1024
LOGIN = 'gcloud auth login --enable-gdrive-access --force'


class GoogleError(Exception):
    pass


def identifier(value):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', value):
        raise GoogleError('Use a Google file ID, not a URL or path.')
    return value


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def gcloud():
    found = shutil.which('gcloud')
    if found:
        return found
    for path in ('/opt/homebrew/share/google-cloud-sdk/bin/gcloud',
                 '/usr/local/share/google-cloud-sdk/bin/gcloud',
                 str(Path.home() / 'google-cloud-sdk/bin/gcloud')):
        if Path(path).is_file() and os.access(path, os.X_OK):
            return path
    raise GoogleError('gcloud is missing. Run installer/google-setup.sh --install-cli, or use an organization-approved Google Cloud CLI installation.')


def token(account=None):
    args = [gcloud(), 'auth', 'print-access-token', '--quiet']
    if account:
        args += ['--account', account]
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        raise GoogleError('Google authentication failed. Run ' + LOGIN) from None
    value = result.stdout.strip()
    if result.returncode or not value or any(c.isspace() for c in value):
        raise GoogleError('Google authentication is unavailable. Run ' + LOGIN)
    return value


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, account=None):
        self.account = account
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, url, *, method='GET', body=None, mime='application/json', binary=False):
        # Tokens may only go to these fixed Google APIs; never follow a redirect.
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != 'https' or parsed.netloc not in ('www.googleapis.com', 'docs.googleapis.com'):
            raise GoogleError('Unsupported Google API destination.')
        payload = encoded(body) if isinstance(body, dict) else body
        req = urllib.request.Request(url, data=payload, method=method,
            headers={'Authorization': 'Bearer ' + token(self.account), 'Content-Type': mime})
        try:
            with self.opener.open(req, timeout=60) as response:
                data = response.read(LIMIT + 1)
            if len(data) > LIMIT:
                raise GoogleError('Google response exceeded the transfer size limit.')
            if binary:
                return data
            value = json.loads(data)
            if not isinstance(value, dict):
                raise GoogleError('Google returned an unexpected response; reconcile any write before retrying.')
            return value
        except urllib.error.HTTPError as exc:
            # Never echo provider bodies, request headers, tokens or auth diagnostics.
            if exc.code == 401:
                message = 'Google sign-in expired; run ' + LOGIN
            elif exc.code == 403:
                message = 'Google denied this operation. Check Drive consent, file permissions, API availability and organization policy; do not broaden access automatically.'
            elif exc.code in (400, 409, 412) and method != 'GET':
                message = 'Google rejected the write. Reread the document and revision before making another request.'
            else:
                message = 'Google request failed (HTTP ' + str(exc.code) + ').'
            raise GoogleError(message) from None
        except (OSError, ValueError):
            raise GoogleError('Google response was unavailable or invalid. A write may have completed; reconcile before retrying.') from None

    def drive(self, path, **query):
        return self.request(DRIVE + path + '?' + urllib.parse.urlencode(query))

    def check(self):
        about = self.drive('about', fields='importFormats')
        formats = about.get('importFormats', {})
        return {'status': 'drive-read', 'html_import_advertised': DOC_MIME in formats.get('text/html', []),
                'docx_import_advertised': DOC_MIME in formats.get(DOCX, []),
                'native_docs': 'unverified', 'write': 'unverified'}

    def metadata(self, file_id):
        return self.drive('files/' + identifier(file_id), supportsAllDrives='true',
            fields='id,name,mimeType,parents,webViewLink,modifiedTime,version,trashed,capabilities(canEdit,canAddChildren)')

    def permissions(self, file_id):
        result = []
        page = None
        for _ in range(100):
            query = {'supportsAllDrives': 'true', 'pageSize': 100,
                     'fields': 'nextPageToken,permissions(id,type,role,emailAddress,domain,allowFileDiscovery,permissionDetails)'}
            if page:
                query['pageToken'] = page
            response = self.drive('files/' + identifier(file_id) + '/permissions', **query)
            result.extend(response.get('permissions', []))
            page = response.get('nextPageToken')
            if not page:
                return sorted(result, key=lambda p: p['id'])
        raise GoogleError('Permission listing was incomplete; no upload performed.')

    def audience(self, folder_id):
        meta = self.metadata(folder_id)
        if meta.get('mimeType') != 'application/vnd.google-apps.folder' or meta.get('trashed'):
            raise GoogleError('Choose an existing Google Drive folder.')
        permissions = self.permissions(folder_id)
        snapshot = {'folder_id': folder_id, 'permissions': permissions}
        return {**snapshot, 'audience_sha256': digest(encoded(snapshot)),
                'can_add_children': meta.get('capabilities', {}).get('canAddChildren', False)}

    def native_read(self, file_id):
        return self.request(DOCS + identifier(file_id) + '?' + urllib.parse.urlencode({
            'includeTabsContent': 'true', 'suggestionsViewMode': 'PREVIEW_WITHOUT_SUGGESTIONS'}))

    def native_update(self, file_id, revision, requests):
        if not isinstance(revision, str) or not revision.strip():
            raise GoogleError('A fresh requiredRevisionId is mandatory.')
        if not isinstance(requests, list) or not requests or not all(isinstance(r, dict) for r in requests):
            raise GoogleError('Provide a nonempty JSON array of selected native edits.')
        response = self.request(DOCS + identifier(file_id) + ':batchUpdate', method='POST',
            body={'writeControl': {'requiredRevisionId': revision}, 'requests': requests})
        return {'status': 'written-unverified', 'document_id': file_id,
                'write_control': response.get('writeControl'), 'next_step': 'Read all affected tabs and verify before google confirm.'}

    def locate(self, operation):
        if not re.fullmatch(r'[0-9a-f]{32}', operation):
            raise GoogleError('Use the original 32-character operation ID.')
        result = self.drive('files', q="trashed = false and appProperties has { key='blogStudioOperation' and value='" + operation + "' }",
            spaces='drive', pageSize=100, includeItemsFromAllDrives='true', supportsAllDrives='true',
            fields='nextPageToken,files(id,name,mimeType,webViewLink,parents)')
        return {'status': 'reconcile-only', 'operation': operation, 'matches': result.get('files', []),
                'incomplete': bool(result.get('nextPageToken')), 'next_step': 'Inspect matches; an empty result does not authorize repeating an uncertain upload.'}

    def export(self, file_id, format):
        meta = self.metadata(file_id)
        if meta.get('mimeType') != DOC_MIME:
            raise GoogleError('The selected file is not a native Google Doc.')
        mime = {'txt': 'text/plain', 'pdf': 'application/pdf', 'docx': DOCX}[format]
        data = self.request(DRIVE + 'files/' + identifier(file_id) + '/export?' + urllib.parse.urlencode({'mimeType': mime}), binary=True)
        if format == 'pdf' and not data.startswith(b'%PDF-'):
            raise GoogleError('Export was not a PDF.')
        if format == 'docx':
            validate_docx(data)
        if format == 'txt':
            try:
                data.decode('utf-8')
            except UnicodeError:
                raise GoogleError('Text export was not UTF-8.') from None
        return data

    def import_new(self, path, title, state_path, folder_id=None, audience_sha256=None):
        path = Path(path)
        if not title.strip() or len(title) > 500 or path.stat().st_size > LIMIT:
            raise GoogleError('Provide a title (1–500 characters) and a file no larger than 20 MB.')
        mime = {'.html': 'text/html', '.txt': 'text/plain', '.docx': DOCX}.get(path.suffix.lower())
        if not mime:
            raise GoogleError('Import accepts HTML, plain text or DOCX. Convert Markdown deliberately before upload.')
        data = path.read_bytes()
        if mime == DOCX:
            validate_docx(data)
        else:
            data.decode('utf-8')
        if folder_id:
            observed = self.audience(folder_id)
            if not observed['can_add_children'] or not audience_sha256 or observed['audience_sha256'] != audience_sha256:
                raise GoogleError('Review the destination audience and pass its current audience_sha256 before uploading.')
        metadata = {'name': title, 'mimeType': DOC_MIME}
        if folder_id:
            metadata['parents'] = [identifier(folder_id)]
        operation = uuid.uuid4().hex
        metadata['appProperties'] = {'blogStudioOperation': operation}
        # Reserve before POST. Existing receipts ALWAYS stop another upload, even
        # after a crash or ambiguous network result. Recovery is read-only.
        receipt = {'schema': 1, 'operation': operation, 'status': 'submitting',
                   'content_sha256': digest(data), 'folder_id': folder_id}
        state_path = Path(state_path)
        write_new(state_path, encoded(receipt))
        boundary = 'blogstudio_' + uuid.uuid4().hex
        body = (('--' + boundary + '\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n').encode()
                + encoded(metadata) + ('\r\n--' + boundary + '\r\nContent-Type: ' + mime + '\r\n\r\n').encode()
                + data + ('\r\n--' + boundary + '--\r\n').encode())
        try:
            response = self.request(UPLOAD + '?' + urllib.parse.urlencode({'uploadType': 'multipart',
                'supportsAllDrives': 'true', 'fields': 'id,mimeType,webViewLink,parents'}), method='POST',
                body=body, mime='multipart/related; boundary=' + boundary)
            if response.get('mimeType') != DOC_MIME or not response.get('id'):
                raise GoogleError('Google did not confirm a native Doc. Reconcile the operation before retrying.')
            receipt.update(status='created-unverified', document_id=identifier(response['id']),
                url='https://docs.google.com/document/d/' + identifier(response['id']) + '/edit')
            # Preserve the known remote ID even if later readback fails.
            temp = state_path.with_name(state_path.name + '.' + uuid.uuid4().hex)
            try:
                write_new(temp, encoded(receipt))
                os.replace(temp, state_path)
            finally:
                temp.unlink(missing_ok=True)
            return {**receipt, 'next_step': 'Read back actual content, structure, folder and access before confirming the handoff.'}
        except (GoogleError, OSError):
            raise GoogleError('Upload outcome needs reconciliation. Keep receipt ' + str(state_path) + '; run reconcile --operation ' + operation + '. Do not repeat import with a new receipt.') from None


def validate_docx(data):
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if not {'[Content_Types].xml', 'word/document.xml'}.issubset(archive.namelist()):
                raise ValueError()
    except (ValueError, zipfile.BadZipFile):
        raise GoogleError('The file is not a DOCX package.') from None


def write_new(path, data):
    # O_EXCL rejects existing files and symlinks; private permissions by default.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--account', help='Use this already-authorized gcloud account without switching the active account.')
    actions = parser.add_subparsers(dest='action', required=True)
    actions.add_parser('check')
    actions.add_parser('login')
    for name in ('metadata', 'audience', 'read', 'export', 'update'):
        sub = actions.add_parser(name);sub.add_argument('--file-id', required=True)
        if name in ('read', 'export'):
            sub.add_argument('--output', type=Path, required=True)
        if name == 'export':
            sub.add_argument('--format', choices=('txt', 'pdf', 'docx'), required=True)
        if name == 'update':
            sub.add_argument('--revision', required=True);sub.add_argument('--requests', type=Path, required=True)
    sub = actions.add_parser('import')
    sub.add_argument('--file', type=Path, required=True);sub.add_argument('--title', required=True)
    sub.add_argument('--receipt', type=Path, required=True);sub.add_argument('--folder-id');sub.add_argument('--audience-sha256')
    actions.add_parser('reconcile').add_argument('--operation', required=True)
    args = parser.parse_args()
    try:
        client = Client(args.account)
        if args.action == 'login':
            command = [gcloud(), 'auth', 'login', '--enable-gdrive-access', '--force']
            if args.account:
                command += [args.account, '--no-activate']
            # Browser consent is interactive. No credentials go through JSON output.
            if subprocess.run(command).returncode:
                raise GoogleError('Google sign-in did not complete.')
            result = client.check()
        elif args.action == 'check': result = client.check()
        elif args.action == 'metadata': result = client.metadata(args.file_id)
        elif args.action == 'audience': result = client.audience(args.file_id)
        elif args.action == 'read':
            result = client.native_read(args.file_id)
            write_new(args.output, encoded(result))
            result = {'status': 'native-read', 'file': str(args.output), 'structure_verified': False}
        elif args.action == 'export':
            write_new(args.output, client.export(args.file_id, args.format))
            result = {'status': 'exported', 'file': str(args.output), 'format': args.format,
                'next_step': 'Inspect the actual export. Plain text does not prove accepted suggestions, all-tab coverage or native fidelity.'}
        elif args.action == 'import': result = client.import_new(args.file, args.title, args.receipt, args.folder_id, args.audience_sha256)
        elif args.action == 'reconcile': result = client.locate(args.operation)
        else: result = client.native_update(args.file_id, args.revision, json.loads(args.requests.read_text()))
        print(json.dumps(result, indent=2))
        return 0
    except GoogleError as exc:
        print(json.dumps({'status': 'unavailable', 'error': str(exc)}), file=sys.stderr)
    except (OSError, ValueError):
        print(json.dumps({'status': 'unavailable', 'error': 'Local input/output failed. Use valid inputs and a new output path; preserve existing receipts and reconcile uncertain writes.'}), file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
