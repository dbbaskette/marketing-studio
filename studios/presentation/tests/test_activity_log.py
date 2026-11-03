"""What an assistant is doing while it works, and the deck's Activity log (#294).

Scripted workers in a disposable workspace: no agent is started and nothing leaves this
computer."""
import json
import subprocess
import threading
import time
import unittest

from runner_support import StudioCase, fails


class ActivityLogTests(StudioCase):

    def log_path(self, root):
        from runner import jobs
        return root / jobs.ACTIVITY

    def test_a_research_job_shows_its_lines_while_it_works_and_is_logged_when_it_ends(self):
        seen = {}

        def researching(tools, job):
            tools.list_inputs()
            for found in self.engine.every():
                seen['view'] = self.engine.view(found)
                seen['log'] = self.engine.activity(found)
            seen['task'] = job.task
            return self.workers.question(tools, job)

        self.workers.then('question', researching)
        root = self.saved_start(research=True)
        self.decide(root, 'gate:research-plan')
        self.assertEqual(self.waiting(root), 'gate:research')
        worker = next(one for one in seen['view']['workers']
                      if one['id'].startswith('research:'))
        self.assertEqual(worker['now']['text'], 'Looking at what it was given')
        self.assertRegex(worker['now']['at'], r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$')
        self.assertEqual(seen['log']['running'][0]['id'], worker['id'])

        jobs = self.engine.activity(root)['jobs']
        research = next(job for job in jobs if job['step'] == worker['id'])
        self.assertEqual((research['outcome'], research['label']), ('finished', worker['label']))
        said = [line['text'] for line in research['lines']]
        self.assertEqual(said[0], 'Looking at what it was given')
        self.assertIn('The finding was accepted', said)

        written = self.log_path(root).read_text(encoding='utf-8')
        self.assertNotIn(seen['task'][:60], written)
        self.assertNotIn('"type"', written)
        for line in written.splitlines():
            self.assertTrue(all(not one['text'].startswith(('{', '['))
                                for one in json.loads(line)['lines']))
        repo = self.space.repo
        tracked = subprocess.run(['git', 'ls-files'], cwd=repo, capture_output=True,
                                 text=True, check=True).stdout
        self.assertNotIn('activity-log', tracked)
        status = subprocess.run(['git', 'status', '--porcelain'], cwd=repo,
                                capture_output=True, text=True, check=True).stdout
        self.assertNotIn('activity-log', status)

    def first_outline(self, act) -> dict:
        self.workers.then('outline', act)
        root = self.saved_start()
        return [job for job in self.engine.activity(root)['jobs']
                if job['step'] == 'outline'][-1]

    def test_a_failed_job_is_logged_as_failed(self):
        self.assertEqual(self.first_outline(fails('The model gave up.'))['outcome'], 'failed')

    def test_a_job_out_of_time_is_logged_as_out_of_time(self):
        job = self.first_outline(fails('It did not finish in 900 seconds, so it was stopped.',
                                       reason='timeout'))
        self.assertEqual((job['outcome'], job['words']), ('timeout', 'Out of time'))
        self.assertIn('900 seconds', job['detail'])

    def test_a_job_at_a_limit_is_logged_as_a_limit(self):
        job = self.first_outline(fails("You've hit your usage limit.", reason='limit'))
        self.assertEqual((job['outcome'], job['words']), ('limit', 'Reached a limit'))

    def test_a_deck_with_no_log_still_opens_and_says_so(self):
        root = self.saved_start()
        self.log_path(root).unlink()
        found = self.engine.activity(root)
        self.assertEqual((found['jobs'], found['empty']), ([], 'No activity recorded yet.'))
        self.assertIsNotNone(self.view(root))

    def test_the_page_serves_the_log(self):
        from runner import page
        self.assertIn('/api/activity', page.READS)


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

        self.workers.then('outline', working)
        root = self.saved_start()
        self.assertTrue(entered.wait(30))
        worker, = self.engine.view(root)['workers']
        self.assertEqual(worker['now']['text'], 'Looking at what it was given')
        self.engine.act(root, 'stop')
        go.set()
        self.until(lambda: any(job['step'] == 'outline'
                               for job in self.engine.activity(root)['jobs']))
        job = next(job for job in self.engine.activity(root)['jobs'] if job['step'] == 'outline')
        self.assertEqual((job['outcome'], job['words']), ('stopped', 'Stopped'))
        self.assertEqual([line['text'] for line in job['lines']],
                         ['Looking at what it was given'])


if __name__ == '__main__':
    unittest.main()
