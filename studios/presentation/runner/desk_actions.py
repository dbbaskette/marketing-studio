"""The engine's desk: what a person does to a deck on the desk, and how its stops are met.

What a caller needs to know
---------------------------
    engine.desk_look(path, look_id, note=None)   # the start chose to pick: the person's pick

- `DeskActions` is a part of the engine (runner/engine.py mixes it in), as `jobs.Jobs` is.
  Every action begins with `_held` and refuses a deck that is not on the desk
  (`desk.NOT_ON_DESK`). Each records what was asked and, where something is to be drawn
  again, reopens gate:build (`desk.reopen`); the engine's own steps then do the work.
- `_desk_gate` meets a stop the desk deck continues past (`desk.passes`) as `_policy_gate`
  meets one a review level continues past: with what the stop shows, a desk receipt and a
  commit, and never as a person's approval.
"""
from __future__ import annotations

import secrets
from pathlib import Path

# isort: off
import runner  # noqa: F401  puts the core on the import path
import home
from workspace import WorkspaceError

from runner import decks, desk, gitstate, stages
from runner.jobs import gate_state, sha256_of
from runner.steps import build, intake, words
from runner.steps import deliver as delivering
from runner.steps import look as looks
from runner.steps import outline as outlines
# isort: on

NO_PICK = 'The look is not waiting to be picked now.'
EDITS = Path('work') / 'desk' / 'edits'   # words saved while a chain ran, until they land
AGAIN = 3   # chains one rest on the desk may run for notes that came while it was put together


