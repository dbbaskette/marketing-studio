"""Saved-flow trainings in their original format, kept as static files (GitHub issue #542).

Each folder under `fixtures/saved/<state>/` is one training exactly as the earlier gated
("saved") flow left it on disk at one stop: its session and run records, its materials,
reviews, history and research, byte for byte. They were captured by running that flow with
the suite's scripted workers while it existed; it went with phase C, and
`test_saved_fixtures.py` checks each stored tree against itself. Tests of the explicit
migration, of saved states and of the finished Open on the desk load them with `load`.
`finished-later-document.documents.json` beside them is what the documents stand-in held for
that training (the stand-in keeps its documents in memory).

    root = saved_fixtures.load(case, 'blueprint-gate')

copies the stored training into the case's disposable workspace, registers it on this
computer as the saved flow did, and commits it, as a saved training is found in a workspace.
Nothing else is changed: the files are the stored bytes.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'saved'
SESSION = '.training-studio/session.json'
# Derived home metadata, rewritten whenever the run is stored: not a saved input
# (`desk_chat._files` leaves it out too), so it is not kept.
LEFT_OUT = ('work/.studio-summary.json',)
# A deck's working files (worker briefs, look samples) name the training's own folder by its
# full path. Stored, that path is this mark; `load` writes the folder it loads into instead,
# as those files say it for a training where it is.
FOLDER = b'@SAVED_TRAINING_FOLDER@'


def names() -> list[str]:
    """Every stored state the earlier gated flow saved (the conversation-guided trainings
    under `conversation/` are listed by `conversation_names`, and `flow/` holds the trees
    `stored_builders` places)."""
    return sorted(path.name for path in FIXTURES.iterdir()
                  if path.is_dir() and path.name not in ('conversation', 'flow'))


def tree(state: str) -> dict[str, bytes]:
    """The stored files of one state, by their path inside the training's folder."""
    folder = FIXTURES / state
    if not folder.is_dir():
        raise KeyError(f'No saved fixture called {state}.')
    return {path.relative_to(folder).as_posix(): path.read_bytes()
            for path in sorted(folder.rglob('*')) if path.is_file()}


def ident(state: str) -> str:
    """The training's folder name, which its session record names as its id."""
    return json.loads((FIXTURES / state / SESSION).read_bytes())['id']


def load(case, state: str) -> Path:
    """Copy one stored state into `case`'s workspace, as a saved training this computer
    knows, committed. Answers the training's folder."""
    import home
    from runner import gitstate
    space = case.engine.space()
    root = space.root / ident(state)
    if root.exists():
        raise FileExistsError(f'{root.name} is already in this workspace.')
    shutil.copytree(FIXTURES / state, root)
    for path in root.rglob('*'):
        if path.is_file() and FOLDER in path.read_bytes():
            path.write_bytes(path.read_bytes().replace(FOLDER, str(root).encode()))
    session = json.loads((root / SESSION).read_bytes())
    home.remember(root, session['title'], list(session['levels']))
    gitstate.commit(space, f'{session["title"]}: a saved training', [root])
    return root


# --- conversation-guided trainings (GitHub issue #547) ---------------------------------------
#
# Each folder under `fixtures/saved/conversation/<state>/` is one training a conversation
# made with the helper `training.py` (approval in chat or on the helper's page), exactly as
# the helper left it at one stop, byte for byte. They were captured by really driving the
# helper with synthetic content: started as the retired `training.py init` started one, then
# every change a helper command (`save`, `approve`, `skip`, `checkpoint`, `pin`, `export`,
# `research-import`) or a decision on the helper's page. None has a run record: no runner
# drove it. Such a training lives in a folder of its own, outside the workspace, and reaches
# the runner only through Bring in.
#
# Those commands and that page are gone, so these trees are the only record of what the
# retired helper wrote and cannot be captured again. They are history: never rewritten, and
# never compared with what is installed today except where a test says what a difference
# would mean for saved work (the Yoodli profile, in `test_saved_fixtures.py`).

CONVERSATION = FIXTURES / 'conversation'


def conversation_names() -> list[str]:
    """Every stored conversation-guided state."""
    return sorted(path.name for path in CONVERSATION.iterdir() if path.is_dir())


def conversation_tree(state: str) -> dict[str, bytes]:
    """The stored files of one conversation-guided state, by their path in its folder."""
    folder = CONVERSATION / state
    if not folder.is_dir():
        raise KeyError(f'No conversation fixture called {state}.')
    return {path.relative_to(folder).as_posix(): path.read_bytes()
            for path in sorted(folder.rglob('*')) if path.is_file()}


def conversation_title(state: str) -> tuple[str, list]:
    """The title and levels the helper remembered the training by: its session record's, or,
    where that record cannot be read, the folder's name (what the registry still holds is
    not part of the stored tree)."""
    try:
        session = json.loads((CONVERSATION / state / SESSION).read_bytes())
        return session['title'], list(session['levels'])
    except (OSError, ValueError, KeyError, TypeError):
        return state, []


def place(state: str, root: Path) -> Path:
    """Copy one stored conversation-guided state into `root` (missing or empty) and register
    it on this computer, as the helper's every command did. Nothing else is written: the
    files are the stored bytes. Answers `root`."""
    import home
    root = Path(root)
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f'{root} is not empty.')
    shutil.copytree(CONVERSATION / state, root, dirs_exist_ok=True)
    title, levels = conversation_title(state)
    home.remember(root, title, levels)
    return root


def conversation(case, state: str) -> Path:
    """One stored conversation-guided state in a folder of its own beside `case`'s workspace,
    outside it, as a conversation keeps one. Answers the training's folder."""
    try:
        ident = json.loads((CONVERSATION / state / SESSION).read_bytes())['id']
    except (OSError, ValueError, KeyError, TypeError):
        ident = state
    return place(state, case.base / 'conversation' / ident)
