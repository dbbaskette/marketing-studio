from unittest import mock
from test_runner_deck import CHOSEN, DeckCase
from runner_support import StudioCase
from runner import pipeline
import workspace
from workspace import WorkspaceError
from studio_core import review_policy


class ReviewLevelsTests(DeckCase):
    def test_row_124_finish_level_waits_for_building(self):
        root = None
        controls = []

        def preparing(tools, job):
            controls.append(self.view(root)['controls']['finish_level'])
            self.workers.document(tools, job)

        def building(tools, job):
            controls.append(self.view(root)['controls']['finish_level'])
            self.workers.section(tools, job)

        with mock.patch.object(review_policy, 'capture', return_value={'schema': 1, 'level': 'balanced'}):
            root = self.saved_begin(levels=['101'])
        self.workers.then('document', preparing)
        self.decide(root, 'research-plan')
        self.workers.then('section', building)
        self.approve_review(root, self.view(root))
        self.assertEqual(controls, [None, '101'])

    def test_balanced_reviews_the_direction_before_any_brief_is_written(self):
        root, shown = self.choose('balanced', levels=['101', '201'])
        self.assertEqual(shown['review']['phase'], 'direction')
        self.assertTrue((root / '101/document.md').is_file())
        self.assertTrue((root / '201/document.md').is_file())
        self.assertEqual(list(root.glob('*/*-brief.md')), [])
        self.assertFalse(any(item['target'].startswith('brief@') for item in shown['review']['items']))
        self.assertEqual(shown['review']['commits']['materials'], ['brief', 'scenario'])
        self.assertTrue(shown['review']['commits']['deck'])

    def test_row_123_a_run_past_its_direction_review_keeps_it(self):
        from runner import reviews
        with mock.patch.object(reviews, 'LAYOUT', 1, create=True):
            root, shown = self.choose('balanced', levels=['101'])
        record = self.engine._load(root)
        record.pop('review_layout', None)
        self.engine._store(root, record)
        shown = self.approve_review(root, self.view(root))
        self.assertEqual(shown['review']['phase'], 'final')
        since = len(self.workers.jobs)
        self.engine.wake(root)
        found = self.engine._survey(root, self.engine._load(root))
        self.assertIn('review:direction', found.done)
        self.assertFalse(any(kind == 'brief' for kind, _, _ in self.workers.jobs[since:]))

    def test_approving_the_direction_writes_the_briefs_then_builds(self):
        root, shown = self.choose('balanced', levels=['101', '201'])
        since = len(self.workers.jobs)
        shown = self.approve_review(root, shown)
        kinds = [kind for kind, _, _ in self.workers.jobs[since:]]
        self.assertEqual(kinds.count('brief'), 2)
        self.assertLess(kinds.index('brief'), kinds.index('section'))
        self.assertEqual(shown['review']['phase'], 'final')

    def choose(self, mode, **changes):
        with mock.patch.object(review_policy, 'capture', return_value={'schema': 1, 'level': mode}):
            root = self.saved_begin(**changes)
        if mode == 'balanced':  # the research plan is read first, before anything is spent
            self.assertEqual(workspace.status(root)['gate'], 'research-plan', self.view(root))
            self.decide(root, 'research-plan')
        shown = self.past_decks(root)
        self.assertIsNone(shown['problem'], shown)
        return root, shown

    def past_decks(self, root):
        """Approve each drawn deck waiting at its own gate, as the person does: a deck is
        never continued under the saved level."""
        for _ in range(4):
            waiting = workspace.status(root)['gate']
            if not waiting or workspace.split(waiting)[0] != 'deck':
                break
            self.decide(root, waiting)
        return self.view(root)

    def test_saved_documents_only_balanced_training_keeps_its_plan(self):
        from studio_core import research_contract
        root = self.saved_start(deck_target='pptx', brand=CHOSEN, review_level='balanced',
                                source_scope='supplied-only',
                                saved_contract=research_contract.snapshot(self.research),
                                research_from={'documents': True, 'sites': [], 'web': False})
        self.assertTrue(pipeline.planned_from_form(self.engine._load(root)))

    def test_balanced_reads_the_research_plan_before_anything_is_researched(self):
        root = self.saved_start(deck_target='pptx', brand=CHOSEN, review_level='balanced')
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

    def test_the_direction_review_shows_the_plan_s_questions(self):
        root, shown = self.choose('balanced')
        item = next(item for item in shown['review']['items'] if item['target'] == 'research-plan')
        self.assertEqual(item['document']['kind'], 'questions')
        self.assertTrue(item['document']['questions'])

    def test_files_a_combined_review_covers_are_decided_there_only(self):
        import desk
        root, shown = self.choose('balanced')
        self.assertEqual(shown['review']['phase'], 'direction')
        gate = self.gate(root, 'research')
        self.assertEqual(gate['combined'], {'phase': 'direction',
                                            'label': 'Review the first drafts',
                                            'name': 'first drafts review'})
        requests = len(workspace.load(root)['requests'])
        with self.assertRaisesRegex(desk.Refusal, 'first drafts review'):
            self.decide(root, 'research', 'revise', 'Add a worked example.')
        with self.assertRaisesRegex(desk.Refusal, 'first drafts review'):
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

    def test_the_deck_can_be_left_out_from_the_direction_review_before_it_is_drawn(self):
        root, shown = self.choose('balanced')
        self.assertEqual(shown['review']['phase'], 'direction')
        self.assertEqual(shown['controls'], {'grouped': True, 'finish_level': None, 'finishing': None,
                                             'skip_deck': True})
        self.assertIn('outline:', [item['target'] for item in shown['review']['items']])
        since = len(self.workers.jobs)
        # Leaving the deck out is about the training, not one file: the review lets it through.
        self.decide(root, 'deck', 'skip', 'We present from the guide.')
        shown = self.view(root)
        self.assertIsNone(shown['problem'], shown)
        self.assertEqual(shown['review']['phase'], 'direction')
        self.assertNotIn('outline:', [item['target'] for item in shown['review']['items']])
        self.assertFalse(shown['controls']['skip_deck'])
        self.assertFalse(shown['review']['commits']['deck'])
        shown = self.approve_review(root, shown)
        self.assertEqual(shown['review']['phase'], 'final')
        shown = self.approve_review(root, shown)
        self.assertEqual(shown['state'], 'done')
        self.assertNotIn('section', self.kinds(since))
        self.assertNotIn('deck', workspace.load(root)['settings']['stages'])

    def test_the_plan_stop_reaches_a_balanced_run_started_earlier_unless_it_is_past_it(self):
        # The saved policy is not versioned: the stop is what Balanced means. A training
        # started before the stop existed and not yet at its plan gets it; one already past
        # its plan is left where it is.
        from runner_support import fails

        def before(record, product, gate, last=None, holding=(), first='outline',
                   run_gates=None):
            return not gate.startswith('review:') and gate not in ('documents', 'intake', 'deck')

        with mock.patch.object(review_policy, 'automatic', before):
            self.workers.then('research-plan', fails(), fails(), fails())  # every try
            with mock.patch.object(review_policy, 'capture', return_value={'schema': 1, 'level': 'balanced'}):
                early = self.saved_begin(title='Started earlier')
                past = self.saved_begin(title='Already past its plan')
            self.assertEqual(self.view(early)['state'], 'failed')
            self.assertEqual(self.view(past)['review']['phase'], 'direction')
        self.assertEqual(self.engine._load(early)['review_policy'], {'schema': 1, 'level': 'balanced'})
        # The one not yet at its plan stops there once it gets there.
        self.engine.act(early, 'retry')
        shown = self.view(early)
        self.assertEqual((shown['state'], shown['review']), ('waiting', None))
        self.assertEqual(workspace.status(early)['gate'], 'research-plan')
        # The one already past it is not asked again.
        shown = self.view(past)
        self.assertEqual(shown['review']['phase'], 'direction')
        self.assertEqual(workspace.load(past)['artifacts']['research-plan']['approved']['by'],
                         'review-policy')

    def test_automatic_continues_past_the_research_plan(self):
        root, shown = self.choose('automatic')
        plan = self.steps(root)['gate:research-plan']
        self.assertEqual((plan['kind'], plan['status']), ('code', 'done'))
        self.assertIn('automatically', plan['label'])
        self.assertEqual(workspace.load(root)['artifacts']['research-plan']['approved']['by'], 'review-policy')

    def approve_review(self, root, shown):
        self.engine.review_decide(root, shown['review']['expected'], 'approve')
        return self.past_decks(root)

    def test_balanced_asks_for_the_draft_and_the_look_in_one_stop(self):
        self.brand.offers_looks = True
        root, shown = self.choose('balanced')
        self.assertEqual(shown['review']['phase'], 'direction')
        direction, = [item for item in shown['review']['items']
                      if item['target'].startswith('outline:')]
        # The brand's looks, never a cover drawn in the studio's own colours.
        self.assertNotIn('sample', direction)
        self.assertEqual([look['id'] for look in direction['looks']['looks']],
                         ['example-contrast', 'example-calm'])
        self.assertNotIn('review-sample', [call for call in self.slides.calls])
        with self.assertRaisesRegex(WorkspaceError, 'Pick a look'):
            self.engine.review_decide(root, shown['review']['expected'], 'approve')
        self.engine.review_decide(root, shown['review']['expected'], 'approve',
                                  looks={'': {'choice': 'example-calm',
                                              'words': 'Calm suits a first course.'}})
        shown = self.view(root)
        self.assertIsNone(shown['problem'], shown)
        # No second stop for the look: it was picked with the draft.
        self.assertEqual(workspace.status(root)['gate'], 'deck')
        chosen = self.engine._load(root)['deck']['']['look']['chosen']
        self.assertEqual((chosen['id'], chosen['by'], chosen['words']),
                         ('example-calm', 'page', 'Calm suits a first course.'))
        self.assertTrue(self.brand.written[-1], 'the brand wrote the outline with the look')

    def test_a_review_approved_before_looks_were_offered_stays_approved(self):
        # A training approved under the code before this: its direction signature had no
        # looks. An older brand draws none, so nothing of looks enters it now either.
        from runner import reviews
        root, shown = self.choose('balanced')
        session, record = workspace.load(root), self.engine._load(root)
        before = reviews.contents(root, session, record, 'direction')
        self.assertFalse([key for key in before['files'] if key.endswith(':looks')])
        shown = self.approve_review(root, shown)
        self.assertEqual(shown['review']['phase'], 'final')
        shown = self.approve_review(root, shown)
        self.assertEqual(shown['state'], 'done')
        # Looked at again, as a new runner would after the upgrade, it is still done.
        other = self.make()
        other.resume()
        self.assertEqual(other.view(root)['state'], 'done')
        self.assertIsNone(other.view(root)['review'])

    def test_balanced_offers_a_way_on_when_the_looks_cannot_be_rendered(self):
        self.brand.offers_looks, self.brand.cannot_render = True, True
        root, shown = self.choose('balanced')
        direction, = [item for item in shown['review']['items']
                      if item['target'].startswith('outline:')]
        self.assertTrue(direction['looks']['failed'])
        with self.assertRaisesRegex(WorkspaceError, 'Pick a look'):
            self.engine.review_decide(root, shown['review']['expected'], 'approve',
                                      looks={'': {'choice': 'example-calm'}})
        # Tried again: still not rendered, and the review is back, not approved.
        shown = self.engine.review_decide(root, shown['review']['expected'], 'approve',
                                          looks={'': {'choice': pipeline.AGAIN_LOOK}})
        self.assertEqual(shown['review']['phase'], 'direction')
        self.assertNotIn('direction', self.engine._load(root).get('review_decisions') or {})
        # Then the brand's default, chosen knowingly.
        self.engine.review_decide(root, shown['review']['expected'], 'approve',
                                  looks={'': {'choice': pipeline.DEFAULT_LOOK}})
        self.assertEqual(workspace.status(root)['gate'], 'deck')
        chosen = self.engine._load(root)['deck']['']['look']['chosen']
        self.assertEqual((chosen['by'], chosen['shown']), ('page', 'unrendered'))

    def test_a_drawn_deck_always_comes_to_the_person(self):
        # Balanced and Automatic draft both stop at the deck itself, before the scenarios
        # and the final review: the policy never accepts a drawn deck for the person.
        for mode in ('balanced', 'automatic'):
            with self.subTest(mode=mode):
                with mock.patch.object(review_policy, 'capture',
                                       return_value={'schema': 1, 'level': mode}):
                    root = self.saved_begin(title=f'Deck stop {mode}')
                if mode == 'balanced':
                    self.decide(root, 'research-plan')
                    shown = self.view(root)
                    self.engine.review_decide(root, shown['review']['expected'], 'approve')
                shown = self.view(root)
                self.assertIsNone(shown['problem'], shown)
                self.assertEqual(workspace.status(root)['gate'], 'deck')
                gate = self.steps(root)['gate:deck']
                self.assertEqual((gate['kind'], gate['status']), ('gate', 'waiting'))
                self.assertNotIn('automatically', gate['label'])
                record = self.engine._load(root)
                self.assertNotIn('gate:deck', [event['gate'] for event in
                                               record.get('review_events') or ()])
                self.decide(root, 'deck')
                shown = self.view(root)
                self.assertEqual(shown['review']['phase'], 'final')
                self.assertEqual(workspace.load(root)['artifacts']['deck']['approved']['by'],
                                 'page')

    def test_the_first_drafts_sheet_lists_only_what_approving_writes(self):
        root, shown = self.choose('balanced', levels=['101'])
        self.assertEqual(shown['review']['label'], 'Review the first drafts')
        # Guides are already written; briefs and scenarios follow this approval.
        self.assertEqual(shown['review']['commits']['materials'], ['brief', 'scenario'])

    def test_row_121_first_drafts_approval_starts_only_what_is_still_to_write(self):
        root, shown = self.choose('balanced', levels=['101'])
        since = len(self.workers.jobs)
        self.approve_review(root, shown)
        started = {kind for kind, _, _ in self.workers.jobs[since:]}
        self.assertIn('scenario', started)
        self.assertFalse(started & {'research', 'blueprint', 'document'}, started)

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

    def test_change_requests_are_sent_together_and_say_what_they_rewrite(self):
        root, shown = self.choose('balanced', levels=['101', '201'])
        items = {item['target']: item for item in shown['review']['items']}
        self.assertEqual(items['research']['rewrites'], [
            'the level 101 blueprint', 'the level 101 learner guide',
            'the level 201 blueprint', 'the level 201 learner guide',
            'the level 101 deck outline', 'the level 201 deck outline'])
        self.assertEqual(items['blueprint@201']['rewrites'], [
            'the level 201 learner guide', 'the level 201 deck outline'])
        self.assertEqual(items['outline:201']['rewrites'], [])
        commits = shown['review']['commits']
        self.assertEqual({key: commits[key] for key in ('levels', 'materials', 'deck')},
                         {'levels': 2, 'materials': ['brief', 'scenario'], 'deck': True})
        self.assertGreater(commits['dollars'], 0)
        self.assertGreater(commits['minutes'], 0)
        expected = shown['review']['expected']
        # Every request is checked before any is recorded.
        for asked, why in (
            ([{'target': 'research', 'note': 'More sources.'}, {'target': 'deck', 'note': 'x'}],
             'from this review'),
            ([{'target': 'research', 'note': ''}], 'Say what should change'),
            ([], 'Say what should change'),
            ([{'target': 'research', 'note': 'One.'}, {'target': 'research', 'note': 'Two.'}],
             'once for each'),
        ):
            with self.subTest(asked=asked), self.assertRaisesRegex(WorkspaceError, why):
                self.engine.review_decide(root, expected, 'revise', requests=asked)
        self.assertEqual(workspace.load(root)['requests'], [])
        self.assertEqual(self.view(root)['review']['expected'], expected)
        since = len(self.workers.jobs)
        shown = self.engine.review_decide(root, expected, 'revise', requests=[
            {'target': 'blueprint@101', 'note': 'Add a module on health checks.'},
            {'target': 'outline:201', 'note': 'Open with the objection.'}])
        self.assertIsNone(shown['problem'], shown)
        self.assertEqual(shown['review']['phase'], 'direction')
        self.assertNotEqual(shown['review']['expected'], expected)
        # Both were taken: the level 101 blueprint was written again, and so was what the
        # level 201 deck says. The research was not. The scripted blueprint comes back
        # unchanged, so nothing built from it is written again: the core goes by content.
        self.assertEqual(self.kinds(since), ['blueprint', 'outline'])
        self.assertIn('request changes to 2 items', self.git('log', '-3', '--format=%s'))
        shown = self.approve_review(root, shown)
        self.assertEqual(shown['review']['phase'], 'final')
        self.assertIsNone(shown['review']['commits'])

    def test_row_134_a_final_change_keeps_the_first_drafts_approval(self):
        root, shown = self.choose('balanced', levels=['101'])
        shown = self.approve_review(root, shown)
        self.assertEqual(shown['review']['phase'], 'final')
        guide = next(item for item in shown['review']['items']
                     if item['target'] == 'document@101')
        self.assertIn('the level 101 slide deck', guide['rewrites'])
        from runner_support import DOCUMENT

        def shorter(tools, job):
            accepted = tools.submit_artifact('document', DOCUMENT.replace('25 minutes',
                                                                          '20 minutes'))
            assert accepted[0], accepted[1]
            tools.submit_review('Shortened, as asked.')
        self.workers.then('document', shorter)
        outlined = len([event for event in self.engine._load(root).get('review_events') or ()
                        if event['gate'] == 'gate:deck-outline@101'])
        self.engine.review_decide(root, shown['review']['expected'], 'revise',
                                  'document@101', 'Shorten the second section.')
        record = self.engine._load(root)
        self.assertIn('direction', record.get('review_decisions') or {})
        seen = []
        for _ in range(6):
            shown = self.view(root)
            waiting = workspace.status(root)['gate']
            seen.append((shown['review'] or {}).get('phase') or waiting)
            if shown['review'] and shown['review']['phase'] == 'final':
                break
            self.assertIsNotNone(waiting, shown)
            self.decide(root, waiting)
        self.assertNotIn('direction', seen)
        self.assertEqual(seen, ['deck@101', 'final'])
        events = [event for event in self.engine._load(root).get('review_events') or ()
                  if event['gate'] == 'gate:deck-outline@101']
        # The scripted outline writer writes the same outline again, so the core keeps it;
        # whichever way, the deck outline is the policy's, never a stop of its own.
        self.assertGreaterEqual(len(events), outlined)
        self.assertEqual({event['by'] for event in events}, {'review-policy'})

    def test_a_kept_first_drafts_approval_ends_with_the_finished_materials(self):
        root, shown = self.choose('balanced', levels=['101'])
        shown = self.approve_review(root, shown)
        self.engine.review_decide(root, shown['review']['expected'], 'revise',
                                  'document@101', 'Shorten the second section.')
        self.assertTrue(self.engine._load(root)['review_decisions']['direction'].get('carried'))
        for _ in range(6):
            shown = self.view(root)
            if shown['review'] and shown['review']['phase'] == 'final':
                break
            self.decide(root, workspace.status(root)['gate'])
        self.engine.review_decide(root, shown['review']['expected'], 'approve')
        kept = self.engine._load(root)['review_decisions']['direction']
        self.assertNotIn('carried', kept, 'approving the finished materials settles it')
        from runner import reviews
        found = self.engine._survey(root, self.engine._load(root))
        self.assertEqual(kept['signature'], reviews.signature(
            root, found.session, self.engine._load(root), 'direction'))

    def test_a_change_outside_the_review_brings_the_first_drafts_back(self):
        root, shown = self.choose('balanced', levels=['101'])
        shown = self.approve_review(root, shown)
        self.engine.review_decide(root, shown['review']['expected'], 'revise',
                                  'document@101', 'Shorten the second section.')
        record = self.engine._load(root)
        from runner import reviews
        reviews.uncarry(record)
        self.assertNotIn('direction', record['review_decisions'],
                         'a change made elsewhere is reviewed with the first drafts again')

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
        root, shown = self.choose('automatic', walkthrough=True)
        self.assertEqual(shown['review']['phase'], 'final')
        self.assertTrue(self.slides.design_status(pipeline.place(root, None, pipeline.DESIGNS))['buildAllowed'])
        shown = self.approve_review(root, shown)
        self.assertEqual(shown['state'], 'done')


