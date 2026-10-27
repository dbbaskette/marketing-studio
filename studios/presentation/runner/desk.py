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

import json
import re
import secrets
import shutil
from pathlib import Path

# isort: off
import runner  # noqa: F401  puts the core on the import path
import home
from studio_core import review_policy, step_times, stops
from studio_core.drafting.parts import Codec
from studio_core.drafting.store import Store
from studio_core.drafting.versions import Versions
from workspace import WorkspaceError

from runner import decks, stages
# isort: on


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
NOT_YET = ('The deck is still being drawn. Note a slide once the deck is on the desk, or '
           'use the note under its preview.')
STOPPED_ASIDE = 'Not redrawn: you stopped the redraw.'
AGAIN_ASIDE = ('Not redrawn: it came while the deck was being put together, too often in a '
               'row. Send it again.')
NO_DECK_NOTE = 'Say how the whole deck should change.'
PUTTING = 'Putting the deck together, rendering and checking it'
HALTED = 'The redraw stopped. Stop it to keep what was redrawn, or carry on.'
STILL = 'Your last change is still being put together. Deliver when it is done.'
BLOCKERS_CHANGED = ('The brand check changed since this page read it. Look again before you '
                    'deliver.')
DELIVERED_AGAIN = ('Delivered as revision {revision}. A change here makes revision {next}, '
                   'delivered when you press Deliver.')
DELIVERED_FROM = 'Delivered from the desk.'
OUTLINE_CHANGED = 'The outline changed since this page read it. Reload it, then try again.'
OUTLINE_BUSY = 'The deck is being redrawn now. Save the outline when that ends.'
SECTION_SIZE = 4   # content slides one section holds at most, as the slides tool splits them
NOTHING_TO_STOP = 'Nothing is being redrawn now, so there is nothing to stop.'
NOT_ENDED = ('It was stopped, but something it started has not ended yet. Try Stop again in '
             'a moment.')


# --- the stops ----------------------------------------------------------------------------

def passes(run: dict, gate: str, root=None) -> bool:
    """Whether a desk deck continues past `gate` with the desk's receipt: every stop before
    the look, and the look itself when the start chose the brand's default, or when the
    brand offers no looks to pick from (`root` is the deck, to say)."""
    if gate in PASSED:
        return True
    if gate == 'gate:look' and root is not None:
        from runner.steps import look as looks
        if looks.shown_looks(root) is None:
            return True
    # Change the look asks for a pick, whatever the start chose.
    return gate == 'gate:look' and (run.get('form') or {}).get('look') == 'default' \
        and not (run.get('desk') or {}).get('pick')


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


def fresh(state: dict) -> set[str]:
    """The sections kept since the deck was last put together: drawn in this chain."""
    rounds = len(state.get('rounds') or ())
    return {ident for ident, entry in (state.get('sections') or {}).items()
            if rounds and entry.get('round', 0) >= rounds}


def working(root, run: dict, state: dict | None = None) -> dict | None:
    """What desk work is under way, for the line above the desk: {'what', 'done', 'total'},
    or None while the deck rests, before it reaches the desk and once it stopped."""
    from runner.steps import build
    if not arrived(run) or resting(run) or decks.delivered(root):
        return None
    nxt = stages.survey(run).next
    if nxt is None:
        return None
    if nxt.kind == 'gate' and ((run.get('gates') or {}).get(nxt.name) or {}).get(
            'state') == 'waiting':
        return None   # a pause for the person, such as the look: not desk work
    state = state if state is not None else build.read_state(root)
    if not state.get('start'):
        return None   # no drawing here: nothing is drawn until Draw it here
    asked = list(((state.get('asked') or {}).get('sections')) or ())
    if run.get('halted'):
        # A redraw that stopped or failed can still be given up with Stop.
        if (run['halted'].get('state') in ('stopped', 'failed')) and (asked or opened(run)):
            return {'what': HALTED, 'done': len(fresh(state) & set(asked)), 'total': len(asked),
                    'halted': True}
        return None
    if not asked:
        building = nxt.stage == 'build' and nxt.name not in ('build-start', 'build-sections')
        return {'what': PUTTING if building else nxt.doing, 'done': 0, 'total': 0}
    done = len(fresh(state) & set(asked))
    if len(asked) == 1:
        numbers = section_numbers(state, asked[0])
        what = f'Redrawing section {build.numbered(asked[0])}' + (
            f' ({slides_words(numbers)})' if numbers else '')
    else:
        what = f'Redrawing: {done} of {len(asked)} sections'
    return {'what': what, 'done': done, 'total': len(asked)}


