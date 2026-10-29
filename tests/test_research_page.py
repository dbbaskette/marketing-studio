"""Shared research component exercises its real script with a disposable DOM adapter."""
import shutil
import subprocess
import unittest
from pathlib import Path

@unittest.skipUnless(shutil.which('node'), 'Node.js is required for the UI component.')
class ResearchPageTests(unittest.TestCase):
    def test_sources_and_progress(self):
        done = subprocess.run(['node', str(Path(__file__).with_name('research_page_check.js'))],
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(done.returncode, 0, done.stderr or done.stdout)
