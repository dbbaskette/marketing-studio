"""Desk jobs: what each kind sends, one job per blog, and how a result lands."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import functools
import json
import unittest

import blog_runner
import desk
import desk_jobs
import tool_jobs
from test_desk import DRAFT, GOOGLE, IMAGE_TWO, SECTIONED, DeskCase


class DeskJobCase(DeskCase):
    def setUp(self):
        super().setUp()
        self.addCleanup(lambda: blog_runner.ENGINES.pop(str(self.root), None))
        self.made = desk.create(self.root, {'title': 'Synthetic', 'manuscript': DRAFT})
        self.ident = self.made['id']
        self.part = self.made['sections'][0]['id']

    def saved(self, job):
        return tool_jobs.read(self.root, job['id'])


class DeskJobTests(DeskJobCase):
    def test_a_section_note_sends_the_part_its_neighbours_and_the_edit_rule(self):
        job = desk_jobs.section(self.root, self.ident, 1, self.part, 'Add an example.')
        saved = self.saved(job)
        self.assertEqual(saved['kind'], 'desk-section')
        self.assertEqual(saved['payload']['part']['text'], 'First text.')
        self.assertEqual(saved['payload']['after'], ['Second text.'])
        self.assertEqual(saved['payload']['note'], 'Add an example.')
        self.assertEqual(saved['payload']['response_kind'], 'writing-with-notes')
        self.assertIn('verbatim', saved['guidance'])
        # The note reaches the worker as the author's instruction, not as document data.
        self.assertIn('AUTHOR’S NOTE FOR THIS SECTION', saved['guidance'])
        self.assertIn('"""\nAdd an example.\n"""', saved['guidance'])
        self.assertEqual(saved['metadata']['article'], self.ident)
        self.assertEqual(saved['metadata']['desk']['seen'], 1)
        self.assertEqual(saved['metadata']['desk']['part'], self.part)

    def test_no_note_writes_the_section_again_without_the_edit_rule(self):
        job = desk_jobs.section(self.root, self.ident, 1, self.part, '')
        saved = self.saved(job)
        self.assertNotIn('verbatim', saved['guidance'])
        self.assertIn('Write this section again', saved['guidance'])
        self.assertEqual(saved['metadata']['desk']['action'], 'again')

    def test_the_title_and_opening_are_edited_directly(self):
        with self.assertRaisesRegex(ValueError, 'edit the title and opening directly'):
            desk_jobs.section(self.root, self.ident, 1, 'opening', 'Shorter.')

    def test_one_desk_job_per_blog(self):
        desk_jobs.section(self.root, self.ident, 1, self.part, 'One.')
        with self.assertRaisesRegex(ValueError, 'already working'):
            desk_jobs.section(self.root, self.ident, 1, self.part, 'Two.')

    def test_a_job_from_an_outdated_form_is_refused(self):
        desk.save(self.root, self.ident, 1, self.part, 'Changed.')
        with self.assertRaisesRegex(ValueError, 'changed since'):
            desk_jobs.section(self.root, self.ident, 1, self.part, 'One.')

    def test_a_selection_must_be_in_the_part_once(self):
        with self.assertRaisesRegex(ValueError, 'no longer in'):
            desk_jobs.selection(self.root, self.ident, 1, self.part, 'Absent.', 'fix', '')
        desk.save(self.root, self.ident, 1, self.part, 'Twice and twice.')
        with self.assertRaisesRegex(ValueError, 'more than once'):
            desk_jobs.selection(self.root, self.ident, 2, self.part, 'wice', 'fix', '')

    def test_a_selection_sends_its_passage_and_action(self):
        job = desk_jobs.selection(self.root, self.ident, 1, self.part, 'First', 'shorten', '')
        saved = self.saved(job)
        self.assertEqual(saved['kind'], 'desk-selection')
        self.assertEqual(saved['payload']['passage'], 'First')
        self.assertEqual(saved['payload']['around'], 'First text.')
        self.assertIn(desk_jobs.ACTIONS['shorten'], saved['guidance'])
        self.assertEqual(saved['metadata']['desk']['selection'], 'First')

    def test_ask_needs_an_instruction_given_as_the_authors(self):
        with self.assertRaisesRegex(ValueError, 'what to do'):
            desk_jobs.selection(self.root, self.ident, 1, self.part, 'First', 'ask', '')
        job = desk_jobs.selection(self.root, self.ident, 1, self.part, 'First', 'ask', 'Bold.')
        self.assertIn('"""\nBold.\n"""', self.saved(job)['guidance'])
        with self.assertRaisesRegex(ValueError, 'Choose rephrase'):
            desk_jobs.selection(self.root, self.ident, 1, self.part, 'First', 'poem', '')

    def test_a_selection_in_the_title_is_allowed(self):
        job = desk_jobs.selection(self.root, self.ident, 1, 'title', 'synthetic', 'rephrase')
        self.assertEqual(self.saved(job)['payload']['around'], 'A synthetic title')

    def test_guidance_is_the_kind_of_post_tone_and_house_guide_and_no_voice(self):
        made = desk.create(
            self.root,
            {'title': 'Styled', 'manuscript': DRAFT, 'style': 'how-to', 'tone': 'Warm'},
        )
        job = desk_jobs.section(self.root, made['id'], 1, made['sections'][0]['id'], 'Shorter.')
        saved = self.saved(job)
        self.assertIn(blog_runner.house_guide(), saved['guidance'])
        self.assertIn(blog_runner.style_rule('How-to and tutorial', voice=False), saved['guidance'])
        self.assertNotIn('voice wins', saved['guidance'])
        self.assertIn('Tone nudge: Warm.', saved['guidance'])
        self.assertEqual(saved['payload']['style']['name'], 'How-to and tutorial')
        self.assertNotIn('voice', saved['payload'])
        self.assertNotIn('Write as', saved['guidance'])

    def test_length_is_for_new_writing_only(self):
        made = desk.create(self.root, {'title': 'Long', 'manuscript': DRAFT, 'length': 'deep'})
        part = made['sections'][0]['id']
        again = self.saved(desk_jobs.section(self.root, made['id'], 1, part, ''))
        self.assertIn(blog_runner.LENGTHS['deep'], again['guidance'])
        tool_jobs.control(self.root, again['id'], 'cancel', blog_runner.engine(self.root))
        note = self.saved(desk_jobs.section(self.root, made['id'], 1, part, 'Shorter.'))
        self.assertNotIn(blog_runner.LENGTHS['deep'], note['guidance'])

    def test_sources_reach_the_job_with_their_stance(self):
        fact, messaging = (
            self.source('A fact.'),
            self.source('Our claim.', 'reference', 'messaging'),
        )
        made = desk.create(
            self.root, {'title': 'Sourced', 'manuscript': DRAFT, 'sources': [fact, messaging]}
        )
        job = desk_jobs.section(self.root, made['id'], 1, made['sections'][0]['id'], 'More.')
        sources = self.saved(job)['payload']['sources']
        self.assertEqual(
            sorted((s['text'], s['stance']) for s in sources),
            [('A fact.', 'evidence'), ('Our claim.', 'messaging')],
        )


class WholeDraftTests(DeskJobCase):
    def test_a_whole_draft_note_starts_with_the_first_section_and_the_whole_draft(self):
        job = desk_jobs.revise_all(self.root, self.ident, 1, 'Tighten throughout.')
        saved = self.saved(job)
        self.assertEqual(saved['kind'], 'desk-revise-all')
        self.assertEqual(
            [s['text'] for s in saved['payload']['sections']], ['First text.', 'Second text.']
        )
        self.assertEqual(saved['payload']['part']['id'], self.part)
        self.assertEqual(saved['payload']['opening'], 'An opening paragraph.')
        self.assertEqual(saved['payload']['note'], 'Tighten throughout.')
        self.assertIn('this section only', saved['guidance'])
        self.assertIn('verbatim', saved['guidance'])
        self.assertIn('"""\nTighten throughout.\n"""', saved['guidance'])
        meta = saved['metadata']['desk']
        self.assertEqual((meta['index'], len(meta['order'])), (0, 2))

    def test_an_empty_whole_draft_note_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'Write the note for the whole draft'):
            desk_jobs.revise_all(self.root, self.ident, 1, '  ')

    def test_a_first_pass_refuses_an_unknown_choice(self):
        with self.assertRaisesRegex(ValueError, 'Choose tighten, reshape'):
            desk_jobs.first_pass(self.root, self.ident, 1, 'polish')

    def test_leave_it_queues_nothing(self):
        self.assertIsNone(desk_jobs.first_pass(self.root, self.ident, 1, 'leave'))
        self.assertEqual(desk_jobs.jobs(self.root, self.ident), [])

    def test_tighten_reads_the_copy_edit_rule(self):
        import manuscript_editor

        saved = self.saved(desk_jobs.first_pass(self.root, self.ident, 1, 'tighten'))
        self.assertEqual(saved['kind'], 'desk-first-pass')
        self.assertIn(desk_jobs.desk_check('copyedit'), saved['guidance'])
        self.assertNotIn(manuscript_editor.CHECKS['copyedit'], saved['guidance'])
        self.assertEqual(saved['metadata']['desk']['action'], 'tighten')

    def test_reshape_needs_a_kind_of_post_and_reads_its_shape(self):
        with self.assertRaisesRegex(ValueError, 'Choose a kind of post'):
            desk_jobs.first_pass(self.root, self.ident, 1, 'reshape')
        made = desk.create(
            self.root,
            {'title': 'Styled', 'manuscript': DRAFT, 'style': 'how-to', 'length': 'short'},
        )
        saved = self.saved(desk_jobs.first_pass(self.root, made['id'], 1, 'reshape'))
        self.assertIn(desk_jobs.RESHAPE, saved['guidance'])
        self.assertIn(blog_runner.LENGTHS['short'], saved['guidance'])
        self.assertNotIn('verbatim', saved['guidance'])

    def test_tighten_proofreads_the_opening_with_the_sections(self):
        saved = self.saved(desk_jobs.first_pass(self.root, self.ident, 1, 'tighten'))
        sent = saved['payload']['sections']
        self.assertEqual(sent[0], {'id': 'opening', 'heading': '', 'text': 'An opening paragraph.'})
        self.assertEqual([s['heading'] for s in sent[1:]], ['First part', 'Second part'])
        self.assertNotIn('opening', saved['payload'])  # Sent once, as the first part.
        self.assertIn('"opening"', saved['guidance'])

    def test_a_draft_without_headings_is_tightened_as_one_part(self):
        made = desk.create(self.root, {'title': 'Flat', 'manuscript': 'Just prose. Teh end.'})
        saved = self.saved(desk_jobs.first_pass(self.root, made['id'], 1, 'tighten'))
        self.assertEqual(
            saved['payload']['sections'],
            [{'id': 'opening', 'heading': '', 'text': 'Just prose. Teh end.'}],
        )
        self.assertIn('Add no ## heading', saved['guidance'])

    def test_reshape_may_divide_a_draft_without_headings(self):
        made = desk.create(
            self.root, {'title': 'Flat', 'manuscript': 'Just prose.', 'style': 'how-to'}
        )
        saved = self.saved(desk_jobs.first_pass(self.root, made['id'], 1, 'reshape'))
        self.assertIn('may divide it into sections with ## headings', saved['guidance'])
        # A draft with sections keeps them: reshaping adds none.
        styled = desk.create(self.root, {'title': 'Styled', 'manuscript': DRAFT, 'style': 'how-to'})
        saved = self.saved(desk_jobs.first_pass(self.root, styled['id'], 1, 'reshape'))
        self.assertNotIn('may divide it into sections', saved['guidance'])

    def test_a_draft_with_no_text_has_no_first_pass(self):
        made = desk.create(self.root, {'title': 'Empty', 'manuscript': '## Only\n'})
        with self.assertRaisesRegex(ValueError, 'no text to work on yet'):
            desk_jobs.first_pass(self.root, made['id'], 1, 'tighten')

    def test_a_whole_draft_note_revises_a_draft_without_headings(self):
        made = desk.create(self.root, {'title': 'Flat', 'manuscript': 'Just prose.'})
        saved = self.saved(desk_jobs.revise_all(self.root, made['id'], 1, 'Warmer.'))
        self.assertEqual(
            saved['payload']['part'], {'id': 'opening', 'heading': '', 'text': 'Just prose.'}
        )
        self.assertEqual(saved['metadata']['desk']['order'], ['opening'])
        self.assertEqual(saved['metadata']['desk']['part'], 'opening')


class SettleTests(DeskJobCase):
    def ready(self, job, content, **result):
        saved = self.saved(job)
        saved.update(
            status='ready', result={'content': content, 'notes': '', **result}, finished_at='x'
        )
        tool_jobs.write(self.root, saved)
        return saved

    def versions(self, part=None):
        return desk.versions(self.root, self.ident, part or self.part)

    def test_a_note_result_lands_in_the_section_and_keeps_the_old_text(self):
        job = desk_jobs.section(self.root, self.ident, 1, self.part, 'Add an example.')
        self.ready(job, '## First part\n\nFirst text, for example this one.')
        self.assertEqual(desk_jobs.settle(self.root, self.ident), [job['id']])
        draft = desk.read(self.root, self.ident)
        self.assertEqual(draft['sections'][0]['text'], 'First text, for example this one.')
        self.assertEqual(draft['revision'], 2)
        self.assertEqual(self.versions()[0]['text'], 'First text.')
        self.assertEqual(self.versions()[0]['source'], 'rewrite')
        self.assertTrue(self.saved(job)['applied'])
        # Settled once: reading again changes nothing.
        self.assertEqual(desk_jobs.settle(self.root, self.ident), [])
        self.assertEqual(desk.read(self.root, self.ident)['revision'], 2)

    def test_typing_in_another_part_does_not_stop_a_rewrite(self):
        job = desk_jobs.section(self.root, self.ident, 1, self.part, 'Shorter.')
        other = self.made['sections'][1]['id']
        desk.save(self.root, self.ident, 1, other, 'Typed meanwhile.')
        self.ready(job, 'First.')
        desk_jobs.settle(self.root, self.ident)
        texts = [s['text'] for s in desk.read(self.root, self.ident)['sections']]
        self.assertEqual(texts, ['First.', 'Typed meanwhile.'])
        # The page saw revision 2 before the rewrite landed; typing in the other part holds.
        desk.save(self.root, self.ident, 2, other, 'Typed again.')
        with self.assertRaisesRegex(ValueError, 'changed since'):
            desk.save(self.root, self.ident, 2, self.part, 'Over the rewrite.')

    def test_a_result_for_a_changed_part_is_not_applied_and_says_why(self):
        job = desk_jobs.section(self.root, self.ident, 1, self.part, 'Shorter.')
        desk.save(self.root, self.ident, 1, self.part, 'Edited meanwhile.')
        self.ready(job, 'First.')
        desk_jobs.settle(self.root, self.ident)
        self.assertEqual(
            desk.read(self.root, self.ident)['sections'][0]['text'], 'Edited meanwhile.'
        )
        saved = self.saved(job)
        self.assertIs(saved['applied'], False)
        self.assertEqual(saved['error'], desk_jobs.STALE)
        self.assertTrue(saved['settled_at'])

    def test_a_selection_replaces_only_its_passage(self):
        desk.save(self.root, self.ident, 1, self.part, 'Keep this. Change this part. Keep that.')
        job = desk_jobs.selection(self.root, self.ident, 2, self.part, 'Change this part.', 'fix')
        self.ready(job, 'Changed.')
        desk_jobs.settle(self.root, self.ident)
        draft = desk.read(self.root, self.ident)
        self.assertEqual(draft['sections'][0]['text'], 'Keep this. Changed. Keep that.')
        self.assertEqual(self.versions()[0]['source'], 'selection')

    def test_a_selection_keeps_its_trailing_space(self):
        job = desk_jobs.selection(self.root, self.ident, 1, self.part, 'First ', 'rephrase')
        self.ready(job, 'Initial')
        desk_jobs.settle(self.root, self.ident)
        self.assertEqual(desk.read(self.root, self.ident)['sections'][0]['text'], 'Initial text.')

    def test_a_selection_ending_in_a_blank_line_keeps_it(self):
        desk.save(self.root, self.ident, 1, self.part, 'One para.\n\nTwo para.')
        job = desk_jobs.selection(self.root, self.ident, 2, self.part, 'One para.\n\n', 'fix')
        self.ready(job, '\nOne paragraph.\n')
        desk_jobs.settle(self.root, self.ident)
        self.assertEqual(
            desk.read(self.root, self.ident)['sections'][0]['text'], 'One paragraph.\n\nTwo para.'
        )

    def test_a_repeated_word_is_the_one_selected(self):
        desk.save(self.root, self.ident, 1, self.part, 'The cache keeps the data near the code.')
        with self.assertRaisesRegex(ValueError, 'more than once'):
            desk_jobs.selection(self.root, self.ident, 2, self.part, 'the', 'fix')
        with self.assertRaisesRegex(ValueError, 'no longer in'):
            desk_jobs.selection(self.root, self.ident, 2, self.part, 'the', 'fix', '', 0)
        job = desk_jobs.selection(self.root, self.ident, 2, self.part, 'the', 'fix', '', 30)
        self.ready(job, 'its')
        desk_jobs.settle(self.root, self.ident)
        self.assertEqual(
            desk.read(self.root, self.ident)['sections'][0]['text'],
            'The cache keeps the data near its code.',
        )

    def test_a_selection_whose_passage_now_occurs_twice_is_not_applied(self):
        job = desk_jobs.selection(self.root, self.ident, 1, self.part, 'First', 'fix')
        desk.save(self.root, self.ident, 1, self.part, 'First text. First again.')
        self.ready(job, 'Primary')
        desk_jobs.settle(self.root, self.ident)
        self.assertEqual(
            desk.read(self.root, self.ident)['sections'][0]['text'], 'First text. First again.'
        )
        self.assertIs(self.saved(job)['applied'], False)

    def run_chain(self, results):
        """Run a whole-draft note through a fake worker: one result per section, in order;
        an exception stands for a section that failed."""
        calls = []

        def worker(engine, payload, guidance, **options):
            calls.append(payload['part']['id'])
            found = results[len(calls) - 1]
            if isinstance(found, Exception):
                raise found
            return {'content': found, 'notes': '', 'gaps': []}

        engine = blog_runner.Engine(self.root, worker=worker)
        desk_jobs.revise_all(self.root, self.ident, 1, 'Tighten.')
        for _ in results:
            tool_jobs.once(engine)
        return calls

    def test_a_whole_draft_note_revises_each_section_in_order(self):
        ids = [s['id'] for s in self.made['sections']]
        self.assertEqual(self.run_chain(['One.', 'Two.']), ids)
        draft = desk.read(self.root, self.ident)
        self.assertEqual([s['text'] for s in draft['sections']], ['One.', 'Two.'])
        self.assertEqual(self.versions(ids[0])[0]['source'], 'revise-all')
        self.assertEqual(self.versions(ids[1])[0]['text'], 'Second text.')
        shown = desk_jobs.view(self.root, self.ident)
        self.assertEqual((shown['chain']['revised'], shown['chain']['total']), (2, 2))
        self.assertIsNone(shown['working'])

    def test_a_section_that_fails_leaves_the_others_done(self):
        ids = [s['id'] for s in self.made['sections']]
        self.assertEqual(self.run_chain([ValueError('The assistant stopped.'), 'Two.']), ids)
        draft = desk.read(self.root, self.ident)
        self.assertEqual([s['text'] for s in draft['sections']], ['First text.', 'Two.'])
        chain = desk_jobs.view(self.root, self.ident)['chain']
        self.assertEqual(chain['revised'], 1)
        self.assertEqual(chain['problems'][0]['heading'], 'First part')
        self.assertRegex(chain['problems'][0]['error'], 'assistant stopped')

    def test_progress_says_which_section_of_how_many(self):
        desk_jobs.revise_all(self.root, self.ident, 1, 'Tighten.')
        working = desk_jobs.view(self.root, self.ident)['working']
        self.assertEqual((working['index'], working['total']), (0, 2))

    def test_stop_ends_a_whole_draft_note(self):
        job = desk_jobs.revise_all(self.root, self.ident, 1, 'Tighten.')
        desk_jobs.stop(self.root, self.ident, job['id'])
        self.assertEqual(
            [j['status'] for j in desk_jobs.jobs(self.root, self.ident)], ['cancelled']
        )
        self.assertIsNone(desk_jobs.view(self.root, self.ident)['working'])

    def test_a_first_pass_keeps_first_pass_versions(self):
        job = desk_jobs.first_pass(self.root, self.ident, 1, 'tighten')
        self.ready(job, json.dumps([{'id': self.part, 'text': 'Tight.'}]))
        desk_jobs.settle(self.root, self.ident)
        self.assertEqual(self.versions()[0]['source'], 'first-pass')

    def flat(self, **extra):
        made = desk.create(
            self.root, {'title': 'Flat', 'manuscript': 'Just prose. Teh end.', **extra}
        )
        return made['id']

    def test_tighten_lands_in_a_draft_without_headings_and_adds_none(self):
        ident = self.flat()
        job = desk_jobs.first_pass(self.root, ident, 1, 'tighten')
        self.ready(job, json.dumps([{'id': 'opening', 'text': 'Just prose. The end.'}]))
        desk_jobs.settle(self.root, ident)
        draft = desk.read(self.root, ident)
        self.assertEqual((draft['opening'], draft['sections']), ('Just prose. The end.', []))
        kept = desk.versions(self.root, ident, 'opening')
        self.assertEqual(
            [(v['source'], v['text']) for v in kept], [('first-pass', 'Just prose. Teh end.')]
        )

    def test_tighten_that_invents_a_heading_is_refused(self):
        ident = self.flat()
        job = desk_jobs.first_pass(self.root, ident, 1, 'tighten')
        self.ready(
            job, json.dumps([{'id': 'opening', 'text': 'Just prose.\n\n## Invented\n\nEnd.'}])
        )
        desk_jobs.settle(self.root, ident)
        self.assertEqual(desk.read(self.root, ident)['opening'], 'Just prose. Teh end.')
        self.assertRegex(self.saved(job)['error'], 'added a ## section heading')

    def test_reshape_divides_a_draft_without_headings_into_sections(self):
        ident = self.flat(style='how-to')
        job = desk_jobs.first_pass(self.root, ident, 1, 'reshape')
        shaped = 'What you will do.\n\n## Before you start\n\nProse.\n\n## Steps\n\nThe end.'
        self.ready(job, json.dumps([{'id': 'opening', 'text': shaped}]))
        desk_jobs.settle(self.root, ident)
        draft = desk.read(self.root, ident)
        self.assertEqual(self.saved(job)['error'], '')
        self.assertEqual(draft['opening'], 'What you will do.')
        self.assertEqual([s['heading'] for s in draft['sections']], ['Before you start', 'Steps'])
        self.assertEqual([s['text'] for s in draft['sections']], ['Prose.', 'The end.'])
        self.assertEqual(draft['title'], 'Flat')
        self.assertEqual(
            desk.versions(self.root, ident, 'opening')[0]['text'], 'Just prose. Teh end.'
        )

    def divide(self):
        ident = self.flat(style='how-to')
        job = desk_jobs.first_pass(self.root, ident, 1, 'reshape')
        shaped = 'What you will do.\n\n## Before you start\n\nProse.\n\n## Steps\n\nThe end.'
        self.ready(job, json.dumps([{'id': 'opening', 'text': shaped}]))
        desk_jobs.settle(self.root, ident)
        return ident, desk.read(self.root, ident)

    def test_restoring_before_a_divide_undoes_the_division_as_a_whole(self):
        ident, draft = self.divide()
        added = [s['id'] for s in draft['sections']]
        kept = desk.versions(self.root, ident, 'opening')[0]
        self.assertEqual((kept['source'], kept['divided']), ('first-pass', added))
        restored = desk.restore(self.root, ident, draft['revision'], 'opening', 0)
        self.assertEqual((restored['opening'], restored['sections']), ('Just prose. Teh end.', []))
        self.assertEqual(desk.join(restored).count('Just prose.'), 1, 'the content is there once')
        # The sections it took out can be brought back from the Outline tab, with their text.
        gone = desk.removed(self.root, ident)
        self.assertEqual(sorted(s['heading'] for s in gone), ['Before you start', 'Steps'])
        self.assertEqual(sorted(s['text'] for s in gone), ['Prose.', 'The end.'])
        # The divided text is kept as a version of the opening too.
        self.assertEqual(desk.versions(self.root, ident, 'opening')[0]['source'], 'restore')

    def test_a_restore_before_a_divide_leaves_sections_added_since(self):
        ident, draft = self.divide()
        made = desk.outline_save(
            self.root,
            ident,
            draft['revision'],
            [{'id': s['id'], 'heading': s['heading']} for s in draft['sections']]
            + [{'heading': 'My own section'}],
        )
        restored = desk.restore(self.root, ident, made['revision'], 'opening', 0)
        self.assertEqual([s['heading'] for s in restored['sections']], ['My own section'])

    def test_an_opening_that_was_not_sent_is_refused(self):
        made = desk.create(self.root, {'title': 'Sections', 'manuscript': '## A\n\nText.'})
        job = desk_jobs.first_pass(self.root, made['id'], 1, 'tighten')
        self.assertEqual(
            [p['id'] for p in self.saved(job)['payload']['sections']], [made['sections'][0]['id']]
        )
        self.ready(job, json.dumps([{'id': 'opening', 'text': 'An invented opening.'}]))
        desk_jobs.settle(self.root, made['id'])
        self.assertEqual(desk.read(self.root, made['id'])['opening'], '')
        self.assertRegex(self.saved(job)['error'], 'sections this draft does not have')

    def test_a_repeated_title_line_is_left_out_of_the_opening(self):
        ident = self.flat()
        job = desk_jobs.first_pass(self.root, ident, 1, 'tighten')
        self.ready(job, json.dumps([{'id': 'opening', 'text': '# Flat\n\nJust prose. The end.'}]))
        desk_jobs.settle(self.root, ident)
        draft = desk.read(self.root, ident)
        self.assertEqual((draft['title'], draft['opening']), ('Flat', 'Just prose. The end.'))
        job = desk_jobs.revise_all(self.root, ident, draft['revision'], 'Warmer.')
        self.ready(job, '# Another title\n\nWarmer prose.')
        desk_jobs.settle(self.root, ident)
        self.assertEqual(desk.read(self.root, ident)['opening'], 'Warmer prose.')

    def test_a_whole_draft_note_that_fails_on_the_opening_names_it(self):
        ident = self.flat()
        job = desk_jobs.revise_all(self.root, ident, 1, 'Warmer.')
        self.ready(job, 'Warmer.\n\n## Invented\n\nMore.')
        desk_jobs.settle(self.root, ident)
        chain = desk_jobs.view(self.root, ident)['chain']
        self.assertEqual(
            [(p['part'], p['heading']) for p in chain['problems']], [('opening', 'the opening')]
        )

    def test_reshape_adds_no_section_to_a_draft_that_has_sections(self):
        made = desk.create(self.root, {'title': 'Styled', 'manuscript': DRAFT, 'style': 'how-to'})
        job = desk_jobs.first_pass(self.root, made['id'], 1, 'reshape')
        self.ready(job, json.dumps([{'id': 'opening', 'text': 'Intro.\n\n## Extra\n\nMore.'}]))
        desk_jobs.settle(self.root, made['id'])
        self.assertEqual(desk.read(self.root, made['id'])['opening'], 'An opening paragraph.')
        self.assertRegex(self.saved(job)['error'], 'added a ## section heading')

    def test_a_first_pass_lands_in_the_opening_and_the_sections(self):
        job = desk_jobs.first_pass(self.root, self.ident, 1, 'tighten')
        self.ready(
            job,
            json.dumps(
                [
                    {'id': 'opening', 'text': 'A tighter opening.'},
                    {'id': self.part, 'text': 'Tight.'},
                ]
            ),
        )
        desk_jobs.settle(self.root, self.ident)
        draft = desk.read(self.root, self.ident)
        self.assertEqual(
            (draft['opening'], draft['sections'][0]['text']), ('A tighter opening.', 'Tight.')
        )

    def test_a_whole_draft_note_lands_in_the_opening_of_a_draft_without_headings(self):
        ident = self.flat()
        job = desk_jobs.revise_all(self.root, ident, 1, 'Warmer.')
        self.ready(job, 'Warmer prose.')
        desk_jobs.settle(self.root, ident)
        self.assertEqual(self.saved(job)['error'], '')
        self.assertEqual(desk.read(self.root, ident)['opening'], 'Warmer prose.')
        self.assertEqual(desk.versions(self.root, ident, 'opening')[0]['source'], 'revise-all')
        self.assertIsNone(desk_jobs.view(self.root, ident)['working'])

    def test_a_first_pass_result_with_an_unknown_id_changes_nothing(self):
        job = desk_jobs.first_pass(self.root, self.ident, 1, 'tighten')
        self.ready(
            job, json.dumps([{'id': self.part, 'text': 'One.'}, {'id': 'ffffffff', 'text': 'X'}])
        )
        desk_jobs.settle(self.root, self.ident)
        draft = desk.read(self.root, self.ident)
        self.assertEqual(draft['revision'], 1)
        self.assertEqual(draft['sections'][0]['text'], 'First text.')
        self.assertRegex(self.saved(job)['error'], 'sections this draft does not have')

    def test_a_malformed_first_pass_result_is_refused_readably(self):
        job = desk_jobs.first_pass(self.root, self.ident, 1, 'tighten')
        self.ready(job, 'Here is your draft!')
        desk_jobs.settle(self.root, self.ident)
        self.assertRegex(self.saved(job)['error'], 'list of sections')

    def test_a_first_pass_over_one_result_is_refused_up_front(self):
        made = desk.create(
            self.root,
            {
                'title': 'Long',
                'manuscript': '## A\n\n' + 'word ' * 18_500 + '\n\n## B\n\n' + 'more ' * 18_500,
            },
        )
        with self.assertRaisesRegex(ValueError, 'too long for one first pass'):
            desk_jobs.first_pass(self.root, made['id'], 1, 'tighten')

    def test_a_rewrite_that_adds_a_section_is_refused_readably(self):
        job = desk_jobs.section(self.root, self.ident, 1, self.part, 'Split it.')
        self.ready(job, 'First half.\n\n## A new part\n\nSecond half.')
        desk_jobs.settle(self.root, self.ident)
        self.assertEqual(desk.read(self.root, self.ident)['sections'][0]['text'], 'First text.')
        self.assertRegex(self.saved(job)['error'], 'added a ## section heading')

    def test_gaps_become_the_drafts_gaps_once(self):
        job = desk_jobs.section(self.root, self.ident, 1, self.part, 'Add the date.')
        self.ready(job, 'First text, on a date.', gaps=['The release date.', 'The release date.'])
        desk_jobs.settle(self.root, self.ident)
        self.assertEqual(desk.read(self.root, self.ident)['gaps'], ['The release date.'])

    def test_a_cancelled_job_settles_nothing(self):
        job = desk_jobs.section(self.root, self.ident, 1, self.part, 'Shorter.')
        tool_jobs.control(self.root, job['id'], 'cancel', blog_runner.engine(self.root))
        self.assertEqual(desk_jobs.settle(self.root, self.ident), [])

    def test_a_fake_worker_runs_a_queued_job_end_to_end(self):
        calls = []

        def worker(engine, payload, guidance, **options):
            calls.append(payload)
            return {'content': payload['part']['text'] + ' Added.', 'notes': '', 'gaps': []}

        engine = blog_runner.Engine(self.root, worker=worker)
        desk_jobs.section(self.root, self.ident, 1, self.part, 'Add a sentence.')
        tool_jobs.once(engine)
        self.assertEqual(len(calls), 1)
        # Settled by the worker as soon as it was ready: nothing reads the desk first.
        self.assertEqual(
            desk.read(self.root, self.ident)['sections'][0]['text'], 'First text. Added.'
        )
        self.assertTrue(desk_jobs.jobs(self.root, self.ident)[-1]['settled_at'])

    def test_an_overlong_result_is_refused_readably(self):
        def worker(engine, payload, guidance, **options):
            return {'content': 'x' * 200_001, 'notes': '', 'gaps': []}

        job = desk_jobs.section(self.root, self.ident, 1, self.part, 'Longer.')
        tool_jobs.once(blog_runner.Engine(self.root, worker=worker))
        saved = self.saved(job)
        self.assertEqual(saved['status'], 'failed')
        self.assertRegex(saved['error'], 'longer than 200,000 characters')

    def test_a_result_for_a_blog_driven_elsewhere_is_left_for_that_computer(self):
        from unittest.mock import patch

        job = desk_jobs.section(self.root, self.ident, 1, self.part, 'Shorter.')
        self.ready(job, 'First.')
        with patch('team_workspace.guard', side_effect=ValueError('Another computer drives it.')):
            self.assertEqual(desk_jobs.settle(self.root, self.ident), [])
        self.assertIsNone(self.saved(job).get('settled_at'))
        self.assertEqual(desk_jobs.settle(self.root, self.ident), [job['id']])


class RobustSettleTests(DeskJobCase):
    """What a settle does when something other than the draft goes wrong."""

    ready = SettleTests.ready

    def test_an_unexpected_error_settles_the_job_with_a_readable_problem(self):
        from unittest.mock import patch

        job = desk_jobs.section(self.root, self.ident, 1, self.part, 'More.')
        self.ready(job, 'First text, more.')
        with patch.object(desk_jobs, '_apply', side_effect=OSError('The disk is full.')):
            desk_jobs.settle(self.root, self.ident)
        saved = self.saved(job)
        self.assertTrue(saved['settled_at'])
        self.assertIs(saved['applied'], False)
        self.assertRegex(saved['error'], 'could not be saved: The disk is full')
        self.assertIsNone(desk_jobs.view(self.root, self.ident)['working'])

    def test_a_chain_that_cannot_queue_its_next_step_says_so_and_still_shares(self):
        from unittest.mock import patch

        job = desk_jobs.revise_all(self.root, self.ident, 1, 'Warmer.')
        self.ready(job, 'Warm first.')
        with patch.object(
            desk_jobs,
            '_create',
            side_effect=ValueError('Use smaller selected excerpts for this task.'),
        ):
            self.assertEqual(desk_jobs.ended(self.root, self.saved(job)), self.ident)
        chain = desk_jobs.view(self.root, self.ident)['chain']
        self.assertEqual((chain['revised'], chain['working'], chain['ended']), (1, False, True))
        self.assertRegex(chain['problems'][-1]['error'], 'smaller selected excerpts')

    def test_a_chain_stops_when_another_computer_takes_the_blog(self):
        from unittest.mock import patch

        job = desk_jobs.revise_all(self.root, self.ident, 1, 'Warmer.')
        self.ready(job, 'Warm first.')
        desk_jobs.settle(self.root, self.ident)
        queued = desk_jobs.jobs(self.root, self.ident)[-1]
        self.assertEqual(queued['status'], 'queued')
        calls = []
        engine = blog_runner.Engine(self.root, worker=lambda *a, **k: calls.append(1))
        with patch('team_workspace.guard', side_effect=ValueError('Another computer drives it.')):
            tool_jobs.once(engine)
        self.assertEqual(calls, [])
        saved = self.saved(queued)
        self.assertEqual(saved['status'], 'cancelled')
        self.assertRegex(saved['error'], 'Another computer')

    def test_next_checks_who_drives_the_blog(self):
        from unittest.mock import patch

        job = desk_jobs.revise_all(self.root, self.ident, 1, 'Warmer.')
        self.ready(job, 'Warm first.')
        with patch.object(desk_jobs, '_guard', side_effect=[None, ValueError('Taken.')]):
            desk_jobs.settle(self.root, self.ident)
        self.assertEqual(len(desk_jobs.jobs(self.root, self.ident)), 1)
        chain = desk_jobs.view(self.root, self.ident)['chain']
        self.assertTrue(chain['ended'])
        self.assertRegex(chain['problems'][-1]['error'], 'Taken')

    def test_a_long_chain_counts_every_section(self):
        sections = ''.join('## Part %d\n\nText %d.\n\n' % (n, n) for n in range(70))
        made = desk.create(self.root, {'title': 'Long', 'manuscript': sections})

        def worker(engine, payload, guidance, **options):
            return {'content': payload['part']['text'] + ' Warm.', 'notes': '', 'gaps': []}

        engine = blog_runner.Engine(self.root, worker=worker)
        desk_jobs.revise_all(self.root, made['id'], 1, 'Warmer.')
        for _ in range(70):
            tool_jobs.once(engine)
        chain = desk_jobs.view(self.root, made['id'])['chain']
        self.assertEqual((chain['revised'], chain['total'], chain['ended']), (70, 70, True))


class SharedGuidanceTests(unittest.TestCase):
    def test_desk_guidance_is_the_tone_the_house_guide_the_kind_of_post_then_the_length(self):
        style = {'name': 'How-to', 'guide': 'Steps.'}
        text = blog_runner.shared_guidance(style, 'Plain', 'short')
        self.assertEqual(
            text,
            'No author voice is pinned; keep the draft’s own voice. Tone nudge: Plain.\n\n'
            + blog_runner.house_guide()
            + '\n\n'
            + blog_runner.style_rule('How-to', voice=False)
            + '\n\n'
            + blog_runner.LENGTHS['short'],
        )
        self.assertNotIn(blog_runner.LENGTHS['short'], blog_runner.shared_guidance(style))

    def test_a_desk_job_is_never_told_a_selected_voice_wins(self):
        text = blog_runner.shared_guidance({'name': 'How-to', 'guide': 'Steps.'}, 'Plain')
        self.assertNotIn('voice wins', text)
        self.assertNotIn('selected voice', text)
        self.assertIn('the voice wins', blog_runner.style_rule('How-to'))


class ImageJobTests(DeskCase):
    """Jobs see the short image references only, and a result keeps every one of them."""

    def setUp(self):
        super().setUp()
        self.addCleanup(lambda: blog_runner.ENGINES.pop(str(self.root), None))
        source = self.source(
            'A synthetic source.\n\n![][image1]\n\n[image1]: <' + IMAGE_TWO + '>\n'
        )
        self.made = desk.create(
            self.root,
            {'title': 'Sectioned', 'manuscript': SECTIONED, 'style': 'how-to', 'sources': [source]},
        )
        self.ident = self.made['id']
        self.one, self.two = (s['id'] for s in self.made['sections'])

    def let_go(self, job):
        """Take a queued job out of the way, so the next kind can be queued."""
        saved = tool_jobs.read(self.root, job['id'])
        saved.update(status='cancelled')
        tool_jobs.write(self.root, saved)
        return saved

    def test_no_queued_desk_or_finishing_job_carries_image_data(self):
        import article_tools

        guide = article_tools.save_profile(
            self.root,
            {'name': 'Plain', 'guide': 'Plain words.', 'status': 'confirmed', 'confirmed': True},
        )['profile']
        draft = desk.read(self.root, self.ident)
        queued = [
            lambda: desk_jobs.section(self.root, self.ident, 1, self.one, 'Tighten it.'),
            lambda: desk_jobs.section(self.root, self.ident, 1, self.two, ''),
            lambda: desk_jobs.selection(
                self.root, self.ident, 1, self.one, '![A diagram][image1]', 'fix'
            ),
            lambda: desk_jobs.revise_all(self.root, self.ident, 1, 'Shorter.'),
            lambda: desk_jobs.first_pass(self.root, self.ident, 1, 'tighten'),
            lambda: desk_jobs.first_pass(self.root, self.ident, 1, 'reshape'),
            lambda: desk_jobs.draft_job(self.root, self.ident, 1),
            lambda: desk_jobs.outline_job(self.root, self.ident),
        ] + [
            functools.partial(desk_jobs.finish, self.root, self.ident, 1, tool, **extra)
            for tool, extra in (
                ('copyedit', {}),
                ('humanize', {'level': 'light'}),
                ('facts', {}),
                ('headline', {}),
                ('feedback', {}),
                ('voice', {'guide': guide}),
            )
        ]
        kinds = []
        for queue in queued:
            saved = self.let_go(queue())
            kinds.append(saved['kind'])
            self.assertNotIn('data:image', json.dumps(saved['payload']), saved['kind'])
            self.assertNotIn('data:image', saved['guidance'], saved['kind'])
            # The guidance says to keep every reference where it is and to add none.
            self.assertIn('![…][imageN]', saved['guidance'], saved['kind'])
        self.assertEqual(len(set(kinds)), 12)
        self.assertEqual(desk.read(self.root, self.ident)['images'], draft['images'])

    def body(self):
        return (self.folder(self.ident) / 'DRAFT.md').read_text()

    def ready(self, job, content):
        saved = tool_jobs.read(self.root, job['id'])
        saved.update(status='ready', result={'content': content, 'notes': ''}, finished_at='x')
        tool_jobs.write(self.root, saved)
        desk_jobs.settle(self.root, self.ident)
        return tool_jobs.read(self.root, job['id']), desk.read(self.root, self.ident)

    def test_a_rewrite_that_drops_a_reference_has_it_put_back_where_it_was(self):
        job = desk_jobs.section(self.root, self.ident, 1, self.two, 'Shorter.')
        saved, draft = self.ready(job, 'Text two, shorter.')
        self.assertTrue(saved['applied'])
        self.assertEqual(draft['sections'][1]['text'], 'Text two, shorter.\n\n![][image2]')
        self.assertIn('[image2]: <' + IMAGE_TWO + '>', self.body())

    def test_an_altered_or_invented_reference_is_undone(self):
        job = desk_jobs.section(self.root, self.ident, 1, self.one, 'More.')
        _, draft = self.ready(job, '![Changed][image1]\n\nText one, more.\n\n![][image9]')
        self.assertEqual(draft['sections'][0]['text'], '![A diagram][image1]\n\nText one, more.')

    def test_a_selection_that_drops_its_reference_keeps_it(self):
        job = desk_jobs.selection(
            self.root, self.ident, 1, self.one, '![A diagram][image1]\n\nText one.', 'shorten'
        )
        _, draft = self.ready(job, 'Text one, short.')
        self.assertEqual(draft['sections'][0]['text'], '![A diagram][image1]\n\nText one, short.')

    def test_a_first_pass_keeps_the_references_of_every_part(self):
        job = desk_jobs.first_pass(self.root, self.ident, 1, 'tighten')
        _, draft = self.ready(
            job,
            json.dumps(
                [
                    {'id': self.one, 'text': '![A diagram][image1]\n\nOne.'},
                    {'id': self.two, 'text': 'Two.'},
                ]
            ),
        )
        self.assertEqual(
            [s['text'] for s in draft['sections']],
            ['![A diagram][image1]\n\nOne.', 'Two.\n\n![][image2]'],
        )

    def test_reshaping_a_draft_with_no_headings_keeps_its_images_in_the_new_sections(self):
        made = desk.create(self.root, {'manuscript': GOOGLE, 'style': 'how-to'})
        self.ident = made['id']
        job = desk_jobs.first_pass(self.root, self.ident, 1, 'reshape')
        shaped = 'A lead.\n\n## First\n\n![][image1]\n\nMore.\n\n## Second\n\n![][image2]\n\nEnd.'
        saved, draft = self.ready(job, json.dumps([{'id': 'opening', 'text': shaped}]))
        self.assertEqual(saved['error'], '')
        self.assertEqual(
            [s['text'] for s in draft['sections']], ['![][image1]\n\nMore.', '![][image2]\n\nEnd.']
        )
        self.assertEqual(self.body().count('data:image'), 2)

    def test_a_whole_draft_revision_of_an_opening_keeps_its_images(self):
        made = desk.create(self.root, {'manuscript': GOOGLE})
        self.ident = made['id']
        job = desk_jobs.revise_all(self.root, self.ident, 1, 'Shorter.')
        _, draft = self.ready(job, '**A bold lead line**\n\nShorter.\n\n![][image2]\n\nEnd.')
        self.assertEqual(
            draft['opening'],
            '**A bold lead line**\n\nShorter.\n\n![][image1]\n\n![][image2]\n\nEnd.',
        )


if __name__ == '__main__':
    unittest.main()
