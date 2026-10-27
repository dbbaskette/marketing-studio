"""Finishing on the desk: proposals previewed, then applied, edited or skipped."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import json
from pathlib import Path
import secrets
import tempfile
import unittest

import blog_runner
import desk
import desk_finish
import desk_jobs
import studio
import tool_jobs
from test_desk import DRAFT, GOOGLE, IMAGE_ONE, IMAGE_TWO, DeskCase
from test_desk_team import TeamCase


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
        with self.assertRaisesRegex(ValueError, 'fields the page does not take'):
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
        sent = studio.inside(self.root, '.blog-runs', 'desk-google', self.ident + '.json')
        studio.write_json(sent, {'plans': {}, 'sent': [{'id': 'desk-x', 'paragraph': 'y'}]})
        blog_delete._forget(self.root, self.ident)
        self.assertFalse(sent.exists(), 'what was sent to its Doc goes too')
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

    def test_findings_sit_in_their_sections_at_any_heading_level(self):
        text = (
            '# Levels\n\nOpen.\n\n### **One**\n\nFirst.\n\n### **Two**\n\nWe leverage it — twice.\n'
        )
        ident = desk.create(self.root, {'manuscript': text})['id']
        draft = desk.read(self.root, ident)
        found = desk_finish.proofread(self.root, ident)['findings']
        self.assertTrue(found)
        for finding in found:
            part = desk.text_of(draft, finding['part'])
            self.assertEqual(
                part[finding['start'] : finding['start'] + len(finding['sentence'])],
                finding['sentence'],
            )
        self.assertEqual({f['part'] for f in found}, {draft['sections'][1]['id']})
        word = next(f for f in found if f['rule'] == 'banished:leverage')
        self.assertEqual(word['target'], 'leverage')
        part = draft['sections'][1]['text']
        self.assertEqual(part[word['at'] : word['at'] + len('leverage')], 'leverage')

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

    def test_humanize_flags_a_changed_code_span(self):
        desk.save(self.root, self.ident, self.seen, self.second, 'Use `run --fast` here.')
        self.seen += 1
        self.ready(
            self.queue('humanize', level='light'),
            {
                'suggestions': [
                    {
                        'part': self.second,
                        'before': 'Use `run --fast` here.',
                        'after': 'Use `run --slow` now.',
                    }
                ]
            },
        )
        self.assertIn(desk_finish.STRUCTURE, self.shown('humanize')['items'][0]['flag'])

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


class CopyEditTests(ToolCase):
    """Copy edit: grammar, spelling, punctuation, consistency, clarity and concision fixes,
    each a located sentence the person approves before it lands."""

    def setUp(self):
        super().setUp()
        desk.save(
            self.root,
            self.ident,
            self.seen,
            self.second,
            'Their are two parser. Use `run --fast` to start it.',
        )
        self.seen += 1

    def fix(self, before, after, part=None, why='Grammar.'):
        return {'part': part or self.second, 'before': before, 'after': after, 'why': why}

    def test_payload_and_guidance_are_the_copy_editing_rules(self):
        job = self.queue('copyedit')
        self.assertEqual(job['kind'], 'finish-copyedit')
        self.assertIn(desk_jobs.desk_check('copyedit'), job['guidance'])
        self.assertIn(desk_jobs.desk_check('proofread'), job['guidance'])
        self.assertIn(desk_finish.COPYEDIT, job['guidance'])
        self.assertIn('"suggestions"', job['guidance'])
        self.assertIn(blog_runner.house_guide(), job['guidance'])
        for kept in ('voice', 'quotation', 'link', 'image reference'):
            self.assertIn(kept, desk_finish.COPYEDIT)
        self.assertEqual([s['id'] for s in job['payload']['sections']], [self.first, self.second])
        self.assertEqual(job['payload']['opening'], 'An opening paragraph.')
        self.assertNotIn('response_kind', job['payload'])
        self.assertNotIn('level', job['payload'])
        self.assertEqual(job['metadata']['desk']['part'], 'finishing')
        self.assertEqual(job['metadata']['desk']['action'], 'copyedit')
        self.assertIn('finish-copyedit', desk_jobs.KINDS)
        self.assertIn('finish-copyedit', desk_jobs.FINISH)
        self.assertIn('finish-copyedit', tool_jobs.KINDS)
        self.assertIn('finish-copyedit', tool_jobs.DESK)
        self.assertEqual(desk_finish.TOOLS['finish-copyedit'], 'copyedit')

    def test_only_the_copy_editing_lenses_and_no_sources_or_examples_are_sent(self):
        fact = self.source('A synthetic source on how the parser was benchmarked.')
        desk.add_sources(self.root, self.ident, {'sources': [fact]})
        self.seen = desk.read(self.root, self.ident)['revision']
        self.assertTrue(self.draft()['sources'])
        job = self.queue('copyedit')
        for left_out in ('sources', 'examples', 'style', 'research', 'gaps'):
            self.assertNotIn(left_out, job['payload'])
        self.assertNotIn('benchmarked', json.dumps(job['payload']))
        guidance = job['guidance']
        # Clarity and voice from the copy-editing guide, and none of its broader lenses.
        self.assertIn('**Clarity:**', guidance)
        self.assertIn('**Voice:**', guidance)
        for lens in (
            '**Evidence:**',
            '**Persuasion',
            '**Structure:**',
            '**Reader relevance:**',
            '**Specificity:**',
            'Make useful repairs',
            'developmental feedback',
        ):
            self.assertNotIn(lens, guidance)
        # Before the house guide every desk job shares, nothing points to sources.
        own = guidance.split(blog_runner.house_guide())[0]
        self.assertNotIn('source', own.lower())
        self.assertNotIn('examples show', guidance)
        # Claims, qualifiers and the argument stay; the desk has no pinned author rules.
        for kept in ('claim', 'qualifier', 'argument'):
            self.assertIn(kept, desk_finish.COPYEDIT)
        self.assertNotIn('pinned author', guidance)

    def test_desk_jobs_never_mention_pinned_author_rules(self):
        import manuscript_editor

        for name in ('copyedit', 'proofread'):
            self.assertIn('pinned author', manuscript_editor.CHECKS[name])
            self.assertNotIn('pinned author', desk_jobs.desk_check(name))
            self.assertIn('house rules', desk_jobs.desk_check(name))
        tighten = desk_jobs.first_pass(self.root, self.ident, self.seen, 'tighten')
        self.assertNotIn('pinned author', tool_jobs.read(self.root, tighten['id'])['guidance'])

    def test_the_title_can_be_fixed_by_copy_edit_but_not_humanize(self):
        self.assertIn('"title"', desk_finish.COPYEDIT_JSON)
        draft = self.draft()
        title = draft['title']
        found = {
            'suggestions': [
                {'part': 'title', 'before': 'synthetic', 'after': 'Synthetic', 'why': 'Case.'},
                {'part': 'title', 'before': title, 'after': 'Two\nlines', 'why': ''},
            ]
        }
        items, dropped, _ = desk_finish._read_copyedit(draft, found)
        self.assertEqual([(i['part'], i['after']) for i in items], [('title', 'Synthetic')])
        self.assertEqual(dropped, 1)
        items, dropped, _ = desk_finish._read_humanize(draft, found)
        self.assertEqual((items, dropped), ([], 2))
        job = self.offer(
            [{'part': 'title', 'before': title, 'after': 'A synthetic title, fixed'}],
            kind='finish-copyedit',
        )
        self.act('apply', seen=self.seen, job=job, items=[{'id': 'p1'}])
        self.assertEqual(self.draft()['title'], 'A synthetic title, fixed')
        self.assertEqual(desk.versions(self.root, self.ident, 'title')[0]['source'], 'finishing')
        # A title fix, suggested or edited, never brings image data into the title.
        title = self.draft()['title']
        pasted = 'A synthetic title ![][image9] [image9]: <' + IMAGE_TWO + '>'
        job = self.offer(
            [
                {'part': 'title', 'before': title, 'after': pasted},
                {'part': 'title', 'before': 'title', 'after': 'heading'},
            ],
            kind='finish-copyedit',
        )
        seen = self.draft()['revision']
        with self.assertRaisesRegex(ValueError, 'Keep images out of the title'):
            self.act('apply', seen=seen, job=job, items=[{'id': 'p1'}])
        with self.assertRaisesRegex(ValueError, 'Keep images out of the title'):
            self.act('apply', seen=seen, job=job, items=[{'id': 'p2', 'after': pasted}])
        self.assertEqual(self.draft()['title'], title)
        shown = self.act('apply', seen=seen, job=job, items=[{'id': 'p1'}, {'id': 'p2'}])
        # The one left takes in the word the other changed, and waits.
        self.assertEqual(shown['finished'], {'applied': 1, 'left': ['p1'], 'carried': 1})
        self.assertEqual(self.draft()['title'], 'A synthetic heading, fixed')
        self.assertNotIn('data:image', json.dumps(self.draft()))

    def test_a_text_found_twice_overlapping_is_not_once(self):
        desk.save(self.root, self.ident, self.seen, self.second, 'Go, go, go, go.')
        self.seen += 1
        draft = self.draft()
        self.assertEqual(draft['sections'][1]['text'].count('go, go'), 1)  # Overlaps twice.
        self.assertFalse(desk_finish._once('Go, go, go, go.', 'go, go'))
        self.assertTrue(desk_finish._once('Go, go, go, go.', 'Go, go'))
        self.assertIsNone(desk_finish._located(draft, self.second, 'go, go'))
        row = {'part': self.second, 'before': 'go, go', 'after': 'go', 'why': ''}
        self.assertEqual(desk_finish._read_copyedit(draft, {'suggestions': [row]})[1], 1)
        self.assertEqual(desk_finish._read_humanize(draft, {'suggestions': [row]})[1], 1)
        claim = {'part': self.second, 'before': 'go, go', 'verdict': 'supported'}
        self.assertEqual(desk_finish._read_facts(draft, {'claims': [claim]})[1], 1)
        item = {'part': self.second, 'before': 'go, go', 'after': 'go'}
        self.assertFalse(desk_finish.present(draft, item))
        job = self.offer([item], kind='finish-copyedit')
        with self.assertRaisesRegex(ValueError, 'no longer in this part'):
            self.act('apply', seen=self.seen, job=job, items=[{'id': 'p1'}])
        self.assertEqual(self.draft()['sections'][1]['text'], 'Go, go, go, go.')

    def test_no_sources_are_needed_but_written_text_is(self):
        self.assertEqual(self.draft()['sources'], [])
        self.assertEqual(self.queue('copyedit')['kind'], 'finish-copyedit')
        made = desk.create(self.root, {'title': 'Empty', 'way': 'topic', 'point': 'A point.'})
        with self.assertRaisesRegex(ValueError, 'Write the draft first'):
            desk_jobs.finish(self.root, made['id'], 1, 'copyedit')

    def test_a_result_is_read_strictly(self):
        draft = self.draft()

        def settle(value):
            job = {
                'id': secrets.token_hex(16),
                'kind': 'finish-copyedit',
                'result': {'content': value if isinstance(value, str) else json.dumps(value)},
                'metadata': {},
            }
            return desk_finish.settle(self.root, self.ident, draft, job)

        for value in (
            'Here are my edits.',
            [1, 2],
            {'edits': []},
            {'suggestions': 'all of them'},
            {'suggestions': [None, 3]},
            {'suggestions': [{'part': ['x'], 'before': 'A.', 'after': 'B.'}]},
            {'suggestions': [{'part': self.second, 'before': 'Their are two parser.'}]},
        ):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'cannot read'):
                settle(value)
        self.assertNotIn('copyedit', desk_jobs.view(self.root, self.ident)['finishing'])
        # Fenced JSON is read; an odd row among good ones is dropped and counted.
        kept = settle(
            '```json\n'
            + json.dumps(
                {
                    'suggestions': [
                        {'part': 7},
                        self.fix('Their are two parser.', 'There are two parsers.'),
                    ]
                }
            )
            + '\n```'
        )
        self.assertEqual((len(kept['items']), kept['dropped']), (1, 1))
        self.assertEqual(kept['kind'], 'finish-copyedit')

    def test_a_before_not_in_its_part_and_other_odd_rows_are_dropped(self):
        before = self.draft()
        self.ready(
            self.queue('copyedit'),
            {
                'suggestions': [
                    self.fix('Their are two parser.', 'There are two parsers.', why='Agreement.'),
                    self.fix('Not in the text.', 'X.'),
                    self.fix('Their are two parser.', 'There are two parsers.', part=self.first),
                    self.fix('Second text.', 'Y.', part='zzzzzzzz'),
                    self.fix('Their are two parser.', 'There are two parsers!'),  # Twice.
                    self.fix('An opening paragraph.', 'An opening paragraph.', part='opening'),
                    self.fix('An opening paragraph.', '## A heading\n\nText.', part='opening'),
                ]
            },
        )
        self.assertEqual(self.draft()['revision'], before['revision'])
        shown = self.shown('copyedit')
        self.assertEqual(shown['dropped'], 6)
        self.assertEqual(
            [(i['part'], i['before'], i['after'], i['note'], i['flag']) for i in shown['items']],
            [(self.second, 'Their are two parser.', 'There are two parsers.', 'Agreement.', '')],
        )
        self.assertTrue(shown['items'][0]['present'])

    def test_a_changed_fact_code_or_shape_is_flagged(self):
        self.ready(
            self.queue('copyedit'),
            {
                'suggestions': [
                    self.fix(
                        'It reads 12 files in 3 seconds at Acme Labs.',
                        'It reads 15 files in 3 seconds at Acme Labs.',
                        part=self.first,
                    ),
                    self.fix('We leverage a robust parser.', 'We use a parser.', part=self.first),
                    self.fix('Use `run --fast` to start it.', 'Use `run --slow` to start it.'),
                    self.fix('Their are two parser.', 'There are two parsers.\n\n- One more.'),
                ]
            },
        )
        flags = [i['flag'] for i in self.shown('copyedit')['items']]
        self.assertIn('a number', flags[0])
        self.assertEqual(flags[1], '')
        self.assertIn(desk_finish.STRUCTURE, flags[2])
        self.assertIn(desk_finish.STRUCTURE, flags[3])

    def test_a_fake_worker_runs_it_end_to_end_and_apply_keeps_a_version(self):
        calls = []

        def worker(engine, payload, guidance, **options):
            calls.append(options)
            return {
                'content': json.dumps(
                    {
                        'suggestions': [
                            self.fix('Their are two parser.', 'There are two parsers.'),
                            self.fix(
                                'We leverage a robust parser.',
                                'We use a sturdy parser.',
                                part=self.first,
                            ),
                        ]
                    }
                ),
                'notes': '',
            }

        job = self.queue('copyedit')
        tool_jobs.once(blog_runner.Engine(self.root, worker=worker))
        self.assertEqual(calls[0]['web'], False)
        self.assertTrue(tool_jobs.read(self.root, job['id'])['settled_at'])
        self.assertEqual(self.draft()['revision'], self.seen, 'nothing lands before Apply')
        shown = self.act('apply', seen=self.seen, job=job['id'], items=[{'id': 'p1'}])
        self.assertEqual(shown['finished'], {'applied': 1, 'left': []})
        self.assertEqual(
            self.draft()['sections'][1]['text'],
            'There are two parsers. Use `run --fast` to start it.',
        )
        kept = desk.versions(self.root, self.ident, self.second)[0]
        self.assertEqual(kept['source'], 'finishing')
        self.assertTrue(kept['text'].startswith('Their are two parser.'))
        # Edit applies the person's own wording; Skip changes nothing in the draft.
        revision = self.draft()['revision']
        self.act('skip', job=job['id'], items=['p2'])
        self.assertEqual(self.draft()['revision'], revision)
        items = self.shown('copyedit')['items']
        self.assertEqual([i['state'] for i in items], ['applied', 'skipped'])

    def test_no_image_data_reaches_the_job(self):
        from test_desk import GOOGLE as WITH_IMAGES

        made = desk.create(self.root, {'manuscript': WITH_IMAGES})
        shown = desk.dispatch(
            self.root, 'finish', {'id': made['id'], 'seen': 1, 'tool': 'copyedit'}
        )
        job = tool_jobs.read(self.root, shown['working']['id'])
        self.assertEqual(job['kind'], 'finish-copyedit')
        self.assertNotIn('data:image', json.dumps(job['payload']))
        self.assertNotIn('data:image', job['guidance'])
        self.assertNotIn(IMAGE_TWO, json.dumps(job))
        self.assertIn('![][image1]', job['payload']['opening'])
        self.assertIn('![…][imageN]', job['guidance'])


class ReviewTests(ToolCase):
    """Check spelling and grammar: Copy edit's fixes accepted, rejected, accepted all at once
    (a flagged one left), and a paragraph edited in place, through the page's routes."""

    def setUp(self):
        super().setUp()
        desk.save(
            self.root,
            self.ident,
            self.seen,
            self.second,
            'Their are two parser.\n\nIt read every files. It is quick.',
        )
        self.seen += 1

    def post(self, route, **data):
        import management

        return management.dispatch(self.root, route, {'id': self.ident, **data})

    def test_accept_reject_accept_all_and_a_paragraph_edit_through_the_routes(self):
        job = self.queue('copyedit')
        rows = [
            ('Their are two parser.', 'There are two parsers.', self.second),
            ('It read every files.', 'It reads every file.', self.second),
            (
                'It reads 12 files in 3 seconds at Acme Labs.',
                'It reads 14 files in 3 seconds at Acme Labs.',
                self.first,
            ),
            ('We leverage a robust parser.', 'We use a robust parser.', self.first),
        ]
        self.ready(
            job,
            {
                'suggestions': [
                    {'part': part, 'before': before, 'after': after, 'why': 'A fix.'}
                    for before, after, part in rows
                ]
            },
        )
        items = self.shown('copyedit')['items']
        self.assertEqual(
            [(i['id'], i['part']) for i in items][::2], [('p1', self.second), ('p3', self.first)]
        )
        flagged = [i['id'] for i in items if i['flag']]
        self.assertEqual(flagged, ['p3'])
        # A paragraph edited in place: the fix in it no longer fits; the others still do.
        shown = self.post(
            'desk-save',
            seen=self.seen,
            part=self.second,
            text='Their are two parser.\n\nIt reads each file. It is quick.',
            session='a' * 16,
        )
        present = {i['id']: i['present'] for i in shown['finishing']['copyedit']['items']}
        self.assertEqual(present, {'p1': True, 'p2': False, 'p3': True, 'p4': True})
        with self.assertRaisesRegex(ValueError, 'no longer in this part'):
            self.post('desk-apply', seen=shown['revision'], job=job['id'], items=[{'id': 'p2'}])
        # Accept all, as the page sends it: open, still fitting and not flagged.
        ready = [
            {'id': i['id']}
            for i in shown['finishing']['copyedit']['items']
            if i['state'] == 'open' and i['present'] and not i['flag']
        ]
        self.assertEqual(ready, [{'id': 'p1'}, {'id': 'p4'}])
        done = self.post('desk-apply', seen=shown['revision'], job=job['id'], items=ready)
        self.assertEqual(done['finished'], {'applied': 2, 'left': []})
        self.assertEqual(
            self.draft()['sections'][1]['text'],
            'There are two parsers.\n\nIt reads each file. It is quick.',
        )
        self.assertTrue(self.draft()['sections'][0]['text'].startswith('We use a robust parser.'))
        self.assertEqual(
            desk.versions(self.root, self.ident, self.second)[0]['source'], 'finishing'
        )
        # Reject sets aside, with nothing in the draft changed.
        revision = self.draft()['revision']
        left = self.post('desk-skip', job=job['id'], items=['p3', 'p2'])
        self.assertEqual(self.draft()['revision'], revision)
        states = {i['id']: i['state'] for i in left['finishing']['copyedit']['items']}
        self.assertEqual(
            states, {'p1': 'applied', 'p2': 'skipped', 'p3': 'skipped', 'p4': 'applied'}
        )
        self.assertIn('12 files', self.draft()['sections'][0]['text'])

    def test_check_again_reads_the_current_text(self):
        first = self.queue('copyedit')
        self.ready(first, {'suggestions': []})
        desk.save(self.root, self.ident, self.seen, self.second, 'Changed text here.')
        self.seen += 1
        again = self.queue('copyedit')
        self.assertNotEqual(again['id'], first['id'])
        texts = [s['text'] for s in again['payload']['sections']]
        self.assertIn('Changed text here.', texts)


