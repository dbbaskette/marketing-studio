"""Desk jobs: what each kind sends, one job per blog, and how a result lands."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
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
