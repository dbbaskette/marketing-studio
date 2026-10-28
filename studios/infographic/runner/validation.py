"""Standard-library validation for saved Infographic Studio contracts."""
from __future__ import annotations

import math
from pathlib import PurePosixPath
import re
import struct

from .contracts import (BASIS_FIELDS, COLLECTIONS, MAX_ASSET_BYTES, MAX_ASSET_EDGE, MAX_ASSET_PIXELS,
                        MAX_RECORD_BYTES, MAX_SOURCE_BYTES, PRESETS, PRODUCT, SCHEMA,
                        Invalid, basis, canonical, digest)

IDENT = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z')
SHA = re.compile(r'[0-9a-f]{64}\Z')
KINDS = ('comparison', 'process', 'timeline', 'numbers', 'parts', 'concept')
REQUIRED_CHECKS = {'coverage', 'facts', 'visual', 'layout', 'brand-accessibility'}
SECRET_KEYS = {'api_key', 'gemini_api_key', 'openai_api_key', 'token', 'session_key',
               'password', 'credentials', 'secret'}


def require(ok, message: str) -> None:
    if not ok:
        raise Invalid(message)


def text(value, *, empty=False, limit=10_000) -> bool:
    return isinstance(value, str) and (empty or bool(value.strip())) and len(value) <= limit


def number(value) -> bool:
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def member(value, known) -> bool:
    return isinstance(value, str) and value in known


def identifier(value) -> bool:
    return isinstance(value, str) and IDENT.fullmatch(value) is not None


def sha(value) -> bool:
    return isinstance(value, str) and SHA.fullmatch(value) is not None


def relative_path(value) -> bool:
    if not isinstance(value, str) or not value or '\\' in value or ':' in value or '\x00' in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and all(part not in ('', '.', '..') for part in value.split('/'))


def image_size(raw: bytes, mime: str) -> tuple[int, int]:
    """Bound encoded-image dimensions before the browser can decode the asset."""
    require(type(raw) is bytes and len(raw) <= MAX_ASSET_BYTES, 'The image exceeds its byte limit.')
    if mime == 'image/png':
        require(len(raw) >= 24 and raw[:8] == b'\x89PNG\r\n\x1a\n' and raw[12:16] == b'IHDR',
                'The image is not a supported PNG.')
        width, height = struct.unpack('>II', raw[16:24])
    elif mime == 'image/jpeg':
        require(raw.startswith(b'\xff\xd8'), 'The image is not a supported JPEG.')
        offset, size = 2, None
        while offset + 3 < len(raw):
            require(raw[offset] == 255, 'The JPEG marker stream is invalid.')
            while offset < len(raw) and raw[offset] == 255:
                offset += 1
            require(offset < len(raw), 'The JPEG marker stream is incomplete.')
            marker = raw[offset]
            offset += 1
            if marker in (0xD9, 0xDA):
                break
            if marker == 1 or 0xD0 <= marker <= 0xD7:
                continue
            require(offset + 2 <= len(raw), 'The JPEG segment is incomplete.')
            length = int.from_bytes(raw[offset:offset + 2], 'big')
            require(length >= 2 and offset + length <= len(raw), 'The JPEG segment size is invalid.')
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                require(length >= 8, 'The JPEG dimensions are incomplete.')
                height, width = struct.unpack('>HH', raw[offset + 3:offset + 7])
                size = width, height
                break
            offset += length
        require(size is not None, 'The JPEG has no readable dimensions.')
        width, height = size
    else:
        raise Invalid('Use PNG or JPEG image assets.')
    require(0 < width <= MAX_ASSET_EDGE and 0 < height <= MAX_ASSET_EDGE
            and width * height <= MAX_ASSET_PIXELS, 'The image dimensions exceed the decode limit.')
    return width, height