class MixedReviewTests(ToolCase):
    """Check spelling and grammar with human-sounding suggestions: Copy edit, then Humanize
    at the chosen strength, their suggestions together and independent: accepting one changes
    another only where it changed the other's words."""

    def setUp(self):
        super().setUp()
        desk.save(self.root, self.ident, self.seen, self.second, 'Their are two parser.')
        self.seen += 1

    def check(self, **extra):
        shown = desk.dispatch(self.root, 'review', {'id': self.ident, 'seen': self.seen, **extra})
        return tool_jobs.read(self.root, shown['working']['id'])

    def jobs(self):
        return [(job['kind'], job['status']) for job in desk_jobs.jobs(self.root, self.ident)]

    def test_humanize_is_queued_when_copy_edit_settles_and_check_again_reuses_it(self):
        first = self.check(humanize='strong')
        self.assertEqual(first['kind'], 'finish-copyedit')
        self.assertEqual(self.jobs(), [('finish-copyedit', 'queued')], 'one job at a time')
        self.assertEqual(desk_jobs.view(self.root, self.ident)['review']['humanize'], 'strong')
        self.ready(first, {'suggestions': []})
        kinds = self.jobs()
        self.assertEqual(kinds, [('finish-copyedit', 'ready'), ('finish-humanize', 'queued')])
        second = desk_jobs.jobs(self.root, self.ident)[-1]
        self.assertEqual(second['metadata']['desk']['level'], 'strong')
        self.assertEqual(second['payload']['level'], 'strong')
        self.assertIn(desk_finish.LEVELS['strong'], second['guidance'])
        # Settling Copy edit again, as an older process might, queues nothing more.
        desk_jobs._review_next(self.root, tool_jobs.read(self.root, first['id']))
        desk_jobs.settle(self.root, self.ident)
        self.assertEqual(len(self.jobs()), 2)
        # A check already under way is not replaced: Check again waits for it.
        with self.assertRaisesRegex(ValueError, 'already working'):
            self.check(humanize=None)
        self.assertEqual(desk_jobs.review_record(self.root, self.ident)['next'], second['id'])
        self.ready(second, {'suggestions': []})
        # Check again, with no strength sent, reruns both at the pinned strength.
        again = self.check()
        self.assertEqual(again['metadata']['desk']['then'], 'strong')
        self.ready(again, {'suggestions': []})
        self.assertEqual(self.jobs()[-1], ('finish-humanize', 'queued'))
        self.ready(desk_jobs.jobs(self.root, self.ident)[-1], {'suggestions': []})
        # Turned off, Check again is Copy edit only, and stays off.
        off = self.check(humanize=None)
        self.assertNotIn('then', off['metadata']['desk'])
        self.ready(off, {'suggestions': []})
        self.assertEqual(self.jobs()[-1], ('finish-copyedit', 'ready'))
        self.assertIsNone(desk_jobs.view(self.root, self.ident)['review']['humanize'])
        with self.assertRaisesRegex(ValueError, 'light, medium'):
            self.check(humanize='loud')

    def test_copy_edits_suggestions_can_be_accepted_while_humanize_works(self):
        desk.save(
            self.root,
            self.ident,
            self.seen,
            self.second,
            'Agentic AI is here. Their are two parser. Agentic tools are there.',
        )
        self.seen += 1
        first = self.check(humanize='light')
        self.ready(
            first,
            {
                'suggestions': [
                    self.fix('Agentic AI', 'agentic AI', kind='consistency'),
                    self.fix('Their are two parser.', 'There are two parsers.'),
                    self.fix('Agentic tools', 'agentic tools', kind='consistency'),
                ]
            },
        )
        shown = desk_jobs.view(self.root, self.ident)
        self.assertEqual(shown['working']['kind'], 'finish-humanize')
        job = shown['finishing']['copyedit']['job']
        items = [{'id': 'p1'}, {'id': 'p2'}, {'id': 'p3'}]
        done = self.act('apply', seen=shown['revision'], job=job, items=items)
        self.assertEqual(done['finished']['applied'], 3)
        self.assertEqual(
            self.draft()['sections'][1]['text'],
            'agentic AI is here. There are two parsers. agentic tools are there.',
        )
        # Humanize read the text before those fixes. Its suggestions for words they changed
        # take the fixes in where they kept those words, and otherwise land retired, saying
        # why, never silently dropped.
        second = desk_jobs.jobs(self.root, self.ident)[-1]
        self.ready(
            second,
            {
                'suggestions': [
                    self.fix('Agentic AI is here.', 'Here, Agentic AI has arrived.'),
                    self.fix('Their are two parser.', 'Two parsers exist.'),
                    self.fix('Agentic tools are there.', 'Agentic tools sit there.'),
                    self.fix('We leverage a robust parser.', 'We use a parser.', part=self.first),
                    self.fix('Not in the text.', 'Nowhere.'),
                ]
            },
        )
        found = self.shown('humanize')
        self.assertEqual(
            [(i['before'], i.get('after'), i['state'], i['present']) for i in found['items']],
            [
                ('agentic AI is here.', 'Here, agentic AI has arrived.', 'open', True),
                ('Their are two parser.', 'Two parsers exist.', 'retired', False),
                ('tools are there.', 'tools sit there.', 'open', True),
                ('We leverage a robust parser.', 'We use a parser.', 'open', True),
            ],
        )
        self.assertEqual(found['dropped'], 1, 'only the one that was never in the text')
        self.assertEqual(found['items'][1]['reason'], desk_finish.CHANGED)
        self.assertEqual(found['items'][1]['retired_by'], {'job': job, 'id': 'p2'})
        self.assertEqual(found['items'][0]['carried'], [{'job': job, 'id': 'p1'}])
        done = self.act(
            'apply',
            seen=self.draft()['revision'],
            job=found['job'],
            items=[{'id': 'p1'}, {'id': 'p3'}],
        )
        self.assertEqual(
            self.draft()['sections'][1]['text'],
            'Here, agentic AI has arrived. There are two parsers. agentic tools sit there.',
        )

    def test_a_late_rewrite_names_the_fix_accepted_with_an_alternative(self):
        first = self.check(humanize='light')
        self.ready(
            first,
            {
                'suggestions': [
                    self.fix(
                        'Their are two parser.',
                        'There are two parsers.',
                        kind='wording',
                        alternatives=['Two parsers are here.'],
                    )
                ]
            },
        )
        shown = desk_jobs.view(self.root, self.ident)
        job = shown['finishing']['copyedit']['job']
        self.act('apply', seen=shown['revision'], job=job, items=[{'id': 'p1', 'alternative': 0}])
        self.assertEqual(self.draft()['sections'][1]['text'], 'Two parsers are here.')
        self.ready(
            desk_jobs.jobs(self.root, self.ident)[-1],
            {'suggestions': [self.fix('Their are two parser.', 'Two parsers exist.')]},
        )
        item = self.shown('humanize')['items'][0]
        self.assertEqual((item['state'], item['reason']), ('retired', desk_finish.CHANGED))
        self.assertEqual(item['retired_by'], {'job': job, 'id': 'p1'})

    def test_a_cut_beside_a_moved_edge_leaves_no_double_space(self):
        self.write('A there the goal. “Files two AI café”!')
        fixes = self.offer(
            [self.fix('the goal. “Files', 'the goal. “'), self.fix('two AI', 'zq two AI')],
            kind='finish-copyedit',
        )
        self.accept(fixes, {'id': 'p2'})
        item = desk_finish.read(self.root, self.ident, fixes)['items'][0]
        self.assertEqual(item['state'], 'open')
        self.accept(fixes, {'id': 'p1'})
        self.assertNotIn('  ', self.draft()['sections'][1]['text'])

    def test_a_rewrite_of_words_edited_by_hand_meanwhile_lands_retired_saying_so(self):
        first = self.check(humanize='light')
        self.ready(first, {'suggestions': []})
        desk.save(self.root, self.ident, self.draft()['revision'], self.second, 'Two parsers.')
        self.ready(
            desk_jobs.jobs(self.root, self.ident)[-1],
            {'suggestions': [self.fix('Their are two parser.', 'Two parsers exist.')]},
        )
        item = self.shown('humanize')['items'][0]
        self.assertEqual((item['state'], item['reason']), ('retired', desk_finish.EDITED))
        self.assertNotIn('retired_by', item)

    def fix(self, before, after, part=None, why='A fix.', **extra):
        return {'part': part or self.second, 'before': before, 'after': after, 'why': why, **extra}

    def test_a_copy_edit_that_fails_still_lets_humanize_go_ahead_and_stop_ends_the_check(self):
        first = self.check(humanize='light')
        first.update(status='failed', error='The assistant stopped.', finished_at='x')
        tool_jobs.write(self.root, first)
        desk_jobs.ended(self.root, first)
        self.assertEqual(self.jobs()[-1], ('finish-humanize', 'queued'))
        second = desk_jobs.jobs(self.root, self.ident)[-1]
        desk.dispatch(self.root, 'stop', {'id': self.ident, 'job': second['id']})
        self.assertEqual(self.jobs()[-1], ('finish-humanize', 'cancelled'))
        # Stopped during Copy edit, Humanize is never queued.
        again = self.check()
        desk.dispatch(self.root, 'stop', {'id': self.ident, 'job': again['id']})
        again = tool_jobs.read(self.root, again['id'])
        desk_jobs._review_next(self.root, again)
        self.assertEqual(self.jobs()[-1], ('finish-copyedit', 'cancelled'))

    def test_a_problem_queuing_humanize_is_kept_for_the_page(self):
        first = self.check(humanize='light')
        for part in (self.first, self.second, 'opening'):
            draft = self.draft()
            desk.save(self.root, self.ident, draft['revision'], part, '')
        self.ready(first, {'suggestions': []})
        self.assertEqual(self.jobs(), [('finish-copyedit', 'ready')])
        problem = desk_jobs.view(self.root, self.ident)['review']['problem']
        self.assertIn('Write the draft first', problem)

    def test_copy_edit_names_each_kind_strictly(self):
        draft = self.draft()
        rows = [
            self.fix('Their are two parser.', 'There are two parsers.', kind='spelling'),
            self.fix(
                'We leverage a robust parser.', 'We use a parser.', self.first, kind='Wording'
            ),
            self.fix('An opening paragraph.', 'An opening paragraph!', 'opening', kind=['x']),
            self.fix('synthetic', 'Synthetic', 'title', kind='punctuation'),
        ]
        items, dropped, _ = desk_finish._read_copyedit(draft, {'suggestions': rows})
        self.assertEqual(dropped, 0)
        self.assertEqual(
            [i['kind'] for i in items], ['spelling', 'grammar', 'grammar', 'punctuation']
        )
        for kind in desk_finish.COPYEDIT_KINDS:
            self.assertIn('"' + kind + '"', desk_finish.COPYEDIT_JSON)
        self.assertIn('alternatives', desk_finish.COPYEDIT_JSON)
        # Humanize's suggestions name no kind: they are all human-sounding wording.
        items, _, _ = desk_finish._read_humanize(draft, {'suggestions': rows[:2]})
        self.assertNotIn('kind', items[0])

    def test_wording_alternatives_are_read_strictly_and_flagged_each(self):
        draft = self.draft()
        before = 'We leverage a robust parser.'

        def read(alternatives, kind='wording', part=None, old=before):
            row = self.fix(old, 'We use a sturdy parser.', part or self.first, kind=kind)
            row['alternatives'] = alternatives
            items, _, _ = desk_finish._read_copyedit(draft, {'suggestions': [row]})
            return items[0].get('alternatives')

        found = read(
            [
                'We rely on a robust parser.',
                'We leverage a robust parser.',  # The same as before.
                'We use a sturdy parser.',  # The same as after.
                '',
                7,
                '## A heading\n\nText.',
            ]
        )
        self.assertIsNone(found, 'more than three is not read at all')
        found = read(['We rely on a robust parser.', 'We leverage a robust parser.', '  '])
        self.assertEqual(found, [{'after': 'We rely on a robust parser.', 'flag': ''}])
        found = read(['We rely on 14 parsers.', 'We trust our robust parser.'])
        self.assertIn('a number', found[0]['flag'])
        self.assertEqual(found[1]['flag'], '')
        self.assertEqual(found[1]['after'], 'We trust our robust parser.')
        # Only a wording fix has alternatives, and never a malformed list.
        self.assertIsNone(read(['We rely on a robust parser.'], kind='grammar'))
        self.assertIsNone(read(['We rely on a robust parser.'], kind='spelling'))
        self.assertIsNone(read('We rely on a robust parser.'))
        self.assertIsNone(read({'after': 'We rely on a robust parser.'}))
        self.assertIsNone(read([]))
        # In the title, an alternative is one line.
        title = read(['A synthetic\ntitle', 'The synthetic title'], part='title', old='A synthetic')
        self.assertEqual([t['after'] for t in title], ['The synthetic title'])

    def test_accept_applies_the_alternative_picked(self):
        job = self.offer(
            [
                {
                    'part': self.first,
                    'before': 'We leverage a robust parser.',
                    'after': 'We use a sturdy parser.',
                    'kind': 'wording',
                    'flag': '',
                    'alternatives': [
                        {'after': 'We rely on a robust parser.', 'flag': ''},
                        {'after': 'Our parser is robust.', 'flag': ''},
                    ],
                }
            ],
            kind='finish-copyedit',
        )
        for entry, said in (
            ({'id': 'p1', 'alternative': 2}, 'alternatives'),
            ({'id': 'p1', 'alternative': -1}, 'alternatives'),
            ({'id': 'p1', 'alternative': True}, 'alternatives'),
            ({'id': 'p1', 'alternative': '1'}, 'alternatives'),
            ({'id': 'p1', 'alternative': 1, 'after': 'Mine.'}, 'alternatives'),
        ):
            with self.subTest(entry=entry), self.assertRaisesRegex(ValueError, said):
                self.act('apply', seen=self.seen, job=job, items=[entry])
        self.act('apply', seen=self.seen, job=job, items=[{'id': 'p1', 'alternative': 1}])
        self.assertTrue(self.draft()['sections'][0]['text'].startswith('Our parser is robust.'))
        self.assertEqual(
            desk_finish.read(self.root, self.ident, job)['items'][0]['state'], 'applied'
        )
        kept = desk.versions(self.root, self.ident, self.first)[0]
        self.assertEqual(kept['source'], 'finishing')

    def write(self, text, part=None):
        desk.save(self.root, self.ident, self.draft()['revision'], part or self.second, text)

    def states(self, job):
        return [item['state'] for item in desk_finish.read(self.root, self.ident, job)['items']]

    def accept(self, job, *entries, **extra):
        seen = self.draft()['revision']
        return self.act('apply', seen=seen, job=job, items=list(entries), **extra)

    def test_a_fix_accepted_first_keeps_each_rewrite_independent_or_retires_it(self):
        self.write('Agentic AI is here. Their are two parser.')
        fixes = self.offer(
            [
                self.fix('Agentic AI', 'agentic AI', kind='consistency'),
                self.fix('Their are', 'There are', kind='grammar'),
            ],
            kind='finish-copyedit',
        )
        human = self.offer(
            [
                self.fix('Agentic AI is here.', 'Agentic AI has arrived.', flag=''),
                self.fix('Their are two parser.', 'Two parsers exist.', flag=''),
            ]
        )
        done = self.accept(fixes, {'id': 'p1'})
        self.assertEqual(done['finished'], {'applied': 1, 'left': [], 'carried': 1})
        item = desk_finish.read(self.root, self.ident, human)['items'][0]
        self.assertEqual(
            (item['state'], item['before'], item['after']),
            ('open', 'AI is here.', 'AI has arrived.'),
            'the rewrite keeps only its own change, with context from the text',
        )
        self.assertEqual(item['carried'], [{'job': fixes, 'id': 'p1'}])
        # A rewrite that rewrote the fixed words would undo the fix: it retires.
        done = self.accept(fixes, {'id': 'p2'})
        self.assertEqual(done['finished'], {'applied': 1, 'left': [], 'retired': 1})
        item = desk_finish.read(self.root, self.ident, human)['items'][1]
        self.assertEqual((item['state'], item['reason']), ('retired', desk_finish.CHANGED))
        self.assertEqual(item['retired_by'], {'job': fixes, 'id': 'p2'})
        # Kept with the waiting set: the view, as after a reload, shows them as they are now.
        shown = desk_jobs.view(self.root, self.ident)['finishing']['humanize']['items']
        self.assertEqual(
            [(i['before'], i['present'], i['state']) for i in shown],
            [('AI is here.', True, 'open'), ('Their are two parser.', False, 'retired')],
        )
        self.accept(human, {'id': 'p1'})
        self.assertEqual(
            self.draft()['sections'][1]['text'], 'agentic AI has arrived. There are two parser.'
        )
        self.assertEqual(self.states(human), ['applied', 'retired'])
        self.assertEqual(self.states(fixes), ['applied', 'applied'])

    def test_a_rewrite_of_the_whole_sentence_takes_in_a_fix_only_where_it_kept_its_words(self):
        self.write('Agentic AI is here. Agentic tools are there.')
        fixes = self.offer(
            [
                self.fix('Agentic AI', 'agentic AI', kind='consistency'),
                self.fix('Agentic tools', 'agentic tools', kind='consistency'),
            ],
            kind='finish-copyedit',
        )
        human = self.offer(
            [
                self.fix('Agentic AI is here.', 'Here, Agentic AI has arrived.'),
                self.fix('Agentic tools are there.', 'Agentive tools sit there.'),
            ]
        )
        done = self.accept(fixes, {'id': 'p1'}, {'id': 'p2'})
        self.assertEqual(done['finished'], {'applied': 2, 'left': [], 'carried': 1, 'retired': 1})
        items = desk_finish.read(self.root, self.ident, human)['items']
        self.assertEqual(
            (items[0]['state'], items[0]['before'], items[0]['after']),
            ('open', 'agentic AI is here.', 'Here, agentic AI has arrived.'),
        )
        self.assertEqual(items[1]['state'], 'retired', 'it reworded the fixed words')
        self.accept(human, {'id': 'p1'})
        self.assertEqual(
            self.draft()['sections'][1]['text'],
            'Here, agentic AI has arrived. agentic tools are there.',
        )

    def test_a_rewrite_accepted_first_never_leaves_a_fix_that_would_undo_it(self):
        self.write('Agentic AI is here. It reads 12 files in 3 seconds.')
        fixes = self.offer(
            [
                self.fix('Agentic AI is here.', 'agentic AI is here.', kind='consistency'),
                self.fix(
                    'It reads 12 files in 3 seconds.',
                    'It reads 12 files in three seconds.',
                    kind='consistency',
                ),
            ],
            kind='finish-copyedit',
        )
        human = self.offer(
            [
                self.fix('Agentic AI is here.', 'Here, Agentic AI has arrived.'),
                self.fix('It reads 12 files in 3 seconds.', 'In 3 seconds it reads 12 files.'),
            ]
        )
        done = self.accept(human, {'id': 'p1'}, {'id': 'p2'})
        self.assertEqual(done['finished'], {'applied': 2, 'left': [], 'carried': 1, 'retired': 1})
        items = desk_finish.read(self.root, self.ident, fixes)['items']
        self.assertEqual(
            (items[0]['state'], items[0]['before'], items[0]['after']),
            ('open', 'Agentic AI', 'agentic AI'),
            'the fix shrinks to its own change, which the rewrite kept',
        )
        self.assertEqual(items[1]['state'], 'retired', 'the rewrite moved the words it fixes')
        self.accept(fixes, {'id': 'p1'})
        self.assertEqual(
            self.draft()['sections'][1]['text'],
            'Here, agentic AI has arrived. In 3 seconds it reads 12 files.',
        )

    def test_a_rewrite_accepted_first_leaves_a_fix_it_kept_open_and_retires_one_it_removed(self):
        fixes = self.offer(
            [self.fix('Their are', 'There are', kind='grammar')], kind='finish-copyedit'
        )
        kept = self.offer([self.fix('Their are two parser.', 'Their are two parsers, it seems.')])
        done = self.accept(kept, {'id': 'p1'})
        self.assertEqual(done['finished'], {'applied': 1, 'left': []})
        item = done['finishing']['copyedit']['items'][0]
        self.assertEqual(
            (item['state'], item['before'], item['present']), ('open', 'Their are', True)
        )
        self.accept(fixes, {'id': 'p1'})
        self.assertEqual(self.draft()['sections'][1]['text'], 'There are two parsers, it seems.')
        # A rewrite that takes the fixed words away retires the fix, saying why.
        self.write('Their are two parser.')
        fixes = self.offer(
            [self.fix('Their are', 'There are', kind='grammar')], kind='finish-copyedit'
        )
        gone = self.offer([self.fix('Their are two parser.', 'Two parsers exist.')])
        done = self.accept(gone, {'id': 'p1'})
        self.assertEqual(done['finished'], {'applied': 1, 'left': [], 'retired': 1})
        item = done['finishing']['copyedit']['items'][0]
        self.assertEqual(item['state'], 'retired')
        self.assertEqual(item['reason'], 'Its words were changed by an accepted suggestion.')
        self.assertEqual(item['retired_by'], {'job': gone, 'id': 'p1'})
        with self.assertRaisesRegex(ValueError, 'no longer fits'):
            self.accept(fixes, {'id': 'p1'})
        self.assertEqual(self.draft()['sections'][1]['text'], 'Two parsers exist.')

    def test_suggestions_that_share_no_changed_words_stay_open_whichever_is_accepted(self):
        fixes = self.offer(
            [
                self.fix('We leverage', 'We use', self.first, kind='wording'),
                self.fix('Their', 'There', kind='spelling'),
            ],
            kind='finish-copyedit',
        )
        human = self.offer(
            [
                self.fix('at Acme Labs.', 'for Acme Labs.', self.first),
                self.fix('two parser.', 'two parsers.'),
            ]
        )
        done = self.accept(fixes, {'id': 'p1'})
        self.assertEqual(done['finished'], {'applied': 1, 'left': []})
        self.assertEqual(self.states(human), ['open', 'open'])
        self.accept(human, {'id': 'p2'})
        self.assertEqual(self.states(fixes), ['applied', 'open'])
        self.assertNotIn('carried', desk_finish.read(self.root, self.ident, fixes)['items'][1])
        self.accept(human, {'id': 'p1'})
        self.accept(fixes, {'id': 'p2'})
        draft = self.draft()
        self.assertEqual(
            draft['sections'][0]['text'],
            'We use a robust parser. It reads 12 files in 3 seconds for Acme Labs.',
        )
        self.assertEqual(draft['sections'][1]['text'], 'There are two parsers.')

    def test_a_cut_beside_an_accepted_word_keeps_that_word_as_context(self):
        self.write('We really leverage AI here.')
        fixes = self.offer(
            [self.fix('really leverage', 'leverage'), self.fix('leverage', 'use')],
            kind='finish-copyedit',
        )
        done = self.accept(fixes, {'id': 'p2'})
        self.assertEqual(done['finished'], {'applied': 1, 'left': [], 'carried': 1})
        item = desk_finish.read(self.root, self.ident, fixes)['items'][0]
        self.assertEqual(
            (item['state'], item['before'], item['after']), ('open', 'really use', 'use')
        )
        self.accept(fixes, {'id': 'p1'})
        self.assertEqual(self.draft()['sections'][1]['text'], 'We use AI here.')
        # The same after a rewrite that changed only the word beside the cut.
        self.write('We really leverage AI here.')
        fixes = self.offer([self.fix('really leverage AI', 'leverage AI')], kind='finish-copyedit')
        human = self.offer([self.fix('We really leverage AI here.', 'We really use AI here.')])
        self.accept(human, {'id': 'p1'})
        item = desk_finish.read(self.root, self.ident, fixes)['items'][0]
        self.assertEqual(
            (item['state'], item['before'], item['after']), ('open', 'really use', 'use')
        )
        self.accept(fixes, {'id': 'p1'})
        self.assertEqual(self.draft()['sections'][1]['text'], 'We use AI here.')

    def test_two_that_add_words_at_one_place_never_both_land(self):
        for first, then in (('fix', 'human'), ('human', 'fix')):
            with self.subTest(first=first):
                self.write('We need two files here.')
                jobs = {
                    'fix': self.offer(
                        [self.fix('two files', 'the two files')], kind='finish-copyedit'
                    ),
                    'human': self.offer([self.fix('two files here.', 'the two files are here.')]),
                }
                done = self.accept(jobs[first], {'id': 'p1'})
                self.assertEqual(done['finished'], {'applied': 1, 'left': [], 'retired': 1})
                self.assertEqual(self.states(jobs[then]), ['retired'])
                self.assertNotIn('the the', self.draft()['sections'][1]['text'])
        self.write('We need two files. Then more.')
        fixes = self.offer(
            [self.fix('need two files', 'need two files today')], kind='finish-copyedit'
        )
        human = self.offer([self.fix('two files', 'both files today')])
        self.accept(fixes, {'id': 'p1'})
        self.assertEqual(self.states(human), ['retired'], 'both add the same word at one place')
        # Accept all of both lands one of them.
        self.write('We need two files here.')
        fixes = self.offer([self.fix('two files', 'the two files')], kind='finish-copyedit')
        human = self.offer([self.fix('two files here.', 'the two files are here.')])
        done = self.accept(fixes, {'id': 'p1'}, {'job': human, 'id': 'p1'}, all=True)
        self.assertEqual(done['finished'], {'applied': 1, 'left': [], 'retired': 1})
        self.assertEqual(self.draft()['sections'][1]['text'], 'We need the two files here.')

    def test_context_from_beyond_a_suggestion_keeps_it_when_its_last_word_changes(self):
        self.write('We ship the Café model now.')
        fixes = self.offer([self.fix('Café model', 'Café model X')], kind='finish-copyedit')
        human = self.offer([self.fix('model', 'Y')])
        self.accept(human, {'id': 'p1'})
        item = desk_finish.read(self.root, self.ident, fixes)['items'][0]
        self.assertEqual(item['state'], 'open')
        self.accept(fixes, {'id': 'p1'})
        self.assertEqual(self.draft()['sections'][1]['text'], 'We ship the Café Y X now.')

    def test_a_word_added_onto_the_last_word_of_another_changes_its_words(self):
        self.write('Each agent focus on one goal.')
        fixes = self.offer(
            [self.fix('Each agent focus on one goal.', 'Each agent focuses on one goal.')],
            kind='finish-copyedit',
        )
        human = self.offer([self.fix('Each agent focus', 'Every agent keeps')])
        done = self.accept(fixes, {'id': 'p1'})
        self.assertEqual(done['finished'], {'applied': 1, 'left': [], 'retired': 1})
        self.assertEqual(self.states(human), ['retired'], 'its words are no longer whole there')

    def test_two_that_start_together_both_apply_when_neither_changes_the_others_words(self):
        job = self.offer(
            [
                self.fix(
                    'We leverage a robust parser.', 'We leverage a robust parser today.', self.first
                ),
                self.fix('We leverage', 'We use', self.first),
                self.fix('Their are', 'There are'),
            ],
            kind='finish-copyedit',
        )
        shown = self.accept(job, {'id': 'p1'}, {'id': 'p2'}, {'id': 'p3'})
        self.assertEqual(shown['finished'], {'applied': 3, 'left': []})
        self.assertTrue(
            self.draft()['sections'][0]['text'].startswith('We use a robust parser today.')
        )
        self.assertEqual(self.states(job), ['applied', 'applied', 'applied'])

    def test_an_alternative_is_carried_too(self):
        fixes = self.offer(
            [
                self.fix(
                    'We leverage a robust parser.',
                    'We use a robust parser.',
                    self.first,
                    kind='wording',
                    flag='',
                    alternatives=[
                        {'after': 'We rely on a robust parser.', 'flag': ''},
                        {'after': 'Our parser is robust.', 'flag': ''},
                    ],
                )
            ],
            kind='finish-copyedit',
        )
        human = self.offer([self.fix('a robust parser', 'a sturdy parser', self.first)])
        done = self.accept(human, {'id': 'p1'})
        self.assertEqual(done['finished'], {'applied': 1, 'left': [], 'carried': 1})
        item = desk_finish.read(self.root, self.ident, fixes)['items'][0]
        self.assertEqual(item['before'], 'We leverage a sturdy parser.')
        self.assertEqual(item['after'], 'We use a sturdy parser.')
        self.assertEqual(
            [a['after'] for a in item['alternatives']],
            ['We rely on a sturdy parser.', 'Our parser is sturdy.'],
        )
        self.accept(fixes, {'id': 'p1', 'alternative': 1})
        self.assertTrue(self.draft()['sections'][0]['text'].startswith('Our parser is sturdy. It'))

    def test_accept_all_leaves_flagged_suggestions_from_both_tools(self):
        first = self.check(humanize='medium')
        self.ready(
            first,
            {
                'suggestions': [
                    self.fix('Their are two parser.', 'There are two parsers.', kind='grammar'),
                    self.fix(
                        'It reads 12 files in 3 seconds at Acme Labs.',
                        'It reads 15 files in 3 seconds at Acme Labs.',
                        self.first,
                    ),
                ]
            },
        )
        self.ready(
            desk_jobs.jobs(self.root, self.ident)[-1],
            {
                'suggestions': [
                    self.fix('We leverage a robust parser.', 'We use a parser.', self.first),
                    self.fix(
                        'It reads 12 files in 3 seconds at Acme Labs.',
                        'It reads 12 files in 3 seconds at Beta Labs.',
                        self.first,
                    ),
                ]
            },
        )

        def ready(view, tool):
            return [
                {'id': i['id']}
                for i in view['finishing'][tool]['items']
                if i['state'] == 'open' and i['present'] and not i['flag']
            ]

        # Accept all, as the page sends it: the fixes first, then what still fits of the rest.
        view = desk_jobs.view(self.root, self.ident)
        self.assertTrue(
            all(view['finishing'][tool]['items'][1]['flag'] for tool in ('copyedit', 'humanize'))
        )
        for tool in ('copyedit', 'humanize'):
            picked = ready(view, tool)
            self.assertEqual(picked, [{'id': 'p1'}], tool)
            view = self.act(
                'apply', seen=view['revision'], job=view['finishing'][tool]['job'], items=picked
            )
        self.assertEqual(
            self.draft()['sections'][0]['text'],
            'We use a parser. It reads 12 files in 3 seconds at Acme Labs.',
        )
        for tool in ('copyedit', 'humanize'):
            states = [i['state'] for i in view['finishing'][tool]['items']]
            self.assertEqual(states, ['applied', 'open'], 'the flagged one waits: ' + tool)

    def flagged_fix_and_rewrite(self):
        """A flagged Copy edit fix and an unflagged Humanize rewrite of the same sentence."""
        first = self.check(humanize='light')
        sentence = 'It reads 12 files in 3 seconds at Acme Labs.'
        self.ready(
            first,
            {
                'suggestions': [
                    self.fix(
                        sentence,
                        'It reads 12 files in 3 seconds at ACME Labs.',
                        self.first,
                        kind='consistency',
                    ),
                    self.fix('Their are two parser.', 'There are two parsers.', kind='grammar'),
                ]
            },
        )
        self.ready(
            desk_jobs.jobs(self.root, self.ident)[-1],
            {
                'suggestions': [
                    self.fix(sentence, 'In 3 seconds it reads 12 files at Acme Labs.', self.first),
                    self.fix('We leverage a robust parser.', 'We use a parser.', self.first),
                ]
            },
        )
        view = desk_jobs.view(self.root, self.ident)
        self.assertTrue(view['finishing']['copyedit']['items'][0]['flag'])
        self.assertFalse(view['finishing']['humanize']['items'][0]['flag'])
        return view

    def test_accept_all_lands_in_reading_order_shrinking_skipping_and_leaving_flagged_ones(self):
        self.write('Agentic AI is here. Their are two parser.')
        fixes = self.offer(
            [
                self.fix('Agentic AI', 'agentic AI', kind='consistency'),
                self.fix('Their are two parser.', 'There are two parsers.', kind='grammar'),
                self.fix('robust parser', 'sturdy tool', self.first, kind='wording'),
                self.fix('in 3 seconds', 'within 3 seconds', self.first, kind='wording'),
            ],
            kind='finish-copyedit',
        )
        human = self.offer(
            [
                self.fix('Agentic AI is here.', 'Agentic AI has arrived.'),
                self.fix('Their are two parser.', 'Two parsers exist.'),
                self.fix(
                    'It reads 12 files in 3 seconds',
                    'It reads 15 files in 3 seconds',
                    self.first,
                    flag='Check the facts: this changes a number.',
                ),
                self.fix('We leverage a robust', 'We use a strong', self.first),
            ]
        )
        with self.assertRaisesRegex(ValueError, 'Choose suggestions'):
            self.accept(fixes, {'id': 'p1'}, {'job': 'f' * 32, 'id': 'p1'}, all=True)
        # As the page sends it: every shown suggestion that is not flagged, from both sets.
        done = self.accept(
            fixes,
            *({'id': name} for name in ('p1', 'p2', 'p3', 'p4')),
            *({'job': human, 'id': name} for name in ('p1', 'p2', 'p4')),
            all=True,
        )
        self.assertEqual(done['finished'], {'applied': 5, 'left': [], 'carried': 1, 'retired': 2})
        draft = self.draft()
        self.assertEqual(
            draft['sections'][0]['text'],
            'We use a strong parser. It reads 12 files within 3 seconds at Acme Labs.',
        )
        self.assertEqual(
            draft['sections'][1]['text'], 'agentic AI has arrived. There are two parsers.'
        )
        self.assertEqual(self.states(fixes), ['applied', 'applied', 'retired', 'applied'])
        self.assertEqual(self.states(human), ['applied', 'retired', 'open', 'applied'])
        # The rewrite that started first landed; the fix whose words it changed retired, and
        # the fix landed before the rewrite that reworded its words, which retired.
        self.assertEqual(
            desk_finish.read(self.root, self.ident, fixes)['items'][2]['retired_by'],
            {'job': human, 'id': 'p4'},
        )
        self.assertEqual(
            desk_finish.read(self.root, self.ident, human)['items'][1]['retired_by'],
            {'job': fixes, 'id': 'p2'},
        )
        # The flagged one waits, shrunk to its own change, with its flag read again.
        waiting = done['finishing']['humanize']['items'][2]
        self.assertEqual(
            (waiting['before'], waiting['after'], waiting['present']),
            ('reads 12 files', 'reads 15 files', True),
        )
        self.assertIn('a number', waiting['flag'])
        for part in (self.first, self.second):
            self.assertEqual(
                [v['source'] for v in desk.versions(self.root, self.ident, part)][:1],
                ['finishing'],
            )
            self.assertEqual(
                [v['source'] for v in desk.versions(self.root, self.ident, part)].count(
                    'finishing'
                ),
                1,
                'one version per part',
            )

    def test_accept_all_never_retires_a_flagged_fix_but_one_accept_may(self):
        fixes = self.offer(
            [
                self.fix(
                    'Acme Labs',
                    'ACME Labs',
                    self.first,
                    kind='consistency',
                    flag='Check the facts: this changes a name.',
                ),
                self.fix(
                    'two parser',
                    'three parsers',
                    kind='grammar',
                    flag='Check the facts: this changes a number.',
                ),
            ],
            kind='finish-copyedit',
        )
        human = self.offer(
            [
                self.fix(
                    'It reads 12 files in 3 seconds at Acme Labs.',
                    'In 3 seconds it reads 12 files at Acme Labs.',
                    self.first,
                ),
                self.fix('Their are two parser.', 'There is a pair of parsers.'),
            ]
        )
        # Accept all lands the rewrite that keeps the flagged fix's words, and leaves the one
        # that would take them away, so the flagged fix still waits.
        done = self.accept(human, {'id': 'p1'}, {'id': 'p2'}, all=True)
        self.assertEqual(done['finished'], {'applied': 1, 'left': ['p2']})
        self.assertEqual(self.states(fixes), ['open', 'open'])
        self.assertEqual(self.states(human), ['applied', 'open'])
        # One Accept of that rewrite is the person's say: the fix then retires.
        done = self.accept(human, {'id': 'p2'})
        self.assertEqual(done['finished'], {'applied': 1, 'left': [], 'retired': 1})
        items = done['finishing']['copyedit']['items']
        self.assertEqual(
            [(i['state'], i['present']) for i in items], [('open', True), ('retired', False)]
        )
        self.assertEqual(items[1]['retired_by'], {'job': human, 'id': 'p2'})
        self.assertEqual(self.states(fixes), ['open', 'retired'], 'as kept for a reload')

    def test_accept_all_never_retires_a_fix_it_was_not_sent(self):
        fixes = self.offer(
            [self.fix('Their are', 'There are', kind='grammar')], kind='finish-copyedit'
        )
        human = self.offer([self.fix('Their are two parser.', 'Two parsers exist.')])
        done = self.accept(human, {'id': 'p1'}, all=True)  # Show: Sounds human.
        self.assertEqual(done['finished'], {'applied': 0, 'left': ['p1']})
        self.assertEqual((self.states(fixes), self.states(human)), (['open'], ['open']))

    def test_accept_all_leaves_a_flagged_pick_for_the_person(self):
        human = self.offer(
            [
                self.fix(
                    'It reads 12 files',
                    'It reads 15 files',
                    self.first,
                    flag='Check the facts: this changes a number.',
                )
            ]
        )
        revision = self.draft()['revision']
        done = self.accept(human, {'id': 'p1'}, all=True)
        self.assertEqual(done['finished'], {'applied': 0, 'left': ['p1']})
        self.assertEqual(self.draft()['revision'], revision)
        self.assertEqual(self.states(human), ['open'])

    def test_a_retired_item_in_a_multi_item_accept_is_left_out_and_the_rest_apply(self):
        fixes = self.offer(
            [
                self.fix(
                    'We leverage a robust parser. It reads',
                    'We use a robust parser, and it reads',
                    self.first,
                )
            ],
            kind='finish-copyedit',
        )
        human = self.offer(
            [
                self.fix('It reads 12 files', 'This reads 12 files', self.first),
                self.fix('Their are two parser.', 'Two parsers.'),
            ]
        )
        self.accept(fixes, {'id': 'p1'})
        self.assertEqual(self.states(human), ['retired', 'open'])
        done = self.accept(human, {'id': 'p1'}, {'id': 'p2'})
        self.assertEqual(done['finished'], {'applied': 1, 'left': ['p1']})
        self.assertEqual(self.draft()['sections'][1]['text'], 'Two parsers.')
        self.assertEqual(self.states(human), ['retired', 'applied'])
        with self.assertRaisesRegex(ValueError, 'no longer fits'):
            self.accept(human, {'id': 'p1'})
        with self.assertRaisesRegex(ValueError, 'Choose suggestions'):
            self.accept(human, {'id': 'p2'}, all='yes')
        # Accept all with only a retired item in it changes nothing, and says so.
        revision = self.draft()['revision']
        done = self.accept(human, {'id': 'p1'}, all=True)
        self.assertEqual(done['finished'], {'applied': 0, 'left': ['p1']})
        self.assertEqual(self.draft()['revision'], revision)

    def test_a_copy_edit_that_never_ran_still_lets_humanize_go_ahead_once(self):
        from unittest.mock import patch

        first = self.check(humanize='medium')
        with patch('studio_core.model_profiles.route', side_effect=ValueError('No model chosen.')):
            tool_jobs.once(blog_runner.Engine(self.root, worker=lambda *a, **k: None))
        self.assertEqual(tool_jobs.read(self.root, first['id'])['status'], 'failed')
        self.assertEqual(
            self.jobs(), [('finish-copyedit', 'failed'), ('finish-humanize', 'queued')]
        )
        second = desk_jobs.jobs(self.root, self.ident)[-1]
        self.assertEqual(second['metadata']['desk']['level'], 'medium')
        desk_jobs.ended(self.root, tool_jobs.read(self.root, first['id']))
        desk_jobs.settle(self.root, self.ident)
        self.assertEqual(len(self.jobs()), 2, 'exactly once')

    def test_a_copy_edit_interrupted_when_blog_studio_closed_still_lets_humanize_go_ahead(self):
        first = self.check(humanize='strong')
        first.update(status='working', started_at='x')
        tool_jobs.write(self.root, first)
        tool_jobs.recover(self.root)
        self.assertEqual(
            self.jobs(), [('finish-copyedit', 'failed'), ('finish-humanize', 'queued')]
        )
        tool_jobs.recover(self.root)
        desk_jobs.settle(self.root, self.ident)
        self.assertEqual(len(self.jobs()), 2, 'exactly once')
        # Interrupted Humanize ends the check with nothing more queued.
        second = desk_jobs.jobs(self.root, self.ident)[-1]
        second.update(status='working', started_at='x')
        tool_jobs.write(self.root, second)
        tool_jobs.recover(self.root)
        self.assertEqual(self.jobs()[-1], ('finish-humanize', 'failed'))
        self.assertEqual(len(self.jobs()), 2)

    def test_no_image_data_reaches_either_job(self):
        from test_desk import GOOGLE as WITH_IMAGES

        made = desk.create(self.root, {'manuscript': WITH_IMAGES})
        shown = desk.dispatch(
            self.root, 'review', {'id': made['id'], 'seen': 1, 'humanize': 'light'}
        )
        first = tool_jobs.read(self.root, shown['working']['id'])
        first.update(status='ready', result={'content': '{"suggestions": []}'}, finished_at='x')
        tool_jobs.write(self.root, first)
        desk_jobs.settle(self.root, made['id'])
        second = desk_jobs.jobs(self.root, made['id'])[-1]
        self.assertEqual([first['kind'], second['kind']], ['finish-copyedit', 'finish-humanize'])
        for job in (first, second):
            with self.subTest(kind=job['kind']):
                self.assertNotIn('data:image', json.dumps(job['payload']))
                self.assertNotIn('data:image', job['guidance'])
                self.assertNotIn(IMAGE_TWO, json.dumps(job))
                self.assertIn('![][image1]', job['payload']['opening'])


