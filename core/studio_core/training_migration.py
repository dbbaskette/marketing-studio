"""Pure Training Studio paired migration validation for domain readers and replay."""
import hashlib
import json
import re
from pathlib import PurePosixPath

SESSION = '.training-studio/session.json'
RUN = '.training-studio/run.json'
DESK_SESSION = '.training-studio/desk/session.json'
DESK_RUN = '.training-studio/desk/run.json'
ORIGIN = '.training-studio/desk/migration-origin.json'
PENDING = 'work/desk/migration-transaction.json'
KINDS = ('text', 'outline', 'research', 'drawing', 'part')
WRITES = (ORIGIN, DESK_SESSION, DESK_RUN)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def relative(name):
    return isinstance(name, str) and bool(name) and not PurePosixPath(name).is_absolute() \
        and all(part not in ('', '.', '..') for part in name.split('/')) and '\\' not in name


def owner(value):
    return value is None or isinstance(value, dict) and all(
        isinstance(value.get(key), str) and value[key] for key in ('computer', 'name', 'since'))


def session_supported(value):
    if not isinstance(value, dict) or type(value.get('schema')) is not int or value['schema'] != 1:
        return False
    shape = {'id': str, 'title': str, 'levels': list, 'sizing': dict, 'stage': str,
             'settings': dict, 'unavailable': dict, 'pins': dict, 'artifacts': dict,
             'exports': dict, 'decisions': list, 'events': list}
    if any(not isinstance(value.get(key), kind) for key, kind in shape.items()) \
            or not value['id'] or not value['title'] or value['stage'] not in (
            'intake', 'research-plan', 'research', 'blueprint', 'document', 'brief', 'deck',
            'scenario', 'yoodli', 'package', 'done'):
        return False
    levels = value['levels']
    settings = value['settings']
    if (any(level not in ('101', '201', '301', '401') for level in levels) or len(set(levels)) != len(levels) \
            or any(key not in settings for key in ('deck_target', 'brand', 'brief_kind', 'stages')) \
            or settings['deck_target'] not in (None, 'pptx', 'google') \
            or settings['brief_kind'] not in ('product', 'competitive') \
            or settings['brand'] is not None and not isinstance(settings['brand'], str) \
            or not isinstance(settings['stages'], list) or any(
                stage not in ('document', 'brief', 'deck', 'scenario', 'yoodli') for stage in settings['stages']) \
            or settings.get('approval', 'chat') not in ('chat', 'page')
            or not isinstance(settings.get('copies', []), list)
            or any(kind not in ('google', 'word') for kind in settings.get('copies', []))
            or type(settings.get('walkthrough', False)) is not bool
            or settings.get('delivery', 'reading') not in ('reading', 'live')
            or not isinstance(value.get('requests', []), list)
            or any(not isinstance(request, dict) for request in value.get('requests', []))):
        return False
    if any(not isinstance(pin, dict) or any(not isinstance(pin.get(key), str) or not pin[key] for key in ('task', 'runtime')) for pin in value['pins'].values()):
        return False
    for entry in value['artifacts'].values():
        if not isinstance(entry, dict) or not relative(entry.get('file')) \
                or not isinstance(entry.get('built_from'), dict) \
                or re.fullmatch(r'[a-f0-9]{64}', str(entry.get('sha256'))) is None:
            return False
        approved = entry.get('approved')
        if approved is not None and (not isinstance(approved, dict) or approved.get('by') not in
                ('page', 'chat', 'review-policy', 'desk') or not isinstance(approved.get('inputs'), dict)
                or not isinstance(approved.get('at'), str) or re.fullmatch(r'[a-f0-9]{64}', str(approved.get('sha256'))) is None):
            return False
    if not isinstance(value.get('pending_local_decks', {}), dict):
        return False
    return all(isinstance(item, dict) for item in value['events'] + value['decisions'])


def run_supported(value):
    if not isinstance(value, dict) or type(value.get('schema')) is not int or value['schema'] not in (1, 2, 3, 4):
        return False
    if not isinstance(value.get('agent'), str) or not value['agent'] or any(
            not isinstance(value.get(key), dict) for key in ('steps', 'limits', 'answers', 'copies', 'deck')) \
            or any(not isinstance(step, dict) or not isinstance(step.get('attempts', []), list)
                   or any(not isinstance(item, dict) for item in step.get('attempts', [])) for step in value['steps'].values()) \
            or not owner(value.get('driver')) or value.get('halt') not in (None, 'paused', 'stopped'):
        return False
    for key in ('problem', 'question'):
        item = value.get(key)
        if item is not None and (not isinstance(item, dict) or not isinstance(item.get('what' if key == 'problem' else 'text'), str)):
            return False
    drafts = value.get('drafts', {})
    if not isinstance(drafts, dict) or not owner(drafts.get('finished_by')) \
            or not isinstance(drafts.get('jobs', []), list) \
            or not isinstance(drafts.get('updates', {}), dict) or not isinstance(drafts.get('update_chain', {}), dict):
        return False
    for job in drafts.get('jobs', []):
        if not isinstance(job, dict) or job.get('status') not in ('queued', 'working', 'ready', 'done', 'stopped', 'failed', 'cancelled'):
            return False
    for item in value['deck'].values():
        if not isinstance(item, dict) or not isinstance(item.get('notes', []), list) or any(
                not isinstance(note, dict) or note.get('status') not in ('waiting', 'drawing', 'done', 'stopped', 'failed', 'cancelled') for note in item.get('notes', [])):
            return False
    if value['schema'] == 2:
        policy = value.get('review_policy')
        if not isinstance(policy, dict) or type(policy.get('schema')) is not int or policy['schema'] != 1 \
                or policy.get('level') not in ('balanced', 'automatic', 'step_by_step'):
            return False
    if value['schema'] in (3, 4):
        contract = value.get('research_contract')
        if not (value['schema'] == 4 and value.get('flow') == 'desk' and value.get('execution') == 'conversation') \
                and (not isinstance(contract, dict) or type(contract.get('schema')) is not int or contract['schema'] != 2):
            return False
    return value.get('execution', 'runner') in ('runner', 'conversation')


