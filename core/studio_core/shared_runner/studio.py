"""The parts of the runner's command line, `studio`, both deck studios share. A studio binds
them into its own module with `studio_core.modules.bind`; they read that module's names.

RESTART stays in each studio: it is a value with the product's name in it. `serve`, the
conversation commands and the parser stay too, as their steps differ.
"""
from __future__ import annotations

# ruff: noqa: F821  these definitions read the names of the studio module they are
# bound into; each studio's test_shared_runner_use checks every one resolves there.

import contextlib
import json
import os
import re
import sys

from runner import engine as engines

KEY = re.compile(r'[A-Za-z0-9_-]{32,128}')


def only_runner():
    """Be the one runner serving on this computer, or refuse. A runner that ended without
    saying so is not counted."""
    return contextlib.contextmanager(_one_runner)()


def _one_runner():
    """What `only_runner` holds while the runner serves: the file naming its process."""
    path = home.data_root() / 'runner.pid'
    path.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        try:
            handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            kept = path.read_text(encoding='utf-8').strip() if path.is_file() else ''
            if kept.isdigit() and int(kept) != os.getpid() and home.alive(int(kept)):
                raise WorkspaceError(
                    f'A runner is already serving on this computer (process {kept}). Use '
                    'its page, or stop it before starting another. If none is running, '
                    f'remove {path} and try again.')
            path.unlink(missing_ok=True)
            continue
        os.write(handle, f'{os.getpid()}\n'.encode())
        os.close(handle)
        break
    else:
        raise WorkspaceError(f'Could not write {path}, which says a runner is serving.')
    try:
        yield
    finally:
        path.unlink(missing_ok=True)


def handed_over() -> str | None:
    """The key a runner that stopped to open a newer version handed to this one, taken out
    of the environment at once so nothing this runner starts is given it."""
    kept = os.environ.pop(RESTART, None)
    try:
        token = json.loads(kept)['token'] if kept else None
    except (ValueError, KeyError, TypeError):
        return None
    return token if isinstance(token, str) and KEY.fullmatch(token) else None


def status(args, make=engines.Engine, out=None, keeper=None) -> int:
    """What is set up on this computer and where all the work is. Starts nothing, changes
    nothing, and asks nothing online: the skills are looked at as they are."""
    engine = make()
    engine.upkeep = (keeper or upkeeping.Upkeep)()
    engine.upkeep.check(repair=False)
    report = {'version': gitstate.installed(), **setup.describe(engine), **engine.status()}
    print(json.dumps(report, indent=2, sort_keys=True), file=out or sys.stdout)
    return 0


def saved_work(args, make=engines.Engine, out=None) -> int:
    """Which saved work still needs each older path. Starts nothing, changes nothing, and
    asks nothing online. Covers only declared local roots, without the runner's upkeep."""
    report = make().saved_work(tuple(args.folder or ()))
    print(json.dumps(report, indent=2, sort_keys=True), file=out or sys.stdout)
    return 0


NAMES = ('KEY', 'only_runner', '_one_runner', 'handed_over', 'status', 'saved_work')
METHODS = {}
