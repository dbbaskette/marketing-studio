"""Open your studios, finish setup, or check this computer."""
import argparse
import fcntl
import json
from pathlib import Path
import signal
import subprocess
import sys
from contextlib import contextmanager

from . import catalog, computer, control, network, server, session, shared, state
from .errors import WorkspaceError
from .launcher import Launcher, describe_job
from .page import Home

ROOT = Path(__file__).resolve().parents[1]
CHOICES = ((('--bs', '-bs', '--blog'), 'blog'), (('--ps', '-ps', '--presentation'), 'presentation'),
           (('--ts', '-ts', '--training'), 'training'))
LEADING = frozenset(('-a', '--all', '--force', '--json', *(spelling for flags, _ in CHOICES for spelling in flags)))
MANAGING = ('start', 'stop', 'restart')
EXAMPLES = {
    'start': """examples:
  marketing-studio start                  Marketing Studio only
  marketing-studio start --ts             also Training Studio
  marketing-studio start --all --lan      everything, with phone access

Marketing Studio keeps running in the background. Stop it with: marketing-studio stop --all""",
    'stop': """examples:
  marketing-studio stop --bs              Blog Studio only
  marketing-studio stop --all             every studio, then Marketing Studio

A studio with a running assistant job is not stopped, because its work so far
would be lost. Wait for the job, or add --force.""",
    'restart': """examples:
  marketing-studio restart --ts           Training Studio
  marketing-studio restart --all          Marketing Studio with its phone access
                                          and port, then the studios that were running

A studio with a running assistant job is not restarted unless you add --force.""",
}


@contextmanager
def singleton(network_requested=False):
    target = state.data_root() / 'home.lock'
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('a') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            message = ('Marketing Studio is already running. Stop its terminal with Ctrl-C, then run marketing-studio serve --lan.'
                       if network_requested else
                       'Marketing Studio is starting or already running. Try the open command again shortly.')
            raise WorkspaceError(message) from exc
        yield


