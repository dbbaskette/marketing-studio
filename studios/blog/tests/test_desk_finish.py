"""Finishing on the desk: proposals previewed, then applied, edited or skipped."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import json
import secrets
import unittest

import blog_runner
import desk
import desk_finish
import desk_jobs
import studio
import tool_jobs
from test_desk import DRAFT, DeskCase


class FinishCase(DeskCase):
    def setUp(self):
        super().setUp()
        self.addCleanup(lambda: blog_runner.ENGINES.pop(str(self.root), None))
        self.made = desk.create(self.root, {'title': 'Synthetic', 'manuscript': DRAFT})
        self.ident = self.made['id']
        self.first, self.second = (s['id'] for s in self.made['sections'])

    def draft(self):
        return desk.read(self.root, self.ident)

    def offer(self, items, kind='finish-humanize', **extra):
        job = secrets.token_hex(16)
        desk_finish.keep(self.root, self.ident, job, kind, items, **extra)
        return job

    def act(self, action, **data):
        return desk.dispatch(self.root, action, {'id': self.ident, **data})

    def tracked(self):
        """Every file in the blog's own folder, which a team workspace records."""
        folder = self.folder(self.ident)
        return sorted(str(path.relative_to(folder)) for path in folder.rglob('*') if path.is_file())


