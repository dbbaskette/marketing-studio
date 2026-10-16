"""Open your studios, finish setup, or check this computer."""
import argparse
import fcntl
import json
from pathlib import Path
import signal
import subprocess
import sys
from contextlib import contextmanager

from . import catalog, computer, control, server, shared, state
from .errors import WorkspaceError
from .launcher import Launcher
from .page import Home

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def singleton():
    target = state.data_root() / 'home.lock'
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('a') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise WorkspaceError('Marketing Studio is starting or already running. Try the open command again shortly.') from exc
        yield


def parser():
    top = argparse.ArgumentParser(prog='marketing-studio', description=__doc__)
    top.add_argument('--version', action='version', version='Marketing Studio ' + (ROOT / 'VERSION').read_text().strip())
    top.set_defaults(studio=None, port=0, no_open=False, json=False, source=None,
                     studios=None, target='both', companions='ask', yes=False)
    commands = top.add_subparsers(dest='command', metavar='command')
    opening = commands.add_parser('open', help='Open the home page or one studio.')
    opening.add_argument('studio', nargs='?', choices=tuple(catalog.STUDIOS))
    setup = commands.add_parser('setup', help='Open shared settings or finish first-run setup.')
    serving = commands.add_parser('serve', help='Run the local home server in this terminal.')
    for command in (opening, setup, serving):
        command.add_argument('--port', type=server.port, default=0)
        command.add_argument('--no-open', action='store_true', help='Keep the browser closed.')
        command.add_argument('--json', action='store_true')
    status = commands.add_parser('status', help='See installed studios and setup status.')
    doctor = commands.add_parser('doctor', aliases=['check'], help='Check installed tools without contacting providers.')
    for command in (status, doctor):
        command.add_argument('--json', action='store_true')
    for action, help_text in (('install', 'Install from this checkout or an unpacked release.'),
                              ('update', 'Install a newer downloaded release.'),
                              ('rollback', 'Restore the prior installation pointers.'),
                              ('uninstall', 'Remove the umbrella launcher; keep independent studios.')):
        command = commands.add_parser(action, help=help_text)
        command.add_argument('--yes', action='store_true', help='Run without a confirmation prompt.')
        if action in ('install', 'update'):
            command.add_argument('--from', dest='source', type=Path, help='Folder containing the release installer.')
            command.add_argument('--studios', nargs='+', choices=tuple(catalog.STUDIOS))
            command.add_argument('--target', choices=('codex', 'claude', 'both'), default='both')
            command.add_argument('--companions', choices=('ask', 'install', 'skip'), default='ask')
    return top


def offline(args):
    if args.command in ('doctor', 'check'):
        report = computer.check()
        if args.json or args.command == 'check':
            print(json.dumps(report, indent=2))
        else:
            print('Marketing Studio · This computer\n')
            for item in report['items']:
                mark = '✓' if item['ready'] else '○' if item['optional'] else '!'
                print(f"{mark} {item['name']}: {item['detail']}")
            print('\nOpen setup: marketing-studio setup')
        return 0 if report['ready'] else 1
    preferences = state.read()
    studios = catalog.describe(preferences.get('paths', {}), lambda _: False)
    result = {'setup_complete': preferences.get('done', False), 'studios': studios}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print('Marketing Studio · ' + ('Ready' if result['setup_complete'] else 'Setup needed'))
        for studio in studios:
            print(f"  {studio['name']}: {'installed' if studio['installed'] else 'not installed'}")
        print('\nOpen a studio: marketing-studio open blog')
    return 0


def main(argv=None):
    top = parser()
    arguments = list(sys.argv[1:] if argv is None else argv)
    arguments = [value for value in arguments if value != '--open']
    if not arguments or arguments[0] in ('--no-open', '--port', '--json'):
        arguments.insert(0, 'open')
    args = top.parse_args(arguments)
    if args.studio and args.command != 'open':
        top.error('A studio name follows open, for example: marketing-studio open presentation.')
    if args.command in ('install', 'update', 'rollback', 'uninstall'):
        if args.command == 'update' and args.source is None:
            top.error('Download and unpack the new release, then use: marketing-studio update --from /path/to/release --yes')
        source = args.source.expanduser().resolve() if args.source else ROOT
        script = source / 'installer/install.py'
        if not script.is_file():
            top.error('That folder does not contain a Marketing Studio installer.')
        command = [sys.executable, str(script), 'install' if args.command == 'update' else args.command,
                   '--target', args.target, '--companions', args.companions]
        if args.studios:
            command += ['--studios', *args.studios]
        if args.yes:
            command += ['--yes']
        return subprocess.call(command)
    try:
        if args.command in ('doctor', 'check', 'status'):
            return offline(args)
        action = {'command': 'setup' if args.command == 'setup' else 'open', 'studio': args.studio}
        if not args.no_open:
            result = control.request(state.data_root(), action)
            if result is not None:
                if result.get('error'):
                    raise WorkspaceError(result['error'])
                print('Opened ' + (args.studio.title() + ' Studio' if args.studio else 'Marketing Studio') + '.')
                return 0
        with singleton():
            launcher = Launcher()
            desk = server.Desk(args.port, page=lambda port: Home(port, launcher))
            ipc = None
            def open_action(wanted):
                if wanted['command'] == 'setup':
                    url = desk.url + '&view=settings'
                elif wanted.get('studio') and state.read().get('done'):
                    values, problem = shared.read()
                    if problem:
                        raise WorkspaceError(problem)
                    url = launcher.open(wanted['studio'], state.read(), values)
                else:
                    url = desk.url
                if not server.show(url):
                    raise WorkspaceError('A browser could not be opened. Use the private link in your terminal.')
            signal.signal(signal.SIGTERM, server.interrupt)
            signal.signal(signal.SIGINT, server.interrupt)
            try:
                ipc = control.Control(state.data_root(), open_action)
                shown = server.announce(desk, sys.stdout.isatty(),
                    (lambda _: False) if args.no_open else (lambda _: (open_action(action) or True)))
                if args.json or not sys.stdout.isatty():
                    print(json.dumps(shown), flush=True)
                else:
                    print('Marketing Studio is ready.\n' + desk.url + '\n\nLeave this terminal open while you work. Press Ctrl-C to stop.', flush=True)
                    if not args.no_open:
                        open_action(action)
                desk.serve()
            except KeyboardInterrupt:
                pass
            finally:
                if ipc:
                    ipc.close()
                desk.stop()
                launcher.close()
        return 0
    except (WorkspaceError, OSError, ValueError) as failure:
        print('Marketing Studio: ' + str(failure), file=sys.stderr)
        return 2
