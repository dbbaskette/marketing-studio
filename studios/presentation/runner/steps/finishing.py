"""Finishing on the desk: the brand check, the deck's review, speaker notes and rehearse.

What a caller needs to know
---------------------------
    finishing.brand(root, run)               # the last render's brand check, per slide
    finishing.check_again(root, run, skill)  # the brand's audit of the deck as it is now
    finishing.proposals(note, noted, notes)  # the deck's waiting proposals (piece 3's)
    finishing.rehearse(outline, minutes)     # how long the speaker notes take to say

- Every tool proposes, and nothing changes until Apply. The proposals are kept with piece 3's
  proposals module, through the shared review findings (`studio_core.drafting.findings`), on
  this computer only (`desk.DeckFolder.local`, under work/). This studio supplies what a
  proposal applies as:
  - a brand check line on a slide: a note on its slide, "The brand's check: {says}";
  - a review finding: a note on its slide, "{note} {fix}";
  - speaker notes: the slide's notes, saved as typed notes are, with no redraw.
  Skip keeps a proposal as read, and changes nothing.
- The brand check and rehearse run in process, with no assistant. The review is the deck's
  own reviewer job (build.review_work); speaker notes are a job of their own, whose result
  is checked here (`check_speaker_notes`, the `speaker-notes` kind).
- Nothing here takes the engine's lock or starts a job: the engine's desk actions do that.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

# isort: off
import runner  # noqa: F401  puts the core on the import path
import home
from studio_core import stops
from studio_core.drafting import findings, record
from workspace import WorkspaceError

from runner import decks, desk, worker_tools
from runner.steps import build
# isort: on

TOOLS = ('brand', 'review', 'notes', 'rehearse')
KINDS = {'finish-brand': 'brand', 'finish-review': 'review', 'finish-notes': 'notes'}
WPM = 150                  # words of speaker notes said in a minute
NOTES_MOST = 4000          # characters in one slide's speaker notes, as its box takes them
BRAND_SAYS = "The brand's check: {says}"
NO_TOOL = 'Choose Brand check, Review the deck, Speaker notes or Rehearse.'
NOT_CHECKED = 'The brand skill was not there to check this deck.'
REVIEW_SAYS = ('Reviews every slide as it is drawn now. What it finds comes back here, slide by '
               'slide, and nothing changes until you apply it.')
NOTES_SAYS = ('Proposes speaker notes for every slide from its words, the outline and your '
              'sources. Nothing changes until you apply them, and applying redraws nothing.')
REVIEWED = ('The deck was reviewed as it is drawn now. What the review found is under Review '
            'the deck.')
NO_DECK = 'The deck has not been rendered yet. Review it once it is on the desk.'
OWN_DECK = ('Finishing is for decks drawn here. Your own deck at Selected changes keeps its '
            'slides: its brand check is on each card.')
NOTES_SHAPE = 'Hand back a JSON list of {"slide", "notes"}, one for each slide you give notes.'


# --- the brand check ------------------------------------------------------------------------

def brand(root, run: dict) -> list[dict]:
    """What the last render's brand check says, line by line: {'id', 'slide', 'number',
    'kind': 'blocker'|'warning', 'says'}, the blockers first, then the warnings, each in
    slide order, and what it says of the whole deck last. No job, and nothing is written."""
    state = build.read_state(root)
    ids = {slide['number']: slide['id'] for slide in desk.last_round(state).get('slides') or ()}
    found = []
    for line in ((state.get('audit') or {}).get('messages') or ()):
        line = str(line)
        kind = 'blocker' if line.endswith(' (error)') else 'warning'
        said = line.rpartition(' (')[0] if line.endswith((' (error)', ' (warning)')) else line
        number = None
        if said.startswith('Slide ') and ': ' in said:
            head, _, rest = said.partition(': ')
            if head[len('Slide '):].isdigit():
                number, said = int(head[len('Slide '):]), rest
        ident = hashlib.sha256(json.dumps([number, kind, said]).encode()).hexdigest()[:12]
        found.append({'id': ident, 'slide': ids.get(number), 'number': number, 'kind': kind,
                      'says': said})
    return sorted(found, key=lambda one: (one['kind'] != 'blocker', one['number'] is None,
                                          one['number'] or 0))


def check_again(root, run: dict, skill) -> list[dict]:
    """Run the brand skill's audit on the deck as it is now (build.delivered_deck), in
    seconds, and keep it as the deck's brand check (`state['audit']`). Returns `brand`."""
    deck = build.delivered_deck(root, run)
    if skill is None:
        raise WorkspaceError(NOT_CHECKED)
    form = run.get('form') or {}
    try:
        audit = build.audited(skill.audit(deck, form.get('brand'), form.get('variant')))
    except WorkspaceError as refusal:
        # The last check the deck had stands: only that this one could not be run is said.
        raise WorkspaceError(f"The brand's check of this deck could not be run. {refusal}") \
            from None
    state = build.read_state(root)
    state.update(audit=audit, auditNote=None)
    build.write_state(root, state)
    return brand(root, run)


