"""A PATH whose python3 is the interpreter running these tests.

Entry points such as package.sh, sync.sh and the studio installers look for `python3` on
PATH. The folder of `sys.executable` need not hold one (uv's interpreters are named
python3.11 and so on, and a `python` shim has no `python3` beside it), and then macOS's own
older python3 in /usr/bin would be found instead. Tests that run those entry points put this
folder first, so they test the entry points with the Python the suite runs under.
"""
from pathlib import Path
import shlex
import sys


def python_path(root, *rest):
    """A PATH with a python3 for sys.executable first, made in `root`, then `rest`."""
    folder = Path(root) / 'test python'
    folder.mkdir(exist_ok=True)
    shim = folder / 'python3'
    shim.write_text('#!/bin/sh\nexec ' + shlex.quote(sys.executable) + ' "$@"\n')
    shim.chmod(0o755)
    return ':'.join([str(folder), *rest])
