"""Finishing on the desk: proposals previewed, then applied, edited or skipped."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import secrets
import unittest

import blog_runner
import desk
import desk_finish
import desk_jobs
import studio
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


if __name__ == '__main__':
    unittest.main()
