"""The person's final build approval, without delivery or runner execution."""
import copy
import hashlib
import json
from pathlib import Path

import home
from workspace import WorkspaceError
from runner import decks, desk, gitstate
from runner.steps import build, existing, words
from runner.desk_migration import materials
from studio_core import presentation_migration, research_contract


def requirements(root, record, engine=None):
    from runner.desk_chat import _files
    files = _files(root)
    try:
        materials(record, files)
        state = json.loads(files[str(build.STATE)])
        if not isinstance(state, dict) or not isinstance(state.get('audit'), dict) \
                or state.get('asked') or state.get('repair') or state.get('rewhole') \
                or record.get('halted') or record.get('question') or desk.opened(record) \
                or record.get('desk_jobs') or (record.get('desk') or {}).get('edits'):
            raise ValueError('Complete the checked drawing and any pending work before marking it ready.')
        audit = state['audit']
        if not isinstance(audit.get('status'), str) or not isinstance(audit.get('messages'), list) \
                or any(not isinstance(line, str) for line in audit['messages']) \
                or any(type(audit.get(key)) is not int or audit[key] < 0 for key in ('errors', 'warnings')):
            raise ValueError('The saved native brand check is incomplete.')
        deck = state.get('deck')
        if not presentation_migration.relative(deck) or deck not in files \
                or not files[deck].startswith(b'PK\x03\x04'):
            raise ValueError('The checked native deck is missing. Complete its drawing first.')
        if desk.selected(record):
            if existing.PLAN not in files or existing.PATCH not in files:
                raise ValueError('The checked Selected changes plan and copy are required.')
            digest = state.get('deckSha256')
        else:
            given = words.given(root)
            current = desk._outline(root)
            if [(s.get('id'), desk.words_of(s)) for s in build.slides_of(given)] \
                    != [(s.get('id'), desk.words_of(s)) for s in build.slides_of(current)]:
                raise ValueError('The current slide words differ from the checked drawing.')
            contract = files.get(str(build.CONTRACT))
            if contract is None or hashlib.sha256(contract).hexdigest() != (state.get('start') or {}).get('contract'):
                raise ValueError('The pinned brand contract differs from the checked drawing.')
            last = desk.last_round(state)
            digest = last.get('deck')
            if not last.get('file') or last['file'] not in files \
                    or hashlib.sha256(files[last['file']]).hexdigest() != digest \
                    or build.to_draw(root):
                raise ValueError('The current complete drawing and its checked preview are required.')
        if digest != hashlib.sha256(files[deck]).hexdigest():
            raise ValueError('The native deck changed since it was checked. Complete its drawing again.')
        if record.get('form', {}).get('research'):
            research_contract.read_bundle(Path(root) / 'research')
        design = files.get('work/.harness-slides/design/session.json')
        if design:
            session = json.loads(design)
            if not isinstance(session, dict) or session.get('schema') != 1 \
                    or session.get('tool') != 'harness-slides-design':
                raise ValueError('The saved companion design format cannot be verified.')
            status = engine.slides().design_status(Path(root) / 'work') if engine is not None else None
            if status is not None and (status.get('question') or status.get('buildAllowed') is not True):
                raise ValueError('Resolve the saved companion design decision before marking ready.')
        if decks.delivered(root) is not None:
            raise ValueError('This deck is already delivered. Change it explicitly before marking a new draft ready.')
        return {'operation': 'ready', 'seen': {'revision': desk.revision(record),
            'expected': desk.on_screen(root, record, state), 'blockers_seen': desk.blockers_seen(state)},
            'blockers': desk.blockers(state), 'reviewed': desk.reviewed(state),
            'response': 'The person’s explicit approval of this deck and the listed brand blockers.',
            'consequences': 'Mark ready records your approval. Nothing is delivered or uploaded.'}
    except (KeyError, ValueError, TypeError, OSError) as error:
        raise WorkspaceError(str(error)) from None


def evidence(root, record):
    from runner.desk_chat import _files
    files = _files(root)
    kept = copy.deepcopy(record)
    for name in ('conversation_ready', 'conversation_decisions'):
        kept.pop(name, None)
    kept.get('gates', {}).pop('gate:build', None)
    inputs = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()
              if name not in ('run.json', presentation_migration.RECORD)}
    return hashlib.sha256(json.dumps({'record': kept, 'inputs': inputs}, sort_keys=True).encode()).hexdigest()


def status(root, record):
    if not decks.in_conversation(record):
        return {'ready': False, 'can_mark_ready': False, 'ready_problem': None}
    try:
        requirements(root, record)
        decision = record.get('conversation_ready') or {}
        gate = record.get('gates', {}).get('gate:build') or {}
        current = (isinstance(decision, dict) and all(isinstance(decision.get(key), str)
                   and decision[key].strip() for key in ('by', 'at', 'response'))
                   and gate.get('state') == 'approved' and gate.get('by') == decision['by']
                   and decision.get('evidence') == evidence(root, record))
        return {'ready': current, 'can_mark_ready': not current, 'ready_problem': None}
    except (WorkspaceError, ValueError, OSError):
        return {'ready': False, 'can_mark_ready': False,
                'ready_problem': 'Complete the checked deck and its required inputs before marking ready.'}


def ready(engine, path, request):
    from runner import desk_chat
    if not isinstance(request, dict) or set(request) != {'expected_basis', 'seen', 'response'} \
            or not isinstance(request['response'], str) or not request['response'].strip() \
            or len(request['response']) > 4000:
        raise WorkspaceError('Supply expected_basis, seen and the person’s explicit response.')
    by = gitstate.identity(engine.space().repo)
    with desk_chat._prepared(engine, path, 'ready', change=True) as prepared:
        space, root, stage, record, before, context = prepared
        if request['expected_basis'] != context['expected_basis'] \
                or request['seen'] != context['requirements']['seen']:
            raise WorkspaceError(desk_chat.CHANGED)
        previous = copy.deepcopy(record.get('gates', {}).get('gate:build'))
        gate = previous or {}
        at = home.now()
        record.setdefault('gates', {})['gate:build'] = {**gate, 'state': 'approved',
            'by': by, 'at': at, 'note': request['response'].strip(), 'round': int(gate.get('round') or 1)}
        record.setdefault('conversation_decisions', []).append({**request, 'target': 'ready',
            'by': by, 'at': at, 'previous_decision': previous})
        record['conversation_ready'] = {'at': at, 'by': by, 'response': request['response'].strip(),
                                         'evidence': evidence(stage, record)}
        decks.write_run(stage, record)
        desk_chat._publish(engine, space, root, stage, before)
    return engine.view(root)
