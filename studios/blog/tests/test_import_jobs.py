"""Slow imports and Google calls as background jobs (import_jobs.py, #516).

Each request is sent to the real page handler, which answers at once with a job; the job is
followed with GET tool-job until it ends, and its answer is compared with what the route
answers when it is called directly. Google is faked, as in the other Google tests; links are
read by a stand-in reader. No assistant, provider or network is used.
"""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import json
import threading
import time
from unittest.mock import patch

import blog_library as library
import import_jobs
import management
import studio
import tool_jobs
from test_blog_runner import RunnerCase
import test_team_library as team
from test_team_library import SITE, encoded_file
from test_voice_links import Pages, page

PORT = 54321


class JobCase(RunnerCase):
    Docs = team.AddTests.Docs  # The Google Docs stand-in the library add tests use.

    def setUp(self):
        super().setUp()
        self.server, url = management.server(self.root, port=PORT, bind=False)
        self.addCleanup(self.server.server_close)
        self.token = url.split('#')[1]

    def call(self, path, data=None):
        body = json.dumps(data).encode() if data is not None else None
        headers = {'Host': '127.0.0.1:%d' % PORT, 'X-Blog-Studio-Token': self.token}
        if body is not None:
            headers.update({'Content-Type': 'application/json', 'Content-Length': str(len(body))})
        status, _, reply, _ = self.server.desk.answer(
            path, headers, 'POST' if body is not None else 'GET', body
        )
        return status, json.loads(reply)

    def follow(self, job, seconds=20):
        ends = time.monotonic() + seconds
        while job['status'] == 'working':
            self.assertLess(time.monotonic(), ends, 'the job never ended')
            time.sleep(0.02)
            status, job = self.call('/api/tool-job?job=' + job['id'])
            self.assertEqual(status, 200)
        return job

    def started(self, route, data):
        status, answer = self.call('/api/' + route, data)
        self.assertEqual(status, 200, answer)
        self.assertTrue(answer['background'])
        self.assertEqual(answer['job']['status'], 'working')
        self.assertEqual(answer['job']['route'], route)
        return answer['job']

    def patched(self, reader=None):
        """The same stand-ins AddTests.add uses, held while a job runs on its own thread."""
        import google_intake

        stack = [
            patch.object(library, 'fetch', reader or Pages({})),
            patch.object(google_intake.drive, 'Client', self.Docs),
            patch.object(library.time, 'sleep', lambda seconds: None),
        ]
        for one in stack:
            one.start()
            self.addCleanup(one.stop)


class LibraryAddJobTests(JobCase):
    def request(self, links):
        return {
            'files': [encoded_file('facts.md', b'The gateway retries twice.')],
            'links': '\n'.join(links) + '\n',
            'role': 'facts',
            'author': 'Avery Quinn',
            'kind': '',
        }

    def test_preview_and_add_return_a_job_and_the_same_answer(self):
        links = [SITE + name + '/' for name in ('one', 'two', 'three', 'four', 'five')]
        reader = Pages({link: page(link[-4:-1], 'Jordan Lee') for link in links})
        self.patched(reader)
        request = self.request(links)
        direct = management.dispatch(self.root, 'library-add-preview', request)  # Saves nothing.
        shown = self.follow(self.started('library-add-preview', request))
        self.assertEqual(shown['status'], 'ready')
        self.assertEqual(shown['result'], direct)
        # More links than one batch: one request, and the job fetches every batch itself.
        with patch.object(library, 'MAX_BATCH', 2):
            data = {**request, 'operation': 'a' * 32, 'expected': direct['expected']}
            added = self.follow(self.started('library-add', data))
        self.assertEqual(added['status'], 'ready', added)
        result = added['result']
        self.assertEqual((result['state'], result['remaining']), ('saved', 0))
        self.assertEqual(result['counts']['imported'], 6)
        self.assertEqual(len(reader.calls), 5, 'each link is fetched once')
        # Called directly again with the same operation, the route answers as the job did.
        again = management.dispatch(self.root, 'library-add', data)
        self.assertEqual(
            [(row['status'], row.get('id')) for row in again['items']],
            [(row['status'], row.get('id')) for row in result['items']],
        )

    def test_a_refusal_keeps_its_status_and_words(self):
        self.patched()
        request = {**self.request([SITE + 'one/']), 'operation': 'b' * 32, 'expected': 'stale'}
        try:
            management.dispatch(self.root, 'library-add', request)
        except ValueError as error:
            words = str(error)
        failed = self.follow(self.started('library-add', request))
        self.assertEqual(failed['status'], 'failed')
        self.assertEqual((failed['error'], failed['error_status']), (words, 400))
        self.assertEqual(failed['error_reply'], {'error': words})

    def test_the_job_is_read_while_another_command_holds_the_workspace(self):
        job = import_jobs.start(
            self.root, 'library-add-preview', {}, runner=lambda root, route, data: {'ok': 1}
        )['job']
        with studio.locked(self.root):
            status, found = self.call('/api/tool-job?job=' + job['id'])
        self.assertEqual(status, 200)
        self.assertIn(found['status'], ('working', 'ready'))
        self.assertNotIn('data', found)
        # An import is not a tool task to resume on a blog's page.
        self.assertEqual(tool_jobs.listing(self.root, None), [])


