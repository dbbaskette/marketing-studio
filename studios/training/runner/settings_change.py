"""Change settings: a training's start form, filled in with what it was started with, changed
while its run is not working, and saved in one go (#296).

What a change does depends on whether research has a finished, accepted report:

- Without one, research that was not accepted is discarded. A change to what research reads
  or asks (the topic, audience, purpose, research questions, sources, external search or
  sites) plans it again; any other change to the research task keeps the plan, and research
  starts over, because Harness Research's task names every setting on the form (a new task
  is a new collection: the earlier one is left as it was, never mixed in). A change the task
  does not name (the deck's brand, delivery or walkthrough) leaves research to carry on.
- With one, the report is kept unless the person chooses Research again with the new
  settings. Changes that do not reach research mark only what depends on them: on the desk
  what is out of date is held for the person to Update or keep, so a material they marked
  ready is never changed without their say.

The form is checked against the revision it was read at (`revision`), the save holds the
engine's files lock only while it writes, and it is refused while assistant work runs. The
save writes intake.md, the session and run records and the research inputs together, restores
them all if any part fails, and commits them as "change the training's settings: …". Nothing
starts until the person presses Continue.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path

import home
import workspace
from workspace import WorkspaceError

import runner  # noqa: F401  puts the core on the import path
from runner import drafts, pipeline, training_plan, practice_intent
from studio_core import research_contract, research_session as research_parallel
from studio_core import research_sites, research_sources, stops
from studio_core.research_view import series

# A run that is not working: stopped, failed or waiting for a decision. Paused counts once
# nothing is in hand (a pause that waits for a step to finish is busy): it is a stop that
# keeps its place. A finished training is not turned back into work by a plain save.
ALLOWED = ('failed', 'stopped', 'waiting', 'paused')
FINISHED = ('This training is finished, so its settings stay as they are. Start a new '
            'training to make it again with other settings.')
RESEARCHED = ('topic', 'audience', 'purpose', 'research_questions', 'sources', 'search')
# What the source panel changes: what research reads, where it may search, and how many
# research workers it uses, which is how the work is done and not what is researched.
SOURCE_KINDS = ('sources', 'search', 'workers')
NAMES = {'topic': 'the topic', 'audience': 'the audience', 'purpose': 'what it is for',
         'time_limit': 'the time limit', 'levels': 'the levels', 'brief_kind': 'the brief',
         'research_questions': 'the research questions', 'sources': 'the sources',
         'search': 'where research may search', 'workers': 'the research workers',
         'materials': 'the materials', 'yoodli': 'the Yoodli scenarios',
         'deck_target': 'the slide deck', 'brand': 'the deck’s brand',
         'delivery': 'how the deck is used', 'walkthrough': 'the slide walkthrough', 'scenario_plan': 'the scenario choices'}
DECK_FIELDS = ('deck_target', 'brand', 'delivery', 'walkthrough')
OUTDATED = ('These settings changed since this form was opened. Close it and open Change '
            'settings again; nothing was changed.')
WORKING = ('It is working now. Stop it, or wait until it stops for you, then change its '
           'settings.')
OLDER = ('This training was started before its settings could be changed, so they stay as '
         'they are. Start a new training to choose others.')
CONVERSATION = 'It is being worked on in conversation, so its settings are changed there.'
THEIRS = 'Someone else runs this training, so only they can change its settings.'
NOTHING = 'Nothing has changed, so there is nothing to save.'
CONFIRM = ('Saving this discards research and cannot be undone. Read what it discards, then '
           'confirm.')
DECK_BEGUN = ('A deck has been begun for this training, so how it is made stays as it is. '
              'Change the deck on the desk.')
SERIAL_DRAFT = ('This training’s research uses the earlier research workflow, which carries '
                'its unfinished draft into the next try, so what it researches stays as it is '
                'until its report is finished. Its other settings can still be changed.')
UNCONFIRMED = ('An earlier research job has not confirmed that it ended, so what research '
               'reads stays as it is. Try again first; earlier work is kept.')
MATERIAL_NAMES = {'document': 'learner guide', 'brief': 'reference brief',
                  'scenario': 'practice scenarios'}
MADE_STAYS = ('The {it} has work in it, so it stays. Its files are kept.')
AFTER_BLUEPRINT = ('The teaching blueprint is written, and it plans the practice, so practice '
                   'scenarios stay as they were chosen. The learner guide and the reference '
                   'brief can still be added.')
CHANGED_AWAY = 'Left out when the training’s settings were changed.'
PLAIN = ('This training was started without levels, so it stays one training without levels.')
WAITS = 'Nothing starts until you press Continue.'
KEPT = 'Everything else made so far is kept as it was.'
RESEARCH_STEPS = ('research-plan', 'research-start', 'research', 'research-report',
                  *research_contract.LEGACY_JOBS)


# --- what can be changed -----------------------------------------------------------------

def refusal(record: dict, state: str, mine: bool, busy: bool) -> str | None:
    """Why Change settings is not offered now, in a sentence, or None when it is."""
    if not drafts.on_desk(record) or not record.get('research_contract') \
            or record.get('opened_on_desk') or record.get('unfinished_migration'):
        return OLDER
    if drafts.in_conversation(record):
        return CONVERSATION
    if not mine:
        return THEIRS
    if state == 'working' or busy:
        return WORKING
    if state == 'done':
        return FINISHED
    return None if state in ALLOWED else WORKING


def _brand(session: dict) -> dict | None:
    chosen = pipeline.brand_of(session)
    return {'brand': chosen[0], 'variant': chosen[1]} if chosen else None


def _time(said: dict) -> str | None:
    kept = (said.get('time limit') or '').strip()
    return None if kept in ('', 'None given') else kept


def values(root: Path, session: dict, record: dict) -> dict:
    """What the training was started with, as the start form says it now."""
    said = pipeline.answers(root)
    looks = pipeline.research_of(record)
    return {'topic': said.get('topic') or session['title'], 'audience': said.get('audience') or '',
            'purpose': said.get('purpose') or '', 'time_limit': _time(said),
            'levels': list(session['levels']), 'brief_kind': session['settings']['brief_kind'],
            'materials': [stage for stage in pipeline.MATERIALS
                          if stage in session['settings']['stages']],
            'yoodli': 'yoodli' in session['settings']['stages'],
            'research_questions': list(record.get('research_questions') or []),
            'research_from': {key: looks[key] for key in ('documents', 'sites', 'web')},
            'deck_target': session['settings']['deck_target'], 'brand': _brand(session),
            'delivery': pipeline.delivery_of(session),
            'walkthrough': pipeline.walkthrough_of(session),
            'scenario_plan': practice_intent.of(session)}


def _accepted(root: Path, session: dict) -> bool:
    return workspace.statuses(root, session).get('research') == 'approved'


def _serial_draft(root: Path, record: dict) -> bool:
    """Whether research done the earlier, serial way holds a draft its next try carries on."""
    if research_parallel.protocol(record):
        return False
    try:
        return (research_contract.working_case(root / research_contract.CASE)
                / '.harness-research/synthesis.json').is_file()
    except ValueError:
        return True


def _made_levels(root: Path, session: dict) -> list[str]:
    """The levels with work in them, which stay: their folders hold what was made."""
    return [level for level in session['levels'] if workspace.level_work(root, level)]


def _stage_made(root: Path, session: dict, stage: str) -> bool:
    """Whether any file of a material (or the blueprint) has been written, at any level."""
    return any(workspace.split(name)[0].partition(':')[0] == stage and _made(root, session, name)
               for name in workspace.artifact_names(root, session))


def _made_materials(root: Path, session: dict) -> list[str]:
    return [stage for stage in (*pipeline.MATERIALS, 'yoodli') if _stage_made(root, session, stage)]


def locked(root: Path, session: dict, record: dict) -> dict:
    """The fields that cannot be changed safely now, each with why."""
    found = {}
    if pipeline.begun(session, record):
        found.update({name: DECK_BEGUN for name in DECK_FIELDS})
    if not session['levels']:
        found['levels'] = PLAIN
    accepted = _accepted(root, session)
    try:
        unresolved = research_parallel.unresolved(root)
    except ValueError as error:
        unresolved = str(error)
    if unresolved:
        why = unresolved if isinstance(unresolved, str) else UNCONFIRMED
        found.update({name: why for name in RESEARCHED})
    elif not accepted and _serial_draft(root, record):
        found.update({name: SERIAL_DRAFT for name in RESEARCHED})
    return found


def revision(root: Path, session: dict, record: dict) -> str:
    """What a form is checked against: every saved value it shows, and where research is."""
    entries = session['artifacts']
    shown = {'intake': workspace.sha256_file(root / 'intake.md'),
             'levels': session['levels'], 'settings': session['settings'],
             'artifacts': {name: (entries.get(name) or {}).get('sha256')
                           for name in ('research-plan', 'research')},
             'report': workspace.sha256_file(root / pipeline.REPORT),
             'record': {key: record.get(key) for key in (
                 'research_from', 'research_questions', 'research_inputs', 'documents',
                 'research', 'problem', 'halt', 'question', 'settings_changes')}}
    return hashlib.sha256(json.dumps(shown, sort_keys=True, default=str).encode()).hexdigest()


def _documents(engine, root: Path) -> int:
    """The readable documents research reads beside the source panel's own: the Document
    Library's and those added on the desk."""
    return sum(1 for entry in engine.documents.listed(root) if entry.get('readable'))


