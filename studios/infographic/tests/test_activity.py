import contextlib
import http.client
import json
import threading
import unittest
from unittest import mock

from helpers import Isolated
from runner.activity import Activity
from runner.contracts import Invalid
from runner import api, server
from runner.workspace import Store


class ActivityTests(unittest.TestCase):
    def test_real_stages_elapsed_and_terminal_outcomes_without_content(self):
        clock = [10.0]
        activity = Activity(clock=lambda: clock[0])
        with activity.track('project1', 'build') as report:
            clock[0] = 14.9
            report('Rendering and checking the page')
            current = activity.snapshot('project1')
            self.assertEqual(current['state'], 'running')
            self.assertEqual(current['elapsed_seconds'], 4)
            self.assertEqual(current['label'], 'Rendering and checking the page')
            with self.assertRaises(Invalid):
                with activity.track('project1', 'build'):
                    self.fail('A duplicate operation must not start.')
        clock[0] = 30
        self.assertEqual(activity.snapshot('project1')['elapsed_seconds'], 4)
        self.assertEqual(activity.snapshot('project1')['state'], 'complete')
        with self.assertRaisesRegex(RuntimeError, 'private failure'):
            with activity.track('project1', 'suggest'):
                raise RuntimeError('private failure')
        self.assertEqual(activity.snapshot('project1')['state'], 'failed')
        self.assertNotIn('private failure', json.dumps(activity.snapshot('project1')))
        self.assertIsNone(activity.snapshot('unknown'))
        with activity.track('project1', 'image-start'):
            activity.outcome('project1', {'state': 'unknown'})
        self.assertEqual(activity.snapshot('project1')['state'], 'unknown')

    def test_terminal_notices_are_bounded_and_do_not_evict_running_work(self):
        activity = Activity()
        with activity.track('active', 'build'):
            for index in range(110):
                with activity.track(str(index), 'suggest'):
                    pass
            self.assertLessEqual(len(activity.items), 100)
            self.assertEqual(activity.snapshot('active')['state'], 'running')


class ActivityServerTests(Isolated):
    def test_authenticated_polling_observes_one_operation_and_its_saved_outcome(self):
        store = Store.setup(self.workspace)
        project = store.create('Synthetic progress')
        desk = server.desk(store, engine=api.Engine(store))
        desk.start()
        self.addCleanup(desk.stop)
        entered, release = threading.Event(), threading.Event()
        calls = []

        def action(found, sent):
            calls.append(sent['action'])
            found.progress('Reading supplied information')
            entered.set()
            if not release.wait(5):
                raise RuntimeError('Synthetic operation was not released.')
            return {'saved': True}

        def request(method, path, body=None, token=True):
            with contextlib.closing(http.client.HTTPConnection('127.0.0.1', desk.port, timeout=8)) as client:
                headers = {'Origin': f'http://127.0.0.1:{desk.port}', 'Content-Type': 'application/json'}
                if token:
                    headers['X-Infographic-Studio-Token'] = desk.token
                client.request(method, path, body=json.dumps(body) if body is not None else None, headers=headers)
                response = client.getresponse()
                return response.status, json.loads(response.read())

        sent = {'action': 'suggest', 'id': project['id'], 'expected_revision': 0}
        route = '/api/activity?id=' + project['id']
        result = []
        with mock.patch.object(api, 'action', side_effect=action):
            caller = threading.Thread(target=lambda: result.append(request('POST', '/api/action', sent)))
            caller.start()
            try:
                self.assertTrue(entered.wait(3))
                self.assertEqual(request('GET', route, token=False)[0], 403)
                status, observed = request('GET', route)
                self.assertEqual(status, 200)
                self.assertEqual(observed['activity']['state'], 'running')
                self.assertEqual(observed['activity']['label'], 'Reading supplied information')
                self.assertEqual(request('POST', '/api/action', sent)[0], 409)
                self.assertEqual(calls, ['suggest'])
                desk_value = request('GET', '/api/desk?id=' + project['id'])[1]
                self.assertEqual(desk_value['activity']['id'], observed['activity']['id'])
            finally:
                release.set()
                caller.join(5)
            self.assertEqual(result, [(200, {'result': {'saved': True}})])
            self.assertEqual(request('GET', route)[1]['activity']['state'], 'complete')
        with mock.patch.object(api, 'action', side_effect=RuntimeError('private provider detail')):
            status, failed = request('POST', '/api/action', sent)
            self.assertEqual(status, 409)
            self.assertNotIn('private provider detail', json.dumps(failed))
            self.assertEqual(request('GET', route)[1]['activity']['state'], 'failed')
        self.assertEqual(request('GET', '/api/activity?id=..%2Fprivate')[0], 409)
