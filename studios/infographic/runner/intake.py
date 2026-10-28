"""Owned immutable intake previews: preview/import uses one captured document revision."""
from __future__ import annotations

import hashlib
import secrets

from . import documents, sources
from .contracts import MAX_RECORD_BYTES, MAX_SOURCE_BYTES, canonical, digest
from .validation import identifier, require, text
from .workspace import _atomic, _json, _read, data_root, file_lock


def prepare(raw, *, kind, name, selection=None, provenance=None, extracted=None):
    require(text(name, limit=200) and '/' not in name and '\\' not in name, 'Choose a plain source display name.')
    require(type(raw) is bytes and 0 < len(raw) <= MAX_SOURCE_BYTES, 'Supply one nonempty source within 16 MB.')
    require(kind in sources.SOURCE_KINDS, 'Choose a supported supplied document type.')
    if extracted is None:
        if kind in ('pdf', 'docx', 'html'): extracted = documents.extract(raw, kind)
        elif kind == 'csv':
            value, selection = sources.select_csv(raw, selection)
            extracted = {'text': value, 'warnings': [], 'locations': [], 'readable': True}
        else:
            require(kind in ('text', 'markdown'), 'Remote or reviewed sources need a captured extractor result.')
            value = sources.decoded(raw)
            extracted = {'text': value, 'warnings': [], 'locations': [], 'readable': True}
    require(len(canonical(extracted)) <= 24_000_000, 'The extraction preview exceeds its bounded size.')
    ident = secrets.token_hex(16)
    record = {'schema': 1, 'id': ident, 'kind': kind, 'name': name, 'selection': selection,
              'provenance': provenance, 'original_sha256': hashlib.sha256(raw).hexdigest(),
              'extracted_sha256': digest(extracted)}
    root = data_root() / 'jobs' / ('intake_' + ident)
    with file_lock(data_root() / '.intake.lock'):
        _atomic(root / 'original.raw', raw)
        _atomic(root / 'extracted.json', canonical(extracted))
        _atomic(root / 'preview.json', canonical(record))
    return {**record, 'characters': len(extracted['text']), 'readable': bool(extracted['text'].strip()),
            'excerpt': extracted['text'][:2500], 'warnings': extracted.get('warnings', []),
            'locations': extracted.get('locations', []), 'extractor': extracted.get('extractor', 'supplied-text')}


def read(ident):
    require(identifier(ident), 'Choose a saved intake preview.')
    root = data_root() / 'jobs' / ('intake_' + ident)
    record = _json(root, 'preview.json', MAX_RECORD_BYTES)
    raw = _read(root, 'original.raw', MAX_SOURCE_BYTES)
    extracted = _json(root, 'extracted.json', 24_000_000)
    require(record.get('schema') == 1 and record.get('id') == ident
            and record['original_sha256'] == hashlib.sha256(raw).hexdigest()
            and record['extracted_sha256'] == digest(extracted),
            'This source preview changed. Import a fresh preview; the existing infographic is kept.')
    return record, raw, extracted


def adopt(store, ident, capture_id, *, expected_revision, acknowledge_warnings=False, replace_id=None):
    record, raw, extracted = read(capture_id)
    return sources.capture_extracted(store, ident, raw, extracted,
        kind=record['kind'], name=record['name'], selection=record['selection'], provenance=record['provenance'],
        expected_revision=expected_revision, acknowledge_warnings=acknowledge_warnings, replace_id=replace_id)
