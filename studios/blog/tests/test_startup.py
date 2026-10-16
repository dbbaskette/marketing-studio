"""Launch and computer-check behavior with synthetic homes, CLIs and documents."""

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
    def check(self, agents=(), git=None, gh=None, signed=None):
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
            return computer.report()

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

    def test_invalid_preferences_do_not_get_replaced(self):
        self.data.mkdir(parents=True)
        saved = self.data / 'page.json'
        saved.write_text('[]')
        self.assertEqual(start_studio.main(['--home', str(self.home)]), 1)
        self.assertEqual(saved.read_text(), '[]')
