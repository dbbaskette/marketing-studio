"""The training desk in the runner: what tells a desk run from a saved one, and the sentences
both sides of that line refuse with.

A training started on the desk has `flow: 'desk'` and no review level. New schema-6
runs wait for one topics review before building the selected materials. Schemas 4
and 5 keep their saved workflow, including explicit slide text approval where
requested. The engine carries other gates with desk receipts. The person marks each
material ready on the desk. A run without `flow` keeps the gates, review screens and
remaking it began with.

On the desk, a material built from something that has since changed is held, not remade:
`held` names it, the survey leaves its steps out, and it waits until the person presses
Update (an open entry in `run['drafts']['updates']`, closed by `close_updates` once the
material is made again) or Keep as it is.

The desk's acceptance is never Ready: only the person's Mark ready is (`workspace.decide`
by the page, with the hash shown). Readiness is read from `workspace.person_statuses`, so
the index is written only once every material is Ready (`ready`), and a copy is made of
what is Ready or what the person sent (`copied`).
"""
from __future__ import annotations

import hashlib
import json
import re
from contextlib import contextmanager
from pathlib import Path

import checks
import home
import workspace
from studio_core import research_view, review_policy, step_times
from studio_core.drafting import basis, parts
from studio_core.drafting import record as desk_record
from studio_core.drafting import versions as desk_versions
from studio_core.drafting.store import Store, require_held

import runner  # noqa: F401  puts the core on the import path

FLOW = 'desk'
SCHEMA = 4
RECORD = f'{workspace.STATE_DIR}/run.json'   # the engine's run record
# The order a level's cards are marked ready in: scenarios and Yoodli layouts by their ID.
ORDER = ('blueprint', 'document', 'brief', 'deck', 'scenario', 'yoodli')
HELD_FIRST = '{it} is built from an earlier {what}. Update it or keep it as it is first.'
NEEDS_YOU = 'Settle what needs you on {it} before marking it ready.'
NO_COPY = 'This training keeps no copy of {it}.'
UNWRITTEN = '{it} has not been written yet.'
# A training on a Harness Research that cannot synthesize is refused before anything is made,
# whatever its flow: one check and one sentence, which the engine's NO_SYNTHESIS is.
NEEDS_SYNTHESIS = ('Research needs Harness Research 1.0 or newer on this computer, and the one '
                   'here cannot do it. Update Harness Research, then start again.')
ON_DESK = 'This training is on the desk. Change it there.'
NOT_FINISHED = 'Open it on the desk once it is finished.'
NOT_BROUGHT_IN = 'Bring it in first, then open it on the desk once it is finished.'
# What a desk receipt says was done at a gate: never the person's approval of a material.
DECISION = 'continued-on-the-desk'
LOOK = "You chose the brand's default look at the start: {name}."
NOT_ON_DESK = ('This training is not on the desk. Use its own screen, or open it on the desk '
               'once it is finished.')
# One change at a time: a desk job or an update under way. Task 13's draft_jobs re-exports it.
BUSY = 'A change is already being made to this training. Wait for it, or stop it.'
UP_TO_DATE = workspace.UP_TO_DATE
# What no step of its own makes again when it is out of date: a scenario the person wrote, the
# research plan and the research. It can only be kept as it is.
NOT_REMADE = '{it} is not made again by the studio. Keep it as it is, or change it yourself.'
NEVER_REMADE = ('research-plan', 'research')
# The person cannot supply an arbitrary scope to an update.
NO_SCOPE = 'Leave out the custom scope when updating this material.'
# What a held card says: what it was built from, and how much of it changed since.
HELD = 'Built from an earlier {what}.'
CHANGED = ' {n} {parts} changed since.'
WAITING = 'Waiting for {what} to be updated or kept.'
UPDATING_FIRST = 'Waiting for {what} to be updated.'
PRACTICE = 'The plan for this practice changed.'
# Each kind of material, and each other thing one is built from, as the desk names it.
WHAT = {'blueprint': 'plan', 'document': 'guide', 'brief': 'brief', 'research': 'research',
        'scenario': 'scenario', 'practice': 'practice plan', 'profile': 'Yoodli profile'}
# What a material is built from that the desk names: its upstream materials, and these.
NAMED = ('practice', 'profile')


AFTERWARDS = ("Afterwards each level's plan and brief, and any deck without a guide, say what "
              'changed. Nothing else is rewritten until you update it.')
WIDENED = ('This training is researched from the public web. From now on it reads your '
           'documents too.')


def source_price(root: Path, record: dict) -> dict:
    """The research's price, with its downstream work held until explicitly updated."""
    attempts = {name: entry.get('attempts') or []
                for name, entry in (record.get('steps') or {}).items() if isinstance(entry, dict)}
    return {'words': research_view.price(attempts, redone=())['words'],
            'afterwards': AFTERWARDS, 'widened': None if record.get('documents') else WIDENED}


def _finding_fingerprints(root: Path) -> dict:
    """Compare Harness Research's saved findings, without interpreting their evidence."""
    facts = workspace.research_record(root) or {}
    findings = ({item['id']: item for item in facts.get('findings') or ()}
                if facts.get('schema') == 2 else facts.get('results') or {})
    return {ident: basis.fingerprint({key: value for key, value in finding.items()
                                     if key not in ('at', 'recorded_at', 'checked_at', 'updated_at')})
            for ident, finding in findings.items() if isinstance(finding, dict)}


def marked(root: Path, record: dict) -> dict:
    before = (record.get('drafts') or {}).get('findings_before')
    if before is None:
        return {}
    return {ident: 'new' if ident not in before else 'changed'
            for ident, fingerprint in _finding_fingerprints(root).items()
            if before.get(ident) != fingerprint}


def add_source(root: Path, record: dict, files: list, documents) -> list[str]:
    """Add documents together and remember the findings before requesting research.

    The engine holds its files lock. A refused batch removes only its own new documents.
    Research execution remains entirely in Harness Research.
    """
    from runner import pipeline

    if not isinstance(files, list) or not files:
        raise workspace.WorkspaceError('Add at least one document first.')
    before = _finding_fingerprints(root)
    added = []
    try:
        for file in files:
            if not isinstance(file, dict):
                raise workspace.WorkspaceError('Give each document a name and content.')
            entry = documents.add(root, file.get('name'), file.get('data'))
            added.append(entry)
            if not entry.get('readable'):
                problem = entry.get('problem') or 'It could not be read.'
                raise workspace.WorkspaceError(f'{entry["name"]}: {problem}')
    except Exception:
        for entry in reversed(added):
            documents.remove(root, entry['name'])
        raise
    now = home.now()
    if not record.get('documents'):
        record['research_from'] = {**pipeline.research_of(record), 'documents': True,
                                   'widened_at': now}
        record['documents'] = {'scope': pipeline.scope_of(record['research_from'])}
    readable = [entry for entry in documents.listed(root) if entry.get('readable')]
    record['documents'].update(done=now, count=len(readable))
    record['documents']['later'] = [*(record['documents'].get('later') or []),
                                   *({'name': entry['name'], 'added_at': now} for entry in added)]
    marker = root / pipeline.ADDED
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(now + '\n', encoding='utf-8')
    record.setdefault('drafts', {})['findings_before'] = before
    return [entry.get('title') or entry['name'] for entry in added]


def in_conversation(record: dict | None) -> bool:
    return on_desk(record) and (record or {}).get('execution') == 'conversation'


def on_desk(record: dict | None) -> bool:
    """Whether a run record, or a form, is a training worked on at the desk."""
    return (record or {}).get('flow') == FLOW


def open_on_desk(root: Path, session: dict, record: dict) -> None:
    """Keep the person's approvals as ready when a completed run moves to the desk."""
    from runner import reviews

    final = (record.get('review_decisions') or {}).get('final') or {}
    reviewed = (final.get('by') == 'page' and
                final.get('signature') == reviews.signature(root, session, record, 'final'))
    ready = {}
    for name in workspace.artifact_names(root, session):
        entry = session['artifacts'].get(name) or {}
        approval = entry.get('approved') or {}
        digest = workspace.sha256_file(root / workspace.artifact(root, session, name)['file'])
        if digest and approval.get('sha256') == digest and (
                approval.get('by') == 'page' or
                approval.get('by') == 'review-policy' and reviewed):
            ready[name] = digest
    session['flow'] = FLOW
    session['desk_ready'] = ready
    session.pop('practice_inputs', None)
    for name, entry in session['artifacts'].items():
        if name.startswith('scenario:'):
            (entry.get('built_from') or {}).pop('practice', None)
            ((entry.get('approved') or {}).get('inputs') or {}).pop('practice', None)
    record['opened_on_desk'] = {'at': home.now(), 'was': {
        key: record.get(key) for key in ('review_policy', 'review_layout')}}
    record['flow'] = FLOW


def receipt(record: dict, gate: str, evidence, at: str, note: str | None = None) -> None:
    """Record that the desk continued `gate`, bound to what it continued. A desk run has no
    review level, so the receipt names none; `note` says, in words kept as they are, how."""
    record.setdefault('review_events', []).append({
        'gate': gate, 'by': 'desk', 'level': None,
        'evidence': review_policy.fingerprint(evidence), 'at': at, 'decision': DECISION,
        **({'note': str(note)} if note else {})})


def what(key: str) -> str:
    """One thing a material is built from, as the desk names it: "guide", "plan"."""
    base = workspace.split(key)[0].partition(':')[0]
    if base == 'setting':
        return f"{key.partition(':')[2].replace('_', ' ')} setting"
    return WHAT.get(base) or workspace.LABELS.get(base, base)


def updates(run: dict | None) -> dict:
    """The updates asked for on a desk run and not yet made, by material."""
    return ((run or {}).get('drafts') or {}).get('updates') or {}


def update_names(root: Path, record: dict, level=None) -> list[str]:
    """Held, runnable materials in level and pipeline order; never a person's scenario."""
    session = workspace.load(root)
    state = workspace.statuses(root, session)
    holding = held(root, session, record, state)
    own = set(workspace.scenarios(root, session)['found']) - set(record.get('drafted') or ())
    names = [name for at in session['levels'] or [None] if level is None or at == level
            for kind in ORDER for name in workspace.artifact_names(root, session)
            if name in holding and name not in own and workspace.split(name)[1] == at
            and workspace.split(name)[0].partition(':')[0] == kind]
    # A person's scenario (or an input outside this chain) must be settled first,
    # just as with an individual Update. Otherwise its dependent can never land current.
    while True:
        allowed = set(names) | set(updates(record))
        ready = [name for name in names if not any(
            state.get(upstream) == 'stale' and upstream not in allowed
            for upstream in workspace.artifact(root, session, name)['upstream'])]
        if ready == names:
            return names
        names = ready


def update_all(root: Path, record: dict) -> list[str]:
    """Extend the explicitly requested chain with materials newly held by its landings.
    The engine calls this under its files lock and prepares each newly queued update."""
    chain = (record.get('drafts') or {}).get('update_chain') or {}
    if not on_desk(record) or chain.get('status') != 'working':
        return []
    names = [name for name in update_names(root, record, chain.get('level'))
             if name not in chain.get('blocked', [])]
    asked = record['drafts'].setdefault('updates', {})
    for name in names:
        asked[name] = {'at': home.now(), 'by': 'page', 'scope': None, 'chain': chain['id']}
    levels = workspace.load(root)['levels'] or [None]
    record['drafts']['updates'] = dict(sorted(asked.items(), key=lambda item: (
        levels.index(workspace.split(item[0])[1]),
        ORDER.index(workspace.split(item[0])[0].partition(':')[0]), item[0])))
    return names