class ProposalStoreTests(FinishCase):
    def edit(self, part=None, before='First text.', after='The first text.', **extra):
        return {'part': part or self.first, 'before': before, 'after': after, 'note': 'Plainer.'}

    def test_a_set_waits_on_this_computer_never_in_the_blogs_folder(self):
        before = self.tracked()
        job = self.offer([self.edit()])
        target = studio.inside(self.root, '.blog-runs', 'desk-proposals', self.ident, job + '.json')
        self.assertTrue(target.is_file())
        self.assertEqual(self.tracked(), before)
        found = desk_finish.read(self.root, self.ident, job)
        self.assertEqual(found['items'][0]['id'], 'p1')
        self.assertEqual(found['items'][0]['state'], 'open')
        self.assertEqual(self.draft()['sections'][0]['text'], 'First text.')

    def test_apply_swaps_the_text_and_keeps_a_finishing_version(self):
        job = self.offer([self.edit()])
        shown = self.act('apply', seen=1, job=job, items=[{'id': 'p1'}])
        self.assertEqual(shown['finished'], {'applied': 1, 'left': []})
        self.assertEqual(self.draft()['sections'][0]['text'], 'The first text.')
        kept = desk.versions(self.root, self.ident, self.first)
        self.assertEqual([(v['source'], v['text']) for v in kept], [('finishing', 'First text.')])
        self.assertIn('The first text.', (self.folder(self.ident) / 'DRAFT.md').read_text())
        self.assertEqual(
            desk_finish.read(self.root, self.ident, job)['items'][0]['state'], 'applied'
        )
        self.assertEqual(shown['finishing']['humanize']['items'][0]['state'], 'applied')

    def test_edit_applies_the_persons_own_text(self):
        job = self.offer([self.edit()])
        self.act('apply', seen=1, job=job, items=[{'id': 'p1', 'after': 'My own words.'}])
        self.assertEqual(self.draft()['sections'][0]['text'], 'My own words.')

    def test_an_edit_that_adds_a_section_or_a_second_title_line_is_refused(self):
        job = self.offer([self.edit(), self.edit('title', 'A synthetic title', 'New')])
        with self.assertRaisesRegex(ValueError, '## heading'):
            self.act('apply', seen=1, job=job, items=[{'id': 'p1', 'after': '## Extra\n\nText.'}])
        with self.assertRaisesRegex(ValueError, 'one line'):
            self.act('apply', seen=1, job=job, items=[{'id': 'p2', 'after': 'Two\nlines'}])
        self.assertEqual(self.draft()['revision'], 1)

    def test_a_suggestion_whose_text_is_gone_is_refused_with_nothing_changed(self):
        job = self.offer([self.edit()])
        desk.save(self.root, self.ident, 1, self.first, 'Rewritten by hand.')
        with self.assertRaisesRegex(ValueError, 'no longer in this part'):
            self.act('apply', seen=2, job=job, items=[{'id': 'p1'}])
        self.assertEqual(self.draft()['sections'][0]['text'], 'Rewritten by hand.')
        self.assertFalse(
            self.act('skip', job=job, items=['p1'])['finishing']['humanize']['items'][0]['present']
        )

    def test_text_that_occurs_twice_is_not_guessed(self):
        desk.save(self.root, self.ident, 1, self.first, 'Same. Same.')
        job = self.offer([self.edit(before='Same.', after='Other.')])
        with self.assertRaisesRegex(ValueError, 'no longer in this part'):
            self.act('apply', seen=2, job=job, items=[{'id': 'p1'}])

    def test_apply_all_lands_what_fits_one_version_per_part_and_counts_the_rest(self):
        desk.save(self.root, self.ident, 1, self.first, 'One. Two. Three.')
        job = self.offer(
            [
                self.edit(before='One.', after='Uno.'),
                self.edit(before='Two.', after='Dos.'),
                self.edit(before='Absent.', after='Nada.'),
                self.edit(self.second, 'Second text.', 'Segundo.'),
            ]
        )
        shown = self.act(
            'apply', seen=2, job=job, items=[{'id': 'p1'}, {'id': 'p2'}, {'id': 'p3'}, {'id': 'p4'}]
        )
        self.assertEqual(shown['finished'], {'applied': 3, 'left': ['p3']})
        draft = self.draft()
        self.assertEqual(draft['sections'][0]['text'], 'Uno. Dos. Three.')
        self.assertEqual(draft['sections'][1]['text'], 'Segundo.')
        self.assertEqual(
            [v['source'] for v in desk.versions(self.root, self.ident, self.first)],
            ['finishing', 'save'],
        )
        states = [item['state'] for item in desk_finish.read(self.root, self.ident, job)['items']]
        self.assertEqual(states, ['applied', 'applied', 'open', 'applied'])

    def test_an_outdated_form_is_refused(self):
        job = self.offer([self.edit()])
        desk.save(self.root, self.ident, 1, self.first, 'First text, typed.')
        with self.assertRaisesRegex(ValueError, 'changed since'):
            self.act('apply', seen=1, job=job, items=[{'id': 'p1'}])

    def test_typing_in_another_part_does_not_refuse_an_apply(self):
        job = self.offer([self.edit()])
        desk.save(self.root, self.ident, 1, self.second, 'Typed elsewhere.')
        self.act('apply', seen=1, job=job, items=[{'id': 'p1'}])
        self.assertEqual(self.draft()['sections'][0]['text'], 'The first text.')

    def test_apply_waits_for_a_job_working_on_that_part(self):
        job = self.offer([self.edit()])
        desk_jobs.section(self.root, self.ident, 1, self.first, 'Shorter.')
        with self.assertRaisesRegex(ValueError, 'working on this part'):
            self.act('apply', seen=1, job=job, items=[{'id': 'p1'}])

    def test_skip_sets_aside_and_writes_nothing_tracked(self):
        job = self.offer([self.edit(), self.edit(self.second, 'Second text.', 'Two.')])
        before = self.tracked()
        record = studio.read_json(self.folder(self.ident) / 'session.json')
        shown = self.act('skip', job=job, items=['p1'])
        self.assertEqual(shown['finished'], {'skipped': 1})
        self.assertEqual(
            [i['state'] for i in shown['finishing']['humanize']['items']], ['skipped', 'open']
        )
        self.assertEqual(self.tracked(), before)
        self.assertEqual(studio.read_json(self.folder(self.ident) / 'session.json'), record)
        with self.assertRaisesRegex(ValueError, 'already applied or skipped'):
            self.act('apply', seen=1, job=job, items=[{'id': 'p1'}])

    def test_unknown_sets_and_items_are_refused_readably(self):
        job = self.offer([self.edit()])
        with self.assertRaisesRegex(ValueError, 'no longer here'):
            self.act('apply', seen=1, job=secrets.token_hex(16), items=[{'id': 'p1'}])
        with self.assertRaisesRegex(ValueError, 'Choose a set'):
            self.act('apply', seen=1, job='../x', items=[{'id': 'p1'}])
        with self.assertRaisesRegex(ValueError, 'from this set'):
            self.act('apply', seen=1, job=job, items=[{'id': 'p9'}])
        with self.assertRaisesRegex(ValueError, 'from this set'):
            self.act('apply', seen=1, job=job, items=[{'id': 'p1'}, {'id': 'p1'}])
        with self.assertRaisesRegex(ValueError, 'fields the desk does not take'):
            self.act('apply', seen=1, job=job, items=[{'id': 'p1'}], extra=True)

    def test_the_view_shows_the_newest_set_for_each_tool(self):
        self.offer([self.edit(after='Older.')])
        self.offer([self.edit(after='Newer.')])
        self.offer(
            [{'part': 'whole', 'quote': '', 'aspect': 'shape', 'comment': 'C.'}], 'finish-feedback'
        )
        shown = desk_jobs.view(self.root, self.ident)['finishing']
        self.assertEqual(sorted(shown), ['feedback', 'humanize'])
        self.assertEqual(shown['humanize']['items'][0]['after'], 'Newer.')
        self.assertTrue(shown['humanize']['items'][0]['present'])

    def test_a_comment_is_never_applied(self):
        job = self.offer(
            [{'part': self.first, 'quote': 'First', 'aspect': 'argument', 'comment': 'Why?'}],
            'finish-feedback',
        )
        with self.assertRaisesRegex(ValueError, 'Make it a note'):
            self.act('apply', seen=1, job=job, items=[{'id': 'p1'}])
        self.assertEqual(
            self.act('skip', job=job, items=['p1'])['finishing']['feedback']['items'][0]['state'],
            'skipped',
        )

    def test_deleting_the_blog_forgets_its_suggestions(self):
        import blog_delete

        job = self.offer([self.edit()])
        blog_delete._forget(self.root, self.ident)
        self.assertFalse(
            studio.inside(self.root, '.blog-runs', 'desk-proposals', self.ident).exists()
        )
        with self.assertRaisesRegex(ValueError, 'no longer here'):
            desk_finish.read(self.root, self.ident, job)


