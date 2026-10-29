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


def update_chain_supported(value):
    return isinstance(value, dict) and (not value or (
        re.fullmatch(r'[a-f0-9]{24}', str(value.get('id'))) is not None
        and 'level' in value and value['level'] in (None, '101', '201', '301', '401')
        and value.get('status') in ('working', 'done', 'stopped')
        and isinstance(value.get('blocked', []), list)
        and all(isinstance(name, str) and name for name in value.get('blocked', []))))


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
            or not isinstance(drafts.get('updates', {}), dict) or not update_chain_supported(drafts.get('update_chain', {})):
        return False
    if not isinstance(value.get('delivered_restore', {}), dict) or any(
            re.fullmatch(r'[a-f0-9]{64}', str(digest)) is None for digest in value.get('delivered_restore', {}).values()):
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


def material_files(session):
    names = {'intake': 'intake.md', 'research-plan': '.training-studio/research-plan.json',
             'research': '.harness-research/research-report.md'}
    for level in session['levels'] or [None]:
        prefix, suffix = (level + '/', '@' + level) if level else ('', '')
        for kind, file in (('blueprint', 'blueprint.md'), ('document', 'document.md'),
                           ('brief', session['settings']['brief_kind'] + '-brief.md'),
                           ('deck', 'deck-link.md' if session['settings']['deck_target'] == 'google' else 'deck.pptx')):
            names[kind + suffix] = prefix + file
    for name, entry in session['artifacts'].items():
        if name.startswith(('scenario:', 'yoodli:')):
            if not re.fullmatch(r'(?:(?:101|201|301|401)/)?(?:scenario\.md|scenarios/[a-z0-9-]+\.md|yoodli/[a-z0-9-]+\.md)', entry['file']):
                raise ValueError('The saved practice material path is unsupported.')
            names[name] = entry['file']
    return names


def declared_inputs(session, targets):
    """Fixed native saved material closure; settings/practice are intrinsic inputs."""
    names, required, visited, profile = material_files(session), {SESSION, RUN}, set(), False
    def visit(name):
        nonlocal profile
        if name in visited:
            return
        if name not in names or name not in session['artifacts']:
            raise ValueError('A declared saved Training Studio input has no native material record.')
        visited.add(name)
        required.add(names[name])
        if name == 'research':
            required.add('research-report.md')
            if session.get('research_contract'):
                required.update('research/' + file for file in ('output.json', 'facts.json', 'report.md', 'brief.md', 'evidence.md'))
            else:
                required.add('.harness-research/research.json')
        for key, value in session['artifacts'][name]['built_from'].items():
            if key in names:
                visit(key)
            elif key == 'profile':
                if re.fullmatch(r'[a-f0-9]{64}', str(value)) is None:
                    raise ValueError('The declared Yoodli profile basis cannot be verified.')
                profile = True
            elif key == 'practice':
                visit('blueprint' + ('@' + name.partition('@')[2] if '@' in name else ''))
            elif key not in ('setting:deck_target', 'setting:brand', 'setting:brief_kind'):
                raise ValueError('A declared saved Training Studio input is unsupported.')
    for name in targets:
        visit(name)
    return required, profile


def receipt(session_bytes, run_bytes, ident, expected, required, targets, sources=False):
    session, _ = originals(session_bytes, run_bytes, ident)
    declared, profile = declared_inputs(session, targets)
    return {'schema': 1, 'product': 'Training Studio', 'id': ident,
            'session_basis': digest(session_bytes), 'run_basis': digest(run_bytes),
            'expected': expected, 'required': sorted(declared | set(required)), 'targets': targets,
            'local': {'sources': sources, 'profile': profile, 'google_decks': True}}


def input_limit(name):
    return 64_000_000 if name.endswith('.pptx') else 8_000_000 if name.startswith('research/') else 1_000_000



def shared_material(name, data):
    if not isinstance(data, bytes) or len(data) > input_limit(name):
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
    elif name == '.harness-research/research.json':
        value = json.loads(data)
        if not isinstance(value, dict) or type(value.get('schema')) is not int or value['schema'] != 1 \
                or value.get('owner') != 'harness-research' or not isinstance(value.get('items'), list) \
                or not isinstance(value.get('results'), dict):
            raise ValueError('The saved research record cannot be interpreted.')
    elif name == '.training-studio/research-plan.json':
        value = json.loads(data)
        if not isinstance(value, dict) or not isinstance(value.get('topic'), str) or not isinstance(value.get('items'), list) \
                or any(not isinstance(item, dict) or not isinstance(item.get('id'), str) or not isinstance(item.get('question'), str) for item in value['items']):
            raise ValueError('The saved research plan cannot be interpreted.')
    elif name.endswith('.pptx'):
        if not data.startswith(b'PK\x03\x04'):
            raise ValueError('The retained PowerPoint deck cannot be read.')
    elif name in ('research/output.json', 'research/facts.json'):
        value = json.loads(data)
        if not isinstance(value, dict) or type(value.get('schema')) is not int or value['schema'] != 2 \
                or value.get('owner') != 'harness-research-synthesis' or not isinstance(value.get('digest'), str) \
                or not value['digest'] or value.get('status') != 'complete':
            raise ValueError('The saved research bundle cannot be interpreted.')
        if name.endswith('facts.json') and (not isinstance(value.get('sources', []), list)
                or any(not isinstance(source, dict) for source in value.get('sources', []))):
            raise ValueError('The saved research source captures cannot be interpreted.')
    elif name not in (SESSION, RUN):
        if not data.decode('utf-8').strip():
            raise ValueError('A retained Training Studio text input is empty.')


