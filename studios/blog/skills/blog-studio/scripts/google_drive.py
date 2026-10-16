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
import time
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
LOGIN = 'gcloud auth login <your-email> --enable-gdrive-access --force --no-activate'
SIGN_IN = 'Sign in with google_drive.py login --account <your-email> (it runs ' + LOGIN + ').'
STAGING = '.google-staging'
STAGING_MAX_AGE = 7 * 24 * 3600
ACCOUNT_FILE = '.google-account.json'
EMAIL = re.compile(r'[^@\s/]{1,64}@[^@\s/]{1,180}\.[^@\s/]{1,60}')
RATE_LABELS = frozenset({'RATE_LIMIT_EXCEEDED', 'rateLimitExceeded', 'userRateLimitExceeded'})
READ_RETRY_DELAYS = (0.5, 2.0)


class GoogleError(Exception):
    def __init__(self, message, *, status=None, review_unavailable=False, labels=(), network=False):
        super().__init__(message)
        self.status = status
        self.review_unavailable = review_unavailable
        self.labels = frozenset(labels)
        self.network = network

    @property
    def definite(self):
        """Google answered with a client error, so this request was not applied.

        Server errors (5xx) and missing responses stay uncertain for writes.
        """
        return self.status is not None and 400 <= self.status < 500

    @property
    def rate_limited(self):
        return self.status == 429 or bool(self.labels & RATE_LABELS)

    @property
    def transient(self):
        """Worth repeating for an idempotent read; never a reason to repeat a write."""
        return self.network or self.rate_limited or self.status in (500, 502, 503, 504)


class ReviewUnavailable(GoogleError):
    """Read-only evidence that the native review surface is unavailable."""

    def __init__(self, message):
        super().__init__(message, review_unavailable=True)


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
    for path in (
        '/opt/homebrew/share/google-cloud-sdk/bin/gcloud',
        '/usr/local/share/google-cloud-sdk/bin/gcloud',
        str(Path.home() / 'google-cloud-sdk/bin/gcloud'),
    ):
        if Path(path).is_file() and os.access(path, os.X_OK):
            return path
    raise GoogleError(
        'gcloud is missing. Run installer/google-setup.sh --install-cli, or use an organization-approved Google Cloud CLI installation.'
    )


