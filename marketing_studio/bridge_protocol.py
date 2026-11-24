"""What Marketing Studio's launcher and the studio bridge it starts agree on: the bridge's
command line, the handoff it is given, and the one-line JSON reports it prints.

The bridge (marketing_studio/bridge.py) runs by file path in a child interpreter, so this
module imports only the standard library.
"""
import json
import os
import signal
import sys
from pathlib import Path

# The bridge's file, from the folder that holds marketing_studio. It stays a script at this
# path: the launcher starts it by this path and knows its processes by it (marker).
BRIDGE = 'marketing_studio/bridge.py'
# Set a missing workspace up; join the storage the shared settings name; and the data root
# that started the bridge, read only from outside.
PREPARE, CONNECT, HOME_DATA = '--prepare', '--connect', '--home-data'
# The environment variable that hands the bridge its token and the shared settings. The
# bridge takes it out of its environment as it reads it.
HANDOFF = 'MARKETING_STUDIO_HANDOFF'


def command(home, identifier, root, *flags):
    """The bridge's command line for one studio. `home` is the folder that holds
    marketing_studio."""
    return [sys.executable, str(Path(home) / BRIDGE), identifier, str(root), *flags]


def marker(identifier):
    """How a bridge started for `identifier` shows on its command line."""
    return f'{BRIDGE} {identifier} '


def handoff(token, shared):
    """The handoff's value: the studio's token and the shared settings."""
    return json.dumps({'token': token, 'shared': shared})


def received():
    """The handoff the launcher gave this bridge, taken out of its environment."""
    return json.loads(os.environ.pop(HANDOFF))


def report(value):
    """One report for the launcher, which reads each line as it comes."""
    print(json.dumps(value), flush=True)


def interrupt_on_terminate():
    """End serving on SIGTERM as on an interrupt, so the studio's own cleanup runs."""
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