class ReviewSpeedTests(FinishCase):
    """Accept all over many suggestions in one long part stays quick: it holds the studio
    lock while it works."""

    def test_accept_all_of_120_suggestions_in_a_5k_part_takes_seconds_not_minutes(self):
        import random
        import time

        r = random.Random(7)
        words = (
            'agent agentic tools parser data model team runs fast slow robust goal focus '
            'reads files café résumé naïve keeps every each there here'
        ).split()

        def sentence():
            picked = [r.choice(words) for _ in range(r.randint(6, 12))]
            return ' '.join(picked).capitalize() + r.choice('.!?')

        paragraphs = [' '.join(sentence() for _ in range(6)) for _ in range(16)]
        text = '\n\n'.join(paragraphs)
        self.assertGreater(len(text), 5000)
        desk.save(self.root, self.ident, 1, self.first, text)
        found = desk.text_of(self.draft(), self.first)
        fixes, rewrites, used = [], [], set()
        while len(fixes) < 60 or len(rewrites) < 60:
            size = 3 if len(fixes) < 60 else 7
            tokens = found.split(' ')
            start = r.randrange(0, len(tokens) - size)
            before = ' '.join(tokens[start : start + size])
            if '\n' in before or before in used or found.count(before) != 1:
                continue
            used.add(before)
            changed = before.split(' ')
            for at in r.sample(range(size), 1 if size == 3 else 3):
                changed[at] = 'zq' + str(len(used)) + str(at)
            row = {'part': self.first, 'before': before, 'after': ' '.join(changed), 'flag': ''}
            (fixes if size == 3 else rewrites).append(row)
        copyedit = self.offer(fixes, kind='finish-copyedit')
        humanize = self.offer(rewrites)
        entries = [{'job': copyedit, 'id': 'p%d' % n} for n in range(1, 61)]
        entries += [{'job': humanize, 'id': 'p%d' % n} for n in range(1, 61)]
        began = time.monotonic()
        done = self.act(
            'apply', seen=self.draft()['revision'], job=copyedit, items=entries, all=True
        )
        took = time.monotonic() - began
        self.assertGreater(done['finished']['applied'], 60)
        self.assertLess(took, 5, 'Accept all took %.1f seconds' % took)