def chain_price(root: Path, record: dict, names) -> str:
    """The last try of every worker for these materials, including deck section jobs."""
    from runner import pipeline
    from runner.engine import Engine
    from studio_core import stops

    session = workspace.load(root)
    listed = pipeline.steps(session['levels'], pipeline.wanted(session),
                            pipeline.practice(root, session), deck=True)
    steps = [step.id for step in listed if step.kind == 'agent' and step.artifact in names
             and (pipeline.bare(step.id) != 'deck-repair' or any(
                 key.startswith(step.id + ':') for key in record['steps']))]
    took = Engine._redo_steps(record, steps) if steps else None
    return stops.cost(*took) if took else NO_UPDATE_RECORD


def update_view(root: Path, record: dict) -> dict:
    """The priced groups shown on the Plan cards and in Sources; reading starts nothing."""
    def preview(level=None):
        names = update_names(root, record, level)
        return {'names': [workspace.label(name) for name in names],
                'price': chain_price(root, record, names)} if names else None

    session = workspace.load(root)
    return {'all': preview(), 'levels': {level or '': preview(level)
                                       for level in session['levels'] or [None]},
            'chain': (record.get('drafts') or {}).get('update_chain'),
            'busy': busy(record)}


UPDATE_RULE = ('The plan changed as "plan change" shows. Change only the sections '
               'that change needs, and copy every other section exactly, word for word.')
NO_UPDATE_RECORD = 'This computer has no record yet of what it costs.'


def plan_change(root: Path, session: dict, name: str) -> dict:
    """Compare the plan used to build this material with the current plan."""
    level = workspace.split(name)[1]
    plan = workspace.qualify('blueprint', level)
    digest = (session['artifacts'].get(name, {}).get('built_from') or {}).get(plan)
    before_file = workspace.history_file(root, plan, digest, '.md') if digest else None
    before = before_file.read_text(encoding='utf-8') if before_file and before_file.is_file() else ''
    current = root / workspace.artifact(root, session, plan)['file']
    after = current.read_text(encoding='utf-8') if current.is_file() else ''
    def lines(text):
        return {m.group(1): line for line in text.splitlines()
                if (m := re.match(r'^### (O[1-9]\d*)\b', line))}
    old, new = lines(before), lines(after)
    return {'before': before, 'after': after,
            'objectives': [key for key in old if key in new and old[key] != new[key]],
            'added': [key for key in new if key not in old],
            'removed': [key for key in old if key not in new]}


def _objective_only(change: dict) -> bool:
    def other(text):
        return [line for line in text.splitlines()
                if not re.match(r'^### O[1-9]\d*\b', line)]
    return (bool(change['before']) and bool(change['objectives'] or change['added'] or change['removed'])
            and other(change['before']) == other(change['after']))


def touched(codec_draft: dict, objectives) -> list[str]:
    """Find sections covering a changed objective or one of its key points."""
    wanted = set(objectives)
    return [part['id'] for part in codec_draft.get('sections', ())
            if any(cover in wanted or (cover.startswith('K') and
                   'O' + cover[1:].partition('.')[0] in wanted)
                   for cover in part.get('covers', ()))]


def scoped_update(root, session, name, change, draft):
    """Only scope an objective change when every changed objective has coverage."""
    spec = workspace.artifact(root, session, name)
    changed = _changed(root, session, name, [*spec['upstream'], *spec['extras']])
    if (workspace.split(name)[0] != 'document' or not _objective_only(change)
            or changed != [workspace.qualify('blueprint', workspace.split(name)[1])]):
        return None
    objectives = change['objectives'] + change['added'] + change['removed']
    if any(not touched(draft, [objective]) for objective in objectives):
        return None
    return set(touched(draft, objectives))


DECK_UPDATE = ('The guide changed. Word again only the slides in "slides to word again", '
               'from the guide as it is now, and copy every other slide exactly.')
NO_SLIDE = 'No slide is built from the sections that changed.'


def slides_for(root: Path, session: dict, level: str | None, since: str) -> dict:
    """Find the slides served by the parts changed since this deck was built."""
    from runner import pipeline, deck
    if since not in ('document', 'blueprint'):
        raise ValueError('Choose the guide or plan.')
    name = workspace.qualify('deck', level)
    source = workspace.qualify(since, level)
    digest = (session['artifacts'].get(name, {}).get('built_from') or {}).get(source)
    old_file = workspace.history_file(root, source, digest, '.md') if digest else None
    current_file = root / workspace.artifact(root, session, source)['file']
    current = current_file.read_text(encoding='utf-8') if current_file.is_file() else ''
    old = old_file.read_text(encoding='utf-8') if old_file and old_file.is_file() else None
    outline = json.loads(pipeline.place(root, level, pipeline.OUTLINE).read_text(encoding='utf-8'))
    slides = deck.slides_of(outline)
    all_ids = [slide['id'] for slide in slides if slide.get('id')]
    if old is None:
        return {'slides': all_ids, 'sections': [], 'whole': True}
    if since == 'blueprint':
        before, after = checks.parse_blueprint(old), checks.parse_blueprint(current)
        a, b = before['objectives'], after['objectives']
        if set(a) != set(b):
            return {'slides': all_ids, 'sections': [], 'whole': True}
        objectives = {key for key in a if a[key] != b[key]}
        # Other plan edits may affect any slide; do not guess at their scope.
        if not _objective_only(plan_change(root, session, name)) and old != current:
            return {'slides': all_ids, 'sections': [], 'whole': True}
        sections = sorted(objectives)
    else:
        codec = GuideCodec()
        before, after = codec.split(old), codec.split(current)
        old_parts = {part['heading']: part for part in before['sections']}
        new_parts = {part['heading']: part for part in after['sections']}
        if len(old_parts) != len(before['sections']) or len(new_parts) != len(after['sections']):
            return {'slides': all_ids, 'sections': [], 'whole': True}
        changed = [part for part in [*before['sections'], *after['sections']]
                   if ({key: value for key, value in old_parts.get(part['heading'], {}).items() if key != 'id'}
                       != {key: value for key, value in new_parts.get(part['heading'], {}).items() if key != 'id'})]
        sections = list(dict.fromkeys(part['heading'] for part in changed))
        objectives = set()
        plan_name = workspace.qualify('blueprint', level)
        plan_file = root / workspace.artifact(root, session, plan_name)['file']
        modules = checks.parse_blueprint(plan_file.read_text(encoding='utf-8'))['modules']
        for part in changed:
            covers = part.get('covers') or []
            direct = {cover for cover in covers if cover.startswith('O')}
            objectives.update(direct)
            if not direct:
                for cover in covers:
                    if cover.startswith('K'):
                        objectives.update(modules.get('M' + cover[1:].partition('.')[0], {}).get('objectives', []))
        if before.get('opening') != after.get('opening'):
            return {'slides': all_ids, 'sections': sections, 'whole': True}
    return {'slides': [slide['id'] for slide in slides
                       if objectives.intersection(slide.get('sources') or [])],
            'sections': sections, 'whole': False}


def deck_update(root: Path, session: dict, level: str | None) -> dict:
    """Scope a deck update only when exactly one supported input changed."""
    from runner import pipeline, deck
    name = workspace.qualify('deck', level)
    changed = input_of(root, session, name)
    supported = [workspace.qualify(key, level) for key in ('document', 'blueprint')]
    if len(changed) == 1 and changed[0] in supported:
        return slides_for(root, session, level, workspace.split(changed[0])[0])
    outline = json.loads(pipeline.place(root, level, pipeline.OUTLINE).read_text(encoding='utf-8'))
    return {'slides': [slide['id'] for slide in deck.slides_of(outline) if slide.get('id')],
            'sections': [], 'whole': True}


def update_preview(root: Path, name: str) -> dict:
    from studio_core import stops
    session = workspace.load(root)
    kind, level = workspace.split(name)
    if kind == 'deck':
        from runner import pipeline
        from runner.engine import Engine
        scoped = deck_update(root, session, level)
        run = run_of(root) or {'steps': {}}
        start = pipeline.read_built(root, level).get('start') or {}
        sections = [part for part in start.get('sections') or ()
                    if set(part.get('slides') or ()).intersection(scoped['slides'])]
        names = [workspace.qualify('deck-outline', level)] + [
            workspace.qualify('deck-sections', level) + ':' + part['id'].rpartition('-')[2]
            for part in sections] + [workspace.qualify('deck-review', level)]
        price = Engine._redo_steps(run, names)
        return {'parts': ['The whole outline'] if scoped['whole'] else scoped['sections'],
                'slides': scoped['slides'], 'whole': scoped['whole'],
                'message': NO_SLIDE if not scoped['slides'] else '',
                'price': stops.redone('the outline', len(names), *price,
                                      after='the affected sections and review') if price
                else NO_UPDATE_RECORD}
    change = plan_change(root, session, name)
    kind = workspace.split(name)[0]
    codec = GuideCodec() if kind == 'document' else BriefCodec()
    file = root / workspace.artifact(root, session, name)['file']
    draft = codec.split(file.read_text(encoding='utf-8'))
    ids = scoped_update(root, session, name, change, draft)
    sections = draft['sections']
    if ids is None:
        ids = {part['id'] for part in sections if not part.get('locked')}
    attempts = ((run_of(root) or {}).get('steps', {}).get(name) or {}).get('attempts') or []
    last = attempts[-1] if attempts else None
    price = stops.redone(workspace.label(name), 1, last.get('seconds'), last.get('dollars')) if last else NO_UPDATE_RECORD
    return {'parts': [part['heading'] for part in sections if part['id'] in ids], 'price': price}


def busy(run: dict | None) -> bool:
    """Whether a change is being made to a desk training: a desk job, or an update asked for
    and not yet made."""
    jobs = ((run or {}).get('drafts') or {}).get('jobs') or ()
    return bool(updates(run)) or any(basis.busy(job) for job in jobs)


def held(root: Path, session: dict, run: dict | None, state: dict | None = None
         ) -> frozenset[str]:
    """The materials of a desk training built from something that has since changed, kept as
    they are until the person updates or keeps each: out of date, on disk, and with no update
    asked for. A saved training holds nothing; it remakes as it always did."""
    if not on_desk(run):
        return frozenset()
    state = workspace.statuses(root, session) if state is None else state
    asked = updates(run)
    return frozenset(
        name for name in workspace.artifact_names(root, session)
        if state.get(name) == 'stale' and name not in asked
        and (root / workspace.artifact(root, session, name)['file']).is_file())


def _changed(root: Path, session: dict, name: str, keys) -> list[str]:
    entry = session['artifacts'].get(name) or {}
    built, now = entry.get('built_from') or {}, workspace.inputs(root, session, name)
    return [key for key in keys if built.get(key) != now.get(key)]


def input_of(root: Path, session: dict, name: str) -> list[str]:
    """What a material was built from that is not what is there now: its upstream materials,
    its practice plan line and the Yoodli profile, in that order."""
    spec = workspace.artifact(root, session, name)
    return _changed(root, session, name, [*spec['upstream'], *(
        extra for extra in spec['extras'] if extra in NAMED)])


