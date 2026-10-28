"""Checked conversation operations on Training Studio's native desk records.

Check supplied materials in disposable copies, then recheck ownership and inputs
under the shared workspace lock before publishing a bounded domain write set.
"""
from contextlib import contextmanager
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import threading
import zlib

import home
import workspace
from workspace import WorkspaceError
from runner import deck_edit, drafts, gitstate, pipeline, settings, team, worker_tools
from studio_core import research_contract, research_sites
from studio_core.sync_guard import SYNC_WAIT, worker_in_progress

KINDS = ('text', 'outline', 'research', 'drawing', 'part')
CHANGED = 'The training or its inputs changed. Read desk context again before saving.'
MAX_BYTES, MAX_FILES = 256 * 1024 * 1024, 10000


def scope_of(value):
    if not isinstance(value, list) or not value or len(value) > 20 or any(
            not isinstance(kind, str) or kind not in KINDS for kind in value):
        raise WorkspaceError('Supply an explicit scope list: text, outline, research, drawing, part.')
    return [kind for kind in KINDS if kind in value]


def create(engine, form, uploads=None):
    if not isinstance(form, dict):
        raise WorkspaceError('Supply a JSON object for desk creation.')
    if uploads is not None and (not isinstance(uploads, dict) or len(uploads) > 40 or
            any(not isinstance(name, str) or not isinstance(data, bytes) for name, data in uploads.items()) or
            sum(map(len, uploads.values())) > 64_000_000):
        raise WorkspaceError('Supply a bounded map of named local source bytes.')
    return engine.start(form, execution='conversation', scope=scope_of(form.get('scope')), uploads=uploads)


def _start(engine, form, scope, uploads=None):
    scope = scope_of(scope)
    # No assistant/capability check, guidance fetch, worker, network claim or settings write.
    checked = pipeline.check_form({**form, 'flow': 'desk'}, conversation=True)
    if uploads and not checked['research_from']['documents']:
        raise WorkspaceError('Explicitly select supplied documents in the research source scope before adding them.')
    space, chosen = engine.space(), settings.load()
    gitstate.identity(space.repo)
    with gitstate.workspace_locked(space, engine.files, configured=True):
        if worker_in_progress(space.repo, refusal=WorkspaceError):
            raise WorkspaceError(SYNC_WAIT)
        root = pipeline.create(space, checked)
        try:
            from runner.engine import new_record
            record = new_record(checked['agent'] or chosen.agent, checked['model'] or chosen.model,
                                chosen, checked['source_scope'], checked['effort'] or chosen.effort,
                                checked['research_from'])
            for name, data in (uploads or {}).items():
                entry = engine.documents.add(root, name, data)
                if not entry.get('readable'):
                    raise WorkspaceError('A supplied source could not be read. Supply a readable local export.')
            record.pop('review_policy', None)
            record.pop('review_layout', None)
            record.update(schema=drafts.SCHEMA, flow='desk', execution='conversation',
                          conversation_scope=scope, conversation_materials=checked['materials'],
                          research_questions=checked['research_questions'], driver=team.claim(space),
                          drafts={'jobs': [], 'updates': {}, 'findings_before': None})
            engine._store(root, record)
            gitstate.commit(space, checked['title'] + ': start requested work in conversation', [root])
        except BaseException:
            shutil.rmtree(root, ignore_errors=True)
            home.forget(root)
            gitstate.discard(space, root)
            raise
    return {'path': str(root), 'id': root.name, 'execution': 'conversation', 'scope': scope}


def _files(root, proposals=True):
    if root.is_symlink():
        raise WorkspaceError('Conversation inputs cannot traverse linked folders.')
    files, size = {}, 0
    def unreadable(error):
        raise WorkspaceError('The training could not be read completely.') from error
    for folder, directories, names in os.walk(root, followlinks=False, onerror=unreadable):
        for name in [*directories, *names]:
            if (Path(folder) / name).is_symlink():
                raise WorkspaceError('Conversation inputs cannot traverse linked files or folders.')
        for name in names:
            file = Path(folder) / name
            details = file.stat()
            if not stat.S_ISREG(details.st_mode):
                raise WorkspaceError('Conversation inputs must be ordinary files.')
            size += details.st_size
            if size > MAX_BYTES or len(files) >= MAX_FILES:
                raise WorkspaceError('This training is too large for a bounded conversation save.')
            files[file.relative_to(root).as_posix()] = file.read_bytes()
    if proposals:
        storage = deck_edit.storage(root) / 'proposals'
        if storage.parent.is_symlink() or storage.parent.parent.is_symlink():
            raise WorkspaceError('Conversation proposals cannot traverse linked folders.')
        if storage.exists():
            files.update({'@proposals/' + name: data for name, data in _files(storage, False).items()})
        if sum(map(len, files.values())) > MAX_BYTES or len(files) > MAX_FILES:
            raise WorkspaceError('This training is too large for a bounded conversation save.')
    return files


def _path(root, name):
    return deck_edit.storage(root) / 'proposals' / name.removeprefix('@proposals/') if name.startswith('@proposals/') else root / name


def _root(engine, path, change=False, owner=True):
    root = engine.driven(path)
    if root is None:
        raise WorkspaceError('There is no training there.')
    record = engine._load(root)
    if not drafts.on_desk(record):
        raise WorkspaceError('This saved training needs its saved-work or migration path before conversation edits.')
    if worker_in_progress(engine.space().repo, refusal=WorkspaceError):
        raise WorkspaceError(SYNC_WAIT)
    if change:
        engine.hold(root, conversation=True)
        if owner and not drafts.in_conversation(record):
            raise WorkspaceError('This training is owned by the runner. Explicitly take it into conversation first.')
        run = engine._run(root)
        if run.busy or run.queued or run.workers or root in engine.pending_commit or any(
                job.get('status') in ('queued', 'working') for job in record.get('drafts', {}).get('jobs', [])) \
                or drafts.updates(record) or any(
                    item.get('redrawing') or item.get('look_pending') or
                    any(note.get('status') in ('waiting', 'drawing') for note in item.get('notes', []))
                    for item in record.get('deck', {}).values()):
            raise WorkspaceError(SYNC_WAIT)
    return root, record


