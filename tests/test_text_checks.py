"""The mechanical text checks, kept in the shared core and still run by Blog Studio."""

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import marketing_studio  # noqa: F401  Puts core/ on the path.
from studio_core import text_checks

ROOT = Path(__file__).resolve().parents[1]
BLOG_SHIM = ROOT / 'studios' / 'blog' / 'skills' / 'blog-studio' / 'scripts' / 'text_checks.py'


class TextCheckTests(unittest.TestCase):
    def test_lint_finds_a_dash_outside_code_and_quotes(self):
        found = text_checks.lint('A — phrase.', {'no_em_dashes': True})['findings']
        self.assertEqual([hit['rule'] for hit in found], ['em-dash'])
        self.assertEqual(text_checks.lint('"A — phrase."', {'no_em_dashes': True})['findings'], [])

    def test_preserve_flags_a_changed_number(self):
        self.assertTrue(text_checks.preserve('20 hours, then 20 hours.', '20 hours.')['needs_review'])
        self.assertFalse(text_checks.preserve('Same.', 'Same.')['needs_review'])

    def test_reader_facing_notes_finds_a_placeholder(self):
        found = text_checks.reader_facing_notes('Intro. [TODO add a quote]')
        self.assertEqual([hit['rule'] for hit in found], ['reader-facing-note'])
        self.assertEqual(text_checks.reader_facing_notes('A plain line.'), [])

    def test_the_command_line_names_the_product_it_runs_for(self):
        with tempfile.TemporaryDirectory() as folder:
            missing = str(Path(folder) / 'missing.md')
            said = io.StringIO()
            with contextlib.redirect_stderr(said):
                code = text_checks.main('Test Studio', ['lint', '--file', missing])
        self.assertEqual(code, 1)
        self.assertTrue(said.getvalue().startswith('Test Studio text check: '), said.getvalue())

    def test_blog_s_command_line_still_runs(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'draft.md'
            path.write_text('one two three')
            ran = subprocess.run(
                [sys.executable, str(BLOG_SHIM), 'count', '--file', str(path)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(json.loads(ran.stdout)['words'], 3)
            ran = subprocess.run(
                [sys.executable, str(BLOG_SHIM), 'count', '--file', str(Path(folder) / 'gone')],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(ran.returncode, 1)
        self.assertTrue(ran.stderr.startswith('Blog Studio text check: '), ran.stderr)

    def test_blog_s_module_names_are_the_shared_ones(self):
        sys.path.insert(0, str(BLOG_SHIM.parent))
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location('blog_text_checks', BLOG_SHIM)
            blog = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(blog)
        finally:
            sys.path.remove(str(BLOG_SHIM.parent))
        for name in ('lint', 'preserve', 'carried_over', 'reader_facing_notes', 'facts',
                     'mask_protected', 'PROTECTED', 'URL', 'NOTE_START', 'READER_FACING_NOTE'):
            self.assertIs(getattr(blog, name), getattr(text_checks, name), name)


if __name__ == '__main__':
    unittest.main()
