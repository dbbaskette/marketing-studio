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
        self.root = Path(temporary.name).resolve()
        home = self.root / 'disposable home'
        home.mkdir()
        self.env = {'HOME': str(home), 'STUDIOS_CONFIG': str(home / 'settings.json'),
                    'PATH': str(Path(sys.executable).parent) + ':/usr/bin:/bin',
                    'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1'}

    def logging_helper(self, suite):
        target = suite / 'core/studio_core/install-log.sh'
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / 'core/studio_core/install-log.sh', target)

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
        (folder / 'installer').mkdir()
        shutil.copy2(ROOT / 'scripts/local_bundle/bootstrap.sh', folder / 'installer/install.sh')
        self.logging_helper(folder / 'studio')
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

    def test_bundle_bootstrap_preserves_stale_bytecode_during_imports_and_retries(self):
        import py_compile
        folder = self.root / 'bundle'
        folder.mkdir()
        shutil.copy2(ROOT / 'scripts/local_bundle/install.sh', folder / 'install.sh')
        (folder / 'installer').mkdir()
        shutil.copy2(ROOT / 'scripts/local_bundle/bootstrap.sh', folder / 'installer/install.sh')
        self.logging_helper(folder / 'studio')
        python = folder / 'studio/runtime/python/bin/python3'
        python.parent.mkdir(parents=True)
        python.symlink_to(sys.executable)
        module = folder / 'synthetic_module.py'
        module.write_text('value = 1\n')
        cache = Path(py_compile.compile(str(module), doraise=True))
        original = cache.read_bytes()
        module.write_text('value = 200\n')
        (folder / 'install-local.py').write_text(
            'import subprocess, sys, synthetic_module\n'
            'assert sys.dont_write_bytecode\n'
            'assert synthetic_module.value == 200\n'
            'subprocess.run([sys.executable, "-c", '
            '\'import sys, synthetic_module; assert sys.dont_write_bytecode; '
            'assert synthetic_module.value == 200\'], check=True)\n')
        env = {**self.no_system_python(), 'PYTHONDONTWRITEBYTECODE': ''}
        for _ in range(2):
            done = subprocess.run(['bash', str(folder / 'install.sh')], cwd=folder,
                                  env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertEqual(cache.read_bytes(), original)
        self.assertEqual(len(list(Path(self.env['HOME']).rglob('install-*'))), 2)

    def test_all_subset_inventories_contain_suite_and_native_shell_entries(self):
        for name in ('blog', 'presentation', 'training'):
            with self.subTest(studio=name):
                entries = bundles.inventory(ROOT, [name])
                for key in ('install.sh', 'studios/' + name + '/install.sh'):
                    self.assertIn(key, entries)
                    self.assertTrue(entries[key].stat().st_mode & 0o111)

    def packaged_suite(self, folder, studios):
        self.logging_helper(folder)
        for name in ('install.sh', 'installer/install.sh',
                     *(str(Path('studios') / studio / entry) for studio in studios
                       for entry in ('install.sh', 'installer/install.sh'))):
            target = folder / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        (folder / 'distribution.json').write_text('{}')

    def no_system_python(self):
        fakebin = self.root / 'fake tools'
        fakebin.mkdir()
        for name, script in {
            'uname': '#!/bin/sh\nif [ "$1" = -m ]; then echo arm64; else echo Darwin; fi\n',
            'python3': '#!/bin/sh\necho "System Python was called" >&2\nexit 91\n',
        }.items():
            target = fakebin / name
            target.write_text(script)
            target.chmod(0o755)
        return {**self.env, 'PATH': str(fakebin) + ':/usr/bin:/bin'}

    def test_every_local_bundle_entry_uses_full_setup_and_private_python(self):
        folder = self.root / 'Presentation Studio bundle'
        folder.mkdir()
        self.packaged_suite(folder / 'studio', ['presentation'])
        shutil.copy2(ROOT / 'scripts/local_bundle/install.sh', folder / 'install.sh')
        (folder / 'installer').mkdir()
        shutil.copy2(ROOT / 'scripts/local_bundle/bootstrap.sh', folder / 'installer/install.sh')
        self.logging_helper(folder / 'studio')
        (folder / 'local-manifest.json').write_text('{}')
        (folder / 'install-local.py').write_text('# synthetic installer\n')
        self.recorder(folder / 'studio/runtime/python/bin/python3')
        env = self.no_system_python()
        arguments = ['--home', str(self.root / 'destination home'), '--verify-only']
        for entry in ('install.sh', 'studio/install.sh', 'studio/installer/install.sh',
                      'studio/studios/presentation/install.sh',
                      'studio/studios/presentation/installer/install.sh'):
            with self.subTest(entry=entry):
                script = folder / entry
                done = subprocess.run(['./install.sh', *arguments], cwd=script.parent,
                                      env=env, capture_output=True, text=True, timeout=20)
                self.assertEqual(done.returncode, 37, done.stdout + done.stderr)
                selected = ['--studios', 'presentation'] if entry.startswith('studio/studios/') else []
                self.assertEqual(json.loads(done.stdout),
                                 [str(folder / 'install-local.py'), *arguments, *selected])
                self.assertNotIn('System Python', done.stderr)
        self.assertEqual(list(Path(self.env['HOME']).iterdir()), [])

    def test_nested_platform_installers_use_suite_private_runtimes(self):
        folder = self.root / 'Platform bundle'
        folder.mkdir()
        names = ('blog', 'presentation', 'training')
        self.packaged_suite(folder, names)
        python = folder / 'runtime/python/bin/python3'
        self.recorder(python)
        python.write_text(python.read_text().replace(
            'print(json.dumps(sys.argv[1:]))',
            'if sys.argv[1:2] == ["-c"]: raise SystemExit(0)\n'
            'print(json.dumps(sys.argv[1:]))'))
        node = folder / 'runtime/node/bin/node'
        node.parent.mkdir(parents=True)
        node.write_text('#!/bin/sh\nexit 0\n')
        node.chmod(0o755)
        (folder / 'runtime/platform').write_text('macos-arm64\n')
        env = self.no_system_python()
        arguments = ['install', '--target', 'codex', '--companions', 'skip',
                     '--home', self.env['HOME'], '--yes']
        for name in names:
            for entry in ('install.sh', 'installer/install.sh'):
                with self.subTest(studio=name, entry=entry):
                    script = folder / 'studios' / name / entry
                    done = subprocess.run(['./install.sh', *arguments], cwd=script.parent,
                                          env=env, capture_output=True, text=True, timeout=20)
                    self.assertEqual(done.returncode, 37, done.stdout + done.stderr)
                    forwarded = json.loads(done.stdout)
                    self.assertEqual(Path(forwarded[0]).resolve(), folder / 'installer/install.py')
                    self.assertEqual(forwarded[1:], [*arguments, '--studios', name])
                    self.assertNotIn('System Python', done.stderr)
        self.assertEqual(len(list(Path(self.env['HOME']).rglob('install-*'))), 6)


if __name__ == '__main__':
    unittest.main()