def hold_says(root: Path, session: dict, holding, name: str, state: dict | None = None,
              asked=()) -> str | None:
    """What a card says of a hold: that it waits for an input of its own to be updated or
    kept (only updated, once the person asked for its update: `asked`), or what it was
    built from an earlier version of. None for a card not held."""
    waiting, changed = _hold(root, session, holding, name, state)
    if waiting is not None:
        said = UPDATING_FIRST if waiting in asked else WAITING
        return said.format(what=f'the {what(waiting)}')
    if name not in holding:
        return None
    if 'practice' in changed:
        return PRACTICE
    return HELD.format(what=' and '.join(what(key) for key in changed))


def _hold(root: Path, session: dict, holding, name: str, state: dict | None
          ) -> tuple[str | None, list[str]]:
    """What a hold is: the input of its own it waits for, if any, and what it was built
    from an earlier version of."""
    spec = workspace.artifact(root, session, name)
    state = workspace.statuses(root, session) if state is None else state
    waiting = next((upstream for upstream in spec['upstream']
                    if upstream in holding or state.get(upstream) == 'stale'), None)
    return waiting, _changed(root, session, name, [*spec['upstream'], *spec['extras']])


def held_first(root: Path, session: dict, holding, name: str, state: dict | None = None
               ) -> str:
    """Why a held material is not marked ready or sent to its copies, as its card says it:
    the input of its own to update or keep first, a practice plan that changed, or what it
    was built from an earlier version of."""
    waiting, changed = _hold(root, session, holding, name, state)
    it = workspace.label(name)
    if waiting is not None:
        return f'Update or keep {workspace.label(waiting)} first.'
    if 'practice' in changed:
        return f'{PRACTICE} Update {it} or keep it as it is first.'
    return HELD_FIRST.format(it=workspace.sentence(it), what=' and '.join(
        dict.fromkeys(what(key) for key in changed)) or 'version of its inputs')


def close_updates(root: Path, session: dict, run: dict | None, state: dict | None = None
                  ) -> list[str]:
    """Close each update whose material is made again, no longer out of date. Returns the
    names closed; the caller stores the run."""
    asked = updates(run)
    if not on_desk(run) or not asked:
        return []
    state = workspace.statuses(root, session) if state is None else state
    closed = [name for name in asked if state.get(name) != 'stale']
    for name in closed:
        del asked[name]
    return closed


def run_of(root: Path) -> dict | None:
    """A training's run record as it is on disk, read for what the desk keeps in it, or
    None when no run is driving it. The engine reads and checks it for everything else."""
    record = workspace.read_run(Path(root))
    return record if isinstance(record, dict) else None


def sent(run: dict | None) -> list[str]:
    """The materials the person sent to their copies while each was a draft."""
    return list(((run or {}).get('drafts') or {}).get('send') or ())


def copied(root: Path, session: dict, run: dict | None = None) -> frozenset[str]:
    """What a copy is made of now. On the desk, what the person marked Ready and any draft
    they sent; the desk's acceptance alone makes no copy. Otherwise, what is approved."""
    if not workspace.on_desk(session):
        return frozenset(name for name, status in workspace.statuses(root, session).items()
                         if status == 'approved')
    asked = set(sent(run))
    return frozenset(name for name, status in workspace.person_statuses(root, session).items()
                     if status == 'approved' or (status == 'draft' and name in asked))


def ready(root: Path) -> bool:
    """Whether every material is Ready and nothing else is in the way, as the index says
    it: on the desk read from what the person marked ready, never the desk's acceptance."""
    import assess
    return bool(assess.run_checks(root)['ready'])


def needs_you(root: Path, found, name: str) -> list[str]:
    """What keeps a material from being marked ready, a sentence each: for a deck, the grave
    findings its last round's review still has and its audit's blockers. `found` is the
    training's survey. Nothing for any other material."""
    if workspace.split(name)[0] != 'deck':
        return []
    if workspace.pending_local_deck(root, found.session, name):
        return ['This deck has an undelivered local draft. Resolve it explicitly before marking a deck ready.']
    from runner import pipeline
    shown = pipeline.deck_gate(root, found.session, name)
    return review_policy.held((shown.get('review') or {}).get('findings'),
                              (shown.get('audit') or {}).get('blockers'))


def level_ready(root: Path, session: dict, level: str | None,
                state: dict | None = None) -> list[str]:
    """What Mark this level ready marks, in ORDER: each card of the level the person has
    not marked Ready, a draft or one held. Scenarios and Yoodli layouts come by their ID."""
    state = workspace.person_statuses(root, session) if state is None else state
    names = workspace.artifact_names(root, session)
    return [name for base in ORDER for name in names
            if workspace.split(name)[1] == level
            and workspace.split(name)[0].partition(':')[0] == base
            and state.get(name) in ('draft', 'stale')]


# --- how long the start takes here -------------------------------------------------------

# The minutes each kind of step is guessed to take until this computer has times of its
# own: research, a plan, a guide, a brief, a scenario and a Yoodli layout. A deck's guess is
# `deck.RATE['minutes']` a slide, with SLIDES slides before what it says is written.
GUESSES = {'research': 6, 'blueprint': 1, 'document': 3, 'brief': 2, 'scenario': 1,
           'yoodli': 1}
SLIDES = 8
EACH_ITS_OWN = ('scenario', 'yoodli')   # a step for each scenario, named by its ID


class Times(Store):
    """Training Studio's store for how long desk steps take on this computer: kept in its
    own data folder, never in a training's, and written outside any training's lock."""
    product, word = 'Training Studio', 'training'

    def held(self):
        return True


def times() -> Path:
    """Where this computer keeps how long each kind of desk step took."""
    return home.data_root() / 'draft-step-times.json'


def _timed(base: str) -> str | None:
    """The kind of step a step's ID is timed as, for one the estimate guesses: a plan, a
    guide, a brief, a scenario or a Yoodli layout. None for any other, a research question
    or a copy among them."""
    kind = base.partition(':')[0]
    if kind in GUESSES and kind != 'research' and (base == kind or kind in EACH_ITS_OWN):
        return kind
    return None


def _since(record: dict, marker: str, belongs) -> float:
    """The seconds of every kept try of the steps `belongs` names since `marker` was last
    kept: the whole of one research, or of one deck."""
    tried = record.get('steps') or {}
    began = max((attempt.get('started_at') or '' for attempt in
                 (tried.get(marker) or {}).get('attempts') or ()
                 if attempt.get('outcome') == 'kept'), default='')
    return float(sum(attempt.get('seconds') or 0 for name, entry in tried.items()
                     if belongs(name) for attempt in entry.get('attempts') or ()
                     if attempt.get('outcome') == 'kept'
                     and (attempt.get('started_at') or '') >= began))


def took(record: dict, step: str, seconds: float) -> None:
    """Keep how long a desk step that worked took on this computer, for the start's
    estimate: a plan, a guide, a brief, a scenario or a Yoodli layout as its step ends, and
    the research and each deck whole, once their last step does. Best effort: a problem
    keeping it never stops the step."""
    from studio_core import research_contract

    from runner import pipeline
    base, level = workspace.split(step.partition(':')[0] if step.startswith('deck-')
                                  else step)
    try:
        if base == 'research-report':
            key, seconds = 'research', _since(record, 'research-start', lambda name: (
                name == 'research' or name.startswith('research:')
                or name in research_contract.LEGACY_JOBS))
        elif base == 'deck-save':
            key, seconds = 'deck', _since(
                record, workspace.qualify('deck-handoff', level), lambda name: (
                    workspace.split(name.partition(':')[0]) in
                    [(each, level) for each in pipeline.DECK_STEPS]))
        else:
            key = _timed(base)
        if key is not None:
            step_times.note(Times(), times(), key, float(seconds or 0))
    except (TypeError, ValueError, AttributeError, OSError):
        return


def _slides(root: Path, level: str | None) -> int:
    """How many slides a deck has, from what it says once that is written; else SLIDES."""
    try:
        said = home.read_json(Path(root) / workspace.prefix(level) / 'deck' / 'outline.json',
                              None)
    except (OSError, ValueError):
        said = None
    slides = said.get('slides') if isinstance(said, dict) else None
    return len(slides) if isinstance(slides, list) and slides else SLIDES


def start_minutes(root: Path, record: dict, found) -> int:
    """About how many minutes are left of a desk training's start: over the steps still to
    run, this computer's usual time for each kind (`step_times.expected`), else its guess
    (GUESSES; a deck's is `deck.RATE['minutes']` a slide). `found` is its survey."""
    from runner import deck, pipeline
    store, path, minutes, decks = Times(), times(), 0.0, set()
    for step in found.steps:
        if step.id in found.done:
            continue
        base, level = workspace.split(step.id)
        if base in pipeline.DECK_STEPS:
            if level not in decks:
                decks.add(level)
                minutes += step_times.expected(store, path, 'deck',
                                               deck.RATE['minutes'] * _slides(root, level))
            continue
        kind = _timed(base) or (base if base == 'research' else None)
        if step.kind == 'agent' and kind is not None:
            minutes += step_times.expected(store, path, kind, GUESSES[kind])
    return round(minutes)


# --- the desk's view ---------------------------------------------------------------------

ACTIONS = ('ready', 'update', 'keep', 'send', 'download')
STATES = ('writing', 'draft', 'ready', 'held', 'needs', 'left-out')
NOTHING_NEEDED = ('Nothing needed from you. Each material opens here as it is ready, in '
                  'about {n} {minutes}.')
WRITING = 'Being written. It opens here when it is ready.'
UPDATING = 'Being made again from what it is built from now.'
DRAFT = 'A draft. Nothing is ready until you mark it.'
READY = 'Ready. You marked it ready.'
NEEDS = 'Needs you before using.'
LEFT_OUT = 'Left out.'
PUTTING = 'Putting {it} on the desk.'
QUESTION = 'A question is waiting for you: {text}'
# What a saved training's list calls a material the desk accepted and the person has not
# marked ready.
DRAFT_WORDS = 'not marked ready yet'


def _left_out(root: Path, session: dict, name: str) -> str | None:
    """Why a material is left out, in the person's own words, or None for one left out as
    the start was chosen (it has no card)."""
    from runner import pipeline
    stage = workspace.artifact(root, session, name)['stage']
    if stage in session['unavailable']:
        return session['unavailable'][stage]
    said = [event.get('reason') for event in session.get('events') or ()
            if event.get('event') == 'skip' and event.get('stage') == stage]
    reason = said[-1] if said else None
    if reason in (None, pipeline.NOT_CHOSEN, pipeline.NO_DECK):
        return None
    return reason


def _checked(outcomes, name: str) -> dict:
    """What a card's "Checked for you" says: the checks of this material that passed, and
    each that did not, as the review screen shows them."""
    import checks
    own = [outcome for outcome in outcomes if checks.artifact_of(outcome['check']) == name]
    return {'passed': sum(outcome['status'] == 'passed' for outcome in own),
            'problems': [{'check': outcome['check'], 'problems': outcome['problems'],
                          'words': ('could not run' if outcome['status'] == 'unavailable'
                                    else 'failed')}
                         for outcome in own if outcome['status'] != 'passed']}