def _secrets(value, depth=0):
    require(depth < 32, 'The infographic record is nested too deeply.')
    if isinstance(value, dict):
        require(not {str(key).lower() for key in value} & SECRET_KEYS,
                'Credentials and session keys do not belong in an infographic record.')
        for child in value.values():
            _secrets(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            _secrets(child, depth + 1)


def records(value, label: str) -> dict:
    require(isinstance(value, list) and len(value) <= 1000, f'{label} must be a bounded list.')
    result = {}
    for record in value:
        require(isinstance(record, dict) and identifier(record.get('id')), f'{label} need stable IDs.')
        require(record['id'] not in result, f'{label} cannot repeat an ID.')
        result[record['id']] = record
    return result


def references(value, known, label):
    require(isinstance(value, list) and all(isinstance(key, str) and key in known for key in value),
            f'{label} refer to missing records.')
    require(len(value) == len(set(value)), f'{label} cannot repeat a reference.')


def input_basis(value):
    require(isinstance(value, dict) and set(value) == set(BASIS_FIELDS)
            and all(sha(part) for part in value.values()), 'Record the complete input basis.')


def bounds(value, *, normalized=False):
    require(isinstance(value, list) and len(value) == 4 and all(number(n) for n in value),
            'A region needs four finite bounds.')
    x, y, width, height = value
    require(x >= 0 and y >= 0 and width > 0 and height > 0, 'Region bounds must be positive.')
    if normalized:
        require(x + width <= 1.000001 and y + height <= 1.000001,
                'Image regions must fit the normalized canvas.')


def validate_image_result(result: dict) -> dict:
    """The same versioned handoff for Codex and Gemini; no provider is executed."""
    require(isinstance(result, dict) and len(canonical(result)) <= MAX_RECORD_BYTES,
            'The image-provider result must be a bounded object.')
    _secrets(result)
    require(set(result) == {'schema', 'provider', 'operation', 'attempt_id', 'state',
                            'reason', 'request_id', 'assets', 'usage', 'inspection'},
            'The image-provider result has missing or unsupported fields.')
    require(type(result['schema']) is int and result['schema'] == SCHEMA,
            'The image-provider result version is unsupported.')
    require(result['provider'] in ('codex', 'gemini') and result['operation'] in
            ('readiness', 'generate', 'edit', 'status', 'cancel'),
            'Name the image provider and supported operation.')
    require(result['attempt_id'] is None and result['operation'] == 'readiness'
            or identifier(result['attempt_id']), 'Image operations need an owned attempt ID.')
    require(result['state'] in ('unavailable', 'unverified', 'ready', 'queued', 'running',
                               'complete', 'failed', 'cancelled', 'unknown'),
            'Record the exact image-provider result state.')
    require(result['reason'] is None or result['reason'] in
            ('assistant-missing', 'sign-in-required', 'gemini-key-required',
             'image-tool-unavailable', 'image-model-unavailable', 'quota', 'provider-refusal',
             'timeout', 'stopped', 'invalid-asset', 'inspection-unavailable'),
            'Use a non-secret normalized image-provider outcome.')
    require(result['request_id'] is None or text(result['request_id'], limit=512),
            'The request identity must be bounded text or explicitly unknown.')
    require(result['inspection'] in ('available', 'unavailable', 'unknown'),
            'Record image-inspection capability separately from generation success.')
    usage = result['usage']
    require(isinstance(usage, dict) and set(usage) == {'cost', 'currency', 'input_tokens', 'output_tokens'},
            'Record reported or unknown image usage.')
    require(usage['cost'] is None or number(usage['cost']) and usage['cost'] >= 0,
            'Image cost must be nonnegative or unknown.')
    require(usage['currency'] is None or isinstance(usage['currency'], str)
            and re.fullmatch('[A-Z]{3}', usage['currency']) is not None,
            'Record the reported currency or leave it unknown.')
    require((usage['cost'] is None) == (usage['currency'] is None),
            'A reported image cost must include its currency.')
    require(all(usage[key] is None or type(usage[key]) is int and usage[key] >= 0
                for key in ('input_tokens', 'output_tokens')), 'Image token usage must be nonnegative or unknown.')
    assets = records(result['assets'], 'Returned image assets')
    for asset in assets.values():
        require(relative_path(asset.get('file')) and sha(asset.get('sha256'))
                and asset.get('mime') in ('image/png', 'image/jpeg'),
                'Returned images need safe owned paths, MIME types, and hashes.')
        require(type(asset.get('bytes')) is int and 0 < asset['bytes'] <= MAX_ASSET_BYTES
                and all(type(asset.get(k)) is int and 0 < asset[k] <= MAX_ASSET_EDGE for k in ('width', 'height'))
                and asset['width'] * asset['height'] <= MAX_ASSET_PIXELS,
                'Returned image dimensions and sizes must fit the asset limits.')
    if result['operation'] in ('generate', 'edit') and result['state'] == 'complete':
        require(bool(assets), 'Successful image work must return actual saved assets.')
        require(result['reason'] is None, 'A completed image operation cannot also report a refusal.')
    return result


def validate_project(project: dict) -> dict:
    require(isinstance(project, dict), 'An infographic record must be an object.')
    require(len(canonical(project)) <= MAX_RECORD_BYTES, 'The infographic record is too large.')
    _secrets(project)
    require(type(project.get('schema')) is int and project['schema'] == SCHEMA,
            'This infographic needs a supported record version.')
    require(set(project) == {'schema', 'product', 'id', 'owner', 'revision', 'brief',
                            'selected_story', 'brand', 'scene', 'approval', *COLLECTIONS},
            'The infographic record has missing or unsupported fields.')
    require(project['product'] == PRODUCT and identifier(project['id']) and identifier(project['owner']),
            'Record the full product name, infographic ID, and workspace owner.')
    require(type(project['revision']) is int and project['revision'] >= 0, 'Record a valid revision.')
    brief = project['brief']
    require(isinstance(brief, dict) and text(brief.get('title'), limit=200), 'Give the infographic a title.')
    require(brief.get('direction') in ('direct', 'suggest', 'hybrid') and member(brief.get('preset'), PRESETS),
            'Choose a supported story direction and page preset.')
    for key in ('audience', 'purpose'):
        require(text(brief.get(key), empty=True), 'Audience and purpose must be text.')
    for key in ('locked_words', 'exclusions'):
        require(isinstance(brief.get(key), list) and all(text(v) for v in brief[key]),
                'Exact wording and exclusions must be lists of text.')
    requirements = records(brief.get('must_show'), 'Required ideas')
    require(all(text(v.get('text')) for v in requirements.values()), 'Describe each required idea.')
    sources = records(project['sources'], 'Sources')
    for source in sources.values():
        require(source.get('kind') in ('text', 'markdown', 'csv') and sha(source.get('sha256')),
                'Sources need a supported type and captured hash.')
        require(relative_path(source.get('file')), 'Source files must be workspace-relative paths.')
        require(type(source.get('bytes')) is int and 0 <= source['bytes'] <= MAX_SOURCE_BYTES,
                'Source sizes must fit the capture limit.')
        require(type(source.get('characters')) is int and source['characters'] >= 0,
                'Record the captured source character count.')
    facts = records(project['facts'], 'Facts')
    for fact in facts.values():
        require(text(fact.get('statement')), 'Describe each factual assertion.')
        value = fact.get('value')
        require(text(value) or number(value), 'Facts need a literal text or finite numeric value.')
        if number(value):
            require(text(fact.get('unit')), 'Numeric facts need explicit units.')
        require(fact.get('status') in ('supplied', 'corroborated'), 'Distinguish supplied assertions.')
        evidence = fact.get('evidence')
        require(isinstance(evidence, list), 'Facts need source locations.')
        for point in evidence:
            require(isinstance(point, dict) and member(point.get('source_id'), sources),
                    'A fact refers to a missing captured source.')
            start, end = point.get('start'), point.get('end')
            require(type(start) is int and type(end) is int
                    and 0 <= start < end <= sources[point['source_id']]['characters'],
                    'A fact location is outside its captured source.')
        require(bool(evidence) or isinstance(fact.get('calculation'), dict),
                'A fact needs evidence or a reproducible calculation.')
    pending = set(facts)
    checked = set()
    while pending:
        ready = []
        for key in pending:
            fact, calculation = facts[key], facts[key].get('calculation')
            if calculation is None:
                ready.append(key)
                continue
            require(isinstance(calculation, dict), 'Record a structured calculation.')
            operands = calculation.get('operands')
            references(operands, facts, 'Calculation operands')
            require(len(operands) >= 2 and all(number(facts[v].get('value')) for v in operands),
                    'Calculations need at least two numeric operands.')
            if not set(operands) <= checked:
                continue
            op, values = calculation.get('operator'), [facts[v]['value'] for v in operands]
            units = {facts[v]['unit'] for v in operands}
            require(len(units) == 1, 'A calculation combines conflicting units.')
            if op == 'sum':
                actual = sum(values)
                require(fact.get('unit') in units, 'A sum must retain its source unit.')
            elif op == 'difference' and len(values) == 2:
                actual = values[0] - values[1]
                require(fact.get('unit') in units, 'A difference must retain its source unit.')
            elif op in ('ratio', 'percent_change') and len(values) == 2 and values[1] != 0:
                actual = values[0] / values[1]
                if op == 'percent_change':
                    actual = (actual - 1) * 100
                require(fact.get('unit') == ('%' if op == 'percent_change' else 'ratio'),
                        'Record the derived numeric unit.')
            else:
                raise Invalid('The calculation operator or denominator is unsupported.')
            require(number(fact['value']) and math.isclose(fact['value'], actual, rel_tol=1e-9, abs_tol=1e-9),
                    'The stored calculation does not match its operands.')
            ready.append(key)
        require(bool(ready), 'Calculations contain a cycle.')
        pending.difference_update(ready)
        checked.update(ready)
    stories = records(project['stories'], 'Stories')
    all_blocks = {}
    for story in stories.values():
        require(text(story.get('headline')) and text(story.get('takeaway')), 'Stories need a headline and takeaway.')
        blocks = records(story.get('blocks'), 'Story blocks')
        for block in blocks.values():
            require(block.get('kind') in KINDS, 'Choose a supported visual relationship.')
            references(block.get('fact_ids'), facts, 'Story facts')
            references(block.get('required_ids'), requirements, 'Required story ideas')
        references(story.get('omissions', []), requirements, 'Recorded omissions')
        all_blocks.update(blocks)
    selected = project['selected_story']
    require(selected is None or isinstance(selected, str) and selected in stories,
            'Select an existing story.')
    brand = project['brand']
    require(brand is None or isinstance(brand, dict) and text(brand.get('revision'))
            and sha(brand.get('sha256')), 'Pin the selected brand revision and digest.')
    assets = records(project['assets'], 'Assets')
    for asset in assets.values():
        require(relative_path(asset.get('file')) and sha(asset.get('sha256')),
                'Assets need safe relative paths and hashes.')
        require(asset.get('mime') in ('image/png', 'image/jpeg'), 'Use supported raster artwork.')
        require(type(asset.get('bytes')) is int and 0 < asset['bytes'] <= MAX_ASSET_BYTES,
                'The image asset exceeds its byte limit.')
        require(all(type(asset.get(k)) is int and 0 < asset[k] <= MAX_ASSET_EDGE for k in ('width', 'height')),
                'The image asset dimensions are unsupported.')
        require(asset['width'] * asset['height'] <= MAX_ASSET_PIXELS,
                'The image asset exceeds the total pixel limit.')
    scene = project['scene']
    elements = {}
    if scene is not None:
        require(selected is not None and isinstance(scene, dict) and identifier(scene.get('id')),
                'A scene needs a selected story and stable ID.')
        preset = PRESETS[brief['preset']]
        require(scene.get('unit') == preset['unit'] and all(number(scene.get(k))
                and math.isclose(scene[k], preset[k], abs_tol=.001) for k in ('width', 'height')),
                'The scene dimensions must match its selected page preset.')
        elements = records(scene.get('elements'), 'Scene elements')
        for element in elements.values():
            require(element.get('kind') in ('text', 'artwork', 'shape', 'chart', 'connector'),
                    'The scene element type is unsupported.')
            bounds(element.get('bounds'))
            x, y, width, height = element['bounds']
            require(x + width <= scene['width'] and y + height <= scene['height'],
                    'Scene elements must fit the page.')
            references(element.get('fact_ids', []), facts, 'Scene facts')
            if element['kind'] == 'artwork':
                require(member(element.get('asset_id'), assets), 'Artwork refers to a missing asset.')
            if element['kind'] == 'text':
                require(text(element.get('text')) and text(element.get('font'))
                        and number(element.get('font_size')) and element['font_size'] > 0,
                        'Text elements need words and explicit typography.')
            if element['kind'] == 'chart':
                values = element.get('values')
                refs = element.get('fact_ids', [])
                require(bool(refs) and isinstance(values, list) and len(values) == len(refs)
                        and all(number(v) and v == facts[key]['value'] for v, key in zip(values, refs)),
                        'Chart values must exactly match their numeric fact references.')
                require(text(element.get('unit')) and all(element['unit'] == facts[key].get('unit') for key in refs),
                        'A chart cannot silently combine different units.')
    briefs = records(project['image_briefs'], 'Image briefs')
    for image in briefs.values():
        require(scene is not None and image.get('story_id') == selected
                and image.get('scene_id') == scene['id'], 'Pin the image brief to its story and scene.')
        require(text(image.get('prompt'), limit=60_000), 'Record the exact provider-ready prompt.')
        input_basis(image.get('basis'))
        for key in ('goal', 'reading_order', 'style', 'exclusions', 'acceptance'):
            require(text(image.get(key)), 'Image briefs need explicit art direction and acceptance requirements.')
        require(image.get('canvas') == {k: scene[k] for k in ('width', 'height', 'unit')},
                'The image brief canvas must match the scene.')
        regions = records(image.get('regions'), 'Image regions')
        require(bool(regions), 'Describe the image composition regions.')
        for region in regions.values():
            bounds(region.get('bounds'), normalized=True)
            require(region.get('owner') in ('image', 'compositor'), 'Assign ownership of every region.')
        for obj in records(image.get('objects'), 'Image objects').values():
            require(member(obj.get('region_id'), regions) and text(obj.get('description'))
                    and type(obj.get('count')) is int and obj['count'] > 0,
                    'Describe each object, its count, and its region.')
        references(image.get('reference_assets'), assets, 'Image references')
        references(image.get('fact_ids'), facts, 'Image facts')
        require(isinstance(image.get('compositor_text'), list)
                and all(text(v) for v in image['compositor_text']), 'Record compositor-owned exact text.')
    attempts = records(project['attempts'], 'Image attempts')
    for attempt in attempts.values():
        require(attempt.get('provider') in ('codex', 'gemini') and attempt.get('state') in
                ('queued', 'running', 'complete', 'failed', 'cancelled', 'unknown'),
                'Record the image provider and exact attempt state.')
        require(type(attempt.get('revision')) is int and 0 <= attempt['revision'] <= project['revision'],
                'Record a valid image attempt revision.')
        require(member(attempt.get('image_brief_id'), briefs), 'An image attempt needs its saved brief.')
        input_basis(attempt.get('basis'))
        references(attempt.get('asset_ids'), assets, 'Returned image assets')
        cost = attempt.get('cost')
        require(cost is None or number(cost) and cost >= 0, 'Reported image cost must be nonnegative or unknown.')
    checks = records(project['checks'], 'Checks')
    for check in checks.values():
        require(scene is not None and text(check.get('kind')) and sha(check.get('scene_digest')) and check.get('status') in
                ('passed', 'failed', 'incomplete') and type(check.get('blocking')) is bool,
                'Checks need a scene identity, status, and blocking decision.')
        input_basis(check.get('basis'))
    approval = project['approval']
    if approval is not None:
        require(isinstance(approval, dict) and type(approval.get('revision')) is int
                and approval.get('revision') == project['revision']
                and approval.get('owner') == project['owner'] and scene is not None,
                'Approval belongs to an exact scene revision and workspace owner.')
        require(approval.get('basis') == basis(project) and approval.get('scene_digest') == digest(scene),
                'Approval does not match the current inputs and scene.')
        require(REQUIRED_CHECKS.issubset({c['kind'] for c in checks.values()})
                and all(c['basis'] == basis(project) and c['scene_digest'] == digest(scene)
                and c['status'] == 'passed' for c in checks.values()
                if c['blocking'] or c['kind'] in REQUIRED_CHECKS),
                'Resolve blocking or incomplete checks before final approval.')
        require(not stories[selected].get('omissions'), 'Required omissions block final approval.')
    for export in records(project['exports'], 'Exports').values():
        require(type(export.get('revision')) is int and 0 <= export['revision'] <= project['revision'],
                'Exports belong to a recorded revision.')
        input_basis(export.get('basis'))
        require(isinstance(export.get('files'), list) and bool(export['files']), 'Exports need an immutable file list.')
        for file in export['files']:
            require(isinstance(file, dict) and relative_path(file.get('file')) and sha(file.get('sha256')),
                    'Export files need safe paths and immutable hashes.')
    return project