def form(engine, path) -> dict:
    """The start form of a training, filled in with what it was started with: its values,
    what cannot be changed and why, the revision a save is checked against, and what
    research has to lose."""
    root = engine._held(path)
    shown = engine.view(root)
    with engine.files:
        record = engine._load(root)
        session = workspace.load(root)
        why = refusal(record, shown['state'], shown['mine'], engine._desk_change_busy(root, record))
        accepted = _accepted(root, session)
        return {'path': str(root), 'title': session['title'], 'may': why is None, 'why': why,
                'revision': revision(root, session, record),
                'values': values(root, session, record),
                'locked': locked(root, session, record),
                'made_levels': _made_levels(root, session),
                'made_materials': _made_materials(root, session),
                'blueprint_made': _stage_made(root, session, 'blueprint'),
                'documents': _documents(engine, root),
                'practice': 'scenario' in pipeline.wanted(session),
                'research': {'accepted': accepted,
                             'discards': _discarded(record, 'again' if accepted else 'replanned')}}


def sources(engine, path) -> dict:
    """A source draft holding what the training's research reads now, for the shared source
    panel to change. Nothing of the training changes until the form is saved."""
    root = engine._held(path)
    with engine.files:
        record = engine._load(root)
        shown = engine.view(root)
        why = refusal(record, shown['state'], shown['mine'], engine._desk_change_busy(root, record))
        if why:
            raise WorkspaceError(why)
    from studio_core import studios_config
    shared, _ = studios_config.read()
    store = research_sources.Sources(engine.space().root / '.research-sources')
    try:
        made = store.from_inputs(root, record.get('research_inputs'), pipeline.research_of(record),
                                 sites=research_sites.defaults(shared))
    except (OSError, ValueError, KeyError) as error:
        raise WorkspaceError(f'The sources this training reads could not be read: {error}') from None
    _forget_draft(store, root, keep=made['id'])
    return made


