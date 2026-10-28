"""Inventory never expires or changes disposable Blog Studio records."""

import isolation  # noqa: F401
import json
import io
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import saved_work


class SavedWorkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))

    def snapshot(self):
        return {
            str(p.relative_to(self.root)): p.read_bytes()
            for p in self.root.rglob('*')
            if p.is_file()
        }

    def test_cli_returns_inventory_before_team_or_worker_operations(self):
        import studio

        out = io.StringIO()
        with (
            patch.object(
                sys,
                'argv',
                [
                    'studio.py',
                    '--root',
                    str(self.root),
                    'saved-work',
                    '--folder',
                    str(self.root / 'absent'),
                ],
            ),
            patch('sys.stdout', out),
            patch('team_workspace.before', side_effect=AssertionError('No team operation')),
        ):
            self.assertEqual(studio.main(), 0)
        self.assertFalse(json.loads(out.getvalue())['complete'])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_cli_excludes_linked_root_and_ancestor_without_resolving(self):
        import studio

        target = self.root / 'target'
        target.mkdir()
        (target / 'nested').mkdir()
        link = self.root / 'linked'
        link.symlink_to(target, target_is_directory=True)
        for declared in (link, link / 'nested'):
            with self.subTest(declared=declared):
                out = io.StringIO()
                with (
                    patch.object(sys, 'argv', ['studio.py', '--root', str(declared), 'saved-work']),
                    patch('sys.stdout', out),
                ):
                    self.assertEqual(studio.main(), 0)
                said = json.loads(out.getvalue())
                self.assertFalse(said['complete'])
                self.assertEqual(said['unused'], [])
                self.assertEqual(said['scope']['roots'][0], str(declared))
                self.assertEqual(list((target / 'nested').iterdir()), [])

    def test_clean_local_scope(self):
        said = saved_work.scan(self.root)
        self.assertTrue(said['complete'])
        self.assertEqual(len(said['unused']), len(saved_work.IDS))
        self.assertEqual(list(self.root.iterdir()), [])

    def test_orphan_corrupt_unsupported_and_missing_are_unknown(self):
        for record in ({'schema': 99}, {'schema': 1}):
            with self.subTest(record=record):
                self.write(self.root / 'articles' / 'orphan' / 'session.json', record)
                before = self.snapshot()
                said = saved_work.scan(self.root, (self.root / 'absent',))
                self.assertFalse(said['complete'])
                self.assertEqual(said['unused'], [])
                self.assertEqual(before, self.snapshot())
        (self.root / 'articles' / 'orphan' / 'session.json').write_text('{')
        self.assertFalse(saved_work.scan(self.root)['complete'])

    def test_guided_and_recoverable_deleted_dependencies_without_expiry(self):
        for directory in (
            self.root / 'articles' / 'saved',
            self.root / '.blog-runs' / 'deleted' / 'old' / 'blog',
        ):
            self.write(
                directory / 'session.json',
                {'id': 'synthetic', 'title': 'Synthetic', 'mode': 'first-draft'},
            )
            self.write(
                directory / 'derived' / 'blog-run.json',
                {'schema': 1, 'approval': 'conversation', 'pipeline': ['research'], 'stages': {}},
            )
        self.write(
            self.root / '.blog-runs' / 'deleted' / 'old.json',
            {'schema': 1, 'deleted_at': '2000-01-01T00:00:00Z'},
        )
        before = self.snapshot()
        with patch('blog_runner.catalog', side_effect=AssertionError('No catalog')):
            said = saved_work.scan(self.root)
        self.assertTrue(said['complete'])
        gated = next(p for p in said['paths'] if p['id'] == 'gated-flow')
        self.assertEqual(len(gated['needed_by']), 2)
        self.assertEqual(before, self.snapshot())

    def test_excluded_link_and_enumeration_error(self):
        (self.root / 'articles').symlink_to(self.root, target_is_directory=True)
        self.assertFalse(saved_work.scan(self.root)['complete'])
        with patch.object(Path, 'iterdir', side_effect=PermissionError('Denied')):
            said = saved_work.scan(self.root)
        self.assertFalse(said['complete'])
        self.assertEqual(said['unused'], [])
