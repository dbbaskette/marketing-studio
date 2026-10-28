"""Checked, bounded conversation operations on Presentation Studio's desk.

Companions validate a disposable copy outside the repository write lock. Publication
rechecks the exact inputs, execution owner and canonical worker markers under files.
"""
from contextlib import contextmanager
import base64
import hashlib
import json
import os
import stat
from pathlib import Path
import tempfile
import zlib

import home
from workspace import WorkspaceError, write_atomic
from runner import decks, desk, documents, gitstate, settings, stages, worker_tools
from runner.steps import build, existing, intake, outline as outlines, words
from runner.steps import deliver as delivering, look as looks
from studio_core import research_contract, research_sites
from studio_core.sync_guard import worker_in_progress, SYNC_WAIT

KINDS = ('text', 'outline', 'research', 'drawing', 'part')
TEXT = ('brief', 'classification', 'research-plan')
CHANGED = 'The deck or its inputs changed. Read desk context again before saving.'
MAX_BYTES = 256 * 1024 * 1024
MAX_FILES = 10000


def scope_of(value):
    if not isinstance(value, list) or not value or len(value) > 20 \
            or any(not isinstance(kind, str) or kind not in KINDS for kind in value):
        raise WorkspaceError('Supply an explicit scope list: text, outline, research, drawing, part.')
    return [kind for kind in KINDS if kind in value]


def create(engine, form, uploads=None):
    if not isinstance(form, dict):
        raise WorkspaceError('Supply a JSON object for desk creation.')
    return engine.start(form, uploads, execution='conversation', scope=scope_of(form.get('scope')))


def _start(engine, form, uploads, scope):
    """Engine.start's no-worker branch; the same checked form, intake and folder domain."""
    space, chosen = engine.space(), settings.load()
    gitstate.identity(space.repo)
    form = {'output': chosen.output, 'brand': chosen.brand, 'variant': chosen.variant,
            **form, 'flow': 'desk'}
    checked = decks.check_form(form, None)
    given = engine._given(form, checked, uploads or {})
    with gitstate.workspace_locked(space, engine.files, configured=True):
        if worker_in_progress(space.repo, refusal=WorkspaceError):
            raise WorkspaceError(SYNC_WAIT)
        root = decks.create(space, checked)
        try:
            for name, data in given.items():
                target = root / 'sources/incoming' / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            record = engine._load(root)
            from runner import team
            record.update(execution='conversation', conversation_scope=scope,
                          driver=team.claim(space), agent=chosen.agent, model=chosen.model,
                          level_of_effort=chosen.effort,
                          limits={'step_seconds': chosen.step_seconds, 'dollars': chosen.deck_dollars})
            engine._store(root, record)
            engine._commit(root, 'start requested work in conversation')
            home.remember(root, checked['title'])
        except BaseException:
            engine._undo_start(space, root)
            raise
    return {'path': str(root), 'id': root.name, 'execution': 'conversation', 'scope': scope}


def _root(engine, path, change=False, owner=True):
    root = engine.driven(path)
    if root is None:
        raise WorkspaceError('There is no deck there.')
    record = engine._load(root)
    if not decks.on_desk(record):
        raise WorkspaceError('This saved deck needs its saved-work or migration path before conversation edits.')
    if change:
        engine.hold(root, conversation=True)
        if owner and not decks.in_conversation(record):
            raise WorkspaceError('This deck is owned by the runner. Use its saved-work path first.')
        if owner:
            scope_of(record.get('conversation_scope'))
        run = engine._run(root)
        if run.busy or run.queued or record.get('desk_jobs') \
                or (record.get('desk') or {}).get('edits') \
                or record.get('review_requested') or desk.opened(record) \
                or (build.read_state(root).get('asked') or {}).get('sections') \
                or worker_in_progress(engine.space().repo, refusal=WorkspaceError):
            raise WorkspaceError(SYNC_WAIT)
    return root, record


def _files(root):
    files, size = {}, 0
    def unreadable(error):
        raise WorkspaceError('The deck could not be read completely.') from error

    for folder, directories, names in os.walk(root, followlinks=False, onerror=unreadable):
        for name in [*directories, *names]:
            if (Path(folder) / name).is_symlink():
                raise WorkspaceError('Conversation inputs cannot traverse linked files or folders.')
        for name in names:
            path = Path(folder) / name
            details = path.stat()
            if not stat.S_ISREG(details.st_mode):
                raise WorkspaceError('Conversation inputs must be ordinary files.')
            size += details.st_size
            if size > MAX_BYTES or len(files) >= MAX_FILES:
                raise WorkspaceError('This deck is too large for a bounded conversation save.')
            files[path.relative_to(root).as_posix()] = path.read_bytes()
    return files


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _basis(files, target, scope, extra):
    return _digest({'files': {name: hashlib.sha256(data).hexdigest()
                              for name, data in files.items()},
                    'target': target, 'scope': scope, 'requirements': extra})