def _drafts_file(store, root: Path) -> Path:
    return store.root / 'settings' / (root.name + '.json')


def _forget_draft(store, root: Path, keep: str | None = None) -> None:
    """Take away the source draft an earlier Change settings sheet of this training opened,
    and remember `keep` as the one open now. Only drafts this sheet made are ever taken."""
    marker = _drafts_file(store, root)
    try:
        earlier = json.loads(marker.read_text()).get('id')
    except (OSError, ValueError, AttributeError):
        earlier = None
    with store.lock:
        if earlier and earlier != keep:
            try:
                shutil.rmtree(store.folder(earlier), ignore_errors=True)
            except ValueError:
                pass
        marker.parent.mkdir(parents=True, exist_ok=True)
        if keep:
            marker.write_text(json.dumps({'id': keep}))
        else:
            marker.unlink(missing_ok=True)


# --- what a change does ------------------------------------------------------------------

def _family(name: str) -> bool:
    return name in RESEARCH_STEPS or name.startswith('research:')


def _since(record: dict, outcome: str) -> str:
    """Where discarded research begins: the last change of settings, and for research not
    accepted, the last report kept."""
    marks = [change.get('at') or '' for change in record.get('settings_changes') or ()]
    if outcome != 'again':
        marks += [attempt.get('ended_at') or '' for attempt in
                  pipeline.tries(record, 'research-report').get('attempts', ())
                  if attempt.get('outcome') == 'kept']
    return max(marks, default='')


def _discarded(record: dict, outcome: str) -> dict:
    """The research tries a change discards, from the run record: how many, and the time and
    money they took. The runner's own steps (handing the plan over, a plan written from the
    form) are not tries. The plan's tries count only when it is planned again."""
    since, tries, seconds, dollars = _since(record, outcome), 0, 0.0, None
    for name, entry in (record.get('steps') or {}).items():
        if not isinstance(entry, dict) or not _family(name) or name in ('research-start', 'research-report'):
            continue
        if name == 'research-plan' and outcome == 'restarted':
            continue
        for attempt in entry.get('attempts') or ():
            if attempt.get('runner') or (attempt.get('started_at') or '') < since:
                continue
            tries += 1
            seconds += attempt.get('seconds') or 0
            if attempt.get('dollars') is not None:
                dollars = (dollars or 0) + attempt['dollars']
    return {'tries': tries, 'seconds': round(seconds, 1),
            'dollars': None if dollars is None else round(dollars, 4)}


def _took(found: dict) -> str:
    return research_contract.took(found['seconds'], found['dollars']) or 'no recorded time or money'


def _intake(form: dict) -> str:
    return pipeline.intake_text(form)


def _lines(text: str) -> dict:
    found, heading = {}, None
    for line in text.splitlines():
        if line.startswith('## '):
            heading = line[3:].strip()
            found[heading] = []
        elif heading is not None:
            found[heading].append(line)
    return {heading: '\n'.join(lines).strip() for heading, lines in found.items()}


