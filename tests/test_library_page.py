"""The Document Library sheet exercises its real script with a disposable DOM stand-in."""
import shutil
import subprocess
import unittest
from pathlib import Path


@unittest.skipUnless(shutil.which('node'), 'Node.js is required for the UI component.')
class LibraryPageTests(unittest.TestCase):
    def test_browse_pick_page_filter_cancel_and_use(self):
        done = subprocess.run(['node', str(Path(__file__).with_name('library_page_check.js'))],
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(done.returncode, 0, done.stderr or done.stdout)
