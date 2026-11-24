"""The parts of the runner's `desk_chat`, the checked conversation operations on the desk,
both deck studios share. A studio binds them into its own module with
`studio_core.modules.bind`; they read that module's names.

CHANGED stays in each studio: it is a value with the item's word in it. Preparing,
checking and publishing a piece differ between the studios and stay in each.
"""
from __future__ import annotations

# ruff: noqa: F821  these definitions read the names of the studio module they are
# bound into; each studio's test_shared_runner_use checks every one resolves there.

import hashlib
import json
import zlib

KINDS = ('text', 'outline', 'research', 'drawing', 'part')


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _preview_png(data):
    """Keep visual PNG chunks byte-for-byte; discard only text and clock metadata."""
    signature = b'\x89PNG\r\n\x1a\n'
    if not data.startswith(signature):
        raise WorkspaceError('The look preview is not a complete PNG.')
    kept, offset, image = [signature], len(signature), False
    while offset + 12 <= len(data):
        length = int.from_bytes(data[offset:offset + 4], 'big')
        end = offset + length + 12
        kind = data[offset + 4:offset + 8]
        body = data[offset + 8:end - 4]
        if end > len(data) or not all(65 <= b <= 90 or 97 <= b <= 122 for b in kind) \
                or zlib.crc32(kind + body) != int.from_bytes(data[end - 4:end], 'big') \
                or (offset == 8 and (kind != b'IHDR' or length != 13)) \
                or (offset != 8 and kind == b'IHDR'):
            break
        if kind not in (b'tEXt', b'zTXt', b'iTXt', b'tIME'):
            kept.append(data[offset:end])
        image = image or kind == b'IDAT'
        if kind == b'IEND':
            if length == 0 and end == len(data) and image:
                return b''.join(kept)
            break
        offset = end
    raise WorkspaceError('The look preview is a malformed or truncated PNG.')


def context(engine, path, target):
    with _prepared(engine, path, target) as prepared:
        return prepared[-1]


def save(engine, path, request):
    return submit(engine, path, request)


# Explicit saved-work migration stays separate from checked content publication.
def prepare_migration(record, saved_inputs):
    from runner.desk_migration import prepare_migration as prepare
    return prepare(record, saved_inputs)


def migration_preview(engine, path):
    from runner.desk_migration import migration_preview as preview
    return preview(engine, path)


def migrate(engine, path, expected):
    from runner.desk_migration import migrate as apply
    return apply(engine, path, expected)


NAMES = ('KINDS', '_digest', '_preview_png', 'context', 'save', 'prepare_migration',
         'migration_preview', 'migrate')
METHODS = {}