def parser():
    top = argparse.ArgumentParser(prog='marketing-studio', description=__doc__)
    top.add_argument('--version', action='version', version='Marketing Studio ' + (ROOT / 'VERSION').read_text().strip())
    top.set_defaults(studio=None, port=0, no_open=False, json=False, source=None, lan=None,
                     studios=None, target='auto', companions='ask', yes=False,
                     selected=None, everything=False, force=False)
    commands = top.add_subparsers(dest='command', metavar='command')
    top.commands = {}
    opening = commands.add_parser('open', help='Open the home page or one studio.')
    opening.add_argument('studio', nargs='?', choices=tuple(catalog.STUDIOS))
    setup = commands.add_parser('setup', help='Open shared settings or finish first-run setup.')
    serving = commands.add_parser('serve', help='Run the local home server in this terminal without opening a browser.')
    for command in (opening, setup, serving):
        command.add_argument('--port', type=server.port, default=0)
        command.add_argument('--lan', nargs='?', const='auto', metavar='ADDRESS',
                             help='Allow access on your trusted local network; optionally choose a private IPv4 address.')
        command.add_argument('--no-open', action='store_true', help='Keep the browser closed.')
        command.add_argument('--json', action='store_true')
    for action, help_text in (('start', 'Start Marketing Studio in the background, and the studios you choose.'),
                              ('stop', 'Stop the studios you choose, or everything with --all.'),
                              ('restart', 'Restart the studios you choose, or everything with --all.')):
        command = commands.add_parser(action, help=help_text, description=help_text, epilog=EXAMPLES[action],
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
        top.commands[action] = command
        command.add_argument('-a', '--all', dest='everything', action='store_true', help={
            'start': 'Every installed studio.', 'stop': 'Every studio, then Marketing Studio itself.',
            'restart': 'Marketing Studio itself, then the studios that were running.'}[action])
        for flags, identifier in CHOICES:
            command.add_argument(*flags, dest='selected', action='append_const', const=identifier,
                                 help=catalog.STUDIOS[identifier][0] + '.')
        if action != 'stop':
            command.add_argument('--lan', nargs='?', const='auto', metavar='ADDRESS',
                                 help='Allow access on your trusted local network; optionally choose a private IPv4 address.'
                                 + (' With --all, instead of the running one.' if action == 'restart' else ''))
            command.add_argument('--port', type=server.port, default=0,
                                 help='The Marketing Studio port.' + (' With --all, instead of the running one.'
                                                                      if action == 'restart' else ''))
        if action != 'start':
            command.add_argument('--force', action='store_true',
                                 help='Stop even a studio with a running assistant job; its work so far is lost.')
        command.add_argument('--json', action='store_true', help='Print JSON, without any private link.')
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
            command.add_argument('--target', choices=('auto', 'codex', 'claude', 'both'), default='auto')
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
    found = session.quietly_current()
    running = {row['id'] for row in found['studios']} if found else set()
    studios = catalog.describe(preferences.get('paths', {}), running.__contains__)
    result = {'version': (ROOT / 'VERSION').read_text().strip(), 'path': str(ROOT),
              'checkout': catalog.checkout(ROOT),
              'setup_complete': Home.configured(shared.read()[0]), 'studios': studios,
              'running': None if found is None else {
                  'port': found['port'], 'lan': found['lan'], 'studios': found['studios']}}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Marketing Studio {result['version']} · " + ('Ready' if result['setup_complete'] else 'Setup needed'))
        if result['checkout']:
            print('Running from the Git checkout at ' + result['path'])
        for studio in studios:
            if not studio['installed']:
                print(f"  {studio['name']}: not installed")
                continue
            label = ' '.join(filter(None, (studio['name'], studio['version'])))
            print(f"  {label}: {studio['path']}" + (' (Git checkout)' if studio['checkout'] else ''))
        copies = [studio['name'] for studio in studios if studio['checkout']]
        if copies:
            print('\nRunning Git checkout copies, not installed releases: ' + ', '.join(copies) + '.'
                  '\nTo run installed releases, use the installed marketing-studio command or set each folder in Settings.')
        if found:
            print('\nRunning now:')
            print(f"  Marketing Studio on port {found['port']}, phone access "
                  + (f"on ({found['lan']})" if found['lan'] else 'off'))
            for row in found['studios']:
                print('  ' + row['name'] + (', left running by an earlier session' if row['earlier'] else '')
                      + (': working on ' + ', '.join(map(describe_job, row['jobs'])) if row['jobs'] else ''))
        print('\nOpen a studio: marketing-studio open blog')
    return 0


def arrange(arguments):
    """Accept `marketing-studio --all stop` as well as `marketing-studio stop --all`."""
    arguments = [value for value in arguments if value != '--open']
    index = 0
    while index < len(arguments) and arguments[index] in LEADING:
        index += 1
    if 0 < index < len(arguments) and arguments[index] in MANAGING:
        arguments.insert(0, arguments.pop(index))
    if not arguments or arguments[0] in ('--no-open', '--port', '--json', '--lan') or arguments[0].startswith(('--port=', '--lan=')):
        arguments.insert(0, 'open')
    return arguments


class Report:
    """A person's terminal reads sentences; a pipe or --json gets JSON without any key."""
    def __init__(self, args):
        self.person = sys.stdout.isatty() and not args.json
        self.lines = []
        self.data = {}

    def say(self, line):
        self.lines.append(line)

    def show(self, code=0, problem=None):
        if self.person:
            if self.lines:
                print('\n'.join(self.lines), flush=True)
            if problem:
                print(problem, file=sys.stderr, flush=True)
        else:
            print(json.dumps({**self.data, **({'problem': problem} if problem else {})}, indent=2), flush=True)
        return code


def address_of(link):
    return link.split('#', 1)[0] if link else None


def running_home(report, found, started):
    report.data.update({'running': True, 'started': started, 'address': address_of(found['url']),
                        'network': {'address': address_of(found['phone'])} if found.get('phone') else None})
    report.say('Marketing Studio is running.\n' + found['url'])
    if found.get('phone'):
        report.say('Open on your phone (same trusted Wi-Fi):\n' + found['phone'] +
                   '\nKeep this link private. HTTP is unencrypted; it grants full studio access.')
    if started:
        report.say('It runs in the background. Stop it with: marketing-studio stop --all')


def start_studios(report, identifiers, restarted=()):
    rows, failed = [], False
    for identifier in identifiers:
        reply = session.ask({'command': 'start', 'studio': identifier})
        row = {'id': identifier, 'name': session.name(identifier)}
        if reply is None or reply.get('error'):
            failed = True
            row.update(result='failed', problem=(reply or {}).get('error') or 'Marketing Studio stopped.')
            report.say(f"{row['name']} could not start: {row['problem']}")
        elif reply.get('started'):
            row['result'] = 'restarted' if identifier in restarted else 'started'
            report.say(f"{row['name']} {row['result']}.")
        else:
            row['result'] = 'already running'
            report.say(f"{row['name']} was already running.")
        rows.append(row)
    report.data.setdefault('studios', []).extend(rows)
    return failed


def stopped_line(identifier, jobs, earlier=False):
    line = session.name(identifier) + (', left running by an earlier session,' if earlier else '') + ' stopped'
    if jobs:
        line += '; ' + ', '.join(map(describe_job, jobs)) + (' were' if len(jobs) > 1 else ' was') + ' cut off'
    return line + '.'


def refuse(report, busy):
    report.data.update({'refused': True, 'working': [
        {'id': identifier, 'name': session.name(identifier), 'jobs': jobs} for identifier, jobs in busy]})
    return report.show(1, session.working(busy))


def stop_left_behind(report, identifiers, force):
    """With no Marketing Studio running, stop studios it left behind. None when refused."""
    with session.left_behind() as launcher:
        left = [(identifier, launcher.jobs(identifier)) for identifier in identifiers if launcher.orphan(identifier)]
        busy = [(identifier, jobs) for identifier, jobs in left if jobs]
        if busy and not force:
            return busy
        rows = []
        for identifier, jobs in left:
            if launcher.stop(identifier):
                rows.append({'id': identifier, 'name': session.name(identifier), 'result': 'stopped',
                             'earlier': True, 'cut_off': jobs})
                report.say(stopped_line(identifier, jobs, earlier=True))
        report.data.setdefault('studios', []).extend(rows)
    return None


def stop_running(report, found, identifiers, force):
    """Stop studios through the running Marketing Studio. True when one could not stop."""
    running = {row['id']: row for row in found['studios']}
    failed = False
    for identifier in identifiers:
        row = {'id': identifier, 'name': session.name(identifier)}
        if identifier not in running:
            row['result'] = 'not running'
            report.say(f"{row['name']} was not running.")
        else:
            reply = session.ask({'command': 'stop', 'studio': identifier, 'force': force}) or {}
            if reply.get('error'):
                failed = True
                row.update(result='failed', problem=reply['error'])
                report.say(f"{row['name']} was not stopped: {reply['error']}")
            else:
                cut = reply.get('jobs') or []
                row.update(result='stopped', cut_off=cut, earlier=running[identifier]['earlier'])
                report.say(stopped_line(identifier, cut, running[identifier]['earlier']))
        report.data.setdefault('studios', []).append(row)
    return failed


def cut_off(report):
    """Keep only the stop lines that say which jobs were cut off, before starting again."""
    rows = report.data.pop('studios', [])
    report.lines = [line for line in report.lines if 'cut off' in line]
    return [{'id': row['id'], 'name': row['name'], 'jobs': row['cut_off']} for row in rows if row.get('cut_off')]


def busy_in(found, identifiers):
    return [(row['id'], row['jobs']) for row in found['studios'] if row['id'] in identifiers and row['jobs']]


def manage(args, chosen):
    report = Report(args)
    everything = list(catalog.STUDIOS)
    found = session.current()
    if args.command == 'start':
        started = found is None
        if started:
            found = session.start_home(session.serving(args.lan, args.port))
        else:
            problem = session.differs(found, args.lan, args.port)
            if problem:
                return report.show(1, problem)
        running_home(report, found, started)
        paths = state.read().get('paths', {})
        wanted = [identifier for identifier in everything if catalog.locate(identifier, paths)] \
            if args.everything else chosen
        return report.show(1 if start_studios(report, wanted) else 0)
    if args.command == 'stop':
        if found is None:
            busy = stop_left_behind(report, everything if args.everything else chosen, args.force)
            if busy:
                return refuse(report, busy)
            report.data['running'] = False
            stopped = {row['id'] for row in report.data.get('studios', [])}
            for identifier in chosen:
                if identifier not in stopped:
                    report.data.setdefault('studios', []).append(
                        {'id': identifier, 'name': session.name(identifier), 'result': 'not running'})
                    report.say(f'{session.name(identifier)} was not running.')
            if args.everything:
                report.say('Marketing Studio was not running.')
            return report.show(0)
        identifiers = [row['id'] for row in found['studios']] if args.everything else chosen
        busy = busy_in(found, identifiers)
        if busy and not args.force:
            return refuse(report, busy)
        failed = stop_running(report, found, identifiers, args.force)
        if not args.everything:
            return report.show(1 if failed else 0)
        if failed:
            return report.show(1, 'Marketing Studio was left running.')
        session.stop_home()
        stop_left_behind(report, everything, True)
        report.data['running'] = False
        report.say('Marketing Studio stopped.')
        return report.show(0)
    # restart
    if not args.everything:
        if found is None:
            return report.show(1, "Marketing Studio isn't running. Start it: marketing-studio start")
        busy = busy_in(found, chosen)
        if busy and not args.force:
            return refuse(report, busy)
        before = {row['id'] for row in found['studios']}
        if stop_running(report, found, [identifier for identifier in chosen if identifier in before], args.force):
            return report.show(1)
        cut = cut_off(report)
        failed = start_studios(report, chosen, restarted=before)
        report.data['cut_off'] = cut
        return report.show(1 if failed else 0)
    if found is None:
        busy = stop_left_behind(report, everything, args.force)
        if busy:
            return refuse(report, busy)
        report.say('Marketing Studio was not running.')
        running_home(report, session.start_home(session.serving(args.lan, args.port)), True)
        report.data['studios'] = report.data.get('studios', [])
        return report.show(0)
    busy = busy_in(found, everything)
    if busy and not args.force:
        return refuse(report, busy)
    before = [row['id'] for row in found['studios']]
    if stop_running(report, found, before, args.force):
        return report.show(1, 'Marketing Studio was left running.')
    cut = cut_off(report)
    session.stop_home()
    stop_left_behind(report, everything, True)
    cut += cut_off(report)
    found = session.start_home(session.serving(args.lan or found['lan'], args.port or found['port']))
    report.say('Marketing Studio restarted.')
    running_home(report, found, False)
    failed = start_studios(report, before, restarted=before)
    report.data['cut_off'] = cut
    return report.show(1 if failed else 0)


def main(argv=None):
    top = parser()
    args = top.parse_args(arrange(sys.argv[1:] if argv is None else argv))
    if args.studio and args.command != 'open':
        top.error('A studio name follows open, for example: marketing-studio open presentation.')
    if args.command in MANAGING:
        chosen = list(dict.fromkeys(args.selected or ()))
        if args.everything and chosen:
            top.commands[args.command].error('Use --all by itself, or choose studios: --bs, --ps, --ts.')
        if args.command != 'start' and not args.everything and not chosen:
            top.commands[args.command].error(f'Choose --all or the studios to {args.command}: --bs, --ps, --ts.')
        if args.command == 'restart' and not args.everything and (args.lan or args.port):
            top.commands[args.command].error('--lan and --port change Marketing Studio itself: use them with restart --all.')
        try:
            return manage(args, chosen)
        except (WorkspaceError, OSError, ValueError) as failure:
            print('Marketing Studio: ' + str(failure), file=sys.stderr)
            return 2
    if args.command == 'serve':
        # A server for this terminal, a headless computer or the network opens no browser.
        args.no_open = True
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
        if not args.no_open and not args.lan:
            result = control.request(state.data_root(), action)
            if result is not None:
                if result.get('error'):
                    raise WorkspaceError(result['error'])
                print('Opened ' + (args.studio.title() + ' Studio' if args.studio else 'Marketing Studio') + '.')
                return 0
        with singleton(network_requested=bool(args.lan)):
            lan = network.Network(network.discover_address() if args.lan == 'auto' else args.lan) if args.lan else None
            launcher = Launcher(lan)
            for row in launcher.clean_orphans(keep_busy=True):
                # An earlier Marketing Studio stopped abruptly and left its studios running.
                if row['stopped']:
                    print(f"Stopped {row['name']}, left running by an earlier Marketing Studio session.",
                          file=sys.stderr, flush=True)
                else:
                    print(f"{row['name']} is still running from an earlier Marketing Studio session and is working: "
                          + ', '.join(map(describe_job, row['jobs'])) + '. It was left running. When that work is '
                          f"done, stop it with: marketing-studio stop {session.flag(row['id'])}",
                          file=sys.stderr, flush=True)
            desk = None
            ipc = None
            def open_action(wanted):
                if wanted['command'] == 'setup':
                    url = desk.url + '&view=settings'
                elif wanted.get('studio') and Home.configured(shared.read()[0]):
                    values, problem = shared.read()
                    if problem:
                        raise WorkspaceError(problem)
                    url = launcher.open(wanted['studio'], state.read(), values)
                else:
                    url = desk.url
                if not server.show(url):
                    raise WorkspaceError('A browser could not be opened. Use the private link in your terminal.')
            def respond(wanted):
                """Answer a command from another terminal of this same account."""
                command = wanted['command']
                if command in ('open', 'setup'):
                    open_action(wanted)
                    return {'opened': True}
                if command == 'state':
                    return session.snapshot(launcher, desk, lan)
                if command == 'shutdown':
                    return {'stopping': True}
                if not wanted.get('studio'):
                    raise WorkspaceError('Choose a studio.')
                if command == 'start':
                    return session.start_studio(launcher, wanted['studio'])
                return session.stop_studio(launcher, wanted['studio'], wanted.get('force', False))

            def first_open(wanted):
                """The first open may fail; the home page stays available either way."""
                try:
                    open_action(wanted)
                    return None
                except (WorkspaceError, OSError, ValueError) as failure:
                    return str(failure)
            signal.signal(signal.SIGTERM, server.interrupt)
            signal.signal(signal.SIGINT, server.interrupt)
            try:
                desk = server.Desk(args.port, page=lambda port: Home(port, launcher))
                if lan:
                    # A separate interface can use the same chosen port as loopback.
                    lan.share('marketing', desk.url, port=desk.port)
                ipc = control.Control(state.data_root(), respond)
                problems = []

                def opener(_):
                    problems.append(first_open(action))
                    return problems[-1] is None
                shown = server.announce(desk, sys.stdout.isatty(),
                    (lambda _: False) if args.no_open else opener)
                if args.json or not sys.stdout.isatty():
                    if lan:
                        shown['network'] = lan.snapshot(private=sys.stdout.isatty())
                    if any(problems):
                        # Only a person's terminal is given the key, never a pipe.
                        shown['problem'] = problems[-1]
                    print(json.dumps(shown), flush=True)
                else:
                    print('Marketing Studio is ready.\n' + desk.url + '\n\nLeave this terminal open while you work. Press Ctrl-C to stop.', flush=True)
                    if lan:
                        print('Open on your phone (same trusted Wi-Fi):\n' + lan.snapshot()['url'] +
                              '\nKeep this link private. HTTP is unencrypted; it grants full studio access.', flush=True)
                    problem = None if args.no_open else first_open(action)
                    if problem:
                        print('\n' + problem + '\nMarketing Studio is still running. Open this private link in a browser:\n'
                              + desk.url, flush=True)
                desk.serve()
            except KeyboardInterrupt:
                pass
            finally:
                if ipc:
                    ipc.close()
                if lan:
                    lan.close()
                if desk:
                    desk.stop()
                launcher.close()
        return 0
    except (WorkspaceError, OSError, ValueError) as failure:
        print('Marketing Studio: ' + str(failure), file=sys.stderr)
        return 2