class GoogleJobTests(JobCase):
    """Each Google route the phone link gave ten minutes now answers at once with a job."""

    ROUTES = (
        'google-preview',
        'google-start',
        'desk-google-plan',
        'desk-google-compare',
        'desk-google-send',
        'editor-google-send',
        'desk-google-take',
    )

    def test_every_google_route_runs_as_a_job_with_the_routes_own_answer(self):
        seen = []

        def route(root, name, data):
            seen.append((name, data, threading.current_thread() is threading.main_thread()))
            if name == 'desk-google-take':
                raise management.CurationConflict('The desk changed. Check again.')
            return {'route': name, 'echo': data}

        with patch.object(management, 'dispatch', route):
            for name in self.ROUTES:
                job = self.follow(self.started(name, {'id': 'blog-1', 'n': len(seen)}))
                if name == 'desk-google-take':
                    self.assertEqual(job['status'], 'failed')
                    self.assertEqual(
                        (job['error'], job['error_status'], job['error_reply']['code']),
                        ('The desk changed. Check again.', 409, 'source-conflict'),
                    )
                    continue
                self.assertEqual(job['status'], 'ready', job)
                self.assertEqual(job['result'], {'route': name, 'echo': seen[-1][1]})
        self.assertEqual([name for name, _, _ in seen], list(self.ROUTES))
        self.assertFalse(any(main for _, _, main in seen), 'none ran on the request')

    def test_google_preview_through_the_real_route(self):
        import google_intake

        value = {'status': 'preview', 'preview': 'p' * 32, 'title': 'A Doc', 'content': 'Text.'}
        with patch.object(google_intake, 'preview', lambda root, data: dict(value, asked=data)):
            direct = management.dispatch(self.root, 'google-preview', {'url': 'u'})
            job = self.follow(self.started('google-preview', {'url': 'u'}))
        self.assertEqual(job['result'], direct)


class StopTests(JobCase):
    def test_a_read_that_saves_nothing_stops_at_once_and_its_answer_is_dropped(self):
        release = threading.Event()

        def slow(root, route, data):
            release.wait(10)
            return {'late': True}

        job = import_jobs.start(self.root, 'desk-google-compare', {'id': 'x'}, runner=slow)['job']
        self.assertTrue(job['stoppable'])
        status, stopped = self.call('/api/import-stop', {'job': job['id']})
        self.assertEqual((status, stopped['status']), (200, 'cancelled'))
        self.assertEqual(stopped['error'], import_jobs.STOPPED)
        release.set()
        for _ in range(200):
            if not import_jobs.running(job['id']):
                break
            time.sleep(0.01)
        found = import_jobs.view(self.root, job['id'])
        self.assertEqual((found['status'], found['result']), ('cancelled', None))

    def test_a_send_cannot_be_stopped_part_way(self):
        release = threading.Event()
        job = import_jobs.start(
            self.root, 'desk-google-send', {}, runner=lambda *a: release.wait(10) and {'sent': 1}
        )['job']
        self.assertFalse(job['stoppable'])
        status, answer = self.call('/api/import-stop', {'job': job['id']})
        self.assertEqual(status, 400)
        self.assertIn('cannot be stopped part way', answer['error'])
        release.set()
        self.assertEqual(self.follow(job)['result'], {'sent': 1})

    def test_adding_links_stops_after_the_batch_under_way_and_keeps_what_it_added(self):
        calls, gate = [], threading.Event()

        def add(root, route, data):
            calls.append(dict(data))
            if len(calls) == 2:
                gate.wait(10)  # The second batch is being fetched when Stop comes.
            left = max(0, 3 - len(calls))
            return {'items': [{}, {}, {}], 'remaining': left, 'state': 'importing'}

        job = import_jobs.start(
            self.root, 'library-add', {'operation': 'c' * 32, 'retry': True}, runner=add
        )['job']
        for _ in range(500):
            if len(calls) == 2:
                break
            time.sleep(0.01)
        stopping = import_jobs.stop(self.root, job['id'])
        self.assertEqual((stopping['status'], stopping['stopping']), ('working', True))
        gate.set()
        done = self.follow(job)
        self.assertEqual(done['status'], 'ready')
        self.assertTrue(done['result']['stopped'])
        self.assertEqual(done['result']['remaining'], 1)
        self.assertEqual(len(calls), 2, 'no batch is fetched after Stop')
        self.assertTrue(calls[0]['retry'])
        self.assertNotIn('retry', calls[1], 'only the first call retries failed links')

    def test_an_interrupted_job_is_said_to_be_so_and_a_running_one_is_left(self):
        release = threading.Event()
        running = import_jobs.start(
            self.root, 'google-preview', {}, runner=lambda *a: release.wait(10) and {'x': 1}
        )['job']
        orphan = {**running, 'id': 'd' * 32, 'route': 'google-preview', 'status': 'working'}
        tool_jobs.write(self.root, {**orphan, 'metadata': {'article': None}})
        tool_jobs.recover(self.root)
        self.assertEqual(import_jobs.view(self.root, 'd' * 32)['status'], 'failed')
        self.assertEqual(import_jobs.view(self.root, running['id'])['status'], 'working')
        release.set()
        self.assertEqual(self.follow(running)['status'], 'ready')
