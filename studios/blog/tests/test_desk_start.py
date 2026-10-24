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

    def test_the_start_reads_settings_research_for_new_blogs(self):
        # The page ticks Search my sites and Search the web too from what run-options says
        # Settings ticked; an older word reads as it meant, and a damaged value as the default.
        path = self.root / '.blog-run-settings.json'
        for saved, shown in (
            (
                {'documents': True, 'sites': True, 'web': True},
                {'documents': True, 'sites': True, 'web': True},
            ),
            (
                {'documents': True, 'sites': False, 'web': False},
                {'documents': True, 'sites': False, 'web': False},
            ),
            ('web-allowed', {'documents': True, 'sites': False, 'web': True}),
            ('none', {'documents': False, 'sites': False, 'web': False}),
            ({'web': 'yes'}, dict(blog_runner.DEFAULTS['research'])),
        ):
            with self.subTest(saved=saved):
                studio.write_json(path, {'schema': 1, 'defaults': {'research': saved}})
                self.assertEqual(
                    blog_runner.options(self.root)['settings']['defaults']['research'], shown
                )
        # The web ticked from Settings puts research before the outline, as ticking it would.
        made = self.start(way='topic', point='P.', research_from={'sites': [], 'web': True})
        self.assertEqual(desk.read_start(self.root, made['id'])['steps'][0], 'research')

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


OUTLINE_RESULT = {
    'title': 'Suggested title',
    'opening_brief': 'Say why stops cost work.',
    'sections': [
        {'heading': 'Why jobs stop', 'brief': 'The usual causes.'},
        {'heading': 'Retry from a checkpoint', 'brief': 'How the retry keeps work.'},
    ],
}
WRITTEN = """# Ignored title

Jobs stop. Work should not.

## Why jobs stop

Usually a timeout.

## Retry from a checkpoint

The retry resumes.

## A last word

Try it.
"""


class WritingJobCase(StartCase):
    def setUp(self):
        super().setUp()
        self.addCleanup(lambda: blog_runner.ENGINES.pop(str(self.root), None))

    def saved(self, job):
        return tool_jobs.read(self.root, job['id'])

    def finish(self, job, content, **result):
        saved = self.saved(job)
        saved.update(
            status='ready', result={'content': content, 'notes': '', **result}, finished_at='x'
        )
        tool_jobs.write(self.root, saved)
        desk_jobs.ended(self.root, saved)
        return self.saved(job)


class OutlineJobTests(WritingJobCase):
    def test_an_outline_reads_the_brief_the_outline_guide_the_length_and_the_notes_rule(self):
        made = self.start(way='topic', point='Retries save work.', length='deep')
        saved = self.saved(desk_jobs.outline_job(self.root, made['id']))
        self.assertEqual(saved['kind'], 'desk-outline')
        self.assertEqual(saved['payload']['brief']['point'], 'Retries save work.')
        guidance = saved['guidance']
        self.assertIn(desk_jobs._guide('desk-write.md'), guidance)
        self.assertIn(desk_jobs._guide('blog-argument-outline.md'), guidance)
        self.assertIn(blog_runner.LENGTHS['deep'], guidance)
        self.assertIn(blog_runner.WRITING_NOTES, guidance)
        self.assertIn('"opening_brief"', guidance)
        self.assertNotIn('verbatim', guidance)

    def test_notes_are_the_authors_structure_and_shape_is_proposed_from_them(self):
        made = self.start(way='outline', outline='Some notes.\n\nMore notes.\n')
        saved = self.saved(desk_jobs.outline_job(self.root, made['id']))
        self.assertEqual(saved['payload']['notes'], 'Some notes.\n\nMore notes.\n')
        self.assertIn(blog_runner.FROM_OUTLINE, saved['guidance'])
        shaped = self.start(way='shape', outline=OUTLINE, title='Shaped')
        guidance = self.saved(desk_jobs.outline_job(self.root, shaped['id']))['guidance']
        self.assertIn('Shape an outline', guidance)
        self.assertNotIn(blog_runner.FROM_OUTLINE, guidance)

    def test_a_ready_outline_lands_as_sections_with_briefs(self):
        made = self.start(way='topic', point='P.')
        job = desk_jobs.outline_job(self.root, made['id'])
        self.assertTrue(self.finish(job, json.dumps(OUTLINE_RESULT))['applied'])
        draft = desk.read(self.root, made['id'])
        self.assertEqual(draft['title'], 'A synthetic topic')  # The person's own title stays.
        self.assertEqual(draft['opening_brief'], 'Say why stops cost work.')
        self.assertEqual([s['brief'] for s in draft['sections']][1], 'How the retry keeps work.')
        self.assertTrue(all(s['text'] == '' for s in draft['sections']))
        self.assertIn('## Why jobs stop', (self.folder(made['id']) / 'DRAFT.md').read_text())

    def test_a_malformed_outline_is_refused_readably(self):
        for value in ({'sections': []}, {'sections': [{'heading': ' ', 'brief': 'x'}]}, 'Prose'):
            with self.subTest(value=value):
                made = self.start(way='topic', point='P.', title='T ' + str(len(str(value))))
                job = desk_jobs.outline_job(self.root, made['id'])
                content = value if isinstance(value, str) else json.dumps(value)
                saved = self.finish(job, content)
                self.assertFalse(saved['applied'])
                self.assertRegex(saved['error'], 'outline came back')
                self.assertEqual(desk.read(self.root, made['id'])['sections'], [])


