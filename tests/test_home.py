import concurrent.futures
import http.client
import json
import os
import tempfile
import threading
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
                                               'MARKETING_STUDIO_DATA': str(self.root / 'data'),
                                               **{key: str(self.root / key.lower()) for key in ('BLOG_STUDIO_DATA','TRAINING_STUDIO_DATA','PRESENTATION_STUDIO_DATA','INFOGRAPHIC_STUDIO_DATA')}})
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
                         ['Blog Studio', 'Presentation Studio', 'Training Studio', 'Infographic Studio'])

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

    def test_cards_show_each_installed_studios_workspace_once_setup_is_done(self):
        self.assertTrue(all(row['workspace'] is None for row in self.page.snapshot()['studios']))
        self.write('/api/shared', {'changes': {'local': {'root': str(self.root / 'work')}}, 'seen': {}})
        self.write('/api/setup', {'done': True})
        with mock.patch('marketing_studio.workspaces.connection', side_effect=lambda identifier, values: {
                'state': 'none', 'connect': False, 'summary': identifier + ' ' + values['local']['root']}) as asked:
            rows = self.page.snapshot()['studios']
        self.assertEqual([row['workspace']['summary'] for row in rows if row['installed']],
                         [f"{row['id']} {self.root / 'work'}" for row in rows if row['installed']])
        self.assertEqual(asked.call_count, sum(row['installed'] for row in rows))

    def test_storage_change_after_setup_prepares_studios_and_reports(self):
        self.write('/api/shared', {'changes': {'local': {'root': str(self.root / 'work')}}, 'seen': {}})
        self.write('/api/setup', {'done': True})
        report = {'blog': {'prepared': True, 'connect': {'from': {}, 'to': {}, 'carry': {'blogs': 1}}}}
        with mock.patch.object(self.launcher, 'prepare', return_value=report) as prepare:
            reply = self.write('/api/shared', {'changes': {'output': 'google'}, 'seen': shared.read()[0]})
            prepare.assert_not_called()
            self.assertNotIn('prepared', reply)
            reply = self.write('/api/shared', {'changes': {'team': {'repository': str(self.root / 'team.git')}},
                                               'seen': shared.read()[0]})
        self.assertEqual(reply['prepared'], report)
        self.assertEqual(prepare.call_args.args[1]['team']['repository'], str(self.root / 'team.git'))
        self.assertTrue(prepare.call_args.args[0]['done'])
        with mock.patch.object(self.launcher, 'prepare', side_effect=WorkspaceError('Git needs an identity')):
            reply = self.write('/api/shared', {'changes': {'share': 'asked'}, 'seen': shared.read()[0]})
        self.assertEqual(reply['prepare_problem'], 'Git needs an identity')
        self.assertEqual(shared.read()[0]['share'], 'asked')

    def test_finishing_setup_returns_what_prepare_reported(self):
        shared.update({'team': {'repository': str(self.root / 'team.git')}})
        report = {'blog': {'prepared': True, 'workspace': {}, 'notice': 'The shared repository did not accept the changes.'}}
        with mock.patch.object(self.launcher, 'prepare', return_value=report):
            reply = self.write('/api/setup', {'done': True, 'prepare': True})
        self.assertEqual(reply['prepared'], report)
        self.assertTrue(reply['setup']['done'])

    def test_storage_change_before_setup_prepares_nothing(self):
        with mock.patch.object(self.launcher, 'prepare') as prepare:
            self.write('/api/shared', {'changes': {'team': {'repository': str(self.root / 'team.git')}}, 'seen': {}})
        prepare.assert_not_called()

    def test_connect_needs_setup_and_relays_the_launcher(self):
        with self.assertRaisesRegex(WorkspaceError, 'Finish shared setup'):
            self.write('/api/connect', {'studio': 'blog'})
        self.write('/api/shared', {'changes': {'team': {'repository': str(self.root / 'team.git')}}, 'seen': {}})
        self.write('/api/setup', {'done': True})
        done = {'connected': True, 'studio': 'blog', 'carried': {'blogs': 2}}
        with mock.patch.object(self.launcher, 'connect', return_value=done) as connect:
            reply = self.write('/api/connect', {'studio': 'blog'})
        self.assertEqual(reply['connected'], done)
        self.assertIn('studios', reply)
        self.assertEqual(connect.call_args.args[0], 'blog')
        self.assertEqual(connect.call_args.args[2]['team']['repository'], str(self.root / 'team.git'))

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
        with self.assertRaisesRegex(WorkspaceError, '^“Your name” was changed in another tab or studio') as refused:
            self.write('/api/shared', {'changes': {'person': {'name': 'Three'}}, 'seen': seen})
        self.assertEqual(refused.exception.details, {'conflict': {'fields': ['person.name']}})
        self.assertIn('Load newer settings', str(refused.exception))
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
        store = {'state': 'none', 'said': 'Synthetic: no brands folder.'}
        before = shared.read()[0]
        # The brands folder's state is pinned: this computer's own Harness Brand folder is never read.
        with mock.patch('studio_core.brand_catalog.choices', return_value=expected) as lookup, \
                mock.patch('studio_core.brand_data.status', return_value=store):
            self.assertEqual(self.request('POST', '/api/brands', '{}')[0], 403)
            lookup.assert_not_called()
            status, _, body = self.request('POST', '/api/brands', '{}', self.auth())
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body), {**expected, 'store': store})
        self.assertEqual(shared.read()[0], before)

    def test_real_post_and_restart_keeps_setup(self):
        body = json.dumps({'changes': {'local': {'root': str(self.root / 'work')}}, 'seen': {}})
        self.assertEqual(self.request('POST', '/api/shared', body, self.auth())[0], 200)
        self.assertEqual(self.request('POST', '/api/setup', '{"done": true}', self.auth())[0], 200)
        self.assertTrue(state.read()['done'])


