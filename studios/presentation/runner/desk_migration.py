"""Presentation Studio's fixed unfinished migration, pure preview and recoverable apply."""
import base64
import copy
import hashlib
import json
import re
from pathlib import Path

import home
from workspace import WorkspaceError
from runner import decks, desk, gitstate
from runner.steps import existing
from studio_core import presentation_migration as format
from studio_core import research_contract
from studio_core.sync_guard import worker_in_progress, SYNC_WAIT
import sync_guidance

# ruff: noqa: F821  names bound from studio_core.shared_runner are unseen by a linter;
# test_shared_runner_use checks the bound parts, and the suites call the rest.
from studio_core import modules
from studio_core.shared_runner import desk_migration as _shared
modules.bind(globals(), _shared, _shared.NAMES)

WORKSPACE = '@presentation-workspace/hub.json'

CONSEQUENCES = ('Open existing slide parts for editing in conversation. Incomplete work stays '
                'incomplete. Nothing is approved, drawn or delivered. Broader work requires an '
                'explicit desk scope change.')
CONSEQUENCES += (' This workspace will require Presentation Studio 4.8.1 or newer. Close older '
                 'running instances before applying; already configured older runners may ignore '
                 'that requirement. Nothing is installed or updated.')
CONSEQUENCES += (' Shared work requires every retained shared file in this deck and the workspace '
                 'record to match its committed version and staging index. Commit intended changes '
                 'with Git, then preview again. '
                 'Private ignored inputs stay local. Local-only migration is not a complete Git backup.')
CHANGED = 'The deck or its saved inputs changed. Preview Open on the desk again.'
# A deck stopped before its outline was drafted has no slide parts to open on the desk.
NOTHING_MADE = ('This deck was stopped before its outline was drafted, so nothing was made '
                'that can be opened on the desk.')
UNSUPPORTED = 'This saved run format is not supported.'
UNREAD = 'This deck’s saved record cannot be read.'
NOTHING_READ = ('This deck was stopped before the deck it started from was read, so nothing '
                'was made that can be opened on the desk.')
NOT_HERE = ('The deck it started from is not on this computer, so this deck can be opened on '
            'the desk only on the computer that holds it.')
UNREADABLE_DECK = 'The deck it started from cannot be read.'
UNREADABLE_DRAWING = 'A saved record of its drawing cannot be read.'
USE_DESK = 'Use this deck’s existing desk or finished Open on the desk action.'
METADATA = 'This deck already has desk metadata or pending recovery.'
# A pause, a stop and a failure are each kept in History; none is resumed on the desk.
HALTS = {'paused': 'The prior runner pause remains in History. Conversation editing will not '
                   'resume that runner.',
         'stopped': 'The prior runner stop or failure remains in History. Conversation editing '
                    'will not resume that runner.'}
HALTS['failed'] = HALTS['stopped']
# A worker's question left unanswered is kept in History too; nothing answers it on the desk.
QUESTION = ('The saved worker question remains in History, unanswered. Conversation editing '
            'will not answer it or resume that runner, and its step stays unfinished.')


class Kept(ValueError):
    """A saved deck the migration cannot open on the desk. `why` is the reason its read-only
    record gives, and what the preview says of it (GitHub issue #542)."""

    def __init__(self, why: str):
        super().__init__(why)
        self.why = why


class Elsewhere(ValueError):
    """Not unfinished saved-flow work for the migration: desk work, a deck delivered by the
    saved flow (the finished Open on the desk), or a deck with desk metadata or an opening
    still pending. `kind` is 'desk' or 'finished'."""

    def __init__(self, said: str, kind: str):
        super().__init__(said)
        self.kind = kind


SHARED = ('Retained shared files in this deck and the existing workspace record must first match '
          'their committed versions and staging index. Commit intended changes with Git, then '
          'preview again. Migration does not commit those edits.')
# A deck another computer runs, or nobody does, in a shared workspace: taken here first.
NOT_OURS = 'This computer does not run this deck. Take it first, then open it on the desk.'


def _json(files, name, required=False):
    if name not in files:
        if required:
            raise Kept(f'{name} is missing.')
        return None
    return json.loads(files[name])


