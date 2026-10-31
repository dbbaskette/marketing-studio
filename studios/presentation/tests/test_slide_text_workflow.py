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

    def kept(self, root):
        """What a saved deck has decided and done: its gates, steps and receipts."""
        record = self.record(root)
        return {key: record.get(key) for key in ('gates', 'steps', 'review_events',
                                                 'deck_content')}

    def restarted(self):
        """The runner started again with text-first starts on, as after an update."""
        self.engine.close()
        self.engine = self.make(content_first=True)
        self.engine.resume()

    def test_a_deck_saved_before_text_first_keeps_its_decisions(self):
        root = self.start_desk(look='pick')
        self.assertEqual(self.waiting(root), 'gate:look')
        before, jobs = self.kept(root), len(self.workers.jobs)
        self.assertIsNone(before['deck_content'])
        self.restarted()
        # Nothing is asked again and nothing runs again: the deck still waits for its look.
        self.assertEqual(self.kept(root), before)
        self.assertEqual(len(self.workers.jobs), jobs)
        shown = self.view(root)
        self.assertEqual(shown['gate']['name'], 'gate:look')
        self.assertFalse(shown['desk']['content_pending'])
        self.pick_look(root)
        self.on_desk(root)
        self.assertNotIn('deck_content', self.record(root))

    def test_approved_slide_text_stays_approved_when_the_runner_starts_again(self):
        self.engine.content_first = True
        root = self.start_desk(look='pick')
        gate = self.view(root)['gate']
        self.engine.decide(root, 'gate:outline', 'approve', expected=gate['expected'])
        self.assertEqual(self.waiting(root), 'gate:look')
        before, jobs = self.kept(root), len(self.workers.jobs)
        self.restarted()
        self.assertEqual(self.kept(root), before)
        self.assertEqual(len(self.workers.jobs), jobs)
        self.assertEqual(self.view(root)['gate']['name'], 'gate:look')
        self.assertFalse(self.view(root)['desk']['content_pending'])
