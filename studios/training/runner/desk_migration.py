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

WORKSPACE = '@training-workspace/hub.json'
CONSEQUENCES = ('Open only the listed existing material parts for editing in conversation. '
    'Incomplete work stays incomplete; earlier approvals and inputs stay in History. '
    'Nothing is approved, made Ready, generated or delivered. Broader work needs an explicit desk scope change. '
    'This workspace requires Training Studio 4.7.0 or newer. Close older running instances first; '
    'already configured older runners may ignore the requirement. Nothing is installed or updated.')
CHANGED = 'The training or its saved inputs changed. Preview Open on the desk again.'


def _json(files, name):
    if name not in files:
        raise ValueError(f'{name} is missing. Keep using the saved flow until it is restored.')
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
        raise ValueError('No usable teaching plan or supported deck outline is saved yet. Continue with the saved flow first.')
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
            raise ValueError(f'{name} has no saved input record. Continue with its saved flow first.')
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


def prepare_migration(record, saved_inputs):
    blockers, retained, targets, required = [], [], [], []
    try:
        session, original = format.originals(saved_inputs.get(format.SESSION), saved_inputs.get(format.RUN))
        if record != original:
            raise ValueError('The saved run does not match the preview inputs.')
        if any(name in saved_inputs for name in (*format.WRITES, format.PENDING)) or drafts.on_desk(record):
            raise ValueError('Use this training’s existing desk or explicit migration recovery.')
        if session['stage'] == 'done':
            raise ValueError('Use the existing finished Open on the desk action.')
        if record.get('problem') or record.get('question'):
            raise ValueError('Resolve the saved failure or question in its saved flow before opening it on the desk.')
        targets, required = materials(session, record, saved_inputs)
        retained = [workspace.label(name) for name in targets]
        if record.get('halt'):
            retained.append('The earlier ' + record['halt'] + ' runner status stays in History; conversation editing does not resume it.')
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
    blockers = [SYNC_WAIT] if busy or any(local.values()) or engine._checking or root in engine.pending_commit else []
    if space.address:
        who = json.loads(identity) if identity else {}
        driver = record.get('driver')
        if not isinstance(who, dict) or who.get('schema') != 1 or not isinstance(driver, dict) or re.fullmatch(r'[0-9a-f]{16}', str(who.get('id'))) is None or driver.get('computer') != who['id']:
            blockers.append('This computer does not own the training. Use its saved team controls first.')
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
            blockers.append('Shared saved records, retained inputs and the existing workspace record must first be committed through the existing workspace workflow. Keep the saved flow available; migration does not commit those edits.')
    return {'head': gitstate.hub.git(space.repo, 'rev-parse', 'HEAD'), 'inputs': basis}, list(dict.fromkeys(blockers))


def _token(files, guard):
    value = {'files': {name: format.digest(data) for name, data in files.items()}, 'guard': guard, 'scope': ['part']}
    return 'tm1.' + base64.urlsafe_b64encode(hashlib.sha256(json.dumps(value, sort_keys=True).encode()).digest()).decode().rstrip('=')


def migration_preview(engine, path):
    try:
        _, root, record, files, guard, blockers = _snapshot(engine, path)
        prepared = prepare_migration(record, files)
        return {**prepared, 'path': str(root), 'expected': _token(files, guard),
                'blockers': prepared['blockers'] + blockers, 'consequences': CONSEQUENCES}
    except (OSError, ValueError, TypeError, KeyError, WorkspaceError) as error:
        return {'path': str(path), 'expected': '', 'scope': ['part'], 'targets': [], 'retained': [],
                'writes': [], 'blockers': [str(error)], 'consequences': CONSEQUENCES}