PROSE = """# A synthetic title

We leverage the parser — it reads every file. It is quick. It is small.

## Setup

Moreover, the installer checks tools. The `leverage` flag stays in code, and "leverage" in a quote.

The registry, the registry client and the registry cache all read one file.

## Usage

Moreover, the installer checks tools. The `leverage` flag stays in code, and "leverage" in a quote.
"""


class ProofreadTests(FinishCase):
    def setUp(self):
        super().setUp()
        self.ident = desk.create(self.root, {'title': 'Prose', 'manuscript': PROSE})['id']
        self.parts = desk.read(self.root, self.ident)

    def found(self):
        return desk_finish.proofread(self.root, self.ident)['findings']

    def rules(self, part):
        return [f['rule'] for f in self.found() if f['part'] == part]

    def test_each_finding_names_its_part_and_the_sentence_fix_rewrites(self):
        found = self.found()
        opening = [f for f in found if f['part'] == 'opening']
        dash = next(f for f in opening if f['rule'] == 'em-dash')
        self.assertEqual(dash['sentence'], 'We leverage the parser — it reads every file.')
        self.assertEqual(dash['start'], 0)
        word = next(f for f in opening if f['rule'] == 'banished:leverage')
        self.assertEqual(word['target'], 'leverage')
        self.assertIn('machine-written', word['label'])
        self.assertIn('leverage', word['fix'])
        again = next(f for f in opening if f['rule'] == 'repeated-start')
        self.assertEqual(again['sentence'], 'It is small.')
        text = self.parts['opening']
        self.assertEqual(
            text[again['start'] : again['start'] + len(again['sentence'])], again['sentence']
        )

    def test_code_and_quotations_are_left_out(self):
        setup = self.parts['sections'][0]
        hits = [
            f for f in self.found() if f['part'] == setup['id'] and f['rule'] == 'banished:leverage'
        ]
        self.assertEqual(hits, [])

    def test_ai_openers_repeated_words_and_repeats_across_sections_are_found(self):
        setup, usage = (s['id'] for s in self.parts['sections'])
        self.assertIn('ai-starter', self.rules(setup))
        self.assertIn('repeated-word', self.rules(setup))
        self.assertIn('echoed-opener', self.rules(usage))
        self.assertIn('duplicate-paragraph', self.rules(usage))

    def test_findings_follow_the_draft_order(self):
        order = ['title', 'opening'] + [s['id'] for s in self.parts['sections']]
        seen = [order.index(f['part']) for f in self.found()]
        self.assertEqual(seen, sorted(seen))

    def test_the_view_writes_nothing(self):
        import management

        folder = self.folder(self.ident)
        before = {p: p.read_bytes() for p in folder.rglob('*') if p.is_file()}
        shown = management.view(self.root, 'desk-proofread', {'id': [self.ident]})
        self.assertTrue(shown['findings'])
        self.assertEqual({p: p.read_bytes() for p in folder.rglob('*') if p.is_file()}, before)
        self.assertEqual(desk_jobs.jobs(self.root, self.ident), [])

    def test_fix_carries_the_finding_and_still_replaces_only_the_sentence(self):
        import tool_jobs

        dash = next(f for f in self.found() if f['rule'] == 'em-dash')
        job = desk_jobs.selection(
            self.root, self.ident, 1, 'opening', dash['sentence'], 'fix', dash['fix'], dash['start']
        )
        saved = tool_jobs.read(self.root, job['id'])
        self.assertIn('PROOFREAD FINDING TO FIX', saved['guidance'])
        self.assertIn(dash['fix'], saved['guidance'])
        self.assertIn(desk_jobs.ACTIONS['fix'], saved['guidance'])
        saved.update(
            status='ready',
            result={'content': 'We use the parser, which reads every file.', 'notes': ''},
        )
        tool_jobs.write(self.root, saved)
        desk_jobs.settle(self.root, self.ident)
        self.assertEqual(
            desk.read(self.root, self.ident)['opening'],
            'We use the parser, which reads every file. It is quick. It is small.',
        )

    def test_a_plain_draft_has_nothing_to_find(self):
        self.assertEqual(desk_finish.proofread(self.root, self.made['id'])['findings'], [])