class VoiceTests(ToolCase):
    """Apply a voice: the draft rewritten in a voice guide, section by section."""

    def setUp(self):
        super().setUp()
        import article_tools

        self.tools = article_tools
        self.guide = article_tools.save_profile(
            self.root,
            {
                'name': 'Plain',
                'guide': 'Plain words. Short sentences.',
                'status': 'confirmed',
                'confirmed': True,
            },
        )['profile']
        self.first_text = self.draft()['sections'][0]['text']

    def parts(self, *rows):
        return {'parts': [dict(zip(('part', 'text', 'why'), row, strict=True)) for row in rows]}

    def test_the_guide_text_goes_in_the_payload_and_the_context_stays_tone_only(self):
        job = self.queue('voice', guide=self.guide)
        self.assertEqual(job['kind'], 'finish-voice')
        self.assertEqual(
            job['payload']['voice_guide'],
            {'name': 'Plain', 'text': 'Plain words. Short sentences.'},
        )
        self.assertNotIn('voice', job['payload'])
        self.assertIn(desk_finish.VOICE, job['guidance'])
        self.assertIn('"parts"', job['guidance'])
        self.assertIn(blog_runner.house_guide(), job['guidance'])
        meta = job['metadata']['desk']
        self.assertEqual(
            (meta['part'], meta['guide'], meta['guide_name']), ('finishing', self.guide, 'Plain')
        )
        extra, _ = desk_jobs._context(self.root, self.draft())
        self.assertNotIn('voice', extra)

    def test_a_retired_unknown_or_missing_guide_is_refused(self):
        current = self.tools.profile(self.root, self.guide)
        self.tools.retire_profile(
            self.root, {'profile': self.guide, 'expected': current['expected'], 'confirmed': True}
        )
        for guide in (self.guide, 'nobody', None):
            with self.subTest(guide=guide), self.assertRaisesRegex(ValueError, 'not retired'):
                self.queue('voice', guide=guide)

    def test_one_whole_part_proposal_per_rewritten_part_and_nothing_changes(self):
        before = self.draft()
        self.ready(
            self.queue('voice', guide=self.guide),
            self.parts(
                ('opening', 'An opening, said plainly.', 'Plainer.'),
                (self.first, self.first_text, 'Already plain.'),
                (self.second, 'Second text, plainly.', ''),
                (self.second, 'A second row for the same part.', ''),
                ('zzzzzzzz', 'Unknown.', ''),
                ('opening', 'Intro\n\n## Extra', ''),
            ),
        )
        self.assertEqual(self.draft()['revision'], before['revision'])
        shown = self.shown('voice')
        self.assertEqual((shown['dropped'], shown['kept'], shown['guide_name']), (3, 1, 'Plain'))
        self.assertEqual(
            [
                (i['part'], i['before'], i['after'], i['whole'], i['present'])
                for i in shown['items']
            ],
            [
                ('opening', 'An opening paragraph.', 'An opening, said plainly.', True, True),
                (self.second, 'Second text.', 'Second text, plainly.', True, True),
            ],
        )

    def test_a_changed_fact_is_flagged_and_apply_all_lands_the_rest(self):
        self.ready(
            self.queue('voice', guide=self.guide),
            self.parts(
                (self.first, self.first_text.replace('12 files', '15 files'), ''),
                (self.second, 'Second text, plainly.', ''),
                ('opening', 'An opening, said plainly.', ''),
            ),
        )
        items = self.shown('voice')['items']
        self.assertIn('a number', items[1]['flag'])
        ready = [{'id': i['id']} for i in items if not i['flag']]
        shown = self.act('apply', seen=self.seen, job=self.shown('voice')['job'], items=ready)
        self.assertEqual(shown['finished'], {'applied': 2, 'left': []})
        draft = self.draft()
        self.assertEqual(draft['opening'], 'An opening, said plainly.')
        self.assertEqual(draft['sections'][1]['text'], 'Second text, plainly.')
        self.assertEqual(draft['sections'][0]['text'], self.first_text)
        for part, text in (('opening', 'An opening paragraph.'), (self.second, 'Second text.')):
            kept = desk.versions(self.root, self.ident, part)[0]
            self.assertEqual((kept['source'], kept['text']), ('finishing', text))

    def test_changed_code_or_shape_is_flagged(self):
        shaped = 'Run `run --fast` first.\n\n- one\n- two\n\n```\nmake all\n```'
        desk.save(self.root, self.ident, self.seen, self.second, shaped)
        self.seen += 1
        self.ready(
            self.queue('voice', guide=self.guide),
            self.parts(
                (self.second, shaped.replace('--fast', '--slow'), ''),
                ('opening', 'An opening paragraph, said plainly.', ''),
            ),
        )
        flags = {i['part']: i['flag'] for i in self.shown('voice')['items']}
        self.assertEqual(flags[self.second], desk_finish.STRUCTURE)
        self.assertEqual(flags['opening'], '')
        self.ready(
            self.queue('voice', guide=self.guide),
            self.parts((self.second, 'Run it first, then make everything.', '')),
        )
        self.assertEqual(self.shown('voice')['items'][0]['flag'], desk_finish.STRUCTURE)
        for before, after in (
            ('Run `a`.', 'Run `b`.'),
            ('One.\n\nTwo.', 'One. Two.'),
            ('- a\n- b', '- a b'),
            ('| a |\n| - |', 'a'),
        ):
            with self.subTest(before=before):
                self.assertEqual(
                    desk_finish.changes_structure(before, after), desk_finish.STRUCTURE
                )
        self.assertEqual(
            desk_finish.changes_structure('Plain `x` words.', 'Plainer `x` words.'), ''
        )

    def test_indented_code_quotes_and_a_fence_language_are_compared_exactly(self):
        flagged = desk_finish.STRUCTURE
        cases = (
            ('Run it:\n\n    tool --fast\n\nDone.', 'Run it:\n\n    tool --slow\n\nDone.', flagged),
            ('Run it:\n\n\ttool --fast', 'Run it:\n\n\ttool --slow', flagged),
            (
                'Said:\n\n> A quoted line.\n\nThen more.',
                'Said:\n\nA quoted line.\n\nThen more.',
                flagged,
            ),
            ('Said:\n> A quoted line.', 'Said: a quoted line.\n> Another line.', flagged),
            ('```bash\nmake all\n```', '```python\nmake all\n```', flagged),
            # A list continuation is prose, not code: rewording it is not a change of code.
            ('- one\n\n    more about one', '- one\n\n    more on one', ''),
            (
                'Run it:\n\n    tool --fast\n\nDone.',
                'Run this:\n\n    tool --fast\n\nFinished.',
                '',
            ),
            ('> A quoted line.\n\nThen more.', '> A quoted line.\n\nAfter that, more.', ''),
        )
        for before, after, expected in cases:
            with self.subTest(before=before, after=after):
                self.assertEqual(desk_finish.changes_structure(before, after), expected)

    def test_a_name_that_only_moves_is_not_flagged_but_one_added_or_dropped_is(self):
        before = 'The parser was built at Acme Labs. It is fast.'
        moved = 'Acme Labs built the parser. It is fast.'
        self.assertEqual(desk_finish.changes_facts(before, moved, anywhere=True), '')
        self.assertIn(
            'a name',
            desk_finish.changes_facts(before, 'The lab built it. It is fast.', anywhere=True),
        )
        self.assertIn(
            'a name', desk_finish.changes_facts(before, before + ' Ask Beta Works.', anywhere=True)
        )

    def test_a_part_edited_since_no_longer_fits(self):
        self.ready(
            self.queue('voice', guide=self.guide),
            self.parts((self.second, 'Second text, plainly.', '')),
        )
        desk.save(self.root, self.ident, self.seen, self.second, 'Typed meanwhile.')
        self.assertFalse(self.shown('voice')['items'][0]['present'])

    def test_a_result_that_is_not_the_json_asked_for_is_unreadable(self):
        job = self.ready(self.queue('voice', guide=self.guide), {'sections': []})
        self.assertEqual(job['error'], desk_finish.UNREADABLE)

    def test_a_fake_worker_runs_it_end_to_end(self):
        def worker(engine, payload, guidance, **options):
            self.assertEqual(payload['voice_guide']['name'], 'Plain')
            return {
                'content': json.dumps(
                    {'parts': [{'part': self.second, 'text': 'Second text, plainly.', 'why': ''}]}
                ),
                'notes': '',
            }

        job = self.queue('voice', guide=self.guide)
        tool_jobs.once(blog_runner.Engine(self.root, worker=worker))
        self.assertTrue(tool_jobs.read(self.root, job['id'])['settled_at'])
        self.act('apply', seen=self.seen, job=job['id'], items=[{'id': 'p1'}])
        self.assertEqual(self.draft()['sections'][1]['text'], 'Second text, plainly.')


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