def _checked(engine, root: Path, session: dict, record: dict, sent: dict) -> tuple[dict, dict | None]:
    """The new values, each checked as the start form's are, and the source panel's prepared
    draft when its sources were sent."""
    if not isinstance(sent, dict):
        raise WorkspaceError('Send the changed settings as a form.')
    now = values(root, session, record)
    given = {key: sent.get(key, now[key]) for key in now if key != 'research_from'}
    prepared = None
    reference = sent.get('research_inputs')
    if reference is not None:
        try:
            prepared = research_sources.prepare_start(engine.space().root, reference,
                                                      primary=_documents(engine, root) > 0)
        except ValueError as error:
            raise WorkspaceError(str(error)) from None
        given['research_from'] = prepared['research_from']
    else:
        given['research_from'] = now['research_from']
    # A brand that is not changing is not checked against the brand skill here now: one
    # dropped or renamed since, or none on a deck training, never blocks another change.
    same = (given['deck_target'] == now['deck_target'] and _brand_sent(given['brand'])
            == _brand_sent(now['brand']))
    checked = pipeline.check_form({
        'title': session['title'], **given,
        'copies': session['settings'].get('copies') or [], 'flow': 'desk'}, None if same else engine.brands())
    # The brand as the session keeps it ("brand/variant"), and as the form shows it.
    if checked['deck_target'] is None:
        checked['brand'] = None
    brand, _, variant = (checked['brand'] or '').rpartition('/')
    checked['brand_value'] = {'brand': brand, 'variant': variant or None} if brand else None
    return checked, prepared


def _brand_sent(value) -> tuple | None:
    if not isinstance(value, dict) or not value.get('brand'):
        return None
    return (value.get('brand'), value.get('variant') or None)


def _sources_changed(root: Path, record: dict, prepared: dict | None, chosen: dict) -> set:
    """What the source panel's draft changes of what the training's research does now:
    `sources` (what it reads, and its focus), `search` (whether and where it may search) and
    `workers` (how many research workers it uses)."""
    if prepared is None:
        return set()
    found = set()
    looked = pipeline.research_of(record)
    if {key: looked[key] for key in ('sites', 'web')} != {key: chosen[key] for key in ('sites', 'web')}:
        found.add('search')
    saved = record.get('research_inputs') or {}
    rows = []
    if saved:
        try:
            rows = json.loads((root / 'sources/research-inputs/manifest.json').read_text())['sources']
        except (OSError, ValueError, KeyError, TypeError):
            rows = []
    before = sorted((row.get('id'), row.get('sha256'), row.get('original_sha256')) for row in rows)
    after = sorted((s.get('id'), s.get('sha256'), s.get('original_sha256')) for s in prepared['sources'])
    # A training started without the source panel reads with its defaults: 3 workers, no focus.
    if before != after or (saved.get('focus') or '') != (prepared['focus'] or '') \
            or bool(looked['documents']) != bool(chosen['documents']):
        found.add('sources')
    if (saved.get('workers') or 3) != prepared['workers']:
        found.add('workers')
    return found


def _streams(engine, root: Path, workers: int) -> int:
    """How many research areas Harness Research's collection splits the plan into, which its
    task's digest names: a change of workers that changes it is a new collection."""
    plan = home.read_json(root / pipeline.PLAN, {})
    asked = len(plan.get('items') or []) if isinstance(plan, dict) else 0
    limit = min(3, getattr(engine, 'at_once', 3), max(1, int(workers or 3)))
    return min(3, max(1, limit), max(1, asked))


