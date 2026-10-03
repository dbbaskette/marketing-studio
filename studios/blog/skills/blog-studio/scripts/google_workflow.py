#!/usr/bin/env python3
"""Local Google Docs transfer checkpoints. Never contacts Google or handles credentials.

The harness supplies bounded, accepted-text observations after provider readback.
These checks verify consistency, not that a provider call actually happened.
"""
import argparse
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
import uuid

import studio

CAPABILITIES = ('read', 'tabs', 'create', 'edit', 'copy', 'revision_guard',
                'accepted_text', 'comments_read', 'comments_write', 'inline_anchors', 'suggestions_read', 'suggestions_write',
                'export_pdf', 'export_docx', 'export_md', 'share', 'permissions_read', 'silent_share')


def object_fields(value, allowed, required=()):
    if not isinstance(value, dict) or set(value) - set(allowed) or set(required) - set(value):
        raise ValueError('Unexpected or missing fields; use the bounded Google contract, never raw provider responses.')
    return value


def token(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,200}', value):
        raise ValueError('Invalid provider identifier.')
    return value


def hash_value(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{64}', value):
        raise ValueError('Expected a SHA-256 fingerprint.')
    return value


def observation(value, body):
    required = ('schema', 'document_id', 'url', 'tab_ids', 'observed_at', 'content_sha256', 'suggestions')
    object_fields(value, (*required, 'revision_id', 'folder_id', 'structure_verified', 'format_sha256', 'review_state'), required)
    if value['schema'] != 1:
        raise ValueError('Unsupported Google observation schema.')
    document_id = token(value['document_id'])
    if not isinstance(value['url'], str):
        raise ValueError('Expected an observed Google Doc URL.')
    url = urlsplit(value['url'])
    match = re.fullmatch(r'/document/(?:u/[0-9]+/)?d/([A-Za-z0-9_.-]+)(?:/edit|/view|/preview)?/?', url.path)
    if url.scheme != 'https' or url.netloc != 'docs.google.com' or not match or match[1] != document_id:
        raise ValueError('The observed native Google Doc URL and identity disagree.')
    tabs = value['tab_ids']
    if not isinstance(tabs, list) or not tabs or not all(isinstance(t, str) for t in tabs) or len(tabs) != len(set(tabs)):
        raise ValueError('Select explicit unique tab IDs in document order.')
    tabs = [token(tab) for tab in tabs]
    if value['suggestions'] not in ('none', 'excluded'):
        raise ValueError('Accepted text must be separated from suggestions before transfer.')
    if not isinstance(body, str) or not body.strip():
        raise ValueError('A transfer needs readable accepted text.')
    if hash_value(value['content_sha256']) != studio.digest(body.encode()):
        raise ValueError('Google readback fingerprint does not match the selected text.')
    from datetime import datetime
    stamp = datetime.fromisoformat(value['observed_at'])
    if stamp.tzinfo is None:
        raise ValueError('Observation timestamps need a timezone.')
    result = {**value, 'url': 'https://docs.google.com/document/d/' + document_id + '/edit', 'tab_ids': tabs}
    for name in ('revision_id', 'folder_id'):
        if result.get(name) is not None:
            token(result[name])
    if 'structure_verified' in result and not isinstance(result['structure_verified'], bool):
        raise ValueError('Structure verification must be true or false.')
    if result.get('format_sha256') is not None:
        hash_value(result['format_sha256'])
    if 'review_state' in result:
        review_state(result['review_state'])
    return result


def review_state(value):
    keys=('pending','accepted','rejected','unresolved_comments')
    object_fields(value, keys, keys)
    if any(type(v) is not int or v < 0 for v in value.values()):
        raise ValueError('Review counts must be nonnegative integers.')
    return value


def observed(args):
    body = studio.read_text(args.file)
    return observation(studio.read_json(Path(args.observation)), body), body


def state(record):
    result = record.setdefault('google', {'schema': 1, 'transfers': {}, 'baselines': {}, 'receipts': []})
    if result.get('schema') != 1:
        raise ValueError('Unsupported Google checkpoint schema; update the managed runtime.')
    return result


def same_target(left, right):
    if any(left.get(k) != right.get(k) for k in ('document_id', 'tab_ids')):
        raise ValueError('Document or selected tabs changed. Start a separate handoff; do not reuse this baseline.')


def local_body(directory, kind):
    path = studio.inside(directory, kind.upper() + '.md')
    if not path.is_file():
        raise ValueError('Save the selected local artifact before transferring it.')
    body = path.read_text(encoding='utf-8')
    if not body.strip():
        raise ValueError('Cannot transfer empty content.')
    return body


def compare(directory, record, kind, obs, body):
    google = state(record)
    base = google['baselines'].get(kind)
    if not base:
        raise ValueError('No confirmed transfer baseline. Import as a source or confirm a matching handoff first.')
    same_target(base['document'], obs)
    local = local_body(directory, kind)
    local_hash = studio.digest(local.encode())
    remote_hash = studio.digest(body.encode())
    local_changed = local_hash != base['local_sha256']
    remote_changed = remote_hash != base['document']['content_sha256']
    status = ('converged' if local_hash == remote_hash and (local_changed or remote_changed) else
              'conflict' if local_changed and remote_changed else
              'local-only' if local_changed else 'remote-only' if remote_changed else 'unchanged')
    inputs = {'baseline': base, 'local_sha256': local_hash, 'document': obs, 'kind': kind}
    return {'status': status, 'comparison': studio.digest(json.dumps(inputs, sort_keys=True).encode()),
            'local_sha256': local_hash, 'remote_sha256': remote_hash,
            'format_changed': (obs['format_sha256'] != base['document'].get('format_sha256')) if obs.get('format_sha256') else None,
            'baseline_file': str(snapshot_path(directory, base['transfer'], 'document')),
            'local_file': str(studio.inside(directory, kind.upper() + '.md')),
            'guard': {'requiredRevisionId': obs['revision_id']} if obs.get('revision_id') else None}


def snapshot_path(directory, transfer, name):
    if not re.fullmatch(r'[a-f0-9]{32}', transfer):
        raise ValueError('Invalid transfer ID.')
    # Existing 1.1 hub readers already preserve derived history artifacts.
    return studio.inside(directory, 'history', 'derived-google-' + transfer + '-' + name + '.md')


def snapshot(directory, transfer, name, body):
    studio.atomic(snapshot_path(directory, transfer, name), body.encode())



def formatted_snapshot(path, obs, body):
    """Only attach inspected helper-generated artifacts for this exact transfer."""
    from google_drive import validate_docx, GoogleError
    from google_roundtrip import semantic, tabs
    from google_drive import encoded as compact
    directory = Path(path)
    names = ('document.md', 'document.docx', 'native.json', 'snapshot.json')
    files = {}
    for name in names:
        source = directory / name
        if source.is_symlink() or not source.is_file():
            raise ValueError('Snapshot files must be regular contained files.')
        limit = 10 * 1024 * 1024 if name.endswith('.docx') else 1024 * 1024
        if source.stat().st_size > limit:
            raise ValueError('Snapshot exceeds the portable Hub artifact limit.')
        files[name] = source.read_bytes()
    meta = json.loads(files['snapshot.json'])
    if meta.get('schema') == 2:
        source=directory/'accepted.json'
        if source.is_symlink() or not source.is_file() or source.stat().st_size > 1024*1024:
            raise ValueError('Accepted native snapshot must be a bounded regular file.')
        files['accepted.json']=source.read_bytes()
    object_fields(meta, ('schema', 'document_id', 'tab_ids', 'revision_id', 'drive_version',
                       'observed_at', 'content_sha256', 'format_sha256', 'files', 'review_state'),
                       ('schema', 'document_id', 'tab_ids', 'revision_id', 'content_sha256', 'format_sha256', 'files'))
    if meta['schema'] not in (1,2) or any(meta[k] != obs.get(k) for k in ('document_id', 'tab_ids', 'revision_id', 'content_sha256', 'format_sha256')):
        raise ValueError('Snapshot and observed document revision disagree.')
    if files['document.md'] != body.encode():
        raise ValueError('Snapshot Markdown and accepted text disagree.')
    if meta['files'] != {name: studio.digest(data) for name, data in files.items() if name != 'snapshot.json'}:
        raise ValueError('Snapshot file fingerprints disagree.')
    try:
        validate_docx(files['document.docx'])
    except GoogleError as exc:
        raise ValueError(str(exc)) from None
    native = json.loads(files['native.json'])
    if meta['schema'] == 2:
        from google_suggestions import accepted_markdown, summary
        accepted=json.loads(files['accepted.json'])
        if (review_state(meta.get('review_state')) != obs.get('review_state')
                or meta['review_state'] != summary(native)
                or native.get('suggestionsViewMode') != 'SUGGESTIONS_INLINE'
                or native.get('commentsViewMode') != 'COMMENTS_VIEW_MODE_INCLUDED'
                or native.get('documentId') != obs['document_id']
                or native.get('revisionId') != obs.get('revision_id')
                or [t['tabProperties']['tabId'] for t in tabs(native)] != obs['tab_ids']
                or accepted_markdown(accepted) != files['document.md']):
            raise ValueError('Review snapshot and accepted projection disagree.')
        native=accepted
    if not native.get('tabs'):
        raise ValueError('Native snapshot must contain selected tabs.')
    if (native.get('documentId') != obs['document_id'] or native.get('revisionId') != obs.get('revision_id')
            or [t['tabProperties']['tabId'] for t in tabs(native)] != obs['tab_ids']
            or studio.digest(compact(semantic(native))) != obs.get('format_sha256')):
        raise ValueError('Native snapshot identity, scope or formatting fingerprint disagrees.')
    return files


def save_formatted_snapshot(directory, transfer, files):
    names = {}
    for name, data in files.items():
        relative = 'history/google-' + transfer + '-' + name
        studio.atomic(studio.inside(directory, relative), data)
        names[name] = relative
    return names


def capabilities(args, root):
    value = studio.read_json(Path(args.file))
    object_fields(value, ('schema', 'harness', 'checked_at', 'capabilities'), ('schema', 'harness', 'checked_at', 'capabilities'))
    if value['schema'] != 1 or value['harness'] not in ('codex', 'claude'):
        raise ValueError('Capability record needs schema 1 and the current harness.')
    from datetime import datetime
    if datetime.fromisoformat(value['checked_at']).tzinfo is None:
        raise ValueError('Capability timestamp needs a timezone.')
    object_fields(value['capabilities'], CAPABILITIES)
    for name, cap in value['capabilities'].items():
        object_fields(cap, ('status', 'tool'), ('status',))
        if cap['status'] not in ('exposed', 'verified', 'unavailable', 'unknown'):
            raise ValueError('Invalid capability status.')
        if cap['status'] in ('exposed', 'verified') and not cap.get('tool'):
            raise ValueError('Name the actual exposed tool; never assume harness parity.')
        if cap.get('tool'):
            token(cap['tool'])
    # Machine-specific connector discovery is deliberately not portable Team Hub memory.
    studio.write_json(studio.inside(root, '.google-capabilities.json'), value)
    return {'status': 'recorded', 'harness': value['harness'], 'capabilities': value['capabilities']}


def receipt(value):
    fields = ('operation', 'document_id', 'status', 'requested', 'observed')
    object_fields(value, fields, fields)
    token(value['document_id'])
    if value['operation'] not in ('comments', 'template', 'export', 'sharing') or value['status'] not in ('verified', 'partial', 'unavailable', 'failed'):
        raise ValueError('Invalid operation receipt.')
    requested, actual = value['requested'], value['observed']
    if value['operation'] == 'sharing':
        def permissions(entries):
            if not isinstance(entries, list) or not entries:
                raise ValueError('Sharing requires an explicit audience and access level.')
            for entry in entries:
                object_fields(entry, ('type', 'audience', 'role', 'notify'), ('type', 'audience', 'role', 'notify'))
                if entry['type'] not in ('user', 'domain') or entry['role'] not in ('reader', 'commenter', 'writer') or not isinstance(entry['notify'], bool):
                    raise ValueError('Public links and ownership transfer are outside this sharing workflow.')
                pattern = r'[^@\s/]+@[^@\s/]+\.[^@\s/]+' if entry['type'] == 'user' else r'[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
                if not isinstance(entry['audience'], str) or not re.fullmatch(pattern, entry['audience']):
                    raise ValueError('Invalid explicit sharing audience.')
        permissions(requested)
        if actual:
            permissions(actual)
        elif actual != []:
            raise ValueError('Observed permissions must be a list.')
        if any(entry not in requested for entry in actual):
            raise ValueError('Receipt contains an unrequested permission change.')
        verified = actual == requested
    elif value['operation'] == 'comments':
        def comments(entries):
            if not isinstance(entries, list):raise ValueError('Comment operations must be a list.')
            for entry in entries:
                object_fields(entry, ('action', 'location', 'tab_id', 'quote', 'thread_id', 'anchor_verified'), ('action', 'location'))
                if entry['action'] not in ('create', 'reply', 'resolve') or entry['location'] not in ('inline', 'document'):
                    raise ValueError('Invalid comment action or location.')
                if entry['action'] == 'create' and (not entry.get('quote') or not entry.get('tab_id')):
                    raise ValueError('Comments need exact text and selected tab evidence.')
                if entry['action'] != 'create' and not entry.get('thread_id'):
                    raise ValueError('Reply/resolve requires a live thread ID.')
                for key in ('tab_id', 'thread_id'):
                    if entry.get(key):token(entry[key])
        comments(requested);comments(actual)
        if not requested:raise ValueError('Select at least one comment operation.')
        # Comment IDs and native-anchor verification come from provider readback.
        expected = [{k: v for k, v in entry.items() if k != 'anchor_verified'} for entry in requested]
        projected = [{k: v for k, v in entry.items() if k != 'anchor_verified' and not (entry['action'] == 'create' and k == 'thread_id')} for entry in actual]
        verified = (expected == projected and all(entry.get('thread_id') for entry in actual)
                    and all(entry.get('anchor_verified') is True for entry in actual if entry['location'] == 'inline'))
    elif value['operation'] == 'template':
        for entry in (requested, actual):
            object_fields(entry, ('template_id', 'tab_signature', 'structure_verified'), ('template_id', 'tab_signature', 'structure_verified'))
            token(entry['template_id']);hash_value(entry['tab_signature'])
            if not isinstance(entry['structure_verified'], bool):raise ValueError('Invalid structure verification.')
        verified = requested == actual and actual['structure_verified']
    else:
        for entry in (requested, actual):
            object_fields(entry, ('format', 'content_sha256', 'artifact_sha256', 'inspected'), ('format', 'content_sha256', 'inspected'))
            if entry['format'] not in ('pdf', 'docx', 'md') or not isinstance(entry['inspected'], bool):
                raise ValueError('Export needs requested PDF/Word/Markdown format and inspection status.')
            hash_value(entry['content_sha256'])
            if entry.get('artifact_sha256'):hash_value(entry['artifact_sha256'])
        verified = (requested['format'] == actual['format'] and requested['content_sha256'] == actual['content_sha256'] and actual['inspected'] and bool(actual.get('artifact_sha256')))
    if value['status'] == 'verified' and not verified:
        raise ValueError('Readback does not support a verified receipt.')
    return {**value, 'recorded_at': studio.now()}



STATUS_LABELS = {'in-sync': 'In sync', 'google-changes': 'Google has changes',
                 'local-changes': 'Local changes pending', 'both-changed': 'Both changed',
                 'pending-review': 'Suggestions pending', 'not-checked': 'Not checked'}


def sync_status(root, directory, record, kind='draft', online=False, account=None):
    """Cached observations are historical only; only a live check can say in sync."""
    from google_drive import Client, GoogleError, encoded as compact
    from google_roundtrip import semantic, tabs
    base = record.get('google', {}).get('baselines', {}).get(kind)
    cache_path = studio.inside(directory, '.google-status-' + kind + '.json')
    cache = studio.read_json(cache_path) if cache_path.exists() else {}
    target = base.get('document') if base else None
    # Never reuse an observation for a newly linked document/baseline.
    baseline_hash = studio.digest(compact(base))
    if cache.get('baseline_sha256') != baseline_hash:
        cache = {}
    result = {'id': record['id'], 'kind': kind, 'status': 'not-checked',
              'document_url': target.get('url') if target else None,
              'last_checked_at': cache.get('last_checked_at'),
              'last_successful_check_at': cache.get('last_successful_check_at'),
              'last_known_status': cache.get('last_known_status'),
              'last_saved_to_hub': None, 'hub_saved_revision': None,
              'reason': 'Run an online check before claiming the Google copy is current.'}
    hub_cache = studio.inside(root, '.hub-workspace.json')
    if hub_cache.exists():
        saved = studio.read_json(hub_cache).get('items', {}).get('articles/' + record['id'], {})
        result['last_saved_to_hub'] = saved.get('last_saved_to_hub')
        result['hub_saved_revision'] = saved.get('last_saved_revision')
    if not base:
        result['reason'] = 'No linked Google transfer baseline.'
    elif not studio.inside(directory, kind.upper() + '.md').is_file():
        result['reason'] = 'The selected local artifact is missing.'
    elif online:
        result['last_checked_at'] = studio.now()
        try:
            if not target.get('format_sha256'):
                raise GoogleError('Capture and accept a formatted return once to establish a comparable baseline.')
            before = local_body(directory, kind)
            client=Client(account)
            from google_suggestions import document, review_read, summary
            from google_roundtrip import suggestions
            remote=document(client,target['document_id'],inline=True)
            if suggestions(remote):
                review=review_read(client,target['document_id'])
                accepted=document(client,target['document_id'])
                again=document(client,target['document_id'],inline=True)
                if len({d['revisionId'] for d in (remote,review,accepted,again)}) != 1:
                    raise GoogleError('Google changed during the check. Check again.')
                result['review_state']=summary(review)
                remote=accepted
            if [tab['tabProperties']['tabId'] for tab in tabs(remote)] != target['tab_ids']:
                raise GoogleError('Google tab scope changed; reconcile the linked document before continuing.')
            if before != local_body(directory, kind):
                raise GoogleError('Local content changed during the check. Check again.')
            local_changed = studio.digest(before.encode()) != base['local_sha256']
            remote_changed = studio.digest(compact(semantic(remote))) != target['format_sha256']
            result['status'] = ('both-changed' if local_changed and remote_changed else
                                'local-changes' if local_changed else 'google-changes' if remote_changed else 'in-sync')
            if result['status']=='in-sync' and result.get('review_state',{}).get('pending'):
                result['status']='pending-review'
            result.update(last_successful_check_at=result['last_checked_at'],
                          last_known_status=result['status'], checked_revision=remote['revisionId'],
                          reason='Compared current Google text/formatting and the local artifact with the saved baseline.')
        except GoogleError as exc:
            result['reason'] = str(exc)
        studio.write_json(cache_path, {k: result[k] for k in
                          ('last_checked_at', 'last_successful_check_at', 'last_known_status')} |
                          {'baseline_sha256': baseline_hash})
    result['label'] = STATUS_LABELS[result['status']]
    result['next_step'] = {'in-sync': 'Continue with the linked editing copy; recheck before sending changes.',
        'google-changes': 'Bring the Google edits and formatting back before writing.',
        'local-changes': 'Send the selected local changes when requested.',
        'both-changed': 'Compare and reconcile both versions before sending.',
        'pending-review': 'Review pending suggestions in Google Docs, then pull accepted changes.',
        'not-checked': 'Check the linked Google Doc when access is available; keep local work intact.'}[result['status']]
    return result


def command(root, args):
    if args.action == 'capabilities':return capabilities(args, root)
    if args.action == 'source':
        obs, body = observed(args)
        # Use the regular source revision and private-hub lifecycle.
        source_args = argparse.Namespace(action='add', name=args.name, file=None, text_file=args.file,
            content=body, origin=obs['url'], purpose=args.purpose, author=args.author, note='Google Docs accepted text', status='ready')
        result = studio.source_command(root, source_args)
        directory, result = studio.item(root, 'sources', result['id'])
        result['google_document'] = obs
        studio.persist(directory, 'sources', result)
        return result
    directory, record = studio.item(root, 'articles', args.id)
    if args.action == 'status':
        return sync_status(root, directory, record, args.kind, args.online, args.account)
    google = state(record)
    if args.action == 'receipt':
        value = receipt(studio.read_json(Path(args.file)))
        google['receipts'].append(value)
        studio.persist(directory, 'articles', record)
        return {'id': record['id'], 'status': value['status'], 'operation': value['operation']}
    kind = args.kind
    if args.action == 'prepare':
        body = local_body(directory, kind)
        base = google['baselines'].get(kind)
        target = None
        if base and not args.new_document:
            if not args.observation or not args.file:
                raise ValueError('Read the linked Google Doc before preparing another handoff.')
            target, remote_body = observed(args)
            check = compare(directory, record, kind, target, remote_body)
            if check['status'] in ('remote-only', 'conflict'):
                raise ValueError('Google content changed. Return or resolve those edits before writing.')
            if not check['guard']:
                raise ValueError('Existing-document writes need a revision guard; create a new copy instead.')
        elif args.observation or args.file:
            raise ValueError('A new-document handoff has no existing target observation.')
        transfer = uuid.uuid4().hex
        snapshot(directory, transfer, 'local', body)
        google['transfers'][transfer] = {'status': 'prepared', 'kind': kind, 'local_sha256': studio.digest(body.encode()),
            'target': target, 'baseline': base, 'prepared_at': studio.now()}
        studio.persist(directory, 'articles', record)
        return {'id': record['id'], 'transfer': transfer, 'file': str(snapshot_path(directory, transfer, 'local')),
                'target': target, 'guard': {'requiredRevisionId': target['revision_id']} if target else None,
                'status': 'prepared', 'next_step': 'Use only this selected editing copy with the connected provider, then confirm readback.'}
    obs, body = observed(args)
    snapshot_files = None
    if args.action in ('confirm', 'accept'):
        if getattr(args, 'snapshot', None):
            snapshot_files = formatted_snapshot(args.snapshot, obs, body)
        elif obs.get('format_sha256'):
            raise ValueError('A formatting observation needs its --snapshot artifacts.')
    if args.action == 'confirm':
        transfer = args.transfer
        saved = google['transfers'].get(transfer)
        if not saved or saved['kind'] != kind:
            raise ValueError('Unknown transfer for this artifact.')
        if saved['status'] == 'confirmed':
            if saved['document'] != obs:
                raise ValueError('Transfer already confirmed with a different readback.')
            return {'id': record['id'], 'transfer': transfer, 'status': 'already-confirmed'}
        if saved.get('baseline') != google['baselines'].get(kind):
            raise ValueError('The baseline changed after preparation. Prepare a fresh transfer.')
        if saved['target']:
            same_target(saved['target'], obs)
            if saved['target'].get('folder_id') != obs.get('folder_id'):
                raise ValueError('Readback changed the target folder.')
        if not obs.get('structure_verified') or saved['local_sha256'] != obs['content_sha256']:
            raise ValueError('Readback must match the selected copy and verify its structure and links.')
        snapshot(directory, transfer, 'document', body)
        saved.update(status='confirmed', document=obs, confirmed_at=studio.now(), direction='to-google')
        google['baselines'][kind] = {'transfer': transfer, 'local_sha256': saved['local_sha256'], 'document': obs}
        result = {'id': record['id'], 'transfer': transfer, 'status': 'confirmed'}
    else:
        check = compare(directory, record, kind, obs, body)
        if args.action == 'compare':return {'id': record['id'], **check}
        if check['comparison'] != args.expected_comparison:
            raise ValueError('The comparison changed. Re-read both versions and compare again.')
        if check['status'] in ('conflict', 'local-only') and not args.resolution_file:
            raise ValueError('Local edits would be overwritten. Resolve explicitly and provide the chosen text.')
        accepted = studio.read_text(args.resolution_file) if args.resolution_file else body
        if not accepted.strip():raise ValueError('Cannot accept empty text.')
        if kind == 'draft' and record['stop_point'] in ('outline', 'brief'):
            raise ValueError('This task stops before drafting. Keep its existing stop point.')
        if kind == 'draft' and record['mode'] == 'existing' and not (directory / 'ORIGINAL.md').is_file():
            raise ValueError('Preserve the imported original before accepting an edited draft.')
        transfer = uuid.uuid4().hex
        snapshot(directory, transfer, 'local', accepted)
        snapshot(directory, transfer, 'document', body)
        previous = google['baselines'][kind]
        if studio.digest(accepted.encode()) != check['local_sha256']:
            studio.save_artifact(directory, kind, accepted, record)
        google['transfers'][transfer] = {'status': 'confirmed', 'kind': kind, 'direction': 'from-google',
            'local_sha256': studio.digest(accepted.encode()), 'document': obs, 'confirmed_at': studio.now(),
            'resolved': bool(args.resolution_file), 'previous_transfer': previous['transfer']}
        # Remote text is the common baseline. A local merge remains visibly unsent.
        google['baselines'][kind] = {'transfer': transfer, 'local_sha256': obs['content_sha256'], 'document': obs}
        result = {'id': record['id'], 'transfer': transfer, 'status': 'accepted', 'reviews': studio.freshness(root, directory, record)}
    if snapshot_files:
        google['transfers'][transfer]['formatted_snapshot'] = save_formatted_snapshot(directory, transfer, snapshot_files)
        result['formatted_snapshot'] = google['transfers'][transfer]['formatted_snapshot']
    studio.persist(directory, 'articles', record)
    return result


def add_parser(groups):
    commands = groups.add_parser('google', help='Local Google Docs checkpoints; provider calls stay in the harness').add_subparsers(dest='action', required=True)
    cap = commands.add_parser('capabilities');cap.add_argument('--file', required=True)
    source = commands.add_parser('source');source.add_argument('--name', required=True)
    source.add_argument('--purpose', action='append', choices=studio.PURPOSES, required=True)
    source.add_argument('--author', default='')
    source.add_argument('--observation', required=True);source.add_argument('--file', required=True)
    status = commands.add_parser('status');status.add_argument('--id', required=True)
    status.add_argument('--kind', choices=('draft', 'outline'), default='draft')
    status.add_argument('--online', action='store_true');status.add_argument('--account')
    for name in ('prepare', 'confirm', 'compare', 'accept', 'receipt'):
        p = commands.add_parser(name);p.add_argument('--id', required=True)
        if name == 'receipt':p.add_argument('--file', required=True);continue
        p.add_argument('--kind', choices=('draft', 'outline'), default='draft')
        p.add_argument('--observation', required=name != 'prepare')
        p.add_argument('--file', required=name != 'prepare', help='Selected accepted text in the same Markdown projection used for handoff')
        if name == 'prepare':p.add_argument('--new-document', action='store_true')
        if name in ('confirm', 'accept'):p.add_argument('--snapshot', help='Inspected formatted snapshot directory from google_roundtrip.py capture')
        if name == 'confirm':p.add_argument('--transfer', required=True)
        if name == 'accept':
            p.add_argument('--expected-comparison', required=True)
            p.add_argument('--resolution-file', help='Only the author-approved merge or replacement after showing the conflict')