def token(account=None):
    args = [gcloud(), 'auth', 'print-access-token', '--quiet']
    if account:
        args += ['--account', account]
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
    except PermissionError:
        raise GoogleError(
            'Local gcloud execution or credential access was denied. Check sandbox/filesystem access; signing in again will not fix a local access denial.'
        ) from None
    except OSError:
        raise GoogleError(
            'Could not run local gcloud. Check executable and filesystem access before attempting sign-in.'
        ) from None
    except subprocess.TimeoutExpired:
        raise GoogleError(
            'Local gcloud token lookup timed out. Check connectivity and the local CLI before retrying; no Google write was sent.'
        ) from None
    diagnostic = (result.stderr or '')[:8192].lower()
    if (
        result.returncode
        and any(
            k in diagnostic
            for k in (
                'permission denied',
                'operation not permitted',
                'unable to open database file',
            )
        )
        and any(k in diagnostic for k in ('credentials.db', 'gcloud', 'sqlite'))
    ):
        raise GoogleError(
            'Local gcloud credential access was denied. Check sandbox/filesystem access to the gcloud configuration; do not repeat login to fix a local access denial.'
        )
    value = result.stdout.strip()
    if result.returncode or not value or any(c.isspace() for c in value):
        raise GoogleError('Google authentication is unavailable. ' + SIGN_IN)
    return value


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, account=None):
        self.account = account
        self.opener = urllib.request.build_opener(NoRedirect())

    def authorize(self):
        """Fetch the access token once per process and keep it only in memory."""
        value = getattr(self, '_token', None)
        if not value:
            value = token(getattr(self, 'account', None))
            self._token = value
        return value

    def request(self, url, *, method='GET', body=None, mime='application/json', binary=False):
        # Tokens may only go to these fixed Google APIs; never follow a redirect.
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != 'https' or parsed.netloc not in (
            'www.googleapis.com',
            'docs.googleapis.com',
        ):
            raise GoogleError('Unsupported Google API destination.')
        payload = encoded(body) if isinstance(body, dict) else body
        # Only idempotent reads are repeated. A write is sent exactly once.
        delays = READ_RETRY_DELAYS if method == 'GET' else ()
        for delay in (*delays, None):
            try:
                return self._send(url, method, payload, mime, binary)
            except GoogleError as exc:
                if delay is None or not exc.transient:
                    raise
                getattr(self, 'sleep', time.sleep)(delay)

    def _send(self, url, method, payload, mime, binary):
        req = urllib.request.Request(
            url,
            data=payload,
            method=method,
            headers={'Authorization': 'Bearer ' + self.authorize(), 'Content-Type': mime},
        )
        try:
            with self.opener.open(req, timeout=60) as response:
                data = response.read(LIMIT + 1)
            if len(data) > LIMIT:
                raise GoogleError('Google response exceeded the transfer size limit.')
            if binary:
                return data
            value = json.loads(data)
            if not isinstance(value, dict):
                raise GoogleError(
                    'Google returned an unexpected response; reconcile any write before retrying.'
                )
            return value
        except urllib.error.HTTPError as exc:
            raise self._http_error(exc, method) from None
        except (OSError, ValueError):
            if method == 'GET':
                raise GoogleError(
                    'Google could not be reached or returned an invalid response. '
                    'Nothing was written; this read is safe to repeat.',
                    network=True,
                ) from None
            raise GoogleError(
                'Google response was unavailable or invalid. A write may have completed; '
                'reconcile before retrying.',
                network=True,
            ) from None

    def _http_error(self, exc, method):
        """Parse only bounded diagnostics and expose fixed allowlisted labels."""
        error = {}
        try:
            payload = json.loads(exc.read(16384))
            if isinstance(payload, dict) and isinstance(payload.get('error'), dict):
                error = payload['error']
        except (OSError, ValueError):
            pass
        allowed = {
            'PERMISSION_DENIED',
            'UNAUTHENTICATED',
            'INVALID_ARGUMENT',
            'ACCESS_TOKEN_SCOPE_INSUFFICIENT',
            'ACCESS_TOKEN_EXPIRED',
            'insufficientPermissions',
            'insufficientFilePermissions',
            'SERVICE_DISABLED',
            'accessNotConfigured',
            'RATE_LIMIT_EXCEEDED',
            'rateLimitExceeded',
            'userRateLimitExceeded',
        }
        labels = set()
        if isinstance(error.get('status'), str) and error['status'] in allowed:
            labels.add(error['status'])
        rows = []
        for group in ('details', 'errors'):
            if isinstance(error.get(group, []), list):
                rows.extend(error.get(group, []))
        for row in rows:
            reason = row.get('reason') if isinstance(row, dict) else None
            if isinstance(reason, str) and reason in allowed:
                labels.add(reason)
        detail = error.get('message', '')
        detail = detail.lower() if isinstance(detail, str) else ''
        if labels & {'ACCESS_TOKEN_SCOPE_INSUFFICIENT', 'insufficientPermissions'}:
            message = (
                'Google authorization lacks required OAuth scopes. With explicit setup approval, reauthorize '
                'the intended account with gcloud auth login --enable-gdrive-access --force --no-activate. '
                'Do not switch to comments or broaden consent automatically.'
            )
        elif exc.code == 401:
            self._token = None
            message = 'Google sign-in expired. ' + SIGN_IN
        elif exc.code == 404:
            who = getattr(self, 'account', None) or 'the signed-in Google account'
            message = (
                'Google could not find this file, or it is not shared with '
                + who
                + '. Check the link '
                'and the Doc’s sharing; nothing was written.'
            )
        elif exc.code == 403:
            message = (
                'Google denied this operation. Check file permission, API access and organization policy. '
                'This alone does not establish review unavailability.'
            )
        elif exc.code in (400, 409, 412) and method != 'GET':
            message = 'Google rejected the write. Reread the document and revision before making another request.'
        elif exc.code == 429:
            message = 'Google is limiting requests right now (HTTP 429). Wait a moment before trying again.'
        else:
            message = 'Google request failed (HTTP ' + str(exc.code) + ').'
        if labels:
            message += ' [' + ', '.join(sorted(labels)) + ']'
        unknown_reason = any(
            isinstance(row, dict) and row.get('reason') not in allowed for row in rows
        )
        unsupported = (
            exc.code in (400, 403)
            and not (labels - {'INVALID_ARGUMENT', 'PERMISSION_DENIED'})
            and not unknown_reason
            and any(k in detail for k in ('writemode', 'commentsviewmode', 'insertcomment'))
            and any(
                k in detail
                for k in ('unknown name', 'not supported', 'unsupported', 'not available')
            )
        )
        return GoogleError(message, status=exc.code, review_unavailable=unsupported, labels=labels)

    def drive(self, path, **query):
        return self.request(DRIVE + path + '?' + urllib.parse.urlencode(query))

    def check(self):
        about = self.drive('about', fields='importFormats')
        formats = about.get('importFormats', {})
        return {
            'status': 'drive-read',
            'html_import_advertised': DOC_MIME in formats.get('text/html', []),
            'docx_import_advertised': DOC_MIME in formats.get(DOCX, []),
            'native_docs': 'unverified',
            'write': 'unverified',
        }

    def metadata(self, file_id):
        return self.drive(
            'files/' + identifier(file_id),
            supportsAllDrives='true',
            fields='id,name,mimeType,parents,webViewLink,modifiedTime,version,trashed,capabilities(canEdit,canAddChildren,canComment)',
        )

    def permissions(self, file_id):
        result = []
        page = None
        for _ in range(100):
            query = {
                'supportsAllDrives': 'true',
                'pageSize': 100,
                'fields': 'nextPageToken,permissions(id,type,role,emailAddress,domain,allowFileDiscovery,permissionDetails)',
            }
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
        return {
            **snapshot,
            'audience_sha256': digest(encoded(snapshot)),
            'can_add_children': meta.get('capabilities', {}).get('canAddChildren', False),
        }

    def native_read(self, file_id, inline=False, comments=False, accepted_preview=False):
        if comments and (not inline or accepted_preview):
            raise GoogleError('Thread reads require inline suggestions.')
        mode = (
            'PREVIEW_SUGGESTIONS_ACCEPTED'
            if accepted_preview
            else 'SUGGESTIONS_INLINE'
            if inline
            else 'PREVIEW_WITHOUT_SUGGESTIONS'
        )
        params = {'includeTabsContent': 'true', 'suggestionsViewMode': mode}
        if comments:
            params['commentsViewMode'] = 'COMMENTS_VIEW_MODE_INCLUDED'
        return self.request(DOCS + identifier(file_id) + '?' + urllib.parse.urlencode(params))

    def native_review_update(self, file_id, revision, requests):
        if not isinstance(revision, str) or not revision.strip() or not requests:
            raise GoogleError('A fresh revision and selected review operations are required.')
        return self.request(
            DOCS + identifier(file_id) + ':batchUpdate',
            method='POST',
            body={
                'writeControl': {'requiredRevisionId': revision, 'writeMode': 'SUGGEST'},
                'requests': requests,
            },
        )

    def native_comments_update(self, file_id, revision, requests):
        if not revision or not requests or any(set(r) != {'insertComment'} for r in requests):
            raise GoogleError('A fresh revision and comment-only requests are required.')
        return self.request(
            DOCS + identifier(file_id) + ':batchUpdate',
            method='POST',
            body={'writeControl': {'requiredRevisionId': revision}, 'requests': requests},
        )

    def review_comments(self, file_id):
        result = []
        page = None
        for _ in range(100):
            query = {
                'fields': 'nextPageToken,comments(id,content,quotedFileContent,resolved,deleted,author(me))',
                'pageSize': 100,
                'includeDeleted': 'true',
            }
            if page:
                query['pageToken'] = page
            response = self.drive('files/' + identifier(file_id) + '/comments', **query)
            result.extend(response.get('comments', []))
            page = response.get('nextPageToken')
            if not page:
                return result
        raise GoogleError('Comment listing was incomplete; no review action performed.')

    def create_review_comment(self, file_id, content, quote):
        return self.request(
            DRIVE
            + 'files/'
            + identifier(file_id)
            + '/comments?fields=id,content,quotedFileContent,resolved,author(me)',
            method='POST',
            body={
                'content': content,
                'quotedFileContent': {'mimeType': 'text/plain', 'value': quote},
            },
        )

    def resolve_review_comment(self, file_id, comment_id):
        return self.request(
            DRIVE
            + 'files/'
            + identifier(file_id)
            + '/comments/'
            + identifier(comment_id)
            + '/replies?fields=id,action',
            method='POST',
            body={
                'action': 'resolve',
                'content': 'Selected edits applied and verified by Blog Studio.',
            },
        )

    def resolve_native_comment(self, file_id, comment_id, revision):
        return self.request(
            DOCS + identifier(file_id) + ':batchUpdate',
            method='POST',
            body={
                'writeControl': {'requiredRevisionId': revision},
                'requests': [
                    {
                        'addCommentReply': {
                            'commentId': comment_id,
                            'post': {'commentAction': 'RESOLVE'},
                        }
                    }
                ],
            },
        )

    def native_update(self, file_id, revision, requests):
        if not isinstance(revision, str) or not revision.strip():
            raise GoogleError('A fresh requiredRevisionId is mandatory.')
        if (
            not isinstance(requests, list)
            or not requests
            or not all(isinstance(r, dict) for r in requests)
        ):
            raise GoogleError('Provide a nonempty JSON array of selected native edits.')
        response = self.request(
            DOCS + identifier(file_id) + ':batchUpdate',
            method='POST',
            body={'writeControl': {'requiredRevisionId': revision}, 'requests': requests},
        )
        return {
            'status': 'written-unverified',
            'document_id': file_id,
            'write_control': response.get('writeControl'),
            'next_step': 'Read all affected tabs and verify before google confirm.',
        }

    def locate(self, operation):
        if not re.fullmatch(r'[0-9a-f]{32}', operation):
            raise GoogleError('Use the original 32-character operation ID.')
        result = self.drive(
            'files',
            q="trashed = false and appProperties has { key='blogStudioOperation' and value='"
            + operation
            + "' }",
            spaces='drive',
            pageSize=100,
            includeItemsFromAllDrives='true',
            supportsAllDrives='true',
            fields='nextPageToken,files(id,name,mimeType,webViewLink,parents)',
        )
        return {
            'status': 'reconcile-only',
            'operation': operation,
            'matches': result.get('files', []),
            'incomplete': bool(result.get('nextPageToken')),
            'next_step': 'Inspect matches; an empty result does not authorize repeating an uncertain upload.',
        }

    def export(self, file_id, format):
        meta = self.metadata(file_id)
        if meta.get('mimeType') != DOC_MIME:
            raise GoogleError('The selected file is not a native Google Doc.')
        mime = {'txt': 'text/plain', 'md': 'text/markdown', 'pdf': 'application/pdf', 'docx': DOCX}[
            format
        ]
        data = self.request(
            DRIVE
            + 'files/'
            + identifier(file_id)
            + '/export?'
            + urllib.parse.urlencode({'mimeType': mime}),
            binary=True,
        )
        if format == 'pdf' and not data.startswith(b'%PDF-'):
            raise GoogleError('Export was not a PDF.')
        if format == 'docx':
            validate_docx(data)
        if format in ('txt', 'md'):
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
            raise GoogleError(
                'Import accepts HTML, plain text or DOCX. Convert Markdown deliberately before upload.'
            )
        data = path.read_bytes()
        if mime == DOCX:
            validate_docx(data)
        else:
            data.decode('utf-8')
        if folder_id:
            observed = self.audience(folder_id)
            if (
                not observed['can_add_children']
                or not audience_sha256
                or observed['audience_sha256'] != audience_sha256
            ):
                raise GoogleError(
                    'Review the destination audience and pass its current audience_sha256 before uploading.'
                )
        # Sign-in problems surface here, before a receipt exists, so they never look like an uncertain upload.
        self.authorize()
        metadata = {'name': title, 'mimeType': DOC_MIME}
        if folder_id:
            metadata['parents'] = [identifier(folder_id)]
        operation = uuid.uuid4().hex
        metadata['appProperties'] = {'blogStudioOperation': operation}
        # Reserve before POST. Existing receipts ALWAYS stop another upload, even
        # after a crash or ambiguous network result. Recovery is read-only.
        receipt = {
            'schema': 1,
            'operation': operation,
            'status': 'submitting',
            'content_sha256': digest(data),
            'folder_id': folder_id,
        }
        state_path = Path(state_path)
        write_new(state_path, encoded(receipt))
        uncertain = (
            'Upload outcome needs reconciliation. Keep receipt '
            + str(state_path)
            + '; run reconcile --operation '
            + operation
            + '. Do not repeat import with a new receipt.'
        )
        boundary = 'blogstudio_' + uuid.uuid4().hex
        body = (
            ('--' + boundary + '\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n').encode()
            + encoded(metadata)
            + ('\r\n--' + boundary + '\r\nContent-Type: ' + mime + '\r\n\r\n').encode()
            + data
            + ('\r\n--' + boundary + '--\r\n').encode()
        )
        try:
            response = self.request(
                UPLOAD
                + '?'
                + urllib.parse.urlencode(
                    {
                        'uploadType': 'multipart',
                        'supportsAllDrives': 'true',
                        'fields': 'id,mimeType,webViewLink,parents',
                    }
                ),
                method='POST',
                body=body,
                mime='multipart/related; boundary=' + boundary,
            )
            if response.get('mimeType') != DOC_MIME or not response.get('id'):
                raise GoogleError(
                    'Google did not confirm a native Doc. Reconcile the operation before retrying.'
                )
            receipt.update(
                status='created-unverified',
                document_id=identifier(response['id']),
                url='https://docs.google.com/document/d/' + identifier(response['id']) + '/edit',
            )
            # Preserve the known remote ID even if later readback fails.
            temp = state_path.with_name(state_path.name + '.' + uuid.uuid4().hex)
            try:
                write_new(temp, encoded(receipt))
                os.replace(temp, state_path)
            finally:
                temp.unlink(missing_ok=True)
            return {
                **receipt,
                'next_step': 'Read back actual content, structure, folder and access before confirming the handoff.',
            }
        except GoogleError as exc:
            if exc.definite and not receipt.get('document_id'):
                # Google refused the request, so nothing was created and the reservation can go.
                state_path.unlink(missing_ok=True)
                raise GoogleError(
                    'Google refused the upload, so no document was created and the receipt was released. '
                    + str(exc),
                    status=exc.status,
                    labels=exc.labels,
                ) from None
            raise GoogleError(uncertain) from None
        except OSError:
            raise GoogleError(uncertain) from None


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