class FeedbackTests(ToolCase):
    def test_guidance_asks_for_comments_and_no_rewrite(self):
        import manuscript_editor

        job = self.queue('feedback')
        self.assertEqual(job['kind'], 'finish-feedback')
        self.assertIn('without rewriting it', job['guidance'])
        self.assertIn('Do not rewrite the draft.', job['guidance'])
        self.assertIn(manuscript_editor.CHECKS['shape'], job['guidance'])
        self.assertIn('Structure feedback', job['guidance'])

    def test_comments_land_by_part_and_a_quote_not_in_the_text_is_dropped(self):
        before = self.draft()
        self.ready(
            self.queue('feedback'),
            {
                'summary': 'A clear start.',
                'comments': [
                    {
                        'part': self.first,
                        'quote': 'We leverage a robust parser.',
                        'aspect': 'claims',
                        'comment': 'Which evidence says robust?',
                    },
                    {
                        'part': self.second,
                        'quote': 'Not in the text.',
                        'aspect': 'audience',
                        'comment': 'Who needs this?',
                    },
                    {'part': 'zzzzzzzz', 'aspect': 'odd', 'comment': 'Overall it wanders.'},
                    {'part': self.first, 'comment': ''},
                ],
            },
        )
        shown = self.shown('feedback')
        self.assertEqual(shown['summary'], 'A clear start.')
        self.assertEqual(
            [(i['part'], i['quote'], i['aspect']) for i in shown['items']],
            [
                (self.first, 'We leverage a robust parser.', 'claims'),
                (self.second, '', 'audience'),
                ('whole', '', 'shape'),
            ],
        )
        self.assertEqual(self.draft(), before)
        job = shown['job']
        with self.assertRaisesRegex(ValueError, 'Make it a note'):
            self.act('apply', seen=self.seen, job=job, items=[{'id': 'p1'}])
        self.act('skip', job=job, items=['p2'])
        self.assertEqual(
            [i['state'] for i in self.shown('feedback')['items']], ['open', 'skipped', 'open']
        )


class BeforePublishingTests(ToolCase):
    def test_the_prepublish_check_reads_the_desks_latest_text(self):
        import prepublish

        desk.save(self.root, self.ident, self.seen, self.second, 'Still to do: TODO add a link.')
        found = prepublish.report(self.root, self.ident)
        self.assertIn('unfinished-note', [f['code'] for f in found['findings']])

    def repurposed(self):
        import article_tools

        desk.save(self.root, self.ident, self.seen, self.second, 'Typed just now on the desk.')
        return article_tools.request(
            self.root,
            {
                'kind': 'repurpose',
                'id': self.ident,
                'operation': secrets.token_hex(16),
                'format': 'linkedin',
                'words': 100,
            },
        )

    def test_a_repurpose_job_reads_the_desks_latest_text(self):
        job = tool_jobs.read(self.root, self.repurposed()['id'])
        self.assertIn('Typed just now on the desk.', job['payload']['source'])
        self.assertEqual(job['payload']['voice']['mode'], 'tone')

    def test_a_repurpose_result_becomes_a_new_desk_blog_once(self):
        job = tool_jobs.read(self.root, self.repurposed()['id'])
        with self.assertRaisesRegex(ValueError, 'Wait for the prepared copy'):
            self.act('repurpose', job=job['id'], title='Copy', content='Text.')
        job.update(status='ready', result={'content': 'A short post.', 'notes': ''})
        tool_jobs.write(self.root, job)
        shown = self.act(
            'repurpose', job=job['id'], title='Parser post', content='A short post, edited.'
        )
        made = shown['made']
        self.assertEqual(shown['id'], self.ident)
        new = desk.read(self.root, made['id'])
        self.assertEqual(new['title'], 'Parser post')
        self.assertEqual(new['opening'], 'A short post, edited.')
        self.assertEqual(new['tone'], self.draft()['tone'])
        again = self.act('repurpose', job=job['id'], title='Other', content='Other.')['made']
        self.assertEqual(again, made)
        self.assertEqual(tool_jobs.read(self.root, job['id'])['applied']['desk']['id'], made['id'])

    def test_repurpose_takes_only_this_blogs_copy(self):
        other = desk.create(self.root, {'title': 'Other', 'manuscript': DRAFT})
        job = self.repurposed()
        with self.assertRaisesRegex(ValueError, 'from this blog'):
            desk.dispatch(
                self.root,
                'repurpose',
                {'id': other['id'], 'job': job['id'], 'title': 'X', 'content': 'Y'},
            )

    def test_a_blog_without_a_google_doc_is_refused_readably(self):
        with self.assertRaisesRegex(ValueError, 'no Google Doc'):
            self.act('google-plan', mode='auto')
        self.assertFalse(desk_jobs.view(self.root, self.ident)['google_suggestions'])

    def test_every_change_becomes_a_suggestion_or_a_comment(self):
        baseline = '## Heading\n\nThe delay is long.\n\nKeep it.\n\nGone soon.\n'
        body = '# Title\n\n## Heading\n\nThe wait is long.\n\nKeep **it**.\n'
        found, left, _ = desk_finish.google_changes(baseline, body)
        self.assertEqual(
            [(f['kind'], f['before'], f.get('after'), f.get('remove')) for f in found],
            [
                ('edit', 'delay', 'wait', None),
                ('comment', 'it', None, None),  # Formatting the Doc shows no words for.
                ('edit', 'Gone soon.', '', True),  # A paragraph cut, with its break.
            ],
        )
        self.assertEqual(found[1]['reason'], 'Make “it” bold.')
        self.assertEqual(left, 0, 'the desk’s title line is the Doc’s name, not a change')