def materials(record, files):
    """Strictly read retained material/dependencies; no repair, conversion or acceptance."""
    if not format.supported(record):
        raise Kept(UNSUPPORTED)
    format.shared_material('run.json', files.get('run.json'))
    if record['route'] == 'existing':
        if existing.SOURCE not in files or not files[existing.SOURCE].startswith(b'PK\x03\x04'):
            raise Kept(NOT_HERE if existing.SOURCE not in files else UNREADABLE_DECK)
        if 'classify.json' not in files:
            # Stopped before the deck it started from was read: nothing made yet.
            raise Kept(NOTHING_READ)
        inventory = _json(files, 'classify.json', True)
        format.shared_material('classify.json', files.get('classify.json'))
        slides = inventory.get('slides') if isinstance(inventory, dict) else None
        if not isinstance(slides, list) or not slides or any(
                not isinstance(s, dict) or type(s.get('number')) is not int
                or not isinstance(s.get('objects'), list) for s in slides):
            raise ValueError('The saved original-deck inventory cannot be read.')
        read = existing.given_name(record)
        if read != existing.SOURCE:
            # Upgraded from Selected changes and redrawn: the inventory is of the deck as it was
            # at the upgrade. That deck must be here as it was kept, and the deck given as it was.
            upgraded = record['upgraded']
            if read not in files or not files[read].startswith(b'PK\x03\x04') \
                    or hashlib.sha256(files[read]).hexdigest() != upgraded.get('sha256'):
                raise ValueError('The deck the redesign started from is missing or changed. '
                                 'Continue on the computer that upgraded it.')
            kept = upgraded.get('original_sha256')
            if kept and hashlib.sha256(files[existing.SOURCE]).hexdigest() != kept:
                raise ValueError('The original deck differs from the one that was upgraded.')
        if inventory.get('sha256') != hashlib.sha256(files[read]).hexdigest():
            raise ValueError('The original deck differs from its saved inventory.')
    if not desk.selected(record):
        if 'outline.json' not in files:
            raise Kept(NOTHING_MADE)
        format.shared_material('outline.json', files.get('outline.json'))
        saved = _json(files, 'outline.json', True)
        slides = saved.get('slides') if isinstance(saved, dict) else None
        if not isinstance(saved, dict) or saved.get('version') != 1 \
                or saved.get('delivery') not in ('live', 'reading') or not isinstance(slides, list) or not slides:
            raise ValueError('The saved outline is missing or uses an unsupported format.')
        ids = []
        for slide in slides:
            if not isinstance(slide, dict) or not isinstance(slide.get('id'), str) \
                    or not re.fullmatch(r'[A-Za-z0-9_-]+', slide['id']) \
                    or slide.get('kind') not in ('cover', 'section', 'content', 'closing') \
                    or not isinstance(slide.get('title'), str) or not isinstance(slide.get('notes'), str):
                raise ValueError('The saved outline has an unsupported slide.')
            ids.append(slide['id'])
        if len(set(ids)) != len(ids):
            raise ValueError('The saved outline repeats a slide identifier.')
    index = _json(files, 'sources/supplied/index.json')
    if index is not None:
        if not isinstance(index, dict) or index.get('schema') != 1 or not isinstance(index.get('documents'), list):
            raise ValueError('The saved source list cannot be read.')
        from runner import documents
        for item in index['documents']:
            if not isinstance(item, dict) or not isinstance(item.get('name'), str) \
                    or not isinstance(item.get('id'), str) or not documents.IDENT.fullmatch(item['id']) \
                    or Path(item['name']).suffix.lower() not in documents.TYPES:
                raise ValueError('A saved source entry cannot be read.')
            text, original = documents._files(item['id'], Path(item['name']).suffix.lower())
            if original not in files or (item.get('readable') is True and text not in files):
                raise Kept('A required saved source is missing.')
            if item.get('sha256') and hashlib.sha256(files[original]).hexdigest() != item['sha256']:
                raise Kept('A pinned source changed.')
    if record['route'] == 'document' and not index:
        raise Kept('The imported source document is missing.')
    # Existing research's consumer validates complete captured bundles on the bounded copy.
    if record.get('research_contract') and (record['steps'].get('research-report') or {}).get('done') \
            and 'research/output.json' not in files:
        raise ValueError('The pinned research bundle is missing.')
    for name in ('work/build/state.json', 'work/patch-plan.json', 'brand/contract.json'):
        if name in files and not isinstance(_json(files, name), dict):
            raise Kept(UNREADABLE_DRAWING)
    return 'Selected changes' if desk.selected(record) else 'Outline and slide parts'


