import contextlib
import io
import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest import mock

from marketing_studio import cli, control
from marketing_studio.errors import WorkspaceError


class Terminal(io.StringIO):
    def isatty(self):
        return True


class FakeDesk:
    """Stands in for the home server: binds nothing and returns from serve at once."""
    made = []

    def __init__(self, port=0, page=None):
        self.port = 43210
        self.address = f'http://127.0.0.1:{self.port}/'
        self.url = self.address + '#token=' + 'k' * 43
        self.served = self.stopped = False
        FakeDesk.made.append(self)

    def serve(self):
        self.served = True

    def stop(self):
        self.stopped = True


class Disposable(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='marketing-cli-')
        self.addCleanup(self.tmp.cleanup)
        self.data = Path(self.tmp.name) / 'data'
        self.data.mkdir()
        patcher = mock.patch.dict(os.environ, {'MARKETING_STUDIO_DATA': str(self.data),
                                               'STUDIOS_CONFIG': str(self.data / 'config.json')})
        patcher.start()
        self.addCleanup(patcher.stop)


class CliTests(Disposable):
    def test_status_and_doctor_are_offline(self):
        with mock.patch.object(cli.server, 'show', side_effect=AssertionError('Opened browser')):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(cli.main(['status', '--json']), 0)
            self.assertFalse(json.loads(output.getvalue())['setup_complete'])
            with mock.patch.object(cli.computer, 'check', return_value={'ready': True, 'items': []}), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(['doctor']), 0)

    def test_help_uses_simple_commands(self):
        output = cli.parser().format_help()
        for name in ('open', 'setup', 'doctor', 'status', 'update'):
            self.assertIn(name, output)
        self.assertEqual(cli.parser().parse_args(['open', 'presentation']).studio, 'presentation')

    def test_repeated_open_reuses_private_control(self):
        actions = []
        ipc = control.Control(self.data, actions.append)
        self.addCleanup(ipc.close)
        output = io.StringIO()
        with contextlib.redirect_stdout(output), mock.patch.object(cli, 'singleton', side_effect=AssertionError('Started another server')):
            self.assertEqual(cli.main(['open', 'presentation']), 0)
            self.assertEqual(cli.main(['setup']), 0)
        self.assertEqual(actions, [{'command': 'open', 'studio': 'presentation'},
                                   {'command': 'setup', 'studio': None}])
        self.assertEqual(ipc.path.stat().st_mode & 0o777, 0o600)
        self.assertNotIn('token', output.getvalue())

    def test_control_refuses_unknown_commands_and_unmanaged_paths(self):
        ipc = control.Control(self.data, lambda _: self.fail('Called action'))
        self.addCleanup(ipc.close)
        self.assertIn('error', control.request(self.data, {'command': 'erase'}))
        other = Path(self.tmp.name) / 'other'
        other.mkdir()
        (other / 'control.sock').write_text('keep this file')
        with self.assertRaises(OSError):
            control.Control(other, lambda _: None)
        self.assertEqual((other / 'control.sock').read_text(), 'keep this file')

    def test_long_data_root_has_private_short_socket_path(self):
        long = self.data / ('long' * 50)
        long.mkdir()
        ipc = control.Control(long, lambda _: None)
        self.addCleanup(ipc.close)
        self.assertLess(len(os.fsencode(ipc.path)), 100)
        self.assertEqual(control.request(long, {'command': 'open'}), {'opened': True})

    def test_installer_commands_forward_explicit_selection(self):
        with mock.patch.object(cli.subprocess, 'call', return_value=0) as call:
            self.assertEqual(cli.main(['install', '--studios', 'blog', '--yes', '--companions', 'skip']), 0)
        command = call.call_args.args[0]
        self.assertIn('--yes', command)
        self.assertEqual(command[command.index('--studios') + 1], 'blog')


class HomeServerTests(Disposable):
    """A failed first open is reported; the home server keeps serving."""

    def setUp(self):
        super().setUp()
        FakeDesk.made.clear()
        for target, name, value in ((cli.server, 'Desk', FakeDesk),
                                    (cli.server, 'show', mock.Mock(return_value=False)),
                                    (cli.signal, 'signal', mock.Mock()),
                                    (cli.control, 'Control', mock.Mock())):
            patcher = mock.patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_home(self, arguments, output):
        errors = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = cli.main(arguments)
        return code, output.getvalue() + errors.getvalue()

    def test_browser_that_cannot_open_keeps_serving_with_private_link(self):
        code, printed = self.run_home([], Terminal())
        desk = FakeDesk.made[-1]
        self.assertEqual(code, 0)
        self.assertTrue(desk.served)
        self.assertTrue(desk.stopped)
        problem = printed.index('A browser could not be opened')
        self.assertIn(desk.url, printed[problem:])

    def test_refused_first_studio_open_keeps_serving(self):
        launcher = mock.Mock()
        launcher.open.side_effect = WorkspaceError('Training Studio stopped before opening.')
        with mock.patch.object(cli, 'Launcher', return_value=launcher), \
                mock.patch.object(cli.Home, 'configured', return_value=True):
            code, printed = self.run_home(['open', 'training'], Terminal())
        desk = FakeDesk.made[-1]
        self.assertEqual(code, 0)
        self.assertTrue(desk.served)
        problem = printed.index('Training Studio stopped before opening.')
        self.assertIn(desk.url, printed[problem:])
        launcher.close.assert_called_once_with()

    def test_failed_open_for_a_pipe_reports_without_the_key(self):
        code, printed = self.run_home([], io.StringIO())
        desk = FakeDesk.made[-1]
        self.assertEqual(code, 0)
        self.assertTrue(desk.served)
        shown = json.loads(printed.splitlines()[0])
        self.assertFalse(shown['opened'])
        self.assertIn('A browser could not be opened', shown['problem'])
        self.assertNotIn('k' * 43, printed)

    def test_serve_never_opens_a_browser_or_asks_a_running_home(self):
        cli.server.show.side_effect = AssertionError('Opened a browser')
        with mock.patch.object(cli.control, 'request', side_effect=AssertionError('Asked a running home')):
            code, printed = self.run_home(['serve'], Terminal())
        self.assertEqual(code, 0)
        self.assertTrue(FakeDesk.made[-1].served)
        self.assertIn(FakeDesk.made[-1].url, printed)


if __name__ == '__main__':
    unittest.main()
