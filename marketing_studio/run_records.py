"""Each running studio's record in the data root's run/ folder: its process, never its
link, so a later Marketing Studio can find a studio left behind by one that stopped
abruptly. marketing_studio.launcher re-exports every name here."""

import hashlib
import json
import os
import secrets

from . import state
from .bridge_protocol import HOME_DATA, marker


def _launcher():
    """marketing_studio.launcher, read when called. Callers and tests replace names on it
    (ps, started, command_of, stop_group, group_alive, WAIT), and a call made here reaches
    what they put there."""
    from . import launcher
    return launcher


def home_key():
    """Names this data root on each studio bridge's command line, so a bridge started
    for another data root can never be taken for one of these."""
    return hashlib.sha256(str(state.data_root().expanduser().resolve()).encode()).hexdigest()[:16]


def records():
    return state.data_root() / 'run'


def record(identifier, pid):
    """Note a running studio's process (never its link) for a later cleanup."""
    folder = records()
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = folder / (identifier + '.json')
    pending = folder / ('.' + identifier + '-' + secrets.token_hex(6))
    try:
        with pending.open('x') as stream:
            os.chmod(pending, 0o600)
            json.dump({'pid': pid, 'started': _launcher().started(pid),
                       'command': marker(identifier) + f'… {HOME_DATA} ' + home_key()}, stream)
        os.replace(pending, target)
    finally:
        pending.unlink(missing_ok=True)


def forget(identifier):
    (records() / (identifier + '.json')).unlink(missing_ok=True)
