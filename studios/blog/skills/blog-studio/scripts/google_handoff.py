"""One explicitly requested, private Google Doc of an approved Blog Studio draft, or of a
draft on the writing desk.

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
NO_DRAFT = 'This blog has no draft yet. Write some on the desk first, then make its Google Doc.'


class Conflict(ValueError):
    """A finished-draft handoff cannot proceed in its current state."""


def pending_link(record):
    """The existing unconfirmed Doc, available for inspection without importing again."""
    pending = (record.get('google') or {}).get('page_handoff') or {}
    try:
        document = drive.identifier(pending.get('document_id') or '')
    except drive.GoogleError:
        return None
    return {'url': 'https://docs.google.com/document/d/' + document + '/edit'}


def _ready(root, ident, desk):
    """Whether the draft may go to Google: a finished run's approved draft, or any draft on
    the writing desk, which has no run and is never finished first."""
    directory, _ = studio.item(root, 'articles', ident)
    draft = directory / 'DRAFT.md'
    if desk:
        if not draft.is_file() or not draft.read_text().strip():
            raise Conflict(NO_DRAFT)
        return
    if not blog_runner.survey(root, ident)['complete'] or not draft.is_file():
        raise Conflict(NOT_FINISHED)


def open_as_doc(root, ident, client=None, capture=None, desk=False):
    """Make the blog's private Google Doc once and link it, with the draft as its baseline.
    With `desk`, the blog is on the writing desk: its item and DRAFT.md are read as they
    are, with no run to load or finish."""
    if desk:
        import desk as writing_desk

        directory, record = studio.item(root, 'articles', ident)
        if not writing_desk.on_desk(directory):
            raise Conflict('This blog is not on the writing desk.')
    else:
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
    _ready(root, ident, desk)
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
    pending['document_id'] = drive.identifier(document)
    studio.persist(directory, 'articles', record)
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
    _ready(root, ident, desk)
    observation['structure_verified'] = True
    studio.write_json(snapshot / 'observation.json', observation)
    workflow.confirm_transfer(root, ident, 'draft', transfer, snapshot)
    directory, record = studio.item(root, 'articles', ident)
    workflow.state(record).pop('page_handoff', None)
    studio.persist(directory, 'articles', record)
    return {'id': ident, 'url': receipt['url'], 'transfer': transfer}