def plan(engine, root: Path, session: dict, record: dict, sent: dict) -> dict:
    """What a change would do, worked out from the form without changing anything."""
    checked, prepared = _checked(engine, root, session, record, sent)
    now = values(root, session, record)
    new = {'topic': checked['topic'], 'audience': checked['audience'],
           'purpose': checked['purpose'], 'time_limit': checked['time_limit'],
           'levels': checked['levels'], 'brief_kind': checked['brief_kind'],
           'research_questions': checked['research_questions'],
           'materials': checked['materials'], 'yoodli': checked['yoodli'],
           'scenario_plan': checked.get('scenario_plan', practice_intent.of(session)),
           'deck_target': checked['deck_target'], 'brand': checked['brand_value'],
           'delivery': checked['delivery'] if checked['deck_target'] else now['delivery'],
           'walkthrough': checked['walkthrough'] if checked['deck_target'] else now['walkthrough']}
    changed = [name for name in new if new[name] != now[name]]
    kinds = _sources_changed(root, record, prepared, checked['research_from'])
    changed += [kind for kind in SOURCE_KINDS if kind in kinds]
    stop = locked(root, session, record)
    for name in changed:
        if name in stop:
            raise WorkspaceError(stop[name])
    if 'levels' in changed:
        dropped = [level for level in _made_levels(root, session) if level not in new['levels']]
        if dropped:
            raise WorkspaceError(f'Level {series(dropped)} has work in it, so it stays. Its '
                                 'materials are kept.')
        if not new['levels']:
            raise WorkspaceError('A training with levels keeps at least one level.')
    if 'materials' in changed or 'yoodli' in changed:
        made = _made_materials(root, session)
        for stage in (*pipeline.MATERIALS, 'yoodli'):
            wanted = new['yoodli'] if stage == 'yoodli' else stage in new['materials']
            if stage in made and not wanted:
                raise WorkspaceError(MADE_STAYS.format(
                    it='Yoodli scenarios' if stage == 'yoodli' else MATERIAL_NAMES[stage]))
        if ('scenario' in new['materials']) != ('scenario' in now['materials']) \
                and _stage_made(root, session, 'blueprint'):
            raise WorkspaceError(AFTER_BLUEPRINT)
    accepted = _accepted(root, session)
    again = sent.get('research_again') is True
    researched = [name for name in changed if name in RESEARCHED]
    intake = _intake({**checked, 'research_from': checked['research_from']})
    before = (root / 'intake.md').read_text(encoding='utf-8') if (root / 'intake.md').is_file() else ''
    differs = [heading for heading, text in _lines(intake).items() if _lines(before).get(heading) != text]
    # The research task names the materials wanted, so a change of them is a new task.
    stages = ('deck_target' in changed and (now['deck_target'] is None) != (new['deck_target'] is None)) \
        or 'materials' in changed or 'yoodli' in changed
    saved_workers = (record.get('research_inputs') or {}).get('workers') or 3
    split = 'workers' in changed and research_parallel.protocol(record) and \
        _streams(engine, root, saved_workers) != _streams(engine, root, prepared['workers'])
    tasked = bool(differs or stages or researched or split)
    # Research again is fresh research only when research is given something new: with the
    # same task and sources Harness Research would find its accepted collection and keep it.
    unchanged_again = accepted and again and not tasked
    if accepted:
        outcome = 'again' if again and tasked else 'kept'
    elif researched:
        outcome = 'replanned'
    elif tasked and research_parallel.protocol(record):
        outcome = 'restarted'
    else:
        outcome = 'continues'
    lost = _discarded(record, outcome) if outcome in ('again', 'replanned', 'restarted') else None
    words = _words(root, session, record, changed, outcome, lost, researched, differs, new, now)
    if unchanged_again:
        words.insert(1, 'Nothing research reads or is given changed, so researching again would '
                        'repeat it: the finished report is kept.')
    if training_plan.enabled(record) and (record['training_plan'].get('approved')) and (
            differs or 'levels' in changed or outcome == 'again'):
        words.insert(-1, 'You approved the topics and teaching plan; it is prepared again for '
                         'you to check before materials are built.')
    return {'changed': changed, 'names': [NAMES[name] for name in changed],
            'research': outcome, 'discards': lost,
            'confirm': bool(outcome == 'again' or (lost and lost['tries'])),
            'words': words, 'checked': checked, 'prepared': prepared, 'intake': intake,
            'differs': differs, 'new': new, 'now': now}


def _made(root: Path, session: dict, name: str) -> bool:
    try:
        return (root / workspace.artifact(root, session, name)['file']).is_file()
    except WorkspaceError:
        return False


def _ready(root: Path, session: dict) -> set:
    return {name for name, status in workspace.person_statuses(root, session).items()
            if status == 'approved' and (session.get('desk_ready') or {}).get(name)}