class NoDeckReviewTests(StudioCase):
    def test_automatic_without_deck_stops_for_finished_documents(self):
        with mock.patch.object(review_policy, 'capture', return_value={'schema': 1, 'level': 'automatic'}):
            root = self.saved_start()
        shown = self.view(root)
        self.assertIsNone(shown['problem'], shown)
        self.assertEqual(shown['review']['phase'], 'final')
        shown = self.engine.review_decide(root, shown['review']['expected'], 'approve')
        self.assertEqual(shown['state'], 'done')


class FormPlanPolicyTests(StudioCase):
    def test_balanced_accepts_a_plan_written_from_the_form(self):
        from studio_core import research_contract
        for level in ('balanced', 'automatic'):
            with self.subTest(level=level), mock.patch.object(research_contract, 'snapshot', return_value={'schema': 2, 'version': '1.0.0', 'digest': 'synthetic'}):
                root = self.saved_start(title='Supplied ' + level, source_scope='supplied-only', review_level=level, saved_contract={'schema': 2, 'version': '1.0.0', 'digest': 'synthetic'})
            self.send(root, 'synthetic.md')
            self.engine.supply(root, 'done')
            session = workspace.load(root)
            self.assertEqual(workspace.statuses(root, session)['research-plan'], 'approved')
            self.assertEqual(session['artifacts']['research-plan']['approved']['by'], 'review-policy')
            self.assertEqual(self.workers.of('research-plan'), [])