def _failing(found, problem: dict) -> str | None:
    """The material whose step the run stopped at, or None."""
    at = problem.get('step') or ''
    return next((step.artifact for step in found.steps if step.artifact and at
                 and (at == step.id or at.startswith(step.id + ':'))), None)


def view(engine, root) -> dict:
    """Everything the desk shows for one desk training: {'flow', 'title', 'levels',
    'progress', 'needs', 'cards', 'sources', 'job', 'team'}.

    `progress` is the start's band: {'running', 'doing', 'started_at', 'minutes', 'line'}.
    `cards` are each level's materials in ORDER, each {'name', 'level', 'kind', 'label',
    'state', 'says', 'checks', 'seen', 'held', 'actions', 'needs'}: `state` one of STATES,
    read from what the person marked (the desk's acceptance is a draft), `seen` the hash of
    its file, `actions` of ACTIONS (only `download` for a teammate). `needs` names the
    cards that need the person, then the run's question or problem, and, once everything is
    Ready, what still keeps the index from being written."""
    import assess
    import desk

    from runner import pipeline
    root = Path(root)
    record = engine._load(root)
    found = engine._survey(root, record, engine._wanted(root, record))
    session = found.session
    state, sentence = engine._state(record, found, engine._run(root))
    mine, who, state, sentence, last = engine._whose(root, record, found, state, sentence)
    plain = workspace.statuses(root, session)
    person = workspace.person_statuses(root, session)
    holding, asked, report = held(root, session, record, plain), updates(record), \
        assess.run_checks(root, show_all=True)
    problem, question = record.get('problem') or {}, record.get('question')
    failing, busy_now = _failing(found, problem), busy(record)
    copied_to = {entry['artifact'] for entry in found.copies}
    levels = session['levels'] or [None]
    names = workspace.artifact_names(root, session)
    cards = []
    for level in levels:
        for base in ORDER:
            for name in names:
                kind = workspace.split(name)[0].partition(':')[0]
                if workspace.split(name)[1] != level or kind != base:
                    continue
                spec = workspace.artifact(root, session, name)
                seen = workspace.sha256_file(root / spec['file'])
                waiting = _hold(root, session, holding, name, plain)[0]
                needs = needs_you(root, found, name) if seen and kind == 'deck' else []
                card_actions = ['download'] if seen else []
                if person.get(name) in ('skipped', 'unavailable'):
                    why = _left_out(root, session, name)
                    if why is None:
                        continue
                    shown, says, card_actions = 'left-out', f'{LEFT_OUT} {why}'.strip(), []
                elif name in asked:
                    shown, says, card_actions = 'writing', UPDATING, []
                elif name == failing and problem:
                    shown, says = 'needs', problem.get('what') or NEEDS
                elif seen is None and in_conversation(record):
                    shown, says, card_actions = 'needs', 'Not provided. No work is scheduled; continue explicitly in conversation.', []
                elif seen is None:
                    shown, says = (('needs', pipeline.deck_says(found))
                                   if kind == 'deck' and found.missing
                                   else ('writing', WRITING))
                    card_actions = []
                elif name in holding:
                    shown = 'held'
                    says = hold_says(root, session, holding, name, plain, asked)
                    remade = (workspace.split(name)[0] not in NEVER_REMADE
                              and name not in found.own)
                    card_actions = [*(['update'] if remade and waiting is None
                                      and not busy_now else []),
                                    *(['keep'] if waiting is None else []), 'download']
                elif needs:
                    shown, says = 'needs', ' '.join([NEEDS, *needs])
                elif person.get(name) == 'approved':
                    shown, says = 'ready', READY
                else:
                    shown, says = 'draft', DRAFT
                    card_actions = ['ready', *(['send'] if name in copied_to
                                               and name not in sent(record) else []),
                                    'download']
                changed = next((job for job in reversed((record.get('drafts') or {}).get('jobs', []))
                                if job.get('name') == name), None)
                if changed and changed.get('dropped'):
                    says = f"{says} {changed.get('says') or ''}".strip()
                if record.get('unfinished_migration') and in_conversation(record):
                    card_actions = [action for action in card_actions if action in ('ready', 'download')]
                cards.append({
                    'name': name, 'level': level or '', 'kind': kind,
                    'label': workspace.label(name), 'state': shown, 'says': says,
                    'checks': _checked(report['checks'], name) if seen else
                    {'passed': 0, 'problems': []},
                    'seen': seen, 'held': name in holding,
                    'actions': card_actions if mine else ['download'], 'needs': needs,
                    **({'proposals': engine.deck_proposals(root, level),
                        **deck_card(engine, root, level, found)}
                       if kind == 'deck' and seen else {})})
    needed = []
    if mine:
        needed = [card['label'] for card in cards if card['state'] in ('held', 'needs')
                  and (card['seen'] or not (record.get('unfinished_migration') and in_conversation(record)))]
        if question:
            needed.append(QUESTION.format(text=question['text']))
        if problem.get('what'):
            needed.append(problem['what'])
        # Everything is Ready, and still no index: what else is in the way is said.
        if not needed and not report['ready'] and cards and all(
                card['state'] in ('ready', 'left-out') for card in cards):
            needed += [desk.plainly_on_desk(reason) for reason in report['blocking']]
    running = state == 'working'
    parallel = (record.get('research_execution') or {}).get('progress')
    minutes = max(1, start_minutes(root, record, found)) if running else None
    doing = ''
    if running:
        doing = (PUTTING.format(it=pipeline.subject(found.next.step))
                 if found.next.kind == 'gate' else sentence)
    plan = desk.document(root, session, 'research-plan')
    questions = plan.get('questions') or []
    listed = engine.documents.listed(root) if record.get('documents') else ()
    jobs = (record.get('drafts') or {}).get('jobs') or ()
    return {
        **({'execution': record.get('execution'), 'saved_status': record.get('migration_saved_status')} if record.get('unfinished_migration') else {}),
        'flow': FLOW, 'title': session['title'], 'levels': [level or '' for level in levels],
        'progress': {'running': running, 'doing': doing,
                     'started_at': record.get('started_at'), 'minutes': minutes,
                     # Said only while nothing on the desk needs the person.
                     'line': NOTHING_NEEDED.format(
                         n=minutes, minutes='minute' if minutes == 1 else 'minutes')
                     if running and not needed and not (parallel and parallel.get('phase') != 'complete') else ''},
        'needs': needed, 'cards': cards,
        'sources': {'account': research_view.account(root / 'research', questions),
                    'updates': update_view(root, record),
                    'plan': questions, 'marked': marked(root, record),
                    'documents': [{key: entry.get(key) for key in
                                   ('name', 'bytes', 'readable', 'problem')}
                                  for entry in listed]},
        'job': next((dict(job) for job in reversed(jobs) if basis.busy(job)), None),
        'team': {'ours': mine, 'driver': who, 'last_shared': last}}


# --- parts: a training's guide, brief and plan as piece 3's parts ------------------------
#
# A material's file stays the one copy of its text. Each codec splits it into an opening
# (everything before the first `## `, the `# ` title included) and its `## ` sections, and
# joins them back to the same file byte for byte: each part keeps the blank lines around it
# as they were written (`layout`), so a changed part goes into the file as it stood. A
# section's covers or findings note is kept on the section, out of its text.

NO_PARTS = 'Choose an editable text material.'
BRIEF_SHAPE = 'A brief keeps its eight numbered sections, in order.'
LOCKED = 'Sources is kept from the findings cited. Change the references in the text instead.'
UNCLOSED = 'Close the code block in this part.'
SECTION_LINE = re.compile(r'## +(\S.*?)[ \t\r]*')
BLANK_LINES = re.compile(r'(?:[ \t\r]*\n)*')
NUMBERED_HEADING = re.compile(r'(\d+)\. (.+)')
ANY_SECTION_LINE = re.compile(r'^[ \t]*## ', re.MULTILINE)


class _Note:
    """A section's note: the key it is kept under, how its line reads, and the IDs in it."""

    def __init__(self, key: str, ids: re.Pattern):
        self.key, self.ids = key, ids
        self.line = re.compile(r'[ \t]*<!--\s*' + key + r':\s*(.*?)\s*-->[ \t\r]*')

    def read(self, line: str) -> list[str] | None:
        found = self.line.fullmatch(line)
        return None if found is None else self.ids.findall(found.group(1))

    def written(self, ids) -> str:
        return f"<!-- {self.key}: {' '.join(ids)} -->"


COVERS_NOTE = _Note('covers', checks.COVERED_ID)
FINDINGS_NOTE = _Note('findings', checks.FINDING_ID)


def _id(seed: str, taken: set) -> str:
    """A section id made from where the section is in its file, so the same file always
    gives the same ids: a read holding the lock and one without agree."""
    count = 0
    while True:
        value = hashlib.sha256(f'{seed}:{count}'.encode()).hexdigest()[:8]
        if value not in taken:
            taken.add(value)
            return value
        count += 1


def _cut(body: str, note: _Note | None) -> dict:
    """A part's written text as the blank lines before it, its note line and the blank lines
    after that, its words, and what follows them."""
    lead = BLANK_LINES.match(body).group(0)
    rest, line, gap, ids = body[len(lead):], None, '', None
    if note is not None:
        first, newline, after = rest.partition('\n')
        ids = note.read(first)
        if ids is not None:
            line, rest = first, newline + after
            if rest:
                gap = '\n' + BLANK_LINES.match(rest, 1).group(0)
                rest = rest[len(gap):]
    embedded = None
    if note is not None and ids is None:
        lines = rest.splitlines(keepends=True)
        for at, (one, outside) in enumerate(parts.free([line.rstrip('\r\n') for line in lines])):
            found = note.read(one) if outside else None
            if found is not None:
                ids = found
                embedded = {'at': at, 'line': lines.pop(at)}
                rest = ''.join(lines)
                break
    words = rest.rstrip()
    return {'embedded': embedded, 'lead': lead, 'line': line, 'gap': gap, 'words': words,
            'tail': rest[len(words):], 'ids': ids}


def _starts(lines: list[str], numbered: bool) -> list[int]:
    """The lines that start a section, outside fenced code: each `## ` line, or for a brief
    each `## N. Title` line, the only ones its check reads as sections."""
    return [at for at, (line, outside) in enumerate(parts.free(lines)) if outside and (
        checks.NUMBERED.match(line) if numbered else SECTION_LINE.fullmatch(line))]


def _split(markdown: str, note: _Note | None, numbered: bool, locked) -> dict:
    """A material's file as its opening and sections, each with how it was written around
    its words; `locked(heading)` says which section is not typed in."""
    lines = markdown.split('\n')
    offsets, at = [], 0
    for line in lines:
        offsets.append(at)
        at += len(line) + 1
    starts = _starts(lines, numbered)
    opening = _cut(markdown[:offsets[starts[0]] if starts else len(markdown)], None)
    draft = {'opening': opening['words'],
             'layout': {'lead': opening['lead'], 'tail': opening['tail'],
                        'blank': not opening['words']}}
    sections, taken = [], set()
    digest = hashlib.sha256(markdown.encode()).hexdigest()
    for number, start in enumerate(starts):
        head = lines[start]
        heading = SECTION_LINE.fullmatch(head).group(1)
        end = offsets[starts[number + 1]] if number + 1 < len(starts) else len(markdown)
        cut = _cut(markdown[offsets[start] + len(head):end], note)
        section = {'id': _id(f'{digest}:{number}', taken), 'heading': heading, 'brief': '',
                   'text': cut['words'], 'locked': locked(heading),
                   'layout': {'head': head, 'lead': cut['lead'], 'line': cut['line'],
                              'gap': cut['gap'], 'tail': cut['tail'],
                              'blank': not cut['words'], 'embedded': cut.get('embedded')}}
        if note is not None:
            section[note.key] = cut['ids'] or []
        sections.append(section)
    draft['sections'] = sections
    return draft