def section_of(state: dict, number) -> str | None:
    """The section that draws slide `number` of the last round: None for a lead slide,
    which no composer draws. A number the deck's last drawing does not have is refused."""
    rounds = state.get('rounds') or []
    if not rounds:
        raise WorkspaceError(NO_DRAWING if state.get('start') is None else NOT_YET)
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


def deliverable(root, run: dict) -> bool:
    """Whether Deliver is offered now: the deck rests on the desk, nothing is halted, and no
    note waits to be drawn."""
    return resting(run) and not run.get('halted') and not opened(run) \
        and decks.delivered(root) is None


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


def step_key(step: str) -> str:
    """The step-time estimate's key for one of a desk deck's steps, or the job under one."""
    return 'deck:' + step.partition(':')[0]


def estimate(run: dict) -> int | None:
    """About how many minutes are left before a desk deck reaches the desk, from how long
    each step left took here before; None while one of them has no record here."""
    names = [step.name for step in stages.steps(run)]
    before = stages.steps(run)[:names.index('gate:build')] if 'gate:build' in names else []
    left = [step for step in before if step.kind != 'gate'
            and not (((run.get('steps') or {}).get(step.name)) or {}).get('done')]
    minutes = 0.0
    for step in left:
        took = step_times.expected(DeckStore(), times(), step_key(step.name), None)
        if took is None:
            return None
        minutes += took
    return max(1, round(minutes))


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


