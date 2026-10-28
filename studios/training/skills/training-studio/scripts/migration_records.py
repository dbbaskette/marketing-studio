"""Training Studio's fixed effective session/run boundary; originals stay immutable."""
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
    for name in origin['required']:
        format.shared_material(name, _bytes(root / name))
    return origin, *values


def record_bytes(root, name):
    value = pair(root)
    if value is None:
        path = Path(root) / name
        return path.read_bytes() if path.is_file() else None
    return (json.dumps(value[1 if name == format.SESSION else 2], sort_keys=True, ensure_ascii=False) + '\n').encode()


def record(root, name):
    data = record_bytes(root, name)
    return json.loads(data) if data is not None else None


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