def _kind(target):
    if target in TEXT:
        return 'text'
    if target in ('outline', 'research', 'drawing'):
        return target
    if target in ('look', 'design'):
        return 'drawing'
    if isinstance(target, str) and '/' in target:
        return 'part'
    if target in ('scope', 'handoff', 'ownership'):
        return None
    raise WorkspaceError('Choose brief, classification, research-plan, outline, research, drawing or a current slide/field.')


def _part(root, record, target):
    ident, _, field = target.partition('/')
    if desk.selected(record):
        inventory = outlines.inventory_of(root) or {}
        slide = next((one for one in inventory.get('slides') or ()
                      if f"slide-{one.get('number')}" == ident), None)
        if slide is None or not field.startswith('object:'):
            raise WorkspaceError('Selected changes edits name a current slide/object:ID:run.')
        bits = field.split(':')
        if len(bits) != 3 or (bits[2] != 'all' and not bits[2].isdigit()):
            raise WorkspaceError('Name object:ID:run, or object:ID:all for a single run.')
        parsed = ('object', bits[1], None if bits[2] == 'all' else int(bits[2]))
        old = words.run_text(inventory, words.plan_of(root), slide['number'], *parsed[1:])
        return ident, slide['number'], parsed, old
    slides = build.slides_of(desk._outline(root))
    slide = next((one for one in slides if one.get('id') == ident), None)
    if slide is None:
        raise WorkspaceError('Choose a stable slide ID from desk show.')
    parsed = field
    if field.startswith('points:'):
        bits = field.split(':')
        if len(bits) != 3 or not bits[1].isdigit():
            raise WorkspaceError('Name points:INDEX:label or points:INDEX:text.')
        parsed = ('points', int(bits[1]), bits[2])
    parsed = words.field_of(parsed)
    return ident, slides.index(slide) + 1, parsed, words.text_of(slide, parsed)


def _intake(engine, root, record, reading=True):
    source = dict(record['form'].get('source') or {})
    route = record['route']
    if route == 'scratch':
        return
    if source.get('kind') == 'google':
        imported = (route == 'existing' and (root / existing.SOURCE).is_file()) \
            or (route == 'document' and documents.listed(root))
        if not imported:
            raise WorkspaceError('Google input has not been imported. Explicitly supply a local export; conversation never fetches it silently.')
    if route == 'document' and not documents.listed(root):
        source.update(data=(root / 'sources/incoming/upload').read_bytes()) \
            if source.get('kind') == 'upload' else source.update(
                text=(root / 'sources/incoming/pasted.txt').read_text())
        intake.take_document(root, source)
    if reading and route == 'document' and not record.get('classified'):
        if record['form'].get('reading') not in intake.KINDS:
            raise WorkspaceError('First submit a checked classification, or explicitly choose reading spec/material at creation.')
        intake.given(root, record, record['form']['reading'])
    if route == 'existing' and not (root / existing.SOURCE).is_file():
        source['data'] = (root / 'sources/incoming/upload').read_bytes()
        existing.fetch(root, source, engine.slides(), False)
    if route == 'existing' and outlines.inventory_of(root) is None:
        existing.keep_inventory(root, record, existing.read_deck(root, engine.slides()))


