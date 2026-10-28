"""The person's final build approval, without delivery or runner execution."""
import copy
import hashlib
import json
from pathlib import Path

import home
from workspace import WorkspaceError
from runner import decks, desk, gitstate, worker_tools
from runner.steps import build, existing, words
from runner.desk_migration import materials
from studio_core import presentation_migration, research_contract


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _pictures(files, folder, listed, numbers, hashes=None):
    from runner.desk_chat import _preview_png
    if not presentation_migration.relative(folder) or not isinstance(listed, list) \
            or len(listed) != len(numbers):
        raise ValueError('The complete current slide preview is required.')
    found = {}
    for slide in listed:
        if not isinstance(slide, dict) or type(slide.get('number')) is not int \
                or slide['number'] not in numbers or slide['number'] in found:
            raise ValueError('The current slide preview identities cannot be verified.')
        image = slide.get('image')
        if not isinstance(image, str) or Path(image).name != image or not image.endswith('.png'):
            raise ValueError('The current preview names an unsupported image.')
        name = folder + '/' + image
        data = files.get(name)
        if not isinstance(data, bytes) or not data.startswith(worker_tools.PNG) \
                or len(data) > worker_tools.PICTURE:
            raise ValueError('A current slide preview is missing or unreadable. Nothing was redrawn.')
        _preview_png(data)  # existing pure complete-PNG parser; never replace the bytes
        digest = hashlib.sha256(data).hexdigest()
        expected = hashes.get(slide['number']) if hashes is not None else slide.get('sha256')
        if any(value is not None and digest != value for value in
               (expected, slide.get('sha256'), slide.get('imageSha256'))):
            raise ValueError('A current slide preview changed since it was checked. Nothing was redrawn.')
        if hashes is not None and not isinstance(expected, str):
            raise ValueError('A checked slide preview has no recorded image proof.')
        found[slide['number']] = digest
    if set(found) != set(numbers):
        raise ValueError('The current slide preview is incomplete.')
    return found


def _round_previews(files, last, outline):
    current = build.slides_of(outline)
    slides = last.get('slides')
    if not isinstance(slides, list) or any(not isinstance(s, dict) for s in slides) \
            or [(s.get('number'), s.get('id')) for s in slides] \
            != [(number, slide['id']) for number, slide in enumerate(current, 1)]:
        raise ValueError('The checked preview does not cover the current slides.')
    hashes = {slide['number']: slide.get('sha256') for slide in slides}
    folder = last.get('preview')
    if not presentation_migration.relative(folder):
        raise ValueError('The checked preview folder is missing.')
    manifest = json.loads(files[folder + '/preview.json'])
    if not isinstance(manifest, dict) or manifest.get('schema') != 1 \
            or manifest.get('deckSha256') != last.get('deck'):
        raise ValueError('The checked preview record cannot be verified.')
    listed = manifest.get('slides')
    if not isinstance(listed, list) or any(not isinstance(s, dict) for s in listed) \
            or [(s.get('number'), s.get('id')) for s in listed] \
            != [(s['number'], s['id']) for s in slides]:
        raise ValueError('The checked preview slide identities changed.')
    # Older native preview records use absolute image paths. Rebase only images
    # directly inside their recorded output, never read outside the bounded copy.
    images = []
    for slide in listed:
        image = Path(slide['image'])
        if image.parent not in (Path('.'), Path(str(manifest.get('output')))):
            raise ValueError('The checked preview image is outside its saved output.')
        images.append({**slide, 'image': image.name})
    _pictures(files, folder, images, hashes, hashes)
    folder = existing.AFTER_SHOTS
    shown = json.loads(files[folder + '/' + existing.SHOTS])
    return _pictures(files, folder, shown['slides'], hashes, hashes)


