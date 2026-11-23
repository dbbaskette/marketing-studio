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


class OneDiscoveryTests(unittest.TestCase):
    """Every studio looks for a brand skill in the same places (#505)."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name).resolve()
        self.addCleanup(mock.patch.stopall)
        self.config = self.home / 'studios-config.json'
        mock.patch.dict('os.environ', {'BRAND_SKILL_RUNTIME': '', 'HARNESS_BRAND_DATA': '',
                                       'STUDIOS_CONFIG': str(self.config)}).start()

    def skill(self, place):
        folder = self.home / place
        name = folder.parent.name if folder.name == 'current' else folder.name
        (folder / 'scripts').mkdir(parents=True)
        (folder / 'SKILL.md').write_text('Synthetic brand')
        (folder / 'package.json').write_text(json.dumps({'name': name}))
        (folder / 'scripts' / f'{name}.mjs').write_text('// brands')
        return folder

    def everywhere(self):
        return [self.skill(place) for place in (
            'Library/Application Support/mac-brand/current', '.local/share/linux-brand/current',
            '.claude/skills/claude-brand', '.agents/skills/agents-brand',
            '.codex/skills/codex-brand', '.cursor/skills/cursor-brand')]

    def test_every_place_in_one_order_and_an_override_is_the_only_place(self):
        from studio_core import brand_skills
        every = self.everywhere()
        self.assertEqual(brand_skills.installed(self.home), every)
        self.assertEqual(brand_skills.locations(home=self.home), every)
        with mock.patch.dict('os.environ', {'BRAND_SKILL_RUNTIME': str(every[4])}):
            self.assertEqual(brand_skills.locations(home=self.home), [every[4]])
            # A chosen folder (the `brand.skill` shared setting) comes before the variable.
            self.assertEqual(brand_skills.locations(every[5], home=self.home), [every[5]])

    def test_marketing_studio_brands_uses_the_same_list(self):
        # The studios' shared runner is checked in Training Studio's test_runner_brand.
        from marketing_studio import brand_skill
        every = self.everywhere()
        self.assertEqual(brand_skill.locations(self.home), every)

    def test_find_installed_brands_reads_every_place_and_the_brands_repository(self):
        every = self.everywhere()
        brands = self.home / 'brands'
        brands.mkdir()
        self.config.write_text(json.dumps({'schema': 1, 'brand': {'brands': str(brands)}}))
        told = []

        def listed(command, **kwargs):
            told.append(kwargs['env'].get('HARNESS_BRAND_DATA'))
            return subprocess.CompletedProcess(command, 0, json.dumps([
                {'brand': 'example', 'name': 'Example', 'variants': ['light']}]), '')

        result = brand_catalog.choices(home=self.home, run=listed, which=lambda _: '/synthetic/node')
        self.assertIsNone(result['problem'])
        self.assertEqual([skill['path'] for skill in result['skills']], [str(one) for one in every])
        self.assertEqual(told, [str(brands)] * len(every))

    def test_a_brands_repository_not_fetched_yet_leaves_the_environment_alone(self):
        from studio_core import brand_skills
        self.config.write_text(json.dumps({'schema': 1, 'brand': {
            'brands': str(self.home / 'not-there')}}))
        self.assertEqual(brand_skills.environment({'HARNESS_BRAND_DATA': 'kept'}),
                         {'HARNESS_BRAND_DATA': 'kept'})
        self.config.write_text('not json')
        self.assertIsNone(brand_skills.brands_folder())

    def test_a_conflict_on_the_brands_repository_names_it_as_the_form_does(self):
        from studio_core import preferences
        self.assertEqual(preferences.label(('brand', 'brands')), 'Brands repository')
