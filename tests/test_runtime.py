"""Startup selects an installed supported Python before loading studio code."""
import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import marketing_studio
from studio_core import runtime


ROOT = Path(__file__).resolve().parents[1]


class PythonBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_supported_current_interpreter_needs_no_discovery(self):
        with mock.patch.object(runtime, 'supported_python') as find, \
                mock.patch.object(runtime.os, 'execv') as execute:
            runtime.ensure_python(self.root)
        find.assert_not_called()
        execute.assert_not_called()

    def test_old_interpreter_restarts_file_with_original_arguments(self):
        with mock.patch.object(runtime.sys, 'version_info', (3, 9, 6)), \
                mock.patch.object(runtime.sys, 'argv', ['marketing-studio', 'serve', '--port', '8123']), \
                mock.patch.object(runtime, 'supported_python', return_value='/installed/python3.11'), \
                mock.patch.object(runtime.os, 'execv') as execute:
            runtime.ensure_python(self.root)
        execute.assert_called_once_with('/installed/python3.11', [
            '/installed/python3.11', str(Path('marketing-studio').absolute()), 'serve', '--port', '8123'])

    def test_module_restart_preserves_module_entry_point(self):
        with mock.patch.object(runtime.sys, 'version_info', (3, 9, 6)), \
                mock.patch.object(runtime.sys, 'argv', ['ignored/__main__.py', '--version']), \
                mock.patch.object(runtime, 'supported_python', return_value='/installed/python3.11'), \
                mock.patch.object(runtime.os, 'execv') as execute:
            runtime.ensure_python(self.root, module='marketing_studio')
        execute.assert_called_once_with('/installed/python3.11', [
            '/installed/python3.11', '-m', 'marketing_studio', '--version'])

    def test_no_supported_python_reports_requirement_without_creating_state(self):
        error = io.StringIO()
        with mock.patch.object(runtime.sys, 'version_info', (3, 9, 6)), \
                mock.patch.object(runtime, 'supported_python', return_value=None), \
                mock.patch.object(runtime.os, 'execv') as execute, contextlib.redirect_stderr(error):
            with self.assertRaises(SystemExit) as stopped:
                runtime.ensure_python(self.root)
        self.assertEqual(stopped.exception.code, 2)
        self.assertIn('Marketing Studio requires Python 3.11 or newer', error.getvalue())
        self.assertNotIn('Traceback', error.getvalue())
        self.assertEqual(list(self.root.iterdir()), [])
        execute.assert_not_called()

    def test_release_private_runtime_is_preferred_and_not_bypassed_if_broken(self):
        private = self.root / 'runtime/python/bin/python3'
        private.parent.mkdir(parents=True)
        private.touch()
        for code in (0, 1):
            with self.subTest(code=code), mock.patch.object(runtime.shutil, 'which') as which, \
                    mock.patch.object(runtime.subprocess, 'run',
                                      return_value=subprocess.CompletedProcess([], code)) as run:
                self.assertEqual(runtime.supported_python(self.root), str(private) if code == 0 else None)
                self.assertEqual(run.call_args.args[0][0], str(private))
                which.assert_not_called()

    def test_path_candidates_are_probed_before_restarting(self):
        candidates = {'python3.14': '/old/python', 'python3.13': '/broken/python',
                      'python3.12': '/supported/python'}

        def probe(command, **kwargs):
            if command[0] == '/broken/python':
                raise OSError('missing interpreter')
            return subprocess.CompletedProcess(command, 0 if command[0] == '/supported/python' else 1)

        with mock.patch.object(runtime.shutil, 'which', side_effect=candidates.get), \
                mock.patch.object(runtime.subprocess, 'run', side_effect=probe):
            self.assertEqual(runtime.supported_python(self.root), '/supported/python')

    def test_uv_lookup_uses_only_existing_offline_interpreters(self):
        def probe(command, **kwargs):
            if command[0] == '/tools/uv':
                self.assertTrue({'--offline', '--no-python-downloads', '--no-project', '--no-config'} <= set(command))
                return subprocess.CompletedProcess(command, 0, '/cached/python3.11\n')
            return subprocess.CompletedProcess(command, 0)

        with mock.patch.object(runtime.shutil, 'which', side_effect=lambda name: '/tools/uv' if name == 'uv' else None), \
                mock.patch.object(runtime.subprocess, 'run', side_effect=probe):
            self.assertEqual(runtime.supported_python(self.root), '/cached/python3.11')

    def test_missing_and_unresponsive_interpreters_are_skipped(self):
        with mock.patch.object(runtime.shutil, 'which', return_value=None):
            self.assertIsNone(runtime.supported_python(self.root))
        with mock.patch.object(runtime.shutil, 'which', return_value='/unresponsive'), \
                mock.patch.object(runtime.subprocess, 'run',
                                  side_effect=subprocess.TimeoutExpired('/unresponsive', 5)):
            self.assertIsNone(runtime.supported_python(self.root))

    def test_macos_old_python_bootstraps_source_module_bridge_and_installer(self):
        old = Path('/usr/bin/python3')
        if not old.is_file():
            self.skipTest('macOS system Python is unavailable')
        check = subprocess.run([str(old), '-c', 'import sys; print(sys.version_info < (3, 11))'],
                               capture_output=True, text=True, timeout=15)
        if check.returncode or check.stdout.strip() != 'True':
            self.skipTest('macOS system Python is already supported')
        binaries = self.root / 'bin'
        binaries.mkdir()
        (binaries / 'python3.11').symlink_to(sys.executable)
        home = self.root / 'home'
        home.mkdir()
        env = {**os.environ, 'PATH': str(binaries), 'HOME': str(home),
               'STUDIOS_CONFIG': str(home / 'shared.json'),
               'MARKETING_STUDIO_DATA': str(home / 'data'), 'PYTHONDONTWRITEBYTECODE': '1'}
        entries = ([str(ROOT / 'marketing-studio'), '--version'],
                   [str(ROOT / 'presentation-studio-package'), '--help'],
                   ['-m', 'marketing_studio', '--version'],
                   [str(ROOT / 'marketing_studio/bridge.py'), '--help'],
                   [str(ROOT / 'installer/install.py'), '--help'])
        for entry in entries:
            with self.subTest(entry=entry):
                result = subprocess.run([str(old), *entry], cwd=ROOT, env=env,
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn('ModuleNotFoundError', result.stderr)
                self.assertTrue(result.stdout)
        self.assertEqual(list(home.iterdir()), [], 'startup probes must not initialize studio state')