def workspace(root):
    """Resolve an initialized writing workspace; local Google state lives nowhere else."""
    path = Path(root).expanduser()
    if not path.is_absolute():
        raise GoogleError('Use an absolute writing workspace path.')
    if not (path / 'studio.json').is_file():
        raise GoogleError('Choose an initialized writing workspace with --root.')
    return path.resolve()


def staging_root(root, create=False):
    """Machine-local folder for captures, plans, findings and receipts. Never shared with a Hub."""
    path = workspace(root) / STAGING
    if path.is_symlink():
        raise GoogleError('Google staging must be a regular folder.')
    if create:
        path.mkdir(mode=0o700, exist_ok=True)
        purge_staging(root, older_than=STAGING_MAX_AGE)
    return path


def staging_path(root, prefix, suffix=''):
    """A new private staging path. The caller creates the file or folder."""
    stamp = time.strftime('%Y%m%dT%H%M%S', time.gmtime())
    return staging_root(root, create=True) / (
        prefix + '-' + stamp + '-' + uuid.uuid4().hex[:8] + suffix
    )


def staged(root, path):
    """True when path lies inside this workspace's staging folder."""
    try:
        folder = staging_root(root).resolve()
        target = Path(path).resolve()
    except (GoogleError, OSError):
        return False
    return target != folder and target.is_relative_to(folder)


