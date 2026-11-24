"""The static saved-flow fixtures are what the saved flow writes today.

The proof of fidelity for fixtures/saved/: each stop is made again by the saved step-by-step
flow in a disposable workspace (saved_fixtures.capture) and compared, byte for byte, with the
stored tree. This file and saved_fixtures.Maker/capture go when the saved flow is retired
(GitHub issue #542, phase C); the fixtures and saved_fixtures.load stay.
"""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import tempfile
from pathlib import Path
import unittest

import saved_fixtures


class SavedFixtureTests(unittest.TestCase):
    def test_every_stored_fixture_is_what_the_saved_flow_writes_now(self):
        for name in saved_fixtures.MAKERS:
            with self.subTest(fixture=name):
                self.assertEqual(saved_fixtures.capture(name), saved_fixtures.stored(name))

    def test_every_stored_fixture_has_its_maker_and_one_blog(self):
        stored = sorted(path.name for path in saved_fixtures.FIXTURES.iterdir())
        self.assertEqual(stored, sorted(saved_fixtures.MAKERS))
        for name in stored:
            with self.subTest(fixture=name):
                blogs = list((saved_fixtures.FIXTURES / name / 'articles').iterdir())
                self.assertEqual(len(blogs), 1)

    def test_a_load_copies_the_stored_bytes_and_replaces_only_its_own_blog(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'writing'
            (root / 'articles' / 'another-blog').mkdir(parents=True)
            (root / 'articles' / 'another-blog' / 'session.json').write_text('{}')
            ident = saved_fixtures.load(root, 'draft-gate-paused')
            stored = saved_fixtures.stored('draft-gate-paused')
            for name, raw in stored.items():
                self.assertEqual((root / name).read_bytes(), raw)
            (root / 'articles' / ident / 'extra.md').write_text('Left by a test.')
            self.assertEqual(saved_fixtures.load(root, 'draft-gate-paused'), ident)
            self.assertFalse((root / 'articles' / ident / 'extra.md').exists())
            self.assertTrue((root / 'articles' / 'another-blog' / 'session.json').exists())

    def test_no_fixture_names_this_computer(self):
        for path in saved_fixtures.FIXTURES.rglob('*'):
            if path.is_file():
                raw = path.read_bytes()
                with self.subTest(path=str(path.relative_to(saved_fixtures.FIXTURES))):
                    self.assertNotIn(b'/Users/', raw)
                    self.assertNotIn(b'/home/', raw)
                    self.assertNotIn(tempfile.gettempdir().encode(), raw)


if __name__ == '__main__':
    unittest.main()
