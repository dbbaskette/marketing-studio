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

    def test_design_bound_title_names_the_design_refusal_and_changes_nothing(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        before, commits = self.saved_files(root), self.log()
        with self.assertRaisesRegex(Exception, 'approved design keeps these words'):
            self.engine.slide_words(root, None, 'check-yourself', 'title', 'A new title', seen)
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