def _prepare(engine, root, record, target):
    kind = _kind(target)
    requirements = {'kind': kind, 'envelope': ['kind', 'target', 'expected_basis', 'payload']}
    if target in ('scope', 'handoff', 'ownership'):
        return {'allowed_scope': list(KINDS), 'existing_scope': record.get('conversation_scope')}
    if target == 'design':
        status = engine.slides().design_status(root / 'work')
        question = status.get('question')
        if not isinstance(question, dict) or not question.get('id') or not status.get('revision'):
            raise WorkspaceError('No current companion design question is waiting.')
        return {'operation': 'answer', 'question': question, 'revision': status['revision'],
                'slides': status.get('slides') or [], 'project': 'work',
                'envelope': ['target', 'expected_basis', 'answer'],
                'answer': ['questionId', 'planRevision', 'decision', 'feedback']}
    if target == 'brief':
        return {**requirements, 'payload': {'text': 'Brief, at most 4,000 characters'}}
    if target == 'classification':
        if record['route'] != 'document':
            raise WorkspaceError('Classification applies to a supplied document.')
        _intake(engine, root, record, reading=False)
        work = intake.classify_work(root, record)
        return {**requirements, 'inputs': work.prepared['inputs'],
                'guidance': work.guidance, 'task': work.task,
                'payload': {'classification': {'kind': 'spec or material',
                    'reason': 'Sentence explaining the reading', 'slides': 'Count for spec; null for material'}}}
    if target in ('research', 'research-plan'):
        if not record['form'].get('research') or record['route'] == 'existing':
            raise WorkspaceError('Research was not requested for this deck.')
        _intake(engine, root, record)
        if record['route'] == 'document' and record.get('classified') != 'material':
            raise WorkspaceError('Research applies to document material, not a slide script.')
        return {**requirements, 'source_scope': decks.research_from(record['form']),
                'inputs': {'supplied_sources': {
                    entry['name']: documents.text_of(root, entry)
                    for entry in documents.listed(root) if entry['readable']}},
                'payload': {'case': 'Absolute local complete reviewed Harness Research case'}
                if target == 'research' else {'plan': 'topic and items, checked by the Studio plan checker'}}
    _intake(engine, root, record)
    if not record['form'].get('brand'):
        raise WorkspaceError('Choose a brand explicitly before checking this material.')
    contract = build.export_brand(root, record, engine.brand())
    # Existing saved starts contain canonical absolute paths: isolate the validation copy.
    state = build.read_state(root)
    if state.get('start'):
        state['start']['brand'] = str(contract)
        build.write_state(root, state)
    if target == 'look':
        return _look_context(engine, root, record)
    if target == 'outline':
        if desk.selected(record):
            raise WorkspaceError('Selected changes keeps its original deck; submit its scoped patch drawing instead.')
        work = outlines.extract_work(root, record, None, None, contract, engine.slides()) \
            if record['route'] == 'existing' and record['form'].get('level') != 'rework' \
            else outlines.outline_work(root, record, None, None, contract, engine.slides())
        return {**requirements, 'payload': {'outline': 'Complete Harness Slides outline JSON object'},
                'spec': work.prepared['artifacts']['outline'],
                'guidance': work.guidance, 'task': work.task, 'inputs': work.prepared['inputs']}
    if kind == 'part':
        ident, number, field, old = _part(root, record, target)
        desk.refuse_words(record, field)
        return {**requirements, 'payload': {'text': 'Checked replacement words'},
                'slide': ident, 'number': number, 'field': field, 'current': old}
    if desk.selected(record):
        return {**requirements, 'payload': {'patch': 'Existing checked selected-slide patch plan'},
                'spec': existing.patch_work(root, record, None, None).prepared['artifacts']['patch']}
    if not (root / outlines.OUTLINE).is_file():
        raise WorkspaceError('Submit a checked outline before its drawing.')
    if record['form'].get('look') != 'default' and not (root / 'look.md').is_file():
        raise WorkspaceError('The look needs the person’s explicit choice. Choose the brand default explicitly at creation, or retain a saved picked look.')
    if (root / 'work/.harness-slides/design/session.json').is_file():
        status = engine.slides().design_status(root / 'work')
        if status.get('question') or not status.get('buildAllowed'):
            raise WorkspaceError('Answer the current companion design question before drawing.')
        engine.slides().design_check(root / 'work')
    if not state.get('start'):
        build.start(root, record, engine.slides(), contract)
    return {**requirements, 'payload': {'sections': 'Object mapping requested section IDs to compositions'},
            'sections': {ident: build.section_spec(root, record, ident, 'local')
                         for ident in build.to_draw(root)}}



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