class DraftJobTests(WritingJobCase):
    def outlined(self):
        return desk.create(self.root, {'way': 'outline', 'outline': OUTLINE})

    def test_a_draft_reads_the_outline_the_write_guide_and_the_open_gaps(self):
        made = self.outlined()
        saved = self.saved(desk_jobs.draft_job(self.root, made['id'], 1))
        self.assertEqual(saved['kind'], 'desk-draft')
        self.assertEqual(
            saved['payload']['outline'][0],
            {'heading': 'The problem', 'brief': 'Readers lose work when the job stops.'},
        )
        self.assertEqual(saved['payload']['opening_brief'], 'Why this matters.')
        self.assertIn(desk_jobs._guide('blog-write.md'), saved['guidance'])
        self.assertIn(blog_runner.GAPS_OPEN, saved['guidance'])
        self.assertEqual(saved['metadata']['desk']['part'], 'sections')

    def test_a_draft_keeps_the_outline_ids_and_briefs_by_order(self):
        made = self.outlined()
        before = desk.read(self.root, made['id'])['sections']
        job = desk_jobs.draft_job(self.root, made['id'], 1)
        self.assertTrue(self.finish(job, WRITTEN, gaps=['A release date.'])['applied'])
        draft = desk.read(self.root, made['id'])
        self.assertEqual([s['id'] for s in draft['sections']][:2], [s['id'] for s in before])
        self.assertEqual(draft['sections'][0]['heading'], 'Why jobs stop')
        self.assertEqual(draft['sections'][0]['brief'], before[0]['brief'])
        self.assertEqual(draft['sections'][1]['text'], 'The retry resumes.')
        self.assertEqual(draft['sections'][2]['brief'], '')  # An added section is kept.
        self.assertEqual(draft['opening'], 'Jobs stop. Work should not.')
        self.assertEqual(draft['title'], 'A synthetic outline')
        self.assertEqual(draft['gaps'], ['A release date.'])

    def test_a_section_the_draft_left_out_stays_as_it_was(self):
        made = self.outlined()
        job = desk_jobs.draft_job(self.root, made['id'], 1)
        self.finish(job, '## Only one\n\nText.\n')
        draft = desk.read(self.root, made['id'])
        self.assertEqual([s['heading'] for s in draft['sections']], ['Only one', 'The fix'])

    def test_writing_the_draft_again_keeps_each_text_it_replaces(self):
        made = self.outlined()
        part = made['sections'][0]['id']
        desk.save(self.root, made['id'], 1, part, 'My own words.')
        job = desk_jobs.draft_job(self.root, made['id'], 2)
        self.finish(job, WRITTEN)
        kept = desk.versions(self.root, made['id'], part)
        self.assertEqual(kept[0]['text'], 'My own words.')
        self.assertEqual(kept[0]['source'], 'draft')

    def test_a_draft_needs_an_outline(self):
        made = self.start(way='topic', point='P.')
        with self.assertRaisesRegex(ValueError, 'Make the outline first'):
            desk_jobs.draft_job(self.root, made['id'], 1)

    def test_a_draft_without_sections_is_refused_readably(self):
        made = self.outlined()
        saved = self.finish(desk_jobs.draft_job(self.root, made['id'], 1), 'Just prose.')
        self.assertFalse(saved['applied'])
        self.assertRegex(saved['error'], 'without its ## sections')

    def test_writing_a_section_from_its_brief(self):
        made = self.outlined()
        part = made['sections'][1]['id']
        saved = self.saved(desk_jobs.section(self.root, made['id'], 1, part, ''))
        self.assertIn(desk_jobs._guide('desk-write.md'), saved['guidance'])
        self.assertIn('part.brief says what this section must do', saved['guidance'])
        self.assertEqual(saved['payload']['part']['brief'], 'Retry from the last checkpoint.')

    def test_a_run_from_an_outline_keeps_its_own_guidance(self):
        found = blog_runner.create(
            self.root,
            {
                'title': 'A run',
                'goal': 'Explain.',
                'audience': 'Readers',
                'mode': 'from-outline',
                'outline_text': OUTLINE,
                'research': 'none',
            },
            approval='page',
        )
        _, _, guidance = blog_runner.job(self.root, found['id'])
        self.assertIn('\n' + blog_runner.FROM_OUTLINE, guidance)
        self.assertIn('\n' + blog_runner.WRITING_NOTES, guidance)
        self.assertIn('\n' + blog_runner.GAPS_OPEN, guidance)


