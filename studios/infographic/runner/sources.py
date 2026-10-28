"""Exact, immutable supplied-source capture. No fetch, inference, or coercion."""
from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat

from .contracts import MAX_SOURCE_BYTES, Invalid, canonical, digest
from .validation import require, text

KINDS = {'.txt': 'text', '.md': 'markdown', '.csv': 'csv', '.pdf': 'pdf', '.docx': 'docx', '.html': 'html', '.htm': 'html'}
SOURCE_KINDS = set(KINDS.values()) | {'google-doc', 'url', 'research', 'handoff'}
MAX_ROWS = 20_000
MAX_COLUMNS = 100
DECIMAL = re.compile(r'[+-]?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z')


def read_file(path: Path) -> tuple[str, bytes]:
    path = Path(path)
    kind = KINDS.get(path.suffix.lower())
    require(kind is not None, 'Use text, Markdown, CSV, PDF, Word (.docx), or HTML.')
    # Reject links in every component; never read a device/FIFO as an upload.
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'Source files cannot traverse links.')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), 'Choose a regular source file.')
        raw = stream.read(MAX_SOURCE_BYTES + 1)
    require(0 < len(raw) <= MAX_SOURCE_BYTES, 'Supply a nonempty source no larger than 16 MB.')
    if kind in ('text', 'markdown', 'csv', 'html'): decoded(raw)
    return kind, raw


def decoded(raw: bytes) -> str:
    require(type(raw) is bytes and 0 < len(raw) <= MAX_SOURCE_BYTES,
            'Supply a nonempty source no larger than 16 MB.')
    try:
        value = raw.decode('utf-8-sig')
    except UnicodeError as failure:
        raise Invalid('The source is not UTF-8. Save it as UTF-8 text and try again.') from failure
    require('\x00' not in value and bool(value.strip()), 'The source has no readable text or contains binary data.')
    return value.replace('\r\n', '\n').replace('\r', '\n')


def csv_preview(raw: bytes) -> dict:
    value = decoded(raw)
    try:
        rows = []
        for row in csv.reader(io.StringIO(value, newline=''), strict=True):
            require(len(rows) <= MAX_ROWS, 'CSV exceeds 20,000 rows. Supply an explicitly selected smaller file.')
            require(0 < len(row) <= MAX_COLUMNS, 'CSV needs 1–100 columns without blank records.')
            rows.append(row)
    except (csv.Error, OverflowError) as failure:
        raise Invalid('CSV could not be parsed. Check quoting and column separators.') from failure
    require(len(rows) >= 2, 'CSV needs a header and at least one data row.')
    header = rows[0]
    require(all(text(v, limit=200) for v in header) and len(set(header)) == len(header),
            'CSV headers must be nonempty and unique.')
    require(all(len(row) == len(header) for row in rows[1:]), 'CSV rows must have the same columns as the header.')
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'columns': header,
            'row_count': len(rows) - 1, 'rows': rows[1:],
            'row_numbering': 'Data rows start at 1; the header is not counted.'}


def select_csv(raw: bytes, selection: dict) -> tuple[str, dict]:
    preview = csv_preview(raw)
    require(isinstance(selection, dict) and set(selection) == {'confirmed', 'sha256', 'rows', 'columns'},
            'Confirm the CSV preview with its hash, data-row numbers, and typed columns.')
    require(selection['confirmed'] is True and selection['sha256'] == preview['sha256'],
            'The CSV preview changed or was not confirmed. Preview it again.')
    rows, columns = selection['rows'], selection['columns']
    require(isinstance(rows, list) and bool(rows) and len(rows) <= MAX_ROWS
            and all(type(n) is int and 1 <= n <= preview['row_count'] for n in rows)
            and len(set(rows)) == len(rows), 'Select unique data-row numbers from this CSV.')
    require(isinstance(columns, list) and bool(columns) and len(columns) <= MAX_COLUMNS,
            'Select at least one typed CSV column.')
    names = []
    for column in columns:
        require(isinstance(column, dict) and set(column) == {'name', 'type', 'unit'}
                and column['name'] in preview['columns'] and column['type'] in ('text', 'number', 'date')
                and text(column['unit'], empty=True, limit=100), 'Choose CSV column names, types and units explicitly.')
        require(column['type'] != 'number' or bool(column['unit'].strip()), 'Numeric CSV columns need an explicit unit.')
        names.append(column['name'])
    require(len(set(names)) == len(names), 'Select each CSV column once.')
    output = ['CSV supplied data. Missing cells are null; literals are preserved.',
              canonical({'columns': columns}).decode()]
    for n in rows:
        cells = {}
        for column in columns:
            literal = preview['rows'][n - 1][preview['columns'].index(column['name'])]
            if literal and column['type'] == 'number':
                require(DECIMAL.fullmatch(literal) is not None,
                        f'Row {n}, {column["name"]}: ambiguous number. Use plain decimal notation, or select text.')
                try:
                    require(Decimal(literal).is_finite(), 'CSV numbers must be finite.')
                except InvalidOperation as failure:
                    raise Invalid('CSV number could not be read.') from failure
            if literal and column['type'] == 'date':
                try:
                    require(re.fullmatch(r'\d{4}-\d{2}-\d{2}', literal) is not None,
                            'CSV dates need YYYY-MM-DD form.')
                    date.fromisoformat(literal)
                except ValueError as failure:
                    raise Invalid(f'Row {n}, {column["name"]}: use an explicit ISO date or select text.') from failure
            cells[column['name']] = literal if literal else None
        output.append(canonical({'row': n, 'cells': cells}).decode())
    return '\n'.join(output) + '\n', {'rows': rows, 'columns': columns, 'confirmed': True}


