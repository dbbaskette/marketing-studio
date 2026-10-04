"""Actual desk JavaScript with synthetic DOM/API responses; no browser or accounts."""
from pathlib import Path
import shutil
import subprocess
import unittest

class ManagementUITests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is required for desk-script checks')
    def test_management_client(self):
        repo = Path(__file__).resolve().parents[1]
        result = subprocess.run(['node', 'scripts/ci/check-management.cjs'], cwd=repo, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
