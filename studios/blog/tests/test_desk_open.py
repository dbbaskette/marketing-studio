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

    def test_opening_twice_returns_the_same_desk(self):
        found = self.finished()
        first = desk.open_run(self.root, found['id'])
        desk.save(self.root, found['id'], 1, 'opening', 'Changed opening.')
        again = desk.open_run(self.root, found['id'])
        self.assertEqual(again['opening'], 'Changed opening.')
        self.assertEqual(first['sections'][0]['id'], again['sections'][0]['id'])

    def test_an_unfinished_run_is_refused(self):
        found = self.create(page=True)
        self.assertFalse(runner.engine(self.root).describe(found['id'])['desk_open'])
        with self.assertRaisesRegex(ValueError, 'Finish this blog, then open it on the desk'):
            desk.open_run(self.root, found['id'])
        self.assertFalse(
            studio.inside(runner.load(self.root, found['id'])[0], 'desk', 'draft.json').exists()
        )


if __name__ == '__main__':
    unittest.main()