def _canonical(value, stage, root):
    if isinstance(value, str):
        return value.replace(str(stage), str(root))
    if isinstance(value, dict):
        return {key: _canonical(item, stage, root) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_canonical(item, stage, root) for item in value]
    return value


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _staged_engine(engine):
    """Native domain methods over scratch state; publication alone touches the repository."""
    staged = copy.copy(engine)
    staged.files = threading.RLock()
    staged._lock = threading.RLock()
    staged._runs, staged.pending_commit, staged._preparing_decks = {}, {}, {}
    for name in ('_ready', '_models', '_listing', '_clash', '_as_of'):
        if isinstance(getattr(staged, name, None), dict):
            setattr(staged, name, dict(getattr(staged, name)))
    staged._active_steps = set()
    staged._local_decks_only = True
    staged._held = lambda path: Path(path)
    staged.driven = lambda path: Path(path)
    staged.hold = lambda *args, **kwargs: None
    staged._commit = lambda *args, **kwargs: None
    staged._commit_slide_words = lambda *args, **kwargs: None
    staged._edited = lambda *args, **kwargs: None
    staged.carry_on = lambda *args, **kwargs: None
    staged.wake = lambda *args, **kwargs: None
    staged.share_soon = lambda *args, **kwargs: None
    staged._how = lambda root, found, level: {
        'renderer': 'local', 'lock': str(root / 'work' / 'render.lock'),
        'kept': str(root / 'work' / 'local-render.json'), 'named': {'name': found.session['title']}}
    return staged


def _target(root, target):
    if target in ('scope', 'handoff', 'ownership'):
        return None, target, None
    if not isinstance(target, str) or len(target) > 200:
        raise WorkspaceError('Choose a current Training Studio material target.')
    name, separator, part = target.partition('/')
    base, level = workspace.split(name)
    session = workspace.load(root)
    if base in ('look', 'design'):
        name = workspace.qualify('deck', level)
    elif base == 'deck-outline':
        name = workspace.qualify('deck', level)
    spec = workspace.artifact(root, session, name)
    # Scenario IDs must be requested by the actual practice plan or already exist.
    names = workspace.artifact_names(root, session)
    for at, planned in pipeline.practice(root, session).items():
        names += [workspace.qualify('scenario:' + ident, at) for ident in planned]
        if 'yoodli' in session['settings']['stages']:
            names += [workspace.qualify('yoodli:' + ident, at) for ident in planned]
    if name not in names or (spec['stage'] in workspace.SKIPPABLE and
                            spec['stage'] not in session['settings']['stages']):
        raise WorkspaceError('This material was not requested for this training and level.')
    if base in ('look', 'design'):
        pending = list((deck_edit.storage(root) / 'proposals').glob('*/request.json'))
        kind = 'part' if base == 'design' and any(home.read_json(file, {}).get('level') == level for file in pending) else 'drawing'
    elif separator:
        kind = 'part'
    elif base in ('blueprint', 'deck-outline'):
        kind = 'outline'
    elif base == 'research':
        kind = 'research'
    elif base == 'deck':
        kind = 'drawing'
    elif base in ('research-plan', 'document', 'brief') or base.partition(':')[0] in ('scenario', 'yoodli'):
        kind = 'text'
    else:
        raise WorkspaceError('Choose a supported material target.')
    return kind, name, part if separator else None


def _step(found, name, outline=False):
    listed = pipeline.steps(found.session['levels'], pipeline.wanted(found.session), found.practice,
                            deck=bool(found.decks))
    return next((step for step in listed if step.artifact == name and step.kind == 'agent'
                 and (not outline or pipeline.bare(step.id) == 'deck-outline')), None)


def _prepare(engine, root, record, target):
    kind, name, part = _target(root, target)
    if kind is None:
        return {'allowed_scope': list(KINDS), 'existing_scope': record.get('conversation_scope'),
                'optional_selection_fields': ['materials', 'deck_target', 'brand', 'yoodli'] if target == 'scope' else []}
    session = workspace.load(root)
    base, level = workspace.split(target.partition('/')[0])
    if base in ('look', 'design'):
        return _answer_context(engine, root, record, base, level)
    spec = workspace.artifact(root, session, name)
    requirements = {'kind': kind, 'envelope': ['kind', 'target', 'expected_basis', 'payload'],
                    'material': name, 'dependencies': list(spec['upstream'])}
    if part:
        if workspace.split(name)[0] == 'deck':
            slide, separator, field = part.partition('/')
            if not separator:
                raise WorkspaceError('Name deck@LEVEL/slide-id/field.')
            outline = home.read_json(pipeline.place(root, level, pipeline.OUTLINE), {})
            drafts.slide_words(outline, slide, field, 'Checked replacement')
            return {**requirements, 'payload': {'text': 'Replacement words'},
                    'seen': (engine._decided(record, level).get('saved') or {}).get('sha256')}
        card = engine.draft_card(root, name)
        known = {'opening', *(section['id'] for section in card['sections'] if not section.get('locked'))}
        if part not in known:
            raise WorkspaceError('Choose an editable part ID from desk show.')
        return {**requirements, 'revision': card['revision'], 'payload': {'text': 'Replacement text'}}
    if kind == 'research':
        return {**requirements, 'source_scope': pipeline.research_of(record),
                'payload': {'case': 'Absolute local complete reviewed Harness Research case'}}
    found = engine._survey(root, record)
    step = _step(found, name, base == 'deck-outline')
    if kind == 'drawing' or base == 'deck-outline':
        _brand(engine, root, level)
        record = engine._load(root)
        found = engine._survey(root, record)
        step = _step(found, name, base == 'deck-outline')
    if kind == 'drawing':
        return _drawing_context(engine, root, record, level, requirements)
    if step is None:
        raise WorkspaceError('This material has no supported checked submission path.')
    designed = bool(engine._designed(found.decks[level], session)) if base == 'deck-outline' else False
    sources = engine.documents.sources(root) if name == 'research-plan' and record.get('documents') else None
    work = pipeline.work(root, found, step, None, None, [], synthesis=True, designed=designed, sources=sources)
    requirements['designed'] = designed
    return {**requirements, 'spec': work.prepared['artifacts'][work.name],
            'inputs': work.prepared.get('inputs', {}), 'guidance': work.guidance,
            'payload': {'outline': 'Complete outline JSON'} if base == 'deck-outline' else
                       {'plan': 'Research plan JSON'} if name == 'research-plan' else {'text': 'Complete material text'}}