def _remove(entry):
    if entry.is_symlink() or entry.is_file():
        entry.unlink(missing_ok=True)
    elif entry.is_dir():
        shutil.rmtree(entry)


def discard(root, path):
    """Remove one staged file or folder. Anything outside staging is left alone."""
    if not path or not staged(root, path):
        return False
    _remove(Path(path))
    return True


def purge_staging(root, older_than=None):
    """Remove staged Google files; older_than limits removal to entries of at least that age in seconds."""
    folder = workspace(root) / STAGING
    if folder.is_symlink() or not folder.is_dir():
        return 0
    removed = 0
    now = time.time()
    for entry in sorted(folder.iterdir()):
        if older_than is not None and now - entry.lstat().st_mtime < older_than:
            continue
        _remove(entry)
        removed += 1
    return removed


def saved_account(root):
    """The Google account remembered for this workspace, or None."""
    try:
        path = workspace(root) / ACCOUNT_FILE
    except GoogleError:
        return None
    if path.is_symlink() or not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    account = value.get('account') if isinstance(value, dict) else None
    return account if isinstance(account, str) and EMAIL.fullmatch(account) else None


def remember_account(root, account):
    """Record which signed-in Google account this workspace uses. Stores the email only, never a credential."""
    if not isinstance(account, str) or len(account) > 254 or not EMAIL.fullmatch(account):
        raise GoogleError('Use the email address of the Google account signed in through gcloud.')
    path = workspace(root) / ACCOUNT_FILE
    if path.is_symlink():
        raise GoogleError('The saved Google account must be a regular file.')
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex)
    try:
        write_new(temp, encoded({'schema': 1, 'account': account}))
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
    return account


