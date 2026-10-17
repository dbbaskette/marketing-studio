"""Release preparation and offline install contracts; no network or real user state."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

import marketing_studio
from studio_core import bundles, distribution, offline_install, runtime

ROOT = Path(__file__).resolve().parents[1]


def installer():
    spec = importlib.util.spec_from_file_location('release_installer', ROOT / 'installer/install.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='marketing-release-', dir='/tmp')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()

    def archive(self, entries):
        path = self.root / 'input.tar.gz'
        with tarfile.open(path, 'w:gz') as archive:
            for name, data, link in entries:
                member = tarfile.TarInfo(name)
                member.mode = 0o755
                if link:
                    member.type = tarfile.SYMTYPE
                    member.linkname = link
                    archive.addfile(member)
                else:
                    member.size = len(data)
                    archive.addfile(member, io.BytesIO(data))
        return path

    def test_private_runtime_links_are_flattened_and_licenses_kept(self):
        archive = self.archive([('python/bin/python3.13', b'python', None),
                                ('python/bin/python3', b'', 'python3.13'),
                                ('python/LICENSE', b'license', None)])
        output = self.root / 'python'
        distribution.unpack(archive, output)
        self.assertFalse((output / 'bin/python3').is_symlink())
        self.assertEqual((output / 'bin/python3').read_bytes(), b'python')
        self.assertTrue(os.access(output / 'bin/python3', os.X_OK))
        self.assertEqual((output / 'LICENSE').read_bytes(), b'license')

    def test_archive_escape_and_cyclic_links_are_refused(self):
        for index, entries in enumerate([
            [('python/../../outside', b'bad', None)],
            [('python/bin/python3', b'', '../../../outside')],
            [('python/a', b'', 'b'), ('python/b', b'', 'a')],
        ]):
            with self.subTest(entries=entries):
                with self.assertRaises(ValueError):
                    distribution.unpack(self.archive(entries), self.root / str(index))
        self.assertFalse((self.root / 'outside').exists())

    def test_cached_runtime_is_verified_before_use(self):
        cache = self.root / 'cache'
        cache.mkdir()
        sha = hashlib.sha256(b'expected').hexdigest()
        (cache / sha).write_bytes(b'damaged')
        with mock.patch('urllib.request.urlopen', side_effect=AssertionError('Network used')):
            with self.assertRaisesRegex(ValueError, 'checksum'):
                distribution.download({'sha256': sha, 'url': 'https://example.com/runtime'}, cache)

    def test_node_bundle_contains_runtime_and_license_without_npm(self):
        archive = self.archive([('node/bin/node', b'node', None), ('node/LICENSE', b'license', None),
                                ('node/lib/node_modules/npm/index.js', b'not a runtime dependency', None)])
        output = self.root / 'node'
        distribution.unpack(archive, output, node=True)
        self.assertEqual(sorted(p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()),
                         ['LICENSE', 'bin/node'])

    def test_linux_terminal_database_is_not_needed_in_browser_studio_bundle(self):
        archive = self.archive([('python/bin/python3', b'python', None),
                                ('python/share/terminfo/a/ansi', b'unused', None),
                                ('python/share/terminfo/a/ANSI', b'unused', None)])
        output = self.root / 'python'
        distribution.unpack(archive, output)
        self.assertTrue((output / 'bin/python3').is_file())
        self.assertFalse((output / 'share/terminfo').exists())

    def test_installer_honors_shared_assistant_before_detecting_other_clis(self):
        config = self.root / 'shared.json'
        config.write_text('{"schema":1,"assistant":{"agent":"claude"}}')
        with mock.patch.dict(os.environ, {'STUDIOS_CONFIG': str(config)}), mock.patch('shutil.which', return_value='/synthetic/codex'):
            self.assertEqual(runtime.assistant_target(self.root), 'claude')

    def test_private_path_precedes_host_tools_in_generated_launchers(self):
        private = self.root / 'runtime'
        (private / 'node/bin').mkdir(parents=True)
        (private / 'node/bin/node').touch()
        (private / 'platform').write_text(distribution.host_platform())
        with mock.patch.object(runtime.sys, 'executable', str(private / 'python/bin/python3')):
            path = runtime.shell_path()
        self.assertIn(str(private / 'node/bin'), path)
        self.assertTrue(path.endswith(':"$PATH"\n'))


class OfflineInstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='marketing-offline-', dir='/tmp')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.source, self.home = self.root / 'source', self.root / 'home'
        self.home.mkdir()
        bundles.materialize(ROOT, self.source, ['presentation'])
        for relative in ('runtime/python/bin/python3', 'runtime/node/bin/node'):
            path = self.source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('#!/bin/sh\nexit 0\n')
            path.chmod(0o755)
        (self.source / 'runtime/platform').write_text(distribution.host_platform())
        self.record = {'schema': 1, 'platform': distribution.host_platform(), 'companions': {}}
        for name in ('harness-research', 'harness-slides'):
            folder = self.source / 'companions' / name
            folder.mkdir(parents=True)
            (folder / 'SKILL.md').write_text('Synthetic companion')
            (folder / 'package.json').write_text('{"version":"1.0.0"}')
            self.record['companions'][name] = {'version': '1.0.0', 'id': '1.0.0-' + 'a' * 20}
        (self.source / 'distribution.json').write_text(json.dumps(self.record))
        self.module = installer()
        self.data = self.home / '.local/share/marketing-studio'

    def install(self):
        with mock.patch.object(self.module, 'run_native', return_value={'installed': True}):
            return self.module.install(self.source, self.home, self.data, ['presentation'], 'codex', 'install')

    def test_offline_install_has_no_fetch_npm_or_provider_calls(self):
        with mock.patch('subprocess.run', side_effect=AssertionError('External command used')):
            self.install()
        current = self.home / '.agents/skills/harness-slides'
        self.assertEqual(json.loads((current / 'package.json').read_text())['version'], '1.0.0')
        launcher = (self.data / 'marketing-studio').read_text()
        self.assertIn(str(self.data / 'versions'), launcher)
        self.assertNotIn(str(self.source), launcher)
        self.assertIn('runtime/node/bin', launcher)
        self.assertFalse((self.home / '.claude/skills/harness-slides').exists())

    def test_wrong_platform_and_unrelated_skills_fail_before_installing(self):
        self.record['platform'] = 'unsupported-platform'
        (self.source / 'distribution.json').write_text(json.dumps(self.record))
        with self.assertRaisesRegex(ValueError, 'another platform'):
            self.install()
        self.assertFalse(self.data.exists())
        self.record['platform'] = distribution.host_platform()
        (self.source / 'distribution.json').write_text(json.dumps(self.record))
        skill = self.home / '.agents/skills/harness-slides'
        skill.mkdir(parents=True)
        sentinel = skill / 'keep'
        sentinel.write_text('preserved')
        with self.assertRaisesRegex(ValueError, 'unmanaged path|unrelated skill|unmanaged folder'):
            self.install()
        self.assertEqual(sentinel.read_text(), 'preserved')
        self.assertFalse((self.data / 'current').exists())

    def test_failure_restores_all_companion_and_suite_pointers(self):
        original = self.module.link
        def fail(path, target):
            if path == self.data / 'current':
                raise OSError('Synthetic late failure')
            return original(path, target)
        with mock.patch.object(self.module, 'link', side_effect=fail):
            with self.assertRaisesRegex(OSError, 'late failure'):
                self.install()
        for path in offline_install.managed_paths(self.home, ['presentation'], 'codex'):
            self.assertFalse(path.exists() or path.is_symlink(), str(path))
        self.assertFalse((self.data / 'installation.json').exists())

    def test_newer_independent_companions_are_kept(self):
        current = offline_install.shared_root(self.home, 'harness-slides') / 'current'
        newer = current.parent / 'versions/2.0.0-newer'
        newer.mkdir(parents=True)
        (newer / 'package.json').write_text('{"version":"2.0.0"}')
        current.symlink_to('versions/2.0.0-newer')
        self.install()
        self.assertEqual(current.resolve(), newer)
        self.assertEqual((self.home / '.agents/skills/harness-slides').resolve(), newer)

    def test_existing_upstream_lock_refuses_changes_and_is_preserved(self):
        root = offline_install.shared_root(self.home, 'harness-research')
        root.mkdir(parents=True)
        lock = root / '.install-lock'
        lock.write_text('another installer')
        with self.assertRaisesRegex(ValueError, 'in progress'):
            self.install()
        self.assertEqual(lock.read_text(), 'another installer')
        self.assertFalse((self.data / 'current').exists())

    def test_same_upstream_revision_without_dependencies_is_preserved_beside_bundle(self):
        name = 'harness-slides'
        root = offline_install.shared_root(self.home, name)
        previous = root / 'versions' / self.record['companions'][name]['id']
        previous.mkdir(parents=True)
        (previous / 'package.json').write_text('{"version":"1.0.0"}')
        (root / 'current').symlink_to('versions/' + previous.name)
        self.install()
        self.assertTrue(previous.is_dir())
        self.assertNotEqual((root / 'current').resolve(), previous)
        self.assertIn('-bundle-', (root / 'current').resolve().name)

    def test_update_and_rollback_restore_companion_versions(self):
        self.install()
        current = offline_install.shared_root(self.home, 'harness-slides') / 'current'
        before = os.readlink(current)
        self.record['companions']['harness-slides'] = {'version': '1.1.0', 'id': '1.1.0-' + 'b' * 20}
        (self.source / 'distribution.json').write_text(json.dumps(self.record))
        (self.source / 'companions/harness-slides/package.json').write_text('{"version":"1.1.0"}')
        self.install()
        self.assertNotEqual(os.readlink(current), before)
        previous = json.loads((self.data / 'installation.json').read_text())['previous']
        permitted = [*self.module.managed_paths(self.home, previous['studios'], self.data),
                     *offline_install.managed_paths(self.home, previous['studios'], 'both')]
        with offline_install.locked(self.home, previous['studios']):
            self.module.restore(previous['paths'], permitted)
        self.assertEqual(os.readlink(current), before)

    def test_tampered_runtime_is_rejected_by_bundle_manifest(self):
        archive = self.root / 'archive'
        result = bundles.build(self.source, archive, selection=['presentation'])
        import zipfile
        with zipfile.ZipFile(archive / next(iter(result))) as source:
            source.extractall(self.root / 'unpacked')
        unpacked = self.root / 'unpacked/marketing-studio-setup'
        (unpacked / 'runtime/node/bin/node').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'bundle changed'):
            self.module.verify_bundle(unpacked)


if __name__ == '__main__':
    unittest.main()