if __name__ == '__main__':
    unittest.main()


class StudioReadinessTests(IsolatedHome):
    def test_all_installed_studios_ready_before_launch_without_starting_them(self):
        shared.update({'local':{'root':str(self.root/'work')},'assistant':{'agent':'codex'}})
        self.write('/api/setup',{'done':True})
        with mock.patch('marketing_studio.page.runtime.assistant_command',return_value='/synthetic/codex'),mock.patch('marketing_studio.page.shutil.which',return_value='/synthetic/git'),mock.patch.object(self.launcher,'open',side_effect=AssertionError('No launch')):
            found=self.page.snapshot()
        for row in found['studios']:
            if row['installed']:
                self.assertEqual(row['readiness']['state'],'done');self.assertEqual(row['readiness']['label'],'Can open');self.assertIsNone(row['readiness']['action']);self.assertFalse(row['running'])

    def test_missing_shared_setup_and_assistant_do_not_show_green(self):
        self.assertTrue(all(r['readiness']['state']!='done' for r in self.page.snapshot()['studios']))
        shared.update({'local':{'root':str(self.root/'work')}});self.write('/api/setup',{'done':True})
        with mock.patch('marketing_studio.page.runtime.assistant_command',return_value=None):
            self.assertTrue(all(r['readiness']['state']!='done' for r in self.page.snapshot()['studios']))

    def test_each_readiness_state_says_why_and_how_to_recover(self):
        row = {'installed': True}
        with mock.patch('marketing_studio.page.runtime.assistant_command', return_value='/synthetic/claude'), \
                mock.patch('marketing_studio.page.shutil.which', return_value=None):
            missing = Home.readiness(row, None, True, 'claude')
        self.assertEqual((missing['state'], missing['label']), ('review', 'Needs setup'))
        self.assertIn('Git was not found', missing['detail'])
        self.assertEqual(missing['action'], {'view': 'computer', 'label': 'Check this computer'})
        with mock.patch('marketing_studio.page.runtime.assistant_command', return_value=None), \
                mock.patch('marketing_studio.page.shutil.which', return_value=None):
            both = Home.readiness(row, None, True, 'codex')
        self.assertIn('Codex and Git were not found', both['detail'])
        unset = Home.readiness(row, None, False, 'claude')
        self.assertEqual((unset['label'], unset['action']['view']), ('Needs setup', 'settings'))
        unread = Home.readiness(row, 'The file could not be read.', False, 'claude')
        self.assertEqual((unread['state'], unread['label'], unread['action']['view']),
                         ('none', 'Not checked', 'settings'))
        absent = Home.readiness({'installed': False}, None, True, 'claude')
        self.assertEqual((absent['state'], absent['label'], absent['action']), ('off', 'Not installed', None))
        self.assertIn('never installs', absent['detail'])
        with mock.patch('marketing_studio.page.runtime.assistant_command', return_value='/synthetic/claude'), \
                mock.patch('marketing_studio.page.shutil.which', return_value='/synthetic/git'):
            ready = Home.readiness(row, None, True, 'claude')
        self.assertEqual((ready['state'], ready['label']), ('done', 'Can open'))
        self.assertIn('Sign-in is checked when a task needs it', ready['detail'])

    def test_browsing_and_checking_start_nothing_and_change_nothing(self):
        shared.update({'local': {'root': str(self.root / 'work')}, 'assistant': {'agent': 'claude'}})
        self.write('/api/setup', {'done': True})
        before = shared.path().read_bytes()
        ran = []

        def local_only(command, **_):
            ran.append(command)
            return mock.Mock(returncode=1, stdout='')
        refuse = AssertionError('Browsing must not open, prepare or connect a studio')
        with mock.patch.object(self.launcher, 'open', side_effect=refuse), \
                mock.patch.object(self.launcher, 'prepare', side_effect=refuse), \
                mock.patch.object(self.launcher, 'connect', side_effect=refuse), \
                mock.patch('subprocess.Popen', side_effect=AssertionError('Nothing is started')), \
                mock.patch('marketing_studio.computer.subprocess.run', side_effect=local_only):
            json.loads(self.page.read('/api/home', lambda _: None)[2])
            looked = self.write('/api/computer', {})['computer']
            again = json.loads(self.page.read('/api/home', lambda _: None)[2])
        # A check reads the version control tool's own settings and nothing else; the home then reports it.
        self.assertTrue(ran and all(command[1:3] == ['config', '--get'] for command in ran))
        self.assertEqual(again['computer'], looked)
        self.assertFalse(next(item for item in looked['items'] if item['name'] == 'Git identity')['ready'])
        self.assertEqual(shared.path().read_bytes(), before)
        self.assertFalse((self.root / 'work').exists())


