"""Actual desk JavaScript with synthetic DOM/API responses; no browser or accounts."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
from pathlib import Path
import shutil
import subprocess
import unittest


class ManagementUITests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is required for desk-script checks')
    def test_management_client(self):
        repo = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            ['node', 'scripts/ci/check-management.cjs'], cwd=repo, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_narrow_toolbar_menu_is_contained_by_full_toolbar_row(self):
        # The menu used to anchor right to a More button near x=96, clipping its
        # left edge on a 390px viewport. Its containing block must be the full row.
        repo = Path(__file__).resolve().parents[1]
        css = (repo / 'skills/blog-studio/assets/management/blog.css').read_text()
        narrow = css[css.rindex('@media(max-width:52rem)') :]
        self.assertRegex(narrow, r'\.toolbar-actions\{[^}]*position:relative;[^}]*width:100%')
        self.assertRegex(narrow, r'\.toolbar-actions \.menu\{position:static\}')
        self.assertRegex(
            narrow,
            r'\.menu-list\{left:0;right:auto;min-width:0;width:min\(20rem,100%\);box-sizing:border-box\}',
        )