class ToolCase(FinishCase):
    def setUp(self):
        super().setUp()
        desk.save(
            self.root,
            self.ident,
            1,
            self.first,
            'We leverage a robust parser. It reads 12 files in 3 seconds at Acme Labs.',
        )
        self.seen = 2

    def queue(self, tool, **extra):
        shown = desk.dispatch(
            self.root, 'finish', {'id': self.ident, 'seen': self.seen, 'tool': tool, **extra}
        )
        return tool_jobs.read(self.root, shown['working']['id'])

    def ready(self, job, value):
        content = value if isinstance(value, str) else json.dumps(value)
        job.update(status='ready', result={'content': content, 'notes': ''}, finished_at='x')
        tool_jobs.write(self.root, job)
        desk_jobs.settle(self.root, self.ident)
        return tool_jobs.read(self.root, job['id'])

    def shown(self, tool):
        return desk_jobs.view(self.root, self.ident)['finishing'][tool]


class HumanizeTests(ToolCase):
    def test_guidance_holds_the_humanize_guide_and_the_level(self):
        job = self.queue('humanize', level='medium')
        self.assertEqual(job['kind'], 'finish-humanize')
        self.assertIn('Humanization capability', job['guidance'])
        self.assertIn(desk_finish.LEVELS['medium'], job['guidance'])
        self.assertIn('"suggestions"', job['guidance'])
        self.assertIn(blog_runner.house_guide(), job['guidance'])
        self.assertEqual(job['payload']['level'], 'medium')
        self.assertEqual([s['id'] for s in job['payload']['sections']], [self.first, self.second])
        self.assertNotIn('response_kind', job['payload'])
        self.assertEqual(job['metadata']['desk']['part'], 'finishing')
        with self.assertRaisesRegex(ValueError, 'light, medium or strong'):
            desk_jobs.stop(self.root, self.ident, job['id'])
            self.queue('humanize', level='loud')

    def test_a_ready_result_lands_as_proposals_and_the_draft_is_unchanged(self):
        before = self.draft()
        job = self.ready(
            self.queue('humanize', level='light'),
            {
                'suggestions': [
                    {
                        'part': self.first,
                        'before': 'We leverage a robust parser.',
                        'after': 'We use a sturdy parser.',
                        'why': 'Stock words.',
                    },
                    {'part': self.first, 'before': 'Not in the text.', 'after': 'X.', 'why': ''},
                    {'part': 'zzzzzzzz', 'before': 'Second text.', 'after': 'Y.', 'why': ''},
                    {'part': self.second, 'before': 'Second text.', 'after': 'Second text.'},
                ]
            },
        )
        self.assertTrue(job['applied'])
        self.assertEqual(self.draft()['revision'], before['revision'])
        shown = self.shown('humanize')
        self.assertEqual(shown['level'], 'light')
        self.assertEqual(shown['dropped'], 3)
        self.assertEqual(
            [(i['before'], i['after'], i['flag']) for i in shown['items']],
            [('We leverage a robust parser.', 'We use a sturdy parser.', '')],
        )

    def test_a_changed_number_or_name_is_flagged(self):
        self.ready(
            self.queue('humanize', level='strong'),
            {
                'suggestions': [
                    {
                        'part': self.first,
                        'before': 'It reads 12 files in 3 seconds at Acme Labs.',
                        'after': 'It reads 15 files in 3 seconds at Acme Labs.',
                    },
                    {
                        'part': self.first,
                        'before': 'We leverage a robust parser.',
                        'after': 'We at Beta Works use a parser.',
                    },
                ]
            },
        )
        flags = [i['flag'] for i in self.shown('humanize')['items']]
        self.assertIn('a number', flags[0])
        self.assertEqual(flags[1], '')
        self.assertIn('a name', desk_finish.changes_facts('Ask Acme Labs.', 'Ask the lab.'))

    def test_a_result_that_is_not_the_json_asked_for_is_refused_readably(self):
        job = self.ready(self.queue('humanize', level='light'), 'Here are my thoughts.')
        self.assertFalse(job['applied'])
        self.assertEqual(job['error'], desk_finish.UNREADABLE)
        self.assertNotIn('humanize', desk_jobs.view(self.root, self.ident)['finishing'])

    def test_a_humanize_job_leaves_every_card_editable_and_the_outline_open(self):
        self.queue('humanize', level='light')
        shown = desk_jobs.view(self.root, self.ident)
        self.assertEqual(shown['working']['part'], 'finishing')
        desk.save(self.root, self.ident, self.seen, self.second, 'Typed while it works.')
        desk.outline_save(
            self.root,
            self.ident,
            self.seen + 1,
            [
                {'id': self.second, 'heading': 'Renamed', 'brief': ''},
                {'id': self.first, 'heading': 'First part', 'brief': ''},
            ],
        )
        with self.assertRaisesRegex(ValueError, 'already working'):
            desk_jobs.section(self.root, self.ident, self.seen + 2, self.first, 'More.')

    def test_nothing_written_yet_is_refused(self):
        made = desk.create(self.root, {'title': 'Empty', 'way': 'topic', 'point': 'A point.'})
        with self.assertRaisesRegex(ValueError, 'Write the draft first'):
            desk_jobs.finish(self.root, made['id'], 1, 'humanize', 'light')

    def test_a_fake_worker_runs_it_end_to_end_and_apply_keeps_a_version(self):
        calls = []

        def worker(engine, payload, guidance, **options):
            calls.append(options)
            return {
                'content': json.dumps(
                    {
                        'suggestions': [
                            {
                                'part': self.first,
                                'before': 'We leverage a robust parser.',
                                'after': 'We use a sturdy parser.',
                                'why': 'Stock words.',
                            }
                        ]
                    }
                ),
                'notes': '',
            }

        job = self.queue('humanize', level='light')
        tool_jobs.once(blog_runner.Engine(self.root, worker=worker))
        self.assertEqual(calls[0]['web'], False)
        self.assertTrue(tool_jobs.read(self.root, job['id'])['settled_at'])
        self.act('apply', seen=self.seen, job=job['id'], items=[{'id': 'p1'}])
        self.assertTrue(self.draft()['sections'][0]['text'].startswith('We use a sturdy parser.'))
        kept = desk.versions(self.root, self.ident, self.first)[0]
        self.assertEqual(kept['source'], 'finishing')
        self.assertTrue(kept['text'].startswith('We leverage'))