def _selected(root, record, files, state, engine):
    inventory = json.loads(files[existing.INVENTORY])
    patch = json.loads(files[existing.PATCH])
    spec = existing._spec(inventory, existing._named_for(record, inventory))
    problems, _, _, _ = existing.check_patch(files[existing.PATCH].decode(), spec)
    if problems:
        raise ValueError('The retained Selected changes plan is invalid. ' + ' '.join(problems))
    ids = {slide['number']: str(slide['id']) for slide in inventory['slides']}
    operations = [{**op, 'slide': ids[op['slide']]} for op in patch['operations']]
    expected = {'sourceSha256': patch['sourceSha256'], 'operations': operations}
    allow = [{'slide': op['slide'], 'object': str(op['object']), 'fields': [
        'text' if field == 'runs' else field for field in existing.FIELDS if field in op]} for op in operations]
    if json.loads(files[existing.PLAN]) != expected or json.loads(files[existing.ALLOW]) != allow:
        raise ValueError('The native Selected changes plan or allowed changes differ from the retained request.')
    folder = existing.AFTER_SHOTS
    shots = json.loads(files[folder + '/' + existing.SHOTS])
    pictures = _pictures(files, folder, shots['slides'], ids)
    digest = hashlib.sha256(files[state['deck']]).hexdigest()
    if state.get('deckSha256') is not None and state['deckSha256'] != digest:
        raise ValueError('The native deck changed since it was checked.')
    missing = not state.get('deckSha256') or any(not (s.get('sha256') or s.get('imageSha256')) for s in shots['slides'])
    validation = {'deck': digest, 'previews': {str(number): value for number, value in pictures.items()},
                  'preservation': None, 'patch_matches': None, 'inspection': None}
    if engine is not None:
        slides = engine.slides()
        report = slides.pptx_compare(Path(root) / existing.SOURCE, Path(root) / state['deck'], Path(root) / existing.ALLOW)
        if not isinstance(report, dict) or report.get('preserved') is not True \
                or not isinstance(report.get('failures'), list) or report['failures']:
            raise ValueError('The current native copy failed preservation outside the permitted changes.')
        current = slides.pptx_inspect(Path(root) / state['deck'])
        if not isinstance(current, dict) or current.get('sha256') != digest or not isinstance(current.get('slides'), list):
            raise ValueError('The current native copy could not be inspected.')
        actual = {(str(s['id']), str(o['id'])): o for s in current['slides'] for o in s['objects']}
        for slide in inventory['slides']:
            for obj in words.objects_now(slide, patch['operations']):
                if actual.get((str(slide['id']), obj['id']), {}).get('runs') != obj['runs']:
                    raise ValueError('The current native copy does not contain the retained patch words.')
        for op in operations:
            obj = actual.get((op['slide'], str(op['object'])), {})
            if any(obj.get(field) != op[field] for field in ('alt', 'title') if field in op):
                raise ValueError('The current native copy does not contain the retained patch changes.')
        validation.update(preservation=report, patch_matches=True, inspection=_digest(current))
    return validation, ('Historical deck or preview byte proof is unavailable. The current copy was checked '
        'for preservation outside permitted changes and against the retained patch. Inspect its current previews; '
        'this does not prove they are byte-identical to the historical render.') if missing else None


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
        validation, historical = None, None
        if desk.selected(record):
            validation, historical = _selected(root, record, files, state, engine)
            digest = validation['deck']
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
            _round_previews(files, last, current)
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
        seen = {'revision': desk.revision(record), 'expected': desk.on_screen(root, record, state),
                'blockers_seen': desk.blockers_seen(state)}
        if validation is not None:
            seen['current_validation'] = _digest(validation)
        if historical:
            seen['historical_proof_ack'] = False
        return {'operation': 'ready', 'seen': seen, 'validation': validation, 'historical_proof': historical,
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
        required = requirements(root, record)
        decision = record.get('conversation_ready') or {}
        gate = record.get('gates', {}).get('gate:build') or {}
        current = (isinstance(decision, dict) and all(isinstance(decision.get(key), str)
                   and decision[key].strip() for key in ('by', 'at', 'response'))
                   and gate.get('state') == 'approved' and gate.get('by') == decision['by']
                   and decision.get('evidence') == evidence(root, record))
        if current and desk.selected(record):
            validation = decision.get('validation')
            report = validation.get('preservation') if isinstance(validation, dict) else None
            current = (isinstance(validation, dict) and isinstance(report, dict)
                       and report.get('preserved') is True and report.get('failures') == []
                       and validation.get('patch_matches') is True
                       and isinstance(validation.get('inspection'), str) and len(validation['inspection']) == 64
                       and all(validation.get(key) == required['validation'][key] for key in ('deck', 'previews')))
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
        seen = dict(context['requirements']['seen'])
        if context['requirements']['historical_proof']:
            if not isinstance(request['seen'], dict) or request['seen'].get('historical_proof_ack') is not True:
                raise WorkspaceError('Explicitly acknowledge the missing historical byte proof before approving the current copy.')
            seen['historical_proof_ack'] = True
        if request['expected_basis'] != context['expected_basis'] or request['seen'] != seen:
            raise WorkspaceError(desk_chat.CHANGED)
        previous = copy.deepcopy(record.get('gates', {}).get('gate:build'))
        gate = previous or {}
        at = home.now()
        record.setdefault('gates', {})['gate:build'] = {**gate, 'state': 'approved',
            'by': by, 'at': at, 'note': request['response'].strip(), 'round': int(gate.get('round') or 1)}
        record.setdefault('conversation_decisions', []).append({**request, 'target': 'ready',
            'by': by, 'at': at, 'previous_decision': previous})
        record['conversation_ready'] = {'at': at, 'by': by, 'response': request['response'].strip(),
                                         'validation': context['requirements']['validation'],
                                         'evidence': evidence(stage, record)}
        decks.write_run(stage, record)
        desk_chat._publish(engine, space, root, stage, before)
    return engine.view(root)
