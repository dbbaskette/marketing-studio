"""Training Studio's bounded unfinished session/run migration and explicit recovery."""
import base64
import copy
import hashlib
import json
import os
import re
from pathlib import Path

import checks
import home
import migration_records
import sync_guidance
import workspace
from workspace import WorkspaceError
from runner import drafts, gitstate, pipeline
from studio_core import training_migration as format, research_contract
from studio_core.sync_guard import worker_in_progress, SYNC_WAIT

# ruff: noqa: F821  names bound from studio_core.shared_runner are unseen by a linter;
# test_shared_runner_use checks the bound parts, and the suites call the rest.
from studio_core import modules
from studio_core.shared_runner import desk_migration as _shared
modules.bind(globals(), _shared, _shared.NAMES)

WORKSPACE = '@training-workspace/hub.json'
CONSEQUENCES = ('Open only the listed existing material parts for editing in conversation. '
    'Incomplete work stays incomplete; earlier approvals and inputs stay in History. '
    'Nothing is approved, made Ready, generated or delivered. Broader work needs an explicit desk scope change. '
    'This workspace requires Training Studio 4.7.0 or newer. Close older running instances first; '
    'already configured older runners may ignore the requirement. Nothing is installed or updated.')
CHANGED = 'The training or its saved inputs changed. Preview Open on the desk again.'
EARLY = ('No usable teaching plan or supported deck outline is saved, so there is nothing to '
         'open on the desk.')
FAILED = ('It stopped on a failure or a worker’s question before its teaching plan was '
          'written, so there is nothing to open on the desk.')
FINISHED = 'Use the existing finished Open on the desk action.'
# What the preview says it keeps of a saved failure or worker question, once a plan exists.
KEPT_FAILURE = ('The earlier failure stays in History. Its step stays unfinished and is not '
                'tried again.')
KEPT_QUESTION = ('The worker’s unanswered question stays in History. Its step stays '
                 'unfinished.')
DESK_WORK = 'Use this training’s existing desk or explicit migration recovery.'
# Why a saved-flow training is a read-only record: the sentence its record shows.
NOTHING_MADE = ('It stopped before its teaching plan was written, so nothing was made that '
                'could be opened on the desk.')
UNREADABLE = ('Its saved run or session record cannot be read, or is in a form this version '
              'does not understand.')
# A run record that is not even a JSON object: nobody can tell which flow wrote it.
UNREAD = 'Its run record cannot be read at all, so how this training was made cannot be told.'
MISSING = 'A saved file it depends on is missing or cannot be read.'
# Its folder could not be walked to check it: a linked file, or more than this version reads.
UNWALKED = ('Its folder holds a linked file or more than this version reads, so its saved '
            'work cannot be checked.')
# What the preview says when another computer owns the training, and when shared originals
# are not committed: both clear once the person acts, and the record then opens on the desk.
OWNER = 'Another computer runs this training. Take it over here first.'
SHARED = ('Shared saved records, retained inputs and the existing workspace record must first '
          'be committed through the existing workspace workflow; opening on the desk does not '
          'commit those edits.')
# How large a small record may be for lists to read it (a run or a session record).
SMALL = 16_000_000
BRING = ('A conversation keeps it outside the workspace. Bring it in first; it is then '
         'classed like any other saved training.')


def _json(files, name):
    if name not in files:
        raise ValueError(f'{name} is missing.')
    return json.loads(files[name])


def _material_files(session):
    """Finite native names, without invoking readers or discovering arbitrary paths."""
    return format.material_files(session)