class FactsTests(ToolCase):
    def test_no_sources_and_no_research_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'Add a source first'):
            self.queue('facts')

    def sourced(self):
        fact = self.source('The parser reads 12 files in 3 seconds.')
        desk.add_sources(self.root, self.ident, {'sources': [fact]})
        self.seen = desk.read(self.root, self.ident)['revision']

    def test_the_payload_carries_the_desks_sources_and_the_fact_check_rules(self):
        import manuscript_editor

        self.sourced()
        job = self.queue('facts')
        self.assertEqual(job['kind'], 'finish-facts')
        self.assertEqual(
            [(s['name'], s['text']) for s in job['payload']['sources']],
            [('Synthetic source', 'The parser reads 12 files in 3 seconds.')],
        )
        self.assertIn(manuscript_editor.CHECKS['factual-support'], job['guidance'])
        self.assertIn('"verdict"', job['guidance'])
        self.assertIn('not-in-sources', job['guidance'])

    def test_research_counts_as_something_to_check_against(self):
        report = self.folder(self.ident) / 'derived' / 'blog-research.md'
        report.parent.mkdir(exist_ok=True)
        report.write_text('Research: the parser is quick.')
        job = self.queue('facts')
        self.assertEqual(job['payload']['research'], 'Research: the parser is quick.')

    def test_verdicts_passages_and_rewordings_land_and_odd_claims_are_dropped(self):
        self.sourced()
        self.ready(
            self.queue('facts'),
            {
                'claims': [
                    {
                        'part': self.first,
                        'before': 'It reads 12 files in 3 seconds at Acme Labs.',
                        'verdict': 'supported',
                        'passage': 'The parser reads 12 files in 3 seconds.',
                        'source': 'Synthetic source',
                        'after': 'Ignored for a supported claim.',
                    },
                    {
                        'part': self.first,
                        'before': 'We leverage a robust parser.',
                        'verdict': 'not-in-sources',
                        'passage': '',
                        'after': 'We use a parser.',
                        'why': 'No source says robust.',
                    },
                    {'part': self.second, 'before': 'Second text.', 'verdict': 'contradicted'},
                    {'part': self.second, 'before': 'Second text.', 'verdict': 'probably'},
                    {'part': self.first, 'before': 'Not there.', 'verdict': 'supported'},
                ]
            },
        )
        shown = self.shown('facts')
        self.assertEqual(shown['dropped'], 2)
        self.assertEqual(
            [i['verdict'] for i in shown['items']], ['contradicted', 'not-in-sources', 'supported']
        )
        contradicted, missing, supported = shown['items']
        self.assertNotIn('after', supported)
        self.assertEqual(supported['passage'], 'The parser reads 12 files in 3 seconds.')
        self.assertEqual(missing['after'], 'We use a parser.')
        self.assertNotIn('after', contradicted)
        job = shown['job']
        with self.assertRaisesRegex(ValueError, 'Write the wording'):
            self.act('apply', seen=self.seen, job=job, items=[{'id': contradicted['id']}])
        self.act('apply', seen=self.seen, job=job, items=[{'id': missing['id']}])
        self.assertTrue(self.draft()['sections'][0]['text'].startswith('We use a parser.'))
        self.assertEqual(desk.versions(self.root, self.ident, self.first)[0]['source'], 'finishing')
        # Fix the wording of a claim with no rewording: the person's own words.
        self.act(
            'apply',
            seen=self.draft()['revision'],
            job=job,
            items=[{'id': contradicted['id'], 'after': 'Second text, as the source says.'}],
        )
        self.assertEqual(self.draft()['sections'][1]['text'], 'Second text, as the source says.')


