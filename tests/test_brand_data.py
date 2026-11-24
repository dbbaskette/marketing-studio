"""The brands repository is fetched only when asked, and recorded for the brand skills."""
import json
import os
import subprocess
from pathlib import Path
from unittest import mock

from test_home import IsolatedHome
from marketing_studio import shared
from studio_core import brand_data, preferences

GIT = {'GIT_AUTHOR_NAME': 'Test', 'GIT_AUTHOR_EMAIL': 'test@example.com', 'GIT_COMMITTER_NAME': 'Test',
       'GIT_COMMITTER_EMAIL': 'test@example.com', 'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1'}


class BrandFolders(IsolatedHome):
    def setUp(self):
        super().setUp()
        config = mock.patch.dict(os.environ, {'XDG_CONFIG_HOME': str(self.root / 'config'), **GIT})
        config.start()
        self.addCleanup(config.stop)

    def brands_folder(self, where: Path, *ids) -> Path:
        for brand in ids:
            (where / brand / 'pack').mkdir(parents=True)
            (where / brand / 'pack' / 'brand.json').write_text('{}')
        where.mkdir(parents=True, exist_ok=True)
        (where / 'README.md').write_text('Brands')
        return where

    def git(self, *args, cwd):
        subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True)

    def remote(self, *ids) -> Path:
        """A disposable repository of brands, cloned as a Git address would be."""
        work = self.brands_folder(self.root / 'origin', *ids)
        self.git('init', '--quiet', '--initial-branch=main', cwd=work)
        self.git('add', '.', cwd=work)
        self.git('commit', '--quiet', '-m', 'Brands', cwd=work)
        return work

    def recorded(self) -> str:
        return (self.root / 'config' / 'harness-brand' / 'data').read_text()


class BrandDataTests(BrandFolders):
    def test_a_brand_with_only_a_rebranding_profile_is_a_brand(self):
        # Harness Brand 1.1 keeps a brand's rebranding profile in `rebrand/`, beside `pack/`.
        folder = self.brands_folder(self.root / 'mixed', 'authored')
        for brand, kind in (('restyled', 'rebrand'), ('older', 'apply-brand')):
            (folder / brand / kind).mkdir(parents=True)
            (folder / brand / kind / 'brand.json').write_text('{}')
        (folder / 'icon-libraries').mkdir()
        self.assertEqual(brand_data.brands(folder), ['authored', 'older', 'restyled'])

    def test_with_no_repository_set_the_brands_are_the_ones_harness_brand_reads(self):
        with mock.patch.dict(os.environ, {'HARNESS_BRAND_DATA': ''}):
            # Harness Brand has no folder: said, and nothing is recorded.
            with mock.patch.object(brand_data.Path, 'home', return_value=self.root / 'nobody'):
                self.assertIsNone(brand_data.harness_folder())
                with self.assertRaisesRegex(Exception, 'Harness Brand has no brands folder yet'):
                    brand_data.bring('')
            folder = self.brands_folder(self.root / 'theirs', 'acme', 'other')
            brand_data.record(folder)
            self.assertEqual(brand_data.harness_folder(), folder)
            self.assertEqual(brand_data.chosen(None), folder)
            self.assertEqual(brand_data.bring(None), {
                'folder': str(folder), 'brands': ['acme', 'other'], 'action': 'used',
                'following': True})
            self.assertEqual(self.recorded(), f'{folder}\n', 'the record is left as it was')
        # What a command's environment names comes first, as it does for Harness Brand.
        with mock.patch.dict(os.environ, {'HARNESS_BRAND_DATA': str(self.root / 'named')}):
            self.assertEqual(brand_data.harness_folder(), self.root / 'named')

    def test_get_brands_says_which_folder_harness_brand_read_before(self):
        with mock.patch.dict(os.environ, {'HARNESS_BRAND_DATA': ''}):
            first = self.brands_folder(self.root / 'first', 'acme')
            second = self.brands_folder(self.root / 'second', 'acme')
            self.assertNotIn('replaced', brand_data.bring(str(first)))
            self.assertNotIn('replaced', brand_data.bring(str(first)))
            self.assertEqual(brand_data.bring(str(second))['replaced'], str(first))
            self.assertEqual(self.recorded(), f'{second}\n')

    def test_saving_the_setting_fetches_nothing(self):
        with mock.patch('subprocess.run') as run, mock.patch('subprocess.Popen') as start:
            self.write('/api/shared', {'changes': {'brand': {'brands': 'https://example.com/org/brands.git'}}, 'seen': {}})
            run.assert_not_called()
            start.assert_not_called()
        self.assertEqual(shared.read()[0]['brand']['brands'], 'https://example.com/org/brands.git')
        self.assertFalse((self.root / 'data' / 'brands').exists())
        self.assertFalse((self.root / 'config').exists())

    def test_the_setting_refuses_an_address_with_a_secret(self):
        with self.assertRaises(ValueError):
            preferences.check({'brand': {'brands': 'https://user:token@example.com/org/brands.git'}}, {})

    def test_a_folder_is_used_as_it_is_and_recorded(self):
        folder = self.brands_folder(self.root / 'brands', 'tanzu', 'vmware')
        self.write('/api/shared', {'changes': {'brand': {'brands': str(folder)}}, 'seen': {}})
        got = self.write('/api/brands-repository', {})
        self.assertEqual((got['action'], got['brands'], got['folder']), ('used', ['tanzu', 'vmware'], str(folder)))
        self.assertEqual(self.recorded(), f'{folder}\n')
        self.assertFalse((folder / '.git').exists())

    def test_a_repository_is_cloned_then_brought_up_to_date_by_fast_forward(self):
        origin = self.remote('broadcom')
        address = str(origin)
        with mock.patch.object(brand_data, '_local', return_value=False):
            got = brand_data.bring(address)
            self.assertEqual((got['action'], got['brands']), ('cloned', ['broadcom']))
            copy = Path(got['folder'])
            self.assertTrue(copy.is_relative_to(self.root / 'data' / 'brands'))
            self.assertEqual(self.recorded(), f'{copy}\n')
            self.brands_folder(origin, 'truesource')
            self.git('add', '.', cwd=origin)
            self.git('commit', '--quiet', '-m', 'TrueSource', cwd=origin)
            again = brand_data.bring(address)
            self.assertEqual((again['action'], again['brands'], again['folder']), ('updated', ['broadcom', 'truesource'], str(copy)))

    def test_a_repository_without_brands_is_refused_and_not_kept(self):
        origin = self.remote()
        with mock.patch.object(brand_data, '_local', return_value=False):
            with self.assertRaisesRegex(ValueError, 'holds no brands'):
                brand_data.bring(str(origin))
        self.assertEqual(list((self.root / 'data' / 'brands').iterdir()), [])
        self.assertFalse((self.root / 'config' / 'harness-brand' / 'data').exists())

    def test_getting_brands_needs_a_saved_setting(self):
        with self.assertRaisesRegex(Exception, 'brands repository'):
            self.page.write('/api/brands-repository', {})

    def test_the_settings_form_offers_the_field_and_the_button(self):
        page = (Path(__file__).parents[1] / 'core' / 'studio_core' / 'setup_web' / 'index.html').read_text()
        self.assertIn('name="brand.brands"', page)
        self.assertIn('id="get-brands"', page)
        self.assertIn("'skill', 'brands']", (Path(__file__).parents[1] / 'core' / 'studio_core' / 'setup_web' / 'app.js').read_text())
        self.assertNotIn('brands', json.dumps(shared.read()[0]))