def materials(session, record, files):
    names = _material_files(session)
    retained, required = [], [format.SESSION, format.RUN]
    for level in session['levels'] or [None]:
        name = workspace.qualify('blueprint', level)
        file = names[name]
        outline = workspace.prefix(level) + pipeline.OUTLINE
        if file in files:
            format.shared_material(file, files[file])
            text = files[file].decode('utf-8')
            parsed = checks.parse_blueprint(text)
            if not parsed['objectives'] or not parsed['modules']:
                raise ValueError(f'{file} is not a usable saved teaching plan.')
            retained.append(name)
            required.append(file)
        elif outline in files:
            raise ValueError(f'{file} is required to interpret the saved deck outline. Restore it first.')
        if outline in files:
            from runner import deck
            format.shared_material(outline, files[outline])
            saved = _json(files, outline)
            slides = saved.get('slides') if isinstance(saved, dict) else None
            if not isinstance(slides, list) or not slides or any(not isinstance(slide, dict)
                    or not isinstance(slide.get('id'), str) or not isinstance(slide.get('title'), str)
                    or not isinstance(slide.get('notes', ''), str) for slide in slides):
                raise ValueError('The saved deck outline cannot be read losslessly.')
            if any(not isinstance(slide.get('points', []), list) or any(not isinstance(point, dict)
                    or not isinstance(point.get('text', ''), str) for point in slide.get('points', [])) for slide in slides):
                raise ValueError('The saved slide points cannot be read losslessly.')
            problems = deck.rules(saved, files[file].decode(), delivery=session['settings'].get('delivery', 'reading'))
            if problems:
                raise ValueError('The saved deck outline needs attention: ' + ' '.join(problems))
            required.append(outline)
    if not retained:
        raise ValueError(EARLY)
    for name, file in names.items():
        base = workspace.split(name)[0].partition(':')[0]
        if base in ('document', 'brief', 'scenario', 'yoodli', 'deck') and file in files:
            if base != 'deck':
                text = files[file].decode()
                if not text.strip():
                    raise ValueError(f'{file} has no usable saved text.')
                drafts.codec_of(name).split(text)
            retained.append(name)
    # Every recorded retained material keeps its dependency interpretation, including
    # older input hashes. Missing inputs refuse; changed usable inputs remain holds.
    for name in retained:
        entry = session['artifacts'].get(name)
        if entry is None:
            raise ValueError(f'{name} has no saved input record.')
        for key, value in entry['built_from'].items():
            if key in names and names[key] not in files:
                raise ValueError(f'{name} needs its saved {key} input. Restore it first.')
            if key == 'research':
                research_file = 'research/facts.json' if session.get('research_contract') else '.harness-research/research.json'
                for file in (research_file, 'research-report.md', '.harness-research/research-report.md'):
                    if file not in files:
                        raise ValueError('The saved research bundle or its approved copy is missing.')
                facts = _json(files, research_file)
                if not isinstance(facts, dict) or facts.get('schema') not in (1, 2):
                    raise ValueError('The saved research record cannot be interpreted.')
            if key == 'profile' and not isinstance(value, str):
                raise ValueError('The saved Yoodli profile cannot be verified.')
    from runner import documents
    if documents.INDEX in files:
        index = _json(files, documents.INDEX)
        if not isinstance(index, dict) or index.get('schema') != 1 or not isinstance(index.get('documents'), list):
            raise ValueError('The saved source index cannot be read.')
        for item in index['documents']:
            if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not documents.IDENT.fullmatch(item['id']) or not isinstance(item.get('name'), str):
                raise ValueError('A saved source record cannot be read.')
            text, original = documents._files(item['id'], Path(item['name']).suffix.lower())
            if original not in files or item.get('readable') is True and text not in files:
                raise ValueError('A required original source or readable source copy is missing.')
            if item.get('sha256') and format.digest(files[original]) != item['sha256']:
                raise ValueError('A required original source changed.')
    required.extend(format.declared_inputs(session, retained)[0])
    origin = {'required': sorted(set(required))}
    format.shared_inputs(origin, lambda name: files.get(name))
    if documents.INDEX in files:
        format.local_sources(lambda name: files.get(name))
    return list(dict.fromkeys(retained)), sorted(set(required))


def _small(root: Path, name: str):
    """One small record read as JSON, or None where it is missing, unreadable, not JSON or
    larger than SMALL."""
    try:
        with (root / name).open('rb') as stream:
            data = stream.read(SMALL + 1)
        return json.loads(data) if len(data) <= SMALL else None
    except (OSError, ValueError, UnicodeError):
        return None