@contextmanager
def _scratch(name):
    with tempfile.TemporaryDirectory(prefix='training-conversation-') as temporary:
        stage = Path(temporary) / name
        stage.mkdir()
        try:
            yield stage
        finally:
            shutil.rmtree(deck_edit.storage(stage), ignore_errors=True)


def _material_input(root, name, part):
    session = workspace.load(root)
    file = workspace.artifact(root, session, name)['file']
    path = root / file
    if not path.is_file():
        return None
    if workspace.split(name)[0] != 'deck':
        return path.read_text()
    outline = home.read_json(pipeline.place(root, workspace.split(name)[1], pipeline.OUTLINE), {})
    material = {'file': file, 'sha256': workspace.sha256_file(path), 'outline': outline,
                'metadata': session['artifacts'].get(name)}
    if part:
        slide, _, field = part.partition('/')
        _, text = drafts.slide_words(outline, slide, field, 'Checked replacement')
        material['selected'] = {'slide': slide, 'field': field, 'text': text}
    return material


@contextmanager
def _prepared(engine, path, target, change=False, owner=True):
    space = engine.space()
    with gitstate.workspace_locked(space, engine.files, configured=True):
        root, record = _root(engine, path, change, owner)
        scope = scope_of(record['conversation_scope']) if 'conversation_scope' in record else None
        kind, name, part = _target(root, target)
        if kind and scope is not None and kind not in scope:
            raise WorkspaceError('This target exceeds the requested conversation scope.')
        before = _files(root)
        if change and workspace.split(target)[0] != 'design' and any(
                name.startswith('@proposals/') and name.endswith('/request.json') for name in before):
            raise WorkspaceError('Answer or cancel the current design-bound word proposal before another change.')
    with _scratch(root.name) as stage:
        for relative, data in before.items():
            file = _path(stage, relative)
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(data)
        # Rebase operational metadata only, preserving original sources/material bytes.
        for file in stage.rglob('*.json'):
            relative = file.relative_to(stage).as_posix()
            if '/work/' in '/' + relative or relative == drafts.RECORD:
                try:
                    value = json.loads(file.read_bytes())
                    rebased = _canonical(value, root, stage)
                    if rebased != value:
                        file.write_text(json.dumps(rebased, indent=2) + '\n')
                except (ValueError, UnicodeError):
                    pass
        for request in (deck_edit.storage(stage) / 'proposals').glob('*/request.json'):
            if workspace.split(target)[0] != 'design':
                continue
            value = json.loads(request.read_bytes())
            canonical_basis = {name: hashlib.sha256(data).hexdigest() for name, data in before.items()
                               if not name.startswith('@proposals/')}
            if value.get('basis') != canonical_basis:
                raise WorkspaceError('The proposed words changed. Read the material and propose them again.')
            if value.get('root') != str(root) or value.get('approval', {}).get('token') != request.parent.name:
                raise WorkspaceError('The proposed words do not belong to this training.')
            deck_edit.proposal_folder(root, request.parent.name)
            value = _canonical(value, root, stage)
            value['basis'] = {str(name): digest.hex() for name, digest in deck_edit.PreparedEdit.files(stage).items()}
            request.write_text(json.dumps(value) + '\n')
        staged = _staged_engine(engine)
        current = staged._load(stage)
        staged._local_deck_approvals = {name: copy.deepcopy(entry.get('approved'))
                                        for name, entry in workspace.load(stage)['artifacts'].items()}
        requirements = _canonical(_prepare(staged, stage, current, target), stage, root)
        # Exported contracts for absent decks are new inputs too, not just saved bytes.
        contracts = {file.relative_to(stage).as_posix(): _canonical(file.read_text(), stage, root)
                     for file in stage.rglob('brand-contract.json')}
        requirements['brand_contracts'] = contracts
        if workspace.split(target.partition('/')[0])[0] == 'look':
            requirements['questionId'] = _digest(requirements)
        context = {'target': target, 'scope': scope, 'requirements': requirements,
                   'inputs': {'intake': pipeline.answers(stage), 'session': workspace.load(stage),
                              'sources': staged.documents.sources(stage)[1],
                              'material': _material_input(stage, name, part) if kind else None}}
        context['expected_basis'] = _digest({'files': {relative: hashlib.sha256(data).hexdigest()
                                           for relative, data in before.items()}, 'target': target,
                                           'scope': scope, 'requirements': requirements})
        with gitstate.workspace_locked(space, engine.files, configured=True):
            _root(engine, root, change, owner)
            if _files(root) != before:
                raise WorkspaceError(CHANGED)
        yield space, root, stage, staged, before, context