class ChainCase(RouteCase):
    """A start runs on its own, step after step, through the single tool worker."""

    def setUp(self):
        super().setUp()
        self.calls = []
        self.failing = {}

    def worker(self, engine, payload, guidance, **options):
        kind = (
            'outline'
            if '"opening_brief"' in guidance and 'outline' not in payload
            else 'draft'
            if 'outline' in payload
            else 'plan'
            if 'research questions' in guidance
            else 'research'
        )
        self.calls.append({'kind': kind, 'payload': payload, 'web': options.get('web')})
        if kind in self.failing:
            raise self.failing.pop(kind)
        if kind == 'outline':
            return {'content': json.dumps(OUTLINE_RESULT), 'notes': '', 'evidence': [], 'gaps': []}
        if kind == 'draft':
            return {'content': WRITTEN, 'notes': '', 'evidence': [], 'gaps': []}
        if kind == 'plan':
            return {'content': '1. What stops jobs?', 'notes': ''}
        return {'content': '# Findings\n\nTimeouts stop most jobs.', 'notes': ''}

    def run_jobs(self, count):
        engine = blog_runner.Engine(self.root, worker=self.worker)
        for _ in range(count):
            tool_jobs.once(engine)

    def begin(self, **extra):
        return self.post(
            'desk-create',
            {
                'operation': 'd' * 32,
                'title': 'A synthetic topic',
                'way': 'topic',
                'point': 'Retries save work.',
                **extra,
            },
        )


class ChainTests(ChainCase):
    def test_a_topic_start_outlines_then_drafts_with_no_stops(self):
        made = self.begin()
        self.assertEqual(made['start']['step'], 'outline')
        self.assertEqual(made['working']['kind'], 'desk-outline')
        self.assertEqual(made['start']['doing'], 'Outlining')
        self.run_jobs(1)
        middle = self.get('desk', id=made['id'])
        self.assertEqual(middle['start']['step'], 'draft')
        self.assertEqual(middle['working']['kind'], 'desk-draft')
        self.run_jobs(1)
        done = self.get('desk', id=made['id'])
        self.assertIsNotNone(done['start']['ended_at'])
        self.assertIsNone(done['working'])
        self.assertEqual(done['sections'][1]['text'], 'The retry resumes.')
        self.assertEqual([call['kind'] for call in self.calls], ['outline', 'draft'])
        self.assertNotIn('notes', done['start'])

    def test_with_the_web_ticked_research_comes_first_and_the_outline_reads_it(self):
        made = self.begin(research_from={'sites': [], 'web': True})
        self.assertEqual(made['working']['kind'], 'desk-research')
        self.run_jobs(3)
        self.assertEqual(
            [(call['kind'], call['web']) for call in self.calls],
            [('plan', False), ('research', True), ('outline', False), ('draft', False)],
        )
        self.assertEqual(
            self.calls[1]['payload']['documents']['research-plan'], '1. What stops jobs?'
        )
        self.assertIn('Timeouts stop most jobs.', self.calls[2]['payload']['research'])
        report = self.folder(made['id']) / 'derived' / 'blog-research.md'
        self.assertIn('Timeouts', report.read_text())

    def test_reviewed_research_is_published_in_the_blog_and_read_as_a_bundle(self):
        from unittest.mock import patch

        import synthesis_fixture
        import synthesis_research
        from studio_core import research_contract

        def generate(directory, run, payload, worker, **options):
            self.assertEqual(run['research_contract'], {'schema': 2})
            synthesis_fixture.published_bundle(directory / research_contract.CASE / 'research')
            return {'content': '# Report\n', 'notes': 'Checked.'}

        with patch.object(research_contract, 'snapshot', return_value={'schema': 2}):
            made = self.begin(research_from={'sites': ['https://docs.example.com'], 'web': False})
        with patch.object(synthesis_research, 'generate', side_effect=generate):
            self.run_jobs(2)
        self.assertTrue((self.folder(made['id']) / 'research' / 'output.json').is_file())
        outline = [call for call in self.calls if call['kind'] == 'outline'][0]
        self.assertEqual(outline['payload']['research_bundle']['digest'], 'synthetic-digest')

    def test_a_failed_research_stops_the_start_readably_and_retry_runs_it_again(self):
        self.failing['research'] = ValueError('The assistant stopped.')
        made = self.begin(research_from={'sites': [], 'web': True})
        first = made['working']['id']
        self.run_jobs(1)
        stopped = self.get('desk', id=made['id'])
        self.assertEqual(stopped['start']['problem'], 'The assistant stopped.')
        self.assertEqual(stopped['start']['step'], 'research')
        self.assertIsNone(stopped['working'])
        again = self.post('desk-retry', {'id': made['id']})
        self.assertEqual(again['start']['problem'], '')
        self.assertEqual(again['working']['kind'], 'desk-research')
        self.assertNotEqual(again['working']['id'], first)
        with self.assertRaisesRegex(ValueError, 'Nothing to retry'):
            self.post('desk-retry', {'id': made['id']})

    def test_stop_ends_the_start_with_a_retry(self):
        made = self.begin()
        stopped = self.post('desk-stop', {'id': made['id'], 'job': made['working']['id']})
        self.assertRegex(stopped['start']['problem'], '^Stopped')
        self.assertIsNone(stopped['working'])
        self.assertEqual(
            self.post('desk-retry', {'id': made['id']})['working']['kind'], 'desk-outline'
        )

    def test_documents_only_go_straight_into_the_outline(self):
        fact = self.source('A synthetic fact.')
        made = self.begin(sources=[fact])
        self.assertEqual(made['start']['steps'], ['outline', 'draft'])
        self.run_jobs(1)
        self.assertEqual(self.calls[0]['payload']['sources'][0]['text'], 'A synthetic fact.')

    def test_shape_ends_on_the_outline(self):
        made = self.begin(way='shape', outline=OUTLINE, point='')
        self.run_jobs(1)
        done = self.get('desk', id=made['id'])
        self.assertIsNotNone(done['start']['ended_at'])
        self.assertEqual(done['start']['open'], 'outline')
        self.assertEqual(len(done['sections']), 2)
        self.assertTrue(all(not s['text'] for s in done['sections']))

    def test_a_step_interrupted_by_closing_blog_studio_can_be_retried(self):
        made = self.begin()
        tool_jobs.recover(self.root)  # As at the next launch: a working job is interrupted.
        job = tool_jobs.read(self.root, made['working']['id'])
        job['status'] = 'working'
        tool_jobs.write(self.root, job)
        tool_jobs.recover(self.root)
        shown = self.get('desk', id=made['id'])
        self.assertRegex(shown['start']['problem'], 'interrupted')
        listed = blog_runner.catalog(self.root)['items'][0]
        self.assertEqual(listed['status'], 'failed')
        self.assertRegex(listed['error'], 'interrupted')
        self.assertEqual(
            self.post('desk-retry', {'id': made['id']})['working']['kind'], 'desk-outline'
        )

    def test_a_retry_needs_a_stopped_start(self):
        made = self.begin()
        with self.assertRaisesRegex(ValueError, 'Nothing to retry'):
            self.post('desk-retry', {'id': made['id']})


