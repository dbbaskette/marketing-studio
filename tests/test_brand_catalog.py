"""Explicit installed-brand discovery uses disposable homes and stub commands."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import marketing_studio  # makes the shared core available
from studio_core import brand_catalog


class BrandCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.folder = self.home / '.agents/skills/synthetic-brand'
        (self.folder / 'scripts').mkdir(parents=True)
        (self.folder / 'SKILL.md').write_text('Synthetic brand')
        (self.folder / 'package.json').write_text('{"name":"synthetic-brand"}')
        (self.folder / 'scripts/synthetic-brand.mjs').write_text('// brands')
        self.addCleanup(mock.patch.stopall)
        mock.patch.dict('os.environ', {'BRAND_SKILL_RUNTIME': ''}).start()

    def run_brand(self, *args, **kwargs):
        self.assertEqual(args[0][2:], ['brands', '--json'])
        return subprocess.CompletedProcess(args[0], 0, json.dumps({'brands': [
            {'brand': 'example', 'name': 'Example', 'variants': ['light', 'dark']}]}), '')

    def test_installed_brand_and_variants_are_listed_once_without_writing(self):
        duplicate = self.home / '.claude/skills/synthetic-brand'
        duplicate.parent.mkdir(parents=True)
        duplicate.symlink_to(self.folder)
        result = brand_catalog.choices(home=self.home, run=self.run_brand, which=lambda _: '/synthetic/node')
        self.assertIsNone(result['problem'])
        self.assertEqual(len(result['skills']), 1)
        self.assertEqual(result['skills'][0]['brands'][0]['variants'], ['light', 'dark'])
        self.assertFalse((self.home / '.config').exists())

    def test_missing_node_or_malformed_brand_output_keeps_manual_setup_available(self):
        result = brand_catalog.choices(home=self.home, which=lambda _: None)
        self.assertIn('Node.js', result['problem'])
        def malformed(*args, **kwargs):
            return subprocess.CompletedProcess(args[0], 0, '{"brands":[{"brand":"example","variants":42}]}', '')
        result = brand_catalog.choices(home=self.home, which=lambda _: '/synthetic/node', run=malformed)
        self.assertEqual(result['skills'], [])
        self.assertIn('unreadable variants', result['problem'])

    def test_explicit_folder_does_not_inspect_other_installed_skills(self):
        with mock.patch.object(Path, 'home', return_value=self.home), mock.patch.object(
                brand_catalog.shutil, 'which', return_value=None):
            found = brand_catalog.choices(skill=str(self.home / 'missing'), home=self.home,
                run=self.run_brand, which=lambda _: '/synthetic/node')
        self.assertEqual(found['skills'], [])
