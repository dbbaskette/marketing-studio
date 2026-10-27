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
from pathlib import Path

import runner  # noqa: F401  puts the core on the import path
import home
from studio_core import review_policy, step_times, stops
from studio_core.drafting.store import Store
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

BUSY = 'Slide {number} is being redrawn now. Your note is kept here; send it when that ends.'
LEAD = ('A cover, section or closing slide is not drawn by an assistant: change its words on '
        'the Outline tab.')
CHANGED = 'The deck changed since this page read it. Reload it, then try again.'
NO_DRAWING = 'There is no drawing of this deck on this computer.'
NO_NOTE = 'Say how the slide should change.'


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


def section_of(state: dict, number) -> str | None:
    """The section that draws slide `number` of the last round: None for a lead slide,
    which no composer draws. A number the deck's last drawing does not have is refused."""
    rounds = state.get('rounds') or []
    if not rounds:
        raise WorkspaceError(NO_DRAWING)
    if type(number) is not int:
        raise WorkspaceError('Name the slide by its number.')
    ident = next((slide['id'] for slide in rounds[-1]['slides'] if slide['number'] == number),
                 None)
    if ident is None:
        raise WorkspaceError(f'The deck has no slide {number}.')
    return next((entry['id'] for entry in (state.get('start') or {}).get('sections') or ()
                 if ident in entry['slides']), None)


def slide_of(state: dict, number: int) -> str:
    return next(slide['id'] for slide in last_round(state)['slides'] if slide['number'] == number)


def add_note(run: dict, state: dict, number: int, note: str, at: str, by) -> dict:
    """Keep a note on slide `number`, waiting to be drawn. Refused for a lead slide, and
    while its section is being redrawn for another note."""
    section = section_of(state, number)
    if section is None:
        raise WorkspaceError(LEAD)
    if busy(run, section):
        raise WorkspaceError(BUSY.format(number=number))
    item = note_of(slide_of(state, number), number, section, note, at, by)
    run.setdefault('desk_notes', []).append(item)
    return item


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


# --- prices -------------------------------------------------------------------------------

SECTION_SAYS = ('Redraws section {number} ({slides}); the other slides stay exactly as they '
                'are. Then the deck is put together, rendered and checked.')
LAST_TOOK = ' Last time this took {cost}.'
NO_RECORD = (' This computer has no record yet of what it costs. Expect minutes, not '
             'seconds.')
USUALLY = ' Usually about {minutes} here.'
DECK_SAYS = 'Redraws every section.'
DECK_TOOK = ' Last time the whole deck took {cost}.'
SLIDE_NOTE = 'deck:slide-note'      # the step-time estimate's key for a slide note's chain
DECK_NOTE = 'deck:deck-note'        # and for a whole-deck note's


class DeckStore(Store):
    """Presentation Studio's store for the shared desk parts: what this computer keeps of
    how long desk work takes is in its own data folder, never in a deck's."""
    product, word = 'Presentation Studio', 'deck'

    def held(self):
        return True


def times() -> Path:
    return home.data_root() / 'desk' / 'step-times.json'


def usually(key: str) -> str:
    """' Usually about N minutes here.' where this computer has a record of `key`."""
    minutes = step_times.expected(DeckStore(), times(), key, None)
    if minutes is None:
        return ''
    return USUALLY.format(minutes=stops.lasted(round(minutes) * 60))


def took(key: str, seconds: float) -> None:
    step_times.note(DeckStore(), times(), key, seconds)


def slides_words(numbers) -> str:
    """'slide 4', 'slides 4 and 5', 'slides 4 to 6' or 'slides 2, 4 and 6'."""
    numbers = sorted(numbers)
    if len(numbers) == 1:
        return f'slide {numbers[0]}'
    if len(numbers) > 2 and numbers == list(range(numbers[0], numbers[-1] + 1)):
        return f'slides {numbers[0]} to {numbers[-1]}'
    return 'slides ' + ', '.join(map(str, numbers[:-1])) + f' and {numbers[-1]}'


def _last_try(run: dict, name: str, kept: bool = False) -> dict | None:
    tried = [attempt for attempt in ((run.get('steps') or {}).get(name) or {}).get('tries') or ()
             if not kept or attempt.get('outcome') == 'kept']
    return tried[-1] if tried else None


def section_numbers(state: dict, section: str) -> list[int]:
    began = state.get('start') or {}
    ids = next((entry['slides'] for entry in began.get('sections') or ()
                if entry['id'] == section), [])
    shown = {slide['id']: slide['number'] for slide in last_round(state).get('slides') or ()}
    return [shown[ident] for ident in ids if ident in shown]


def section_price(run: dict, state: dict, section: str) -> dict:
    """What redrawing one section costs, said before it is asked: its last kept drawing,
    and the last time the deck was put together and rendered. Without a kept drawing here,
    there is no record, and it says to expect minutes."""
    from runner.steps import build
    numbers = section_numbers(state, section)
    says = SECTION_SAYS.format(number=build.numbered(section), slides=slides_words(numbers)
                               if numbers else 'its slides')
    drawn = _last_try(run, f'build-sections:{section}', kept=True)
    if drawn is None:
        return {'seconds': None, 'dollars': None, 'recorded': False,
                'says': says + NO_RECORD + usually(SLIDE_NOTE)}
    tried = [drawn, *filter(None, (_last_try(run, 'build-whole'), _last_try(run, 'build-render')))]
    seconds = round(sum(float(attempt.get('seconds') or 0) for attempt in tried), 1)
    dollars = drawn.get('dollars')
    return {'seconds': seconds, 'dollars': dollars, 'recorded': True,
            'says': says + LAST_TOOK.format(cost=stops.cost(seconds, dollars))
            + usually(SLIDE_NOTE)}


def deck_price(last: dict) -> str:
    """What redrawing every section costs, from what the last whole build took
    (`Engine._last_build`)."""
    if not last or not last.get('sections'):
        return DECK_SAYS + NO_RECORD + usually(DECK_NOTE)
    return DECK_SAYS + DECK_TOOK.format(cost=stops.cost(last.get('seconds'), last.get(
        'dollars'))) + usually(DECK_NOTE)


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
