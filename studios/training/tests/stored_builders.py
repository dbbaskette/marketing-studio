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

The trees were recorded by running the suites that use these builders with
`TRAINING_STUDIO_RECORD_BUILDERS=1` while the helper's commands existed. A builder whose steps
have no stored tree fails, naming them.
"""
from __future__ import annotations

import functools
import hashlib
import inspect
import json
import os
import re
import unittest
from pathlib import Path

STORE = Path(__file__).resolve().parent / 'fixtures' / 'saved' / 'flow'
TREES = STORE / 'trees.json'
BLOBS = STORE / 'blobs'
RECORD = 'TRAINING_STUDIO_RECORD_BUILDERS'
TRACE = 'TRAINING_STUDIO_HELPER_TRACE'
# The helper's commands that continue a training: none of them reaches a stored tree.
CONTINUING = ('save', 'approve', 'skip', 'checkpoint', 'pin', 'export', 'research-import')
STAMP = re.compile(rb'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)?')

_state: dict[str, dict] = {}     # a training's folder -> {'steps', 'tree'}; steps None once off
_depth = 0                       # inside a builder, the builders it calls run as they are
_trees: dict | None = None


def recording() -> bool:
    return os.environ.get(RECORD) == '1'


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


def _test_id() -> str:
    for frame in inspect.stack():
        found = frame.frame.f_locals.get('self')
        if isinstance(found, unittest.TestCase):
            return found.id()
    return 'an unknown test'


def trace(what: str) -> None:
    """Note that a test drove a helper command that continues a training."""
    target = os.environ.get(TRACE)
    if target and _depth == 0:
        with open(target, 'a', encoding='utf-8') as log:
            log.write(json.dumps({'test': _test_id(), 'did': what}) + '\n')


def _normal(tree: dict[str, bytes]) -> dict[str, bytes]:
    return {name: STAMP.sub(b'@', data) for name, data in tree.items()}


def _store(steps: list, tree: dict[str, bytes]) -> None:
    for data in tree.values():
        for mark in (b'/Users/', b'/home/', b'/var/folders/', b'/private/', b'/tmp/'):
            if mark in data:
                raise AssertionError(f'A recorded tree names a place on this computer: {steps}')
    found = trees()
    name = key(steps)
    if name in found:
        stored = {path: (BLOBS / sha).read_bytes() for path, sha in found[name]['files'].items()}
        if _normal(stored) != _normal(tree):
            raise AssertionError(f'The same steps made a different tree: {steps}')
        return
    BLOBS.mkdir(parents=True, exist_ok=True)
    entry = {}
    for path, data in tree.items():
        sha = hashlib.sha256(data).hexdigest()
        if not (BLOBS / sha).is_file():
            (BLOBS / sha).write_bytes(data)
        entry[path] = sha
    found[name] = {'steps': steps, 'files': entry}
    # Read again and merged, so separate recording runs add to one another.
    merged = json.loads(TREES.read_text(encoding='utf-8')) if TREES.is_file() else {}
    merged.update(found)
    TREES.write_text(json.dumps(merged, indent=1, sort_keys=True) + '\n', encoding='utf-8')


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


def step(root, name: str, arguments, run):
    """Reach on `root` the state the builder `name` makes with `arguments`: its stored tree,
    placed, where the training is as the stored steps before it left it; else `run()`, which
    drives the helper. Answers what `run()` answers, or None where the tree was placed."""
    global _depth
    root = Path(root)
    if _depth:
        return run()
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
        return replay(root, name, arguments, lambda: (run(), None))[0]
    steps = [*steps, [name, plain(arguments)]]
    stored = trees().get(key(steps))
    if stored is not None and not recording():
        tree = {path: (BLOBS / sha).read_bytes() for path, sha in stored['files'].items()}
        _place(root, now, tree)
        _state[str(root)] = {'steps': steps, 'tree': digest(tree)}
        if len(steps) == 1:
            _remember(root)
        if any(name != 'saved_init' for name, _ in steps):
            _locked(root)
        return None
    if not recording():
        raise AssertionError(f'No stored tree for these builder steps: {steps}. Record them '
                             f'with {RECORD}=1 (see stored_builders.py).')
    _depth += 1
    try:
        answer = run()
    finally:
        _depth -= 1
    after = files(root)
    _store(steps, after)
    _state[str(root)] = {'steps': steps, 'tree': digest(after)}
    return answer


def normal(tree: dict[str, bytes]) -> str:
    """A tree's digest with every time it records left out, so the same state reached at
    another time has the same digest."""
    return digest(_normal(tree))


def replay(root, name: str, arguments, run):
    """Reach on `root`, from whatever it holds now, the state `name` with `arguments` made
    from it when it was recorded: a helper command a test runs itself (`command`), or a
    builder after the test changed the training. Keyed by what the training held (times left
    out) and the step. Answers `run()`'s (answer, output); a placed state answers the stored
    output and None."""
    global _depth
    root = Path(root)
    now = files(root)
    step_ = [name, plain(arguments)]
    name_ = 't-' + hashlib.sha256(json.dumps([normal(now), step_], sort_keys=True)
                                  .encode()).hexdigest()[:24]
    stored = trees().get(name_)
    if stored is not None and not recording():
        tree = {path: (BLOBS / sha).read_bytes() for path, sha in stored['files'].items()}
        _place(root, now, tree)
        _locked(root)
        return None, stored.get('output')
    if not recording():
        raise AssertionError(f'No stored state for {step_} from what this training holds. '
                             f'Record it with {RECORD}=1 (see stored_builders.py).')
    _depth += 1
    try:
        answer, output = run()
    finally:
        _depth -= 1
    _store_state(name_, step_, files(root), output)
    return answer, output


def _store_state(name: str, step_: list, tree: dict[str, bytes], output) -> None:
    for data in tree.values():
        for mark in (b'/Users/', b'/home/', b'/var/folders/', b'/private/', b'/tmp/'):
            if mark in data:
                raise AssertionError(f'A recorded state names a place on this computer: {step_}')
    if output is not None and any(mark in json.dumps(output).encode() for mark in
                                  (b'/Users/', b'/home/', b'/var/folders/', b'/private/', b'/tmp/')):
        raise AssertionError(f'A recorded answer names a place on this computer: {step_}')
    found = trees()
    if name in found:
        stored = {path: (BLOBS / sha).read_bytes() for path, sha in found[name]['files'].items()}
        if _normal(stored) != _normal(tree):
            raise AssertionError(f'The same step from the same state made a different tree: '
                                 f'{step_}')
        return
    BLOBS.mkdir(parents=True, exist_ok=True)
    entry = {}
    for path, data in tree.items():
        sha = hashlib.sha256(data).hexdigest()
        if not (BLOBS / sha).is_file():
            (BLOBS / sha).write_bytes(data)
        entry[path] = sha
    found[name] = {'step': step_, 'files': entry, 'output': output}
    merged = json.loads(TREES.read_text(encoding='utf-8')) if TREES.is_file() else {}
    merged.update(found)
    TREES.write_text(json.dumps(merged, indent=1, sort_keys=True) + '\n', encoding='utf-8')


def command(root, arguments: list, run):
    """A helper command that continues a training, run by a test to reach a state: the state
    it made, stored (`replay`), and its exit code and output as the helper gave them. `run()`
    answers (code, output) and runs only while recording."""
    if _depth:
        return run()
    root = Path(root)
    places = ((str(root), '@TRAINING@'), (str(root.parent), '@BESIDE@'))

    def recorded():
        code, output = run()
        kept = output
        for place, mark in places:
            kept = kept.replace(place, mark)
        return (code, output), [code, kept]
    answer, output = replay(root, 'training.py', [
        _marked(argument, places) for argument in arguments], recorded)
    if answer is not None:
        return answer
    code, kept = output
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
        step(self.root, method.__qualname__, [list(args), kwargs],
             lambda: method(self, *args, **kwargs))
    return placed