class SharedSettingsSaveTests(IsolatedHome):
    """The everyday save keeps every override and unrelated value, and an outdated form is
    still refused leaf by leaf."""
    OVERRIDES = ('{\n  "schema": 1,\n  "kept": {"by": "another tool"},\n'
                 '  "person": {"name": "Ana"},\n  "assistant": {"agent": "claude"},\n  "local": {"root": "/tmp/studios"},\n'
                 '  "brand": {"repository": "https://example.com/brand.git", "release": "v1.4.0"},\n'
                 '  "models": {"schema": 1, "agent": "claude", "mode": "by_task", "profiles": '
                 '{"quick": {"selection": "explicit", "model": "synthetic-small", "effort": "low"}}},\n'
                 '  "research": {"sites": ["https://docs.example.com/guide"]},\n'
                 '  "setup": {"version": 1}\n}\n')

    def test_an_everyday_save_keeps_overrides_and_unrelated_values(self):
        shared.path().write_text(self.OVERRIDES)
        seen = shared.read()[0]
        self.write('/api/shared', {'changes': {'person': {'name': 'Bea'}}, 'seen': seen})
        self.assertEqual(shared.path().read_text(), self.OVERRIDES.replace('"Ana"', '"Bea"'))

    def test_an_outdated_form_cannot_replace_an_override_another_studio_changed(self):
        shared.path().write_text(self.OVERRIDES)
        seen = shared.read()[0]
        shared.update({'brand': {'repository': 'https://example.com/brand-2.git'}})
        with self.assertRaisesRegex(WorkspaceError, '“Brand Git repository” was changed in another tab or studio'):
            self.write('/api/shared', {'changes': {'brand': {'repository': None}}, 'seen': seen})
        # Changing only an everyday value from the same outdated form is still accepted.
        self.write('/api/shared', {'changes': {'person': {'name': 'Bea'}}, 'seen': seen})
        values = shared.read()[0]
        self.assertEqual((values['brand']['repository'], values['person']['name']),
                         ('https://example.com/brand-2.git', 'Bea'))
        self.assertEqual(values['models']['profiles']['quick']['model'], 'synthetic-small')
        self.assertEqual(values['kept'], {'by': 'another tool'})

    def test_a_brand_release_kept_or_sent_by_an_older_version_is_dropped_silently(self):
        # Saved by an older version: the settings still load, the release is not shown, and it
        # is left in the file as it is.
        shared.path().write_text(self.OVERRIDES)
        shown = self.page.snapshot()
        self.assertNotIn('release', shown['shared']['brand'])
        self.assertEqual(shown['shared']['brand']['repository'], 'https://example.com/brand.git')
        seen = shared.read()[0]
        # Sent by a form an older version drew: dropped, never refused and never written.
        self.write('/api/shared', {'changes': {'person': {'name': 'Bea'},
                                               'brand': {'release': 'v9.9.9'}}, 'seen': seen})
        self.assertEqual(shared.path().read_text(), self.OVERRIDES.replace('"Ana"', '"Bea"'))


