"""The shared activity lines and per-project Activity log (#294), with disposable folders."""
import json
import tempfile
import threading
import unittest
from dataclasses import dataclass
from pathlib import Path

import marketing_studio  # noqa: F401  puts the shared core on the import path
from studio_core import activity_log


@dataclass
class Ended:
    """Stands in for agents.Outcome: how a job ended."""
    finished: bool
    reason: str | None = None
    detail: str = ''


class LinesTests(unittest.TestCase):
    def test_lines_keep_times_and_drop_the_oldest_past_the_cap(self):
        lines = activity_log.Lines(limit=3, clock=iter(f'2030-01-01T00:00:0{n}Z'
                                                         for n in range(9)).__next__)
        for text in ('Started', 'Thinking', 'Searching the web: rolling restarts',
                     'Reading saved source S1', 'Handing back research-result'):
            lines.append(text)
        self.assertEqual(lines.count, 5)
        self.assertEqual([line['text'] for line in lines.items()],
                         ['Searching the web: rolling restarts', 'Reading saved source S1',
                          'Handing back research-result'])
        self.assertEqual(lines.latest(), {'at': '2030-01-01T00:00:04Z',
                                          'text': 'Handing back research-result'})

    def test_the_default_cap_is_two_hundred_lines(self):
        lines = activity_log.Lines()
        for number in range(250):
            lines.append(f'Reading saved source S{number}')
        self.assertEqual(len(lines), 200)
        self.assertEqual(lines.items()[0]['text'], 'Reading saved source S50')

    def test_raw_json_and_empty_lines_are_never_kept_and_long_lines_are_clipped(self):
        lines = activity_log.Lines()
        lines.append('{"type": "assistant", "message": {"content": "secret"}}')
        lines.append('[1, 2]')
        lines.append('   ')
        lines.append(None)
        lines.append('x' * 1000)
        kept = lines.items()
        self.assertEqual(len(kept), 1)
        self.assertEqual(len(kept[0]['text']), activity_log.LINE_LENGTH)
        self.assertTrue(kept[0]['text'].endswith('…'))

    def test_live_shows_each_running_job_with_its_latest_line(self):
        lines = activity_log.Lines()
        lines.append('Started')
        lines.append('Reading saved source S3')
        shown, = activity_log.live([('research:investigate-1-a', {
            'label': 'Investigating research area a', 'started_at': '2030-01-01T00:00:00Z',
            'lines': lines, 'folder': Path('/somewhere'), 'stop': threading.Event()})])
        self.assertEqual(shown['now']['text'], 'Reading saved source S3')
        # A poll carries the latest line and how many there are, never the lines themselves.
        self.assertEqual(set(shown), {'id', 'label', 'started_at', 'now', 'count'})
        self.assertEqual(shown['count'], 2)
        # A worker kept as plain strings, as an older caller or a test has it, still reads.
        old, = activity_log.live([('x', {'label': 'X', 'started_at': None, 'lines': ['Writing']})])
        self.assertEqual((old['now'], old['count']), ({'at': None, 'text': 'Writing'}, 1))

    def test_an_open_show_activity_reads_only_the_lines_it_has_not_had(self):
        lines = activity_log.Lines(limit=3)
        workers = [('job', {'label': 'Job', 'started_at': None, 'lines': lines})]
        for text in ('One', 'Two'):
            lines.append(text)
        first = activity_log.running_lines(workers, 'job', 0)
        self.assertEqual(([line['text'] for line in first['lines']], first['count'],
                          first['start']), (['One', 'Two'], 2, 0))
        for text in ('Three', 'Four', 'Five'):
            lines.append(text)
        later = activity_log.running_lines(workers, 'job', first['count'])
        self.assertEqual([line['text'] for line in later['lines']], ['Three', 'Four', 'Five'])
        self.assertEqual(activity_log.running_lines(workers, 'job', 5)['lines'], [])
        # Opened late, it is told the lines before the cap are not here.
        late = activity_log.running_lines(workers, 'job', 0)
        self.assertEqual((late['start'], len(late['lines'])), (2, 3))
        self.assertEqual(activity_log.running_lines(workers, 'gone', 0),
                         {'lines': [], 'count': 0, 'start': 0, 'running': False})

    def test_lines_can_be_appended_from_another_thread_while_read(self):
        lines = activity_log.Lines()
        writer = threading.Thread(target=lambda: [lines.append(f'Line {n}') for n in range(500)])
        writer.start()
        while writer.is_alive():
            activity_log.live([('a', {'label': 'A', 'started_at': None, 'lines': lines})])
        writer.join()
        self.assertEqual(lines.count, 500)


