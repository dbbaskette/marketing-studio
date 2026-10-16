"""Marketing Studio: configure once, then open an independent studio."""
import argparse
import fcntl
import json
import signal
import sys
from contextlib import contextmanager

from . import computer, server, state
from .errors import WorkspaceError
from .launcher import Launcher
from .page import Home


@contextmanager
def singleton():
    target = state.data_root() / 'home.lock'
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('a') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise WorkspaceError('Marketing Studio is already running. Use its open page or stop its terminal first.') from exc
        yield


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('serve', 'check'), nargs='?', default='serve')
    parser.add_argument('--port', type=server.port, default=0)
    parser.add_argument('--open', action='store_true', help='Open the home page in your browser.')
    parser.add_argument('--no-open', action='store_true', help='Serve without opening a browser.')
    args = parser.parse_args(argv)
    if sys.version_info < (3, 11):
        parser.error('Marketing Studio requires Python 3.11 or newer.')
    if args.command == 'check':
        print(json.dumps(computer.check(), indent=2))
        return 0
    try:
        with singleton():
            launcher = Launcher()
            desk = server.Desk(args.port, page=lambda port: Home(port, launcher))
            signal.signal(signal.SIGTERM, server.interrupt)
            signal.signal(signal.SIGINT, server.interrupt)
            try:
                shown = server.announce(desk, sys.stdout.isatty(),
                                        (lambda _: False) if args.no_open else server.show)
                print(json.dumps(shown), flush=True)
                if sys.stdout.isatty() and args.open and not args.no_open:
                    server.show(desk.url)
                desk.serve()
            except KeyboardInterrupt:
                pass
            finally:
                desk.stop()
                launcher.close()
        return 0
    except (WorkspaceError, OSError) as failure:
        print(json.dumps({'error': str(failure)}), file=sys.stderr)
        return 2