def capture(store, ident: str, raw: bytes, *, kind='text', name='Pasted information',
            selection=None, replace_id=None, expected_revision: int, acknowledge_warnings=False) -> dict:
    require(kind in KINDS.values(), 'Use a supported supplied file type.')
    if kind in ('pdf', 'docx', 'html'):
        from .documents import extract
        require(selection is None, 'CSV selection applies only to CSV sources.')
        return capture_extracted(store, ident, raw, extract(raw, kind), kind=kind, name=name,
                                 replace_id=replace_id, expected_revision=expected_revision,
                                 acknowledge_warnings=acknowledge_warnings)
    value = decoded(raw)
    selected = None
    if kind == 'csv': value, selected = select_csv(raw, selection)
    elif selection is not None: raise Invalid('CSV selection applies only to CSV sources.')
    return capture_extracted(store, ident, raw, {'text': value}, kind=kind, name=name,
                             replace_id=replace_id, expected_revision=expected_revision, selection=selected)


def capture_extracted(store, ident, raw, extracted, *, kind, name, expected_revision,
                      replace_id=None, acknowledge_warnings=False, selection=None, provenance=None):
    """Internal capture boundary for deterministic local or explicitly retrieved snapshots."""
    require(kind in SOURCE_KINDS and type(raw) is bytes and 0 < len(raw) <= MAX_SOURCE_BYTES,
            'Supply a supported captured source within 16 MB.')
    require(text(name, limit=200) and '/' not in name and '\\' not in name,
            'Give a short display name, without a machine path.')
    value = extracted['text']
    require(isinstance(value, str) and value.strip() and '\x00' not in value,
            'No readable text was found. Supply text or another accessible document; no OCR or provider upload was attempted.')
    require(type(acknowledge_warnings) is bool, 'Confirm readable-only coverage explicitly.')
    warnings = extracted.get('warnings', [])
    require(not warnings or acknowledge_warnings,
            'Review the extraction gaps and confirm using only the readable text before importing.')
    normalized = value.encode('utf-8')
    require(len(normalized) <= MAX_SOURCE_BYTES, 'Selected source text exceeds 16 MB; confirm a smaller explicit selection.')
    raw_hash = hashlib.sha256(raw).hexdigest()
    normalized_hash = hashlib.sha256(normalized).hexdigest()
    record = {'id': 's_' + hashlib.sha256(raw + normalized).hexdigest()[:24], 'kind': kind,
              'name': name, 'file': 'sources/' + raw_hash + '.raw', 'sha256': raw_hash,
              'bytes': len(raw), 'characters': len(value),
              'normalized_file': 'sources/' + normalized_hash + '.txt',
              'normalized_sha256': normalized_hash, 'selection': selection}
    if 'extractor' in extracted:
        coverage = {'extractor': extracted['extractor'], 'locations': extracted['locations'],
                    'warnings': warnings, 'acknowledged': acknowledge_warnings}
        record.update(coverage=coverage, coverage_sha256=digest(coverage))
    if provenance:
        record['provenance'] = provenance
        record['id'] = 's_' + digest({'original': raw_hash, 'normalized': normalized_hash, 'provenance': provenance})[:24]
    with store.locked():
        project = store.read(ident)
        store.expect(project, expected_revision)
        if replace_id is not None:
            require(any(s['id'] == replace_id for s in project['sources']), 'Choose an existing source to replace.')
        sources = [s for s in project['sources'] if s['id'] not in (replace_id, record['id'])]
        sources.append(record)
        store.write_blob(ident, record['file'], raw)
        store.write_blob(ident, record['normalized_file'], normalized)
        return store.change_locked(project, {'sources': sources})


def read(store, project: dict, source: dict) -> str:
    from .workspace import _read
    raw = _read(store.root, f'projects/{project["id"]}/{source["file"]}', MAX_SOURCE_BYTES)
    require(len(raw) == source['bytes'] and hashlib.sha256(raw).hexdigest() == source['sha256'],
            'The original source no longer matches its captured revision.')
    if source['kind']=='research':
        from .research import validate_capture
        validate_capture(raw,source.get('provenance',{}))
    if 'normalized_file' not in source:
        return decoded(raw)
    normalized = _read(store.root, f'projects/{project["id"]}/{source["normalized_file"]}', MAX_SOURCE_BYTES)
    require(hashlib.sha256(normalized).hexdigest() == source['normalized_sha256'],
            'The normalized source no longer matches its captured revision.')
    value = normalized.decode('utf-8')
    require(len(value) == source['characters'], 'Source character coverage is inconsistent.')
    if source.get('coverage') is not None:
        coverage = source['coverage']
        require(digest(coverage) == source.get('coverage_sha256')
                and (not coverage['warnings'] or coverage['acknowledged']),
                'The captured extraction coverage changed or its gaps were not acknowledged.')
        require(all(type(point['start']) is int and type(point['end']) is int
                    and 0 <= point['start'] < point['end'] <= len(value) for point in coverage['locations']),
                'A document location no longer belongs to the captured text.')
    return value