class ReviewFixTests(ToolCase):
    """What the independent review of Finishing found."""

    def test_odd_json_types_are_unreadable_never_a_type_error(self):
        draft = self.draft()
        for kind, value in [
            ('finish-humanize', {'suggestions': [{'part': ['x'], 'before': 'A.', 'after': 'B.'}]}),
            (
                'finish-facts',
                {'claims': [{'part': 'opening', 'before': 'A.', 'verdict': ['supported']}]},
            ),
            ('finish-headline', {'titles': 'abc'}),
            ('finish-humanize', [1, 2]),
            ('finish-humanize', {'suggestions': [None, 3]}),
        ]:
            job = {
                'id': secrets.token_hex(16),
                'kind': kind,
                'result': {'content': json.dumps(value)},
                'metadata': {},
            }
            with (
                self.subTest(kind=kind, value=value),
                self.assertRaisesRegex(ValueError, 'cannot read'),
            ):
                desk_finish.settle(self.root, self.ident, draft, job)
        # A comment with an odd part goes to the whole draft; an odd row among good ones is dropped.
        job = {
            'id': secrets.token_hex(16),
            'kind': 'finish-feedback',
            'result': {
                'content': json.dumps(
                    {'comments': [{'part': {'a': 1}, 'aspect': ['x'], 'comment': 'C.'}]}
                )
            },
            'metadata': {},
        }
        kept = desk_finish.settle(self.root, self.ident, draft, job)
        self.assertEqual([(i['part'], i['aspect']) for i in kept['items']], [('whole', 'shape')])
        mixed = {
            'suggestions': [
                {'part': 7},
                {
                    'part': self.first,
                    'before': 'We leverage a robust parser.',
                    'after': 'We use a parser.',
                },
            ]
        }
        job = {
            'id': secrets.token_hex(16),
            'kind': 'finish-humanize',
            'result': {'content': json.dumps(mixed)},
            'metadata': {},
        }
        kept = desk_finish.settle(self.root, self.ident, draft, job)
        self.assertEqual((len(kept['items']), kept['dropped']), (1, 1))

    def test_an_empty_edit_is_refused_and_apply_all_leaves_it(self):
        job = self.offer(
            [
                {
                    'part': 'opening',
                    'before': 'An opening paragraph.',
                    'after': 'New.',
                    'whole': True,
                    'group': 'opening',
                },
                {'part': self.first, 'before': 'We leverage a robust parser.', 'after': ''},
                {'part': self.second, 'before': 'Second text.', 'after': 'Two.'},
            ]
        )
        for item in ('p1', 'p2'):
            with self.subTest(item=item), self.assertRaisesRegex(ValueError, 'not applied empty'):
                self.act('apply', seen=self.seen, job=job, items=[{'id': item, 'after': '  '}])
        shown = self.act('apply', seen=self.seen, job=job, items=[{'id': 'p2'}, {'id': 'p3'}])
        self.assertEqual(shown['finished'], {'applied': 1, 'left': ['p2']})
        self.assertTrue(self.draft()['sections'][0]['text'].startswith('We leverage'))

    def test_proposals_are_marked_applied_only_once_the_draft_is_written(self):
        from unittest.mock import patch

        job = self.offer([{'part': self.second, 'before': 'Second text.', 'after': 'Two.'}])
        with patch('desk._write', side_effect=OSError('disk full')), self.assertRaises(OSError):
            self.act('apply', seen=self.seen, job=job, items=[{'id': 'p1'}])
        self.assertEqual(desk_finish.read(self.root, self.ident, job)['items'][0]['state'], 'open')

    def test_skip_counts_only_what_was_open(self):
        job = self.offer(
            [
                {'part': self.second, 'before': 'Second text.', 'after': 'Two.'},
                {'part': self.second, 'before': 'Second', 'after': 'X'},
            ]
        )
        self.assertEqual(self.act('skip', job=job, items=['p1'])['finished'], {'skipped': 1})
        self.assertEqual(
            self.act('skip', job=job, items=['p1', 'p2', 'p2'])['finished'], {'skipped': 1}
        )

    def test_sets_are_pruned_and_a_poll_reads_only_the_newest(self):
        from unittest.mock import patch

        older = self.offer([{'part': self.second, 'before': 'Second text.', 'after': 'Two.'}])
        self.act('skip', job=older, items=['p1'])
        waiting = self.offer([{'part': self.second, 'before': 'Second text.', 'after': 'Deux.'}])
        newest = self.offer([{'part': self.second, 'before': 'Second text.', 'after': 'Zwei.'}])
        folder = studio.inside(self.root, '.blog-runs', 'desk-proposals', self.ident)
        names = sorted(path.stem for path in folder.glob('*.json'))
        self.assertNotIn(older, names, 'a resolved older set is let go')
        self.assertIn(
            waiting, names, 'an open older set waits a day for a page that still shows it'
        )
        with patch('desk_finish.sets', side_effect=AssertionError('read every set')):
            shown = desk_jobs.view(self.root, self.ident)['finishing']
        self.assertEqual(shown['humanize']['job'], newest)

    def test_a_request_that_shares_nothing_does_not_settle_a_waiting_result(self):
        job = self.offer([{'part': self.second, 'before': 'Second text.', 'after': 'Two.'}])
        queued = desk_jobs.section(self.root, self.ident, self.seen, self.first, 'More.')
        saved = tool_jobs.read(self.root, queued['id'])
        saved.update(status='ready', result={'content': 'Rewritten.', 'notes': ''}, finished_at='x')
        tool_jobs.write(self.root, saved)
        self.act('skip', job=job, items=['p1'])
        self.assertFalse(tool_jobs.read(self.root, queued['id']).get('settled_at'))
        self.act(
            'apply',
            seen=self.seen,
            job=self.offer(
                [{'part': 'title', 'before': 'A synthetic title', 'after': 'T', 'whole': True}],
                'finish-headline',
            ),
            items=[{'id': 'p1'}],
        )
        self.assertTrue(tool_jobs.read(self.root, queued['id']).get('settled_at'))


PROOF_EDGES = """# Proof

Intro.

## List

- Install the parser on each machine.
- Install the checker on each machine.
- Install the reporter on each machine.

## Indented

    code -- here — delve

Plain sentence.

## Code first

```sh
make all the things we need to build here
```

Then we explain what the build did for you.

## Code second

```sh
make all the things we need to build here
```

After that the tests run on their own.
"""


class ProofreadEdgeTests(FinishCase):
    def test_indented_code_lists_and_code_openers_are_not_findings(self):
        ident = desk.create(self.root, {'title': 'Edges', 'manuscript': PROOF_EDGES})['id']
        self.assertEqual(desk_finish.proofread(self.root, ident)['findings'], [])

    def test_a_list_continuation_is_prose_not_code(self):
        text = '- An item\n\n    continues with a robust tapestry.\n'
        self.assertIn('tapestry', desk_finish._mask_indented(text))
        self.assertNotIn('delve', desk_finish._mask_indented('Text.\n\n    delve\n'))


class GooglePairingTests(unittest.TestCase):
    """Each desk change is sent against the Doc paragraph it came from, never a neighbour."""

    def changes(self, baseline, body):
        found, left, _ = desk_finish.google_changes(baseline, body)
        return [(f['before'], f.get('after'), f.get('occurrence')) for f in found], left

    def test_a_deleted_paragraph_is_not_rewritten_into_its_edited_neighbour(self):
        self.assertEqual(
            self.changes(
                'We ship on Monday at noon.\n\nWe ship on Friday at noon.\n',
                'We ship on Friday at nine.\n',
            ),
            ([('We ship on Monday at noon.', '', None), ('noon', 'nine', None)], 0),
        )
        self.assertEqual(
            self.changes(
                'Step one: install the parser on each machine.\n\n'
                'Step two: install the checker on each machine.\n',
                'Step two: install the reporter on each machine.\n',
            ),
            (
                [
                    ('Step one: install the parser on each machine.', '', None),
                    ('checker', 'reporter', None),
                ],
                0,
            ),
        )

    def test_pairs_never_cross(self):
        found, left = self.changes(
            'Alpha one two three.\n\nBeta four five six.\n',
            'Beta four five seven.\n\nAlpha one two three.\n',
        )
        # A move is a paragraph added before the one it passes and the old one removed.
        self.assertEqual(
            (found, left),
            (
                [
                    ('Alpha', 'Beta four five seven.\nAlpha', None),
                    ('Beta four five six.', '', None),
                ],
                0,
            ),
        )

    def test_each_copy_of_a_repeated_paragraph_is_located_on_its_own(self):
        found, _, _ = desk_finish.google_changes(
            'Keep it short.\n\nMiddle.\n\nKeep it short.\n',
            'Keep it brief.\n\nMiddle.\n\nKeep it brief.\n',
        )
        self.assertEqual(
            [(f['before'], f['context'], f['occurrence']) for f in found],
            [('short', 'Keep it short.', 1), ('short', 'Keep it short.', 2)],
        )
        self.assertEqual(len({f['id'] for f in found}), 2)
        found, _, _ = desk_finish.google_changes(
            'Keep it short.\n\nMiddle.\n\nKeep it short.\n',
            'Keep it short.\n\nMiddle.\n\nKeep it brief.\n',
        )
        self.assertEqual([(f['before'], f['occurrence']) for f in found], [('short', 2)])

    def occurrence(self, baseline, body):
        found, _, expected = desk_finish.google_changes(baseline, body)
        self.assertEqual(len(found), 1)
        return found[0].get('occurrence'), expected[found[0]['id']]['matches']

    def test_occurrences_count_only_what_a_reader_of_the_doc_sees(self):
        # A link target, a table row and an image are not text in the Doc's body paragraphs.
        cases = [
            (
                'See [the guide](https://example.com/setup).\n\nRun setup first.\n\n'
                '**Then** run setup again.\n\nFinally setup ends.\n',
                'See [the guide](https://example.com/setup).\n\nRun setup first.\n\n'
                '**Then** run install again.\n\nFinally setup ends.\n',
            ),
            (
                '| setup | x |\n|---|---|\n\nRun setup first.\n\n**Then** run setup again.\n',
                '| setup | x |\n|---|---|\n\nRun setup first.\n\n**Then** run install again.\n',
            ),
            (
                '![setup diagram](setup.png)\n\nRun setup first.\n\n**Then** run setup again.\n',
                '![setup diagram](setup.png)\n\nRun setup first.\n\n**Then** run install again.\n',
            ),
        ]
        for baseline, body in cases:
            with self.subTest(baseline=baseline[:20]):
                found, _, expected = desk_finish.google_changes(baseline, body)
                self.assertEqual(
                    [(f['before'], f.get('context'), f.get('occurrence')) for f in found],
                    [('setup', 'Then run setup again.', None)],
                    'found by its own paragraph as the Doc shows it',
                )
                self.assertEqual(expected[found[0]['id']]['matches'], 1)

    def test_an_edit_to_one_of_several_copies_after_a_table_row_is_that_copy(self):
        baseline = '| Keep it short. |\n\nKeep it short.\n\nKeep it short.\n\nKeep it short.\n'
        for edited, copy in ((1, 1), (2, 2), (3, 3)):
            lines = ['| Keep it short. |', 'Keep it short.', 'Keep it short.', 'Keep it short.']
            lines[edited] = 'Keep it brief.'
            with self.subTest(edited=edited):
                self.assertEqual(self.occurrence(baseline, '\n\n'.join(lines) + '\n'), (copy, 3))

    def test_a_change_only_to_a_link_address_or_formatting_is_a_comment_on_its_words(self):
        for baseline, body, words, said in (
            (
                'See [docs](https://x.com/setup).\n\nRun setup first.\n',
                'See [docs](https://x.com/install).\n\nRun setup first.\n',
                'docs',
                'Link changed: “docs” now points to https://x.com/install.',
            ),
            (
                'Read [the setup guide](https://x.com/setup) before setup.\n',
                'Read [the setup guide](https://x.com/install) before setup.\n',
                'the setup guide',
                'Link changed: “the setup guide” now points to https://x.com/install.',
            ),
            ('Keep it short.\n', 'Keep it **short**.\n', 'short', 'Make “short” bold.'),
            (
                'Read [the guide](https://x.com/a) now.\n',
                'Read the guide now.\n',
                'the guide',
                'Remove the link from “the guide”.',
            ),
            (
                '### Heading\n\nText.\n',
                'Heading\n\nText.\n',
                'Heading',
                'Make this paragraph normal text.',
            ),
        ):
            with self.subTest(body=body):
                found, left, _ = desk_finish.google_changes(baseline, body)
                self.assertEqual(
                    ([(f['kind'], f['before'], f['reason']) for f in found], left),
                    ([('comment', words, said)], 0),
                )

    def test_a_word_changed_beside_a_link_is_found_in_the_visible_text(self):
        found, left, expected = desk_finish.google_changes(
            'Read [the setup guide](https://x.com/setup) before setup.\n',
            'Read [the setup guide](https://x.com/setup) before install.\n',
        )
        self.assertEqual(
            [(f['before'], f['after'], f.get('occurrence')) for f in found],
            [('setup', 'install', 2)],
        )
        self.assertEqual(expected[found[0]['id']]['text'], 'Read the setup guide before setup.')

    def test_a_table_row_changed_is_a_comment_beside_the_table(self):
        found, left, _ = desk_finish.google_changes(
            'Before the table.\n\n| a | b |\n|---|---|\n\nAfter it.\n',
            'Before the table.\n\n| a | c |\n|---|---|\n\nAfter it.\n',
        )
        self.assertEqual(
            ([(f['kind'], f['before']) for f in found], left),
            ([('comment', 'Before the table.')], 0),
        )
        self.assertIn('The table row “| a | b |” reads “| a | c |”', found[0]['reason'])

    def test_escapes_read_as_the_characters_they_stand_for(self):
        self.assertEqual(
            desk_finish._visible('A \\*star\\* and snake\\_case.'), 'A *star* and snake_case.'
        )

    def guard(self, doc_lines, baseline, body):
        """What the placement guard sends to a Doc of these paragraphs."""
        import test_google_suggestions as fixtures

        inline = fixtures.paragraph_doc(*[([(line + '\n', {})], {}, None) for line in doc_lines])
        found, _, expected = desk_finish.google_changes(baseline, body)
        document = {'document_id': 'fixture-doc', 'tab_ids': ['t.0']}
        free, waiting, unplaced, _ = desk_finish._not_pending(inline, document, found, expected)
        return [(f['kind'], f['before']) for f in free], waiting, unplaced, free

    def test_a_quote_found_in_another_paragraph_goes_as_a_comment_on_a_certain_one(self):
        # The Doc's second paragraph has other words than the desk was made from: the change
        # is not suggested there, but goes as a comment on the paragraph that is certain.
        free, waiting, unplaced, found = self.guard(
            ['Run setup first.', 'Then run setup again later.'],
            'Run setup first.\n\n**Then** run setup again.\n',
            'Run setup first.\n\n**Then** run install again.\n',
        )
        self.assertEqual((free, waiting, unplaced), ([('comment', 'Run setup first.')], 0, 0))
        self.assertIn('“Then run setup again.” reads “Then run install again.”', found[0]['reason'])

    def test_a_quote_the_doc_shows_another_number_of_times_is_never_suggested(self):
        free, waiting, unplaced, _ = self.guard(
            ['Run setup first.', 'Then run setup again.', 'Then run setup again.'],
            'Run setup first.\n\n**Then** run setup again.\n',
            'Run setup first.\n\n**Then** run install again.\n',
        )
        self.assertEqual((free, waiting, unplaced), ([('comment', 'Run setup first.')], 0, 0))
        # With no paragraph the Doc shows once, nothing is placed, and it is counted.
        free, waiting, unplaced, _ = self.guard(
            ['Then run setup again.', 'Then run setup again.'],
            'Then run setup again.\n',
            'Then run install again.\n',
        )
        self.assertEqual((free, waiting, unplaced), ([], 0, 1))

    def test_a_comment_standing_for_several_changes_carries_each_ones_marker(self):
        free, waiting, unplaced, found = self.guard(
            ['Run setup first.', 'Then we run setup on every machine again later.'],
            'Run setup first.\n\nThen we run setup on every machine again.\n',
            'Run setup first.\n\nNow we run setup on every machine today.\n',
        )
        self.assertEqual((free, waiting, unplaced), ([('comment', 'Run setup first.')], 0, 0))
        changes, _, _ = desk_finish.google_changes(
            'Run setup first.\n\nThen we run setup on every machine again.\n',
            'Run setup first.\n\nNow we run setup on every machine today.\n',
        )
        self.assertEqual(len(changes), 2)
        for change in changes:
            self.assertIn('[Blog Studio ' + change['id'] + ']', found[0]['reason'])

    def test_a_comments_id_does_not_change_with_its_wording(self):
        from unittest.mock import patch

        case = ('Keep it short.\n', 'Keep it **short**.\n')
        first = desk_finish.google_changes(*case)[0][0]['id']
        with patch.object(desk_finish, '_restyle', return_value='Embolden “short”.'):
            again = desk_finish.google_changes(*case)[0]
        self.assertEqual((again[0]['id'], again[0]['reason']), (first, 'Embolden “short”.'))

    def test_inserted_words_never_start_with_the_space_already_there(self):
        for after in ('Second new item here.', 'Second 😀 item here.'):
            with self.subTest(after=after):
                (found,), _, _ = desk_finish.google_changes('Second item here.\n', after + '\n')
                import google_suggestions

                keep, end = google_suggestions.trimmed(found['before'], found['after'])
                inserted = found['after'][keep : len(found['after']) - end]
                self.assertFalse(inserted[0].isspace(), inserted)

    def test_each_change_lands_in_the_paragraph_it_is_meant_for(self):
        free, waiting, unplaced, _ = self.guard(
            ['Keep it short.', 'Middle.', 'Keep it short.'],
            'Keep it short.\n\nMiddle.\n\nKeep it short.\n',
            'Keep it short.\n\nMiddle.\n\nKeep it brief.\n',
        )
        self.assertEqual((free, waiting, unplaced), ([('edit', 'short')], 0, 0))


