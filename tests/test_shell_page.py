"""Search and jump runs its real script over a disposable DOM stand-in.

shell_page_check.js drives deck_web/shell.js: a studio's own work found by name and opened
with Return, the focus given back to the opener when the palette is put away (and not when
a command takes the person on), a pointer that marks a row without scrolling the list, and a
count of the results past the first forty. Each studio's own list is checked in its suite.
It checks the parts of a project (StudioShell.parts) too: groups under visible headings, each
part's name then its state, the part shown marked and entered by Tab, the arrow keys, Home
and End, a choice keeping the focus, and the one control a narrower window shows.
It also checks that two of deck_web/deck-panels.js's pickers of looks never share an id.
"""
import shutil
import subprocess
import unittest
from pathlib import Path

HERE = Path(__file__).parent


@unittest.skipUnless(shutil.which('node'), 'Node.js is required for the shell kit.')
class ShellPageTests(unittest.TestCase):
    def test_find_open_put_away_hover_and_count(self):
        done = subprocess.run(['node', str(HERE / 'shell_page_check.js')],
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(done.returncode, 0, done.stderr or done.stdout)


if __name__ == '__main__':
    unittest.main()
