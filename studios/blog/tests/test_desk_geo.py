"""Improve discovery on the desk: GEO additions on request, each previewed then applied or
skipped, and a post's own Include a GEO review choice. Fake workers only; no provider runs."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import json
from pathlib import Path
import re

import blog_runner
import desk
import desk_finish
import desk_jobs
import studio
import tool_jobs
from test_desk import DRAFT
from test_desk_finish import ToolCase
from test_desk_start import WRITTEN, StartCase

SKILL = Path(__file__).resolve().parents[1] / 'skills/blog-studio'
# The playbook guidelines (#280) and the limits the GEO review keeps, as its guidance words
# them. The GEO report's job reads the same words (test_geo_report).
GUIDELINES = (
    'Claim context',
    'method, sample, environment',
    'First-hand or borrowed',
    'original source',
    'Conditions and tradeoffs',
    '("Overview", "More", "Details")',
    'numbered steps',
    'summarizes an embedded video',
    'Renamed products and aliases',
    '"as of" date',
    'Never suggest refreshing a date without changing the facts',
    'Decision support, where it fits',
    'Do not force these on a post they do not fit',
    'an aid for readers',
    'never present it as earning citations or rankings',
    'What Drives AI Citations?',
)
KEPT = (
    'Do not force\nFAQ, question headings, brand mentions, certainty, sentence lengths, or schema',
    'keyword density',
    'tiny snippets',
    'near-duplicates',
    'expected outcome',
    'Never invent a date, version, baseline or source',
)
# Words that would say an addition or a change earns citations or rankings.
PROMISE = re.compile(
    r'\b(?:boosts?|increases?|improves?|raises?|earns?|wins?|gains?|more|higher|better|top)\b'
    r'\W+(?:\w+\W+){0,3}?(?:citations?|cited|rankings?|ranks?)\b',
    re.I,
)
CLAIM = 'The cache cuts costs by 40%. Pricing starts at $20 a month.'

POST = """# A synthetic title

An opening paragraph about parsers.

## First part

First text.

## Second part

Second text.

## Next steps

