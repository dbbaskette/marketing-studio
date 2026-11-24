"""Brand files, read and written safely: a walk that never follows a link, whole-file
writes, fingerprints, and what Harness Brand says of a folder.
marketing_studio.brand_store re-exports every name here."""
from __future__ import annotations

import base64
import errno
import hashlib
import json
import os
import tempfile
import stat
import zipfile
from pathlib import Path

from . import brand_skill
from .errors import WorkspaceError

from .brand_terms import SOURCE_LIMIT


def _store():
    """marketing_studio.brand_store, read when called. Callers and tests replace names on it
    (LOCK, git, walk, write_json and others), and a call made here reaches what they put there."""
    from . import brand_store
    return brand_store


TREE_LIMIT = 250_000_000
FILE_LIMIT = 10_000


def no_links(path: Path) -> Path:
    path = Path(path).absolute()
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise WorkspaceError('Brand files cannot use symbolic links. Copy the actual file into the brands folder.')
    return path


LINKED = 'Brand files cannot use symbolic links. Copy the actual file into the brands folder.'
FOLDER = os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0)
NOFOLLOW = getattr(os, 'O_NOFOLLOW', 0)


def open_folder(name, dir_fd=None, expected=None) -> int | None:
    """A descriptor of the folder `name` (inside `dir_fd` when given), opened without
    following a link; None when it is gone or cannot be listed, as os.walk passed such a
    folder over. `expected` is (st_dev, st_ino) of the entry as it was listed: a folder
    that is not that one any more (swapped for a link, or for another folder) is refused,
    which also holds where the platform has no O_NOFOLLOW."""
    try:
        handle = os.open(name, FOLDER | _store().NOFOLLOW, dir_fd=dir_fd)
    except OSError as failure:
        if failure.errno == errno.ELOOP:
            raise WorkspaceError(LINKED) from None
        if failure.errno == errno.ENOTDIR:
            # macOS says ENOTDIR, not ELOOP, for a link opened as a folder without following.
            try:
                if stat.S_ISLNK(os.lstat(name, dir_fd=dir_fd).st_mode):
                    raise WorkspaceError(LINKED) from None
            except FileNotFoundError:
                pass
            return None
        if failure.errno in (errno.ENOENT, errno.EACCES):
            return None
        raise
    seen = os.fstat(handle)
    if not stat.S_ISDIR(seen.st_mode) or (expected is not None
                                         and (seen.st_dev, seen.st_ino) != expected):
        os.close(handle)
        raise WorkspaceError(LINKED)
    return handle


def walk(folder: Path) -> list[tuple[Path, int]]:
    """Every file in `folder` with its size, sorted, each path validated before it is
    followed or written. The folder and its ancestors are checked for links once. Inside
    it, each folder is opened from its parent's descriptor without following a link and
    checked to be the very folder that was listed, so a folder swapped for a link while
    the walk runs is refused and nothing outside the brand folder is ever listed. A file
    that is gone by the time it is looked at (one a running command just renamed) is
    passed over."""
    folder = no_links(folder)
    if not folder.exists():
        return []
    if not folder.is_dir():
        raise WorkspaceError('A brand or library must be a folder.')
    files: list[tuple[Path, int]] = []
    total = 0

    def scan(handle: int, base: Path) -> None:
        nonlocal total
        with os.scandir(handle) as listing:
            entries = list(listing)
        for entry in entries:
            if entry.is_symlink():
                raise WorkspaceError(LINKED)
            try:
                found = entry.stat(follow_symlinks=False)
            except FileNotFoundError:
                continue
            if entry.name == '.git' or not (stat.S_ISREG(found.st_mode) or stat.S_ISDIR(found.st_mode)):
                raise WorkspaceError('Brand folders cannot contain Git metadata or special files.')
            if stat.S_ISDIR(found.st_mode):
                inner = open_folder(entry.name, handle, (found.st_dev, found.st_ino))
                if inner is not None:
                    try:
                        scan(inner, base / entry.name)
                    finally:
                        os.close(inner)
                continue
            total += found.st_size
            files.append((base / entry.name, found.st_size))
            if found.st_size > SOURCE_LIMIT or total > TREE_LIMIT or len(files) > FILE_LIMIT:
                raise WorkspaceError('This brand exceeds the file or working-copy size limit.')

    top = open_folder(str(folder))
    if top is None:
        return []
    try:
        scan(top, folder)
    finally:
        os.close(top)
    return sorted(files)


