"""Local-only foundation: explicit setup, protected drafts, immutable revisions.

No provider, update, fetch, push, or workspace relocation happens here. Team
connection and complete native installation remain their own later issues.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import subprocess
import tempfile
import threading

from studio_core import studios_config, workspace_setup

from .contracts import (MAX_ASSET_BYTES, MAX_RECORD_BYTES, PRODUCT, Invalid,
                        advance, canonical, new_project, renamed, renaming)
from .validation import identifier, image_size, relative_path, require, sha, validate_project

NOFOLLOW = getattr(os, 'O_NOFOLLOW', 0)
DIRECTORY = getattr(os, 'O_DIRECTORY', 0)


def data_root() -> Path:
    return Path(os.environ.get('INFOGRAPHIC_STUDIO_DATA') or
                Path.home() / '.local/share/infographic-studio').expanduser()


def _directory(path: Path):
    if path.is_symlink():
        raise Invalid('Infographic Studio folders cannot be links.')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.is_dir():
        raise Invalid('Infographic Studio needs a directory.')


def _atomic(path: Path, data: bytes, *, mode=0o600):
    _directory(path.parent)
    if path.is_symlink() or path.exists() and not path.is_file():
        raise Invalid('A link or directory blocks this save.')
    pending = path.with_name('.' + path.name + '-' + secrets.token_hex(8))
    try:
        descriptor = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL | NOFOLLOW, mode)
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(pending, path)
    finally:
        pending.unlink(missing_ok=True)


def _read(root: Path, relative: str, limit: int) -> bytes:
    """Open every owned path component without following a link."""
    if not relative_path(relative):
        raise Invalid('Use a safe workspace-relative file name.')
    directory = None
    try:
        directory = os.open(root, os.O_RDONLY | DIRECTORY | NOFOLLOW)
        parts = relative.split('/')
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | DIRECTORY | NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NONBLOCK | NOFOLLOW, dir_fd=directory)
        with os.fdopen(descriptor, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
                raise Invalid('The requested file is not a regular file within its size limit.')
            result = stream.read(limit + 1)
        if len(result) > limit:
            raise Invalid('The requested file exceeds its size limit.')
        return result
    except OSError as failure:
        raise Invalid('The requested Infographic Studio file is missing or unsafe.') from failure
    finally:
        if directory is not None:
            os.close(directory)


def _json(root: Path, relative: str, limit=MAX_RECORD_BYTES):
    try:
        return json.loads(_read(root, relative, limit))
    except (ValueError, UnicodeError, RecursionError) as failure:
        raise Invalid('The saved Infographic Studio record cannot be read safely.') from failure


def _valid_marker(value) -> bool:
    return (isinstance(value, dict) and set(value) == {'schema', 'product', 'owner'}
            and type(value['schema']) is int and value['schema'] == 1
            and value['product'] == PRODUCT and identifier(value['owner']))


@contextmanager
def file_lock(path: Path):
    _directory(path.parent)
    try:
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT | NOFOLLOW, 0o600)
    except OSError as failure:
        raise Invalid('The Infographic Studio lock is unsafe.') from failure
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise Invalid('The Infographic Studio lock must be a regular file.')
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as failure:
            raise Invalid('Another Infographic Studio operation is using this workspace.') from failure
        yield
    finally:
        os.close(descriptor)


class Store:
    def __init__(self, root: Path, owner: str):
        if Path(root).is_symlink() or not identifier(owner):
            raise Invalid('The workspace root or owner is invalid.')
        self.root = Path(root).resolve(strict=True)
        self.owner = owner
        self._thread_lock = threading.RLock()
        self._held = threading.local()

    @classmethod
    def current(cls, data: Path | None = None):
        data = Path(data) if data is not None else data_root()
        if not data.exists():
            return None
        if data.is_symlink():
            raise Invalid('The Infographic Studio data folder cannot be a link.')
        if not (data / 'workspace.json').exists() and not (data / 'workspace.json').is_symlink():
            return None
        saved = _json(data, 'workspace.json', 10_000)
        if not isinstance(saved, dict) or type(saved.get('schema')) is not int \
                or saved['schema'] != 1 or not isinstance(saved.get('root'), str):
            raise Invalid('Restore a valid Infographic Studio workspace record.')
        root, owner = Path(saved['root']), saved.get('owner')
        if not root.is_absolute() or root.is_symlink() or not root.is_dir():
            raise Invalid('The configured Infographic Studio workspace is missing or unsafe.')
        marker = _json(root, '.infographic-studio/workspace.json', 10_000)
        if not _valid_marker(marker) or marker['owner'] != owner:
            raise Invalid('The configured workspace owner or marker does not match.')
        return cls(root, owner)

    @classmethod
    def setup(cls, root: Path | None = None, *, data: Path | None = None):
        """Called only by an explicit native setup or launch action."""
        data = Path(data) if data is not None else data_root()
        _directory(data)
        with file_lock(data / 'setup.lock'):
            existing = cls.current(data)
            if existing:
                if root is not None and Path(root).expanduser().resolve() != existing.root:
                    raise Invalid('Keep the configured workspace. Moving it requires an explicit future Connect action.')
                return existing
            if root is None:
                shared, problem = studios_config.read()
                if problem:
                    raise Invalid('Correct the shared settings before adopting a workspace.')
                target = workspace_setup.target(shared, 'infographic')
                if 'repository' in target:
                    raise Invalid('Team connection is not implemented yet. Choose an explicit local workspace for this foundation.')
                root = Path(target['root'])
            root = Path(root).expanduser()
            if root.is_symlink():
                raise Invalid('The workspace root cannot be a link.')
            root = root.absolute()
            native = Path(__file__).resolve().parents[1]
            application = next((p for p in native.parents if (p / 'core/studio_core').is_dir()), native)
            if root.resolve().is_relative_to(application):
                raise Invalid('Keep infographic content outside the application repository.')
            if root.exists() and not root.is_dir():
                raise Invalid('Choose a directory for the local workspace.')
            if root.resolve().is_relative_to(data.resolve()) or data.resolve().is_relative_to(root.resolve()):
                raise Invalid('Use separate workspace and application-data folders.')
            if root.exists() and any(root.iterdir()):
                # Recover/adopt only an explicitly named native workspace with its
                # own valid marker. Never repurpose unrelated existing content.
                if not (root / '.infographic-studio/workspace.json').exists():
                    raise Invalid('Keep existing files. Choose an empty, unconfigured local workspace.')
                marker = _json(root, '.infographic-studio/workspace.json', 10_000)
                if not _valid_marker(marker) or not (root / 'projects').is_dir() \
                        or (root / 'projects').is_symlink():
                    raise Invalid('The existing directory is not a valid Infographic Studio workspace.')
                _atomic(data / 'workspace.json', canonical({'schema': 1, 'root': str(root.resolve()),
                                                           'owner': marker['owner']}))
                return cls(root, marker['owner'])
            _directory(root)
            # No identity, hooks, template, account, fetch, push or commit is needed.
            with tempfile.TemporaryDirectory(prefix='infographic-git-', dir=data) as temp:
                env = {'PATH': os.environ.get('PATH', ''), 'HOME': temp,
                       'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull,
                       'GIT_TEMPLATE_DIR': temp}
                try:
                    result = subprocess.run(['git', 'init', '--quiet', '--initial-branch=main', str(root)],
                                            env=env, capture_output=True, timeout=15)
                except (OSError, subprocess.TimeoutExpired) as failure:
                    raise Invalid('Git could not initialize this local workspace.') from failure
                if result.returncode:
                    raise Invalid('Git could not initialize this local workspace.')
            owner = secrets.token_hex(16)
            marker = {'schema': 1, 'product': PRODUCT, 'owner': owner}
            _atomic(root / '.infographic-studio/workspace.json', canonical(marker))
            _directory(root / 'projects')
            _atomic(data / 'workspace.json', canonical({'schema': 1, 'root': str(root.resolve()), 'owner': owner}))
            return cls(root, owner)

    @contextmanager
    def locked(self):
        with self._thread_lock, file_lock(self.root / '.infographic-studio/workspace.lock'):
            self._verify_owner()
            self._held.active = True
            try:
                yield
            finally:
                self._held.active = False

    def _verify_owner(self):
        marker = _json(self.root, '.infographic-studio/workspace.json', 10_000)
        if not _valid_marker(marker) or marker['owner'] != self.owner:
            raise Invalid('The workspace owner changed. Reload Infographic Studio.')

    def _project(self, ident: str) -> Path:
        if not identifier(ident):
            raise Invalid('Give a valid infographic ID.')
        path = self.root / 'projects' / ident
        for part in (self.root / 'projects', path, path / 'versions'):
            if part.is_symlink():
                raise Invalid('Infographic Studio project folders cannot be links.')
        return path

    def read(self, ident: str) -> dict:
        self._verify_owner()
        self._project(ident)
        pointer = _json(self.root, f'projects/{ident}/current.json', 10_000)
        if not isinstance(pointer, dict) or type(pointer.get('schema')) is not int \
                or pointer['schema'] != 1 or pointer.get('id') != ident \
                or type(pointer.get('revision')) is not int or pointer['revision'] < 0 or not sha(pointer.get('sha256')):
            raise Invalid('The infographic revision pointer is invalid.')
        name = f"projects/{ident}/versions/{pointer['revision']}-{pointer['sha256']}.json"
        raw = _read(self.root, name, MAX_RECORD_BYTES)
        if hashlib.sha256(raw).hexdigest() != pointer['sha256']:
            raise Invalid('The saved infographic revision has changed unexpectedly.')
        try:
            project = json.loads(raw)
        except (ValueError, UnicodeError, RecursionError) as failure:
            raise Invalid('The saved infographic revision cannot be read.') from failure
        validate_project(project)
        if project['id'] != ident or project['owner'] != self.owner or project['revision'] != pointer['revision']:
            raise Invalid('The infographic identity or workspace owner does not match.')
        return project

    def _publish(self, project: dict):
        if not getattr(self._held, 'active', False):
            raise Invalid('Infographic Studio saves must hold the workspace lock.')
        validate_project(project)
        if project['owner'] != self.owner:
            raise Invalid('This infographic belongs to another workspace owner.')
        folder = self._project(project['id'])
        _directory(folder / 'versions')
        raw = canonical(project)
        value = hashlib.sha256(raw).hexdigest()
        version = folder / 'versions' / f"{project['revision']}-{value}.json"
        if not version.exists():
            _atomic(version, raw)
        elif _read(self.root, version.relative_to(self.root).as_posix(), MAX_RECORD_BYTES) != raw:
            raise Invalid('An existing immutable revision is damaged.')
        _atomic(folder / 'current.json', canonical({'schema': 1, 'id': project['id'],
                                                  'revision': project['revision'], 'sha256': value}))

    def create(self, title: str, *, preset='a4', direction='suggest', request_id=None) -> dict:
        with self.locked():
            require(request_id is None or identifier(request_id), 'Choose an owned creation request identity.')
            project = new_project(self.owner, title, preset=preset, direction=direction, ident=request_id)
            if self._project(project['id']).exists():
                if request_id is None:
                    raise Invalid('An infographic with that ID already exists.')
                folder = self._project(project['id'])
                if not (folder / 'current.json').exists():
                    expected = '0-' + hashlib.sha256(canonical(project)).hexdigest() + '.json'
                    require({p.name for p in folder.iterdir()} <= {'versions'}
                            and {p.name for p in (folder / 'versions').iterdir()} <= {expected},
                            'The interrupted creation contains other work. Restore its pointer explicitly; nothing was replaced.')
                    self._publish(project)
                    return project
                original = self.history(project['id'], revision=0)
                require(len(original) == 1 and original[0] == project,
                        'This creation request was used for another brief. Open the saved draft rather than replacing it.')
                return original[0]
            self._publish(project)
            return project

    def edit_brief(self, ident: str, brief: dict, *, expected_revision: int) -> dict:
        """Save the brief. A change to the working title alone is a rename that clears
        nothing (`contracts.renamed`); any other change clears the story, page and approval
        built from the earlier brief, under the input rules. Captured facts stay either way."""
        with self.locked():
            current = self.read(ident)
            if renaming(current, brief):
                return self._rename_locked(current, brief['title'], expected_revision)
            project = advance(current, {'brief': brief},
                              expected_revision=expected_revision, owner=self.owner)
            self._publish(project)
            return project

    def _rename_locked(self, current: dict, title, expected_revision) -> dict:
        self.expect(current, expected_revision)
        require(not any(a['state'] in ('queued', 'running', 'unknown') for a in current['attempts']),
                'An image request is still pending or uncertain. Rename this infographic once '
                'Image work needs attention is resolved.')
        from .visual_review import latest     # imported here: visual_review reads this module
        review = latest(self, current)
        candidate = deepcopy(current)
        candidate['brief']['title'] = title
        already = latest(self, candidate)     # a review kept from when it last had this title
        result, carried = renamed(current, title, review,
                                  sequence=(already or {}).get('sequence', 0))
        if carried is not None:
            self.write_blob(current['id'], 'jobs/visual_' + secrets.token_hex(12) + '/review.json',
                            canonical(carried))
        self._publish(result)
        return result

    def expect(self, project: dict, revision: int):
        require(type(revision) is int and revision == project['revision'],
                'This infographic changed. Reload it before saving.')
        require(project['owner'] == self.owner, 'This infographic belongs to another workspace owner.')

    def change_locked(self, project: dict, changes: dict) -> dict:
        """Only native validated content mutations call this under the workspace lock."""
        require(getattr(self._held, 'active', False), 'Hold the workspace lock before saving.')
        current = self.read(project['id'])
        self.expect(current, project['revision'])
        result = advance(current, changes, expected_revision=current['revision'], owner=self.owner)
        self._publish(result)
        return result

    def update(self, ident: str, changes: dict, *, expected_revision: int) -> dict:
        with self.locked():
            current = self.read(ident)
            self.expect(current, expected_revision)
            return self.change_locked(current, changes)

    def commit_locked(self, previous: dict, result: dict) -> dict:
        """Internal state transition, never a public arbitrary-record write endpoint."""
        require(getattr(self._held, 'active', False), 'Hold the workspace lock before saving.')
        self.expect(self.read(previous['id']), previous['revision'])
        require(result['id'] == previous['id'] and result['owner'] == self.owner
                and result['revision'] == previous['revision'] + 1,
                'Internal state transitions need the exact next revision and owner.')
        self._publish(result)
        return result

    def write_blob(self, ident: str, relative: str, data: bytes):
        """Private immutable bytes. Callers choose generated names, never assistant paths."""
        require(getattr(self._held, 'active', False), 'Hold the workspace lock before writing bytes.')
        limit = 64_000_000 if isinstance(relative, str) and relative.startswith('exports/') else MAX_ASSET_BYTES
        require(relative_path(relative) and relative.split('/')[0] in ('sources', 'assets', 'exports', 'jobs')
                and type(data) is bytes and len(data) <= limit,
                'Store bounded bytes only in an owned content folder.')
        base = self._project(ident)
        path = base / relative
        for folder in reversed(path.parent.relative_to(base).parents):
            _directory(base / folder)
        _directory(path.parent)
        if path.exists() or path.is_symlink():
            require(_read(self.root, path.relative_to(self.root).as_posix(), limit) == data,
                    'An immutable file already exists with different bytes.')
        else:
            _atomic(path, data)

    def history(self, ident: str, *, revision=None, before=None, limit=100) -> list[dict]:
        self.read(ident)
        require(type(limit) is int and 1 <= limit <= 1000
                and (revision is None or type(revision) is int and revision >= 0)
                and (before is None or type(before) is int and before >= 0), 'Choose a bounded history page or exact revision.')
        result = []
        paths = self._project(ident).joinpath('versions').glob(str(revision) + '-*.json') if revision is not None else self._project(ident).joinpath('versions').iterdir()
        candidates = []
        for path in paths:
            if path.suffix != '.json' or '-' not in path.stem:
                continue
            number, fingerprint = path.stem.split('-', 1)
            if number.isdecimal() and sha(fingerprint) and (before is None or int(number) < before):
                candidates.append((int(number), fingerprint, path))
        for number, fingerprint, path in sorted(candidates, reverse=True)[:limit]:
            raw = _read(self.root, path.relative_to(self.root).as_posix(), MAX_RECORD_BYTES)
            require(hashlib.sha256(raw).hexdigest() == fingerprint, 'An immutable history entry is damaged.')
            saved = json.loads(raw)
            validate_project(saved)
            require(saved['id'] == ident and saved['owner'] == self.owner
                    and saved['revision'] == number, 'History identity does not match.')
            result.append(saved)
        return sorted(result, key=lambda item: item['revision'])

    def saved_at(self, ident: str, revision: int, fingerprint: str):
        """When an immutable revision was written, from its own file; None if unknown."""
        from datetime import datetime, timezone
        require(type(revision) is int and revision >= 0 and sha(fingerprint), 'Name one exact saved revision.')
        path = self._project(ident) / 'versions' / f'{revision}-{fingerprint}.json'
        if path.is_symlink() or not path.is_file():
            return None
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec='seconds')

    def listing(self) -> list[dict]:
        projects = self.root / 'projects'
        if projects.is_symlink():
            raise Invalid('The project directory cannot be a link.')
        result = []
        for folder in sorted(projects.iterdir()):
            if not identifier(folder.name):
                continue
            try:
                project = self.read(folder.name)
                from .progress import readiness
                from .history import Pages
                result.append({'id': project['id'], 'title': project['brief']['title'],
                               'revision': project['revision'], 'readiness': readiness(project),
                               'page_revision': Pages(self, project['id'], (project,)).of(project['revision'])})
            except Invalid:
                result.append({'id': folder.name, 'problem': 'This infographic cannot be read safely.'})
        return result

    def read_asset(self, ident: str, asset_id: str) -> tuple[str, bytes]:
        project = self.read(ident)
        asset = next((a for a in project['assets'] if a['id'] == asset_id), None)
        if asset is None or not asset['file'].startswith('assets/'):
            raise Invalid('That image is not an asset of this infographic.')
        raw = _read(self.root, f"projects/{ident}/{asset['file']}", MAX_ASSET_BYTES)
        if len(raw) != asset['bytes'] or hashlib.sha256(raw).hexdigest() != asset['sha256']:
            raise Invalid('The saved infographic asset does not match its captured revision.')
        if image_size(raw, asset['mime']) != (asset['width'], asset['height']):
            raise Invalid('The asset dimensions do not match their captured revision.')
        return asset['mime'], raw
