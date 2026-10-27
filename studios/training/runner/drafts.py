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
"""
from __future__ import annotations

from pathlib import Path

import workspace
from studio_core import review_policy
from studio_core.drafting import basis

import runner  # noqa: F401  puts the core on the import path

FLOW = 'desk'
SCHEMA = 4
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
    spec = workspace.artifact(root, session, name)
    state = workspace.statuses(root, session) if state is None else state
    waiting = next((upstream for upstream in spec['upstream']
                    if upstream in holding or state.get(upstream) == 'stale'), None)
    if waiting is not None:
        return WAITING.format(what=f'the {what(waiting)}')
    if name not in holding:
        return None
    changed = _changed(root, session, name, [*spec['upstream'], *spec['extras']])
    if 'practice' in changed:
        return PRACTICE
    return HELD.format(what=' and '.join(what(key) for key in changed))


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