def _metadata(files) -> bool:
    return any(name in files for name in (format.RECORD, format.ORIGIN, format.PENDING))


def _assess(record, files, retained: list) -> None:
    """The preview's checks, in the order it has always made them, each refusal raised
    with the sentence the preview says. What it retains is added to `retained` as found."""
    if not isinstance(files.get('run.json'), bytes) or len(files['run.json']) > 1_000_000:
        raise ValueError('The original run record is too large or cannot be read.')
    retained.append(materials(record, files))
    if record.get('flow') == 'desk' or 'deliver.json' in files:
        raise Elsewhere(USE_DESK, 'desk' if record.get('flow') == 'desk' else 'finished')
    if _metadata(files):
        raise Elsewhere(METADATA, 'desk')
    halted = record.get('halted')
    if halted:
        if not isinstance(halted, dict) or halted.get('state') not in HALTS:
            raise Kept('This deck’s saved runner stop cannot be read.')
        retained.append(HALTS[halted['state']])
    if record.get('question'):
        retained.append(QUESTION)


def outcome(record, files, refusal=None) -> dict:
    """What becomes of a deck: the one answer the migration preview and the read-only
    record both use (GitHub issue #542).

    `record` is its run.json as read (None when it cannot be parsed), `files` its saved
    files by name as `desk_chat._files` reads them, and `refusal` the runner's own refusal
    to load it, when there is one. Returns one of these, each with `retained` (what the
    preview lists as kept) and `preview` (the preview's blocker, or None):

    - {'outcome': 'desk'}: desk work, whatever its schema (a newer version's too), or a
      deck with desk metadata, a migration receipt or an opening still pending. Never
      read-only and never migrated.
    - {'outcome': 'migrates', 'by': 'migration'}: the explicit migration opens it on the
      desk. A pause, a stop, a failure or a worker's unanswered question is kept in History
      and its step stays unfinished.
    - {'outcome': 'migrates', 'by': 'finished'}: delivered by the saved flow, it opens
      through the finished Open on the desk, which reads no saved runner stop.
    - {'outcome': 'read-only', 'why', 'next'}: nothing was made yet, or its record or a
      file it needs cannot be read or understood. `why` is the reason its read-only record
      gives, `next` its one next action ('copy': Start new work from this, where its start
      form can be read; 'new': start a new deck). `preview` is what the migration preview
      says of it.

    What is transient (a step in hand, another computer driving, shared files not yet
    committed) is the preview's own check, not this one. Only reads."""
    retained, said, error = [], None, None
    try:
        _assess(record, files, retained)
    except (ValueError, KeyError, TypeError, UnicodeError) as caught:
        error, said = caught, str(caught)
    found = {'retained': retained, 'preview': said}
    if (isinstance(record, dict) and record.get('flow') == 'desk') or _metadata(files):
        return {'outcome': 'desk', **found}
    form = record.get('form') if isinstance(record, dict) else None
    after = 'copy' if isinstance(form, dict) and form and record.get('route') in decks.ROUTES \
        else 'new'

    def read_only(why):
        return {'outcome': 'read-only', 'why': why, 'next': after, **found}

    if refusal is not None:
        return read_only(str(refusal))
    if not isinstance(record, dict):
        # Which flow made a record nobody can read is not known, so none is named.
        return read_only(UNREAD)
    if isinstance(error, Elsewhere):
        return {'outcome': 'migrates', 'by': 'finished', **found}
    if isinstance(error, Kept):
        return read_only(error.why)
    if error is not None:
        return read_only(said)
    return {'outcome': 'migrates', 'by': 'migration', **found}


