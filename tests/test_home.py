import concurrent.futures
import http.client
import json
import os
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from unittest import mock

from marketing_studio import catalog, server, shared, state, validation
from marketing_studio.errors import WorkspaceError
from marketing_studio.launcher import Launcher, local_link
from marketing_studio.page import Home


class IsolatedHome(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = mock.patch.dict(os.environ, {'STUDIOS_CONFIG': str(self.root / 'shared.json'),
                                               'MARKETING_STUDIO_DATA': str(self.root / 'data')})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.launcher = Launcher()
        self.addCleanup(self.launcher.close)
        self.page = Home(8000, self.launcher)

    def write(self, path, sent):
        return json.loads(self.page.write(path, sent)[2])


class HomeTests(IsolatedHome):
    def test_first_launch_is_setup_and_shared_values_carry_over(self):
        shared.update({'person': {'name': 'Author'}, 'assistant': {'agent': 'codex'}})
        found = self.page.snapshot()
        self.assertFalse(found['setup']['done'])
        self.assertEqual(found['shared']['person']['name'], 'Author')
        self.assertEqual([s['name'] for s in found['studios']],
                         ['Blog Studio', 'Presentation Studio', 'Training Studio'])

    def test_complete_and_reopen_settings(self):
        self.write('/api/shared', {'changes': {'local': {'root': str(self.root / 'work')}}, 'seen': {}})
        self.write('/api/setup', {'done': True})
        self.assertTrue(Home(8000, self.launcher).snapshot()['setup']['done'])
        self.assertNotIn('shared', state.read())
        self.write('/api/shared', {'changes': {'output': 'google'}, 'seen': shared.read()[0]})
        self.assertEqual(shared.read()[0]['output'], 'google')

    def test_cannot_finish_without_workspace_or_launch_before_setup(self):
        with self.assertRaises(WorkspaceError):
            self.write('/api/setup', {'done': True})
        with self.assertRaises(WorkspaceError):
            self.write('/api/open', {'studio': 'blog'})
        self.assertFalse(state.read()['done'])

    def test_prepare_failure_does_not_complete_setup(self):
        shared.update({'local': {'root': str(self.root / 'work')}})
        with mock.patch.object(self.launcher, 'prepare', side_effect=WorkspaceError('Git needs an identity')):
            with self.assertRaisesRegex(WorkspaceError, 'identity'):
                self.write('/api/setup', {'done': True, 'prepare': True})
        self.assertFalse(state.read()['done'])

    def test_invalid_group_is_read_as_problem(self):
        shared.path().write_text('{"schema": 1, "assistant": 23}')
        self.assertTrue(shared.read()[1])

    def test_partial_setup_is_durable(self):
        self.write('/api/shared', {'changes': {'person': {'name': 'Writer'}}, 'seen': {}})
        self.assertEqual(self.page.snapshot()['shared']['person']['name'], 'Writer')
        self.assertFalse(state.read()['done'])

    def test_invalid_shared_file_is_never_overwritten(self):
        shared.path().write_text('not json')
        self.assertTrue(self.page.snapshot()['shared_problem'])
        with self.assertRaises(WorkspaceError):
            self.write('/api/shared', {'changes': {'share': 'asked'}, 'seen': {}})
        self.assertEqual(shared.path().read_text(), 'not json')

    def test_lossless_merge_and_same_leaf_conflict(self):
        original = '{\n  "unknown": {"keep": [1, 2]},\n  "person": {"name": "One"}\n}\n'
        shared.path().write_text(original)
        seen = shared.read()[0]
        shared.update({'person': {'name': 'Two'}})
        with self.assertRaises(WorkspaceError):
            self.write('/api/shared', {'changes': {'person': {'name': 'Three'}}, 'seen': seen})
        self.write('/api/shared', {'changes': {'output': 'pptx'}, 'seen': seen})
        self.assertIn('"unknown": {"keep": [1, 2]}', shared.path().read_text())
        self.assertEqual(shared.read()[0]['person']['name'], 'Two')

    def test_concurrent_unrelated_writes_both_survive(self):
        def save(changes):
            shared.update(changes)
        with concurrent.futures.ThreadPoolExecutor() as pool:
            list(pool.map(save, [{'person': {'name': 'Writer'}}, {'output': 'pptx'}, {'share': 'asked'}]))
        self.assertEqual(shared.read()[0], {'schema': 1, 'person': {'name': 'Writer'}, 'output': 'pptx', 'share': 'asked'})
        self.assertEqual(shared.path().stat().st_mode & 0o777, 0o600)

    def test_switch_to_local_clears_repository_without_erasing_branch(self):
        shared.update({'team': {'repository': 'https://example.com/team.git', 'branch': 'work'}})
        self.write('/api/shared', {'changes': {'team': {'repository': None}, 'local': {'root': str(self.root)}},
                                   'seen': shared.read()[0]})
        self.assertIsNone(shared.read()[0]['team']['repository'])
        self.assertEqual(shared.read()[0]['team']['branch'], 'work')

    def test_unknown_studio_and_invalid_path_are_refused(self):
        with self.assertRaises(WorkspaceError):
            self.launcher.open('other', {}, {})
        with self.assertRaises(WorkspaceError):
            self.write('/api/paths', {'paths': {'blog': str(self.root)}})

    def test_preferences_invalid_file_is_preserved(self):
        state.data_root().mkdir()
        target = state.data_root() / 'home.json'
        target.write_text('broken')
        with self.assertRaises(WorkspaceError):
            state.read()
        self.assertEqual(target.read_text(), 'broken')


class ValidationTests(unittest.TestCase):
    def test_valid_optional_values_and_local_only(self):
        validation.check({'assistant': {'agent': 'codex', 'model': 'model-from-account', 'effort': 'high'},
                          'team': {'repository': None}, 'local': {'root': '~/Studios'}, 'output': 'pptx'}, {})
        validation.repository('git@github.com:example/team.git')
        validation.repository('/tmp/local-team.git')

    def test_invalid_values(self):
        invalid = [{'schema': 2}, {'assistant': {'agent': 'other'}},
                   {'assistant': {'model': '--bad'}}, {'assistant': {'model': 'two words'}},
                   {'assistant': {'agent': 'claude', 'effort': 'ultra'}},
                   {'local': {'root': 'relative/folder'}}, {'person': {'name': 'n' * 101}},
                   {'output': 'pdf'}, {'share': 'always'}, {'team': {'branch': '../branch'}},
                   {'brand': {'release': 'v1'}}, {'brand': {'brand': '<script>'}},
                   {'assistant': {'unknown': 'value'}}, {'person': {'name': '\n'}}]
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(WorkspaceError):
                validation.check(changes, {})

    def test_repository_credentials_and_helpers_are_refused(self):
        for address in ['https://secret@example.com/repo', 'https://a:b@example.com/repo',
                        'https://example.com/repo?token=secret', 'ext::command',
                        'file:///tmp/repo', '-upload-pack=bad', 'ssh://user:secret@example.com/repo']:
            with self.subTest(address=address), self.assertRaises(WorkspaceError):
                validation.repository(address)

    def test_only_local_session_links(self):
        token = 'a' * 40
        self.assertTrue(local_link('http://127.0.0.1:9000/#token=' + token))
        self.assertTrue(local_link('http://127.0.0.1:9000/#' + token))
        for link in ['https://example.com/#' + token, 'http://localhost:9000/#' + token,
                     'http://127.0.0.1:9000/other#' + token, 'javascript:alert(1)',
                     'http://127.0.0.1:9000/#bad', 'http://127.0.0.1:999999/#' + token]:
            self.assertFalse(local_link(link))


class SecurityTests(IsolatedHome):
    def setUp(self):
        super().setUp()
        self.desk = server.Desk(page=lambda port: Home(port, self.launcher))
        self.desk.start()
        self.addCleanup(self.desk.stop)

    def request(self, method='GET', path='/api/home', data=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.desk.port, timeout=3)
        self.addCleanup(connection.close)
        connection.request(method, path, body=data, headers=headers or {})
        response = connection.getresponse()
        body = response.read()
        return response.status, response.headers, body

    def auth(self):
        return {server.TOKEN_HEADER: self.desk.token, 'Origin': self.desk.address.rstrip('/'),
                'Content-Type': 'application/json'}

    def test_http_auth_and_static_security_headers(self):
        status, headers, body = self.request(path='/')
        self.assertEqual(status, 200)
        self.assertNotIn(self.desk.token.encode(), body)
        self.assertEqual(headers['X-Frame-Options'], 'DENY')
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertEqual(self.request()[0], 403)
        self.assertEqual(self.request(headers=self.auth())[0], 200)
        self.assertEqual(self.request(headers={**self.auth(), 'Host': 'evil.example'})[0], 403)

    def test_changes_require_own_origin_json_and_bounded_body(self):
        for update, expected in [({'Origin': 'https://evil.example'}, 403),
                                 ({'Content-Type': 'text/plain'}, 415),
                                 ({server.TOKEN_HEADER: 'wrong'}, 403)]:
            self.assertEqual(self.request('POST', '/api/setup', '{}', {**self.auth(), **update})[0], expected)
        self.assertEqual(self.request('POST', '/api/setup', '[]', self.auth())[0], 400)
        self.assertEqual(self.request('POST', '/api/setup', 'x' * 64001, self.auth())[0], 413)
        self.assertEqual(self.request('PUT', headers=self.auth())[0], 405)
        self.assertEqual(self.request('GET', '/../../etc/passwd', headers=self.auth())[0], 404)

    def test_installed_brand_lookup_is_authenticated_and_read_only(self):
        expected = {'skills': [], 'problem': 'No synthetic brand is installed.'}
        before = shared.read()[0]
        with mock.patch('studio_core.brand_catalog.choices', return_value=expected) as lookup:
            self.assertEqual(self.request('POST', '/api/brands', '{}')[0], 403)
            lookup.assert_not_called()
            status, _, body = self.request('POST', '/api/brands', '{}', self.auth())
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body), expected)
        self.assertEqual(shared.read()[0], before)

    def test_real_post_and_restart_keeps_setup(self):
        body = json.dumps({'changes': {'local': {'root': str(self.root / 'work')}}, 'seen': {}})
        self.assertEqual(self.request('POST', '/api/shared', body, self.auth())[0], 200)
        self.assertEqual(self.request('POST', '/api/setup', '{"done": true}', self.auth())[0], 200)
        self.assertTrue(state.read()['done'])


if __name__ == '__main__':
    unittest.main()
