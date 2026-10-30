"""Presentation Studio uses the same explicit text-before-design checkpoint."""
from runner_support import DeskCase
from workspace import WorkspaceError

class ContentFirstTests(DeskCase):
    def test_text_waits_before_any_look_or_render_and_revision_is_required(self):
        self.engine.content_first = True
        root = self.start_desk(look='default')
        shown = self.view(root)['gate']
        self.assertEqual(shown['name'], 'gate:outline')
        self.assertTrue(shown['content_first'])
        self.assertTrue(shown['slides'])
        self.assertFalse((self.record(root).get('steps') or {}).get('look-preview', {}).get('done'))
        self.assertFalse((root / 'work' / 'build').exists())
        with self.assertRaises(WorkspaceError):
            self.engine.decide(root, 'gate:outline', 'approve', expected='wrong-version')
        self.engine.decide(root, 'gate:outline', 'changes', 'Clarify the first title.', expected=shown['expected'])
        revised = self.view(root)['gate']
        self.assertEqual(revised['name'], 'gate:outline')
        self.engine.decide(root, 'gate:outline', 'approve', expected=revised['expected'])
        self.assertEqual(self.waiting(root), 'gate:build')
        self.assertFalse(self.view(root)['problem'])