def _write(path, data):
    workspace.write_atomic(path, data)
    with Path(path).open('rb') as stream:
        os.fsync(stream.fileno())
    directory = os.open(Path(path).parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _path(space, root, name):
    return space.root / gitstate.MARKER if name == WORKSPACE else root / name


def _restore_index(space, root, writes, before, check=False):
    paths = [gitstate.inside(space, _path(space, root, name)) for name in writes]
    if not isinstance(before, str):
        raise WorkspaceError('The saved migration index cannot be verified.')
    for entry in before.split('\0'):
        if entry:
            header, _, name = entry.partition('\t')
            if name not in paths or not re.fullmatch(r'[0-7]{6} [a-f0-9]{40,64} 0', header):
                raise WorkspaceError('The saved migration index has an unsupported entry.')
    if not check:
        gitstate.hub.git(space.repo, 'reset', '-q', 'HEAD', '--', *paths)
        if before and gitstate.hub.run(space.repo, 'update-index', '-z', '--index-info', input=before).returncode:
            raise WorkspaceError('The migration index could not be restored; keep its recovery record.')


def _committed(space, root, writes):
    for name, data in writes.items():
        result = gitstate.hub.run(space.repo, 'show', f'HEAD:{gitstate.inside(space, _path(space, root, name))}')
        if result.returncode or result.stdout.encode() != data:
            return False
    return True


def _prepared_index(space, root, writes):
    entries = []
    for name, data in writes.items():
        relative = gitstate.inside(space, _path(space, root, name))
        result = gitstate.hub.run(space.repo, 'hash-object', '--stdin', input=data.decode())
        if result.returncode or not re.fullmatch(r'[a-f0-9]{40,64}', result.stdout.strip()):
            raise WorkspaceError('The prepared migration index cannot be verified.')
        entries.append((relative, f'100644 {result.stdout.strip()} 0\t{relative}\0'))
    return ''.join(entry for _, entry in sorted(entries))


def _check_recovery_index(space, root, writes, before, prepared):
    _restore_index(space, root, writes, before, check=True)
    _restore_index(space, root, writes, prepared, check=True)
    if prepared != _prepared_index(space, root, writes):
        raise WorkspaceError('The prepared migration index changed. Keep its recovery record.')
    paths = [gitstate.inside(space, _path(space, root, name)) for name in writes]
    current = gitstate.hub.git(space.repo, 'ls-files', '--stage', '-z', '--', *paths)
    if current not in (before, prepared):
        raise WorkspaceError('The migration staging index changed. Nothing was replaced; keep its recovery record.')


def _recover(space, root, expected):
    journal = json.loads(migration_records._bytes(root / format.PENDING, limit=8_000_000))
    fields = {'schema', 'product', 'id', 'expected', 'originals', 'after', 'before_workspace', 'index_before', 'index_prepared'}
    if set(journal) != fields or type(journal['schema']) is not int or journal['schema'] != 1 or journal['product'] != 'Training Studio' or journal['id'] != root.name or journal['expected'] != expected \
            or journal['originals'] != {name: format.digest(migration_records._bytes(root / name)) for name in (format.SESSION, format.RUN)} \
            or not isinstance(journal['after'], dict) or set(journal['after']) != {*format.WRITES, WORKSPACE}:
        raise WorkspaceError('The interrupted opening cannot be verified. Keep its recovery record.')
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
    for name, data in after.items():
        path = _path(space, root, name)
        if path.exists() and path.read_bytes() != data and not (name == WORKSPACE and path.read_bytes() == original_marker):
            raise WorkspaceError('The interrupted desk metadata changed. Nothing was replaced.')
    if _committed(space, root, after):
        (root / format.PENDING).unlink()
        return True
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
        if effective.get('halt'):
            effective['migration_saved_status'] = {'halt': effective['halt'], 'halt_after': effective.get('halt_after')}
            effective['halt'] = None
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
                   'after': {name: base64.b64encode(data).decode() for name, data in writes.items()}}
        committed = False
        try:
            _write(root / format.PENDING, json.dumps(journal).encode())
            for name, data in writes.items():
                _write(_path(space, root, name), data)
            gitstate.commit(space, session['title'] + ': open unfinished work on the desk', [_path(space, root, name) for name in writes])
            committed = True
            (root / format.PENDING).unlink()
        except BaseException:
            if not committed and not _committed(space, root, writes):
                _check_recovery_index(space, root, writes, journal['index_before'], journal['index_prepared'])
                for name in format.WRITES:
                    (root / name).unlink(missing_ok=True)
                _write(space.root / gitstate.MARKER, marker_bytes)
                _restore_index(space, root, writes, guard['index'])
                (root / format.PENDING).unlink(missing_ok=True)
            raise
    from runner.desk_chat import show
    return show(engine, root)
