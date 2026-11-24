"""Bounded incremental metadata signal, with explicit age-limited cached results.

A completed walk is reused, without walking again, by idle polls for IDLE_SECONDS. A
page shown on screen asks every 5 seconds and a hidden one every 20, so a single shown
page walks at most every other poll, several pages open on one studio share one walk,
and a person's own edit made outside the studio shows within IDLE_SECONDS plus one poll.
The pages still read everything at least once a minute. A poll made while the engine is
working always walks, and so does the first idle poll after it, because a working job
writes. A writer that changes the workspace, the data folder or the shared settings
calls `invalidate(engine)`, and the next poll walks.
"""
import hashlib
import os
from pathlib import Path
import secrets
import stat
import threading
import time

SKIP = {'.git', 'node_modules', '__pycache__', 'intake-drafts', '.cache'}
CACHE_SECONDS = 30
IDLE_SECONDS = 8
MAX_DEPTH = 64


def _identity(path, held):
    return str((str(path), held.st_mode, held.st_ino, held.st_size,
                held.st_mtime_ns, held.st_ctime_ns)).encode()


def _metadata(path, depth=0, held=None):
    """Keep only a bounded directory stack; never read content or follow links."""
    if held is None:
        try:
            held = Path(path).lstat()
        except FileNotFoundError:
            yield str((str(path), 'missing')).encode()
            return
    yield _identity(path, held)
    if stat.S_ISDIR(held.st_mode):
        if depth >= MAX_DEPTH:
            raise OSError('Metadata traversal depth exceeded')
        with os.scandir(path) as entries:
            for entry in entries:
                if entry.name in SKIP:
                    yield None  # Skipped entries still consume the traversal budget.
                    continue
                try:
                    # The directory listing's own record, never the link's target.
                    found = entry.stat(follow_symlinks=False)
                except FileNotFoundError:
                    yield str((entry.path, 'missing')).encode()
                    continue
                yield from _metadata(entry.path, depth + 1, found)


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
        # Whether the completed revision may stand in for a walk while idle: only a walk
        # made entirely while idle, with no invalidation since it started.
        self.quiet = False
        self.walk_quiet = False
        self.generation = 0
        self.walk_generation = 0
        self.retired = False   # replaced as the engine's scan: it never walks again

    def close(self):
        if self.walk is not None:
            self.walk.close()
        self.walk = None

    def retire(self):
        """Close its walk for good. Called holding `lock`, as it is replaced."""
        self.retired = True
        self.close()

    def invalidate(self):
        """Something was written: the next poll walks."""
        with self.lock:
            self.generation += 1
            self.quiet = False

    def advance(self, maximum, seconds, idle=True):
        started = time.monotonic()
        if self.retired or maximum <= 0 or seconds <= 0:
            # A replaced scan opens no new walk, so no directory is left open on it.
            self.close()
            return {'revision': secrets.token_hex(32), 'complete': False, 'cached': False}
        if not idle:
            self.quiet = self.walk_quiet = False
        elif (self.walk is None and self.quiet and self.revision is not None
              and started - self.completed_at < IDLE_SECONDS):
            # Reused, explicitly as a cached result: no walk was made for this poll.
            return {'revision': self.revision, 'complete': False, 'cached': True}
        if self.walk is None:
            self.walk = _walk(self.roots)
            self.total = self.fingerprint = 0
            self.walk_quiet, self.walk_generation = idle, self.generation
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
            self.quiet = self.walk_quiet and self.walk_generation == self.generation
            complete = True
        except (OSError, ValueError):
            # A scan failure is not evidence of unchanged work, even with a cached result.
            self.close()
            self.revision = None
            self.quiet = False
        cached = (not complete and self.revision is not None
                  and time.monotonic() - self.completed_at < CACHE_SECONDS)
        return {'revision': self.revision if complete or cached else secrets.token_hex(32),
                'complete': complete, 'cached': cached}


def invalidate(engine):
    """Call after writing the workspace, the data folder or the shared settings, so the
    next poll walks instead of reusing a revision from before the write."""
    with engine._lock:
        scan = getattr(engine, '_polling_scan', None)
    if scan is not None:
        scan.invalidate()


def snapshot(engine, data, *, maximum=5000, seconds=.075):
    space = engine.workspace
    roots = [Path(data), Path(os.environ.get('STUDIOS_CONFIG') or Path.home()/'.config/studios-config.json')]
    if space is not None:
        roots.append(space.root)
    roots = tuple(roots)
    replaced = None
    with engine._lock:
        active = any(run.busy or run.workers or run.thread and run.thread.is_alive()
                     for run in engine._runs.values())
        scan = getattr(engine, '_polling_scan', None)
        if scan is None or scan.roots != roots:
            replaced, scan = scan, _Scan(roots)
            engine._polling_scan = scan
    if replaced is not None:
        # Its unfinished walk holds open directory handles: close them now.
        with replaced.lock:
            replaced.retire()
    signal = None
    for _ in range(2):
        with scan.lock:
            if not scan.retired:
                signal = scan.advance(maximum, seconds, idle=not active)
                break
        # Another poll replaced it after this one took it (the workspace moved): the
        # engine's current scan answers instead.
        with engine._lock:
            scan = getattr(engine, '_polling_scan', scan)
    if signal is None:
        signal = {'revision': secrets.token_hex(32), 'complete': False, 'cached': False}
    # `complete` refers only to the scan just finished. `cached` explicitly refers
    # to a previous completed scan, never a claim that this partial scan is fresh.
    # Clients must keep active-job refresh and their periodic authoritative reads.
    return {**signal, 'active': bool(active)}
