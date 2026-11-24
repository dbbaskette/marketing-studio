"""Infographic Studio's page script, run over a disposable stand-in page.

ui/page_check.js cuts the real functions from runner/web/app.js: Search and jump lists each
infographic Home shows (group Infographics, what its card says as the hint) and New
infographic, and runs each as its card or button does; and a story card's Use this story is
a quiet button named for its story, never a second filled one. No browser, server, provider
or studio state.
"""
import shutil
import subprocess
import unittest
from pathlib import Path

HERE = Path(__file__).parent


@unittest.skipUnless(shutil.which('node'), 'Node.js is required to run the page script.')
class PageScriptTests(unittest.TestCase):
    def test_search_and_jump_and_story_choices(self):
        done = subprocess.run(['node', str(HERE / 'ui' / 'page_check.js')],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr or done.stdout)


if __name__ == '__main__':
    unittest.main()
