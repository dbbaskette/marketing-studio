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


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='marketing-cli-', dir='/tmp')
        self.addCleanup(self.tmp.cleanup)
        self.data = Path(self.tmp.name) / 'data'
        self.data.mkdir()
        patcher = mock.patch.dict(os.environ, {'MARKETING_STUDIO_DATA': str(self.data),
                                               'STUDIOS_CONFIG': str(self.data / 'config.json')})
        patcher.start()
        self.addCleanup(patcher.stop)

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


if __name__ == '__main__':
    unittest.main()