class SlowPrepareTests(IsolatedHome):
    """Preparing studios lets go of the home's lock: reads answer meanwhile, and a result
    made for settings that changed meanwhile is not kept. Counted, never timed."""

    def setUp(self):
        super().setUp()
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self.addCleanup(self.pool.shutdown, wait=True)
        self.entered, self.release = threading.Event(), threading.Event()
        self.addCleanup(self.release.set)
        self.during = None   # what to do while the prepare is in hand, on the test's thread

    def slow(self, preferences, values, only=None):
        self.entered.set()
        if not self.release.wait(10):
            raise AssertionError('The test never let the prepare finish')
        return {'blog': {'prepared': True, 'workspace': {}}}

    def read(self, path):
        # Answered on another thread, so a read stuck behind the lock fails instead of hanging.
        return json.loads(self.pool.submit(self.page.read, path, lambda _: None).result(timeout=5)[2])

    def started(self, path, sent):
        with mock.patch.object(self.launcher, 'prepare', side_effect=self.slow):
            reply = self.pool.submit(self.write, path, sent)
            self.assertTrue(self.entered.wait(5), 'The prepare did not start')
            found = self.during() if self.during else None
            self.assertFalse(reply.done(), 'The prepare was still in hand')
            self.release.set()
            return reply, found

    def test_home_and_this_computer_answer_while_a_slow_prepare_runs(self):
        self.write('/api/shared', {'changes': {'local': {'root': str(self.root / 'work')}}, 'seen': {}})
        self.write('/api/setup', {'done': True})
        self.during = lambda: (self.read('/api/home'), self.read('/api/computer'))
        reply, (home, computer) = self.started(
            '/api/shared', {'changes': {'team': {'repository': str(self.root / 'team.git')}},
                            'seen': shared.read()[0]})
        self.assertIn('studios', home)
        self.assertIn('computer', computer)
        self.assertEqual(reply.result(timeout=5)['prepared'], {'blog': {'prepared': True, 'workspace': {}}})

    def test_finishing_setup_answers_reads_while_it_prepares(self):
        shared.update({'local': {'root': str(self.root / 'work')}})
        self.during = lambda: self.read('/api/home')
        reply, home = self.started('/api/setup', {'done': True, 'prepare': True})
        self.assertFalse(home['setup']['done'])
        found = reply.result(timeout=5)
        self.assertTrue(found['setup']['done'])
        self.assertIn('prepared', found)
        self.assertTrue(state.read()['done'])

    def test_the_same_setup_sent_twice_succeeds_twice(self):
        # Two tabs, or a double click: the second arrives while the first prepares.
        shared.update({'local': {'root': str(self.root / 'work')}})
        sent = {'done': True, 'prepare': True}
        self.during = lambda: self.pool.submit(self.write, '/api/setup', sent)
        first, second = self.started('/api/setup', sent)
        replies = [first.result(timeout=10), second.result(timeout=10)]
        self.assertTrue(all(reply['setup']['done'] and 'prepared' in reply for reply in replies))
        self.assertTrue(state.read()['done'])

    def test_settings_changed_during_setup_keep_the_newer_state(self):
        shared.update({'local': {'root': str(self.root / 'work')}})
        install = self.root / 'installed-blog'
        (install / 'scripts').mkdir(parents=True)
        (install / 'scripts/start_studio.py').write_text('# fixture')
        self.during = lambda: self.write('/api/paths', {'paths': {'blog': str(install)}})
        reply, _ = self.started('/api/setup', {'done': True, 'prepare': True})
        with self.assertRaisesRegex(WorkspaceError, 'changed while the studios were being prepared'):
            reply.result(timeout=5)
        kept = state.read()
        self.assertEqual(kept['paths'], {'blog': str(install)})
        self.assertFalse(kept['done'])
        self.assertFalse(self.page.snapshot()['setup']['done'])

    def test_storage_changed_again_during_a_prepare_is_not_reported_as_done(self):
        self.write('/api/shared', {'changes': {'local': {'root': str(self.root / 'work')}}, 'seen': {}})
        self.write('/api/setup', {'done': True})
        newer = str(self.root / 'newer')
        self.during = lambda: shared.update({'local': {'root': newer}})
        reply, _ = self.started('/api/shared', {'changes': {'team': {'repository': str(self.root / 'team.git')}},
                                                'seen': shared.read()[0]})
        found = reply.result(timeout=5)
        self.assertNotIn('prepared', found)
        self.assertIn('changed while the studios were being prepared', found['prepare_problem'])
        self.assertEqual(found['shared']['local']['root'], newer)


