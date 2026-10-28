"""Reentrant, bounded write serialization for a local Studio workspace.

Lock files are persistent: unlinking one would allow writers to lock different
inodes. Merely constructing a lock (including inventory engines) creates nothing.
"""
from __future__ import annotations

import fcntl
import os
from pathlib import Path
import threading
import time

WAIT = 10.0


class LockPathChanged(RuntimeError):
    """The configured lock scope changed while an outer acquisition waited."""


def workspace_lock_path(repo: Path | None, data: Path) -> Path:
    """Resolve Git's directory, including linked-worktree/separate-git-dir files."""
    if repo is None:
        return Path(data).resolve() / 'studios-write.lock'
    dotgit = Path(repo).resolve() / '.git'
    if dotgit.is_file():
        text = dotgit.read_text(encoding='utf-8').strip()
        if not text.startswith('gitdir: ') or not text[8:].strip():
            raise ValueError('The workspace Git directory cannot be read.')
        folder = Path(text[8:].strip())
        dotgit = folder if folder.is_absolute() else dotgit.parent / folder
    dotgit = dotgit.resolve()
    if not dotgit.is_dir():
        raise FileNotFoundError('The workspace Git directory is unavailable.')
    return dotgit / 'studios-write.lock'


class ProcessRLock:
    """Thread RLock followed by an OS lock; one handle per outer acquisition."""

    def __init__(self, path, timeout=WAIT, refusal=TimeoutError):
        self._path = path
        self._timeout = timeout
        self._refusal = refusal
        self._thread = threading.RLock()
        self._depth = 0
        self._handle = None

    def _is_owned(self):
        return self._thread._is_owned()

    def acquire(self, blocking=True, timeout=-1):
        limit = self._timeout if timeout == -1 else timeout
        if limit < 0:
            raise ValueError('timeout must be nonnegative')
        deadline = time.monotonic() + limit
        if not self._thread.acquire(blocking, max(0, limit) if blocking else -1):
            return False
        if self._depth:
            self._depth += 1
            return True
        handle = None
        try:
            path = Path(self._path())
            path.parent.mkdir(parents=True, exist_ok=True)
            handle = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
            while True:
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    if Path(self._path()).resolve() != path.resolve():
                        raise LockPathChanged('The workspace changed while waiting to save. '
                                              'Try again in the current workspace.')
                    self._handle, self._depth = handle, 1
                    return True
                except BlockingIOError:
                    remaining = deadline - time.monotonic()
                    if not blocking or remaining <= 0:
                        os.close(handle)
                        self._thread.release()
                        return False
                    time.sleep(min(.05, remaining))
        except BaseException:
            if handle is not None:
                os.close(handle)
            self._thread.release()
            raise

    def release(self):
        if not self._is_owned():
            raise RuntimeError('cannot release un-acquired lock')
        self._depth -= 1
        try:
            if not self._depth:
                handle, self._handle = self._handle, None
                os.close(handle)
        finally:
            self._thread.release()

    def __enter__(self):
        try:
            acquired = self.acquire()
        except LockPathChanged as error:
            raise self._refusal(str(error)) from error
        except (OSError, ValueError) as error:
            raise self._refusal('The workspace write lock could not be opened. Check the '
                                'workspace and its permissions, then try again.') from error
        if not acquired:
            raise self._refusal('Another Studio is changing this workspace. Try again in a moment.')
        return self

    def __exit__(self, *exc):
        self.release()
