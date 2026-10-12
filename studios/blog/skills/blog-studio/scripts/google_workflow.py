#!/usr/bin/env python3
"""Local Google Docs transfer checkpoints.

Checkpoint commands (start, prepare, confirm, compare, accept, source, receipt)
work from files only: they never contact Google or handle credentials. The one
exception is `status --online`, which makes read-only calls through the gcloud
transport to compare the linked Doc with its saved baseline.

Observations describe accepted text after provider readback. These checks verify
consistency, not that a provider call actually happened.
"""
import argparse
import difflib
import json
import os
import shutil
import tempfile
from pathlib import Path
import re
from urllib.parse import urlsplit
import uuid

import studio

# Raw Docs JSON (which can hold collaborators' comment threads) stays in this dot folder, which Hub sync skips.
LOCAL_NATIVE = '.google-native'
SHARED_SNAPSHOT = ('document.md', 'document.docx', 'snapshot.json')
LOCAL_MARK, SPLIT_MARK, REMOTE_MARK = '<<<<<<< local', '=======', '>>>>>>> google'

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
    optional = ('revision_id', 'folder_id', 'structure_verified', 'format_sha256', 'review_state',
                'format_version', 'legacy_format_sha256', 'projection')
    object_fields(value, (*required, *optional), required)
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
    for name in ('format_sha256', 'legacy_format_sha256'):
        if result.get(name) is not None:
            hash_value(result[name])
    if 'format_version' in result and result['format_version'] not in (1, 2):
        raise ValueError('Unsupported formatting fingerprint version; update the managed runtime.')
    projection = result.get('projection')
    if 'projection' in result and (not isinstance(projection, str) or not re.fullmatch(r'[a-z0-9/-]{1,40}', projection)):
        raise ValueError('Invalid Markdown projection label.')
    if 'review_state' in result:
        review_state(result['review_state'])
    return result


def review_state(value):
    keys=('pending','accepted','rejected','unresolved_comments')
    object_fields(value, keys, keys)
    if any(type(v) is not int or v < 0 for v in value.values()):
        raise ValueError('Review counts must be nonnegative integers.')
    return value


def capture_paths(args):
    """--snapshot alone names a capture folder; its observation and Markdown are used unless given."""
    folder = getattr(args, 'snapshot', None)
    observation_path = args.observation or (str(Path(folder) / 'observation.json') if folder else None)
    file_path = args.file or (str(Path(folder) / 'document.md') if folder else None)
    if not observation_path or not file_path:
        raise ValueError('Pass --snapshot <capture folder>, or both --observation and --file.')
    return observation_path, file_path


def observed(args):
    observation_path, file_path = capture_paths(args)
    body = studio.read_text(file_path)
    return observation(studio.read_json(Path(observation_path)), body), body


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


def format_pair(base_document, obs):
    """(baseline fingerprint, observed fingerprint computed the same way), or None where unavailable.

    Baselines saved by older runtimes use fingerprint version 1; captures carry
    that legacy value too, so an upgrade never makes an unchanged Doc look changed.
    """
    saved = base_document.get('format_sha256')
    if not saved:
        return None, None
    version = base_document.get('format_version', 1)
    if obs.get('format_version', 1) == version:
        return saved, obs.get('format_sha256')
    return saved, obs.get('legacy_format_sha256') if version == 1 else None