def brand_items(listed: list[dict]) -> list[dict]:
    """The brand check as proposals: each line on a slide applies as a note on that slide in
    the check's own words; a line about the whole deck is shown, and only skipped."""
    on_slides = findings.items([one for one in listed if one['slide']], 'slide',
                               words=lambda one: BRAND_SAYS.format(says=one['says']),
                               fields=('kind', 'says'))
    whole = [{'part': None, 'number': None, 'kind': one['kind'], 'says': one['says'],
              'comment': one['says']} for one in listed if not one['slide']]
    return on_slides + whole


def audit_seen(state: dict) -> str:
    """The brand check a set of its proposals was made from, to tell when it has changed."""
    return hashlib.sha256(json.dumps(state.get('audit'), sort_keys=True).encode()).hexdigest()


# --- the review -------------------------------------------------------------------------------

def review_items(state: dict) -> list[dict]:
    """The last round's review findings, gravest first, each a proposal on its slide whose
    Apply is a note made of the finding's note and fix."""
    found = (desk.last_round(state).get('review') or {}).get('findings')
    drawn = drawings(state)
    return [{**item, 'drawn': drawn.get(item['part'])}
            for item in findings.items(build.ordered(found or ()), 'slide')]


def drawings(state: dict) -> dict:
    """Which drawing of its section each slide has now, {slide ID: the section's file}: a
    section drawn again has another file, so a finding made before it no longer fits."""
    files = {ident: entry.get('file') for ident, entry in (state.get('sections') or {}).items()}
    return {slide: files.get(entry['id']) for entry in (state.get('start') or {}).get(
        'sections') or () for slide in entry.get('slides') or ()}


def _priced(run: dict, name: str, says: str) -> str:
    """`says`, then what the last try of job `name` took here: a try the runner made with no
    assistant, such as a review put off for the person, is not one."""
    tried = [attempt for attempt in ((run.get('steps') or {}).get(name) or {}).get('tries') or ()
             if not attempt.get('runner') and attempt.get('outcome') == 'kept']
    if not tried:
        return says + desk.NO_RECORD
    return says + desk.LAST_TOOK.format(cost=stops.cost(tried[-1].get('seconds'),
                                                       tried[-1].get('dollars')))


def review_price(run: dict) -> str:
    """What Review the deck costs, said before it is asked: the last review here."""
    return _priced(run, 'build-review', REVIEW_SAYS)


def notes_price(run: dict) -> str:
    """What proposing speaker notes costs: the last such job here."""
    return _priced(run, 'desk-notes', NOTES_SAYS)


# --- speaker notes ----------------------------------------------------------------------------

def notes_slides(outline: dict) -> list[dict]:
    """Each slide as the speaker-notes job reads it: its ID, number, kind, words and notes."""
    return [{'slide': slide.get('id'), 'number': number, 'kind': slide.get('kind'),
             **{key: slide.get(key) for key in desk.WORDS if slide.get(key)},
             'notes': slide.get('notes') or ''}
            for number, slide in enumerate(build.slides_of(outline), 1)]


def check_speaker_notes(text: str, spec: dict):
    """A speaker-notes job's result: a JSON list of {"slide", "notes"}, each naming one of
    the deck's slides (`spec['slides']`) once, with notes of at most NOTES_MOST characters.
    Returns problems, the checks that ran, warnings and the text to keep."""
    problems = []
    slides = list(spec.get('slides') or ())
    try:
        found = json.loads(text or '')
    except ValueError:
        found = None
    if not isinstance(found, list) or not all(isinstance(one, dict) for one in found):
        problems.append(NOTES_SHAPE)
        found = []
    seen = set()
    for one in found:
        ident, notes = one.get('slide'), one.get('notes')
        if not isinstance(ident, str) or ident not in slides:
            problems.append(f'{ident} is not a slide of this deck.')
            continue
        if ident in seen:
            problems.append(f'{ident} is given notes twice. Give each slide its notes once.')
        seen.add(ident)
        if not isinstance(notes, str) or not notes.strip():
            problems.append(f'Give {ident} its notes as text.')
        elif len(notes.strip()) > NOTES_MOST:
            problems.append(f'Keep the notes of {ident} to {NOTES_MOST:,} characters.')
    if not found and not problems:
        problems.append('Give at least one slide its notes.')
    kept = json.dumps([{'slide': one.get('slide'), 'notes': str(one.get('notes') or '').strip()}
                       for one in found], ensure_ascii=False)
    return problems, [worker_tools.result('speaker-notes.slides', problems)], [], kept


worker_tools.register('speaker-notes', check_speaker_notes)


def notes_items(outline: dict, handed: str) -> list[dict]:
    """The speaker notes a job proposed, as proposals: each slide's notes now (`before`) and
    the notes proposed (`after`), for the slides whose notes would change."""
    now = {one['slide']: one for one in notes_slides(outline)}
    made = []
    for one in json.loads(handed):
        slide = now.get(one.get('slide'))
        after = str(one.get('notes') or '').strip()
        if slide is None or not after or after == slide['notes'].strip():
            continue
        made.append({'part': slide['slide'], 'number': slide['number'], 'before': slide['notes'],
                     'after': after})
    return made


