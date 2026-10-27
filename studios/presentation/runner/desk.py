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
    """Each time a desk deck's gate:build waits, it is on the desk; the first time, it
    arrives. What was sent while its sections were drawn was drawn then, so it is put aside
    and never sent again; a note that came too late for its section stays, as a desk note to
    draw. True the first time."""
    first = not arrived(run)
    if first:
        run['desk'] = {**(run.get('desk') or {}), 'arrived_at': home.now()}
    left = []
    for item in run.get('build_feedback') or ():
        if item.get('late') and item.get('number'):
            run.setdefault('desk_notes', []).append(note_of(
                item.get('slide'), item['number'], item.get('section'), item['note'],
                item.get('at') or home.now(), None))
        else:
            left.append(item)
    if left or run.get('build_feedback'):
        run['build_feedback_done'] = [*(run.get('build_feedback_done') or []), *left]
        run['build_feedback'] = []
    return first


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


# --- the desk's cards ---------------------------------------------------------------------

WORDS = ('title', 'subtitle', 'detail', 'points', 'caveat', 'source')
SET_ASIDE = 'Not redrawn: you stopped the whole-deck note.'
REDRAWING = 'Redrawing…'


def _build():
    from runner.steps import build
    return build


def _outline(root) -> dict:
    from runner.steps import outline
    found = home.read_json(root / outline.OUTLINE, None)
    return found if isinstance(found, dict) else {}


def last_round(state: dict) -> dict:
    return (state.get('rounds') or [{}])[-1] or {}


def audit_lines(state: dict, number: int) -> list[dict]:
    """What the last render's brand check says of one slide: {'says', 'kind'}, its blockers
    ('error') first."""
    found = []
    for line in ((state.get('audit') or {}).get('messages') or ()):
        line = str(line)
        head = f'Slide {number}: '
        if not line.startswith(head):
            continue
        said, _, kind = line[len(head):].rpartition(' (')
        kind = kind.rstrip(')')
        found.append({'says': said if kind in ('error', 'warning') else line[len(head):],
                      'kind': kind if kind in ('error', 'warning') else 'warning'})
    return sorted(found, key=lambda one: one['kind'] != 'error')


def blockers(state: dict) -> list[dict]:
    """The last render's brand check lines that block delivery, each with its slide."""
    found = []
    for line in ((state.get('audit') or {}).get('messages') or ()):
        line = str(line)
        if not line.endswith(' (error)'):
            continue
        said = line[:-len(' (error)')]
        number = None
        if said.startswith('Slide ') and ': ' in said:
            head, _, rest = said.partition(': ')
            if head[len('Slide '):].isdigit():
                number, said = int(head[len('Slide '):]), rest
        found.append({'number': number, 'says': said})
    return found


def blockers_seen(state: dict) -> str:
    return review_policy.fingerprint(blockers(state))


def reviewed(state: dict) -> bool:
    """Whether the last round's deck was reviewed."""
    return last_round(state).get('review') is not None


def _parts(root, state: dict, outline: dict) -> list[tuple[str | None, bool, list[str]]]:
    """The deck's parts in order, as (section, lead, slide IDs): the start's parts.json where
    this computer split the deck, else runs of content slides between lead slides."""
    build = _build()
    began = state.get('start') or {}
    by_section = {entry['id']: entry['slides'] for entry in began.get('sections') or ()}
    listed = home.read_json(root / began['folder'] / 'parts.json', {}) if began else {}
    parts = []
    if isinstance(listed, dict) and listed.get('parts'):
        leads = [slide['id'] for slide in build.slides_of(outline)
                 if slide.get('kind') in build.LEADS]
        for part in listed['parts']:
            stem = part.rsplit('/', 1)[-1].rsplit('.', 1)[0]
            if stem in by_section:
                parts.append((stem, False, list(by_section[stem])))
            elif leads:
                parts.append((None, True, [leads.pop(0)]))
        return parts
    run = []
    for slide in build.slides_of(outline):
        if slide.get('kind') in build.LEADS:
            if run:
                parts.append((None, False, run))
                run = []
            parts.append((None, True, [slide['id']]))
        else:
            run.append(slide['id'])
    if run:
        parts.append((None, False, run))
    return parts


def cards(root, run: dict, price=None) -> dict:
    """The desk's slide cards, under the sections the deck was split into, in deck order:
    {'sections': [{'id', 'lead', 'number', 'slides': [card]}], 'expected', 'drawn_here'}.
    A card is {'number', 'id', 'section', 'lead', 'image', 'words', 'notes', 'findings',
    'audit', 'note', 'busy', 'price'}. Its words and notes are the outline's, which every
    computer has; its picture, findings and brand check are this computer's last round, so
    a deck with none here has cards without pictures. `price(section)` says what redrawing
    a section costs."""
    build = _build()
    state = build.read_state(root)
    outline = _outline(root)
    last = last_round(state)
    drawn = bool(state.get('rounds'))
    by_id = {slide['id']: slide for slide in build.slides_of(outline)}
    numbers = {slide['id']: slide['number'] for slide in last.get('slides') or ()} if drawn \
        else {slide['id']: at for at, slide in enumerate(build.slides_of(outline), 1)}
    findings = build.ordered((last.get('review') or {}).get('findings')) if drawn else []
    kept = notes(run)
    sections, counted = [], 0
    for section, lead, ids in _parts(root, state, outline):
        counted += 0 if lead else 1
        busy_now = bool(section) and busy(run, section)
        priced = price(section) if price and section and not lead else ''
        slides = []
        for ident in ids:
            slide = by_id.get(ident) or {}
            number = numbers.get(ident)
            noted = next((item for item in reversed(kept) if item.get('slide') == ident or (
                not item.get('slide') and section and item.get('section') == section)), None)
            slides.append({
                'number': number, 'id': ident, 'section': section, 'lead': lead,
                'kind': slide.get('kind'),
                'image': {'kind': 'build', 'ref': number} if drawn and number else None,
                'words': {key: slide.get(key) for key in WORDS},
                'notes': slide.get('notes') or '',
                'findings': [{key: finding.get(key) for key in (
                    'severity', 'about', 'question', 'note', 'fix')}
                    for finding in findings if finding.get('slide') == ident],
                'audit': audit_lines(state, number) if drawn and number else [],
                'note': _note_shown(noted),
                'busy': busy_now,
                'price': priced})
        sections.append({'id': section, 'lead': lead, 'number': None if lead else counted,
                         'slides': slides})
    return {'sections': sections, 'expected': last.get('deck') if drawn else None,
            'drawn_here': drawn}


def _note_shown(item: dict | None) -> dict | None:
    if not item:
        return None
    says = {'waiting': 'Your note is kept: it is drawn next.', 'drawing': REDRAWING,
            'set aside': SET_ASIDE}.get(item.get('status'))
    return {'note': item.get('note'), 'status': item.get('status'), 'whole': not item.get('slide'),
            **({'says': says} if says else {})}
