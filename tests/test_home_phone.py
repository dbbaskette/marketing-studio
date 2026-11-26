"""A phone on Marketing Studio's private link, on Marketing Studio's own page (GitHub issue
#539): it cannot set or ask about a folder on this computer, and is not shown installed brand
folder paths; it can still give a brand repository web address. A caller on the computer
keeps today's behaviour.

Every route the page answers is walked with the network bridge's header, and each has its
decision in marketing_studio.page.PHONE, so a route added without one fails here. Disposable
settings, stand-in launches and lookups only."""
import json
import os
from email.message import Message
from pathlib import Path
from unittest import mock

from test_brand_data import BrandFolders
from marketing_studio import catalog, computer, page as home_page, shared, state
from marketing_studio.errors import WorkspaceError
from marketing_studio.page import BRAND_ROUTES, REMOTE_BRANDS
from studio_core import brand_catalog, brand_data, graphics
from studio_core.document_library import context as library_context

SKILLS = {'skills': [{'name': 'synthetic-brand', 'path': '/opt/synthetic-brand-skill',
                      'brands': [{'brand': 'example', 'name': 'Example Co', 'variants': ['light']}]}],
          'problem': None}
LIBRARY = (*library_context.ROUTES, '/api/library-upload', '/api/library-download',
           '/api/library-existing', '/api/library-adopt', '/api/library-hide')


