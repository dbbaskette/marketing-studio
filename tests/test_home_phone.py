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


def folders_shown(value, at=''):
    """Where in an answer a folder on this computer is written: each key path (a list's
    items as []) whose text names one."""
    if isinstance(value, dict):
        return set().union(*(folders_shown(part, f'{at}.{key}' if at else key) for key, part in value.items()))
    if isinstance(value, list):
        return set().union(*(folders_shown(part, at + '[]') for part in value))
    return {at} if isinstance(value, str) and brand_data.names_a_folder(value) else set()


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
        except WorkspaceError as refused:   # the HTTP server answers these 409, with their details
            details = getattr(refused, 'details', None)
            return 409, {**(details if isinstance(details, dict) else {}), 'error': str(refused)}
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
        # Nothing new is written from a phone, not even an empty entry (second review, item 7).
        self.assertEqual(state.read()['paths'], {'blog': str(install)})

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

    def test_a_folder_is_unchanged_only_when_it_is_exactly_what_is_saved(self):
        work = str(self.root / 'work')
        self.assertEqual(self.save({'local': {'root': work}}, network=False)[0], 200)
        self.assertEqual(self.ask('/api/setup', {'done': True}, network=False)[0], 200)
        with mock.patch.object(self.launcher, 'prepare') as prepare:
            for sent, seen in [(sent, seen) for sent in (work + ' ', work + '/', work + '/.')
                           for seen in (shared.read()[0], {'local': {'root': sent}})]:
                with self.subTest(sent=sent, seen=seen):
                    status, answer = self.ask('/api/shared', {
                        'changes': {'local': {'root': sent}, 'person': {'name': 'Ana'}},
                        'seen': seen})
                    self.assertEqual(status, 409)
                    # A forged `seen` is an outdated form, refused as such first (second review, item 4).
                    self.assertIn('names a folder' if 'schema' in seen else 'was changed in another tab', answer['error'])
                    self.assertEqual(shared.read()[0]['local']['root'], work)
            prepare.assert_not_called()
        # A saved folder that ends in a space, sent back exactly, is no change.
        with mock.patch.object(self.launcher, 'prepare', return_value={}):
            self.assertEqual(self.save({'local': {'root': work + ' '}}, network=False)[0], 200)
        self.assertEqual(self.save({'local': {'root': work + ' '}, 'person': {'name': 'Bo'}})[0], 200)
        self.assertEqual((shared.read()[0]['local']['root'], shared.read()[0]['person']['name']), (work + ' ', 'Bo'))

    def test_an_installation_folder_is_unchanged_only_when_it_is_exactly_what_is_saved(self):
        install = str(self.root / 'blog-install')
        with mock.patch.object(catalog, 'locate', return_value=Path(install)) as located:
            self.assertEqual(self.ask('/api/paths', {'paths': {'blog': install}}, network=False)[0], 200)
            located.reset_mock()
            for sent in (install + ' ', ' ' + install, install + '/'):
                with self.subTest(sent=sent):
                    self.assertEqual(self.ask('/api/paths', {'paths': {'blog': sent}}),
                                     (409, {'error': home_page.REMOTE_PATHS}))
            located.assert_not_called()
            self.assertEqual(state.read()['paths'], {'blog': install})
            # One saved with a space at its end, sent back exactly, is no change.
            self.assertEqual(self.ask('/api/paths', {'paths': {'blog': install + ' '}}, network=False)[0], 200)
            self.assertEqual(self.ask('/api/paths', {'paths': {'blog': install + ' ', 'training': ''}})[0], 200)
        self.assertEqual(state.read()['paths'], {'blog': install + ' '})   # no empty entry written

    def test_a_failure_that_names_a_folder_is_said_to_a_phone_without_it(self):
        # Review item 3: each lookup raising an OSError (or a refusal) that names a folder.
        folder = self.brands_folder(self.root / 'brands', 'acme')
        self.assertEqual(self.save({'brand': {'brands': str(folder)}}, network=False)[0], 200)
        secret = str(self.root / 'private-folder')
        denied = PermissionError(13, 'Permission denied', secret)
        cases = (
            ('/api/brands-repository', {}, mock.patch.object(brand_data, 'record', side_effect=denied)),
            ('/api/brands-repository', {}, mock.patch.object(brand_data, 'bring',
                                                             side_effect=ValueError(f'{secret} holds no brands'))),
            ('/api/brands', {}, mock.patch.object(brand_catalog, 'choices', side_effect=denied)),
            ('/api/brands', {}, mock.patch.object(brand_data, 'status', side_effect=denied)),
            ('/api/computer', {}, mock.patch.object(computer, 'check', side_effect=denied)),
            ('/api/connect', {'studio': 'blog'}, mock.patch.object(self.launcher, 'connect', side_effect=denied)),
            ('/api/open', {'studio': 'blog'}, mock.patch.object(self.launcher, 'open',
                                                                side_effect=WorkspaceError(f'Nothing at {secret}.'))),
            ('/api/library-upload', {'name': 'a.md', 'content': 'YQ=='},
             mock.patch('studio_core.document_library.opened', side_effect=denied)),
        )
        self.assertEqual(self.save({'local': {'root': str(self.root / 'work')}}, network=False)[0], 200)
        self.assertEqual(self.ask('/api/setup', {'done': True}, network=False)[0], 200)
        for path, sent, patch in cases:
            with self.subTest(path=path, patch=patch.attribute):
                with patch:
                    status, answer = self.ask(path, sent)
                self.assertNotIn(secret, json.dumps(answer))
                self.assertNotIn('Errno', json.dumps(answer))
        # The computer is told as before: the error itself, which its server describes.
        with mock.patch.object(brand_data, 'record', side_effect=denied):
            with self.assertRaises(PermissionError):
                self.ask('/api/brands-repository', {}, network=False)

    def test_a_phone_gives_only_a_web_address_of_another_computer(self):
        # Review item 4: one rule for a phone's repository address (studio_core.repository_address).
        for address in ('http://127.0.0.1:8000/x.git', 'https://localhost/a', 'ssh://localhost/Users/x/repo',
                        'me@localhost:/Users/x/repo', 'http://example.com/org/brands.git',
                        # Second review, item 1: an encoded host, a user that starts with a dash,
                        # and an IPv6 address carrying a loopback.
                        'ssh://git@%6c%6fcalhost/x', 'ssh://%31%32%37.0.0.1/srv/x.git',
                        'ssh://-oProxyCommand=x@example.com/r', 'ssh://-user@example.com/x',
                        'ssh://[0:0:0:0:0:0:7f00:1]/x'):   # ::127.0.0.1, written without ::
            for group, key in (('brand', 'brands'), ('brand', 'repository'), ('team', 'repository')):
                with self.subTest(address=address, setting=(group, key)):
                    status, answer = self.save({group: {key: address}})
                    self.assertEqual(status, 409)
                    self.assertIn('only an https or ssh address of another computer', answer['error'])
                    self.assertIsNone((shared.read()[0].get(group) or {}).get(key))
        for address in ('https://example.com/org/brands.git', 'git@example.com:org/brands.git',
                        'ssh://git@192.168.1.5/brands.git'):
            with self.subTest(address=address):
                self.assertEqual(self.save({'brand': {'brands': address}})[0], 200)
                self.assertEqual(shared.read()[0]['brand']['brands'], address)
        # A local address saved on the computer is sent back unchanged, or emptied only there.
        self.assertEqual(self.save({'brand': {'brands': 'me@localhost:/x/brands'}}, network=False)[0], 200)
        self.assertEqual(self.save({'brand': {'brands': 'me@localhost:/x/brands'}, 'person': {'name': 'Ana'}})[0], 200)
        self.assertEqual(self.save({'brand': {'brands': None}})[0], 409)
        # A web address may be emptied from a phone.
        self.assertEqual(self.save({'brand': {'brands': 'https://example.com/b.git'}})[0], 200)
        self.assertEqual(self.save({'brand': {'brands': None}})[0], 200)

    def test_what_each_route_still_shows_a_phone_of_saved_folders(self):
        # Review item 5: the saved folder values each route answers a phone with, route by
        # route, as page.PHONE_SHOWS records them. What is shown is the owner's separate
        # decision; this keeps the record true.
        folder = self.brands_folder(self.root / 'brands', 'acme')
        install = self.root / 'blog-install'
        tools = {'ready': True, 'items': [{'name': 'Git', 'ready': True, 'detail': '/usr/bin/git', 'optional': False}]}
        with mock.patch.object(self.launcher, 'prepare', return_value={}), \
                mock.patch.object(catalog, 'locate', return_value=install):
            self.assertEqual(self.save({'local': {'root': str(self.root / 'work')},
                                        'brand': {'skill': str(self.root / 'skill'), 'brands': str(folder),
                                                  'repository': str(self.root / 'skill-repo')},
                                        'team': {'repository': str(self.root / 'team-repo')}}, network=False)[0], 200)
            self.assertEqual(self.ask('/api/setup', {'done': True}, network=False)[0], 200)
            self.assertEqual(self.ask('/api/paths', {'paths': {'blog': str(install)}}, network=False)[0], 200)
        # A Blog Studio workspace the studio remembers, with a source to add to the library.
        from test_library_adopt import Workspace
        blogs = Workspace(self.root / 'writing')
        blogs.source('gateway-guide-1a2b3c4e', 'Gateway guide', '# Gateway guide\n\nRoutes.\n',
                     library={'origin_kind': 'upload'})
        data = Path(os.environ['BLOG_STUDIO_DATA'])
        data.mkdir(parents=True, exist_ok=True)
        (data / 'page.json').write_text(json.dumps({'workspace': str(blogs.root)}))
        with mock.patch.object(computer, 'check', return_value=tools):
            self.assertEqual(self.ask('/api/computer', {}, network=False)[0], 200)   # one look taken here
        signature = self.ask('/api/library-existing', {}, network=False)[1]['signature']
        asked = {
            '/api/home': None, '/api/computer': {}, '/api/models': {'agent': 'claude'},
            '/api/shared': {'changes': {'person': {'name': 'Ana'}}, 'seen': {}},
            '/api/setup': {'done': True}, '/api/open': {'studio': 'blog'}, '/api/connect': {'studio': 'blog'},
            '/api/paths': {'paths': {'blog': str(install)}}, '/api/graphics': {'models': 'gemini'},
            '/api/brands': {}, '/api/brands-repository': {}, '/api/research-site': {'site': 'https://example.com'},
            **{path: {} for path in LIBRARY},
            '/api/library-upload': {'name': 'note.md', 'content': 'IyBOb3RlCg=='},
            '/api/library-adopt': {'signature': signature},
            **{f'/api/brand-{name}': {} for name in BRAND_ROUTES}}
        self.assertEqual(set(asked), set(home_page.PHONE))
        shown = {}
        with mock.patch.object(computer, 'check', return_value=tools), \
                mock.patch.object(self.launcher, 'prepare', return_value={}), \
                mock.patch.object(self.launcher, 'open', return_value='http://192.168.1.9:1/#token=x'), \
                mock.patch.object(self.launcher, 'connect', return_value={'connected': True}), \
                mock.patch.object(catalog, 'locate', return_value=install), \
                mock.patch.object(self.page.models, 'get', return_value={'models': []}), \
                mock.patch.object(graphics, 'listed', return_value={'provider': 'gemini', 'models': []}), \
                mock.patch.object(brand_catalog, 'choices', return_value=SKILLS):
            # Walked twice: with a team repository, then with only a local work folder.
            for storage in ({}, {'team': {'repository': None}}):
                if storage:
                    self.assertEqual(self.save(storage, network=False)[0], 200)
                for path, sent in asked.items():
                    with self.subTest(path=path, storage=storage):
                        status, answer = self.ask(path, sent)
                        shown.setdefault(path, set()).update(folders_shown(answer))
        shown = {path: found for path, found in shown.items() if found}
        self.assertEqual(shown, {path: set(fields) for path, fields in home_page.PHONE_SHOWS.items()})
        # Each route's written decision says whether it shows saved folders, and only then.
        for path, why in home_page.PHONE.items():
            self.assertEqual(home_page.SAVED in why, path in home_page.PHONE_SHOWS, path)

    def test_a_phone_looks_up_the_saved_skill_folder_by_name_and_no_other(self):
        # Review item 7: the saved installed skill folder, exactly as saved, is looked up.
        saved = str(self.root / 'skill')
        self.assertEqual(self.save({'brand': {'skill': saved}}, network=False)[0], 200)
        with mock.patch.object(brand_catalog, 'choices', return_value=SKILLS) as choices:
            status, answer = self.ask('/api/brands', {'skill': saved})
            self.assertEqual((status, answer['skills'], answer['problem']),
                             (200, [{'name': 'synthetic-brand', 'brands': SKILLS['skills'][0]['brands']}], None))
            choices.assert_called_once_with(saved)
            self.assertNotIn('/opt/', json.dumps(answer))
            choices.reset_mock()
            for other in (saved + ' ', saved + '/', str(self.root / 'other-skill'), '/opt/synthetic-brand-skill'):
                with self.subTest(skill=other):
                    self.assertEqual(self.ask('/api/brands', {'skill': other})[1]['problem'], brand_catalog.REMOTE_SKILL)
            choices.assert_not_called()

    def test_the_products_own_advice_reaches_a_phone_as_it_is(self):
        # Second review, item 6: a fixed sentence that says "~/" names no folder here.
        for changes, said in (({'local': {'root': ' /x'}}, 'Choose an absolute work folder, or one beginning with ~/.'),
                              ({'brand': {'skill': 'relative'}}, 'Use Git repository for a brand skill URL. Installed '
                               'skill folder needs an absolute path or one beginning with ~/.')):
            with self.subTest(changes=changes):
                self.assertEqual(self.save(changes), (409, {'error': said}))
        for text in ('/x', '~/brands', "No folder at '/srv/brands'.", 'Read from /x/y.'):
            self.assertTrue(brand_data.names_a_folder(text), text)
        for text in ('one beginning with ~/.', 'https://example.com/a', 'and/or', 'a / b'):
            self.assertFalse(brand_data.names_a_folder(text), text)

    def test_an_outdated_form_from_a_phone_is_refused_as_from_the_computer(self):
        # Second review, item 4: the outdated-form check answers first, with its fields.
        first, second = str(self.root / 'first'), str(self.root / 'second')
        self.assertEqual(self.save({'local': {'root': first}}, network=False)[0], 200)
        shown = shared.read()[0]                     # the phone loads the form
        self.assertEqual(self.save({'local': {'root': second}}, network=False)[0], 200)
        sent = {'changes': {'local': {'root': first}, 'person': {'name': 'Ana'}}, 'seen': shown}
        phone, here = self.ask('/api/shared', sent), self.ask('/api/shared', sent, network=False)
        self.assertEqual(phone, here)
        self.assertEqual((phone[0], phone[1]['conflict']), (409, {'fields': ['local.root']}))
        self.assertEqual(shared.read()[0]['local']['root'], second)

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
