"""All studio adapters accept actual PDF bytes using an explicitly available local reader."""
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

@unittest.skipUnless(shutil.which('pdftotext'), 'Real PDF intake check needs installed pdftotext.')
class PdfSourceWorkflows(unittest.TestCase):
    def test_every_studio_captures_and_previews_a_real_pdf(self):
        for product in ('blog', 'presentation', 'training', 'infographic'):
            with self.subTest(studio=product):
                done = subprocess.run([sys.executable, str(Path(__file__).with_name('pdf_source_case.py')), product],
                    capture_output=True, text=True, timeout=40)
                self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