class HomePhoneTests(BrandFolders):
    def setUp(self):
        super().setUp()
        for patch in (mock.patch.dict(os.environ, {'HARNESS_BRAND_DATA': '',
                                                   'STUDIOS_LIBRARY': str(self.root / 'library')}),
                      mock.patch.object(brand_data.Path, 'home', return_value=self.root / 'nobody'),
                      # No look at this computer's own tools or Git identity.
                      mock.patch.object(computer, 'check', return_value={'ready': True, 'items': []})):
            patch.start()
            self.addCleanup(patch.stop)

    def ask(self, path, sent=None, network=True):
        headers = Message()
        for key, value in {'Host': '127.0.0.1:8000', 'Origin': 'http://127.0.0.1:8000',
                           'Content-Type': 'application/json', 'X-Marketing-Studio-Token': self.page.token,
                           # The header the network bridge adds (marketing_studio.network.VIA_HEADER).
                           **({'X-Marketing-Studio-Via': 'network'} if network else {})}.items():
            headers[key] = value
        try:
            reply = self.page.answer(path, headers, 'GET' if sent is None else 'POST',
                                     None if sent is None else json.dumps(sent).encode())
        except WorkspaceError as refused:   # the HTTP server answers these 409
            return 409, {'error': str(refused)}
        return reply[0], json.loads(reply[2])

    def save(self, changes, network=True):
        return self.ask('/api/shared', {'changes': changes, 'seen': shared.read()[0]}, network)

    def test_every_route_has_a_phone_decision(self):
        routes = {*self.page.reads, *self.page.writes}
        self.assertEqual(routes, set(home_page.PHONE))
        self.assertTrue(all(isinstance(why, str) and why for why in home_page.PHONE.values()))

    def test_each_route_from_a_phone(self):
        folder = self.brands_folder(self.root / 'brands', 'acme', 'other')
        asked = set()

        def route(path):
            asked.add(path)
            return path

        # Reads and lookups that take no folder.
        self.assertEqual(self.ask(route('/api/home'))[0], 200)
        self.assertEqual(self.ask(route('/api/computer'))[0], 200)
        self.assertEqual(self.ask('/api/computer', {})[0], 200)
        with mock.patch.object(self.page.models, 'get', return_value={'models': []}):
            self.assertEqual(self.ask(route('/api/models') + '?agent=claude')[0], 200)
            self.assertEqual(self.ask('/api/models', {'agent': 'claude'})[0], 200)
        status, answer = self.ask(route('/api/research-site'), {'site': 'https://example.com/docs'})
        self.assertEqual(status, 200)

        # Shared settings: other settings and a web address save; a folder does not.
        self.assertEqual(self.save({'person': {'name': 'Ana'}})[0], 200)
        address = 'https://example.com/org/brands.git'
        self.assertEqual(self.save({'brand': {'brands': address}})[0], 200)
        self.assertEqual(shared.read()[0]['brand']['brands'], address)
        for changes, named in (({'local': {'root': str(self.root / 'work')}}, '“Workspace folder”'),
                               ({'brand': {'skill': str(self.root / 'skill')}}, '“Installed skill folder”'),
                               ({'brand': {'brands': str(folder)}}, '“Brands repository”'),
                               ({'brand': {'repository': str(self.root / 'skill-repo')}}, '“Brand Git repository”'),
                               ({'team': {'repository': str(self.root / 'team-repo')}}, '“Repository address”')):
            with self.subTest(changes=changes):
                status, answer = self.save({**changes, 'person': {'name': 'Bo'}})
                self.assertEqual(status, 409)
                self.assertIn(named, answer['error'])
                self.assertIn('only on that computer', answer['error'])
                self.assertEqual(shared.read()[0]['person']['name'], 'Ana', 'nothing of the save is kept')
        route('/api/shared')
        # A folder this computer saved, sent as the form was shown, lets the rest save.
        self.assertEqual(self.save({'local': {'root': str(self.root / 'work')}}, network=False)[0], 200)
        held = shared.read()[0]
        status, _ = self.ask('/api/shared', {'changes': {'local': {'root': str(self.root / 'work')},
                                                          'person': {'name': 'Cy'}}, 'seen': held})
        self.assertEqual((status, shared.read()[0]['person']['name']), (200, 'Cy'))
        status, answer = self.save({'local': {'root': None}})
        self.assertEqual(status, 409)
        self.assertIn('“Workspace folder”', answer['error'])
        # An outdated form is refused as before, naming what someone else changed meanwhile.
        status, answer = self.ask('/api/shared', {'changes': {'person': {'name': 'Di'}},
                                                  'seen': {**shared.read()[0], 'person': {'name': 'Old'}}})
        self.assertEqual(status, 409)
        self.assertIn('“Your name” was changed in another tab', answer['error'])

        # Setup, opening and connecting a studio take no folder from the caller.
        self.assertEqual(self.ask(route('/api/setup'), {'done': True})[0], 200)
        with mock.patch.object(self.launcher, 'open', return_value='http://127.0.0.1:9/#token=x') as opened:
            self.assertEqual(self.ask(route('/api/open'), {'studio': 'blog'})[0], 200)
        self.assertTrue(opened.call_args.kwargs['remote'])
        with mock.patch.object(self.launcher, 'connect', return_value={'connected': True}):
            self.assertEqual(self.ask(route('/api/connect'), {'studio': 'blog'})[0], 200)

        # Installation folders: a phone sets none, and looks none up; those saved pass again.
        install = self.root / 'blog-install'
        with mock.patch.object(catalog, 'locate', return_value=install) as located:
            self.assertEqual(self.ask('/api/paths', {'paths': {'blog': str(install)}}, network=False)[0], 200)
            located.reset_mock()
            for paths in ({'blog': str(self.root / 'elsewhere')}, {'blog': ''},
                          {'blog': str(install), 'training': str(self.root / 'training-install')}):
                with self.subTest(paths=paths):
                    self.assertEqual(self.ask(route('/api/paths'), {'paths': paths}), (409, {'error': getattr(home_page, 'REMOTE_PATHS', 'refused')}))
            located.assert_not_called()
            self.assertEqual(self.ask('/api/paths', {'paths': {'blog': str(install), 'training': ''}})[0], 200)
        self.assertEqual(state.read()['paths'], {'blog': str(install), 'training': ''})

        # Document graphics: models listed, a key never taken over the link.
        status, answer = self.ask(route('/api/graphics'), {'key': 'synthetic-not-a-key'})
        self.assertEqual(status, 409)
        self.assertIn('not taken over the phone link', answer['error'])
        with mock.patch.object(graphics, 'listed', return_value={'provider': 'gemini', 'models': []}):
            self.assertEqual(self.ask('/api/graphics', {'models': 'gemini'})[0], 200)

        # Installed brands by name; a skill folder refused unread.
        with mock.patch.object(brand_catalog, 'choices', return_value=SKILLS) as choices:
            status, answer = self.ask(route('/api/brands'), {})
            self.assertEqual(answer['skills'], [{'name': 'synthetic-brand', 'brands': SKILLS['skills'][0]['brands']}])
            self.assertEqual(self.ask('/api/brands', {'skill': '/opt/x'})[1]['problem'], brand_catalog.REMOTE_SKILL)
            self.assertEqual(choices.call_count, 1)

        # Get brands: what was got, without the folder; a refusal names no folder.
        self.assertEqual(self.save({'brand': {'brands': str(folder)}}, network=False)[0], 200)
        status, answer = self.ask(route('/api/brands-repository'), {})
        self.assertEqual((status, answer['brands'], answer['action']), (200, ['acme', 'other'], 'used'))
        self.assertNotIn(str(self.root), json.dumps(answer))
        here = self.ask('/api/brands-repository', {}, network=False)[1]
        self.assertEqual(here['folder'], str(folder))
        gone = self.root / 'gone-brands'
        self.assertEqual(self.save({'brand': {'brands': str(gone)}}, network=False)[0], 200)
        self.assertEqual(self.ask('/api/brands-repository', {}), (409, {'error': brand_data.REMOTE_UNGOT}))
        self.assertIn(str(gone), self.ask('/api/brands-repository', {}, network=False)[1]['error'])

        # The Document Library: answered to a phone exactly as to this computer.
        for path in LIBRARY:
            with self.subTest(path=path):
                self.assertEqual(self.ask(route(path), {}), self.ask(path, {}, network=False))

        # Brands is used on the computer.
        for name in BRAND_ROUTES:
            self.assertEqual(self.ask(route(f'/api/brand-{name}'), {}), (409, {'error': REMOTE_BRANDS}))

        self.assertEqual(asked, {*self.page.reads, *self.page.writes}, 'every route was asked from a phone')

    def test_a_computer_still_changes_folder_settings_and_installation_folders(self):
        status, _ = self.save({'local': {'root': str(self.root / 'work')},
                               'brand': {'skill': str(self.root / 'skill')}}, network=False)
        self.assertEqual(status, 200)
        self.assertEqual(shared.read()[0]['brand']['skill'], str(self.root / 'skill'))
        with mock.patch.object(catalog, 'locate', return_value=Path(self.root / 'x')):
            self.assertEqual(self.ask('/api/paths', {'paths': {'blog': str(self.root / 'x')}}, network=False)[0], 200)
        status, answer = self.ask('/api/paths', {'paths': {'blog': str(self.root / 'no-launcher')}}, network=False)
        self.assertEqual((status, answer['error']), (409, 'That folder does not contain the studio launcher.'))


if __name__ == '__main__':
    import unittest
    unittest.main()
