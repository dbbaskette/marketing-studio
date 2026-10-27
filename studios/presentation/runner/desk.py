"""The deck desk: what a deck started from the desk's start holds, and what its desk shows.

What a caller needs to know
---------------------------
    desk.passes(run, 'gate:outline')          # a stop the desk deck continues past
    desk.receipt(run, gate, evidence, at)     # the desk's receipt, never a person's
    desk.arrive(run)                          # True the first time the deck reaches the desk

- A desk deck is a run record with `flow: 'desk'` (decks.on_desk). It runs the same
  `stages.PIPELINE` as any other deck. Its stops before the deck are continued with a
  receipt `by: 'desk'` in `review_events` (PASSED); gate:look waits only when the start chose
  to pick the look; gate:build waiting is the desk itself, and Deliver is its approval.
- A desk note is a person's note on one slide (or, with `slide` None, on the whole deck),
  kept in `run['desk_notes']` as {'id', 'slide', 'number', 'section', 'note', 'at', 'by',
  'status'}. 'waiting' notes are drawn at the next safe point of the run; 'drawing' notes
  are in their section's ask and go to its composer once; 'done' once the section is kept;
  'set aside' when Stop took the section off the ask. A note is never sent to a composer
  twice: a composer is handed only its section's 'drawing' notes, and keeping the section
  makes them 'done'.
- Nothing here starts a job, takes the engine's lock or writes a file: the engine's desk
  actions (runner/desk_actions.py) do that, holding `files`.
"""
from __future__ import annotations

import secrets

import runner  # noqa: F401  puts the core on the import path
import home
from studio_core import review_policy, stops
from workspace import WorkspaceError

from runner import decks, stages

PASSED = ('gate:classify', 'gate:research-plan', 'gate:research', 'gate:outline')
DECISION = 'continued-on-the-desk'
CONTINUED = 'Continued on the desk.'

ON_DESK = 'This deck is on the desk. Change it there.'
NOT_ON_DESK = ('This deck is not on the desk. Use its own screen, or open it on the desk '
               'once it is finished.')

STATUSES = ('waiting', 'drawing', 'done', 'set aside')
OPEN = ('waiting', 'drawing')


# --- the stops ----------------------------------------------------------------------------

def passes(run: dict, gate: str) -> bool:
    """Whether a desk deck continues past `gate` with the desk's receipt: every stop before
    the look, and the look itself when the start chose the brand's default."""
    if gate in PASSED:
        return True
    return gate == 'gate:look' and (run.get('form') or {}).get('look') == 'default'


def receipt(run: dict, gate: str, evidence, at: str, note: str | None = None) -> None:
    """Record that the desk continued `gate`, bound to what it showed. A desk receipt is
    never a person's: delivering is."""
    run.setdefault('review_events', []).append({
        'gate': gate, 'by': 'desk', 'evidence': review_policy.fingerprint(evidence), 'at': at,
        'decision': DECISION, **({'note': str(note)} if note else {})})


def refuse_on_desk(run: dict) -> None:
    if decks.on_desk(run):
        raise WorkspaceError(ON_DESK)


def refuse_off_desk(run: dict) -> None:
    if not decks.on_desk(run):
        raise WorkspaceError(NOT_ON_DESK)


def arrived(run: dict) -> bool:
    return bool((run.get('desk') or {}).get('arrived_at'))


def arrive(run: dict) -> bool:
    """The first time a desk deck's gate:build waits, it is on the desk. What was sent while
    its sections were drawn was drawn then, so it is put aside and never sent again; a note
    that came too late for its section stays, as a desk note to draw. True the first time."""
    if arrived(run):
        return False
    run['desk'] = {**(run.get('desk') or {}), 'arrived_at': home.now()}
    left = []
    for item in run.get('build_feedback') or ():
        if item.get('late') and item.get('number'):
            run.setdefault('desk_notes', []).append(note_of(
                item.get('slide'), item['number'], item.get('section'), item['note'],
                item.get('at') or home.now(), None))
        else:
            left.append(item)
    run['build_feedback_done'] = [*(run.get('build_feedback_done') or []), *left]
    run['build_feedback'] = []
    return True


# --- desk notes ---------------------------------------------------------------------------

def note_of(slide: str | None, number: int | None, section: str | None, note: str, at: str,
            by, status: str = 'waiting') -> dict:
    return {'id': secrets.token_hex(6), 'slide': slide, 'number': number, 'section': section,
            'note': note, 'at': at, 'by': by, 'status': status}


def notes(run: dict) -> list[dict]:
    return [item for item in run.get('desk_notes') or () if isinstance(item, dict)]


def pending(run: dict, section: str) -> list[dict]:
    """The notes a composer of `section` is handed: those in its ask now."""
    return [item for item in notes(run)
            if item.get('section') == section and item.get('status') == 'drawing']


def busy(run: dict, section: str) -> bool:
    """Whether `section` is being redrawn for a note now."""
    return bool(pending(run, section))


def settle_notes(run: dict, section: str) -> None:
    """The section was kept: the notes it was drawn for are done."""
    for item in notes(run):
        if item.get('section') == section and item.get('status') == 'drawing':
            item.update(status='done', done_at=home.now())


def waiting(run: dict) -> list[dict]:
    return [item for item in notes(run) if item.get('status') == 'waiting']


def opened(run: dict) -> list[dict]:
    return [item for item in notes(run) if item.get('status') in OPEN]


def ask(state: dict, sections) -> None:
    """Add `sections` to the build's ask, keeping what it asks already, so `build.to_draw`
    draws them in the next chain. A desk ask has no note of its own: the composer reads
    its section's desk notes."""
    asked = state.get('asked') or {}
    had = list(asked.get('sections') or ())
    union = had + [section for section in sections if section not in had]
    state.update(asked={'note': None, 'sections': union, 'at': home.now()}, repaired=0)


def reopen(run: dict) -> dict:
    """Send a desk deck that rests on the desk back to draw what it is asked: gate:build
    asks for changes, with no note of its own, and is reopened, so it waits on the desk
    again once the chain is done. Returns the run."""
    gate = (run.get('gates') or {}).get('gate:build') or {}
    run.setdefault('gates', {})['gate:build'] = {
        **gate, 'state': 'changes', 'by': 'desk', 'note': None, 'slides': None,
        'slide_notes': None, 'at': home.now()}
    return stages.reopen(run, 'gate:build')


def resting(run: dict) -> bool:
    """Whether a desk deck rests on the desk: gate:build waits, and nothing is halted."""
    return ((run.get('gates') or {}).get('gate:build') or {}).get('state') == 'waiting'


def cost(seconds, dollars) -> str:
    return stops.cost(seconds, dollars)
