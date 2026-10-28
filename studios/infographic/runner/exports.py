"""Immutable revision-bound local delivery, with no assistant or image-provider call."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import secrets
import tempfile

from . import render, svg
from .contracts import Invalid, basis, canonical, digest
from .validation import identifier, require, validate_project, sha, input_basis, text
from .workspace import _read

FORMATS = {'png': ('page.png', 'image/png'), 'pdf': ('page.pdf', 'application/pdf'),
           'svg': ('page.svg', 'image/svg+xml'), 'text': ('page.txt', 'text/plain; charset=utf-8')}


def validate_manifest(value, export_id, project=None):
    require(isinstance(value, dict) and value.get('schema') == 1 and value.get('id') == export_id
            and identifier(export_id) and type(value.get('revision')) is int and value['revision'] >= 0
            and type(value.get('draft')) is bool and isinstance(value.get('files'), list)
            and len(value['files']) == 4 and text(value.get('font_caveat'), limit=2000), 'The delivery manifest is incomplete or has changed identity.')
    input_basis(value.get('basis'))
    require(all(sha(value.get(k)) for k in ('scene_digest', 'checks_digest', 'approval_digest', 'measurement_sha256')),
            'The delivery has invalid content identities.')
    seen = set()
    for item in value['files']:
        require(isinstance(item, dict) and item.get('format') in FORMATS and item['format'] not in seen,
                'The delivery must contain each of its four formats exactly once.')
        kind = item['format']; seen.add(kind)
        require(item.get('file') == 'exports/' + export_id + '/' + FORMATS[kind][0]
                and item.get('mime') == FORMATS[kind][1] and sha(item.get('sha256'))
                and type(item.get('bytes')) is int and 0 < item['bytes'] <= (46_000_000 if kind == 'svg' else 32_000_000),
                'An exported file changed its identity, type or bounded size.')
    if project is not None:
        require(value['revision'] == project['revision'] and value['basis'] == basis(project)
                and value['scene_digest'] == digest(project['scene']) and value['checks_digest'] == digest(project['checks'])
                and value['approval_digest'] == digest(project['approval']), 'The saved delivery does not belong to this exact checked revision.')
    return value


def build(store, ident, *, expected_revision, executable, draft=False, renderer=render.render):
    from . import visual_review
    with store.locked():
        project = store.read(ident)
        store.expect(project, expected_revision)
        validate_project(project)
        require(draft or project['approval'] is not None, 'Approve this exact checked page before creating final exports.')
        require(draft or visual_review.checked(store, project),
                'The visual review changed. Run checks and approve the latest review before final export.')
        scene_id = digest(project['scene'])
        key = 'e_' + digest({'project': project, 'draft': draft})[:24]
        marker = f'projects/{ident}/exports/{key}/manifest.json'
        folder = store._project(ident) / 'exports' / key
        require(not folder.parent.is_symlink() and not folder.is_symlink(), 'Export folders cannot be links.')
        if folder.exists():
            manifest = validate_manifest(json.loads(_read(store.root, marker, 100_000)), key, project)
            require(manifest['draft'] == draft, 'The saved delivery changed its approval label.')
            for item in manifest['files']:
                raw = _read(store.root, f'projects/{ident}/' + item['file'], 64_000_000)
                require(hashlib.sha256(raw).hexdigest() == item['sha256'], 'A prior delivery is damaged; restore its exact files before retrying.')
            return manifest
    # Render outside the project lock; adopt only on the unchanged content revision.
    with tempfile.TemporaryDirectory(prefix='infographic-export-') as temp:
        output = Path(temp) / 'page'
        renderer(svg.compose(store, project, draft=draft), preset=project['brief']['preset'],
                 fonts=[project['brand']['font']], executable=executable, destination=output)
        dimensions = render.dimensions(project['brief']['preset'])
        require(render.png_size(output / 'page.png') == (dimensions['width_px'], dimensions['height_px']),
                'The exported PNG does not match its selected dimensions.')
        pages = render.pdf_pages(output / 'page.pdf')
        require(len(pages) == 1 and all(abs(a - b) <= 1 for a, b in zip(pages[0],
                (dimensions['width_pt'], dimensions['height_pt']))), 'The export must be exactly one page at its selected physical size.')
        measurement_bytes = (output / 'measurements.json').read_bytes()
        require(len(measurement_bytes) <= 100_000, 'The renderer measurement report exceeds its limit.')
        measurement = json.loads(measurement_bytes)
        require(measurement.get('complete') is True and not any(measurement.get(k) for k in
                ('missing_fonts', 'invalid_assets', 'overflow')), 'Resolve actual renderer findings before delivery.')
        (output / 'page.txt').write_text(svg.accessible_text(project, draft=draft), encoding='utf-8')
        files = []
        payload = {}
        for kind, (name, mime) in FORMATS.items():
            path = output / name
            require(path.is_file() and not path.is_symlink() and path.stat().st_size <= (46_000_000 if kind == 'svg' else 32_000_000),
                    'The exported file is missing, unsafe or too large.')
            raw = path.read_bytes()
            relative = 'exports/' + key + '/' + name
            files.append({'format': kind, 'file': relative, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw), 'mime': mime})
            payload[relative] = raw
        manifest = {'schema': 1, 'id': key, 'revision': project['revision'], 'basis': basis(project),
                    'scene_digest': scene_id, 'checks_digest': digest(project['checks']),
                    'approval_digest': digest(project['approval']), 'draft': draft,
                    'measurement_sha256': hashlib.sha256(measurement_bytes).hexdigest(),
                    'font_caveat': project['brand']['font_license'], 'files': files}
        with store.locked():
            current = store.read(ident)
            store.expect(current, expected_revision)
            require(basis(current) == basis(project) and current['approval'] == project['approval'],
                    'The page changed during export. The earlier approved delivery is kept.')
            require(draft or visual_review.checked(store, current),
                    'The visual review changed during export. Run checks and approve its latest decision.')
            if folder.exists():
                # A concurrent identical export may have finished while this one rendered.
                return validate_manifest(json.loads(_read(store.root, marker, 100_000)), key, project)
            pending = 'exports/.pending_' + secrets.token_hex(12)
            for relative, raw in payload.items():
                store.write_blob(ident, pending + '/' + Path(relative).name, raw)
            store.write_blob(ident, pending + '/measurements.json', measurement_bytes)
            store.write_blob(ident, pending + '/manifest.json', canonical(manifest))
            os.rename(store._project(ident) / pending, folder)
        return manifest


def read(store, ident, export_id, kind):
    require(identifier(export_id) and kind in FORMATS, 'Choose a listed local export and format.')
    store.read(ident)
    manifest = validate_manifest(json.loads(_read(store.root, f'projects/{ident}/exports/{export_id}/manifest.json', 100_000)), export_id)
    item = next((item for item in manifest['files'] if item['format'] == kind), None)
    require(item is not None and item['file'] == 'exports/' + export_id + '/' + FORMATS[kind][0],
            'The requested format is absent or its delivery identity is invalid.')
    raw = _read(store.root, f'projects/{ident}/' + item['file'], 46_000_000 if kind == 'svg' else 32_000_000)
    require(hashlib.sha256(raw).hexdigest() == item['sha256'], 'The exported bytes no longer match their immutable identity.')
    return FORMATS[kind][1], raw
