"""Actual-pixel review, private exact-basis records, and a shared bounded repair ledger."""
from copy import deepcopy
import json
import secrets

from . import exports
from .contracts import basis, canonical, digest
from .validation import require, text
from .workspace import _read


def latest(store, project):
    root = store._project(project['id']) / 'jobs'
    if not root.exists():
        return None
    require(not root.is_symlink(), 'Review history cannot traverse a link.')
    records = []
    for folder in root.iterdir():
        if folder.name.startswith('visual_') and not folder.is_symlink():
            try:
                saved = json.loads(_read(store.root, f'projects/{project["id"]}/jobs/{folder.name}/review.json', 100_000))
            except (OSError, ValueError):
                continue
            if saved.get('basis') == basis(project) and saved.get('scene_digest') == digest(project['scene']):
                records.append((saved.get('sequence', 0), folder.name, saved))
    return max(records, key=lambda item: item[:2])[2] if records else None


def inspect(engine, ident, *, expected_revision):
    project = engine.store.read(ident)
    engine.store.expect(project, expected_revision)
    initial_sequence = (latest(engine.store, project) or {}).get('sequence', 0)
    require(engine.assistant is not None, 'Configure an assistant for pixel inspection, or record your own actual-page review.')
    delivery = next((d for d in engine.deliveries(ident) if d['basis'] == basis(project)
                    and d['scene_digest'] == digest(project['scene'])), None)
    require(delivery is not None, 'Render the current page before inspecting actual pixels.')
    _, page = exports.read(engine.store, ident, delivery['id'], 'png')
    images = [page]
    artwork = [e['asset_id'] for e in project['scene']['elements'] if e['kind'] == 'artwork']
    if artwork:
        mime, raw = engine.store.read_asset(ident, artwork[0])
        require(mime == 'image/png', 'Inspect PNG artwork only.')
        images.append(raw)
    context = {'scene': project['scene'], 'brief': project['brief'], 'facts': project['facts'],
               'brand': project['brand'], 'images': ['actual composed page', 'original artwork'][:len(images)]}
    answer = engine.assistant.inspect_images(context, images)
    require(isinstance(answer, dict) and set(answer) == {'capability', 'observations', 'findings'}
            and answer['capability'] == 'inspected'
            and isinstance(answer['observations'], list) and 0 < len(answer['observations']) <= 30
            and isinstance(answer['findings'], list) and len(answer['findings']) <= 30,
            'Image inspection returned no valid located observations. Your page is unchanged; inspect manually or retry explicitly.')
    allowed = {'page', *(e['id'] for e in project['scene']['elements']),
               *(r['id'] for r in project['scene'].get('art_regions', []))}
    kinds = {'counts', 'relationships', 'crop', 'resolution', 'label_clearance', 'brand', 'factual_implications'}
    for observation in answer['observations']:
        require(isinstance(observation, dict) and set(observation) == {'kind', 'region_id', 'text'}
                and observation['kind'] in kinds and observation['region_id'] in allowed
                and text(observation['text'], limit=2000), 'Image observations must locate what was actually inspected.')
    require(kinds <= {o['kind'] for o in answer['observations']},
            'Pixel inspection did not cover the complete image-review checklist. Your page is unchanged; inspect manually or retry explicitly.')
    for finding in answer['findings']:
        require(isinstance(finding, dict) and set(finding) == {'region_id', 'blocking', 'message', 'correction'}
                and finding['region_id'] in allowed and type(finding['blocking']) is bool
                and text(finding['message'], limit=2000) and text(finding['correction'], limit=2000),
                'Image findings must identify an actual scene region and a precise correction.')
    with engine.store.locked():
        current = engine.store.read(ident)
        engine.store.expect(current, expected_revision)
        previous = latest(engine.store, current)
        require((previous or {}).get('sequence', 0) == initial_sequence,
                'A newer visual review was recorded while the assistant worked. That decision is kept; the late result was not adopted.')
        record = {**deepcopy(answer), 'observations': [o['kind'] + ' · ' + o['region_id'] + ': ' + o['text'] for o in answer['observations']],
                  'schema': 1, 'by': 'assistant',
                  'sequence': (previous or {}).get('sequence', 0) + 1,
                  'status': 'failed' if any(f['blocking'] for f in answer['findings']) else 'passed',
                  'basis': basis(current), 'scene_digest': digest(current['scene']), 'export_id': delivery['id'],
                  'inspected_png_sha256': next(f['sha256'] for f in delivery['files'] if f['format'] == 'png')}
        engine.store.write_blob(ident, 'jobs/visual_' + secrets.token_hex(12) + '/review.json', canonical(record))
        return record


def consume_repair(store, ident, *, expected_revision, kind):
    """Reserve before work. Layout and image repairs share two attempts across restarts."""
    with store.locked():
        project = store.read(ident)
        store.expect(project, expected_revision)
        return consume_repair_locked(store, project, kind=kind)


def consume_repair_locked(store, project, *, kind):
    ident = project['id']
    root = store._project(ident) / 'jobs'
    require(not root.is_symlink(), 'Repair history cannot traverse a link.')
    used = len(list(root.glob('repair_*/intent.json'))) if root.exists() else 0
    require(used < 2, 'The shared two-attempt repair budget is exhausted. Make a focused manual revision or revise the story.')
    record = {'kind': kind, 'revision': project['revision'], 'basis': basis(project), 'attempt': used + 1}
    store.write_blob(ident, 'jobs/repair_' + secrets.token_hex(12) + '/intent.json', canonical(record))
    return record
