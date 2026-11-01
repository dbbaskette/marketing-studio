"""Bounded, read-only file reads for the Add existing work adapters (*_existing.py).

Every read refuses a link, anything that is not an ordinary file and anything larger than
its limit, and never raises for a missing or unreadable file: the adapter says what it left
out instead. Nothing here writes, locks, follows a link or reads the network.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

CHUNK = 1 << 20


def bounded(path: Path, limit: int) -> bytes | None:
    """A file's bytes, or None when it is a link, not a file or larger than `limit`."""
    try:
        if path.is_symlink() or not path.is_file():
            return None
        with open(path, 'rb') as stream:
            data = stream.read(limit + 1)
    except OSError:
        return None
    return data if len(data) <= limit else None


def record(path: Path, limit: int = 256_000) -> dict | None:
    """A JSON object read within `limit` bytes, or None."""
    data = bounded(path, limit)
    try:
        found = json.loads(data.decode('utf-8')) if data is not None else None
    except (UnicodeDecodeError, ValueError, RecursionError):
        return None
    return found if isinstance(found, dict) else None


def kept_record(root: Path, relative: str, limit: int) -> tuple[dict | None, bool]:
    """(A studio's own JSON record, True); (None, True) when there is none at all; or (None,
    False) when one is there but cannot be read safely: linked (the file or a folder on
    its way), larger than `limit`, or not a JSON object. A caller that would otherwise make
    up what the record says must refuse in the last case: the studio may still read it."""
    place, parts = Path(root), Path(relative).parts
    for part in parts:
        place = place / part
        if place.is_symlink():
            return None, False
        if not place.exists():
            return None, True
    found = record(place, limit)
    return found, found is not None


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(path: Path, limit: int = 256_000_000) -> str | None:
    """The SHA-256 of a file read in pieces, or None when it is a link, not a file, or
    larger than `limit`: what a studio's own `sha256_file` gives for an ordinary file."""
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
            return None
        found = hashlib.sha256()
        with open(path, 'rb') as stream:
            while chunk := stream.read(CHUNK):
                found.update(chunk)
    except OSError:
        return None
    return found.hexdigest()


def unlinked(root: Path, relative: str) -> bool:
    """Whether no folder between `root` and `relative` is a link (the file itself is
    checked by the read)."""
    place = Path(root)
    for part in Path(relative).parts[:-1]:
        place = place / part
        if place.is_symlink():
            return False
    return True


def folders(parent: Path, named, most: int) -> tuple[list[Path], bool]:
    """The folders directly in `parent` whose names `named` accepts, sorted, never a link;
    and whether there were more than `most`."""
    if parent.is_symlink() or not parent.is_dir():
        return [], False
    found, more = [], False
    try:
        with os.scandir(parent) as entries:
            for entry in entries:
                if named(entry.name) and entry.is_dir(follow_symlinks=False):
                    if len(found) >= most:
                        more = True
                        break
                    found.append(Path(entry.path))
    except OSError:
        return [], False
    return sorted(found), more