def record_kind(root: Path) -> str:
    """Which kind of training a folder holds, from its two small records alone, as lists and
    polling ask it: 'desk' (either record says flow desk, or it has desk metadata or an
    interrupted opening), 'unread' (its run record is not a JSON object and nothing says
    desk, so which flow made it cannot be told) or 'saved' (a readable run record without
    flow: the earlier gated flow's). Reads at most the run and session records."""
    if any((root / name).exists() or (root / name).is_symlink()
           for name in (*format.WRITES, format.PENDING)):
        return 'desk'
    run, session = _small(root, format.RUN), _small(root, format.SESSION)
    if any(isinstance(raw, dict) and drafts.on_desk(raw) for raw in (run, session)):
        return 'desk'
    return 'saved' if isinstance(run, dict) else 'unread'


def _start_form(files) -> bool:
    """Whether a saved training's start form can be read, to start new work from it: a
    supported session record, its intake and a run record that is at least JSON."""
    try:
        session = json.loads(files[format.SESSION])
        run = json.loads(files[format.RUN])
    except (KeyError, TypeError, ValueError, UnicodeError):
        return False
    return format.session_supported(session) and isinstance(run, dict) \
        and bool(files.get('intake.md', b'').strip())


def _read_only(files, said, reason):
    return {'outcome': 'read-only', 'said': said, 'reason': reason,
            'next': 'copy' if _start_form(files) else 'new'}


def classify(files) -> dict:
    """What becomes of one saved-flow training, from its files alone (`desk_chat._files`).

    - {'outcome': 'migrates', 'session', 'record', 'targets', 'required'}: the explicit
      migration opens it on the desk (the preview may still name a passing blocker: a
      worker in hand, another computer driving it, originals not yet committed).
    - {'outcome': 'read-only', 'said', 'reason', 'next'}: it can be neither continued on the
      desk nor moved there. `said` is the preview's refusal, `reason` the read-only record's
      sentence, `next` 'copy' (Start new work from this) or 'new' (Start a new training).
    - {'outcome': 'finished', 'said'}: finished work keeps its own Open on the desk.
    - {'outcome': 'desk', 'said'}: not saved-flow work: desk work, or an opening's own
      recovery.
    Only reads. The read-only outcome is work stopped before its teaching plan, and records
    or dependencies that cannot be read or understood."""
    # Desk work first, whatever its records hold: desk metadata, an interrupted opening, or
    # a run record that says flow desk (a newer version's desk work among it).
    if any(name in files for name in (*format.WRITES, format.PENDING)):
        return {'outcome': 'desk', 'said': DESK_WORK}
    def loaded(name):
        try:
            return json.loads(files[name])
        except (KeyError, TypeError, ValueError, UnicodeError):
            return None
    raw = loaded(format.RUN)
    if any(isinstance(found, dict) and drafts.on_desk(found)
           for found in (raw, loaded(format.SESSION))):
        return {'outcome': 'desk', 'said': DESK_WORK}
    try:
        session, record = format.originals(files.get(format.SESSION), files.get(format.RUN))
    except (ValueError, KeyError, TypeError, UnicodeError) as error:
        # A run record that is not even an object: which flow made it cannot be told.
        return _read_only(files, str(error), UNREADABLE if isinstance(raw, dict) else UNREAD)
    # A record the runner itself refuses to read cannot be opened on the desk either: once
    # opened, the desk reads the same record.
    from runner.engine import check_record
    try:
        check_record(raw, 'this training')
    except WorkspaceError as error:
        return _read_only(files, str(error), UNREADABLE)
    if session['stage'] == 'done':
        return {'outcome': 'finished', 'said': FINISHED}
    try:
        targets, required = materials(session, record, files)
    except (ValueError, KeyError, TypeError, UnicodeError) as error:
        if str(error) == EARLY:
            # A failure or question before any plan keeps its own refusal sentence.
            said = FAILED if record.get('problem') or record.get('question') else EARLY
            return _read_only(files, said, NOTHING_MADE)
        # Missing or unreadable dependencies. A sentence that points at the saved flow is
        # not repeated on a record that can no longer be continued.
        detail = str(error) if 'saved flow' not in str(error) else ''
        return _read_only(files, str(error), (MISSING + ' ' + detail).strip())
    return {'outcome': 'migrates', 'session': session, 'record': record,
            'targets': targets, 'required': required}


