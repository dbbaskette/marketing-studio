"""Pure Presentation Studio record checks shared by its reader and replay guard."""
import hashlib
import json
import re
from pathlib import PurePosixPath

RECORD = 'desk/migration.json'
ORIGIN = 'desk/migration-origin.json'
PENDING = 'work/desk/migration-transaction.json'
KINDS = ('text', 'outline', 'research', 'drawing', 'part')


def supported(record):
    if not isinstance(record, dict) or type(record.get('schema')) is not int \
            or record['schema'] not in (1, 2, 3):
        return False
    if any(not isinstance(record.get(key), str) or not record[key].strip()
           for key in ('id', 'title', 'created', 'agent')):
        return False
    form = record.get('form')
    if not isinstance(form, dict) or record.get('route') not in ('scratch', 'document', 'existing') \
            or form.get('route') != record['route'] or not isinstance(form.get('title'), str) \
            or form.get('output') not in ('pptx', 'google'):
        return False
    if record['route'] in ('document', 'existing'):
        source = form.get('source')
        if not isinstance(source, dict) or source.get('kind') not in ('upload', 'paste', 'google') \
                or (record['route'] == 'existing' and source['kind'] == 'paste'):
            return False
        key = {'upload': 'name', 'google': 'link'}.get(source['kind'])
        if key and (not isinstance(source.get(key), str) or not source[key]):
            return False
    if record['route'] == 'existing' and form.get('level') not in ('brand-only', 'polish', 'redesign', 'rework', 'selected'):
        return False
    if any(not isinstance(record.get(key), dict) for key in ('steps', 'gates', 'limits')) \
            or not isinstance(record.get('revisions'), list):
        return False
    if any(not isinstance(value, dict) for value in record['steps'].values()) \
            or any(not isinstance(value, dict) or value.get('state') not in
                   ('absent', 'waiting', 'approved', 'changes') for value in record['gates'].values()):
        return False
    driver = record.get('driver')
    if driver is not None and (not isinstance(driver, dict) or any(
            not isinstance(driver.get(key), str) or not driver[key]
            for key in ('computer', 'name', 'since'))):
        return False
    if record['schema'] == 2:
        policy = record.get('review_policy')
        if not isinstance(policy, dict) or policy.get('schema') != 1 \
                or policy.get('level') not in ('balanced', 'automatic', 'step_by_step'):
            return False
    if record['schema'] == 3 and (not isinstance(record.get('research_contract'), dict)
                                 or record['research_contract'].get('schema') != 2):
        return False
    return True


def relative(name):
    return isinstance(name, str) and bool(name) and not PurePosixPath(name).is_absolute() \
        and all(part not in ('', '.', '..') for part in name.split('/')) and '\\' not in name


def receipt(value):
    return {key: value[key] for key in ('schema', 'product', 'id', 'original', 'expected')}


def shared_material(name, data):
    if not isinstance(data, bytes) or len(data) > 1_000_000:
        raise ValueError('A required shared Presentation Studio record cannot be read.')
    value = json.loads(data)
    if name == 'run.json':
        if not supported(value):
            raise ValueError('The original Presentation Studio record is unsupported.')
    elif name == 'outline.json':
        slides = value.get('slides') if isinstance(value, dict) else None
        if not isinstance(value, dict) or value.get('version') != 1 \
                or value.get('delivery') not in ('live', 'reading') or not isinstance(slides, list) or not slides:
            raise ValueError('The shared saved outline cannot be read.')
        ids = []
        for slide in slides:
            if not isinstance(slide, dict) or not isinstance(slide.get('id'), str) \
                    or not re.fullmatch(r'[A-Za-z0-9_-]+', slide['id']) \
                    or slide.get('kind') not in ('cover', 'section', 'content', 'closing') \
                    or any(not isinstance(slide.get(key), str) for key in ('title', 'notes')):
                raise ValueError('The shared outline has an unsupported slide.')
            ids.append(slide['id'])
            points = slide.get('points') or []
            if not isinstance(points, list) or any(not isinstance(point, dict) or any(
                    not isinstance(point.get(key, ''), str) for key in ('label', 'text')) for point in points):
                raise ValueError('The shared slide points cannot be read losslessly.')
        if len(set(ids)) != len(ids):
            raise ValueError('The shared outline repeats a slide identifier.')
    elif name == 'classify.json':
        slides = value.get('slides') if isinstance(value, dict) else None
        if not isinstance(slides, list) or not slides or any(
                not isinstance(slide, dict) or type(slide.get('number')) is not int
                or not isinstance(slide.get('objects'), list) for slide in slides):
            raise ValueError('The shared saved inventory cannot be read.')
    return value


def validated(value, original, ident=None, origin=None):
    """Return the effective record, or refuse; never reinterpret a broken overlay."""
    if not isinstance(original, bytes) or len(original) > 1_000_000:
        raise ValueError('The original Presentation Studio record cannot be verified.')
    raw = json.loads(original)
    if not supported(raw) or not isinstance(value, dict) or type(value.get('schema')) is not int or value['schema'] != 1 \
            or value.get('product') != 'Presentation Studio' \
            or value.get('original') != hashlib.sha256(original).hexdigest() \
            or value.get('id') != raw['id'] or (ident is not None and value['id'] != ident) \
            or re.fullmatch(r'pm1\.[A-Za-z0-9_-]{43}', str(value.get('expected'))) is None:
        raise ValueError('The Presentation Studio desk record does not match its original.')
    if origin != receipt(value):
        raise ValueError('The Presentation Studio migration receipt is missing or changed.')
    effective = value.get('record')
    if not supported(effective) or effective['id'] != raw['id'] \
            or effective['schema'] != raw['schema'] or effective['route'] != raw['route'] \
            or effective['form'].get('level') != raw['form'].get('level') \
            or effective.get('flow') != 'desk' or effective.get('execution') not in ('conversation', 'runner'):
        raise ValueError('The Presentation Studio desk record uses an unsupported format.')
    scope = effective.get('conversation_scope')
    if not isinstance(scope, list) or not scope or len(scope) > len(KINDS) \
            or any(kind not in KINDS for kind in scope) or len(set(scope)) != len(scope):
        raise ValueError('The Presentation Studio desk scope cannot be verified.')
    required = value.get('required')
    if not isinstance(required, list) or len(required) > 10000 \
            or not required or len(set(required)) != len(required) \
            or any(name not in ('run.json', 'classify.json', 'outline.json') for name in required) \
            or 'run.json' not in required:
        raise ValueError('The Presentation Studio saved dependencies cannot be verified.')
    expected = {'run.json'} | ({'classify.json'} if raw['route'] == 'existing' else set()) \
        | (set() if raw['route'] == 'existing' and raw['form'].get('level') == 'selected' else {'outline.json'})
    if set(required) != expected:
        raise ValueError('The Presentation Studio saved dependency set is incomplete.')
    return effective
