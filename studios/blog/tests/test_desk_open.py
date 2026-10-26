"""A finished step-by-step blog opens on the writing desk; its run stays as it was."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import unittest

import blog_runner as runner
import desk
import management
import studio
from test_blog_runner import RunnerCase


class OpenOnTheDeskTests(RunnerCase):
    def finished(self, **extra):
        found = self.create(page=True, **extra)
        for _ in range(8):
            if found['complete']:
                return found
            content = None
            if found['next'] == 'draft':
                content = '# Synthetic gateway guide\n\nOpening.\n\n## Why\n\nBecause.\n'
            self.submit(runner.survey(self.root, found['id']), content, page=True)
            found = self.approve(runner.survey(self.root, found['id']), page=True)
        self.fail('The run did not finish.')

    def state(self, ident):
        directory, _, _ = runner.load(self.root, ident)
        return (directory / runner.STATE).read_bytes()

    def test_opening_a_finished_run_creates_the_desk_and_leaves_the_run(self):
        found = self.finished(tone='Warm')
        before = self.state(found['id'])
        shown = runner.engine(self.root).describe(found['id'])
        self.assertTrue(shown['desk_open'])
        self.assertFalse(shown['on_desk'])
        opened = management.dispatch(self.root, 'desk-open', {'id': found['id']})
        self.assertEqual(opened['title'], 'Synthetic gateway guide')
        self.assertEqual(opened['opening'], 'Opening.')
        self.assertEqual(opened['sections'][0]['heading'], 'Why')
        self.assertEqual(opened['tone'], 'Warm')
        self.assertTrue(opened['run'])
        self.assertEqual(self.state(found['id']), before)
        self.assertTrue(runner.engine(self.root).describe(found['id'])['on_desk'])
        row = next(r for r in runner.catalog(self.root)['items'] if r['id'] == found['id'])
        self.assertEqual(row['flow'], 'desk')

    def test_a_finished_draft_of_more_than_sixty_sections_is_refused_readably(self):
        found = self.finished()
        directory, _, _ = runner.load(self.root, found['id'])
        many = '# Many\n\n' + '\n\n'.join('## H%d\n\nText.' % n for n in range(61)) + '\n'
        (directory / 'DRAFT.md').write_text(many)
        with self.assertRaisesRegex(ValueError, 'Keep the draft to 60 sections.'):
            management.dispatch(self.root, 'desk-open', {'id': found['id']})
        self.assertFalse((directory / 'desk' / 'draft.json').exists())

    def test_opening_twice_returns_the_same_desk(self):
        found = self.finished()
        with studio.locked(self.root):
            first = desk.open_run(self.root, found['id'])
            desk.save(self.root, found['id'], 1, 'opening', 'Changed opening.')
            again = desk.open_run(self.root, found['id'])
        self.assertEqual(again['opening'], 'Changed opening.')
        self.assertEqual(first['sections'][0]['id'], again['sections'][0]['id'])

    def test_a_finished_blog_edited_in_the_old_editor_still_opens_with_its_latest_text(self):
        import manuscript_editor

        found = self.finished()
        current = manuscript_editor.read(self.root, found['id'])
        edited = current['content'].replace('Because.', 'Because, edited in the editor.')
        management.dispatch(
            self.root,
            'editor-save',
            {'id': found['id'], 'expected': current['expected'], 'content': edited},
        )
        shown = runner.engine(self.root).describe(found['id'])
        self.assertFalse(shown['complete'], 'the edit reads as a stale draft')
        self.assertTrue(shown['desk_open'])
        row = next(r for r in runner.catalog(self.root)['items'] if r['id'] == found['id'])
        self.assertTrue(row['desk_open'], 'the list knows it can go on the desk')
        self.assertTrue(manuscript_editor.read(self.root, found['id'])['operation']['desk_open'])
        opened = management.dispatch(self.root, 'desk-open', {'id': found['id']})
        self.assertEqual(opened['sections'][0]['text'], 'Because, edited in the editor.')

    def test_a_run_step_under_way_keeps_the_blog_off_the_desk(self):
        from unittest.mock import patch

        import manuscript_editor

        found = self.finished()
        current = manuscript_editor.read(self.root, found['id'])
        edited = current['content'].replace('Because.', 'Because, edited.')
        management.dispatch(
            self.root,
            'editor-save',
            {'id': found['id'], 'expected': current['expected'], 'content': edited},
        )
        # Continue it: a polish step is queued on the run.
        current = manuscript_editor.read(self.root, found['id'])
        with patch.object(runner.Engine, 'start', return_value=None):
            manuscript_editor.dispatch(
                self.root,
                'check',
                {'id': found['id'], 'expected': current['expected'], 'check': 'polish'},
            )
        shown = runner.engine(self.root).describe(found['id'])
        self.assertIn(shown['status'], ('queued', 'working'))
        self.assertFalse(shown['desk_open'])
        with self.assertRaisesRegex(ValueError, 'is under way'):
            management.dispatch(self.root, 'desk-open', {'id': found['id']})
        directory = runner.load(self.root, found['id'])[0]
        self.assertFalse((directory / 'desk' / 'draft.json').exists())

    def test_a_submit_for_a_blog_on_the_desk_writes_nothing(self):
        found = self.finished()
        management.dispatch(self.root, 'desk-open', {'id': found['id']})
        directory = runner.load(self.root, found['id'])[0]
        before = {p: p.read_bytes() for p in directory.rglob('*') if p.is_file()}
        with self.assertRaisesRegex(ValueError, 'on the desk'):
            runner.submit(
                self.root,
                found['id'],
                'draft',
                {'content': '# Late\n\n## Why\n\nA late result.\n', 'notes': ''},
                'x',
                page=True,
            )
        after = {p: p.read_bytes() for p in directory.rglob('*') if p.is_file()}
        self.assertEqual(after, before)

    def test_an_unfinished_run_is_refused(self):
        found = self.create(page=True)
        self.assertFalse(runner.engine(self.root).describe(found['id'])['desk_open'])
        with self.assertRaisesRegex(ValueError, 'Finish this blog, then open it on the desk'):
            with studio.locked(self.root):
                desk.open_run(self.root, found['id'])
        self.assertFalse(
            studio.inside(runner.load(self.root, found['id'])[0], 'desk', 'draft.json').exists()
        )

    def test_once_on_the_desk_the_run_is_read_only_and_reads_as_it_ended(self):
        found = self.finished()
        management.dispatch(self.root, 'desk-open', {'id': found['id']})
        management.dispatch(
            self.root,
            'desk-save',
            {
                'id': found['id'],
                'seen': 1,
                'part': 'opening',
                'text': 'Changed on desk.',
                'session': 'a' * 16,
            },
        )
        shown = runner.engine(self.root).describe(found['id'])
        self.assertEqual(
            (shown['complete'], shown['status'], shown['next']), (True, 'on-desk', None)
        )
        self.assertEqual({row['status'] for row in shown['stages']}, {'approved'})
        for action in ('changes', 'resume', 'apply-review'):
            with self.assertRaisesRegex(ValueError, 'on the desk. Edit it there'):
                management.dispatch(
                    self.root, 'run-' + action, {'id': found['id'], 'expected': shown['expected']}
                )
        directory, record, run = runner.load(self.root, found['id'])
        with self.assertRaisesRegex(ValueError, 'on the desk'):
            runner.save(self.root, directory, record, run, 'A late decision')


class SavedBlogVoiceTests(RunnerCase):
    def test_a_saved_blog_brought_to_the_desk_keeps_its_pinned_voice(self):
        found = self.create(page=True)
        directory, record, _ = runner.load(self.root, found['id'])
        (directory / runner.STATE).unlink()  # A saved blog with no run: brought by `article`.
        record['voice'] = {'mode': 'profile', 'profile_id': 'someone', 'revision': 2, 'tone': ''}
        studio.persist(directory, 'articles', record)
        (directory / 'DRAFT.md').write_text('# Saved\n\nOpening.\n\n## A\n\nText.\n')
        made = management.dispatch(
            self.root,
            'desk-create',
            {'operation': 'e' * 32, 'article': found['id'], 'tone': 'Warm'},
        )
        self.assertEqual(made['tone'], 'Warm', 'the desk writes with its tone')
        _, after = studio.item(self.root, 'articles', found['id'])
        self.assertEqual(after['voice'], record['voice'], 'the record keeps its pin')


if __name__ == '__main__':
    unittest.main()