def forget_account(root):
    path = workspace(root) / ACCOUNT_FILE
    existed = path.is_file() and not path.is_symlink()
    if existed:
        path.unlink()
    return existed


def account_for(root=None, account=None):
    """An explicit account wins; otherwise the workspace's remembered account; otherwise gcloud's active one."""
    return account or (saved_account(root) if root else None)


def linked_documents(root):
    """IDs of the Google Docs that blogs in this workspace are linked to."""
    import studio

    base = workspace(root)
    folder = studio.inside(base, 'articles')
    found = set()
    if not folder.is_dir():
        return found
    for entry in sorted(folder.iterdir()):
        if not entry.is_dir():
            continue
        try:
            _, record = studio.item(base, 'articles', entry.name)
        except (ValueError, OSError):
            continue
        google = record.get('google', {}) if isinstance(record, dict) else {}
        baselines = google.get('baselines', {}) if isinstance(google, dict) else {}
        for baseline in baselines.values():
            document_id = (
                baseline.get('document', {}).get('document_id')
                if isinstance(baseline, dict)
                else None
            )
            if isinstance(document_id, str):
                found.add(document_id)
    return found


def require_linked(root, file_id, first_handoff=False):
    """Writes go only to Docs linked in the workspace, or to an explicitly declared first handoff."""
    if first_handoff:
        return
    if root is None:
        raise GoogleError(
            'Writes are limited to Google Docs linked to a blog. Pass --root <workspace>; use '
            '--first-handoff only for the explicit first handoff of a new editing copy.'
        )
    from team_workspace import before, space, guard
    import studio

    if space(Path(root)):
        before(Path(root))
        for session in studio.inside(Path(root), 'articles').glob('*/session.json'):
            record = studio.read_json(session)
            baselines = record.get('google', {}).get('baselines', {})
            if any(
                baseline.get('document', {}).get('document_id') == file_id
                for baseline in baselines.values()
            ):
                guard(Path(root), session.parent.name)
    if identifier(file_id) not in linked_documents(root):
        raise GoogleError(
            'This Google Doc is not linked to a blog in this workspace, so it will not be changed. '
            'Start from the Doc or confirm its handoff first; use --first-handoff only for the '
            'explicit first handoff of a new editing copy.'
        )


