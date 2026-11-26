"""A phone on Marketing Studio's private link, on a studio's own shared setup page (GitHub
issue #539): it cannot set or ask about a folder on the computer the studios run on, and is
not shown installed brand folder paths; it can still give a brand repository web address.

Every route of the page is walked with the network bridge's header, so a route added without
a decision in studio_core.onboarding.PHONE fails here. Disposable settings only."""
import json
import os
from email.message import Message
from unittest import mock

from test_brand_data import BrandFolders
from marketing_studio import shared
from studio_core import brand_catalog, brand_data, graphics, onboarding

SKILLS = {'skills': [{'name': 'synthetic-brand', 'path': '/opt/synthetic-brand-skill',
                      'brands': [{'brand': 'example', 'name': 'Example Co', 'variants': ['light']}]}],
          'problem': None}


class OnboardingPhoneTests(BrandFolders):
    def setUp(self):
        super().setUp()
        for patch in (mock.patch.dict(os.environ, {'HARNESS_BRAND_DATA': ''}),
                      mock.patch.object(brand_data.Path, 'home', return_value=self.root / 'nobody')):
            patch.start()
            self.addCleanup(patch.stop)
        self.prepared = []
        self.page = onboarding.Controller(8000, 'a' * 40, 'Training Studio', 'X-Test-Token',
                                          self.prepared.append, shared)

    def ask(self, path, sent=None, network=True):
        headers = Message()
        for key, value in {'Host': '127.0.0.1:8000', 'Origin': 'http://127.0.0.1:8000',
                           'Content-Type': 'application/json', 'X-Test-Token': 'a' * 40,
                           # The header the network bridge adds (marketing_studio.network.VIA_HEADER).
                           **({'X-Marketing-Studio-Via': 'network'} if network else {})}.items():
            headers[key] = value
        method = 'GET' if sent is None else 'POST'
        reply = self.page.answer(path, headers, method, None if sent is None else json.dumps(sent).encode())
        return reply[0], json.loads(reply[2])

    def save(self, changes, network=True):
        return self.ask('/onboarding/api/shared', {'changes': changes, 'seen': shared.read()[0]}, network)

    def test_every_route_has_a_phone_decision(self):
        routes = {*self.page.page.reads, *self.page.page.writes}
        self.assertEqual(routes, set(onboarding.PHONE))
        self.assertTrue(all(isinstance(why, str) and why for why in onboarding.PHONE.values()))

    def test_each_route_from_a_phone(self):
        folder = self.brands_folder(self.root / 'brands', 'acme', 'other')
        seen = set()

        def route(path):
            seen.add(path)
            return path

        # Reads: the saved settings and an assistant's models, nothing about a folder asked.
        self.assertEqual(self.ask(route('/onboarding/api/home'))[0], 200)
        with mock.patch.object(self.page.models, 'get', return_value={'models': []}):
            self.assertEqual(self.ask(route('/onboarding/api/models') + '?agent=claude')[0], 200)
            self.assertEqual(self.ask('/onboarding/api/models', {'agent': 'claude'})[0], 200)

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
        route('/onboarding/api/shared')
        # A folder the computer saved can be sent as it was shown, and the rest saves.
        self.assertEqual(self.save({'local': {'root': str(self.root / 'work')}}, network=False)[0], 200)
        held = shared.read()[0]
        status, _ = self.ask('/onboarding/api/shared', {'changes': {'local': {'root': str(self.root / 'work')},
                                                                     'person': {'name': 'Cy'}}, 'seen': held})
        self.assertEqual((status, shared.read()[0]['person']['name']), (200, 'Cy'))
        # Emptying a folder setting changes it too.
        status, answer = self.save({'local': {'root': None}})
        self.assertEqual(status, 409)
        self.assertIn('“Workspace folder”', answer['error'])
        # An outdated form is still refused as before: a value someone else changed meanwhile.
        status, answer = self.ask('/onboarding/api/shared', {'changes': {'person': {'name': 'Di'}},
                                                             'seen': {**held, 'person': {'name': 'Old'}}})
        self.assertEqual(status, 409)
        self.assertEqual(answer['conflict'], {'fields': ['person.name']})

        # Finishing setup takes no folder: it uses what the settings already hold.
        self.assertEqual(self.ask(route('/onboarding/api/setup'), {'done': True})[0], 200)
        self.assertEqual(len(self.prepared), 1)

        # Document graphics: the models are listed, a key is never taken over the link.
        status, answer = self.ask(route('/onboarding/api/graphics'), {'key': 'synthetic-not-a-key'})
        self.assertEqual(status, 409)
        self.assertIn('not taken over the phone link', answer['error'])
        with mock.patch.object(graphics, 'listed', return_value={'provider': 'gemini', 'models': []}):
            self.assertEqual(self.ask('/onboarding/api/graphics', {'models': 'gemini'})[0], 200)

        # Installed brands by name; a skill folder refused unread.
        with mock.patch.object(brand_catalog, 'choices', return_value=SKILLS) as choices:
            status, answer = self.ask(route('/onboarding/api/brands'), {})
            self.assertEqual((status, answer['skills']),
                             (200, [{'name': 'synthetic-brand', 'brands': SKILLS['skills'][0]['brands']}]))
            status, answer = self.ask('/onboarding/api/brands', {'skill': '/opt/synthetic-brand-skill'})
            self.assertEqual((status, answer['problem']), (200, brand_catalog.REMOTE_SKILL))
            self.assertEqual(choices.call_count, 1)
            # The computer is answered as before.
            self.assertEqual(self.ask('/onboarding/api/brands', {}, network=False)[1]['skills'], SKILLS['skills'])

        # Get brands: what was got, without the folder; a refusal names no folder.
        self.assertEqual(self.save({'brand': {'brands': str(folder)}}, network=False)[0], 200)
        status, answer = self.ask(route('/onboarding/api/brands-repository'), {})
        self.assertEqual(status, 200)
        self.assertEqual((answer['brands'], answer['action']), (['acme', 'other'], 'used'))
        self.assertNotIn('folder', answer)
        self.assertNotIn(str(self.root), json.dumps(answer))
        self.assertEqual(self.ask('/onboarding/api/brands-repository', {}, network=False)[1]['folder'], str(folder))
        gone = self.root / 'gone-brands'
        self.assertEqual(self.save({'brand': {'brands': str(gone)}}, network=False)[0], 200)
        status, answer = self.ask('/onboarding/api/brands-repository', {})
        self.assertEqual((status, answer['error']), (409, brand_data.REMOTE_UNGOT))
        self.assertIn(str(gone), self.ask('/onboarding/api/brands-repository', {}, network=False)[1]['error'])

        # A research site is a web address.
        status, answer = self.ask(route('/onboarding/api/research-site'), {'site': 'https://example.com/docs'})
        self.assertEqual(status, 200)

        self.assertEqual(seen, {*self.page.page.reads, *self.page.page.writes}, 'every route was asked from a phone')

    def test_a_folder_is_unchanged_only_when_it_is_exactly_what_is_saved(self):
        work = str(self.root / 'work')
        self.assertEqual(self.save({'local': {'root': work}}, network=False)[0], 200)
        # Another folder by one character, even with `seen` saying the phone was shown it.
        for sent, seen in [(sent, seen) for sent in (work + ' ', work + '/', work + '/.')
                           for seen in (shared.read()[0], {'local': {'root': sent}})]:
            with self.subTest(sent=sent, seen=seen):
                status, answer = self.ask('/onboarding/api/shared', {
                    'changes': {'local': {'root': sent}, 'person': {'name': 'Ana'}},
                    'seen': seen})
                self.assertEqual(status, 409)
                self.assertIn('“Workspace folder” names a folder', answer['error'])
                self.assertEqual(shared.read()[0]['local']['root'], work)
        # A saved folder that ends in a space, sent back exactly, is no change.
        self.assertEqual(self.save({'local': {'root': work + ' '}}, network=False)[0], 200)
        self.assertEqual(self.save({'local': {'root': work + ' '}, 'person': {'name': 'Bo'}})[0], 200)
        self.assertEqual((shared.read()[0]['local']['root'], shared.read()[0]['person']['name']), (work + ' ', 'Bo'))

    def test_a_failure_that_names_a_folder_is_said_to_a_phone_without_it(self):
        # Review item 3: each lookup raising an OSError (or a refusal) that names a folder.
        folder = self.brands_folder(self.root / 'brands', 'acme')
        self.assertEqual(self.save({'brand': {'brands': str(folder)}, 'local': {'root': str(self.root / 'work')}},
                                   network=False)[0], 200)
        secret = str(self.root / 'private-folder')
        denied = PermissionError(13, 'Permission denied', secret)

        def prepare_fails(values):
            raise denied
        cases = (
            ('/onboarding/api/brands-repository', {}, mock.patch.object(brand_data, 'record', side_effect=denied)),
            ('/onboarding/api/brands-repository', {}, mock.patch.object(
                brand_data, 'bring', side_effect=ValueError(f'{secret} holds no brands'))),
            ('/onboarding/api/brands', {}, mock.patch.object(brand_catalog, 'choices', side_effect=denied)),
            ('/onboarding/api/brands', {}, mock.patch.object(brand_data, 'status', side_effect=denied)),
            ('/onboarding/api/setup', {'done': True}, mock.patch.object(self.page, 'prepare', prepare_fails)),
            ('/onboarding/api/shared', {'changes': {'person': {'name': 'Ana'}}, 'seen': {}},
             mock.patch.object(shared, 'update', side_effect=denied)),
        )
        for path, sent, patch in cases:
            with self.subTest(path=path, patch=patch.attribute):
                with patch:
                    status, answer = self.ask(path, sent)
                self.assertNotIn(secret, json.dumps(answer))
                self.assertNotIn('Errno', json.dumps(answer))
                if status != 200:
                    self.assertEqual(status, 409)
        # The computer is told as before: the error itself.
        with mock.patch.object(brand_data, 'record', side_effect=denied):
            with self.assertRaises(PermissionError):
                self.ask('/onboarding/api/brands-repository', {}, network=False)

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
        # Review item 5: the saved folder values each route answers a phone with, as
        # onboarding.PHONE_SHOWS records them; what is shown is the owner's separate decision.
        from test_home_phone import folders_shown
        folder = self.brands_folder(self.root / 'brands', 'acme')
        self.assertEqual(self.save({'local': {'root': str(self.root / 'work')},
                                    'brand': {'skill': str(self.root / 'skill'), 'brands': str(folder),
                                              'repository': str(self.root / 'skill-repo')},
                                    'team': {'repository': str(self.root / 'team-repo')}}, network=False)[0], 200)
        asked = {'/onboarding/api/home': None, '/onboarding/api/models': {'agent': 'claude'},
                 '/onboarding/api/shared': {'changes': {'person': {'name': 'Ana'}}, 'seen': {}},
                 '/onboarding/api/setup': {'done': True}, '/onboarding/api/graphics': {'models': 'gemini'},
                 '/onboarding/api/brands': {}, '/onboarding/api/brands-repository': {},
                 '/onboarding/api/research-site': {'site': 'https://example.com'}}
        self.assertEqual(set(asked), set(onboarding.PHONE))
        shown = {}
        with mock.patch.object(self.page.models, 'get', return_value={'models': []}), \
                mock.patch.object(graphics, 'listed', return_value={'provider': 'gemini', 'models': []}), \
                mock.patch.object(brand_catalog, 'choices', return_value=SKILLS):
            for path, sent in asked.items():
                with self.subTest(path=path):
                    found = folders_shown(self.ask(path, sent)[1])
                    if found:
                        shown[path] = found
        self.assertEqual(shown, {path: set(fields) for path, fields in onboarding.PHONE_SHOWS.items()})
        for path, why in onboarding.PHONE.items():
            self.assertEqual(onboarding.SAVED in why, path in onboarding.PHONE_SHOWS, path)

    def test_a_phone_looks_up_the_saved_skill_folder_by_name_and_no_other(self):
        # Review item 7: the saved installed skill folder, exactly as saved, is looked up.
        saved = str(self.root / 'skill')
        self.assertEqual(self.save({'brand': {'skill': saved}}, network=False)[0], 200)
        with mock.patch.object(brand_catalog, 'choices', return_value=SKILLS) as choices:
            status, answer = self.ask('/onboarding/api/brands', {'skill': saved})
            self.assertEqual((status, answer['skills'], answer['problem']),
                             (200, [{'name': 'synthetic-brand', 'brands': SKILLS['skills'][0]['brands']}], None))
            choices.assert_called_once_with(saved)
            self.assertNotIn('/opt/', json.dumps(answer))
            choices.reset_mock()
            for other in (saved + ' ', saved + '/', str(self.root / 'other-skill'), '/opt/synthetic-brand-skill'):
                with self.subTest(skill=other):
                    self.assertEqual(self.ask('/onboarding/api/brands', {'skill': other})[1]['problem'],
                                     brand_catalog.REMOTE_SKILL)
            choices.assert_not_called()

    def test_a_computer_still_changes_folder_settings(self):
        status, _ = self.save({'local': {'root': str(self.root / 'work')}, 'brand': {'skill': str(self.root / 'skill')}},
                              network=False)
        self.assertEqual(status, 200)
        self.assertEqual(shared.read()[0]['brand']['skill'], str(self.root / 'skill'))

    def test_the_refusal_names_every_folder_setting_it_refuses(self):
        said = onboarding.folders_refused({'local': {'root': '/a'}, 'brand': {'skill': '~/b', 'brands': 'git@example.com:o/b.git'}}, {})
        self.assertEqual(said, '“Workspace folder” and “Installed skill folder” name folders on the computer the '
                               'studios run on, so they are changed only on that computer. Put them back as they '
                               'were to save your other changes here.')
        # A folder replaced by a web address is allowed; the same value, or none, is no change.
        self.assertIsNone(onboarding.folders_refused({'brand': {'brands': 'https://example.com/b.git'}},
                                                     {'brand': {'brands': '/a'}}))
        # Unchanged means exactly what is held, character for character (review item 1).
        self.assertIsNotNone(onboarding.folders_refused({'local': {'root': '/a '}}, {'local': {'root': '/a'}}))
        self.assertIsNone(onboarding.folders_refused({'local': {'root': '/a '}}, {'local': {'root': '/a '}}))
        self.assertIsNone(onboarding.folders_refused({'brand': {'skill': ''}}, {}))
        # The header is read as the bridge sends it, and only so.
        from marketing_studio import network
        self.assertEqual(onboarding.VIA_HEADER, network.VIA_HEADER)
        for value, remote in (('network', True), (' Network ', True), ('local', False)):
            headers = Message()
            headers[onboarding.VIA_HEADER] = value
            self.assertEqual(onboarding.carried(headers), remote)
        self.assertFalse(onboarding.carried(Message()))


if __name__ == '__main__':
    import unittest
    unittest.main()
