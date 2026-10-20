"""One source packager per product, with disposable configuration and no downloads."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('product_installer', ROOT / 'scripts/local_bundle/install-local.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)
PRODUCTS = {'marketing': ['blog', 'presentation', 'training'], 'blog': ['blog'],
            'presentation': ['presentation'], 'training': ['training']}


class PackagingEntryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='studio-package-entry-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.home = self.root / 'disposable home'
        self.home.mkdir()
        self.env = {'HOME': str(self.home), 'STUDIOS_CONFIG': str(self.home / 'settings.json'),
                    'PATH': str(Path(sys.executable).parent) + ':/usr/bin:/bin',
                    'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1'}

    def folder(self, product):
        return ROOT if product == 'marketing' else ROOT / 'studios' / product

    def test_products_have_identical_root_installer_and_packager_scripts(self):
        for product in PRODUCTS:
            for name in ('install.sh', 'package.sh'):
                with self.subTest(product=product, script=name):
                    path = self.folder(product) / name
                    self.assertEqual(path.read_bytes(), (ROOT / name).read_bytes())
                    self.assertTrue(path.stat().st_mode & 0o111)
        self.assertEqual((ROOT / 'scripts/local_bundle/install.sh').read_bytes(), (ROOT / 'install.sh').read_bytes())

    def test_every_product_plans_only_its_own_bundle_without_touching_installed_state(self):
        brand = self.root / 'synthetic brand'
        brand.mkdir()
        (brand / 'package.json').write_text('{"version":"1.2.3"}')
        config = self.root / 'sources.json'
        config.write_text(json.dumps({'schema': 1, 'sources': {'brand': {'path': str(brand)}}}))
        for product, selected in PRODUCTS.items():
            with self.subTest(product=product):
                output = self.root / ('output ' + product)
                done = subprocess.run(['bash', str(self.folder(product) / 'package.sh'), '--plan',
                                       '--config', str(config), '--output', str(output)],
                                      cwd=self.root, env=self.env, capture_output=True, text=True, timeout=30)
                self.assertEqual(done.returncode, 0, done.stderr)
                plan = json.loads(done.stdout)
                self.assertEqual(plan['product'], product)
                self.assertEqual(plan['studios'], selected)
                self.assertEqual(plan['mode'], 'online')
                self.assertEqual('harness-slides' in plan['companions'], product != 'blog')
                self.assertFalse(output.exists())
        self.assertEqual(list(self.home.iterdir()), [])

    def test_product_wrapper_preserves_arguments_and_status_from_another_directory(self):
        checkout = self.root / 'source checkout'
        checkout.mkdir()
        shutil.copy2(ROOT / 'package.sh', checkout / 'package.sh')
        (checkout / 'studio-package').write_text('import json,sys\nprint(json.dumps(sys.argv[1:]))\nraise SystemExit(37)\n')
        for product in PRODUCTS:
            folder = checkout if product == 'marketing' else checkout / 'studios' / product
            folder.mkdir(parents=True, exist_ok=True)
            if product != 'marketing':
                shutil.copy2(ROOT / 'package.sh', folder / 'package.sh')
            arguments = ['--config', str(self.root / 'some sources.json'), '--mode', 'offline']
            done = subprocess.run(['bash', str(folder / 'package.sh'), *arguments], cwd=self.root,
                                  env=self.env, capture_output=True, text=True, timeout=20)
            self.assertEqual(done.returncode, 37, done.stderr)
            self.assertEqual(json.loads(done.stdout), [product, *arguments])

    def test_local_installer_scopes_studios_and_preserves_legacy_bundles(self):
        self.assertEqual(installer.selection({}), ('presentation', ['presentation']))
        for product, selected in PRODUCTS.items():
            manifest = {'product': product, 'studios': selected}
            self.assertEqual(installer.selection(manifest), (product, selected))
            if product == 'marketing':
                self.assertEqual(installer.selection(manifest, ['blog']), ('marketing', ['blog']))
            else:
                absent = 'training' if product != 'training' else 'presentation'
                with self.assertRaisesRegex(RuntimeError, 'does not include'):
                    installer.selection(manifest, [absent])
        for manifest in ({'product': '../outside'}, {'product': 'blog', 'studios': ['training']}):
            with self.assertRaises(RuntimeError):
                installer.selection(manifest)

    def test_local_install_invokes_only_selected_studios_and_keeps_other_launchers(self):
        for product, selected in PRODUCTS.items():
            with self.subTest(product=product):
                home = self.root / product / 'home'
                source = self.root / product / 'source'
                source.mkdir(parents=True)
                (source / 'verify-installed.py').write_text('# synthetic verifier\n')
                (source / 'diagnose-git.sh').write_text('# synthetic diagnostic\n')
                suite = home / '.local/share/marketing-studio/versions/synthetic'
                suite.mkdir(parents=True)
                (suite.parent.parent / 'current').symlink_to(suite)
                saved = {}
                for name in ('marketing', 'blog', 'presentation', 'training'):
                    folder = home / '.local/share' / (name + '-studio')
                    folder.mkdir(parents=True, exist_ok=True)
                    for filename in ('studio', name if name != 'marketing' else 'marketing-studio'):
                        path = folder / filename
                        path.write_text('#!/bin/sh\n# synthetic retained launcher\n')
                        saved[path] = path.read_bytes()
                base = home / '.local/share' / (product + '-studio-local-bundle')
                version = base / 'versions/synthetic-bundle'
                version.mkdir(parents=True)
                (version / 'ready.json').write_text('{}')
                config = mock.Mock()
                with mock.patch.object(installer, 'ROOT', source), mock.patch.object(installer, 'run', return_value=json.dumps({'current': '/synthetic/brand'})) as run, mock.patch.object(installer, 'install_tools', side_effect=AssertionError('Installed tools')):
                    installer.install(home, base, {'PATH': '/fixture'}, 'codex',
                                      {'id': 'synthetic-bundle', 'product': product, 'studios': selected}, config, 'codex')
                command = list(run.call_args_list[1].args[0])
                start = command.index('--studios') + 1
                self.assertEqual(command[start:command.index('--target')], selected)
                record = json.loads((base / 'installation.json').read_text())
                self.assertEqual(record['studios'], selected)
                self.assertEqual(record['product'], product)
                title = product.title() + ' Studio'
                self.assertTrue((home / ('Applications/Verify ' + title + '.sh')).is_file())
                self.assertTrue((home / ('Applications/Diagnose ' + title + ' Git.sh')).is_file())
                for path, prior in saved.items():
                    if not any(str(path).startswith(str(home / '.local/share' / (name + '-studio')) + '/') for name in ('marketing', *selected)):
                        self.assertEqual(path.read_bytes(), prior)
                self.assertEqual(len(run.call_args_list), 3)  # Brand check, studio setup, brand activation.


if __name__ == '__main__':
    unittest.main()