# --- the proposals ----------------------------------------------------------------------------

class Desk:
    """The deck's desk record as piece 3's proposals check a form against it: the desk's
    revision, the revision each slide last changed at, and each slide's speaker notes now."""

    codec = desk.SLIDES

    def read(self, ident):
        root = Path(ident)
        run = home.read_json(root / decks.RUN, {}) or {}
        held = run.get('desk') or {}
        return {'revision': int(held.get('revision') or 1), 'changed': held.get('changed') or {},
                'slides': {slide.get('id'): slide.get('notes') or ''
                           for slide in build.slides_of(desk._outline(root))},
                'drawn': drawings(build.read_state(root))}

    def checked(self, draft, seen, parts=None):
        record.checked(draft, seen, parts, 'deck')


def present(draft: dict, item: dict) -> bool:
    """Whether a proposal still fits the deck: its slide is still in it; for a review's
    finding, the slide has not been drawn again since the review; and for speaker notes, the
    slide's notes are still as they were proposed against."""
    slides = draft.get('slides') or {}
    if item.get('part') not in slides:
        return False
    if 'drawn' in item and (draft.get('drawn') or {}).get(item['part']) != item['drawn']:
        return False
    return 'before' not in item or slides[item['part']] == item['before']


class Proposals(findings.Noted):
    """The deck's waiting proposals. A brand check line or a review finding is applied as a
    note on its slide (`note`); speaker notes are written through the notes edit (`notes`).
    `noted(ident, applied)` is told once every chosen one is done."""

    def __init__(self, note=None, noted=None, notes=None):
        super().__init__(desk.DeckFolder(), Desk(), KINDS, note, owner='deck', present=present,
                         noted=noted)
        self.notes = notes

    def act(self, ident, job, found, draft, picks, every, named, left=()):
        if found.get('kind') != 'finish-notes':
            return super().act(ident, job, found, draft, picks, every, named, left)
        single = len(named) == 1 and not every
        applied, left = [], list(left)
        for item, words in picks:
            words = str(words).strip()
            try:
                if not words:
                    raise ValueError('Write the speaker notes to use, then apply them.')
                if len(words) > NOTES_MOST:
                    raise ValueError(f'Keep speaker notes to {NOTES_MOST:,} characters.')
                if not present(draft, item):
                    raise ValueError('The notes of this slide changed since these were '
                                     'proposed, so they were not applied. Skip them.')
                self.notes(ident, item, words)
            except ValueError:
                if single:
                    raise
                left.append(item['id'])
                continue
            applied.append(item)
        if not applied:
            if every:
                return {'applied': 0, 'left': left}
            raise ValueError(findings.NONE_NOTED)
        if self.noted is not None:
            self.noted(ident, applied)
        for item in applied:
            item['state'] = 'applied'
        self.store.write_json(self.path(ident, job), found)
        return {'applied': len(applied), 'left': left}


def proposals(note=None, noted=None, notes=None) -> Proposals:
    return Proposals(note, noted, notes)


def summary(root) -> dict:
    """The newest set of each tool, as the panel shows it: {tool: set}, each proposal with
    whether it still fits (`present`)."""
    kept = proposals()
    return kept.summary(str(root), kept.desk.read(str(root)))


# --- rehearse -----------------------------------------------------------------------------------

def _minutes(value: float) -> str:
    """'about 3 minutes', or 'under a minute' for a time that rounds to no minutes."""
    whole = round(value)
    if whole < 1:
        return 'under a minute'
    return f"about {whole} minute{'' if whole == 1 else 's'}"


def rehearse(outline: dict, minutes=None) -> dict:
    """How long the deck's speaker notes take to say, at WPM words a minute, slide by slide
    against the minutes the deck is given: {'slides': [{'number', 'minutes'}], 'total',
    'long': [numbers], 'says'}. A slide is long when it takes more than twice the deck's
    minutes divided by its content slides. No job: it is counted here."""
    slides = build.slides_of(outline)
    counted = [{'number': number, 'minutes': round(len(build.WORD.findall(
        str(slide.get('notes') or ''))) / WPM, 2)} for number, slide in enumerate(slides, 1)]
    total = round(sum(one['minutes'] for one in counted), 2)
    content = [one for one, slide in zip(counted, slides) if slide.get('kind') not in build.LEADS]
    given = minutes if type(minutes) in (int, float) and minutes > 0 else None
    share = 2 * given / len(content) if given and content else None
    long = [one['number'] for one in content if share is not None and one['minutes'] > share]
    whole = round(total)
    if not total:
        says = 'The deck has no speaker notes yet.'
    elif given is None:
        says = f"The deck's notes take {_minutes(total)}."
    else:
        longest = max(counted, key=lambda one: one['minutes'])
        part = f'about {whole}' if whole >= 1 else 'under a minute'
        says = (f"Slide {longest['number']}'s notes take {_minutes(longest['minutes'])}; "
                f"the deck's notes take {part} of your {given:g} minute"
                f"{'' if given == 1 else 's'}.")
    return {'slides': counted, 'total': total, 'long': long, 'says': says}
