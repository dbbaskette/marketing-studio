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

import hashlib
import re
from contextlib import contextmanager
from pathlib import Path

import checks
import home
import workspace
from studio_core import research_view, review_policy, step_times
from studio_core.drafting import basis, parts
from studio_core.drafting import record as desk_record
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


# --- parts: a training's guide, brief and plan as piece 3's parts ------------------------
#
# A material's file stays the one copy of its text. Each codec splits it into an opening
# (everything before the first `## `, the `# ` title included) and its `## ` sections, and
# joins them back to the same file byte for byte: each part keeps the blank lines around it
# as they were written (`layout`), so a changed part goes into the file as it stood. A
# section's covers or findings note is kept on the section, out of its text.

NO_PARTS = 'Only a guide, a brief or a plan is written in parts.'
BRIEF_SHAPE = 'A brief keeps its eight numbered sections, in order.'
LOCKED = 'Sources is kept from the findings cited. Change the references in the text instead.'
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
    words = rest.rstrip()
    return {'lead': lead, 'line': line, 'gap': gap, 'words': words,
            'tail': rest[len(words):], 'ids': ids}


def _starts(lines: list[str], code_too: bool) -> list[int]:
    """The lines that start a section: each `## ` line outside fenced code, or in it too
    when `code_too` (a brief's check reads every `## ` line)."""
    outside = [True] * len(lines) if code_too else [free for _, free in parts.free(lines)]
    return [at for at, line in enumerate(lines) if outside[at] and SECTION_LINE.fullmatch(line)]


def _split(markdown: str, note: _Note | None, code_too: bool, locked) -> dict:
    """A material's file as its opening and sections, each with how it was written around
    its words; `locked(heading)` says which section is not typed in."""
    lines = markdown.split('\n')
    offsets, at = [], 0
    for line in lines:
        offsets.append(at)
        at += len(line) + 1
    starts = _starts(lines, code_too)
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
                              'blank': not cut['words']}}
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
        head = kept.get('head')
        if not head or SECTION_LINE.fullmatch(head).group(1) != section['heading']:
            head = '## ' + section['heading']
        line, ids = None, section.get(note.key) or [] if note is not None else []
        if note is not None and kept.get('line') is not None:
            line = kept['line'] if note.read(kept['line']) == ids else (
                note.written(ids) if ids else None)
        elif ids:
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
    """The marks of a `## ` heading a part holds outside code, which would start a section."""
    return parts.heading_in(text, 2)


def _sources(heading: str) -> bool:
    return heading.lower() == 'sources'


def _brief_fits(draft: dict, kind: str) -> bool:
    """Whether a brief's sections are its kind's eight, numbered and in order."""
    expected = checks.BRIEF_SECTIONS[kind]
    sections = draft.get('sections') or []
    if len(sections) != len(expected):
        return False
    for number, (section, title) in enumerate(zip(sections, expected, strict=True), 1):
        found = NUMBERED_HEADING.fullmatch(section['heading'])
        if not found or int(found.group(1)) != number \
                or found.group(2).strip().lower() != title.lower():
            return False
    return True


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
                   lambda heading: _sources(heading.partition('. ')[2].strip()))
    draft['kind'] = _brief_kind(draft)
    if not _brief_fits(draft, draft['kind']):
        raise ValueError(BRIEF_SHAPE)
    return draft


def _brief_join(draft: dict) -> str:
    if not _brief_fits(draft, draft.get('kind') or _brief_kind(draft)):
        raise ValueError(BRIEF_SHAPE)
    return _join(draft, FINDINGS_NOTE)


def _brief_heading(text: str, level: int = 2) -> str:
    """A brief's check reads every `## ` line as a section, in code too: a part holds none."""
    return '##' if ANY_SECTION_LINE.search(text) else parts.heading_in(text, 2)


def GuideCodec() -> parts.Codec:
    """A guide: its opening, then each `## ` section with its covers note. Sources, which
    the references resolve to, is kept from the findings and not typed in."""
    return parts.Codec(
        fixed=('opening',), single=(), thing='draft', noun='section',
        split=lambda markdown: _split(markdown, COVERS_NOTE, False, _sources),
        join=lambda draft, after=(): _join(draft, COVERS_NOTE),
        deepest=lambda draft: 2, heading_in=_section_heading)


def BriefCodec() -> parts.Codec:
    """A brief: its title, then its eight numbered sections in order, each with its findings
    note. "8. Sources" is not typed in, and no section is added, taken out or moved."""
    return parts.Codec(
        fixed=('opening',), single=(), thing='draft', noun='section', split=_brief_split,
        join=lambda draft, after=(): _brief_join(draft), deepest=lambda draft: 2,
        heading_in=_brief_heading)


def PlanCodec() -> parts.Codec:
    """A plan: its opening, then the blueprint's `## ` sections, none of them locked."""
    return parts.Codec(
        fixed=('opening',), single=(), thing='draft', noun='section',
        split=lambda markdown: _split(markdown, None, False, lambda heading: False),
        join=lambda draft, after=(): _join(draft, None),
        deepest=lambda draft: 2, heading_in=_section_heading)


CODECS = {'document': GuideCodec(), 'brief': BriefCodec(), 'blueprint': PlanCodec()}


def codec_of(name: str) -> parts.Codec:
    """The codec a material's file is read with, by the material's name."""
    found = CODECS.get(workspace.split(name)[0])
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


class TrainingDesk(desk_record.Desk):
    """Piece 3's desk over a training's store and one material's codec. A read follows the
    file (`current`); a save names its kind of change, one of `workspace.VIA`, and the page's
    session, which go on the material's save event; a locked part (Sources) is never typed
    in. `versions` keeps the text a save replaces: Task 11 passes the material's own history;
    until then, piece 3's version files in the record's folder."""

    def __init__(self, store: TrainingStore, codec: parts.Codec, versions=None):
        super().__init__(store, codec, workspace.VIA, versions)

    def read(self, ident: str) -> dict:
        return current(self.store, self.codec, ident)

    def save(self, ident, seen, part, text, source='save', session=None):
        if source not in workspace.VIA:
            raise ValueError(workspace.NO_VIA)
        if part not in self.codec.fixed and (
                self.codec.section(self.read(ident), part) or {}).get('locked'):
            raise ValueError(LOCKED)
        with self.store.making(source, session):
            return super().save(ident, seen, part, text, source=source, session=session)
