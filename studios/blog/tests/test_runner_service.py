"""Native runner lifecycle fixtures; no network, credential, runner, or real VM."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('runner_service', REPO/'scripts/ci/runner-service.py')
service = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(service)


def policy():
    return ({'full_name': service.REPO, 'private': True}, [{'login': service.OWNER}],
            {'run_workflows_from_fork_pull_requests': False,
             'send_write_tokens_to_workflows': False, 'send_secrets_and_variables': False},
            {'default_workflow_permissions': 'read'})


class FakeProcess:
    instances = []
    def __init__(self, args, **kwargs):
        self.args = args
        self.returncode = None
        self.instances.append(self)

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.returncode = 0
        return 0

    def terminate(self):
        self.returncode = 0


class FakeService(service.Service):
    def __init__(self, state):
        super().__init__(state)
        self.calls = []
        self.requests = []
        self.commands = []
        self.payloads = []
        self.boundary = policy()
        self.vm = None
        self.fail_guest = False

    def log(self, message):
        pass

    def api(self, route, method='GET'):
        self.requests.append((route, method))
        if route.endswith('/registration-token'):
            return {'token': 'fixture-not-a-real-token', 'expires_at': 'fixture'}
        if route.endswith('/actions/runners?per_page=100'):
            return {'total_count': 2, 'runners': [{'id': 11, 'name': self.vm},
                                               {'id': 12, 'name': 'unrelated-runner'}]}
        if method == 'DELETE':
            return None
        if route.endswith('/collaborators?per_page=100'):
            return self.boundary[1]
        if route.endswith('/fork-pr-workflows-private-repos'):
            return self.boundary[2]
        if route.endswith('/permissions/workflow'):
            return self.boundary[3]
        return self.boundary[0]

    def call(self, arguments, *, data=None, timeout=120):
        self.calls.append(arguments)
        if arguments[:2] == ['tart', 'clone']:
            self.vm = arguments[-1]
        if arguments[:2] == ['tart', 'get']:
            platform = 'linux' if arguments[2].startswith('saypipe') else 'darwin'
            return json.dumps({'Running': False, 'OS': platform, 'CPU': 4,
                               'Memory': 8192 if platform == 'linux' else 4096}).encode()
        if data:
            self.payloads.append(data)
        return b''

    def artifact(self, platform):
        self.state.mkdir(parents=True, exist_ok=True)
        archive = self.state/'fixture-public-runner.tar.gz'
        archive.write_bytes(b'not an executable archive')
        return archive

    def wait_command(self, args, logfile, **kwargs):
        self.commands.append(args)
        if self.fail_guest:
            raise service.LifecycleError('fixture guest failure')


class RunnerServiceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.state = Path(self.temporary.name)/'state'
        self.runner = FakeService(self.state)
        FakeProcess.instances = []
        self.process = patch.object(service.subprocess, 'Popen', FakeProcess)
        self.process.start()
        self.addCleanup(self.process.stop)

    def test_policy_changes_fail_before_clone_or_credential_request(self):
        for index, key, value in ((0, 'private', False),
                                  (2, 'run_workflows_from_fork_pull_requests', True),
                                  (3, 'default_workflow_permissions', 'write')):
            self.runner.boundary = policy()
            self.runner.boundary[index][key] = value
            with self.assertRaises(service.LifecycleError):
                self.runner.cycle('linux')
        self.runner.boundary = policy()
        self.runner.boundary[1].append({'login': 'external'})
        with self.assertRaises(service.LifecycleError):
            self.runner.cycle('macos')
        self.assertFalse(self.runner.calls)
        self.assertFalse(any(method == 'POST' for _, method in self.runner.requests))

    def test_preparation_has_no_registration_and_only_read_only_bootstrap_mount(self):
        self.runner.cycle('linux', prepare_only=True)
        self.assertFalse(any(method != 'GET' for _, method in self.runner.requests))
        self.assertFalse(self.runner.payloads)
        self.assertTrue(any(args[:2] == ['tart', 'delete'] for args in self.runner.calls))
        self.assertEqual(len(self.runner.commands), 1)
        self.assertIn('/mnt/shared/bootstrap/runner-bootstrap.sh', self.runner.commands[0][-1])
        shares = [a for a in FakeProcess.instances[0].args if a.startswith('--dir=')]
        self.assertEqual(len(shares), 1)
        self.assertTrue(shares[0].startswith('--dir=bootstrap:'))
        self.assertTrue(shares[0].endswith(':ro'))
        self.assertIn('--no-clipboard', FakeProcess.instances[0].args)
        self.assertIn('--no-audio', FakeProcess.instances[0].args)
        record = json.loads(next((self.state/'runs').glob('*/record.json')).read_text())
        self.assertTrue(record['cleaned'])
        self.assertFalse(record['registration_started'])

    def test_token_transmitted_only_in_stdin_never_args_or_record(self):
        self.runner.cycle('macos')
        self.assertEqual(len(self.runner.payloads), 1)
        payload = json.loads(self.runner.payloads[0])
        self.assertEqual(payload['token'], 'fixture-not-a-real-token')
        self.assertNotIn('fixture-not-a-real-token', json.dumps(self.runner.calls))
        for record in (self.state/'runs').glob('*/record.json'):
            self.assertNotIn('token', record.read_text())
        deleted = [route for route, method in self.runner.requests if method == 'DELETE']
        self.assertEqual(deleted, ['repos/'+service.REPO+'/actions/runners/11'])
        self.assertIn("'--ephemeral'", service.REGISTER)
        self.assertIn('ACTIONS_RUNNER_INPUT_TOKEN=', service.REGISTER)
        self.assertIn('stdout=subprocess.DEVNULL', service.REGISTER)

    def test_guest_failure_still_deletes_its_clone_without_registration(self):
        self.runner.fail_guest = True
        with self.assertRaises(service.LifecycleError):
            self.runner.cycle('macos')
        self.assertTrue(any(args == ['tart', 'delete', self.runner.vm] for args in self.runner.calls))
        self.assertFalse(any(method == 'POST' for _, method in self.runner.requests))

    def test_invalid_or_unrelated_cleanup_record_is_rejected(self):
        for vm in ('unrelated-vm', 'blog-studio-native-../../other',
                   'blog-studio-native-linux-123'):
            with self.assertRaises(service.LifecycleError):
                self.runner.cleanup({'repository': service.REPO, 'vm': vm})
        self.assertFalse(self.runner.calls)

    def test_restart_recovers_only_recorded_owned_clones(self):
        vm = 'blog-studio-native-linux-0123456789abcdef'
        run = self.state/'runs'/vm
        run.mkdir(parents=True)
        record = {'repository': service.REPO, 'vm': vm, 'clone_created': True,
                  'registration_started': False, 'cleaned': False}
        self.runner.write_record(run, record)
        self.runner.recover()
        self.assertIn(['tart', 'delete', vm], self.runner.calls)
        self.assertTrue(json.loads((run/'record.json').read_text())['cleaned'])

    def test_busy_lookup_is_limited_to_exact_owned_runner(self):
        self.runner.vm = 'blog-studio-native-linux-0123456789abcdef'
        self.assertFalse(self.runner.runner_is_busy(self.runner.vm))
        with self.assertRaises(service.LifecycleError):
            self.runner.runner_is_busy('unrelated-runner')

    def test_retired_archives_are_removed_but_unfinished_records_preserved(self):
        self.runner.cycle('linux', prepare_only=True)
        run = next((self.state/'runs').iterdir())
        self.assertFalse((run/'bootstrap').exists())
        self.assertTrue((run/'record.json').exists())
        unfinished = self.state/'runs'/'blog-studio-native-linux-0123456789abcdef'
        unfinished.mkdir()
        self.runner.write_record(unfinished, {'repository': service.REPO,
            'vm': unfinished.name, 'platform': 'linux', 'cleaned': False})
        self.runner.prune_logs()
        self.assertTrue(unfinished.exists())


if __name__ == '__main__':
    unittest.main()