class HeadlineTests(ToolCase):
    def alternatives(self):
        return {
            'titles': [
                {'text': 'How the parser reads twelve files', 'why': 'Concrete.'},
                {'text': '# A parser worth knowing', 'why': 'Shorter.'},
                {'text': 'Two\nlines', 'why': ''},
                {'text': 'A synthetic title', 'why': 'Same as now.'},
            ],
            'openings': [
                {'text': 'Twelve files, three seconds.', 'why': 'Starts with the number.'},
                {'text': 'Intro\n\n## Extra', 'why': ''},
            ],
        }

    def test_guidance_is_the_headline_lab_and_the_brief(self):
        job = self.queue('headline')
        self.assertEqual(job['kind'], 'finish-headline')
        self.assertIn('Headline and hook lab', job['guidance'])
        self.assertIn('"titles"', job['guidance'])
        self.assertEqual(job['payload']['title'], 'A synthetic title')

    def test_alternatives_land_grouped_by_part_and_odd_ones_are_dropped(self):
        self.ready(self.queue('headline'), self.alternatives())
        shown = self.shown('headline')
        self.assertEqual(shown['dropped'], 3)
        self.assertEqual(
            [(i['group'], i['after']) for i in shown['items']],
            [
                ('title', 'How the parser reads twelve files'),
                ('title', 'A parser worth knowing'),
                ('opening', 'Twelve files, three seconds.'),
            ],
        )
        self.assertTrue(all(i['whole'] and i['present'] for i in shown['items']))

    def test_applying_one_alternative_skips_the_others_for_that_part(self):
        self.ready(self.queue('headline'), self.alternatives())
        job = self.shown('headline')['job']
        self.act('apply', seen=self.seen, job=job, items=[{'id': 'p2'}])
        self.assertEqual(self.draft()['title'], 'A parser worth knowing')
        self.assertEqual(
            desk.versions(self.root, self.ident, 'title')[0]['text'], 'A synthetic title'
        )
        states = [i['state'] for i in self.shown('headline')['items']]
        self.assertEqual(states, ['skipped', 'applied', 'open'])

    def test_a_part_changed_since_makes_its_alternatives_no_longer_fit(self):
        self.ready(self.queue('headline'), self.alternatives())
        desk.save(self.root, self.ident, self.seen, 'opening', 'Typed a new opening.')
        items = self.shown('headline')['items']
        self.assertEqual([i['present'] for i in items], [True, True, False])
        with self.assertRaisesRegex(ValueError, 'no longer in this part'):
            self.act(
                'apply', seen=self.seen + 1, job=self.shown('headline')['job'], items=[{'id': 'p3'}]
            )


if __name__ == '__main__':
    unittest.main()