def active_account():
    """gcloud's active account, read from local configuration only."""
    try:
        result = subprocess.run(
            [gcloud(), 'config', 'get-value', 'account', '--quiet'],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = result.stdout.strip()
    return value if result.returncode == 0 and EMAIL.fullmatch(value) else None


def login(account=None, activate=False):
    """Interactive browser consent. gcloud's active account changes only when asked or when none exists."""
    command = [gcloud(), 'auth', 'login']
    if account:
        if len(account) > 254 or not EMAIL.fullmatch(account):
            raise GoogleError('Use the email address of the Google account to sign in.')
        command.append(account)
    elif not activate:
        current = active_account()
        if current:
            raise GoogleError(
                'gcloud is already signed in as ' + current + '. Name the Google Docs account '
                '(login --account you@example.com) to add it without switching, or pass --activate '
                'to make this sign-in gcloud’s active account.'
            )
    command += ['--enable-gdrive-access', '--force']
    if account and not activate:
        command.append('--no-activate')
    # Browser consent is interactive. No credentials go through JSON output.
    if subprocess.run(command).returncode:
        raise GoogleError('Google sign-in did not complete.')


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--account',
        help='Use this already-authorized gcloud account without switching the active account.',
    )
    parser.add_argument(
        '--root',
        type=Path,
        help='Writing workspace: its remembered Google account, private staging '
        'folder, and the linked Docs that writes are limited to.',
    )
    actions = parser.add_subparsers(dest='action', required=True)
    actions.add_parser('check')
    sign_in = actions.add_parser('login')
    sign_in.add_argument(
        '--activate', action='store_true', help="Also make this sign-in gcloud's active account."
    )
    remembered = actions.add_parser(
        'account', help='Show, set or clear the Google account remembered for --root.'
    )
    choice = remembered.add_mutually_exclusive_group()
    choice.add_argument('--set', dest='set_account', metavar='EMAIL')
    choice.add_argument('--clear', action='store_true')
    staging = actions.add_parser(
        'staging', help='Inspect or clear staged captures, plans, findings and receipts.'
    )
    staging.add_argument('--clear', action='store_true')
    for name in ('metadata', 'audience', 'read', 'export', 'update'):
        sub = actions.add_parser(name)
        sub.add_argument('--file-id', required=True)
        if name == 'read':
            sub.add_argument(
                '--output',
                type=Path,
                help='New local JSON file; defaults to the workspace staging folder.',
            )
        if name == 'export':
            sub.add_argument('--output', type=Path, required=True)
            sub.add_argument('--format', choices=('txt', 'md', 'pdf', 'docx'), required=True)
        if name == 'update':
            sub.add_argument('--revision', required=True)
            sub.add_argument('--requests', type=Path, required=True)
            sub.add_argument(
                '--first-handoff',
                action='store_true',
                help='Explicit first handoff of a new editing copy that is not linked yet.',
            )
    sub = actions.add_parser('import')
    sub.add_argument('--file', type=Path, required=True)
    sub.add_argument('--title', required=True)
    sub.add_argument(
        '--receipt',
        type=Path,
        help='New private receipt; defaults to the workspace staging folder.',
    )
    sub.add_argument('--folder-id')
    sub.add_argument('--audience-sha256')
    actions.add_parser('reconcile').add_argument('--operation', required=True)
    return parser