def _join(draft: dict, note: _Note | None) -> str:
    """The file a draft's parts make: each part as it was written around its words, and a
    part whose words came or went (or whose note came) written the plain way."""
    sections = draft['sections']
    opening, layout = draft.get('opening') or '', draft.get('layout') or {}
    if layout and layout.get('blank') == (not opening):
        text = layout['lead'] + opening + layout['tail']
    else:
        text = opening + ('\n\n' if sections else '\n') if opening else ''
    for number, section in enumerate(sections):
        last = number == len(sections) - 1
        words, kept = section.get('text') or '', section.get('layout') or {}
        embedded = kept.get('embedded')
        if embedded and note is not None:
            lines = words.splitlines(keepends=True)
            at = min(embedded['at'], len(lines))
            if at and not lines[at - 1].endswith('\n'):
                lines[at - 1] += '\n\n'
            raw = embedded['line']
            if note.read(raw.rstrip('\r\n')) != (section.get(note.key) or []):
                raw = note.written(section.get(note.key) or []) + '\n'
            lines.insert(at, raw)
            words = ''.join(lines)
        head = kept.get('head')
        if not head or SECTION_LINE.fullmatch(head).group(1) != section['heading']:
            head = '## ' + section['heading']
        line, ids = None, section.get(note.key) or [] if note is not None else []
        if note is not None and kept.get('line') is not None:
            line = kept['line'] if note.read(kept['line']) == ids else (
                note.written(ids) if ids else None)
        elif ids and not embedded:
            line = note.written(ids)
        if kept and kept.get('blank') == (not words) and (
                line is None or kept.get('line') is not None):
            noted = line + kept['gap'] if line is not None else ''
            written = head + kept['lead'] + noted + words + kept['tail']
            text += written if last or written.endswith('\n') else written + '\n'
        elif line is None and not words:
            text += head + ('\n' if last else '\n\n')
        else:
            noted = line + ('\n\n' if words else '') if line is not None else ''
            text += head + '\n\n' + noted + words + ('\n' if last else '\n\n')
    return text


def _section_heading(text: str, level: int = 2) -> str:
    """The marks of a `## ` line a part holds outside code, which would start a section."""
    lines = text.replace('\r\n', '\n').split('\n')
    if any(outside and SECTION_LINE.fullmatch(line) for line, outside in parts.free(lines)):
        return '##'
    return parts.heading_in(text, 2)


def _vet(part: str, text: str) -> None:
    """Refuse a part that leaves a code block open: every heading after it would be read as
    code the next time the file is split."""
    fence = None
    for line in text.replace('\r\n', '\n').split('\n'):
        marker = parts.FENCE.match(line)
        if marker and fence is None:
            fence = marker.group(1)
        elif marker and marker.group(1).startswith(fence[0] * len(fence)):
            fence = None
    if fence is not None:
        raise ValueError(UNCLOSED)


def _landed(draft: dict, before: str, text: str) -> str:
    """A job's result as it lands: never in a locked part (Sources), which is kept from the
    findings cited."""
    if text.strip() != before.strip() and any(
            section.get('locked') and section['text'] == before
            for section in draft.get('sections') or ()):
        raise ValueError(LOCKED)
    return text


def _sources(heading: str) -> bool:
    return heading.lower() == 'sources'


def _brief_title(heading: str) -> str:
    found = NUMBERED_HEADING.fullmatch(heading)
    return found.group(2).strip().lower() if found else ''


def _brief_fits(draft: dict, kind: str) -> bool:
    """Whether a brief has its kind's eight sections, in order, as `checks.check_brief`
    reads them: by title, other numbered sections between them allowed."""
    expected = [title.lower() for title in checks.BRIEF_SECTIONS[kind]]
    titles = [_brief_title(section['heading']) for section in draft.get('sections') or ()]
    return [title for title in titles if title in expected] == expected


def _brief_kind(draft: dict) -> str:
    """Which brief a draft is: its title says, or else its sections do."""
    title = (draft.get('opening') or '').lstrip()
    for kind, start in checks.BRIEF_TITLES.items():
        if title.startswith(start):
            return kind
    for kind in checks.BRIEF_SECTIONS:
        if _brief_fits(draft, kind):
            return kind
    raise ValueError(BRIEF_SHAPE)


def _brief_split(markdown: str) -> dict:
    draft = _split(markdown, FINDINGS_NOTE, True,
                   lambda heading: _brief_title(heading) == 'sources')
    draft['kind'] = _brief_kind(draft)
    if not _brief_fits(draft, draft['kind']):
        raise ValueError(BRIEF_SHAPE)
    return draft


def _brief_join(draft: dict) -> str:
    if not _brief_fits(draft, draft.get('kind') or _brief_kind(draft)):
        raise ValueError(BRIEF_SHAPE)
    return _join(draft, FINDINGS_NOTE)


def _brief_heading(text: str, level: int = 2) -> str:
    """A brief's part holds no `## ` line at all, in code or not: its check would read a
    numbered one as a section wherever it is."""
    return '##' if ANY_SECTION_LINE.search(text) else parts.heading_in(text, 2)


def GuideCodec() -> parts.Codec:
    """A guide: its opening, then each `## ` section with its covers note. Sources, which
    the references resolve to, is kept from the findings and not typed in."""
    return parts.Codec(
        fixed=('opening',), single=(), thing='draft', noun='section',
        split=lambda markdown: _split(markdown, COVERS_NOTE, False, _sources),
        join=lambda draft, after=(): _join(draft, COVERS_NOTE),
        deepest=lambda draft: 2, heading_in=_section_heading, vet=_vet, landed=_landed)


def BriefCodec() -> parts.Codec:
    """A brief: its title, then its eight numbered sections in order, each with its findings
    note. "8. Sources" is not typed in, and no section is added, taken out or moved."""
    return parts.Codec(
        fixed=('opening',), single=(), thing='draft', noun='section', split=_brief_split,
        join=lambda draft, after=(): _brief_join(draft), deepest=lambda draft: 2,
        heading_in=_brief_heading, vet=_vet, landed=_landed)


def PlanCodec() -> parts.Codec:
    """A plan: its opening, then the blueprint's `## ` sections, none of them locked."""
    return parts.Codec(
        fixed=('opening',), single=(), thing='draft', noun='section',
        split=lambda markdown: _split(markdown, None, False, lambda heading: False),
        join=lambda draft, after=(): _join(draft, None),
        deepest=lambda draft: 2, heading_in=_section_heading, vet=_vet, landed=_landed)


class WholeCodec(parts.Codec):
    """A scenario or Yoodli layout has one editable part and whole-file History."""

    def __init__(self):
        super().__init__(
            fixed=('opening',), single=(), part=re.compile(r'(?!)'), thing='draft',
            split=lambda text: {'opening': text, 'sections': []},
            join=lambda draft, after=(): draft['opening'],
            heading_in=lambda text, level: '', vet=_vet,
            taken=lambda draft, part, text, previous: (text, dict(draft)))

    def set_text(self, draft, part, text):
        self.section(draft, part)  # Refuse any name other than the whole-file part.
        draft[part] = text


CODECS = {'document': GuideCodec(), 'brief': BriefCodec(), 'blueprint': PlanCodec(),
          'scenario': WholeCodec(), 'yoodli': WholeCodec()}


def codec_of(name: str) -> parts.Codec:
    """The codec a material's file is read with, by the material's name."""
    found = CODECS.get(workspace.split(name)[0].partition(':')[0])
    if found is None:
        raise ValueError(NO_PARTS)
    return found


def _folder_name(name: str) -> str:
    return name.replace(':', '-').replace('@', '-')


class TrainingStore(Store):
    """Training Studio's desk store over one training's folder.

    A material's record is `work/drafts/<name>/` in its level folder (never shared: `work/`
    is ignored), its waiting Finishing proposals are in this computer's data folder, and a
    write saves the joined parts as the material's file. Every desk write runs holding the
    engine's `files` lock, and `held()` is whether this thread holds it."""

    product, word = 'Training Studio', 'training'

    def __init__(self, engine, root: Path):
        self.engine, self.root = engine, Path(root)
        self._making: tuple[str, str | None] | None = None

    def held(self) -> bool:
        # `files` is a threading.RLock: `_is_owned` says whether this thread holds it, as
        # threading.Condition asks it. Another thread holding it is not this one.
        return self.engine.files._is_owned()

    def folder(self, name: str) -> Path:
        from runner import pipeline
        return pipeline.place(self.root, workspace.split(name)[1], 'work/drafts') \
            / _folder_name(name)

    def local(self, name: str, *names: str) -> Path:
        return home.data_root().joinpath('draft-proposals', self.root.name, _folder_name(name),
                                         *names)

    @contextmanager
    def making(self, via: str, session: str | None):
        """The kind of change and the page's session that writes made inside are saved
        with, for a caller (piece 3's desk) that passes neither."""
        before, self._making = self._making, (via, session)
        try:
            yield
        finally:
            self._making = before

    def write(self, name: str, draft: dict, changed, via: str | None = None,
              session: str | None = None) -> dict:
        """One revision on, then the joined parts saved as the material's file: an edit,
        which keeps what the material was built from, then accepted on the desk unless it is
        out of date (an edit never clears that). The record keeps the file's hash."""
        require_held(self)
        made_via, made_session = self._making or ('save', None)
        via = via or made_via
        session = session if session is not None else made_session
        text = codec_of(name).join(draft)
        desk_record.advance(draft, changed, self.now())
        spec = workspace.artifact(self.root, workspace.load(self.root), name)
        joined = self.path(name, Path(spec['file']).name)
        self.atomic(joined, text.encode('utf-8'))
        try:
            entry = workspace.save(self.root, name, source=joined, edit=True, via=via,
                                   session_token=session)
        finally:
            joined.unlink(missing_ok=True)
        draft['file_sha256'] = entry['sha256']
        self.write_json(self.path(name, 'draft.json'), draft)
        if workspace.statuses(self.root, workspace.load(self.root)).get(name) != 'stale':
            workspace.accept_desk(self.root, name)
        return draft


def _noted(section: dict) -> tuple:
    return tuple(section.get('covers') or section.get('findings') or ())


