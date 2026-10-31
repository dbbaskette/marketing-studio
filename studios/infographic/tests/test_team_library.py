"""Team library first use: an unset repository is a setup state, not a validation error.

Every repository here is a disposable local bare remote; nothing reaches a network host.
"""
import json
import subprocess
from unittest import mock

from helpers import NATIVE, Isolated
from runner import team
from runner.contracts import Invalid


def git(*args):
    return subprocess.run(['git', *args], capture_output=True, check=True, text=True).stdout.strip()


class TeamLibrarySetupTests(Isolated):
    def write_settings(self, team_value=None):
        values = {'schema': 1, 'person': {'name': 'Synthetic owner'}, 'local': {'root': str(self.temp / 'work')},
                  'output': 'pdf'}
        if team_value is not None:
            values['team'] = team_value
        self.settings.write_text(json.dumps(values))
        return self.settings.read_bytes()

    def remote(self):
        remote, seed = self.temp / 'team.git', self.temp / 'seed'
        seed.mkdir()
        git('init', '--bare', '--initial-branch=main', str(remote))
        git('-C', str(seed), 'init', '--initial-branch=main')
        (seed / 'README.md').write_text('Synthetic team repository.')
        git('-C', str(seed), 'add', 'README.md')
        git('-C', str(seed), '-c', 'user.name=Synthetic', '-c', 'user.email=s@example.invalid',
            'commit', '-q', '-m', 'Synthetic seed')
        git('-C', str(seed), 'push', '-q', str(remote), 'main')
        return remote

    def test_unset_repository_reads_as_setup_without_a_validation_error_or_any_git(self):
        for value in (None, {}, {'repository': None, 'branch': 'main'}, {'repository': ''}):
            with self.subTest(team=value):
                before = self.write_settings(value)
                with mock.patch.object(team.subprocess, 'run', side_effect=AssertionError('No Git')):
                    state = team.status()
                self.assertEqual(state, {'configured': False, 'repository': None, 'branch': None, 'problem': None,
                                         'connected': False, 'items': [], 'synced_at': None, 'pending': 0})
                self.assertEqual(self.settings.read_bytes(), before)
        with self.assertRaisesRegex(Invalid, 'Configure a shared repository in shared settings'):
            team.connect()

    def test_a_malformed_setting_names_its_recovery_without_echoing_credentials(self):
        for repository in ('https://person:private-token@example.invalid/team.git', 'not a repository',
                           str(self.temp / 'missing-folder')):
            with self.subTest(repository=repository):
                self.write_settings({'repository': repository, 'branch': 'main'})
                state = team.status()
                self.assertFalse(state['configured'])
                self.assertIn('shared settings', state['problem'])
                self.assertNotIn('private-token', json.dumps(state))
                with self.assertRaises(Invalid) as raised:
                    team.connect()
                self.assertNotIn('private-token', str(raised.exception))

    def test_configured_repository_shows_its_state_and_connecting_shares_nothing(self):
        remote = self.remote()
        before = self.write_settings({'repository': str(remote), 'branch': 'main'})
        waiting = team.status()
        self.assertEqual((waiting['configured'], waiting['connected'], waiting['repository'], waiting['branch']),
                         (True, False, str(remote), 'main'))
        remote_head = git('--git-dir', str(remote), 'rev-parse', 'main')
        connected = team.connect()
        self.assertEqual((connected['connected'], connected['pending'], connected['items']), (True, 0, []))
        self.assertIsNotNone(connected['synced_at'])
        self.assertEqual(git('--git-dir', str(remote), 'rev-parse', 'main'), remote_head, 'Connecting pushes nothing.')
        self.assertEqual(self.settings.read_bytes(), before, 'Shared settings are only read.')

    def test_a_failed_first_connection_can_be_retried_and_offline_keeps_the_last_copy(self):
        missing = self.temp / 'not-yet-a-repository'
        missing.mkdir()
        self.write_settings({'repository': str(missing), 'branch': 'main'})
        with self.assertRaisesRegex(Invalid, 'not found'):
            team.connect()
        retry = team.status()
        self.assertEqual((retry['configured'], retry['connected'], retry['head']), (True, False, None))
        missing.rmdir()
        self.remote().rename(missing)
        self.assertTrue(team.connect()['connected'])
        # Offline: reading still lists the last synced copy; syncing reports a recovery step.
        missing.rename(self.temp / 'away')
        missing.mkdir()
        offline = team.status()
        self.assertTrue(offline['connected'])
        with self.assertRaisesRegex(Invalid, 'Retry connection|not found'):
            team.connect()
        self.assertTrue(team.status()['connected'])

    def test_git_diagnostics_choose_a_recovery_and_are_never_echoed(self):
        remote = self.remote()
        self.write_settings({'repository': str(remote), 'branch': 'main'})
        folder = self.temp / 'clone'
        folder.mkdir()
        cases = {
            "fatal: Authentication failed for 'https://person:private-token@example.invalid/'": 'refused access',
            'git@example.invalid: Permission denied (publickey).': 'refused access',
            'fatal: could not read Username: terminal prompts disabled': 'refused access',
            "remote: Repository not found.\nfatal: repository 'https://example.invalid/x' not found": 'not found',
            "fatal: couldn't find remote ref main": 'not found',
            "fatal: unable to access 'https://example.invalid/': Could not resolve host: example.invalid": 'could not be reached',
            'ssh: connect to host example.invalid port 22: Connection refused': 'could not be reached',
            'error: something unexpected private-token': 'Team Git could not finish',
        }
        real = subprocess.run
        for stderr, words in cases.items():
            with self.subTest(stderr=stderr):
                def run(command, **options):
                    if 'fetch' in command:
                        return subprocess.CompletedProcess(command, 128, b'', stderr.encode())
                    return real(command, **options)
                with mock.patch.object(team.subprocess, 'run', side_effect=run):
                    with self.assertRaises(Invalid) as raised:
                        team.git(folder, 'fetch', '--no-tags', 'origin', 'main')
                self.assertIn(words, str(raised.exception))
                self.assertNotIn('private-token', str(raised.exception))
                self.assertNotIn('example.invalid', str(raised.exception))
        with mock.patch.object(team.subprocess, 'run', side_effect=subprocess.TimeoutExpired('git', 60)):
            with self.assertRaisesRegex(Invalid, 'could not be reached'):
                team.git(folder, 'push', 'origin', 'HEAD:refs/heads/main')
        # Local Git failures never claim a network or sign-in cause.
        with self.assertRaisesRegex(Invalid, 'Team Git could not finish'):
            team.git(folder, 'add', '--', 'no-such-file')


class TeamLibraryPageTests(Isolated):
    def test_the_page_reads_an_unset_repository_as_a_setup_state(self):
        import http.client
        from runner import server
        from runner.workspace import Store
        self.settings.write_text(json.dumps({'schema': 1, 'local': {'root': str(self.temp / 'work')}}))
        desk = server.desk(Store.setup(self.workspace))
        desk.start()
        self.addCleanup(desk.stop)
        connection = http.client.HTTPConnection('127.0.0.1', desk.port, timeout=5)
        self.addCleanup(connection.close)
        connection.request('GET', '/api/team', headers={'Host': f'127.0.0.1:{desk.port}',
                                                        'X-Infographic-Studio-Token': desk.token})
        response = connection.getresponse()
        state = json.loads(response.read())
        self.assertEqual(response.status, 200)
        self.assertEqual((state['configured'], state['connected'], state['problem']), (False, False, None))
        self.assertNotIn('Give a repository address', json.dumps(state))
        script = (NATIVE / 'runner/web/app.js').read_text()
        # The sheet offers the shared settings part that owns the repository, and returns here.
        self.assertIn("sharedSettingsLink('Configure shared repository','workspace-part')", script)
        self.assertIn("'infographic-studio-return'", script)
