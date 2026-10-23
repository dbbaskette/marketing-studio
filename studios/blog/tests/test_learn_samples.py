"""How many samples one learning job takes, and how long ones are fitted to it."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import tempfile
import unittest
from pathlib import Path

import article_tools
import studio


class LearnSampleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / 'workspace'
        studio.initialize(self.root)

    def sample(self, name, text):
        from types import SimpleNamespace

        path = Path(tempfile.mkdtemp(dir=self.root.parent)) / (name + '.md')
        path.write_text(text)
        return studio.source_command(
            self.root,
            SimpleNamespace(
                action='add',
                name=name,
                file=str(path),
                content=text,
                text_file=None,
                origin=path.name,
                purpose=['voice-sample'],
                author='Synthetic Author',
                note='',
                status='ready',
            ),
        )['id']

    def test_twenty_samples_are_taken_and_twenty_one_are_refused(self):
        ids = [self.sample('post%d' % n, 'Sentence %d.\n' % n) for n in range(21)]
        self.assertEqual(len(article_tools.samples(self.root, ids[:20])), 20)
        with self.assertRaisesRegex(ValueError, 'one to twenty'):
            article_tools.samples(self.root, ids)

    def test_long_samples_are_cut_to_a_fair_share_and_short_ones_kept_whole(self):
        found = [
            {'id': 'short', 'text': 'Short.'},
            {'id': 'long-a', 'text': ('Paragraph. ' * 50 + '\n\n') * 200},
            {'id': 'long-b', 'text': ('Another. ' * 50 + '\n\n') * 200},
        ]
        fitted = article_tools.shared(found, budget=60_000)
        self.assertEqual(fitted[0], found[0])
        for entry in fitted[1:]:
            self.assertTrue(entry['excerpted'])
            self.assertIn('[Cut here to fit one job', entry['text'])
            self.assertLess(len(entry['text']), 31_000)
        self.assertLessEqual(sum(len(e['text']) for e in fitted), 60_000 + 200)
        self.assertEqual(
            article_tools.shared(found, budget=60_000), fitted, 'the same cut each time'
        )
        self.assertEqual(article_tools.shared(found[:1]), found[:1])

    def test_a_sample_up_to_200000_characters_is_read(self):
        ident = self.sample('long', 'Word. ' * 30_000)
        self.assertEqual(len(article_tools.samples(self.root, [ident])), 1)
        too_long = self.sample('too-long', 'Word. ' * 40_000)
        with self.assertRaisesRegex(ValueError, 'shorter'):
            article_tools.samples(self.root, [too_long])


if __name__ == '__main__':
    unittest.main()