def follow(before: dict | None, after: dict) -> dict:
    """Give a fresh split the ids of the record it replaces: by heading, then by covers or
    findings note, then by place. A section none of them matches keeps the id its split gave
    it, or another when that one is taken."""
    if not before:
        return after
    old = list(before.get('sections') or ())
    used, ids = set(), [None] * len(after['sections'])
    for same in (lambda one, other, at: one['heading'] == other['heading'],
                 lambda one, other, at: bool(_noted(one)) and _noted(one) == _noted(other),
                 lambda one, other, at: old.index(other) == at):
        for at, section in enumerate(after['sections']):
            if ids[at] is None:
                found = next((other for other in old
                              if other['id'] not in used and same(section, other, at)), None)
                if found is not None:
                    ids[at] = found['id']
                    used.add(found['id'])
    for at, section in enumerate(after['sections']):
        if ids[at] is None:
            ids[at] = section['id'] if section['id'] not in used else _id(section['id'], used)
            used.add(ids[at])
        section['id'] = ids[at]
    return after


def current(store: TrainingStore, codec: parts.Codec, name: str) -> dict:
    """A material's draft record, following its file. When something else wrote the file (a
    step, a Google pull, the conversation helper, another computer), it is split again: each
    part keeps its id where it can (`follow`), the revision goes up by one, and every part
    is marked changed, so a form opened before is told to reload. The record is kept only
    holding the engine's `files`; without it, the same file reads the same way."""
    root = store.root
    file = workspace.managed(root, workspace.artifact(root, workspace.load(root), name)['file'])
    digest = workspace.sha256_file(file)
    if digest is None:
        raise ValueError(UNWRITTEN.format(it=workspace.sentence(workspace.label(name))))
    try:
        before = store.read(name)
    except ValueError:
        before = None
    if before is not None and before.get('file_sha256') == digest:
        return before
    draft = follow(before, codec.split(file.read_bytes().decode('utf-8')))
    revision = (before or {}).get('revision', 0) + 1
    draft.update(revision=revision, updated_at=store.now(), file_sha256=digest,
                 changed={} if before is None else {
                     part: revision for part in (*codec.fixed, *(
                         section['id'] for section in draft['sections']))})
    if store.held():
        store.write_json(store.path(name, 'draft.json'), draft)
    return draft


# What History calls each version, by the change that came after it: a save with no kind of
# change (one from before the desk) is "Saved", and a history file no save names is "An
# earlier version".
EARLIER = 'earlier'
SOURCE_WORDS = {'save': 'Saved', 'rewrite': 'Rewritten',
                'revise-all': 'Revised with the whole note', 'selection': 'Selection',
                'restore': 'Restored', 'google': "Before Google's text", 'finishing': 'Finishing',
                'update': 'Updated', EARLIER: 'An earlier version'}
HEX = re.compile(r'[0-9a-f]{64}')


class HistoryVersions:
    """Piece 3's `Versions` over the versions a training already keeps, with no file of its
    own: each save keeps the whole file by its hash (`workspace.snapshot`) and is an event
    with its time, and on the desk its kind of change (`via`) and the page's session.

    A part's versions are its texts in those files, newest first: each event's file
    labelled by the change that came after it, then the history files no event names
    ("An earlier version", with no time: copies kept before a hand edit outside the
    desk). Each file is split by the codec and the part followed across them by heading,
    then note, then place (`follow`). A version whose file is gone is left out, the same
    text twice running is one version, and saves from one editing session are one, the
    text before the first of them. At most piece 3's cap are listed per part. Reading
    writes nothing: `keep` records nothing, `workspace.save` having kept the file."""

    def __init__(self, store: TrainingStore, codec: parts.Codec,
                 keep: int = desk_versions.KEEP):
        self.store, self.codec, self.most = store, codec, keep
        self.sources = workspace.VIA

    def keep(self, ident, part, text, source, session=None, extra=None):
        """Nothing to keep: the save that follows keeps the file and its event says how."""
        require_held(self.store)
        if source not in self.sources:
            raise ValueError(workspace.NO_VIA)

    def kept(self, ident, part):
        """A part's versions, newest first, as Restore reads them."""
        if not self.codec.known(part):
            raise ValueError('Choose a part of this ' + self.codec.thing + '.')
        return self._history(ident, part).get(part, [])

    def versions(self, ident, part):
        """A part's versions, newest first, each as the page shows it."""
        return [entry if self.codec.shown(entry['text']) == entry['text']
                else {**entry, 'text': self.codec.shown(entry['text'])}
                for entry in self.kept(ident, part)]

    def counts(self, ident):
        """How many versions each part has, for parts that have any."""
        return {part: len(found) for part, found in self._history(ident).items() if found}

    def _states(self, root: Path, name: str, now: str, suffix: str) -> list[tuple]:
        """The material's earlier files, newest first, each as (hash, the change that came
        after it); a run of saves from one session is one change, its first."""
        events = [event for event in workspace.load(root)['events']
                  if event.get('event') == 'save' and event.get('artifact') == name
                  and isinstance(event.get('sha256'), str)]
        states = []
        for at, event in enumerate(events):
            after = events[at + 1] if at + 1 < len(events) else None
            if after is None:
                if event['sha256'] != now:   # changed since outside the desk, not saved
                    states.append((event['sha256'], {'at': None, 'via': EARLIER}))
                continue
            if (event.get('session') and event.get('via') == after.get('via') == 'save'
                    and after.get('session') == event['session']):
                continue   # partway through one editing session
            states.append((event['sha256'], after))
        states.reverse()
        named = {event['sha256'] for event in events} | {now}
        folder = workspace.history_file(root, name, now, suffix).parent
        earlier = [] if folder.is_symlink() or not folder.is_dir() else [
            path for path in folder.iterdir()
            if path.suffix == suffix and HEX.fullmatch(path.stem) and path.stem not in named
            and path.is_file() and not path.is_symlink()]
        earlier.sort(key=lambda path: (-path.stat().st_mtime, path.name))
        return states + [(path.stem, {'at': None, 'via': EARLIER, 'unnamed': True})
                         for path in earlier]

    def _history(self, name: str, only: str | None = None) -> dict:
        """Every part of the material as it is now, with its versions; with `only`, read
        as far as that part needs.

        A file no event names is not in the run of saves: its text is listed only where it
        is neither the part's text now nor a version already listed."""
        root = self.store.root
        try:
            draft = current(self.store, self.codec, name)
        except ValueError:   # not written yet, or a file its codec cannot read
            return {}
        suffix = Path(workspace.artifact(root, workspace.load(root), name)['file']).suffix
        names = (*self.codec.fixed, *(section['id'] for section in draft['sections']))
        now = {part: self.codec.text_of(draft, part) for part in names}
        last, found = dict(now), {part: [] for part in names}
        wanted = names if only is None else (only,) if only in names else ()
        for digest, after in self._states(root, name, draft['file_sha256'], suffix):
            if all(len(found[part]) >= self.most for part in wanted):
                break
            path = workspace.history_file(root, name, digest, suffix)
            if path.is_symlink() or not path.is_file():
                continue   # a version whose file is gone is left out
            try:
                older = follow(draft, self.codec.split(path.read_bytes().decode('utf-8')))
            except (ValueError, UnicodeDecodeError):
                continue
            ids = {section['id'] for section in older['sections']}
            for part in names:
                if part not in self.codec.fixed and part not in ids:
                    continue
                text = self.codec.text_of(older, part)
                listed = (text == now[part] or any(
                    entry['text'] == text for entry in found[part])) if after.get(
                    'unnamed') else text == last[part]
                if not listed and len(found[part]) < self.most:
                    found[part].append({'at': after.get('at'),
                                        'source': after.get('via') or 'save',
                                        'text': text, 'words': len(text.split())})
                last[part] = text
            draft = older
        return found


class TrainingDesk(desk_record.Desk):
    """Piece 3's desk over a training's store and one material's codec. A read follows the
    file (`current`); a save names its kind of change, one of `workspace.VIA`, and the page's
    session, which go on the material's save event; a locked part (Sources) is never typed
    in. History is the material's own history files (`HistoryVersions`), with no second
    store."""

    def __init__(self, store: TrainingStore, codec: parts.Codec, versions=None):
        super().__init__(store, codec, workspace.VIA,
                         versions if versions is not None else HistoryVersions(store, codec))

    def read(self, ident: str) -> dict:
        return current(self.store, self.codec, ident)

    def save(self, ident, seen, part, text, source='save', session=None):
        require_held(self.store)   # before the kind of change is set on the store
        if source not in workspace.VIA:
            raise ValueError(workspace.NO_VIA)
        if part not in self.codec.fixed and (
                self.codec.section(self.read(ident), part) or {}).get('locked'):
            raise ValueError(LOCKED)
        if isinstance(self.codec, WholeCodec) and self.codec.text_of(self.read(ident), part) == text:
            return self.read(ident)
        with self.store.making(source, session):
            return super().save(ident, seen, part, text, source=source, session=session)


# --- a card's parts: typing, History and Restore -----------------------------------------
#
# The page types into one part at a time, against the revision its form saw. Each save goes
# through the desk holding the engine's `files`, so the part ids the page holds are the ones
# the record keeps, and it is answered with the card's view: the card, its parts as the save
# left them, and the whole desk, which a save changes too (a Ready card is a draft again, and
# what is built from it is held). The engine commits the saves together.

PART_KEYS = ('id', 'heading', 'text', 'locked', 'covers', 'findings')


def desk_of(engine, root: Path, name) -> TrainingDesk:
    """The desk over one material of a training, refused for one not written in parts."""
    root = Path(root)
    if not isinstance(name, str) or name not in workspace.artifact_names(
            root, workspace.load(root)):
        raise ValueError(NO_PARTS)
    return TrainingDesk(TrainingStore(engine, root), codec_of(name))


def parts_of(desk: TrainingDesk, name: str, draft: dict) -> dict:
    """A material's parts as the page shows them: {'revision', 'opening', 'sections',
    'versions'}, each section {'id', 'heading', 'text', 'locked'} with its covers or findings
    note, and `versions` how many versions each part with any has."""
    return {'revision': draft['revision'], 'opening': draft.get('opening') or '',
            'sections': [{key: section[key] for key in PART_KEYS if key in section}
                         for section in draft['sections']],
            'versions': desk.versions.counts(name)}


def card(engine, root, name: str, draft: dict | None = None,
         desk: TrainingDesk | None = None) -> dict:
    """One card's view: the desk's card for the material (`view`), its parts (`parts_of`),
    `working`, the desk job changing it or None, and `desk`, the whole desk's view. Read it
    holding `files`, so the record that names the parts is the one kept."""
    from runner import draft_finish
    root = Path(root)
    if workspace.split(name)[0] == 'deck':
        return draft_finish.deck_card(engine, root, name)
    desk = desk if desk is not None else desk_of(engine, root, name)
    draft = draft if draft is not None else desk.read(name)
    whole = view(engine, root)
    found = next((one for one in whole['cards'] if one['name'] == name),
                 {'name': name, 'label': workspace.label(name)})
    job = whole['job']
    run = run_of(root) or {}
    return {**found, **parts_of(desk, name, draft), **whole_parts(engine, root, name, draft),
            'finishing': draft_finish.proposals(engine, root, name).summary(name, draft),
            'finish_prices': draft_finish.prices(name),
            'working': job if job and job.get('name') == name else None,
            'jobs': [dict(one) for one in (run.get('drafts') or {}).get('jobs', []) if one.get('name') == name],
            'chain': _chain(run, name), 'start': _start(whole),
            'readonly': _reading(engine, root, name), 'desk': whole}