def tree_files(folder: Path):
    """Validate every copied path, including hidden entries, before following or writing it."""
    return [path for path, _ in _store().walk(folder)]


def read_json(path: Path, default=None):
    try:
        path = no_links(path)
        if path.stat().st_size > 4_000_000:
            raise WorkspaceError('Brand metadata is too large to read.')
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def write_json(path: Path, value) -> None:
    put(path, (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode('utf-8'))


def put(path: Path, data: bytes) -> None:
    path = no_links(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f'.{path.name}-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def fingerprint(folder: Path, digests: dict | None = None) -> str:
    """One hash of every file in `folder`, by path and content. `digests`, when given, is
    {path: (its stat, its hash)} from an earlier fingerprint of the same folder: a file whose
    size, times and inode are as they were then is not read again, and one that changed is."""
    folder = no_links(folder)
    if not folder.exists():
        return 'none'
    digest = hashlib.sha256()
    for path in tree_files(folder):
        if path.name == '.DS_Store':
            continue
        digest.update(path.relative_to(folder).as_posix().encode('utf-8') + b'\0')
        seen = path.stat()
        mark = (seen.st_size, seen.st_mtime_ns, seen.st_ctime_ns, seen.st_ino)
        held = digests.get(path) if digests is not None else None
        if held is not None and held[0] == mark:
            file_hash = held[1]
        else:
            with path.open('rb') as stream:
                file_hash = hashlib.file_digest(stream, 'sha256').digest()
            if digests is not None:
                digests[path] = (mark, file_hash)
        digest.update(file_hash)
    return digest.hexdigest()


def files_in(folder: Path, walked=None) -> list[dict]:
    """The files in `folder` a person added, with their sizes. `walked` is a walk() of a
    folder that holds this one, when one was just made: it is not walked again."""
    folder = no_links(folder)
    if walked is None:
        walked = _store().walk(folder)
    shown = []
    for path, size in walked:
        if folder not in path.parents:
            continue
        relative = path.relative_to(folder)
        if not any(part.startswith('.') for part in relative.parts):
            shown.append({'name': relative.as_posix(), 'size': size})
    return shown


def checked(found, folder, env=None) -> dict:
    """What `pack check` says of a pack or library folder: {'ok', 'problems'}."""
    try:
        _, said = brand_skill.answer(found, ['pack', 'check', str(folder), '--json'], env=env)
    except WorkspaceError as failure:
        return {'ok': False, 'problems': [str(failure)]}
    problems = [str(each) for each in (said.get('problems') or [])] if isinstance(said, dict) else []
    return {'ok': bool(isinstance(said, dict) and said.get('ok')) and not problems,
            'problems': problems or ([] if isinstance(said, dict) else ['pack check gave no answer.'])}


def library_summary(archive: Path) -> dict:
    try:
        no_links(archive)
        with zipfile.ZipFile(archive) as opened:
            if any(opened.getinfo(name).file_size > 4_000_000 for name in ('library.json', 'icons.json')):
                raise WorkspaceError('Icon library metadata is too large to read.')
            library = json.loads(opened.read('library.json'))
            icons = json.loads(opened.read('icons.json')).get('icons') or []
        return {'name': str(library.get('name') or archive.parent.name),
                'kind': library.get('kind'), 'count': len(icons)}
    except (OSError, KeyError, ValueError, zipfile.BadZipFile, AttributeError):
        return {'name': archive.parent.name, 'kind': None, 'count': None}


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def same(part, one, other) -> bool:
    if one is None or other is None:
        return one is other
    if part == 'guide':
        return one.strip() == other.strip()
    try:
        return canonical(json.loads(one)) == canonical(json.loads(other))
    except ValueError:
        return one == other


def decode(content) -> bytes:
    try:
        if not isinstance(content, str) or not content:
            raise ValueError
        return base64.b64decode(content, validate=True)
    except ValueError:
        raise WorkspaceError('The file did not arrive whole. Choose it again.') from None
