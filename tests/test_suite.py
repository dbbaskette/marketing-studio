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
                for guide in ('incremental-workflow.md', 'research-synthesis.md', 'audit-integration-evidence.md'):
                    self.assertIn('docs/' + guide, payload)
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

    GONE = ('The earlier version is no longer on this computer: an update keeps only the newest. '
            'Install the release you want instead. Nothing was changed.')
    LATER = {'blog': 'skills/blog-studio/SKILL.md', 'presentation': 'skills/presentation-studio/VERSION',
             'training': 'skills/training-studio/VERSION', 'infographic': 'VERSION'}

    def later(self, source, *studios):
        """Turn a source into a later release of the suite and of each studio named."""
        (source / 'VERSION').write_text('9.9.9\n')
        for identifier in studios:
            path = source / 'studios' / identifier / self.LATER[identifier]
            path.write_text(path.read_text() + '\nA later release.\n' if identifier == 'blog' else '9.9.9\n')

    def versions(self, tool):
        return sorted(path.name for path in (self.home / '.local/share' / tool / 'versions').iterdir())

    def keep_from_removal(self, folder):
        """Make a folder one that cannot be removed, and put that right when the test ends."""
        folders = [folder, *(path for path in folder.rglob('*') if path.is_dir())]
        for path in folders:
            path.chmod(0o555)
        self.addCleanup(lambda: [path.chmod(0o755) for path in folders if path.is_dir()])

    def written(self):
        """Every launcher, opener and command wrapper the installers wrote: {path: bytes}."""
        share = self.home / '.local/share'
        found = [path for folder in share.iterdir() if folder.name.endswith('-studio')
                 for path in folder.iterdir() if path.is_file() and path.read_bytes().startswith(b'#!')]
        for folder in (self.home / 'Applications', self.home / '.local/bin'):
            found += [path for path in folder.iterdir()] if folder.is_dir() else []
        return {path: path.read_bytes() for path in found}

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

    def test_an_update_keeps_one_version_of_everything_and_nothing_names_a_version_folder(self):
        studios = ('blog', 'presentation', 'training', 'infographic')
        tools = ['marketing-studio', *(identifier + '-studio' for identifier in studios)]
        source = self.case / 'source'
        bundles.materialize(ROOT, source, list(studios))
        first = self.run_setup(source)
        share = self.home.resolve() / '.local/share'   # the installers name the real home
        before = self.written()
        self.assertGreaterEqual(len(before), 2 + 2 * len(studios))
        old = {tool: (share / tool / 'current').resolve() for tool in tools}
        # What an interrupted install and someone's own link can leave beside the versions.
        outside = self.case / 'kept elsewhere'
        outside.mkdir()
        (outside / 'mine.txt').write_text('Not the installer\'s.')
        for tool in ('marketing-studio', 'training-studio'):
            (share / tool / 'versions/linked').symlink_to(outside, target_is_directory=True)
            (share / tool / 'versions/.pending-0123abcd').mkdir()
        self.later(source, *studios)
        second = self.run_setup(source)
        # One folder each, the new one; every older one and every leftover went.
        for tool in tools:
            active = (share / tool / 'current').resolve()
            self.assertNotEqual(active, old[tool], tool)
            self.assertEqual(self.versions(tool), [active.name], tool)
            self.assertFalse(old[tool].exists(), tool)
        self.assertEqual((outside / 'mine.txt').read_text(), "Not the installer's.", 'a link is never followed')
        self.assertEqual(sorted(second['removed']), sorted(
            str(share / 'marketing-studio/versions' / name) for name in (first['id'], 'linked', '.pending-0123abcd')))
        self.assertEqual(second['retained'], [])
        self.assertEqual((second['runtime'], second['versionDirectory']),
                         (str(share / 'marketing-studio/current'), str(share / 'marketing-studio/versions' / second['id'])))
        for identifier in studios:
            cleaned = second['results'][identifier]
            self.assertIn(str(old[identifier + '-studio']), cleaned['removed'], identifier)
            self.assertEqual(cleaned['retained'], [], identifier)
            self.assertEqual(cleaned['runtime'], str(share / (identifier + '-studio') / 'current'), identifier)
        self.assertEqual(len(second['results']['training']['removed']), 3)
        # Nothing the installers wrote names a version folder, so the update rewrote nothing
        # that an earlier launcher, link or record depends on.
        after = self.written()
        self.assertEqual(after, before, 'launchers and command wrappers are the same bytes')
        for path, data in after.items():
            self.assertNotIn(b'versions/', data, str(path))
        self.assertEqual(os.readlink(self.home / '.local/bin/marketing-studio'), str(share / 'marketing-studio/marketing-studio'))
        linked = [path for folder in ('.claude/skills', '.agents/skills') if (self.home / folder).is_dir()
                  for path in (self.home / folder).iterdir()]
        self.assertEqual(len(linked), len(studios))
        for path in linked:
            self.assertEqual(os.readlink(path), str(share / path.name / 'current'))
            self.assertTrue((path / 'SKILL.md').is_file(), str(path))
        for tool in tools:
            state = json.loads((share / tool / 'installation.json').read_text())
            # A rollback record holds the pointer it would put back, and nothing else names a folder.
            kept = {key: value for key, value in state.items() if key not in ('previous', 'original')}
            self.assertNotIn('versions/', json.dumps(kept), tool)
        # And all of it still opens what was installed.
        command = self.home / '.local/bin/marketing-studio'
        done = subprocess.run([str(command), 'status', '--json'], env=self.env, capture_output=True, text=True, timeout=20)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(all(studio['installed'] for studio in json.loads(done.stdout)['studios']))
        for identifier in studios:
            helper = share / (identifier + '-studio') / identifier
            done = subprocess.run(['/bin/sh', str(helper), '--help'], env=self.env, capture_output=True, text=True, timeout=30)
            self.assertEqual(done.returncode, 0, identifier + ': ' + done.stderr)

    def test_a_version_a_studio_not_renewed_still_opens_with_is_kept_until_it_is_installed(self):
        source = self.case / 'source'
        bundles.materialize(ROOT, source, ['presentation', 'infographic'])
        first = self.run_setup(source)
        share = self.home.resolve() / '.local/share'
        old = share / 'marketing-studio/versions' / first['id']
        # As an earlier installer left it: the launcher names the Python inside the suite's version.
        opener = share / 'infographic-studio/studio'
        opener.write_text(opener.read_text().replace('exec ', 'exec ' + str(old / 'runtime/python/bin/python3') + ' # ', 1))
        self.later(source, 'presentation')
        second = self.run_setup(source, '--studios', 'presentation')
        self.assertEqual(second['removed'], [])
        self.assertEqual([kept['path'] for kept in second['retained']], [str(old)])
        self.assertIn('Infographic Studio still opens with the Python inside it', second['retained'][0]['reason'])
        self.assertTrue((old / 'marketing-studio').is_file())
        self.assertEqual(len(self.versions('presentation-studio')), 1)
        # Installing that studio renews its launcher, and the older version then goes.
        third = self.run_setup(source)
        self.assertIn(str(old), third['removed'])
        self.assertEqual(self.versions('marketing-studio'), [third['id']])
        self.assertNotIn('versions/', opener.read_text())

    def test_rollback_after_an_update_refuses_and_changes_nothing(self):
        source = self.case / 'source'
        bundles.materialize(ROOT, source, ['presentation'])
        self.run_setup(source)
        data = self.home / '.local/share/marketing-studio'
        self.later(source, 'presentation')
        self.run_setup(source)
        native = self.home / '.local/share/presentation-studio'
        pointers = {path: os.readlink(path) for path in (data / 'current', native / 'current')}
        records = {path: path.read_bytes() for path in (data / 'installation.json', native / 'installation.json')}
        launchers = self.written()
        refused = self.run_setup(source, 'rollback', success=False)
        self.assertEqual(json.loads(refused.stderr.splitlines()[-1]), {'error': self.GONE})
        self.assertEqual({path: os.readlink(path) for path in pointers}, pointers)
        self.assertEqual({path: path.read_bytes() for path in records}, records)
        self.assertEqual(self.written(), launchers)
        self.assertEqual(len(self.versions('marketing-studio')), 1)
        self.assertEqual(len(self.versions('presentation-studio')), 1)

    def test_rollback_restores_the_previous_suite_and_native_pointers_that_are_still_there(self):
        source = self.case / 'source'
        bundles.materialize(ROOT, source, ['presentation'])
        self.run_setup(source)
        data = self.home / '.local/share/marketing-studio'
        before = (data / 'installation.json').read_bytes()
        previous = os.readlink(data / 'current')
        native = os.readlink(self.home / '.local/share/presentation-studio/current')
        for folder in (previous, native):
            self.keep_from_removal(Path(folder))
        self.later(source, 'presentation')
        updated = self.run_setup(source)
        self.assertEqual([kept['path'] for kept in updated['retained']], [previous])
        self.assertEqual([kept['path'] for kept in updated['results']['presentation']['retained']], [native])
        self.assertNotEqual(os.readlink(data / 'current'), previous)
        self.assertNotEqual(os.readlink(self.home / '.local/share/presentation-studio/current'), native)
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
        native = self.home / '.local/share/presentation-studio'
        record, active, launchers = (native / 'installation.json').read_bytes(), os.readlink(native / 'current'), self.written()
        # A later release whose first studio installs, moving its pointer, before the second fails.
        self.later(source, 'presentation')
        (source / 'studios/training/installer/install.py').write_text('raise SystemExit(9)\n')
        self.run_setup(source, '--studios', 'presentation', 'training', success=False)
        self.assertEqual((data / 'installation.json').read_bytes(), previous)
        self.assertEqual(os.readlink(data / 'current'), pointer)
        self.assertFalse((self.home / '.local/share/training-studio/current').exists())
        # Nothing was removed by the install that failed: every pointer that was put back
        # names a version that is still whole, and still opens.
        self.assertEqual(os.readlink(native / 'current'), active)
        self.assertEqual((native / 'installation.json').read_bytes(), record)
        self.assertTrue((Path(pointer) / 'marketing-studio').is_file())
        self.assertTrue((Path(active) / 'runner/studio.py').is_file())
        self.assertIn(Path(active).name, self.versions('presentation-studio'))
        self.assertEqual(len(self.versions('presentation-studio')), 2, 'the staged newer one is still beside it')
        self.assertEqual(self.written(), launchers)
        done = subprocess.run(['/bin/sh', str(native / 'presentation'), '--help'], env=self.env,
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(done.returncode, 0, done.stderr)
        done = subprocess.run([str(self.home / '.local/bin/marketing-studio'), 'status', '--json'], env=self.env,
                              capture_output=True, text=True, timeout=20)
        self.assertEqual(done.returncode, 0, done.stderr)


if __name__ == '__main__':
    unittest.main()
