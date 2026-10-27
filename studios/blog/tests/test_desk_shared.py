"""Blog Studio's desk runs on the shared desk parts in studio_core.drafting."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import unittest
from unittest.mock import patch

import desk
import desk_finish
import desk_images
import desk_jobs
import tool_jobs
from studio_core import step_times
from studio_core.drafting import (
    basis,
    guards,
    parts,
    prompts,
    proofread,
    proposals,
    record,
    versions,
)
from test_desk import DeskCase
from test_desk_jobs import DeskJobCase


class SharedCodecTests(unittest.TestCase):
    def test_the_desk_uses_the_shared_codec(self):
        self.assertIs(desk._divide, parts.divide)
        self.assertIs(desk.has_heading, parts.has_heading)
        self.assertIs(desk.outline_from, parts.outline_from)
        self.assertIs(desk.SECTION, parts.SECTION)
        self.assertEqual(desk.PARTS, ('title', 'opening'))
        self.assertIs(desk.PART, parts.MARKDOWN.part)
        self.assertEqual(desk.CODEC.fixed, parts.MARKDOWN.fixed)
        # Blog's split and join keep images beside the text: the shared ones, with its hooks.
        found = desk.split('# T\n\nOpen.\n\n## One\n\nA.\n')
        self.assertEqual(list(found), ['title', 'opening', 'sections', 'images'])
        self.assertEqual(desk.join(found), '# T\n\nOpen.\n\n## One\n\nA.\n')


class SharedChecksTests(unittest.TestCase):
    def test_finishing_checks_with_the_shared_guards_and_proofread(self):
        self.assertIs(desk_finish.STRUCTURE, guards.STRUCTURE)
        self.assertIs(desk_finish._mask_indented, proofread.mask_indented)
        self.assertIs(desk_finish._sentences, proofread.sentences)
        self.assertEqual(desk_images.REFERENCE.pattern, guards.REFERENCE.pattern)
        self.assertEqual(
            desk_finish.changes_facts('In 2024.', 'In 2025.'),
            'Check the facts: this changes a number.',
        )


class SharedRecordTests(DeskCase):
    def test_the_desk_record_is_the_shared_one_with_blog_s_store(self):
        made = self.make()
        kept = desk._drafting(self.root)
        self.assertIsInstance(kept, record.Desk)
        self.assertEqual((kept.store.product, kept.store.word), ('Blog Studio', 'blog'))
        self.assertEqual(desk.SOURCES, versions.SOURCES + ('chat', 'google'))
        self.assertEqual(kept.store.folder(made['id']), self.folder(made['id']) / 'desk')

    def test_a_save_still_reaches_blog_s_own_write(self):
        made = self.make()
        part = made['sections'][0]['id']
        with patch('desk._write', side_effect=OSError('Synthetic disk failure')) as write:
            with self.assertRaisesRegex(OSError, 'Synthetic disk failure'):
                desk.save(self.root, made['id'], 1, part, 'New first text.')
        self.assertEqual(write.call_args.args[3], [part])
        self.assertEqual(desk.read(self.root, made['id'])['revision'], 1)

    def test_a_title_holding_an_image_is_refused_by_blog_s_own_rule(self):
        made = self.make()
        with self.assertRaisesRegex(ValueError, desk.TITLE_IMAGE):
            desk.save(self.root, made['id'], 1, 'title', 'A ![x](data:image/png;base64,AAAA) title')


class SharedSettleTests(DeskJobCase):
    def ready(self, job, content, **result):
        saved = self.saved(job)
        saved.update(
            status='ready', result={'content': content, 'notes': '', **result}, finished_at='x'
        )
        tool_jobs.write(self.root, saved)
        return saved

    def test_a_flagged_rewrite_still_lands_and_its_job_keeps_the_check(self):
        desk.save(self.root, self.ident, 1, self.part, 'First text from 2024.')
        job = desk_jobs.section(self.root, self.ident, 2, self.part, 'Update the year.')
        self.ready(job, 'First text from 2025.')
        self.assertEqual(desk_jobs.settle(self.root, self.ident), [job['id']])
        draft = desk.read(self.root, self.ident)
        self.assertEqual(draft['sections'][0]['text'], 'First text from 2025.')
        check = {self.part: 'Check the facts: this changes a number.'}
        self.assertEqual(tool_jobs.read(self.root, job['id'])['checks'], check)
        self.assertEqual(desk_jobs.view(self.root, self.ident)['jobs'][-1]['checks'], check)

    def test_a_clean_rewrite_keeps_no_checks(self):
        job = desk_jobs.section(self.root, self.ident, 1, self.part, 'Say it plainly.')
        self.ready(job, 'First words.')
        desk_jobs.settle(self.root, self.ident)
        self.assertTrue(tool_jobs.read(self.root, job['id'])['applied'])
        self.assertNotIn('checks', tool_jobs.read(self.root, job['id']))
        self.assertEqual(desk_jobs.view(self.root, self.ident)['jobs'][-1]['checks'], {})

    def test_a_flagged_selection_edit_keeps_the_check_too(self):
        desk.save(self.root, self.ident, 1, self.part, 'Run `a` here.')
        job = desk_jobs.selection(self.root, self.ident, 2, self.part, '`a`', 'fix', '', 4)
        self.ready(job, '`b`')
        desk_jobs.settle(self.root, self.ident)
        self.assertEqual(desk.read(self.root, self.ident)['sections'][0]['text'], 'Run `b` here.')
        self.assertEqual(
            tool_jobs.read(self.root, job['id'])['checks'], {self.part: guards.STRUCTURE}
        )

    def test_a_flagged_first_pass_still_lands_and_keeps_each_part_s_check(self):
        import json

        desk.save(self.root, self.ident, 1, self.part, 'First text from 2024.')
        job = desk_jobs.first_pass(self.root, self.ident, 2, 'tighten')
        self.ready(job, json.dumps([{'id': self.part, 'text': 'First text from 2025.'}]))
        desk_jobs.settle(self.root, self.ident)
        self.assertEqual(
            desk.read(self.root, self.ident)['sections'][0]['text'], 'First text from 2025.'
        )
        self.assertEqual(
            tool_jobs.read(self.root, job['id'])['checks'],
            {self.part: 'Check the facts: this changes a number.'},
        )

    def test_a_flagged_whole_draft_revision_still_lands_and_keeps_the_check(self):
        desk.save(self.root, self.ident, 1, self.part, 'First text from 2024.')
        job = desk_jobs.revise_all(self.root, self.ident, 2, 'Update the year.')
        self.assertEqual(self.saved(job)['metadata']['desk']['part'], self.part)
        self.ready(job, 'First text from 2025.')
        desk_jobs.settle(self.root, self.ident)
        self.assertEqual(
            desk.read(self.root, self.ident)['sections'][0]['text'], 'First text from 2025.'
        )
        self.assertIn('a number', tool_jobs.read(self.root, job['id'])['checks'][self.part])
        desk_jobs.stop(self.root, self.ident, job['id'])  # The note's next section waits.

    def test_the_section_job_reads_the_shared_edit_rule(self):
        job = desk_jobs.section(self.root, self.ident, 1, self.part, 'Add an example.')
        self.assertTrue(self.saved(job)['guidance'].startswith(prompts.edit_rule('blog draft')))
        job = desk_jobs.stop(self.root, self.ident, job['id'])

    def test_the_jobs_land_through_the_shared_basis_rule(self):
        self.assertIs(desk_jobs.fingerprint, basis.fingerprint)
        self.assertIs(desk_jobs.busy, basis.busy)
        self.assertEqual(desk_jobs.STALE, basis.stale())
        self.assertIs(desk_jobs.ACTIONS, prompts.ACTIONS)

    def test_a_step_s_time_is_kept_where_it_was_with_the_shared_estimate(self):
        self.assertIs(desk_jobs._seconds, step_times.seconds)
        for seconds in (60, 180, 600):
            desk_jobs._note_time(self.root, 'draft:short', seconds)
        self.assertEqual(desk_jobs.expected_minutes(self.root, 'draft', 'short'), 3)
        self.assertEqual(desk_jobs.expected_minutes(self.root, 'outline', 'short'), 1)
        kept = desk_jobs._times_path(self.root)
        self.assertEqual(kept.name, 'desk-step-times.json')
        self.assertEqual(kept.parent.name, '.blog-runs')


class SharedProposalTests(DeskJobCase):
    JOB = 'c' * 32

    def offer(self):
        part = self.made['sections'][1]['id']
        item = {'part': part, 'before': 'Second text.', 'after': 'Two.'}
        return desk_finish.keep(self.root, self.ident, self.JOB, 'finish-humanize', [item])

    def test_finishing_keeps_its_sets_keyed_blog_with_the_shared_proposals(self):
        made = self.offer()
        self.assertEqual(made['blog'], self.ident)
        self.assertIsInstance(desk_finish._proposals(self.root), proposals.Proposals)
        self.assertIs(desk_finish.GONE, proposals.GONE)
        where = desk.BlogStore(self.root).local(self.ident, self.JOB + '.json')
        self.assertTrue(where.is_file())
        done = desk_finish.apply(self.root, self.ident, 1, self.JOB, [{'id': 'p1'}])
        self.assertEqual(done, {'applied': 1, 'left': []})
        self.assertEqual(
            desk.versions(self.root, self.ident, made['items'][0]['part'])[0]['source'], 'finishing'
        )

    def test_rebuilding_the_newest_sets_still_reaches_this_module_s_sets(self):
        from unittest.mock import patch

        self.offer()
        desk.BlogStore(self.root).local(self.ident, proposals.LATEST).unlink()
        with patch('desk_finish.sets', side_effect=AssertionError('read every set')):
            with self.assertRaisesRegex(AssertionError, 'read every set'):
                desk_finish.summary(self.root, self.ident, desk.read(self.root, self.ident))
        shown = desk_finish.summary(self.root, self.ident, desk.read(self.root, self.ident))
        self.assertEqual(shown['humanize']['job'], self.JOB)

    def test_an_apply_waits_for_a_job_working_on_its_part(self):
        self.offer()
        desk_jobs.first_pass(self.root, self.ident, 1, 'tighten')
        with self.assertRaisesRegex(ValueError, 'A desk job is working on this part.'):
            desk_finish.apply(self.root, self.ident, 1, self.JOB, [{'id': 'p1'}])


if __name__ == '__main__':
    unittest.main()
