"""Blog adapters and the pinned Training Studio non-interactive Git primitives."""

from __future__ import annotations
import os
import json
import re
import shutil
import subprocess
import threading
from pathlib import Path
from contextlib import contextmanager


class WorkspaceError(ValueError):
    """A workspace operation was refused without replacing author work."""


class SyncError(ValueError):
    pass


SKILL_DIR = Path(__file__).resolve().parents[2]
STATE_DIR = '.blog-studio'
INHERITED = ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_OBJECT_DIRECTORY', 'GIT_COMMON_DIR')
COPY_AS_IS = (
    '-c',
    'core.autocrlf=false',
    '-c',
    'core.symlinks=false',
    '-c',
    'core.hooksPath=/dev/null',
)
REMOTE = ('clone', 'fetch', 'push', 'ls-remote')
BATCH_SSH = 'ssh -o BatchMode=yes'
ATTEMPTS = 3
TIMEOUT = 30
ADDRESS_WITH_SECRET = re.compile(r'^https?://[^/]*@|^[a-z][a-z0-9+.-]*://[^/@]*:[^/@]*@', re.I)


def data_root():
    return Path(
        os.environ.get('BLOG_STUDIO_DATA', Path.home() / '.local/share/blog-studio')
    ).expanduser()


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def write_json(path, value):
    import studio

    studio.write_json(Path(path), value)


def now():
    import studio

    return studio.now()


def runtime_version():
    return (SKILL_DIR / 'VERSION').read_text().strip()


def as_tuple(value):
    if not re.fullmatch(r'[0-9]+(?:\.[0-9]+)*', value):
        raise SyncError('Invalid runtime version.')
    return tuple(map(int, value.split('.')))


def slugify(value):
    return re.sub('[^a-z0-9]+', '-', value.lower()).strip('-')[:64] or 'workspace'


_LOCKS = {}
_DEPTH = threading.local()


@contextmanager
def locked(path):
    from hub_store import acquire_lock, release_lock

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    key = str(path.resolve())
    lock = _LOCKS.setdefault(key, threading.RLock())
    if not lock.acquire(timeout=30):
        raise WorkspaceError('Another workspace operation is running. Retry shortly.')
    depths = getattr(_DEPTH, 'values', {})
    _DEPTH.values = depths
    fd = None
    try:
        if not depths.get(key):
            fd = acquire_lock(path)
            if fd is None:
                raise WorkspaceError('Another workspace operation is running. Retry shortly.')
        depths[key] = depths.get(key, 0) + 1
        yield
    finally:
        depths[key] = max(0, depths.get(key, 1) - 1)
        if fd is not None:
            release_lock(fd)
        lock.release()


class Held:
    """A reusable file-lock context for upstream sync's separate read/replay phases."""

    def __init__(self, path):
        self.path = path
        self.local = threading.local()

    def __enter__(self):
        context = locked(self.path)
        result = context.__enter__()
        stack = getattr(self.local, 'stack', [])
        stack.append(context)
        self.local.stack = stack
        return result

    def __exit__(self, *args):
        return self.local.stack.pop().__exit__(*args)


class GitError(WorkspaceError):
    """git failed; the message is the line of its output that says why."""


def subcommand(args: tuple[str, ...]) -> str | None:
    """The git command in a list of arguments, after any `-c name=value` before it."""
    at = 0
    while at < len(args) and args[at] == '-c':
        at += 2
    return args[at] if at < len(args) else None


def run(
    repo: Path, *args: str, input: str | None = None, timeout: float = TIMEOUT
) -> subprocess.CompletedProcess:
    """Run git in `repo` without prompting, and without reaching a repository above it.

    git has no terminal to ask on: it runs in a session of its own, and ssh is told not
    to ask for a passphrase or about a host key, unless the user chose their own ssh
    command. `input` is what git reads, when it reads anything. A command that cannot
    start or does not finish in `timeout` seconds comes back as a failed one, so a slow
    remote is handled like an unreachable one.
    """
    env = {key: value for key, value in os.environ.items() if key not in INHERITED}
    env.update(GIT_TERMINAL_PROMPT='0', GIT_EDITOR='true', GIT_CEILING_DIRECTORIES=str(repo.parent))
    if subcommand(args) in REMOTE and not own_ssh(repo, env):
        env['GIT_SSH_COMMAND'] = BATCH_SSH
    try:
        return subprocess.run(
            ['git', '-c', 'core.hooksPath=/dev/null', '-c', 'protocol.ext.allow=never', *args],
            cwd=repo,
            env=env,
            capture_output=True,
            stdin=subprocess.DEVNULL if input is None else None,
            input=input,
            encoding='utf-8',
            errors='replace',
            timeout=timeout,
            start_new_session=True,
        )
    except subprocess.TimeoutExpired:
        problem = f'git {subcommand(args)} did not finish in {timeout:g} seconds'
    except OSError as failure:
        if shutil.which('git') is None:
            raise WorkspaceError(
                'A hub needs git, which is not installed. Install it and try again.'
            ) from failure
        problem = str(failure)
    return subprocess.CompletedProcess(args, 124, '', f'fatal: {problem}')


def own_ssh(repo: Path, env: dict) -> bool:
    """True when the user chose how git runs ssh, which is then left as they chose."""
    if env.get('GIT_SSH_COMMAND') or env.get('GIT_SSH'):
        return True
    return bool(run(repo, 'config', '--get', 'core.sshCommand').stdout.strip())


def reason(done: subprocess.CompletedProcess) -> str:
    """Why git failed, in its own words and the remote's: one line, with no full stop."""
    lines = [line.strip() for line in done.stderr.splitlines() if line.strip()]
    said = ' '.join(line[8:] for line in lines if line.startswith('remote: '))
    for prefix in ('fatal: ', '! ', 'error: ', ''):
        for line in lines:
            if line.startswith(prefix) and not line.startswith('remote: '):
                return (line[len(prefix) :] + (f': {said}' if said else '')).rstrip('.')
    return said.rstrip('.') or 'git failed'


def git(repo: Path, *args: str) -> str:
    done = run(repo, *args)
    if done.returncode != 0:
        raise GitError(reason(done))
    return done.stdout.strip()


def passes(repo: Path, *args: str) -> bool:
    return run(repo, *args).returncode == 0


def names(output: str) -> list[str]:
    """Paths from git output that was asked for with -z."""
    return [path for path in output.split('\0') if path]


def apart(repo: Path, tracking: str) -> tuple[int, int] | None:
    """Commits only the local copy has and commits only the remote has, as of the last
    fetch. None while the remote has no such branch."""
    done = run(repo, 'rev-list', '--left-right', '--count', f'HEAD...{tracking}')
    return tuple(map(int, done.stdout.split())) if done.returncode == 0 else None


def ahead(repo: Path, tracking: str) -> int:
    """How many local commits the remote did not have when it was last reached."""
    counts = apart(repo, tracking)
    if counts is None:
        done = run(repo, 'rev-list', '--count', 'HEAD')
        return int(done.stdout) if done.returncode == 0 else 0
    return counts[0]


def name_from(url: str) -> str:
    stem = re.split(r'[/:]', url.rstrip('/'))[-1].removesuffix('.git')
    return slugify(stem) if re.search(r'[a-z0-9]', stem.lower()) else 'hub'
