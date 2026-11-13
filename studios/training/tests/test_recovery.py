"""Ways on from a deck that stopped on the desk, beside Try again (`runner.recovery`)."""
from test_runner_deck import DeckCase

import workspace
from workspace import WorkspaceError

from runner import pipeline, recovery
from runner_support import fails


class RecoveryTests(DeckCase):
    def stopped(self, **form):
        """A desk training whose deck stopped at a section, with no slide text approval."""
        self.engine.content_first = True
        self.workers.then('section', *[fails()] * 12)
        root = self.begin(flow='desk', slide_text_review=False, **form)
        view = self.view(root)
        self.assertIn('Draw section', view['problem']['what'], view)
        return root, view

    def test_a_stopped_deck_offers_its_ways_on_beside_try_again(self):
        root, view = self.stopped()
        self.assertEqual(view['problem']['action'], 'retry')
        self.assertEqual([way['id'] for way in view['problem']['ways']],
                         ['slide-text', 'leave-deck'])
        self.assertEqual(view['problem']['ways'][0]['label'], 'Review the slide text')
        self.assertFalse(view['deck_aside'])

    def test_a_deck_the_runner_stopped_itself_offers_the_same_ways_on(self):
        # Such as a brand that changed under the deck: recorded as stopped, not failed.
        root, view = self.stopped()
        record = self.engine._load(root)
        record['problem'].update(state='stopped', step='deck-sections')
        with self.engine.files:
            self.engine._store(root, record)
        self.assertEqual([way['id'] for way in self.view(root)['problem']['ways']],
                         ['slide-text', 'leave-deck'])
        self.workers.queued.pop('section', None)
        shown = self.engine.act(root, 'slide-text')['outline']
        self.assertTrue(shown['waiting'] and shown['content_first'])

    def test_a_stop_that_is_not_a_decks_offers_nothing_more(self):
        self.engine.content_first = True
        self.workers.then('document', *[fails()] * 3)
        root = self.begin(flow='desk', slide_text_review=False)
        view = self.view(root)
        self.assertIsNotNone(view['problem'], view)
        self.assertNotIn('ways', view['problem'])
        with self.assertRaisesRegex(WorkspaceError, 'not offered'):
            self.engine.act(root, 'leave-deck')

    def test_review_the_slide_text_waits_for_approval_and_then_draws(self):
        root, view = self.stopped()
        self.assertEqual(self.record(root)['deck']['']['approved']['by'], 'desk')
        self.workers.queued.pop('section', None)
        drawn = len(self.workers.of('section'))
        view = self.engine.act(root, 'slide-text')
        self.assertIsNone(view['problem'], view)
        shown = view['outline']
        self.assertTrue(shown['waiting'] and shown['content_first'], shown)
        self.assertEqual(len(self.workers.of('section')), drawn, 'nothing is drawn yet')
        self.engine.outline(root, None, 'approve', seen=shown['sha256'])
        self.assertGreater(len(self.workers.of('section')), drawn)
        self.assertIsNone(self.view(root)['problem'])
        self.assertEqual(self.record(root)['deck']['']['approved']['by'], 'page')

    def test_finish_without_the_deck_sets_it_aside_and_it_can_come_back(self):
        root, view = self.stopped()
        view = self.engine.act(root, 'leave-deck')
        self.assertIsNone(view['problem'], view)
        self.assertTrue(view['deck_aside'])
        self.assertNotIn('deck', workspace.load(root)['settings']['stages'])
        self.assertTrue((root / pipeline.OUTLINE).is_file(), 'its slide text is kept')
        with self.assertRaisesRegex(WorkspaceError, 'not offered'):
            self.engine.act(root, 'leave-deck')
        self.workers.queued.pop('section', None)
        drawn = len(self.workers.of('section'))
        view = self.engine.act(root, 'bring-deck')
        self.assertFalse(view['deck_aside'])
        self.assertIn('deck', workspace.load(root)['settings']['stages'])
        self.assertIsNone(view['problem'], view)
        self.assertGreater(len(self.workers.of('section')), drawn, 'it carries on drawing')
        self.assertEqual(len(self.workers.of('outline')),
                         len([job for job in self.workers.of('outline')]))

    def test_a_deck_left_out_another_way_is_not_brought_back_from_here(self):
        self.engine.content_first = True
        root = self.begin(flow='desk', slide_text_review=False)
        self.assertFalse(self.view(root)['deck_aside'])
        with self.assertRaisesRegex(WorkspaceError, 'not offered'):
            self.engine.act(root, 'bring-deck')
        self.assertEqual(recovery.level_of('deck-sections@301:3'), '301')
        self.assertIsNone(recovery.level_of('deck-look'))


class DesignedRecoveryTests(RecoveryTests):
    """The same, for a deck written with each slide's design, as a walkthrough asks."""

    def setUp(self):
        super().setUp()
        self.slides.design = True

    def stopped(self, **form):
        return super().stopped(walkthrough=True, **form)

    def test_the_slide_text_comes_back_with_its_design(self):
        root, view = self.stopped()
        self.workers.queued.pop('section', None)
        shown = self.engine.act(root, 'slide-text')['outline']
        self.assertIsNotNone(shown['design'])
        self.engine.outline(root, None, 'approve', seen=shown['sha256'])
        self.assertIsNone(self.view(root)['problem'])