def whole_parts(engine, root, name, draft):
    """Copy fields and limits come from the same parser/profile as the Yoodli checks."""
    kind = workspace.split(name)[0].partition(':')[0]
    if kind not in ('scenario', 'yoodli'):
        return {}
    fields = []
    if kind == 'yoodli':
        parsed, _ = checks.fenced_fields(draft['opening'])
        limits = (home.read_json(workspace.profile_for(root), {}) or {}).get('limits', {})
        for heading, text in parsed.items():
            key = 'context_chars' if heading == ('Context',) else next((key for field, key
                in checks.YOODLI_GOAL_LIMITS if heading[0] == 'Goals' and heading[-1] == field), None)
            fields.append({'heading': list(heading), 'text': text,
                           'limit': (limits.get(key) or {}).get('value')})
    run = run_of(root) or {}
    return {'whole': True, 'fields': fields,
            'own': kind == 'scenario' and name in engine._survey(root, run).own}


def _reading(engine, root, name):
    from runner import draft_jobs
    return draft_jobs.readonly(engine, root, name)


def _chain(run, name):
    job = next((j for j in reversed((run.get('drafts') or {}).get('jobs', []))
                if j.get('name') == name and j.get('chain')), None)
    if job is None:
        return None
    return {'working': basis.busy(job), 'total': job['total'], 'revised': len(job['done']),
            'problems': job.get('problems') or []}


def _start(whole):
    progress = whole['progress']
    if not progress['running'] or whole['job']:
        return None
    return {**progress, 'status': 'working', 'busy': False, 'steps': [], 'step': None,
            'minutes_left': progress['minutes'], 'phase': progress['doing'], 'problem': None}


def _saved(desk: TrainingDesk, name: str, save) -> tuple[dict, bool, str | None]:
    """Make one save: (the draft after it, whether the file changed, and why the desk could
    not accept it, or None). The file is saved before the desk accepts it, so a save the
    desk refuses afterwards is still made, and said."""
    root = desk.store.root
    file = workspace.managed(root, workspace.artifact(root, workspace.load(root), name)['file'])
    before = workspace.sha256_file(file)
    try:
        draft, said = save(), None
    except workspace.WorkspaceError as refusal:
        if workspace.sha256_file(file) == before:
            raise
        draft, said = desk.read(name), str(refusal)
    return draft, workspace.sha256_file(file) != before, said


def save_part(engine, root, name, part, seen, text, session=None) -> tuple:
    """Save what was typed into one part, against the revision the form saw (`seen`), as an
    edit with `via: 'save'` and the page's session. Call it holding `files`. Returns
    (desk, draft, changed, said): see `_saved`."""
    desk = desk_of(engine, root, name)
    return (desk, *_saved(desk, name, lambda: desk.save(name, seen, part, text, 'save',
                                                        session)))


def restore_part(engine, root, name, part, seen, index) -> tuple:
    """Bring back one of a part's versions (`index`, newest first, as History lists them),
    saved with `via: 'restore'`; the text it replaces is then a version too. Call it holding
    `files`. Returns as `save_part` does."""
    desk = desk_of(engine, root, name)
    return (desk, *_saved(desk, name, lambda: desk.restore(name, seen, part, index)))


def versions_of(engine, root, name, part) -> dict:
    """A part's History: {'versions': newest first, each {'at', 'source', 'label', 'text',
    'words'}, `label` the words History shows for it; 'sources': those words by kind of
    change}, for the page's kit."""
    found = desk_of(engine, root, name).versions.versions(name, part)
    return {'versions': [{**one, 'label': SOURCE_WORDS.get(one['source'], SOURCE_WORDS[EARLIER])}
                         for one in found],
            'sources': dict(SOURCE_WORDS)}


def section_price(record: dict, level: str | None, section: str) -> str:
    """Describe the work and the last recorded cost of redrawing a section."""
    from runner import pipeline
    from studio_core import stops
    level = level or None
    number = pipeline.numbered(section)
    numbers = sorted((((record.get('deck') or {}).get(level or '') or {})
                      .get('section_numbers') or {}).get(section) or [])
    if len(numbers) == 1:
        slides = f'slide {numbers[0]}'
    elif len(numbers) > 2 and numbers == list(range(numbers[0], numbers[-1] + 1)):
        slides = f'slides {numbers[0]} to {numbers[-1]}'
    elif numbers:
        slides = 'slides ' + ', '.join(map(str, numbers[:-1])) + f' and {numbers[-1]}'
    else:
        slides = 'its slides'
    says = (f'Redraws section {number} ({slides}); the other slides stay exactly as they are. '
            'Then the deck is put together, rendered and checked. ')
    steps = record.get('steps') or {}
    drawings = [((steps.get(workspace.qualify(kind, level) + f':{number}') or {})
                 .get('attempts') or []) for kind in ('deck-sections', 'deck-repair')]
    tried = [attempts[-1] for attempts in drawings if attempts]
    if not tried:
        return says + ('This computer has no record yet of what it costs. '
                       'Expect minutes, not seconds.')
    drawn = max(tried, key=lambda attempt: attempt.get('started_at') or '')
    attempts = [drawn]
    for kind in ('deck-whole', 'deck-review'):
        earlier = (steps.get(workspace.qualify(kind, level)) or {}).get('attempts') or []
        if earlier:
            attempts.append(earlier[-1])
    seconds = sum(float(attempt.get('seconds') or 0) for attempt in attempts)
    costs = [attempt.get('dollars') for attempt in attempts if attempt is drawn or
             attempt.get('dollars') is not None]
    dollars = None if any(cost is None for cost in costs) else sum(costs)
    return says + f'Last time this took {stops.cost(seconds, dollars)}.'


