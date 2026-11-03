"""The brand export tells the brand command where Harness Brand's packs are, and no more."""
import json
import os
from pathlib import Path
import subprocess
import unittest

from helpers import Isolated
from runner import brand

from test_composition import contract


class BrandExportTests(Isolated):
    def setUp(self):
        super().setUp()
        self.skill = self.home / '.claude/skills/synthetic-brand'
        (self.skill / 'scripts').mkdir(parents=True)
        (self.skill / 'SKILL.md').write_text('Synthetic brand')
        (self.skill / 'package.json').write_text('{"name":"synthetic-brand"}')
        (self.skill / 'scripts/synthetic-brand.mjs').write_text('// brands')
        self.told = []

    def brand_command(self, command, **kwargs):
        """A stand-in brand command that records the environment each call is given."""
        self.told.append((command[2], kwargs.get('env')))
        if command[2] == 'brands':
            return subprocess.CompletedProcess(command, 0, json.dumps([
                {'brand': 'example', 'name': 'Example Brand', 'variants': ['light']}]), '')
        output = Path(command[command.index('--output') + 1])
        output.mkdir()
        (output / 'brand-contract.json').write_text(json.dumps(contract()))
        return subprocess.CompletedProcess(command, 0, '{}', '')

    def export(self):
        return brand.export_selected(skill=self.skill, brand_id='example', run=self.brand_command,
                                     which=lambda _: '/synthetic/node')

    def test_with_local_storage_both_calls_are_told_the_local_brands_folder(self):
        self.settings.write_text(json.dumps({'schema': 1, 'local': {'root': str(self.temp / 'Studios')}}))
        self.assertEqual(self.export()['identity']['id'], 'example')
        packs = str(self.temp / 'Studios' / 'brands')
        self.assertEqual([(called, env.get('HARNESS_BRAND_DATA')) for called, env in self.told],
                         [('brands', packs), ('contract', packs)])
        # The export's environment stays the minimal one, with just that variable added.
        exported = self.told[1][1]
        self.assertLessEqual(set(exported), {'PATH', 'HOME', 'TMPDIR', 'LANG', 'LC_ALL', 'CODEX_HOME',
                                             'CLAUDE_CONFIG_DIR', 'SYSTEMROOT', 'WINDIR',
                                             'HARNESS_BRAND_DATA'})
        self.assertNotIn('STUDIOS_CONFIG', exported)

    def test_a_folder_the_person_named_already_is_kept(self):
        os.environ['HARNESS_BRAND_DATA'] = str(self.temp / 'their-own')
        self.export()
        self.assertEqual({env.get('HARNESS_BRAND_DATA') for _, env in self.told},
                         {str(self.temp / 'their-own')})

    def test_with_a_team_repository_no_folder_can_be_named(self):
        self.settings.write_text(json.dumps({'schema': 1, 'team': {'repository': 'https://example.com/hub'}}))
        self.export()
        self.assertEqual([env.get('HARNESS_BRAND_DATA') for _, env in self.told], [None, None])


if __name__ == '__main__':
    unittest.main()
