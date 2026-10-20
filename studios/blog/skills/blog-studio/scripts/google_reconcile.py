"""Explicit read/compare/accept for the linked Google Doc; never writes to Google."""

import re
from types import SimpleNamespace
import uuid

import google_drive as drive
import google_intake
import google_roundtrip as roundtrip
import google_workflow as workflow
import manuscript_editor
import manuscript_preview
import studio


def preview(root, data):
    current = manuscript_editor.guard(root, data)
    if not current['google']:
        raise ValueError('Import or link a Google Doc before comparing versions.')
    token = uuid.uuid4().hex
    folder = studio.inside(drive.staging_root(root, create=True), 'reconcile-' + token)
    folder.mkdir(mode=0o700)
    account = drive.account_for(root)
    snapshot = folder / 'snapshot'
    try:
        summary = roundtrip.capture(
            drive.Client(account), current['google']['document_id'], None, snapshot
        )
        observation, body = workflow.observed(
            SimpleNamespace(snapshot=str(snapshot), observation=None, file=None)
        )
        directory, record = studio.item(root, 'articles', current['id'])
        comparison = workflow.compare(directory, record, 'draft', observation, body, root)
        base = workflow.baseline_text(directory, record['google']['baselines']['draft'])
        merged = (
            workflow.merged_text(workflow.text_chunks(base, current['content'], body))[0]
            if base is not None
            else None
        )
        saved = {
            'id': current['id'],
            'preview': token,
            'expected': current['expected'],
            'capture': google_intake.fingerprint(snapshot),
            'comparison': comparison['comparison'],
            'account': account,
            'remote_guard': remote_guard(observation),
        }
        studio.write_json(folder / 'preview.json', saved)
        return {
            **saved,
            'status': comparison['status'],
            'local': current['content'],
            'remote': body,
            'baseline': base,
            'local_preview': manuscript_preview.text_only(current['content']),
            'remote_preview': manuscript_preview.text_only(body),
            'baseline_preview': manuscript_preview.text_only(base) if base else None,
            'resolution': merged,
            'merge': comparison.get('merge'),
            'review_state': observation.get('review_state'),
            'summary': summary['summary'],
            'has_proposals': bool(current['proposals']),
            'google_written': False,
        }
    except BaseException:
        drive.discard(root, folder)
        raise


def accept(root, data):
    if data.get('confirmed') is not True:
        raise ValueError('Compare both versions and confirm the chosen local text first.')
    current = manuscript_editor.guard(root, data)
    if current['proposals']:
        raise ValueError(
            'Review or clear the saved wording suggestions before reconciling. They have been kept.'
        )
    token = data.get('preview')
    if not isinstance(token, str) or not re.fullmatch('[a-f0-9]{32}', token):
        raise ValueError('Choose a current Google comparison.')
    folder = studio.inside(drive.staging_root(root), 'reconcile-' + token)
    saved = studio.read_json(folder / 'preview.json')
    if saved.get('result'):
        return saved['result']
    if (
        saved['id'] != current['id']
        or saved['expected'] != current['expected']
        or data.get('comparison') != saved['comparison']
    ):
        raise ValueError(
            'The local text or comparison changed. Compare again; no text was replaced.'
        )
    if drive.account_for(root) != saved['account']:
        raise ValueError('The selected Google account changed. Compare again with this account.')
    snapshot = folder / 'snapshot'
    if google_intake.fingerprint(snapshot) != saved['capture']:
        raise ValueError('The saved capture changed. Compare again.')
    # Verify accepted text and formatting again immediately before the local checkpoint.
    fresh = folder / ('check-' + uuid.uuid4().hex)
    try:
        roundtrip.capture(
            drive.Client(saved['account']), current['google']['document_id'], None, fresh
        )
        observation, body = workflow.observed(
            SimpleNamespace(snapshot=str(fresh), observation=None, file=None)
        )
        directory, record = studio.item(root, 'articles', current['id'])
        comparison = workflow.compare(directory, record, 'draft', observation, body)
        if remote_guard(observation) != saved['remote_guard']:
            raise ValueError(
                'Google changed since the preview. Compare again; your local work is kept.'
            )
        resolution = data.get('resolution')
        resolution_file = None
        if resolution is not None:
            if (
                not isinstance(resolution, str)
                or not resolution.strip()
                or len(resolution) > 200_000
            ):
                raise ValueError('Use a nonempty reviewed resolution up to 200,000 characters.')
            resolution_file = folder / 'resolution.md'
            studio.atomic(resolution_file, resolution.encode())
            resolution_file.chmod(0o600)
        observation['structure_verified'] = True
        studio.write_json(fresh / 'observation.json', observation)
        comparison = workflow.compare(directory, record, 'draft', observation, body)
        result = workflow.command(
            root,
            SimpleNamespace(
                action='accept',
                id=current['id'],
                kind='draft',
                snapshot=str(fresh),
                observation=None,
                file=None,
                expected_comparison=comparison['comparison'],
                resolution_file=str(resolution_file) if resolution_file else None,
                discard_remote=data.get('discard_remote') is True,
            ),
        )
        saved['result'] = {**result, 'google_written': False}
        studio.write_json(folder / 'preview.json', saved)
        drive.discard(root, snapshot)
        if resolution_file:
            drive.discard(root, resolution_file)
        return saved['result']
    finally:
        drive.discard(root, fresh)


def remote_guard(observation):
    return {
        key: value
        for key, value in observation.items()
        if key not in ('observed_at', 'structure_verified')
    }
