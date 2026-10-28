import json
import os
import selectors
import subprocess
import sys
import shutil

from helpers import Isolated, NATIVE


class CommandTests(Isolated):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(NATIVE / 'runner/studio.py'), *args],
                              cwd=self.temp, capture_output=True, text=True, timeout=10)

    def test_help_status_and_unconfigured_create_have_no_setup_side_effects(self):
        self.assertEqual(self.run_cli('--help').returncode, 0)
        result = self.run_cli('status')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)['configured'])
        self.assertFalse(self.data.exists())
        self.assertEqual(self.run_cli('create', 'Unconfigured').returncode, 2)
        self.assertFalse(self.data.exists())

    def test_native_setup_create_show_and_stale_edit(self):
        result = self.run_cli('setup', '--workspace', str(self.workspace))
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_cli('create', 'Synthetic brief', '--direction', 'hybrid')
        self.assertEqual(result.returncode, 0, result.stderr)
        project = json.loads(result.stdout)
        self.assertEqual(json.loads(self.run_cli('show', project['id']).stdout), project)
        file = self.temp / 'brief.json'
        file.write_text(json.dumps({**project['brief'], 'title': 'Changed'}))
        result = self.run_cli('edit-brief', project['id'], '--expected-revision', '0', '--file', str(file))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['revision'], 1)
        self.assertEqual(self.run_cli('edit-brief', project['id'], '--expected-revision', '0',
                                      '--file', str(file)).returncode, 2)

    def test_materialized_native_copy_runs_without_checkout_links(self):
        from studio_core.packaging import files
        destination = self.temp / 'native-copy'
        for source in files(NATIVE):
            target = destination / source.relative_to(NATIVE)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        self.assertFalse(any(path.is_symlink() for path in destination.rglob('*')))
        result = subprocess.run([sys.executable, str(destination / 'runner/studio.py'), 'status'],
                                cwd=self.temp, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['product'], 'Infographic Studio')
        self.assertFalse(self.data.exists())

    def test_owned_native_server_stops_cleanly_and_piped_output_has_no_key(self):
        process = subprocess.Popen([sys.executable, str(NATIVE / 'runner/studio.py'), 'serve',
                                    '--workspace', str(self.workspace)], cwd=self.temp,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, start_new_session=True)
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                self.assertTrue(selector.select(timeout=10), 'The disposable server did not announce readiness.')
            line = json.loads(process.stdout.readline())
            self.assertTrue(line['address'].startswith('http://127.0.0.1:'))
            self.assertNotIn('token', json.dumps(line).lower())
            self.assertNotIn('url', line)
            process.terminate()
            output, error = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0, error)
            self.assertEqual(output, '')
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
