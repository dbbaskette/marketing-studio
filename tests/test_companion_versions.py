"""Version resolution against synthetic Git repositories; no network or installed skills."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import marketing_studio
from studio_core import companions

ROOT = Path(__file__).resolve().parents[1]


def updater():
    spec = importlib.util.spec_from_file_location('companion_updater', ROOT / 'scripts/update_companions.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CompanionVersionsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='studio-companion-tests-', dir='/tmp')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.repo = self.root / 'remote'
        self.repo.mkdir()
        patcher = mock.patch.dict(os.environ, {'GIT_CONFIG_GLOBAL': os.devnull,
                                               'GIT_CONFIG_NOSYSTEM': '1'})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Synthetic Release')
        self.git('config', 'user.email', 'synthetic@example.invalid')
        commit = self.release('1.0.0')
        exported = self.root / 'exported'
        exported.mkdir()
        companions.fetch_revision(str(self.repo), commit, exported)
        self.pin = {'repository': str(self.repo), 'version': '1.0.0', 'commit': commit,
                    'sha256': companions.tree_digest(exported), 'stub': 'bootstrap/SKILL.md',
                    'installer': 'scripts/install.mjs', 'requirement': '>=1.0.0'}

    def git(self, *arguments):
        return subprocess.check_output(['git', *arguments], cwd=self.repo, text=True,
                                       stderr=subprocess.PIPE).strip()

    def release(self, version, tag=None, annotated=False):
        (self.repo / 'package.json').write_text(json.dumps({'version': version}))
        (self.repo / 'bootstrap').mkdir(exist_ok=True)
        (self.repo / 'bootstrap/SKILL.md').write_text('---\nname: harness-research\n---\n')
        (self.repo / 'scripts').mkdir(exist_ok=True)
        (self.repo / 'scripts/install.mjs').write_text('// Synthetic installer; never execute.\n')
        self.git('add', '-A')
        self.git('commit', '-qm', 'Synthetic release '+version)
        selected = tag or 'v'+version
        self.git('tag', *(['-a', '-m', 'Synthetic release'] if annotated else []), selected)
        return self.git('rev-parse', 'HEAD')

    def pinfile(self, pin=None):
        path = self.root / 'companions.json'
        path.write_text(json.dumps({'schema': 1, 'unrelated': {'keep': True},
                                   'companions': {'harness-research': pin or self.pin}}))
        return path

    def test_newest_stable_tag_uses_numeric_order_and_annotated_commit(self):
        self.release('1.2.0')
        expected = self.release('1.10.0', annotated=True)
        self.release('99.0.0', tag='v99.0.0-beta')
        self.release('100.0.0', tag='unreleased-example')
        selected = companions.select_release(self.pin)
        self.assertEqual(selected['version'], '1.10.0')
        self.assertEqual(selected['commit'], expected)
        self.assertIsNone(selected['sha256'])
        resolved = companions.lock_companion('harness-research', selected)
        self.assertRegex(resolved['sha256'], r'^[0-9a-f]{64}$')
        self.assertNotEqual(resolved['sha256'], self.pin['sha256'])
        self.assertEqual(self.pin['version'], '1.0.0')

    def test_old_exact_pins_still_do_not_look_up_releases(self):
        pin = {key: value for key, value in self.pin.items() if key != 'requirement'}
        with mock.patch.object(companions, 'git', side_effect=AssertionError('Lookup used')):
            self.assertEqual(companions.resolve_companion('harness-research', pin), pin)
        self.assertEqual(companions.read_pins(self.pinfile(pin))['harness-research'], pin)

    def test_invalid_requirements_and_locks_below_minimum_are_refused(self):
        for requirement in ('latest', '>=1.0', '>1.0.0', '>=1.0.0-beta', '>=2.0.0', None, 1):
            with self.subTest(requirement=requirement), self.assertRaises(ValueError):
                companions.read_pins(self.pinfile({**self.pin, 'requirement': requirement}))

    def test_existing_release_hash_and_tag_cannot_be_silently_replaced(self):
        self.assertEqual(companions.resolve_companion('harness-research', self.pin), self.pin)
        (self.repo / 'changed').write_text('New bytes under the same tag')
        self.git('add', '-A'); self.git('commit', '-qm', 'Changed release')
        self.git('tag', '-f', 'v1.0.0')
        with self.assertRaisesRegex(ValueError, 'tag changed'):
            companions.resolve_companion('harness-research', self.pin)

    def test_moved_tag_after_selection_cannot_change_downloaded_commit(self):
        selected_commit = self.release('1.1.0')
        selected = companions.select_release(self.pin)
        self.release('2.0.0')
        self.git('tag', '-f', 'v1.1.0')
        resolved = companions.lock_companion('harness-research', selected)
        self.assertEqual(resolved['commit'], selected_commit)
        self.assertEqual(resolved['version'], '1.1.0')

    def test_tag_and_package_version_must_agree(self):
        self.release('1.1.0', tag='v2.0.0')
        with self.assertRaisesRegex(ValueError, 'match its tag'):
            companions.resolve_companion('harness-research', self.pin)

    def test_unsafe_source_links_are_refused_before_metadata_is_read(self):
        self.release('1.1.0')
        (self.repo / 'outside').symlink_to('/etc/passwd')
        self.git('add', '-A'); self.git('commit', '-qm', 'Unsafe package link')
        self.git('tag', 'v1.2.0')
        with self.assertRaisesRegex(ValueError, 'link or a special file'):
            companions.resolve_companion('harness-research', self.pin)

    def test_no_matching_tag_and_remote_failure_are_explicit(self):
        with mock.patch.object(companions, 'git', return_value=(0, '')):
            with self.assertRaisesRegex(ValueError, 'No stable'):
                companions.select_release(self.pin)
        with mock.patch.object(companions, 'git', return_value=(1, 'unavailable')):
            with self.assertRaisesRegex(ValueError, 'could not be checked'):
                companions.select_release(self.pin)

    def test_refresh_records_exact_bytes_and_preserves_other_metadata(self):
        self.release('1.1.0')
        path = self.pinfile()
        previous = path.read_bytes()
        result = updater().refresh(path, check=True)
        self.assertFalse(result['written'])
        self.assertEqual(path.read_bytes(), previous)
        result = updater().refresh(path)
        self.assertTrue(result['written'])
        record = json.loads(path.read_text())
        self.assertEqual(record['unrelated'], {'keep': True})
        self.assertEqual(record['companions']['harness-research']['version'], '1.1.0')
        self.assertEqual(record['companions']['harness-research']['requirement'], '>=1.0.0')
        self.assertFalse(updater().refresh(path)['written'])

    def test_failed_refresh_never_replaces_the_lock_file(self):
        self.release('1.1.0', tag='v2.0.0')
        path = self.pinfile()
        previous = path.read_bytes()
        with self.assertRaises(ValueError):
            updater().refresh(path)
        self.assertEqual(path.read_bytes(), previous)

    def bring(self, found, agree, declined=None, pin=None):
        self.root_state = {}
        with mock.patch.object(companions, 'companion_found', return_value=found), \
                mock.patch.object(companions, 'node_version', return_value='v24.0.0'):
            return companions.bring_companions(self.root / 'home', self.root / 'install', ['codex'],
                {'harness-research': pin or self.pin}, agree, self.root_state, declined)['harness-research']

    def offline(self):
        """Release lookups fail as they would offline; fetching an exact commit still works."""
        real = companions.git

        def git(args, cwd):
            if args[0] == 'ls-remote':
                raise AssertionError('Release lookup used')
            return real(args, cwd)
        return mock.patch.object(companions, 'git', side_effect=git)

    def test_skip_and_noninteractive_ask_never_query_or_fetch(self):
        for declined in ('skipped', 'nobody to ask'):
            with mock.patch.object(companions, 'git', side_effect=AssertionError('Lookup used')):
                self.assertEqual(self.bring({'codex': None}, lambda *args: False, declined)['state'], 'waiting')

    def test_declining_does_not_download_source_or_run_installers(self):
        self.release('1.1.0')
        with mock.patch.object(companions, 'fetch_revision', side_effect=AssertionError('Source fetched')):
            result = self.bring({'codex': None}, lambda *args: False, 'declined')
        self.assertEqual(result['state'], 'waiting')
        self.assertEqual(result['wanted'], '1.0.0')
        self.assertFalse((self.root / 'install').exists())

    def test_newer_installed_release_is_never_downgraded(self):
        self.release('1.1.0')
        with mock.patch.object(companions, 'fetch_revision', side_effect=AssertionError('Source fetched')):
            self.assertEqual(self.bring({'codex': '2.0.0'}, lambda *args: True)['state'], 'left alone')

    def test_an_installed_copy_meeting_the_requirement_is_accepted_offline(self):
        newer = {**self.pin, 'version': '1.1.0', 'commit': self.release('1.1.0')}
        with mock.patch.object(companions, 'git', side_effect=AssertionError('Lookup used')):
            for pin in (self.pin, newer):
                with self.subTest(locked=pin['version']):
                    result = self.bring({'codex': '1.0.0'}, lambda *args: True, pin=pin)
                    self.assertEqual(result['state'], 'left alone')
                    self.assertEqual(self.root_state, {})

    def test_install_uses_the_exact_lock_even_when_newer_tags_exist(self):
        self.release('1.1.0')
        for found in ({'codex': None}, {'codex': '0.9.0'}):
            with self.subTest(found=found), self.offline(), \
                    mock.patch.object(companions, 'run_companion', return_value={'state': 'installed'}) as run:
                result = self.bring(found, lambda *args: True)
            self.assertEqual((result['wanted'], result['state']), ('1.0.0', 'installed'))
            self.assertEqual(run.call_args.args[1], self.pin)
            recorded = self.root_state['companions']['harness-research']
            self.assertEqual({key: recorded[key] for key in ('version', 'commit', 'sha256')},
                             {key: self.pin[key] for key in ('version', 'commit', 'sha256')})

    def test_a_lock_whose_source_changed_is_refused_rather_than_recomputed(self):
        changed = {**self.pin, 'sha256': '0' * 64}
        with self.offline(), mock.patch.object(companions, 'run_companion',
                                               side_effect=AssertionError('Installer ran')):
            result = self.bring({'codex': None}, lambda *args: True, pin=changed)
        self.assertEqual(result['state'], 'refused')
        self.assertIn('not what this installer expects', result['detail'])
        self.assertEqual(self.root_state, {})

if __name__ == '__main__':
    unittest.main()