def _words(root, session, record, changed, outcome, lost, researched, differs, new, now) -> list[str]:
    said = ['You changed ' + series([NAMES[name] for name in changed]) + '.']
    took = _took(lost) if lost else ''
    if outcome == 'again':
        said.append('The finished research report is set aside, and research is planned and '
                    f'done again with the new settings. The research being replaced took {took}. '
                    'This cannot be undone.')
    elif outcome == 'replanned':
        said.append('Research that has not been accepted into a finished report is discarded, '
                    'and research is planned again with the new settings.'
                    + (f' The discarded tries took {took}. This cannot be undone.'
                       if lost['tries'] else ' No research has been tried yet, so nothing is lost.'))
    elif outcome == 'restarted':
        said.append('The research plan is kept. Research that has not been accepted into a '
                    'finished report starts again, because the research is given every setting '
                    'on this form.'
                    + (f' The discarded tries took {took}. This cannot be undone.'
                       if lost['tries'] else ' No research has been tried yet, so nothing is lost.'))
    elif outcome == 'continues':
        said.append('Research carries on as it was: Continue tries it again.')
    else:
        said.append('The finished research report is kept.' + (
            ' It was researched with the earlier ' + series([NAMES[name].removeprefix('the ')
                                                              for name in researched])
            + '. Choose Research again with the new settings to research it again.'
            if researched else ''))
    ready = _ready(root, session)
    after = []
    if outcome == 'again':
        after = [name for name in workspace.downstream(root, session, 'research')
                 if _made(root, session, name)]
    elif any(heading not in ('Levels', 'Brief') for heading in differs) or \
            (outcome == 'kept' and researched):
        after = [name for name in workspace.downstream(root, session, 'intake')
                 if name not in ('research-plan', 'research') and _made(root, session, name)]
    if 'scenario_plan' in changed:
        after += [name for level in session['levels'] or [None]
                  for name in [workspace.qualify('blueprint', level),
                               *workspace.downstream(root, session, workspace.qualify('blueprint', level))]
                  if _made(root, session, name)]
        proposed = {**session, 'settings': {**session['settings'], 'scenario_plan': new['scenario_plan']}}
        after += [name for name in workspace.artifact_names(root, session)
                  if workspace.split(name)[0].startswith(('scenario:', 'yoodli:'))
                  and _made(root, session, name)
                  and workspace.inputs(root, session, name) != workspace.inputs(root, proposed, name)]
        after = list(dict.fromkeys(after))
    if after:
        marked = [name for name in after if name in ready]
        said.append('Out of date afterwards: ' + series([workspace.label(name) for name in after])
                    + '. Each waits on the desk for you to update it or keep it as it is.'
                    + (' You marked ' + series([workspace.label(name) for name in marked])
                       + ' ready; it stays as it is until you decide.' if marked else ''))
    if 'brief_kind' in changed:
        briefs = [workspace.qualify('brief', level) for level in session['levels'] or [None]]
        made = [name for name in briefs if _made(root, session, name)]
        if made:
            marked = [name for name in made if name in ready]
            kind = 'comparison' if new['brief_kind'] == 'competitive' else 'product'
            said.append(f'The brief is written again as a {kind} brief'
                        + (' at ' + series(level for level in session['levels']) if session['levels'] else '')
                        + '.' + (' The one you marked ready stays in its file but is no longer '
                                 'the training’s brief.' if marked else ''))
    if 'materials' in changed or 'yoodli' in changed:
        def chosen(held):
            return [MATERIAL_NAMES[stage] for stage in held['materials']] \
                + (['Yoodli scenarios'] if held['yoodli'] else [])
        more = [name for name in chosen(new) if name not in chosen(now)]
        fewer = [name for name in chosen(now) if name not in chosen(new)]
        if more:
            said.append('Also made now: ' + series(more) + '.')
        if fewer:
            said.append('No longer made: ' + series(fewer) + '. Nothing of '
                        + ('it' if len(fewer) == 1 else 'them') + ' had been written.')
    added = [level for level in new['levels'] if level not in now['levels']]
    dropped = [level for level in now['levels'] if level not in new['levels']]
    if added:
        said.append('Materials are made for level ' + series(added) + '.')
    if dropped:
        said.append('Level ' + series(dropped) + ' is left out.')
    said.append(WAITS)
    return said


# --- the save ----------------------------------------------------------------------------

class _Kept:
    """What a save may change, copied first, so a save that fails puts it all back."""

    FILES = ('intake.md', f'{workspace.STATE_DIR}/session.json', f'{workspace.STATE_DIR}/run.json',
             pipeline.PLAN, pipeline.REPORT)
    FOLDERS = ('sources/research-inputs',)

    def __init__(self, root: Path):
        self.root, self.folder = root, Path(tempfile.mkdtemp(prefix='training-settings-'))
        self.files = {}
        for name in self.FILES:
            path = root / name
            self.files[name] = path.read_bytes() if path.is_file() else None
        for name in self.FOLDERS:
            if (root / name).is_dir():
                shutil.copytree(root / name, self.folder / name)

    def restore(self) -> None:
        for name, data in self.files.items():
            path = self.root / name
            if data is None:
                path.unlink(missing_ok=True)
            else:
                workspace.write_atomic(path, data)
        for name in self.FOLDERS:
            shutil.rmtree(self.root / name, ignore_errors=True)
            if (self.folder / name).is_dir():
                shutil.copytree(self.folder / name, self.root / name)

    def close(self) -> None:
        shutil.rmtree(self.folder, ignore_errors=True)


def _install(root: Path, prepared: dict) -> dict:
    """Keep the source panel's draft as the training's research inputs, and take away the
    captures no longer read."""
    kept = research_sources.install(prepared, root)
    folder = root / 'sources/research-inputs'
    manifest = json.loads((folder / 'manifest.json').read_text())
    used = {Path(row[key]).name for row in manifest['sources'] for key in ('file', 'original')}
    for path in folder.iterdir():
        if path.is_file() and path.name not in used | {'manifest.json', '.gitignore'}:
            path.unlink()
    return kept