def compare(directory, record, kind, obs, body, root=None):
    google = state(record)
    base = google['baselines'].get(kind)
    if not base:
        raise ValueError('No confirmed transfer baseline. Use google start for a starting manuscript, or import as a reference source.')
    same_target(base['document'], obs)
    local = local_body(directory, kind)
    local_hash = studio.digest(local.encode())
    remote_hash = studio.digest(body.encode())
    saved_format, observed_format = format_pair(base['document'], obs)
    # Equal fingerprints mean the Doc itself is unchanged, however its Markdown happens to be rendered.
    same_document = bool(saved_format and observed_format and saved_format == observed_format)
    local_changed = local_hash != base['local_sha256']
    remote_changed = remote_hash != base['document']['content_sha256'] and not same_document
    status = ('converged' if local_hash == remote_hash and (local_changed or remote_changed) else
              'conflict' if local_changed and remote_changed else
              'local-only' if local_changed else 'remote-only' if remote_changed else 'unchanged')
    inputs = {'baseline': base, 'local_sha256': local_hash, 'document': obs, 'kind': kind}
    comparison = studio.digest(json.dumps(inputs, sort_keys=True).encode())
    result = {'status': status, 'comparison': comparison,
            'local_sha256': local_hash, 'remote_sha256': remote_hash,
            'format_changed': (not same_document) if obs.get('format_sha256') else None,
            'baseline_file': str(snapshot_path(directory, base['transfer'], 'document')),
            'local_file': str(studio.inside(directory, kind.upper() + '.md')),
            'guard': {'requiredRevisionId': obs['revision_id']} if obs.get('revision_id') else None}
    if status == 'conflict':
        result['merge'] = merge_preview(root, directory, base, local, body, comparison)
    return result


def baseline_text(directory, base):
    """The Google text both sides started from, if this computer still has an intact copy."""
    path = snapshot_path(directory, base['transfer'], 'document')
    if path.is_symlink() or not path.is_file():
        return None
    data = path.read_bytes()
    if studio.digest(data) != base['document']['content_sha256']:
        return None
    return data.decode('utf-8')


def merge_chunks(base, ours, theirs):
    """Three-way merge of line lists.

    Returns ('same', lines), ('ours', lines), ('theirs', lines) or
    ('conflict', our lines, their lines). A passage only one side changed is
    taken from that side; a passage both changed differently is a conflict.
    """
    def blocks(other):
        return difflib.SequenceMatcher(None, base, other, autojunk=False).get_matching_blocks()
    ours_blocks, theirs_blocks = blocks(ours), blocks(theirs)
    regions = []
    i = j = 0
    while i < len(ours_blocks) and j < len(theirs_blocks):
        base_a, start_a, size_a = ours_blocks[i]
        base_b, start_b, size_b = theirs_blocks[j]
        low, high = max(base_a, base_b), min(base_a + size_a, base_b + size_b)
        if low < high:
            regions.append((low, high, start_a + low - base_a, start_b + low - base_b))
        if base_a + size_a < base_b + size_b:
            i += 1
        else:
            j += 1
    regions.append((len(base), len(base), len(ours), len(theirs)))
    chunks = []
    at_base = at_ours = at_theirs = 0
    for low, high, in_ours, in_theirs in regions:
        original, mine, yours = base[at_base:low], ours[at_ours:in_ours], theirs[at_theirs:in_theirs]
        if original or mine or yours:
            if mine == yours:
                chunks.append(('same', mine))
            elif mine == original:
                chunks.append(('theirs', yours))
            elif yours == original:
                chunks.append(('ours', mine))
            else:
                chunks.append(('conflict', mine, yours))
        if high > low:
            chunks.append(('same', base[low:high]))
        at_base, at_ours, at_theirs = high, in_ours + high - low, in_theirs + high - low
    return chunks


def merged_text(chunks):
    """(text, number of conflicts). Conflicting passages are marked for the author to choose."""
    lines = []
    conflicts = 0
    for chunk in chunks:
        if chunk[0] == 'conflict':
            conflicts += 1
            lines += [LOCAL_MARK, *chunk[1], SPLIT_MARK, *chunk[2], REMOTE_MARK]
        else:
            lines += chunk[1]
    return '\n'.join(lines), conflicts


def text_chunks(base_text, local, remote):
    return merge_chunks(base_text.split('\n'), local.split('\n'), remote.split('\n'))


def dropped_remote_lines(chunks, resolution):
    """Lines that only Google changed and that a proposed resolution no longer contains."""
    kept = {line.strip() for line in resolution.split('\n')}
    return [line for chunk in chunks if chunk[0] == 'theirs'
            for line in chunk[1] if line.strip() and line.strip() not in kept]