def originals(session_bytes, run_bytes, ident=None):
    if any(not isinstance(data, bytes) or len(data) > 1_000_000 for data in (session_bytes, run_bytes)):
        raise ValueError('The original Training Studio records cannot be verified.')
    session, run = json.loads(session_bytes), json.loads(run_bytes)
    if not session_supported(session) or not run_supported(run) or ident is not None and session['id'] != ident:
        raise ValueError('The original Training Studio saved format is unsupported. Keep using its saved flow.')
    return session, run


def receipt(session_bytes, run_bytes, ident, expected, required):
    return {'schema': 1, 'product': 'Training Studio', 'id': ident,
            'session_basis': digest(session_bytes), 'run_basis': digest(run_bytes),
            'expected': expected, 'required': required}



def shared_material(name, data):
    if not isinstance(data, bytes) or len(data) > 1_000_000:
        raise ValueError('A required shared Training Studio input is missing or too large.')
    if name.endswith('blueprint.md'):
        text = data.decode('utf-8')
        if not re.search(r'^### O[1-9]\d*\b', text, re.M) or not re.search(r'^## M[1-9]\d*\b', text, re.M):
            raise ValueError('The shared saved teaching plan cannot be read.')
    elif name.endswith('deck/outline.json'):
        value = json.loads(data)
        slides = value.get('slides') if isinstance(value, dict) else None
        if not isinstance(slides, list) or not slides or any(not isinstance(slide, dict)
                or not isinstance(slide.get('id'), str) or not slide['id']
                or not isinstance(slide.get('title'), str) or not isinstance(slide.get('notes', ''), str)
                or not isinstance(slide.get('points', []), list) or any(not isinstance(point, dict)
                    or not isinstance(point.get('text', ''), str) for point in slide.get('points', [])) for slide in slides):
            raise ValueError('The shared saved deck outline cannot be read losslessly.')
        if len({slide['id'] for slide in slides}) != len(slides):
            raise ValueError('The saved outline repeats slide identifiers.')
    elif name not in (SESSION, RUN):
        raise ValueError('The shared Training Studio dependency is unsupported.')


def validated(origin, session, run, session_bytes, run_bytes, ident=None):
    raw_session, raw_run = originals(session_bytes, run_bytes, ident)
    if not isinstance(origin, dict) or type(origin.get('schema')) is not int or origin['schema'] != 1 \
            or origin.get('product') != 'Training Studio' or origin.get('id') != raw_session['id'] \
            or origin.get('session_basis') != digest(session_bytes) or origin.get('run_basis') != digest(run_bytes) \
            or re.fullmatch(r'tm1\.[A-Za-z0-9_-]{43}', str(origin.get('expected'))) is None:
        raise ValueError('The Training Studio migration receipt is missing or changed.')
    required = origin.get('required')
    if not isinstance(required, list) or not required or len(required) > 10000 \
            or any(not relative(name) for name in required) or len(set(required)) != len(required) \
            or not {SESSION, RUN} <= set(required) or not any(name.endswith('blueprint.md') for name in required) \
            or any(name not in (SESSION, RUN, 'blueprint.md', 'deck/outline.json') and re.fullmatch(r'(101|201|301|401)/(blueprint\.md|deck/outline\.json)', name) is None for name in required):
        raise ValueError('The Training Studio saved dependency list is unsupported.')
    if any(not isinstance(value, dict) or set(value) != {'origin', 'record'} or value['origin'] != origin for value in (session, run)):
        raise ValueError('The Training Studio migration pair is missing or mismatched.')
    effective_session, effective_run = session['record'], run['record']
    if not session_supported(effective_session) or not run_supported(effective_run) \
            or effective_session['schema'] != raw_session['schema'] or effective_session['id'] != raw_session['id'] \
            or effective_session['levels'] != raw_session['levels'] or effective_run['schema'] != raw_run['schema'] \
            or effective_session.get('flow') != 'desk' or effective_run.get('flow') != 'desk' \
            or effective_run.get('execution') not in ('conversation', 'runner') \
            or effective_run.get('unfinished_migration') is not True \
            or type(effective_run.get('migration_scope_released', False)) is not bool:
        raise ValueError('The Training Studio effective records are unsupported.')
    scope = effective_run.get('conversation_scope')
    if not isinstance(scope, list) or not scope or any(kind not in KINDS for kind in scope) or len(set(scope)) != len(scope):
        raise ValueError('The Training Studio conversation scope cannot be verified.')
    targets = effective_run.get('migration_targets')
    if not isinstance(targets, list) or not targets or any(not isinstance(name, str) or name not in effective_session['artifacts'] and not name.startswith('deck@') and name != 'deck' for name in targets):
        raise ValueError('The Training Studio retained target scope cannot be verified.')
    return effective_session, effective_run