def outcome(engine, path) -> dict | None:
    """`classify` for a training in the workspace, as the page and the preview ask it. A
    training a conversation keeps outside the workspace is brought in first ('bring'). None
    where there is no training at all. Only reads."""
    from runner.desk_chat import _files
    root = engine.driven(path)
    if root is None:
        folder = Path(path)
        if (folder / format.SESSION).is_file() and not (folder / format.RUN).exists():
            return {'outcome': 'bring', 'said': 'There is no saved training there.', 'reason': BRING}
        return None
    if record_kind(root) == 'desk':
        return {'outcome': 'desk', 'said': DESK_WORK}
    try:
        files = _files(root)
    except (OSError, WorkspaceError) as error:
        # The folder cannot be walked: its start form may still be read from the three
        # small files the start form needs, each read on its own.
        small = {}
        for name in (format.SESSION, format.RUN, 'intake.md'):
            path = root / name
            try:
                if not path.is_symlink() and path.is_file() and path.stat().st_size <= SMALL:
                    small[name] = path.read_bytes()
            except OSError:
                pass
        return {'outcome': 'read-only', 'said': str(error), 'reason': UNWALKED,
                'next': 'copy' if _start_form(small) else 'new'}
    found = classify(files)
    return {key: value for key, value in found.items() if key not in ('session', 'record')}


def prepare_migration(record, saved_inputs):
    blockers, retained, targets, required = [], [], [], []
    try:
        _, original = format.originals(saved_inputs.get(format.SESSION), saved_inputs.get(format.RUN))
        if record != original:
            raise ValueError('The saved run does not match the preview inputs.')
        found = classify(saved_inputs)
        if found['outcome'] != 'migrates':
            raise ValueError(found['said'])
        targets, required = found['targets'], found['required']
        retained = [workspace.label(name) for name in targets]
        if record.get('halt'):
            retained.append('The earlier ' + record['halt'] + ' runner status stays in History; conversation editing does not resume it.')
        # A failure or worker question after the plan is kept as History: the step it
        # stopped stays unfinished, and nothing is tried again or answered.
        if record.get('problem'):
            retained.append(KEPT_FAILURE)
        if record.get('question'):
            retained.append(KEPT_QUESTION)
    except (ValueError, KeyError, TypeError, UnicodeError) as error:
        blockers.append(str(error))
    return {'blockers': blockers, 'retained': retained + ['Original files, History, source and guidance pins, Google baselines and real decisions'],
            'writes': [] if blockers else [*format.WRITES, WORKSPACE], 'scope': ['part'],
            'targets': targets, 'required': required}