def _look_context(engine, root, record):
    """Offer actual local samples without publishing them or choosing an answer."""
    if looks.chosen(root) is not None:
        raise WorkspaceError('The look question has already been answered.')
    if not (root / outlines.OUTLINE).is_file():
        raise WorkspaceError('Submit a checked outline before choosing its look.')
    skill = engine.brand()
    shown = looks.draw_looks(root, record, skill, 'local', engine.slides().has) \
        if skill.looks() else None
    offered, previews, size = (shown or {}).get('looks') or [], {}, 0
    if len(offered) > 12:
        raise WorkspaceError('The brand offered too many look samples for one bounded answer.')
    for item in offered:
        picture = root / looks.FOLDER / f"{item['number']}.png"
        with picture.open('rb') as source:
            data = source.read(4_000_001 - size)
        size += len(data)
        if size > 4_000_000 or not data.startswith(b'\x89PNG\r\n\x1a\n'):
            raise WorkspaceError('The look previews exceed the bounded PNG input limit.')
        previews[item['id']] = {'mime': 'image/png', 'base64': base64.b64encode(_preview_png(data)).decode()}
    packet = {'operation': 'answer', 'offered': offered, 'previews': previews,
              'default': (shown or {}).get('default'),
              'failed': bool((shown or {}).get('failed')), 'unseen': (shown or {}).get('unseen'),
              'outline': hashlib.sha256((root / outlines.OUTLINE).read_bytes()).hexdigest(),
              'envelope': ['target', 'expected_basis', 'answer'],
              'answer': ['questionId', 'choice', 'response']}
    return packet


def _look_answer(engine, root, record, requirements, reply):
    if set(reply) != {'questionId', 'choice', 'response'} \
            or reply['questionId'] != requirements['questionId']:
        raise WorkspaceError('Answer the current look question.')
    choice, response = reply['choice'], reply['response']
    if not isinstance(choice, str) or not isinstance(response, str) \
            or not response.strip() or len(response) > 4000:
        raise WorkspaceError('Supply the person’s explicit look choice and response.')
    offered = {item['id'] for item in requirements['offered']}
    shown = looks.shown_looks(root)
    if choice == 'default':
        if shown is None:
            picked = looks._unseen_default(root, engine.brand(), {}, root / build.CONTRACT, response)
            picked.update(words=response, by='conversation-person', at=home.now())
            home.write_json(root / looks.CHOSEN, picked)
        else:
            actual = looks.DEFAULT if shown.get('failed') else shown.get('default')
            if actual != looks.DEFAULT and actual not in offered:
                raise WorkspaceError('The brand did not identify a current default look.')
            picked = looks.choose(root, engine.brand(), actual, response, by='conversation-person')
    else:
        if choice not in offered:
            raise WorkspaceError('Choose an offered look from the current context.')
        picked = looks.choose(root, engine.brand(), choice, response, by='conversation-person')
    if picked is None:
        raise WorkspaceError(CHANGED)
    # Apply the actual chosen direction without the page's approve()/wake path.
    outline = desk._outline(root)
    for key in ('direction', 'house', 'layouts'):
        outline.pop(key, None)
        if picked.get(key):
            outline[key] = {k: v for k, v in picked[key].items()
                            if k in ('cover', 'section', 'closing')} if key == 'layouts' else picked[key]
    outlines._write(root, outline)
    write_atomic(root / looks.LOOK_MD, looks._markdown(record['form'], shown))
    record['form']['look'] = 'default' if choice == 'default' else 'pick'
    record['look_shown'], record['look_by'] = picked.get('shown'), 'conversation-person'
    if build.read_state(root).get('start'):
        build.start(root, record, engine.slides(), root / build.CONTRACT)


def _canonical(value, stage, root):
    if isinstance(value, str):
        return value.replace(str(stage), str(root))
    if isinstance(value, dict):
        return {key: _canonical(item, stage, root) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical(item, stage, root) for item in value]
    if callable(value):
        # Work specs contain importable checker functions and partials.
        return worker_tools.reference(value)
    return value


@contextmanager
def _prepared(engine, path, target, change=False, owner=True):
    space = engine.space()
    with gitstate.workspace_locked(space, engine.files, configured=True):
        root, record = _root(engine, path, change, owner)
        scope = scope_of(record['conversation_scope']) if 'conversation_scope' in record else None
        kind = _kind(target)
        if kind and scope is not None and kind not in scope:
            raise WorkspaceError('This target exceeds the requested conversation scope.')
        before = _files(root)
    with tempfile.TemporaryDirectory(prefix='presentation-conversation-') as temporary:
        stage = Path(temporary) / root.name
        for name, data in before.items():
            file = stage / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(data)
        current = decks.read_run(stage)
        requirements = _prepare(engine, stage, current, target)
        requirements = _canonical(requirements, stage, root)
        contract = stage / build.CONTRACT
        brand_input = _canonical(contract.read_text(encoding='utf-8'), stage, root) \
            if contract.is_file() else None
        if brand_input is not None:
            # The first context exports only in scratch space. Bind those bytes too,
            # rebasing the scratch prefix so a new preparation has the same identity.
            requirements['brand_contract_sha256'] = hashlib.sha256(brand_input.encode()).hexdigest()
        if target == 'look':
            requirements['questionId'] = _digest(requirements)
        context = {'target': target, 'scope': scope, 'requirements': requirements,
                   'inputs': {'form': record['form'], 'outline': home.read_json(root / 'outline.json', None),
                              'brand_contract': brand_input,
                              'sources': documents.listed(stage),
                              'research': home.read_json(root / 'research/output.json', None)}}
        context['expected_basis'] = _basis(before, target, scope, requirements)
        with gitstate.workspace_locked(space, engine.files, configured=True):
            _root(engine, root, change, owner)
            if _files(root) != before:
                raise WorkspaceError(CHANGED)
        yield space, root, stage, current, before, context


