"""Ways on from a deck that stopped, beside Try again.

A training on the desk that stops at one of its deck's steps offers, with Try again:

    'slide-text'   go back to what the deck says: it waits for the person's approval as
                   slide text, and drawing starts again from what they approve
    'leave-deck'   finish without the deck: it is left out with SET_ASIDE as the reason,
                   everything written for it is kept, and the rest can be made ready
    'bring-deck'   bring back a deck that was set aside this way; it carries on from what
                   it kept

What a caller needs to know
---------------------------
    recovery.WAYS                          # the actions, as `Engine.act` takes them
    recovery.ways(root, record, session)   # what a stop offers now: [{'id', 'label', 'says'}]
    recovery.aside(session)                # whether the deck is set aside, to be brought back
    recovery.take(engine, root, way)       # do one; call it holding the engine's `files`

- Nothing is offered to a training that is not on the desk, or for a stop that is not a
  deck's: those keep the one action their stop has.
- None of these spends anything by itself. Bringing the deck back and approving the slide
  text start the deck's steps again, as Try again does.
"""
from __future__ import annotations

from pathlib import Path

import workspace
from studio_core import deck_content

from runner import drafts, pipeline

WAYS = ('slide-text', 'leave-deck', 'bring-deck')
SET_ASIDE = ('Set aside after it stopped. What was written for it is kept: bring it back to '
             'carry on from there.')
LABELS = {
    'slide-text': ('Review the slide text',
                   'Go back to what the deck says. Nothing is drawn until you approve it.'),
    'leave-deck': ('Finish without the deck',
                   'The deck is set aside and its slide text is kept. The other materials '
                   'can be marked ready and exported, and you can bring the deck back.'),
    'bring-deck': ('Bring the deck back',
                   'The deck carries on from what it kept.'),
}
NOT_OFFERED = 'That is not offered for this training now. Nothing was changed.'
# The deck steps that come after what it says is approved: a stop at one can go back to it.
AFTER_TEXT = pipeline.DECK_STEPS[pipeline.DECK_STEPS.index('gate:deck-outline') + 1:]


def _base(step: str) -> str:
    return pipeline.bare(step.partition(':')[0]) if not step.startswith('gate:') \
        else pipeline.bare(step)


def level_of(step: str) -> str | None:
    """The level a deck step is for: `deck-sections@301:3` is 301, and a plain one None."""
    return (step.partition(':')[0] if not step.startswith('gate:') else step
            ).partition('@')[2] or None


def aside(session: dict) -> bool:
    """Whether the deck was set aside after a stop, and has not been brought back."""
    if 'deck' in session['settings']['stages']:
        return False
    said = [event.get('reason') for event in session.get('events') or ()
            if event.get('event') == 'skip' and event.get('stage') == 'deck']
    return bool(said) and said[-1] == SET_ASIDE


def ways(root: Path, record: dict, session: dict) -> list[dict]:
    """What a stop offers beside its one action, in the order to show them."""
    if not drafts.on_desk(record):
        return []
    offered = []
    problem = record.get('problem') or {}
    step = problem.get('step') or ''
    base = _base(step) if step else ''
    if problem.get('state') == 'failed' and base in pipeline.DECK_STEPS \
            and 'deck' in session['settings']['stages']:
        level = level_of(step)
        if base in AFTER_TEXT and pipeline.place(root, level, pipeline.OUTLINE).is_file():
            offered.append('slide-text')
        offered.append('leave-deck')
    return [{'id': way, 'label': LABELS[way][0], 'says': LABELS[way][1]} for way in offered]


def take(engine, root: Path, way: str) -> str:
    """Take one way on. Returns what to say in the commit. Call it holding `files`."""
    record, session = engine._load(root), workspace.load(root)
    problem = record.get('problem') or {}
    if way == 'bring-deck':
        if not drafts.on_desk(record) or not aside(session):
            raise workspace.WorkspaceError(NOT_OFFERED)
        workspace.skip(root, 'deck', clear=True, by='page')
        for step in pipeline.DECK_STEPS:
            engine._fresh(record, step)
        engine._store(root, record)
        return 'bring back the slide deck that was set aside'
    if way not in [offer['id'] for offer in ways(root, record, session)]:
        raise workspace.WorkspaceError(NOT_OFFERED)
    step = problem['step']
    if way == 'leave-deck':
        workspace.skip(root, 'deck', reason=SET_ASIDE, by='page')
        said = 'set the slide deck aside after it stopped'
    else:
        # The approval the desk gave on the way through is withdrawn, and this training
        # waits for the person's own from here on.
        kept = engine._decided(record, level_of(step))
        kept['approved'] = None
        record['deck_content'] = deck_content.PROTOCOL
        said = 'go back to what the slide deck says, for approval'
    engine._fresh(record, step.partition(':')[0])
    record['problem'] = record['halt'] = None
    engine._store(root, record)
    return said
