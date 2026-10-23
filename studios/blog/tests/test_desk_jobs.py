"""Desk jobs: what each kind sends, one job per blog, and how a result lands."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import json
import unittest

import blog_runner
import desk
import desk_jobs
import tool_jobs
from test_desk import DRAFT, DeskCase


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
        self.assertIn(blog_runner.style_rule('How-to and tutorial'), saved['guidance'])
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
    def test_a_whole_draft_note_sends_every_section_and_the_note(self):
        job = desk_jobs.revise_all(self.root, self.ident, 1, 'Tighten throughout.')
        saved = self.saved(job)
        self.assertEqual(saved['kind'], 'desk-revise-all')
        self.assertEqual(
            [s['text'] for s in saved['payload']['sections']], ['First text.', 'Second text.']
        )
        self.assertEqual(saved['payload']['opening'], 'An opening paragraph.')
        self.assertEqual(saved['payload']['note'], 'Tighten throughout.')
        self.assertIn('ids unchanged', saved['guidance'])
        self.assertIn('verbatim', saved['guidance'])
        self.assertIn('"""\nTighten throughout.\n"""', saved['guidance'])

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
        self.assertIn(manuscript_editor.CHECKS['copyedit'], saved['guidance'])
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

    def test_a_draft_without_sections_has_no_first_pass(self):
        made = desk.create(self.root, {'title': 'Flat', 'manuscript': 'Just prose.'})
        with self.assertRaisesRegex(ValueError, 'section by section'):
            desk_jobs.first_pass(self.root, made['id'], 1, 'tighten')


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

    def test_a_selection_whose_passage_now_occurs_twice_is_not_applied(self):
        job = desk_jobs.selection(self.root, self.ident, 1, self.part, 'First', 'fix')
        desk.save(self.root, self.ident, 1, self.part, 'First text. First again.')
        self.ready(job, 'Primary')
        desk_jobs.settle(self.root, self.ident)
        self.assertEqual(
            desk.read(self.root, self.ident)['sections'][0]['text'], 'First text. First again.'
        )
        self.assertIs(self.saved(job)['applied'], False)

    def test_a_whole_draft_revision_lands_in_one_revision_with_a_version_each(self):
        job = desk_jobs.revise_all(self.root, self.ident, 1, 'Tighten.')
        ids = [s['id'] for s in self.made['sections']]
        self.ready(
            job,
            '```json\n'
            + json.dumps([{'id': ids[0], 'text': 'One.'}, {'id': ids[1], 'text': 'Second text.'}])
            + '\n```',
        )
        desk_jobs.settle(self.root, self.ident)
        draft = desk.read(self.root, self.ident)
        self.assertEqual([s['text'] for s in draft['sections']], ['One.', 'Second text.'])
        self.assertEqual(draft['revision'], 2)
        self.assertEqual(self.versions(ids[0])[0]['source'], 'revise-all')
        self.assertEqual(self.versions(ids[1]), [])  # Unchanged: no version.

    def test_a_first_pass_keeps_first_pass_versions(self):
        job = desk_jobs.first_pass(self.root, self.ident, 1, 'tighten')
        self.ready(job, json.dumps([{'id': self.part, 'text': 'Tight.'}]))
        desk_jobs.settle(self.root, self.ident)
        self.assertEqual(self.versions()[0]['source'], 'first-pass')

    def test_a_whole_draft_result_with_an_unknown_id_changes_nothing(self):
        job = desk_jobs.revise_all(self.root, self.ident, 1, 'Tighten.')
        self.ready(
            job, json.dumps([{'id': self.part, 'text': 'One.'}, {'id': 'ffffffff', 'text': 'X'}])
        )
        desk_jobs.settle(self.root, self.ident)
        draft = desk.read(self.root, self.ident)
        self.assertEqual(draft['revision'], 1)
        self.assertEqual(draft['sections'][0]['text'], 'First text.')
        self.assertRegex(self.saved(job)['error'], 'sections this draft does not have')

    def test_a_malformed_whole_draft_result_is_refused_readably(self):
        job = desk_jobs.revise_all(self.root, self.ident, 1, 'Tighten.')
        self.ready(job, 'Here is your draft!')
        desk_jobs.settle(self.root, self.ident)
        self.assertRegex(self.saved(job)['error'], 'list of sections')

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
        desk_jobs.settle(self.root, self.ident)
        self.assertEqual(
            desk.read(self.root, self.ident)['sections'][0]['text'], 'First text. Added.'
        )


class SharedGuidanceTests(unittest.TestCase):
    def test_it_is_the_same_text_runs_use(self):
        style = {'name': 'How-to', 'guide': 'Steps.'}
        text = blog_runner.shared_guidance(style, 'Plain', 'short')
        self.assertTrue(text.startswith('No author voice is pinned'))
        self.assertIn('Tone nudge: Plain.', text)
        parts = [blog_runner.house_guide(), blog_runner.style_rule('How-to')]
        parts.append(blog_runner.LENGTHS['short'])
        positions = [text.index(part) for part in parts]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn(blog_runner.LENGTHS['short'], blog_runner.shared_guidance(style))


if __name__ == '__main__':
    unittest.main()
