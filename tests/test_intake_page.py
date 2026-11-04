import shutil
import subprocess
import unittest
from pathlib import Path


class IntakeBrowserContractTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is required')
    def test_private_intake_writes_are_ordered_and_incremental(self):
        script = Path(__file__).with_name('intake_page_check.js')
        result = subprocess.run(['node', str(script)], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
