"""Immutable tree reuse stays operation-scoped, bounded and revision-bound."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import os
from pathlib import Path
import tempfile
import unittest
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/blog-studio/scripts'))
import hub_store as store


class TreeReadCacheTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        environment = patch.dict(
            os.environ, {'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1'}
        )
        environment.start()
        self.addCleanup(environment.stop)
        store.git(self.root, 'init', '-q')
        self.commit = store.commit_files(
            self.root,
            None,
            {'first.md': b'First text'},
            'Synthetic snapshot',
            'Synthetic Author',
        )

    def test_reuses_one_verified_read_and_returns_independent_mappings(self):
        original = store.git
        with patch.object(store, 'git', wraps=original) as git:
            with store.tree_read_scope():
                first = store.tree_files(self.root, self.commit)
                first['first.md'] = b'Changed caller mapping'
                with store.tree_read_scope():
                    self.assertEqual(
                        store.tree_files(self.root, self.commit)['first.md'], b'First text'
                    )
                self.assertEqual(git.call_count, 2)
            store.tree_files(self.root, self.commit)
            self.assertEqual(git.call_count, 4)

    def test_new_commit_and_cache_budget_force_actual_reads(self):
        second = store.commit_files(
            self.root,
            self.commit,
            {'first.md': b'New text'},
            'Synthetic new snapshot',
            'Synthetic Author',
        )
        with store.tree_read_scope():
            self.assertEqual(store.tree_files(self.root, self.commit)['first.md'], b'First text')
            self.assertEqual(store.tree_files(self.root, second)['first.md'], b'New text')
        with (
            patch.object(store, 'MAX_TREE_CACHE_BYTES', 1),
            patch.object(store, 'git', wraps=store.git) as git,
        ):
            with store.tree_read_scope():
                store.tree_files(self.root, second)
                store.tree_files(self.root, second)
            self.assertEqual(git.call_count, 4)
