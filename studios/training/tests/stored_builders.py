"""Stored trees for the test builders that made conversation-guided trainings by driving the
helper `training.py` (GitHub issue #547).

`helpers.saved_init`, the `test_cli.Flow` builders (`research`, `content`, `deck`, `scenario`,
`complete`, `make`) and the builders built on them in other test modules once reached each
state by running the helper's commands (`save`, `approve`, `skip`, `checkpoint`, `export`, ...).
Those commands continue a conversation-guided training, which nothing does any more. A
builder marked `@builder` now places the tree it made, stored byte for byte under
`fixtures/saved/flow/` (a training's files, by the steps that made it), so a test of what
still reads such a training (lists, checks, the hub, the index, Google, copies) runs on a
stored tree and needs none of those commands.

A test that changes its training itself (writing a file, making a Google Doc) and then calls
a builder, or runs one of those helper commands itself (`test_cli.Flow.cli`), reaches the
state that step made from what the training held then, stored the same way and keyed by
that (`replay`), with the command's exit code and answer as the helper gave them.

The trees were recorded while the helper's continuing commands existed, by running the
suites that use these builders. Those commands are gone, so the trees are the only record of
what they wrote and cannot be recorded again: they are history, never rewritten. A builder
whose steps have no stored tree fails, naming them; such a test reaches its state another way
(a stored tree that exists, or desk work), never by recording one.
"""
from __future__ import annotations

import functools
import hashlib
import json
import re
from pathlib import Path

STORE = Path(__file__).resolve().parent / 'fixtures' / 'saved' / 'flow'
TREES = STORE / 'trees.json'
BLOBS = STORE / 'blobs'
# The helper's commands that continue a training: none of them reaches a stored tree.
CONTINUING = ('save', 'approve', 'skip', 'checkpoint', 'pin', 'export', 'research-import')
STAMP = re.compile(rb'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)?')

_state: dict[str, dict] = {}     # a training's folder -> {'steps', 'tree'}; steps None once off
_trees: dict | None = None


def files(root: Path) -> dict[str, bytes]:
    """A training's files, without any repository a test made in its folder."""
    found = {}
    if not root.is_dir():
        return found
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if '.git' in relative.parts or path.is_symlink() or not path.is_file():
            continue
        found[relative.as_posix()] = path.read_bytes()
    return found


def digest(tree: dict[str, bytes]) -> str:
    whole = hashlib.sha256()
    for name, data in sorted(tree.items()):
        whole.update(name.encode() + b'\0' + hashlib.sha256(data).digest())
    return whole.hexdigest()


def plain(value):
    """An argument as the steps record it: long text by its digest."""
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    if isinstance(value, dict):
        return {str(key): plain(item) for key, item in sorted(value.items())}
    if isinstance(value, str) and len(value) > 60:
        return 'sha256:' + hashlib.sha256(value.encode()).hexdigest()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f'A stored builder takes text, numbers and lists, not {value!r}.')


def key(steps: list) -> str:
    return hashlib.sha256(json.dumps(steps, sort_keys=True).encode()).hexdigest()[:24]


def trees() -> dict:
    global _trees
    if _trees is None:
        _trees = json.loads(TREES.read_text(encoding='utf-8')) if TREES.is_file() else {}
    return _trees


def _normal(tree: dict[str, bytes]) -> dict[str, bytes]:
    return {name: STAMP.sub(b'@', data) for name, data in tree.items()}


# Why a step has no stored tree, said where a test asks for one (GitHub issue #547).
CANNOT_RECORD = ('The helper commands that made the stored trees are gone, so no new tree can be '
                 'recorded: reach this state from a stored tree that exists, or with desk work.')


def _place(root: Path, before: dict[str, bytes], tree: dict[str, bytes]) -> None:
    for name in before:
        if name not in tree:
            (root / name).unlink()
    for name, data in tree.items():
        target = root / name
        if before.get(name) != data:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)


def _remember(root: Path) -> None:
    """A training placed where none was is remembered on this computer, as the helper's
    start remembered every training it started."""
    import home
    import workspace
    try:
        session = workspace.load(root)
    except workspace.WorkspaceError:
        return
    home.remember(root, session['title'], session['levels'])


def _locked(root: Path) -> None:
    """The write lock file the helper's commands leave beside a training they changed (in
    its repository, or in the data folder), as they left it: empty, and only made."""
    import home
    from studio_core.process_lock import workspace_lock_path
    repo = next((folder for folder in (root, *root.parents) if (folder / '.git').exists()),
                None)
    path = workspace_lock_path(repo, home.data_root())
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()


def step(root, name: str, arguments) -> None:
    """Reach on `root` the state the builder `name` makes with `arguments`: its stored tree,
    placed, where the training is as the stored steps before it left it."""
    root = Path(root)
    now = files(root)
    state = _state.get(str(root))
    if state is None:
        steps = [] if not now else None
    else:
        steps = state['steps'] if state['steps'] is not None and digest(now) == state['tree'] \
            else None
    if steps is None:
        # The test changed the training itself: the state this builder reaches from what the
        # training holds now is stored by that, as a helper command's is (`replay`).
        _state[str(root)] = {'steps': None, 'tree': None}
        replay(root, name, arguments)
        return
    steps = [*steps, [name, plain(arguments)]]
    stored = trees().get(key(steps))
    if stored is None:
        raise AssertionError(f'No stored tree for these builder steps: {steps}. '
                             + CANNOT_RECORD)
    tree = {path: (BLOBS / sha).read_bytes() for path, sha in stored['files'].items()}
    _place(root, now, tree)
    _state[str(root)] = {'steps': steps, 'tree': digest(tree)}
    if len(steps) == 1:
        _remember(root)
    if any(name != 'saved_init' for name, _ in steps):
        _locked(root)


def normal(tree: dict[str, bytes]) -> str:
    """A tree's digest with every time it records left out, so the same state reached at
    another time has the same digest."""
    return digest(_normal(tree))


def replay(root, name: str, arguments):
    """Reach on `root`, from whatever it holds now, the state `name` with `arguments` made
    from it when it was recorded: a helper command a test runs itself (`command`), or a
    builder after the test changed the training. Keyed by what the training held (times left
    out) and the step. Answers the stored output."""
    root = Path(root)
    now = files(root)
    step_ = [name, plain(arguments)]
    name_ = 't-' + hashlib.sha256(json.dumps([normal(now), step_], sort_keys=True)
                                  .encode()).hexdigest()[:24]
    stored = trees().get(name_)
    if stored is None:
        raise AssertionError(f'No stored state for {step_} from what this training holds. '
                             + CANNOT_RECORD)
    tree = {path: (BLOBS / sha).read_bytes() for path, sha in stored['files'].items()}
    _place(root, now, tree)
    _locked(root)
    return stored.get('output')


def command(root, arguments: list) -> tuple:
    """A helper command that continued a training, run by a test to reach a state: the state
    it made, stored (`replay`), and its exit code and output as the helper gave them."""
    root = Path(root)
    places = ((str(root), '@TRAINING@'), (str(root.parent), '@BESIDE@'))
    code, kept = replay(root, 'training.py', [
        _marked(argument, places) for argument in arguments])
    for place, mark in places:
        kept = kept.replace(mark, place)
    return code, kept


def _marked(argument, places):
    for place, mark in places:
        argument = str(argument).replace(place, mark)
    return argument


def builder(method):
    """A test method that reaches a state by driving the helper: placed from its stored tree
    where it can be (see `step`). It answers nothing."""
    @functools.wraps(method)
    def placed(self, *args, **kwargs):
        step(self.root, method.__qualname__, [list(args), kwargs])
    return placed
