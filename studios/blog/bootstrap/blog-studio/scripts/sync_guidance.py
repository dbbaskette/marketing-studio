#!/usr/bin/env python3
"""Quietly cache trusted guidance and pin an immutable task snapshot."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import uuid

VERSION = '1.11.0'
TRUSTED_SOURCE = 'https://github.com/dbbaskette/blog-studio.git'
BRANCH = 'main'
CONTENT_ROOT = 'skills/blog-studio'
GUIDANCE_METADATA = ('sources.lock.json', 'blogforge.lock.json')
MAX_FILE = 1024 * 1024
MAX_TOTAL = 8 * 1024 * 1024
MAX_FILES = 500


class SyncError(Exception):
    pass


def write_json(path, value):
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temp.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def git(repository, *args):
    environment = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    environment['GIT_TERMINAL_PROMPT'] = '0'
    try:
        result = subprocess.run(['git', '--git-dir=' + str(repository), '-c',
            'core.hooksPath=' + os.devnull, *args], capture_output=True,
            timeout=45, env=environment)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SyncError('Git is unavailable or the repository check timed out.') from exc
    if result.returncode:
        raise SyncError('Repository access failed. Check your network and GitHub repository access.')
    return result.stdout


@contextmanager
def lock(cache):
    path = cache / '.sync.lock'
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise SyncError('Another guidance update is running. Retry after it finishes.') from exc
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(str(os.getpid()))
        yield
    finally:
        path.unlink(missing_ok=True)


def cache_root(workspace):
    workspace = Path(workspace).expanduser().resolve()
    installed = Path(__file__).resolve().parents[1]
    if workspace == installed or workspace.is_relative_to(installed):
        raise SyncError('Choose an author workspace outside the installed skill.')
    cache = workspace / 'task-context'
    if cache.is_symlink():
        raise SyncError('Task context must not be a symlink.')
    return cache


def read_blob(repository, commit, path):
    listing = git(repository, 'ls-tree', commit, '--', path).decode('utf-8').strip()
    if not listing:
        raise SyncError('Required guidance is missing from the approved revision.')
    metadata, name = listing.split('\t', 1)
    fields = metadata.split()
    if fields[:2] != ['100644', 'blob'] or name != path:
        raise SyncError('Guidance must be a regular non-executable file.')
    if int(git(repository, 'cat-file', '-s', fields[2])) > MAX_FILE:
        raise SyncError('A guidance file exceeds the size limit.')
    data = git(repository, 'cat-file', 'blob', fields[2])
    try:
        data.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise SyncError('Guidance must be UTF-8 text.') from exc
    return data


def compatible(manifest):
    try:
        if not isinstance(manifest, dict):
            raise TypeError()
        needed = tuple(int(n) for n in manifest['minimum_runtime'].split('.'))
    except (KeyError, ValueError, AttributeError, TypeError) as exc:
        raise SyncError('The guidance compatibility manifest is invalid.') from exc
    if (not isinstance(manifest, dict) or any(n < 0 for n in needed) or manifest.get('schema') != 1 or len(needed) != 3 or
            needed > tuple(int(n) for n in VERSION.split('.'))):
        raise SyncError('This guidance needs a newer local Blog Studio runtime. Run the installer update.')
    if manifest.get('content_root') != CONTENT_ROOT or manifest.get('entry') != CONTENT_ROOT + '/SKILL.md':
        raise SyncError('The approved guidance layout is unsupported.')


def result_for(snapshot, pin, fresh):
    root = snapshot / CONTENT_ROOT
    return {'fresh': fresh, 'revision': pin['revision'], 'task': pin['task'],
            'guidance': str(root / 'SKILL.md'),
            'runtime': str(Path(__file__).resolve().parent)}


def start(workspace, source=TRUSTED_SOURCE, revision=None):
    # source injection is a library-only seam for disposable test repositories.
    cache = cache_root(workspace)
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    if (cache / 'repository.git').is_symlink() or (cache / 'tasks').is_symlink():
        raise SyncError('Cache locations must not be symlinks.')
    with lock(cache):
        repository = cache / 'repository.git'
        if not repository.exists():
            git(repository, 'init', '--bare', '--initial-branch=main')
        if revision is not None:
            if not re.fullmatch(r'[0-9a-f]{40,64}', revision):
                raise SyncError('Choose a valid saved guidance revision.')
            shallow = git(repository, 'rev-parse', '--is-shallow-repository').decode().strip() == 'true'
            git(repository, 'fetch', '--quiet', '--no-tags', *(['--unshallow'] if shallow else []), source, 'refs/heads/' + BRANCH)
        else:
            git(repository, 'fetch', '--quiet', '--no-tags', '--depth=1', source, 'refs/heads/' + BRANCH)
        commit = git(repository, 'rev-parse', '--verify', 'FETCH_HEAD^{commit}').decode().strip()
        if revision is not None:
            try:git(repository, 'merge-base', '--is-ancestor', revision, commit)
            except SyncError as exc:raise SyncError('The saved guidance revision is not in approved main history.') from exc
            commit = revision
        if not re.fullmatch(r'[0-9a-f]{40,64}', commit):
            raise SyncError('The repository returned an invalid revision.')
        try:
            manifest = json.loads(read_blob(repository, commit, 'guidance/manifest.json'))
        except ValueError as exc:
            raise SyncError('The guidance compatibility manifest is invalid.') from exc
        compatible(manifest)
        task = uuid.uuid4().hex
        tasks = cache / 'tasks'
        tasks.mkdir(exist_ok=True, mode=0o700)
        staging = tasks / ('.' + task)
        final = tasks / task
        staging.mkdir(mode=0o700)
        try:
            entries = git(repository, 'ls-tree', '-r', '-z', commit, '--', CONTENT_ROOT).split(b'\0')
            selected = []
            for entry in entries:
                if not entry:
                    continue
                metadata, raw_name = entry.split(b'\t', 1)
                name = raw_name.decode('utf-8')
                relative = PurePosixPath(name)
                if relative.is_absolute() or '..' in relative.parts or '\\' in name:
                    raise SyncError('A guidance path is invalid.')
                suffix = str(relative.relative_to(CONTENT_ROOT))
                if suffix == 'SKILL.md' or suffix in GUIDANCE_METADATA or suffix.startswith('references/'):
                    if metadata.split()[:2] != [b'100644', b'blob']:
                        raise SyncError('Guidance contains a symlink or executable file.')
                    selected.append(name)
            if not selected or len(selected) > MAX_FILES:
                raise SyncError('The guidance inventory is empty or exceeds the file limit.')
            files = {}
            total = 0
            for name in selected:
                data = read_blob(repository, commit, name)
                total += len(data)
                if total > MAX_TOTAL:
                    raise SyncError('The guidance snapshot exceeds the size limit.')
                target = staging / name
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                target.write_bytes(data)
                target.chmod(0o400)
                files[name] = hashlib.sha256(data).hexdigest()
            if manifest['entry'] not in files:
                raise SyncError('The guidance entry point is missing.')
            pin = {'task': task, 'revision': commit, 'source': source, 'runtime_version': VERSION,
                   'created_at': datetime.now(timezone.utc).isoformat(), 'files': files}
            write_json(staging / 'pin.json', pin)
            (staging / 'pin.json').chmod(0o400)
            os.replace(staging, final)
            return result_for(final, pin, True)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise


def resume(workspace, task, cached=False):
    if not re.fullmatch(r'[0-9a-f]{32}', task):
        raise SyncError('Choose a valid saved task ID.')
    cache = cache_root(workspace)
    snapshot = cache / 'tasks' / task
    if snapshot.is_symlink() or (cache / 'tasks').is_symlink():
        raise SyncError('Saved task locations must not be symlinks.')
    try:
        if (snapshot / 'pin.json').is_symlink():
            raise SyncError('The saved task pin must not be a symlink.')
        pin = json.loads((snapshot / 'pin.json').read_text())
        if pin['task'] != task or not re.fullmatch(r'[0-9a-f]{40,64}', pin['revision']):
            raise SyncError('The saved task pin is invalid.')
        for name, digest in pin['files'].items():
            path = snapshot / name
            if (name != CONTENT_ROOT + '/SKILL.md' and name not in {CONTENT_ROOT + '/' + n for n in GUIDANCE_METADATA}
                    and not name.startswith(CONTENT_ROOT + '/references/')):
                raise SyncError('The saved guidance layout is invalid.')
            if any(parent.is_symlink() for parent in path.parents if parent.is_relative_to(snapshot)):
                raise SyncError('Saved guidance folders must not be symlinks.')
            if not path.resolve().is_relative_to(snapshot.resolve()) or path.is_symlink():
                raise SyncError('The saved guidance path is invalid.')
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise SyncError('Saved guidance changed. Reopen an intact snapshot or start a new task.')
        if CONTENT_ROOT + '/SKILL.md' not in pin['files']:
            raise SyncError('The saved guidance entry is missing.')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SyncError('The saved task could not be reopened.') from exc
    result = result_for(snapshot, pin, False if cached else 'pinned')
    return result


def recent_tasks(workspace):
    tasks = cache_root(workspace) / 'tasks'
    results = []
    if tasks.is_dir() and not tasks.is_symlink():
        for path in sorted(tasks.iterdir(), key=lambda p: p.name):
            if re.fullmatch(r'[0-9a-f]{32}', path.name) and not path.is_symlink():
                try:
                    pin = json.loads((path / 'pin.json').read_text())
                    results.append({'task': path.name, 'revision': pin['revision'], 'created_at': pin['created_at']})
                except (OSError, ValueError, KeyError):
                    continue
    return sorted(results, key=lambda p: p['created_at'], reverse=True)[:3]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('start', 'pin', 'resume', 'cached'))
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--task')
    parser.add_argument('--revision')
    args = parser.parse_args()
    try:
        if args.action in ('start', 'pin'):
            if args.action == 'pin' and not args.revision:
                raise SyncError('A saved guidance revision is required.')
            if args.action == 'start' and args.revision:
                raise SyncError('Use pin to reopen a saved revision.')
            if args.task:
                raise SyncError('A new task creates its own pin. Use resume for an existing task.')
            result = start(args.workspace, revision=args.revision) if args.action == 'pin' else start(args.workspace)
        else:
            if not args.task:
                raise SyncError('A saved task ID is required.')
            result = resume(args.workspace, args.task, cached=args.action == 'cached')
        print(json.dumps(result))
        return 0
    except (SyncError, OSError) as exc:
        message = str(exc) if isinstance(exc, SyncError) else 'Local storage is unavailable. Check paths and permissions.'
        error = {'fresh': False, 'error': message}
        if args.action in ('start', 'pin'):
            try:
                error['cached_tasks'] = recent_tasks(args.workspace)
            except (OSError, SyncError):
                error['cached_tasks'] = []
        print(json.dumps(error))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
