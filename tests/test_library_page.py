"""The Document Library sheet exercises its real script with a disposable DOM stand-in.

library_page_check.js drives deck_web/library.js: one action a row, the preview below its
row with the downloads and focus back to the row, the phone Filters toggle and its count
(in the Library and the Add from library sheet), and Remove from library with Restore.
The mixed-file upload, an oversize file and phone Filters at 390px in the real home are
looked at by hand over tests/library_visual_server.py (docs/testing.md).
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


if __name__ == '__main__':
    unittest.main()
