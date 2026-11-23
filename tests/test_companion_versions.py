"""Companions from `main` against synthetic Git repositories; no network or installed skills.

There are no release tags and no locks: a companion is installed and updated from its
repository's `main`, checked file for file, with the pin's version as a floor only.
"""
import importlib.util
import json
import os
import shutil
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import marketing_studio  # noqa: F401
from studio_core import companions

ROOT = Path(__file__).resolve().parents[1]


def updater():
    spec = importlib.util.spec_from_file_location('companion_updater', ROOT / 'scripts/update_companions.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CompanionMainTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='studio-companion-tests-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.repo = self.root / 'remote'
        self.repo.mkdir()
        patcher = mock.patch.dict(os.environ, {'GIT_CONFIG_GLOBAL': os.devnull,
                                               'GIT_CONFIG_NOSYSTEM': '1'})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.name', 'Synthetic Release')
        self.git('config', 'user.email', 'synthetic@example.invalid')
        self.first = self.commit('1.0.0')
        self.pin = {'repository': str(self.repo), 'branch': 'main', 'version': '1.0.0',
                    'stub': 'bootstrap/SKILL.md', 'installer': 'scripts/install.mjs',
                    'requirement': '>=1.0.0'}

    def git(self, *arguments):
        return subprocess.check_output(['git', *arguments], cwd=self.repo, text=True,
                                       stderr=subprocess.PIPE).strip()

    def commit(self, version, tag=None):
        (self.repo / 'package.json').write_text(json.dumps({'version': version}))
        (self.repo / 'bootstrap').mkdir(exist_ok=True)
        (self.repo / 'bootstrap/SKILL.md').write_text('---\nname: harness-research\n---\n')
        (self.repo / 'scripts').mkdir(exist_ok=True)
        (self.repo / 'scripts/install.mjs').write_text('// Synthetic installer; never execute.\n')
        self.git('add', '-A')
        self.git('commit', '-qm', 'Synthetic ' + version)
        if tag:
            self.git('tag', tag)
        return self.git('rev-parse', 'HEAD')

    def pinfile(self, pin=None):
        path = self.root / 'companions.json'
        path.write_text(json.dumps({'schema': 1, 'unrelated': {'keep': True},
                                   'companions': {'harness-research': pin or self.pin}}))
        return path

    def test_main_is_installed_whatever_tags_there_are(self):
        self.commit('1.1.0', tag='v1.1.0')
        newest = self.commit('1.2.0')   # main moved past the last tag
        folder, fetched = companions.fetch_main('harness-research', self.pin, self.root / 'install')
        self.assertEqual((fetched['version'], fetched['commit']), ('1.2.0', newest))
        self.assertEqual(fetched['sha256'], companions.tree_digest(folder))
        self.assertFalse((folder / '.git').exists())
        self.assertEqual(companions.main_commit(self.pin), newest)

    def test_pins_name_main_and_a_floor_only(self):
        self.assertEqual(companions.read_pins(self.pinfile())['harness-research']['branch'], 'main')
        without = {key: value for key, value in self.pin.items() if key != 'branch'}
        self.assertEqual(companions.read_pins(self.pinfile(without))['harness-research']['branch'], 'main')
        for wrong in ({'branch': 'v1.0.0'}, {'branch': 'release'}, {'requirement': '>=2.0.0'},
                      {'requirement': 'latest'}, {'commit': 'not-a-commit'}, {'stub': '../SKILL.md'}):
            with self.subTest(wrong=wrong), self.assertRaises(ValueError):
                companions.read_pins(self.pinfile({**self.pin, **wrong}))

    def test_a_main_older_than_the_floor_is_refused_with_an_update_sentence(self):
        floor = {**self.pin, 'version': '2.0.0', 'requirement': '>=2.0.0'}
        with self.assertRaisesRegex(ValueError, 'older than the 2.0.0 this version needs'):
            companions.fetch_main('harness-research', floor, self.root / 'install')
        self.assertEqual(list((self.root / 'install/companions/harness-research').iterdir()), [])

    def test_unsafe_links_are_refused_before_anything_is_read_or_run(self):
        (self.repo / 'outside').symlink_to('/etc/passwd')
        self.git('add', '-A'); self.git('commit', '-qm', 'Unsafe package link')
        with self.assertRaisesRegex(ValueError, 'link or a special file'):
            companions.fetch_main('harness-research', self.pin, self.root / 'install')

    def test_a_fetched_copy_that_changed_is_refused_rather_than_used(self):
        folder, _ = companions.fetch_main('harness-research', self.pin, self.root / 'install')
        (folder / 'scripts/install.mjs').write_text('// Changed after the check.\n')
        with self.assertRaisesRegex(ValueError, 'has changed since it was fetched'):
            companions.fetch_main('harness-research', self.pin, self.root / 'install')

    def test_hooks_are_never_placed_or_run(self):
        hooks = self.root / 'hooks'
        hooks.mkdir()
        (hooks / 'post-checkout').write_text('#!/bin/sh\ntouch "$0.ran"\n')
        (hooks / 'post-checkout').chmod(0o755)
        with mock.patch.dict(os.environ, {'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'core.hooksPath',
                                          'GIT_CONFIG_VALUE_0': str(hooks)}):
            companions.fetch_main('harness-research', self.pin, self.root / 'install')
        self.assertFalse((hooks / 'post-checkout.ran').exists())

    def test_an_unreachable_main_is_explicit(self):
        with mock.patch.object(companions, 'git', return_value=(128, 'Could not resolve host')):
            with self.assertRaisesRegex(ValueError, 'main branch of .* could not be read'):
                companions.main_commit(self.pin)

    def test_the_report_reads_main_and_writes_nothing(self):
        newest = self.commit('1.1.0')
        path = self.pinfile()
        before = path.read_bytes()
        result = updater().report(path)
        self.assertEqual(path.read_bytes(), before)
        found = result['companions']['harness-research']
        self.assertEqual((found['version'], found['commit'], found['floor']), ('1.1.0', newest, '1.0.0'))
        self.assertEqual(result['short'], [])
        short = updater().report(self.pinfile({**self.pin, 'version': '3.0.0', 'requirement': '>=3.0.0'}))
        self.assertEqual(short['short'], ['harness-research'])

    def bring(self, found, agree, declined=None, pin=None, update=False, state=None):
        self.root_state = state if state is not None else {}
        with mock.patch.object(companions, 'companion_found', return_value=found), \
                mock.patch.object(companions, 'node_version', return_value='v24.0.0'):
            return companions.bring_companions(self.root / 'home', self.root / 'install', ['codex'],
                {'harness-research': pin or self.pin}, agree, self.root_state, declined,
                update=update)['harness-research']

    def test_skip_and_noninteractive_ask_never_query_or_fetch(self):
        for declined in ('skipped', 'nobody to ask'):
            with mock.patch.object(companions, 'git', side_effect=AssertionError('Lookup used')):
                self.assertEqual(self.bring({'codex': None}, lambda *args: False, declined)['state'], 'waiting')

    def test_declining_does_not_download_source_or_run_installers(self):
        with mock.patch.object(companions, 'fetch_revision', side_effect=AssertionError('Source fetched')):
            result = self.bring({'codex': None}, lambda *args: False, 'declined')
        self.assertEqual((result['state'], result['wanted']), ('waiting', '1.0.0'))
        self.assertFalse((self.root / 'install').exists())

    def test_install_brings_main_once_agreed_and_records_its_commit(self):
        newest = self.commit('1.1.0')
        for found in ({'codex': None}, {'codex': '0.9.0'}):
            with self.subTest(found=found), \
                    mock.patch.object(companions, 'run_companion', return_value={'state': 'installed'}) as run:
                result = self.bring(found, lambda *args: True)
            self.assertEqual((result['wanted'], result['state'], result['commit']), ('1.1.0', 'installed', newest))
            installed = run.call_args.args[1]
            self.assertEqual((installed['version'], installed['commit']), ('1.1.0', newest))
            recorded = self.root_state['companions']['harness-research']
            self.assertEqual((recorded['version'], recorded['commit'], recorded['sha256'], recorded['branch']),
                             ('1.1.0', newest, installed['sha256'], 'main'))

    def test_an_installed_copy_meeting_the_floor_is_left_alone_without_update(self):
        self.commit('1.1.0')
        with mock.patch.object(companions, 'git', side_effect=AssertionError('Lookup used')):
            for found in ({'codex': '1.0.0'}, {'codex': '2.0.0'}):
                with self.subTest(found=found):
                    result = self.bring(found, lambda *args: True)
                    self.assertEqual(result['state'], 'left alone')
                    self.assertEqual(self.root_state, {})

    def test_an_update_installs_main_when_it_moved_and_not_otherwise(self):
        state = {'companions': {'harness-research': {'commit': self.first, 'version': '1.0.0'}}}
        with mock.patch.object(companions, 'run_companion', side_effect=AssertionError('Installer ran')):
            result = self.bring({'codex': '1.0.0'}, lambda *args: True, update=True, state=state)
        self.assertEqual(result['state'], 'left alone')   # main is where it was installed from
        moved = self.commit('1.0.1')
        with mock.patch.object(companions, 'run_companion', return_value={'state': 'installed'}):
            result = self.bring({'codex': '1.0.0'}, lambda *args: True, update=True, state=state)
        self.assertEqual((result['state'], result['commit']), ('installed', moved))
        self.assertEqual(state['companions']['harness-research']['commit'], moved)

    def test_an_update_of_a_copy_not_installed_from_here_takes_main(self):
        newest = self.commit('1.0.1')
        with mock.patch.object(companions, 'run_companion', return_value={'state': 'installed'}):
            result = self.bring({'codex': '5.0.0'}, lambda *args: True, update=True)
        self.assertEqual((result['state'], result['commit']), ('installed', newest))

    def test_a_main_below_the_floor_is_refused_and_nothing_runs(self):
        floor = {**self.pin, 'version': '2.0.0', 'requirement': '>=2.0.0'}
        with mock.patch.object(companions, 'run_companion', side_effect=AssertionError('Installer ran')):
            result = self.bring({'codex': None}, lambda *args: True, pin=floor)
        self.assertEqual(result['state'], 'refused')
        self.assertIn('older than the 2.0.0 this version needs', result['detail'])
        self.assertEqual(self.root_state, {})

    def test_a_bundle_record_of_an_exact_commit_is_fetched_exactly(self):
        exported = self.root / 'exported'
        exported.mkdir()
        companions.fetch_revision(str(self.repo), self.first, exported)
        exact = {**self.pin, 'commit': self.first, 'sha256': companions.tree_digest(exported)}
        self.commit('1.5.0')   # main moved on since the bundle was built
        folder, fetched = companions.fetch_main('harness-research', exact, self.root / 'install')
        self.assertEqual((fetched['commit'], fetched['version']), (self.first, '1.0.0'))
        with self.assertRaisesRegex(ValueError, 'not what this installer expects'):
            companions.fetch_main('harness-research', {**exact, 'sha256': '0' * 64}, self.root / 'other')


class BrokenInstallTests(unittest.TestCase):
    """What an installed companion is judged by: a version that cannot be read, a prerelease
    below the floor, and the entry its installer leaves, whatever its line endings."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='studio-companion-installed-')
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name).resolve() / 'home'
        self.checkout = Path(temp.name).resolve() / 'checkout'
        (self.checkout / 'bootstrap').mkdir(parents=True)
        self.stub = '---\nname: harness-research\n---\n\nUse the research helper.\n'
        (self.checkout / 'bootstrap/SKILL.md').write_text(self.stub, encoding='utf-8')
        self.pin = {'repository': 'unused', 'branch': 'main', 'version': '1.3.1',
                    'stub': 'bootstrap/SKILL.md', 'installer': 'scripts/install.mjs',
                    'requirement': '>=1.3.1'}

    def installed(self, package, entry=None):
        skill = companions.skill_link(self.home, 'claude').parent / 'harness-research'
        skill.mkdir(parents=True, exist_ok=True)
        if package is not None:
            (skill / 'package.json').write_bytes(package.encode())
        (skill / 'SKILL.md').write_bytes((self.stub if entry is None else entry).encode())
        return skill

    def test_a_missing_or_corrupt_package_json_is_wanting(self):
        for package in (None, '', '{', '[]', '{"name": "x"}', '{"version": 3}',
                        '{"version": "not a version"}'):
            with self.subTest(package=package):
                self.installed(package)
                found = companions.companion_found(self.home, ['claude'], 'harness-research')
                self.assertEqual(found, {'claude': ''})
                self.assertEqual(companions.wanting(found, '1.3.1'), ['claude'])
                shutil.rmtree(self.home)
        self.installed('{"version": "1.3.1"}')
        found = companions.companion_found(self.home, ['claude'], 'harness-research')
        self.assertEqual(companions.wanting(found, '1.3.1'), [])

    def test_a_broken_copy_is_offered_again_rather_than_left_alone(self):
        asked = []
        with mock.patch.object(companions, 'companion_found', return_value={'claude': ''}), \
                mock.patch.object(companions, 'node_version', return_value='v24.0.0'):
            result = companions.bring_companions(self.home, self.home / 'install', ['claude'],
                                                 {'harness-research': self.pin},
                                                 lambda *args: asked.append(args) or False, {},
                                                 'declined')['harness-research']
        self.assertEqual((result['state'], len(asked)), ('waiting', 1))

    def test_a_prerelease_does_not_meet_its_release(self):
        self.assertEqual(companions.wanting({'claude': '1.3.1-alpha.1'}, '1.3.1'), ['claude'])
        self.assertEqual(companions.wanting({'claude': '1.3.1-rc.2'}, '1.3.1'), ['claude'])
        self.assertEqual(companions.wanting({'claude': '1.3.2-alpha.1'}, '1.3.1'), [])
        self.assertEqual(companions.wanting({'claude': '1.3.1'}, '1.3.1'), [])
        folder = self.checkout
        (folder / 'scripts').mkdir()
        (folder / 'scripts/install.mjs').write_text('// Synthetic installer; never execute.\n')
        (folder / 'package.json').write_text(json.dumps({'version': '1.3.1-alpha.1'}))
        with self.assertRaisesRegex(ValueError, 'holds 1.3.1-alpha.1, older than the 1.3.1'):
            companions._checked('harness-research', self.pin, folder)
        path = Path(self.home.parent) / 'companions.json'
        path.write_text(json.dumps({'schema': 1, 'companions': {'harness-research': {
            **self.pin, 'version': '1.3.1-alpha.1'}}}))
        with self.assertRaises(ValueError):
            companions.read_pins(path)

    def run_installer(self):
        done = subprocess.CompletedProcess([], 0, '{}', '')
        with mock.patch.object(companions.shutil, 'which', return_value='/synthetic/node'), \
                mock.patch.object(companions.subprocess, 'run', return_value=done) as ran:
            outcome = companions.run_companion('harness-research', self.pin, self.checkout,
                                               self.home, ['claude'])
        self.assertEqual(ran.call_count, 1)   # the stand-in, never Node
        return outcome

    def test_the_entry_check_tolerates_line_endings_and_trailing_space(self):
        for entry in (self.stub, self.stub.replace('\n', '\r\n'), '﻿' + self.stub,
                      self.stub.replace('---\n', '---  \n') + '\n\n'):
            with self.subTest(entry=entry):
                self.installed('{"version": "1.3.1"}', entry)
                self.assertEqual(self.run_installer()['state'], 'installed')

    def test_a_different_or_missing_entry_still_fails(self):
        self.installed('{"version": "1.3.1"}', self.stub.replace('research helper', 'other helper'))
        self.assertEqual(self.run_installer()['state'], 'failed')
        (self.installed('{"version": "1.3.1"}') / 'SKILL.md').unlink()
        self.assertEqual(self.run_installer()['state'], 'failed')
        self.installed('{"version": "1.3.1-alpha.1"}')
        self.assertEqual(self.run_installer()['state'], 'failed')


class FloorTests(unittest.TestCase):
    def test_the_companions_come_from_main_with_the_floors_marketing_studio_needs(self):
        pins = json.loads((ROOT / 'pins/companions.json').read_text(encoding='utf-8'))
        companion = pins['companions']
        self.assertEqual(set(companion), {'harness-research', 'harness-slides'})
        self.assertEqual({name: (pin['branch'], pin['requirement']) for name, pin in companion.items()},
                         {'harness-research': ('main', '>=1.3.1'), 'harness-slides': ('main', '>=0.19.0')})
        for name, pin in companion.items():
            with self.subTest(companion=name):
                self.assertNotIn('commit', pin)
                self.assertNotIn('sha256', pin)
                self.assertEqual(pin['requirement'], '>=' + pin['version'])
                self.assertEqual(companions.wanting({'claude': pin['version']}, companions.minimum_version(pin)), [])
                self.assertEqual(companions.wanting({'claude': '0.1.0'}, companions.minimum_version(pin)), ['claude'])

    def test_brand_skill_floor_is_not_installed_by_the_installers(self):
        path = ROOT / 'pins/companions.json'
        pins = json.loads(path.read_text(encoding='utf-8'))
        floor = pins['brand_skill']
        self.assertEqual(floor['requirement'], '>=1.4.0')
        for companion in pins['companions'].values():
            self.assertEqual(companion['tested'], floor['tested'])
            self.assertGreaterEqual(companions.as_tuple(companion['tested']), companions.as_tuple(companion['version']))
        self.assertTrue(floor['note'])
        self.assertNotIn('brand_skill', pins['companions'])
        self.assertEqual(sorted(companions.read_pins(path)), ['harness-research', 'harness-slides'])

    def test_no_document_calls_companions_locked_or_pinned_to_a_release(self):
        for path in ('README.md', 'docs/installation.md'):
            text = (ROOT / path).read_text(encoding='utf-8')
            with self.subTest(path=path):
                self.assertNotIn('0.14.1', text)
                self.assertNotIn('locked release', text)
                self.assertNotIn('newest stable tag', text)


if __name__ == '__main__':
    unittest.main()
