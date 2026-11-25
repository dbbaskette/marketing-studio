"""The one gate every changing page route and desk command passes before it runs: a deck the
earlier step-by-step flow saved is refused by default (GitHub issue #542).

Nothing continues such a deck. What may change its folder is a short list, and only for the
decks it is for: the explicit migration (its preview, apply, and finishing an interrupted
opening); Take, the team's own action, where the deck must be taken to open it on the desk
(the engine checks that it would open there: `Engine._take_only_to_open`); Delete; start-up's
recovery of a stopped step; and, for a delivered deck, what a finished deck could always do
that does not continue the flow (the finished Open on the desk, publishing it to the team).
Reading it (its check, its files, copying its setup into a new deck's form) changes nothing.

`page.SAVED_ROUTES` and `studio.SAVED_COMMANDS` give every changing route and desk command
one decision: `WORKSPACE` (about no deck), `READS` (allowed only as a read), `TAKE` (Take
only), or the deck states it is allowed for. A route or command with no decision is refused
for every saved deck. `check` refuses in plain words and changes nothing.
"""
from __future__ import annotations

from pathlib import Path

from runner import decks
from studio_core import presentation_migration as migration
from workspace import WorkspaceError

# How a saved deck stands, as far as its small record says: 'saved' (not delivered: it
# opens on the desk or is read-only), 'finished' (delivered), 'unreadable' (the runner
# refuses its record) or 'interrupted' (its opening on the desk stopped part way).
STATES = ('saved', 'finished', 'unreadable', 'interrupted')
ALL = frozenset(STATES)
NEVER = frozenset()
WORKSPACE = 'workspace'   # about no deck: the gate does not look
READS = 'reads'           # allowed only when it is sent as a read ({"action": "read"})
TAKE = 'take'             # /api/drive: Take only, for a deck that may be taken to open it

FLOW_ENDED = ('The earlier step-by-step flow no longer continues the decks it saved. Open '
              'this one on the desk, or start new work from it.')
UNREAD = ('This deck’s saved record cannot be read, so nothing changes it here. Its saved '
          'files are kept as they are: restore its record from your workspace history, or '
          'start a new deck.')
UNREAD_NEXT = ('Nothing here changes it: its saved files are kept as they are, and its record '
               'comes back from your workspace history, or new work starts from it.')
INTERRUPTED = ('Opening this deck on the desk was interrupted. Finish opening it on the desk '
               'first.')
SAID = {'saved': FLOW_ENDED, 'finished': FLOW_ENDED, 'unreadable': UNREAD,
        'interrupted': INTERRUPTED}


def standing(engine, path) -> str | None:
    """How a saved deck stands (one of STATES), or None for anything else: desk work, no
    deck there, or no workspace. Only its small records are read."""
    if not isinstance(path, (str, Path)) or not str(path):
        return None
    root = engine.driven(path)
    if root is None:
        return None
    pending = root / migration.PENDING
    if pending.exists() or pending.is_symlink():
        return 'interrupted'
    try:
        record = engine._load(root)
    except WorkspaceError:
        return 'unreadable'
    if decks.on_desk(record):
        return None
    return 'finished' if decks.delivered(root) is not None else 'saved'


def allowed(decision, state: str, sent: dict) -> bool:
    if decision == WORKSPACE:
        return True
    if decision == READS:
        return sent.get('action') == 'read'
    if decision == TAKE:
        return sent.get('action') == 'take' and state in ('saved', 'finished')
    return state in decision


def check(engine, decision, path, sent: dict | None = None) -> None:
    """Refuse, in plain words and changing nothing, what `decision` does not allow for the
    saved deck at `path`. Anything that is not a saved deck passes."""
    if decision == WORKSPACE:
        return
    state = standing(engine, path)
    if state is None or allowed(decision, state, sent or {}):
        return
    if state == 'unreadable':
        # The runner's own reason first, as its read-only record says it.
        try:
            engine._load(engine.driven(path))
        except WorkspaceError as refusal:
            raise WorkspaceError(f'{refusal} {UNREAD_NEXT}') from None
    raise WorkspaceError(SAID[state])