def staged_default(args, value, prefix, suffix):
    """Use the caller's path, or a new one in the workspace staging folder."""
    if value:
        return value
    if not args.root:
        raise GoogleError(
            'Pass --root <workspace> so this file goes to its private staging folder, or name a path.'
        )
    return staging_path(args.root, prefix, suffix)


def import_receipt(args):
    """One staged receipt per file, title and folder, so repeating the same import is always stopped."""
    if not args.root:
        raise GoogleError(
            'Pass --root <workspace> so the receipt goes to its private staging folder, or name a path.'
        )
    identity = digest(args.file.read_bytes() + encoded([args.title, args.folder_id]))
    return staging_root(args.root, create=True) / ('import-receipt-' + identity[:16] + '.json')


def run(args):
    if args.action == 'account':
        if not args.root:
            raise GoogleError(
                'Pass --root <workspace>; the Google account is remembered per workspace.'
            )
        if args.set_account:
            return {
                'status': 'account-saved',
                'account': remember_account(args.root, args.set_account),
            }
        if args.clear:
            return {'status': 'account-cleared', 'removed': forget_account(args.root)}
        saved = saved_account(args.root)
        return {
            'status': 'account',
            'account': saved,
            'source': 'workspace'
            if saved
            else 'gcloud active account (none saved for this workspace)',
        }
    if args.action == 'staging':
        if not args.root:
            raise GoogleError('Pass --root <workspace>; staging belongs to one workspace.')
        if args.clear:
            return {'status': 'staging-cleared', 'removed': purge_staging(args.root)}
        folder = staging_root(args.root)
        entries = sorted(e.name for e in folder.iterdir()) if folder.is_dir() else []
        return {'status': 'staging', 'folder': str(folder), 'entries': entries}
    account = account_for(args.root, args.account)
    client = Client(account)
    if args.action == 'login':
        login(args.account, args.activate)
        result = client.check()
        if args.account and args.root:
            result['remembered_account'] = remember_account(args.root, args.account)
        return result
    if args.action == 'check':
        return {**client.check(), 'account': account or 'gcloud active account'}
    if args.action == 'metadata':
        return client.metadata(args.file_id)
    if args.action == 'audience':
        return client.audience(args.file_id)
    if args.action == 'read':
        output = staged_default(args, args.output, 'native', '.json')
        write_new(output, encoded(client.native_read(args.file_id)))
        return {'status': 'native-read', 'file': str(output), 'structure_verified': False}
    if args.action == 'export':
        write_new(args.output, client.export(args.file_id, args.format))
        return {
            'status': 'exported',
            'file': str(args.output),
            'format': args.format,
            'next_step': 'Inspect the actual export. Plain text does not prove accepted suggestions, '
            'all-tab coverage or native fidelity.',
        }
    if args.action == 'import':
        receipt = args.receipt or import_receipt(args)
        try:
            return client.import_new(
                args.file, args.title, receipt, args.folder_id, args.audience_sha256
            )
        except FileExistsError:
            raise GoogleError(
                'This import was already attempted (receipt ' + str(receipt) + '). Reconcile that '
                'attempt first; an existing receipt always stops another upload.'
            ) from None
    if args.action == 'reconcile':
        return client.locate(args.operation)
    require_linked(args.root, args.file_id, args.first_handoff)
    return client.native_update(args.file_id, args.revision, json.loads(args.requests.read_text()))


def main():
    args = build_parser().parse_args()
    try:
        print(json.dumps(run(args), indent=2))
        return 0
    except GoogleError as exc:
        print(json.dumps({'status': 'unavailable', 'error': str(exc)}), file=sys.stderr)
    except (OSError, ValueError):
        print(
            json.dumps(
                {
                    'status': 'unavailable',
                    'error': 'Local input or output failed: check the file paths and '
                    'JSON, and use a new output path. Nothing was sent to Google by this step.',
                }
            ),
            file=sys.stderr,
        )
    return 1


if __name__ == '__main__':
    sys.exit(main())
