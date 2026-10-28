"""The Training Studio desk's scoped deck changes."""
import copy
import json
from unittest import mock

from test_runner_deck import DeckCase, MAJOR, PageCase
from runner_support import drawn
import workspace
from runner import deck, drafts, pipeline


class SlideNoteTests(DeckCase):
    def test_row_166_a_slide_note_redraws_its_section_only(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        before = self.built(root)
        first = before['sections']['section-1']
        drawing = (root / pipeline.WORK / first['file']).read_bytes()
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        count = len(self.workers.of('section'))
        reviews = len(self.workers.of('review'))
        self.workers.placing['check-yourself'] = [{'type': 'box', 'id': 's2_detail', 'text': 'Detail'}]
        self.workers.found = [[{**MAJOR, 'slide': 'check-yourself'}]]
        self.engine.slide_note(root, None, 'check-yourself', 'Make the diagram larger.', seen)
        self.to_end(root)
        after = self.built(root)
        self.assertEqual(len(self.workers.of('section')), count + 1)
        job = self.workers.jobs[-1]  # review follows the single composer
        section_job = next(spec for kind, _, spec in reversed(self.workers.jobs) if kind == 'section')
        self.assertIn('what the person asked', [entry['name'] for entry in section_job['inputs']])
        self.assertEqual(set(section_job['artifacts']['section']['frozen']), {'the-objection'})
        self.assertEqual(len(self.workers.of('review')), reviews + 1)
        self.assertEqual([slide['id'] for slide in job[2]['review']['slides']], ['check-yourself'])
        self.assertTrue(self.engine.deck_proposals(root, None)['review']['items'])
        self.assertEqual(workspace.person_statuses(root, workspace.load(root))['deck'], 'draft')
        self.assertEqual((root / pipeline.WORK / after['sections']['section-1']['file']).read_bytes(), drawing)
        self.assertEqual(self.engine._load(root)['deck']['']['notes'][-1]['status'], 'done')

    def test_a_frozen_slide_cannot_change(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        built = self.built(root)
        section = json.loads((root / pipeline.WORK / built['sections']['section-2']['file']).read_text())
        frozen = copy.deepcopy(section['slides'][0])
        section['slides'][0]['canvas'] = []
        whole = json.loads((root / pipeline.WORK / built['start']['folder'] / 'given' / 'outline.json').read_text())
        spec = deck.fixed(whole, built['start']['sections'][1]['slides'], 2, None)
        spec['frozen'] = {frozen['id']: frozen}
        self.assertTrue(any('this slide has no requested repair. Keep its drawing unchanged.' in p
                            for p in deck.kept(section, spec)))

    def test_a_composer_cannot_submit_a_changed_frozen_slide(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        refusals = []

        def compose(tools, job):
            spec = tools.job['artifacts']['section']
            made = drawn(spec)
            made['slides'][0]['brief']['rhythm'] = 'changed'
            frozen = spec.pop('frozen')
            try:
                self.assertTrue(tools.preview_section(json.dumps(made))[0])
            finally:
                spec['frozen'] = frozen
            accepted, said = tools.submit_section(json.dumps(made))
            self.assertFalse(accepted)
            refusals.append(said)
            made['slides'][0] = frozen[made['slides'][0]['id']]
            self.assertTrue(tools.preview_section(json.dumps(made))[0])
            self.assertTrue(tools.submit_section(json.dumps(made))[0])

        self.workers.then('section', compose)
        self.engine.slide_note(root, None, 'check-yourself', 'Make the diagram larger.', seen)
        self.assertIn('this slide has no requested repair. Keep its drawing unchanged.', refusals[0])

    def test_a_note_arriving_after_survey_is_handed_in_before_it_is_done(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        self.engine.slide_note(root, None, 'check-yourself', 'FIRST NOTE', seen, _defer=True)
        original_section = self.engine._section
        original_work = pipeline.section_work
        captured = []
        injected = False

        def before_section(root, run, found, step, section, how):
            nonlocal injected
            if not injected:
                injected = True
                self.engine.slide_note(root, None, 'the-objection', 'SECOND NOTE', seen,
                                       _defer=True)
            return original_section(root, run, found, step, section, how)

        def capture_work(*args, **kwargs):
            work = original_work(*args, **kwargs)
            captured.append(work.prepared)
            return work

        with mock.patch.object(self.engine, '_section', side_effect=before_section), \
                mock.patch.object(pipeline, 'section_work', side_effect=capture_work):
            self.engine.carry_on(root)
        self.to_end(root)
        notes = self.engine._load(root)['deck']['']['notes']
        self.assertEqual([note['status'] for note in notes], ['done', 'done'])
        self.assertIn('FIRST NOTE', captured[0]['inputs']['what the person asked'])
        self.assertIn('SECOND NOTE', captured[0]['inputs']['what the person asked'])
        self.assertNotIn('the-objection', captured[0]['artifacts']['section']['frozen'])
        self.assertEqual(set(self.built(root)['rounds'][-1]['review_slides']),
                         {'the-objection', 'check-yourself'})

    def test_a_note_on_a_section_being_drawn_waits(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        record = self.engine._load(root)
        seen = record['deck']['']['saved']['sha256']
        record['deck']['']['notes'] = [{'id': 'one', 'slide': 'check-yourself', 'section': 'section-2',
                                        'note': 'Change it.', 'status': 'drawing'}]
        self.engine._store(root, record)
        with self.assertRaisesRegex(Exception, 'Slide 5 is being redrawn now'):
            self.engine.slide_note(root, None, 'check-yourself', 'Another note.', seen)

        record['deck']['']['notes'] = []
        self.engine._store(root, record)
        self.engine._run(root).workers['deck-sections:2'] = {}
        with self.assertRaisesRegex(Exception, 'Slide 5 is being redrawn now'):
            self.engine.slide_note(root, None, 'check-yourself', 'Another note.', seen)
        self.engine._run(root).workers.clear()


    def test_review_finding_apply_makes_a_priced_note(self):
        self.workers.found = [[{**MAJOR, 'slide': 'check-yourself'}], []]
        root = self.begin(flow='desk')
        self.to_end(root)
        shown = self.engine.deck_proposals(root, None)['review']
        item = shown['items'][0]
        self.assertIn('Redraws section 2', item['price'])
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        count = len(self.workers.of('section'))
        self.engine.deck_finding(root, None, seen, shown['job'], 'apply', [item['id']])
        self.to_end(root)
        self.assertEqual(len(self.workers.of('section')), count + 1)
        note = self.engine._load(root)['deck']['']['notes'][-1]
        self.assertEqual(note['note'], item['after'])
        self.assertEqual(note['status'], 'done')

    def test_skipping_a_grave_finding_still_blocks_ready(self):
        self.workers.found = [[{**MAJOR, 'slide': 'check-yourself'}]]
        root = self.begin(flow='desk')
        self.to_end(root)
        shown = self.engine.deck_proposals(root, None)['review']
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        self.engine.deck_finding(root, None, seen, shown['job'], 'skip', [shown['items'][0]['id']])
        self.assertEqual(self.engine.deck_proposals(root, None)['review']['items'][0]['state'], 'skipped')
        with self.assertRaisesRegex(Exception, 'Settle what needs you'):
            self.engine.mark_ready(root, 'deck', seen)

    def test_a_note_makes_a_ready_deck_a_draft_and_refuses_an_old_form(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        self.engine.mark_ready(root, 'deck', seen)
        self.assertEqual(workspace.person_statuses(root, workspace.load(root))['deck'], 'approved')
        with self.assertRaisesRegex(Exception, 'has changed since it was opened'):
            self.engine.slide_note(root, None, 'check-yourself', 'Enlarge it.', 'old')
        self.assertFalse(self.engine._load(root)['deck'][''].get('notes'))
        self.engine.slide_note(root, None, 'check-yourself', 'Enlarge it.', seen)
        self.assertEqual(workspace.person_statuses(root, workspace.load(root))['deck'], 'draft')

    def test_a_file_changed_outside_the_page_refuses_the_note(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        file = root / workspace.artifact(root, workspace.load(root), 'deck')['file']
        file.write_bytes(file.read_bytes() + b'changed')
        with self.assertRaisesRegex(Exception, 'has changed since it was opened'):
            self.engine.slide_note(root, None, 'check-yourself', 'Enlarge it.', seen)
        self.assertFalse(self.engine._load(root)['deck'][''].get('notes'))

    def test_a_review_keeps_findings_on_untouched_slides(self):
        self.workers.found = [[MAJOR], []]
        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        self.engine.slide_note(root, None, 'check-yourself', 'Enlarge it.', seen)
        self.to_end(root)
        review = self.built(root)['rounds'][-1]['review']
        self.assertIsNotNone(review, self.view(root))
        self.assertEqual([item['slide'] for item in review['findings']], ['what-it-does'])
        self.assertEqual(self.engine.deck_proposals(root, None)['review']['items'][0]['part'],
                         'what-it-does')

    def test_the_price_uses_the_recorded_section(self):
        record = {'deck': {'101': {'section_numbers': {'section-2': [4, 5]}}},
                  'steps': {'deck-sections@101:2': {'attempts': [
                      {'seconds': 200, 'dollars': .5}]}}}
        self.assertIn('about $0.50', drafts.section_price(record, '101', 'section-2'))
        record['steps'] = {}
        self.assertTrue(drafts.section_price(record, '101', 'section-2').endswith(
            'This computer has no record yet of what it costs. Expect minutes, not seconds.'))

    def test_the_price_says_what_it_redraws(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        record = self.engine._load(root)
        self.assertTrue(drafts.section_price(record, None, 'section-2').startswith(
            'Redraws section 2 (slides 4 and 5); the other slides stay exactly as they are.'))


class JudgedSlideNoteTests(DeckCase):
    WALKTHROUGH = True

    def setUp(self):
        super().setUp()
        self.slides.design, self.slides.judges = True, True
        self.slides.have['local'] = True

    def test_a_note_on_a_deck_reviewed_against_its_design(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        count = len(self.workers.of('review'))
        self.engine.slide_note(root, None, 'check-yourself', 'Make the diagram larger.', seen)
        self.to_end(root)
        self.assertEqual(len(self.workers.of('review')), count + 1)
        self.assertIsNotNone(self.built(root)['rounds'][-1]['review'], self.view(root))


class SlideNotePageTests(PageCase):
    def test_slide_note_and_finding_routes(self):
        self.workers.found = [[{**MAJOR, 'slide': 'check-yourself'}], []]
        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        item = self.engine.deck_proposals(root, None)['review']
        self.post('drafts/finding', {'path': str(root), 'level': '', 'seen': seen,
                                    'job': item['job'], 'action': 'apply',
                                    'ids': [item['items'][0]['id']]})
        self.to_end(root)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        self.post('drafts/slide-note', {'path': str(root), 'level': '', 'seen': seen,
                                       'slide': 'check-yourself', 'note': 'Enlarge it.'})
        self.assertEqual(self.engine._load(root)['deck']['']['notes'][-1]['status'], 'done')


class SlideWordsTests(DeckCase):
    def test_row_167_words_that_fit_are_patched_with_no_worker(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        before = self.built(root)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        self.engine.mark_ready(root, 'deck', seen)
        jobs = len(self.workers.jobs)
        self.engine.slide_words(root, None, 'check-yourself', 'title', 'A new title', seen)
        self.assertEqual(workspace.person_statuses(root, workspace.load(root))['deck'], 'draft')
        self.assertEqual(len(self.workers.jobs), jobs)
        outline = json.loads((root / pipeline.OUTLINE).read_text())
        slide = next(s for s in outline['slides'] if s['id'] == 'check-yourself')
        self.assertEqual(slide['title'], 'A new title')
        after = self.built(root)
        section = json.loads((root / pipeline.WORK / after['sections']['section-2']['file']).read_text())
        self.assertEqual(next(s for s in section['slides'] if s['id'] == 'check-yourself')['title'], 'A new title')
        self.assertNotEqual(before['rounds'][-1]['folder'], after['rounds'][-1]['folder'])
        self.assertEqual(self.engine._load(root)['deck']['']['saved']['deck'], after['rounds'][-1]['deck'])

    def test_words_that_do_not_fit_save_nothing(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        outline = (root / pipeline.OUTLINE).read_bytes()
        built = self.built(root)
        section = (root / pipeline.WORK / built['sections']['section-2']['file']).read_bytes()
        result = self.engine.slide_words(root, None, 'check-yourself', 'title', 'TOO LONG TO FIT', seen)
        self.assertFalse(result['fits'])
        self.assertEqual(result['said'], 'These words do not fit the slide as it is drawn.')
        self.assertEqual((root / pipeline.OUTLINE).read_bytes(), outline)
        self.assertEqual(self.built(root), built)
        self.assertEqual((root / pipeline.WORK / built['sections']['section-2']['file']).read_bytes(), section)

    def test_row_168_speaker_notes_need_no_worker(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        count = len(self.workers.jobs)
        self.engine.slide_speaker_notes(root, None, 'check-yourself', 'New speaker notes.', seen)
        self.assertEqual(len(self.workers.jobs), count)
        built = self.built(root)
        section = json.loads((root / pipeline.WORK / built['sections']['section-2']['file']).read_text())
        whole = json.loads((root / pipeline.WORK / built['start']['folder'] / 'given' / 'outline.json').read_text())
        spec = deck.fixed(whole, built['start']['sections'][1]['slides'], 2, None)
        self.assertEqual(deck.kept(section, spec), [])
        self.assertEqual(next(s for s in section['slides'] if s['id'] == 'check-yourself')['notes'], 'New speaker notes.')

    def test_words_found_twice_are_refused(self):
        section = {'slides': [{'id': 'a', 'canvas': [{'text': 'same same'}]}]}
        with self.assertRaisesRegex(Exception, 'The words are not found once on the slide.'):
            deck.patch_section(section, 'a', 'points[0].text', 'same', 'new')

    def test_lead_subtitle_and_point_words(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        self.assertTrue(self.engine.slide_words(root, None, 'cover-restarts', 'subtitle',
                                                'A new subtitle', seen)['fits'])
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        self.assertTrue(self.engine.slide_words(root, None, 'check-yourself', 'points[0].label',
                                                'Tell', seen)['fits'])
        outline = json.loads((root / pipeline.OUTLINE).read_text())
        self.assertEqual(outline['slides'][0]['subtitle'], 'A new subtitle')
        self.assertEqual(outline['slides'][4]['points'][0]['label'], 'Tell')

    def test_old_form_does_not_change_the_deck(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        before = (root / pipeline.OUTLINE).read_bytes()
        with self.assertRaisesRegex(Exception, 'has changed since it was opened'):
            self.engine.slide_words(root, None, 'check-yourself', 'title', 'New title', 'old')
        self.assertEqual((root / pipeline.OUTLINE).read_bytes(), before)


class SlideWordsPageTests(PageCase):
    def test_words_and_notes_routes(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        self.post('drafts/slide-words', {'path': str(root), 'level': '', 'seen': seen,
            'slide': 'check-yourself', 'field': 'title', 'text': 'A new title'})
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        self.post('drafts/slide-speaker-notes', {'path': str(root), 'level': '', 'seen': seen,
            'slide': 'check-yourself', 'text': 'New notes.'})
        outline = json.loads((root / pipeline.OUTLINE).read_text())
        self.assertEqual(outline['slides'][4]['notes'], 'New notes.')


class JudgedSlideWordsTests(JudgedSlideNoteTests):
    def test_speaker_notes_on_a_design_reviewed_deck(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        result = self.engine.slide_speaker_notes(root, None, 'check-yourself', 'New notes.', seen)
        self.assertTrue(result['fits'])
        self.assertEqual(self.engine._load(root)['deck']['']['saved']['deck'],
                         self.built(root)['rounds'][-1]['deck'])

    def test_render_failure_restores_the_previous_deck(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        outline = (root / pipeline.OUTLINE).read_bytes()
        built = self.built(root)
        session = workspace.load(root)
        with mock.patch.object(self.engine, '_whole', side_effect=workspace.WorkspaceError('Render failed.')):
            with self.assertRaisesRegex(Exception, 'Render failed'):
                self.engine.slide_speaker_notes(root, None, 'check-yourself', 'New notes.', seen)
        self.assertEqual((root / pipeline.OUTLINE).read_bytes(), outline)
        self.assertEqual(self.built(root), built)
        self.assertEqual(workspace.load(root), session)

    @staticmethod
    def saved_files(root):
        return {path.relative_to(root): path.read_bytes() for path in root.rglob('*') if path.is_file()}

    def test_keep_failure_after_saving_leaves_all_live_files_and_commits_unchanged(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        before, commits = self.saved_files(root), self.log()
        keep = self.engine._keep

        def fail(*args):
            keep(*args)
            raise workspace.WorkspaceError('Save failed.')

        with mock.patch.object(self.engine, '_keep', side_effect=fail):
            with self.assertRaisesRegex(Exception, 'Save failed'):
                self.engine.slide_speaker_notes(root, None, 'check-yourself', 'New notes.', seen)
        self.assertEqual(self.saved_files(root), before)
        self.assertEqual(self.log(), commits)

    def test_reported_render_failure_leaves_all_live_files_and_commits_unchanged(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        before, commits = self.saved_files(root), self.log()
        with mock.patch.object(self.slides, 'merge', side_effect=workspace.WorkspaceError('Merge failed.')):
            with self.assertRaisesRegex(Exception, 'Merge failed'):
                self.engine.slide_speaker_notes(root, None, 'check-yourself', 'New notes.', seen)
        self.assertEqual(self.saved_files(root), before)
        self.assertEqual(self.log(), commits)

    def test_change_during_render_is_preserved_and_refuses_publication(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        before, commits = self.saved_files(root), self.log()
        whole = self.engine._whole
        changed = root / 'document.md'

        def concurrently(*args):
            whole(*args)
            changed.write_text('A concurrent edit.\n', encoding='utf-8')

        with mock.patch.object(self.engine, '_whole', side_effect=concurrently):
            with self.assertRaisesRegex(Exception, 'changed while the slide was being prepared'):
                self.engine.slide_speaker_notes(root, None, 'check-yourself', 'New notes.', seen)
        before[changed.relative_to(root)] = changed.read_bytes()
        self.assertEqual(self.saved_files(root), before)
        self.assertEqual(self.log(), commits)

    def test_new_unrelated_file_is_neither_overwritten_nor_committed(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        whole = self.engine._whole
        added = root / 'my-note.txt'

        def concurrently(*args):
            whole(*args)
            added.write_text('A concurrent note.\n', encoding='utf-8')

        with mock.patch.object(self.engine, '_whole', side_effect=concurrently):
            self.assertTrue(self.engine.slide_speaker_notes(root, None, 'check-yourself', 'New notes.', seen)['fits'])
        self.assertEqual(added.read_text(), 'A concurrent note.\n')
        self.assertIn('my-note.txt', self.git('status', '--porcelain'))
        built = self.built(root)
        self.slides.review_slide(root / pipeline.WORK / built['rounds'][-1]['preview'], 'check-yourself')

    def test_design_bound_title_proposes_a_question_and_changes_nothing(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        before, commits = self.saved_files(root), self.log()
        result = self.engine.slide_words(root, None, 'check-yourself', 'title', 'A new title', seen)
        self.assertEqual(result['approval']['question']['phase'], 'design')
        self.assertEqual(self.saved_files(root), before)
        self.assertEqual(self.log(), commits)

    def test_outline_change_during_fit_check_is_not_overwritten(self):
        from runner import worker_tools
        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        file = root / pipeline.OUTLINE
        newer = json.loads(file.read_text())
        newer['slides'][0]['title'] = 'A concurrent title'
        check = worker_tools.check_section

        def concurrently(*args):
            result = check(*args)
            file.write_text(json.dumps(newer), encoding='utf-8')
            return result

        with mock.patch.object(worker_tools, 'check_section', side_effect=concurrently):
            with self.assertRaisesRegex(Exception, 'changed while the slide'):
                self.engine.slide_speaker_notes(root, None, 'check-yourself', 'New notes.', seen)
        self.assertEqual(json.loads(file.read_text()), newer)


class SlideWordsPreviewTests(DeckCase):
    def test_two_successful_edits_reuse_the_discoverable_drive_preview(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        left, files = self.engine.previews_left(), list(self.slides.files)
        self.assertTrue(left)
        for notes in ('First notes.', 'Second notes.'):
            seen = self.engine._load(root)['deck']['']['saved']['sha256']
            self.engine.slide_speaker_notes(root, None, 'check-yourself', notes, seen)
            self.assertEqual(self.slides.files, files)
            self.assertEqual(self.engine.previews_left(), left)

    def test_failed_render_keeps_its_remote_receipt_and_retry_reuses_it(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        # Simulate a fresh upload whose rendering failed, as Harness Slides reports it.
        self.slides.files.append('file-9')
        refused = workspace.WorkspaceError('Render failed after upload.')
        refused.left = {'fileId': 'file-9',
                        'url': 'https://docs.example.com/presentation/d/file-9/edit'}
        with mock.patch.object(self.slides, 'preview', side_effect=refused):
            with self.assertRaisesRegex(workspace.WorkspaceError, 'Render failed after upload'):
                self.engine.slide_speaker_notes(root, None, 'check-yourself', 'New notes.', seen)
        self.assertIn(refused.left['url'], [entry['url'] for entry in self.engine.previews_left()])
        before = list(self.slides.files)
        self.engine.slide_speaker_notes(root, None, 'check-yourself', 'New notes.', seen)
        self.assertEqual(self.slides.files, before)
        self.assertIn(refused.left['url'], [entry['url'] for entry in self.engine.previews_left()])


class ApprovedWordsTests(JudgedSlideNoteTests):
    @staticmethod
    def files(root):
        return {path.relative_to(root): path.read_bytes() for path in root.rglob('*') if path.is_file()}

    def propose(self, root, title='A new title'):
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        result = self.engine.slide_words(root, None, 'check-yourself', 'title', title, seen)
        return seen, result['approval']

    def approve(self, root, seen, proposed, **changes):
        values = {'question': proposed['question']['id'], 'revision': proposed['revision'],
                  'response': 'Approve updated words', **changes}
        return self.engine.slide_words_decide(root, proposed['token'], 'approve', seen, **values)

    def test_a_guide_update_keeps_the_approved_word_project(self):
        from test_drafts import edit
        root = self.begin(flow='desk')
        self.to_end(root)
        seen, proposed = self.propose(root)
        self.approve(root, seen, proposed)
        project = pipeline.design_project(root, None)
        edit(self, root, 'document', lambda text: text.replace(
            '## When capacity holds', '## When capacity holds\nOne line more.'))
        self.engine.update(root, 'deck')
        self.to_end(root)
        self.assertIsNone(self.engine._load(root)['problem'])
        self.assertEqual(pipeline.design_project(root, None), project)
        self.assertEqual(self.engine._load(root)['deck']['']['approved']['design']['project'],
                         project.relative_to(root).as_posix())

    def test_a_teammate_without_local_drawings_uses_the_shared_design_project(self):
        import shutil
        root = self.begin(flow='desk')
        self.to_end(root)
        seen, proposed = self.propose(root)
        self.approve(root, seen, proposed)
        project = pipeline.design_project(root, None)
        shutil.rmtree(root / 'work')
        before = self.files(root)
        self.assertEqual(pipeline.design_project(root, None), project)
        self.assertEqual(self.slides.design_check(pipeline.design_project(root, None))[
            'plan']['slides'][4]['title'], 'A new title')
        self.assertEqual(self.files(root), before)

    def test_page_outline_approval_keeps_the_question_project(self):
        from dataclasses import replace
        root = self.begin(flow='desk')
        self.to_end(root)
        seen, proposed = self.propose(root)
        self.approve(root, seen, proposed)
        record = self.engine._load(root)
        kept = record['deck']['']
        expected = copy.deepcopy(kept['approved']['design'])
        kept['waiting'] = {'sha256': kept['approved']['sha256'], 'design': expected}
        self.engine._store(root, record)
        found = self.engine._survey(root, record)
        step = next(step for step in found.steps if step.id == 'gate:deck-outline')
        found = replace(found, next=pipeline.Next('outline', step))
        with mock.patch.object(self.engine, '_survey', return_value=found), \
                mock.patch.object(self.engine, '_answer'), \
                mock.patch.object(self.engine, 'carry_on'), mock.patch.object(self.engine, 'view'):
            self.engine.outline(root, None, 'approve')
        self.assertEqual(self.engine._load(root)['deck']['']['approved']['design'], expected)

    def test_a_cover_subtitle_requires_approval_of_its_focal_copy(self):
        from stand_ins import slides as slides_stand_in
        self.slides.keeps = True
        self.slides.listed = set(slides_stand_in.CURRENT)
        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        before, answers = self.files(root), len(self.slides.replies)
        result = self.engine.slide_words(root, None, 'cover-restarts', 'subtitle',
                                         'A clearer explanation', seen)
        self.assertIn('approval', result)
        self.assertEqual(self.files(root), before)
        self.assertEqual(len(self.slides.replies), answers)
        self.assertTrue(self.approve(root, seen, result['approval'])['fits'])
        plan = self.slides.design_check(pipeline.design_project(root, None))['plan']
        self.assertEqual(plan['slides'][0]['copy']['focal'], 'A clearer explanation')
        outline = json.loads((root / pipeline.OUTLINE).read_text())
        self.assertEqual(outline['slides'][0]['subtitle'], 'A clearer explanation')

    def change_cover_subtitle(self, initial, text):
        from stand_ins import slides as slides_stand_in
        self.slides.keeps = True
        self.slides.listed = set(slides_stand_in.CURRENT)
        self.workers.outline_said = copy.deepcopy(self.workers.outline_said)
        cover = self.workers.outline_said['slides'][0]
        if initial:
            cover['subtitle'] = initial
        else:
            cover.pop('subtitle', None)
        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        before, answers, jobs = self.files(root), len(self.slides.replies), len(self.workers.jobs)
        result = self.engine.slide_words(root, None, 'cover-restarts', 'subtitle', text, seen)
        self.assertIn('approval', result)
        self.assertEqual(self.files(root), before)
        self.assertEqual(len(self.slides.replies), answers)
        self.assertTrue(self.approve(root, seen, result['approval'])['fits'])
        self.assertEqual(len(self.workers.jobs), jobs)
        plan = self.slides.design_check(pipeline.design_project(root, None))['plan']
        outline = json.loads((root / pipeline.OUTLINE).read_text())
        self.assertEqual(outline['slides'][0].get('subtitle', ''), text)
        self.assertEqual(plan['slides'][0]['copy'], deck._copy(outline['slides'][0]))

    def test_adding_the_first_cover_subtitle_replaces_the_approved_title_fallback(self):
        self.change_cover_subtitle(None, 'A first subtitle')

    def test_clearing_the_cover_subtitle_restores_the_approved_title_fallback(self):
        self.change_cover_subtitle('A first subtitle', '')

    def change_title_copy(self, *, subtitle=None, content=False, focal=None):
        from stand_ins import slides as slides_stand_in
        self.slides.keeps = True
        self.slides.listed = set(slides_stand_in.CURRENT)
        self.workers.outline_said = copy.deepcopy(self.workers.outline_said)
        index = 4 if content else 0
        slide = self.workers.outline_said['slides'][index]
        slide.pop('subtitle', None)
        if subtitle:
            slide['subtitle'] = subtitle
        if content:
            slide['points'] = []
            slide.pop('focal', None)
            if focal:
                slide['focal'] = focal
        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        jobs = len(self.workers.jobs)
        result = self.engine.slide_words(root, None, slide['id'], 'title', 'A changed title', seen)
        self.assertTrue(self.approve(root, seen, result['approval'])['fits'])
        outline = json.loads((root / pipeline.OUTLINE).read_text())
        plan = self.slides.design_check(pipeline.design_project(root, None))['plan']
        self.assertEqual(plan['slides'][index]['copy'], deck._copy(outline['slides'][index]))
        self.assertEqual(len(self.workers.jobs), jobs)
        if not content and not subtitle:
            seen = self.engine._load(root)['deck']['']['saved']['sha256']
            result = self.engine.slide_words(root, None, slide['id'], 'subtitle', 'A first subtitle', seen)
            self.assertTrue(self.approve(root, seen, result['approval'])['fits'])
            plan = self.slides.design_check(pipeline.design_project(root, None))['plan']
            self.assertEqual(plan['slides'][index]['copy']['focal'], 'A first subtitle')

    def test_row_169_title_fallback_then_first_subtitle_uses_current_approved_copy(self):
        self.change_title_copy()

    def test_title_edit_preserves_an_independent_subtitle(self):
        self.change_title_copy(subtitle='An independent subtitle')

    def test_title_edit_preserves_an_independent_content_focal(self):
        self.change_title_copy(content=True, focal='An independent focal statement')

    def test_title_edit_updates_a_content_title_fallback(self):
        self.change_title_copy(content=True)

    def test_row_169_bound_title_requires_an_explicit_current_design_answer(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        before, jobs = self.files(root), len(self.workers.jobs)
        original = pipeline.design_project(root, None)
        seen, proposed = self.propose(root)
        self.assertEqual(self.files(root), before)
        self.assertEqual(proposed['before'], 'Check what you can now explain')
        self.assertEqual(proposed['after'], 'A new title')
        with self.assertRaisesRegex(workspace.WorkspaceError, 'question'):
            self.approve(root, seen, proposed, question='wrong')
        self.assertEqual(self.files(root), before)
        self.assertTrue(self.approve(root, seen, proposed)['fits'])
        self.assertEqual(len(self.workers.jobs), jobs)
        self.assertEqual(json.loads((root / pipeline.OUTLINE).read_text())['slides'][4]['title'], 'A new title')
        project = pipeline.design_project(root, None)
        self.assertNotEqual(project, original)
        self.assertEqual(self.slides.design_check(project)['plan']['slides'][4]['title'], 'A new title')
        self.assertNotEqual(self.slides.design_check(original)['plan']['slides'][4]['title'], 'A new title')
        built = self.built(root)
        self.slides.review_slide(root / pipeline.WORK / built['rounds'][-1]['preview'], 'check-yourself')
        seen, proposed = self.propose(root, 'Another title')
        self.assertTrue(self.approve(root, seen, proposed)['fits'])
        self.assertEqual(self.slides.design_check(pipeline.design_project(root, None))['plan']['slides'][4]['title'], 'Another title')

    def test_cancelled_and_unfit_approved_words_keep_the_previous_deck(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        before = self.files(root)
        seen, proposed = self.propose(root)
        self.engine.slide_words_decide(root, proposed['token'], 'cancel', seen)
        self.assertEqual(self.files(root), before)
        seen, proposed = self.propose(root, 'TOO LONG TO FIT')
        self.assertFalse(self.approve(root, seen, proposed)['fits'])
        self.assertEqual(self.files(root), before)

    def test_changed_inputs_and_render_failure_do_not_publish_the_proposed_design(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        before = self.files(root)
        seen, proposed = self.propose(root)
        with mock.patch.object(self.engine, '_whole', side_effect=workspace.WorkspaceError('Render failed.')):
            with self.assertRaisesRegex(workspace.WorkspaceError, 'Render failed'):
                self.approve(root, seen, proposed)
        self.assertEqual(self.files(root), before)
        seen, proposed = self.propose(root)
        outline = root / pipeline.OUTLINE
        outline.write_bytes(outline.read_bytes() + b'\n')
        changed = outline.read_bytes()
        with self.assertRaisesRegex(workspace.WorkspaceError, 'changed'):
            self.approve(root, seen, proposed)
        self.assertEqual(outline.read_bytes(), changed)

    def test_a_change_during_the_explicit_answer_is_preserved(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        seen, proposed = self.propose(root)
        answer = self.slides.design_respond
        document = root / 'my-note.txt'

        def concurrently(*args):
            result = answer(*args)
            document.write_text('A concurrent edit.\n', encoding='utf-8')
            return result

        with mock.patch.object(self.slides, 'design_respond', side_effect=concurrently):
            with self.assertRaisesRegex(workspace.WorkspaceError, 'changed'):
                self.approve(root, seen, proposed)
        self.assertEqual(document.read_text(), 'A concurrent edit.\n')
        self.assertEqual(self.engine._load(root)['deck']['']['saved']['sha256'], seen)

    def test_presented_review_paths_survive_the_private_copy(self):
        from pathlib import Path
        root = self.begin(flow='desk')
        self.to_end(root)
        seen, proposed = self.propose(root)
        has = self.engine._has
        with mock.patch.object(self.engine, '_has', side_effect=lambda name:
                               name == 'design-present-findings' or has(name)):
            self.assertTrue(self.approve(root, seen, proposed)['fits'])
        output = Path(self.slides.presented[-1][1])
        self.assertTrue(output.is_relative_to(root))
        self.assertTrue((output / 'review.json').is_file())

    def test_approved_words_keep_their_level_and_allow_a_later_slide_note(self):
        root = self.begin(flow='desk', levels=['101'])
        self.to_end(root)
        seen = self.engine._load(root)['deck']['101']['saved']['sha256']
        proposed = self.engine.slide_words(root, '101', 'check-yourself', 'title',
                                           'A new title', seen)['approval']
        self.assertTrue(self.approve(root, seen, proposed)['fits'])
        project = pipeline.design_project(root, '101')
        self.assertTrue(project.is_relative_to(root / '101' / 'deck' / 'design-edits'))
        self.assertFalse((root / 'deck').exists())
        seen = self.engine._load(root)['deck']['101']['saved']['sha256']
        self.engine.slide_note(root, '101', 'check-yourself', 'Make the diagram larger.', seen)
        self.to_end(root)
        self.assertEqual(pipeline.design_project(root, '101'), project)

    def test_approved_words_with_the_current_tool_capabilities(self):
        from stand_ins import slides as slides_stand_in
        self.slides.keeps = True
        self.slides.listed = set(slides_stand_in.CURRENT)
        root = self.begin(flow='desk')
        self.to_end(root)
        seen, proposed = self.propose(root)
        self.assertTrue(self.approve(root, seen, proposed)['fits'])
        self.assertEqual(self.slides.design_check(pipeline.design_project(root, None))[
            'plan']['slides'][4]['title'], 'A new title')


class ApprovedWordsPageTests(PageCase):
    WALKTHROUGH = True

    def setUp(self):
        super().setUp()
        self.slides.design, self.slides.judges = True, True
        self.slides.have['local'] = True

    def test_words_question_is_answered_only_by_the_explicit_decision_route(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        reply = self.post('drafts/slide-words', {'path': str(root), 'seen': seen,
            'slide': 'check-yourself', 'field': 'title', 'text': 'A new title'})
        approval = reply['approval']
        sent = {'path': str(root), 'seen': seen, 'proposal': approval['token'], 'decision': 'approve',
                'question': approval['question']['id'], 'revision': approval['revision'],
                'response': 'Approve updated words'}
        self.post('drafts/slide-words-decide', {**sent, 'question': 'old'}, expect=409)
        self.assertTrue(self.post('drafts/slide-words-decide', sent)['fits'])
        self.assertEqual(json.loads((root / pipeline.OUTLINE).read_text())['slides'][4]['title'], 'A new title')


class ApprovedWordsAssetTests(DeckCase):
    WALKTHROUGH = True

    def test_pictures_and_icons_follow_the_approved_project_after_a_word_edit(self):
        from test_runner_deck import with_assets
        from runner_support import OUTLINE, designed, png
        self.slides.design = self.slides.keeps = self.slides.judges = True
        self.slides.have['local'] = True
        self.workers.design_said = with_assets(designed(OUTLINE))
        root = self.begin(flow='desk')
        self.engine.supply_asset(root, None, 'console_view', png(40), 'The console', 'Course author', '')
        self.to_end(root)
        original = pipeline.design_project(root, None)
        old_assets = pipeline.recorded(root, None)
        picture = original / old_assets['console_view']['path']
        old_picture = picture.read_bytes()
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        pending = self.engine.slide_words(root, None, 'check-yourself', 'title', 'A new title', seen)['approval']
        self.assertTrue(self.engine.slide_words_decide(root, pending['token'], 'approve', seen,
            question=pending['question']['id'], revision=pending['revision'], response='Approve updated words')['fits'])
        project = pipeline.design_project(root, None)
        self.assertNotEqual(project, original)
        self.assertEqual(pipeline.recorded(root, None), old_assets)
        self.assertEqual((project / old_assets['console_view']['path']).read_bytes(), old_picture)
        self.engine.supply_asset(root, None, 'console_view', png(70), 'A new console', 'Course author', '')
        self.assertEqual(picture.read_bytes(), old_picture)
        self.assertNotEqual((project / old_assets['console_view']['path']).read_bytes(), old_picture)


class GuideUpdateTests(DeckCase):
    def change(self, root, name, change):
        from test_drafts import edit
        edit(self, root, name, change)

    def test_row_170_update_from_the_guide_rewords_only_the_slides_that_serve_it(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        before = json.loads((root / pipeline.OUTLINE).read_text())
        self.change(root, 'document', lambda text: text.replace(
            '## When capacity holds', '## When capacity holds\nChanged detail.'))
        scope = drafts.slides_for(root, workspace.load(root), None, 'document')
        self.assertEqual(scope['slides'], ['when-capacity-holds', 'check-yourself'])
        self.assertIn('When capacity holds', scope['sections'])
        self.workers.outline_said = copy.deepcopy(before)
        self.workers.outline_said['slides'][2]['notes'] += ' Changed.'
        self.workers.outline_said['slides'][4]['notes'] += ' Changed.'
        count = len(self.workers.of('section'))
        self.engine.update(root, 'deck')
        self.to_end(root)
        job = next(spec for kind, _, spec in reversed(self.workers.jobs) if kind == 'outline')
        self.assertIn('slides to word again', [entry['name'] for entry in job['inputs']])
        after = json.loads((root / pipeline.OUTLINE).read_text())
        for index in (0, 1, 3, 5):
            self.assertEqual(before['slides'][index], after['slides'][index])
        self.assertEqual(len(self.workers.of('section')), count + 2)

    def test_key_point_without_an_objective_uses_its_module(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        self.change(root, 'document', lambda text: text.replace('covers: O2 K1.2', 'covers: K1.2'))
        scope = drafts.slides_for(root, workspace.load(root), None, 'document')
        self.assertEqual(scope['slides'], ['what-it-does', 'when-capacity-holds',
                                           'the-objection', 'check-yourself'])

    def test_duplicate_guide_headings_do_not_hide_a_change(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        first = {'id': 'one', 'heading': 'Repeated', 'text': 'Before', 'covers': ['O2']}
        second = {'id': 'two', 'heading': 'Repeated', 'text': 'Same', 'covers': ['O3']}
        old = {'opening': '', 'sections': [first, second]}
        new = {'opening': '', 'sections': [{**first, 'text': 'After'}, second]}
        codec = mock.Mock()
        codec.split.side_effect = [old, new]
        with mock.patch.object(drafts, 'GuideCodec', return_value=codec):
            scope = drafts.slides_for(root, workspace.load(root), None, 'document')
        self.assertTrue(scope['whole'])
        self.assertEqual(len(scope['slides']), 6)

    def test_a_glossary_edit_names_no_slide(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        self.change(root, 'document', lambda text: text.replace('## Glossary', '## Glossary\nChanged.'))
        self.assertEqual(drafts.slides_for(root, workspace.load(root), None, 'document')['slides'], [])
        self.assertEqual(drafts.update_preview(root, 'deck')['message'], drafts.NO_SLIDE)
        with self.assertRaisesRegex(workspace.WorkspaceError, 'No slide is built'):
            self.engine.update(root, 'deck')
        self.assertFalse(drafts.busy(self.engine._load(root)))

    def test_a_new_objective_rewords_the_whole_outline(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        self.change(root, 'blueprint', lambda text: text.replace(
            '## M1', '### O4: New objective [explain]\n\n## M1'))
        scope = drafts.slides_for(root, workspace.load(root), None, 'blueprint')
        self.assertTrue(scope['whole'])
        self.assertEqual(len(scope['slides']), 6)
        preview = drafts.update_preview(root, 'deck')
        self.assertTrue(preview['whole'])
        self.assertEqual(preview['parts'], ['The whole outline'])
        self.assertIn('affected sections and review', preview['price'])

    def test_a_frozen_slide_in_the_outline_is_handed_back(self):
        from runner import worker_tools
        from runner_support import OUTLINE
        root = self.begin(flow='desk')
        self.to_end(root)
        outline = copy.deepcopy(OUTLINE)
        frozen = copy.deepcopy(outline['slides'][2])
        outline['slides'][2]['notes'] = 'Changed.'
        spec = {'brand': str(root / 'brand.json'),
                'frozen': {frozen['id']: frozen}}
        problems, _, _, _ = worker_tools.check_outline(json.dumps(outline), spec, self.slides, self.base)
        self.assertIn('Slide 3 is not one to word again. Copy it exactly.', problems)


class ScopedUpdateReviewTests(DeckCase):
    def test_frozen_fields_stripped_for_the_tool_still_cannot_change(self):
        from runner import worker_tools
        from runner_support import OUTLINE
        root = self.begin(flow='desk')
        self.to_end(root)
        before = copy.deepcopy(OUTLINE)
        before['slides'][2]['points'][0]['parts'] = ['Several', 'Instances']
        before['slides'][2]['provenance'] = 'Original source'
        for field in ('parts', 'provenance'):
            with self.subTest(field=field):
                changed = copy.deepcopy(before)
                if field == 'parts':
                    changed['slides'][2]['points'][0]['parts'] = ['Different']
                else:
                    changed['slides'][2]['provenance'] = 'Changed source'
                spec = {'brand': str(root / 'brand.json'), 'previous': before,
                        'frozen': {before['slides'][2]['id']: before['slides'][2]}}
                problems, _, _, _ = worker_tools.check_outline(
                    json.dumps(changed), spec, self.slides, self.base)
                self.assertIn('Slide 3 is not one to word again. Copy it exactly.', problems)

    def test_changed_guide_before_worker_refreshes_scope(self):
        from test_drafts import edit
        root = self.begin(flow='desk')
        self.to_end(root)
        edit(self, root, 'document', lambda text: text.replace(
            '## Why this matters', '## Why this matters\nChanged first.'))
        with mock.patch.object(self.engine, 'carry_on'):
            self.engine.update(root, 'deck')
        card = self.engine.draft_card(root, 'document')
        section = next(part for part in card['sections'] if part['heading'] == 'When capacity holds')
        self.engine.draft_save(root, 'document', section['id'], card['revision'],
                               section['text'] + '\nChanged later.')
        self.engine.carry_on(root)
        self.to_end(root)
        spec = next(spec for kind, _, spec in reversed(self.workers.jobs) if kind == 'outline')
        self.assertEqual(set(spec['artifacts']['outline']['frozen']),
                         {'cover-restarts', 'what-it-does', 'closing-practice'})

    def test_edit_after_a_failed_try_refreshes_the_retry_scope(self):
        from runner.agents import Outcome
        from test_drafts import edit
        root = self.begin(flow='desk')
        self.to_end(root)
        edit(self, root, 'document', lambda text: text.replace(
            '## Why this matters', '## Why this matters\nChanged first.'))
        self.workers.then('outline', lambda tools, job: Outcome(False, 'failed', 'Try again.'))
        failed = self.engine._failed

        def save_after_failure(*args):
            failed(*args)
            card = self.engine.draft_card(root, 'document')
            section = next(part for part in card['sections'] if part['heading'] == 'When capacity holds')
            self.engine.draft_save(root, 'document', section['id'], card['revision'],
                                   section['text'] + '\nChanged before retry.')

        with mock.patch.object(self.engine, '_failed', side_effect=save_after_failure):
            self.engine.update(root, 'deck')
        self.to_end(root)
        spec = next(spec for kind, _, spec in reversed(self.workers.jobs) if kind == 'outline')
        self.assertEqual(set(spec['artifacts']['outline']['frozen']),
                         {'cover-restarts', 'what-it-does', 'closing-practice'})
        self.assertIsNone(self.engine._load(root)['problem'])

    def test_changed_guide_during_worker_discards_and_retries(self):
        from test_drafts import edit
        root = self.begin(flow='desk')
        self.to_end(root)
        edit(self, root, 'document', lambda text: text.replace(
            '## Why this matters', '## Why this matters\nChanged first.'))
        before = len(self.workers.of('outline'))

        def edit_during(tools, job):
            # Another computer or external editor can change an input while the local
            # desk prevents typing into an input used by the active worker.
            edit(self, root, 'document', lambda text: text.replace(
                '## When capacity holds', '## When capacity holds\nChanged during the job.'))
            self.workers.outline(tools, job)

        self.workers.then('outline', edit_during)
        self.engine.update(root, 'deck')
        self.to_end(root)
        self.assertEqual(len(self.workers.of('outline')), before + 2)
        spec = next(spec for kind, _, spec in reversed(self.workers.jobs) if kind == 'outline')
        self.assertEqual(set(spec['artifacts']['outline']['frozen']),
                         {'cover-restarts', 'what-it-does', 'closing-practice'},
                         (self.engine._load(root).get('problem'),
                          self.engine._load(root)['steps']['deck-outline'],
                          self.engine._load(root)['deck']['']))
        self.assertNotIn('deck', drafts.held(root, workspace.load(root), self.engine._load(root)))


class DesignedScopedUpdateReviewTests(JudgedSlideNoteTests):
    def test_only_changed_section_redrawn_after_design_revision(self):
        from test_drafts import edit
        from studio_core import stops
        root = self.begin(flow='desk')
        self.to_end(root)
        before = self.built(root)
        original = (root / pipeline.WORK / before['sections']['section-1']['file']).read_bytes()
        outline = json.loads((root / pipeline.OUTLINE).read_text())
        self.workers.outline_said = copy.deepcopy(outline)
        self.workers.outline_said['slides'][3]['notes'] += ' Changed.'
        edit(self, root, 'document', lambda text: text.replace(
            '## Why this matters', '## Why this matters\nChanged.'))
        record = self.engine._load(root)
        price = self.engine._redo_steps(record, ['deck-outline', 'deck-sections:2', 'deck-review'])
        preview = drafts.update_preview(root, 'deck')
        self.assertEqual(preview['price'], stops.redone('the outline', 3, *price,
                              after='the affected sections and review'))
        count = len(self.workers.of('section'))
        self.engine.update(root, 'deck')
        self.to_end(root)
        after = self.built(root)
        self.assertEqual(len(self.workers.of('section')), count + 1)
        self.assertEqual((root / pipeline.WORK / after['sections']['section-1']['file']).read_bytes(), original)

    def test_a_changed_approved_design_redraws_that_section(self):
        from test_drafts import edit
        from runner_support import designed
        root = self.begin(flow='desk')
        self.to_end(root)
        outline = json.loads((root / pipeline.OUTLINE).read_text())
        self.workers.outline_said = copy.deepcopy(outline)
        self.workers.outline_said['slides'][3]['notes'] += ' Changed.'
        self.workers.design_said = designed(self.workers.outline_said)
        self.workers.design_said['slides'][1]['composition'] += ' A different arrangement.'
        edit(self, root, 'document', lambda text: text.replace(
            '## Why this matters', '## Why this matters\nChanged.'))
        count = len(self.workers.of('section'))
        self.engine.update(root, 'deck')
        self.to_end(root)
        self.assertIsNone(self.engine._load(root)['problem'])
        self.assertEqual(len(self.workers.of('section')), count + 2)

    def test_current_slides_capabilities_keep_the_unchanged_section(self):
        from stand_ins import slides as slides_stand_in
        from test_drafts import edit
        self.slides.keeps = True
        self.slides.listed = set(slides_stand_in.CURRENT)
        root = self.begin(flow='desk')
        self.to_end(root)
        self.workers.outline_said = json.loads((root / pipeline.OUTLINE).read_text())
        self.workers.outline_said['slides'][3]['notes'] += ' Changed.'
        edit(self, root, 'document', lambda text: text.replace(
            '## Why this matters', '## Why this matters\nChanged.'))
        count = len(self.workers.of('section'))
        self.engine.update(root, 'deck')
        self.to_end(root)
        self.assertIsNone(self.engine._load(root)['problem'])
        self.assertEqual(len(self.workers.of('section')), count + 1)


class ScopedUpdateRetryTests(DeckCase):
    def _section_failure_then_guide_edit(self, legacy=False):
        from runner_support import fails
        from test_drafts import edit
        root = self.begin(flow='desk')
        self.to_end(root)
        original = json.loads((root / pipeline.OUTLINE).read_text())
        edit(self, root, 'document', lambda text: text.replace(
            '## Why this matters', '## Why this matters\nChanged first.'))
        self.workers.outline_said = copy.deepcopy(original)
        self.workers.outline_said['slides'][3]['notes'] += ' Updated.'
        self.workers.then('section', *[fails()] * 6)
        self.engine.update(root, 'deck')
        self.assertIsNotNone(self.engine._load(root)['problem'])
        self.assertIn('deck', drafts.updates(self.engine._load(root)))
        self.assertIsNone(self.engine._load(root)['deck']['']['asked'])
        if legacy:
            record = self.engine._load(root)
            record['drafts']['updates']['deck'].pop('deck_request')
            self.engine._store(root, record)
        card = self.engine.draft_card(root, 'document')
        section = next(part for part in card['sections'] if part['heading'] == 'When capacity holds')
        self.engine.draft_save(root, 'document', section['id'], card['revision'],
                               section['text'] + '\nChanged before retry.')
        self.workers.queued.pop('section', None)
        refused = []

        def try_wrong_outline(tools, job):
            spec = tools.job['artifacts']['outline']
            self.assertIn('what-it-does', spec.get('frozen', {}))
            changed = copy.deepcopy(self.workers.outline_said)
            changed['slides'][1]['notes'] += ' Unrelated change.'
            accepted, message = tools.submit_outline(json.dumps(changed))
            self.assertFalse(accepted)
            refused.append(message)
            self.workers.outline(tools, job)

        self.workers.then('outline', try_wrong_outline)
        self.engine.act(root, 'retry')
        self.to_end(root)
        self.assertIsNone(self.engine._load(root)['problem'])
        self.assertIn('Slide 2 is not one to word again. Copy it exactly.', refused[0])
        self.assertEqual(json.loads((root / pipeline.OUTLINE).read_text())['slides'][1],
                         original['slides'][1])
        self.assertNotIn('deck', drafts.updates(self.engine._load(root)))

    def test_section_failure_then_guide_edit_keeps_the_outline_scope_on_retry(self):
        self._section_failure_then_guide_edit()

    def test_a_preexisting_pending_update_recovers_scope_on_retry(self):
        self._section_failure_then_guide_edit(legacy=True)

    def test_retry_without_an_input_change_does_not_reword_the_outline(self):
        from runner_support import fails
        from test_drafts import edit
        root = self.begin(flow='desk')
        self.to_end(root)
        self.workers.outline_said = json.loads((root / pipeline.OUTLINE).read_text())
        self.workers.outline_said['slides'][3]['notes'] += ' Updated.'
        edit(self, root, 'document', lambda text: text.replace(
            '## Why this matters', '## Why this matters\nChanged.'))
        self.workers.then('section', *[fails()] * 6)
        self.engine.update(root, 'deck')
        self.assertIsNotNone(self.engine._load(root)['problem'])
        count = len(self.workers.of('outline'))
        self.workers.queued.pop('section', None)
        self.engine.act(root, 'retry')
        self.to_end(root)
        self.assertIsNone(self.engine._load(root)['problem'])
        self.assertEqual(len(self.workers.of('outline')), count)
        self.assertNotIn('deck', drafts.updates(self.engine._load(root)))


class SlideHistoryLookTests(DeckCase):
    def test_row_171_another_look_redraws_the_whole_deck(self):
        self.brand.offers_looks = True
        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        count = len(self.workers.of('section'))
        chosen = copy.deepcopy(self.engine._load(root)['deck']['']['look'])
        samples = self.engine.look_samples(root, None)
        self.assertTrue(samples['looks'])
        self.assertEqual(self.engine._load(root)['deck']['']['look'], chosen)
        self.engine.wake(root)
        self.assertEqual(len(self.workers.of('section')), count)
        self.engine.look_apply(root, None, samples['looks'][-1]['id'], seen)
        self.to_end(root)
        self.assertEqual(len(self.workers.of('section')), count + 2)
        self.assertEqual(workspace.person_statuses(root, workspace.load(root))['deck'], 'draft')

    def test_row_172_a_slide_keeps_its_words_and_drawing_as_versions(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        original = drafts.deck_drawings(root, None)['check-yourself']
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        jobs = len(self.workers.jobs)
        self.engine.slide_words(root, None, 'check-yourself', 'title', 'A new title', seen)
        versions = self.engine.slide_versions(root, None, 'check-yourself')['versions']
        self.assertEqual(len(versions), 1)
        self.assertTrue((root / 'deck/versions/check-yourself.jsonl').is_file())
        folder = root / 'work/deck/versions/check-yourself'
        self.assertEqual(len(list(folder.glob('*.json'))), 1)
        self.assertEqual(len(list(folder.glob('*.png'))), 1)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        self.engine.slide_restore(root, None, 'check-yourself', versions[0]['stamp'], seen)
        self.assertEqual(drafts.deck_drawings(root, None)['check-yourself'], original)
        self.assertEqual(len(self.workers.jobs), jobs)
        self.assertEqual(len(self.engine.slide_versions(root, None, 'check-yourself')['versions']), 2)

    def test_the_current_look_also_redraws_and_old_samples_are_refused(self):
        self.brand.offers_looks = True
        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        self.engine.look_samples(root, None)
        with self.assertRaisesRegex(Exception, 'has changed'):
            self.engine.look_apply(root, None, self.brand.LOOKS[0]['id'], 'old')
        count = len(self.workers.of('section'))
        self.engine.look_apply(root, None, self.brand.LOOKS[0]['id'], seen)
        self.to_end(root)
        self.assertEqual(len(self.workers.of('section')), count + 2)


class SlideRestoreContinuationTests(DeckCase):
    def test_restoring_without_the_local_drawing_uses_the_word_chain(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        original = drafts.deck_drawings(root, None)['check-yourself']
        self.engine.slide_words(root, None, 'check-yourself', 'title', 'New words', seen)
        for file in (root / 'work/deck/versions/check-yourself').iterdir():
            file.unlink()
        version = self.engine.slide_versions(root, None, 'check-yourself')['versions'][0]
        self.assertFalse(version['drawing'])
        jobs = len(self.workers.jobs)
        self.engine.slide_restore(root, None, 'check-yourself', version['stamp'],
                                  self.engine._load(root)['deck']['']['saved']['sha256'])
        self.assertEqual(drafts.deck_drawings(root, None)['check-yourself'], original)
        self.assertEqual(len(self.workers.jobs), jobs)

    def test_row_173_explicit_redraw_installs_the_requested_words_before_the_composer(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        count = len(self.workers.of('section'))
        self.engine.slide_words(root, None, 'check-yourself', 'title', 'A different title', seen,
                                _redraw=True)
        self.to_end(root)
        self.assertEqual(len(self.workers.of('section')), count + 1)
        self.assertEqual(json.loads((root / pipeline.OUTLINE).read_text())['slides'][4]['title'],
                         'A different title')
        self.assertIsNone(self.engine._load(root).get('problem'))

    def test_draw_here_rebuilds_only_after_the_explicit_action(self):
        import shutil
        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        shutil.rmtree(root / pipeline.WORK)
        count = len(self.workers.of('section'))
        card = next(card for card in drafts.view(self.engine, root)['cards'] if card['kind'] == 'deck')
        self.assertFalse(card['local'])
        self.assertTrue(card['slides'])
        self.assertFalse((root / pipeline.WORK).exists())
        self.engine.draw_here(root, None, seen)
        self.to_end(root)
        self.assertEqual(len(self.workers.of('section')), count + 2)
        self.assertIsNone(self.engine._load(root).get('problem'))

    def test_history_refuses_a_linked_folder_and_an_unlisted_level(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        with self.assertRaisesRegex(Exception, 'Choose a level'):
            self.engine.slide_versions(root, '../elsewhere', 'check-yourself')
        outside = self.base / 'outside-history'
        outside.mkdir()
        (root / 'deck/versions').symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(Exception, 'plain file|symbolic|plain files|linked file'):
            self.engine.slide_words(root, None, 'check-yourself', 'title', 'New title',
                                    self.engine._load(root)['deck']['']['saved']['sha256'])
        self.assertEqual(list(outside.iterdir()), [])


class ApprovedHistoryTests(JudgedSlideNoteTests):
    propose = ApprovedWordsTests.propose
    approve = ApprovedWordsTests.approve

    def test_restoring_bound_words_asks_again_before_changing_the_deck(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        seen, proposed = self.propose(root)
        self.approve(root, seen, proposed)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        versions = self.engine.slide_versions(root, None, 'check-yourself')['versions']
        self.assertTrue(versions)
        outline = (root / pipeline.OUTLINE).read_bytes()
        jobs = len(self.workers.jobs)
        result = self.engine.slide_restore(root, None, 'check-yourself', versions[0]['stamp'], seen)
        self.assertIn('approval', result)
        self.assertEqual((root / pipeline.OUTLINE).read_bytes(), outline)
        self.approve(root, seen, result['approval'])
        self.assertEqual(len(self.workers.jobs), jobs)
        self.assertEqual(json.loads((root / pipeline.OUTLINE).read_text())['slides'][4]['title'],
                         versions[0]['words']['title'])

    def test_an_approved_redraw_uses_the_persons_words_and_only_one_answer(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        seen, proposed = self.propose(root)
        count = len(self.workers.of('section'))
        self.engine.slide_words_decide(root, proposed['token'], 'approve', seen,
            question=proposed['question']['id'], revision=proposed['revision'],
            response='I approve these words.', redraw=True)
        self.to_end(root)
        self.assertIsNone(self.engine._load(root).get('problem'))
        self.assertEqual(len(self.workers.of('section')), count + 1)
        self.assertEqual(json.loads((root / pipeline.OUTLINE).read_text())['slides'][4]['title'],
                         proposed['after'])


class SlideHistoryRoutesTests(PageCase):
    def test_history_restore_and_looks_routes(self):
        self.brand.offers_looks = True
        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        self.post('drafts/slide-words', {'path': str(root), 'level': '', 'slide': 'check-yourself',
            'field': 'title', 'text': 'Changed title', 'seen': seen})
        versions = self.get('drafts/slide-versions', path=str(root), level='', slide='check-yourself')['versions']
        image = self.get('slide', path=str(root), artifact='deck', number=5,
                         version='check-yourself/' + versions[0]['stamp'])
        self.assertTrue(image.startswith(b'\x89PNG'))
        self.post('drafts/slide-restore', {'path': str(root), 'level': '', 'slide': 'check-yourself',
            'stamp': versions[0]['stamp'], 'seen': self.engine._load(root)['deck']['']['saved']['sha256']})
        result = self.post('drafts/look-samples', {'path': str(root), 'level': ''})
        self.assertTrue(result['look']['looks'])
        self.assertTrue(self.get('slide', path=str(root), artifact='deck', section='look',
                                number=1).startswith(b'\x89PNG'))
        self.post('drafts/look', {'path': str(root), 'level': '',
            'choice': result['look']['looks'][-1]['id'],
            'seen': self.engine._load(root)['deck']['']['saved']['sha256']})
        self.assertIsNone(self.engine._load(root).get('problem'))


class SlideReviewFixTests(DeckCase):
    def test_restore_kept_drawing_can_change_the_number_of_points(self):
        from test_drafts import edit
        root = self.begin(flow='desk')
        self.to_end(root)
        original = json.loads((root / pipeline.OUTLINE).read_text())
        before = drafts.deck_drawings(root, None)['check-yourself']
        self.workers.outline_said = copy.deepcopy(original)
        self.workers.outline_said['slides'][4]['points'].append({'label': 'Added', 'text': 'Another point.'})
        edit(self, root, 'document', lambda text: text.replace('## When capacity holds', '## When capacity holds\nMore.'))
        self.engine.update(root, 'deck')
        self.to_end(root)
        version = self.engine.slide_versions(root, None, 'check-yourself')['versions'][0]
        count = len(self.workers.jobs)
        self.engine.slide_restore(root, None, 'check-yourself', version['stamp'],
                                  self.engine._load(root)['deck']['']['saved']['sha256'])
        self.assertEqual(drafts.deck_drawings(root, None)['check-yourself'], before)
        self.assertEqual(len(self.workers.jobs), count)

    def test_whole_price_uses_the_recorded_cost_words(self):
        from studio_core import stops
        root = self.begin(flow='desk')
        self.to_end(root)
        with mock.patch.object(self.engine, '_redo_steps', return_value=(90, 0.42)):
            card = next(one for one in drafts.view(self.engine, root)['cards'] if one['kind'] == 'deck')
        self.assertIn(stops.cost(90, 0.42), card['look_price'])
        self.assertNotIn('(90,', card['look_price'])

    def test_failed_look_samples_offer_the_explicit_default(self):
        self.brand.offers_looks = True
        root = self.begin(flow='desk')
        self.to_end(root)
        self.brand.cannot_render = True
        look = self.engine.look_samples(root, None)
        self.assertTrue(look['failed'])
        self.assertTrue(look['default_available'])
        count = len(self.workers.of('section'))
        self.engine.look_apply(root, None, pipeline.DEFAULT_LOOK,
                              self.engine._load(root)['deck']['']['saved']['sha256'])
        self.to_end(root)
        self.assertEqual(len(self.workers.of('section')), count + 2)

    def test_whole_deck_note_finishes_every_section(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        count = len(self.workers.of('section'))
        self.engine.deck_note(root, None, 'Use simpler diagrams.',
            self.engine._load(root)['deck']['']['saved']['sha256'])
        self.to_end(root)
        self.assertEqual(len(self.workers.of('section')), count + 2)
        card = next(item for item in drafts.view(self.engine, root)['cards'] if item['kind'] == 'deck')
        self.assertEqual((card['change']['status'], card['change']['done']), ('done', 2))

    def test_whole_deck_note_draws_all_sections_and_stop_keeps_the_rest(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        count = len(self.workers.of('section'))
        original = self.engine._section
        calls = []
        def stop_after_one(*args):
            result = original(*args)
            calls.append(True)
            self.engine.deck_note_stop(root, None)
            return result
        with mock.patch.object(self.engine, '_section', side_effect=stop_after_one):
            self.engine.deck_note(root, None, 'Use a simpler drawing.',
                                  self.engine._load(root)['deck']['']['saved']['sha256'])
        self.to_end(root)
        self.assertEqual(len(self.workers.of('section')), count + 1)
        card = next(one for one in drafts.view(self.engine, root)['cards'] if one['kind'] == 'deck')
        self.assertEqual(card['change']['status'], 'stopped')
        self.assertEqual(card['change']['done'], 1)
        self.assertEqual(card['change']['total'], 2)
        self.engine.look_samples(root, None)
        self.engine.look_apply(root, None, pipeline.DEFAULT_LOOK,
            self.engine._load(root)['deck']['']['saved']['sha256'])
        self.to_end(root)
        self.assertIsNone(self.engine._load(root).get('problem'))
        self.assertEqual(len(self.workers.of('section')), count + 3)


class SlideSelectionTests(DeckCase):
    def test_selection_changes_only_its_passage_and_keeps_history(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        old = json.loads((root / pipeline.OUTLINE).read_text())['slides'][4]['title']
        count = len(self.workers.of('section'))
        self.workers.then('words', lambda tools, job: tools.submit_artifact('words', 'Review'))
        self.engine.slide_selection(root, None, 'check-yourself', 'title', 'rephrase', 0,
            old.split()[0], old, self.engine._load(root)['deck']['']['saved']['sha256'])
        self.to_end(root)
        self.assertFalse(self.engine._load(root)['drafts']['jobs'][-1].get('error'), self.engine._load(root)['drafts']['jobs'][-1])
        new = json.loads((root / pipeline.OUTLINE).read_text())['slides'][4]['title']
        self.assertEqual(new, 'Review' + old[len(old.split()[0]):])
        self.assertEqual(len(self.workers.of('section')), count)
        self.assertEqual(self.engine.slide_versions(root, None, 'check-yourself')['versions'][0]['source'], 'selection')

    def test_selection_does_not_replace_concurrently_edited_words(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        old = json.loads((root / pipeline.OUTLINE).read_text())['slides'][4]['title']
        def during(tools, job):
            path = root / pipeline.OUTLINE
            outline = json.loads(path.read_text())
            outline['slides'][4]['title'] = 'Later typing'
            path.write_text(json.dumps(outline))
            return tools.submit_artifact('words', 'Review')
        self.workers.then('words', during)
        self.engine.slide_selection(root, None, 'check-yourself', 'title', 'fix', 0,
            old, old, self.engine._load(root)['deck']['']['saved']['sha256'])
        self.assertEqual(json.loads((root / pipeline.OUTLINE).read_text())['slides'][4]['title'], 'Later typing')
        self.assertFalse(self.engine._load(root)['drafts']['jobs'][-1]['applied'])


class DeckOutlineTests(DeckCase):
    def test_outline_prices_then_saves_titles_and_order_with_history(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        before = json.loads((root / pipeline.OUTLINE).read_text())
        slides = copy.deepcopy(before['slides'])
        slides[4]['title'] = 'Review your choice'
        slides[2], slides[4] = slides[4], slides[2]
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        count = len(self.workers.jobs)
        priced = self.engine.deck_outline(root, None, slides, seen, price=True)
        self.assertTrue(priced['price'])
        self.assertEqual(len(self.workers.jobs), count)
        self.assertEqual(json.loads((root / pipeline.OUTLINE).read_text()), before)
        self.engine.deck_outline(root, None, slides, seen)
        self.to_end(root)
        self.assertIsNone(self.engine._load(root).get('problem'))
        self.assertEqual(json.loads((root / pipeline.OUTLINE).read_text())['slides'], slides)
        self.assertEqual(self.engine.slide_versions(root, None, 'check-yourself')['versions'][0]['source'], 'outline')

    def test_new_slide_ids_follow_the_slides_tool_contract(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        slides = json.loads((root / pipeline.OUTLINE).read_text())['slides']
        added = {'kind': 'content', 'title': 'Practice again', 'understand': 'Practice again',
                 'relation': 'none', 'rhythm': 'breathing', 'points': [], 'sources': ['O2'],
                 'notes': 'Explain your choice.'}
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        for ident in ('a', '12345', 'added-' + 'a' * 45, 'a' * 80, '../escape', 'a/bbb'):
            with self.subTest(ident=ident), self.assertRaises(workspace.WorkspaceError):
                self.engine.deck_outline(root, None, [*slides, {**added, 'id': ident}], seen, price=True)
        for ident in ('abcde', '_Abcd', 'a' * 41):
            with self.subTest(ident=ident):
                self.assertTrue(self.engine.deck_outline(root, None,
                    [*slides, {**added, 'id': ident}], seen, price=True)['price'])
        ident = 'a' * 41
        self.engine.deck_outline(root, None, [*slides, {**added, 'id': ident}], seen)
        self.to_end(root)
        self.assertIsNone(self.engine._load(root).get('problem'))
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        self.engine.slide_speaker_notes(root, None, ident, 'Explain the new slide.', seen)
        versions = self.engine.slide_versions(root, None, ident)['versions']
        self.assertEqual(versions[0]['source'], 'save')
        self.assertTrue(versions[0]['drawing'])

    def test_row_172_saved_legacy_slide_ids_keep_history_and_notes(self):
        ids = ('a', '12345', 'added-' + 'a' * 45, 'a' * 80)
        self.workers.outline_said = copy.deepcopy(self.workers.outline_said)
        for slide, ident in zip(self.workers.outline_said['slides'][1:5], ids):
            slide['id'] = ident
        root = self.begin(flow='desk')
        self.to_end(root)
        for ident in ids:
            with self.subTest(ident=ident):
                self.assertEqual(self.engine.slide_versions(root, None, ident)['versions'], [])
                seen = self.engine._load(root)['deck']['']['saved']['sha256']
                self.engine.slide_speaker_notes(root, None, ident, 'Explain the choice again.', seen)
                versions = self.engine.slide_versions(root, None, ident)['versions']
                self.assertEqual(versions[0]['source'], 'save')
                self.assertTrue(versions[0]['drawing'])
                self.assertTrue((root / 'deck/versions' / (ident + '.jsonl')).is_file())
        for ident in ('../escape', '/tmp/escape', 'a/bbb', 'a\\bbb', '.', '..', 'a' * 81):
            with self.subTest(ident=ident), self.assertRaises((ValueError, workspace.WorkspaceError)):
                self.engine.slide_versions(root, None, ident)

    def test_outline_refuses_removing_the_only_slide_for_an_objective(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        before = json.loads((root / pipeline.OUTLINE).read_text())
        with self.assertRaises(workspace.WorkspaceError):
            self.engine.deck_outline(root, None, before['slides'][:2],
                self.engine._load(root)['deck']['']['saved']['sha256'])
        self.assertEqual(json.loads((root / pipeline.OUTLINE).read_text()), before)


class ApprovedReviewFixTests(JudgedSlideNoteTests):
    approve = ApprovedWordsTests.approve

    def test_selection_waits_for_the_actual_design_answer(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        before = (root / pipeline.OUTLINE).read_bytes()
        title = json.loads(before)['slides'][4]['title']
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        self.workers.then('words', lambda tools, job: tools.submit_artifact('words', 'Review'))
        self.engine.slide_selection(root, None, 'check-yourself', 'title', 'shorten', 0,
            title, title, seen)
        card = next(item for item in drafts.view(self.engine, root)['cards'] if item['kind'] == 'deck')
        result = card['selection']['result']
        self.assertIn('approval', result)
        self.assertEqual((root / pipeline.OUTLINE).read_bytes(), before)
        self.approve(root, seen, result['approval'])
        self.assertEqual(json.loads((root / pipeline.OUTLINE).read_text())['slides'][4]['title'], 'Review')

    def test_outline_waits_for_design_approval_before_saving(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        before = (root / pipeline.OUTLINE).read_bytes()
        slides = json.loads(before)['slides']
        slides[4]['title'] = 'Review your choice'
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        result = self.engine.deck_outline(root, None, slides, seen)
        self.assertIn('approval', result)
        self.assertEqual((root / pipeline.OUTLINE).read_bytes(), before)
        self.approve(root, seen, result['approval'])
        self.to_end(root)
        self.assertIsNone(self.engine._load(root).get('problem'))
        self.assertEqual(json.loads((root / pipeline.OUTLINE).read_text())['slides'], slides)

    def test_restore_different_point_count_waits_for_design_approval(self):
        from test_drafts import edit
        root = self.begin(flow='desk')
        self.to_end(root)
        original = json.loads((root / pipeline.OUTLINE).read_text())
        self.workers.outline_said = copy.deepcopy(original)
        self.workers.outline_said['slides'][4]['points'].append({'label': 'Added', 'text': 'Another point.'})
        edit(self, root, 'document', lambda text: text.replace('## When capacity holds', '## When capacity holds\nMore.'))
        self.engine.update(root, 'deck')
        self.to_end(root)
        version = self.engine.slide_versions(root, None, 'check-yourself')['versions'][0]
        before = (root / pipeline.OUTLINE).read_bytes()
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        result = self.engine.slide_restore(root, None, 'check-yourself', version['stamp'], seen)
        self.assertIn('approval', result)
        self.assertEqual((root / pipeline.OUTLINE).read_bytes(), before)
        count = len(self.workers.jobs)
        self.approve(root, seen, result['approval'])
        self.assertEqual(len(self.workers.jobs), count)
        self.assertEqual(json.loads((root / pipeline.OUTLINE).read_text())['slides'][4]['points'],
                         original['slides'][4]['points'])


class DeckControlRoutesTests(PageCase):
    def test_selection_outline_and_whole_note_routes(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        slides = json.loads((root / pipeline.OUTLINE).read_text())['slides']
        slides[4]['title'] = 'Review your choice'
        sent = {'path': str(root), 'level': '', 'seen': seen, 'slides': slides}
        self.assertTrue(self.post('drafts/deck-outline-price', sent)['price'])
        self.post('drafts/deck-outline', sent)
        self.to_end(root)
        self.workers.then('words', lambda tools, job: tools.submit_artifact('words', 'Check'))
        self.post('drafts/slide-selection', {'path': str(root), 'level': '', 'slide': 'check-yourself',
            'field': 'title', 'action': 'rephrase', 'start': 0, 'passage': 'Review',
            'text': slides[4]['title'], 'seen': self.engine._load(root)['deck']['']['saved']['sha256']})
        self.to_end(root)
        self.assertEqual(json.loads((root / pipeline.OUTLINE).read_text())['slides'][4]['title'], 'Check your choice')
        self.post('drafts/deck-note', {'path': str(root), 'level': '', 'note': 'Use a simpler diagram.',
            'seen': self.engine._load(root)['deck']['']['saved']['sha256']})
        self.to_end(root)
        card = next(item for item in drafts.view(self.engine, root)['cards'] if item['kind'] == 'deck')
        self.assertEqual(card['change']['status'], 'done')


class DeckReviewLifecycleTests(JudgedSlideNoteTests):
    approve = ApprovedWordsTests.approve

    def selected(self, root):
        title = json.loads((root / pipeline.OUTLINE).read_text())['slides'][4]['title']
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        self.workers.then('words', lambda tools, job: tools.submit_artifact('words', 'Review'))
        self.engine.slide_selection(root, None, 'check-yourself', 'title', 'shorten', 0, title, title, seen)
        card = next(item for item in drafts.view(self.engine, root)['cards'] if item['kind'] == 'deck')
        return seen, card['selection']

    def test_added_slide_waits_for_design_approval_and_keeps_existing_sections(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        before = (root / pipeline.OUTLINE).read_bytes()
        section = self.built(root)['sections']['section-1']['sha256']
        slides = json.loads(before)['slides']
        slides.append({'id': 'added-practice', 'kind': 'content', 'title': 'Practice again',
            'understand': 'Practice again', 'relation': 'none', 'rhythm': 'breathing',
            'points': [], 'sources': ['O2'], 'notes': 'Ask the learner to explain the choice.'})
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        self.assertTrue(self.engine.deck_outline(root, None, slides, seen, price=True)['price'])
        result = self.engine.deck_outline(root, None, slides, seen)
        self.assertIn('approval', result)
        self.assertEqual((root / pipeline.OUTLINE).read_bytes(), before)
        self.approve(root, seen, result['approval'])
        self.to_end(root)
        self.assertIsNone(self.engine._load(root).get('problem'))
        self.assertEqual(json.loads((root / pipeline.OUTLINE).read_text())['slides'], slides)
        self.assertEqual(self.built(root)['sections']['section-1']['sha256'], section)

    def test_selection_result_settles_after_approval_and_cancellation(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        seen, job = self.selected(root)
        self.approve(root, seen, job['result']['approval'])
        result = next(item for item in drafts.view(self.engine, root)['cards'] if item['kind'] == 'deck')['selection']['result']
        self.assertNotIn('approval', result)
        self.assertTrue(result['fits'])
        self.engine.slide_words(root, None, 'check-yourself', 'notes', 'A note.', self.engine._load(root)['deck']['']['saved']['sha256'])
        # A different selection avoids a no-op wording result.
        self.workers.then('words', lambda tools, job: tools.submit_artifact('words', 'Another title'))
        title = json.loads((root / pipeline.OUTLINE).read_text())['slides'][4]['title']
        self.engine.slide_selection(root, None, 'check-yourself', 'title', 'rephrase', 0, title, title,
            self.engine._load(root)['deck']['']['saved']['sha256'])
        job = next(item for item in drafts.view(self.engine, root)['cards'] if item['kind'] == 'deck')['selection']
        self.engine.slide_words_decide(root, job['result']['approval']['token'], 'cancel', None)
        result = next(item for item in drafts.view(self.engine, root)['cards'] if item['kind'] == 'deck')['selection']['result']
        self.assertNotIn('approval', result)
        self.assertTrue(result['cancelled'])


class DeckReviewConflictTests(DeckCase):
    def test_outline_cannot_remove_a_queued_selection_target(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        slides = json.loads((root / pipeline.OUTLINE).read_text())['slides']
        title = slides[4]['title']
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        with mock.patch.object(self.engine, 'wake'):
            self.engine.slide_selection(root, None, 'check-yourself', 'title', 'fix', 0, title, title, seen)
        with self.assertRaisesRegex(workspace.WorkspaceError, 'selection|selected words'):
            self.engine.deck_outline(root, None, slides[:4], seen)

    def test_outline_can_price_and_add_a_slide_without_redrawing_unchanged_sections(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        slides = json.loads((root / pipeline.OUTLINE).read_text())['slides']
        slides.append({'id': 'added-practice', 'kind': 'content', 'title': 'Practice again',
            'understand': 'Practice again', 'relation': 'none', 'rhythm': 'breathing',
            'points': [], 'sources': ['O2'], 'notes': 'Ask the learner to explain the choice.'})
        before = self.built(root)['sections']['section-1']['sha256']
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        self.assertTrue(self.engine.deck_outline(root, None, slides, seen, price=True)['price'])
        self.engine.deck_outline(root, None, slides, seen)
        self.to_end(root)
        self.assertIsNone(self.engine._load(root).get('problem'))
        self.assertEqual(json.loads((root / pipeline.OUTLINE).read_text())['slides'], slides)
        self.assertEqual(self.built(root)['sections']['section-1']['sha256'], before)


class DeckActiveStopTests(DeckCase):
    def test_stop_terminates_a_composer_companion_command(self):
        import sys
        from runner import companion
        from runner_support import written, still_running
        root = self.begin(flow='desk')
        self.to_end(root)
        pids = self.base / 'composer-pids'
        def command(tools, job):
            companion.run_command([sys.executable, '-c',
                'import os,sys,time; open(sys.argv[1], "w").write(str(os.getpid()) + "\\n"); time.sleep(20)',
                str(pids)], None, 30, 'A stand-in composer command')
        self.workers.then('section', command)
        self.engine.background = True
        self.engine.deck_note(root, None, 'Make it simpler.',
            self.engine._load(root)['deck']['']['saved']['sha256'])
        processes = written(pids)
        self.engine.deck_note_stop(root, None)
        self.assertEqual(still_running(processes), [])
        thread = self.engine._run(root).thread
        if thread:
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive())
        self.assertIsNone(self.engine._load(root).get('problem'))

    def test_stop_terminates_the_active_composer_and_keeps_only_completed_sections(self):
        import subprocess
        import sys
        import threading
        from runner import agents, worker_tools
        root = self.begin(flow='desk')
        self.to_end(root)
        before = copy.deepcopy(self.built(root)['sections'])
        adapter = self.engine.adapter(self.engine._load(root)['agent'])
        original = adapter.run
        started, terminated = threading.Event(), threading.Event()
        calls, processes = [], []
        def run(job, activity=None, stop=None):
            spec = worker_tools.WorkerTools(job.folder).job
            if 'section' not in spec['artifacts']:
                return original(job, activity=activity, stop=stop)
            calls.append(True)
            if len(calls) == 1:
                return original(job, activity=activity, stop=stop)
            child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'])
            processes.append(child)
            started.set()
            try:
                while not stop.is_set():
                    try:
                        child.wait(timeout=0.03)
                        break
                    except subprocess.TimeoutExpired:
                        pass
                child.terminate()
                child.wait(timeout=5)
                terminated.set()
                return agents.Outcome(False, 'stopped', 'Stopped by the person.')
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait()
        self.engine.background = True
        try:
            with mock.patch.object(adapter, 'run', side_effect=run):
                self.engine.deck_note(root, None, 'Use simpler diagrams.',
                    self.engine._load(root)['deck']['']['saved']['sha256'])
                self.assertTrue(started.wait(10), 'The second composer did not start.')
                self.engine.deck_note_stop(root, None)
                self.assertTrue(terminated.is_set(), 'Stop returned before the active process terminated.')
                thread = self.engine._run(root).thread
                if thread:
                    thread.join(timeout=10)
                    self.assertFalse(thread.is_alive())
        finally:
            self.engine._run(root).stop.set()
            for child in processes:
                if child.poll() is None:
                    child.terminate()
                    child.wait(timeout=5)
            thread = self.engine._run(root).thread
            if thread:
                thread.join(timeout=10)
        after = self.built(root)['sections']
        self.assertNotEqual(after['section-1']['file'], before['section-1']['file'])
        self.assertEqual(after['section-2'], before['section-2'])
        self.assertEqual(len(calls), 2)
        chain = self.engine._load(root)['deck']['']['note_chain']
        self.assertEqual(chain['status'], 'stopped')


class SelectionSettlementRoutesTests(PageCase):
    def test_fit_refused_selection_can_be_discarded_without_changing_the_slide(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        before = (root / pipeline.OUTLINE).read_bytes()
        title = json.loads(before)['slides'][4]['title']
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        self.workers.then('words', lambda tools, job: tools.submit_artifact('words', 'TOO LONG TO FIT'))
        self.post('drafts/slide-selection', {'path': str(root), 'level': '', 'slide': 'check-yourself',
            'field': 'title', 'action': 'expand', 'start': 0, 'passage': title, 'text': title, 'seen': seen})
        job = next(item for item in drafts.view(self.engine, root)['cards'] if item['kind'] == 'deck')['selection']
        self.assertFalse(job['result']['fits'])
        self.post('drafts/slide-selection-settle', {'path': str(root), 'job': job['id'], 'action': 'discard'})
        result = next(item for item in drafts.view(self.engine, root)['cards'] if item['kind'] == 'deck')['selection']['result']
        self.assertTrue(result['cancelled'])
        self.assertNotIn('fits', result)
        self.assertEqual((root / pipeline.OUTLINE).read_bytes(), before)

    def test_selection_result_can_only_be_marked_saved_after_publication(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        title = json.loads((root / pipeline.OUTLINE).read_text())['slides'][4]['title']
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        self.workers.then('words', lambda tools, job: tools.submit_artifact('words', 'TOO LONG TO FIT'))
        self.engine.slide_selection(root, None, 'check-yourself', 'title', 'expand', 0, title, title, seen)
        job = next(item for item in drafts.view(self.engine, root)['cards'] if item['kind'] == 'deck')['selection']
        with self.assertRaisesRegex(workspace.WorkspaceError, 'not been saved'):
            self.engine.slide_selection_settle(root, job['id'], 'saved')
        self.engine.slide_words(root, None, 'check-yourself', 'title', 'TOO LONG TO FIT', seen, _redraw=True)
        self.to_end(root)
        self.engine.slide_selection_settle(root, job['id'], 'saved')
        result = next(item for item in drafts.view(self.engine, root)['cards'] if item['kind'] == 'deck')['selection']['result']
        self.assertTrue(result['fits'])
        self.assertNotIn('approval', result)