def prepare_migration(record, saved_inputs):
    found = outcome(record, saved_inputs)
    blockers = [found['preview']] if found['preview'] else []
    return {'blockers': blockers, 'retained': found['retained'] + [
        'Original files, History, source and guidance pins, Google records and earlier decisions'],
        'writes': [] if blockers else [format.ORIGIN, format.RECORD, WORKSPACE], 'scope': ['part']}


def _snapshot(engine, path):
    from runner.desk_chat import _files
    space = engine.space()
    root = engine.driven(path)
    if root is None:
        raise WorkspaceError('There is no deck there.')
    files = _files(root)
    marker = space.root / gitstate.MARKER
    if marker.is_symlink() or not marker.is_file() or marker.stat().st_size > 1_000_000:
        raise WorkspaceError('The existing Presentation Studio workspace record is required.')
    marker_bytes = marker.read_bytes()
    record = _json(files, 'run.json', True)
    if format.supported(record) and record.get('research_contract') \
            and (record['steps'].get('research-report') or {}).get('done'):
        research_contract.read_bundle(root / 'research')
    identity_path = home.data_root() / 'computer.json'
    identity = identity_path.read_bytes() if identity_path.is_file() and not identity_path.is_symlink() else None
    state = engine._runs.get(str(root))
    local = {key: bool(getattr(state, key, False)) for key in ('busy', 'queued', 'gone', 'again')}
    pending = bool(record.get('desk_jobs') or (record.get('desk') or {}).get('edits')
                   or record.get('review_requested')) if isinstance(record, dict) else False
    busy = worker_in_progress(space.repo, refusal=WorkspaceError)
    guard = {'workspace': [str(space.repo), space.folder, space.branch, space.address],
             'identity': identity.hex() if identity else None, 'workers': local, 'busy': busy,
             'checking': engine._checking}
    guard['workspace_marker'] = base64.b64encode(marker_bytes).decode()
    scope = [gitstate.inside(space, _path(space, root, name)) for name in (format.ORIGIN, format.RECORD, WORKSPACE)]
    guard['index'] = gitstate.hub.git(space.repo, 'ls-files', '--stage', '-z', '--', *scope)
    _restore_index(space, root, (format.ORIGIN, format.RECORD, WORKSPACE), guard['index'], check=True)
    guard['head_before'] = _scoped_head(space, root)
    blockers = []
    for name in (format.ORIGIN, format.RECORD):
        relative = gitstate.inside(space, root / name)
        if gitstate.hub.git(space.repo, 'ls-files', '--stage', '-z', '--', relative) or guard['head_before'][name]:
            blockers.append('Saved desk metadata already exists in Git. Restore its paired records before continuing.')
    if busy or any(local.values()) or pending or engine._checking:
        blockers.append(SYNC_WAIT)
    if space.address:
        who = json.loads(identity) if identity else {}
        driver = record.get('driver') if isinstance(record, dict) else None
        if not isinstance(who, dict) or who.get('schema') != 1 or not isinstance(driver, dict) \
                or re.fullmatch(r'[0-9a-f]{16}', str(who.get('id'))) is None \
                or who.get('id') != driver.get('computer'):
            blockers.append(NOT_OURS)
    guard['shared'], dirty = _shared_basis(space, root, files)
    blockers.extend(dirty)
    return space, root, record, files, guard, blockers


def _object_format(space):
    algorithm = gitstate.hub.git(space.repo, 'rev-parse', '--show-object-format')
    if algorithm not in ('sha1', 'sha256'):
        raise WorkspaceError('The workspace Git object format cannot be verified.')
    return algorithm


