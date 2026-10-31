"""The Document Library sheet exercises its real script with a disposable DOM stand-in.

library_page_check.js drives deck_web/library.js: one action a row, the preview below its
row with the downloads and focus back to the row, the phone Filters toggle and its count
(in the Library and the Add from library sheet), and Remove from library with Restore.
The cases that need a real browser and the real home live in library_visual.cjs: the
mixed-file upload (alpha.md, beta.png, gamma.txt) and an oversize file reported per file
and retried without duplicates, a removed file shown again by uploading it, and phone
Filters at 390px. That check needs Playwright and a headless renderer (docs/testing.md).
"""
import shutil
import subprocess
import unittest
from pathlib import Path

HERE = Path(__file__).parent


@unittest.skipUnless(shutil.which('node'), 'Node.js is required for the UI component.')
class LibraryPageTests(unittest.TestCase):
    def test_browse_pick_page_filter_cancel_and_use(self):
        done = subprocess.run(['node', str(HERE / 'library_page_check.js')],
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(done.returncode, 0, done.stderr or done.stdout)


class LibraryBrowserCaseTests(unittest.TestCase):
    """The browser check keeps the cases issue #246 asked for."""

    def test_the_browser_check_covers_mixed_uploads_and_phone_filters(self):
        check = (HERE / 'library_visual.cjs').read_text(encoding='utf-8')
        for case in ("name:'alpha.md'", "name:'beta.png'", "name:'gamma.txt'", "'only the refused file stays chosen'",
                     "'2 added, 1 not added.'", "'larger than 8 MB'", "'Shown again as “alpha”'",
                     "phoneFilters('#library'", "phoneFilters('dialog.library-sheet'",
                     "for(const key of ['kind','studio','origin','state','author'])"):
            with self.subTest(case=case):
                self.assertIn(case, check)


if __name__ == '__main__':
    unittest.main()