def merge_preview(root, directory, base, local, body, comparison):
    """Describe how a both-changed return would merge, and stage the result for inspection."""
    base_text = baseline_text(directory, base)
    if base_text is None:
        return {'status': 'unavailable',
                'reason': 'The saved baseline text is not on this computer, so both versions need a manual resolution.'}
    text, conflicts = merged_text(text_chunks(base_text, local, body))
    preview = {'status': 'conflicts' if conflicts else 'clean', 'conflicts': conflicts,
               'next_step': ('Show the marked passages, record the chosen wording in this file without the markers, '
                             'then accept with --resolution-file.') if conflicts else
                            'The edits do not overlap. Accept without a resolution file to keep both.'}
    if root is not None:
        from google_drive import staging_root
        path = staging_root(root, create=True) / ('merge-' + comparison[:16] + '.md')
        studio.atomic(path, text.encode())
        path.chmod(0o600)
        preview['file'] = str(path)
    return preview


def choose_accepted(args, directory, base, check, local, body):
    """Text to keep locally after a return. Local edits are never replaced without an explicit choice."""
    base_text = baseline_text(directory, base)
    chunks = text_chunks(base_text, local, body) if base_text is not None else None
    if args.resolution_file:
        accepted = studio.read_text(args.resolution_file)
        if not accepted.strip():
            raise ValueError('Cannot accept empty text.')
        if any(line in (LOCAL_MARK, REMOTE_MARK) for line in accepted.split('\n')):
            raise ValueError('The resolution still contains conflict markers. Choose the wording for each marked passage first.')
        missing = dropped_remote_lines(chunks, accepted) if chunks is not None and not args.discard_remote else []
        if missing:
            raise ValueError('The resolution drops text that only Google changed (' + str(len(missing))
                             + ' line(s), starting “' + missing[0].strip()[:80] + '”). Keep that text, or pass '
                             '--discard-remote when the author chose to drop it.')
        return accepted, 'resolution'
    if check['status'] in ('unchanged', 'local-only'):
        return local, None
    if check['status'] in ('remote-only', 'converged'):
        return body, None
    if chunks is None:
        raise ValueError('Both versions changed and the saved baseline text is unavailable here; local edits would be '
                         'overwritten. Resolve explicitly and provide the chosen text.')
    text, conflicts = merged_text(chunks)
    if conflicts:
        raise ValueError('Both versions changed the same passage (' + str(conflicts) + ' place(s)); local edits would be '
                         'overwritten. Open the merge file from google compare, choose the wording for each marked '
                         'passage, and pass it as --resolution-file.')
    return text, 'clean-merge'


def snapshot_path(directory, transfer, name):
    if not re.fullmatch(r'[a-f0-9]{32}', transfer):
        raise ValueError('Invalid transfer ID.')
    # Existing 1.1 hub readers already preserve derived history artifacts.
    return studio.inside(directory, 'history', 'derived-google-' + transfer + '-' + name + '.md')


def snapshot(directory, transfer, name, body):
    studio.atomic(snapshot_path(directory, transfer, name), body.encode())



