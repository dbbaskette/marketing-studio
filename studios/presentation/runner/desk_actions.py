"""The engine's desk: what a person does to a deck on the desk, and how its stops are met.

What a caller needs to know
---------------------------
    engine.desk_look(path, look_id, note=None)   # the start chose to pick: the person's pick

- `DeskActions` is a part of the engine (runner/engine.py mixes it in), as `jobs.Jobs` is.
  Every action begins with `_held` and refuses a deck that is not on the desk
  (`desk.NOT_ON_DESK`). Each records what was asked and, where something is to be drawn
  again, reopens gate:build (`desk.reopen`); the engine's own steps then do the work.
  `open_on_desk` is the one way onto the desk for a saved deck: a deck delivered the gated
  way opens there, still delivered.
- `_desk_gate` meets a stop the desk deck continues past (`desk.passes`) as `_policy_gate`
  meets one a review level continues past: with what the stop shows, a desk receipt and a
  commit, and never as a person's approval.
"""
from __future__ import annotations

import json
import secrets
from pathlib import Path

# isort: off
import runner  # noqa: F401  puts the core on the import path
import home
from workspace import WorkspaceError, write_atomic

from runner import briefs, decks, desk, documents, gitstate, library_keep, marks, stages
from studio_core import deck_content, research_view
from studio_core.document_library import LibraryError
from studio_core.document_library import context as library_context
from studio_core.drafting import prompts
from runner.jobs import gate_state, sha256_of
from runner.steps import build, finishing, intake, words
from runner.steps import deliver as delivering
from runner.steps import look as looks
from runner.steps import outline as outlines
# isort: on

NO_PICK = 'The look is not waiting to be picked now.'
NO_RESEARCH = 'This deck has no research. Add a source, and its words jobs read it.'
RESEARCH_BUSY = 'The deck is being redrawn now. Change the research when that ends.'
LIBRARY_BUSY = ('The deck is being made now. Add from the library, or take a newer revision, '
                'when that ends: a job that is running keeps the sources it started with.')
LEFT_OUT_ALREADY = 'Those findings are left out already.'
PASTED = 'Pasted text'
SOURCES_TOLD = ('The person\'s own sources are in your input "sources". Add only what they, '
                'the slide or the outline support.')
CHECK_BUSY = 'The deck is being redrawn now. Check it again when that ends.'
REVIEW_BUSY = 'The deck is being redrawn now. Review it when that ends.'
REVIEW_DELIVERED = ('This deck is delivered as it is. A change here makes the next revision: '
                    'review that one before you deliver it.')
OWN_REVIEW = ('Your own deck at Selected changes is not reviewed: only the slides you name '
              'change, and the brand check looks at the copy.')
NOT_DRAWN = 'This slide is not in the deck as it is drawn now, so it was not noted. Skip it.'
EDITS = Path('work') / 'desk' / 'edits'   # words saved while a chain ran, until they land
AGAIN = 3   # chains one rest on the desk may run for notes that came while it was put together
# Selected changes: the plan and the shared copy as they were before the change under way,
# and that change, put back if the copy cannot be made; and the mark that this computer was
# asked to draw the deck here. Both are this computer's only.
BEFORE = Path('work') / 'desk' / 'patch-before.json'
DRAW_HERE = Path('work') / 'desk' / 'draw-here'