def shared_inputs(origin, read, session=None):
    """Pure native common-input validation for both local readers and shared replay."""
    source, cached, size = read, {}, 0
    def read(name):
        nonlocal size
        if name not in cached:
            data = source(name)
            if not isinstance(data, bytes):
                raise ValueError('A required shared Training Studio input is missing.')
            size += len(data)
            if len(data) > input_limit(name) or size > 256 * 1024 * 1024 or len(cached) >= 10000:
                raise ValueError('The saved Training Studio dependency scope is too large.')
            cached[name] = data
        return cached[name]
    required = set(origin['required'])
    if session is not None:
        required.update(declared_inputs(session, [name for name in origin['targets'] if name in session['artifacts']])[0])
    for name in sorted(required):
        shared_material(name, read(name))
    if 'research/output.json' in required:
        manifest = json.loads(read('research/output.json'))
        entries, names = manifest.get('artifacts'), set()
        if not isinstance(entries, list) or len(entries) > 10000:
            raise ValueError('The research bundle has no supported file manifest.')
        for entry in entries:
            if not isinstance(entry, dict) or not relative(entry.get('file')) or entry['file'] in names \
                    or entry['file'].startswith(('work/', '.')) or re.fullmatch(r'[a-f0-9]{64}', str(entry.get('sha256'))) is None:
                raise ValueError('The research bundle has an unsupported file manifest.')
            names.add(entry['file'])
            data = read('research/' + entry['file'])
            if not isinstance(data, bytes) or len(data) > 8_000_000 or digest(data) != entry['sha256']:
                raise ValueError('Research evidence or output changed. Revise and review it again.')
        if not {'report.md', 'brief.md', 'evidence.md', 'facts.json'} <= names:
            raise ValueError('The research bundle is incomplete.')
        facts = json.loads(read('research/facts.json'))
        review = facts.get('review')
        if any(facts.get(key) != manifest.get(key) for key in ('owner', 'schema', 'digest', 'status')) \
                or manifest.get('status') != 'complete' or not isinstance(review, dict) \
                or review.get('digest') != manifest.get('digest') or review.get('accepted') is not True:
            raise ValueError('The saved research bundle needs its completed independent review.')
        for source in facts.get('sources', []):
            for key in ('snapshot', 'original_snapshot'):
                name = source.get(key)
                if name and (not isinstance(name, str) or not name.startswith('research/') or name[9:] not in names):
                    raise ValueError('The bundle is missing a pinned source capture.')
    return set(cached)


def local_sources(read):
    """Supplied originals/readable copies are explicitly private, never replay inputs."""
    index = json.loads(read('sources/supplied/index.json'))
    if not isinstance(index, dict) or type(index.get('schema')) is not int or index['schema'] != 1 \
            or not isinstance(index.get('documents'), list) or len(index['documents']) > 40:
        raise ValueError('The saved private source index cannot be read.')
    seen = set()
    for entry in index['documents']:
        if not isinstance(entry, dict) or re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', str(entry.get('id'))) is None \
                or entry['id'] in seen or not isinstance(entry.get('name'), str) or type(entry.get('readable')) is not bool:
            raise ValueError('A saved private source record cannot be read.')
        seen.add(entry['id'])
        suffix = PurePosixPath(entry['name']).suffix.lower()
        if suffix not in ('.txt', '.md', '.html', '.htm', '.docx', '.pdf'):
            raise ValueError('The private source format is unsupported.')
        data = read('sources/supplied/' + entry['id'] + '.original' + suffix)
        if not isinstance(data, bytes) or len(data) > 8_000_000 or re.fullmatch(r'[a-f0-9]{64}', str(entry.get('sha256'))) is None or digest(data) != entry['sha256']:
            raise ValueError('A required original private source changed or is missing.')
        if entry['readable']:
            text = read('sources/supplied/' + entry['id'] + '.txt')
            if not isinstance(text, bytes) or len(text) > 8_000_000 or not text.decode().strip():
                raise ValueError('A required private readable source is missing.')


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
            or not {SESSION, RUN} <= set(required) or not any(name.endswith('blueprint.md') for name in required):
        raise ValueError('The Training Studio saved dependency list is unsupported.')
    targets, local = origin.get('targets'), origin.get('local')
    if not isinstance(targets, list) or not targets or len(targets) > 10000 or any(not isinstance(name, str) for name in targets) or len(set(targets)) != len(targets):
        raise ValueError('The original retained Training Studio targets are unsupported.')
    declared, profile = declared_inputs(raw_session, targets)
    allowed_outlines = {(level + '/' if level else '') + 'deck/outline.json' for level in raw_session['levels'] or [None]}
    outlines = set(required) & allowed_outlines
    if set(required) != declared | outlines or not isinstance(local, dict) or set(local) != {'sources', 'profile', 'google_decks'} \
            or any(type(value) is not bool for value in local.values()) or local['profile'] != profile \
            or local['google_decks'] is not True or raw_run.get('documents') and not local['sources']:
        raise ValueError('The saved shared/private Training Studio dependency proof is incomplete.')
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
