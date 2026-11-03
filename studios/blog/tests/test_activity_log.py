"""What Blog Studio's assistant is doing while it works, and each blog's Activity log.

Every assistant here is a synthetic CLI written by the test: it prints the events Claude Code
(`--output-format stream-json`) or Codex (`exec --json`) would, and nothing reaches a provider
or the network. Workspaces are disposable.
"""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import json
import os
import sys
import threading
import time
import unittest
from unittest.mock import patch

from test_blog_runner import RunnerCase
import blog_activity
import blog_runner as runner
import blog_worker
import management
import tool_jobs
from studio_core import activity_log

VALUE = {'content': '# Synthetic outline', 'notes': 'Fixture CLI; no account.'}
# What Claude Code says as it works: it starts, searches, hands back its answer, and its result.
CLAUDE_EVENTS = [
    {'type': 'system', 'subtype': 'init', 'model': 'synthetic-model'},
    {
        'type': 'assistant',
        'message': {
            'content': [
                {
                    'type': 'tool_use',
                    'id': 't1',
                    'name': 'WebSearch',
                    'input': {'query': 'retry budgets'},
                }
            ]
        },
    },
    {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': 't1'}]}},
    {
        'type': 'assistant',
        'message': {
            'content': [
                {'type': 'tool_use', 'id': 't2', 'name': 'StructuredOutput', 'input': VALUE}
            ]
        },
    },
    {
        'type': 'result',
        'subtype': 'success',
        'is_error': False,
        'result': '',
        'structured_output': VALUE,
        'total_cost_usd': 0.0125,
        'usage': {'input_tokens': 100, 'cache_read_input_tokens': 20, 'output_tokens': 30},
    },
]
CODEX_EVENTS = [
    {'type': 'thread.started', 'thread_id': 'synthetic'},
    {'type': 'item.completed', 'item': {'type': 'reasoning', 'text': 'private'}},
    {'type': 'item.completed', 'item': {'type': 'web_search', 'query': 'retry budgets'}},
    {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': json.dumps(VALUE)}},
    {'type': 'turn.completed', 'usage': {'input_tokens': 10, 'output_tokens': 5}},
]


class Case(RunnerCase):
    def setUp(self):
        super().setUp()
        self.binary = self.base / 'fixture-agent'
        self.capture = self.base / 'command.json'
        self.release = self.base / 'release'
        patches = [
            patch.object(blog_worker.source_curator, 'executable', return_value=str(self.binary)),
            patch.object(blog_worker.source_curator, 'codex_options', return_value=[]),
        ]
        for one in patches:
            one.start()
            self.addCleanup(one.stop)
        self.running = blog_activity.Running(self.root)

    def agent(self, claude=CLAUDE_EVENTS, codex=CODEX_EVENTS, wait=False, code=0, last=VALUE):
        """A synthetic CLI: it records its arguments, prints its events one at a time and,
        with `wait`, holds after the first until the test lets it go."""
        self.binary.write_text(
            '#!' + sys.executable + '\nimport sys,json,time\nfrom pathlib import Path\n'
            'args=sys.argv[1:]\n'
            f'Path({str(self.capture)!r}).write_text(json.dumps(args))\n'
            "codex='--output-last-message' in args\n"
            f'events={claude!r} if not codex else {codex!r}\n'
            'for at,event in enumerate(events):\n'
            ' print(json.dumps(event),flush=True)\n'
            f' if at==0 and {wait!r}:\n'
            f'  while not Path({str(self.release)!r}).exists(): time.sleep(0.05)\n'
            f'if codex and {last!r} is not None:\n'
            " Path(args[args.index('--output-last-message')+1]).write_text(json.dumps("
            f'{last!r}))\n'
            f'sys.exit({code!r})\n'
        )
        self.binary.chmod(0o700)

    def log(self, subject='blog-synthetic'):
        return activity_log.read(blog_activity.path(self.root, subject))

    def generate(self, engine='claude', subject='blog-synthetic', **options):
        with blog_activity.within(self.running, subject, 'Writing the outline', 'outline'):
            return blog_worker.generate(engine, {'title': 'Synthetic'}, 'Outline it', **options)


class StreamedRunsTests(Case):
    def test_claude_code_streams_and_returns_the_same_result_and_usage(self):
        self.agent()
        with blog_worker.metered() as jobs:
            found = self.generate(seconds=10)
        self.assertEqual(found, VALUE)
        self.assertEqual(jobs, [{'tokens': 150, 'dollars': 0.0125}])
        args = json.loads(self.capture.read_text())
        at = args.index('--output-format')
        self.assertEqual(args[at + 1 : at + 3], ['stream-json', '--verbose'])
        [job] = self.log()
        self.assertEqual(
            (job['label'], job['step'], job['outcome']),
            ('Writing the outline', 'outline', 'finished'),
        )
        self.assertEqual(
            [line['text'] for line in job['lines']],
            [
                'Started on synthetic-model',
                'Searching the web: retry budgets',
                'Handing back its answer',
            ],
        )
        self.assertTrue(all(line['at'] for line in job['lines']))
        self.assertEqual(self.running.live('blog-synthetic'), [])

    def test_codex_streams_its_events_and_still_answers_from_its_last_message(self):
        self.agent()
        with blog_worker.metered() as jobs:
            found = self.generate('codex', seconds=10)
        self.assertEqual(found, VALUE)
        self.assertEqual(
            jobs, [{'tokens': None, 'dollars': None}]
        )  # Codex reports none, as before.
        self.assertIn('--json', json.loads(self.capture.read_text()))
        [job] = self.log()
        self.assertEqual(
            [line['text'] for line in job['lines']],
            ['Started', 'Thinking', 'Searching the web: retry budgets'],
        )
        self.assertNotIn('private', json.dumps(job))  # Never what it thought or wrote.

    def test_a_running_job_shows_its_latest_line_and_its_lines_from_since(self):
        self.agent(wait=True)
        done = {}
        thread = threading.Thread(target=lambda: done.update(found=self.generate(seconds=20)))
        thread.start()
        try:
            for _ in range(200):
                shown = self.running.live('blog-synthetic')
                if shown and shown[0]['count']:
                    break
                time.sleep(0.05)
            [worker] = shown
            self.assertEqual(worker['label'], 'Writing the outline')
            self.assertEqual(worker['now']['text'], 'Started on synthetic-model')
            self.assertNotIn('lines', worker)  # A poll stays small.
            lines = self.running.lines('blog-synthetic', worker['id'], 0)
            self.assertEqual(
                [line['text'] for line in lines['lines']], ['Started on synthetic-model']
            )
            self.assertEqual(self.running.lines('blog-synthetic', worker['id'], 1)['lines'], [])
            self.assertEqual(self.running.live('blog-other'), [])  # Another blog's jobs only.
            self.assertEqual(self.log(), [])  # Logged once it ends, not before.
        finally:
            self.release.write_text('go')
            thread.join(20)
        self.assertEqual(done['found'], VALUE)
        self.assertEqual(self.log()[0]['outcome'], 'finished')

    def test_a_failed_result_says_what_it_said_before_and_is_logged_as_failed(self):
        failing = [
            CLAUDE_EVENTS[0],
            {
                'type': 'result',
                'subtype': 'success',
                'is_error': True,
                'result': 'Synthetic failure.',
            },
        ]
        self.agent(claude=failing)
        with self.assertRaises(blog_worker.WorkerFailure) as caught:
            self.generate(seconds=10)
        self.assertIn('could not finish this step', str(caught.exception))
        self.assertIn('Synthetic failure.', caught.exception.said)
        [job] = self.log()
        self.assertEqual(job['outcome'], 'failed')
        self.assertIn('could not finish this step', job['detail'])

    def test_an_account_limit_is_logged_as_a_limit(self):
        limited = [
            CLAUDE_EVENTS[0],
            {'type': 'result', 'subtype': 'error_max_budget_usd', 'is_error': True, 'result': ''},
        ]
        self.agent(claude=limited, code=1)
        with self.assertRaises(blog_worker.WorkerFailure):
            self.generate(seconds=10)
        self.assertEqual(self.log()[0]['outcome'], 'limit')

    def test_codex_error_events_are_its_error_lines_for_a_connection_failure(self):
        failing = [
            CODEX_EVENTS[0],
            {
                'type': 'error',
                'message': 'Reconnecting... 5/5 (stream disconnected '
                'before completion: error sending request)',
            },
            {
                'type': 'turn.failed',
                'error': {
                    'message': 'stream disconnected before completion: error sending request'
                },
            },
        ]
        self.agent(codex=failing, code=1, last=None)
        with patch.object(
            blog_worker, 'unreachable', return_value='Synthetic: unreachable.'
        ) as said:
            with self.assertRaises(blog_worker.WorkerFailure) as caught:
                self.generate('codex', seconds=10)
        self.assertEqual(str(caught.exception), 'Synthetic: unreachable.')
        self.assertEqual(said.call_args.args[-1], 'dropped')
        self.assertTrue(
            any(line.startswith('ERROR: Reconnecting... 5/5') for line in caught.exception.said)
        )
        self.assertEqual(self.log()[0]['outcome'], 'failed')

    def test_out_of_time_and_stop_end_as_they_did_and_are_logged_so(self):
        self.agent(wait=True)
        with self.assertRaises(blog_worker.WorkerFailure) as caught:
            self.generate(seconds=1)
        self.assertEqual(caught.exception.reason, 'time-limit')
        self.assertEqual(self.log()[0]['outcome'], 'timeout')
        stop = threading.Event()
        threading.Timer(0.5, stop.set).start()
        with self.assertRaises(ValueError) as caught:
            self.generate(seconds=20, stop=stop)
        self.assertEqual(str(caught.exception), 'Run stopped. Saved work is kept.')
        self.assertEqual(self.log()[0]['outcome'], 'stopped')

    def test_too_large_a_result_is_refused_as_before(self):
        large = [
            {
                'type': 'result',
                'subtype': 'success',
                'is_error': False,
                'structured_output': {'content': 'x' * 2_100_000, 'notes': ''},
            }
        ]
        self.agent(claude=large)
        with self.assertRaises(ValueError) as caught:
            self.generate(seconds=20)
        self.assertIn('too much text', str(caught.exception))

    def test_outside_a_job_nothing_is_shown_or_kept(self):
        self.agent()
        self.assertEqual(
            blog_worker.generate('claude', {'title': 'x'}, 'Outline', seconds=10), VALUE
        )
        self.assertFalse((self.root / '.blog-runs' / 'activity').exists())


class EngineTests(Case):
    def test_a_run_stage_is_a_job_of_its_blog_in_a_log_git_ignores(self):
        self.agent()
        found = self.create(page=True)
        engine = runner.Engine(self.root)
        self.addCleanup(engine.close)
        engine.control(found['id'], 'resume')
        engine.once(found['id'])
        self.assertEqual(engine.describe(found['id'])['activity'], [])
        subject = blog_activity.blog(found['id'])
        target = blog_activity.path(self.root, subject)
        self.assertEqual(target.relative_to(self.root).parts[:2], ('.blog-runs', 'activity'))
        from studio_sync import gitstate

        self.assertIn('/.blog-runs/', gitstate.IGNORED)  # Never committed or shared.
        shown = management.activity_view(self.root, {'id': [found['id']]})
        [job] = shown['jobs']
        self.assertEqual(
            (job['label'], job['outcome'], job['steps']), ('Writing the outline', 'finished', 3)
        )
        self.assertNotIn('lines', job)
        lines = management.activity_view(self.root, {'id': [found['id']], 'entry': [job['id']]})
        self.assertEqual(len(lines['lines']), 3)
        # Another blog's log is its own.
        self.assertEqual(management.activity_view(self.root, {'id': ['another']})['jobs'], [])

    def test_the_run_view_shows_the_job_while_it_runs(self):
        found = self.create(page=True)
        seen = []

        def worker(*args, stop=None, **kwargs):
            with blog_activity.job(stop) as job:
                job.say('Started on synthetic-model')
                seen.append(engine.describe(found['id'])['activity'])
                return VALUE

        engine = runner.Engine(self.root, worker)
        self.addCleanup(engine.close)
        engine.control(found['id'], 'resume')
        engine.once(found['id'])
        [[worker_shown]] = seen
        self.assertEqual(worker_shown['label'], 'Writing the outline')
        self.assertEqual(worker_shown['now']['text'], 'Started on synthetic-model')
        self.assertEqual(engine.describe(found['id'])['activity'], [])
        self.assertNotIn('activity', engine.describe(found['id'], listing=True))

    def test_a_tool_job_is_a_job_of_its_blog_and_its_own_owner(self):
        found = self.create(page=True)
        ident = 'a' * 32
        tool_jobs.create(
            self.root,
            ident,
            'interview-question',
            {'answers': []},
            'Ask one.',
            None,
            {'article': found['id']},
        )
        seen = []

        def worker(*args, stop=None, **kwargs):
            with blog_activity.job(stop) as job:
                job.say('Thinking')
                running = engine.activity
                seen.append(
                    (
                        running.live(blog_activity.blog(found['id'])),
                        running.live(blog_activity.blog(found['id']), 'b' * 32),
                    )
                )
                return {'content': 'A synthetic question?', 'notes': ''}

        engine = runner.Engine(self.root, worker)
        self.addCleanup(engine.close)
        tool_jobs.once(engine)
        [(mine, others)] = seen
        self.assertEqual(mine[0]['label'], 'Asking an interview question')
        self.assertEqual(others, [])
        [job] = self.log(blog_activity.blog(found['id']))
        self.assertEqual((job['step'], job['outcome']), ('interview-question', 'finished'))

    def test_the_page_reads_a_running_jobs_lines_and_refuses_a_bad_since(self):
        self.agent()
        engine = runner.engine(self.root)
        job = engine.activity.start(
            'workspace', 'Finding where the page gets its text', 'find-text'
        )
        job.say('Started')
        job.say('Thinking')
        found = management.activity_view(self.root, {'job': [job.id], 'since': ['1']})
        self.assertEqual(
            ([line['text'] for line in found['lines']], found['count']), (['Thinking'], 2)
        )
        with self.assertRaises(ValueError):
            management.activity_view(self.root, {'job': [job.id], 'since': ['-1']})
        with self.assertRaises(ValueError):
            management.activity_view(self.root, {'report': ['not-a-report']})
        engine.activity.end(job, 'finished')
        self.assertEqual(
            management.activity_view(self.root, {})['jobs'][0]['label'],
            'Finding where the page gets its text',
        )

    def test_a_log_that_cannot_be_written_never_changes_how_the_job_ended(self):
        self.agent()
        folder = self.root / '.blog-runs' / 'activity'
        folder.mkdir(parents=True)
        os.symlink(self.base / 'elsewhere.jsonl', folder / 'blog-synthetic.jsonl')
        self.assertEqual(self.generate(seconds=10), VALUE)
        self.assertFalse((self.base / 'elsewhere.jsonl').exists())

    def test_forgetting_a_blog_lets_its_log_go(self):
        self.agent()
        self.generate(seconds=10)
        self.assertEqual(len(self.log()), 1)
        blog_activity.forget(self.root, 'blog-synthetic')
        self.assertEqual(self.log(), [])


class ResearchLabelTests(unittest.TestCase):
    def test_each_research_job_is_named_by_its_phase_area_and_round(self):
        import synthesis_research as research

        self.assertEqual(research.phase_words('discovery', 0, {}), 'Finding public sources')
        self.assertEqual(
            research.phase_words('investigate', 1, {'_execution': {'stream': 'area2'}}),
            'Investigating research area 2',
        )
        self.assertEqual(
            research.phase_words('review', 2, {}), 'Checking the research independently, round 2'
        )


if __name__ == '__main__':
    unittest.main()