def deck_drawings(root: Path, level: str | None) -> dict:
    """Fingerprint the actual drawing of each slide, including lead slides."""
    import json
    from runner import pipeline
    built = pipeline.read_built(root, level)
    start = built.get('start') or {}
    work = pipeline.place(root, level, pipeline.WORK)
    folder = work / str(start.get('folder') or '')
    paths = [work / entry['file'] for entry in (built.get('sections') or {}).values()
             if entry.get('file')]
    paths.extend(folder.glob('lead-*.json'))
    found = {}
    for path in paths:
        data = home.read_json(path, {}) or {}
        for slide in data.get('slides') or ():
            if isinstance(slide, dict) and isinstance(slide.get('id'), str):
                found[slide['id']] = hashlib.sha256(json.dumps(
                    slide, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return found


class DeckProposalDesk:
    """The saved deck revision used to check a finding before it becomes a note."""
    codec = parts.Codec(fixed=(), single=(), thing='deck', noun='slide')

    def __init__(self, engine, root, level):
        self.engine, self.root, self.level = engine, root, level

    def read(self, ident):
        name = workspace.qualify('deck', self.level)
        session = workspace.load(self.root)
        file = self.root / workspace.artifact(self.root, session, name)['file']
        return {'seen': workspace.sha256_file(file), 'drawn': deck_drawings(self.root, self.level)}

    def checked(self, draft, seen, parts=None):
        if not seen or seen != draft['seen']:
            raise ValueError('This deck has changed since it was opened. Read the new version before deciding.')


def deck_proposals(engine, root, level, note=None):
    """The shared findings store, scoped to this training's deck."""
    from studio_core.drafting import findings
    store = TrainingStore(engine, root)
    desk = DeckProposalDesk(engine, root, level)
    return findings.Noted(store, desk, {'finish-review': 'review'}, note or (lambda *_: None),
                          owner='training', present=lambda draft, item:
                          (draft.get('drawn') or {}).get(item.get('part')) == item.get('drawn')
                          and item.get('drawn') is not None)


def slide_words(outline: dict, slide: str, field: str, text: str) -> tuple[dict, str]:
    """Return an edited outline and the previous words, without changing the original."""
    import copy

    if not isinstance(text, str) or len(text) > (4000 if field == 'notes' else 2000):
        raise workspace.WorkspaceError('Keep the words to the allowed length.')
    made = copy.deepcopy(outline)
    target = next((item for item in made.get('slides', []) if item.get('id') == slide), None)
    if target is None:
        raise workspace.WorkspaceError('The deck has no such slide.')
    match = re.fullmatch(r'points\[(\d+)\]\.(label|text)', field) if isinstance(field, str) else None
    if match:
        points = target.get('points') or []
        index = int(match[1])
        if index >= len(points):
            raise workspace.WorkspaceError('Choose a part of the slide.')
        target, field = points[index], match[2]
    elif field not in ('title', 'subtitle', 'caveat', 'source', 'notes'):
        raise workspace.WorkspaceError('Choose a part of the slide.')
    old = target.get(field) or ''
    if isinstance(old, dict):
        old = old.get('text') or ''
        target[field]['text'] = text.strip()
    elif text.strip():
        target[field] = text.strip()
    else:
        target.pop(field, None)
    return made, old


def slide_speaker_notes(outline: dict, slide: str, text: str) -> tuple[dict, str]:
    return slide_words(outline, slide, 'notes', text)


def design_words(plan: dict, outline: dict, slide: str, field: str, old: str, text: str) -> dict:
    """Derive approved copy from the edited outline, including title fallbacks."""
    import copy
    from runner import deck
    made = copy.deepcopy(plan)
    target = next((item for item in made.get('slides', []) if item.get('id') == slide), None)
    if target is None:
        raise workspace.WorkspaceError('The approved design has no such slide.')
    original = next((item for item in outline.get('slides', []) if item.get('id') == slide), None)
    edited, found = slide_words(outline, slide, field, text)
    if (found != old or original is None or target.get('title') != original.get('title')
            or target.get('copy') != deck._copy(original)):
        raise workspace.WorkspaceError('The design and the outline have different words. Review the design first.')
    updated = next(item for item in edited['slides'] if item['id'] == slide)
    target['title'], target['copy'] = updated['title'], deck._copy(updated)
    target.pop('visibleText', None)  # Harness Slides derives this from its copy.
    if field != 'title' and target.get('qualifications'):
        target['qualifications'] = [text.strip() if value == old else value
                                    for value in target['qualifications']]
    return made


SLIDE_SOURCES = ('save', 'selection', 'note', 'redraw', 'restore', 'outline', 'finishing', 'open', 'update')
SLIDE_WORDS = ('title', 'subtitle', 'points', 'caveat', 'source', 'notes')
# Harness Slides outline and composition IDs; new slides must satisfy both.
SLIDE_ID = re.compile(r'[a-zA-Z_][a-zA-Z0-9_-]{4,40}')
# Older desk versions accepted short, digit-leading and longer lowercase IDs.
# Keep their saved History readable without allowing separators or path traversal.
SLIDE_CODEC = parts.Codec(fixed=(), single=(), part=re.compile(
    r'(?:[a-zA-Z_][a-zA-Z0-9_-]{4,40}|[a-z0-9][a-z0-9-]{0,79})'),
                          thing='deck', noun='slide')


class DeckStore(TrainingStore):
    """Shared slide words beside the outline; drawings remain local under work/deck."""
    def folder(self, name):
        from runner import pipeline
        if workspace.split(name)[0] != 'deck' or name not in workspace.artifact_names(self.root, workspace.load(self.root)):
            raise ValueError('Choose a level with a slide deck.')
        return plain_deck_path(self.root, pipeline.place(self.root, workspace.split(name)[1], 'deck'))


def plain_deck_path(root, path):
    """Never follow a linked History directory, including an existing parent."""
    root, path = Path(root), Path(path)
    if root not in path.parents:
        raise workspace.WorkspaceError('Choose a saved slide version.')
    for item in (path, *path.parents):
        if item == root:
            break
        if item.is_symlink():
            raise workspace.WorkspaceError('Slide History must use plain files inside this training.')
    return path


def slide_history(engine, root):
    return desk_versions.Versions(DeckStore(engine, root), SLIDE_CODEC, SLIDE_SOURCES)


def words_of(slide):
    return {key: slide.get(key) for key in SLIDE_WORDS}


def with_slide_words(outline, slide, wanted):
    made = json.loads(json.dumps(outline))
    target = next(item for item in made['slides'] if item['id'] == slide)
    for key in SLIDE_WORDS:
        if wanted.get(key) is None:
            target.pop(key, None)
        else:
            target[key] = wanted[key]
    return made


def word_changes(now, wanted):
    """Individual editable fields, including each point's text."""
    if len(now.get('points') or []) != len(wanted.get('points') or []):
        raise workspace.WorkspaceError('The slide has another number of points now.')
    changes = []
    for field in SLIDE_WORDS:
        if field == 'points':
            fields = [(f'points[{i}].{key}', point.get(key) or '',
                       (wanted['points'][i].get(key) or ''))
                      for i, point in enumerate(now.get('points') or []) for key in ('label', 'text')]
        else:
            def text(value):
                return value.get('text', '') if isinstance(value, dict) else value or ''
            fields = [(field, text(now.get(field)), text(wanted.get(field)))]
        changes.extend((field, old, new) for field, old, new in fields if old != new)
    return changes


def drawing_file(root, level, slide):
    from runner import pipeline
    built = pipeline.read_built(root, level)
    work = pipeline.place(root, level, pipeline.WORK)
    start = built.get('start') or {}
    section = next((part for part in start.get('sections') or [] if slide in part['slides']), None)
    if section:
        entry = (built.get('sections') or {}).get(section['id']) or {}
        return work / entry['file'] if entry.get('file') else None
    return next((file for file in (work / str(start.get('folder') or '')).glob('lead-*.json')
                 if any(item.get('id') == slide for item in home.read_json(file, {}).get('slides', []))), None)


def keep_slide(engine, root, level, slide, source):
    import json
    from runner import pipeline
    outline = home.read_json(pipeline.place(root, level, pipeline.OUTLINE), {})
    current = next((item for item in outline.get('slides', []) if item.get('id') == slide), None)
    if current is None:
        return
    versions = slide_history(engine, root)
    name = workspace.qualify('deck', level)
    versions.keep(name, slide, json.dumps(words_of(current), ensure_ascii=False), source)
    entry = versions.kept(name, slide)[0]
    stamp = re.sub(r'[^0-9A-Za-z]', '', entry['at'])
    file = drawing_file(root, level, slide)
    drawn = next((item for item in (home.read_json(file, {}) if file else {}).get('slides', [])
                  if item.get('id') == slide), None)
    if drawn is not None:
        folder = plain_deck_path(root, pipeline.place(root, level, f'work/deck/versions/{slide}'))
        versions.store.write_json(plain_deck_path(root, folder / f'{stamp}.json'), drawn)
        number = next((i for i, item in enumerate(outline['slides'], 1) if item['id'] == slide), None)
        picture = pipeline.place(root, level, pipeline.SHOTS) / f'{number}.png'
        if picture.is_file() and not picture.is_symlink():
            versions.store.atomic(plain_deck_path(root, folder / f'{stamp}.png'), picture.read_bytes())


def slide_versions(engine, root, level, slide):
    import json
    from runner import pipeline
    found = []
    for entry in slide_history(engine, root).kept(workspace.qualify('deck', level), slide):
        try:
            words = json.loads(entry['text'])
        except ValueError:
            continue
        stamp = re.sub(r'[^0-9A-Za-z]', '', entry['at'])
        folder = plain_deck_path(root, pipeline.place(root, level, f'work/deck/versions/{slide}'))
        found.append({'at': entry['at'], 'source': entry['source'], 'words': words,
                      'stamp': stamp, 'drawing': plain_deck_path(root, folder / f'{stamp}.json').is_file(),
                      'picture': plain_deck_path(root, folder / f'{stamp}.png').is_file()})
    return {'versions': found}


def deck_card(engine, root, level, found):
    from runner import pipeline, deck
    from studio_core import stops
    mine = found.decks.get(level)
    if mine is None:
        return {'slides': [], 'local': False}
    outline = home.read_json(pipeline.place(root, level, pipeline.OUTLINE), {})
    counts = slide_history(engine, root).counts(mine.name)
    record = engine._load(root)
    drawn = deck_drawings(root, level)
    slides = []
    for number, item in enumerate(outline.get('slides') or [], 1):
        section = next((part['id'] for part in mine.start.get('sections') or []
                        if item['id'] in part['slides']), None)
        slides.append({**words_of(item), 'id': item['id'], 'number': number,
                       'picture': (pipeline.place(root, level, pipeline.SHOTS) / f'{number}.png').is_file(),
                       'history': counts.get(item['id'], 0),
                       'price': section_price(record, level, section) if section else '',
                       'redraw': bool(section)})
    estimate = deck.before(len(slides))
    cost = engine._redo_steps(record, [workspace.qualify(kind, level)
        for kind in ('deck-sections', 'deck-whole', 'deck-review')])
    price = ('Redraws the whole deck. ' + (f'Last time this took {stops.cost(*cost)}.' if cost else
             'Expect about ' + stops.cost(estimate['minutes'] * 60, estimate['dollars']) + '.'))
    from runner import deck_edit
    selection = next((job for job in reversed((record.get('drafts') or {}).get('jobs', []))
                      if job.get('name') == mine.name and job.get('kind') == 'slide-selection'), None)
    if selection:
        selection = {**selection, 'result': home.read_json(
            deck_edit.storage(root) / f"selection-{selection['id']}.json", None)}
    chain = mine.kept.get('note_chain') or {}
    notes = [note for note in mine.kept.get('notes') or [] if note['id'] in chain.get('ids', [])]
    done = sum(all(note['status'] == 'done' for note in notes if note['section'] == section)
               for section in chain.get('sections', []))
    return {'slides': slides, 'local': bool(drawn), 'look_price': price,
            'change': {**chain, 'done': done, 'total': len(chain.get('sections', []))} if chain else None,
            'outline': outline, 'outline_delivery': pipeline.delivery_of(found.session), 'selection': selection,
            'look': (mine.kept.get('look_pending') or None)}


def check_added_slide(slide, delivery):
    allowed = {'id', 'kind', 'title', 'understand', 'relation', 'rhythm', 'points', 'sources', 'notes'}
    if set(slide) - allowed or slide.get('kind') != 'content' or slide.get('points') != [] \
            or slide.get('relation') != 'none' or slide.get('rhythm') != 'breathing' \
            or slide.get('understand') != slide.get('title'):
        raise workspace.WorkspaceError('Add a content slide with its title, objectives and speaker notes.')
    if not isinstance(slide.get('sources'), list) or not slide['sources'] \
            or any(not isinstance(item, str) for item in slide['sources']):
        raise workspace.WorkspaceError('Choose the objectives the new slide serves.')
    notes = slide.get('notes', '')
    if not isinstance(notes, str) or len(notes) > 2000 or (delivery == 'live' and not notes.strip()):
        raise workspace.WorkspaceError('A live slide needs speaker notes, up to 2,000 characters.')


def added_slide_design(slide):
    """A transparent, text-only proposal for a person's added slide; still needs approval."""
    from runner import deck
    return {'id': slide['id'], 'title': slide['title'], 'copy': deck._copy(slide),
            'sources': slide['sources'], 'objectives': slide['sources'],
            **({'notes': slide['notes']} if slide.get('notes') else {}),
            'composition': 'Show the requested title as a single native text block with generous space.',
            'intent': {'takeaway': slide['title'], 'audienceQuestion': 'What should I practise next?',
                       'relationship': 'none', 'evidence': slide['sources'],
                       'rationale': 'This added slide states the person’s requested topic without adding claims.',
                       'alternative': {'treatment': 'An illustration',
                                       'reason': 'No illustration was requested or supplied for this topic.'},
                       'visual': {'family': 'text', 'purpose': 'Name the requested topic clearly.'}},
            'asset': {'description': 'No asset.', 'disposition': 'not-needed',
                      'reason': 'The requested title is the slide; no picture is needed to state it.'}}


def select_materials(root: Path, record: dict, selection: dict) -> None:
    """Apply an explicit finite conversation request, preserving all existing content."""
    from runner import pipeline
    allowed = {'materials', 'deck_target', 'brand', 'yoodli'}
    if not isinstance(selection, dict) or not set(selection) <= allowed:
        raise workspace.WorkspaceError('Choose materials, deck_target, brand or yoodli only.')
    if not in_conversation(record):
        raise workspace.WorkspaceError('Requested materials change only on a conversation desk.')
    if 'materials' in selection and (not isinstance(selection['materials'], list) or len(selection['materials']) > 20):
        raise workspace.WorkspaceError('Give materials as a finite list.')
    session = workspace.load(root)
    current = session['settings']
    if not isinstance(current['stages'], list) or any(stage not in workspace.SKIPPABLE for stage in current['stages']):
        raise workspace.WorkspaceError('This saved material selection cannot be changed safely.')
    brand, _, variant = str(current.get('brand') or '').partition('/')
    form = {**pipeline.answers(root), 'title': session['title'], 'levels': session['levels'],
            'brief_kind': current['brief_kind'], 'delivery': current['delivery'],
            'materials': [kind for kind in pipeline.MATERIALS if kind in current['stages']],
            'deck_target': current['deck_target'],
            'brand': {'brand': brand, 'variant': variant} if brand else None,
            'yoodli': 'yoodli' in current['stages'], 'research_from': pipeline.research_of(record),
            **selection}
    checked = pipeline.check_form(form, conversation=True)
    has_deck = workspace.deck_written(root, session) or bool(session.get('pending_local_decks')) or any(
        workspace.qualify('deck', level) in session['artifacts'] or
        (root / workspace.prefix(level) / 'deck-link.md').exists() or
        (root / workspace.prefix(level) / 'deck.pptx').exists()
        for level in session['levels'] or [None])
    if has_deck and any(key in selection and checked[key] != current[key]
                        for key in ('deck_target', 'brand')):
        raise workspace.WorkspaceError('This deck already has saved work. Keep its target and brand; conversion needs its own explicit saved-work path.')
    stages = set(current['stages'])
    if 'materials' in selection:
        stages.difference_update(pipeline.MATERIALS)
        stages.update(checked['materials'])
    if 'deck_target' in selection:
        stages.discard('deck')
        if checked['deck_target'] is not None:
            stages.add('deck')
        current['deck_target'] = checked['deck_target']
    if 'brand' in selection:
        current['brand'] = checked['brand']
    if 'yoodli' in selection:
        stages.discard('yoodli')
        if checked['yoodli']:
            stages.add('yoodli')
    current['stages'] = [stage for stage in workspace.SKIPPABLE if stage in stages]
    workspace.log(session, 'requested-materials', by='conversation-person', selection=selection)
    workspace.store(root, session)
