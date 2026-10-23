"""Desk starts: a blog from a topic, an outline or notes, with angles, research, an outline
and a draft written with no stops, then shaped on the desk."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import json
import unittest

import blog_runner
import desk
import desk_jobs
import studio
import tool_jobs
from test_desk import DeskCase, RouteCase

OUTLINE = """# A synthetic outline

Why this matters.

## The problem

Readers lose work when the job stops.

## The fix

Retry from the last checkpoint.
"""


class OutlineFromTests(unittest.TestCase):
    def test_headings_become_sections_with_their_briefs(self):
        found = desk.outline_from(OUTLINE)
        self.assertEqual(found['title'], 'A synthetic outline')
        self.assertEqual(found['opening_brief'], 'Why this matters.')
        self.assertEqual([s['heading'] for s in found['sections']], ['The problem', 'The fix'])
        self.assertEqual(found['sections'][0]['brief'], 'Readers lose work when the job stops.')
        self.assertTrue(all(s['text'] == '' and len(s['id']) == 8 for s in found['sections']))

    def test_deeper_headings_are_read_at_the_shallowest_level(self):
        found = desk.outline_from('### One\n\n#### Detail\n\nMore.\n\n### Two\n')
        self.assertEqual([s['heading'] for s in found['sections']], ['One', 'Two'])
        self.assertEqual(found['sections'][0]['brief'], '#### Detail\n\nMore.')

    def test_top_level_list_items_become_sections(self):
        found = desk.outline_from('Intro line.\n\n- One:\n  - a detail\n  - another\n- Two\n')
        self.assertEqual([s['heading'] for s in found['sections']], ['One', 'Two'])
        self.assertEqual(found['sections'][0]['brief'], '- a detail\n- another')
        self.assertEqual(found['opening_brief'], 'Intro line.')
        numbered = desk.outline_from('1. First\n2. Second\n   why it matters\n')
        self.assertEqual([s['heading'] for s in numbered['sections']], ['First', 'Second'])
        self.assertEqual(numbered['sections'][1]['brief'], 'why it matters')

    def test_notes_without_structure_are_not_an_outline(self):
        self.assertIsNone(desk.outline_from('Some notes.\n\nMore notes about it.\n'))
        self.assertIsNone(desk.outline_from('## Only one\n\nText.\n'))
        self.assertIsNone(desk.outline_from(''))

    def test_a_heading_in_code_is_not_a_section(self):
        found = desk.outline_from('## One\n\n```\n## not\n```\n\n## Two\n')
        self.assertEqual([s['heading'] for s in found['sections']], ['One', 'Two'])


class StartCase(DeskCase):
    def start(self, **data):
        return desk.create(self.root, {'title': 'A synthetic topic', **data})


class StartRecordTests(StartCase):
    def test_a_topic_start_keeps_its_brief_and_plans_an_outline_then_a_draft(self):
        made = self.start(way='topic', point='Retries save work.', audience='Operators')
        directory = self.folder(made['id'])
        draft = desk.read(self.root, made['id'])
        self.assertEqual(draft['sections'], [])
        self.assertEqual(draft['brief'], {'point': 'Retries save work.', 'audience': 'Operators'})
        self.assertFalse((directory / 'DRAFT.md').exists())
        start = desk.read_start(self.root, made['id'])
        self.assertEqual(start['way'], 'topic')
        self.assertEqual(start['steps'], ['outline', 'draft'])
        self.assertEqual(start['step'], 'outline')
        self.assertEqual(start['open'], 'draft')
        self.assertIsNone(start['ended_at'])
        record = studio.read_json(directory / 'session.json')
        self.assertEqual(record['flow'], 'desk')
        self.assertEqual(record['voice'], {'mode': 'tone', 'tone': ''})

    def test_a_topic_needs_its_point(self):
        with self.assertRaisesRegex(ValueError, 'Say the point to make'):
            self.start(way='topic', point=' ')

    def test_a_topic_takes_no_draft(self):
        with self.assertRaisesRegex(ValueError, 'brings no draft'):
            self.start(way='topic', point='P.', manuscript='# T\n\nText.\n')

    def test_an_unknown_way_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'Choose a topic'):
            self.start(way='poem', point='P.')

    def test_a_parsed_outline_is_the_desk_outline_and_goes_to_the_draft(self):
        made = desk.create(self.root, {'way': 'outline', 'outline': OUTLINE})
        draft = desk.read(self.root, made['id'])
        self.assertEqual(draft['title'], 'A synthetic outline')
        self.assertEqual(
            [s['brief'] for s in draft['sections']][1], 'Retry from the last checkpoint.'
        )
        self.assertEqual(draft['opening_brief'], 'Why this matters.')
        self.assertEqual(desk.read_start(self.root, made['id'])['steps'], ['draft'])

    def test_notes_are_outlined_first(self):
        made = self.start(way='outline', outline='Some notes.\n\nMore notes.\n')
        start = desk.read_start(self.root, made['id'])
        self.assertEqual(start['steps'], ['outline', 'draft'])
        self.assertEqual(start['notes'], 'Some notes.\n\nMore notes.\n')

    def test_shape_outlines_with_the_person_and_opens_the_outline(self):
        made = self.start(way='shape', outline=OUTLINE)
        start = desk.read_start(self.root, made['id'])
        self.assertEqual(start['steps'], ['outline'])
        self.assertEqual(start['open'], 'outline')
        self.assertEqual(desk.read(self.root, made['id'])['sections'], [])

    def test_an_outline_needs_its_text_and_a_title(self):
        with self.assertRaisesRegex(ValueError, 'Paste or upload your outline'):
            self.start(way='outline', outline='')
        with self.assertRaisesRegex(ValueError, 'Give the blog a title'):
            desk.create(self.root, {'way': 'shape', 'outline': 'Notes only.'})

    def test_an_uploaded_outline_is_read_from_its_source(self):
        source = self.source(OUTLINE)
        made = desk.create(self.root, {'way': 'outline', 'outline_source': source})
        self.assertEqual(len(desk.read(self.root, made['id'])['sections']), 2)

    def test_research_from_the_web_comes_first_and_is_kept_on_the_record(self):
        made = self.start(way='topic', point='P.', research_from={'sites': [], 'web': True})
        start = desk.read_start(self.root, made['id'])
        self.assertEqual(start['steps'], ['research', 'outline', 'draft'])
        self.assertEqual(start['research_from'], {'documents': False, 'sites': [], 'web': True})
        record = studio.read_json(self.folder(made['id']) / 'session.json')
        self.assertEqual(record['research_from'], start['research_from'])
        self.assertEqual(record['research_policy'], 'web-allowed')

    def test_no_sites_and_no_web_is_no_research(self):
        made = self.start(way='topic', point='P.', research_from={'sites': [], 'web': False})
        self.assertEqual(desk.read_start(self.root, made['id'])['steps'], ['outline', 'draft'])

    def test_your_sites_alone_need_harness_research(self):
        with self.assertRaisesRegex(ValueError, 'needs Harness Research'):
            self.start(
                way='topic',
                point='P.',
                research_from={'sites': ['https://docs.example.com'], 'web': False},
            )
        self.assertIn('Harness Research', blog_runner.NEEDS_HARNESS_RESEARCH)

    def test_research_is_for_new_writing(self):
        with self.assertRaisesRegex(ValueError, 'Research runs before new writing'):
            desk.create(
                self.root,
                {'manuscript': OUTLINE, 'research_from': {'sites': [], 'web': True}},
            )

    def test_documents_count_when_readable_sources_are_given(self):
        source = self.source('A fact.')
        made = self.start(
            way='topic', point='P.', sources=[source], research_from={'sites': [], 'web': True}
        )
        self.assertTrue(desk.read_start(self.root, made['id'])['research_from']['documents'])
        self.assertEqual(desk.read(self.root, made['id'])['sources'][0]['source_id'], source)


THREE = [
    {'headline': 'Retries that keep work', 'point': 'Retry saves work.', 'audience': 'Operators'},
    {'headline': 'Why jobs stop', 'point': 'Stops are normal.', 'audience': 'Developers'},
    {'headline': 'A checkpoint primer', 'point': 'Checkpoints help.', 'audience': 'Newcomers'},
]


class AnglesTests(RouteCase):
    OPERATION = 'b' * 32

    def ask(self, **extra):
        return self.post(
            'desk-angles',
            {'operation': self.OPERATION, 'title': 'Retries', 'point': 'Keep work.', **extra},
        )

    def job(self, shown):
        return tool_jobs.read(self.root, shown['job'])

    def finish(self, shown, content):
        job = self.job(shown)
        job.update(status='ready', result={'content': content, 'notes': ''}, finished_at='x')
        tool_jobs.write(self.root, job)
        desk_jobs.ended(self.root, job)

    def test_angles_read_the_chosen_sources_and_the_point_before_a_blog_exists(self):
        fact = self.source('A synthetic fact.')
        shown = self.ask(sources=[fact], audience='Operators')
        self.assertEqual(shown['status'], 'queued')
        self.assertTrue(shown['busy'])
        job = self.job(shown)
        self.assertEqual(job['kind'], 'desk-angles')
        self.assertIsNone(job['metadata']['article'])
        self.assertEqual(job['metadata']['desk']['operation'], self.OPERATION)
        self.assertEqual(job['payload']['sources'][0]['text'], 'A synthetic fact.')
        self.assertEqual(job['payload']['brief'], {'point': 'Keep work.', 'audience': 'Operators'})
        self.assertIn('three distinct angles', job['guidance'])
        self.assertIn(blog_runner.house_guide(), job['guidance'])
        self.assertEqual(list(studio.inside(self.root, 'articles').glob('*')), [])

    def test_the_same_request_is_the_same_job_and_a_changed_one_is_refused(self):
        first, again = self.ask(), self.ask()
        self.assertEqual(first['job'], again['job'])
        with self.assertRaisesRegex(ValueError, 'Ask for angles again'):
            self.ask(point='Something else.')

    def test_a_ready_result_is_three_angles_to_pick(self):
        shown = self.ask()
        self.finish(shown, '```json\n' + json.dumps(THREE) + '\n```')
        found = self.get('desk-angles', operation=self.OPERATION)
        self.assertEqual(found['angles'], THREE)
        self.assertFalse(found['busy'])
        self.assertEqual(found['error'], '')

    def test_a_malformed_result_is_refused_readably(self):
        for content in (json.dumps(THREE[:2]), 'Three angles.', json.dumps([*THREE[:2], {}])):
            with self.subTest(content=content):
                shown = self.post(
                    'desk-angles', {'operation': desk_jobs.secrets.token_hex(16), 'point': 'P.'}
                )
                self.finish(shown, content)
                found = self.get('desk-angles', operation=shown['operation'])
                self.assertEqual(found['angles'], [])
                self.assertRegex(found['error'], 'cannot read. Ask again')

    def test_a_fake_worker_suggests_them_end_to_end(self):
        def worker(engine, payload, guidance, **options):
            return {'content': json.dumps(THREE), 'notes': ''}

        self.ask()
        tool_jobs.once(blog_runner.Engine(self.root, worker=worker))
        self.assertEqual(self.get('desk-angles', operation=self.OPERATION)['angles'], THREE)

    def test_an_unknown_operation_is_said(self):
        with self.assertRaisesRegex(ValueError, 'Ask for angles again'):
            self.get('desk-angles', operation='c' * 32)


if __name__ == '__main__':
    unittest.main()