Try the parser today.
"""


class AdditionCase(ToolCase):
    def ready_geo(self, tool, value, **extra):
        return self.ready(self.queue(tool, **extra), value)

    def set_of(self, tool):
        return self.shown(tool)

    def post(self, text=POST):
        made = desk.create(self.root, {'title': 'Post', 'manuscript': text})
        self.ident = made['id']
        self.seen = made['revision']
        return made


class RequestTests(AdditionCase):
    def test_each_addition_asks_only_from_the_post_and_never_applies(self):
        for tool in ('faq', 'table', 'takeaways', 'queries', 'opener'):
            job = self.queue(tool, **({'count': 4} if tool == 'faq' else {}))
            self.assertEqual(job['kind'], 'finish-' + tool)
            self.assertIn('Never invent a statistic, quotation, citation', job['guidance'])
            self.assertIn('Do not promise rankings', job['guidance'])
            self.assertIn('Return JSON in content', job['guidance'])
            self.assertIn('sections', job['payload'])
            desk_jobs.stop(self.root, self.ident, job['id'])
        self.assertTrue(self.draft()['sections'][0]['text'].startswith('We leverage'))

    def test_an_faq_takes_three_to_six_questions(self):
        for count in (2, 7, '4', None):
            with self.assertRaisesRegex(ValueError, 'Choose 3 to 6 questions'):
                self.queue('faq', count=count)
        job = self.queue('faq', count=3)
        self.assertEqual(job['payload']['questions_wanted'], 3)
        self.assertEqual(job['metadata']['desk']['count'], 3)

    def test_quotes_need_a_source(self):
        with self.assertRaisesRegex(ValueError, 'quotations come only from your sources'):
            self.queue('quotes')

    def test_alt_text_needs_an_image_without_alt(self):
        with self.assertRaisesRegex(ValueError, 'no images'):
            self.queue('alt')
        desk.save(self.root, self.ident, self.seen, self.second, '![A chart](https://x.test/a.png)')
        self.seen = self.draft()['revision']
        with self.assertRaisesRegex(ValueError, 'already has alt text'):
            self.queue('alt')


class FAQTests(AdditionCase):
    def faq(self, rows, count=4, **more):
        done = self.ready_geo('faq', {'questions': rows, **more}, count=count)
        self.assertFalse(done.get('error'), done.get('error'))
        return done

    def test_an_faq_is_a_new_section_at_the_end_before_a_closing_call_to_action(self):
        self.post()
        rows = [{'question': f'Question {n}?', 'answer': f'Answer {n}.'} for n in range(1, 7)]
        rows.append({'question': 'Question 1?', 'answer': 'A repeat.'})
        self.faq(rows, count=4)
        found = self.set_of('faq')
        item = found['items'][0]
        self.assertTrue(item['insert'])
        self.assertEqual(item['heading'], 'Frequently asked questions')
        self.assertEqual(len(item['questions']), 4, 'no more than the person chose')
        last = self.draft()['sections'][-1]
        self.assertEqual(last['heading'], 'Next steps')
        self.assertEqual((item['at'], item['cta']), (last['id'], last['id']))
        self.assertTrue(item['present'])
        self.assertEqual(found['dropped'], 3)
        self.assertEqual(len(self.draft()['sections']), 3, 'nothing is added by itself')
        # Only the ticked questions, as edited, at the place the person picked.
        chosen = [item['questions'][0], {'question': 'My own?', 'answer': 'Edited answer.'}]
        first = self.draft()['sections'][0]['id']
        shown = self.act(
            'apply',
            seen=self.seen,
            job=found['job'],
            items=[{'id': item['id'], 'after': desk_finish.faq_text(chosen), 'at': first}],
        )
        self.assertEqual(shown['finished']['applied'], 1)
        sections = self.draft()['sections']
        self.assertEqual(sections[0]['heading'], 'Frequently asked questions')
        self.assertEqual(
            sections[0]['text'],
            '**Question 1?**\n\nAnswer 1.\n\n**My own?**\n\nEdited answer.',
        )
        self.assertIn('## Frequently asked questions', desk.join(self.draft()))
        self.assertEqual(self.set_of('faq')['items'][0]['state'], 'applied')

    def test_by_default_the_faq_goes_at_the_end_and_is_ordinary_text(self):
        self.faq([{'question': 'Why?', 'answer': 'Because the parser is robust.'}])
        item = self.set_of('faq')['items'][0]
        self.assertEqual(item['at'], 'end')
        self.act('apply', seen=self.seen, job=self.set_of('faq')['job'], items=[{'id': 'p1'}])
        faq = self.draft()['sections'][-1]
        self.assertEqual(faq['text'], '**Why?**\n\nBecause the parser is robust.')
        desk.save(self.root, self.ident, self.draft()['revision'], faq['id'], 'Edited by hand.')
        self.assertEqual(self.draft()['sections'][-1]['text'], 'Edited by hand.')

    def test_a_post_that_changed_since_marks_the_faq_out_of_date(self):
        self.faq([{'question': 'Why?', 'answer': 'Because.'}])
        desk.save(self.root, self.ident, self.seen, self.second, 'A change made later.')
        item = self.set_of('faq')['items'][0]
        self.assertFalse(item['present'])
        with self.assertRaisesRegex(ValueError, 'suggested before the post’s latest changes'):
            self.act(
                'apply',
                seen=self.draft()['revision'],
                job=self.set_of('faq')['job'],
                items=[{'id': 'p1'}],
            )
        self.assertEqual(len(self.draft()['sections']), 2)

    def test_a_heading_that_only_mentions_faqs_is_not_the_posts_faq(self):
        self.post(POST + '\n## Why FAQs fail\n\nThey repeat the post.\n')
        self.assertNotIn('faq_section', self.queue('faq', count=3)['payload'])

    def test_running_it_again_on_a_post_with_an_faq_proposes_changes_to_that_faq(self):
        self.post(POST + '\n## FAQ\n\n**Old?**\n\nOld answer.\n')
        job = self.queue('faq', count=3)
        self.assertEqual(job['payload']['faq_section']['heading'], 'FAQ')
        self.assertIn('instead of a second one', job['guidance'])
        self.ready(job, {'questions': [{'question': 'New?', 'answer': 'New answer.'}]})
        item = self.set_of('faq')['items'][0]
        self.assertNotIn('insert', item)
        self.assertTrue(item['whole'])
        self.assertEqual(item['before'], '**Old?**\n\nOld answer.')
        self.act('apply', seen=self.seen, job=self.set_of('faq')['job'], items=[{'id': 'p1'}])
        headings = [s['heading'] for s in self.draft()['sections']]
        self.assertEqual(headings.count('FAQ'), 1)
        self.assertNotIn('Frequently asked questions', headings, 'never a second FAQ')
        self.assertEqual(self.draft()['sections'][-1]['text'], '**New?**\n\nNew answer.')

    def test_an_answer_with_a_number_the_post_lacks_is_flagged(self):
        self.faq([{'question': 'How fast?', 'answer': 'It reads 900 files a second.'}])
        self.assertIn('adds a number', self.set_of('faq')['items'][0]['flag'])

    def test_an_faq_can_be_skipped_and_never_lands_with_other_items(self):
        self.faq([{'question': 'Why?', 'answer': 'Because.'}])
        job = self.set_of('faq')['job']
        with self.assertRaisesRegex(ValueError, 'on its own'):
            self.act('apply', seen=self.seen, job=job, items=[{'id': 'p1'}], all=True)
        self.act('skip', job=job, items=['p1'])
        self.assertEqual(self.set_of('faq')['items'][0]['state'], 'skipped')
        self.assertEqual(len(self.draft()['sections']), 2)

    def test_a_question_the_post_cannot_answer_leaves_an_empty_set(self):
        self.faq([], summary='The post answers no reader questions yet.')
        found = self.set_of('faq')
        self.assertEqual(found['items'], [])
        self.assertEqual(found['summary'], 'The post answers no reader questions yet.')


class TakeawaysTests(AdditionCase):
    def test_key_takeaways_go_after_the_opening_as_a_list(self):
        self.ready_geo(
            'takeaways', {'takeaways': ['- Parse once.', 'Keep 12 files.', 'Parse once.']}
        )
        item = self.set_of('takeaways')['items'][0]
        self.assertEqual(item['at'], self.first)
        self.assertEqual([p['point'] for p in item['points']], ['Parse once.', 'Keep 12 files.'])
        self.act('apply', seen=self.seen, job=self.set_of('takeaways')['job'], items=[{'id': 'p1'}])
        section = self.draft()['sections'][0]
        self.assertEqual(section['heading'], 'Key takeaways')
        self.assertEqual(section['text'], '- Parse once.\n- Keep 12 files.')


class TableAndQuoteTests(AdditionCase):
    def test_a_table_follows_the_paragraph_that_compares(self):
        table = '| Parser | Speed |\n| --- | --- |\n| Old | 3 seconds |'
        self.ready_geo(
            'table',
            {
                'tables': [
                    {
                        'part': self.first,
                        'after_text': 'It reads 12 files in 3 seconds at Acme Labs.',
                        'table': table,
                        'why': 'Side by side.',
                    },
                    {'part': self.first, 'after_text': 'We leverage', 'table': table},
                    {'part': self.second, 'after_text': 'Second text.', 'table': 'not a table'},
                ]
            },
        )
        found = self.set_of('table')
        self.assertEqual(len(found['items']), 1)
        self.assertEqual(found['dropped'], 2, 'mid-paragraph and non-tables are left out')
        item = found['items'][0]
        self.assertTrue(item['after'].endswith('\n\n' + table))
        self.assertEqual(item['flag'], '')
        self.act('apply', seen=self.seen, job=found['job'], items=[{'id': 'p1'}])
        self.assertIn(table, self.draft()['sections'][0]['text'])
        self.assertEqual(desk.versions(self.root, self.ident, self.first)[0]['source'], 'finishing')

    def anchored(self, text, after_text, tool='table'):
        desk.save(self.root, self.ident, self.seen, self.second, text)
        self.seen = self.draft()['revision']
        table = '| Parser | Speed |\n| --- | --- |\n| Old | slow |'
        row = {'part': self.second, 'after_text': after_text, 'table': table}
        self.ready_geo('table', {'tables': [row]})
        return self.set_of('table')

    def test_a_table_never_lands_inside_a_paragraph_a_list_or_code(self):
        wrapped = 'The old parser is slow.\nThe new parser is fast.\nBoth read the same files.'
        self.assertEqual(self.anchored(wrapped, 'The old parser is slow.')['items'], [])
        listed = 'Two parsers:\n\n- The old parser is slow.\n- The new parser is fast.'
        self.assertEqual(self.anchored(listed, 'The old parser is slow.')['items'], [])
        self.assertEqual(self.anchored(listed, 'The new parser is fast.')['items'], [])
        fenced = 'Run this:\n\n```\nThe old parser is slow.\n\nmore code\n```\n\nDone.'
        self.assertEqual(self.anchored(fenced, 'The old parser is slow.')['items'], [])
        quoted = '> The old parser is slow.\n\nAfter the quote.'
        self.assertEqual(self.anchored(quoted, 'The old parser is slow.')['items'], [])

    def test_a_table_after_a_wrapped_paragraph_keeps_a_blank_line_on_each_side(self):
        text = 'The old parser is slow.\nThe new parser is fast.\n\nBoth read the same files.'
        found = self.anchored(text, 'The new parser is fast.')
        self.act('apply', seen=self.seen, job=found['job'], items=[{'id': 'p1'}])
        self.assertEqual(
            desk.text_of(self.draft(), self.second),
            'The old parser is slow.\nThe new parser is fast.\n\n'
            '| Parser | Speed |\n| --- | --- |\n| Old | slow |\n\nBoth read the same files.',
        )

    def test_no_comparison_is_an_empty_set_with_its_reason(self):
        self.ready_geo('table', {'tables': [], 'summary': 'The post compares nothing.'})
        self.assertEqual(self.set_of('table')['items'], [])
        self.assertEqual(self.set_of('table')['summary'], 'The post compares nothing.')

    def test_quotes_are_word_for_word_from_a_named_source(self):
        passage = 'The parser reads twelve files in three seconds on a laptop.'
        desk.add_sources(
            self.root, self.ident, {'sources': [self.source('Intro. ' + passage + ' More.')]}
        )
        self.seen = self.draft()['revision']
        job = self.queue('quotes')
        source = job['payload']['sources'][0]
        after = 'It reads 12 files in 3 seconds at Acme Labs.'
        self.ready(
            job,
            {
                'quotes': [
                    {
                        'source': source['id'],
                        'quote': passage,
                        'part': self.first,
                        'after_text': after,
                    },
                    {
                        'source': source['id'],
                        'quote': 'The parser reads twelve files very quickly indeed.',
                        'part': self.first,
                        'after_text': after,
                    },
                ]
            },
        )
        found = self.set_of('quotes')
        self.assertEqual(len(found['items']), 1, 'a paraphrase is left out')
        item = found['items'][0]
        self.assertEqual(item['after'], after + '\n\n> ' + passage + '\n>\n> — Synthetic source')
        self.assertIn('Word for word from Synthetic source.', item['note'])
        # Applied, the quotation is a block of its own: the paragraph after it stays prose.
        desk.save(
            self.root,
            self.ident,
            self.draft()['revision'],
            self.first,
            after + '\n\nThe next part.',
        )
        self.seen = self.draft()['revision']
        job = self.queue('quotes')
        row = {'source': source['id'], 'quote': passage, 'part': self.first, 'after_text': after}
        self.ready(job, {'quotes': [row]})
        self.act('apply', seen=self.seen, job=self.set_of('quotes')['job'], items=[{'id': 'p1'}])
        self.assertTrue(
            desk.text_of(self.draft(), self.first).endswith(
                '> — Synthetic source\n\nThe next part.'
            )
        )
        # A line that ends a line, not a paragraph, takes none.
        desk.save(
            self.root, self.ident, self.draft()['revision'], self.first, after + '\nThe next line.'
        )
        self.seen = self.draft()['revision']
        job = self.queue('quotes')
        self.ready(job, {'quotes': [row]})
        self.assertEqual(self.set_of('quotes')['items'], [])

    def test_a_quotation_is_whole_sentences_never_a_fragment_that_reverses_them(self):
        text = 'It is not true that the parser is safe on every input file. It reads them all.'
        desk.add_sources(self.root, self.ident, {'sources': [self.source(text)]})
        self.seen = self.draft()['revision']
        job = self.queue('quotes')
        source = job['payload']['sources'][0]
        after = 'It reads 12 files in 3 seconds at Acme Labs.'
        rows = [
            {'quote': 'true that the parser is safe on every input file.'},
            {'quote': 'It is not true that the parser is safe on every input'},
            {'quote': 'It is not true that the parser is safe on every input file.'},
        ]
        self.ready(
            job,
            {
                'quotes': [
                    {**row, 'source': source['id'], 'part': self.first, 'after_text': after}
                    for row in rows
                ]
            },
        )
        found = self.set_of('quotes')
        self.assertEqual(len(found['items']), 1)
        self.assertIn('> It is not true that the parser is safe', found['items'][0]['after'])


class AltTextTests(AdditionCase):
    def setUp(self):
        super().setUp()
        text = 'The chart below shows parse time per file.\n\n![](https://x.test/parse-time.png)'
        desk.save(
            self.root, self.ident, self.seen, self.second, text + '\n\n![](https://x.test/b.png)'
        )
        self.seen = self.draft()['revision']

    def test_alt_text_is_written_from_what_the_post_says_and_says_so(self):
        job = self.queue('alt')
        wanted = job['payload']['images_without_alt']
        self.assertEqual([w['file_name'] for w in wanted], ['parse-time.png', 'b.png'])
        self.assertIn('The chart below shows parse time per file.', wanted[0]['context'])
        self.assertIn('You cannot see the images', job['guidance'])
        self.ready(
            job,
            {
                'alts': [
                    {'image': 'i1', 'alt': 'Chart of parse time per file', 'why': 'the line above'},
                    {'image': 'i2', 'alt': ''},
                ]
            },
        )
        found = self.set_of('alt')
        self.assertEqual(found['unknown'], 1, 'an image the post says nothing about is said')
        item = found['items'][0]
        self.assertEqual(
            item['after'], '![Chart of parse time per file](https://x.test/parse-time.png)'
        )
        self.assertIn('Blog Studio cannot see the image itself', item['note'])
        self.act('apply', seen=self.seen, job=found['job'], items=[{'id': 'p1'}])
        self.assertIn(
            '![Chart of parse time per file](https://x.test/parse-time.png)',
            desk.text_of(self.draft(), self.second),
        )

    def test_alt_text_with_a_number_the_post_lacks_is_flagged(self):
        job = self.queue('alt')
        self.ready(job, {'alts': [{'image': 'i1', 'alt': 'Chart of 40 parse times'}]})
        self.assertIn('adds a number', self.set_of('alt')['items'][0]['flag'])

    def test_an_edit_may_change_only_the_alt_words(self):
        job = self.queue('alt')
        self.ready(job, {'alts': [{'image': 'i1', 'alt': 'Chart of parse time'}]})
        found = self.set_of('alt')
        with self.assertRaisesRegex(ValueError, 'Keep the image reference'):
            self.act(
                'apply',
                seen=self.seen,
                job=found['job'],
                items=[{'id': 'p1', 'after': '![Chart](https://x.test/other.png)'}],
            )
        self.act(
            'apply',
            seen=self.seen,
            job=found['job'],
            items=[{'id': 'p1', 'after': '![My words](https://x.test/parse-time.png)'}],
        )
        self.assertIn(
            '![My words](https://x.test/parse-time.png)', desk.text_of(self.draft(), self.second)
        )

    def test_a_held_images_reference_takes_alt_text(self):
        from test_desk import IMAGE_ONE

        made = desk.create(
            self.root,
            {
                'title': 'Images',
                'manuscript': '# Images\n\nA diagram of the parser.\n\n![][image1]\n\n[image1]: <'
                + IMAGE_ONE
                + '>\n',
            },
        )
        self.ident, self.seen = made['id'], made['revision']
        job = self.queue('alt')
        self.assertNotIn('data:image', json.dumps(job['payload']))
        self.ready(job, {'alts': [{'image': 'i1', 'alt': 'Diagram of the parser'}]})
        self.act('apply', seen=self.seen, job=self.set_of('alt')['job'], items=[{'id': 'p1'}])
        self.assertIn('![Diagram of the parser][image1]', self.draft()['opening'])
        self.assertIn(
            '[image1]: <data:image', desk.join(self.draft(), data=desk._data(self.root, self.ident))
        )


class QueriesAndOpenerTests(AdditionCase):
    def test_likely_search_questions_are_advice_only(self):
        self.ready_geo(
            'queries',
            {
                'queries': [
                    'How do parsers read files?',
                    'How do parsers read files?',
                    'Why parse once?',
                ]
            },
        )
        found = self.set_of('queries')
        self.assertEqual(found['items'], [])
        self.assertEqual(found['queries'], ['How do parsers read files?', 'Why parse once?'])
        self.assertEqual(self.draft()['revision'], self.seen, 'nothing goes into the post')

    def test_a_definition_opening_replaces_the_openings_first_sentence(self):
        self.ready_geo(
            'opener',
            {
                'before': 'An opening paragraph.',
                'after': 'A parser turns files into data.',
                'why': 'Defines it.',
            },
        )
        item = self.set_of('opener')['items'][0]
        self.assertEqual(
            (item['before'], item['after']),
            ('An opening paragraph.', 'A parser turns files into data.'),
        )
        self.act('apply', seen=self.seen, job=self.set_of('opener')['job'], items=[{'id': 'p1'}])
        self.assertEqual(self.draft()['opening'], 'A parser turns files into data.')
        self.assertEqual(desk.versions(self.root, self.ident, 'opening')[0]['source'], 'finishing')

    def test_an_opening_that_is_a_list_or_takes_more_than_one_paragraph_is_left_out(self):
        desk.save(self.root, self.ident, self.seen, 'opening', '- A list item.\n- Another.')
        self.seen = self.draft()['revision']
        self.ready_geo('opener', {'before': '- A list item.', 'after': 'A parser reads files.'})
        self.assertEqual(self.set_of('opener')['items'], [])
        desk.save(self.root, self.ident, self.seen, 'opening', 'An opening.')
        self.seen = self.draft()['revision']
        self.ready_geo('opener', {'before': 'An opening.', 'after': 'One.\n\nTwo paragraphs.'})
        self.assertEqual(self.set_of('opener')['items'], [])

    def test_an_opening_that_is_not_the_start_is_left_out(self):
        self.ready_geo('opener', {'before': 'paragraph.', 'after': 'A definition.'})
        self.assertEqual(self.set_of('opener')['items'], [])

    def test_a_fake_worker_runs_an_addition_end_to_end_without_applying_it(self):
        def worker(engine, payload, guidance, **options):
            self.assertEqual(options['web'], False)
            return {'content': json.dumps({'takeaways': ['Parse once.']}), 'notes': ''}

        self.queue('takeaways')
        tool_jobs.once(blog_runner.Engine(self.root, worker=worker))
        self.assertEqual(self.set_of('takeaways')['items'][0]['state'], 'open')
        self.assertEqual(len(self.draft()['sections']), 2)


class GuidelineTests(AdditionCase):
    """The playbook guidelines reach the worker, and a finding comes back located."""

    def run_geo(self, value):
        seen = []

        def worker(engine, payload, guidance, **options):
            seen.append((payload, guidance, options))
            return {'content': json.dumps(value), 'notes': ''}

        job = self.queue('geo')
        tool_jobs.once(blog_runner.Engine(self.root, worker=worker))
        self.assertEqual(len(seen), 1)
        return job, seen[0]

    def test_the_desk_geo_review_gives_the_worker_every_guideline_and_keeps_its_limits(self):
        _, (_, guidance, options) = self.run_geo({'suggestions': []})
        self.assertEqual(options['web'], False)
        for words in GUIDELINES + KEPT:
            self.assertIn(words, guidance)
        self.assertIn('"as of" dates on time-sensitive facts', guidance, 'the check says it too')
        self.assertIn('the date or baseline a claim needs', guidance)
        # Improve discovery's additions read the same guidance: each an aid for readers.
        job = self.queue('takeaways')
        for words in GUIDELINES + KEPT:
            self.assertIn(words, job['guidance'])

    def test_a_claim_missing_its_context_is_a_located_proposal_to_apply_or_skip(self):
        desk.save(self.root, self.ident, self.draft()['revision'], self.first, CLAIM)
        self.seen = self.draft()['revision']
        job, (payload, _, _) = self.run_geo(
            {
                'suggestions': [
                    {
                        'part': self.first,
                        'before': 'The cache cuts costs by 40%.',
                        'after': 'In our March 2026 pilot, the cache cut costs by 40% against '
                        'the previous quarter.',
                        'why': 'Claim context: gives the period and baseline.',
                    },
                    {
                        'part': self.first,
                        'before': 'Pricing starts at $20 a month.',
                        'after': 'As of March 2026, pricing starts at $20 a month.',
                        'why': 'Time-sensitive: an "as of" date.',
                    },
                ],
                'summary': 'Name the source of the 40% saving.',
            }
        )
        self.assertIn(CLAIM, json.dumps(payload))
        shown = self.shown('geo')
        self.assertEqual(self.draft()['sections'][0]['text'], CLAIM, 'nothing applied by itself')
        self.assertEqual(shown['summary'], 'Name the source of the 40% saving.')
        context, dated = shown['items']
        self.assertEqual((context['part'], context['state']), (self.first, 'open'))
        self.assertEqual(context['before'], 'The cache cuts costs by 40%.')
        self.assertEqual(context['note'], 'Claim context: gives the period and baseline.')
        self.assertTrue(context['flag'], 'a date the post did not have waits to be checked')
        self.assertTrue(dated['flag'])
        self.act('skip', job=job['id'], items=[dated['id']])
        self.act('apply', seen=self.seen, job=job['id'], items=[{'id': context['id']}])
        self.assertEqual(
            self.draft()['sections'][0]['text'],
            'In our March 2026 pilot, the cache cut costs by 40% against the previous quarter. '
            'Pricing starts at $20 a month.',
        )
        states = {item['id']: item['state'] for item in self.shown('geo')['items']}
        self.assertEqual(states, {context['id']: 'applied', dated['id']: 'skipped'})

    def test_no_geo_words_a_person_reads_promise_citations_or_rankings(self):
        for path in (
            SKILL / 'assets/management/desk.js',
            SKILL / 'scripts/desk_finish.py',
            SKILL / 'scripts/geo_report.py',
        ):
            found = [m.group(0) for m in PROMISE.finditer(path.read_text())]
            self.assertEqual(found, [], path.name)
        self.assertIsNone(PROMISE.search('Answers the questions a reader asks next.'))
        self.assertTrue(PROMISE.search('An FAQ boosts your AI citations.'))
        self.assertTrue(PROMISE.search('Key takeaways help it earn more citations.'))


class GEOChoiceTests(StartCase):
    def setUp(self):
        super().setUp()
        self.addCleanup(lambda: blog_runner.ENGINES.pop(str(self.root), None))

    def create(self, **data):
        return desk.dispatch(
            self.root,
            'create',
            {
                'operation': studio.digest(json.dumps(data).encode())[:32],
                'title': 'Synthetic',
                **data,
            },
        )

    def geo_jobs(self, ident):
        return [job for job in desk_jobs.jobs(self.root, ident) if job['kind'] == 'finish-geo']

    def record(self, ident):
        return studio.item(self.root, 'articles', ident)[1]

    def settle(self, job, content):
        saved = tool_jobs.read(self.root, job['id'])
        saved.update(status='ready', result={'content': content, 'notes': ''}, finished_at='x')
        tool_jobs.write(self.root, saved)
        desk_jobs.ended(self.root, saved)
        return tool_jobs.read(self.root, job['id'])

    def test_it_is_off_unless_chosen_and_nothing_geo_runs(self):
        made = self.create(manuscript=DRAFT, first_pass='leave')
        self.assertNotIn('geo_review', self.record(made['id']))
        self.assertEqual(self.geo_jobs(made['id']), [])
        self.assertEqual(made['geo_review'], {'include': False, 'status': 'none', 'due': 'now'})
        with self.assertRaisesRegex(ValueError, 'GEO review'):
            self.create(manuscript=DRAFT, geo_review='yes')

    def test_chosen_with_a_brought_draft_one_review_runs_once_and_applies_nothing(self):
        made = self.create(manuscript=DRAFT, first_pass='leave', geo_review=True)
        found = self.geo_jobs(made['id'])
        self.assertEqual(len(found), 1)
        kept = self.record(made['id'])['geo_review']
        self.assertEqual((kept['include'], kept['job']), (True, found[0]['id']))
        self.assertTrue(found[0]['metadata']['desk']['auto'])
        self.assertEqual(desk_jobs.view(self.root, made['id'])['geo_review']['status'], 'working')
        result = {
            'suggestions': [
                {'part': 'opening', 'before': 'An opening paragraph.', 'after': 'A direct answer.'}
            ]
        }
        self.settle(found[0], json.dumps(result))
        self.assertEqual(desk.read(self.root, made['id'])['opening'], 'An opening paragraph.')
        shown = desk_jobs.view(self.root, made['id'])
        self.assertEqual(shown['finishing']['geo']['items'][0]['state'], 'open')
        self.assertEqual(shown['geo_review']['status'], 'done')
        self.assertEqual(shown['geo_review']['open'], 1)
        # Never again by itself: another job settling, or asking again, queues nothing.
        self.assertFalse(desk_jobs.geo_due(self.root, made['id']))
        self.assertEqual(len(self.geo_jobs(made['id'])), 1)
        # Its own proposal applied: still done. Any other change: out of date, not rerun.
        desk.dispatch(
            self.root,
            'apply',
            {'id': made['id'], 'seen': 1, 'job': found[0]['id'], 'items': [{'id': 'p1'}]},
        )
        self.assertEqual(desk_jobs.view(self.root, made['id'])['geo_review']['status'], 'done')
        draft = desk.read(self.root, made['id'])
        desk.save(self.root, made['id'], draft['revision'], 'opening', 'Changed by hand.')
        self.assertEqual(desk_jobs.view(self.root, made['id'])['geo_review']['status'], 'stale')
        self.assertEqual(len(self.geo_jobs(made['id'])), 1)

    def test_with_a_first_pass_the_review_waits_for_it(self):
        made = self.create(manuscript=DRAFT, first_pass='feedback', geo_review=True)
        self.assertEqual(self.geo_jobs(made['id']), [])
        self.assertEqual(made['geo_review']['status'], 'waiting')
        self.assertEqual(made['geo_review']['waiting'], 'busy')
        feedback = made['working']
        self.settle(feedback, json.dumps({'summary': 'Fine.', 'comments': []}))
        self.assertEqual(len(self.geo_jobs(made['id'])), 1, 'queued once the first pass settles')

    def test_a_start_runs_it_once_the_full_draft_is_written(self):
        made = self.create(way='topic', point='Retries save work.', geo_review=True)
        ident = made['id']
        outline = desk.read_start(self.root, ident)['job']
        self.assertEqual(desk_jobs.view(self.root, ident)['geo_review']['waiting'], 'draft')
        self.settle(
            {'id': outline},
            json.dumps(
                {
                    'title': 'T',
                    'opening_brief': 'Why.',
                    'sections': [
                        {'heading': 'Why jobs stop'},
                        {'heading': 'Retry from a checkpoint'},
                        {'heading': 'A last word'},
                    ],
                }
            ),
        )
        self.assertEqual(self.geo_jobs(ident), [], 'an outline is not the full draft')
        drafting = desk.read_start(self.root, ident)['job']
        self.settle({'id': drafting}, WRITTEN)
        self.assertTrue(desk.read_start(self.root, ident)['ended_at'])
        self.assertEqual(len(self.geo_jobs(ident)), 1)

    def test_the_choice_changes_on_the_desk_and_turned_on_runs_one_review(self):
        made = self.create(manuscript=DRAFT, first_pass='leave')
        ident = made['id']
        with self.assertRaisesRegex(ValueError, 'GEO review'):
            desk.dispatch(self.root, 'geo-option', {'id': ident, 'include': 'on'})
        shown = desk.dispatch(self.root, 'geo-option', {'id': ident, 'include': True})
        kept = self.record(ident)['geo_review']
        self.assertEqual((kept['include'], kept['job']), (True, self.geo_jobs(ident)[0]['id']))
        self.assertTrue(kept['queued_at'], 'the post itself says its one review was queued')
        self.assertEqual(shown['geo_review']['include'], True)
        self.assertEqual(len(self.geo_jobs(ident)), 1)
        desk_jobs.stop(self.root, ident, self.geo_jobs(ident)[0]['id'])
        desk.dispatch(self.root, 'geo-option', {'id': ident, 'include': False})
        self.assertEqual(self.record(ident)['geo_review']['include'], False)
        desk.dispatch(self.root, 'geo-option', {'id': ident, 'include': True})
        self.assertEqual(len(self.geo_jobs(ident)), 1, 'one review per post, never rerun by itself')
        # On demand, always: Run GEO review is the ordinary finishing request.
        desk.dispatch(self.root, 'finish', {'id': ident, 'seen': 1, 'tool': 'geo'})
        self.assertEqual(len(self.geo_jobs(ident)), 2)

    def test_the_one_review_is_never_queued_again_on_another_computer(self):
        import shutil

        made = self.create(manuscript=DRAFT, first_pass='leave', geo_review=True)
        ident = made['id']
        self.settle(self.geo_jobs(ident)[0], json.dumps({'suggestions': []}))
        # A teammate takes the post over: the record travels, this computer's files do not.
        shutil.rmtree(self.root / '.blog-runs' / 'desk-proposals' / ident)
        self.assertTrue(self.record(ident)['geo_review']['queued_at'])
        desk.dispatch(self.root, 'finish', {'id': ident, 'seen': 1, 'tool': 'feedback'})
        feedback = [
            job for job in desk_jobs.jobs(self.root, ident) if job['kind'] == 'finish-feedback'
        ]
        self.settle(feedback[0], json.dumps({'summary': 'Fine.', 'comments': []}))
        self.assertEqual(len(self.geo_jobs(ident)), 1, 'no second review with no button press')
        self.assertEqual(desk_jobs.view(self.root, ident)['geo_review']['status'], 'none')

    def test_turned_on_after_a_current_review_that_review_is_the_one(self):
        made = self.create(manuscript=DRAFT, first_pass='leave')
        ident = made['id']
        desk.dispatch(self.root, 'finish', {'id': ident, 'seen': 1, 'tool': 'geo'})
        self.settle(self.geo_jobs(ident)[0], json.dumps({'suggestions': []}))
        self.assertEqual(desk_jobs.view(self.root, ident)['geo_review']['due'], 'ran')
        shown = desk.dispatch(self.root, 'geo-option', {'id': ident, 'include': True})
        self.assertEqual(len(self.geo_jobs(ident)), 1, 'the current review stands for it')
        self.assertTrue(self.record(ident)['geo_review']['queued_at'])
        self.assertEqual(shown['geo_review']['status'], 'done')

    def test_a_post_the_conversation_drives_says_it_does_not_run_by_itself(self):
        made = self.create(manuscript=DRAFT, first_pass='leave')
        ident = made['id']
        directory, record = studio.item(self.root, 'articles', ident)
        record['execution'] = 'conversation'
        studio.persist(directory, 'articles', record)
        shown = desk.dispatch(self.root, 'geo-option', {'id': ident, 'include': True})
        self.assertEqual(self.geo_jobs(ident), [])
        self.assertEqual(
            (shown['geo_review']['status'], shown['geo_review']['why']), ('not-run', 'conversation')
        )
