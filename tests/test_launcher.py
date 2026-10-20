import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from marketing_studio import bridge, catalog
from marketing_studio.errors import WorkspaceError
from marketing_studio.launcher import Launcher


class BridgeTests(unittest.TestCase):
    def test_existing_workspace_is_never_moved(self):
        gitstate = mock.Mock()
        existing = gitstate.current.return_value
        result = bridge.configure(gitstate, {'local': {'root': '/unused'}}, 'training')
        self.assertIs(result, existing)
        gitstate.local.assert_not_called()
        gitstate.join.assert_not_called()

    def test_local_default_and_remote_are_explicit_choices(self):
        gitstate = mock.Mock()
        gitstate.current.return_value = None
        bridge.configure(gitstate, {'local': {'root': '/work'}}, 'training')
        gitstate.local.assert_called_once_with(Path('/work/training-workspace'), branch='main')
        gitstate.reset_mock()
        bridge.configure(gitstate, {'team': {'repository': '/tmp/team.git', 'branch': 'main'},
                                   'share': 'asked'}, 'presentation')
        gitstate.join.assert_called_once_with('/tmp/team.git', branch='main', share='asked')
        gitstate.local.assert_not_called()


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        patcher = mock.patch.dict(os.environ, {'MARKETING_STUDIO_DATA': str(self.root / 'data')})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.launcher = Launcher()
        self.addCleanup(self.launcher.close)
        self.install = self.root / 'studio'
        (self.install / 'runner').mkdir(parents=True)
        (self.install / 'runner/studio.py').write_text('# fixture')
        self.preferences = {'paths': {'training': str(self.install.resolve())}}
        self.fixture_root = self.root / 'marketing'
        (self.fixture_root / 'marketing_studio').mkdir(parents=True)

    def fixture(self, content):
        (self.fixture_root / 'marketing_studio/bridge.py').write_text(content)
        return mock.patch('marketing_studio.launcher.ROOT', self.fixture_root)

    def test_launch_reuse_and_child_cleanup(self):
        content = """import json, os, time
handoff = json.loads(os.environ.pop('MARKETING_STUDIO_HANDOFF'))
print(json.dumps({'address': 'http://127.0.0.1:12345/'}), flush=True)
time.sleep(60)
"""
        with self.fixture(content):
            link = self.launcher.open('training', self.preferences, {})
            self.assertIn('#token=', link)
            self.assertTrue(self.launcher.running('training'))
            process = self.launcher.children['training'][0]
            self.assertEqual(link, self.launcher.open('training', self.preferences, {}))
            self.assertEqual(process.pid, self.launcher.children['training'][0].pid)
            self.launcher.close()
            self.assertIsNotNone(process.poll())
            self.assertFalse(self.launcher.children)
        self.assertNotIn(link, (self.root / 'data/logs/training.log').read_text())

    def test_failure_and_timeout_stop_the_child(self):
        with self.fixture("import json\nprint(json.dumps({'error':'Fixture refused'}), flush=True)\n"):
            with self.assertRaisesRegex(WorkspaceError, 'Fixture refused'):
                self.launcher.open('training', self.preferences, {})
        with self.fixture('import time\ntime.sleep(60)\n'), mock.patch('marketing_studio.launcher.TIMEOUT', .1):
            with self.assertRaisesRegex(WorkspaceError, 'too long'):
                self.launcher.open('training', self.preferences, {})
        self.assertFalse(self.launcher.children)

    def test_stopped_studio_names_its_log_and_last_lines(self):
        with self.fixture("import sys\nfor n in range(1, 21):\n    print('fixture line', n, file=sys.stderr)\n"):
            with self.assertRaises(WorkspaceError) as raised:
                self.launcher.open('training', self.preferences, {})
        message = str(raised.exception)
        log = self.root / 'data/logs/training.log'
        self.assertIn('Training Studio stopped before opening', message)
        self.assertIn(str(log), message)
        for n in range(9, 21):
            self.assertIn(f'fixture line {n}\n' if n < 20 else 'fixture line 20', message)
        self.assertNotIn('fixture line 8\n', message)
        self.assertFalse(self.launcher.children)

    def test_slow_studio_names_its_log(self):
        content = "import sys, time\nprint('fixture is waiting', file=sys.stderr)\ntime.sleep(60)\n"
        with self.fixture(content), mock.patch('marketing_studio.launcher.TIMEOUT', 2):
            with self.assertRaises(WorkspaceError) as raised:
                self.launcher.open('training', self.preferences, {})
        message = str(raised.exception)
        self.assertIn('took too long', message)
        self.assertIn(str(self.root / 'data/logs/training.log'), message)
        self.assertIn('fixture is waiting', message)

    def test_previous_launch_log_is_kept(self):
        logs = self.root / 'data/logs'
        for run in ('first run', 'second run'):
            with self.fixture(f"import sys\nprint({run!r}, file=sys.stderr)\n"):
                with self.assertRaises(WorkspaceError):
                    self.launcher.open('training', self.preferences, {})
        self.assertEqual((logs / 'training.log').read_text(), 'second run\n')
        self.assertEqual((logs / 'training.previous.log').read_text(), 'first run\n')
        self.assertEqual((logs / 'training.previous.log').stat().st_mode & 0o777, 0o600)

    def test_external_link_is_refused_and_browser_not_started(self):
        with self.fixture("import json\nprint(json.dumps({'link':'https://evil.example/'}), flush=True)\n"):
            with self.assertRaisesRegex(WorkspaceError, 'invalid local address'):
                self.launcher.open('training', self.preferences, {})

    def test_prepare_is_bounded_and_propagates_failure(self):
        with self.fixture("import json\nprint(json.dumps({'error':'Git identity needed'}), flush=True)\n"), mock.patch('marketing_studio.catalog.STUDIOS', {'training': catalog.STUDIOS['training']}):
            with self.assertRaisesRegex(WorkspaceError, 'Git identity needed'):
                self.launcher.prepare(self.preferences, {})
        with self.fixture('import time\ntime.sleep(60)\n'), mock.patch('marketing_studio.catalog.STUDIOS', {'training': catalog.STUDIOS['training']}), mock.patch('marketing_studio.launcher.TIMEOUT', .1):
            with self.assertRaisesRegex(WorkspaceError, 'too long'):
                self.launcher.prepare(self.preferences, {})

    def test_installed_blog_layout_is_found(self):
        installed = self.root / 'installed-blog'
        (installed / 'scripts').mkdir(parents=True)
        (installed / 'scripts/start_studio.py').write_text('# fixture')
        self.assertEqual(catalog.locate('blog', {'blog': str(installed)}), installed.resolve())

    def test_configured_path_is_authoritative(self):
        self.assertEqual(catalog.locate('training', self.preferences['paths']), self.install.resolve())
        self.assertIsNone(catalog.locate('training', {'training': '/does-not-exist'}))


if __name__ == '__main__':
    unittest.main()