def _snapshot(engine, path):
    from runner.desk_chat import _files
    space = engine.space()
    root = engine.driven(path)
    if root is None:
        raise WorkspaceError('There is no saved training there.')
    files = _files(root)
    record = _json(files, format.RUN)
    session = _json(files, format.SESSION)
    format.originals(files[format.SESSION], files[format.RUN], root.name)
    marker = space.root / gitstate.MARKER
    marker_bytes = migration_records._bytes(marker)
    identity_path = home.data_root() / 'computer.json'
    identity = migration_records._bytes(identity_path) if identity_path.is_file() else None
    state = engine._runs.get(str(root))
    local = {key: bool(getattr(state, key, False)) for key in ('busy', 'queued', 'gone', 'again', 'workers')}
    busy = worker_in_progress(space.repo, refusal=WorkspaceError)
    pending = record.get('drafts', {})
    busy = busy or any(name in files for name in ('.training-studio/lock', '.harness-research/research.lock', '.studio-research/lock')) \
        or any(name.endswith(('/step.lock', '/.lock')) for name in files) \
        or any(job['status'] in ('queued', 'working', 'ready') for job in pending.get('jobs', [])) \
        or bool(pending.get('updates')) or pending.get('update_chain', {}).get('status') == 'working' \
        or any(item.get('redrawing') or item.get('look_pending') or any(note['status'] in ('waiting', 'drawing') for note in item.get('notes', [])) for item in record['deck'].values())
    guard = {'workspace': [str(space.repo), space.folder, space.branch, space.address],
             'identity': identity.hex() if identity else None, 'workers': local,
             'busy': bool(busy), 'checking': engine._checking,
             'marker': base64.b64encode(marker_bytes).decode()}
    if any('profile' in entry['built_from'] for entry in session['artifacts'].values()):
        profile, profile_bytes = migration_records._profile(root)
        guard['profile'] = [str(profile), format.digest(profile_bytes)]
    scope = [gitstate.inside(space, _path(space, root, name)) for name in (*format.WRITES, WORKSPACE)]
    guard['index'] = gitstate.hub.git(space.repo, 'ls-files', '--stage', '-z', '--', *scope)
    _restore_index(space, root, (*format.WRITES, WORKSPACE), guard['index'], check=True)
    guard['head_before'] = _scoped_head(space, root)
    _validate_head_before(space, root, guard['head_before'])
    blockers = [SYNC_WAIT] if busy or any(local.values()) or engine._checking or root in engine.pending_commit else []
    if space.address:
        who = json.loads(identity) if identity else {}
        driver = record.get('driver')
        if not isinstance(who, dict) or who.get('schema') != 1 or not isinstance(driver, dict) or re.fullmatch(r'[0-9a-f]{16}', str(who.get('id'))) is None or driver.get('computer') != who['id']:
            blockers.append(OWNER)
    for name in session.get('pending_local_decks', {}):
        workspace.pending_local_deck(root, session, name)
        from runner.desk_chat import _read_restore
        _read_restore(root, name)
    for name in files:
        if name.endswith(('work/deck/state.json', 'brand/contract.json', 'deck/design.json', 'deck/review.json')) and not isinstance(_json(files, name), dict):
            raise WorkspaceError('A saved native deck record cannot be read.')
    if session.get('research_contract') and session.get('research'):
        research_contract.read_bundle(root / 'research')
    shared, dirty = _shared_basis(space, root, session, record, files)
    guard['shared'] = shared
    blockers.extend(dirty)
    return space, root, record, files, guard, blockers


def _shared_basis(space, root, session, record, files):
    """Only a shared workspace needs byte-identical committed common inputs.

    Private work/sources/checker files remain local; this does not implicitly commit them.
    """
    if not space.address:
        return None, []
    prepared = prepare_migration(record, files)
    shared = set(prepared['required'])
    if not prepared['blockers']:
        shared.update(format.shared_inputs({'required': prepared['required']}, lambda name: files.get(name)))
    basis, blockers = {}, []
    for name in sorted({*shared, WORKSPACE}):
        relative = gitstate.inside(space, _path(space, root, name))
        head = gitstate.hub.run(space.repo, 'rev-parse', '--verify', f'HEAD:{relative}')
        current = gitstate.hub.run(space.repo, 'hash-object', '--no-filters', '--', relative)
        staged = gitstate.hub.git(space.repo, 'ls-files', '--stage', '-z', '--', relative)
        digest = head.stdout.strip() if head.returncode == 0 else None
        basis[name] = {'head': digest, 'index': staged}
        if head.returncode or current.returncode or current.stdout.strip() != digest or staged != f'100644 {digest} 0\t{relative}\0':
            blockers.append(SHARED)
    return {'head': gitstate.hub.git(space.repo, 'rev-parse', 'HEAD'), 'inputs': basis}, list(dict.fromkeys(blockers))


