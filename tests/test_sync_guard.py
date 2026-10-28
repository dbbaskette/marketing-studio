"""Repository-wide worker exclusion fails closed on unreadable known records."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import marketing_studio  # noqa: F401
from studio_core.sync_guard import SYNC_WAIT, worker_in_progress


class SyncGuardTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)

    def presentation_item(self):
        item = self.repo / 'presentation'
        item.mkdir()
        (item / 'run.json').write_text(json.dumps({'schema': 1, 'id': item.name,
            'title': 'Synthetic saved Presentation Studio deck', 'created': '2026-10-28T12:00:00Z',
            'agent': 'test', 'route': 'scratch', 'form': {
                'route': 'scratch', 'title': 'Synthetic saved deck', 'output': 'pptx'},
            'steps': {}, 'gates': {}, 'limits': {}, 'revisions': []}))
        return item

    def test_recognized_item_linked_cache_roots_refuse_without_traversal(self):
        item = self.presentation_item()
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside)
            material = target / 'nested/desk/migration.json'
            material.parent.mkdir(parents=True)
            material.write_text('{unknown saved metadata')
            record = (item / 'run.json').read_bytes()
            from studio_core import sync_guard
            walk = sync_guard.os.walk
            for cache in ('work', 'sources'):
                for dangling in (False, True):
                    with self.subTest(cache=cache, dangling=dangling):
                        link = item / cache
                        destination = target / 'missing' if dangling else target
                        link.symlink_to(destination, target_is_directory=True)
                        walked = []
                        def tracked(folder, *args, **kwargs):
                            walked.append(Path(folder))
                            return walk(folder, *args, **kwargs)
                        try:
                            with mock.patch.object(sync_guard.os, 'walk', side_effect=tracked):
                                with self.assertRaisesRegex(ValueError, 'could not be checked'):
                                    worker_in_progress(self.repo)
                            self.assertNotIn(link, walked)
                            self.assertNotIn(target, walked)
                            self.assertEqual(link.readlink(), destination)
                            self.assertEqual((item / 'run.json').read_bytes(), record)
                            self.assertEqual(material.read_text(), '{unknown saved metadata')
                        finally:
                            link.unlink()

    def test_recognized_item_absent_optional_caches_are_idle_but_nested_migration_is_not(self):
        item = self.presentation_item()
        self.assertFalse(worker_in_progress(self.repo))
        for cache in ('work', 'sources'):
            folder = item / cache
            folder.mkdir()
            self.assertFalse(worker_in_progress(self.repo))
            nested = folder / 'nested/deck'
            pending = nested / 'work/desk/migration-transaction.json'
            pending.parent.mkdir(parents=True)
            pending.write_text('{interrupted')
            self.assertTrue(worker_in_progress(self.repo))
            self.assertEqual(pending.read_text(), '{interrupted')
            pending.unlink()
            marker = nested / 'desk/migration-origin.json'
            marker.parent.mkdir()
            marker.write_text('{unknown')
            with self.assertRaisesRegex(ValueError, 'could not be checked'):
                worker_in_progress(self.repo)
            self.assertEqual(marker.read_text(), '{unknown')
            marker.unlink()
            self.assertFalse(worker_in_progress(self.repo))

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
            for record, data in (('deck/run.json', {'schema': 1, 'id': 'deck', 'title': 'Synthetic deck', 'steps': {}, 'route': 'idea', 'form': {}}),
                                 ('training/.training-studio/run.json', {'schema': 1, 'steps': {}, 'agent': 'test'})):
                item = self.repo / record.split('/')[0]
                path = self.repo / record
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(data))
                if item.name == 'training':
                    (item / '.training-studio/session.json').write_text(json.dumps({
                        'schema': 1, 'id': 'training', 'title': 'Synthetic training',
                        'levels': [], 'stage': 'intake', 'sizing': {}, 'settings': {
                            'deck_target': None, 'brand': None, 'brief_kind': 'product', 'stages': []},
                        'unavailable': {}, 'pins': {}, 'artifacts': {}, 'exports': {},
                        'decisions': [], 'events': []}))
                for cache in ('work', 'sources'):
                    (item / cache / 'deep/work').mkdir(parents=True)
                    (item / cache / 'deep/work/step.lock').touch()
            self.assertFalse(worker_in_progress(self.repo))

    def test_workspace_and_container_names_work_and_sources_do_not_hide_workers(self):
        for folder in ('work', 'sources', 'nested/work', 'nested/sources',
                       'work/nested/sources', 'sources/nested/work'):
            for shape in ('deck/work/step.lock', 'training/.training-studio/step.lock',
                          '.blog-runs/one.json', '.blog-runs/tools/abc.json'):
                with self.subTest(folder=folder, shape=shape):
                    marker = self.repo / folder / shape
                    marker.parent.mkdir(parents=True, exist_ok=True)
                    text = '{"status":"working"}' if marker.suffix == '.json' else 'active step'
                    marker.write_text(text)
                    self.assertTrue(worker_in_progress(self.repo))
                    self.assertEqual(marker.read_text(), text)
                    marker.unlink()
                    self.assertFalse(worker_in_progress(self.repo))

    def test_linked_training_metadata_does_not_hide_real_nested_workers(self):
        with tempfile.TemporaryDirectory() as outside:
            metadata = Path(outside)
            (metadata / 'run.json').write_text(json.dumps({
                'schema': 1, 'steps': {}, 'agent': 'test'}))
            (metadata / 'session.json').write_text(json.dumps({
                'schema': 1, 'id': 'training', 'title': 'Synthetic training',
                'levels': [], 'stage': 'intake', 'sizing': {}, 'settings': {
                    'deck_target': None, 'brand': None, 'brief_kind': 'product', 'stages': []},
                'unavailable': {}, 'pins': {}, 'artifacts': {}, 'exports': {},
                'decisions': [], 'events': []}))
            container = self.repo / 'container'
            container.mkdir()
            (container / '.training-studio').symlink_to(metadata, target_is_directory=True)

            def snapshot(root):
                return {str(path.relative_to(root)): (
                    ('link', str(path.readlink())) if path.is_symlink() else
                    ('directory',) if path.is_dir() else ('file', path.read_bytes()))
                    for path in root.rglob('*')}

            for cache in ('work', 'sources'):
                for shape in ('deck/work/step.lock', 'training/.training-studio/step.lock',
                              '.blog-runs/one.json'):
                    with self.subTest(cache=cache, shape=shape):
                        marker = container / cache / 'nested' / shape
                        marker.parent.mkdir(parents=True, exist_ok=True)
                        marker.write_text('{"status":"working"}' if marker.suffix == '.json'
                                          else 'active step')
                        before = snapshot(self.repo), snapshot(metadata)
                        self.assertTrue(worker_in_progress(self.repo))
                        self.assertEqual((snapshot(self.repo), snapshot(metadata)), before)
                        marker.unlink()
                        self.assertFalse(worker_in_progress(self.repo))

    def test_notice_explains_recovery_after_stop_or_interruption(self):
        self.assertIn('stopped', SYNC_WAIT.lower())
        self.assertIn('interrupted', SYNC_WAIT.lower())
        self.assertIn('reopen', SYNC_WAIT.lower())

    def test_pending_blog_migration_is_not_hidden_by_recognized_output_cache(self):
        container = self.repo / 'deck'
        container.mkdir()
        (container / 'run.json').write_text(json.dumps({'schema': 1, 'id': 'deck', 'title': 'Synthetic', 'steps': {}, 'route': 'idea', 'form': {}}))
        journal = container / 'sources/nested/blogs/one/desk/migration.pending.json'
        journal.parent.mkdir(parents=True)
        journal.write_text('{interrupted')
        self.assertTrue(worker_in_progress(self.repo))
        self.assertEqual(journal.read_text(), '{interrupted')
        journal.unlink()
        (journal.parent / 'migration.json').write_text('{broken')
        with self.assertRaisesRegex(ValueError, 'could not be checked'):
            worker_in_progress(self.repo)

    def test_unknown_item_records_do_not_hide_nested_workspaces(self):
        for record in ('container/run.json', 'container/.training-studio/run.json'):
            for text in ('{bad', '{}', '{"schema":999,"steps":{}}',
                         '{"schema":1,"steps":{},"route":"idea"}',
                         '{"schema":2,"id":"item","title":"Synthetic","steps":{},"form":{},"route":"idea"}',
                         '{"schema":3,"id":"item","title":"Synthetic","steps":{},"form":{},"route":"idea"}'):
                for shape in ('deck/work/step.lock', 'training/.training-studio/step.lock',
                              '.blog-runs/one.json'):
                    with self.subTest(record=record, text=text, shape=shape):
                        path = self.repo / record
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(text)
                        marker = self.repo / 'container/sources/nested/work' / shape
                        marker.parent.mkdir(parents=True, exist_ok=True)
                        marker.write_text('{"status":"working"}' if marker.suffix == '.json' else 'step')
                        self.assertTrue(worker_in_progress(self.repo))
                        marker.unlink()
                        path.unlink()
