from unittest import mock
from pathlib import Path
from test_runner_deck import CHOSEN, DeckCase
from runner_support import FORM, StudioCase
from runner import pipeline
import workspace
from workspace import WorkspaceError
from studio_core import review_policy


class ReviewLevelsTests(DeckCase):
    def choose(self, mode, **changes):
        with mock.patch.object(review_policy, 'capture', return_value={'schema': 1, 'level': mode}):
            root = self.begin(**changes)
        if mode == 'balanced':  # the research plan is read first, before anything is spent
            self.assertEqual(workspace.status(root)['gate'], 'research-plan', self.view(root))
            self.decide(root, 'research-plan')
        shown = self.view(root)
        self.assertIsNone(shown['problem'], shown)
        return root, shown

    def test_balanced_reads_the_research_plan_before_anything_is_researched(self):
        with mock.patch.object(review_policy, 'capture', return_value={'schema': 1, 'level': 'balanced'}):
            made = self.engine.start(pipeline.check_form({**FORM, 'deck_target': 'pptx',
                                                          'brand': CHOSEN}))
        root = Path(made['path'])
        self.assertEqual(made['gates'], 3)
        shown = self.view(root)
        self.assertEqual((shown['state'], shown['review']), ('waiting', None))
        self.assertEqual(workspace.status(root)['gate'], 'research-plan')
        self.assertEqual(set(self.kinds()), {'research-plan'}, 'nothing is researched before the plan is read')
        plan = self.steps(root)['gate:research-plan']
        self.assertEqual((plan['kind'], plan['status']), ('gate', 'waiting'))
        self.assertNotIn('automatically', plan['label'])
        shown = self.gate(root, 'research-plan')
        self.assertEqual((shown['waiting'], shown['decisions'][0]), (True, 'approve'))
        self.decide(root, 'research-plan')
        shown = self.view(root)
        self.assertIsNone(shown['problem'], shown)
        self.assertEqual(shown['review']['phase'], 'direction')
        self.assertEqual(workspace.load(root)['artifacts']['research-plan']['approved']['by'], 'page')
        self.assertEqual(workspace.load(root)['artifacts']['research']['approved']['by'], 'review-policy')

    def test_files_a_combined_review_covers_are_decided_there_only(self):
        import desk
        root, shown = self.choose('balanced')
        self.assertEqual(shown['review']['phase'], 'direction')
        gate = self.gate(root, 'research')
        self.assertEqual(gate['combined'], {'phase': 'direction', 'label': 'Review the direction',
                                            'name': 'direction review'})
        requests = len(workspace.load(root)['requests'])
        with self.assertRaisesRegex(desk.Refusal, 'direction review'):
            self.decide(root, 'research', 'revise', 'Add a worked example.')
        with self.assertRaisesRegex(desk.Refusal, 'direction review'):
            self.decide(root, 'blueprint', 'rebuild')
        self.assertEqual(len(workspace.load(root)['requests']), requests)
        self.assertEqual(self.view(root)['review']['phase'], 'direction')
        # Once the review is approved, nothing is pending and the gate says so.
        shown = self.approve_review(root, shown)
        self.assertEqual(shown['review']['phase'], 'final')
        self.assertEqual(self.gate(root, 'research')['combined']['phase'], 'final')
        shown = self.approve_review(root, shown)
        self.assertEqual(shown['state'], 'done')
        self.assertIsNone(self.gate(root, 'research')['combined'])

    def test_automatic_continues_past_the_research_plan(self):
        root, shown = self.choose('automatic')
        plan = self.steps(root)['gate:research-plan']
        self.assertEqual((plan['kind'], plan['status']), ('code', 'done'))
        self.assertIn('automatically', plan['label'])
        self.assertEqual(workspace.load(root)['artifacts']['research-plan']['approved']['by'], 'review-policy')

    def approve_review(self, root, shown):
        return self.engine.review_decide(root, shown['review']['expected'], 'approve')

    def test_balanced_all_levels_have_two_combined_reviews(self):
        root, shown = self.choose('balanced', levels=['101', '201'])
        self.assertEqual(shown['review']['phase'], 'direction')
        items = shown['review']['items']
        self.assertIn('research', [item['target'] for item in items])
        self.assertEqual(len([item for item in items if item.get('sample')]), 2)
        shown = self.approve_review(root, shown)
        self.assertIsNone(shown['problem'], shown)
        self.assertEqual(shown['review']['phase'], 'final')
        self.assertEqual(len([item for item in shown['review']['items'] if item.get('deck_view')]), 2)
        self.assertTrue(all(item['deck_view']['slides'] for item in shown['review']['items'] if item.get('deck_view')))
        shown = self.approve_review(root, shown)
        self.assertIsNone(shown['problem'], shown)
        self.assertEqual(shown['state'], 'done')
        self.assertTrue(shown['finished'])
        session = workspace.load(root)
        self.assertEqual(session['artifacts']['research']['approved']['by'], 'review-policy')
        record = self.engine._load(root)
        self.assertEqual(set(record['review_decisions']), {'direction', 'final'})

    def test_a_sample_slide_that_cannot_be_drawn_is_a_note_on_the_direction_review(self):
        # The renderer refuses, as it does when it is not signed in: the training is not
        # stopped for it. The direction review comes up with a note in the sample's place.
        self.slides.refuse['preview'] = ['The renderer could not be started.']
        root, shown = self.choose('balanced')
        self.assertEqual(shown['review']['phase'], 'direction')
        direction, = [item for item in shown['review']['items']
                      if item['target'].startswith('outline:')]
        self.assertNotIn('sample', direction)
        self.assertIn('A sample slide could not be drawn', direction['sample_note'])
        self.assertIn('The renderer could not be started.', direction['sample_note'])
        self.assertEqual(self.steps(root)['review-sample']['status'], 'done')
        # Once the renderer works again, approving the direction goes on to the materials.
        del self.slides.refuse['preview']
        shown = self.approve_review(root, shown)
        self.assertIsNone(shown['problem'], shown)
        self.assertEqual(shown['review']['phase'], 'final')

    def test_automatic_preserves_checks_and_rejects_old_review(self):
        root, shown = self.choose('automatic')
        self.assertEqual(shown['review']['phase'], 'final')
        other = self.make()
        other.resume()
        self.assertEqual(other.view(root)['review']['expected'], shown['review']['expected'])
        old = shown['review']['expected']
        document = root / workspace.artifact(root, workspace.load(root), 'document')['file']
        document.write_text(document.read_text() + '\nChanged externally\n')
        with self.assertRaises(WorkspaceError):
            self.engine.review_decide(root, old, 'approve')

    def test_change_to_direction_regenerates_and_returns_for_review(self):
        root, shown = self.choose('balanced')
        shown = self.engine.review_decide(root, shown['review']['expected'], 'revise',
                                          'outline:', 'Make the conclusion clearer.')
        self.assertIsNone(shown['problem'], shown)
        self.assertEqual(shown['review']['phase'], 'direction')
        shown = self.approve_review(root, shown)
        self.assertIsNone(shown['problem'], shown)
        self.assertEqual(shown['review']['phase'], 'final')

    def test_final_scenario_revision_does_not_repeat_the_unchanged_direction_review(self):
        root, shown = self.choose('balanced')
        shown = self.approve_review(root, shown)
        target = next(item['target'] for item in shown['review']['items']
                      if item['target'].startswith('scenario'))
        shown = self.engine.review_decide(root, shown['review']['expected'], 'revise',
                                          target, 'Make the persona clearer.')
        self.assertIsNone(shown['problem'], shown)
        self.assertEqual(shown['review']['phase'], 'final')
        self.assertEqual(self.approve_review(root, shown)['state'], 'done')

    def test_sample_images_and_review_notes_cannot_escape_the_training(self):
        import shutil
        root, shown = self.choose('balanced')
        sample = root / 'work/review-sample/sample.png'
        outside = self.base / 'outside.png'
        outside.write_bytes(sample.read_bytes())
        sample.unlink()
        sample.symlink_to(outside)
        with self.assertRaises((WorkspaceError, FileNotFoundError)):
            self.engine.picture(root, 1, 'deck', 'review-sample')
        sample.unlink()
        sample.write_bytes(outside.read_bytes())
        outside_notes = self.base / 'outside-notes'
        outside_notes.mkdir()
        (outside_notes / 'research.md').write_text('Private text must not be served.')
        shutil.rmtree(root / 'reviews')
        (root / 'reviews').symlink_to(outside_notes)
        with self.assertRaises(WorkspaceError):
            self.view(root)
        self.assertEqual((outside_notes / 'research.md').read_text(), 'Private text must not be served.')

    def test_new_review_findings_invalidate_the_displayed_final_decision(self):
        root, shown = self.choose('automatic')
        notes = root / workspace.review_file('deck')
        notes.write_text(notes.read_text() + '\nAn additional review finding.\n')
        with self.assertRaisesRegex(WorkspaceError, 'materials changed'):
            self.engine.review_decide(root, shown['review']['expected'], 'approve')

    def test_design_tool_continues_under_explicit_policy(self):
        self.slides.design = True
        root, shown = self.choose('automatic')
        self.assertEqual(shown['review']['phase'], 'final')
        self.assertTrue(self.slides.design_status(pipeline.place(root, None, pipeline.DESIGNS))['buildAllowed'])
        shown = self.approve_review(root, shown)
        self.assertEqual(shown['state'], 'done')


class NoDeckReviewTests(StudioCase):
    def test_automatic_without_deck_stops_for_finished_documents(self):
        with mock.patch.object(review_policy, 'capture', return_value={'schema': 1, 'level': 'automatic'}):
            root = self.start()
        shown = self.view(root)
        self.assertIsNone(shown['problem'], shown)
        self.assertEqual(shown['review']['phase'], 'final')
        shown = self.engine.review_decide(root, shown['review']['expected'], 'approve')
        self.assertEqual(shown['state'], 'done')
