"""marketing-studio start | stop | restart, with disposable data, settings and processes.

A scripted stand-in answers the control socket for the command-line tests; the
background test starts a real Marketing Studio with a fake Training Studio.
"""
import contextlib
import io
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

from marketing_studio import cli, control

ROOT = Path(__file__).resolve().parents[1]
KEY = 'k' * 43
JOB = {'assistant': 'codex', 'label': 'deck-1', 'pid': 99999, 'seconds': 250}


def binds(family, address):
    with socket.socket(family, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(address)
            return True
        except OSError:
            return False


with tempfile.TemporaryDirectory() as _folder:
    UNIX = binds(socket.AF_UNIX, str(Path(_folder) / 'probe.sock'))
TCP = binds(socket.AF_INET, ('127.0.0.1', 0))


class Terminal(io.StringIO):
    def isatty(self):
        return True


class Disposable(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='marketing-start-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = self.root / 'data'
        self.data.mkdir()
        (self.root / 'home').mkdir()
        patcher = mock.patch.dict(os.environ, {'MARKETING_STUDIO_DATA': str(self.data),
                                               'HOME': str(self.root / 'home'),
                                               'STUDIOS_CONFIG': str(self.root / 'studios-config.json')})
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_cli(self, arguments, output=None):
        output = output if output is not None else Terminal()
        errors = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            try:
                code = cli.main(arguments)
            except SystemExit as stopped:
                code = stopped.code
        return code, output.getvalue(), errors.getvalue()


class ParserTests(Disposable):
    def test_every_selection_spelling(self):
        spellings = {'blog': ('--bs', '-bs', '--blog'), 'presentation': ('--ps', '-ps', '--presentation'),
                     'training': ('--ts', '-ts', '--training')}
        for command in ('start', 'stop', 'restart'):
            for identifier, flags in spellings.items():
                for flag in flags:
                    with self.subTest(command=command, flag=flag):
                        self.assertEqual(cli.parser().parse_args([command, flag]).selected, [identifier])
            for flag in ('--all', '-a'):
                self.assertTrue(cli.parser().parse_args([command, flag]).everything)
        both = cli.parser().parse_args(['start', '-bs', '--training'])
        self.assertEqual(both.selected, ['blog', 'training'])
        self.assertTrue(cli.parser().parse_args(['stop', '--ts', '--force']).force)

    def test_the_owners_word_order(self):
        self.assertEqual(cli.arrange(['--all', 'stop']), ['stop', '--all'])
        self.assertEqual(cli.arrange(['-bs', '-ts', 'start']), ['start', '-bs', '-ts'])
        self.assertEqual(cli.arrange(['--force', '--ts', 'restart']), ['restart', '--force', '--ts'])
        self.assertEqual(cli.arrange(['stop', '--all']), ['stop', '--all'])
        args = cli.parser().parse_args(cli.arrange(['-a', 'stop']))
        self.assertEqual((args.command, args.everything), ('stop', True))

    def test_lan_and_other_bare_flags_still_mean_open(self):
        self.assertEqual(cli.arrange(['--lan']), ['open', '--lan'])
        self.assertEqual(cli.arrange(['--json']), ['open', '--json'])
        self.assertEqual(cli.arrange(['--port', '8000']), ['open', '--port', '8000'])
        self.assertEqual(cli.arrange([]), ['open'])
        args = cli.parser().parse_args(cli.arrange(['--lan']))
        self.assertEqual((args.command, args.lan), ('open', 'auto'))

    def test_stop_and_restart_need_a_selection(self):
        for command in ('stop', 'restart'):
            code, _, errors = self.run_cli([command])
            self.assertEqual(code, 2)
            self.assertIn(f'Choose --all or the studios to {command}: --bs, --ps, --ts.', errors)

    def test_all_with_studio_flags_is_refused(self):
        for arguments in (['stop', '--all', '--bs'], ['start', '-a', '-ts'], ['--all', '--ps', 'restart']):
            code, _, errors = self.run_cli(arguments)
            self.assertEqual(code, 2)
            self.assertIn('Use --all by itself', errors)

    def test_help_explains_start_stop_and_force(self):
        top = cli.parser().format_help()
        for name in ('start', 'stop', 'restart'):
            self.assertIn(name, top)
        self.assertIn('--force', cli.parser().commands['stop'].format_help())
        self.assertIn('start --all --lan', cli.parser().commands['start'].format_help())


class FakeHome:
    """Answers the control socket the way a running Marketing Studio does."""
    def __init__(self, data, studios=(), lan=None):
        self.actions = []
        self.studios = [dict(row) for row in studios]
        self.lan = lan
        self.ipc = control.Control(data, self.handle, shutdown=self.shutdown)

    def handle(self, action):
        self.actions.append(action)
        command = action['command']
        if command == 'state':
            return {'pid': 1, 'port': 4321, 'url': 'http://127.0.0.1:4321/#token=' + KEY,
                    'lan': self.lan, 'phone': f'http://{self.lan}:4321/#token={KEY}' if self.lan else None,
                    'studios': self.studios}
        if command == 'shutdown':
            return {'stopping': True}
        row = next((row for row in self.studios if row['id'] == action['studio']), None)
        if command == 'start':
            if row is None:
                self.studios.append({'id': action['studio'], 'name': action['studio'].title() + ' Studio',
                                     'jobs': [], 'earlier': False})
            return {'started': row is None}
        if row and row['jobs'] and not action['force']:
            return {'error': 'Working.', 'jobs': row['jobs']}
        if row:
            self.studios.remove(row)
        return {'stopped': row is not None, 'jobs': row['jobs'] if row else []}

    def shutdown(self):
        threading.Thread(target=self.ipc.close).start()

    def close(self):
        if not self.ipc.stopped.is_set():
            self.ipc.close()

    def commands(self):
        return [action['command'] for action in self.actions]


@unittest.skipUnless(UNIX, 'Local sockets are not permitted here.')
class ManagingTests(Disposable):
    def home(self, studios=(), lan=None):
        fake = FakeHome(self.data, studios, lan)
        self.addCleanup(fake.close)
        return fake

    def busy(self):
        return self.home([{'id': 'training', 'name': 'Training Studio', 'jobs': [JOB], 'earlier': False}])

    def test_stop_refuses_a_studio_with_a_running_job_and_stops_nothing(self):
        fake = self.busy()
        code, _, errors = self.run_cli(['stop', '--ts'])
        self.assertEqual(code, 1)
        self.assertEqual(errors.strip(), 'Training Studio is working: codex job deck-1 (4 min). '
                         'Its work so far would be lost. Wait for it, or add --force.')
        code, _, _ = self.run_cli(['stop', '--all'])
        self.assertEqual(code, 1)
        code, _, _ = self.run_cli(['restart', '--all'])
        self.assertEqual(code, 1)
        self.assertEqual(fake.commands(), ['state', 'state', 'state'])

    def test_refusal_for_a_pipe_is_json(self):
        self.busy()
        code, output, _ = self.run_cli(['stop', '--ts'], io.StringIO())
        self.assertEqual(code, 1)
        found = json.loads(output)
        self.assertTrue(found['refused'])
        self.assertEqual(found['working'][0]['jobs'][0]['label'], 'deck-1')

    def test_force_stops_and_says_which_job_was_cut_off(self):
        fake = self.busy()
        code, output, _ = self.run_cli(['--force', '-ts', 'stop'])
        self.assertEqual(code, 0)
        self.assertIn({'command': 'stop', 'studio': 'training', 'force': True}, fake.actions)
        self.assertIn('Training Studio stopped; codex job deck-1 (4 min) was cut off.', output)

    def test_stop_all_stops_the_studios_then_marketing_studio(self):
        fake = self.home([{'id': 'blog', 'name': 'Blog Studio', 'jobs': [], 'earlier': False}])
        code, output, _ = self.run_cli(['--all', 'stop'])
        self.assertEqual(code, 0)
        self.assertEqual(fake.commands(), ['state', 'stop', 'shutdown'])
        self.assertIn('Blog Studio stopped.', output)
        self.assertIn('Marketing Studio stopped.', output)

    def test_start_prints_the_link_only_to_a_terminal(self):
        fake = self.home()
        code, output, _ = self.run_cli(['start', '--ts'])
        self.assertEqual(code, 0)
        self.assertIn('Marketing Studio is running.\nhttp://127.0.0.1:4321/#token=' + KEY, output)
        self.assertIn('Training Studio started.', output)
        code, output, _ = self.run_cli(['start', '-ts'], io.StringIO())
        self.assertEqual(code, 0)
        self.assertNotIn(KEY, output)
        found = json.loads(output)
        self.assertEqual((found['running'], found['started'], found['address']),
                         (True, False, 'http://127.0.0.1:4321/'))
        self.assertEqual(found['studios'], [{'id': 'training', 'name': 'Training Studio',
                                             'result': 'already running'}])
        code, output, _ = self.run_cli(['start', '--json'], Terminal())
        self.assertNotIn(KEY, output)
        self.assertEqual(fake.commands().count('start'), 2)

    def test_start_shows_the_phone_link_when_lan_is_on(self):
        self.home(lan='192.168.1.20')
        code, output, _ = self.run_cli(['start'])
        self.assertEqual(code, 0)
        self.assertIn('Open on your phone (same trusted Wi-Fi):\nhttp://192.168.1.20:4321/#token=' + KEY, output)

    def test_start_with_other_network_settings_suggests_restart(self):
        fake = self.home()
        code, _, errors = self.run_cli(['start', '--ts', '--lan', '192.168.1.20'])
        self.assertEqual(code, 1)
        self.assertIn('already running without phone access', errors)
        self.assertIn('marketing-studio restart --all --lan 192.168.1.20', errors)
        code, _, errors = self.run_cli(['start', '--port', '8000'])
        self.assertIn('already running on port 4321', errors)
        self.assertNotIn('start', fake.commands())

    def test_restart_a_studio_stops_then_starts_it(self):
        fake = self.home([{'id': 'training', 'name': 'Training Studio', 'jobs': [], 'earlier': False}])
        code, output, _ = self.run_cli(['restart', '--ts', '--bs'])
        self.assertEqual(code, 0)
        self.assertEqual(fake.commands(), ['state', 'stop', 'start', 'start'])
        self.assertIn('Training Studio restarted.', output)
        self.assertIn('Blog Studio started.', output)

    def test_status_lists_what_is_running_now(self):
        self.busy()
        code, output, _ = self.run_cli(['status'])
        self.assertEqual(code, 0)
        self.assertIn('Running now:\n  Marketing Studio on port 4321, phone access off\n'
                      '  Training Studio: working on codex job deck-1 (4 min)', output)
        code, output, _ = self.run_cli(['status', '--json'])
        found = json.loads(output)
        self.assertEqual(found['running']['port'], 4321)
        self.assertNotIn(KEY, output)


class NothingRunningTests(Disposable):
    def test_stop_all_without_marketing_studio_says_so(self):
        code, output, _ = self.run_cli(['stop', '--all'])
        self.assertEqual(code, 0)
        self.assertIn('Marketing Studio was not running.', output)
        code, output, _ = self.run_cli(['stop', '--bs'])
        self.assertEqual(code, 0)
        self.assertIn('Blog Studio was not running.', output)

    def test_restarting_a_studio_needs_marketing_studio(self):
        code, _, errors = self.run_cli(['restart', '--ts'])
        self.assertEqual(code, 1)
        self.assertIn("Marketing Studio isn't running. Start it: marketing-studio start", errors)

    def test_status_stays_offline_when_nothing_runs(self):
        code, output, _ = self.run_cli(['status'])
        self.assertEqual(code, 0)
        self.assertNotIn('Running now', output)

    def test_lan_and_port_belong_to_restart_all(self):
        code, _, errors = self.run_cli(['restart', '--ts', '--lan'])
        self.assertEqual(code, 2)
        self.assertIn('use them with restart --all', errors)


FAKE_STUDIO = """import contextlib, json, os, time
RESTART = 'FAKE_TRAINING_RESTART'


@contextlib.contextmanager
def only_runner():
    yield


def main(arguments):
    json.loads(os.environ[RESTART])
    print(json.dumps({'address': 'http://127.0.0.1:9/'}), flush=True)
    time.sleep(600)
"""


@unittest.skipUnless(UNIX and TCP, 'Local sockets are not permitted here.')
class BackgroundTests(Disposable):
    """A real Marketing Studio in the background, with a fake Training Studio."""

    def setUp(self):
        super().setUp()
        studio = self.root / 'training'
        (studio / 'runner').mkdir(parents=True)
        (studio / 'runner/__init__.py').write_text('')
        (studio / 'runner/gitstate.py').write_text('def current():\n    return object()\n')
        (studio / 'runner/setup.py').write_text('def migrate():\n    pass\n')
        (studio / 'runner/studio.py').write_text(FAKE_STUDIO)
        missing = str(self.root / 'not-installed')
        os.environ.update({'TRAINING_STUDIO_INSTALL': str(studio), 'BLOG_STUDIO_INSTALL': missing,
                           'PRESENTATION_STUDIO_INSTALL': missing})
        from studio_core import preferences
        cli.shared.update({'local': {'root': str(self.root / 'work')}, 'assistant': {'agent': 'codex'},
                           'output': 'pptx'})
        preferences.finish(cli.shared, lambda _: None)
        self.addCleanup(self.leave_nothing_running)

    def leave_nothing_running(self):
        """Stop whatever this test started in its own data root, and nothing else."""
        try:
            found = control.request(self.data, {'command': 'state'})
        except (OSError, ValueError):
            found = None
        if found and found.get('pid'):
            try:
                control.request(self.data, {'command': 'shutdown'})
            except (OSError, ValueError):
                pass
            if not self.gone(found['pid'], 20):
                os.killpg(found['pid'], signal.SIGKILL)
        for record in (self.data / 'run').glob('*.json'):
            try:
                os.killpg(json.loads(record.read_text())['pid'], signal.SIGKILL)
            except (OSError, ValueError, KeyError):
                pass

    @staticmethod
    def gone(pid, seconds=10):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return True
            time.sleep(.1)
        return False

    def command(self, *arguments):
        done = subprocess.run([sys.executable, str(ROOT / 'marketing-studio'), *arguments, '--json'],
                              capture_output=True, text=True, timeout=90, env=os.environ, cwd=self.root)
        self.assertNotIn('#token=', done.stdout)
        return done.returncode, (json.loads(done.stdout) if done.stdout.strip() else None), done.stderr

    def test_start_in_the_background_then_stop_everything(self):
        code, found, errors = self.command('start')
        self.assertEqual(code, 0, errors)
        self.assertEqual((found['running'], found['started']), (True, True))
        running = control.request(self.data, {'command': 'state'})
        self.assertEqual(running['studios'], [])
        code, found, errors = self.command('start', '--ts')
        self.assertEqual(code, 0, errors)
        self.assertFalse(found['started'])
        self.assertEqual(found['studios'][0]['result'], 'started')
        self.assertTrue((self.data / 'run/training.json').is_file())
        code, found, _ = self.command('status')
        self.assertEqual([row['id'] for row in found['running']['studios']], ['training'])
        code, found, errors = self.command('stop', '--all')
        self.assertEqual(code, 0, errors)
        self.assertEqual(found['studios'][0]['result'], 'stopped')
        self.assertIsNone(control.request(self.data, {'command': 'state'}))
        self.assertFalse(control.address(self.data).exists())
        self.assertTrue(self.gone(running['pid']))
        self.assertEqual(list((self.data / 'run').glob('*.json')), [])
        self.assertNotIn('#token=', (self.data / 'logs/home.log').read_text())

    def test_restart_all_keeps_the_port_and_the_running_studios(self):
        self.assertEqual(self.command('start', '--ts')[0], 0)
        before = control.request(self.data, {'command': 'state'})
        code, found, errors = self.command('restart', '--all')
        self.assertEqual(code, 0, errors)
        after = control.request(self.data, {'command': 'state'})
        self.assertNotEqual(after['pid'], before['pid'])
        self.assertEqual(after['port'], before['port'])
        self.assertEqual([row['id'] for row in after['studios']], ['training'])
        self.assertEqual(found['studios'][0]['result'], 'restarted')
        self.assertEqual(self.command('stop', '--all')[0], 0)


if __name__ == '__main__':
    unittest.main()
