"""Scan, outline, then fill in (#297): a quick scan of the ground, the training outline the
person approves, and research done section by section after that approval.

What a caller needs to know
---------------------------
    outline_first.on(record)                   whether a run takes this flow
    outline_first.scan_work(root, found, ...)  the quick scan's job: bounded, never research
    outline_first.keep(root, text, handed, asked)
                                               keep the scan and the outline drafted from it
    outline_first.view(root, found, record)    what the outline gate shows
    outline_first.edited(sent)                 an outline as the person edited it, checked
    outline_first.plan_text(root, found)       the research plan the approved outline gives
    outline_first.scope_text(root)             the outline as research's task scope names it
    outline_first.offer(...) / switch(...)     an older stopped training's explicit move here

- A run started on the desk with this flow has record schema 7, and its `training_plan` is
  {'schema': 2, 'revision', 'approved'?}: the existing training-plan gate ("Here's what this
  training will cover"), put before research instead of after the blueprints.
  `training_plan.outlined` says so; older runs keep the flow they were saved with.
- The scan is one assistant job, capped at SCAN_SECONDS and SCAN_DOLLARS, that reads the
  person's documents and, only where the training may search, saves at most SCAN_PAGES
  pages. Its tools refuse a page more. It hands back an overview (candidate sections, key
  terms, what each document covers, gaps), kept in SCAN. The scan is never research
  evidence: nothing in it is cited, and the materials quote only what research finds.
- The outline (OUTLINE) is drafted here, in code, from the scan and the form, so the scan
  is the only spend before the person sees it. Questions typed on the form are kept: each
  is attached to the section it shares the most words with, or listed separately.
- Once approved, each section's questions become research plan items that name their
  section; `research_session.streams` gives each section an area of its own, up to 3 at a
  time, grouping neighbouring sections when there are more.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import runner  # noqa: F401  puts the core on the import path
import home
import workspace
from workspace import WorkspaceError

RECORD_SCHEMA = 7
PLAN_SCHEMA = 2          # the training_plan record of this flow
SCAN = f'{workspace.STATE_DIR}/scan.json'
OUTLINE = f'{workspace.STATE_DIR}/training-outline.json'
NAME = 'training-scan'   # what the scan's worker hands its overview back under
STEP = 'scan'
FROM_OUTLINE = 'Research plan: written from your training outline'

SCAN_SECONDS = 180       # the quick scan's time, far less than research's
SCAN_DOLLARS = 0.75      # and its money; never more than the training has left
SCAN_PAGES = 5           # pages the scan may save, where the training may search at all
SECTIONS = (2, 8)        # sections a scan proposes
EDITED_SECTIONS = 12     # sections a person may keep
ASKED = 3                # questions a scan gives each section
EDITED_ASKED = 5         # questions a person may give each section
OBJECTIVES = 3           # objectives a scan gives each section
EDITED_OBJECTIVES = 5
SEPARATE = 8             # questions kept apart from every section
PLAN_MOST = 30           # research questions an outline gives research, in all
TITLE, TEXT, TERMS, GAPS = 120, 300, 20, 10
FROMS = ('scan', 'form', 'you')
OTHER = ('other', 'Other questions you asked')
NOT_EVIDENCE = ('The quick scan is a first look at the ground, not research: nothing from it '
                'is cited or quoted in the materials. Research reads the sources again for '
                'each section you approve.')
STOP_WORDS = frozenset('''about after also and are because been being between both but can
could does doing done each from have having here how into its itself just more most much must
only other over same should some such than that their them then there these they this those
through under very want were what when where which while who whom whose why will with within
would your yours'''.split())


def on(record: dict | None) -> bool:
    """Whether a run takes the scan, outline, then fill-in flow."""
    from runner import training_plan
    return training_plan.outlined(record or {})


# --- the quick scan ----------------------------------------------------------------------

def scan_work(root: Path, found, sources, error: str | None, asked) -> 'pipeline.Work':
    """The quick scan's job. `sources` is what the engine's `_sources` returned, or None
    when the training reads no documents."""
    from runner import briefs, pipeline
    from studio_core import research_sites
    offered = list((sources or ((), ()))[1])
    looks = found.research_from
    web = research_sites.fetches(looks)
    listed = [{'id': f's{number}', 'title': source.get('title') or source.get('origin') or f's{number}'}
              for number, source in enumerate(offered, start=1)]
    lines = ['Take a quick look at the ground this training covers and propose its outline.',
             'This is not the research: it is a short first look, so the person can approve '
             'what the training covers before the full research starts.', '',
             'The training:', pipeline._about(root, found.session), '']
    if listed:
        lines.append('The person supplied these documents, saved for you already. Skim each '
                     'and say in a line what it covers:')
        lines += [f"- {item['id']}: {item['title']}" for item in listed]
    else:
        lines.append('No documents were supplied.')
    if web:
        lines.append(f'You may run at most {SCAN_PAGES} web searches and save at most '
                     f'{SCAN_PAGES} pages with save_source, to see what the ground holds. '
                     + research_sites.scope_text(looks))
    else:
        lines.append('This training may not search the web: work from the documents and the '
                     'topic alone.')
    if asked:
        lines += ['', 'The person typed these research questions on the form. The studio keeps '
                  'each one for research and places it in your outline itself: do not copy them '
                  'into your sections, but shape the sections so they have a home:']
        lines += ['- ' + question for question in asked]
    lines += ['', f'You have about {SCAN_SECONDS // 60} minutes. Hand back early rather than '
              f'run out of time. Hand the overview back with submit_artifact under the name '
              f'"{NAME}".']
    if error:
        lines += ['', f'An earlier try at this scan did not work: {error}']
    prepared = {'inputs': {'intake': (root / 'intake.md').read_text(encoding='utf-8')
                           if (root / 'intake.md').is_file() else ''},
                'artifacts': {NAME: {'kind': 'scan', 'documents': [item['id'] for item in listed]}},
                'sources': offered, 'fetch': web, 'ask': False,
                **({'pages': SCAN_PAGES} if web else {})}
    return pipeline.Work(briefs.guidance('scan'), '\n'.join(lines), 'research' if web else 'write',
                         prepared, NAME)


def _strings(value, most: int, longest: int, what: str, problems: list, least: int = 0) -> list:
    if not isinstance(value, list) or not least <= len(value) <= most or any(
            not isinstance(item, str) or not item.strip() or len(item) > longest for item in value):
        problems.append(f'{what} must be a list of {least} to {most} texts of at most '
                        f'{longest} characters each.')
        return []
    return [' '.join(item.split()) for item in value]


def check_scan(text: str, spec: dict) -> tuple[list[str], list[dict], list[str], str]:
    """The scan's overview, as its worker hands it back: problems, the checks that ran,
    warnings and the overview as it is kept."""
    try:
        given = json.loads(text)
    except ValueError as failure:
        return [f'The overview is not valid JSON ({failure}).'], [], [], text
    if not isinstance(given, dict):
        return ['The overview must be a JSON object.'], [], [], text
    problems = []
    unknown = set(given) - {'sections', 'terms', 'documents', 'gaps'}
    if unknown:
        problems.append('Leave out ' + ', '.join(sorted(unknown)) + ': hand back sections, '
                        'terms, documents and gaps only.')
    sections = given.get('sections')
    kept_sections = []
    if not isinstance(sections, list) or not SECTIONS[0] <= len(sections) <= SECTIONS[1]:
        problems.append(f'"sections" must hold {SECTIONS[0]} to {SECTIONS[1]} sections.')
    else:
        for number, section in enumerate(sections, start=1):
            if not isinstance(section, dict) or set(section) - {'title', 'objectives', 'questions', 'covers'}:
                problems.append(f'Section {number} holds title, objectives, questions and covers only.')
                continue
            title = section.get('title')
            if not isinstance(title, str) or not title.strip() or len(title) > TITLE:
                problems.append(f'Section {number} needs a title of at most {TITLE} characters.')
            objectives = _strings(section.get('objectives'), OBJECTIVES, TEXT,
                                  f'Section {number} "objectives"', problems, 1)
            questions = _strings(section.get('questions'), ASKED, TEXT,
                                 f'Section {number} "questions"', problems, 1)
            covers = section.get('covers')
            if covers is not None and (not isinstance(covers, str) or len(covers) > TEXT):
                problems.append(f'Section {number} "covers" is one line of at most {TEXT} characters.')
            kept_sections.append({'title': ' '.join(str(title or '').split()),
                                  'objectives': objectives, 'questions': questions,
                                  'covers': ' '.join(str(covers or '').split())})
    terms = _strings(given.get('terms', []), TERMS, 80, '"terms"', problems)
    gaps = _strings(given.get('gaps', []), GAPS, TEXT, '"gaps"', problems)
    wanted = list(spec.get('documents') or [])
    documents = given.get('documents', [])
    kept_documents = []
    if not isinstance(documents, list):
        problems.append('"documents" must be a list of {"source", "covers"}.')
    else:
        for entry in documents:
            if not isinstance(entry, dict) or entry.get('source') not in wanted \
                    or not isinstance(entry.get('covers'), str) or not entry['covers'].strip() \
                    or len(entry['covers']) > TEXT:
                problems.append('Each entry of "documents" names a supplied source by its ID ('
                                + (', '.join(wanted) or 'none was supplied')
                                + f') and says what it covers in at most {TEXT} characters.')
                break
            kept_documents.append({'source': entry['source'], 'covers': ' '.join(entry['covers'].split())})
        missing = [ident for ident in wanted[:20]
                   if ident not in {entry['source'] for entry in kept_documents}]
        if missing and not problems:
            problems.append('Say what each supplied document covers: ' + ', '.join(missing)
                            + ' is missing from "documents".')
    kept = {'sections': kept_sections, 'terms': terms, 'documents': kept_documents, 'gaps': gaps}
    outcome = {'name': 'scan.overview', 'problems': list(problems)}
    return problems, [outcome], [], json.dumps(kept, indent=2, ensure_ascii=False) + '\n'


# --- the outline -------------------------------------------------------------------------

def _words(text: str) -> set:
    return {word for word in re.findall(r'[a-z0-9]+', text.lower())
            if len(word) > 3 and word not in STOP_WORDS}


def _same(a: str, b: str) -> bool:
    return ' '.join(a.lower().split()).rstrip('?.') == ' '.join(b.lower().split()).rstrip('?.')


def outline_from(scan: dict, asked) -> dict:
    """The outline the scan and the form give: the scan's sections, and each typed question
    attached to the section it shares the most words with, or listed separately."""
    sections = [{'id': f'section-{number}', 'title': section['title'],
                 'objectives': list(section['objectives']),
                 'questions': [{'text': text, 'from': 'scan'} for text in section['questions']]}
                for number, section in enumerate(scan['sections'], start=1)]
    separate = []
    for question in asked or ():
        held = next((item for section in sections for item in section['questions']
                     if _same(item['text'], question)), None)
        if held is not None:
            held['from'] = 'form'
            continue
        words, best, score = _words(question), None, 0.0
        for section in sections:
            if len(section['questions']) >= EDITED_ASKED:
                continue
            theirs = _words(' '.join([section['title'], *section['objectives'],
                                      *(item['text'] for item in section['questions'])]))
            shared = len(words & theirs) / max(1, len(words))
            if shared > score:
                best, score = section, shared
        if best is not None and score >= 0.25:
            best['questions'].append({'text': question, 'from': 'form'})
        else:
            separate.append({'text': question, 'from': 'form'})
    return {'schema': 1, 'sections': sections, 'separate': separate[:SEPARATE]}


def scanned(root: Path) -> bool:
    """Whether the scan is done: its overview and the outline drafted from it are here."""
    return isinstance(read(root), dict) and isinstance(home.read_json(root / SCAN, None), dict)


def read(root: Path) -> dict | None:
    value = home.read_json(root / OUTLINE, None)
    return value if isinstance(value, dict) and isinstance(value.get('sections'), list) else None


def keep(root: Path, text: str, handed: dict, asked) -> dict:
    """Keep the scan's overview and the outline drafted from it, under the training's state
    folder. The pages the scan saved are named, never kept as sources."""
    scan = json.loads(text)
    pages = [{'title': entry.get('title'), 'url': entry.get('url')}
             for entry in handed.get('sources') or () if not entry.get('offered')]
    scan.update(schema=1, at=home.now(), evidence=False, pages=pages[:SCAN_PAGES])
    workspace.write_atomic(root / SCAN, (json.dumps(scan, indent=2, ensure_ascii=False) + '\n').encode('utf-8'))
    return rebuild(root, asked)


def rebuild(root: Path, asked) -> dict:
    """The outline drafted again from the scan kept, with the questions the form has now."""
    scan = home.read_json(root / SCAN, None)
    if not isinstance(scan, dict):
        raise WorkspaceError('The quick scan is missing, so the outline cannot be drafted.')
    outline = outline_from(scan, asked)
    write(root, outline)
    return outline


def write(root: Path, outline: dict) -> None:
    workspace.write_atomic(root / OUTLINE, (json.dumps(outline, indent=2, ensure_ascii=False)
                                            + '\n').encode('utf-8'))


def forget(root: Path) -> None:
    """Take the scan and its outline away, so the scan runs again on Continue."""
    for name in (SCAN, OUTLINE):
        (root / name).unlink(missing_ok=True)


def edited(sent) -> dict:
    """An outline as the person edited it on the page, checked. Refuses with a sentence."""
    if not isinstance(sent, dict) or not isinstance(sent.get('sections'), list):
        raise WorkspaceError('Send the outline as its sections.')
    sections, separate = [], []
    if not 1 <= len(sent['sections']) <= EDITED_SECTIONS:
        raise WorkspaceError(f'Keep 1 to {EDITED_SECTIONS} sections.')
    for number, section in enumerate(sent['sections'], start=1):
        if not isinstance(section, dict):
            raise WorkspaceError(f'Section {number} cannot be read.')
        title = ' '.join(str(section.get('title') or '').split())
        if not title or len(title) > TITLE:
            raise WorkspaceError(f'Give section {number} a title of at most {TITLE} characters.')
        objectives = [' '.join(str(text).split()) for text in section.get('objectives') or []
                      if isinstance(text, str) and text.strip()]
        if len(objectives) > EDITED_OBJECTIVES or any(len(text) > TEXT for text in objectives):
            raise WorkspaceError(f'Section {number} keeps at most {EDITED_OBJECTIVES} objectives '
                                 f'of {TEXT} characters each.')
        questions = _questions(section.get('questions'), f'Section {number}')
        if not 1 <= len(questions) <= EDITED_ASKED:
            raise WorkspaceError(f'Give "{title}" 1 to {EDITED_ASKED} research questions.')
        sections.append({'id': f'section-{number}', 'title': title, 'objectives': objectives,
                         'questions': questions})
    separate = _questions(sent.get('separate') or [], 'The separate questions')
    if len(separate) > SEPARATE:
        raise WorkspaceError(f'Keep at most {SEPARATE} questions apart from the sections.')
    if sum(len(section['questions']) for section in sections) + len(separate) > PLAN_MOST:
        raise WorkspaceError(f'Research takes at most {PLAN_MOST} questions in all. Remove some.')
    return {'schema': 1, 'sections': sections, 'separate': separate}


def _questions(value, what: str) -> list[dict]:
    if not isinstance(value, list):
        raise WorkspaceError(f'{what}: send the questions as a list.')
    found = []
    for item in value:
        text = item.get('text') if isinstance(item, dict) else item
        if not isinstance(text, str) or not text.strip():
            continue
        text = ' '.join(text.split())
        if len(text) > TEXT:
            raise WorkspaceError(f'{what}: keep each question to {TEXT} characters.')
        said = item.get('from') if isinstance(item, dict) else None
        found.append({'text': text, 'from': said if said in FROMS else 'you'})
    return found


def view(root: Path, found, record: dict, expected: str) -> dict | None:
    """What the outline gate shows: the outline, what the scan found, and what it took."""
    outline, scan = read(root), home.read_json(root / SCAN, None)
    if outline is None or not isinstance(scan, dict):
        return None
    tries = [attempt for attempt in ((record.get('steps') or {}).get(STEP) or {}).get('attempts', ())
             if attempt.get('outcome') == 'kept']
    took = tries[-1] if tries else {}
    titles = {f's{number}': source.get('title') for number, source in enumerate(
        _offered(root, record), start=1)}
    return {'mode': 'outline', 'expected': expected,
            'sections': outline['sections'], 'separate': outline.get('separate') or [],
            'scan': {'terms': scan.get('terms') or [], 'gaps': scan.get('gaps') or [],
                     'documents': [{**entry, 'title': titles.get(entry['source']) or entry['source']}
                                   for entry in scan.get('documents') or []],
                     'pages': scan.get('pages') or [], 'most_pages': SCAN_PAGES,
                     'covers': [section.get('covers') or '' for section in scan.get('sections') or []],
                     'seconds': took.get('seconds'), 'dollars': took.get('dollars'),
                     'note': NOT_EVIDENCE},
            'limits': {'sections': EDITED_SECTIONS, 'questions': EDITED_ASKED,
                       'objectives': EDITED_OBJECTIVES, 'separate': SEPARATE, 'title': TITLE,
                       'text': TEXT, 'all': PLAN_MOST},
            'levels': list(found.session['levels'])}


def _offered(root: Path, record: dict) -> list:
    """The documents the scan was offered, in order, for naming them by title. Best effort."""
    try:
        from runner import documents
        from studio_core import research_sources
        return [*documents.sources(root)[1],
                *research_sources.sources(root, record.get('research_inputs'))[1]]
    except Exception:  # noqa: BLE001  a title is a nicety; the source ID still says which
        return []


# --- research from the approved outline --------------------------------------------------

def items(outline: dict) -> list[dict]:
    """The research plan's questions: each section's, naming its section, then those kept
    apart as a section of their own."""
    listed = []
    groups = [(section['id'], section['title'], section['questions']) for section in outline['sections']]
    if outline.get('separate'):
        groups.append((*OTHER, outline['separate']))
    for number, (ident, title, questions) in enumerate(groups, start=1):
        for count, question in enumerate(questions, start=1):
            listed.append({'id': f's{number}-q{count}', 'question': question['text'],
                           'public_query': None, 'claim': None,
                           'section': ident, 'section_title': title})
    return listed


def plan_text(root: Path, found) -> str:
    """The research plan the approved outline gives, in the shape research takes."""
    from runner import documents, worker_tools
    from studio_core import research_sites
    outline = read(root)
    if outline is None:
        raise WorkspaceError('The approved training outline is missing. Restore it, or change '
                             'the settings to scan again.')
    from runner import pipeline
    scope = ('supplied-only' if found.scope == 'supplied-only'
             else research_sites.plan_scope(found.research_from))
    plan = dict(topic=pipeline.answers(root).get('topic') or found.session['title'],
                purpose='planning', scope=scope, sources=documents.sources(root)[0],
                items=items(outline))
    checked = worker_tools.check_research_plan(plan, most=PLAN_MOST)
    if checked['problems']:
        raise WorkspaceError(checked['problems'][0])
    return json.dumps(plan, indent=2, ensure_ascii=False) + '\n'


def outline_text(outline: dict) -> str:
    """The approved outline in words, for research's scope and the blueprint's input."""
    lines = []
    for number, section in enumerate(outline['sections'], start=1):
        lines.append(f"{number}. {section['title']}")
        lines += [f'   Objective: {text}' for text in section.get('objectives') or ()]
        lines += [f"   Research question: {item['text']}" for item in section['questions']]
    if outline.get('separate'):
        lines.append(f'{len(outline["sections"]) + 1}. {OTHER[1]}')
        lines += [f"   Research question: {item['text']}" for item in outline['separate']]
    return '\n'.join(lines)


def scope_text(root: Path) -> str:
    """What research's task scope says of the approved outline: the report is organized by
    its sections, in their order."""
    outline = read(root)
    if outline is None:
        return ''
    return ('\nApproved training outline. Organize the report by these training sections, in '
            'this order, and keep each finding with the section whose question it answers:\n'
            + outline_text(outline))


def blueprint_input(root: Path) -> str | None:
    outline = read(root)
    if outline is None:
        return None
    return ('# The approved training outline\n\nThe person approved these sections before the '
            'research was done. Lay the modules out as these sections, in this order, one module '
            'for each, unless the time limit cannot hold them; then join neighbouring sections '
            'and say so under open gaps.\n\n' + outline_text(outline) + '\n')


# --- an older training's explicit move here ------------------------------------------------

SWITCH_WORDS = ('Use the outline-first flow: a quick scan of your sources drafts the training '
                'outline, you check and edit it, and research then fills in each section you '
                'approve, up to three at a time.')
SWITCH_DISCARDS = ('Switching discards the research plan and any research not yet accepted '
                   'into a finished report{took}. It cannot be undone. Nothing starts until you '
                   'press Continue.')
SWITCHED = ('This training now uses the outline-first flow. Nothing starts until you press '
            'Continue. Continue runs a quick scan and drafts the training outline for you to '
            'check before any research starts.')


def offer(engine, root: Path, record: dict, state: str, mine: bool) -> dict | None:
    """What an older desk training stopped before its research was accepted is offered: a
    move to this flow, with what it discards, or None. Never offered once research is
    accepted, a material is drafted, a deck is begun, or research has a job unconfirmed."""
    from runner import pipeline, settings_change, training_plan
    try:
        if on(record) or not record.get('research_contract'):
            return None
        why = settings_change.refusal(record, state, mine, engine._desk_change_busy(root, record))
        if why is not None:
            return None
        session = workspace.load(root)
        statuses = workspace.statuses(root, session)
        if statuses.get('research') == 'approved' or pipeline.begun(session, record) \
                or any(workspace.split(name)[0] == 'blueprint' and status != 'not-started'
                       for name, status in statuses.items()):
            return None
        if any(name in settings_change.locked(root, session, record)
               for name in settings_change.RESEARCHED):
            return None
        lost = settings_change._discarded(record, 'replanned')
        took = (', which took ' + settings_change._took(lost)) if lost['tries'] else ''
        return {'words': SWITCH_WORDS, 'discards': lost,
                'confirm': SWITCH_DISCARDS.format(took=took),
                'expected': settings_change.revision(root, session, record),
                'plan_first': training_plan.enabled(record)}
    except (WorkspaceError, OSError, ValueError):
        return None


def switch(engine, path, expected, confirmed) -> dict:
    """Move an older stopped training to this flow, as the person chose with the offer's
    words before them. Refused for an outdated offer, and without the confirmation."""
    from runner import settings_change
    root = engine._held(path)
    shown = engine.view(root)
    with engine.files:
        record = engine._load(root)
        found = offer(engine, root, record, shown['state'], shown['mine'])
        if found is None:
            raise WorkspaceError('This training cannot move to the outline-first flow now. '
                                 'Only one stopped before its research was accepted can.')
        if expected != found['expected']:
            raise WorkspaceError(settings_change.OUTDATED)
        if confirmed is not True:
            raise WorkspaceError('Read what switching discards, then confirm.')
        engine._edits_first(root)
        session = workspace.load(root)
        if (root / workspace.artifact(root, session, 'research-plan')['file']).is_file():
            settings_change._set_aside(root, 'research-plan')
        record = engine._load(root)
        record.update(schema=RECORD_SCHEMA,
                      training_plan={'schema': PLAN_SCHEMA, 'revision': 0})
        record['research'] = None
        record.setdefault('answers', {}).pop('research-plan', None)
        if (record.get('question') or {}).get('step') == 'research-plan':
            record['question'] = None
        if record.get('documents'):
            record['documents']['later'] = []
        (record.get('research_execution') or {}).pop('progress', None)
        forget(root)
        at = home.now()
        record.setdefault('flow_changes', []).append({'at': at, 'to': 'outline-first',
                                                      'discards': found['discards']})
        record['problem'] = {'state': 'waiting', 'step': None, 'action': 'retry',
                             'label': 'Continue', 'at': at, 'what': SWITCHED,
                             'kept': settings_change.KEPT}
        record['halt'] = None
        engine._store(root, record)
        engine._commit(root, 'use the outline-first flow: scan, outline, then research each section')
    return engine.view(root)