class DeskActions:
    """The engine's part for decks on the desk."""

    # --- the stops a desk deck continues past ------------------------------------------------

    def _desk_gate(self, root, step: stages.Step) -> None:
        """Continue past a stop of a desk deck with the desk's receipt: what the stop shows
        is fingerprinted, and the gate is approved by the desk. At the look, the start chose
        the brand's default: it is chosen, in words that say so."""
        with self.files:
            record = self._load(root)
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
        first = desk.arrive(record)
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
        record['desk']['again'] = again + 1 if left else 0
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
        shown = desk.cards(root, record, lambda section: desk.section_price(
            record, state, section)['says'])
        return {**shown, 'arrived': desk.arrived(record), 'seen': desk.revision(record),
                'progress': None if desk.arrived(record) else {
                    'minutes_left': desk.estimate(record), 'started_at': record.get('created')},
                'working': desk.working(root, record, state),
                'deliverable': desk.deliverable(root, record),
                'outline': self._desk_outline_view(root, record),
                **({} if shown['drawn_here'] else {
                    'no_drawing': desk.NO_DRAWING,
                    'draw_here_price': desk.deck_price(self._last_build(record))}),
                'delivered': decks.delivered(root),
                'revision': desk.DELIVERED_AGAIN.format(
                    revision=len(record['revisions']), next=len(record['revisions']) + 1)
                if record.get('revisions') and decks.delivered(root) is None else None,
                'deck_price': desk.deck_price(self._last_build(record)),
                'blockers': desk.blockers(state), 'blockers_seen': desk.blockers_seen(state),
                'reviewed': desk.reviewed(state)}

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
            if not expected or desk.last_round(state).get('deck') != expected:
                raise WorkspaceError(desk.CHANGED)
            item = desk.add_note(record, state, number, note, home.now(), by)
            record, also, now = self._desk_ask(root, record, state, [item['section']], note,
                                               space)
            if now and desk.arrived(record):
                record['desk']['chain'] = {'kind': desk.SLIDE_NOTE, 'at': home.now()}
            self._store(root, record)
            self._commit(root, f'ask to redraw slide {number}', also)
        self._desk_shared()
        self.wake(root)
        return self.view(root)

    def desk_deck_note(self, path, note, expected) -> dict:
        """A note for the whole deck: every section is redrawn with it, three at a time, and
        the deck is put together once they are. Bound to the deck on screen."""
        note = self._note(note)
        if not note:
            raise WorkspaceError(desk.NO_DECK_NOTE)
        root, space, by = self._desk_change(path)
        with self.files:
            record, state = self._load(root), build.read_state(root)
            if not desk.arrived(record):
                raise WorkspaceError(desk.NOT_YET)
            if not expected or desk.last_round(state).get('deck') != expected:
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
        again = (record.get('halted') or {}).get('state') in ('stopped', 'failed') and (
            desk.opened(record) or (build.read_state(root).get('asked') or {}).get('sections'))
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
            self._store(root, record)
            self._commit(root, 'stop the whole-deck note' if whole else 'stop the redraw')
        run.stop.clear()
        self._desk_shared()
        self.wake(root)
        return self.view(root)

    # --- words -------------------------------------------------------------------------------

    def _desk_words_of(self, root, record: dict, state: dict, number, field) -> dict:
        """The slide a word edit names, as the desk reads it: its ID, its section (None for
        a lead slide) and its words in the outline now. Refused while its section is redrawn."""
        if not desk.arrived(record):
            raise WorkspaceError(desk.NOT_YET)
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
        return {'slide': ident, 'section': section, 'outline': outline,
                'old': words.text_of(slide, field)}

    def desk_words(self, path, number, field, text, seen, session=None) -> dict:
        """A slide's words typed on its card, against the slide's revision the form saw.
        Where they still fit the slide as it is drawn, they are saved to the outline and put
        into the drawing with no composer, and the deck is put together again; where they do
        not, nothing is saved, and the card keeps them with what the slides tool said."""
        field = words.field_of(field)
        if not isinstance(text, str):
            raise WorkspaceError('The words are text.')
        root, space, _ = self._desk_change(path)
        with self.files:
            record, state = self._load(root), build.read_state(root)
            found = self._desk_words_of(root, record, state, number, field)
            ident, section = found['slide'], found['section']
            desk.check_seen(record, seen, ident)
            if found['old'] == text.strip():
                return self.view(root)
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
                self._store(root, record)
                self._commit(root, f'keep the new words of slide {number}, which do not fit')
                return self.view(root)
            desk.advance(record, ident)
            record['desk'].get('unfit', {}).pop(ident, None)
            edit = {'slide': ident, 'number': number, 'section': section,
                    'field': list(field) if isinstance(field, tuple) else field,
                    'text': text.strip(), 'old': found['old'], 'session': session}
            also = ()
            if decks.delivered(root) is not None or desk.resting(record):
                record, also = self._desk_land(root, record, edit, patched, space)
                what = f'change the words of slide {number} on the desk'
            else:
                # The chain under way puts the deck together: the words land between its
                # steps, and join its next pass.
                held = secrets.token_hex(6)
                home.write_json(root / EDITS / f'{held}.json', {**edit, 'patched': patched})
                record['desk'].setdefault('edits', []).append(held)
                what = f'keep the new words of slide {number} for the next pass'
            self._store(root, record)
            self._commit(root, what, also)
        self._desk_shared()
        self.wake(root)
        return self.view(root)

    def desk_notes(self, path, number, text, seen, session=None) -> dict:
        """A slide's speaker notes, saved as its words are, with no composer."""
        return self.desk_words(path, number, 'notes', text, seen, session)

    def _desk_land(self, root, record: dict, edit: dict, patched: dict, space) -> tuple:
        """Put saved words into the outline, the start's outline and the drawing, and have
        the deck put together again. A deck that rests or is delivered is reopened; one in
        its chain puts them together in its next pass. Call it holding `files`, where no step
        is writing the build. Returns the run and what else the commit lists."""
        field = words.field_of(edit['field'])
        ident, section = edit['slide'], edit['section']
        outline = words.retext(desk._outline(root), ident, field, edit['text'])
        state = build.read_state(root)
        # The words go into the drawing as it is now: another edit may have landed in it
        # since these words were checked.
        if section is None:
            file = words.lead_file(root, state, ident)
            current = home.read_json(file, {})
        else:
            current = home.read_json(root / state['sections'][section]['file'], {})
        if current != patched:
            patched = words.patch_section(current, ident, field, edit['old'], edit['text'])
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
        """Land the words saved while the chain ran, oldest first, between its steps."""
        with self.files:
            record = self._load(root)
            held = list((record.get('desk') or {}).get('edits') or ())
            for name in held:
                file = root / EDITS / f'{name}.json'
                edit = home.read_json(file, None)
                if isinstance(edit, dict):
                    try:
                        record, _ = self._desk_land(root, record, edit, edit.pop('patched'),
                                                    self.space())
                    except WorkspaceError:
                        pass   # the slide is gone or redrawn: its words are not drawn here
                file.unlink(missing_ok=True)
            record['desk']['edits'] = []
            self._store(root, record)
            self._commit(root, 'put in the words saved while the deck was put together')

    def desk_redraw_words(self, path, number, field, text, expected) -> dict:
        """Redraw with these words: the words that did not fit are saved to the outline,
        and the slide's section is redrawn to fit them, priced as its slide note is."""
        field = words.field_of(field)
        root, space, by = self._desk_change(path)
        with self.files:
            record, state = self._load(root), build.read_state(root)
            if not expected or desk.last_round(state).get('deck') != expected:
                raise WorkspaceError(desk.CHANGED)
            if decks.delivered(root) is None and not desk.resting(record):
                raise WorkspaceError(desk.WORDS_BUSY)
            found = self._desk_words_of(root, record, state, number, field)
            ident, section = found['slide'], found['section']
            if section is None:
                raise WorkspaceError(desk.LEAD)
            edited = words.retext(found['outline'], ident, field, text)
            outline = outlines.checked_edits(root, record, edited['slides'], self.slides(),
                                             self._contract(root))
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

    def desk_discard(self, path, number) -> dict:
        """Let go of words that did not fit: the card shows the slide's words as saved."""
        root = self._desk_held(path)
        with self.files:
            record, state = self._load(root), build.read_state(root)
            ident = desk.slide_of(state, number) if state.get('rounds') else None
            if ident and ident in (record.get('desk') or {}).get('unfit', {}):
                record['desk']['unfit'].pop(ident)
                self._store(root, record)
                self._commit(root, f'let go of the new words of slide {number}')
        return self.view(root)

    # --- a deck drawn elsewhere -------------------------------------------------------------

    def desk_draw_here(self, path) -> dict:
        """Draw a desk deck on this computer, which has no drawing of it: every build step is
        done again here, with the notes it was asked for, as `_settle` does for a gated deck."""
        from runner.engine import BUILT
        root, _, _ = self._desk_change(path)
        with self.files:
            record = self._load(root)
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
                    or desk.opened(record) or record.get('halted'):
                raise WorkspaceError(desk.STILL)
            if not state.get('rounds'):
                raise WorkspaceError(desk.NO_DRAWING)
            if not expected or desk.last_round(state).get('deck') != expected:
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
            self._edit_outline(root, record, edited)   # nothing is written when refused
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
        if not decks.on_desk(record) or not desk.waiting(record):
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
