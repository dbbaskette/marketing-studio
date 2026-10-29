"""Training Studio's fixed effective session/run boundary; originals stay immutable."""
import base64
import json
import stat
from pathlib import Path

from studio_core import training_migration as format


def _bytes(path, limit=1_000_000):
    root = Path(path)
    if root.is_symlink() or any(p.is_symlink() for p in root.parents):
        raise ValueError('Linked Training Studio migration records cannot be read.')
    if not stat.S_ISREG(root.stat().st_mode):
        raise ValueError('Training Studio records must be ordinary files.')
    with root.open('rb') as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError('The Training Studio record is too large.')
    return data


def pair(root):
    root = Path(root)
    if (root / format.PENDING).exists() or (root / format.PENDING).is_symlink():
        raise ValueError('An interrupted Open on the desk needs explicit migration retry. Keep its recovery record.')
    if not any((root / name).exists() or (root / name).is_symlink() for name in format.WRITES):
        return None
    origin = json.loads(_bytes(root / format.ORIGIN))
    session, run = (json.loads(_bytes(root / name)) for name in (format.DESK_SESSION, format.DESK_RUN))
    values = format.validated(origin, session, run, _bytes(root / format.SESSION), _bytes(root / format.RUN), root.name)
    format.shared_inputs(origin, lambda name: _bytes(root / name, format.input_limit(name)), values[0])
    local_inputs(root, origin, *values)
    return origin, *values


def _profile(root):
    import workspace
    path = workspace.profile_for(root)
    data = _bytes(path)
    profile = json.loads(data)
    lists = ('types', 'persona_required_types', 'persona_fields', 'goal_types')
    limits = ('context_chars', 'personas_max', 'goal_explanation_chars', 'goal_achieved_chars', 'goal_missed_chars')
    if not isinstance(profile, dict) or type(profile.get('schema')) is not int or profile['schema'] != 1 \
            or profile.get('profile') != 'yoodli' or not isinstance(profile.get('limits'), dict) \
            or any(not isinstance(profile.get(key), list) or not profile[key] or any(not isinstance(item, str) or not item for item in profile[key]) for key in lists) \
            or not isinstance(profile.get('mode_types'), dict) or any(not isinstance(key, str) or not isinstance(value, str) for key, value in profile['mode_types'].items()):
        raise ValueError('The local pinned Yoodli profile cannot be verified.')
    for key in limits:
        value = profile['limits'].get(key)
        if not isinstance(value, dict) or type(value.get('value')) is not int or value['value'] <= 0 or 'verified' not in value:
            raise ValueError('The local pinned Yoodli limits cannot be verified.')
    return path, data


def local_inputs(root, origin, session, run):
    import workspace
    if origin['local']['sources'] or run.get('documents'):
        format.local_sources(lambda name: _bytes(root / name, 8_000_000))
    if origin['local']['profile'] or any('profile' in item['built_from'] for item in session['artifacts'].values()):
        _profile(root)
    # These filenames are transient native state, not permanent shared requirements:
    # lossless return-delivered archives the local draft and removes its pending marker.
    for name in session.get('pending_local_decks', {}):
        marker = workspace.pending_local_deck(root, session, name)
        prefix = workspace.prefix(workspace.split(name)[1])
        data = _bytes(root / (prefix + 'deck/delivered-state.json'), 64_000_000)
        binding = run.get('delivered_restore', {}).get(name)
        value = json.loads(data)
        fields = {'schema', 'material', 'inputs', 'artifact', 'desk_ready', 'deck', 'delivered_sha256', 'files'}
        if marker.get('schema') != 2 or binding != marker['restore_sha256'] or format.digest(data) != binding \
                or not isinstance(value, dict) or set(value) != fields or type(value.get('schema')) is not int or value['schema'] != 1 \
                or value.get('material') != name or not isinstance(value.get('files'), dict) or not isinstance(value.get('inputs'), dict) \
                or any(value[key] is not None and not isinstance(value[key], dict) for key in ('artifact', 'deck')):
            raise ValueError('The local Google draft delivered-state proof cannot be verified.')
        total = 0
        for relative, content in value['files'].items():
            if not format.relative(relative) or not relative.startswith((prefix + 'deck/', prefix + 'work/deck/')) \
                    or relative == prefix + 'deck/delivered-state.json' or not isinstance(content, str):
                raise ValueError('The local delivered-state proof has unsupported paths.')
            total += len(base64.b64decode(content, validate=True))
            if total > 64_000_000:
                raise ValueError('The local delivered-state proof is too large.')


def record_bytes(root, name):
    value = pair(root)
    if value is None:
        path = Path(root) / name
        return path.read_bytes() if path.is_file() else None
    return (json.dumps(value[1 if name == format.SESSION else 2], sort_keys=True, ensure_ascii=False) + '\n').encode()


def record(root, name):
    data = record_bytes(root, name)
    value = json.loads(data) if data is not None else None
    if name == format.RUN and isinstance(value, dict):
        drafts = value.get('drafts', {})
        if not isinstance(drafts, dict) or not format.update_chain_supported(drafts.get('update_chain', {})):
            raise ValueError('The Training Studio update chain cannot be verified.')
    return value


def write(root, name, value, atomic):
    selected = pair(root)
    if selected is None:
        atomic(Path(root) / name, (json.dumps(value, indent=2, sort_keys=True) + '\n').encode())
        return
    origin, session, run = selected
    if name == format.SESSION:
        session = value
    else:
        run = value
    a, b = {'origin': origin, 'record': session}, {'origin': origin, 'record': run}
    format.validated(origin, a, b, _bytes(Path(root) / format.SESSION), _bytes(Path(root) / format.RUN), Path(root).name)
    path = format.DESK_SESSION if name == format.SESSION else format.DESK_RUN
    atomic(Path(root) / path, (json.dumps(a if name == format.SESSION else b, indent=2, sort_keys=True) + '\n').encode())


def from_snapshot(files, name, ident=None):
    if any(key in files for key in format.WRITES):
        origin = json.loads(files[format.ORIGIN])
        values = format.validated(origin, json.loads(files[format.DESK_SESSION]), json.loads(files[format.DESK_RUN]), files[format.SESSION], files[format.RUN], ident)
        return values[0 if name == format.SESSION else 1]
    return json.loads(files[name])