def formatted_snapshot(path, obs, body):
    """Validate a helper-made capture against this exact observation. Returns its files by name."""
    from google_drive import validate_docx, GoogleError
    from google_roundtrip import FORMAT_VERSION, PROJECTION, fingerprint, suggestion_ids, tabs
    from google_suggestions import accepted_markdown, summary
    directory = Path(path)
    files = {}

    def load(name, limit=1024 * 1024):
        source = directory / name
        if source.is_symlink() or not source.is_file():
            raise ValueError('Snapshot files must be regular contained files.')
        if source.stat().st_size > limit:
            raise ValueError('Snapshot exceeds the portable Hub artifact limit.')
        files[name] = source.read_bytes()

    for name in ('document.md', 'native.json', 'snapshot.json'):
        load(name)
    load('document.docx', 10 * 1024 * 1024)
    meta = json.loads(files['snapshot.json'])
    if not isinstance(meta, dict) or meta.get('schema') != 3:
        raise ValueError('This capture was made by a different runtime version. Capture the Doc again.')
    identity = ('document_id', 'tab_ids', 'revision_id', 'content_sha256', 'format_sha256', 'format_version',
                'legacy_format_sha256', 'projection')
    object_fields(meta, ('schema', *identity, 'drive_version', 'observed_at', 'files', 'review_state',
                         'review_threads', 'structure'), ('schema', *identity, 'files'))
    if 'accepted.json' in meta['files']:
        load('accepted.json')
    if meta['format_version'] != FORMAT_VERSION or any(meta[k] != obs.get(k) for k in identity):
        raise ValueError('Snapshot and observed document revision disagree.')
    if files['document.md'] != body.encode():
        raise ValueError('Snapshot Markdown and accepted text disagree.')
    if meta['files'] != {name: studio.digest(data) for name, data in files.items() if name != 'snapshot.json'}:
        raise ValueError('Snapshot file fingerprints disagree.')
    native = json.loads(files['native.json'])
    accepted = json.loads(files['accepted.json']) if 'accepted.json' in files else native
    try:
        validate_docx(files['document.docx'])
        for view in (native, accepted):
            if (not view.get('tabs') or view.get('documentId') != obs['document_id']
                    or view.get('revisionId') != obs.get('revision_id')
                    or [t['tabProperties']['tabId'] for t in tabs(view)] != obs['tab_ids']):
                raise ValueError('Native snapshot identity or scope disagrees.')
        if fingerprint(accepted) != obs['format_sha256']:
            raise ValueError('Native snapshot formatting fingerprint disagrees.')
        if meta['projection'] == PROJECTION and accepted_markdown(accepted) != files['document.md']:
            raise ValueError('Snapshot Markdown is not the accepted text of this native snapshot.')
    except GoogleError as exc:
        raise ValueError(str(exc)) from None
    review = meta.get('review_state')
    if review is not None or obs.get('review_state') is not None:
        threads = meta.get('review_threads')
        if threads == 'threads':
            expected = summary(native)
            listed = native.get('commentsViewMode') == 'COMMENTS_VIEW_MODE_INCLUDED'
        else:
            expected = {'pending': len(suggestion_ids(native)), 'accepted': 0, 'rejected': 0, 'unresolved_comments': 0}
            listed = threads == 'markers'
        if not listed or review_state(review) != obs.get('review_state') or review != expected:
            raise ValueError('Review snapshot and accepted projection disagree.')
    return files


def save_formatted_snapshot(directory, transfer, files):
    """Keep text, DOCX and the hash summary with the blog's shared history; keep raw Docs JSON on this computer.

    Returns (shared names, local names), each mapping a snapshot file to its path in the blog folder.
    """
    shared, local = {}, {}
    for name, data in files.items():
        if name in SHARED_SNAPSHOT:
            relative = 'history/google-' + transfer + '-' + name
            shared[name] = relative
            studio.atomic(studio.inside(directory, relative), data)
        else:
            relative = LOCAL_NATIVE + '/' + transfer + '-' + name
            local[name] = relative
            target = studio.inside(directory, relative)
            target.parent.mkdir(mode=0o700, exist_ok=True)
            studio.atomic(target, data)
            target.chmod(0o600)
    return shared, local