def _token(files, guard):
    value = {'files': {name: format.digest(data) for name, data in files.items()}, 'guard': guard, 'scope': ['part']}
    return 'tm1.' + base64.urlsafe_b64encode(hashlib.sha256(json.dumps(value, sort_keys=True).encode()).digest()).decode().rstrip('=')


def _said(found) -> dict:
    """The classification as the preview carries it beside its blockers."""
    if found is None:
        return {}
    return {'outcome': {key: found[key] for key in ('outcome', 'reason', 'next') if key in found}}


def migration_preview(engine, path):
    try:
        _, root, record, files, guard, blockers = _snapshot(engine, path)
        prepared = prepare_migration(record, files)
        return {**prepared, 'path': str(root), 'expected': _token(files, guard),
                'blockers': prepared['blockers'] + blockers, 'consequences': CONSEQUENCES,
                **_said(classify(files))}
    except (OSError, ValueError, TypeError, KeyError, WorkspaceError) as error:
        try:
            found = outcome(engine, path)
        except (OSError, ValueError, TypeError, KeyError, WorkspaceError):
            found = None
        return {'path': str(path), 'expected': '', 'scope': ['part'], 'targets': [], 'retained': [],
                'writes': [], 'blockers': [str(error)], 'consequences': CONSEQUENCES, **_said(found)}


