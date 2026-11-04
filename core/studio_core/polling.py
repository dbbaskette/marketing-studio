"""Bounded metadata-only change signal; never surveys content or starts work."""
import hashlib
import os
from pathlib import Path
import secrets
import stat
import time

SKIP = {'.git', 'node_modules', '__pycache__', 'intake-drafts', '.cache'}


def snapshot(engine, data, *, maximum=5000, seconds=.075):
    started = time.monotonic()
    digest = hashlib.sha256()
    count = 0
    complete = True
    space = engine.workspace
    roots = [Path(data), Path(os.environ.get('STUDIOS_CONFIG') or Path.home()/'.config/studios-config.json')]
    if space is not None: roots.append(space.root)
    pending = list(roots)
    while pending:
        path = pending.pop()
        count += 1
        if count > maximum or time.monotonic()-started > seconds:
            complete = False
            break
        try:
            held = path.lstat()
            digest.update(str((str(path), held.st_mode, held.st_ino, held.st_size, held.st_mtime_ns, held.st_ctime_ns)).encode())
            if stat.S_ISDIR(held.st_mode):
                children = []
                with os.scandir(path) as entries:
                    for entry in entries:
                        if count+len(pending)+len(children) >= maximum or time.monotonic()-started > seconds:
                            complete = False
                            break
                        if entry.name not in SKIP: children.append(Path(entry.path))
                if not complete: break
                pending.extend(sorted(children, reverse=True))
        except (OSError, ValueError):
            digest.update(str((str(path), 'unavailable')).encode())
    with engine._lock:
        active = any(run.busy or run.workers or run.thread and run.thread.is_alive()
                     for run in engine._runs.values())
    # An incomplete signal must fail open to the ordinary, authoritative reads.
    return {'revision': digest.hexdigest() if complete else secrets.token_hex(32),
            'active': bool(active), 'complete': complete}