def prune_local_native(directory, google):
    """Raw Docs JSON is kept only for the current baselines; older copies are removed."""
    folder = studio.inside(directory, LOCAL_NATIVE)
    if folder.is_symlink() or not folder.is_dir():
        return
    current = {baseline['transfer'] for baseline in google['baselines'].values()}
    for entry in folder.iterdir():
        if entry.name[:32] not in current and entry.is_file() and not entry.is_symlink():
            entry.unlink()


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
    """Cached observations are historical only; only a live check can say in sync.

    The online check is read-only and needs neither stored native snapshots nor
    comment readback, so another Hub member can run it right after checkout.
    """
    from google_drive import Client, GoogleError, account_for, encoded as compact
    from google_roundtrip import fingerprint, inline_read, read_views, tabs
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
            client = Client(account_for(root, account))
            from google_suggestions import review_counts
            inline, remote = read_views(client, target['document_id'])
            if remote is not inline:
                # Suggestions are pending: compare accepted text only, and count what is waiting.
                _, result['review_state'], _ = review_counts(client, target['document_id'], inline)
                if inline_read(client, target['document_id'])['revisionId'] != inline['revisionId']:
                    raise GoogleError('Google changed during the check. Check again.')
            if [tab['tabProperties']['tabId'] for tab in tabs(remote)] != target['tab_ids']:
                raise GoogleError('Google tab scope changed; reconcile the linked document before continuing.')
            if before != local_body(directory, kind):
                raise GoogleError('Local content changed during the check. Check again.')
            local_changed = studio.digest(before.encode()) != base['local_sha256']
            # A baseline saved by an older runtime is compared the way it was computed.
            remote_changed = fingerprint(remote, target.get('format_version', 1)) != target['format_sha256']
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


def start(root, args):
    """Adopt an inspected existing Doc as a new manuscript and working baseline.

    Called under studio's workspace lock. No provider calls or Google writes.
    """
    from google_drive import discard
    obs, body = observed(args)
    if not obs.get('structure_verified') or not obs.get('revision_id') or not obs.get('format_sha256'):
        raise ValueError('Inspect a fresh formatted Google capture before starting this blog.')
    files = formatted_snapshot(args.snapshot, obs, body)
    if not args.title.strip() or len(args.title.strip()) > 500:
        raise ValueError('Use a blog title between 1 and 500 characters.')
    # A repeated start selects the existing blog; never replace local edits or its baseline.
    matches = []
    for folder in sorted(studio.inside(root, 'articles').iterdir()):
        if not folder.is_dir():
            continue
        _, existing = studio.item(root, 'articles', folder.name)
        for base in existing.get('google', {}).get('baselines', {}).values():
            doc = base['document']
            if doc['document_id'] == obs['document_id']:
                if doc['tab_ids'] != obs['tab_ids']:
                    raise ValueError('This Doc is already linked with different tabs; reconcile its scope first.')
                matches.append(existing)
                break
    if len(matches) > 1:
        raise ValueError('Several blogs link to this Doc; choose the existing blog before continuing.')
    if matches:
        record = matches[0]
        studio.write_json(studio.inside(root, '.active-article.json'), {'id': record['id']})
        return {'id': record['id'], 'title': record['title'], 'status': 'already-linked',
                'linked_document': obs['url'], 'next_step': 'Resume this blog and compare Google before editing; local work was retained.'}
    value = studio.new_id(args.title)
    create = studio.parser().parse_args(['--root', str(root), 'article', 'create',
        '--title', args.title.strip(), '--mode', 'existing', '--voice', 'preserve'])
    record = studio.article_record(root, create, value)
    transfer = uuid.uuid4().hex
    stage = Path(tempfile.mkdtemp(prefix='.google-start-', dir=root))
    directory = studio.inside(root, 'articles', value)
    try:
        studio.save_artifact(stage, 'original', body, record, label='Google manuscript intake')
        studio.save_artifact(stage, 'draft', body, record, label='Google manuscript intake')
        snapshot(stage, transfer, 'local', body)
        snapshot(stage, transfer, 'document', body)
        formatted, local_files = save_formatted_snapshot(stage, transfer, files)
        google = state(record)
        google['transfers'][transfer] = {'status': 'confirmed', 'kind': 'draft',
            'direction': 'from-google', 'document': obs, 'local_sha256': obs['content_sha256'],
            'confirmed_at': studio.now(), 'formatted_snapshot': formatted}
        google['baselines']['draft'] = {'transfer': transfer,
            'local_sha256': obs['content_sha256'], 'document': obs}
        record['next_step'] = 'Proofread or edit this manuscript; Google operations use the linked original Doc.'
        studio.persist(stage, 'articles', record)
        if directory.exists():
            raise ValueError('Article already exists; no local writing was replaced.')
        os.rename(stage, directory)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    studio.write_json(studio.inside(root, '.active-article.json'), {'id': value})
    discard(root, args.snapshot)  # Only removes a capture that sits in this workspace's staging folder.
    return {'id': value, 'title': record['title'], 'status': 'started-from-google',
            'linked_document': obs['url'], 'transfer': transfer, 'formatted_snapshot': formatted,
            'local_snapshot': local_files, 'next_step': record['next_step']}


