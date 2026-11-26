"""Paths inside a research case folder: confined, link-free, written whole.

Part of the schema-2 Harness Research integration; studio_core.research_contract
re-exports every name here."""
import os
from pathlib import Path
import re
import secrets

# How a supplied document is named where its origin is shown (issue #550).
SUPPLIED = 'Supplied document'


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


def local_origin(origin):
    """Whether a research source's origin names a document on a computer, not a web address
    or a label: Harness Research 1.6.0 records a new supplied document as `supplied:<name>`
    (its name inside the folder it was taken from); earlier versions recorded the absolute
    path of that folder's copy, and a `file:` address is one too. A section author is shown a
    supplied document's retained copy as `retained-original:<file>` (research_sections)."""
    return isinstance(origin, str) and (origin.startswith(('supplied:', 'retained-original:', 'file:', '/', '\\\\'))
                                        or bool(re.match(r'[A-Za-z]:[\\/]', origin)))


def shown_origin(origin):
    """A source's origin as a person or a writer is shown it: a web address or a label as it
    is, and a supplied document, in either form `local_origin` knows, as SUPPLIED, never a
    folder of this computer."""
    if not isinstance(origin, str):
        return ''
    return SUPPLIED if local_origin(origin) else origin


def write(root, name, value):
    path = inside(root, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + '.pending-' + secrets.token_hex(6))
    try:
        pending.write_bytes(value if isinstance(value, bytes) else value.encode('utf-8'))
        os.replace(pending, path)
    finally:
        pending.unlink(missing_ok=True)
