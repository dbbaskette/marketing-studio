"""Paths inside a research case folder: confined, link-free, written whole.

Part of the schema-2 Harness Research integration; studio_core.research_contract
re-exports every name here."""
import os
from pathlib import Path
import secrets


def inside(root, name):
    if Path(root).is_symlink():
        raise ValueError('Research paths cannot traverse links.')
    root = Path(root).resolve()
    path = root / name
    if Path(name).is_absolute() or '..' in Path(name).parts:
        raise ValueError('Research paths must remain inside their case folder.')
    for part in (path, *path.parents):
        if part == root:
            break
        if part.is_symlink():
            raise ValueError('Research paths cannot traverse links.')
    if root not in path.resolve().parents:
        raise ValueError('Research paths must remain inside their case folder.')
    return path


def write(root, name, value):
    path = inside(root, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + '.pending-' + secrets.token_hex(6))
    try:
        pending.write_bytes(value if isinstance(value, bytes) else value.encode('utf-8'))
        os.replace(pending, path)
    finally:
        pending.unlink(missing_ok=True)
