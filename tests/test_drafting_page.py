"""The shared desk kit, ui-kit/drafting.js, run in Node against a stand-in page.

Each test runs one group of tests/drafting_page_check.js with an adapter that is not Blog
Studio's, so the kit proves it draws the desk from what a studio passes in.
"""
import shutil
import subprocess
import unittest
from pathlib import Path

CHECK = Path(__file__).with_name('drafting_page_check.js')


@unittest.skipUnless(shutil.which('node'), 'The page kit check needs Node.js.')
class DraftingPageTests(unittest.TestCase):
    def group(self, name):
        done = subprocess.run(['node', str(CHECK), name], check=False, capture_output=True, text=True,
                              timeout=120)
        self.assertEqual(done.returncode, 0, done.stderr or done.stdout)

    def test_diff_on_the_page_kit(self):
        self.group('diff')

    def test_lazy_on_the_page_kit(self):
        self.group('lazy')

    def test_autosave_on_the_page_kit(self):
        self.group('autosave')

    def test_history_on_the_page_kit(self):
        self.group('history')

    def test_selection_on_the_page_kit(self):
        self.group('selection')

    def test_cards_on_the_page_kit(self):
        self.group('cards')

    def test_job_on_the_page_kit(self):
        self.group('job')

    def test_progress_on_the_page_kit(self):
        self.group('progress')

    def test_tools_on_the_page_kit(self):
        self.group('tools')

    def test_proposals_on_the_page_kit(self):
        self.group('proposals')

    def test_feedback_on_the_page_kit(self):
        self.group('feedback')

    def test_layout_on_the_page_kit(self):
        self.group('layout')


if __name__ == '__main__':
    unittest.main()
