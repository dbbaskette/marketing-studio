"""Local bundle generation checks: no downloads, installed state, or provider jobs."""
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('presentation_bundle', ROOT / 'scripts/build_presentation_bundle.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class PresentationBundleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='presentation-bundle-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def test_cli_installs_a_source_link_and_repeated_install_preserves_it(self):
        target = builder.install_cli(self.root)
        self.assertEqual(target, self.root / '.local/bin/presentation-studio-package')
        self.assertEqual(target.resolve(), ROOT / 'presentation-studio-package')
        before = target.lstat().st_ino
        self.assertEqual(builder.install_cli(self.root), target)
        self.assertEqual(before, target.lstat().st_ino)

    def test_cli_install_preserves_unrelated_commands_and_broken_links(self):
        target = self.root / '.local/bin/presentation-studio-package'
        target.parent.mkdir(parents=True)
        target.write_text('existing command')
        with self.assertRaisesRegex(ValueError, 'unrelated command'):
            builder.install_cli(self.root)
        self.assertEqual(target.read_text(), 'existing command')
        target.unlink()
        target.symlink_to(self.root / 'other-checkout/missing-command')
        before = target.readlink()
        with self.assertRaisesRegex(ValueError, 'unrelated command'):
            builder.install_cli(self.root)
        self.assertEqual(target.readlink(), before)

    def test_installed_cli_forwards_options_from_another_working_directory(self):
        target = builder.install_cli(self.root)
        brand = self.root / 'sample brand'
        brand.mkdir()
        (brand / 'package.json').write_text('{"version":"1.2.3"}')
        output = self.root / 'local output'
        config = self.root / 'sources.json'
        config.write_text('{"schema":1,"sources":{}}')
        env = {'HOME': str(self.root), 'PATH': str(Path(sys.executable).parent),
               'STUDIOS_CONFIG': str(self.root / 'disposable-settings.json')}
        result = subprocess.run([sys.executable, str(target), '--plan', '--brand', str(brand),
                                 '--output', str(output), '--config', str(config)], cwd=self.root, env=env,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual(plan['brand_source'], str(brand))
        self.assertEqual(plan['output'], str(output))
        self.assertEqual(plan['brand_version'], '1.2.3')
        self.assertFalse(output.exists())
        self.assertFalse((self.root / 'disposable-settings.json').exists())

    def test_cli_discovery_does_not_depend_on_the_source_working_directory(self):
        target = builder.install_cli(self.root)
        self.assertTrue(os.access(target, os.X_OK))
        result = subprocess.run([sys.executable, str(target), '--help'], cwd=self.root,
                                env={'HOME': str(self.root)}, capture_output=True,
                                text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('usage: presentation-studio-package', result.stdout)
        self.assertIn('--install-cli', result.stdout)

    def stage(self):
        root = self.root / 'Presentation-Studio-test-macos-arm64'
        root.mkdir()
        (root / 'launch.command').write_text('#!/bin/sh\necho test\n')
        (root / 'launch.command').chmod(0o755)
        (root / 'version').write_text('one')
        manifest = {'schema': 1, 'id': 'test-0123456789ab', 'platform': 'macos-arm64',
                    'files': builder.inventory(root)}
        (root / 'local-manifest.json').write_text(json.dumps(manifest))
        return root, manifest

    def test_rebuild_is_deterministic_and_keeps_launcher_permissions(self):
        root, manifest = self.stage()
        target, digest = builder.write_archive(root, self.root / 'output', manifest)
        original = target.read_bytes()
        (root / 'version').touch()
        again, repeated = builder.write_archive(root, self.root / 'output', manifest)
        self.assertEqual((target, digest), (again, repeated))
        self.assertEqual(original, target.read_bytes())
        self.assertEqual(builder.verify_archive(target)['id'], manifest['id'])
        with zipfile.ZipFile(target) as archive:
            self.assertTrue(archive.getinfo(root.name + '/launch.command').external_attr >> 16 & 0o111)
            self.assertTrue(all(item.date_time == (1980, 1, 1, 0, 0, 0) for item in archive.infolist()))
        self.assertEqual(target.with_suffix('.zip.sha256').read_text(), digest + '  ' + target.name + '\n')

    def test_corrupted_build_cannot_replace_a_previous_good_archive(self):
        root, manifest = self.stage()
        target, _ = builder.write_archive(root, self.root / 'output', manifest)
        before = target.read_bytes()
        (root / 'version').write_text('changed after manifest')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            builder.write_archive(root, target.parent, manifest)
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(list(target.parent.glob('.presentation-bundle-*')), [])

    def test_changed_source_is_rejected_if_it_reuses_an_existing_identity(self):
        root, manifest = self.stage()
        target, _ = builder.write_archive(root, self.root / 'output', manifest)
        (root / 'version').write_text('a newer component')
        manifest['files'] = builder.inventory(root)
        (root / 'local-manifest.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'Refusing to replace'):
            builder.write_archive(root, target.parent, manifest)

    def test_archive_verifier_rejects_unexpected_private_files_and_unsafe_paths(self):
        root, manifest = self.stage()
        target, _ = builder.write_archive(root, self.root / 'output', manifest)
        with zipfile.ZipFile(target, 'a') as archive:
            archive.writestr(root.name + '/unexpected-account.json', '{}')
        with self.assertRaisesRegex(ValueError, 'Unexpected'):
            builder.verify_archive(target)
        for name in ('../escape', '/absolute', 'directory/../escape', 'directory\\escape'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'Unsafe'):
                builder.safe_name(name)

    def test_extraction_refuses_zip_links_and_traversal(self):
        for name, mode in (('../escape', 0o100644), ('link', 0o120777)):
            with self.subTest(name=name):
                source = self.root / 'unsafe.zip'
                with zipfile.ZipFile(source, 'w') as archive:
                    item = zipfile.ZipInfo(name)
                    item.external_attr = mode << 16
                    archive.writestr(item, b'outside')
                with self.assertRaisesRegex(ValueError, 'Unsafe|links'):
                    builder.unpack_zip(source, self.root / 'extract')
        self.assertFalse((self.root / 'escape').exists())

    def test_generation_stays_outside_tracked_source_and_refuses_linked_payload(self):
        checkout = self.root / 'checkout'
        self.assertEqual(builder.build_path(checkout / 'dist/local', checkout), checkout / 'dist/local')
        self.assertEqual(builder.build_path(self.root / 'local', checkout), self.root / 'local')
        for path in (checkout, checkout / 'scripts/output', checkout / 'pins/cache'):
            with self.assertRaisesRegex(ValueError, 'outside the repository'):
                builder.build_path(path, checkout)
        root, _ = self.stage()
        (root / 'linked').symlink_to(root / 'version')
        with self.assertRaisesRegex(ValueError, 'regular'):
            builder.inventory(root)

    def test_lock_rejects_foreign_architecture_bad_hash_and_duplicate_packages(self):
        lock = json.loads((ROOT / 'pins/presentation-bundle.json').read_text())
        self.assertEqual(builder.load_lock(ROOT / 'pins/presentation-bundle.json')['platform'], 'macos-arm64')
        path = self.root / 'lock.json'
        variants = [json.loads(json.dumps(lock)) for _ in range(3)]
        variants[0]['packages'][0]['url'] = 'https://example.test/osx-64/package.conda'
        variants[1]['archives']['libreoffice']['sha256'] = 'invalid'
        variants[2]['packages'].append(variants[2]['packages'][0])
        for variant in variants:
            path.write_text(json.dumps(variant))
            with self.assertRaises(ValueError):
                builder.load_lock(path)

    def test_architecture_check_works_on_intel_without_executing_the_binary(self):
        binary = self.root / 'binary'
        binary.write_bytes(b'\xcf\xfa\xed\xfe' + struct.pack('<I', 0x0100000c))
        builder.require_arm64(binary)
        binary.write_bytes(b'\xcf\xfa\xed\xfe' + struct.pack('<I', 0x01000007))
        with self.assertRaisesRegex(ValueError, 'ARM64'):
            builder.require_arm64(binary)

    def test_only_explicit_google_test_fixture_links_are_omitted(self):
        archive = self.root / 'sdk.tar.gz'
        with tarfile.open(archive, 'w:gz') as output:
            for name, data in [('sdk/bin/gcloud', b'cli'), ('sdk/LICENSE', b'license')]:
                item = tarfile.TarInfo(name)
                item.size = len(data)
                output.addfile(item, io.BytesIO(data))
            link = tarfile.TarInfo('sdk/tests/missing-cert')
            link.type = tarfile.SYMTYPE
            link.linkname = 'missing'
            output.addfile(link)
        with self.assertRaisesRegex(ValueError, 'Broken'):
            builder.unpack_tar(archive, self.root / 'refused')
        target = self.root / 'sdk'
        builder.unpack_tar(archive, target, exclude=['tests/missing-cert'])
        self.assertEqual((target / 'bin/gcloud').read_bytes(), b'cli')
        self.assertEqual((target / 'LICENSE').read_bytes(), b'license')
        self.assertFalse((target / 'tests/missing-cert').exists())

    def test_build_environment_does_not_inherit_accounts_or_git_identity(self):
        with mock.patch.dict('os.environ', {'GOOGLE_API_KEY': 'fixture-only', 'CODEX_HOME': '/unrelated',
                                           'STUDIOS_CONFIG': '/unrelated', 'GIT_CONFIG_GLOBAL': '/unrelated'}):
            env = builder.clean_environment(self.root / 'home', self.root / 'cache')
        for key in ('GOOGLE_API_KEY', 'CODEX_HOME', 'STUDIOS_CONFIG'):
            self.assertNotIn(key, env)
        self.assertEqual(env['GIT_CONFIG_GLOBAL'], '/dev/null')
        self.assertEqual(env['HOME'], str(self.root / 'home'))

    def test_failed_download_does_not_prepare_or_package_partial_tools(self):
        lock = builder.load_lock(ROOT / 'pins/presentation-bundle.json')
        payload = self.root / 'payload'
        with mock.patch.object(builder.distribution, 'download', side_effect=ValueError('bad hash')):
            with self.assertRaisesRegex(ValueError, 'bad hash'):
                builder.prepare_tools(lock, self.root / 'cache', payload)
        self.assertFalse(payload.exists())

    def test_linked_packaging_guide_is_in_each_studio_archive_inventory(self):
        for studio in ('blog', 'presentation', 'training'):
            with self.subTest(studio=studio):
                entries = builder.bundles.inventory(ROOT, [studio])
                self.assertIn('docs/local-presentation-bundle.md', entries)


if __name__ == '__main__':
    unittest.main()