import google_drive  # noqa: E402
import google_roundtrip as rt  # noqa: E402
import google_workflow as gw  # noqa: E402
import test_google_start  # noqa: E402


class DeskGoogleTests(unittest.TestCase):
    start = test_google_start.GoogleStartTests.start

    def setUp(self):
        test_google_start.GoogleStartTests.setUp(self)
        self.addCleanup(lambda: blog_runner.ENGINES.pop(str(self.root), None))
        ident = self.start()['id']
        held = studio._HELD.set(True)
        self.addCleanup(studio._HELD.reset, held)
        self.made = desk.create(self.root, {'article': ident})
        self.ident = self.made['id']
        self.part = self.made['sections'][0]['id']
        # The Doc's name is its title, as when a blog starts from it.
        self.client.doc['title'] = self.made['title']

    def act(self, action, **data):
        from unittest.mock import patch

        with patch.object(google_drive, 'Client', return_value=self.client):
            return desk.dispatch(self.root, action, {'id': self.ident, **data})

    def test_the_desks_latest_wording_is_sent_as_suggestions(self):
        self.assertTrue(desk_jobs.view(self.root, self.ident)['google_suggestions'])
        text = self.made['sections'][0]['text']
        desk.save(self.root, self.ident, 1, self.part, text.replace('slow', 'late'))
        plan = self.act('google-plan', mode='auto')
        self.assertEqual(plan['count'], 1)
        self.assertEqual([(p['before'], p['after']) for p in plan['proposals']], [('slow', 'late')])
        self.assertEqual((plan['left'], plan['suggestions'], plan['comments']), (0, 1, 0))
        self.assertEqual(self.client.writes, 0)
        result = self.act('google-send', plan=plan['plan'], confirmed=True)
        self.assertEqual(result['status'], 'verified-pending')
        writes = self.client.writes
        self.act('google-send', plan=plan['plan'], confirmed=True)
        self.assertEqual(self.client.writes, writes)

    def test_a_send_after_the_desk_changed_is_refused(self):
        text = self.made['sections'][0]['text']
        desk.save(self.root, self.ident, 1, self.part, text.replace('slow', 'late'))
        plan = self.act('google-plan', mode='auto')
        desk.save(self.root, self.ident, 2, self.part, text.replace('slow', 'later'))
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.act('google-send', plan=plan['plan'], confirmed=True)
        with self.assertRaisesRegex(ValueError, 'confirm'):
            self.act('google-send', plan=plan['plan'], confirmed=False)

    def test_nothing_changed_is_said(self):
        with self.assertRaisesRegex(ValueError, 'Nothing new to send'):
            self.act('google-plan', mode='auto')
        # Once the Doc's name is known, nothing changed is said without reading Google.
        self.client.native_read = None
        with self.assertRaisesRegex(ValueError, 'Nothing new to send'):
            self.act('google-plan', mode='auto')

    def test_a_second_batch_sends_only_what_is_new(self):
        text = self.made['sections'][0]['text']
        desk.save(self.root, self.ident, 1, self.part, text.replace('slow', 'late'))
        first = self.act('google-plan', mode='auto')
        self.act('google-send', plan=first['plan'], confirmed=True)
        writes = self.client.writes
        # Sent before, and nothing else changed: said, and nothing is planned.
        with self.assertRaisesRegex(ValueError, '1 change was sent before'):
            self.act('google-plan', mode='auto')
        # A change in another paragraph goes on its own; the first is not sent again.
        draft = desk.read(self.root, self.ident)
        heading = draft['sections'][0]['heading'].replace('delay', 'wait')
        desk.outline_save(
            self.root,
            self.ident,
            draft['revision'],
            [{'id': self.part, 'heading': heading, 'brief': ''}],
        )
        second = self.act('google-plan', mode='auto')
        self.assertEqual(
            [(p['before'], p['after']) for p in second['proposals']], [('delay', 'wait')]
        )
        self.assertEqual(second['sent_before'], 1)
        self.assertEqual(
            self.act('google-send', plan=second['plan'], confirmed=True)['status'],
            'verified-pending',
        )
        self.assertGreater(self.client.writes, writes)
        # A paragraph added above moves the first change; it is still known as sent.
        draft = desk.read(self.root, self.ident)
        desk.save(self.root, self.ident, draft['revision'], 'opening', 'A new first line.')
        with self.assertRaisesRegex(ValueError, '2 changes were sent before'):
            self.act('google-plan', mode='auto')

    def test_a_paragraph_with_a_pending_suggestion_waits_until_it_is_reviewed(self):
        import copy

        unsent = copy.deepcopy(self.client.doc)
        text = self.made['sections'][0]['text']
        desk.save(self.root, self.ident, 1, self.part, text.replace('slow', 'late'))
        first = self.act('google-plan', mode='auto')
        self.act('google-send', plan=first['plan'], confirmed=True)
        desk.save(self.root, self.ident, 2, self.part, text.replace('slow', 'very late'))
        with self.assertRaisesRegex(
            ValueError, 'waits? for the Doc’s owner to decide the earlier suggestion'
        ):
            self.act('google-plan', mode='auto')
        # The Doc's owner rejects it: the paragraph is free again and the new wording goes.
        self.client.doc = unsent
        again = self.act('google-plan', mode='auto')
        self.assertEqual(
            [(p['before'], p['after']) for p in again['proposals']], [('slow', 'very late')]
        )


def link(url):
    return {'link': {'url': url}}


def harbour_doc():
    """A synthetic Doc shaped like a real one: no title line (its name is its title), a bold
    lead line and a bold level-3 heading, links inside paragraphs, curly quotes and a
    paragraph that repeats."""
    import test_google_suggestions as fixtures

    bold, normal, heading = (
        {'bold': True},
        {'namedStyleType': 'NORMAL_TEXT'},
        {'namedStyleType': 'HEADING_3'},
    )
    doc = fixtures.paragraph_doc(
        ([('Plans for the Harbour Data Service\n', bold)], normal, None),
        (
            [
                (
                    'Most early Machine Learning (ML) projects stalled. To move Agentic Search '
                    'past basic demos, we rely on proven ',
                    {},
                ),
                ('data patterns', link('https://example.com/patterns')),
                (' that keep improving.\n', {}),
            ],
            normal,
            None,
        ),
        ([('Key Data Patterns\n', bold)], heading, None),
        (
            [
                ('This is where ', {}),
                ('Harbour Flow', link('https://example.com/flow')),
                (' comes in. Built on the open ', {}),
                ('Stream Kit', link('https://example.com/kit')),
                (' project, it runs batch tasks.\n', {}),
            ],
            normal,
            None,
        ),
        (
            [
                (
                    'It refers to systems, or ‘agents’, that act alone. Event logs track every step.\n',
                    {},
                )
            ],
            normal,
            None,
        ),
        (
            [
                ('Read the ', {}),
                ('setup guide', link('https://example.com/old')),
                (' first.\n', {}),
            ],
            normal,
            None,
        ),
        ([('Keep it short.\n', {})], normal, None),
        ([('A paragraph that goes away.\n', {})], normal, None),
        ([('Keep it short.\n', {})], normal, None),
        ([('The end.\n', {})], normal, None),
    )
    doc['title'] = 'Plans for Harbour'
    return doc


# Every kind of desk change to the Doc above.
HARBOUR_EDITS = (
    ('Most early Machine Learning (ML)', 'Most early machine learning (ML)'),
    ('move Agentic Search', 'move agentic search'),
    ('that keep improving.', 'that improve over time.'),
    (
        'This is where [Harbour Flow](<https://example.com/flow>) comes in. Built on the open '
        '[Stream Kit]',
        '[Harbour Flow](<https://example.com/flow>) is built for this job. Based on the open '
        '[Stream Toolkit]',
    ),
    ('‘agents’,', '“agents,”'),
    ('Event logs', '**Event logs**'),
    (
        '(<https://example.com/old>) first.',
        '(<https://example.com/new>) first.\n\nA new '
        'paragraph with a [link](<https://example.com/added>) in it.',
    ),
    ('A paragraph that goes away.\n\n', ''),
    ('Keep it short.\n\nThe end.', 'Keep it brief.\n\nThe end.'),
)


class GoogleSendAllTests(unittest.TestCase):
    """Every desk change goes to the Google Doc, as a suggestion or a comment: none stays
    only on the desk."""

    def setUp(self):
        import test_google_suggestions as fixtures

        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'workspace'
        studio.initialize(self.root)
        self.addCleanup(lambda: blog_runner.ENGINES.pop(str(self.root), None))
        self.client = self.provider(fixtures)
        capture = self.base / 'capture'
        rt.capture(self.client, 'fixture-doc', 't.0', capture)
        observation = capture / 'observation.json'
        found = json.loads(observation.read_text())
        found['structure_verified'] = True
        observation.write_text(json.dumps(found))
        words = [
            '--root',
            str(self.root),
            'google',
            'start',
            '--title',
            'Plans for Harbour',
            '--observation',
            str(observation),
            '--file',
            str(capture / 'document.md'),
            '--snapshot',
            str(capture),
        ]
        with studio.locked(self.root):
            ident = gw.command(self.root, studio.parser().parse_args(words))['id']
        held = studio._HELD.set(True)
        self.addCleanup(studio._HELD.reset, held)
        self.ident = desk.create(self.root, {'article': ident})['id']

    def provider(self, fixtures):
        client = fixtures.ReviewProvider()
        client.doc = harbour_doc()
        return client

    def act(self, action, **data):
        from unittest.mock import patch

        with patch.object(google_drive, 'Client', return_value=self.client):
            return desk.dispatch(self.root, action, {'id': self.ident, **data})

    def edit(self, changes):
        draft = desk.read(self.root, self.ident)
        for part in ['opening'] + [section['id'] for section in draft['sections']]:
            text = desk.text_of(draft, part)
            changed = text
            for old, new in changes:
                changed = changed.replace(old, new)
            if changed != text:
                desk.save(self.root, self.ident, draft['revision'], part, changed)
                draft = desk.read(self.root, self.ident)

    def desk_text(self):
        """The desk's paragraphs as the Doc shows them, without its title line."""
        directory, _ = studio.item(self.root, 'articles', self.ident)
        lines = [line for line in (directory / 'DRAFT.md').read_text().splitlines() if line.strip()]
        return [desk_finish._visible(line) for line in lines[1:]]

    def doc_text(self, accepted=True):
        doc = self.client.native_read('fixture-doc', accepted_preview=accepted)
        text = ''.join(
            rt.paragraph_text(block['paragraph'])
            for block in doc['tabs'][0]['documentTab']['body']['content']
            if 'paragraph' in block
        )
        return text.splitlines()

    def test_every_change_goes_to_the_doc_and_accepting_all_gives_the_desks_text(self):
        self.edit(HARBOUR_EDITS)
        plan = self.act('google-plan', mode='auto')
        self.assertEqual(plan['left'], 0, 'nothing stays only on the desk')
        self.assertEqual(plan['waiting'], 0)
        self.assertEqual(plan['count'], plan['suggestions'] + plan['comments'])
        edits = [(p['before'], p['after']) for p in plan['proposals'] if p['kind'] == 'edit']
        self.assertEqual(
            edits,
            [
                ('Machine Learning', 'machine learning'),
                ('Agentic Search', 'agentic search'),
                ('keep improving', 'improve over time'),
                ('This is where ', ''),
                ('comes in. Built', 'is built for this job. Based'),
                ('Kit', 'Toolkit'),
                ('‘agents’,', '“agents,”'),
                ('.', '.\nA new paragraph with a link in it.'),
                ('A paragraph that goes away.', ''),
                ('short', 'brief'),
            ],
        )
        removed = [p for p in plan['proposals'] if p.get('remove')]
        self.assertEqual([p['before'] for p in removed], ['A paragraph that goes away.'])
        comments = {p['before']: p['reason'] for p in plan['proposals'] if p['kind'] == 'comment'}
        self.assertEqual(
            comments,
            {
                'Event logs': 'Make “Event logs” bold.',
                'setup guide': 'Link changed: “setup guide” now points to https://example.com/new.',
                # The new paragraph's link is a comment of its own, on a paragraph with no
                # suggestion, never riding on the suggestion that brings the words in.
                'Key Data Patterns': 'In the paragraph “Read the setup guide first.”: Link '
                '“link” to https://example.com/added.',
            },
        )
        repeated = next(p for p in plan['proposals'] if p['before'] == 'short')
        # Placed on the second copy, by the Doc's own indexes.
        copies = [
            block['startIndex']
            for block in self.client.doc['tabs'][0]['documentTab']['body']['content']
            if rt.paragraph_text(block.get('paragraph', {})) == 'Keep it short.\n'
        ]
        self.assertEqual(repeated['start_index'], copies[1] + len('Keep it '))
        self.assertEqual(self.client.writes, 0, 'nothing is sent until Send')
        self.assertNotEqual(self.doc_text(), self.desk_text())
        result = self.act('google-send', plan=plan['plan'], confirmed=True)
        self.assertEqual(result['status'], 'verified-pending')
        self.assertTrue(all(comment['verified'] for comment in result['comments']))
        self.assertEqual(self.doc_text(accepted=False)[-1], 'The end.')
        self.assertEqual(self.doc_text(), self.desk_text(), 'accepting every suggestion')
        # Nothing is sent twice.
        with self.assertRaisesRegex(ValueError, str(plan['count']) + ' changes were sent before'):
            self.act('google-plan', mode='auto')

    def test_a_change_in_a_paragraph_with_a_pending_suggestion_goes_next_time(self):
        self.edit(HARBOUR_EDITS[:1])
        first = self.act('google-plan', mode='auto')
        self.act('google-send', plan=first['plan'], confirmed=True)
        self.edit([('we rely on', 'we count on')])
        with self.assertRaisesRegex(
            ValueError,
            '1 change was sent before; 1 change waits for the Doc’s owner to decide the '
            'earlier suggestion in its paragraph',
        ):
            self.act('google-plan', mode='auto')

    def test_a_title_other_than_the_docs_name_goes_as_a_comment(self):
        draft = desk.read(self.root, self.ident)
        desk.save(self.root, self.ident, draft['revision'], 'title', 'Harbour plans, revised')
        plan = self.act('google-plan', mode='auto')
        self.assertEqual(
            [(p['kind'], p['before'], p['reason']) for p in plan['proposals']],
            [
                (
                    'comment',
                    'Plans for the Harbour Data Service',
                    'Suggested title: “Harbour plans, revised”.',
                )
            ],
        )
        self.assertEqual((plan['suggestions'], plan['comments']), (0, 1))


