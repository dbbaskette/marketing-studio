"""Repository-wide worker exclusion fails closed on unreadable known records."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import marketing_studio  # noqa: F401
from studio_core.sync_guard import worker_in_progress


class SyncGuardTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)

    def test_both_deck_marker_shapes_anywhere_in_repository_and_stale_markers(self):
        for shape in ('work/step.lock', '.training-studio/step.lock'):
            marker = self.repo / 'another' / 'workspace' / 'one' / shape
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text('left by an interrupted worker')
            self.assertTrue(worker_in_progress(self.repo))
            self.assertTrue(marker.exists(), 'checking must never repair or remove')
            marker.unlink()
            self.assertFalse(worker_in_progress(self.repo))

    def test_blog_run_and_tool_statuses_are_checked(self):
        for shape in ('.blog-runs/one.json', '.blog-runs/tools/abc.json'):
            record = self.repo / 'blogs' / shape
            record.parent.mkdir(parents=True, exist_ok=True)
            record.write_text(json.dumps({'status': 'working'}))
            self.assertTrue(worker_in_progress(self.repo))
            record.write_text(json.dumps({'status': 'stopped'}))
            self.assertFalse(worker_in_progress(self.repo))
            record.unlink()

    def test_unknown_scope_and_malformed_blog_records_refuse(self):
        def unreadable(*args, **kwargs):
            kwargs['onerror'](PermissionError('synthetic'))
            return iter(())
        with mock.patch('studio_core.sync_guard.os.walk', side_effect=unreadable):
            with self.assertRaisesRegex(ValueError, 'could not be checked'):
                worker_in_progress(self.repo)
        record = self.repo / '.blog-runs/one.json'
        record.parent.mkdir()
        record.write_text('{bad')
        with self.assertRaisesRegex(ValueError, 'could not be checked'):
            worker_in_progress(self.repo)

    def test_linked_directories_and_output_caches_are_not_traversed(self):
        with tempfile.TemporaryDirectory() as outside:
            other = Path(outside)
            (other / 'work').mkdir()
            (other / 'work/step.lock').touch()
            (self.repo / 'linked').symlink_to(other, target_is_directory=True)
            (self.repo / 'sources/deep/work').mkdir(parents=True)
            (self.repo / 'sources/deep/work/step.lock').touch()
            self.assertFalse(worker_in_progress(self.repo))