class OutlineTabTests(RouteCase):
    def setUp(self):
        super().setUp()
        made = self.post(
            'desk-create', {'operation': 'e' * 32, 'title': 'Synthetic', 'manuscript': WRITTEN}
        )
        self.ident = made['id']
        self.ids = [s['id'] for s in made['sections']]

    def rows(self, view=None):
        view = view or self.get('desk', id=self.ident)
        return [
            {'id': s['id'], 'heading': s['heading'], 'brief': s['brief']} for s in view['sections']
        ]

    def save(self, rows, seen=None):
        seen = seen or self.get('desk', id=self.ident)['revision']
        return self.post('desk-outline-save', {'id': self.ident, 'seen': seen, 'sections': rows})

    def test_reordering_keeps_ids_and_text(self):
        rows = self.rows()
        saved = self.save([rows[2], rows[0], rows[1]])
        self.assertEqual(
            [s['id'] for s in saved['sections']], [self.ids[2], self.ids[0], self.ids[1]]
        )
        self.assertEqual(saved['sections'][1]['text'], 'Usually a timeout.')
        self.assertIn('## A last word\n\nTry it.\n\n## Why jobs stop', saved['markdown'])

    def test_rename_and_brief_save_and_an_outdated_form_is_refused(self):
        rows = self.rows()
        rows[0] = {**rows[0], 'heading': 'Why work is lost', 'brief': 'The causes.'}
        saved = self.save(rows, seen=1)
        self.assertEqual(saved['sections'][0]['heading'], 'Why work is lost')
        self.assertEqual(saved['sections'][0]['brief'], 'The causes.')
        rows[0] = {**rows[0], 'heading': 'Stale rename'}
        with self.assertRaisesRegex(ValueError, 'changed since'):
            self.save(rows, seen=1)

    def test_typing_in_one_section_does_not_refuse_renaming_another(self):
        self.post('desk-save', {'id': self.ident, 'seen': 1, 'part': self.ids[0], 'text': 'Typed.'})
        rows = self.rows()
        rows[1] = {**rows[1], 'heading': 'Renamed'}
        self.assertEqual(self.save(rows, seen=1)['sections'][1]['heading'], 'Renamed')

    def test_adding_and_removing_sections(self):
        rows = self.rows()
        saved = self.save([rows[0], {'heading': 'A new part', 'brief': 'Say more.'}, rows[2]])
        self.assertEqual(len(saved['sections']), 3)
        added = saved['sections'][1]
        self.assertRegex(added['id'], '^[a-f0-9]{8}$')
        self.assertNotIn(added['id'], self.ids)
        self.assertEqual(added['text'], '')
        self.assertNotIn('The retry resumes.', saved['markdown'])

    def test_a_heading_is_one_line_without_marks_and_ids_are_known(self):
        rows = self.rows()
        for row, said in (
            ({**rows[0], 'heading': ''}, 'heading of one line'),
            ({**rows[0], 'heading': 'Two\nlines'}, 'heading of one line'),
            ({**rows[0], 'heading': '## Marked'}, 'Leave out the #'),
            ({**rows[0], 'id': 'ffffffff'}, 'does not have'),
        ):
            with self.subTest(row=row), self.assertRaisesRegex(ValueError, said):
                self.save([row, *rows[1:]])

    def test_the_outline_cannot_change_while_the_draft_is_written(self):
        written = self.post('desk-draft', {'id': self.ident, 'seen': 1})
        self.assertEqual(written['working']['kind'], 'desk-draft')
        rows = self.rows(written)
        rows[0] = {**rows[0], 'brief': 'Later.'}
        with self.assertRaisesRegex(ValueError, 'being written'):
            self.save(rows)

    def test_write_this_section_starts_from_its_brief(self):
        rows = self.rows()
        rows[1] = {**rows[1], 'brief': 'Explain the checkpoint.'}
        saved = self.save(rows, seen=1)
        job = self.post(
            'desk-note',
            {'id': self.ident, 'seen': saved['revision'], 'part': self.ids[1], 'note': ''},
        )['working']
        payload = tool_jobs.read(self.root, job['id'])['payload']
        self.assertEqual(payload['part']['brief'], 'Explain the checkpoint.')

    def test_a_source_added_on_the_desk_is_read_by_later_rewrites(self):
        fact = self.source('A new synthetic fact.')
        added = self.post('desk-sources', {'id': self.ident, 'sources': [fact]})
        self.assertEqual([entry['source_id'] for entry in added['sources']], [fact])
        self.assertEqual(added['source_names'][0]['name'], 'Synthetic source')
        record = studio.read_json(self.folder(self.ident) / 'session.json')
        self.assertIn(fact, [entry['source_id'] for entry in record['sources']])
        job = self.post(
            'desk-note',
            {'id': self.ident, 'seen': added['revision'], 'part': self.ids[0], 'note': 'Use it.'},
        )['working']
        payload = tool_jobs.read(self.root, job['id'])['payload']
        self.assertEqual(payload['sources'][0]['text'], 'A new synthetic fact.')

    def test_adding_nothing_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'Choose a source to add'):
            self.post('desk-sources', {'id': self.ident, 'sources': []})