class SnapshotCostTests(IsolatedHome):
    def test_one_snapshot_looks_each_thing_up_once_and_runs_no_process_list(self):
        shared.update({'local': {'root': str(self.root / 'work')}, 'assistant': {'agent': 'codex'}})
        self.write('/api/setup', {'done': True})
        installed = sum(row['installed'] for row in self.page.snapshot()['studios'])
        self.assertGreater(installed, 1, 'The bundled studios are found, so the cards repeat the lookups')
        from marketing_studio import launcher as launching
        with mock.patch('marketing_studio.page.runtime.assistant_default', return_value='claude') as default, \
                mock.patch('marketing_studio.page.runtime.assistant_command', return_value='/synthetic/codex') as command, \
                mock.patch('marketing_studio.page.shutil.which', return_value='/synthetic/git') as which, \
                mock.patch.object(launching, 'ps', side_effect=AssertionError('No process list')):
            found = self.page.snapshot()
        self.assertEqual(default.call_count, 1)
        self.assertEqual(command.call_count, 1)
        self.assertEqual([call.args for call in which.call_args_list], [('git',)])
        self.assertEqual(found['assistant_default'], 'claude')
        self.assertTrue(all(row['readiness']['state'] == 'done' for row in found['studios'] if row['installed']))

    def test_open_reads_the_shared_settings_once(self):
        shared.update({'local': {'root': str(self.root / 'work')}})
        self.write('/api/setup', {'done': True})
        with mock.patch('marketing_studio.page.shared.read', wraps=shared.read) as read, \
                mock.patch.object(self.launcher, 'open', return_value='http://127.0.0.1:9/#' + 'a' * 40):
            self.write('/api/open', {'studio': 'blog'})
        self.assertEqual(read.call_count, 1)