def context(engine, path, target):
    with _prepared(engine, path, target) as prepared:
        return prepared[-1]


def show(engine, path):
    with _prepared(engine, path, 'ownership') as prepared:
        _, root, stage, staged, _, context = prepared
        session = workspace.load(stage)
        cards = {}
        for name in workspace.artifact_names(stage, session):
            if workspace.split(name)[0].partition(':')[0] in drafts.CODECS and (
                    stage / workspace.artifact(stage, session, name)['file']).is_file():
                cards[name] = staged.draft_card(stage, name)
        return {'path': str(root), 'id': root.name, 'execution': staged._load(stage).get('execution', 'runner'),
                'scope': context['scope'], 'session': session, 'cards': _canonical(cards, stage, root),
                'materials': workspace.person_statuses(stage, session),
                'local_decks': {name: {'file': workspace.artifact(stage, session, name)['file'], **marker}
                                for name, marker in session.get('pending_local_decks', {}).items()},
                'outlines': {level or '': home.read_json(pipeline.place(stage, level, pipeline.OUTLINE), None)
                             for level in session['levels'] or [None]},
                'provenance': staged._load(stage).get('conversation_submissions', [])}


def _publish(engine, space, root, stage, before, owner=True):
    after = _files(stage)
    # Canonicalize metadata paths; never rewrite input or material text.
    for name, data in list(after.items()):
        if ('/work/' in '/' + name or name == drafts.RECORD or name.startswith('@proposals/')) and name.endswith('.json'):
            try:
                value = json.loads(data)
                canonical = _canonical(value, stage, root)
                if canonical != value:
                    after[name] = (json.dumps(canonical, indent=2) + '\n').encode()
            except (ValueError, UnicodeError):
                pass
    for name, data in list(after.items()):
        if name.startswith('@proposals/') and name.endswith('/request.json') and name not in before:
            value = json.loads(data)
            value['basis'] = {relative: hashlib.sha256(content).hexdigest()
                              for relative, content in after.items() if not relative.startswith('@proposals/')}
            after[name] = (json.dumps(value, indent=2) + '\n').encode()
    changed = {name for name in before.keys() | after.keys() if before.get(name) != after.get(name)}
    allowed = {'.training-studio', '.harness-research', '.studio-research', 'research', 'sources',
               'work', 'deck', 'scenarios', 'yoodli', 'reviews', 'history', '@proposals'}
    material_files = {workspace.artifact(stage, workspace.load(stage), name)['file']
                      for name in workspace.artifact_names(stage, workspace.load(stage))}
    for name in changed:
        pieces = name.split('/')
        prefix = pieces[1] if pieces[0] in workspace.LEVELS and len(pieces) > 1 else pieces[0]
        if name not in material_files and prefix not in allowed and name not in ('research-report.md',):
            raise WorkspaceError('A checker attempted to change an unsupported training file.')
    with gitstate.workspace_locked(space, engine.files, configured=True):
        _root(engine, root, True, owner)
        if _files(root) != before:
            raise WorkspaceError(CHANGED)
        try:
            for name in sorted(changed):
                if name in after:
                    workspace.write_atomic(_path(root, name), after[name])
                else:
                    _path(root, name).unlink(missing_ok=True)
            gitstate.commit(space, workspace.load(root)['title'] + ': keep checked conversation work', [root])
        except BaseException:
            for name in changed:
                if name in before:
                    workspace.write_atomic(_path(root, name), before[name])
                else:
                    _path(root, name).unlink(missing_ok=True)
            raise


def _checked(result):
    if result[0]:
        raise WorkspaceError('The material cannot be saved. ' + ' '.join(map(str, result[0])))
    return result


def _text(engine, root, record, target, payload, requirements):
    kind, name, part = _target(root, target)
    if part:
        if set(payload) != {'text'} or not isinstance(payload['text'], str):
            raise WorkspaceError('A part takes replacement text only.')
        if workspace.split(name)[0] == 'deck':
            slide, _, field = part.partition('/')
            return engine.slide_words(root, workspace.split(name)[1], slide, field, payload['text'], requirements['seen'])
        return engine.draft_save(root, name, part, requirements['revision'], payload['text'])
    spec = requirements['spec']
    if name == 'research-plan':
        if set(payload) != {'plan'} or not isinstance(payload['plan'], dict):
            raise WorkspaceError('Submit plan only.')
        result = worker_tools.check_research_plan(payload['plan'], most=worker_tools.PLAN_MOST)
        if result['problems'] or payload['plan'].get('scope') != spec['scope']:
            raise WorkspaceError('The research plan failed its checks or exceeds its pinned source scope.')
        if (spec['scope'] == 'supplied-only' and any(item.get('public_query') for item in payload['plan'].get('items', []))) or payload['plan'].get('sources', []) != spec.get('sources', []):
            raise WorkspaceError('Keep the pinned supplied sources and allowed research queries.')
        text, checks, warnings = json.dumps(payload['plan']), [], []
    else:
        if set(payload) != {'text'} or not isinstance(payload['text'], str):
            raise WorkspaceError('Submit complete text only.')
        base = workspace.split(name)[0].partition(':')[0]
        checker = getattr(worker_tools, 'check_' + base)
        _, checks, warnings, text = _checked(checker(payload['text'], spec))
    found = engine._survey(root, record)
    step = _step(found, name)
    with tempfile.TemporaryDirectory(prefix='training-text-check-') as temporary:
        file = Path(temporary) / 'material'
        file.write_text(text)
        handed = {'artifacts': {name: {'path': file, 'text': text, 'checks': checks, 'warnings': warnings}}, 'review': None}
        missing = ('research',) if workspace.split(name)[0] == 'blueprint' and workspace.inputs(root, workspace.load(root), name).get('research') is None else ()
        pipeline.keep_draft(root, step, handed, None, found, unprovided=missing)
    # A focused plan can be useful before optional upstream research exists. Never
    # invent that research or mark an unfulfilled dependency accepted.
    session = workspace.load(root)
    state = workspace.statuses(root, session)
    if all(state.get(upstream) in ('approved', 'skipped') for upstream in workspace.artifact(root, session, name)['upstream']):
        workspace.accept_desk(root, name)
    if workspace.split(name)[0].startswith('scenario:'):
        record = engine._load(root)
        if name not in record['drafted']:
            record['drafted'].append(name)
            engine._store(root, record)
    engine._ready_again(root)


