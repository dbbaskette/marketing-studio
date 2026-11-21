"""Traverse approved checkout links and materialize self-contained studio bundles.

Also the one rule every installer shares for its `versions` folder: one version stays,
and everything written down names it through the `current` link beside that folder. And
which commit of `main` each installed version came from, so that a studio can say whether
`main` has moved on since (`source_commit`, `remember_commit`, `installed_commit`).
"""
import os
from pathlib import Path
import re
import shutil
import subprocess

COMMIT = re.compile(r'[0-9a-f]{40}')


def shared_link(path):
    """Only the suite's named code and UI links are allowed in source packages."""
    path = Path(path)
    if not path.is_symlink():
        return False
    target = path.resolve()
    for parent in path.parents:
        if not (parent / 'core/studio_core/__init__.py').is_file():
            continue
        if path.name == 'companions.json' and path.parent.name == 'installer' and target == parent / 'pins/companions.json':
            return True
        if path.name in ('index.html', 'app.js', 'home.css', 'qr.js') and path.parent == parent / 'marketing_studio/web' and target == parent / 'core/studio_core/setup_web' / path.name:
            return True
        if path.name == 'studio_core' and target == parent / 'core/studio_core':
            return True
        if path.name in ('style.css', 'markdown.js', 'drafting.js', 'research.js', 'activity.js') and target == parent / 'ui-kit' / path.name:
            return True
    return False


def files(root):
    """Walk links only when their targets are the suite's shared source directories."""
    root = Path(root)
    result = []
    for directory, dirs, names in os.walk(root, followlinks=True):
        dirs[:] = sorted(name for name in dirs if name not in ('__pycache__', '.git'))
        for name in dirs + names:
            path = Path(directory) / name
            if path.is_symlink() and not shared_link(path):
                raise ValueError('Package files and folders must be regular, not links.')
        result.extend(Path(directory) / name for name in sorted(names))
    return sorted(result)


GONE = ('The earlier version is no longer on this computer: an update keeps only the newest. '
        'Install the version you want from its repository instead. Nothing was changed.')


def prune(versions, keep, in_use=None):
    """Remove every direct child of an installer's own `versions` folder except `keep`.

    Called only after an install has fully succeeded, so no saved work, launcher or caller
    can stay on an older copy. A link is unlinked and never followed, and a real folder is
    removed without following the links inside it. Nothing is removed when `versions` is
    itself a link, or does not hold `keep`. An entry that cannot be removed is reported and
    never raised: {'removed': [path], 'retained': [{'path', 'reason'}]}. `in_use` names
    children that something still runs from, each with the reason to report: they stay.
    """
    versions = Path(versions)
    removed, retained = [], []
    in_use = in_use or {}
    try:
        if versions.is_symlink():
            raise OSError('The versions folder is a link, so older versions were left in place.')
        names = sorted(os.listdir(versions))
        if keep not in names:
            raise OSError('The installed version is not in this folder, so nothing was removed.')
    except FileNotFoundError:
        return {'removed': removed, 'retained': retained}
    except OSError as failure:
        return {'removed': removed,
                'retained': [{'path': str(versions), 'reason': failure.strerror or str(failure)}]}
    for name in names:
        if name == keep:
            continue
        path = versions / name
        if name in in_use:
            retained.append({'path': str(path), 'reason': in_use[name]})
            continue
        try:
            if path.is_symlink() or not path.is_dir():
                path.unlink()
            else:
                shutil.rmtree(path)
            removed.append(str(path))
        except OSError as failure:
            retained.append({'path': str(path), 'reason': failure.strerror or str(failure)})
    return {'removed': removed, 'retained': retained}


def version_target(link, text):
    """The version folder a link with this text names, or None when it names anything else:
    `current` itself points into `versions`, and every other link points at `current`."""
    target = Path(os.path.normpath(Path(link).parent / text))
    return target if target.parent.name == 'versions' else None


def stable_address(path, saved=False):
    """The same place said through its installer's `current` link, when `path` is inside
    the version folder that link names. A later update replaces that folder, and the
    address through `current` goes on working.

    `saved` is for a path written down earlier, by this or an older version: one inside any
    `versions/<id>` folder is said through `current` while that link is there, whichever
    version it names now, since an update keeps only the newest and that folder may be
    gone."""
    path = Path(path)
    parts = path.parts
    for index in range(len(parts) - 1):
        if parts[index] != 'versions' or index + 1 >= len(parts):
            continue
        current = Path(*parts[:index]) / 'current'
        folder = Path(*parts[:index + 2])
        try:
            if current.is_symlink() and (saved or current.resolve() == folder.resolve()):
                return current.joinpath(*parts[index + 2:])
        except OSError:
            pass
    return path


def stable_place(place):
    """Where an installed companion is, said so that it outlives an update: through its
    `current` link when it lives in a version folder, whatever link led to it; otherwise
    the place as it was named, unresolved."""
    place = Path(place).absolute()
    try:
        resolved = place.resolve()
    except (OSError, RuntimeError):
        return place
    stable = stable_address(resolved)
    return stable if stable != resolved else place


def source_commit(folder):
    """The commit a Git checkout holding `folder` is at, or None when it is not in one or
    git cannot say. git is asked apart from the person's own setup, and only `rev-parse`
    runs: no hook, no filter, nothing fetched."""
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT='0')
    try:
        done = subprocess.run(['git', '-C', str(folder), '-c', f'core.hooksPath={os.devnull}',
                               '-c', 'core.fsmonitor=false', 'rev-parse', '--verify', '--quiet',
                               'HEAD^{commit}'], env=env, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    commit = done.stdout.strip()
    return commit if done.returncode == 0 and COMMIT.fullmatch(commit) else None


def remember_commit(state, key, commit):
    """Keep, in an installer's record, which commit the version `key` was installed from.
    Only versions in its history are kept. Without a commit, one kept for the same `key`
    stays: the same key is the same files."""
    history = set(state.get('history') or ()) | {key}
    kept = state.get('commits') if isinstance(state.get('commits'), dict) else {}
    commits = {name: value for name, value in kept.items()
               if name in history and isinstance(value, str) and COMMIT.fullmatch(value)}
    if isinstance(commit, str) and COMMIT.fullmatch(commit):
        commits[key] = commit
    state['commits'] = commits
    return state


def installed_commit(state, key):
    """The commit the installed version `key` came from, as `remember_commit` kept it, or
    None when it is not known: installed from a download, or by an older installer."""
    kept = (state or {}).get('commits') if isinstance((state or {}).get('commits'), dict) \
        else {}
    commit = kept.get(key)
    return commit if isinstance(commit, str) and COMMIT.fullmatch(commit) else None