if __name__ == '__main__':
    unittest.main()


class ReviewFixTests(ChainCase):
    """The Phase 2 review: estimates, the opening, reordered drafts, removed sections, angle
    clean-up and research."""

    def test_an_estimate_uses_recent_step_times_and_says_when_a_step_overruns(self):
        import datetime

        self.begin(operation='e' * 32)
        self.run_jobs(2)
        times = studio.read_json(studio.inside(self.root, '.blog-runs', 'desk-step-times.json'))
        self.assertEqual(len(times['outline']), 1)
        self.assertEqual(len(times['draft:style']), 1)
        studio.write_json(
            studio.inside(self.root, '.blog-runs', 'desk-step-times.json'),
            {'outline': [120, 180, 240], 'draft:style': [600]},
        )
        made = self.begin()
        self.assertEqual(made['start']['minutes_left'], 13)  # 3 for the outline, 10 to draft.
        self.assertFalse(made['start']['over'])
        job = tool_jobs.read(self.root, made['working']['id'])
        long_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=9)
        job.update(status='working', started_at=long_ago.isoformat())
        tool_jobs.write(self.root, job)
        shown = self.get('desk', id=made['id'])
        self.assertTrue(shown['start']['over'])
        self.assertEqual(shown['start']['minutes_left'], 10)

    def test_typing_the_opening_while_the_draft_is_written_keeps_both(self):
        made = self.post(
            'desk-create', {'operation': 'f' * 32, 'title': 'T', 'manuscript': REORDER_DOC}
        )
        queued = self.post('desk-draft', {'id': made['id'], 'seen': 1})
        self.post(
            'desk-save',
            {'id': made['id'], 'seen': queued['revision'], 'part': 'opening', 'text': 'Typed.'},
        )

        def worker(engine, payload, guidance, **options):
            return {'content': 'Op.\n\n## A\n\nNew A.\n\n## B\n\nNew B.', 'notes': ''}

        tool_jobs.once(blog_runner.Engine(self.root, worker=worker))
        shown = self.get('desk', id=made['id'])
        self.assertEqual([s['text'] for s in shown['sections']], ['New A.', 'New B.'])
        self.assertEqual(shown['opening'], 'Typed.')
        self.assertTrue(shown['jobs'][-1]['applied'])

    def test_a_draft_in_another_order_keeps_each_sections_id_and_brief(self):
        made = self.post(
            'desk-create', {'operation': 'f' * 32, 'title': 'T', 'manuscript': REORDER_DOC}
        )
        ids = [s['id'] for s in made['sections']]
        self.post(
            'desk-outline-save',
            {
                'id': made['id'],
                'seen': 1,
                'sections': [
                    {'id': ids[0], 'heading': 'A', 'brief': 'About A'},
                    {'id': ids[1], 'heading': 'B', 'brief': 'About B'},
                ],
            },
        )
        self.post('desk-draft', {'id': made['id'], 'seen': 2})

        def worker(engine, payload, guidance, **options):
            return {'content': 'Op.\n\n## b\n\nNew B.\n\n## A.\n\nNew A.', 'notes': ''}

        tool_jobs.once(blog_runner.Engine(self.root, worker=worker))
        shown = self.get('desk', id=made['id'])
        self.assertEqual(
            [(s['id'], s['heading'], s['brief'], s['text']) for s in shown['sections']],
            [(ids[1], 'b', 'About B', 'New B.'), (ids[0], 'A.', 'About A', 'New A.')],
        )
        self.assertEqual(desk.versions(self.root, made['id'], ids[1])[0]['text'], 'Beta.')

    def test_a_removed_section_can_be_brought_back_with_its_history(self):
        made = self.post(
            'desk-create', {'operation': 'f' * 32, 'title': 'T', 'manuscript': REORDER_DOC}
        )
        ids = [s['id'] for s in made['sections']]
        self.post('desk-save', {'id': made['id'], 'seen': 1, 'part': ids[1], 'text': 'Beta 2.'})
        removed = self.post(
            'desk-outline-save',
            {
                'id': made['id'],
                'seen': 2,
                'sections': [{'id': ids[0], 'heading': 'A', 'brief': ''}],
            },
        )
        self.assertEqual([s['id'] for s in removed['sections']], [ids[0]])
        self.assertEqual(removed['removed'][0]['heading'], 'B')
        self.assertEqual(removed['removed'][0]['words'], 2)
        back = self.post(
            'desk-unremove', {'id': made['id'], 'seen': removed['revision'], 'index': 0}
        )
        self.assertEqual([s['id'] for s in back['sections']], ids)
        self.assertEqual(back['sections'][1]['text'], 'Beta 2.')
        self.assertEqual(back['removed'], [])
        self.assertEqual(back['versions'][ids[1]], 1)  # Its History came back with it.

    def test_angles_are_cleared_once_the_start_is_made_or_left_a_day(self):
        import os
        import time

        asked = self.post('desk-angles', {'operation': '1' * 32, 'point': 'P.'})
        older = self.post('desk-angles', {'operation': '2' * 32, 'point': 'Q.'})
        stale = studio.inside(self.root, '.blog-runs', 'desk-angles', '2' * 32 + '.json')
        tool_jobs.control(self.root, older['job'], 'cancel', blog_runner.engine(self.root))
        day_ago = time.time() - 2 * 86400
        os.utime(stale, (day_ago, day_ago))
        self.begin(angles='1' * 32)
        self.assertFalse(
            studio.inside(self.root, '.blog-runs', 'desk-angles', '1' * 32 + '.json').exists()
        )
        with self.assertRaises(ValueError):
            tool_jobs.read(self.root, asked['job'])
        self.assertFalse(stale.exists())
        with self.assertRaises(ValueError):
            tool_jobs.read(self.root, older['job'])
        replaced = self.post('desk-angles', {'operation': '3' * 32, 'point': 'R.'})
        self.post('desk-angles', {'operation': '4' * 32, 'point': 'S.', 'replaces': '3' * 32})
        with self.assertRaises(ValueError):
            tool_jobs.read(self.root, replaced['job'])

    def test_angle_jobs_stay_out_of_the_tools_list(self):
        self.post('desk-angles', {'operation': '5' * 32, 'point': 'P.'})
        self.assertEqual(tool_jobs.listing(self.root), [])

    def test_research_saves_its_plan_and_shares_one_time_limit(self):
        import time

        limits = []

        def worker(engine, payload, guidance, **options):
            limits.append(options['seconds'])
            if 'research questions' in guidance:
                time.sleep(1.2)
                return {'content': '1. What stops jobs?', 'notes': ''}
            return {'content': '# Findings\n\nTimeouts.', 'notes': ''}

        made = self.begin(research_from={'sites': [], 'web': True})
        tool_jobs.once(blog_runner.Engine(self.root, worker=worker))
        plan = self.folder(made['id']) / 'derived' / 'blog-research-plan.md'
        self.assertEqual(plan.read_text(), '1. What stops jobs?')
        self.assertGreaterEqual(limits[0], 598)
        self.assertLess(limits[1], limits[0])

    def test_research_writes_into_the_blog_only_when_it_settles(self):
        # A start's research takes minutes: the blog's folder stays as it was meanwhile, so a
        # team workspace has nothing outside a recorded decision. The plan and the findings
        # land together when the job settles.
        during = []

        def worker(engine, payload, guidance, **options):
            if 'research questions' in guidance:
                return {'content': '1. What stops jobs?', 'notes': ''}
            folder = self.folder(made['id']) / 'derived'
            during.append(sorted(path.name for path in folder.glob('*')) if folder.exists() else [])
            return {'content': '# Findings\n\nTimeouts.', 'notes': ''}

        made = self.begin(research_from={'sites': [], 'web': True})
        tool_jobs.once(blog_runner.Engine(self.root, worker=worker))
        self.assertEqual(during, [[]])
        derived = self.folder(made['id']) / 'derived'
        self.assertEqual((derived / 'blog-research-plan.md').read_text(), '1. What stops jobs?')
        self.assertIn('Timeouts', (derived / 'blog-research.md').read_text())
        self.assertFalse(studio.inside(self.root, '.blog-runs', 'desk-starts', made['id']).exists())

    def test_reviewed_research_is_staged_until_it_settles(self):
        from unittest.mock import patch

        import synthesis_fixture
        import synthesis_research
        from studio_core import research_contract

        seen = {}

        def generate(directory, run, payload, worker, **options):
            synthesis_fixture.published_bundle(directory / research_contract.CASE / 'research')
            seen['research'] = (self.folder(made['id']) / 'research').exists()
            seen['plan'] = (self.folder(made['id']) / 'derived' / 'blog-research-plan.md').exists()
            return {'content': '# Report\n', 'notes': ''}

        with patch.object(research_contract, 'snapshot', return_value={'schema': 2}):
            made = self.begin(research_from={'sites': [], 'web': True})
        with patch.object(synthesis_research, 'generate', side_effect=generate):
            self.run_jobs(1)
        self.assertEqual(seen, {'research': False, 'plan': False})
        self.assertTrue((self.folder(made['id']) / 'research' / 'output.json').is_file())
        self.assertTrue((self.folder(made['id']) / research_contract.CASE).is_dir())
        self.assertTrue((self.folder(made['id']) / 'derived' / 'blog-research-plan.md').is_file())
        self.assertFalse(studio.inside(self.root, '.blog-runs', 'desk-starts', made['id']).exists())

    def test_an_overlong_research_report_is_refused_readably(self):
        def worker(engine, payload, guidance, **options):
            if 'research questions' in guidance:
                return {'content': 'Plan.', 'notes': ''}
            return {'content': 'x' * 200_001, 'notes': ''}

        made = self.begin(research_from={'sites': [], 'web': True})
        tool_jobs.once(blog_runner.Engine(self.root, worker=worker))
        shown = self.get('desk', id=made['id'])
        self.assertRegex(shown['start']['problem'], 'research report came back longer')
        self.assertFalse((self.folder(made['id']) / 'derived' / 'blog-research.md').exists())

    def test_the_outline_and_draft_are_told_to_read_the_reviewed_research(self):
        from unittest.mock import patch

        import synthesis_fixture
        import synthesis_research
        from studio_core import research_contract

        def generate(directory, run, payload, worker, **options):
            synthesis_fixture.published_bundle(directory / research_contract.CASE / 'research')
            return {'content': '# Report\n', 'notes': ''}

        with patch.object(research_contract, 'snapshot', return_value={'schema': 2}):
            made = self.begin(research_from={'sites': [], 'web': True})
        with patch.object(synthesis_research, 'generate', side_effect=generate):
            self.run_jobs(1)
        job = tool_jobs.read(self.root, self.get('desk', id=made['id'])['working']['id'])
        self.assertIn('research_bundle', job['guidance'])
        self.assertIn(research_contract.HANDOFF, job['guidance'])