def context(engine, path, target):
    with _prepared(engine, path, target) as prepared:
        return prepared[-1]


def show(engine, path):
    space = engine.space()
    with gitstate.workspace_locked(space, engine.files, configured=True):
        root, record = _root(engine, path)
        outline = home.read_json(root / 'outline.json', None)
        return {'path': str(root), 'id': root.name, 'execution': record.get('execution', 'runner'),
                'scope': record.get('conversation_scope'), 'form': record['form'],
                'outline': outline, 'sources': documents.listed(root),
                'conversation_eligible': decks.on_desk(record),
                'ownership_target': 'ownership',
                'research': home.read_json(root / 'research/output.json', None),
                'drawing': build.read_state(root), 'delivered': decks.delivered(root),
                'history': {slide['id']: desk.versions_of(root, slide['id'])
                            for slide in build.slides_of(outline or {})},
                'provenance': record.get('conversation_submissions', [])}


def _checked(check):
    if check[0]:
        raise WorkspaceError('The material cannot be saved. ' + ' '.join(map(str, check[0])))
    return check[-1]


def _text(engine, root, record, target, payload):
    if target == 'brief':
        if set(payload) != {'text'}:
            raise WorkspaceError('A brief takes text only.')
        text = decks._text({'notes': payload['text']}, 'notes', 'brief')
        record['form']['notes'] = text
        write_atomic(root / 'intake.md', decks.intake(record['form']))
        return
    if target == 'classification':
        if set(payload) != {'classification'}:
            raise WorkspaceError('Submit classification only.')
        given = payload['classification']
        _checked(intake.check_classification(json.dumps(given), {}))
        intake.keep_classification(root, record, given)
        return
    if set(payload) != {'plan'}:
        raise WorkspaceError('Submit plan only.')
    result = worker_tools.check_research_plan(payload['plan'], most=8)
    if result['problems']:
        raise WorkspaceError(' '.join(result['problems']))
    looks = decks.research_from(record['form'])
    if payload['plan'].get('scope') != research_sites.plan_scope(looks):
        raise WorkspaceError('The research plan exceeds the pinned source scope.')
    if not research_sites.fetches(looks) and any(item.get('public_query') for item in payload['plan']['items']):
        raise WorkspaceError('Supplied-only research has no public search queries.')
    engine._keep_plan(root, record, json.dumps(payload['plan']))


def _outline(engine, root, record, payload):
    if set(payload) != {'outline'} or not isinstance(payload['outline'], dict):
        raise WorkspaceError('Submit a complete outline JSON object only.')
    spec = _prepare(engine, root, record, 'outline')['spec']
    with tempfile.TemporaryDirectory(prefix='presentation-outline-check-') as temporary:
        text = _checked(worker_tools.check_outline(json.dumps(payload['outline']), spec,
                                                  engine.slides(), Path(temporary)))
    before = desk._outline(root)
    after = json.loads(text)
    for slide in build.slides_of(before):
        changed = next((s for s in build.slides_of(after) if s['id'] == slide['id']), None)
        if changed != slide:
            desk.keep_slide(root, slide['id'], 'outline')
            desk.advance(record, slide['id'])
    outlines.keep_outline(root, record, text)
    if build.read_state(root).get('start'):
        build.start(root, record, engine.slides(), root / build.CONTRACT)
    record['steps']['outline' if 'gate:outline' in {s.name for s in stages.steps(record)} else 'extract'] = {
        'done': True, 'at': home.now(), 'source': 'conversation'}


