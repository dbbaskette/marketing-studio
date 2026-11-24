"""Rebrand a Google file from the Brands screen (GitHub issue #516).

Harness Brand is the stand-in in tests/brand_stand_in, copied into a disposable folder for
each test: its `rebrand status` and `rebrand run` are made up and reach no Google service and
no assistant. Every setting, brands folder and record is disposable too (BrandsCase).
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from unittest import mock

from test_brands import BrandsCase, brand_pack
from marketing_studio import brand_rebrand
from marketing_studio.errors import WorkspaceError

ROOT = Path(__file__).resolve().parents[1]
SLIDES = 'https://docs.google.com/presentation/d/1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789/edit#slide=id.p'
CANONICAL = 'https://docs.google.com/presentation/d/1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789/edit'


class Rebrand(BrandsCase):
    def setUp(self):
        super().setUp()
        # The fake brand skill, in a folder of this test's own.
        fake = self.root / 'fake-skill'
        shutil.copytree(ROOT / 'tests/brand_stand_in', fake)
        patcher = mock.patch.dict(os.environ, {'BRAND_SKILL_RUNTIME': str(fake / 'harness-brand'),
                                               'STAND_IN_REBRAND_PAUSE': '0.05'})
        patcher.start()
        self.addCleanup(patcher.stop)
        brand_pack(self.brands, 'example')
        brand_pack(self.brands, 'plain')
        profile = self.brands / 'example' / 'rebrand'
        profile.mkdir()
        (profile / 'manifest.json').write_text('{"schema": 1, "brand": "example", "files": {}}')
        self.addCleanup(self.stop_any)

    def stop_any(self):
        brand_rebrand.stop()
        brand_rebrand.wait(20)

    def runs(self):
        lines = self.calls.read_text().splitlines() if self.calls.exists() else []
        return [json.loads(line) for line in lines if json.loads(line)[:2] == ['rebrand', 'run']]

    def refused(self, route, **sent):
        with self.assertRaises(WorkspaceError) as caught:
            self.page.write(f'/api/brand-{route}', sent)
        return str(caught.exception)

    def until(self, test, seconds=20):
        limit = time.monotonic() + seconds
        while time.monotonic() < limit:
            shown = self.call('rebrand')
            if test(shown):
                return shown
            time.sleep(0.05)
        self.fail(f'Never reached: {shown}')

    def start(self, **sent):
        return self.call('rebrand-start', **{'source': SLIDES, 'brand': 'example', 'confirm': True, **sent})

    def test_only_a_google_slides_or_docs_address_is_taken_and_rebuilt_from_its_id(self):
        ident = '1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789'
        for given, kind in ((SLIDES, 'slides'), (f'https://docs.google.com/document/u/0/d/{ident}/edit?tab=t.0', 'docs'),
                            (f'  https://docs.google.com/document/d/{ident}  ', 'docs')):
            with self.subTest(given=given):
                address, found = brand_rebrand.source(given)
                self.assertEqual(found, kind)
                self.assertTrue(address.endswith(f'/d/{ident}/edit'))
        for given in (f'https://docs.google.com/spreadsheets/d/{ident}/edit', f'https://drive.google.com/file/d/{ident}/view',
                      f'http://docs.google.com/presentation/d/{ident}/edit', f'https://docs.google.com.example.com/presentation/d/{ident}',
                      f'https://docs.google.com/presentation/d/{ident}; rm -rf ~', 'javascript:alert(1)', '--brand=other',
                      f'https://docs.google.com/presentation/d/short/edit', 42, None):
            with self.subTest(given=given):
                with self.assertRaisesRegex(WorkspaceError, 'Google Slides or Google Docs'):
                    brand_rebrand.source(given)

    def test_a_brand_not_set_up_is_refused_in_the_skills_own_words_and_nothing_runs(self):
        said = self.refused('rebrand-check', source=SLIDES, brand='plain')
        self.assertIn('Plain Co cannot rebrand a file yet. Harness Brand says: plain is not set up for rebranding', said)
        self.assertIn('Set it up with:', said)   # what to do, as Harness Brand says it
        self.assertNotIn('Rebranding command failed', said)
        self.assertIn('cannot rebrand a file yet', self.refused('rebrand-start', source=SLIDES, brand='plain', confirm=True))
        self.assertIn('Choose a brand', self.refused('rebrand-check', source=SLIDES, brand='../example'))
        self.assertIn('Google Slides or Google Docs', self.refused('rebrand-check', source='https://example.com/deck', brand='example'))
        self.assertIn('Say yes', self.refused('rebrand-start', source=SLIDES, brand='example'))
        self.assertEqual(self.runs(), [])
        self.assertIsNone(self.call('rebrand')['job'])

    def test_a_brand_that_is_set_up_is_checked_before_anything_runs(self):
        checked = self.call('rebrand-check', source=SLIDES, brand='example')
        self.assertEqual(checked, {'source': CANONICAL, 'kind': 'slides', 'what': 'Google Slides deck',
                                   'brand': 'example', 'name': 'Example Co'})
        self.assertEqual(self.runs(), [])
        self.assertEqual(self.call('rebrand')['brands'], [{'id': 'example', 'name': 'Example Co'},
                                                          {'id': 'plain', 'name': 'Plain Co'}])

    def test_progress_one_at_a_time_and_a_result_awaiting_the_persons_check(self):
        with mock.patch.dict(os.environ, {'STAND_IN_REBRAND_PAUSE': '0.4'}):
            started = self.start()
            self.assertEqual(started['job']['state'], 'running')
            self.assertIn('Exporting the original from Google Drive; it is not changed',
                          self.until(lambda shown: len(shown['job']['lines']) > 1)['job']['lines'])
            self.assertIn('A rebrand is running', self.refused('rebrand-start', source=SLIDES, brand='example', confirm=True))
            running = self.until(lambda shown: 'The new copy is in your Google Drive' in shown['job']['lines'])
            self.assertTrue(running['job']['copy'].startswith('https://docs.google.com/presentation/d/'))
            brand_rebrand.wait(20)
        job = self.call('rebrand')['job']
        self.assertEqual(job['state'], 'done', job)
        # The address went to Harness Brand as one argument, rebuilt from the file's id.
        [command] = self.runs()
        self.assertEqual(command, ['rebrand', 'run', CANONICAL, '--brand', 'example', '--run-dir', job['runDir']])
        result = job['result']
        self.assertEqual((result['status'], result['verdict'], result['review']), ('branded', 'branded', None))
        self.assertEqual(result['next'], 'Open the native file and inspect every page before calling it done.')
        self.assertEqual(result['url'], 'https://docs.google.com/presentation/d/stand-in-copy-1234567890/edit')
        self.assertIn('# Stand-in example branding report', result['report'])
        self.assertEqual(result['reportPath'], str(Path(job['runDir']) / 'report.md'))
        self.assertTrue(Path(job['runDir']).is_relative_to(self.root / 'data' / 'brand-rebrand' / 'runs'))
        # The page says the copy awaits the person's own look; it never calls it accepted.
        script = (ROOT / 'marketing_studio/web/brands.js').read_text()
        rebrand = script[script.index('// --- Rebrand a Google file'):script.index('function libraryTable')]
        self.assertIn('Awaiting your visual check', rebrand)
        self.assertNotIn('accept', rebrand.lower())

    def test_a_review_is_asked_for_only_when_ticked_and_names_the_assistant(self):
        shared_values = {'assistant': {'agent': 'codex'}}
        from marketing_studio import shared
        shared.update(shared_values)
        self.start(review=True)
        brand_rebrand.wait(20)
        job = self.call('rebrand')['job']
        [command] = self.runs()
        self.assertEqual(command[-3:], ['--review', '--reviewer', 'codex'])
        self.assertEqual((job['state'], job['review'], job['result']['verdict'], job['result']['review']),
                         ('done', True, 'branded with exceptions', 'passed_with_findings'))

    def gone(self, *pids, seconds=5):
        """Whether every one of these processes has ended (and been reaped by whoever owned it)."""
        limit = time.monotonic() + seconds
        while time.monotonic() < limit:
            alive = []
            for pid in pids:
                try:
                    os.kill(pid, 0)
                    alive.append(pid)
                except ProcessLookupError:
                    pass
            if not alive:
                return True
            time.sleep(0.05)
        return False

    def test_stop_ends_the_run_and_every_process_it_started(self):
        pids = self.root / 'pids.json'
        with mock.patch.dict(os.environ, {'STAND_IN_REBRAND_PAUSE': '5', 'STAND_IN_PIDS': str(pids)}):
            self.start()
            self.until(lambda shown: len(shown['job']['lines']) > 1 and pids.exists())
            child, node = json.loads(pids.read_text())
            running = json.loads(brand_rebrand.record_path().read_text())
            self.assertEqual(running['pgid'], node)   # kept, so a later Marketing Studio can end it
            began = time.monotonic()
            self.call('rebrand-stop')
            brand_rebrand.wait(20)
        self.assertLess(time.monotonic() - began, 5)
        # Node, and the Python process it started, are both gone.
        self.assertTrue(self.gone(child, node), 'the rebrand left a process running')
        job = self.call('rebrand')['job']
        self.assertNotIn('pgid', job)
        self.assertEqual(job['state'], 'stopped')
        self.assertEqual(job['detail'], 'It was stopped before it finished. No copy was made in your Google Drive.')
        self.assertIsNone(job['result'])
        # A stopped job can be put away; its run folder stays.
        self.call('rebrand-clear')
        self.assertIsNone(self.call('rebrand')['job'])

    def test_a_run_that_did_not_finish_gives_the_skills_reason_and_the_copy_it_made(self):
        with mock.patch.dict(os.environ, {'STAND_IN_REBRAND_FAIL': 'Google conversion changed checked content: slide 2: text.'}):
            self.start()
            brand_rebrand.wait(20)
        job = self.call('rebrand')['job']
        self.assertEqual(job['state'], 'failed')
        self.assertEqual(job['detail'], 'Google conversion changed checked content: slide 2: text. A copy had already '
                                        'been made in your Google Drive; check it before you use it.')
        self.assertEqual((job['result']['verdict'], job['copy']),
                         ('incomplete', 'https://docs.google.com/presentation/d/stand-in-copy-1234567890/edit'))

    def test_a_reloaded_page_finds_the_job_and_one_left_by_a_closed_studio_reads_as_it_ended(self):
        self.start()
        brand_rebrand.wait(20)
        listed = self.call('list')
        self.assertEqual(listed['rebrand']['job']['state'], 'done')
        record = brand_rebrand.record_path()
        job = json.loads(record.read_text())
        # A record left running, as after Marketing Studio closed, whose run finished by itself:
        # its result is read, not guessed.
        job.update(state='running', result=None, copy=None, pgid=999_999)
        record.write_text(json.dumps(job))
        shown = self.call('rebrand')['job']
        self.assertEqual((shown['state'], shown['result']['verdict']), ('done', 'branded'))
        self.assertTrue(shown['detail'].startswith('It finished after Marketing Studio was closed.'))
        # One whose run was cut short: stopped, and its checkpoint says a copy was made.
        (Path(job['runDir']) / 'result.json').unlink()
        record.write_text(json.dumps(job))
        shown = self.call('rebrand')['job']
        self.assertEqual(shown['state'], 'stopped')
        self.assertIn('Marketing Studio was closed while this ran', shown['detail'])
        self.assertIn('A copy had already been made', shown['detail'])
        # With neither a result nor a checkpoint, nothing is claimed about the copy.
        (Path(job['runDir']) / 'checkpoint.json').unlink()
        record.write_text(json.dumps(job))
        self.assertIn('No copy was recorded. Look in your Google Drive', self.call('rebrand')['job']['detail'])

    def orphan(self, job_id='orphan'):
        """A `rebrand run` that a Marketing Studio which has closed left going: started in a
        process group of its own, with a record that still says running."""
        run_dir = brand_rebrand.folder() / 'runs' / job_id
        fake = Path(os.environ['BRAND_SKILL_RUNTIME'])
        pids = self.root / f'{job_id}-pids.json'
        env = {**os.environ, 'STAND_IN_REBRAND_PAUSE': '30', 'STAND_IN_PIDS': str(pids),
               'HARNESS_BRAND_DATA': str(self.brands)}
        process = subprocess.Popen(['node', str(fake / 'scripts/harness-brand.mjs'), 'rebrand', 'run', CANONICAL,
                                    '--brand', 'example', '--run-dir', str(run_dir)], env=env,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        self.addCleanup(lambda: (process.kill(), process.wait()))
        limit = time.monotonic() + 10
        while not pids.exists() and time.monotonic() < limit:
            time.sleep(0.05)
        brand_rebrand.record_path().parent.mkdir(parents=True, exist_ok=True)
        brand_rebrand.record_path().write_text(json.dumps({
            'schema': 1, 'id': job_id, 'source': CANONICAL, 'kind': 'slides', 'brand': 'example',
            'brandName': 'Example Co', 'review': False, 'state': 'running', 'lines': ['Starting Harness Brand'],
            'detail': '', 'copy': None, 'result': None, 'started': time.time(), 'ended': None,
            'runDir': str(run_dir), 'pgid': process.pid}))
        return process, json.loads(pids.read_text())

    def test_a_run_left_going_by_a_closed_studio_is_ended_before_it_is_called_stopped(self):
        process, (child, _) = self.orphan()
        shown = self.call('rebrand')['job']
        process.wait(5)
        self.assertTrue(self.gone(child, process.pid), 'the orphaned rebrand was left running')
        self.assertEqual(shown['state'], 'stopped')
        self.assertTrue(shown['detail'].startswith('Marketing Studio was closed while this ran, so it was stopped '
                                                   'when Marketing Studio next opened Brands.'), shown['detail'])
        self.assertIn('No copy was recorded', shown['detail'])

    def test_a_new_rebrand_ends_one_left_going_first_so_only_one_runs(self):
        process, (child, _) = self.orphan()
        self.start()
        process.wait(5)
        self.assertTrue(self.gone(child, process.pid))
        brand_rebrand.wait(20)
        self.assertEqual(self.call('rebrand')['job']['state'], 'done')

    def test_a_process_group_now_running_something_else_is_never_touched(self):
        other = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], start_new_session=True)
        self.addCleanup(lambda: (other.kill(), other.wait()))
        brand_rebrand.record_path().parent.mkdir(parents=True, exist_ok=True)
        brand_rebrand.record_path().write_text(json.dumps({
            'schema': 1, 'id': 'old', 'source': CANONICAL, 'kind': 'slides', 'brand': 'example', 'brandName': 'Example Co',
            'review': False, 'state': 'running', 'lines': [], 'detail': '', 'copy': None, 'result': None,
            'started': 0, 'ended': None, 'runDir': str(self.root / 'no-such-run'), 'pgid': other.pid}))
        self.assertEqual(self.call('rebrand')['job']['state'], 'stopped')
        self.assertIsNone(other.poll(), 'a process that is not this rebrand was ended')

    def test_closing_marketing_studio_ends_the_running_rebrand(self):
        pids = self.root / 'pids.json'
        with mock.patch.dict(os.environ, {'STAND_IN_REBRAND_PAUSE': '5', 'STAND_IN_PIDS': str(pids)}):
            self.start()
            self.until(lambda shown: pids.exists())
            child, node = json.loads(pids.read_text())
            brand_rebrand._shutdown()   # what Marketing Studio's exit runs
            self.assertTrue(self.gone(child, node))
            brand_rebrand.wait(20)
        job = json.loads(brand_rebrand.record_path().read_text())
        self.assertEqual(job['state'], 'stopped')
        self.assertTrue(job['detail'].startswith('Marketing Studio was closed while this ran, so it was stopped.'), job['detail'])

    def test_a_folder_named_like_an_option_is_never_offered_as_a_brand(self):
        brand_pack(self.brands, 'odd')
        (self.brands / 'odd').rename(self.brands / '--help')
        ids = [each['id'] for each in self.call('rebrand')['brands']]
        self.assertNotIn('--help', ids)
        self.assertIn('Choose a brand', self.refused('rebrand-check', source=SLIDES, brand='--help'))

    def test_the_routes_are_brand_routes_refused_over_the_network(self):
        from marketing_studio.page import Home
        for name in ('rebrand', 'rebrand-check', 'rebrand-start', 'rebrand-stop', 'rebrand-clear', 'documents', 'document'):
            self.assertIn(f'/api/brand-{name}', Home.writes)
        self.page.caller.remote = True
        try:
            self.assertIn('Brands are made on the computer', self.refused('rebrand-start', source=SLIDES, brand='example', confirm=True))
        finally:
            self.page.caller.remote = False
