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

from runner import desk, gitstate, stages
from runner.jobs import gate_state
from runner.steps import build
from runner.steps import look as looks

NO_PICK = 'The look is not waiting to be picked now.'


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

    def _desk_held(self, path):
        """The deck, held for a change on the desk: refused when this computer may not
        change it, and when it is not on the desk."""
        root = self._held(path)
        desk.refuse_off_desk(self._load(root))
        return root

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
            gated = record['gates'].get('gate:look') or {}
            record['gates']['gate:look'] = {**gated, 'state': 'approved', 'note': note,
                                            'at': home.now(), 'by': by,
                                            'round': int(gated.get('round') or 1)}
            self._store(root, record)
            self._commit(root, 'pick the look on the desk')
        self.wake(root)
        return self.view(root)