def _drawing(engine, root, record, payload):
    if desk.selected(record):
        if set(payload) != {'patch'}:
            raise WorkspaceError('Selected changes takes a checked patch only.')
        spec = existing.patch_work(root, record, None, None).prepared['artifacts']['patch']
        text = _checked(existing.check_patch(json.dumps(payload['patch']), spec))
        existing.keep_patch(root, text)
        build.render(root, record, engine.slides(), engine.brand(), 'local')
    else:
        if set(payload) != {'sections'} or not isinstance(payload['sections'], dict):
            raise WorkspaceError('Submit section compositions only.')
        wanted = build.to_draw(root)
        if set(payload['sections']) != set(wanted):
            raise WorkspaceError('Supply exactly the requested drawing section IDs.')
        for ident in wanted:
            spec = build.section_spec(root, record, ident, 'local')
            with tempfile.TemporaryDirectory(prefix='presentation-section-check-') as temporary:
                folder = Path(temporary) / 'job'
                worker_tools.prepare(folder, artifacts={'section': spec}, ask=False)
                tools = worker_tools.WorkerTools(folder)
                text = json.dumps(payload['sections'][ident])
                for operation in (tools.preview_section, tools.submit_section):
                    checked = operation(text)
                    if not checked[0]:
                        raise WorkspaceError(str(checked[1]))
                build.keep_section(root, record, ident, worker_tools.collect(folder))
        build.whole(root, record, engine.slides(), 'local')
        build.render(root, record, engine.slides(), engine.brand(), 'local')
    desk.arrive(record)
    record.setdefault('gates', {})['gate:build'] = {
        **record.get('gates', {}).get('gate:build', {}), 'state': 'waiting'}


def _part_save(engine, root, record, target, payload):
    if set(payload) != {'text'} or not isinstance(payload['text'], str):
        raise WorkspaceError('A part save takes replacement text only.')
    ident, number, field, old = _part(root, record, target)
    text = _checked(words.check_words(payload['text'], {'single': field != 'notes'}))
    desk.refuse_words(record, field)
    if desk.selected(record):
        desk.keep_slide(root, ident, 'save')
        words.add_op(root, words.plan_op(outlines.inventory_of(root), number, *field[1:], text))
        build.render(root, record, engine.slides(), engine.brand(), 'local')
    else:
        edited = words.retext(desk._outline(root), ident, field, text)
        outlines.checked_edits(root, record, edited['slides'], engine.slides(), root / build.CONTRACT)
        state = build.read_state(root)
        if state.get('start'):
            section = desk.section_of(state, number)
            file = root / state['sections'][section]['file'] if section \
                else words.lead_file(root, state, ident)
            if file is None:
                raise WorkspaceError(desk.NO_DRAWING)
            patched = words.patch_section(home.read_json(file, {}), ident, field, old, text)
            whole = words.with_words(words.given(root), edited, ident)
            problems = words.fits(root, record, section, patched, engine.slides(), whole) \
                if section else words.lead_fits(patched, root / build.CONTRACT, engine.slides())
            if problems:
                raise WorkspaceError(' '.join(problems))
            engine._desk_land(root, record, {'slide': ident, 'number': number, 'section': section,
                'field': field, 'text': text, 'old': old, 'source': 'save'}, patched, None)
            # The checked native file must match the edited drawing; no composer is started.
            build.whole(root, record, engine.slides(), 'local')
            build.render(root, record, engine.slides(), engine.brand(), 'local')
        else:
            desk.keep_slide(root, ident, 'save')
            outlines._write(root, edited)
        desk.advance(record, ident)


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, pending = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(handle, 'wb') as stream:
            stream.write(data)
        os.replace(pending, path)
    finally:
        Path(pending).unlink(missing_ok=True)


