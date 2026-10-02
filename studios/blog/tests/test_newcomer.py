"""Portable generated requests preserve route stops and author input."""
from pathlib import Path
import json
import shutil
import subprocess
import unittest

class NewcomerTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is required for browser-script checks')
    def test_actual_generator_routes_and_portability(self):
        script=Path(__file__).resolve().parents[1]/'scripts/ci/check-newcomer.cjs'
        result=subprocess.run(['node',str(script)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'],'passed')