class DeskActions:
    """The engine's part for decks on the desk."""

    # --- the stops a desk deck continues past ------------------------------------------------

    def _desk_gate(self, root, step: stages.Step) -> None:
        """Continue past a stop of a desk deck with the desk's receipt: what the stop shows
        is fingerprinted, and the gate is approved by the desk. At the look, the start chose
        the brand's default: it is chosen, in words that say so."""
        with self.files:
            record = self._load(root)
            if decks.in_conversation(record):
                return
            if not desk.passes(record, step.name, root):
                raise WorkspaceError('This step needs your review.')
            evidence = getattr(self, f"_show_{step.name.partition(':')[2].replace('-', '_')}")(
                root, record)
            note = None
            if step.name == 'gate:look':
                if looks.shown_looks(root) is not None:
                    made = looks.choose_default(root, self._skill(),
                                                words=looks.START_DEFAULT_WORDS, by='desk')
                    if made is None:
                        # The outline changed since the samples were drawn: they are drawn
                        # again, and the default chosen from those.
                        record['steps']['look-preview'] = {
                            **(record['steps'].get('look-preview') or {}), 'done': False}
                        self._store(root, record)
                        self._commit(root, 'draw the looks again: what the deck says changed')
                        return
                    if made.get('shown') == 'unrendered':
                        note = made.get('words')
                looks.approve(root, record, None, by='desk')
                record = self._load(root)
            else:
                record = self._approve(root, record, step.name, None, {}, {})
            at = home.now()
            gate = record['gates'].get(step.name) or {}
            record['gates'][step.name] = {**gate, 'state': 'approved', 'by': 'desk', 'at': at,
                                          'note': desk.CONTINUED}
            desk.receipt(record, step.name, evidence, at, note=note)
            self._store(root, record)
            from runner.engine import WORDS
            self._commit(root, f'continue the {WORDS[step.name]} on the desk')

    def _on_desk(self, root, record: dict) -> None:
        """gate:build waits on a desk deck: the deck is on the desk. Notes that came while
        the deck was put together, and any its chain did not draw, are drawn now, in one more
        chain, before it rests. Call it holding `files`, from `_gate`."""
        if decks.in_conversation(record):
            return
        first = desk.arrive(record)
        if desk.selected(record):
            # Nothing is drawn: a note on a slide was planned and made with the copy now.
            for item in desk.opened(record):
                item.update(status='done', done_at=home.now())
            record['desk'].pop('chain', None)
            self._store(root, record)
            self._commit(root, 'the deck is on the desk' if first
                         else 'the deck is back on the desk')
            return
        state = build.read_state(root)
        known = {entry['id'] for entry in (state.get('start') or {}).get('sections') or ()}
        left = [item for item in desk.opened(record) if item.get('section') in known]
        for item in desk.opened(record):
            if item.get('section') not in known:
                item['status'] = 'set aside'
        again = int((record.get('desk') or {}).get('again') or 0)
        if left and again >= AGAIN:
            # Drawn as often as one rest allows and still open: set aside, never looped on.
            for item in left:
                item.update(status='set aside', aside='again')
            left = []
        whole = not left and again < AGAIN and bool(state.get('rounds')) \
            and self._needs_whole(root)
        record['desk']['again'] = again + 1 if left or whole else 0
        if whole:
            record = desk.reopen(record)
            self._store(root, record)
            self._commit(root, 'put the words saved after the deck was put together into it')
            return
        chain = record['desk'].get('chain') if not left else None
        if chain:
            # What a note's chain took here, for the next price's "usually".
            from datetime import datetime
            try:
                took = (datetime.fromisoformat(home.now())
                        - datetime.fromisoformat(chain['at']))
                desk.took(chain['kind'], max(0.0, took.total_seconds()))
            except (KeyError, TypeError, ValueError):
                pass
            record['desk'].pop('chain', None)
        if left and state.get('rounds'):
            for item in left:
                item['status'] = 'drawing'
            desk.ask(state, sorted({item['section'] for item in left}, key=build.numbered))
            build.write_state(root, state)
            record = desk.reopen(record)
            self._store(root, record)
            self._commit(root, 'draw what was noted while the deck was put together')
            return
        self._store(root, record)
        self._commit(root, 'the deck is on the desk' if first else 'the deck is back on the desk')

    # --- what the desk shows -------------------------------------------------------------------

    def _desk_view(self, root, record: dict) -> dict:
        """What the page's desk shows of a desk deck: its cards, whether it has reached the
        desk, what desk work is under way, and what Deliver is bound to."""
        state = build.read_state(root)
        from runner.desk_ready import status as ready_status
        shown = desk.cards(root, record, lambda section: desk.section_price(
            record, state, section)['says'])
        return {**shown, **ready_status(root, record), 'migrated': bool(record.get('unfinished_migration')),
                'saved_status': record.get('migration_saved_status'),
                'content_pending': deck_content.enabled(record)
                    and 'gate:outline' in {step.name for step in stages.steps(record)}
                    and gate_state(record, 'gate:outline') != 'approved',
                'arrived': desk.arrived(record), 'seen': desk.revision(record),
                'progress': None if desk.arrived(record) else {
                    'minutes_left': desk.estimate(record), 'started_at': record.get('created')},
                'working': None if decks.in_conversation(record) else desk.working(root, record, state),
                'deliverable': desk.deliverable(root, record),
                'outline': self._desk_outline_view(root, record),
                **({} if shown['drawn_here'] else {
                    'no_drawing': desk.NO_DRAWING,
                    'draw_here_price': desk.draw_here_price(record) if desk.selected(record)
                    else desk.deck_price(self._last_build(record))}),
                'delivered': decks.delivered(root),
                'revision': desk.DELIVERED_AGAIN.format(
                    revision=len(record['revisions']), next=len(record['revisions']) + 1)
                if record.get('revisions') and decks.delivered(root) is None else None,
                'deck_price': desk.deck_price(self._last_build(record)),
                'blockers': desk.blockers(state), 'blockers_seen': desk.blockers_seen(state),
                'reviewed': desk.reviewed(state),
                # Your own deck: its words kept exactly, or its speaker notes kept as they are.
                'level': desk.level(record), 'words_locked': desk.words_locked(record),
                'notes_locked': desk.OWN_NOTES if desk.selected(record) else None,
                # Each source pinned from the Document Library says whether a newer revision
                # is there; the deck keeps reading its own copy either way.
                'sources': library_context.marked(documents.listed(root)),
                'library': library_keep.status(root) if decks.delivered(root) else None,
                **self._desk_research_view(root, record),
                **self._desk_finishing_view(root, record, state, shown)}

    def _desk_finishing_view(self, root, record: dict, state: dict, shown: dict) -> dict:
        """The Finishing panel: the newest proposals of each tool, each finding with what
        applying it redraws (its slide's price), the last render's brand check, what the
        review and the speaker notes cost, and rehearse, counted here."""
        prices = {card['id']: card['price'] for part in shown['sections']
                  for card in part['slides']}
        sets = finishing.summary(root)
        for kept in sets.values():
            for item in kept['items']:
                if kept['kind'] != 'finish-notes' and item.get('part') in prices:
                    item['price'] = prices[item['part']]
        return {'finishing': sets, 'brand_check': finishing.brand(root, record),
                'brand_current': (sets.get('brand') or {}).get('audit')
                == finishing.audit_seen(state),
                'finish_prices': {'review': finishing.review_price(record),
                                  'notes': finishing.notes_price(record)},
                'reviewing': bool(record.get('review_requested')) and not record.get('halted'),
                'rehearse': finishing.rehearse(desk._outline(root),
                                               (record.get('form') or {}).get('minutes'))}

    @staticmethod
    def _desk_research(record: dict) -> bool:
        return 'gate:research' in {step.name for step in stages.steps(record)}

    def _desk_research_view(self, root, record: dict) -> dict:
        """The Research panel: the findings and gaps of the research, what researching
        again costs, and what leaving findings out costs. Nothing where the deck has no
        research."""
        if not self._desk_research(record):
            return {'research': None, 'research_items': [], 'research_price': None,
                    'leave_out_price': None}
        questions = [{'id': ident, 'question': text}
                     for ident, text in self._questions(root).items()]
        return {'research': research_view.account(root / 'research', questions)
                if record.get('research_contract') else None,
                'research_items': self._findings_shown(root, record),
                'research_price': self._research_price(root, record)['words'],
                'leave_out_price': desk.leave_out_price(record)}

    def _desk_held(self, path):
        """The deck, held for a change on the desk: refused when this computer may not
        change it, and when it is not on the desk."""
        root = self._held(path)
        desk.refuse_off_desk(self._load(root))
        return root

    # --- notes --------------------------------------------------------------------------------

    def _desk_change(self, path):
        """Hold a desk deck for a change that draws something again: a deck this computer
        delivered is taken back first, as asking for changes to it is."""
        root = self._desk_held(path)
        space = self.space()
        if self._delivered_here(self._load(root)):
            self._take(root, space)
        self.hold(root)
        return root, space, gitstate.identity(space.repo)

    def _desk_ask(self, root, record: dict, state: dict, sections, note: str, space) -> tuple:
        """Draw `sections` again for their notes, now, where the deck rests on the desk or
        is delivered: the notes are in the ask, and gate:build is reopened. A deck whose
        chain is under way is not touched: its notes wait, and the chain draws them at its
        next safe point (`_desk_pick_up`). Call it holding `files`. Returns the run, what
        else the commit lists, and whether it was asked now."""
        delivered = decks.delivered(root) is not None
        if not (delivered or desk.resting(record)):
            return record, (), False
        for item in desk.waiting(record):
            if item.get('section') in sections:
                item['status'] = 'drawing'
        if delivered:
            record = delivering.again(root, record, self.slides(), note, space,
                                      sections=sections)
            state = build.read_state(root)
        desk.ask(state, sections)
        build.write_state(root, state)
        record = desk.reopen(record)
        for step in self._reopened(record, 'gate:build'):
            self._fresh(record, step)
        return record, (self._listed(space) if delivered else ()), True

    def desk_note(self, path, number, note, expected) -> dict:
        """A note on one slide: its section is redrawn with it, and every other slide of the
        section is kept exactly as it is drawn. Bound to the deck on screen (`expected`)."""
        note = self._note(note)
        if not note:
            raise WorkspaceError(desk.NO_NOTE)
        root, space, by = self._desk_change(path)
        with self.files:
            record, state = self._load(root), build.read_state(root)
            if not desk.arrived(record):
                raise WorkspaceError(desk.NOT_YET)
            if not expected or desk.on_screen(root, record, state) != expected:
                raise WorkspaceError(desk.CHANGED)
            if desk.selected(record):
                record, also = self._desk_patch_note(root, record, number, note, by, space)
                what = f'ask to change slide {number} of your deck'
            else:
                item = desk.add_note(record, state, number, note, home.now(), by)
                desk.keep_slide(root, item['slide'], 'note')
                record, also, now = self._desk_ask(root, record, state, [item['section']],
                                                   note, space)
                if now and desk.arrived(record):
                    record['desk']['chain'] = {'kind': desk.SLIDE_NOTE, 'at': home.now()}
                what = f'ask to redraw slide {number}'
            self._store(root, record)
            self._commit(root, what, also)
        self._desk_shared()
        self.wake(root)
        return self.view(root)

    def _desk_patch_note(self, root, record: dict, number, note: str, by, space) -> tuple:
        """A note on a slide of a Selected changes deck: the slide joins the slides the plan
        may change (`desk_patch_slides`), and the plan is made again with the note, then the
        copy. Call it holding `files`. Returns the run, and what else the commit lists."""
        have = {slide.get('number') for slide in (outlines.inventory_of(root) or {}).get(
            'slides') or () if isinstance(slide, dict)}
        if type(number) is not int or number not in have:
            raise WorkspaceError(f'The deck has no slide {number}.')
        delivered = self._desk_patch_ready(root, record)
        said = f'Slide {number}: {note}'
        item = desk.note_of(f'slide-{number}', number, None, note, home.now(), by,
                            status='drawing')
        record.setdefault('desk_notes', []).append(item)
        self._desk_patch_keep(root, {'kind': 'note', 'number': number, 'id': item['id']})
        named = record.setdefault('desk_patch_slides', [])
        if number not in named:
            named.append(number)
        also = ()
        if delivered:
            record = delivering.again(root, record, self.slides(), said, space, sections=[])
            also = self._listed(space)
        else:
            gate = record['gates'].get('gate:build') or {}
            record['gates']['gate:build'] = {**gate, 'state': 'changes', 'by': 'desk',
                                             'note': said, 'slides': None, 'at': home.now()}
            record = stages.reopen(record, 'gate:build')
        for step in self._reopened(record, 'gate:build'):
            self._fresh(record, step)
        return record, also

    def desk_deck_note(self, path, note, expected) -> dict:
        """A note for the whole deck: every section is redrawn with it, three at a time, and
        the deck is put together once they are. Bound to the deck on screen."""
        note = self._note(note)
        if not note:
            raise WorkspaceError(desk.NO_DECK_NOTE)
        root, space, by = self._desk_change(path)
        with self.files:
            record, state = self._load(root), build.read_state(root)
            if desk.selected(record):
                raise WorkspaceError(desk.WHOLE_SELECTED)
            if not desk.arrived(record):
                raise WorkspaceError(desk.NOT_YET)
            if not expected or desk.on_screen(root, record, state) != expected:
                raise WorkspaceError(desk.CHANGED)
            sections = [entry['id'] for entry in (state.get('start') or {}).get('sections') or ()]
            busy = [section for section in sections if desk.busy(record, section)]
            if busy:
                numbers = desk.section_numbers(state, busy[0])
                raise WorkspaceError(desk.BUSY.format(number=numbers[0] if numbers else 1))
            at = home.now()
            for section in sections:
                record.setdefault('desk_notes', []).append(
                    desk.note_of(None, None, section, note, at, by))
            record, also, now = self._desk_ask(root, record, state, sections, note, space)
            if now:
                record['desk']['chain'] = {'kind': desk.DECK_NOTE, 'at': home.now()}
            self._store(root, record)
            self._commit(root, 'ask to redraw every section', also)
        self._desk_shared()
        self.wake(root)
        return self.view(root)

    def desk_stop(self, path) -> dict:
        """Stop the redraw under way, as Stop does, and wait for it to end. What was redrawn
        is kept; the sections not redrawn yet come off the ask, their notes set aside, and
        the deck is put together from what it has."""
        from runner.engine import Engine
        root = self._desk_held(path)
        record = self._load(root)
        # A Stop that did not end in time left the deck stopped mid-redraw: Stop again waits
        # for it and tidies up.
        # A redraw that failed is given up the same way.
        # So is a words or speaker-notes job, or Review the deck, that stopped or failed.
        again = (record.get('halted') or {}).get('state') in ('stopped', 'failed') and (
            desk.opened(record) or (build.read_state(root).get('asked') or {}).get('sections')
            or desk.selected(record) or record.get('desk_jobs')
            or record.get('review_requested'))
        if not again and desk.working(root, record) is None:
            raise WorkspaceError(desk.NOTHING_TO_STOP)
        if not again:
            self.act(root, 'stop')
        run = self._run(root)
        if not Engine._ended(run):
            raise WorkspaceError(desk.NOT_ENDED)
        with self.files:
            record, state = self._load(root), build.read_state(root)
            asked = list(((state.get('asked') or {}).get('sections')) or ())
            drawn = desk.fresh(state)
            undrawn = [section for section in asked if section not in drawn]
            if state.get('asked'):
                kept = [section for section in asked if section in drawn]
                state['asked'] = {**state['asked'], 'sections': kept} if kept else None
                build.write_state(root, state)
            whole = False
            for item in desk.opened(record):
                if item.get('section') in undrawn or item.get('status') == 'waiting' \
                        or item.get('section') not in drawn:
                    item.update(status='set aside', aside='stopped')
                    whole = whole or not item.get('slide')
            record['halted'] = None
            record['desk'].pop('chain', None)
            what = 'stop the whole-deck note' if whole else 'stop the redraw'
            if record.get('desk_jobs'):
                # The words or speaker-notes job is given up: nothing it did is kept.
                record['desk_jobs'] = []
                what = 'stop the change on the desk'
            if record.pop('review_requested', None) is not None:
                # The review is given up: the deck rests on the desk as it did before it.
                for name in ('build-review', 'build-repair', 'build-render'):
                    if name in record['steps']:
                        record['steps'][name] = {**record['steps'][name], 'done': True}
                record['gates']['gate:build'] = {**(record['gates'].get('gate:build') or {}),
                                                 'state': 'waiting'}
                what = 'stop the review of the deck'
            if desk.selected(record):
                # The plan made before the change is put back: the copy is made again from it.
                kept = home.read_json(root / BEFORE, None)
                if isinstance(kept, dict) and (kept.get('change') or {}).get('kind') == 'note':
                    kept['change'] = {}   # the note is set aside as stopped, above
                    home.write_json(root / BEFORE, kept)
                record = self._desk_patch_back(root, record, [])
                self._desk_repatch(root, record)
                what = 'stop the change to your deck'
            self._store(root, record)
            self._commit(root, what)
        run.stop.clear()
        self._desk_shared()
        self.wake(root)
        return self.view(root)

    # --- words -------------------------------------------------------------------------------

    @staticmethod
    def _desk_field(record: dict, field):
        """A field of a slide's words, as the desk deck names it: one of the outline's, or
        on a Selected changes deck ('object', object_id, run_index), one run of one object of
        your own deck, whose speaker notes are kept as they are."""
        if desk.selected(record):
            if field == 'notes':
                raise WorkspaceError(desk.OWN_NOTES)
            return ('object', *words.object_field(field))
        return words.field_of(field)

    def _desk_words_of(self, root, record: dict, state: dict, number, field) -> dict:
        """The slide a word edit names, as the desk reads it: its ID, its section (None for
        a lead slide) and its words in the outline now. Refused while its section is redrawn.
        On a Selected changes deck it is the run's words as the plan makes them, the object
        and the run."""
        if not desk.arrived(record):
            raise WorkspaceError(desk.NOT_YET)
        if gate_state(record, 'gate:build') == 'approved' and decks.delivered(root) is None:
            # Deliver was pressed: words saved now would miss the deck it sends.
            raise WorkspaceError(desk.DELIVERING)
        if desk.selected(record):
            old = words.run_text(outlines.inventory_of(root) or {}, words.plan_of(root),
                                 number, field[1], field[2])
            return {'slide': f'slide-{number}', 'section': None, 'old': old.strip(),
                    'saved': old.strip(), 'object': field[1], 'run': field[2]}
        section = desk.section_of(state, number)
        ident = desk.slide_of(state, number)
        if section is None and isinstance(field, tuple):
            raise WorkspaceError(desk.NO_POINTS)
        if section is not None and desk.busy(record, section):
            raise WorkspaceError(desk.BUSY.format(number=number))
        outline = desk._outline(root)
        slide = next((one for one in build.slides_of(outline) if one.get('id') == ident), None)
        if slide is None:
            raise WorkspaceError(f'The deck has no slide {number}.')
        old = words.text_of(slide, field)
        queued = self._desk_queued(root, record, ident, field)
        return {'slide': ident, 'section': section, 'outline': outline, 'old': old,
                'saved': queued['text'] if queued else old}

    def _desk_queued(self, root, record: dict, ident: str, field) -> dict | None:
        """The newest words queued for one field of one slide, with the name they wait
        under, or None."""
        wanted = list(field) if isinstance(field, tuple) else field
        found = None
        for name in (record.get('desk') or {}).get('edits') or ():
            queued = home.read_json(root / EDITS / f'{name}.json', None)
            if isinstance(queued, dict) and queued.get('slide') == ident \
                    and queued.get('field') == wanted:
                found = {**queued, 'name': name}
        return found

    def desk_words(self, path, number, field, text, seen, session=None) -> dict:
        """A slide's words typed on its card, against the slide's revision the form saw.
        Where they still fit the slide as it is drawn, they are saved to the outline and put
        into the drawing with no composer, and the deck is put together again; where they do
        not, nothing is saved, and the card keeps them with what the slides tool said. On a
        Selected changes deck they are one operation of the plan, made to a copy."""
        if not isinstance(text, str):
            raise WorkspaceError('The words are text.')
        root, space, _ = self._desk_change(path)
        with self.files:
            record, state = self._load(root), build.read_state(root)
            field = self._desk_field(record, field)
            desk.refuse_words(record, field)
            found = self._desk_words_of(root, record, state, number, field)
            desk.check_seen(record, seen, found['slide'])
            if found['saved'] == text.strip():
                return self.view(root)
            if desk.selected(record):
                record, what, also = self._desk_patch(root, record, number, found, text, space)
            else:
                record, what, also = self._desk_save(root, record, state, number, field, text,
                                                     session, space, found)
            self._store(root, record)
            self._commit(root, what, also)
        self._desk_shared()
        self.wake(root)
        return self.view(root)

    def _desk_repatch(self, root, record: dict) -> None:
        """Keep a Selected changes deck's plan as it is, and have the copy made again from it,
        pictured and checked, with no plan job: gate:build waits again once it is."""
        from runner.steps import existing
        steps = record.setdefault('steps', {})
        steps['patch'] = {**(steps.get('patch') or {}),
                          'done': (Path(root) / existing.PATCH).is_file()}
        steps['build-render'] = {**(steps.get('build-render') or {}), 'done': False}
        self._fresh(record, 'build-render')
        gate = record['gates'].get('gate:build') or {}
        record['gates']['gate:build'] = {**gate, 'state': 'absent', 'by': 'desk', 'note': None,
                                         'slides': None, 'at': home.now()}

    def _desk_patch_ready(self, root, record: dict) -> bool:
        """Refuse a change to a Selected changes deck that cannot be made now: while the last
        change is being made, and on a computer that has not made the deck's plan. Returns
        whether the deck is delivered."""
        from runner.steps import existing
        delivered = decks.delivered(root) is not None
        if not delivered and (not desk.resting(record) or desk.opened(record)):
            raise WorkspaceError(desk.PATCH_BUSY)
        if not (Path(root) / existing.PATCH).is_file():
            raise WorkspaceError(desk.NO_DRAWING + ' ' + desk.PATCH_HERE)
        return delivered

    @staticmethod
    def _desk_patch_keep(root, change: dict) -> None:
        """Keep the plan and the desk's shared copy as they are, before `change` is made, so
        they can be put back if the copy cannot be made with it."""
        from runner.steps import existing
        root = Path(root)

        def text(file):
            return file.read_text(encoding='utf-8') if file.is_file() else None
        home.write_json(root / BEFORE, {'plan': text(root / existing.PATCH),
                                        'shared': text(root / words.SHARED_OPS),
                                        'change': change})

    @staticmethod
    def _desk_patch_back(root, record: dict, lines) -> dict:
        """Put the plan and the shared copy back as they were before the change under way,
        which the copy could not take: a typed change stays on its card, with what was said
        of it, as words that do not fit do; a note is set aside, saying why. Call it holding
        `files`. Returns the run."""
        from runner.steps import existing
        root = Path(root)
        kept = home.read_json(root / BEFORE, None)
        if not isinstance(kept, dict):
            return record
        for file, key in ((root / existing.PATCH, 'plan'), (root / words.SHARED_OPS, 'shared')):
            if isinstance(kept.get(key), str):
                write_atomic(file, kept[key])   # byte for byte as it was
            else:
                file.unlink(missing_ok=True)
        change = kept.get('change') or {}
        lines = [str(line) for line in lines]
        if change.get('kind') == 'words':
            record.setdefault('desk', {}).setdefault('unfit', {})[
                f"slide-{change['number']}"] = {
                'number': change['number'], 'field': change['field'], 'text': change['text'],
                'lines': lines, 'at': home.now()}
        for item in desk.notes(record):
            if change.get('kind') == 'note' and item.get('id') == change.get('id'):
                item.update(status='set aside', aside='refused', lines=lines)
        (root / BEFORE).unlink(missing_ok=True)
        return record

    def _desk_patch(self, root, record: dict, number, found: dict, text: str, space,
                    source: str = 'save') -> tuple:
        """One run of one object of a Selected changes deck given new words: one operation
        of the deck's plan, and the copy made again from the whole plan, pictured and checked,
        with no plan job. Your own deck is never changed. Call it holding `files`. Returns the
        run, what the commit says and what else it lists."""
        delivered = self._desk_patch_ready(root, record)
        op = words.plan_op(outlines.inventory_of(root) or {}, number, found['object'],
                           found['run'], text)
        record['desk'].get('unfit', {}).pop(found['slide'], None)
        self._desk_patch_keep(root, {'kind': 'words', 'number': number,
                                     'field': ['object', found['object'], found['run']],
                                     'text': text.strip()})
        also = ()
        if delivered:
            record = delivering.again(root, record, self.slides(), 'Change the words.', space,
                                      sections=[])
            also = self._listed(space)
        words.add_op(root, op)
        desk.advance(record, found['slide'])
        versions = record.setdefault('build_feedback_revisions', {})
        versions[f"slide:{found['slide']}"] = versions.get(f"slide:{found['slide']}", 0) + 1
        self._desk_repatch(root, record)
        said = 'from a selection' if source == 'selection' else 'on the desk'
        return record, f'change the words of slide {number} of your deck {said}', also

    def _desk_save(self, root, record: dict, state: dict, number, field, text, session, space,
                   found: dict, source: str = 'save') -> tuple:
        """Save one slide's words, checked: where they fit they land now (the deck rests or
        is delivered) or between the steps of the chain under way; where they do not, the
        card keeps them. Call it holding `files`. Returns the run, what the commit says and
        what else it lists."""
        ident, section = found['slide'], found['section']
        edited = words.retext(found['outline'], ident, field, text)
        # The outline's own check first: nothing is saved when it refuses.
        outlines.checked_edits(root, record, edited['slides'], self.slides(),
                               self._contract(root))
        whole = words.with_words(words.given(root), edited, ident)
        try:
            if section is None:
                file = words.lead_file(root, state, ident)
                patched = words.patch_section(home.read_json(file, {}), ident, field,
                                              found['old'], text)
                lines = words.lead_fits(patched, state['start']['brand'], self.slides())
            else:
                drawn = home.read_json(root / state['sections'][section]['file'], {})
                patched = words.patch_section(drawn, ident, field, found['old'], text)
                lines = words.fits(root, record, section, patched, self.slides(), whole)
        except WorkspaceError as refusal:
            lines = [str(refusal)]
        if lines:
            record['desk'].setdefault('unfit', {})[ident] = {
                'number': number, 'field': list(field) if isinstance(field, tuple)
                else field, 'text': text.strip(), 'lines': lines, 'at': home.now()}
            return record, f'keep the new words of slide {number}, which do not fit', ()
        desk.advance(record, ident)
        versions = record.setdefault('build_feedback_revisions', {})
        versions[f'slide:{ident}'] = versions.get(f'slide:{ident}', 0) + 1
        record['desk'].get('unfit', {}).pop(ident, None)
        edit = {'slide': ident, 'number': number, 'section': section,
                'field': list(field) if isinstance(field, tuple) else field,
                'text': text.strip(), 'old': found['old'], 'session': session,
                'source': source}
        also = ()
        if decks.delivered(root) is not None or desk.resting(record):
            record, also = self._desk_land(root, record, edit, patched, space)
            what = f'change the words of slide {number} on the desk'
        else:
            # The chain under way puts the deck together: the words land between its
            # steps, and join its next pass. Newer words for the field take the place of
            # those queued for it.
            earlier = self._desk_queued(root, record, ident, field)
            if earlier:
                (root / EDITS / f"{earlier['name']}.json").unlink(missing_ok=True)
                record['desk']['edits'] = [name for name in record['desk'].get('edits') or ()
                                           if name != earlier['name']]
            held = secrets.token_hex(6)
            home.write_json(root / EDITS / f'{held}.json', {**edit, 'patched': patched})
            record['desk'].setdefault('edits', []).append(held)
            what = f'keep the new words of slide {number} for the next pass'
        return record, what, also

    def desk_selection(self, path, number, field, start, end, action, instruction,
                       seen, passage=None) -> dict:
        """Rephrase, Shorten, Expand, Fix or Ask… on a passage of one slide's words: a small
        words job rewrites it, and its words are saved as typed words are. One change to a
        deck at a time."""
        if action not in (*prompts.ACTIONS, 'ask'):
            raise WorkspaceError('Choose Rephrase, Shorten, Expand, Fix or Ask.')
        instruction = self._note(instruction) if action == 'ask' else None
        if action == 'ask' and not instruction:
            raise WorkspaceError('Say what to do with the words.')
        root, _, by = self._desk_change(path)
        with self.files:
            record, state = self._load(root), build.read_state(root)
            desk.refuse_words(record)
            if record.get('desk_jobs'):
                raise WorkspaceError(desk.ONE_CHANGE)
            field = self._desk_field(record, field)
            found = self._desk_words_of(root, record, state, number, field)
            desk.check_seen(record, seen, found['slide'])
            text = found['saved']
            if passage is not None and text[start:end] != passage:
                raise WorkspaceError(desk.SELECTION_CHANGED)
            if type(start) is not int or type(end) is not int \
                    or not 0 <= start < end <= len(text):
                raise WorkspaceError('Select some of the words first.')
            versions = record.get('build_feedback_revisions') or {}
            record['desk_jobs'] = [{
                'id': secrets.token_hex(6), 'kind': 'words', 'slide': found['slide'],
                'number': number, 'field': list(field) if isinstance(field, tuple) else field,
                'start': start, 'end': end, 'action': action, 'instruction': instruction,
                'basis': text, 'by': by, 'at': home.now(),
                'guard': versions.get(f"slide:{found['slide']}", 0)}]
            self._store(root, record)
            self._commit(root, f'ask to change the words of slide {number}')
        self._desk_shared()
        self.wake(root)
        return self.view(root)

    def _desk_job(self, root, run) -> None:
        """The words job the deck waits on: its result replaces the passage, and the field
        is saved as typed words are, while the field is as the job saw it."""
        from runner.steps import Work
        record = self._load(root)
        if decks.in_conversation(record):
            return
        job = record['desk_jobs'][0]
        if job.get('kind') == 'speaker-notes':
            return self._desk_notes_job(root, run, job)
        field = self._desk_field(record, job['field'])
        own = desk.selected(record)
        named = 'words of one part of the slide' if own else words.field_words(field)
        step = stages.Step('desk-words', 'build', 'agent', 'Change the words',
                           'Changing the words of a slide')

        def make(record, request, error):
            if own:
                # Your own deck's slide: its title and the words of each of its parts.
                shown = next((one for one in (outlines.inventory_of(root) or {}).get('slides')
                              or () if one.get('number') == job['number']), {})
                slide = {'title': shown.get('title'), 'parts': [
                    ''.join(item['runs']) for item in words.objects_now(
                        shown, words.plan_of(root))]}
            else:
                outline = desk._outline(root)
                drawn = next((one for one in build.slides_of(outline)
                              if one.get('id') == job['slide']), {})
                slide = {key: drawn.get(key) for key in (*words.FIELDS, 'points')}
            text = job['basis']
            passage = text[job['start']:job['end']]
            line = prompts.ASK if job['action'] == 'ask' else prompts.ACTIONS[job['action']]
            told = [f"Change the words of slide {job['number']} of "
                    f"\"{record.get('title') or 'the deck'}\": one passage of its "
                    f'{named}.' + prompts.passage_task(line).rstrip(),
                    f'The whole {named}:\n\n{text}',
                    f'The passage:\n\n{passage}',
                    ('The slide\'s other words are in your input "slide". Keep the passage '
                     'about as long as the slide has room for: the words must still fit it.')]
            if job['action'] == 'ask':
                told.append(prompts.request('INSTRUCTION', job['instruction'],
                                            prompts.ONLY_PASSAGE, 'Presentation Studio'))
            if error:
                told.append(f'An earlier try at this job did not work: {error}\n'
                            'Take care not to end the same way.')
            read = self._desk_sources(root) if job['action'] == 'expand' else ''
            if read:
                told.append(SOURCES_TOLD)
            told.append('Hand back the replacement for the passage with submit_artifact under '
                        'the name "words".')
            single = field == 'title' or isinstance(field, tuple)   # a run is one line
            return Work(guidance=briefs.guidance('words') + '\n\n' + prompts.edit_rule('slide'),
                        task='\n\n'.join(told), profile='write', name='words',
                        guard=(f"slide:{job['slide']}", job['guard']),
                        prepared={'inputs': {'slide': json.dumps(
                            slide, ensure_ascii=False, indent=2),
                            **({'sources': read} if read else {})}, 'ask': False,
                            'artifacts': {'words': {'kind': 'words', 'text': passage,
                                                    'single': single}}})

        def keep(record, handed):
            state = build.read_state(root)
            text = (job['basis'][:job['start']] + self._text(handed, 'words').strip()
                    + job['basis'][job['end']:])
            try:
                found = self._desk_words_of(root, record, state, job['number'], field)
                if found['saved'] != job['basis']:
                    return   # the words changed since: the job's are not kept
                if own:
                    record, _, _ = self._desk_patch(root, record, job['number'], found, text,
                                                    self.space(), 'selection')
                else:
                    record, _, _ = self._desk_save(root, record, state, job['number'], field,
                                                   text, None, self.space(), found, 'selection')
            except WorkspaceError as refusal:
                # Kept on the card, as words that do not fit are: the deck carries on.
                record['desk'].setdefault('unfit', {})[job['slide']] = {
                    'number': job['number'], 'field': job['field'], 'text': text,
                    'lines': [str(refusal)], 'at': home.now()}
            record['desk_jobs'] = []
            self._store(root, record)

        try:
            self._agent(root, run, step, make, keep, 'change the words of a slide',
                        name=f"desk-words:{job['slide']}", label='Change the words')
        finally:
            with self.files:
                record = self._load(root)
                if not record.get('halted') and record.get('desk_jobs'):
                    record['desk_jobs'] = []
                    self._store(root, record)
                    self._commit(root, 'the change to the words is done')

    @staticmethod
    def _desk_sources(root) -> str:
        """The person's readable sources as one input, each under its title: '' for none."""
        return '\n\n'.join(f"# {one['title']}\n\n{one['text'].strip()}"
                           for one in documents.sources(root)[1])

    def desk_notes(self, path, number, text, seen, session=None) -> dict:
        """A slide's speaker notes, saved as its words are, with no composer."""
        return self.desk_words(path, number, 'notes', text, seen, session)

    def _desk_land(self, root, record: dict, edit: dict, patched: dict, space) -> tuple:
        """Put saved words into the outline, the start's outline and the drawing, and have
        the deck put together again. A deck that rests or is delivered is reopened; one in
        its chain is put together once more before it rests (`_on_desk`). Words queued while
        a chain ran are put into the drawing as it is now, from the words the outline has
        now, and checked again: where they no longer fit, WorkspaceError says why and nothing
        is written. Call it holding `files`, where no step is writing the build. Returns the
        run and what else the commit lists."""
        ident, section = edit['slide'], edit['section']
        state = build.read_state(root)
        if section is None:
            file = words.lead_file(root, state, ident)
            if file is None:
                raise WorkspaceError(desk.NO_DRAWING)
            current = home.read_json(file, {})
        else:
            entry = (state.get('sections') or {}).get(section)
            if entry is None:
                raise WorkspaceError(desk.NO_DRAWING)
            current = home.read_json(root / entry['file'], {})
        outline_now = desk._outline(root)
        if 'words' in edit:
            # A restore: every word of the slide at once, landed while the deck rests.
            outline = desk.with_slide_words(outline_now, ident, edit['words'])
        else:
            field = words.field_of(edit['field'])
            slide = next((one for one in build.slides_of(outline_now)
                          if one.get('id') == ident), None)
            if slide is None:
                raise WorkspaceError('The slide is not in the deck now.')
            old = words.text_of(slide, field)
            outline = words.retext(outline_now, ident, field, edit['text'])
            if current != patched or old != edit.get('old'):
                # The drawing or the words moved on since these words were checked.
                patched = words.patch_section(current, ident, field, old, edit['text'])
                whole = words.with_words(words.given(root), outline, ident)
                lines = words.lead_fits(patched, state['start']['brand'], self.slides()) \
                    if section is None else words.fits(root, record, section, patched,
                                                        self.slides(), whole)
                if lines:
                    raise WorkspaceError(' '.join(lines))
        # Every check is done: from here everything is written.
        desk.keep_slide(root, ident, edit.get('source') or 'save', edit.get('session'))
        outlines._write(root, outline)
        words.retold(root, words.with_words(words.given(root), outline, ident),
                     self.slides().knows())
        if section is None:
            words.land_lead(root, file, patched)
        else:
            words.land(root, record, section, patched)
        versions = record.setdefault('build_feedback_revisions', {})
        for scope in filter(None, (section, 'whole')):
            versions[scope] = versions.get(scope, 0) + 1
        also = ()
        if decks.delivered(root) is not None:
            record = delivering.again(root, record, self.slides(), 'Change the words.', space,
                                      sections=[])
            also = self._listed(space)
        if desk.resting(record) or also:
            record = desk.reopen(record)
            for step in self._reopened(record, 'gate:build'):
                self._fresh(record, step)
        return record, also

    def _desk_land_queued(self, root) -> None:
        """Land the words saved while the chain ran, oldest first, between its steps. Words
        that no longer fit are kept on their card, as typed words that do not fit are."""
        with self.files:
            record = self._load(root)
            if decks.in_conversation(record):
                return
            held, also = list((record.get('desk') or {}).get('edits') or ()), ()
            for name in held:
                file = root / EDITS / f'{name}.json'
                edit = home.read_json(file, None)
                if isinstance(edit, dict):
                    try:
                        record, more = self._desk_land(root, record, edit, edit.pop('patched'),
                                                       self.space())
                        also = also or more
                    except Exception as refusal:  # noqa: BLE001  one edit never stops the deck
                        record['desk'].setdefault('unfit', {})[edit.get('slide')] = {
                            'number': edit.get('number'), 'field': edit.get('field'),
                            'text': edit.get('text') or '',
                            'lines': [str(refusal) if isinstance(refusal, WorkspaceError)
                                      else words.NO_FIT], 'at': home.now()}
                file.unlink(missing_ok=True)
            record['desk']['edits'] = []
            self._store(root, record)
            self._commit(root, 'put in the words saved while the deck was put together', also)

    def desk_redraw_words(self, path, number, field, text, expected) -> dict:
        """Redraw with these words: the words that did not fit are saved to the outline,
        and the slide's section is redrawn to fit them, priced as its slide note is."""
        restoring = field == 'restore'
        root, space, by = self._desk_change(path)
        with self.files:
            record, state = self._load(root), build.read_state(root)
            if desk.selected(record):
                raise WorkspaceError(desk.OWN_REDRAW)
            field = 'title' if restoring else words.field_of(field)
            desk.refuse_words(record, field)
            if not expected or desk.on_screen(root, record, state) != expected:
                raise WorkspaceError(desk.CHANGED)
            if decks.delivered(root) is None and not desk.resting(record):
                raise WorkspaceError(desk.WORDS_BUSY)
            found = self._desk_words_of(root, record, state, number, field)
            ident, section = found['slide'], found['section']
            if section is None:
                raise WorkspaceError(desk.LEAD)
            if restoring:
                kept = ((record.get('desk') or {}).get('unfit') or {}).get(ident) or {}
                if not kept.get('words'):
                    raise WorkspaceError('There is no version of this slide waiting to be '
                                         'redrawn.')
                edited = desk.with_slide_words(found['outline'], ident, kept['words'])
            else:
                edited = words.retext(found['outline'], ident, field, text)
            outline = outlines.checked_edits(root, record, edited['slides'], self.slides(),
                                             self._contract(root))
            desk.keep_slide(root, ident, 'redraw')
            outlines._write(root, outline)
            words.retold(root, words.with_words(words.given(root), outline, ident),
                         self.slides().knows())
            desk.advance(record, ident)
            record['desk'].get('unfit', {}).pop(ident, None)
            retold = record['desk'].setdefault('retold', {}).setdefault(section, [])
            if ident not in retold:
                retold.append(ident)
            item = desk.add_note(record, state, number,
                                 desk.REDRAW_WORDS.format(number=number), home.now(), by)
            record, also, _ = self._desk_ask(root, record, state, [item['section']],
                                             item['note'], space)
            self._store(root, record)
            self._commit(root, f'redraw slide {number} with its new words', also)
        self._desk_shared()
        self.wake(root)
        return self.view(root)

    def desk_versions(self, path, slide) -> list[dict]:
        """A slide's kept versions, newest first: its words, and its picture where this
        computer kept the drawing."""
        root = self.driven(path)
        if root is None:
            raise WorkspaceError('There is no deck there.')
        desk.refuse_off_desk(self._load(root))
        return desk.versions_of(root, slide)

    def desk_restore(self, path, slide, index, seen, stamp=None) -> dict:
        """Bring back a kept version of a slide: its words, and, where this computer kept
        it, its drawing, with no job. Without the drawing the words go back as typed words
        do, and where they no longer fit the card says so. A restore is a version too."""
        root, space, _ = self._desk_change(path)
        with self.files:
            record, state = self._load(root), build.read_state(root)
            if desk.selected(record):
                raise WorkspaceError(desk.OWN_RESTORE)
            kept = desk.versions_of(root, slide)
            if stamp is not None:
                # A version is named by its own stamp: a version kept since the page read
                # the list never moves the one chosen.
                index = next((at for at, one in enumerate(kept) if one['stamp'] == stamp), None)
            if type(index) is not int or not 0 <= index < len(kept):
                raise WorkspaceError('Choose a saved version.')
            if decks.delivered(root) is None and not desk.resting(record):
                raise WorkspaceError(desk.RESTORE_BUSY)
            number = next((one['number'] for one in desk.last_round(state).get('slides') or ()
                           if one['id'] == slide), None)
            found = self._desk_words_of(root, record, state, number, 'title')
            desk.check_seen(record, seen, slide)
            wanted = kept[index]['words']
            outline = desk.with_slide_words(found['outline'], slide, wanted)
            outlines.checked_edits(root, record, outline['slides'], self.slides(),
                                   self._contract(root))
            whole = words.with_words(words.given(root), outline, slide)
            section = found['section']
            drawing = desk.version_drawing(root, slide, kept[index])
            lead = words.lead_file(root, state, slide) if section is None else None
            if section is None and lead is None:
                raise WorkspaceError(desk.NO_DRAWING)
            current = home.read_json(lead if lead else root / state['sections'][section]['file'],
                                     {})
            try:
                if drawing is not None:
                    patched = desk.with_drawing(current, drawing)
                else:
                    patched = current
                    now = next((one for one in build.slides_of(found['outline'])
                                if one.get('id') == slide), {})
                    for field in desk.changed_fields(now, wanted):
                        patched = words.patch_section(patched, slide, field,
                                                      words.text_of(now, field),
                                                      words.text_of(wanted, field))
                lines = words.lead_fits(patched, state['start']['brand'], self.slides()) \
                    if lead else words.fits(root, record, section, patched, self.slides(),
                                            whole)
            except WorkspaceError as refusal:
                lines = [str(refusal)]
            if lines:
                record['desk'].setdefault('unfit', {})[slide] = {
                    'number': number, 'field': 'restore', 'text': wanted.get('title') or '',
                    'words': wanted, 'lines': lines, 'at': home.now()}
                what, also = f'keep version {index + 1} of slide {number}, which does not fit', ()
            else:
                desk.advance(record, slide)
                record['desk'].get('unfit', {}).pop(slide, None)
                record, also = self._desk_land(
                    root, record, {'slide': slide, 'number': number, 'section': section,
                                   'words': wanted, 'source': 'restore'}, patched, space)
                what = f'bring back version {index + 1} of slide {number}'
            self._store(root, record)
            self._commit(root, what, also)
        self._desk_shared()
        self.wake(root)
        return self.view(root)

    def desk_discard(self, path, number) -> dict:
        """Let go of words that did not fit: the card shows the slide's words as saved."""
        root = self._desk_held(path)
        with self.files:
            record, state = self._load(root), build.read_state(root)
            ident = f'slide-{number}' if desk.selected(record) \
                else desk.slide_of(state, number) if state.get('rounds') else None
            if ident and ident in (record.get('desk') or {}).get('unfit', {}):
                record['desk']['unfit'].pop(ident)
                self._store(root, record)
                self._commit(root, f'let go of the new words of slide {number}')
        return self.view(root)

    # --- a saved deck, opened on the desk ---------------------------------------------------

    def open_on_desk(self, path) -> dict:
        """Open a deck delivered the gated way on the desk, from this computer's last drawing
        of it. The gates it passed stay as they were and deliver.json is left as it is: the
        revision delivered stays delivered until a change is made, and the first change makes
        the next revision, as any desk change to a delivered deck does. One version of each
        slide's words is kept first. A deck on the desk already is returned as it is."""
        root = self._held(path)
        if decks.on_desk(self._load(root)):
            return self.view(root)
        space = self.space()
        if decks.delivered(root) is None:
            raise WorkspaceError(desk.NOT_DELIVERED)
        if not self._drawn_here(root, self._load(root)):
            raise WorkspaceError(desk.NO_DRAWING + ' ' + desk.OPEN_ELSEWHERE)
        if self._delivered_here(self._load(root)):
            self._take(root, space)
        self.hold(root)
        with self.files:
            record = self._load(root)
            if decks.on_desk(record):
                return self.view(root)
            if decks.delivered(root) is None:
                raise WorkspaceError(desk.NOT_DELIVERED)
            if not desk.selected(record):
                # Your own deck at Selected changes keeps no versions of its slides.
                for slide in build.slides_of(desk._outline(root)):
                    desk.keep_slide(root, slide.get('id'), 'open')
                # As every desk deck is, it is reviewed only from Finishing: a slide note
                # runs no review by itself. A review asked for before it was delivered is
                # long done.
                record['form'] = {**(record.get('form') or {}), 'initial_review': 'user-first',
                                  'initial_review_source': 'desk'}
                record.pop('review_requested', None)
            # A look drawn again on the desk is picked as this deck's was: by the person, or
            # the brand's default where the saved level chose it.
            picked = looks.chosen(root) or {}
            if picked and not (record.get('form') or {}).get('look'):
                record['form'] = {**(record.get('form') or {}), 'look': 'default'
                                  if picked.get('by') in ('review-policy', 'desk') else 'pick'}
            # Notes from the gated flow were for the deck as delivered: nothing draws them
            # on the desk, and they never ride along with a change made there.
            record['build_feedback_done'] = [*(record.get('build_feedback_done') or []),
                                             *(record.get('build_feedback') or [])]
            record['build_feedback'] = []
            record['flow'] = 'desk'
            record['opened_on_desk'] = home.now()
            desk.arrive(record)
            self._store(root, record)
            self._commit(root, 'open the deck on the desk')
        self._desk_shared()
        return self.view(root)

    @staticmethod
    def _drawn_here(root, record: dict) -> bool:
        """Whether this computer has the deck's last drawing: the last round of its build,
        with the start it was split by, or at Selected changes the plan and its copy."""
        from runner.steps import existing
        state = build.read_state(root)
        if desk.selected(record):
            kept = state.get('deck')
            return bool(kept) and (Path(root) / kept).is_file() \
                and (Path(root) / existing.PATCH).is_file()
        return bool(state.get('rounds')) and bool((state.get('start') or {}).get('sections'))

    # --- a deck drawn elsewhere -------------------------------------------------------------

    def desk_draw_here(self, path) -> dict:
        """Draw a desk deck on this computer, which has no drawing of it: every build step is
        done again here, with the notes it was asked for, as `_settle` does for a gated deck."""
        from runner.engine import BUILT
        root, _, _ = self._desk_change(path)
        with self.files:
            record = self._load(root)
            if desk.selected(record):
                record = self._desk_draw_patch_here(root, record)
                self._store(root, record)
                self._commit(root, 'make the plan and the copy of your deck on this computer')
                self._desk_shared()
                self.wake(root)
                return self.view(root)
            if build.read_state(root).get('start'):
                raise WorkspaceError('This deck is drawn on this computer already.')
            names = [step.name for step in stages.steps(record)]
            for name in BUILT:
                if name in names:
                    record['steps'][name] = {**(record['steps'].get(name) or {}), 'done': False,
                                             'failed': 0}
            if gate_state(record, 'gate:build') == 'waiting' or decks.delivered(root) is None:
                record['gates']['gate:build'] = {**(record['gates'].get('gate:build') or {}),
                                                 'state': 'absent'}
            for item in desk.waiting(record):
                item['status'] = 'drawing'
            self._store(root, record)
            self._commit(root, 'draw the deck on this computer')
        self._desk_shared()
        self.wake(root)
        return self.view(root)

    @staticmethod
    def _desk_draw_patch_here(root, record: dict) -> dict:
        """A Selected changes deck made on this computer, which has neither its plan nor its
        copy: the plan job runs here, with every note made on the desk and the words typed
        there, and the copy is made from it. Call it holding `files`. Returns the run."""
        from runner.steps import existing
        root = Path(root)
        if (root / existing.PATCH).is_file() and (root / existing.PATCHED).is_file():
            raise WorkspaceError('This deck is drawn on this computer already.')
        for name in ('patch', 'build-render'):
            record['steps'][name] = {**(record['steps'].get(name) or {}), 'done': False,
                                     'failed': 0}
        if gate_state(record, 'gate:build') == 'waiting' or decks.delivered(root) is None:
            record['gates']['gate:build'] = {**(record['gates'].get('gate:build') or {}),
                                             'state': 'absent', 'note': None}
        (root / DRAW_HERE).parent.mkdir(parents=True, exist_ok=True)
        (root / DRAW_HERE).write_text('asked\n', encoding='utf-8')
        return record

    def _desk_shared(self) -> None:
        """Share what a desk action did, where the workspace shares after each decision."""
        space = self.workspace
        if space is not None and space.share == gitstate.SHARE[0]:
            self.share_soon()

    # --- Deliver ------------------------------------------------------------------------------

    def desk_deliver(self, path, expected, blockers_seen=None) -> dict:
        """Deliver the deck on screen: the brand's `final` checkpoint, and always the
        person's. Bound to the deck the page read (`expected`) and, where the brand check
        found blockers, to the list the person was shown (`blockers_seen`). Refused while
        desk work runs."""
        root = self._desk_held(path)
        space = self.space()
        by = gitstate.identity(space.repo)
        with self.files:
            record, state = self._load(root), build.read_state(root)
            step = stages.survey(record).next
            if step is None or step.name != 'gate:build' or not desk.resting(record) \
                    or desk.opened(record) or record.get('halted') or record.get('desk_jobs') \
                    or (record.get('desk') or {}).get('edits'):
                raise WorkspaceError(desk.STILL)
            if not (state.get('deck') if desk.selected(record) else state.get('rounds')):
                raise WorkspaceError(desk.NO_DRAWING)
            if not expected or desk.on_screen(root, record, state) != expected:
                raise WorkspaceError(desk.CHANGED)
            if desk.blockers(state) and blockers_seen != desk.blockers_seen(state):
                raise WorkspaceError(desk.BLOCKERS_CHANGED)
            gated = record['gates'].get('gate:build') or {}
            record['gates']['gate:build'] = {**gated, 'state': 'approved',
                                             'note': desk.DELIVERED_FROM, 'at': home.now(),
                                             'by': by, 'round': int(gated.get('round') or 1)}
            self._store(root, record)
            self._commit(root, 'deliver the deck from the desk')
        if space.share == gitstate.SHARE[0]:
            self.share_soon()
        self.wake(root)
        return self.view(root)

    # --- the Outline tab -----------------------------------------------------------------------

    def _desk_resting(self, root, record: dict, space,
                      said: str = 'Change the outline.') -> tuple[dict, tuple]:
        """A change the Outline tab makes is taken while the deck rests on the desk or is
        delivered: a delivered deck is set aside first, to make its next revision. Call it
        holding `files`, once every check of the change has passed. Returns the run, and
        what else its commit lists."""
        if decks.delivered(root) is not None:
            return (delivering.again(root, record, self.slides(), said, space, sections=[]),
                    self._listed(space))
        if not desk.resting(record):
            raise WorkspaceError(desk.OUTLINE_BUSY)
        return record, ()

    def desk_outline(self, path, edited, expected) -> dict:
        """Save the outline as the Outline tab edited it, checked by the slides tool: the
        deck is split again, every section whose slides did not change is kept as drawn, and
        the others are drawn. Bound to the outline the page read (`expected`)."""
        root, space, _ = self._desk_change(path)
        with self.files:
            record = self._load(root)
            if not expected or sha256_of(root / outlines.OUTLINE) != expected:
                raise WorkspaceError(desk.OUTLINE_CHANGED)
            if decks.delivered(root) is None and not desk.resting(record):
                raise WorkspaceError(desk.OUTLINE_BUSY)
            if 'gate:outline' not in {step.name for step in stages.steps(record)}:
                raise WorkspaceError("This deck's words come from the deck you gave: change "
                                     'them there, or note the slide.')
            before = {slide.get('id'): desk.words_of(slide)
                      for slide in build.slides_of(desk._outline(root))}
            outlines.checked_edits(root, record, edited, self.slides(), self._contract(root))
            changed = [slide.get('id') for slide in edited if isinstance(slide, dict)
                       and slide.get('id') in before
                       and desk.words_of(slide) != before[slide.get('id')]]
            for ident in changed:
                desk.keep_slide(root, ident, 'outline')
            self._edit_outline(root, record, edited)   # nothing is written when refused
            for ident in changed:
                desk.advance(record, ident)
            if changed:
                self._store(root, record)
            record, also = self._desk_resting(root, self._load(root), space)
            kept = {name: dict(record['steps'].get(name) or {})
                    for name in ('outline', 'extract', 'brand', 'look-preview')}
            look = dict(record['gates'].get('gate:look') or {})
            record = stages.reopen(record, 'gate:outline')
            for name, entry in kept.items():
                if name in record['steps']:
                    record['steps'][name] = entry
            if look:
                record['gates']['gate:look'] = look
            # The outline's stop is met on the desk again, with the outline as saved.
            record['gates']['gate:outline'] = {
                **(record['gates'].get('gate:outline') or {}), 'state': 'absent'}
            for step in self._reopened(record, 'gate:outline'):
                self._fresh(record, step)
            self._store(root, record)
            self._commit(root, 'save the outline on the desk', also)
        self._desk_shared()
        self.wake(root)
        return self.view(root)

    def desk_outline_price(self, path, edited) -> dict:
        """What saving these unsaved slides would redraw, said before Save: {'says',
        'sections'}. None is the outline as it is saved."""
        root = self.driven(path)
        if root is None:
            raise WorkspaceError('There is no deck there.')
        desk.refuse_off_desk(self._load(root))
        if edited is None:
            edited = build.slides_of(desk._outline(root))
        if not isinstance(edited, list) or not all(isinstance(one, dict) for one in edited):
            raise WorkspaceError('The slides are a list, each one an object.')
        record = self._load(root)
        found = desk.outline_price(record, build.read_state(root), desk._outline(root), edited)
        return {'says': found['says'], 'sections': found['sections']}

    def desk_reread(self, path, kind) -> dict:
        """Read the person's document the other way: as a script for the slides, or as
        material to build from. The outline is written again from it, and the deck after."""
        root, space, by = self._desk_change(path)
        with self.files:
            record = self._load(root)
            if record.get('route') != 'document' or kind not in intake.KINDS:
                raise WorkspaceError(decks.WRONG_READING)
            if kind == record.get('classified'):
                raise WorkspaceError('Your document is read as '
                                     + ('a spec' if kind == 'spec' else 'material')
                                     + ' already.')
            if decks.delivered(root) is None and not desk.resting(record):
                raise WorkspaceError(desk.OUTLINE_BUSY)
            record, also = self._desk_resting(root, record, space)
            for slide in build.slides_of(desk._outline(root)):
                desk.advance(record, slide.get('id'))   # the outline is written again
            said = self._reclassify(root, record, {'kind': kind}, None, home.now(), by)
            self._commit(root, said + ' on the desk', also)
        self._desk_shared()
        self.wake(root)
        return self.view(root)

    def desk_look_again(self, path) -> dict:
        """Change the look: the brand's looks are drawn again, the deck waits for a pick,
        and every section is drawn again in the look picked."""
        root, space, _ = self._desk_change(path)
        with self.files:
            record = self._load(root)
            if 'gate:look' not in {step.name for step in stages.steps(record)}:
                raise WorkspaceError('This deck keeps the look of the deck you gave.')
            if gate_state(record, 'gate:look') == 'waiting':
                also = ()   # at the look's pause: its looks are drawn again for the pick
            else:
                record, also = self._desk_resting(root, record, space, 'Change the look.')
            looks.drop(root)
            record.pop('look_picked', None)
            record = stages.reopen(record, 'gate:look')
            record['gates']['gate:look'] = {**(record['gates'].get('gate:look') or {}),
                                            'state': 'absent'}
            record.setdefault('desk', {})['pick'] = True
            for step in self._reopened(record, 'gate:look'):
                self._fresh(record, step)
            self._store(root, record)
            self._commit(root, 'draw the looks again on the desk', also)
        self._desk_shared()
        self.wake(root)
        return self.view(root)

    def _desk_outline_view(self, root, record: dict) -> dict:
        """What the Outline tab shows: the slides with the version the page sends back, how
        the document is read with what reading it the other way costs, and the look with
        what changing it costs."""
        outline = desk._outline(root)
        picked = looks.chosen(root) or {}
        names = {step.name for step in stages.steps(record)}
        return {'slides': build.slides_of(outline) if outline else [],
                'expected': sha256_of(root / outlines.OUTLINE),
                'editable': 'gate:outline' in names,
                'reading': {'kind': record.get('classified'),
                            'price': (self._reclassify_price(record) or {}).get('says')}
                if record.get('route') == 'document' else None,
                'look': {'name': picked.get('name'),
                         'price': desk.deck_price(self._last_build(record))}
                if 'gate:look' in names else None}

    def _desk_pick_up(self, root) -> None:
        """The notes that came while the deck's sections were drawn, for sections not drawn
        again in this chain yet, go into the ask now, so this chain draws them before the
        deck is put together. Call it holding `files`, between the drawing jobs."""
        record = self._load(root)
        if decks.in_conversation(record) or not decks.on_desk(record) or not desk.waiting(record):
            return
        state = build.read_state(root)
        rounds = len(state.get('rounds') or ())
        fresh = {ident for ident, entry in (state.get('sections') or {}).items()
                 if entry.get('round', 0) >= rounds and rounds}
        taken = sorted({item['section'] for item in desk.waiting(record)
                        if item.get('section') and item['section'] not in fresh},
                       key=build.numbered)
        if not taken:
            return
        for item in desk.waiting(record):
            if item.get('section') in taken:
                item['status'] = 'drawing'
        desk.ask(state, taken)
        build.write_state(root, state)
        self._store(root, record)
        self._commit(root, 'draw the notes that came while the slides were drawn')

    # --- sources and research ------------------------------------------------------------------

    def desk_source(self, path, name, data=None, text=None, title=None) -> dict:
        """Add a source to the deck: a file, or text the person pasted. It is listed under
        Sources and read by the words jobs, the speaker-notes proposals and the outline when
        it is written again. Nothing is drawn and research does not run: Research again
        does, when asked."""
        root = self._desk_held(path)
        if text is not None:
            documents.add_text(root, PASTED if title is None else title, text)
        else:
            documents.add(root, name, data, title)
        return self.view(root)

    @staticmethod
    def _library_idle(root, record: dict) -> None:
        """Refuse a change to the deck's context while an assistant job may be reading it:
        the chain under way, or a desk job running. Hold `files`."""
        if (decks.delivered(root) is None and not desk.resting(record)) \
                or record.get('desk_jobs'):
            raise WorkspaceError(LIBRARY_BUSY)

    def desk_library(self, path, picks) -> dict:
        """Add documents chosen from the shared Document Library to the deck's sources, as
        desk_source adds a file: each chosen revision is checked first, and its text and file
        are copied into the deck, which keeps them when the library changes. Nothing is drawn,
        research does not run and no research setting changes. Refused while a job runs."""
        root = self._desk_held(path)
        with self.files:
            self._library_idle(root, self._load(root))
            try:
                library_context.pin(documents, root, picks)
            except LibraryError as refusal:
                raise WorkspaceError(str(refusal)) from None
        return self.view(root)

    def desk_library_update(self, path, document) -> dict:
        """Take the newest library revision of one source, only because the person asked.
        Refused while a job runs."""
        root = self._desk_held(path)
        with self.files:
            self._library_idle(root, self._load(root))
            try:
                library_context.update(documents, root, document)
            except LibraryError as refusal:
                raise WorkspaceError(str(refusal)) from None
        return self.view(root)

    def desk_library_keep(self, path) -> dict:
        """Keep the delivered deck in the library again, after a failure: from what was
        delivered, with no upload and no slides or assistant job."""
        root = self._desk_held(path)
        library_keep.again(root, self._load(root))
        return self.view(root)

    def desk_research_again(self, path, expected) -> dict:
        """Research again with the sources as they are now: gate:research is reopened as a
        request for changes would reopen it, bringing the evidence up to date, and the
        outline, the look samples and the deck are made again after it. Bound to the deck on
        screen, and priced on the desk (`research_view.price`) before it is asked."""
        root, space, by = self._desk_change(path)
        with self.files:
            record, state = self._load(root), build.read_state(root)
            if not self._desk_research(record):
                raise WorkspaceError(NO_RESEARCH)
            if not expected or desk.on_screen(root, record, state) != expected:
                raise WorkspaceError(desk.CHANGED)
            if decks.delivered(root) is None and not desk.resting(record):
                raise WorkspaceError(RESEARCH_BUSY)
            record, also = self._desk_resting(root, record, space, 'Research again.')
            record, note, more = self._apply_marks(root, record, 'gate:research',
                                                   {'refresh': True}, None)
            gated = record['gates'].get('gate:research') or {}
            record['gates']['gate:research'] = {**gated, 'state': 'changes', 'note': note,
                                                'at': home.now(), 'by': by,
                                                'round': int(gated.get('round') or 1), **more}
            record = stages.reopen(record, 'gate:research')
            for step in self._reopened(record, 'gate:research'):
                self._fresh(record, step)
            self._store(root, record)
            self._commit(root, 'ask to research again on the desk', also)
        self._desk_shared()
        self.wake(root)
        return self.view(root)

    def desk_leave_out(self, path, ids) -> dict:
        """Leave research findings out: the outline and the look samples are made again
        without them, the research is not run again (`_leave_out`), and the slides whose
        outline changed are redrawn (priced by `desk.leave_out_price`). `ids` are every
        finding left out, so an empty list brings back the ones left out before."""
        root, space, by = self._desk_change(path)
        with self.files:
            record = self._load(root)
            if not self._desk_research(record):
                raise WorkspaceError(NO_RESEARCH)
            if decks.delivered(root) is None and not desk.resting(record):
                raise WorkspaceError(RESEARCH_BUSY)
            marked = marks.check('gate:research', 'changes', {'left_out': ids},
                                 self._marked_ids(root, 'gate:research', {}))
            if marked['left_out'] == list((record.get('research') or {}).get('left_out') or ()):
                raise WorkspaceError(LEFT_OUT_ALREADY)
            record, also = self._desk_resting(root, record, space, 'Leave findings out.')
            self._leave_out(root, record, marked['left_out'], home.now(), by)
            record = self._load(root)
            # The outline's stop is met on the desk again, with the outline drafted anew.
            record['gates']['gate:outline'] = {
                **(record['gates'].get('gate:outline') or {}), 'state': 'absent'}
            self._store(root, record)
            self._commit(root, 'leave research findings out on the desk', also)
        self._desk_shared()
        self.wake(root)
        return self.view(root)

    # --- Finishing -----------------------------------------------------------------------------

    def _desk_finishing(self, path):
        """The deck, held for Finishing: refused when it is not on the desk, and for your own
        deck at Selected changes, whose slides are its own and not drawn here."""
        root = self._desk_held(path)
        if desk.selected(self._load(root)):
            raise WorkspaceError(finishing.OWN_DECK)
        return root

    def desk_finish(self, path, tool, expected=None, again=False) -> dict:
        """Run one of Finishing's tools (finishing.TOOLS). Each proposes, and nothing changes
        until Apply: the brand check keeps what the last render's check says, or with
        `again` what the brand's audit says of the deck now, in seconds; Review the deck asks
        the deck's reviewer, bound to the deck on screen (`expected`); Speaker notes asks a
        job for every slide's notes; Rehearse is counted on the page's view, with no job."""
        if tool not in finishing.TOOLS:
            raise WorkspaceError(finishing.NO_TOOL)
        if again is not None and type(again) is not bool:
            raise WorkspaceError('Say whether to check the deck again with true or false.')
        self._desk_finishing(path)
        if tool == 'review':
            return self._desk_review(path, expected)
        if tool == 'notes':
            return self._desk_propose_notes(path)
        root = self._desk_held(path)
        if tool == 'rehearse':
            return self.view(root)
        with self.files:
            record, state = self._load(root), build.read_state(root)
            if not desk.arrived(record):
                raise WorkspaceError(desk.NOT_YET)
            if again:
                if decks.delivered(root) is None and not desk.resting(record):
                    raise WorkspaceError(CHECK_BUSY)
                try:
                    skill = self._skill()
                except WorkspaceError:
                    skill = None
                finishing.check_again(root, record, skill)
                state = build.read_state(root)
            kept = finishing.proposals()
            latest = kept.latest(str(root)).get('brand')
            try:
                current = kept.read(str(root), latest) if latest else None
            except ValueError:
                current = None
            seen = finishing.audit_seen(state)
            if again or current is None or current.get('audit') != seen:
                kept.keep(str(root), secrets.token_hex(16), 'finish-brand',
                          finishing.brand_items(finishing.brand(root, record)), audit=seen)
        return self.view(root)

    def _desk_review(self, path, expected) -> dict:
        """Review the deck, as `review_draft` asks for a gated deck's first draft: the
        reviewer job runs on the deck on screen (`expected`), and what it finds comes back
        per slide as proposals; no section is sent back by itself (build.keep_review)."""
        root = self._desk_held(path)
        with self.files:
            record, state = self._load(root), build.read_state(root)
            if not desk.arrived(record):
                raise WorkspaceError(desk.NOT_YET)
            if desk.selected(record):
                raise WorkspaceError(OWN_REVIEW)
            if not state.get('rounds'):
                raise WorkspaceError(finishing.NO_DECK)
            if not expected or desk.on_screen(root, record, state) != expected:
                raise WorkspaceError(desk.CHANGED)
            if record.get('review_requested'):
                return self.view(root)
            if decks.delivered(root) is not None:
                raise WorkspaceError(REVIEW_DELIVERED)
            if not desk.resting(record) or desk.opened(record) or record.get('desk_jobs') \
                    or (record.get('desk') or {}).get('edits') or record.get('halted'):
                raise WorkspaceError(REVIEW_BUSY)
            if desk.reviewed(state):
                raise WorkspaceError(finishing.REVIEWED)
            record['review_requested'] = {'at': home.now(), 'deck': expected}
            # As review_draft does, except that what each step took is kept, for the price.
            for name in ('build-review', 'build-repair', 'build-render'):
                if name in record['steps']:
                    record['steps'][name] = {**record['steps'][name], 'done': False}
                self._fresh(record, name)
            record['gates']['gate:build'] = {**(record['gates'].get('gate:build') or {}),
                                             'state': 'absent'}
            self._store(root, record)
            self._commit(root, 'ask for a review of the deck on the desk')
        self._desk_shared()
        self.wake(root)
        return self.view(root)

    def _desk_reviewed(self, root) -> None:
        """A desk deck's review is in: what it found is kept as proposals, per slide. Call it
        holding `files`, as the review is kept."""
        state = build.read_state(root)
        # The deck reviewed, and each finding with its slide's own drawing then: the slide
        # drawn again since, or its words changed, no longer takes it.
        finishing.proposals().keep(str(root), secrets.token_hex(16), 'finish-review',
                                   finishing.review_items(root, state),
                                   reviewed_deck=desk.last_round(state).get('deck'))

    def _desk_propose_notes(self, path) -> dict:
        """Speaker notes for every slide, proposed by a job from its words, the outline and
        the sources: one change to a deck at a time, as a words job is."""
        root = self._desk_held(path)
        self.hold(root)
        by = gitstate.identity(self.space().repo)
        with self.files:
            record = self._load(root)
            if not desk.arrived(record):
                raise WorkspaceError(desk.NOT_YET)
            if desk.selected(record):
                raise WorkspaceError(desk.OWN_NOTES)
            if record.get('desk_jobs'):
                raise WorkspaceError(desk.ONE_CHANGE)
            record['desk_jobs'] = [{'id': secrets.token_hex(6), 'kind': 'speaker-notes',
                                    'by': by, 'at': home.now()}]
            self._store(root, record)
            self._commit(root, 'ask for speaker notes for every slide')
        self._desk_shared()
        self.wake(root)
        return self.view(root)

    def _desk_notes_job(self, root, run, job: dict) -> None:
        """The speaker-notes job the deck waits on: what it proposes is kept as proposals,
        each slide's notes now beside the notes proposed. Nothing in the deck changes."""
        from runner.steps import Work
        step = stages.Step('desk-notes', 'build', 'agent', 'Propose speaker notes',
                           'Proposing speaker notes for every slide')

        def make(record, request, error):
            outline = desk._outline(root)
            slides = finishing.notes_slides(outline)
            minutes = (record.get('form') or {}).get('minutes')
            read = self._desk_sources(root)
            title = record.get('title') or 'the deck'
            told = [(f'Propose speaker notes for every slide of "{title}": what the speaker '
                     'says while the slide is shown. Your input "slides" has each slide\'s ID, '
                     'its words and its notes now; your input "outline" is the whole outline.'),
                    (f'The talk is given {minutes} minutes. Notes are said at about '
                     f'{finishing.WPM} words a minute, so share the minutes among the slides.'
                     if minutes else f'Notes are said at about {finishing.WPM} words a minute.')]
            if read:
                told.append(SOURCES_TOLD)
            if error:
                told.append(f'An earlier try at this job did not work: {error}\n'
                            'Take care not to end the same way.')
            told.append('Hand back a JSON list of {"slide", "notes"} with submit_artifact under '
                        'the name "speaker-notes", naming slides only by the IDs in "slides".')
            return Work(guidance=briefs.guidance('speaker-notes'), task='\n\n'.join(told),
                        profile='write', name='speaker-notes',
                        prepared={'inputs': {
                            'slides': json.dumps(slides, ensure_ascii=False, indent=2),
                            'outline': json.dumps(outline, ensure_ascii=False, indent=2),
                            **({'sources': read} if read else {})}, 'ask': False,
                            'artifacts': {'speaker-notes': {
                                'kind': 'speaker-notes',
                                'slides': [one['slide'] for one in slides]}}})

        def keep(record, handed):
            items = finishing.notes_items(desk._outline(root),
                                          self._text(handed, 'speaker-notes'))
            finishing.proposals().keep(str(root), secrets.token_hex(16), 'finish-notes', items)
            record['desk_jobs'] = []
            self._store(root, record)

        try:
            self._agent(root, run, step, make, keep, 'propose speaker notes', name='desk-notes',
                        label='Propose speaker notes')
        finally:
            with self.files:
                record = self._load(root)
                if not record.get('halted') and record.get('desk_jobs'):
                    record['desk_jobs'] = []
                    self._store(root, record)
                    self._commit(root, 'the speaker notes are proposed')

    def desk_apply(self, path, set_id, ids, seen) -> dict:
        """Apply proposals of one of Finishing's sets, against the desk's revision the page
        read (`seen`): a brand check line or a review finding is a note on its slide, which
        redraws its section, as a slide note does; speaker notes are saved as typed notes
        are, with no redraw. `ids` names each proposal, or is {'id', 'after'} with the
        person's own words."""
        self._desk_finishing(path)
        root, space, by = self._desk_change(path)
        with self.files:
            record, state = self._load(root), build.read_state(root)
            if not desk.arrived(record):
                raise WorkspaceError(desk.NOT_YET)
            chosen = [one if isinstance(one, dict) else {'id': one}
                      for one in ids] if isinstance(ids, list) else ids
            numbers = {slide['id']: slide['number']
                       for slide in desk.last_round(state).get('slides') or ()}
            held = {'record': record, 'notes': [], 'also': (), 'numbers': []}

            def note(ident, item, words):
                number = numbers.get(item.get('part'))
                if number is None:
                    raise ValueError(NOT_DRAWN)
                try:
                    made = desk.add_note(held['record'], state, number, words, home.now(), by)
                except WorkspaceError as refusal:
                    raise ValueError(str(refusal)) from None
                held['notes'].append(made)
                held['numbers'].append(number)

            def notes(ident, item, words):
                number = numbers.get(item.get('part'))
                if number is None:
                    raise ValueError(NOT_DRAWN)
                now = build.read_state(root)   # as the notes applied before left it
                try:
                    found = self._desk_words_of(root, held['record'], now, number, 'notes')
                    made, _, also = self._desk_save(root, held['record'], now, number,
                                                    'notes', words, None, space, found,
                                                    'finishing')
                except WorkspaceError as refusal:
                    raise ValueError(str(refusal)) from None
                if item['part'] in ((made.get('desk') or {}).get('unfit') or {}):
                    raise ValueError(desk.UNFIT)
                held['record'], held['also'] = made, (*held['also'], *also)
                held['numbers'].append(number)

            def noted(ident, applied):
                if not held['notes']:
                    return
                for made in held['notes']:
                    desk.keep_slide(root, made['slide'], 'finishing')
                sections = sorted({made['section'] for made in held['notes']}, key=build.numbered)
                made, also, now = self._desk_ask(root, held['record'], state, sections,
                                                 'Apply what Finishing found.', space)
                if now and desk.arrived(made):
                    made['desk']['chain'] = {'kind': desk.SLIDE_NOTE, 'at': home.now()}
                held['record'], held['also'] = made, (*held['also'], *also)

            try:
                done = finishing.proposals(note, noted, notes).apply(str(root), seen, set_id,
                                                                    chosen)
            except ValueError as refusal:
                raise WorkspaceError(str(refusal)) from None
            self._store(root, held['record'])
            told = desk.slides_words(held['numbers']) if held['numbers'] else 'the deck'
            self._commit(root, f'apply what Finishing proposed for {told}', held['also'])
        self._desk_shared()
        self.wake(root)
        return {**self.view(root), 'finished': done}

    def desk_skip(self, path, set_id, ids) -> dict:
        """Skip proposals: each is kept as read, and nothing in the deck changes. Only this
        computer's waiting set does."""
        root = self._desk_finishing(path)
        with self.files:
            try:
                done = finishing.proposals().skip(str(root), set_id, ids)
            except ValueError as refusal:
                raise WorkspaceError(str(refusal)) from None
        return {**self.view(root), 'finished': done}

    # --- the look -----------------------------------------------------------------------------

    def desk_look(self, path, choice, note=None) -> dict:
        """The person's pick at the desk's one pause: the look the deck is drawn in. It is
        theirs, as a pick at the look's gate is, and the deck carries on."""
        root = self._desk_held(path)
        note = self._note(note)
        by = gitstate.identity(self.space().repo)
        with self.files:
            record = self._load(root)
            if gate_state(record, 'gate:look') != 'waiting' or looks.chosen(root) is not None:
                raise WorkspaceError(NO_PICK)
            record = self._approve(root, record, 'gate:look', note, {'look': choice}, {})
            record.get('desk', {}).pop('pick', None)
            gated = record['gates'].get('gate:look') or {}
            record['gates']['gate:look'] = {**gated, 'state': 'approved', 'note': note,
                                            'at': home.now(), 'by': by,
                                            'round': int(gated.get('round') or 1)}
            self._store(root, record)
            self._commit(root, 'pick the look on the desk')
        self._desk_shared()
        self.wake(root)
        return self.view(root)
