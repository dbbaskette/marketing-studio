"""Continue in another studio's links run their real scripts over stand-ins.

continue_link_check.js drives StudioShell.continueLink (deck_web/shell.js): the home page's
link with `continue=<id>@<revision>` when Marketing Studio opened the studio, null when it
runs alone, and only for a document named as the Document Library names one. It also reads
`continue=` as the home page (setup_web/app.js) does, which takes nothing else from it. The
chooser itself is checked in library_page_check.js; /api/open in test_library_handoff.py.
"""
import shutil
import subprocess
import unittest
from pathlib import Path

HERE = Path(__file__).parent


@unittest.skipUnless(shutil.which('node'), 'Node.js is required for the page scripts.')
class ContinueLinkTests(unittest.TestCase):
    def test_continue_link_and_the_home_pages_reading_of_it(self):
        done = subprocess.run(['node', str(HERE / 'continue_link_check.js')],
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(done.returncode, 0, done.stderr or done.stdout)


if __name__ == '__main__':
    unittest.main()