def split(slides: list[dict]) -> list[list[str]]:
    """The sections the slides tool makes of an outline's slides, as it makes them: each
    run of content slides between lead slides, cut into as few even parts of at most
    SECTION_SIZE as it takes."""
    from runner.steps import build
    parts, run = [], []

    def cut():
        if not run:
            return
        count = -(-len(run) // SECTION_SIZE)
        size = -(-len(run) // count)
        parts.extend(run[at:at + size] for at in range(0, len(run), size))
        run.clear()

    for slide in slides:
        if not isinstance(slide, dict):
            continue
        if slide.get('kind') in build.LEADS:
            cut()
        else:
            run.append(slide.get('id'))
    cut()
    return parts


def outline_price(run: dict, state: dict, outline: dict, edited: list) -> dict:
    """What saving an edited outline redraws, said before it is saved: the sections whose
    slides change, in any field their composer reads, or that hold other slides now, priced
    as the sum of what each last took here."""
    from runner.steps import build
    before = {slide['id']: build._read_by_composer(slide) for slide in build.slides_of(outline)}
    now = {slide.get('id'): build._read_by_composer(slide) for slide in edited
           if isinstance(slide, dict)}
    was = [entry['slides'] for entry in (state.get('start') or {}).get('sections') or ()] \
        or split(build.slides_of(outline))
    changed = []
    for number, ids in enumerate(split(edited), 1):
        old = was[number - 1] if number <= len(was) else None
        if old != ids or any(before.get(ident) != now.get(ident) for ident in ids):
            changed.append(f'section-{number}')
    count = len(changed)
    if not count:
        says = ('No section changes: the deck is put together again from what is drawn, and '
                'rendered and checked.')
        return {'sections': [], 'says': says}
    says = (f'{count} sections change and are redrawn; the rest stay as drawn.' if count > 1
            else '1 section changes and is redrawn; the rest stay as drawn.')
    priced = [section_price(run, state, section) for section in changed
              if section in {entry['id'] for entry in (state.get('start') or {}).get(
                  'sections') or ()}]
    if len(priced) == count and all(one['recorded'] for one in priced):
        seconds = sum(one['seconds'] for one in priced)
        dollars = [one['dollars'] for one in priced]
        total = None if None in dollars else round(sum(dollars), 4)
        says += (' Last time those took ' if count > 1 else ' Last time that took ') \
            + stops.cost(seconds, total) + '.'
    else:
        says += NO_RECORD
    return {'sections': changed, 'says': says}


def deck_price(last: dict) -> str:
    """What redrawing every section costs, from what the last whole build took
    (`Engine._last_build`)."""
    if not last or not last.get('sections'):
        return DECK_SAYS + NO_RECORD + usually(DECK_NOTE)
    return DECK_SAYS + DECK_TOOK.format(cost=stops.cost(last.get('seconds'), last.get(
        'dollars'))) + usually(DECK_NOTE)


# --- the desk's cards ---------------------------------------------------------------------

WORDS = ('title', 'subtitle', 'detail', 'points', 'caveat', 'source')
UNFIT = 'These words do not fit the slide as it is drawn.'
ONE_CHANGE = 'A change is already being made to this deck. Wait or stop it.'
RESTORE_BUSY = 'The deck is being redrawn now. Bring the version back when that ends.'
NO_POINTS = 'A cover, section or closing slide has no points to change.'
REDRAW_WORDS = 'Fit the new words of slide {number}.'
WORDS_BUSY = 'The deck is being redrawn now. Redraw with these words when that ends.'
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


# --- History -------------------------------------------------------------------------------

VERSION_SOURCES = ('save', 'selection', 'note', 'redraw', 'restore', 'outline', 'finishing',
                   'open')
PART = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_-]{4,40}$')   # the outline's slide ID rule
STAMP = re.compile(r'^[0-9A-Za-z]{8,40}$')
DRAWINGS = Path('work') / 'desk' / 'versions'   # each slide's drawings: this computer's only
KEPT_WORDS = (*WORDS, 'notes')


class DeckFolder(DeckStore):
    """The deck's own desk folder, `desk/` beside run.json, which the team shares: the
    versions of each slide's words are kept there. The deck's path is its ident."""

    def folder(self, ident):
        return Path(ident) / 'desk'


SLIDES = Codec(fixed=(), single=(), part=PART, thing='deck', noun='slide')


def versions() -> Versions:
    return Versions(DeckFolder(), SLIDES, VERSION_SOURCES)


def words_of(slide: dict) -> dict:
    return {key: slide.get(key) for key in KEPT_WORDS}


def with_slide_words(outline: dict, ident: str, kept: dict) -> dict:
    """A new outline with one slide's words as `kept` has them; the rest of it as it is."""
    made = json.loads(json.dumps(outline))
    for slide in made.get('slides') or ():
        if isinstance(slide, dict) and slide.get('id') == ident:
            for key in KEPT_WORDS:
                if kept.get(key) in (None, '', []):
                    slide.pop(key, None)
                else:
                    slide[key] = kept[key]
    return made


def changed_fields(now: dict, kept: dict) -> list:
    """The fields of a slide whose words differ: each field, and each point's label and
    text where the points are as many."""
    from runner.steps import words
    found = [field for field in words.FIELDS
             if words.text_of(now, field) != words.text_of(kept, field)]
    old, new = now.get('points') or [], kept.get('points') or []
    if len(old) != len(new):
        from workspace import WorkspaceError as Refused
        raise Refused('The slide has another number of points now.')
    for at, (one, other) in enumerate(zip(old, new)):
        for key in ('label', 'text'):
            if (one.get(key) or '') != (other.get(key) or ''):
                found.append(('points', at, key))
    return found


def _stamp(entry: dict) -> str:
    return re.sub(r'[^0-9A-Za-z]', '', str(entry.get('at') or ''))


def keep_slide(root, slide_id: str, source: str, session=None) -> None:
    """Keep a slide's words as they are, before they change, in the deck's shared desk
    folder (piece 3's version store); and, where this computer has it, the slide's drawing and
    picture under work/, which is never shared. Saves of one editing session keep one."""
    from runner.steps import build, words
    root = Path(root)
    slide = next((one for one in build.slides_of(_outline(root)) if one.get('id') == slide_id),
                 None)
    if slide is None or not PART.match(slide_id):
        return
    store = versions()
    before = store.kept(str(root), slide_id)
    store.keep(str(root), slide_id, json.dumps(words_of(slide), sort_keys=True,
                                               ensure_ascii=False), source, session)
    after = store.kept(str(root), slide_id)
    if not after or (before and after[0] == before[0]):
        return   # one editing session keeps one version
    state = build.read_state(root)
    if not state.get('rounds'):
        return
    section = next((entry['id'] for entry in (state.get('start') or {}).get('sections') or ()
                    if slide_id in entry['slides']), None)
    file = (root / state['sections'][section]['file']) if section in (state.get('sections') or {}) \
        else words.lead_file(root, state, slide_id)
    drawn = next((one for one in (home.read_json(file, {}) if file else {}).get('slides') or ()
                  if isinstance(one, dict) and one.get('id') == slide_id), None)
    if drawn is None:
        return
    folder = root / DRAWINGS / slide_id
    folder.mkdir(parents=True, exist_ok=True)
    stamp = _stamp(after[0])
    home.write_json(folder / f'{stamp}.json', drawn)
    number = next((one['number'] for one in last_round(state)['slides']
                   if one['id'] == slide_id), None)
    picture = build.shots(root) / f'{number}.png'
    if number and picture.is_file():
        shutil.copyfile(picture, folder / f'{stamp}.png')


def version_drawing(root, slide_id: str, entry: dict) -> dict | None:
    if not PART.match(slide_id):
        return None
    found = home.read_json(Path(root) / DRAWINGS / slide_id / f"{entry['stamp']}.json", None)
    return found if isinstance(found, dict) else None


def version_picture(root, ref) -> Path | None:
    """The picture a version kept, by its ref '<slide>/<stamp>', and nothing else."""
    if not isinstance(ref, str) or ref.count('/') != 1:
        return None
    slide_id, stamp = ref.split('/')
    if not PART.match(slide_id) or not STAMP.match(stamp):
        return None
    return Path(root) / DRAWINGS / slide_id / f'{stamp}.png'


def versions_of(root, slide_id) -> list[dict]:
    """A slide's kept versions, newest first: {'at', 'source', 'words', 'stamp', 'picture'}."""
    if not isinstance(slide_id, str) or not PART.match(slide_id):
        raise WorkspaceError('Choose a slide of this deck.')
    found = []
    for entry in versions().kept(str(root), slide_id):
        try:
            kept = json.loads(entry['text'])
        except ValueError:
            continue
        stamp = _stamp(entry)
        pictured = (Path(root) / DRAWINGS / slide_id / f'{stamp}.png').is_file()
        found.append({'at': entry.get('at'), 'source': entry.get('source'), 'words': kept,
                      'stamp': stamp, 'picture': {'kind': 'version', 'ref': f'{slide_id}/{stamp}'}
                      if pictured else None})
    return found


def with_drawing(section: dict, drawn: dict) -> dict:
    """A drawn section (or a lead's file) with one slide's drawing put back."""
    made = json.loads(json.dumps(section))
    made['slides'] = [drawn if isinstance(one, dict) and one.get('id') == drawn.get('id')
                      else one for one in made.get('slides') or ()]
    return made


def check_seen(run: dict, seen, part: str) -> None:
    """Refuse a form older than the slide it changes: piece 3's per-part check, over the
    desk's own revision and the revision each slide last changed at."""
    from studio_core.drafting import record
    held = run.get('desk') or {}
    try:
        record.checked({'revision': int(held.get('revision') or 1),
                        'changed': held.get('changed') or {}}, seen, [part], 'deck')
    except ValueError as refusal:
        raise WorkspaceError(str(refusal)) from None


def advance(run: dict, part: str) -> int:
    """One revision on, with `part` changed at it. Returns the revision."""
    held = run.setdefault('desk', {})
    held['revision'] = int(held.get('revision') or 1) + 1
    held.setdefault('changed', {})[part] = held['revision']
    return held['revision']


def revision(run: dict) -> int:
    return int((run.get('desk') or {}).get('revision') or 1)


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
    unfit = (run.get('desk') or {}).get('unfit') or {}
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
                'unfit': {**unfit[ident], 'says': UNFIT} if ident in unfit else None,
                'price': priced})
        sections.append({'id': section, 'lead': lead, 'number': None if lead else counted,
                         'slides': slides})
    return {'sections': sections, 'expected': last.get('deck') if drawn else None,
            'drawn_here': drawn}


def _note_shown(item: dict | None) -> dict | None:
    if not item:
        return None
    aside = {'stopped': SET_ASIDE if not item.get('slide') else STOPPED_ASIDE,
             'again': AGAIN_ASIDE}.get(item.get('aside'), SET_ASIDE)
    says = {'waiting': 'Your note is kept: it is drawn next.', 'drawing': REDRAWING,
            'set aside': aside}.get(item.get('status'))
    return {'note': item.get('note'), 'status': item.get('status'), 'whole': not item.get('slide'),
            **({'says': says} if says else {})}
