"""Bounded incremental metadata signal, with explicit age-limited cached results."""
import hashlib
import os
from pathlib import Path
import secrets
import stat
import threading
import time

SKIP = {'.git', 'node_modules', '__pycache__', 'intake-drafts', '.cache'}
CACHE_SECONDS = 30
MAX_DEPTH = 64


def _metadata(path, depth=0):
    """Keep only a bounded directory stack; never read content or follow links."""
    try:
        held = path.lstat()
    except FileNotFoundError:
        yield str((str(path), 'missing')).encode()
        return
    yield str((str(path), held.st_mode, held.st_ino, held.st_size,
               held.st_mtime_ns, held.st_ctime_ns)).encode()
    if stat.S_ISDIR(held.st_mode):
        if depth >= MAX_DEPTH:
            raise OSError('Metadata traversal depth exceeded')
        with os.scandir(path) as entries:
            for entry in entries:
                if entry.name not in SKIP:
                    yield from _metadata(Path(entry.path), depth + 1)
                else:
                    yield None  # Skipped entries still consume the traversal budget.


def _walk(roots):
    for root in roots:
        yield from _metadata(root)


class _Scan:
    def __init__(self, roots):
        self.roots = roots
        self.lock = threading.Lock()
        self.walk = None
        self.revision = None
        self.completed_at = 0
        self.total = self.fingerprint = 0

    def close(self):
        if self.walk is not None:
            self.walk.close()
        self.walk = None

    def advance(self, maximum, seconds):
        started = time.monotonic()
        if maximum <= 0 or seconds <= 0:
            self.close()
            return {'revision': secrets.token_hex(32), 'complete': False, 'cached': False}
        if self.walk is None:
            self.walk = _walk(self.roots)
            self.total = self.fingerprint = 0
        complete = False
        try:
            for _ in range(maximum):
                if time.monotonic() - started >= seconds:
                    break
                item = next(self.walk)
                if item is not None:
                    # Order-independent: scandir order need not be stable. Paths are part
                    # of each identity, and the count also binds additions/deletions.
                    self.fingerprint = (self.fingerprint + int.from_bytes(hashlib.sha256(item).digest(), 'big')) % (1 << 256)
                    self.total += 1
        except StopIteration:
            self.revision = hashlib.sha256(f'{self.total}:{self.fingerprint}'.encode()).hexdigest()
            self.completed_at = time.monotonic()
            self.close()
            complete = True
        except (OSError, ValueError):
            # A scan failure is not evidence of unchanged work, even with a cached result.
            self.close()
            self.revision = None
        cached = (not complete and self.revision is not None
                  and time.monotonic() - self.completed_at < CACHE_SECONDS)
        return {'revision': self.revision if complete or cached else secrets.token_hex(32),
                'complete': complete, 'cached': cached}


def snapshot(engine, data, *, maximum=5000, seconds=.075):
    space = engine.workspace
    roots = [Path(data), Path(os.environ.get('STUDIOS_CONFIG') or Path.home()/'.config/studios-config.json')]
    if space is not None:
        roots.append(space.root)
    roots = tuple(roots)
    with engine._lock:
        active = any(run.busy or run.workers or run.thread and run.thread.is_alive()
                     for run in engine._runs.values())
        scan = getattr(engine, '_polling_scan', None)
        if scan is None or scan.roots != roots:
            scan = engine._polling_scan = _Scan(roots)
    with scan.lock:
        signal = scan.advance(maximum, seconds)
    # `complete` refers only to the scan just finished. `cached` explicitly refers
    # to a previous completed scan, never a claim that this partial scan is fresh.
    # Clients must keep active-job refresh and their periodic authoritative reads.
    return {**signal, 'active': bool(active)}
