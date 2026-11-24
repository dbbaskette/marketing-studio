"""The static saved-flow fixtures are what the saved flow writes today.

The proof of fidelity for fixtures/saved/: each stop is made again by the saved step-by-step
flow in a disposable workspace (saved_fixtures.capture) and compared with the stored tree,
byte for byte except the fields that follow what is installed (saved_fixtures.FOLLOWS_INSTALLED).
This file and saved_fixtures.Maker/capture go when the saved flow is retired (GitHub issue
#542, phase C); the fixtures and saved_fixtures.load stay.
"""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import saved_fixtures


class SavedFixtureTests(unittest.TestCase):
    def capturable(self):
        """Every fixture this run can make again: the two whose research really ran need the
        pinned Harness Research stand-in (STUDIO_TEST_RESEARCH_RUNTIME)."""
        return [
            name
            for name in saved_fixtures.MAKERS
            if saved_fixtures.RESEARCH_RUNTIME or name not in saved_fixtures.NEEDS_RESEARCH
        ]

    def test_every_stored_fixture_is_what_the_saved_flow_writes_now(self):
        for name in self.capturable():
            with self.subTest(fixture=name):
                made, kept = saved_fixtures.capture(name), saved_fixtures.stored(name)
                self.assertEqual(sorted(made), sorted(kept))
                self.assertTrue(saved_fixtures.same(made, kept))

    def test_the_comparison_holds_when_blog_studio_has_a_newer_version(self):
        """The stored bytes stay as captured at their version; a capture made by a later
        version differs only in the fields that follow the installed version."""
        import hub_store

        with patch.object(hub_store, 'VERSION', '99.1.0'):
            for name in ('brief-only', 'draft-gate-paused', 'finished-page'):
                with self.subTest(fixture=name):
                    made, kept = saved_fixtures.capture(name), saved_fixtures.stored(name)
                    session = next(n for n in made if n.endswith('/session.json'))
                    self.assertIn(b'"99.1.0"', made[session])  # It really follows the version.
                    self.assertNotEqual(made[session], kept[session])
                    self.assertTrue(saved_fixtures.same(made, kept))
        # Anything else that differs still fails the comparison.
        made = saved_fixtures.stored('brief-only')
        session = next(n for n in made if n.endswith('/session.json'))
        changed = {**made, session: made[session].replace(b'Synthetic', b'Changed', 1)}
        self.assertFalse(saved_fixtures.same(changed, made))

    def test_a_capture_never_uses_this_computers_research_helper(self):
        with patch.dict(os.environ, {'HARNESS_RESEARCH_RUNTIME': '/elsewhere/harness-research'}):
            made, kept = saved_fixtures.capture('brief-only'), saved_fixtures.stored('brief-only')
        self.assertTrue(saved_fixtures.same(made, kept))

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
