from unittest import mock
from runner_support import StudioCase
from runner import decks, stages
from studio_core import review_policy


class ReviewLevelsTests(StudioCase):
    def test_balanced_combines_direction_then_deck_and_keeps_snapshot(self):
        with mock.patch.object(review_policy, 'capture', return_value={'schema': 1, 'level': 'balanced'}):
            root = self.start(research=True)
        shown = self.view(root)
        self.assertIsNone(shown['problem'])
        self.assertEqual(shown['gate']['name'], 'gate:outline')
        self.assertTrue(shown['gate']['research']['text'])
        self.assertIsNotNone(shown['gate']['look']['picture'])
        self.assertEqual(shown['review_level'], 'balanced')
        self.decide(root)
        shown = self.view(root)
        self.assertIsNone(shown['problem'])
        self.assertEqual(shown['gate']['name'], 'gate:build')
        self.decide(root)
        self.assertEqual(self.view(root)['state'], 'finished')
        run = decks.read_run(root)
        self.assertTrue(run['review_events'])
        self.assertEqual(run['gates']['gate:look']['by'], 'review-policy')
        self.assertEqual(run['gates']['gate:outline']['by'], 'Alex')

    def test_automatic_stops_only_at_rendered_deck_and_old_run_stays_strict(self):
        with mock.patch.object(review_policy, 'capture', return_value={'schema': 1, 'level': 'automatic'}):
            root = self.start(research=True)
        shown = self.view(root)
        self.assertIsNone(shown['problem'])
        self.assertEqual(shown['gate']['name'], 'gate:build')
        self.decide(root)
        self.assertEqual(self.view(root)['state'], 'finished')
        run = decks.read_run(root)
        run.pop('review_policy')
        self.assertEqual(review_policy.level(run), 'step_by_step')
        names = [s.name for s in stages.steps(run)]
        self.assertLess(names.index('gate:outline'), names.index('look-preview'))

    def test_combined_review_rejects_changed_material_and_can_research_again(self):
        from workspace import WorkspaceError
        with mock.patch.object(review_policy, 'capture', return_value={'schema': 1, 'level': 'balanced'}):
            root = self.start(research=True)
        shown = self.view(root)['gate']
        with self.assertRaises(WorkspaceError):
            self.engine.decide(root, 'gate:outline', 'approve', expected='old-version')
        returned = self.engine.decide(root, 'gate:outline', 'changes',
                                     'Clarify the answer to availability.',
                                     {'direction_target': 'gate:research'}, shown['expected'])
        self.assertIsNone(returned['problem'])
        self.assertEqual(returned['gate']['name'], 'gate:outline')
        self.assertEqual(decks.read_run(root)['schema'], 2)

    def test_balanced_document_classification_continues_without_an_extra_stop(self):
        with mock.patch.object(review_policy, 'capture', return_value={'schema': 1, 'level': 'balanced'}):
            root = self.start(route='document', research=True,
                              source={'kind': 'paste', 'text': 'Synthetic source material'})
        shown = self.view(root)
        self.assertIsNone(shown['problem'])
        self.assertEqual(shown['gate']['name'], 'gate:outline')
        self.assertEqual(decks.read_run(root)['gates']['gate:classify']['by'], 'review-policy')

    def test_brand_can_change_through_the_combined_review_page(self):
        from runner import page
        with mock.patch.object(review_policy, 'capture', return_value={'schema': 1, 'level': 'balanced'}):
            root = self.start(research=True)
        shown = self.view(root)['gate']
        reply = page.RunnerPage(8765, self.engine).decide({
            'path': str(root), 'gate': 'gate:outline', 'decision': 'changes',
            'expected': shown['expected'],
            'extra': {'direction_target': 'gate:look', 'brand': 'example', 'variant': 'dark'}})
        self.assertIsNone(reply['problem'])
        self.assertEqual(reply['gate']['name'], 'gate:outline')
        self.assertEqual(reply['gate']['look']['variant'], 'dark')
