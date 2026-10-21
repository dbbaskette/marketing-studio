"""No test reads or changes this computer's own studio settings or data."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import os
from pathlib import Path
import re
import unittest

TESTS = Path(__file__).resolve().parent
REAL_HOME = os.path.expanduser('~' + os.environ.get('USER', ''))
FIRST = re.compile(r'\A(?:"""[\s\S]*?"""\s*)?import isolation\b')


class IsolationTests(unittest.TestCase):
    def test_every_test_file_imports_the_isolation_first(self):
        files = sorted(TESTS.glob('test*.py')) + [TESTS / 'hub_fixtures.py']
        late = [path.name for path in files if not FIRST.match(path.read_text())]
        self.assertEqual(
            late,
            [],
            'Import isolation before anything else, right after the docstring, so no test '
            'reads the real studios config or Blog Studio data.',
        )

    def test_the_home_folder_settings_and_data_are_a_temporary_place(self):
        place = Path(isolation.PLACE).resolve()
        self.assertEqual(Path.home().resolve(), place / 'home')
        home = Path(REAL_HOME).resolve()
        for name in ('STUDIOS_CONFIG', 'BLOG_STUDIO_DATA'):
            value = Path(os.environ[name]).resolve()
            with self.subTest(name=name):
                self.assertFalse(value.is_relative_to(home / '.config'), value)
                self.assertFalse(value.is_relative_to(home / '.local'), value)
                self.assertTrue(value.is_relative_to(place), value)

    def test_analysis_finds_no_assistant_in_the_shared_settings(self):
        import source_curator

        root = Path(isolation.PLACE) / 'workspace'
        root.mkdir(exist_ok=True)
        self.assertIsNone(source_curator.harness(root))


if __name__ == '__main__':
    unittest.main()