class OnePassBrandCardTests(BrandFolders):
    """Shared settings' Brand card: Save makes Harness Brand read a brands folder on this
    computer; a Git address is only saved, and the card says its brands are not fetched yet."""

    def setUp(self):
        super().setUp()
        named = mock.patch.dict(os.environ, {'HARNESS_BRAND_DATA': ''})
        named.start()
        self.addCleanup(named.stop)
        nobody = mock.patch.object(brand_data.Path, 'home', return_value=self.root / 'nobody')
        nobody.start()
        self.addCleanup(nobody.stop)

    def test_saving_a_folder_with_brands_records_it_as_part_of_save(self):
        folder = self.brands_folder(self.root / 'brands', 'acme', 'other')
        with mock.patch('subprocess.run') as run:
            saved = self.write('/api/shared', {'changes': {'brand': {'brands': str(folder)}}, 'seen': {}})
            run.assert_not_called()
        self.assertEqual(saved['brands_saved'], {'folder': str(folder), 'brands': ['acme', 'other'], 'action': 'used'})
        self.assertEqual(self.recorded(), f'{folder}\n')
        self.assertEqual(brand_data.status(str(folder)), {
            'state': 'local', 'folder': str(folder), 'exists': True, 'brands': ['acme', 'other'], 'read': True})
        # Saving another value records nothing more.
        again = self.write('/api/shared', {'changes': {'person': {'name': 'Ana'}}, 'seen': shared.read()[0]})
        self.assertNotIn('brands_saved', again)

    def test_a_folder_without_brands_is_saved_and_not_recorded(self):
        empty = self.root / 'new-brands'
        saved = self.write('/api/shared', {'changes': {'brand': {'brands': str(empty)}}, 'seen': {}})
        self.assertNotIn('brands_saved', saved)
        self.assertEqual(shared.read()[0]['brand']['brands'], str(empty))
        self.assertFalse((self.root / 'config' / 'harness-brand' / 'data').exists())
        self.assertEqual(brand_data.status(str(empty)), {
            'state': 'local', 'folder': str(empty), 'exists': False, 'brands': [], 'read': False})

    def test_a_repository_address_is_saved_unfetched_and_the_lookup_says_so(self):
        from studio_core import brand_catalog
        address = 'https://example.com/org/brands.git'
        with mock.patch('subprocess.run') as run, mock.patch('subprocess.Popen') as start:
            saved = self.write('/api/shared', {'changes': {'brand': {'brands': address}}, 'seen': {}})
            run.assert_not_called()
            start.assert_not_called()
        self.assertNotIn('brands_saved', saved)
        with mock.patch.object(brand_catalog, 'choices', return_value={'skills': [], 'problem': None}):
            looked = self.write('/api/brands', {})
        self.assertEqual(looked['store']['state'], 'remote')
        self.assertEqual((looked['store']['address'], looked['store']['fetched'], looked['store']['brands']),
                         (address, False, []))
        self.assertFalse((self.root / 'data' / 'brands').exists())

    def test_status_follows_harness_brand_with_nothing_set(self):
        self.assertEqual(brand_data.status(None)['state'], 'none')
        folder = self.brands_folder(self.root / 'theirs', 'acme')
        brand_data.record(folder)
        self.assertEqual(brand_data.status(''), {'state': 'following', 'folder': str(folder), 'exists': True,
                                                 'brands': ['acme'], 'read': True})

    def test_a_folder_that_cannot_be_recorded_still_saves_and_says_why(self):
        folder = self.brands_folder(self.root / 'brands', 'acme')
        refused = PermissionError(13, 'Permission denied', str(self.root / 'config' / 'harness-brand'))
        with mock.patch.object(brand_data, 'record', side_effect=refused):
            saved = self.write('/api/shared', {'changes': {'brand': {'brands': str(folder)}}, 'seen': {}})
        self.assertIn('Permission denied', saved['brands_saved']['problem'])
        self.assertEqual(shared.read()[0]['brand']['brands'], str(folder))

    def onboarding_request(self, path, sent):
        from email.message import Message
        from studio_core import onboarding
        page = onboarding.Controller(8000, 'a' * 40, 'Training Studio', 'X-Test-Token', lambda _: None, shared)
        headers = Message()
        for key, value in {'Host': '127.0.0.1:8000', 'Origin': 'http://127.0.0.1:8000',
                           'Content-Type': 'application/json', 'X-Test-Token': 'a' * 40}.items():
            headers[key] = value
        reply = page.answer('/onboarding/api/' + path, headers, 'POST', json.dumps(sent).encode())
        return reply[0], json.loads(reply[2])

    def test_a_studios_own_setup_page_also_records_a_folder_as_part_of_save(self):
        folder = self.brands_folder(self.root / 'brands', 'acme')
        status, saved = self.onboarding_request('shared', {'changes': {'brand': {'brands': str(folder)}}, 'seen': {}})
        self.assertEqual(status, 200)
        self.assertEqual(saved['brands_saved'], {'folder': str(folder), 'brands': ['acme'], 'action': 'used'})
        self.assertEqual(self.recorded(), f'{folder}\n')
        self.assertEqual(saved['shared']['brand']['brands'], str(folder))
        # And its lookup says what the folder holds, while a failing skill lookup leaves it standing.
        from studio_core import brand_catalog
        with mock.patch.object(brand_catalog, 'choices', side_effect=OSError('no skills folder')):
            status, looked = self.onboarding_request('brands', {})
        self.assertEqual((status, looked['skills'], looked['store']['state'], looked['store']['brands']),
                         (200, [], 'local', ['acme']))
        self.assertIn('no skills folder', looked['problem'])

    def test_a_caller_through_the_network_bridge_is_told_no_paths(self):
        from studio_core import brand_catalog
        folder = self.brands_folder(self.root / 'brands', 'acme', 'other')
        self.write('/api/shared', {'changes': {'brand': {'brands': str(folder)}}, 'seen': {}})
        with mock.patch.object(brand_catalog, 'choices', return_value={'skills': [], 'problem': None}):
            self.page.caller.remote = True
            try:
                looked = self.write('/api/brands', {})
            finally:
                self.page.caller.remote = False
            here = self.write('/api/brands', {})
        self.assertEqual(looked['store'], {'state': 'local', 'exists': True, 'read': True, 'count': 2})
        self.assertNotIn(str(self.root), json.dumps(looked))
        self.assertEqual(here['store']['folder'], str(folder))

    def test_a_folder_that_cannot_be_looked_at_is_said_and_the_lookup_answers(self):
        with mock.patch.object(brand_data, 'status', side_effect=OSError('the disk went away')):
            store = brand_data.lookup('/somewhere')
        self.assertEqual(store, {'state': 'unknown', 'said': 'The brands folder could not be looked at: the disk went away'})

    def test_a_fetched_repository_is_said_with_its_brands(self):
        origin = self.remote('acme')
        with mock.patch.object(brand_data, '_local', return_value=False):
            brand_data.bring(str(origin))
            found = brand_data.status(str(origin))
        self.assertEqual((found['state'], found['fetched'], found['brands'], found['read']),
                         ('remote', True, ['acme'], True))
