"""What an assistant is doing while it works, and the training's Activity log (#294).

Scripted workers in a disposable workspace: no agent is started and nothing leaves this
computer."""
import json
import re
import subprocess
import threading
import time
import unittest

from runner_support import StudioCase, fails


class ActivityLogTests(StudioCase):

    def log_path(self, root):
        from runner import engine
        return root / engine.ACTIVITY

    def test_a_research_job_shows_its_lines_while_it_works_and_is_logged_when_it_ends(self):
        seen = {}

        def researching(tools, job):
            tools.list_inputs()
            for found in self.engine.trainings():
                seen['view'] = self.engine.view(found)
                seen['log'] = self.engine.activity(found)
                ident = next(one['id'] for one in seen['view']['workers'])
                seen['lines'] = self.engine.activity(found, job=ident, since=0)['lines']
                seen['task'] = job.task
            return self.workers.question(tools, job)

        # The first research question's job: research jobs of every kind run through the
        # engine's one way to run a worker, the parallel research transport's among them.
        self.workers.then('question', researching)
        root = self.saved_start()
        self.to_gate(root, 'research')
        worker = next(one for one in seen['view']['workers']
                      if one['id'].startswith('research:'))
        self.assertEqual((worker['now']['text'], worker['count']),
                         ('Looking at what it was given', 1))
        self.assertEqual([line['text'] for line in seen['lines']],
                         ['Looking at what it was given'])
        self.assertRegex(worker['now']['at'], r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$')
        self.assertEqual(seen['log']['running'][0]['id'], worker['id'])

        jobs = self.engine.activity(root)['jobs']
        research = next(job for job in jobs if job['step'] == worker['id'])
        self.assertEqual(research['outcome'], 'finished')
        self.assertEqual(research['words'], 'Finished')
        self.assertEqual(research['label'], worker['label'])
        said = [line['text'] for line in self.engine.activity(root, entry=research['id'])['lines']]
        self.assertEqual(said[0], 'Looking at what it was given')
        self.assertIn('Handing back the finding for ' + worker['id'].partition(':')[2], said)
        self.assertIn('The finding was accepted', said)
        self.assertTrue(research['started_at'] <= research['ended_at'])
        # Newest first: the research job came after the research plan.
        self.assertLess(jobs.index(research),
                        next(i for i, job in enumerate(jobs) if job['step'] == 'research-plan'))

        # Only plain lines: never the task, the brief or a raw event.
        written = self.log_path(root).read_text(encoding='utf-8')
        self.assertNotIn(seen['task'][:60], written)
        self.assertNotIn('"type"', written)
        for line in written.splitlines():
            item = json.loads(line)
            if 'checkpoint' in item:
                self.assertEqual(set(item), {'checkpoint', 'unit', 'at'})
                continue
            for one in item['lines']:
                self.assertFalse(one['text'].startswith(('{', '[')))

        # The log is this computer's and never shared: it is in no commit and leaves the
        # repository clean.
        repo = self.space.repo
        tracked = subprocess.run(['git', 'ls-files'], cwd=repo, capture_output=True,
                                 text=True, check=True).stdout
        self.assertNotIn('activity-log', tracked)
        status = subprocess.run(['git', 'status', '--porcelain', '--ignored=no'], cwd=repo,
                                capture_output=True, text=True, check=True).stdout
        self.assertNotIn('activity-log', status)

    def ending_of(self, act) -> dict:
        self.workers.then('research-plan', act)
        root = self.saved_start()
        # The first try at the research plan: the oldest, as the log reads newest first.
        tried = [job for job in self.engine.activity(root)['jobs']
                 if job['step'] == 'research-plan']
        return tried[-1]

    def test_a_failed_job_is_logged_as_failed_with_why(self):
        job = self.ending_of(fails('It stopped without finishing: the model gave up.'))
        self.assertEqual((job['outcome'], job['words']), ('failed', 'Failed'))
        self.assertIn('the model gave up', job['detail'])

    def test_a_job_out_of_time_is_logged_as_out_of_time(self):
        job = self.ending_of(fails('It did not finish in 600 seconds, so it was stopped.',
                                   reason='timeout'))
        self.assertEqual((job['outcome'], job['words']), ('timeout', 'Out of time'))

    def test_a_job_that_reached_a_limit_is_logged_as_a_limit(self):
        job = self.ending_of(fails('It stopped without finishing: its spending limit was '
                                   'reached', reason='limit'))
        self.assertEqual(job['outcome'], 'limit')

    def test_a_log_that_cannot_be_written_never_stops_the_run(self):
        # The files lock busy past its wait refuses with a WorkspaceError: the job is still
        # kept and the run carries on to its gate, with nothing logged.
        from unittest import mock
        from workspace import WorkspaceError
        with mock.patch('studio_core.activity_log.append',
                        side_effect=WorkspaceError('The workspace is busy.')) as append:
            root = self.saved_start()
            self.assertTrue(append.called)
        self.assertEqual(self.view(root)['state'], 'waiting')
        self.assertEqual(self.engine.activity(root)['jobs'], [])

    def test_a_training_with_no_log_still_opens_and_says_so(self):
        self.workers.then('research-plan', fails())
        root = self.saved_start()
        self.log_path(root).unlink()
        found = self.engine.activity(root)
        self.assertEqual((found['jobs'], found['empty']), ([], 'No activity recorded yet.'))
        self.assertIsNotNone(self.engine.view(root))

    def test_the_page_reads_the_log_for_a_training_it_knows(self):
        from runner import page
        root = self.saved_start()
        served = page.RunnerPage(8765, self.engine)
        found = served.engine.activity(served.driving(str(root)))
        self.assertTrue(found['jobs'])
        self.assertIn('/api/activity', page.READS)
        # `since` is a whole number in ASCII digits: anything else is refused, never a 500.
        import desk

        def asked(**given):
            def one(name):
                if name not in given:
                    raise desk.Refusal(400, f'Give {name}.')
                return given[name]
            return one
        self.assertEqual(page.activity_asked(asked(job='research-plan', since='12')),
                         {'entry': None, 'job': 'research-plan', 'since': 12})
        for bad in ('²', '-1', '1e3', '9' * 10):
            with self.assertRaises(desk.Refusal):
                page.activity_asked(asked(job='research-plan', since=bad))



class StoppedJobTests(StudioCase):
    """Stop, as the person presses it while a worker works, on the runner's own threads."""

    BACKGROUND = True

    def until(self, check, seconds: float = 30):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            found = check()
            if found:
                return found
            time.sleep(0.02)
        self.fail('It did not happen in time.')

    def test_a_stopped_job_is_logged_as_stopped_with_what_it_did(self):
        entered, go = threading.Event(), threading.Event()
        self.addCleanup(go.set)

        def working(tools, job):
            tools.list_inputs()
            entered.set()
            go.wait(30)

        self.workers.then('research-plan', working)
        root = self.saved_start()
        self.assertTrue(entered.wait(30))
        self.assertEqual(self.engine.act(root, 'stop')['state'], 'stopped')
        go.set()
        self.until(lambda: self.engine._run(root).thread is None)
        job, = self.engine.activity(root)['jobs']
        self.assertEqual((job['step'], job['outcome'], job['words']),
                         ('research-plan', 'stopped', 'Stopped'))
        self.assertEqual([line['text'] for line in self.engine.activity(
            root, entry=job['id'])['lines']], ['Looking at what it was given'])

    def test_stop_still_stops_when_the_log_cannot_be_written(self):
        from unittest import mock
        from workspace import WorkspaceError
        entered, go = threading.Event(), threading.Event()
        self.addCleanup(go.set)

        def working(tools, job):
            tools.list_inputs()
            entered.set()
            go.wait(30)

        self.workers.then('research-plan', working)
        with mock.patch('studio_core.activity_log.append',
                        side_effect=WorkspaceError('The workspace is busy.')):
            root = self.saved_start()
            self.assertTrue(entered.wait(30))
            self.assertEqual(self.engine.act(root, 'stop')['state'], 'stopped')
            go.set()
            self.until(lambda: self.engine._run(root).thread is None)
        self.assertEqual(self.view(root)['state'], 'stopped')


if __name__ == '__main__':
    unittest.main()
