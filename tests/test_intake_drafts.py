"""Only disposable private intake files; no project, workspace or provider exists."""
import os
from pathlib import Path
import tempfile
import unittest

import marketing_studio  # noqa: F401
from studio_core import intake_drafts as drafts


class IntakeTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.data = Path(folder.name) / 'private'

    def send(self, action, **sent):
        return drafts.dispatch(self.data, 'workspace-a', {'action': action, **sent})

    def test_read_creates_nothing_and_saves_preserve_fields_and_source_pins(self):
        self.assertEqual(self.send('read'), {'revision': 0, 'draft': None})
        self.assertFalse(self.data.exists())
        first = self.send('save', expected=0, patch={'title': 'Synthetic', 'step': 1,
            'library': [{'id': 'document', 'revision': 4}], 'sourceDraft': {'id': 'capture', 'expected': 2}})
        last = self.send('save', expected=first['revision'], patch={'step': 2})
        self.assertEqual(last['draft']['library'][0]['revision'], 4)
        self.assertEqual(last['draft']['sourceDraft']['expected'], 2)
        self.assertEqual(self.send('read'), last)
        self.assertEqual(os.stat(drafts.path(self.data, 'workspace-a')).st_mode & 0o777, 0o600)

    def test_stale_tab_and_discard_cannot_replace_newer_values(self):
        held = self.send('save', expected=0, patch={'title': 'Kept'})
        for action, extra in [('save', {'patch': {'title': 'Old'}}), ('discard', {})]:
            with self.assertRaises(drafts.Conflict):
                self.send(action, expected=0, **extra)
        self.assertEqual(self.send('read'), held)
        cleared = self.send('discard', expected=held['revision'])
        self.assertIsNone(cleared['draft'])
        self.assertGreater(cleared['revision'], held['revision'])

    def test_identical_save_is_idempotent_and_workspaces_are_separate(self):
        held = self.send('save', expected=0, patch={'step': 1})
        self.assertEqual(self.send('save', expected=held['revision'], patch={'step': 1}), held)
        self.assertIsNone(drafts.dispatch(self.data, 'workspace-b', {'action': 'read'})['draft'])

    def test_unreadable_or_linked_draft_is_preserved(self):
        file = drafts.path(self.data, 'workspace-a')
        file.parent.mkdir(parents=True)
        file.write_text('damaged')
        with self.assertRaises(ValueError):
            self.send('save', expected=0, patch={'title': 'Replacement'})
        self.assertEqual(file.read_text(), 'damaged')
        target = self.data / 'unrelated'
        target.write_text('keep')
        file.unlink()
        file.symlink_to(target)
        with self.assertRaises(ValueError):
            self.send('discard', expected=0)
        self.assertEqual(target.read_text(), 'keep')
