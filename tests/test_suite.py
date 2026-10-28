import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

import marketing_studio
from studio_core import bundles
from studio_core.server import for_product as server_for
from studio_core.studios_config import for_product as config_for

ROOT = Path(__file__).resolve().parents[1]


class CoreTests(unittest.TestCase):
    def test_products_have_independent_protocol_and_config_contexts(self):
        first = server_for('_first_protocol', 'First Studio', 'X-First-Token', ROOT, {}, None, ValueError)
        second = server_for('_second_protocol', 'Second Studio', 'X-Second-Token', ROOT, {}, None, RuntimeError)
        self.assertEqual(first.TOKEN_HEADER, 'X-First-Token')
        self.assertEqual(second.TOKEN_HEADER, 'X-Second-Token')
        self.assertIs(first.WorkspaceError, ValueError)
        self.assertIs(second.WorkspaceError, RuntimeError)
        first_config = config_for('_first_config', 'First Studio', ValueError, lambda _: None)
        second_config = config_for('_second_config', 'Second Studio', RuntimeError, lambda _: None)
        first_config.WAIT = .01
        self.assertNotEqual(first_config.WAIT, second_config.WAIT)
        self.assertIn('Second Studio', second_config.USING)

    def test_shared_setup_guide_and_ui_are_in_every_subset_bundle(self):
        for identifier in ('blog', 'presentation', 'training'):
            with self.subTest(studio=identifier):
                payload = bundles.inventory(ROOT, [identifier])
                self.assertIn('docs/shared-setup.md', payload)
                for asset in ('index.html', 'app.js', 'home.css', 'style.css'):
                    self.assertIn('core/studio_core/setup_web/' + asset, payload)
                    self.assertIn('studios/' + identifier + '/skills/' + identifier
                                  + '-studio/scripts/studio_core/setup_web/' + asset, payload)

    def test_one_pin_set_and_one_asset_source(self):
        for identifier in ('blog', 'presentation', 'training'):
            self.assertEqual((ROOT / 'studios' / identifier / 'installer/companions.json').resolve(),
                             ROOT / 'pins/companions.json')
        self.assertEqual((ROOT / 'marketing_studio/web/style.css').resolve(), ROOT / 'ui-kit/style.css')


class SuiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='marketing-suite-', dir='/tmp')
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.base = Path(cls.tmp.name)
        cls.archives = cls.base / 'archives'
        cls.digests = bundles.build(ROOT, cls.archives)

    def setUp(self):
        self.case = Path(tempfile.mkdtemp(prefix='case-', dir=self.base))
        self.addCleanup(shutil.rmtree, self.case)
        self.home = self.case / 'home'
        self.home.mkdir()
        self.env = {**os.environ, 'HOME': str(self.home), 'CODEX_HOME': str(self.home / '.codex'),
                    'CLAUDE_CONFIG_DIR': str(self.home / '.claude'),
                    'STUDIOS_CONFIG': str(self.home / 'shared.json'), 'GIT_CONFIG_GLOBAL': os.devnull}
        for name in list(self.env):
            if name.startswith(('ANTHROPIC_', 'OPENAI_', 'CLAUDECODE')):
                self.env.pop(name)

    def run_setup(self, source, *args, success=True):
        done = subprocess.run([sys.executable, str(source / 'installer/install.py'), *args,
                               '--home', str(self.home), '--yes', '--companions', 'skip', '--json'],
                              env=self.env, capture_output=True, text=True, timeout=180)
        if success:
            self.assertEqual(done.returncode, 0, done.stderr + done.stdout)
            return json.loads(done.stdout)
        self.assertNotEqual(done.returncode, 0, done.stdout)
        return done

    def unpack(self, product):
        destination = self.case / product
        with zipfile.ZipFile(self.archives / (product + '-installer.zip')) as archive:
            archive.extractall(destination)
        return destination / (product + '-setup')

    def test_archives_are_reproducible_and_contain_only_regular_files(self):
        self.assertEqual(bundles.build(ROOT, self.case / 'again'), self.digests)
        self.assertEqual(len(self.digests), 5)
        for name, digest in self.digests.items():
            path = self.archives / name
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
            with zipfile.ZipFile(path) as archive:
                self.assertEqual(archive.namelist(), sorted(archive.namelist()))
                self.assertTrue(all((entry.external_attr >> 16) & 0o170000 == 0o100000 for entry in archive.infolist()))

    def test_each_subset_installs_and_runs_without_the_source_checkout(self):
        for identifier in ('blog', 'presentation', 'training', 'infographic'):
            with self.subTest(studio=identifier):
                source = self.unpack(identifier + '-studio')
                result = self.run_setup(source)
                self.assertIn(identifier, result['studios'])
                current = self.home / '.local/share' / (identifier + '-studio') / 'current'
                scripts = 'runner' if identifier == 'infographic' else 'scripts'
                self.assertTrue((current / scripts / 'studio_core/server.py').is_file())
                for asset in ('index.html', 'app.js', 'home.css', 'style.css'):
                    self.assertTrue((current / scripts / 'studio_core/setup_web' / asset).is_file())
                self.assertFalse(any(path.is_symlink() for path in current.resolve().rglob('*')))
                shutil.rmtree(source)
                native = current / ('scripts/start_studio.py' if identifier == 'blog' else 'runner/studio.py')
                done = subprocess.run([sys.executable, str(native), '--help'], env=self.env,
                                      capture_output=True, text=True, timeout=20)
                self.assertEqual(done.returncode, 0, done.stderr)
        command = self.home / '.local/bin/marketing-studio'
        done = subprocess.run([str(command), 'status', '--json'], env=self.env,
                              capture_output=True, text=True, timeout=20)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(len(json.loads(done.stdout)['studios']), 4)

    def test_repeat_install_and_uninstall_preserve_native_settings_and_studios(self):
        source = self.unpack('marketing-studio')
        sentinels = []
        for identifier in ('blog', 'presentation', 'training'):
            path = self.home / '.local/share' / (identifier + '-studio') / 'workspace.json'
            path.parent.mkdir(parents=True)
            path.write_bytes(b'{"synthetic": "keep this workspace"}\n')
            sentinels.append(path)
        first = self.run_setup(source)
        data = self.home / '.local/share/marketing-studio'
        key = os.readlink(data / 'current')
        previous = json.loads((data / 'installation.json').read_text())['previous']
        self.run_setup(source)
        self.assertEqual(os.readlink(data / 'current'), key)
        self.assertEqual(json.loads((data / 'installation.json').read_text())['previous'], previous)
        self.run_setup(source, 'uninstall')
        self.assertFalse((data / 'current').exists())
        self.assertFalse((self.home / '.local/bin/marketing-studio').exists())
        for path in sentinels:
            self.assertEqual(path.read_bytes(), b'{"synthetic": "keep this workspace"}\n')
            self.assertTrue((path.parent / 'current').is_dir())

    def test_rollback_restores_the_previous_suite_and_native_pointers(self):
        source = self.case / 'source'
        bundles.materialize(ROOT, source, ['presentation'])
        self.run_setup(source)
        data = self.home / '.local/share/marketing-studio'
        before = (data / 'installation.json').read_bytes()
        previous = os.readlink(data / 'current')
        native = os.readlink(self.home / '.local/share/presentation-studio/current')
        (source / 'VERSION').write_text('4.0.1\n')
        self.run_setup(source)
        self.assertNotEqual(os.readlink(data / 'current'), previous)
        self.run_setup(source, 'rollback')
        self.assertEqual((data / 'installation.json').read_bytes(), before)
        self.assertEqual(os.readlink(data / 'current'), previous)
        self.assertEqual(os.readlink(self.home / '.local/share/presentation-studio/current'), native)

    def test_tampering_and_live_studios_are_refused(self):
        source = self.unpack('marketing-studio')
        (source / 'marketing_studio/cli.py').write_text('# changed')
        self.assertIn('bundle changed', self.run_setup(source, success=False).stderr)
        source2 = self.case / 'clean-source'
        bundles.materialize(ROOT, source2, ['training'])
        pid = self.home / '.local/share/training-studio/runner.pid'
        pid.parent.mkdir(parents=True)
        pid.write_text(str(os.getpid()))
        self.assertIn('is open', self.run_setup(source2, success=False).stderr)
        self.assertFalse((self.home / '.local/share/training-studio/current').exists())

    def test_partial_failure_restores_preexisting_launchers(self):
        source = self.case / 'source'
        bundles.materialize(ROOT, source, ['presentation', 'training'])
        self.run_setup(source, '--studios', 'presentation')
        data = self.home / '.local/share/marketing-studio'
        previous = (data / 'installation.json').read_bytes()
        pointer = os.readlink(data / 'current')
        (source / 'studios/training/installer/install.py').write_text('raise SystemExit(9)\n')
        self.run_setup(source, '--studios', 'presentation', 'training', success=False)
        self.assertEqual((data / 'installation.json').read_bytes(), previous)
        self.assertEqual(os.readlink(data / 'current'), pointer)
        self.assertFalse((self.home / '.local/share/training-studio/current').exists())


if __name__ == '__main__':
    unittest.main()
