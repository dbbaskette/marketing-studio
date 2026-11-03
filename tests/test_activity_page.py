"""The shared activity lines and Activity log run as the page runs them, in a disposable DOM."""
import shutil
import subprocess
import unittest
from pathlib import Path


@unittest.skipUnless(shutil.which('node'), 'Node.js is required for the UI component.')
class ActivityPageTests(unittest.TestCase):
    def test_live_lines_research_panel_and_activity_log(self):
        done = subprocess.run(['node', str(Path(__file__).with_name('activity_page_check.js'))],
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(done.returncode, 0, done.stderr or done.stdout)


if __name__ == '__main__':
    unittest.main()