def _previous_decisions(before):
    """Keep genuine prior facts as history when a checked change advances the material."""
    session = json.loads(before[f'{workspace.STATE_DIR}/session.json'])
    record = json.loads(before[drafts.RECORD])
    return {'materials': {name: {key: copy.deepcopy(entry[key]) for key in ('built_from', 'approved') if key in entry}
                          for name, entry in session['artifacts'].items()},
            'decks': {level: {key: copy.deepcopy(entry[key]) for key in ('approved', 'look', 'saved') if key in entry}
                      for level, entry in record.get('deck', {}).items()}}


def submit(engine, path, request):
    if not isinstance(request, dict) or set(request) != {'kind', 'target', 'expected_basis', 'payload'} \
            or not isinstance(request['payload'], dict):
        raise WorkspaceError('Submit kind, target, expected_basis and payload together.')
    if len(json.dumps(request['payload'])) > 2_000_000:
        raise WorkspaceError('The submission is too large.')
    with _prepared(engine, path, request['target'], True) as prepared:
        space, root, stage, staged, before, context = prepared
        kind, name, part = _target(stage, request['target'])
        if request['kind'] not in KINDS or kind != request['kind'] or workspace.split(request['target'])[0] in ('look', 'design'):
            raise WorkspaceError('The submission kind does not match its target; use desk answer for explicit answers.')
        if request['expected_basis'] != context['expected_basis']:
            raise WorkspaceError(CHANGED)
        record = staged._load(stage)
        requirements = _canonical(context['requirements'], root, stage)
        result = None
        if part or kind == 'text' or (kind == 'outline' and workspace.split(name)[0] == 'blueprint'):
            result = _text(staged, stage, record, request['target'], request['payload'], requirements)
        elif kind == 'outline':
            with staged.files:
                _outline(staged, stage, record, request['target'], request['payload'], requirements)
        elif kind == 'research':
            _research(staged, stage, record, request['payload'])
        else:
            _drawing(staged, stage, record, request['target'], request['payload'])
        record = staged._load(stage)
        record.setdefault('conversation_submissions', []).append({
            'kind': kind, 'target': request['target'], 'basis': request['expected_basis'],
            'scope': context['scope'], 'at': home.now(), 'by': 'conversation',
            'previous_decisions': _previous_decisions(before)})
        staged._store(stage, record)
        _publish(engine, space, root, stage, before)
    shown = show(engine, root)
    if result is not None and isinstance(result, dict) and result.get('approval'):
        shown['approval'] = result['approval']
    return shown


def save(engine, path, request):
    return submit(engine, path, request)


def set_scope(engine, path, expected_basis, scope, **selection):
    return _ownership(engine, path, 'scope', expected_basis, scope, selection)


def take(engine, path, expected_basis, scope):
    return _ownership(engine, path, 'ownership', expected_basis, scope)


def handoff(engine, path, expected_basis, scope):
    result = _ownership(engine, path, 'handoff', expected_basis, scope)
    engine.wake(Path(path))
    return result


def _ownership(engine, path, target, expected_basis, scope, selection=None):
    scope = scope_of(scope)
    with _prepared(engine, path, target, True, target != 'ownership') as prepared:
        space, root, stage, staged, before, context = prepared
        if expected_basis != context['expected_basis']:
            raise WorkspaceError(CHANGED)
        record = staged._load(stage)
        if target != 'scope' and context['scope'] is not None and scope != context['scope']:
            raise WorkspaceError('Keep the current requested scope; change scope separately.')
        if selection:
            if target != 'scope':
                raise WorkspaceError('Only scope changes select requested materials.')
            drafts.select_materials(stage, record, selection)
            record['conversation_materials'] = [kind for kind in pipeline.MATERIALS
                                                if kind in workspace.load(stage)['settings']['stages']]
        if target == 'handoff':
            _handoff_check(staged, stage, record, scope)
            record['execution'] = 'runner'
        elif target == 'ownership':
            record['execution'] = 'conversation'
        record['conversation_scope'] = scope
        record.setdefault('conversation_ownership' if target != 'scope' else 'conversation_scope_changes', []).append({
            'operation': target, 'basis': expected_basis, 'scope': scope, 'at': home.now(), 'by': 'person-request',
            **({'selection': selection} if selection else {})})
        staged._store(stage, record)
        _publish(engine, space, root, stage, before, target != 'ownership')
    return show(engine, root)