class GooglePendingTests(GoogleSendAllTests):
    """Sends again while earlier suggestions wait for the Doc's owner, on a closer model of
    Google's suggest mode: a suggested break splits its paragraph, and inserted text takes
    its left neighbour's style until it is set."""

    def provider(self, fixtures):
        import google_model

        return google_model.Model(harbour_doc())

    def send(self):
        plan = self.act('google-plan', mode='auto')
        self.assertEqual(
            self.act('google-send', plan=plan['plan'], confirmed=True)['status'], 'verified-pending'
        )
        return plan

    def accepted(self):
        import google_model

        self.client.decide()
        return google_model.styled_paragraphs(self.client.native_read('x', accepted_preview=True))

    def test_a_note_after_a_suggestion_sent_before_still_goes(self):
        self.edit([('keep improving', 'improve over time')])
        self.send()
        self.edit([('improve over time', '**improve** over time')])
        plan = self.act('google-plan', mode='auto')
        self.assertEqual(
            [(p['kind'], p['reason']) for p in plan['proposals']],
            [
                (
                    'comment',
                    'In the paragraph “Most early Machine Learning (ML) projects stalled. To move Agentic Search past…”: Make “improve” bold.',
                )
            ],
        )
        self.assertEqual(plan['sent_before'], 1)
        draft = desk.read(self.root, self.ident)
        desk.save(self.root, self.ident, draft['revision'], 'title', 'Harbour, renamed')
        plan = self.act('google-plan', mode='auto')
        self.assertIn(
            'Suggested title: “Harbour, renamed”.', [p['reason'] for p in plan['proposals']]
        )

    def test_formatting_added_later_leaves_the_change_sent_before_as_it_was(self):
        self.edit([('The end.', 'The finish.')])
        self.send()
        self.edit([('The finish.', 'The **finish**.')])
        plan = self.act('google-plan', mode='auto')
        self.assertEqual(
            [(p['kind'], p['reason']) for p in plan['proposals']],
            [('comment', 'In the paragraph “The end.”: Make “finish” bold.')],
        )
        self.assertEqual((plan['sent_before'], plan['waiting']), (1, 0))

    def test_copies_are_counted_in_the_text_the_doc_had(self):
        # A pending suggestion adds a copy of "Keep it short." in the last paragraph; the desk
        # then rewords the second copy, which must be the one changed.
        self.edit(
            [
                ('Keep it short.\n\nA paragraph', 'Keep it very short.\n\nA paragraph'),
                ('The end.', 'The end. Keep it short.'),
            ]
        )
        self.send()
        self.edit([('away.\n\nKeep it short.', 'away.\n\nKeep it brief.')])
        plan = self.send()
        self.assertEqual(
            [(p['before'], p['after']) for p in plan['proposals']], [('short', 'brief')]
        )
        texts = [''.join(c for c, _ in chars).strip() for _, chars in self.accepted()]
        self.assertEqual(texts, self.desk_text())

    def test_a_change_to_a_suggestion_still_waiting_waits_and_is_never_undone(self):
        self.edit([('keep improving.', 'keep improving fast.')])
        self.send()
        writes = self.client.writes
        for changes in (
            [('improving fast.', 'improving slowly.')],
            [('improving slowly.', 'improving.')],
        ):
            self.edit(changes)
            with self.assertRaisesRegex(ValueError, 'waits? for the Doc’s owner to decide'):
                self.act('google-plan', mode='auto')
        self.assertEqual(self.client.writes, writes, 'nothing is sent around a waiting suggestion')

    def test_a_new_paragraph_takes_the_kind_and_style_of_the_paragraph_it_joins(self):
        self.edit(
            [
                ('This is where', 'A plain new paragraph.\n\nThis is where'),
                ('act alone. Event logs', 'act alone.\n\nEvent logs'),
            ]
        )
        plan = self.send()
        self.assertFalse(
            [p for p in plan['proposals'] if p['kind'] == 'comment'], 'nothing to fix by hand'
        )
        found = [
            (
                kind,
                ''.join(c for c, _ in chars).strip(),
                {style for c, style in chars if not c.isspace()},
            )
            for kind, chars in self.accepted()
        ]
        self.assertIn(('text', 'A plain new paragraph.', {(False, False, None)}), found)
        self.assertIn(('text', 'Event logs track every step.', {(False, False, None)}), found)
        self.assertEqual([text for _, text, _ in found], self.desk_text())

    def test_a_wrong_style_landing_in_a_split_is_noticed(self):
        original = self.client.native_review_update

        def bold(file_id, revision, requests):
            landed = []
            for request in requests:
                if 'updateTextStyle' in request:
                    request = {
                        'updateTextStyle': {
                            **request['updateTextStyle'],
                            'textStyle': {'bold': True},
                        }
                    }
                landed.append(request)
            return original(file_id, revision, landed)

        self.client.native_review_update = bold
        self.edit([('The end.', 'The end.\n\nA new last paragraph.')])
        plan = self.act('google-plan', mode='auto')
        result = self.act('google-send', plan=plan['plan'], confirmed=True)
        self.assertEqual(result['status'], 'needs-reconciliation')


class ImageFinishingTests(DeskCase):
    """Finishing, the Google suggestion plan and the pre-publish check with images present."""

    def test_a_dropped_or_altered_image_reference_changes_the_structure(self):
        before = 'A paragraph.\n\n![][image1]\n\nAnother.'
        self.assertEqual(desk_finish.changes_structure(before, before), '')
        self.assertEqual(
            desk_finish.changes_structure(before, 'A paragraph.\n\nAnother.'),
            desk_finish.STRUCTURE,
        )
        self.assertEqual(
            desk_finish.changes_structure(before, before.replace('![]', '![A chart]')),
            desk_finish.STRUCTURE,
        )
        # Without counting paragraphs, as an alternative opening is compared, it still counts.
        self.assertEqual(
            desk_finish.changes_structure(before, 'A paragraph. Another.', paragraphs=False),
            desk_finish.STRUCTURE,
        )

    def test_a_word_after_an_image_reference_is_not_taken_for_a_name(self):
        before = 'Intro.\n\n![][image1]\n\nThe end.'
        self.assertEqual(
            desk_finish.changes_facts(before, 'Intro.\n\n![][image1]\n\nThat is all.'), ''
        )
        self.assertEqual(
            desk_finish.changes_facts(
                'See ![Diagram][image1] Here.', 'Look: ![Diagram][image1] Here.'
            ),
            '',
        )
        self.assertEqual(desk_finish._names('Intro ![Diagram][image1] Then [Acme] More'), {'Acme'})
        self.assertNotIn('image1', desk_finish._names('Ask Acme ![][image1] now.'))
        self.assertIn('a name', desk_finish.changes_facts('Ask Acme Labs.', 'Ask the lab.'))
        self.assertIn(
            'a name',
            desk_finish.changes_facts(before, 'Intro.\n\n![][image1]\n\nThe end, at Acme.', True),
        )

    def test_a_change_only_to_an_image_reference_is_nothing_to_apply(self):
        made = desk.create(self.root, {'manuscript': GOOGLE})
        ident = made['id']
        before = 'An opening paragraph.\n\n![][image1]'
        offered = secrets.token_hex(16)
        desk_finish.keep(
            self.root,
            ident,
            offered,
            'finish-copyedit',
            [
                {'part': 'opening', 'before': before, 'after': before.replace('![]', '![A chart]')},
                {'part': 'opening', 'before': 'The end.', 'after': 'That is all.'},
            ],
        )
        seen = desk.read(self.root, ident)['revision']
        act = lambda **data: desk.dispatch(self.root, 'apply', {'id': ident, 'seen': seen, **data})  # noqa: E731
        with self.assertRaisesRegex(ValueError, 'Nothing would change'):
            act(job=offered, items=[{'id': 'p1'}])
        self.assertEqual(desk.read(self.root, ident)['revision'], seen)
        self.assertEqual(desk.versions(self.root, ident, 'opening'), [])
        shown = act(job=offered, items=[{'id': 'p1'}, {'id': 'p2'}])
        self.assertEqual(shown['finished'], {'applied': 1, 'left': ['p1']})
        states = [i['state'] for i in desk_finish.read(self.root, ident, offered)['items']]
        self.assertEqual(states, ['open', 'applied'])

    def test_a_suggestion_that_drops_an_image_is_flagged_and_left_out_of_apply_all(self):
        made = desk.create(self.root, {'manuscript': GOOGLE})
        draft = desk.read(self.root, made['id'])
        items, dropped, _ = desk_finish._read_humanize(
            draft,
            {
                'suggestions': [
                    {
                        'part': 'opening',
                        'before': 'An opening paragraph.\n\n![][image1]',
                        'after': 'A first paragraph.',
                        'why': 'Stock wording.',
                    },
                    {
                        'part': 'opening',
                        'before': 'The end.',
                        'after': 'That is all.',
                        'why': 'Flat.',
                    },
                ]
            },
        )
        self.assertEqual(dropped, 0)
        self.assertIn(desk_finish.STRUCTURE, items[0]['flag'])
        self.assertEqual(items[1]['flag'], '')

    def test_the_google_plan_reads_draft_md_with_its_images_as_the_doc_shows_them(self):
        baseline = GOOGLE.replace('The end.', 'See ![][image1] here.\n\nThe end.')
        body = baseline.replace('More text after', 'More words after').replace('here.', 'there.')
        found, left, paragraphs = desk_finish.google_changes(baseline, body)
        # A paragraph with an image cannot take a suggestion: its change is a comment beside it.
        self.assertEqual(
            [(f['kind'], f['before'], f.get('after')) for f in found],
            [('edit', 'text', 'words'), ('comment', 'The end.', None)],
        )
        self.assertIn('“See here.”, reads “See there.”', found[1]['reason'])
        self.assertEqual(left, 0)
        self.assertNotIn('data:image', json.dumps([found, paragraphs]))
        # An image removed or replaced is made in the Doc by hand, never sent as words.
        for changed, said in (
            (baseline.replace('![][image2]\n\n', ''), 'The image here is removed'),
            (baseline.replace(IMAGE_TWO, IMAGE_ONE), 'The image “image2” changed'),
        ):
            with self.subTest(said=said):
                found, left, paragraphs = desk_finish.google_changes(baseline, changed)
                self.assertEqual(([f['kind'] for f in found], left), (['comment'], 0))
                self.assertIn(said, found[0]['reason'])
                self.assertNotIn('data:image', json.dumps([found, paragraphs]))

    def test_the_prepublish_check_reads_images_sensibly(self):
        import prepublish

        # Synthetic data that happens to hold a placeholder word between base64 marks.
        odd = 'data:image/png;base64,iVBORw0KGgo/TODO+AAAA/TK+AAAA'
        manuscript = (
            '# Images synthetic\n\nText.\n\n![][image1]\n\n![A chart][image2]\n\n![][missing]\n\n'
            '[image1]: <' + odd + '>\n\n[image2]: <' + IMAGE_TWO + '>\n'
        )
        made = desk.create(self.root, {'manuscript': manuscript})
        body = (self.folder(made['id']) / 'DRAFT.md').read_text()
        self.assertIn('[image1]: <' + odd + '>', body)
        codes = [f['code'] for f in prepublish.report(self.root, made['id'])['findings']]
        self.assertNotIn('unfinished-note', codes)
        self.assertEqual(codes.count('image-alt'), 2)  # image1 and the missing one
        self.assertEqual(codes.count('image-source'), 1)  # a reference with no image


class CopyEditTeamTests(TeamCase):
    """Copy edit in a team workspace: waiting and skipped suggestions stay on this computer;
    only an Apply is a decision, committed and shared."""

    def test_settle_and_skip_leave_the_tree_clean_and_apply_is_shared(self):
        import management
        from studio_sync import gitstate, support

        ident = self.made['id']
        fix = {'part': self.part, 'before': 'First text.', 'after': 'The first text.'}

        def worker(engine, payload, guidance, **options):
            return {'content': json.dumps({'suggestions': [fix]}), 'notes': ''}

        def run():
            seen = management.view(self.root, 'desk', {'id': [ident]})['revision']
            management.dispatch(
                self.root, 'desk-finish', {'id': ident, 'seen': seen, 'tool': 'copyedit'}
            )
            tool_jobs.once(blog_runner.Engine(self.root, worker=worker))
            return management.view(self.root, 'desk', {'id': [ident]})

        remote = self.remote_commits()
        shown = run()
        self.assertEqual(gitstate.changed(self.found), [])
        self.assertEqual(self.remote_commits(), remote)
        job = shown['finishing']['copyedit']['job']
        management.dispatch(self.root, 'desk-skip', {'id': ident, 'job': job, 'items': ['p1']})
        self.assertEqual(gitstate.changed(self.found), [])
        self.assertEqual(self.remote_commits(), remote)
        shown = run()
        management.dispatch(
            self.root,
            'desk-apply',
            {
                'id': ident,
                'seen': shown['revision'],
                'job': shown['finishing']['copyedit']['job'],
                'items': [{'id': 'p1'}],
            },
        )
        self.assertEqual(gitstate.changed(self.found), [])
        self.assertGreater(self.remote_commits(), remote)
        self.assertEqual(self.remote_commits(), self.local_commits())
        self.assertIn(
            'The first text.',
            support.git(self.remote, 'show', 'main:blogs/' + ident + '/DRAFT.md'),
        )

    def test_a_carried_or_retired_suggestion_stays_on_this_computer(self):
        import management
        from studio_sync import gitstate

        ident = self.made['id']
        seen = management.view(self.root, 'desk', {'id': [ident]})['revision']
        management.dispatch(
            self.root,
            'desk-save',
            {
                'id': ident,
                'seen': seen,
                'part': self.part,
                'text': 'Agentic AI is here. Their are two parser.',
                'session': 'a' * 16,
            },
        )
        fixes, human = secrets.token_hex(16), secrets.token_hex(16)
        with studio.locked(self.root):
            desk_finish.keep(
                self.root,
                ident,
                fixes,
                'finish-copyedit',
                [
                    {'part': self.part, 'before': 'Agentic AI', 'after': 'agentic AI'},
                    {'part': self.part, 'before': 'Their are', 'after': 'There are'},
                ],
            )
            desk_finish.keep(
                self.root,
                ident,
                human,
                'finish-humanize',
                [
                    {
                        'part': self.part,
                        'before': 'Agentic AI is here.',
                        'after': 'Agentic AI has arrived.',
                    },
                    {'part': self.part, 'before': 'Their are two parser.', 'after': 'Two parsers.'},
                ],
            )
        remote = self.remote_commits()

        def accept(job, item):
            seen = management.view(self.root, 'desk', {'id': [ident]})['revision']
            return management.dispatch(
                self.root, 'desk-apply', {'id': ident, 'seen': seen, 'job': job, 'items': [item]}
            )

        done = accept(fixes, {'id': 'p1'})
        self.assertEqual(done['finished'], {'applied': 1, 'left': [], 'carried': 1})
        done = accept(human, {'id': 'p2'})
        self.assertEqual(done['finished'], {'applied': 1, 'left': [], 'retired': 1})
        self.assertEqual(gitstate.changed(self.found), [], 'the waiting sets are not shared')
        self.assertGreater(self.remote_commits(), remote, 'the accepts are')
        self.assertEqual(self.remote_commits(), self.local_commits())
        shown = management.view(self.root, 'desk', {'id': [ident]})['finishing']
        self.assertEqual(shown['humanize']['items'][0]['before'], 'AI is here.')
        self.assertEqual(shown['copyedit']['items'][1]['state'], 'retired')


if __name__ == '__main__':
    unittest.main()