def _write(path, data):
    workspace.write_atomic(path, data)
    with Path(path).open('rb') as stream:
        os.fsync(stream.fileno())
    directory = os.open(Path(path).parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _committed(space, root, writes):
    entries = {}
    for entry in _prepared_index(space, root, writes).split('\0'):
        if entry:
            header, _, relative = entry.partition('\t')
            mode, digest, _ = header.split()
            entries[relative] = f'{mode} blob {digest}\t{relative}\0'
    return _scoped_head(space, root) == {name: entries[gitstate.inside(space, _path(space, root, name))] for name in writes}


def _scoped_head(space, root):
    paths = {gitstate.inside(space, _path(space, root, name)): name for name in (*format.WRITES, WORKSPACE)}
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
    if not isinstance(basis, dict) or set(basis) != {*format.WRITES, WORKSPACE} \
            or any(basis[name] != '' for name in format.WRITES) \
            or not isinstance(basis[WORKSPACE], str) or (basis[WORKSPACE] and not re.fullmatch(
                r'100(?:644|755) blob [a-f0-9]{40,64}\t' + re.escape(relative) + '\0', basis[WORKSPACE])):
        raise WorkspaceError('The original migration publication basis cannot be verified. Keep its recovery record.')


def _check_rollback_head(space, root, basis):
    _validate_head_before(space, root, basis)
    if _scoped_head(space, root) != basis:
        raise WorkspaceError('The migration publication state cannot be verified. Keep its recovery record; nothing was rolled back.')


def _check_outputs(space, root, writes, before_workspace, *, complete=False):
    for name, data in writes.items():
        path = _path(space, root, name)
        if not path.exists() and not path.is_symlink():
            # Only new sidecars may still be absent before publication completes.
            if complete or name == WORKSPACE:
                raise WorkspaceError('The interrupted desk metadata is missing. Keep its recovery record.')
            continue
        current = migration_records._bytes(path)
        if current != data and not (name == WORKSPACE and current == before_workspace and not complete):
            raise WorkspaceError('The interrupted desk metadata changed. Nothing was replaced; keep its recovery record.')


def _prepared_index(space, root, writes):
    entries = []
    for name, data in writes.items():
        relative = gitstate.inside(space, _path(space, root, name))
        result = gitstate.hub.run(space.repo, 'hash-object', '--stdin', input=data.decode())
        if result.returncode or not re.fullmatch(r'[a-f0-9]{40,64}', result.stdout.strip()):
            raise WorkspaceError('The prepared migration index cannot be verified.')
        entries.append((relative, f'100644 {result.stdout.strip()} 0\t{relative}\0'))
    return ''.join(entry for _, entry in sorted(entries))


def _recover(space, root, expected):
    journal = json.loads(migration_records._bytes(root / format.PENDING, limit=8_000_000))
    fields = {'schema', 'product', 'id', 'expected', 'originals', 'after', 'before_workspace', 'index_before', 'index_prepared', 'head_before'}
    if set(journal) != fields or type(journal['schema']) is not int or journal['schema'] != 1 or journal['product'] != 'Training Studio' or journal['id'] != root.name or journal['expected'] != expected \
            or journal['originals'] != {name: format.digest(migration_records._bytes(root / name)) for name in (format.SESSION, format.RUN)} \
            or not isinstance(journal['after'], dict) or set(journal['after']) != {*format.WRITES, WORKSPACE}:
        raise WorkspaceError('The interrupted opening cannot be verified. Keep its recovery record.')
    _validate_head_before(space, root, journal['head_before'])
    after = {name: base64.b64decode(data, validate=True) for name, data in journal['after'].items()}
    original_marker = base64.b64decode(journal['before_workspace'], validate=True)
    for data in (original_marker, after[WORKSPACE]):
        marker = json.loads(data)
        if not isinstance(marker, dict) or type(marker.get('schema')) is not int or marker['schema'] != 1 or marker.get('tool') != 'training-studio' or marker.get('folder') != space.folder or marker.get('branch') != space.branch or not isinstance(marker.get('name'), str):
            raise WorkspaceError('The interrupted workspace requirement cannot be verified.')
    if sync_guidance.as_tuple(json.loads(after[WORKSPACE])['minimum_runtime']) < (4, 7, 0):
        raise WorkspaceError('The interrupted workspace requirement is unsupported.')
    before_marker = json.loads(original_marker)
    proposed_marker = json.loads(after[WORKSPACE])
    required_marker = dict(before_marker)
    if sync_guidance.as_tuple(required_marker['minimum_runtime']) < (4, 7, 0):
        required_marker['minimum_runtime'] = '4.7.0'
    if proposed_marker != required_marker:
        raise WorkspaceError('The interrupted workspace requirement changed unrelated settings.')
    format.validated(json.loads(after[format.ORIGIN]), json.loads(after[format.DESK_SESSION]), json.loads(after[format.DESK_RUN]),
                     migration_records._bytes(root / format.SESSION), migration_records._bytes(root / format.RUN), root.name)
    _check_recovery_index(space, root, after, journal['index_before'], journal['index_prepared'])
    durable = _committed(space, root, after)
    _check_outputs(space, root, after, original_marker, complete=durable)
    if durable:
        (root / format.PENDING).unlink()
        return True
    _check_rollback_head(space, root, journal['head_before'])
    for name in format.WRITES:
        (root / name).unlink(missing_ok=True)
    _write(space.root / gitstate.MARKER, original_marker)
    _restore_index(space, root, after, journal['index_before'])
    (root / format.PENDING).unlink()
    return False


def migrate(engine, path, expected):
    space, root = engine.space(), engine.driven(path)
    if root is None:
        raise WorkspaceError('There is no saved training there.')
    with gitstate.workspace_locked(space, engine.files, configured=True):
        if (root / format.PENDING).exists():
            from runner.desk_chat import _files
            _files(root)
            if worker_in_progress(space.repo, refusal=WorkspaceError, recovering_training=root / format.PENDING):
                raise WorkspaceError(SYNC_WAIT)
            try:
                settled = _recover(space, root, expected)
            except (ValueError, TypeError, KeyError, OSError) as error:
                raise WorkspaceError('The interrupted opening cannot be verified. Keep its recovery record.') from error
            if not settled:
                raise WorkspaceError('The interrupted opening was rolled back. Preview Open on the desk again.')
        if migration_records.pair(root) is not None:
            if migration_records.pair(root)[0]['expected'] != expected:
                raise WorkspaceError(CHANGED)
            from runner.desk_chat import show
            return show(engine, root)
        _, current, record, files, guard, blockers = _snapshot(engine, path)
        prepared = prepare_migration(record, files)
        if current != root or blockers or prepared['blockers']:
            raise WorkspaceError(' '.join(blockers + prepared['blockers']))
        if not expected or _token(files, guard) != expected:
            raise WorkspaceError(CHANGED)
        session = copy.deepcopy(_json(files, format.SESSION))
        effective = copy.deepcopy(record)
        session['flow'] = 'desk'
        effective.update(flow='desk', execution='conversation', conversation_scope=['part'],
                         migration_targets=prepared['targets'], unfinished_migration=True)
        saved_status = {}
        if effective.get('halt'):
            saved_status.update(halt=effective['halt'], halt_after=effective.get('halt_after'))
            effective['halt'] = None
        # The effective record carries no live failure or question: neither is retried or
        # answered on the desk. Both stay, as they were, in the original run record and in
        # the History the desk shows.
        for key in ('problem', 'question'):
            if effective.get(key):
                saved_status[key] = copy.deepcopy(effective[key])
                effective[key] = None
        if saved_status:
            effective['migration_saved_status'] = saved_status
        origin = format.receipt(files[format.SESSION], files[format.RUN], session['id'], expected, prepared['required'], prepared['targets'],
                                sources='sources/supplied/index.json' in files)
        a, b = {'origin': origin, 'record': session}, {'origin': origin, 'record': effective}
        format.validated(origin, a, b, files[format.SESSION], files[format.RUN], root.name)
        marker_bytes = base64.b64decode(guard['marker'])
        marker = json.loads(marker_bytes)
        if sync_guidance.as_tuple(marker['minimum_runtime']) < (4, 7, 0):
            marker['minimum_runtime'] = '4.7.0'
            new_marker = (json.dumps(marker, indent=2) + '\n').encode()
        else:
            new_marker = marker_bytes
        writes = {format.ORIGIN: (json.dumps(origin, indent=2) + '\n').encode(),
                  format.DESK_SESSION: (json.dumps(a, indent=2) + '\n').encode(),
                  format.DESK_RUN: (json.dumps(b, indent=2) + '\n').encode(), WORKSPACE: new_marker}
        if any(len(data) > 1_000_000 for data in writes.values()):
            raise WorkspaceError('The prepared desk records exceed the bounded saved format size.')
        journal = {'schema': 1, 'product': 'Training Studio', 'id': root.name, 'expected': expected, 'originals': {name: format.digest(files[name]) for name in (format.SESSION, format.RUN)},
                   'before_workspace': guard['marker'], 'index_before': guard['index'],
                   'index_prepared': _prepared_index(space, root, writes),
                   'head_before': guard['head_before'],
                   'after': {name: base64.b64encode(data).decode() for name, data in writes.items()}}
        try:
            _write(root / format.PENDING, json.dumps(journal).encode())
            for name, data in writes.items():
                _write(_path(space, root, name), data)
            gitstate.commit(space, session['title'] + ': open unfinished work on the desk', [_path(space, root, name) for name in writes])
            _check_recovery_index(space, root, writes, journal['index_before'], journal['index_prepared'])
            if not _committed(space, root, writes):
                raise WorkspaceError('The migration publication state cannot be verified. Keep its recovery record.')
            _check_outputs(space, root, writes, marker_bytes, complete=True)
            (root / format.PENDING).unlink()
        except BaseException:
            _check_recovery_index(space, root, writes, journal['index_before'], journal['index_prepared'])
            durable = _committed(space, root, writes)
            _check_outputs(space, root, writes, marker_bytes, complete=durable)
            if not durable:
                _check_rollback_head(space, root, journal['head_before'])
                for name in format.WRITES:
                    (root / name).unlink(missing_ok=True)
                _write(space.root / gitstate.MARKER, marker_bytes)
                _restore_index(space, root, writes, guard['index'])
                (root / format.PENDING).unlink(missing_ok=True)
            raise
    from runner.desk_chat import show
    return show(engine, root)