def _brand(engine, root, level):
    built = pipeline.read_built(root, level)
    if built.get('brand'):
        engine._skill().check(pipeline.contract(root, engine._survey(root, engine._load(root)).decks[level]))
        return
    session = workspace.load(root)
    chosen = pipeline.brand_of(session)
    if not chosen:
        raise WorkspaceError('Choose a brand explicitly before checking a slide outline.')
    work = pipeline.place(root, level, pipeline.WORK)
    folder, told = work / 'brand-conversation', work / 'told-conversation'
    tool = engine.slides()
    made = engine._skill().export(folder, *chosen, delivery=pipeline.delivery_of(session))
    contract = Path(made['contract'])
    told.mkdir(parents=True, exist_ok=True)
    worker_tools._write(told / 'outline-contract.txt', tool.outline_contract(contract))
    worker_tools._write(told / 'compose-contract.txt', tool.compose_contract(contract))
    home.write_json(told / 'layouts.json', tool.layouts(contract))
    for name, text in tool.reading(contract).items():
        worker_tools._write(told / pipeline.reading_file(name), text)
    engine._note(root, level, brand={'brand': chosen[0], 'variant': chosen[1],
        'folder': folder.name, 'told': told.name, 'contract': contract.relative_to(work).as_posix(),
        'sha256': workspace.sha256_file(contract), 'changed': None, 'guidance': {}})


def _outline(engine, root, record, target, payload, requirements):
    if set(payload) != {'outline'} or not isinstance(payload['outline'], dict):
        raise WorkspaceError('Submit complete outline JSON only.')
    level = workspace.split(target)[1]
    with tempfile.TemporaryDirectory(prefix='training-outline-check-') as temporary:
        _, checks, warnings, text = _checked(worker_tools.check_outline(
            json.dumps(payload['outline']), requirements['spec'], engine.slides(), Path(temporary)))
        file = Path(temporary) / 'outline.json'
        file.write_text(text)
        found = engine._survey(root, engine._load(root))
        previous = home.read_json(pipeline.place(root, level, pipeline.OUTLINE), {})
        for slide in previous.get('slides', []):
            drafts.keep_slide(engine, root, level, slide['id'], 'outline')
        kept = pipeline.keep_outline(root, found, level, {'artifacts': {'outline': {
            'path': file, 'text': text, 'checks': checks, 'warnings': warnings}}, 'review': None}, None, designed=requirements.get('designed', False))
        record = engine._load(root)
        engine._decided(record, level).update(outline=kept, waiting=None)
        engine._store(root, record)
        if requirements.get('designed'):
            engine._propose(root, level, pipeline.contract(root, engine._survey(root, record).decks[level]))
    engine._ready_again(root)


def _research(engine, root, record, payload):
    if set(payload) != {'case'} or not isinstance(payload['case'], str) or not Path(payload['case']).is_absolute():
        raise WorkspaceError('Research takes an absolute local reviewed case folder.')
    case = Path(payload['case'])
    _files(case, False)
    facts, _ = research_contract.read_bundle(case / 'research')
    chosen = pipeline.research_of(record)
    supplied = engine.documents.sources(root)[1]
    for source in facts.get('sources', []):
        if source.get('permission') == 'selected':
            if not chosen['documents'] or not source.get('file') or research_contract.inside(case, source['file']).read_text() not in {item['text'] for item in supplied}:
                raise WorkspaceError('The research includes a supplied source outside this training’s pinned inputs.')
        elif source.get('permission') != 'public':
            raise WorkspaceError('The research includes an unknown source permission.')
        if source.get('permission') == 'public' and not chosen['web'] and not research_sites.under(
                source.get('origin'), chosen['sites']):
            raise WorkspaceError('The research exceeds the pinned source scope.')
    research_contract.adopt_case(case, root)
    _, manifest = research_contract.publish(root / research_contract.CASE, root / 'research')
    session = workspace.load(root)
    # Imported contract identifies actual checked bundle format, never an invented runtime.
    session['research_contract'] = {'schema': 2, 'imported': True}
    workspace.store(root, session)
    workspace.write_atomic(root / pipeline.REPORT, (root / 'research/report.md').read_bytes())
    workspace.save(root, 'research', built=True)
    workspace.accept_desk(root, 'research')
    record = engine._load(root)
    record['research'] = {'digest': manifest['digest'], 'reviewed': True, 'imported': True}
    engine._store(root, record)


def _drawing_context(engine, root, record, level, requirements):
    found = engine._survey(root, record)
    mine = found.decks[level]
    if not mine.outline:
        raise WorkspaceError('Submit the checked slide outline first.')
    kept = engine._decided(record, level)
    if not pipeline.looked(kept, workspace.sha256_file(pipeline.place(root, level, pipeline.OUTLINE))):
        raise WorkspaceError('Answer the current look question explicitly before drawing.')
    if mine.designed:
        status = engine.slides().design_status(pipeline.design_project(root, level))
        if not status.get('buildAllowed'):
            raise WorkspaceError('Answer the actual companion design question before drawing.')
        checked = engine.slides().design_check(pipeline.design_project(root, level))
        design = {'sha256': workspace.sha256_file(pipeline.place(root, level, pipeline.DESIGN)),
                  'revision': checked['revision']}
    else:
        design = None
    # Continuation is checked execution evidence, never a person approval.
    kept['approved'] = {**kept['outline'], 'design': design, 'by': 'desk', 'decision': drafts.DECISION}
    engine._store(root, record)
    found = engine._survey(root, record)
    step = next(step for step in found.steps if pipeline.bare(step.id) == 'deck-start' and workspace.split(step.artifact)[1] == level)
    if not mine.start or mine.start.get('outline') != kept['outline']['sha256']:
        engine._split(root, engine._run(root), found, pipeline.Next('code', step))
    built = pipeline.read_built(root, level)
    if built.get('start'):
        old = pipeline.place(root, level, pipeline.WORK) / built['start']['folder']
        stable = old.parent / 'start-conversation'
        if old != stable:
            old.rename(stable)
            for file in stable.rglob('*.json'):
                file.write_text(file.read_text().replace(str(old), str(stable)))
            built = _canonical(built, old, stable)
            for section in (built.get('sections') or {}).values():
                if section.get('start') == old.name:
                    section['start'] = stable.name
                if (section.get('file') or '').startswith(old.name + '/'):
                    section['file'] = stable.name + section['file'][len(old.name):]
            built['start']['folder'] = stable.name
            pipeline.write_built(root, level, built)
    record = engine._load(root)
    if record.get('problem'):
        raise WorkspaceError(record['problem']['what'])
    found = engine._survey(root, record)
    step = next(step for step in found.steps if pipeline.bare(step.id) == 'deck-sections' and workspace.split(step.artifact)[1] == level)
    mine = found.decks[level]
    sections = {item['id']: pipeline.section_work(root, found, step, item['id'], None,
                         engine._how(root, found, level)).prepared
                for item in mine.start['sections'] if item['id'] not in (mine.built.get('sections') or {})}
    return {**requirements, 'sections': sections, 'payload': {'sections': 'Exactly the requested section IDs'}}


