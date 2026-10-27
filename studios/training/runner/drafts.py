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
from studio_core import review_policy
from studio_core.drafting import basis

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


def hold_says(root: Path, session: dict, holding, name: str, state: dict | None = None
              ) -> str | None:
    """What a card says of a hold: that it waits for an input of its own to be updated or
    kept, or what it was built from an earlier version of. None for a card not held."""
    waiting, changed = _hold(root, session, holding, name, state)
    if waiting is not None:
        return WAITING.format(what=f'the {what(waiting)}')
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
