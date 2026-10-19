"""Terminal install entry points use disposable files, homes, and stub installers."""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'core'))
from studio_core import bundles

ENTRY_POINTS = [ROOT / 'install.sh', *(ROOT / 'studios' / name / 'install.sh'
                                      for name in ('blog', 'presentation', 'training'))]


class ShellInstallerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='studio-shell-install-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        home = self.root / 'disposable home'
        home.mkdir()
        self.env = {'HOME': str(home), 'STUDIOS_CONFIG': str(home / 'settings.json'),
                    'PATH': str(Path(sys.executable).parent) + ':/usr/bin:/bin',
                    'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1'}

    def recorder(self, target):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('#!' + sys.executable + '\nimport json,sys\n'
                          'print(json.dumps(sys.argv[1:]))\nraise SystemExit(37)\n')
        target.chmod(0o755)

    def test_each_top_level_shell_preserves_arguments_and_the_installer_exit_status(self):
        for index, source in enumerate(ENTRY_POINTS):
            with self.subTest(source=source.relative_to(ROOT)):
                folder = self.root / ('setup folder ' + str(index))
                folder.mkdir()
                shutil.copy2(source, folder / 'install.sh')
                recorder = folder / 'record-arguments'
                self.recorder(recorder)
                (folder / 'installer').mkdir()
                (folder / 'installer/install.sh').write_text(
                    '#!/bin/sh\nexec ' + shlex.quote(str(recorder)) + ' "$@"\n')
                arguments = ['--home', str(self.root / 'another home'), '--target', 'codex', '--help']
                result = subprocess.run(['bash', str(folder / 'install.sh'), *arguments],
                                        cwd=self.root, env=self.env, capture_output=True,
                                        text=True, timeout=20)
                self.assertEqual(result.returncode, 37, result.stderr)
                self.assertEqual(json.loads(result.stdout), arguments)
                self.assertFalse(Path(self.env['STUDIOS_CONFIG']).exists())

    def test_actual_source_entry_points_offer_help_without_installing_anything(self):
        for source in ENTRY_POINTS:
            with self.subTest(source=source.relative_to(ROOT)):
                result = subprocess.run(['bash', str(source), '--help'], cwd=self.root,
                                        env=self.env, capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('--target', result.stdout + result.stderr)
        self.assertEqual(list(Path(self.env['HOME']).iterdir()), [])

    def test_local_presentation_shell_uses_private_python_without_a_command_file(self):
        folder = self.root / 'Presentation Studio setup'
        folder.mkdir()
        shutil.copy2(ROOT / 'scripts/local_bundle/install.sh', folder / 'install.sh')
        self.recorder(folder / 'studio/runtime/python/bin/python3')
        fakebin = self.root / 'fakebin'
        fakebin.mkdir()
        uname = fakebin / 'uname'
        uname.write_text('#!/bin/sh\necho arm64\n')
        uname.chmod(0o755)
        env = {**self.env, 'PATH': str(fakebin) + ':/usr/bin:/bin'}
        arguments = ['--home', str(self.root / 'destination home'), '--verify-only']
        result = subprocess.run(['bash', str(folder / 'install.sh'), *arguments], cwd=self.root,
                                env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 37, result.stderr)
        self.assertEqual(json.loads(result.stdout), [str(folder / 'install-local.py'), *arguments])
        self.assertFalse(list(folder.rglob('*.command')))
        uname.write_text('#!/bin/sh\necho x86_64\n')
        refused = subprocess.run(['bash', str(folder / 'install.sh'), *arguments], cwd=self.root,
                                 env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(refused.returncode, 1)
        self.assertIn('Apple Silicon', refused.stderr)

    def test_all_subset_inventories_contain_suite_and_native_shell_entries(self):
        for name in ('blog', 'presentation', 'training'):
            with self.subTest(studio=name):
                entries = bundles.inventory(ROOT, [name])
                for key in ('install.sh', 'studios/' + name + '/install.sh'):
                    self.assertIn(key, entries)
                    self.assertTrue(entries[key].stat().st_mode & 0o111)


if __name__ == '__main__':
    unittest.main()