def _drawing(engine, root, record, target, payload):
    if set(payload) != {'sections'} or not isinstance(payload['sections'], dict):
        raise WorkspaceError('Supply checked section compositions only.')
    level = workspace.split(target)[1]
    found = engine._survey(root, engine._load(root))
    mine = found.decks[level]
    wanted = {item['id'] for item in mine.start['sections']} - set(mine.built.get('sections') or {})
    if set(payload['sections']) != wanted:
        raise WorkspaceError('Supply exactly the requested drawing section IDs.')
    step = next(step for step in found.steps if pipeline.bare(step.id) == 'deck-sections' and workspace.split(step.artifact)[1] == level)
    drawn = dict(mine.built.get('sections') or {})
    for ident in sorted(wanted):
        spec = pipeline.section_work(root, found, step, ident, None, engine._how(root, found, level)).prepared
        with tempfile.TemporaryDirectory(prefix='training-section-check-') as temporary:
            folder = Path(temporary)
            worker_tools.prepare(folder, **spec)
            tools = worker_tools.WorkerTools(folder)
            text = json.dumps(payload['sections'][ident])
            for operation in (tools.preview_section, tools.submit_section):
                result = operation(text)
                if not result[0]:
                    raise WorkspaceError(str(result[1]))
            handed = worker_tools.collect(folder)
            draft = handed['artifacts']['section']
            work = pipeline.place(root, level, pipeline.WORK)
            target_file = work / mine.start['folder'] / ('conversation-' + ident + '.json')
            workspace.write_atomic(target_file, Path(draft['path']).read_bytes())
            drawn[ident] = {'start': mine.start['folder'], 'round': len(mine.rounds),
                            'previews': handed['shown']['previews'],
                            'pictures': [slide['number'] for slide in handed['shown']['slides']],
                            'file': target_file.relative_to(work).as_posix(),
                            'sha256': workspace.sha256_file(target_file), 'checks': draft['checks'],
                            'warnings': draft['warnings'], 'at': home.now()}
    engine._note(root, level, sections=drawn)
    found = engine._survey(root, engine._load(root))
    step = next(step for step in found.steps if pipeline.bare(step.id) == 'deck-whole' and workspace.split(step.artifact)[1] == level)
    engine._whole(root, engine._run(root), found, pipeline.Next('code', step))
    record = engine._load(root)
    if record.get('problem'):
        raise WorkspaceError(record['problem']['what'])
    found = engine._survey(root, record)
    step = next(step for step in found.steps if pipeline.bare(step.id) == 'deck-save' and workspace.split(step.artifact)[1] == level)
    engine._keep(root, engine._run(root), found, pipeline.Next('code', step))
    record = engine._load(root)
    if record.get('problem'):
        raise WorkspaceError(record['problem']['what'])
    session = workspace.load(root)
    file = root / workspace.artifact(root, session, mine.name)['file']
    saved = engine._decided(record, level).get('saved') or {}
    last = engine._survey(root, record).decks[level].last
    if (not file.is_file() or saved.get('sha256') != workspace.sha256_file(file)
            or not last or last.get('stale') or saved.get('deck') != last['deck']
            or saved.get('round') != last['folder']):
        raise WorkspaceError('The checked drawing was not saved. Read its current context and try again.')
    engine._ready_again(root)


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