def command(root, args):
    if args.action == 'start':return start(root, args)
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
        supplied = args.observation or args.file or args.snapshot
        if base and not args.new_document:
            if not args.snapshot and not (args.observation and args.file):
                raise ValueError('Read the linked Google Doc before preparing another handoff.')
            target, remote_body = observed(args)
            check = compare(directory, record, kind, target, remote_body)
            if check['status'] in ('remote-only', 'conflict'):
                raise ValueError('Google content changed. Return or resolve those edits before writing.')
            if not check['guard']:
                raise ValueError('Existing-document writes need a revision guard; create a new copy instead.')
        elif supplied:
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
        formatted_baseline = (google['baselines'].get(kind) or {}).get('document', {}).get('format_sha256')
        if getattr(args, 'snapshot', None):
            snapshot_files = formatted_snapshot(args.snapshot, obs, body)
        elif obs.get('format_sha256'):
            raise ValueError('A formatting observation needs its --snapshot artifacts.')
        elif formatted_baseline:
            # A hand-built observation would silently drop the formatting baseline that live status,
            # suggestions and comments depend on.
            raise ValueError('This blog has a formatted Google baseline. Capture the Doc with google_roundtrip.py '
                             'capture and pass that capture as --snapshot; nothing was saved.')
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
        if not obs.get('structure_verified') or not same_text(directory, transfer, saved, obs, body):
            raise ValueError('Readback must match the selected copy and verify its structure and links.')
        snapshot(directory, transfer, 'document', body)
        saved.update(status='confirmed', document=obs, confirmed_at=studio.now(), direction='to-google')
        google['baselines'][kind] = {'transfer': transfer, 'local_sha256': saved['local_sha256'], 'document': obs}
        result = {'id': record['id'], 'transfer': transfer, 'status': 'confirmed'}
    else:
        check = compare(directory, record, kind, obs, body, root)
        if args.action == 'compare':return {'id': record['id'], **check}
        if check['comparison'] != args.expected_comparison:
            raise ValueError('The comparison changed. Re-read both versions and compare again.')
        previous = google['baselines'][kind]
        accepted, how = choose_accepted(args, directory, previous, check, local_body(directory, kind), body)
        if kind == 'draft' and record['stop_point'] in ('outline', 'brief'):
            raise ValueError('This task stops before drafting. Keep its existing stop point.')
        if kind == 'draft' and record['mode'] == 'existing' and not (directory / 'ORIGINAL.md').is_file():
            raise ValueError('Preserve the imported original before accepting an edited draft.')
        transfer = uuid.uuid4().hex
        snapshot(directory, transfer, 'local', accepted)
        snapshot(directory, transfer, 'document', body)
        if studio.digest(accepted.encode()) != check['local_sha256']:
            studio.save_artifact(directory, kind, accepted, record)
        google['transfers'][transfer] = {'status': 'confirmed', 'kind': kind, 'direction': 'from-google',
            'local_sha256': studio.digest(accepted.encode()), 'document': obs, 'confirmed_at': studio.now(),
            'resolved': bool(args.resolution_file), 'merged': how == 'clean-merge',
            'previous_transfer': previous['transfer']}
        # Remote text is the common baseline. A local merge, or local edits kept as they were, stay visibly unsent.
        kept_local = how is None and check['status'] in ('unchanged', 'local-only')
        synced_local = previous['local_sha256'] if kept_local else obs['content_sha256']
        google['baselines'][kind] = {'transfer': transfer, 'local_sha256': synced_local, 'document': obs}
        result = {'id': record['id'], 'transfer': transfer, 'status': 'accepted', 'outcome': check['status'],
                  'merge': how, 'reviews': studio.freshness(root, directory, record)}
        if how == 'clean-merge' or (kept_local and check['status'] == 'local-only'):
            result['next_step'] = 'Local edits that Google does not have yet were kept. Send them when the author asks.'
    if snapshot_files:
        shared_files, local_files = save_formatted_snapshot(directory, transfer, snapshot_files)
        google['transfers'][transfer]['formatted_snapshot'] = shared_files
        result['formatted_snapshot'] = shared_files
        result['local_snapshot'] = local_files
        prune_local_native(directory, google)
    studio.persist(directory, 'articles', record)
    finish_staging(root, args, result)
    return result