def _publish(engine, space, root, stage, before, owner=True):
    after = _files(stage)
    # Canonicalize generated work metadata only; never rewrite original source bytes.
    for name, data in list(after.items()):
        if name.startswith('work/') and name.endswith('.json') and before.get(name) != data:
            try:
                value = _canonical(json.loads(data), stage, root)
                after[name] = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()
            except (UnicodeDecodeError, ValueError):
                pass
    changed = {name for name in before.keys() | after.keys() if before.get(name) != after.get(name)}
    allowed = {'run.json', 'README.md', 'intake.md', 'classify.json', 'classify.md',
               'outline.json', 'outline.md', 'look.md', 'deliver.json', 'deck.pptx',
               'contact-sheet.png'}
    if any(name not in allowed and name.split('/')[0] not in
           {'brand', 'sources', 'research', 'desk', 'work', '.studio-research'} for name in changed):
        raise WorkspaceError('A checker attempted to change an unsupported deck file.')
    with gitstate.workspace_locked(space, engine.files, configured=True):
        _root(engine, root, True, owner)
        if _files(root) != before:
            raise WorkspaceError(CHANGED)
        index = space.root / 'README.md'
        index_before = index.read_bytes() if index.is_file() else None
        index_changed = ('deliver.json' in changed)
        try:
            for name in sorted(changed):
                if name in after:
                    _write(root / name, after[name])
                else:
                    (root / name).unlink(missing_ok=True)
            if index_changed:
                decks.write_index(space)
            engine._commit(root, 'keep checked conversation work', [index] if index_changed else ())
        except BaseException:
            if index_changed:
                _write(index, index_before) if index_before is not None else index.unlink(missing_ok=True)
            for name in changed:
                if name in before:
                    _write(root / name, before[name])
                else:
                    (root / name).unlink(missing_ok=True)
            raise


def submit(engine, path, request):
    if not isinstance(request, dict) or set(request) != {'kind', 'target', 'expected_basis', 'payload'} \
            or not isinstance(request['payload'], dict):
        raise WorkspaceError('Submit kind, target, expected_basis and payload together.')
    target, kind, payload = request['target'], request['kind'], request['payload']
    if target in ('look', 'design'):
        raise WorkspaceError('Use desk answer for an explicit look or design answer.')
    if kind not in KINDS or _kind(target) != kind:
        raise WorkspaceError('The submission kind does not match its target.')
    if len(json.dumps(payload)) > 2_000_000:
        raise WorkspaceError('The submission is too large.')
    with _prepared(engine, path, target, change=True) as prepared:
        space, root, stage, record, before, context = prepared
        if request['expected_basis'] != context['expected_basis']:
            raise WorkspaceError(CHANGED)
        previous_decisions = json.loads(json.dumps(record.get('gates') or {}))
        if decks.delivered(stage) is not None:
            record = delivering.again(stage, record, engine.slides(),
                                      'Changes explicitly requested in conversation.', sections=[])
        if kind == 'text':
            _text(engine, stage, record, target, payload)
        elif kind == 'outline':
            _outline(engine, stage, record, payload)
        elif kind == 'drawing':
            _drawing(engine, stage, record, payload)
        elif kind == 'part':
            _part_save(engine, stage, record, target, payload)
        else:
            if set(payload) != {'case'} or not isinstance(payload['case'], str) \
                    or not Path(payload['case']).is_absolute():
                raise WorkspaceError('Research takes an absolute local reviewed case folder.')
            facts, _ = research_contract.read_bundle(Path(payload['case']) / 'research')
            looks = decks.research_from(record['form'])
            for source in facts.get('sources') or ():
                if source.get('permission') == 'public' and not looks['web'] \
                        and not research_sites.under(source.get('origin'), looks['sites']):
                    raise WorkspaceError('The research bundle exceeds the pinned source scope.')
            research_contract.adopt_case(Path(payload['case']), stage)
            _, manifest = research_contract.publish(stage / research_contract.CASE, stage / 'research')
            record['research'] = {**(record.get('research') or {}), 'contract': 2, 'digest': manifest['digest']}
        if kind in ('text', 'outline', 'research'):
            gate = 'gate:outline' if 'gate:outline' in {s.name for s in stages.steps(record)} else 'gate:build'
            checked_outline = record.get('steps', {}).get('outline')
            reopened = stages.reopen(record, gate)
            reopened['gates'][gate] = {**reopened['gates'].get(gate, {}), 'state': 'absent'}
            if kind == 'outline' and checked_outline:
                reopened['steps']['outline'] = checked_outline
            record = reopened
        # No submission supplies an approval, Ready state or execution transfer.
        record.setdefault('conversation_submissions', []).append({
            'kind': kind, 'target': target, 'basis': request['expected_basis'],
            'scope': context['scope'], 'at': home.now(), 'by': 'conversation',
            'previous_decisions': previous_decisions})
        decks.write_run(stage, record)
        _publish(engine, space, root, stage, before)
    return show(engine, root)


def save(engine, path, request):
    return submit(engine, path, request)