def _answer_context(engine, root, record, target, level):
    _brand(engine, root, level)
    record = engine._load(root)
    found = engine._survey(root, record)
    mine = found.decks[level]
    if not mine.outline:
        raise WorkspaceError('Submit the checked slide outline before answering its design.')
    if target == 'look':
        if pipeline.looked(engine._decided(record, level), workspace.sha256_file(pipeline.place(root, level, pipeline.OUTLINE))):
            raise WorkspaceError('The look question was already answered.')
        step = next(step for step in found.steps if pipeline.bare(step.id) == 'deck-look' and workspace.split(step.artifact)[1] == level)
        engine._looks(root, engine._run(root), found, pipeline.Next('code', step))
        shown = pipeline.read_built(root, level).get('look') or {}
        previews, size = [], 0
        if len(shown.get('looks') or []) > 12:
            raise WorkspaceError('The brand offered too many look samples.')
        for item in shown.get('looks') or []:
            file = pipeline.place(root, level, pipeline.WORK) / shown['folder'] / f"{item['number']}.png"
            data = file.read_bytes()
            size += len(data)
            if size > 4_000_000:
                raise WorkspaceError('The look previews exceed the bounded PNG input limit.')
            previews.append({**item, 'preview': base64.b64encode(_preview_png(data)).decode()})
        return {'operation': 'answer', 'question': 'Choose this deck’s look.', 'offered': previews,
                'default': shown.get('default'), 'failed': bool(shown.get('failed')),
                'answer': ['questionId', 'choice', 'response']}
    proposals = list((deck_edit.storage(root) / 'proposals').glob('*/request.json'))
    proposals = [file for file in proposals if home.read_json(file, {}).get('level') == level]
    if len(proposals) > 1:
        raise WorkspaceError('More than one proposed word change is waiting. Settle it on its saved desk first.')
    if proposals:
        requested = home.read_json(proposals[0], {})
        project = proposals[0].parent / 'project'
        token, seen = proposals[0].parent.name, requested['seen']
    else:
        project, token, seen = pipeline.design_project(root, level), None, None
        if not project.exists() and mine.designed:
            engine._propose(root, level, pipeline.contract(root, mine))
    status = engine.slides().design_status(project)
    question = status.get('question')
    if not isinstance(question, dict) or not question.get('id') or not status.get('revision'):
        raise WorkspaceError('No current companion design question is waiting.')
    return {'operation': 'answer', 'question': question, 'revision': status['revision'],
            'token': token, 'seen': seen, 'answer': ['questionId', 'planRevision', 'decision', 'feedback']}


def answer(engine, path, request):
    if not isinstance(request, dict) or set(request) != {'target', 'expected_basis', 'answer'} \
            or not isinstance(request['answer'], dict):
        raise WorkspaceError('Supply target, expected_basis and the person’s answer.')
    target, reply = request['target'], request['answer']
    base, level = workspace.split(target)
    if base not in ('look', 'design'):
        raise WorkspaceError('Choose a current look or design answer target.')
    with _prepared(engine, path, target, True) as prepared:
        space, root, stage, staged, before, context = prepared
        if request['expected_basis'] != context['expected_basis']:
            raise WorkspaceError(CHANGED)
        requirements = context['requirements']
        if base == 'look':
            if set(reply) != {'questionId', 'choice', 'response'} or reply['questionId'] != requirements['questionId'] \
                    or not isinstance(reply['response'], str) or not reply['response'].strip() or len(reply['response']) > 4000:
                raise WorkspaceError('Supply the current look question and the person’s actual choice and response.')
            shown = pipeline.read_built(stage, level).get('look') or {}
            choice = reply['choice']
            if choice == 'default':
                choice = pipeline.DEFAULT_LOOK if shown.get('failed') or shown.get('unavailable') else shown.get('default')
            if choice != pipeline.DEFAULT_LOOK and choice not in {item['id'] for item in requirements['offered']}:
                raise WorkspaceError('Choose an actual offered look or explicitly choose default.')
            record = staged._load(stage)
            previous = (staged._decided(record, level).get('look') or {}).get('chosen')
            if previous:
                staged._decided(record, level).setdefault('look_history', []).append(previous)
                staged._store(stage, record)
            if not staged._choose_look(stage, level, choice, reply['response'], 'conversation-person'):
                raise WorkspaceError(CHANGED)
        else:
            if set(reply) != {'questionId', 'planRevision', 'decision', 'feedback'} \
                    or reply['questionId'] != requirements['question']['id'] or reply['planRevision'] != requirements['revision'] \
                    or not isinstance(reply['feedback'], str) or not reply['feedback'].strip() or len(reply['feedback']) > 4000:
                raise WorkspaceError('Answer the current design question and revision with the person’s actual response.')
            if requirements['token']:
                staged.slide_words_decide(stage, requirements['token'], reply['decision'], requirements['seen'],
                    question=reply['questionId'], revision=reply['planRevision'], response=reply['feedback'])
            else:
                staged.slides().design_respond(pipeline.design_project(stage, level), reply)
        record = staged._load(stage)
        record.setdefault('conversation_answers', []).append({'target': target, 'basis': request['expected_basis'],
                'answer': reply, 'at': home.now(), 'by': 'person-request', 'scope': context['scope'],
                'previous_decisions': _previous_decisions(before)})
        staged._store(stage, record)
        _publish(engine, space, root, stage, before)
    return show(engine, root)


def _handoff_check(engine, root, record, scope):
    session = workspace.load(root)
    if session['settings']['copies'] or session['settings']['deck_target'] == 'google':
        raise WorkspaceError('Handoff would request copies. Continue the focused work in conversation.')
    found = engine._survey(root, record)
    mapping = {'blueprint': 'outline', 'deck-outline': 'outline', 'research-plan': 'text',
               'research-start': 'research', 'research': 'research', 'research-report': 'research',
               'document': 'text', 'brief': 'text', 'scenario': 'text', 'yoodli': 'text'}
    # Check actual native completion/dependencies, including reopened/held materials,
    # rather than trusting old done flags or changing any real approval facts.
    effective = pipeline.steps(session['levels'], pipeline.wanted(session), found.practice,
                               deck=bool(found.decks), synthesis=bool(record.get('research_contract')))
    for step in effective:
        if step.kind == 'gate' or step.stage in ('intake', 'package') or step.id.startswith('copies:'):
            continue
        if step.id not in found.done and mapping.get(pipeline.bare(step.id), 'drawing') not in scope:
            raise WorkspaceError('The remaining runner plan exceeds this scope. Continue the focused work in conversation.')
    if not record.get('research_contract'):
        raise WorkspaceError('This conversation has no saved runner research contract. Continue its focused work in conversation.')
    ready = engine.ready(record['agent'])
    if not ready.ready:
        raise WorkspaceError(ready.problem)
