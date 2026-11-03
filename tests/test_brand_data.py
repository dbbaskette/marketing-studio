"""Where Harness Brand reads brand packs, from disposable settings and workspaces only."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import marketing_studio  # noqa: F401  makes the shared core available
from studio_core import brand_data

TEAM = 'https://example.com/team/hub.git'


class BrandsFolderTests(unittest.TestCase):
    def setUp(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.base = Path(holder.name).resolve()

    def test_with_a_team_repository_it_is_at_the_root_of_the_studio_s_checkout(self):
        shared = {'team': {'repository': TEAM}, 'local': {'root': str(self.base / 'local')}}
        clone = self.base / 'clones' / 'hub'
        self.assertEqual(brand_data.folder(shared, clone, 'https://example.com/team/hub'),
                         clone / 'brands')

    def test_with_a_team_repository_another_checkout_or_none_cannot_say(self):
        shared = {'team': {'repository': TEAM}}
        self.assertIsNone(brand_data.folder(shared))
        self.assertIsNone(brand_data.folder(shared, self.base / 'work', None))
        self.assertIsNone(brand_data.folder(shared, self.base / 'old',
                                            'https://example.com/team/old'))

    def test_with_local_storage_every_studio_shares_the_local_root_s_folder(self):
        shared = {'local': {'root': str(self.base / 'Studios')}}
        for repository, address in ((None, None), (self.base / 'Studios/blog-workspace', None)):
            self.assertEqual(brand_data.folder(shared, repository, address),
                             self.base / 'Studios' / 'brands')

    def test_with_nothing_set_local_storage_is_the_default_root(self):
        self.assertEqual(brand_data.folder({}), Path('~/Studios/brands').expanduser())
        self.assertEqual(brand_data.folder(None), Path('~/Studios/brands').expanduser())

    def test_without_a_workspace_the_first_team_checkout_holding_packs_is_used(self):
        shared = {'team': {'repository': TEAM}}
        first, second, other = (self.base / name for name in ('first', 'second', 'other'))
        for folder in (second / 'brands', other / 'brands'):
            folder.mkdir(parents=True)
        checkouts = [(other, 'https://example.com/team/other'), (first, TEAM), (second, TEAM)]
        self.assertEqual(brand_data.unplaced(shared, checkouts), second / 'brands')
        self.assertIsNone(brand_data.unplaced(shared, checkouts[:2]))
        self.assertIsNone(brand_data.unplaced(shared))

    def test_without_a_workspace_local_storage_needs_none(self):
        shared = {'local': {'root': str(self.base / 'Studios')}}
        self.assertEqual(brand_data.unplaced(shared, [(self.base / 'x', TEAM)]),
                         self.base / 'Studios' / 'brands')

    def test_the_shared_settings_are_read_from_the_studios_config(self):
        config = self.base / 'studios-config.json'
        with mock.patch.dict(os.environ, {'STUDIOS_CONFIG': str(config)}):
            config.write_text(json.dumps({'schema': 1, 'local': {'root': str(self.base)}}))
            self.assertEqual(brand_data.current(), self.base / 'brands')
            config.write_text('not JSON')
            self.assertIsNone(brand_data.current())
        self.assertEqual(config.read_text(), 'not JSON')   # nothing is written


class EnvironmentTests(unittest.TestCase):
    def test_the_folder_is_named_unless_the_person_named_one(self):
        self.assertEqual(brand_data.environment({'PATH': '/bin'}, Path('/packs'), {}),
                         {'PATH': '/bin', 'HARNESS_BRAND_DATA': '/packs'})
        given = {'HARNESS_BRAND_DATA': '/mine'}
        self.assertEqual(brand_data.environment({'PATH': '/bin'}, Path('/packs'), given),
                         {'PATH': '/bin', 'HARNESS_BRAND_DATA': '/mine'})
        self.assertEqual(brand_data.environment({'PATH': '/bin'}, None, {}), {'PATH': '/bin'})

    def test_the_environment_given_is_not_changed(self):
        env = {'PATH': '/bin'}
        brand_data.environment(env, Path('/packs'), {})
        self.assertEqual(env, {'PATH': '/bin'})


class MissingTests(unittest.TestCase):
    def test_each_line_says_what_is_wrong_and_links_the_format(self):
        with tempfile.TemporaryDirectory() as name:
            there = Path(name)
            lines = [brand_data.missing(None), brand_data.missing(there / 'brands'),
                     brand_data.missing(there)]
        self.assertIn('team repository', lines[0])
        self.assertIn(f'no brands folder at {there / "brands"}', lines[1])
        self.assertIn(f'{there} holds no brand pack', lines[2])
        for line in lines:
            self.assertTrue(line.endswith(brand_data.FORMAT))
            self.assertNotIn('\n', line)


if __name__ == '__main__':
    unittest.main()
