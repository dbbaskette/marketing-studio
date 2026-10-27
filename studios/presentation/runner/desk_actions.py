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

import runner  # noqa: F401  puts the core on the import path
import home
from workspace import WorkspaceError

from runner import decks, desk, gitstate, stages
from runner.jobs import gate_state, sha256_of
from runner.steps import build, intake
from runner.steps import deliver as delivering
from runner.steps import outline as outlines
from runner.steps import look as looks

NO_PICK = 'The look is not waiting to be picked now.'
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
            if not desk.passes(record, step.name):
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
                item['status'] = 'set aside'
            left = []
        record['desk']['again'] = again + 1 if left else 0
        chain = record['desk'].get('chain') if not left else None
        if chain:
            # What a note's chain took here, for the next price's "usually".
            from datetime import datetime
            try:
                took = (datetime.fromisoformat(home.now().replace('Z', '+00:00'))
                        - datetime.fromisoformat(chain['at'].replace('Z', '+00:00')))
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
        return {**shown, 'arrived': desk.arrived(record),
                'working': desk.working(root, record, state),
                'outline': self._desk_outline_view(root, record),
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
            if not expected or desk.last_round(state).get('deck') != expected:
                raise WorkspaceError(desk.CHANGED)
            item = desk.add_note(record, state, number, note, home.now(), by)
            record, also, now = self._desk_ask(root, record, state, [item['section']], note,
                                               space)
            if now and desk.arrived(record):
                record['desk']['chain'] = {'kind': desk.SLIDE_NOTE, 'at': home.now()}
            self._store(root, record)
            self._commit(root, f'ask to redraw slide {number}', also)
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
        self.wake(root)
        return self.view(root)

    def desk_stop(self, path) -> dict:
        """Stop the redraw under way, as Stop does, and wait for it to end. What was redrawn
        is kept; the sections not redrawn yet come off the ask, their notes set aside, and
        the deck is put together from what it has."""
        from runner.engine import Engine
        root = self._desk_held(path)
        if desk.working(root, self._load(root)) is None:
            raise WorkspaceError(desk.NOTHING_TO_STOP)
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
            for item in desk.opened(record):
                if item.get('section') in undrawn or item.get('status') == 'waiting':
                    item['status'] = 'set aside'
            record['halted'] = None
            record['desk'].pop('chain', None)
            self._store(root, record)
            self._commit(root, 'stop the whole-deck note')
        run.stop.clear()
        self.wake(root)
        return self.view(root)

    # --- the Outline tab -----------------------------------------------------------------------

    def _desk_resting(self, root, record: dict, space) -> dict:
        """A change the Outline tab makes is taken while the deck rests on the desk or is
        delivered: a delivered deck is set aside first, to make its next revision. Call it
        holding `files`. Returns the run."""
        if decks.delivered(root) is not None:
            return delivering.again(root, record, self.slides(), 'Change the outline.', space,
                                    sections=[])
        if not desk.resting(record):
            raise WorkspaceError(desk.OUTLINE_BUSY)
        return record

    def desk_outline(self, path, edited, expected) -> dict:
        """Save the outline as the Outline tab edited it, checked by the slides tool: the
        deck is split again, every section whose slides did not change is kept as drawn, and
        the others are drawn. Bound to the outline the page read (`expected`)."""
        root, space, by = self._desk_change(path)
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
            record = self._desk_resting(root, self._load(root), space)
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
            self._commit(root, 'save the outline on the desk',
                         self._listed(space) if decks.delivered(root) is None
                         and record.get('revisions') else ())
        self.wake(root)
        return self.view(root)

    def desk_outline_price(self, path, edited) -> dict:
        """What saving these unsaved slides would redraw, said before Save: {'says'}."""
        root = self._desk_held(path)
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
            record = self._desk_resting(root, record, space)
            said = self._reclassify(root, record, {'kind': kind}, None, home.now(), by)
            self._commit(root, said + ' on the desk')
        self.wake(root)
        return self.view(root)

    def desk_look_again(self, path) -> dict:
        """Change the look: the brand's looks are drawn again, the deck waits for a pick,
        and every section is drawn again in the look picked."""
        root, space, by = self._desk_change(path)
        with self.files:
            record = self._load(root)
            if 'gate:look' not in {step.name for step in stages.steps(record)}:
                raise WorkspaceError('This deck keeps the look of the deck you gave.')
            record = self._desk_resting(root, record, space)
            looks.drop(root)
            record.pop('look_picked', None)
            record = stages.reopen(record, 'gate:look')
            record['gates']['gate:look'] = {**(record['gates'].get('gate:look') or {}),
                                            'state': 'absent'}
            record.setdefault('desk', {})['pick'] = True
            for step in self._reopened(record, 'gate:look'):
                self._fresh(record, step)
            self._store(root, record)
            self._commit(root, 'draw the looks again on the desk')
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
        self.wake(root)
        return self.view(root)