REORDER_DOC = '# T\n\nOpening.\n\n## A\n\nAlpha.\n\n## B\n\nBeta.\n'


class SourcesStayWithTheBlogTests(RouteCase):
    PAGE = b'<html><head><title>Synthetic gateway guide</title></head><body><h1>Guide</h1><p>The gateway keeps one retry budget per route.</p></body></html>'

    def add_link(self, url='https://docs.example.com/guide', keep=False):
        from unittest.mock import patch

        import blog_library

        with patch.object(
            blog_library, 'fetch', return_value=(self.PAGE, url, 'text/html')
        ) as fetched:
            found = self.post(
                'upload',
                {
                    'operation': desk_jobs.secrets.token_hex(16),
                    'files': [{'link': url, 'purpose': 'material'}],
                    'purpose': 'material',
                    'keep': keep,
                    'analyze': False,
                },
            )
        self.assertEqual(fetched.call_args.args[1].site, 'example.com')
        return found['files'][0]

    def library(self):
        import library_add

        return [row['id'] for row in library_add.matching(self.root)['items']]

    def test_a_link_is_read_and_kept_with_the_blog_unless_ticked(self):
        row = self.add_link()
        self.assertEqual(row['state'], 'ready')
        self.assertEqual(row['link'], 'https://docs.example.com/guide')
        self.assertEqual(row['filename'], 'Synthetic gateway guide')
        self.assertNotIn(row['source']['id'], self.library())
        made = self.post(
            'desk-create',
            {
                'operation': 'a' * 32,
                'title': 'T',
                'way': 'topic',
                'point': 'P.',
                'sources': [row['source']['id']],
            },
        )
        job = tool_jobs.read(self.root, made['working']['id'])
        self.assertIn('one retry budget per route', job['payload']['sources'][0]['text'])
        self.assertNotIn(row['source']['id'], self.library())

    def test_a_ticked_link_reaches_the_library_only_when_kept_on_start(self):
        row = self.add_link()
        kept = self.post('source-keep', {'id': row['source']['id'], 'keep': True})
        self.assertTrue(kept['kept'])
        self.assertIn(row['source']['id'], self.library())
        _, record = studio.item(self.root, 'sources', row['source']['id'])
        self.assertEqual(record['library']['origin_kind'], 'link')

    def test_a_link_must_be_a_public_https_page(self):
        with self.assertRaisesRegex(ValueError, 'https'):
            self.post(
                'upload',
                {
                    'operation': 'c' * 32,
                    'files': [{'link': 'http://docs.example.com/guide'}],
                    'purpose': 'material',
                    'keep': False,
                    'analyze': False,
                },
            )


