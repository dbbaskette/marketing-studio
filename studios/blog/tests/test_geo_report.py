"""A GEO report for a published post: read from a local fake site on 127.0.0.1, one job with a
fake result (no provider runs), the report, its downloads, Edit this post on the desk, Run
again, and its new Google Doc with suggestions against the fake Google model only."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import json
from unittest.mock import patch

import desk
import desk_finish
import geo_report
import studio
import tool_jobs
from fake_site import Site
from test_desk import RouteCase
from test_published_post import page

URL = 'https://blog.example.com/posts/retry-budgets'
OPENING = (
    'A retry budget caps the retries each route may make. It keeps a slow service from being\n'
    'flooded by its own clients.'
)
RESULT = {
    'works': ['It defines a retry budget in its first sentence.', 'Each section has one idea.'],
    'suggestions': [
        {
            'part': 'opening',
            'before': 'It keeps a slow service',
            'after': 'A retry budget keeps a slow service',
            'why': 'names the subject in each passage',
            'help': 'The sentence stands on its own when an assistant quotes it.',
        },
        {
            'part': 'opening',
            'before': 'Not in the post at all.',
            'after': 'Invented.',
            'why': 'x',
            'help': 'x',
        },
    ],
    'summary': 'The post answers its question directly.',
    'faq': {
        'questions': [
            {'question': 'What is a retry budget?', 'answer': 'A cap on retries per route.'},
            {'question': 'Why use one?', 'answer': 'It saves 40% of load on a slow service.'},
        ],
        'closing_cta': '',
        'summary': '',
    },
    'takeaways': {'takeaways': ['Cap retries per route.', 'Start with one route.'], 'summary': ''},
    'tables': [],
    'alts': [{'image': 'i1', 'alt': 'A chart of retries per minute', 'why': 'its file name'}],
    'opener': {'before': '', 'after': '', 'why': ''},
    'queries': ['what is a retry budget', 'how do retry budgets work'],
    'sources_needed': [
        {
            'part': 'opening',
            'claim': 'A retry budget caps the retries each route may make.',
            'kind': 'the product documentation that defines it',
        },
        {'part': 'opening', 'claim': 'A claim the post never makes.', 'kind': 'a study'},
    ],
}


class ReportCase(RouteCase):
    def site(self, html=None):
        site = Site()
        site.page('/posts/retry-budgets', html or page())
        site.page('/robots.txt', 'User-agent: *\nAllow: /\n', kind='text/plain')
        return site

    def preview(self, site=None):
        with (site or self.site()).serving():
            return self.post('published-preview', {'url': URL})

    def begin(self, operation='a' * 32):
        shown = self.preview()
        return self.post(
            'geo-report-start',
            {
                'operation': operation,
                'published': {'preview': shown['preview'], 'expected': shown['expected']},
            },
        )

    def finish(self, ident, value=RESULT):
        job = tool_jobs.read(self.root, ident)
        job.update(
            status='ready',
            result={'content': json.dumps(value), 'notes': ''},
            finished_at=studio.now(),
        )
        tool_jobs.write(self.root, job)
        tool_jobs._ended(self.root, job)
        return self.get('geo-report', id=ident)

    def ready(self, operation='a' * 32, value=RESULT):
        made = self.begin(operation)
        return self.finish(made['id'], value)


class ReportTests(ReportCase):
    def test_one_press_starts_one_job_and_makes_no_blog(self):
        made = self.begin()
        self.assertEqual(made['status'], 'working')
        self.assertEqual(made['kind'], 'geo-report')
        self.assertEqual(made['url'], URL)
        job = tool_jobs.read(self.root, made['id'])
        self.assertEqual(job['kind'], 'geo-report')
        for rule in ('Never invent a statistic, quotation, citation', 'no score, grade'):
            self.assertIn(rule, job['guidance'])
        self.assertIn("post's own text is its\nevidence", job['guidance'])
        self.assertEqual(job['payload']['images_without_alt'][0]['image'], 'i1')
        self.assertEqual(list(studio.inside(self.root, 'articles').glob('*')), [])
        # The same press again is the same report and the same job.
        again = self.post(
            'geo-report-start', {'operation': 'a' * 32, 'published': {'preview': 'x'}}
        )
        self.assertEqual(again['id'], made['id'])
        self.assertEqual(len(list(studio.inside(self.root, '.blog-runs', 'tools').glob('*'))), 1)

    def test_the_report_keeps_the_desks_rules(self):
        shown = self.ready()
        self.assertEqual(shown['status'], 'ready')
        self.assertEqual(shown['works'], RESULT['works'])
        rows = shown['recommendations']
        self.assertEqual(rows[0]['kind'], 'change')
        self.assertEqual(rows[0]['help'], RESULT['suggestions'][0]['help'])
        self.assertEqual([row['kind'] for row in rows], ['change', 'alt', 'faq', 'takeaways'])
        self.assertNotIn('Invented', json.dumps(shown), 'a change not in the post is dropped')
        faq = next(row for row in rows if row['kind'] == 'faq')
        self.assertIn('the post and its sources do not have', faq['flag'], 'a new number')
        self.assertEqual(faq['where'], 'before “Next steps”')
        self.assertEqual(shown['questions'], RESULT['queries'])
        self.assertEqual(
            [row['claim'] for row in shown['sources_needed']],
            ['A retry budget caps the retries each route may make.'],
        )
        self.assertNotIn('score', json.dumps(shown))
        kinds = [entry['type'] for entry in shown['post']]
        self.assertEqual(kinds[0], 'title')
        marked = next(entry for entry in shown['post'] if entry['type'] == 'marked')
        self.assertIn({'t': 'ins', 'v': 'A retry budget'}, marked['segments'])
        self.assertIn({'t': 'del', 'v': 'It'}, marked['segments'])
        self.assertEqual(marked['notes'], [{'n': 1, 'why': 'names the subject in each passage'}])
        additions = [entry for entry in shown['post'] if entry['type'] == 'addition']
        self.assertEqual([a['kind'] for a in additions], ['takeaways', 'faq'])
        at = shown['post'].index(additions[1])
        self.assertEqual(
            shown['post'][at + 1], {'type': 'heading', 'level': 2, 'text': 'Next steps'}
        )
        alt = next(e for e in shown['post'] if e['type'] == 'marked' and 'Image' in json.dumps(e))
        self.assertEqual(
            [s['v'] for s in alt['segments'] if s['t'] != 'note'],
            ['[Image: budget-chart.png — alt text: ', 'A chart of retries per minute', ']'],
        )
        self.assertEqual(alt['notes'][0]['n'], 2)
        self.assertIn('eligibility checks', shown['access']['eligibility'])

    def test_downloads_are_markdown_and_one_self_contained_html_file(self):
        self.ready()
        md = self.get('geo-report-download', id='a' * 32, format='md')
        self.assertEqual(md['filename'], 'geo-report-retry-budgets.md')
        for heading in (
            '# GEO report: Retry budgets',
            '## Summary',
            '## The post with changes marked',
            '## Questions this post answers',
            '## Sources needed',
            '## Page access',
        ):
            self.assertIn(heading, md['content'])
        self.assertIn('~~It~~ **A retry budget** keeps a slow service', md['content'])
        doc = self.get('geo-report-download', id='a' * 32, format='html')['content']
        self.assertTrue(doc.startswith('<!doctype html>'))
        self.assertIn('<del>It</del> <ins>A retry budget</ins>', doc)
        self.assertIn('@media print', doc)
        for outside in ('<script', 'src=', '<link', 'http-equiv="refresh"'):
            self.assertNotIn(outside, doc)
        self.assertIn("default-src 'none'", doc)

    def test_a_report_is_listed_as_a_report_not_a_draft(self):
        self.ready()
        listed = self.get('geo-reports')['items']
        self.assertEqual(
            [(row['kind'], row['status']) for row in listed], [('geo-report', 'ready')]
        )
        self.assertEqual(self.get('runs')['items'], [])
        self.assertEqual(self.get('board')['items'], [])

    def test_an_unreadable_result_says_so(self):
        made = self.begin()
        shown = self.finish(made['id'], 'not json')
        self.assertEqual(shown['status'], 'failed')
        self.assertIn('cannot read', shown['error'])

    def test_a_change_inside_another_is_listed_not_marked_twice(self):
        draft = geo_report._draft({'title': 'T', 'markdown': '# T\n\nOne two three four.\n'})
        change = {'part': 'opening', 'note': 'x', 'flag': ''}
        result = {
            'changes': [
                {**change, 'before': 'two three', 'after': '2 3'},
                {**change, 'before': 'three four', 'after': '3 4'},
            ],
            'additions': {},
        }
        post, overlaps = geo_report.marked(draft, result)
        self.assertEqual(overlaps, [2])
        marks = [s for e in post if e['type'] == 'marked' for s in e['segments']]
        self.assertEqual([s['n'] for s in marks if s['t'] == 'note'], [1])

    def test_reports_of_different_collection_posts_are_each_current(self):
        held = studio._HELD.set(True)
        self.addCleanup(studio._HELD.reset, held)
        for operation, item in (('1' * 32, 'post-a'), ('2' * 32, 'post-b')):
            found = {
                'title': 'Post ' + item,
                'markdown': '# Post\n\nSome text.\n',
                'url': '',
                'final_url': '',
                'read_at': studio.now(),
                'collection_item': {'id': item, 'location': 'local'},
                'access': None,
            }
            geo_report.start(self.root, operation, found)
        listed = self.get('geo-reports')['items']
        self.assertEqual([row['newer'] for row in listed], [None, None])

    def test_an_interrupted_job_is_said_as_failed(self):
        made = self.begin()
        job = tool_jobs.read(self.root, made['id'])
        job.update(status='failed', error='This task was interrupted.')
        tool_jobs.write(self.root, job)
        shown = self.get('geo-report', id=made['id'])
        self.assertEqual(
            (shown['status'], shown['error']), ('failed', 'This task was interrupted.')
        )


class AfterwardsTests(ReportCase):
    def test_edit_on_the_desk_brings_a_copy_with_the_recommendations_in_finishing(self):
        self.ready()
        shown = self.post('geo-report-desk', {'id': 'a' * 32, 'operation': 'b' * 32})
        ident = shown['desk']
        self.assertEqual(shown['desk']['id'] if isinstance(shown['desk'], dict) else ident, ident)
        article = ident if isinstance(ident, str) else ident['id']
        _, record = studio.item(self.root, 'articles', article)
        self.assertEqual(record['published_post']['url'], URL)
        self.assertEqual(record['geo_review']['report'], 'a' * 32)
        view = self.get('desk', id=article)
        self.assertEqual(view['geo_review']['status'], 'done', 'the report stands for it')
        geo = view['finishing']['geo']
        self.assertEqual(geo['items'][0]['after'], 'A retry budget keeps a slow service')
        faq = view['finishing']['faq']['items'][0]
        self.assertEqual(faq['at'], view['sections'][-1]['id'], 'before Next steps')
        self.assertTrue(faq['present'])
        # The FAQ applies as any FAQ does; nothing was applied by itself.
        self.assertNotIn('Frequently asked questions', desk.join(desk.read(self.root, article)))
        held = studio._HELD.set(True)
        self.addCleanup(studio._HELD.reset, held)
        done = desk_finish.apply(
            self.root,
            article,
            view['revision'],
            view['finishing']['faq']['job'],
            [{'id': faq['id']}],
        )
        self.assertEqual(done['applied'], 1)
        # Once made, the same desk copy opens again.
        again = self.post('geo-report-desk', {'id': 'a' * 32, 'operation': 'c' * 32})
        self.assertEqual(again['desk'], article)

    def test_run_again_reads_the_page_again_and_says_what_changed(self):
        self.ready()
        changed = (
            page()
            .replace('It keeps a slow service', 'A retry budget keeps a slow service')
            .replace(
                '<h2>Next steps</h2>',
                '<h2>Limits</h2><p>One budget per route.</p><h2>Next steps</h2>',
            )
        )
        with self.site(changed).serving():
            made = self.post('geo-report-again', {'id': 'a' * 32, 'operation': 'd' * 32})
        self.assertEqual(made['previous'], 'a' * 32)
        said = made['changed']
        self.assertFalse(said['same'])
        self.assertEqual(said['added'], ['Limits'])
        self.assertEqual(said['changed'], ['the opening'])
        self.assertEqual((said['taken'], said['of']), (1, 1))
        listed = {row['id']: row for row in self.get('geo-reports')['items']}
        self.assertEqual(listed['a' * 32]['newer'], 'd' * 32)
        self.assertEqual(self.get('geo-report', id='a' * 32)['newer'], 'd' * 32)
        with self.site(changed).serving():
            same = self.post('geo-report-again', {'id': 'd' * 32, 'operation': 'e' * 32})
        self.assertTrue(same['changed']['same'])


import google_drive as gd  # noqa: E402
from google_suggestions import accepted_markdown  # noqa: E402
import test_google_handoff  # noqa: E402
import test_google_suggestions  # noqa: E402


class Drive(test_google_handoff.Drive, test_google_suggestions.ReviewProvider):
    """The fake Google model: a new Doc made once, then suggestions and comments on it."""


class GoogleTests(ReportCase):
    def setUp(self):
        super().setUp()
        self.drive = Drive()
        test_google_handoff.titled(self.drive.doc, 'Handoffs')
        for patcher in (
            patch.object(gd, 'active_account', return_value='test@example.invalid'),
            patch.object(gd, 'Client', return_value=self.drive),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        markdown = accepted_markdown(self.drive.doc).decode('utf-8')
        held = studio._HELD.set(True)
        try:
            found = {
                'title': 'Handoffs',
                'markdown': markdown,
                'url': URL,
                'final_url': URL,
                'read_at': studio.now(),
                'access': None,
            }
            with studio.locked(self.root):
                geo_report.start(self.root, 'f' * 32, found)
        finally:
            studio._HELD.reset(held)
        draft = geo_report.read(self.root, 'f' * 32)['draft']
        part = draft['sections'][0]['id']
        self.finish(
            'f' * 32,
            {
                'works': [],
                'suggestions': [
                    {
                        'part': part,
                        'before': 'This isn’t slow.',
                        'after': 'This isn’t slow at all.',
                        'why': 'says it plainly',
                        'help': 'A direct answer is easier to quote.',
                    }
                ],
                'takeaways': {'takeaways': ['Handoffs cause the delay.']},
            },
        )

    def test_a_new_doc_gets_each_change_as_a_suggestion_and_each_reason_as_a_comment(self):
        writes = self.drive.writes
        plan = self.post(
            'geo-report-google-plan', {'id': 'f' * 32, 'operation': '1' * 32, 'mode': 'auto'}
        )
        self.assertEqual(len(self.drive.imports), 1, 'one new Doc of the post')
        self.assertEqual((plan['suggestions'], plan['comments']), (1, 1))
        self.assertEqual(self.drive.writes, writes, 'checking sends nothing')
        sent = self.post(
            'geo-report-google-send', {'id': 'f' * 32, 'plan': plan['plan'], 'confirmed': True}
        )
        self.assertEqual(sent['status'], 'verified-pending')
        notes = json.dumps(self.drive.comments + self.drive.threads, ensure_ascii=False)
        self.assertIn('says it plainly', notes)
        self.assertIn('A direct answer is easier to quote.', notes)
        self.assertIn('Key takeaways suggested', notes)
        # Sending again sends nothing twice.
        writes = self.drive.writes
        self.post(
            'geo-report-google-send', {'id': 'f' * 32, 'plan': plan['plan'], 'confirmed': True}
        )
        self.assertEqual(self.drive.writes, writes)

    def test_a_desk_copy_edited_since_is_sent_from_the_desk_instead(self):
        made = self.post('geo-report-desk', {'id': 'f' * 32, 'operation': '2' * 32})
        held = studio._HELD.set(True)
        self.addCleanup(studio._HELD.reset, held)
        draft = desk.read(self.root, made['desk'])
        desk.save(self.root, made['desk'], draft['revision'], 'opening', 'Changed by hand.')
        with self.assertRaisesRegex(ValueError, 'Send the desk copy’s changes from the desk'):
            self.post(
                'geo-report-google-plan', {'id': 'f' * 32, 'operation': '3' * 32, 'mode': 'auto'}
            )
        self.assertEqual(self.drive.imports, [])