def _set_aside(root: Path, name: str) -> None:
    """Keep a copy of a file in the training's history, then take it away so its step makes
    it again."""
    path = root / workspace.artifact(root, workspace.load(root), name)['file']
    if path.is_file():
        workspace.snapshot(root, name, path)
        path.unlink()


def save(engine, path, sent: dict, *, preview: bool = False) -> dict:
    """Work out what a change does (`preview`), or save it. A save is refused for a form read
    at an earlier revision, while the run works, and for a change that discards research but
    is not confirmed."""
    root = engine._held(path)
    shown = engine.view(root)
    with engine.files:
        record = engine._load(root)
        why = refusal(record, shown['state'], shown['mine'], engine._desk_change_busy(root, record))
        if why:
            raise WorkspaceError(why)
        session = workspace.load(root)
        if not isinstance(sent, dict) or sent.get('expected') != revision(root, session, record):
            raise WorkspaceError(OUTDATED)
        found = plan(engine, root, session, record, sent)
        if not found['changed']:
            raise WorkspaceError(NOTHING)
        if preview:
            return {key: found[key] for key in ('changed', 'names', 'research', 'discards',
                                                'confirm', 'words')}
        if found['confirm'] and sent.get('confirmed') is not True:
            raise WorkspaceError(CONFIRM)
        engine._edits_first(root)
        kept = _Kept(root)
        try:
            summary = _apply(engine, root, found)
        except BaseException:
            kept.restore()
            raise
        finally:
            kept.close()
    if found['prepared'] is not None:
        try:
            _forget_draft(research_sources.Sources(engine.space().root / '.research-sources'), root)
        except Exception:  # noqa: BLE001  the change is saved; a draft left is only tidied later
            pass
    try:
        shown = engine.view(root)
    except Exception:  # noqa: BLE001  the change is saved; the page reads the run again
        shown = {}
    return {**shown, 'changed_settings': summary}