def set_scope(engine, path, expected_basis, scope):
    scope = scope_of(scope)
    with _prepared(engine, path, 'scope', change=True) as prepared:
        space, root, stage, record, before, context = prepared
        if expected_basis != context['expected_basis']:
            raise WorkspaceError(CHANGED)
        record['conversation_scope'] = scope
        record.setdefault('conversation_scope_changes', []).append({
            'basis': expected_basis, 'scope': scope, 'at': home.now(), 'by': 'person-request'})
        decks.write_run(stage, record)
        _publish(engine, space, root, stage, before)
    return show(engine, root)


def handoff(engine, path, expected_basis, scope):
    scope = scope_of(scope)
    with _prepared(engine, path, 'handoff', change=True) as prepared:
        space, root, stage, record, before, context = prepared
        if expected_basis != context['expected_basis']:
            raise WorkspaceError(CHANGED)
        if scope != context['scope']:
            raise WorkspaceError('Handoff must use the current requested scope.')
        mapping = {'intake-source': 'text', 'classify': 'text', 'inventory': 'text',
                   'research-plan': 'research', 'research': 'research', 'research-report': 'research',
                   'outline': 'outline', 'extract': 'outline'}
        remaining = [s for s in stages.steps(record) if s.kind != 'gate' and s.name != 'deliver'
                     and not (record.get('steps', {}).get(s.name) or {}).get('done')]
        if any(mapping.get(s.name, 'drawing') not in scope for s in remaining):
            raise WorkspaceError('The remaining runner plan exceeds this scope. Continue the focused work in conversation, or explicitly change scope.')
        if (record.get('research') or {}).get('contract') == 2 and not record.get('research_contract'):
            raise WorkspaceError('This imported research has no saved runner contract. Continue its focused work in conversation.')
        ready = engine.ready(record['agent'])
        if not ready.ready:
            raise WorkspaceError(ready.problem)
        record['execution'] = 'runner'
        record['conversation_handoff'] = {'basis': expected_basis, 'scope': scope, 'at': home.now()}
        decks.write_run(stage, record)
        _publish(engine, space, root, stage, before)
    engine.wake(root)
    return show(engine, root)


def take(engine, path, expected_basis, scope):
    """Explicitly continue an existing desk in chat; never convert a saved old flow."""
    scope = scope_of(scope)
    with _prepared(engine, path, 'ownership', change=True, owner=False) as prepared:
        space, root, stage, record, before, context = prepared
        if expected_basis != context['expected_basis']:
            raise WorkspaceError(CHANGED)
        if context['scope'] is not None and scope != context['scope']:
            raise WorkspaceError('Keep the current requested scope; explicitly change scope separately.')
        record.update(execution='conversation', conversation_scope=scope)
        record.setdefault('conversation_ownership', []).append({
            'basis': expected_basis, 'scope': scope, 'at': home.now(), 'by': 'person-request'})
        decks.write_run(stage, record)
        _publish(engine, space, root, stage, before, owner=False)
    return show(engine, root)


def answer(engine, path, request):
    """Only an explicit person answer may settle a current look/design question."""
    if not isinstance(request, dict) or set(request) != {'target', 'expected_basis', 'answer'} \
            or request['target'] not in ('look', 'design') or not isinstance(request['answer'], dict):
        raise WorkspaceError('Supply target look/design, expected_basis and the person’s answer.')
    target, reply = request['target'], request['answer']
    with _prepared(engine, path, target, change=True) as prepared:
        space, root, stage, record, before, context = prepared
        if request['expected_basis'] != context['expected_basis']:
            raise WorkspaceError(CHANGED)
        requirements = context['requirements']
        if target == 'look':
            _look_answer(engine, stage, record, requirements, reply)
        else:
            if set(reply) != {'questionId', 'planRevision', 'decision', 'feedback'} \
                    or reply['questionId'] != requirements['question']['id'] \
                    or reply['planRevision'] != requirements['revision']:
                raise WorkspaceError('Answer the current design question and revision.')
            if not isinstance(reply['decision'], str) or not reply['decision'] \
                    or len(reply['decision']) > 64 or not isinstance(reply['feedback'], str) \
                    or not reply['feedback'].strip() or len(reply['feedback']) > 4000:
                raise WorkspaceError('Supply the person’s actual design decision and response.')
            engine.slides().design_respond(stage / 'work', reply)
        record.setdefault('conversation_answers', []).append({
            'target': target, 'basis': request['expected_basis'], 'answer': reply,
            'scope': context['scope'], 'at': home.now(), 'by': 'person-request'})
        decks.write_run(stage, record)
        _publish(engine, space, root, stage, before)
    return show(engine, root)