class SecondReviewTests(SourcesStayWithTheBlogTests):
    """The re-review: angles ids, keeping on a successful create, and reading one link."""

    test_a_link_is_read_and_kept_with_the_blog_unless_ticked = None
    test_a_ticked_link_reaches_the_library_only_when_kept_on_start = None
    test_a_link_must_be_a_public_https_page = None

    def create(self, operation='a' * 32, **extra):
        return self.post(
            'desk-create',
            {'operation': operation, 'title': 'T', 'way': 'topic', 'point': 'P.', **extra},
        )

    def blogs(self):
        return sorted(studio.inside(self.root, 'articles').glob('*/session.json'))

    def test_a_bad_angles_id_is_refused_before_the_blog_is_made(self):
        with self.assertRaisesRegex(ValueError, 'Angles need their page operation ID'):
            self.create(angles='not-an-id')
        self.assertEqual(self.blogs(), [])

    def test_letting_angles_go_never_fails_a_made_blog(self):
        from unittest.mock import patch

        with patch.object(desk_jobs, 'forget_angles', side_effect=OSError('disk')):
            made = self.create(angles='1' * 32)
        self.assertTrue(made['id'])
        with patch.object(desk_jobs, 'prune_angles', side_effect=OSError('disk')):
            self.assertTrue(self.create(operation='b' * 32)['id'])

    def test_a_ticked_source_is_kept_only_once_the_blog_is_made(self):
        row = self.add_link()
        ident = row['source']['id']
        with self.assertRaisesRegex(ValueError, 'Say the point'):
            self.create(point='', sources=[ident], keep=[ident])
        self.assertNotIn(ident, self.library())
        made = self.create(sources=[ident], keep=[ident])
        self.assertIn(ident, self.library())
        record = studio.read_json(self.folder(made['id']) / 'session.json')
        self.assertEqual(record['material'], [])
        self.assertIn('reference', record['sources'][0]['purposes'])
        self.assertNotIn('material', record['sources'][0]['purposes'])
        # The same request again returns the same blog and keeps nothing twice.
        self.assertEqual(self.create(sources=[ident], keep=[ident])['id'], made['id'])
        job = tool_jobs.read(self.root, made['working']['id'])
        self.assertIn('retry budget', job['payload']['sources'][0]['text'])

    def test_keep_names_only_sources_of_this_request(self):
        row = self.add_link()
        with self.assertRaisesRegex(ValueError, 'Keep only sources you are adding'):
            self.create(keep=[row['source']['id']])

    def test_a_source_added_on_the_desk_is_kept_when_ticked(self):
        made = self.create()
        row = self.add_link()
        added = self.post(
            'desk-sources',
            {'id': made['id'], 'sources': [row['source']['id']], 'keep': [row['source']['id']]},
        )
        self.assertIn(row['source']['id'], self.library())
        self.assertEqual(added['sources'][0]['source_id'], row['source']['id'])

    def read_link(self, link, fetched=None):
        from unittest.mock import patch

        import blog_library

        with patch.object(
            blog_library,
            'fetch',
            side_effect=fetched or (lambda *a, **k: (self.PAGE, link, 'text/html')),
        ):
            return self.post(
                'upload',
                {
                    'operation': desk_jobs.secrets.token_hex(16),
                    'files': [{'link': link, 'purpose': 'material'}],
                    'purpose': 'material',
                    'keep': False,
                    'analyze': False,
                },
            )

    def test_a_refused_link_speaks_of_a_link(self):
        import blog_library

        for said, words in (
            (blog_library.CREDENTIALS, 'Use a public https link without a password or port.'),
            (blog_library.PRIVATE, 'That link points to a private address, so it cannot be read.'),
        ):

            def fetched(*args, said=said, **options):
                raise ValueError(said)

            with self.subTest(said=said), self.assertRaisesRegex(ValueError, '^' + words + '$'):
                self.read_link('https://docs.example.com/guide', fetched)

    def test_a_redirect_may_stay_on_the_site_and_no_further(self):
        import management

        scope = management.LinkScope('https://example.com/guide')
        self.assertIsNone(scope.refuse('https://www.example.com/guide'))
        self.assertRegex(scope.refuse('https://elsewhere.test/page'), 'elsewhere.test')
        british = management.LinkScope('https://www.example.co.uk/a')
        self.assertIsNone(british.refuse('https://shop.example.co.uk/b'))
        self.assertTrue(british.refuse('https://other.co.uk/b'))

    def test_the_page_title_loses_its_markup(self):
        self.PAGE = b'<html><head><title>A <b>bold</b> &amp; plain title</title></head><body><p>Text here.</p></body></html>'
        row = self.read_link('https://docs.example.com/guide')['files'][0]
        self.assertEqual(row['filename'], 'A bold & plain title')

    def test_a_link_is_read_before_the_studio_lock_is_taken(self):
        held = studio._HELD.set(False)
        self.addCleanup(studio._HELD.reset, held)
        seen = []

        def fetched(*args, **options):
            seen.append(studio.lock_held())
            return self.PAGE, 'https://docs.example.com/guide', 'text/html'

        self.read_link('https://docs.example.com/guide', fetched)
        self.assertEqual(seen, [False])
