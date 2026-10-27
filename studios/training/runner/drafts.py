"""The training desk in the runner: what tells a desk run from a saved one, and the sentences
both sides of that line refuse with.

A training started on the desk is a run of schema 4 with `flow: 'desk'` and no review level:
the engine carries it past every gate with a desk receipt, and the person marks each
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

from pathlib import Path

import home
import workspace
from studio_core import research_view, review_policy, step_times
from studio_core.drafting import basis
from studio_core.drafting.store import Store

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
# Until the deck's scoped update (Task 20), an update is of the whole material.
NO_SCOPE = 'An update is of the whole material for now. Leave out what it covers.'
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


def on_desk(record: dict | None) -> bool:
    """Whether a run record, or a form, is a training worked on at the desk."""
    return (record or {}).get('flow') == FLOW


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
    record = home.read_json(Path(root) / RECORD, None)
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
                cards.append({
                    'name': name, 'level': level or '', 'kind': kind,
                    'label': workspace.label(name), 'state': shown, 'says': says,
                    'checks': _checked(report['checks'], name) if seen else
                    {'passed': 0, 'problems': []},
                    'seen': seen, 'held': name in holding,
                    'actions': card_actions if mine else ['download'], 'needs': needs})
    needed = []
    if mine:
        needed = [card['label'] for card in cards if card['state'] in ('held', 'needs')]
        if question:
            needed.append(QUESTION.format(text=question['text']))
        if problem.get('what'):
            needed.append(problem['what'])
        # Everything is Ready, and still no index: what else is in the way is said.
        if not needed and not report['ready'] and cards and all(
                card['state'] in ('ready', 'left-out') for card in cards):
            needed += [desk.plainly_on_desk(reason) for reason in report['blocking']]
    running = state == 'working'
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
        'flow': FLOW, 'title': session['title'], 'levels': [level or '' for level in levels],
        'progress': {'running': running, 'doing': doing,
                     'started_at': record.get('started_at'), 'minutes': minutes,
                     # Said only while nothing on the desk needs the person.
                     'line': NOTHING_NEEDED.format(
                         n=minutes, minutes='minute' if minutes == 1 else 'minutes')
                     if running and not needed else ''},
        'needs': needed, 'cards': cards,
        'sources': {'account': research_view.account(root / 'research', questions),
                    'plan': questions,
                    'documents': [{key: entry.get(key) for key in
                                   ('name', 'bytes', 'readable', 'problem')}
                                  for entry in listed]},
        'job': next((dict(job) for job in reversed(jobs) if basis.busy(job)), None),
        'team': {'ours': mine, 'driver': who, 'last_shared': last}}
