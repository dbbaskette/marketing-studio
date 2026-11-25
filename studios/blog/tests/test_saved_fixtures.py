"""The static saved-flow fixtures load as stored, only into a disposable workspace, and name
nothing of this computer. (They were proven against the saved flow that wrote them while it
ran; that flow and its capture were retired with GitHub issue #542, and the stored bytes
stay.)
"""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import tempfile
from pathlib import Path
import unittest

import saved_fixtures


class SavedFixtureTests(unittest.TestCase):
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

    def test_a_load_refuses_anything_but_a_disposable_workspace(self):
        with tempfile.TemporaryDirectory() as folder:
            for root in (
                Path(tempfile.gettempdir()),  # The temporary folder itself.
                Path(folder) / 'writing',  # No Blog Studio workspace there.
                Path(isolation.PLACE),  # The test run's own home and settings.
            ):
                with self.subTest(root=str(root)), self.assertRaises(RuntimeError):
                    saved_fixtures.load(root, 'brief-only')
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_no_fixture_names_this_computer(self):
        for path in saved_fixtures.FIXTURES.rglob('*'):
            if path.is_file():
                raw = path.read_bytes()
                with self.subTest(path=str(path.relative_to(saved_fixtures.FIXTURES))):
                    self.assertNotIn(b'/Users/', raw)
                    self.assertNotIn(b'/home/', raw)
                    self.assertNotIn(b'/var/folders/', raw)
                    self.assertNotIn(tempfile.gettempdir().encode(), raw)


if __name__ == '__main__':
    unittest.main()
