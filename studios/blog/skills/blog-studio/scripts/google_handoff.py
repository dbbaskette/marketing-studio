"""One explicitly requested, private Google Doc of an approved Blog Studio draft.

The caller holds the workspace lock. A durable reservation names one transfer and one
upload receipt; a crash or an uncertain response never permits a second import.
"""

from pathlib import Path

import blog_runner
import editorial
import google_drive as drive
import google_roundtrip as roundtrip
import google_workflow as workflow
import studio

NOT_SIGNED_IN = (
    'Google is not signed in on this computer. See Status → Check this computer, then try again.'
)
NOT_FINISHED = 'Finish the blog first; its approved draft is what goes to Google.'
RECONCILING = 'The last upload is being checked. Wait for it, then look at the blog again.'


class Conflict(ValueError):
    """A finished-draft handoff cannot proceed in its current state."""


def open_as_doc(root, ident, client=None, capture=None):
    directory, record, run = blog_runner.load(root, ident)
    linked = editorial.doc_link(record)
    google = workflow.state(record)
    if linked:
        return {
            'id': ident,
            'url': linked['url'],
            'transfer': (google['baselines'].get('draft') or {}).get('transfer'),
        }
    if not drive.active_account():
        raise Conflict(NOT_SIGNED_IN)
    if not blog_runner.survey(root, ident)['complete'] or not (directory / 'DRAFT.md').is_file():
        raise Conflict(NOT_FINISHED)
    client = client or drive.Client(drive.account_for(root))
    capture = capture or roundtrip.capture
    pending = google.get('page_handoff')
    if not pending:
        prepared = workflow.prepare_transfer(root, ident, 'draft', True)
        directory, record = studio.item(root, 'articles', ident)
        google = workflow.state(record)
        pending = {
            'transfer': prepared['transfer'],
            'receipt': drive.staging_path(root, 'handoff-' + ident, '.json').name,
        }
        google['page_handoff'] = pending
        studio.persist(directory, 'articles', record)
        try:
            client.import_new(
                Path(prepared['file']),
                record['title'],
                drive.staging_root(root) / pending['receipt'],
            )
        except drive.GoogleError:
            if not (drive.staging_root(root) / pending['receipt']).exists():
                google.pop('page_handoff', None)
                studio.persist(directory, 'articles', record)
            raise
    receipt_path = drive.staging_root(root) / pending['receipt']
    if (
        not drive.staged(root, receipt_path)
        or receipt_path.is_symlink()
        or not receipt_path.is_file()
    ):
        raise Conflict(RECONCILING)
    receipt = studio.read_json(receipt_path)
    document = receipt.get('document_id')
    if not document:
        found = client.locate(receipt['operation'])
        matches = found.get('matches') or []
        if (
            found.get('incomplete')
            or len(matches) != 1
            or matches[0].get('mimeType') != drive.DOC_MIME
        ):
            raise Conflict(RECONCILING)
        document = drive.identifier(matches[0]['id'])
        receipt.update(
            status='created-unverified',
            document_id=document,
            url='https://docs.google.com/document/d/' + document + '/edit',
        )
        studio.write_json(receipt_path, receipt)
    transfer = pending['transfer']
    saved = google['transfers'][transfer]
    # The frozen copy must still be the approved local draft, including after a failed readback.
    if studio.digest((directory / 'DRAFT.md').read_bytes()) != saved['local_sha256']:
        raise Conflict(
            'The approved draft changed after this upload. Reconcile the existing Doc before sending again.'
        )
    snapshot = drive.staging_path(root, 'handoff-readback-' + ident)
    capture(client, document, None, snapshot)
    observation = studio.read_json(snapshot / 'observation.json')
    body = (snapshot / 'document.md').read_text(encoding='utf-8')
    # Only the native renderer preserves the structural Markdown we can verify automatically.
    if observation.get('projection') != roundtrip.PROJECTION or not workflow.same_text(
        directory, transfer, saved, observation, body
    ):
        raise Conflict(
            'The Google Doc readback does not match the approved draft. The existing Doc is kept; no second Doc is made.'
        )
    workflow.formatted_snapshot(snapshot, observation, body)
    if not blog_runner.survey(root, ident)['complete']:
        raise Conflict(NOT_FINISHED)
    observation['structure_verified'] = True
    studio.write_json(snapshot / 'observation.json', observation)
    workflow.confirm_transfer(root, ident, 'draft', transfer, snapshot)
    directory, record = studio.item(root, 'articles', ident)
    workflow.state(record).pop('page_handoff', None)
    studio.persist(directory, 'articles', record)
    return {'id': ident, 'url': receipt['url'], 'transfer': transfer}
