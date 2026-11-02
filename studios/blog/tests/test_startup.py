"""Launch and computer-check behavior with synthetic homes, CLIs and documents."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import importlib.util
import json
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/blog-studio/scripts'
sys.path.insert(0, str(SCRIPTS))
import computer
import start_studio


class ComputerTests(unittest.TestCase):
    def check(self, agents=(), git=None, gh=None, signed=None, network=False):
        def probe(command, cwd=None):
            if command[-2:] == ['login', 'status']:
                return signed
            if command[0] == 'python3':
                return 0, 'Python 3.9.0'
            return 0, 'Synthetic identity only'

        with (
            patch.object(
                computer,
                'cli_path',
                side_effect=lambda name: '/fixture/' + name if name in agents else None,
            ),
            patch.object(computer, 'git_path', return_value=git),
            patch.object(computer.shutil, 'which', return_value=gh),
            patch.object(computer, 'probe', side_effect=probe),
        ):
            return computer.report(network=network)

    def test_missing_assistant_is_actionable_and_optional_hub_is_separate(self):
        found = self.check()
        self.assertEqual(
            next(x for x in found['checks'] if x['key'] == 'assistant')['status'], 'action'
        )
        self.assertTrue(next(x for x in found['checks'] if x['key'] == 'hub')['optional'])
        self.assertIn('Local writing needs neither', computer.describe(found))
        self.assertIn('Nothing needs changing', computer.describe(found))

    def test_sign_in_is_bounded_and_reports_no_account_details(self):
        found = self.check(
            ('codex', 'claude'),
            git='/fixture/git',
            gh='/fixture/gh',
            signed=(0, 'Synthetic account marker'),
        )
        self.assertTrue(found['agents']['codex']['signed_in'])
        self.assertIsNone(found['agents']['claude']['signed_in'])
        self.assertNotIn('Synthetic account marker', json.dumps(found))
        self.assertNotIn('Synthetic identity', json.dumps(found))
        found = self.check(('codex',), signed=(1, 'Not logged in'))
        self.assertIn('codex login', computer.describe(found))
        with patch.object(
            computer.subprocess, 'run', side_effect=subprocess.TimeoutExpired('fixture', 4)
        ):
            self.assertIsNone(computer.probe(['fixture']))

    def looked(self, blocked, **given):
        """Check this computer where `blocked` maps the hosts this network does not let
        through to what blocked() found. Returns the report and the hosts looked at; the
        look is a stand-in, so nothing is contacted."""
        from studio_core import reachability

        with patch.object(
            reachability, 'blocked', side_effect=lambda host, seconds: blocked.get(host)
        ) as look:
            found = self.check(network=True, **given)
        for call in look.call_args_list:
            self.assertEqual(call.args[1], computer.NETWORK_SECONDS)
        return found, sorted(call.args[0] for call in look.call_args_list)

    def row(self, found, key):
        return next(x for x in found['checks'] if x['key'] == key)

    def test_a_signed_in_assistant_this_network_cuts_off_is_reported(self):
        found, hosts = self.looked(
            {'chatgpt.com': ('intercepted', 'self-signed certificate in certificate chain')},
            agents=('codex', 'claude'),
            signed=(0, 'Logged in using ChatGPT'),
        )
        self.assertEqual(hosts, ['api.anthropic.com', 'chatgpt.com'])
        codex = self.row(found, 'codex')
        self.assertEqual(codex['status'], 'action')
        self.assertEqual(
            codex['detail'],
            'CLI found; signed in, but it cannot be used from this network: the connection to '
            'chatgpt.com is being intercepted on this network, or its certificate is not '
            'trusted here (self-signed certificate in certificate chain).',
        )
        self.assertEqual(
            codex['next_step'],
            'Try another network, or choose Claude Code for new work under Settings → Writing '
            'preferences, then check again.',
        )
        self.assertEqual(self.row(found, 'claude')['status'], 'manual')
        self.assertEqual(found['agents']['codex']['reachable'], False)
        self.assertEqual(found['agents']['claude']['reachable'], True)
        self.assertIn('cannot be used from this network', computer.describe(found))

    def test_claude_code_out_of_reach_and_codex_with_an_api_key(self):
        found, hosts = self.looked(
            {'api.anthropic.com': ('unreachable', 'timed out')},
            agents=('codex', 'claude'),
            signed=(0, 'Logged in using an API key - sk-proj-***'),
        )
        self.assertEqual(hosts, ['api.anthropic.com', 'api.openai.com'])
        claude = self.row(found, 'claude')
        self.assertEqual(claude['status'], 'action')
        self.assertIn('api.anthropic.com cannot be reached from this network', claude['detail'])
        self.assertIn('choose Codex for new work', claude['next_step'])
        self.assertEqual(self.row(found, 'codex')['status'], 'ready')

    def test_the_network_is_not_looked_at_without_a_signed_in_assistant(self):
        found, hosts = self.looked({}, agents=('codex',), signed=(1, 'Not logged in'))
        self.assertEqual(hosts, [])
        self.assertIsNone(found['agents']['codex']['reachable'])

    def test_the_status_page_and_the_check_command_ask_for_the_network(self):
        import management

        empty = {'checks': [], 'notes': [], 'agents': {}}
        with (
            patch.object(computer, 'report', return_value=empty) as made,
            patch('brand_skill.status', return_value={'brands': [], 'problem': '', 'name': ''}),
        ):
            management.view(Path(tempfile.gettempdir()), 'computer', {})
            self.assertEqual(made.call_args.kwargs, {'network': True})
            with patch('builtins.print'):
                start_studio.main(['check', '--home', tempfile.gettempdir()])
            self.assertEqual(made.call_args.kwargs, {'network': True})

    def test_the_network_is_looked_at_only_when_asked(self):
        from studio_core import reachability

        with patch.object(reachability, 'blocked') as look:
            found = self.check(('codex', 'claude'), signed=(0, 'Logged in using ChatGPT'))
        look.assert_not_called()
        self.assertIsNone(found['agents']['claude']['reachable'])
        self.assertEqual(self.row(found, 'codex')['status'], 'ready')
        with patch.object(computer, 'unreachable') as look:
            with (
                patch.object(computer, 'cli_path', return_value='/fixture/claude'),
                patch.object(computer, 'git_path', return_value=None),
                patch.object(computer, 'probe', return_value=None),
            ):
                computer.report(sign_in=False, network=True)
        look.assert_called_once_with([])

    def test_bundled_codex_sign_in_uses_a_command_that_exists(self):
        bundled = '/Applications/Synthetic app/codex'
        with (
            patch.object(
                computer, 'cli_path', side_effect=lambda name: bundled if name == 'codex' else None
            ),
            patch.object(computer, 'git_path', return_value=None),
            patch.object(computer.shutil, 'which', return_value=None),
            patch.object(computer, 'probe', return_value=(1, 'Not logged in')),
        ):
            found = computer.report()
        self.assertIn("Run '/Applications/Synthetic app/codex' login", computer.describe(found))

    def test_apple_git_placeholder_does_not_open_developer_setup(self):
        with (
            patch.object(computer.sys, 'platform', 'darwin'),
            patch.object(computer.shutil, 'which', return_value='/usr/bin/git'),
            patch.object(computer, 'probe', return_value=(1, '')) as probe,
        ):
            self.assertIsNone(computer.git_path())
        self.assertEqual(probe.call_args.args[0], ['xcode-select', '-p'])


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='blog-start-synthetic-')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name).resolve()
        self.data = self.home / '.local/share/blog-studio'
        self.workspace = self.home / 'Synthetic writing'

    def test_start_remembers_workspace_and_calls_the_page_without_enabling_analysis(self):
        with patch('management.main', return_value=0) as serve:
            self.assertEqual(
                start_studio.main(['--home', str(self.home), '--root', str(self.workspace)]), 0
            )
            self.assertEqual(serve.call_args.args[0], self.workspace)
            self.assertNotIn('harness', serve.call_args.kwargs)
            self.assertTrue(serve.call_args.kwargs['open_browser'])
            self.assertEqual(start_studio.main(['--home', str(self.home)]), 0)
            self.assertEqual(serve.call_args.args[0], self.workspace)
        self.assertEqual(list((self.data / 'running').glob('*.json')), [])
        self.assertEqual(
            json.loads((self.data / 'page.json').read_text()), {'workspace': str(self.workspace)}
        )

    def test_real_start_stops_cleanly_and_blocks_setup_while_serving(self):
        process = subprocess.Popen(
            [
                sys.executable,
                str(SCRIPTS / 'start_studio.py'),
                '--home',
                str(self.home),
                '--root',
                str(self.workspace),
                '--no-open',
                '--json',
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(lambda: process.poll() is None and process.kill())
        timer = threading.Timer(10, process.kill)
        timer.start()
        self.addCleanup(timer.cancel)
        try:
            while True:
                line = process.stdout.readline()
                if line.startswith('{'):
                    result = json.loads(line)
                    break
                if not line:
                    self.fail(process.stderr.read())
            self.assertNotIn('#', result['url'])
            spec = importlib.util.spec_from_file_location(
                'startup_setup_fixture', SCRIPTS.parents[2] / 'installer/install.py'
            )
            setup = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(setup)
            with self.assertRaisesRegex(setup.InstallError, 'Blog Studio is open'):
                with setup.not_running(self.data):
                    pass
            process.send_signal(signal.SIGTERM)
            self.assertEqual(process.wait(timeout=10), 0, process.stderr.read())
            self.assertEqual(list((self.data / 'running').glob('*.json')), [])
            with setup.not_running(self.data):
                pass
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdout.close()
            process.stderr.close()

    def test_loopback_startup_never_waits_for_hostname_resolution(self):
        from management import server

        with patch('socket.getfqdn', side_effect=AssertionError('No DNS during startup')):
            httpd, _ = server(self.workspace)
        try:
            self.assertEqual(httpd.server_name, '127.0.0.1')
            self.assertGreater(httpd.server_port, 0)
        finally:
            httpd.server_close()

    def test_invalid_preferences_do_not_get_replaced(self):
        self.data.mkdir(parents=True)
        saved = self.data / 'page.json'
        saved.write_text('[]')
        self.assertEqual(start_studio.main(['--home', str(self.home)]), 1)
        self.assertEqual(saved.read_text(), '[]')