def _apply(engine, root: Path, found: dict) -> dict:
    """Write the change, under the engine's files lock. The caller restores on failure."""
    checked, new, now, outcome = found['checked'], found['new'], found['now'], found['research']
    changed = found['changed']
    # The session's own settings, through the core's checkpoint and skip.
    shape = {}
    if 'levels' in changed:
        shape['levels'] = new['levels']
    if 'brief_kind' in changed:
        shape['brief_kind'] = new['brief_kind']
    if new['deck_target'] is not None and ('deck_target' in changed or 'brand' in changed):
        shape['deck_target'] = new['deck_target']
        shape['brand'] = checked['brand'] or ''
    if 'delivery' in changed and new['deck_target'] is not None:
        shape['delivery'] = new['delivery']
    if shape:
        workspace.checkpoint(root, by='page', **shape)
    if 'deck_target' in changed:
        if now['deck_target'] is None:
            workspace.skip(root, 'deck', clear=True, by='page')
        elif new['deck_target'] is None:
            workspace.skip(root, 'deck', reason=pipeline.NO_DECK, by='page')
            with workspace.locked(root):
                session = workspace.load(root)
                session['settings']['brand'] = None
                session['settings']['deck_target'] = None
                workspace.store(root, session)
    if 'materials' in changed or 'yoodli' in changed:
        # Yoodli is built from the brief and the scenarios: it goes first, and comes back last.
        if now['yoodli'] and not new['yoodli']:
            workspace.skip(root, 'yoodli', reason=CHANGED_AWAY, by='page')
        for stage in pipeline.MATERIALS:
            if stage in now['materials'] and stage not in new['materials']:
                workspace.skip(root, stage, reason=CHANGED_AWAY, by='page')
            elif stage in new['materials'] and stage not in now['materials']:
                workspace.skip(root, stage, clear=True, by='page')
        if new['yoodli'] and not now['yoodli']:
            workspace.skip(root, 'yoodli', clear=True, by='page')
    if 'scenario_plan' in changed:
        with workspace.locked(root):
            session = workspace.load(root)
            session['settings']['scenario_plan'] = new['scenario_plan']
            workspace.store(root, session)
    if 'walkthrough' in changed:
        with workspace.locked(root):
            session = workspace.load(root)
            session['settings']['walkthrough'] = new['walkthrough']
            workspace.store(root, session)
    # intake.md, saved and approved as the person's own answers, as the start does.
    if found['differs']:
        workspace.write_atomic(root / 'intake.md', found['intake'].encode('utf-8'))
        workspace.save(root, 'intake', built=True)
        workspace.approve(root, 'intake', by='page')
    record = engine._load(root)
    # The research inputs, from the source panel's draft.
    if any(kind in changed for kind in SOURCE_KINDS):
        prepared = found['prepared']
        record['research_inputs'] = _install(root, prepared)
        if research_parallel.protocol(record):
            record['research_execution']['workers'] = prepared['workers']
    chosen = checked['research_from']
    if 'sources' in changed or 'search' in changed:
        scope = pipeline.scope_of(chosen)
        given = record.get('documents')
        if chosen['documents']:
            count = len(found['prepared']['sources']) + _documents(engine, root)
            record['documents'] = {**(given or {}), 'scope': scope,
                                   'done': (given or {}).get('done') or home.now(), 'count': count}
        else:
            record['documents'] = None
        record['research_from'] = chosen
    record['research_questions'] = new['research_questions']
    if record.get('outline_first', {}).get('outline') and (found['differs'] or any(name in RESEARCHED for name in changed)):
        record['outline_first']['inputs_changed'] = True
        if 'research_questions' in changed:
            record['outline_first']['outline']['personal_questions'] = list(new['research_questions'])
    # Research: planned again, started again, carried on or kept.
    if outcome in ('again', 'replanned'):
        _set_aside(root, 'research-plan')
        if outcome == 'again':
            _set_aside(root, 'research')
        record['research'] = None
        record.setdefault('answers', {}).pop('research-plan', None)
        if (record.get('question') or {}).get('step') == 'research-plan':
            record['question'] = None
        if record.get('documents'):
            record['documents']['later'] = []
    else:
        session = workspace.load(root)
        if workspace.statuses(root, session).get('research-plan') == 'stale':
            workspace.keep_as_is(root, 'research-plan', reason='Kept when the training’s '
                                 'settings were changed: ' + series(found['names']) + '.', by='page')
    if outcome in ('again', 'replanned', 'restarted'):
        (record.get('research_execution') or {}).pop('progress', None)
    # A blueprint is not out of date for a level added or the brief's kind alone.
    if found['differs'] and all(heading in ('Levels', 'Brief') for heading in found['differs']) \
            and outcome != 'again':
        session = workspace.load(root)
        for level in now['levels'] or [None]:
            name = workspace.qualify('blueprint', level)
            if level in (session['levels'] or [None]) and \
                    workspace.statuses(root, session).get(name) == 'stale':
                workspace.keep_as_is(root, name, reason='Kept: only the levels or the brief’s '
                                     'kind changed.', by='page')
                session = workspace.load(root)
    if 'levels' in changed:
        home.remember(root, workspace.load(root)['title'], new['levels'])
    previous = record.get('problem') or {}
    summary = {'at': home.now(), 'changed': changed, 'research': outcome,
               'discards': found['discards']}
    record.setdefault('settings_changes', []).append(summary)
    if previous and not previous.get('settings') and outcome in ('continues', 'kept'):
        # The change does not address what stopped: the stop stays, with its own action
        # (Try again, Give it more time, Carry on) and what that
        # action needs, and says the settings changed. Its own words are kept apart, so a
        # second change says so once.
        stopped = previous.get('stopped_what') or previous.get('what', '')
        record['problem'] = {**previous, 'settings_changed': summary['at'],
                             'stopped_what': stopped,
                             'what': 'Its settings were changed; what stopped is not changed '
                                     'by that. ' + stopped}
    else:
        # Waiting for Continue. A change saved over an earlier one keeps what that one said
        # research does on Continue, unless this one does more.
        if previous.get('settings') and outcome in ('continues', 'kept'):
            outcome = previous.get('outcome') or outcome
        # A stop for time is carried into Continue, so research planned or started again is
        # given the same room Give it more time would give, and says so.
        more = (previous.get('carried') or previous.get('action')) == stops.MORE_TIME
        carried = {key: previous[key] for key in ('seconds',) if previous.get(key)}
        if more:
            carried['carried'] = stops.MORE_TIME
        if outcome in ('restarted', 'continues') and previous.get('unreadable'):
            carried['unreadable'] = previous['unreadable']
        record['problem'] = {
            'state': 'waiting', 'step': None, 'action': 'retry', 'label': 'Continue',
            'at': summary['at'], 'settings': True, 'outcome': outcome, **carried,
            'what': 'Its settings were changed. ' + WAITS + (
                ' Continue plans the research again with the new settings.'
                if outcome in ('again', 'replanned') else
                ' Continue starts the research again with the new settings.'
                if outcome == 'restarted' else ' Continue carries on with the new settings.')
                + (' Continue also gives each step twice the time.' if more else ''),
            'kept': KEPT}
    record['halt'] = None
    engine._store(root, record)
    engine._commit(root, "change the training's settings: " + series(found['names']))
    return {'changed': changed, 'names': found['names'], 'research': outcome,
            'discards': found['discards'], 'words': found['words']}