def canonical_text(text):
    """Paragraph text without incidental whitespace: trailing spaces, runs of blank lines, a final newline."""
    lines = []
    for line in (raw.rstrip() for raw in text.replace('\r\n', '\n').split('\n')):
        if line or (lines and lines[-1]):
            lines.append(line)
    while lines and not lines[-1]:
        lines.pop()
    return '\n'.join(lines)


def same_text(directory, transfer, saved, obs, body):
    """Readback equals the frozen copy: byte for byte, or differing only in incidental whitespace."""
    if saved['local_sha256'] == obs['content_sha256']:
        return True
    frozen = snapshot_path(directory, transfer, 'local')
    if frozen.is_symlink() or not frozen.is_file():
        return False
    data = frozen.read_bytes()
    return studio.digest(data) == saved['local_sha256'] and canonical_text(data.decode('utf-8')) == canonical_text(body)


def finish_staging(root, args, result):
    """Staged inputs that reached their checkpoint are removed; anything outside staging is left alone."""
    from google_drive import discard, staging_root
    if result.get('status') not in ('accepted', 'confirmed'):
        return
    discard(root, getattr(args, 'snapshot', None))
    expected = getattr(args, 'expected_comparison', None)
    if expected:
        discard(root, staging_root(root) / ('merge-' + expected[:16] + '.md'))


def add_parser(groups):
    commands = groups.add_parser('google', help='Local Google Docs checkpoints; provider calls stay in the harness').add_subparsers(dest='action', required=True)
    intake = commands.add_parser('start', help='Start a blog from an inspected existing Google Doc')
    intake.add_argument('--title', required=True)
    intake.add_argument('--snapshot', required=True, help='Capture folder from google_roundtrip.py capture')
    intake.add_argument('--observation', help='Defaults to observation.json in the capture folder')
    intake.add_argument('--file', help='Defaults to document.md in the capture folder')
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
        p.add_argument('--snapshot', help='Capture folder from google_roundtrip.py capture; supplies the observation '
                       'and Markdown, and its formatted snapshot is saved by confirm and accept')
        p.add_argument('--observation', help='Defaults to observation.json in the capture folder')
        p.add_argument('--file', help='Accepted text in the same Markdown projection used for handoff; defaults to '
                       'document.md in the capture folder')
        if name == 'prepare':p.add_argument('--new-document', action='store_true')
        if name == 'confirm':p.add_argument('--transfer', required=True)
        if name == 'accept':
            p.add_argument('--expected-comparison', required=True)
            p.add_argument('--resolution-file', help='Only the author-approved merge or replacement after showing the conflict')
            p.add_argument('--discard-remote', action='store_true',
                           help='With --resolution-file: the author chose to drop text that only Google changed')
