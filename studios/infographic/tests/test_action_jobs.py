"""Long actions run as background jobs: start, progress, Stop, restart and one at a time."""
import json
from pathlib import Path
import os
import sys
import threading
import time
from unittest import mock

from helpers import Isolated
from runner import action_jobs, api, server, sources
from runner.activity import Activity
from runner.author import Author
from runner.engine import Engine
from runner.images.codex import execute
from runner.workspace import Store


def wait(predicate, seconds=10):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(.02)
    raise AssertionError('The background action did not reach the expected state.')


class ActionJobTests(Isolated):
    def setUp(self):
        super().setUp()
        self.store = Store.setup(self.workspace)
        project = self.store.create('Synthetic background work')
        project = sources.capture(self.store, project['id'], b'Synthetic notes: restart one instance at a time.',
                                  kind='text', name='Synthetic notes', expected_revision=project['revision'])
        self.ident = project['id']
        self.revision = project['revision']

    def page(self, engine):
        page = server.Page(8000, self.store, engine)
        self.addCleanup(page.actions.shutdown)
        return page

    def ended(self, page):
        return wait(lambda: (lambda shown: shown if shown and shown['state'] != 'running' else None)(page.doing(self.ident)))

    def test_start_returns_at_once_shows_progress_and_runs_one_at_a_time(self):
        entered, release = threading.Event(), threading.Event()
        calls = []

        def slow(found, sent):
            calls.append(sent['action'])
            found.progress('Reading sources and finding the story')
            entered.set()
            release.wait(5)
            found.progress('Checking the proposed facts and story')
            return {'saved': True}
        page = self.page(Engine(self.store))
        sent = {'action': 'suggest', 'id': self.ident, 'expected_revision': self.revision}
        with mock.patch.object(api, 'action', side_effect=slow):
            started = time.monotonic()
            status, _, raw = page.write('/api/action', sent)
            self.assertLess(time.monotonic() - started, 2, 'The request is answered before the work ends.')
            self.assertEqual(status, 202)
            job = json.loads(raw)['job']
            self.assertEqual((job['state'], job['action'], job['stoppable']), ('running', 'suggest', True))
            self.assertTrue(entered.wait(3))
            self.assertEqual(page.doing(self.ident)['label'], 'Reading sources and finding the story')
            # One at a time per infographic: a second long action is refused while one runs.
            with self.assertRaisesRegex(Exception, 'still working'):
                page.write('/api/action', {'action': 'build', 'id': self.ident,
                                           'expected_revision': self.revision, 'request_id': 'second-build'})
            saved = json.loads((self.store.root / '.action-runs' / (self.ident + '.json')).read_text())
            self.assertEqual((saved['state'], saved['action']), ('running', 'suggest'))
            release.set()
            shown = self.ended(page)
        self.assertEqual(calls, ['suggest'])
        self.assertEqual((shown['state'], shown['result']), ('complete', {'saved': True}))
        saved = json.loads((self.store.root / '.action-runs' / (self.ident + '.json')).read_text())
        self.assertEqual(saved['state'], 'complete')

    def test_an_outdated_revision_is_refused_before_anything_starts(self):
        page = self.page(Engine(self.store))
        with mock.patch.object(api, 'action') as action:
            with self.assertRaisesRegex(Exception, 'changed'):
                page.write('/api/action', {'action': 'suggest', 'id': self.ident, 'expected_revision': 0})
            action.assert_not_called()
        self.assertIsNone(page.doing(self.ident))

    def test_ordering_checks_still_run_inside_the_job(self):
        # A build without a chosen story is refused by the engine, as before, and says so.
        page = self.page(Engine(self.store, executable=sys.executable))
        status, _, _ = page.write('/api/action', {'action': 'build', 'id': self.ident,
                                                   'expected_revision': self.revision, 'request_id': 'build-one'})
        self.assertEqual(status, 202)
        shown = self.ended(page)
        self.assertEqual(shown['state'], 'failed')
        self.assertEqual(shown['problem'], 'Compose the page could not finish. Completed work is kept.')
        self.assertEqual(shown['recovery']['step'], 'composition')
        self.assertEqual(self.store.read(self.ident)['revision'], self.revision)

    def test_stop_ends_the_assistant_child_process_and_the_job(self):
        marker = self.temp / 'child.pid'
        child = ('import os, sys, time\n'
                 'open(sys.argv[1], "w").write(str(os.getpid()))\n'
                 'time.sleep(60)\n')

        def run(command, prompt, folder, seconds, stop=None, watch=None):
            return execute([sys.executable, '-c', child, str(marker)], prompt, folder, seconds, stop=stop)
        engine = Engine(self.store, assistant=Author({'agent': 'codex'}, run=run))
        page = self.page(engine)
        status, _, _ = page.write('/api/action', {'action': 'suggest', 'id': self.ident,
                                                   'expected_revision': self.revision})
        self.assertEqual(status, 202)
        pid = int(wait(lambda: marker.exists() and marker.read_text()))
        os.kill(pid, 0)     # the assistant's process is running
        status, _, raw = page.write('/api/action-control', {'id': self.ident, 'action': 'stop'})
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(raw)['stopping'])
        shown = self.ended(page)
        self.assertEqual(shown['state'], 'stopped')
        self.assertIn('Stopped on request', shown['problem'])
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)
        saved = json.loads((self.store.root / '.action-runs' / (self.ident + '.json')).read_text())
        self.assertEqual(saved['state'], 'stopped')
        self.assertEqual(self.store.read(self.ident)['revision'], self.revision, 'Nothing was saved.')
        with self.assertRaisesRegex(Exception, 'Nothing is running'):
            page.write('/api/action-control', {'id': self.ident, 'action': 'stop'})

    def test_stop_cancels_a_pending_image_request_so_no_late_result_lands(self):
        engine = Engine(self.store)
        page = self.page(engine)
        cancelled = []
        entered, release = threading.Event(), threading.Event()

        def slow(found, sent):
            entered.set()
            release.wait(5)
            found.progress('Placing the artwork')     # the next step ends a stopped job
            return {'state': 'complete'}
        with mock.patch.object(api, 'action', side_effect=slow), \
                mock.patch('runner.image_jobs.Jobs.recovery', return_value=[{'attempt_id': 'image-one', 'state': 'running'}]), \
                mock.patch('runner.image_jobs.Jobs.cancel', side_effect=lambda *a, **k: cancelled.append(a[1])):
            page.write('/api/action', {'action': 'image-start', 'id': self.ident, 'expected_revision': self.revision,
                                       'brief_id': 'b1', 'provider': 'codex', 'request_id': 'image-one'})
            self.assertTrue(entered.wait(3))
            page.write('/api/action-control', {'id': self.ident, 'action': 'stop'})
            self.assertTrue(page.doing(self.ident)['stopping'])
            self.assertEqual(cancelled, ['image-one'])
            release.set()
            shown = self.ended(page)
        self.assertEqual(shown['state'], 'stopped')
        self.assertNotIn('result', shown)

    def test_a_restart_shows_interrupted_work_and_what_to_do_next(self):
        entered, release = threading.Event(), threading.Event()

        def slow(found, sent):
            entered.set()
            release.wait(5)
            return {}
        page = self.page(Engine(self.store))
        with mock.patch.object(api, 'action', side_effect=slow):
            page.write('/api/action', {'action': 'build', 'id': self.ident, 'expected_revision': self.revision,
                                       'request_id': 'build-two'})
            self.assertTrue(entered.wait(3))
            # A new server (a restart) has no memory of the running job, only its record.
            later = server.Page(8001, self.store, Engine(self.store))
            shown = later.doing(self.ident)
            self.assertEqual(shown['state'], 'interrupted')
            self.assertNotEqual(shown['state'], 'running')
            self.assertFalse(shown['stoppable'])
            self.assertIn('Building the page was interrupted', shown['problem'])
            self.assertIn('Build the page again', shown['next'])
            listed = json.loads(later.read('/api/projects', lambda name: None)[2])['projects']
            self.assertEqual(listed[0]['activity']['state'], 'interrupted')
            # A new long action may start; reading the notice repeats nothing.
            status, _, raw = later.write('/api/action-control', {'id': self.ident, 'action': 'dismiss'})
            self.assertEqual(status, 200)
            self.assertIsNone(later.doing(self.ident))
            release.set()
            self.ended(page)

    def test_shutdown_stops_running_jobs(self):
        actions = action_jobs.Actions(self.store, Activity())
        entered = threading.Event()

        def waits(found, sent):
            entered.set()
            while True:
                found.progress('Still working')
                time.sleep(.01)
        actions.start({'action': 'suggest', 'id': self.ident, 'expected_revision': self.revision},
                      lambda: Engine(self.store), waits)
        self.assertTrue(entered.wait(3))
        actions.shutdown()
        self.assertEqual(actions.running(), [])
        self.assertEqual(actions.activity.snapshot(self.ident)['state'], 'stopped')

    def test_a_stop_that_lands_before_a_save_saves_nothing_and_ends_stopped(self):
        page = self.page(Engine(self.store))
        before = self.store.read(self.ident)

        def answered_then_saves(found, sent):
            found.progress('Reading sources and finding the story')
            # The assistant has answered; Stop lands before its work is saved.
            page.actions.stop(self.ident)
            current = self.store.read(self.ident)
            self.store.update(self.ident, {'brief': {**current['brief'], 'audience': 'Late save'}},
                              expected_revision=current['revision'])
            return {'saved': True}
        with mock.patch.object(api, 'action', side_effect=answered_then_saves):
            page.write('/api/action', {'action': 'suggest', 'id': self.ident, 'expected_revision': self.revision})
            shown = self.ended(page)
        self.assertEqual(shown['state'], 'stopped')
        self.assertEqual(self.store.read(self.ident), before, 'Nothing was saved after Stop.')

    def test_a_page_drawn_anyway_does_not_swallow_stop(self):
        from runner.contracts import Stopped
        engine = Engine(self.store)
        with mock.patch.object(engine, 'preview', side_effect=Stopped()), \
                mock.patch.object(self.store, 'read', return_value={**self.store.read(self.ident), 'scene': {}}):
            with self.assertRaises(Stopped):
                engine._drawn_anyway(self.ident, {'state': 'failed'})

    def test_approval_review_export_and_delivery_run_in_the_background_without_stop(self):
        entered, release = threading.Event(), threading.Event()

        def slow(found, sent):
            found.progress('Approving this exact revision')
            entered.set()
            release.wait(5)
            return {'approved': True}
        page = self.page(Engine(self.store))
        self.assertEqual(set(action_jobs.BACKGROUND) - set(action_jobs.STOPPABLE),
                         {'approve', 'review', 'export', 'google-deliver'})
        with mock.patch.object(api, 'action', side_effect=slow):
            status, _, raw = page.write('/api/action', {'action': 'approve', 'id': self.ident,
                                                       'expected_revision': self.revision, 'then_export': True})
            self.assertEqual(status, 202)
            self.assertTrue(entered.wait(3))
            shown = page.doing(self.ident)
            self.assertEqual((shown['state'], shown['stoppable'], shown['label']),
                             ('running', False, 'Approving this exact revision'))
            with self.assertRaisesRegex(Exception, 'finishes once started'):
                page.write('/api/action-control', {'id': self.ident, 'action': 'stop'})
            # The one slot holds: nothing else, the conversation included, saves meanwhile.
            with self.assertRaisesRegex(Exception, 'still working'):
                page.write('/api/desk-submit', {'id': self.ident, 'kind': 'facts', 'target': 'facts',
                                                'expected_basis': 'x', 'payload': {'facts': []}})
            release.set()
            self.assertEqual(self.ended(page)['result'], {'approved': True})
            # A delivery request names its own saved revision: it is not refused for being older.
            release.clear()
            status, _, _ = page.write('/api/action', {'action': 'google-deliver', 'id': self.ident,
                                                     'expected_revision': 0, 'export_id': 'e_x', 'request_id': 'r1'})
            self.assertEqual(status, 202)
            release.set()
            self.ended(page)

    def test_home_lists_activity_without_results(self):
        page = self.page(Engine(self.store))
        with mock.patch.object(api, 'action', return_value={'large': 'x' * 1000}):
            page.write('/api/action', {'action': 'suggest', 'id': self.ident, 'expected_revision': self.revision})
            self.ended(page)
        self.assertIn('result', page.doing(self.ident))
        listed = json.loads(page.read('/api/projects', lambda name: None)[2])['projects']
        self.assertEqual(listed[0]['activity']['state'], 'complete')
        self.assertNotIn('result', listed[0]['activity'])
        one = json.loads(page.read('/api/activity', lambda name: self.ident)[2])['activity']
        self.assertEqual(one['result'], {'large': 'x' * 1000})

    def test_without_setup_control_is_refused_in_words(self):
        page = server.Page(8002, None)
        with self.assertRaisesRegex(Exception, 'Finish shared setup'):
            page.write('/api/action-control', {'id': self.ident, 'action': 'stop'})

    def test_the_page_sizes_come_from_the_one_table_and_say_what_they_suit(self):
        from runner.contracts import PRESETS
        page = self.page(Engine(self.store))
        sizes = json.loads(page.read('/api/status', lambda name: None)[2])['sizes']
        self.assertEqual([s['id'] for s in sizes], list(PRESETS))
        social = next(s for s in sizes if s['id'] == 'social')
        self.assertEqual((social['label'], social['detail'], social['landscape']), ('Social landscape', '1200 × 628 px', True))
        self.assertIn('one or two short blocks', social['suits'])
        script = (Path(__file__).resolve().parents[1] / 'runner/web/app.js').read_text()
        self.assertNotIn('1920 × 1080', script, 'The page names no size of its own.')
        self.assertIn("request('/api/status')", script)