def _blob(space, data, algorithm=None):
    algorithm = algorithm or _object_format(space)
    return hashlib.new(algorithm, b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def _head_entry(space, relative):
    return gitstate.hub.git(space.repo, 'ls-tree', '-z', 'HEAD', '--', relative)


def _shared_basis(space, root, files, *, marker=True):
    """Bounded retained deck files, with tracking taking precedence over ignoring."""
    if not space.address:
        return None, []
    prefix = gitstate.inside(space, root) + '/'
    heads = gitstate.hub.git(space.repo, 'ls-tree', '-r', '-z', 'HEAD', '--', prefix)
    staged = gitstate.hub.git(space.repo, 'ls-files', '--stage', '-z', '--', prefix)
    head_entries = {entry.partition('\t')[2][len(prefix):]: entry + '\0'
                    for entry in heads.split('\0') if entry}
    index_entries = {}
    for entry in staged.split('\0'):
        if entry:
            index_entries.setdefault(entry.partition('\t')[2][len(prefix):], []).append(entry + '\0')
    tracked = head_entries.keys() | index_entries.keys()
    names = set(files) | tracked
    names.difference_update((format.ORIGIN, format.RECORD, format.PENDING))
    if WORKSPACE in names:
        raise WorkspaceError('A retained deck file uses a reserved migration name.')
    untracked = sorted(names - tracked)
    ignored_names = set()
    if untracked:
        ignored = gitstate.hub.run(space.repo, 'check-ignore', '-z', '--stdin',
            input=''.join(prefix + name + '\0' for name in untracked))
        if ignored.returncode not in (0, 1):
            raise WorkspaceError('The retained shared input classification cannot be verified.')
        ignored_names = {name[len(prefix):] for name in ignored.stdout.split('\0') if name}
    algorithm = _object_format(space)
    basis, blockers = {}, []
    for name in sorted(names | ({WORKSPACE} if marker else set())):
        path = _path(space, root, name)
        relative = gitstate.inside(space, path)
        if name in ignored_names:
            continue
        head = _head_entry(space, relative) if name == WORKSPACE else head_entries.get(name, '')
        index = (gitstate.hub.git(space.repo, 'ls-files', '--stage', '-z', '--', relative)
                 if name == WORKSPACE else ''.join(index_entries.get(name, ())))
        basis[name] = {'head': head, 'index': index}
        match = re.fullmatch(r'(100644|100755) blob ([a-f0-9]{40,64})\t' + re.escape(relative) + '\0', head)
        data = path.read_bytes() if name == WORKSPACE else files.get(name)
        if not match or data is None:
            blockers.append(SHARED)
            continue
        mode, digest = match.groups()
        ordinary_mode = '100755' if path.stat().st_mode & 0o111 else '100644'
        if index != f'{mode} {digest} 0\t{relative}\0' or ordinary_mode != mode or _blob(space, data, algorithm) != digest:
            blockers.append(SHARED)
    return basis, list(dict.fromkeys(blockers))


def _token(files, guard):
    value = {'files': {name: hashlib.sha256(data).hexdigest() for name, data in files.items()},
             'guard': guard, 'scope': ['part']}
    return 'pm1.' + base64.urlsafe_b64encode(hashlib.sha256(
        json.dumps(value, sort_keys=True).encode()).digest()).decode().rstrip('=')


def migration_preview(engine, path):
    try:
        _, root, record, files, guard, blockers = _snapshot(engine, path)
        prepared = prepare_migration(record, files)
        return {**prepared, 'path': str(root), 'expected': _token(files, guard),
                'blockers': prepared['blockers'] + blockers, 'consequences': CONSEQUENCES}
    except (OSError, ValueError, TypeError, WorkspaceError) as error:
        return {'path': str(path), 'expected': '', 'scope': ['part'], 'retained': [],
                'writes': [], 'blockers': [str(error)], 'consequences': CONSEQUENCES}


def _write(path, data):
    from runner.desk_chat import _write as atomic
    atomic(path, data)


def _committed(space, root, writes):
    for name, data in writes.items():
        relative = gitstate.inside(space, _path(space, root, name))
        if _head_entry(space, relative) != f'100644 blob {_blob(space, data)}\t{relative}\0':
            return False
    return True


def _scoped_head(space, root):
    paths = {gitstate.inside(space, _path(space, root, name)): name
             for name in (format.ORIGIN, format.RECORD, WORKSPACE)}
    entries = gitstate.hub.git(space.repo, 'ls-tree', '-z', 'HEAD', '--', *paths)
    result = dict.fromkeys(paths.values(), '')
    for entry in entries.split('\0'):
        if entry:
            relative = entry.partition('\t')[2]
            if relative not in paths or result[paths[relative]]:
                raise WorkspaceError('The original migration publication basis cannot be verified.')
            result[paths[relative]] = entry + '\0'
    return result


def _validate_head_before(space, root, basis):
    relative = gitstate.inside(space, _path(space, root, WORKSPACE))
    if not isinstance(basis, dict) or set(basis) != {format.ORIGIN, format.RECORD, WORKSPACE} \
            or basis[format.ORIGIN] != '' or basis[format.RECORD] != '' \
            or not isinstance(basis[WORKSPACE], str) or (basis[WORKSPACE] and not re.fullmatch(
                r'100(?:644|755) blob [a-f0-9]{40,64}\t' + re.escape(relative) + '\0', basis[WORKSPACE])):
        raise WorkspaceError('The original migration publication basis cannot be verified. Keep its recovery record.')


def _check_rollback_head(space, root, basis, before_workspace):
    if basis is None:
        # Older journals can prove only this ordinary, unchanged marker state.
        # A dirty local marker needs the explicitly captured HEAD in a new journal.
        relative = gitstate.inside(space, _path(space, root, WORKSPACE))
        basis = {format.ORIGIN: '', format.RECORD: '',
                 WORKSPACE: f'100644 blob {_blob(space, before_workspace)}\t{relative}\0'}
    _validate_head_before(space, root, basis)
    if _scoped_head(space, root) != basis:
        raise WorkspaceError('The migration publication state cannot be verified. '
                             'Keep the recovery record and saved files; nothing was rolled back.')


def _prepared_index(space, root, writes):
    entries = [f'100644 {_blob(space, data)} 0\t{gitstate.inside(space, _path(space, root, name))}\0'
               for name, data in writes.items()]
    return ''.join(sorted(entries, key=lambda entry: entry.partition('\t')[2]))


def _check_shared_recovery(space, root, files, shared, after, before_workspace):
    current, blockers = _shared_basis(space, root, files, marker=False)
    if shared is None and current is None:
        return
    if not isinstance(shared, dict) or not isinstance(current, dict) or WORKSPACE not in shared \
            or blockers or current != {name: value for name, value in shared.items() if name != WORKSPACE}:
        raise WorkspaceError('The shared retained evidence changed. Keep the migration recovery record and restore its committed inputs.')
    relative = gitstate.inside(space, _path(space, root, WORKSPACE))
    prior = shared[WORKSPACE]
    match = re.fullmatch(r'(100644|100755) blob ' + _blob(space, before_workspace) + '\t' + re.escape(relative) + '\0', prior['head'])
    if not match or prior['index'] != f'{match[1]} {_blob(space, before_workspace)} 0\t{relative}\0':
        raise WorkspaceError('The original shared workspace record cannot be verified. Keep its recovery record.')
    prepared = f'100644 blob {_blob(space, after[WORKSPACE])}\t{relative}\0'
    if _head_entry(space, relative) not in (prior['head'], prepared):
        raise WorkspaceError('The shared workspace record changed. Keep its migration recovery record.')


def _check_workspace_change(space, before, after, *, legacy=False):
    old, new = json.loads(before), json.loads(after)
    if not isinstance(old, dict) or type(old.get('schema')) is not int or old['schema'] != 1 \
            or old.get('tool') != 'presentation-studio' or old.get('folder') != space.folder \
            or old.get('branch') != space.branch or not isinstance(old.get('name'), str):
        raise WorkspaceError('The interrupted workspace requirement cannot be verified.')
    needed = (4, 8, 0) if legacy else (4, 8, 1)
    wanted = dict(old)
    if sync_guidance.as_tuple(old['minimum_runtime']) < needed:
        wanted['minimum_runtime'] = '.'.join(map(str, needed))
    if new != wanted:
        raise WorkspaceError('The interrupted workspace requirement changed unrelated settings.')


def _check_outputs(space, root, writes, before_workspace, *, complete=False):
    for name, data in writes.items():
        path = _path(space, root, name)
        if path.is_symlink() or path.parent.is_symlink():
            raise WorkspaceError('The interrupted desk record changed. Keep its recovery record.')
        if not path.exists():
            if complete:
                raise WorkspaceError('The committed desk record changed. Keep its recovery record.')
            continue
        if path.read_bytes() != data and not (name == WORKSPACE and path.read_bytes() == before_workspace and not complete):
            raise WorkspaceError('The interrupted desk record changed. Nothing was replaced.')


def _recover(space, root, expected):
    if (root / format.PENDING).stat().st_size > 8_000_000:
        raise WorkspaceError('The migration recovery record is too large. Keep its saved files.')
    journal = json.loads((root / format.PENDING).read_bytes())
    fields = {'schema', 'expected', 'original', 'after', 'before_workspace', 'index_before'}
    if set(journal) not in (fields, fields | {'shared', 'index_prepared'}, fields | {'shared', 'index_prepared', 'head_before'}) or type(journal['schema']) is not int or journal['schema'] != 1 \
            or journal['expected'] != expected \
            or hashlib.sha256((root / 'run.json').read_bytes()).hexdigest() != journal['original']:
        raise WorkspaceError('The interrupted opening cannot be verified. Keep the saved files and inspect its recovery record.')
    if not isinstance(journal['after'], dict) or set(journal['after']) != {format.ORIGIN, format.RECORD, WORKSPACE}:
        raise WorkspaceError('The interrupted opening has unsupported writes.')
    after = {name: base64.b64decode(data, validate=True) for name, data in journal['after'].items()}
    before_workspace = base64.b64decode(journal['before_workspace'], validate=True)
    if 'head_before' in journal:
        _validate_head_before(space, root, journal['head_before'])
    _check_workspace_change(space, before_workspace, after[WORKSPACE], legacy=set(journal) == fields)
    _check_recovery_index(space, root, after, journal['index_before'],
                          journal.get('index_prepared', _prepared_index(space, root, after)))
    format.validated(json.loads(after[format.RECORD]), (root / 'run.json').read_bytes(), root.name,
                     json.loads(after[format.ORIGIN]))
    durable = _committed(space, root, after)
    _check_outputs(space, root, after, before_workspace, complete=durable)
    from runner.desk_chat import _files
    _check_shared_recovery(space, root, _files(root), journal.get('shared'), after, before_workspace)
    if durable:
        (root / format.PENDING).unlink()
        return True
    _check_rollback_head(space, root, journal.get('head_before'), before_workspace)
    for name in after:
        if name != WORKSPACE:
            (root / name).unlink(missing_ok=True)
    _write(space.root / gitstate.MARKER, before_workspace)
    _restore_index(space, root, after, journal['index_before'])
    (root / format.PENDING).unlink()
    return False


def migrate(engine, path, expected):
    space = engine.space()
    root = engine.driven(path)
    if root is None:
        raise WorkspaceError('There is no deck there.')
    with gitstate.workspace_locked(space, engine.files, configured=True):
        if (root / format.PENDING).exists():
            from runner.desk_chat import _files
            _files(root)  # bound recovery and reject links/nonordinary files before any write
            if worker_in_progress(space.repo, refusal=WorkspaceError,
                                  recovering_presentation=root / format.PENDING):
                raise WorkspaceError(SYNC_WAIT)
            try:
                recovered = _recover(space, root, expected)
            except (ValueError, TypeError, KeyError, OSError) as error:
                raise WorkspaceError('The interrupted opening cannot be verified. Keep its recovery record.') from error
            if not recovered:
                raise WorkspaceError('The interrupted opening was rolled back. Preview Open on the desk again.')
        if (root / format.RECORD).exists():
            value = json.loads((root / format.RECORD).read_bytes())
            decks.read_run(root)
            if value.get('expected') != expected:
                raise WorkspaceError(CHANGED)
            return engine.view(root)
        _, current_root, record, files, guard, blockers = _snapshot(engine, path)
        prepared = prepare_migration(record, files)
        if current_root != root or prepared['blockers'] or blockers:
            raise WorkspaceError(' '.join(prepared['blockers'] + blockers))
        if not expected or _token(files, guard) != expected:
            raise WorkspaceError(CHANGED)
        _validate_head_before(space, root, guard['head_before'])
        # Validate pinned research through its existing pure consumer on canonical local files.
        if record.get('research_contract') and (record['steps'].get('research-report') or {}).get('done'):
            research_contract.read_bundle(root / 'research')
        effective = copy.deepcopy(record)
        effective.update(flow='desk', execution='conversation', conversation_scope=['part'])
        effective['unfinished_migration'] = True
        if effective.get('halted'):
            effective['migration_saved_status'] = copy.deepcopy(effective['halted'])
            effective['halted'] = None
        if effective.get('question'):
            # Kept in History, unanswered: the desk never answers it, and its step stays
            # as the saved flow left it.
            effective['migration_saved_question'] = copy.deepcopy(effective['question'])
            effective['question'] = None
        value = {'schema': 1, 'product': 'Presentation Studio', 'id': record['id'],
                 'original': hashlib.sha256(files['run.json']).hexdigest(), 'expected': expected,
                 # Replay verifies shared metadata. Private sources/drawings are checked
                 # locally before migration/approval and need not exist on every clone.
                 'required': ['run.json', *(['classify.json'] if record['route'] == 'existing' else []),
                              *([] if desk.selected(record) else ['outline.json'])],
                 'record': effective}
        origin = format.receipt(value)
        format.validated(value, files['run.json'], root.name, origin)
        after = (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode()
        writes = {format.ORIGIN: (json.dumps(origin, indent=2) + '\n').encode(), format.RECORD: after}
        before_workspace = base64.b64decode(guard['workspace_marker'])
        workspace_record = json.loads(before_workspace)
        if sync_guidance.as_tuple(workspace_record['minimum_runtime']) < (4, 8, 1):
            workspace_record['minimum_runtime'] = '4.8.1'
            writes[WORKSPACE] = (json.dumps(workspace_record, indent=2, ensure_ascii=False) + '\n').encode()
        else:
            writes[WORKSPACE] = before_workspace
        journal = {'schema': 1, 'expected': expected, 'original': value['original'],
                   'before_workspace': base64.b64encode(before_workspace).decode(),
                   'index_before': guard['index'],
                   'index_prepared': _prepared_index(space, root, writes), 'shared': guard['shared'],
                   'head_before': guard['head_before'],
                   'after': {name: base64.b64encode(data).decode() for name, data in writes.items()}}
        journal_bytes = json.dumps(journal).encode()
        if len(journal_bytes) > 8_000_000 or len(after) > 2_000_000:
            raise WorkspaceError('The prepared desk records exceed the bounded saved format size.')
        committed = False
        try:
            _write(root / format.PENDING, journal_bytes)
            for name, data in writes.items():
                _write(_path(space, root, name), data)
            from runner.desk_chat import _files
            _check_shared_recovery(space, root, _files(root), guard['shared'], writes, before_workspace)
            _check_recovery_index(space, root, writes, guard['index'], journal['index_prepared'])
            gitstate.commit(space, f'{record["title"]}: open unfinished work on the desk',
                            [_path(space, root, name) for name in writes])
            committed = True
            _check_recovery_index(space, root, writes, guard['index'], journal['index_prepared'])
            (root / format.PENDING).unlink()
        except BaseException:
            # A commit wrapper may publish successfully and then fail. Leave the
            # journal for explicit retry rather than undoing committed ownership.
            _check_recovery_index(space, root, writes, guard['index'], journal['index_prepared'])
            durable = committed or _committed(space, root, writes)
            _check_outputs(space, root, writes, before_workspace, complete=durable)
            from runner.desk_chat import _files
            _check_shared_recovery(space, root, _files(root), guard['shared'], writes, before_workspace)
            if not durable:
                _check_rollback_head(space, root, guard['head_before'], before_workspace)
                for name in writes:
                    if name != WORKSPACE:
                        (root / name).unlink(missing_ok=True)
                _write(space.root / gitstate.MARKER, before_workspace)
                _restore_index(space, root, writes, guard['index'])
                (root / format.PENDING).unlink(missing_ok=True)
            raise
    return engine.view(root)
