"""Quiet guidance refresh and task pins using disposable local Git repositories."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('sync_guidance', REPO / 'bootstrap/blog-studio/scripts/sync_guidance.py')
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.remote = self.base / 'source repo'
        self.remote.mkdir()
        self.workspace = self.base / 'author workspace'
        self.run_git('init', '-b', 'main')
        (self.remote / 'guidance').mkdir()
        self.manifest = {'schema': 1, 'minimum_runtime': '1.0.0',
                         'entry': 'skills/blog-studio/SKILL.md', 'content_root': 'skills/blog-studio'}
        self.write('guidance/manifest.json', json.dumps(self.manifest))
        self.write('skills/blog-studio/SKILL.md', 'First guidance.')
        self.write('skills/blog-studio/references/outline.md', 'A useful outline.')
        self.write('skills/blog-studio/sources.lock.json', '{"source": "fixture"}')
        self.write('skills/blog-studio/scripts/never.py', 'raise RuntimeError("DO NOT EXECUTE")')
        self.commit()

    def run_git(self, *args):
        result = subprocess.run(['git', '-C', str(self.remote), *args], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def write(self, name, text):
        path = self.remote / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def commit(self):
        self.run_git('add', '.')
        self.run_git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'Fixture guidance')
        return self.run_git('rev-parse', 'HEAD')

    def start(self):
        return sync.start(self.workspace, source=str(self.remote))

    def test_new_task_refreshes_existing_task_resumes_original_pin(self):
        a = self.start()
        self.write('skills/blog-studio/SKILL.md', 'Updated guidance.')
        revision = self.commit()
        b = self.start()
        self.assertEqual(b['revision'], revision)
        self.assertNotEqual(a['revision'], b['revision'])
        old = sync.resume(self.workspace, a['task'])
        self.assertEqual(old['fresh'], 'pinned')
        self.assertEqual(Path(old['guidance']).read_text(), 'First guidance.')
        self.assertFalse((Path(old['guidance']).parent / 'scripts/never.py').exists())
        self.assertTrue((Path(old['guidance']).parent / 'sources.lock.json').is_file())
        self.assertLess(len(json.dumps(b)), 800)
        self.assertNotIn('Updated guidance', json.dumps(b))

    def test_cached_fallback_is_explicit_and_fetch_failure_preserves_pin(self):
        a = self.start()
        with self.assertRaises(sync.SyncError):
            sync.start(self.workspace, source=str(self.base / 'absent repository'))
        self.assertEqual(sync.resume(self.workspace, a['task'])['revision'], a['revision'])
        self.assertIs(sync.resume(self.workspace, a['task'], cached=True)['fresh'], False)
        self.assertEqual(sync.recent_tasks(self.workspace)[0]['task'], a['task'])
        self.assertFalse((self.workspace / 'task-context/.sync.lock').exists())

    def test_future_runtime_and_schema_are_rejected(self):
        for changes in ({'minimum_runtime': '2.0.0'}, {'schema': 2}):
            self.write('guidance/manifest.json', json.dumps({**self.manifest, **changes}))
            self.commit()
            with self.assertRaisesRegex(sync.SyncError, 'newer local'):
                self.start()

    def test_missing_manifest_or_entry_is_not_a_success(self):
        (self.remote / 'guidance/manifest.json').unlink()
        self.commit()
        with self.assertRaises(sync.SyncError):
            self.start()
        self.write('guidance/manifest.json', json.dumps(self.manifest))
        (self.remote / 'skills/blog-studio/SKILL.md').unlink()
        self.commit()
        with self.assertRaises(sync.SyncError):
            self.start()

    def test_symlink_and_executable_guidance_are_rejected(self):
        target = self.remote / 'skills/blog-studio/references/outline.md'
        target.unlink()
        target.symlink_to('../../../../guidance/manifest.json')
        self.commit()
        with self.assertRaisesRegex(sync.SyncError, 'symlink'):
            self.start()
        target.unlink()
        target.write_text('Regular but executable guidance.')
        target.chmod(0o755)
        self.commit()
        with self.assertRaisesRegex(sync.SyncError, 'executable'):
            self.start()

    def test_limits_invalid_encoding_and_lock_protect_cache(self):
        with patch.object(sync, 'MAX_FILE', 10):
            with self.assertRaisesRegex(sync.SyncError, 'size limit'):
                self.start()
        target = self.remote / 'skills/blog-studio/references/outline.md'
        target.write_bytes(b'\xff')
        self.commit()
        with self.assertRaisesRegex(sync.SyncError, 'UTF-8'):
            self.start()
        cache = self.workspace / 'task-context'
        (cache / '.sync.lock').write_text('running')
        with self.assertRaisesRegex(sync.SyncError, 'Another guidance'):
            self.start()

    def test_snapshot_changes_and_invalid_task_are_detected(self):
        a = self.start()
        entry = Path(a['guidance'])
        entry.chmod(0o600)
        entry.write_text('Manually changed instructions.')
        with self.assertRaisesRegex(sync.SyncError, 'changed'):
            sync.resume(self.workspace, a['task'])
        with self.assertRaises(sync.SyncError):
            sync.resume(self.workspace, '../escape')

    def test_saved_pin_symlink_is_rejected(self):
        a = self.start()
        pin = self.workspace / 'task-context/tasks' / a['task'] / 'pin.json'
        outside = self.base / 'outside-pin.json'
        outside.write_bytes(pin.read_bytes())
        pin.unlink()
        pin.symlink_to(outside)
        with self.assertRaisesRegex(sync.SyncError, 'symlink'):
            sync.resume(self.workspace, a['task'])

    def test_malformed_manifest_returns_controlled_failure(self):
        for value in ([], {'minimum_runtime': '-1.0.0'}, None):
            self.write('guidance/manifest.json', json.dumps(value))
            self.commit()
            with self.assertRaises(sync.SyncError):
                self.start()

    def test_repository_timeout_and_stderr_do_not_expose_credentials(self):
        failure = subprocess.CompletedProcess([], 1, stdout=b'', stderr=b'https://SECRET@github.com/private')
        with patch.object(sync.subprocess, 'run', return_value=failure):
            with self.assertRaises(sync.SyncError) as observed:
                self.start()
        self.assertNotIn('SECRET', str(observed.exception))
        with patch.object(sync.subprocess, 'run', side_effect=subprocess.TimeoutExpired('git', 45)):
            with self.assertRaisesRegex(sync.SyncError, 'timed out'):
                self.start()

    def test_cli_failure_returns_compact_json_and_nonzero(self):
        with patch.object(sync, 'start', side_effect=sync.SyncError('Repository access failed.')):
            import io
            from contextlib import redirect_stdout
            output = io.StringIO()
            with patch.object(sys, 'argv', ['sync', 'start', '--workspace', str(self.workspace)]), redirect_stdout(output):
                self.assertEqual(sync.main(), 1)
        self.assertFalse(json.loads(output.getvalue())['fresh'])

    def test_cache_symlink_is_not_followed(self):
        self.workspace.mkdir()
        outside = self.base / 'outside'
        outside.mkdir()
        (self.workspace / 'task-context').symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(sync.SyncError, 'symlink'):
            self.start()
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