class LogTests(unittest.TestCase):
    def setUp(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.path = Path(holder.name) / 'project' / 'work' / activity_log.FILE

    def test_endings_read_from_an_outcome(self):
        self.assertEqual(activity_log.ending(Ended(True)), 'finished')
        self.assertEqual(activity_log.ending(Ended(False, 'stopped')), 'stopped')
        self.assertEqual(activity_log.ending(Ended(False, 'timeout')), 'timeout')
        self.assertEqual(activity_log.ending(Ended(False, 'limit')), 'limit')
        self.assertEqual(activity_log.ending(Ended(False, 'failed')), 'failed')
        self.assertEqual(activity_log.ending(Ended(False, 'unavailable')), 'failed')
        with self.assertRaises(ValueError):
            activity_log.entry('A', 'a', None, 'gone', [])

    def test_a_project_with_no_log_says_so(self):
        found = activity_log.view(self.path)
        self.assertEqual(found['jobs'], [])
        self.assertEqual(found['empty'], 'No activity recorded yet.')
        self.path.parent.mkdir(parents=True)
        self.path.write_text('not json\n{"outcome": "unknown"}\n', encoding='utf-8')
        self.assertEqual(activity_log.view(self.path)['empty'], 'No activity recorded yet.')

    def test_jobs_are_read_newest_first_with_their_outcome_and_lines(self):
        for number, ended in enumerate(('finished', 'failed', 'stopped', 'timeout', 'limit')):
            lines = activity_log.Lines()
            lines.append(f'Doing job {number}')
            activity_log.append(self.path, activity_log.entry(
                f'Job {number}', f'step-{number}', '2030-01-01T00:00:00Z', ended, lines,
                detail='It did not finish in 600 seconds, so it was stopped.'))
        jobs = activity_log.view(self.path)['jobs']
        self.assertEqual([job['label'] for job in jobs], [f'Job {n}' for n in range(4, -1, -1)])
        self.assertEqual([job['words'] for job in jobs],
                         ['Reached a limit', 'Out of time', 'Stopped', 'Failed', 'Finished'])
        # The view is headers: each job's lines are read when it is opened.
        self.assertNotIn('lines', jobs[0])
        self.assertEqual(jobs[0]['steps'], 1)
        opened = activity_log.entry_lines(self.path, jobs[0]['id'])
        self.assertEqual(opened['lines'][0]['text'], 'Doing job 4')
        self.assertRegex(opened['lines'][0]['at'], r'^\d{4}-\d\d-\d\dT')
        self.assertTrue(activity_log.entry_lines(self.path, 'nothing')['missing'])
        jobs = activity_log.read(self.path)
        self.assertNotIn('detail', jobs[-1])   # a job that finished says no why
        self.assertIn('600 seconds', jobs[0]['detail'])

    def test_the_log_keeps_the_newest_jobs_and_each_job_its_newest_lines(self):
        for number in range(activity_log.JOBS + activity_log.SLACK + 5):
            activity_log.append(self.path, activity_log.entry(
                f'Job {number}', 'step', None, 'finished', [f'Line {number}']))
        jobs = activity_log.read(self.path)
        self.assertLessEqual(len(self.path.read_text().splitlines()),
                             activity_log.JOBS + activity_log.SLACK)
        self.assertEqual(len(jobs), activity_log.JOBS)
        self.assertEqual(jobs[0]['label'], f'Job {activity_log.JOBS + activity_log.SLACK + 4}')
        long = activity_log.entry('Long', 'step', None, 'finished',
                                  [f'Line {n}' for n in range(450)])
        self.assertEqual(len(long['lines']), activity_log.LINES)
        self.assertEqual(long['lines'][0]['text'], 'Line 250')
        self.assertEqual(long['dropped'], 250)

    def test_the_log_holds_plain_lines_only(self):
        lines = activity_log.Lines()
        lines.append('Searching the web: rolling restart minimum instances')
        lines.append(json.dumps({'type': 'user', 'message': {'content': 'The task text'}}))
        activity_log.append(self.path, activity_log.entry(
            'Investigating', 'research:investigate-1', None, 'failed', lines,
            detail='{"type": "result", "result": "raw"}'))
        written = json.loads(self.path.read_text())
        self.assertEqual(set(written), {'id', 'label', 'step', 'started_at', 'ended_at',
                                        'outcome', 'lines', 'dropped'})
        self.assertEqual([line['text'] for line in written['lines']],
                         ['Searching the web: rolling restart minimum instances'])
        self.assertNotIn('The task text', self.path.read_text())


if __name__ == '__main__':
    unittest.main()
