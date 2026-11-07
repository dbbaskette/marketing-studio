"""Explicit review copies for view-only Docs; local receipts survive retries/restarts.

The management caller holds the workspace lock. No original document or sharing
is changed. An uncertain copy is reconciled by its private operation tag, never
repeated. Receipts live outside the Hub and the expiring capture cache.
"""

import json
import os
from pathlib import Path
import re
import uuid

import google_drive as drive
import google_roundtrip as roundtrip


def receipt_path(root, key):
    if not isinstance(key, str) or not re.fullmatch('[a-f0-9]{64}', key):
        raise ValueError('Check the Google Doc’s access before making a copy.')
    private = Path(os.environ.get('BLOG_STUDIO_DATA', '~/.local/share/blog-studio')).expanduser()
    scope = drive.digest(str(drive.workspace(root)).encode())
    folder = private / 'google-copies' / scope
    for path in (private, private / 'google-copies', folder):
        if path.is_symlink():
            raise ValueError('Google copy receipts must use regular local folders.')
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = folder / (key + '.json')
    if path.is_symlink():
        raise ValueError('The Google copy receipt must be a regular local file.')
    return path


def save(path, value):
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex)
    try:
        drive.write_new(temporary, drive.encoded(value))
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def offer(root, client, file_id, tab_id, metadata):
    """Return a warning before any editor-only read. No Google write occurs here."""
    capabilities = metadata.get('capabilities', {})
    if capabilities.get('canEdit') is not False:
        return None
    if metadata.get('mimeType') != drive.DOC_MIME or metadata.get('trashed'):
        raise drive.GoogleError('Choose an available native Google Doc to review.')
    # Ask the same authenticated client, so the displayed identity is the account
    # whose permissions were checked, even when gcloud's active account changes.
    account = client.drive('about', fields='user(emailAddress)').get('user', {}).get('emailAddress')
    if not isinstance(account, str) or not drive.EMAIL.fullmatch(account):
        raise drive.GoogleError(
            'Google did not identify the signed-in account. Check sign-in before copying.'
        )
    key = drive.digest(drive.encoded([file_id, tab_id, account]))
    path = receipt_path(root, key)
    receipt = json.loads(path.read_text()) if path.exists() else None
    pending = bool(receipt and receipt.get('status') in ('submitting', 'created'))
    can_copy = capabilities.get('canCopy') is True
    if can_copy and not pending:
        selected = None
        if tab_id:
            document = client.native_read(file_id)
            listed = roundtrip.tabs(document)
            identities = [tab.get('tabProperties', {}).get('tabId') for tab in listed]
            if identities.count(tab_id) != 1:
                raise ValueError(
                    'The selected tab is missing or ambiguous. Copy its current address again.'
                )
            index = identities.index(tab_id)
            selected = {
                'index': index,
                'titles': [tab['tabProperties'].get('title', '') for tab in listed],
            }
        receipt = {
            'schema': 1,
            'source': file_id,
            'tab': selected,
            'source_version': metadata.get('version'),
            'account': account,
            'operation': uuid.uuid4().hex,
            'status': 'offered',
            'title': (str(metadata.get('name') or 'Google Doc')[:470] + ' — Blog Studio review'),
        }
        save(path, receipt)
    return {
        'status': 'view-only',
        'access': 'comment-only' if capabilities.get('canComment') else 'view-only',
        'account': account,
        'title': str(metadata.get('name') or 'Google Doc'),
        'can_copy': can_copy or pending,
        'copy': key if can_copy or pending else None,
        'copy_pending': pending,
        'selected_tab': bool(tab_id),
    }


def copy(root, data):
    if (
        not isinstance(data, dict)
        or set(data) != {'copy', 'confirmed'}
        or data['confirmed'] is not True
    ):
        raise ValueError('Confirm creating a review copy in My Drive first.')
    path = receipt_path(root, data['copy'])
    if not path.is_file():
        raise ValueError('Check the Google Doc’s access again before copying.')
    receipt = json.loads(path.read_text())
    account = drive.account_for(root) or drive.active_account()
    if not account or account != receipt['account']:
        raise ValueError(
            'The Google account changed. Check access again to review the destination account.'
        )
    client = drive.Client(account)
    if receipt['status'] == 'offered':
        source = client.metadata(receipt['source'])
        if source.get('mimeType') != drive.DOC_MIME or source.get('trashed'):
            raise drive.GoogleError('The source must be an available native Google Doc.')
        if source.get('capabilities', {}).get('canCopy') is not True:
            raise drive.GoogleError(
                'Google does not allow this account to copy the Doc. Ask its owner for access.'
            )
        if source.get('version') != receipt['source_version']:
            raise drive.GoogleError(
                'The source Doc changed. Check access again before making its copy.'
            )
        parent = client.drive('files/root', fields='id')['id']
        # Token/auth failures happen before reservation. The request itself is
        # never automatically retried, including after a crash or a lost reply.
        client.authorize()
        receipt.update(status='submitting', parent=drive.identifier(parent))
        save(path, receipt)
        try:
            made = client.copy_document(
                receipt['source'], receipt['title'], parent, receipt['operation']
            )
            receipt['document_id'] = drive.identifier(made.get('id', ''))
            receipt['status'] = 'created'
            save(path, receipt)
        except drive.GoogleError as error:
            if error.definite and not receipt.get('document_id'):
                receipt['status'] = 'offered'
                save(path, receipt)
                raise drive.GoogleError(
                    'Google refused the copy; no copy was created. ' + str(error)
                ) from None
            raise drive.GoogleError(
                'Google has not confirmed the copy. Choose Check copy to look for it; no second copy will be made.'
            ) from None
    if not receipt.get('document_id'):
        matches = client.locate(receipt['operation']).get('matches', [])
        if len(matches) != 1:
            raise drive.GoogleError(
                'The copy is not confirmed yet. Choose Check copy again later; no second copy will be made.'
            )
        receipt.update(document_id=drive.identifier(matches[0]['id']), status='created')
        save(path, receipt)
    file_id = receipt['document_id']
    details = client.copy_details(file_id)
    if (
        details.get('id') != file_id
        or details.get('mimeType') != drive.DOC_MIME
        or details.get('trashed')
        or details.get('parents') != [receipt['parent']]
        or details.get('appProperties', {}).get('blogStudioOperation') != receipt['operation']
        or details.get('capabilities', {}).get('canEdit') is not True
    ):
        raise drive.GoogleError(
            'The copy exists, but its My Drive location and edit access could not be verified. No second copy was made.'
        )
    link = 'https://docs.google.com/document/d/' + file_id + '/edit'
    if receipt['tab']:
        listed = roundtrip.tabs(client.native_read(file_id))
        if [tab['tabProperties'].get('title', '') for tab in listed] != receipt['tab']['titles']:
            raise drive.GoogleError(
                'The copy’s tabs changed. Open the copy in My Drive and select the tab to review.'
            )
        link += '?tab=' + listed[receipt['tab']['index']]['tabProperties']['tabId']
    return {'status': 'copied', 'url': link, 'account': account, 'title': receipt['title']}
