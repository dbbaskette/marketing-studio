"""A guided run that stops says what happened and what to do, and keeps what it made.

Research that the independent check refused is kept beside the blog, listed by what the
check objected to, and Try again continues from it. No provider runs: workers and the
research workflow are synthetic.
"""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from test_blog_runner import RunnerCase
import blog_runner as runner
import blog_worker
import synthesis_research
from studio_core import research_contract
from synthesis_fixture import dossier

CONTRACT = {'schema': 2, 'version': '1.0.0', 'digest': 'a' * 64}
DRAFT = '.studio-research-draft'
REFUSED = {
    'facts': [
        {'id': 'fact-a', 'verdict': 'narrow', 'note': 'Only the fictional example says this.'},
        {'id': 'fact-b', 'verdict': 'narrow', 'note': 'Also narrower than the source.'},
        {'id': 'fact-c', 'verdict': 'supported', 'note': 'Matches the capture.'},
    ],
    'findings': [
        {'id': 'instance-min', 'verdict': 'unsupported', 'note': 'No saved fact supports it.'}
    ],
    'prose': [],
    'assessment': {
        'coverage': 'needs-revision',
        'usefulness': 'adequate',
        'note': 'The brief leaves out the strongest objection.',
    },
}
STATE = {'owner': research_contract.OWNER, 'dossier': {'topic': 'Synthetic'}, 'review': REFUSED}


def refused_case(case):
    """What the helper leaves in a case after its last refused round."""
    (case / '.harness-research').mkdir(parents=True, exist_ok=True)
    (case / '.harness-research/synthesis.json').write_text(json.dumps(STATE))
    (case / 'review.json').write_text(json.dumps(REFUSED))


def reviewed_bundle(case):
    """A complete, accepted bundle in a case, as the helper publishes one."""
    folder = case / 'research'
    folder.mkdir(parents=True, exist_ok=True)
    digest = 'd' * 64
    facts = {
        'owner': research_contract.OWNER,
        'schema': 2,
        'digest': digest,
        'status': 'complete',
        'review': {'digest': digest, 'accepted': True},
        'sources': [],
        'facts': [],
        'findings': [],
    }
    files = {
        'report.md': '# Synthetic research\nA reviewed synthetic report.\n',
        'brief.md': '# Brief\nExplain the fictional gateway.\n',
        'evidence.md': '# Evidence\nSynthetic only.\n',
        'facts.json': json.dumps(facts),
    }
    for name, text in files.items():
        (folder / name).write_text(text)
    manifest = {
        'owner': research_contract.OWNER,
        'schema': 2,
        'digest': digest,
        'status': 'complete',
        'artifacts': [
            {'file': name, 'sha256': hashlib.sha256(text.encode()).hexdigest()}
            for name, text in files.items()
        ],
    }
    (folder / 'output.json').write_text(json.dumps(manifest))
    return {'content': files['report.md'], 'notes': 'Synthetic independent review.'}


class ResearchCase(RunnerCase):
    def research_run(self):
        """A page run whose next stage is reviewed research, its plan approved."""
        source = self.source('A fictional gateway routes synthetic requests.')
        with patch.object(runner.research_contract, 'snapshot', return_value=dict(CONTRACT)):
            found = self.create(page=True, research='supplied-only', sources=[source['id']])
        self.assertEqual(found['next'], 'research-plan')
        found = self.approve(self.submit(found, page=True), page=True)
        self.assertEqual(found['next'], 'research')
        return found

    def engine(self):
        engine = runner.Engine(self.root, worker=lambda *a, **k: self.fail('no plain job'))
        self.addCleanup(engine.close)
        return engine


class RefusedResearchTests(ResearchCase):
    def test_a_refused_case_is_kept_listed_by_objection_and_try_again_continues_from_it(self):
        found = self.research_run()
        directory = Path(found['directory'])
        engine = self.engine()

        def refusing(case_root, run, payload, worker, *, seconds, stop, progress=None):
            case = case_root / research_contract.CASE
            refused_case(case)
            raise research_contract.ReviewRefused(research_contract.objections(case), 3)

        engine.control(found['id'], 'resume')
        with patch('synthesis_research.generate', refusing):
            engine._once(found['id'])
        shown = engine.describe(found['id'])
        self.assertEqual(shown['status'], 'failed')
        self.assertEqual(shown['next'], 'research')
        # The stop sentence is true: the draft and the check's notes are kept here.
        self.assertIn('4 objections in 3 groups', shown['error'])
        self.assertIn('kept on this computer', shown['error'])
        self.assertIn('Try again continues from them', shown['error'])
        kept = directory / DRAFT
        self.assertEqual(json.loads((kept / '.harness-research/synthesis.json').read_text()), STATE)
        self.assertEqual(json.loads((kept / 'review.json').read_text()), REFUSED)
        research = shown['research']
        self.assertTrue(research['kept'])
        self.assertEqual(research['refusal']['rounds'], 3)
        self.assertEqual(research['refusal']['count'], 4)
        self.assertEqual(
            [
                (group['kind'], group['verdict'], group['count'], group['note'])
                for group in research['refusal']['groups']
            ],
            [
                ('facts', 'narrow', 2, 'Only the fictional example says this.'),
                ('findings', 'unsupported', 1, 'No saved fact supports it.'),
                (
                    'assessment',
                    'needs-revision',
                    1,
                    'The brief leaves out the strongest objection.',
                ),
            ],
        )
        self.assertEqual(research['refusal']['groups'][2]['asked'], ['coverage'])

        # Try again hands the kept case to the research, which reads the previous dossier
        # and review from it; success publishes the bundle and lets the draft go.
        seen = []

        def continuing(case_root, run, payload, worker, *, seconds, stop, progress=None):
            case = case_root / research_contract.CASE
            seen.append(json.loads((case / '.harness-research/synthesis.json').read_text()))
            return reviewed_bundle(case)

        shown = runner.dispatch(
            self.root, 'retry', {'id': found['id'], 'expected': shown['expected']}
        )
        self.assertEqual(shown['status'], 'queued')
        with patch('synthesis_research.generate', continuing):
            engine._once(found['id'])
        self.assertEqual(seen, [STATE])
        shown = engine.describe(found['id'])
        self.assertEqual(shown['status'], 'waiting-for-approval', shown['error'])
        self.assertEqual(shown['next'], 'research')
        self.assertFalse(kept.exists(), 'a finished research needs no kept draft')
        self.assertIsNone(shown['research'] and shown['research']['refusal'])
        research_contract.read_bundle(directory / 'research')

    def test_the_kept_case_never_reaches_the_team_hub_or_a_shared_folder(self):
        found = self.research_run()
        directory = Path(found['directory'])
        engine = self.engine()

        def refusing(case_root, run, payload, worker, *, seconds, stop, progress=None):
            refused_case(case_root / research_contract.CASE)
            raise research_contract.ReviewRefused([], 3)

        engine.control(found['id'], 'resume')
        with patch('synthesis_research.generate', refusing):
            engine._once(found['id'])
        self.assertTrue((directory / DRAFT / 'review.json').is_file())
        from hub_workspace import Workspace

        shared = Workspace.read_artifacts(None, directory, 'articles')
        self.assertIn('derived/blog-research-plan.md', shared)
        self.assertFalse([name for name in shared if DRAFT in name])
        # In a shared studios repository the blog folder is committed; the kept case is not.
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        listed = subprocess.run(
            ['git', '-C', str(self.root), 'status', '--porcelain', '--untracked-files=all'],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        self.assertIn('derived/blog-run.json', listed)
        self.assertNotIn(DRAFT, listed)

    def test_a_check_that_said_nothing_still_says_what_was_kept(self):
        found = self.research_run()
        engine = self.engine()

        def refusing(case_root, run, payload, worker, *, seconds, stop, progress=None):
            (case_root / research_contract.CASE / '.harness-research').mkdir(parents=True)
            (case_root / research_contract.CASE / '.harness-research/synthesis.json').write_text(
                json.dumps(STATE)
            )
            raise research_contract.ReviewRefused([], 3)

        engine.control(found['id'], 'resume')
        with patch('synthesis_research.generate', refusing):
            engine._once(found['id'])
        shown = engine.describe(found['id'])
        self.assertIn('did not say what', shown['error'])
        self.assertIn('kept on this computer', shown['error'])
        self.assertEqual(shown['research']['refusal']['groups'], [])

    def test_the_cores_own_grouping_and_cause_are_used_when_it_has_them(self):
        found = self.research_run()
        engine = self.engine()

        def refusing(case_root, run, payload, worker, *, seconds, stop, progress=None):
            refused_case(case_root / research_contract.CASE)
            refusal = research_contract.ReviewRefused(['one (narrow): a note'], 3)
            refusal.groups = [
                {'kind': 'facts', 'verdict': 'narrow', 'count': 7, 'note': 'From the core.'}
            ]
            refusal.cause = 'The check could not read the original of "Synthetic".'
            raise refusal

        engine.control(found['id'], 'resume')
        with patch('synthesis_research.generate', refusing):
            engine._once(found['id'])
        shown = engine.describe(found['id'])
        self.assertEqual(
            [(g['kind'], g['count'], g['note']) for g in shown['research']['refusal']['groups']],
            [('facts', 7, 'From the core.')],
        )
        self.assertEqual(
            shown['research']['refusal']['cause'],
            'The check could not read the original of "Synthetic".',
        )
        self.assertIn('could not read the original', shown['error'])

    def test_research_that_stopped_partway_keeps_its_draft_too(self):
        found = self.research_run()
        directory = Path(found['directory'])
        engine = self.engine()

        def timing_out(case_root, run, payload, worker, *, seconds, stop, progress=None):
            refused_case(case_root / research_contract.CASE)
            raise ValueError('Research ran out of the time a step may take (10 minutes).')

        engine.control(found['id'], 'resume')
        with patch('synthesis_research.generate', timing_out):
            engine._once(found['id'])
        shown = engine.describe(found['id'])
        self.assertTrue((directory / DRAFT / '.harness-research/synthesis.json').is_file())
        self.assertTrue(shown['research']['kept'])
        self.assertIn('kept on this computer', shown['error'])
        self.assertIsNone(shown['research']['refusal'])

    def test_nothing_is_claimed_kept_when_research_saved_nothing(self):
        found = self.research_run()
        directory = Path(found['directory'])
        engine = self.engine()

        def failing(case_root, run, payload, worker, *, seconds, stop, progress=None):
            raise ValueError('Research source discovery returned an invalid source list.')

        engine.control(found['id'], 'resume')
        with patch('synthesis_research.generate', failing):
            engine._once(found['id'])
        shown = engine.describe(found['id'])
        self.assertFalse((directory / DRAFT).exists())
        self.assertNotIn('kept on this computer', shown['error'])
        self.assertFalse(shown['research']['kept'])


class FakeWorkflow:
    """The shared contract's loop over synthesis_research's own invoke, with no helper: an
    author and an independent check each round, then a refusal after `rounds` rounds."""

    rounds = 2

    def __init__(self, runtime=None, call=None):
        pass

    def command(self, case, action, file=None, worker=None):
        return {}

    def run(self, root, task, invoke, sources=()):
        case = Path(root) / research_contract.CASE
        case.mkdir(parents=True, exist_ok=True)
        for _ in range(self.rounds):
            author = {'task': task, 'worker': 'author-' + 'a' * 24}
            invoke('author', 'Synthetic author guidance.', author, sources, False)
            check = {'task': task, 'worker': 'reviewer-' + 'b' * 24, 'review_template': {}}
            invoke('review', 'Synthetic check guidance.', check, sources, False)
        refused_case(case)
        raise research_contract.ReviewRefused(research_contract.objections(case), self.rounds)


def research_worker(during=None):
    """A worker that answers the author with a dossier citing the capture it was shown and
    the check with a review, reporting tokens and cost as a CLI would."""

    def worker(engine, data, guidance, **options):
        if during:
            during(data)
        blog_worker.reported(1000, 0.01)
        if 'review_template' in data:
            return {'content': json.dumps(REFUSED), 'notes': ''}
        capture = data['sources'][0]
        value = dossier(data['worker'], capture['file'], capture['origin'], 'selected')
        return {'content': json.dumps(value), 'notes': ''}

    return worker


class ResearchRoundTests(ResearchCase):
    def setUp(self):
        super().setUp()
        for patcher in (
            patch.object(research_contract, 'Workflow', FakeWorkflow),
            patch.object(research_contract, 'runtime_for', lambda saved, runtime=None: '/x'),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_research_says_its_round_and_records_each_job(self):
        found = self.research_run()
        directory, _, run = runner.load(self.root, found['id'])
        _, payload, _ = runner.job(self.root, found['id'])
        events = []
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(research_contract.ReviewRefused):
                synthesis_research.generate(
                    Path(temp),
                    run,
                    payload,
                    research_worker(),
                    seconds=60,
                    stop=threading.Event(),
                    progress=events.append,
                )
        rounds = [(e['round'], e['phase']) for e in events if 'job' not in e]
        self.assertEqual(rounds, [(1, 'author'), (1, 'review'), (2, 'author'), (2, 'review')])
        jobs = [e['job'] for e in events if 'job' in e]
        self.assertEqual(
            [(j['round'], j['phase'], j['outcome']) for j in jobs],
            [
                (1, 'author', 'kept'),
                (1, 'review', 'kept'),
                (2, 'author', 'kept'),
                (2, 'review', 'kept'),
            ],
        )
        self.assertTrue(all(j['tokens'] == 1000 and j['dollars'] == 0.01 for j in jobs))
        self.assertTrue(all(isinstance(j['seconds'], float) for j in jobs))

    def test_the_run_shows_the_round_under_way_and_what_the_last_attempt_took(self):
        found = self.research_run()
        engine = self.engine()
        seen = []
        engine.worker = research_worker(
            during=lambda data: seen.append(engine.describe(found['id']))
        )
        engine.control(found['id'], 'resume')
        engine._once(found['id'])
        self.assertEqual(
            [(s['status'], s['research']['round'], s['research']['phase']) for s in seen],
            [
                ('working', 1, 'author'),
                ('working', 1, 'review'),
                ('working', 2, 'author'),
                ('working', 2, 'review'),
            ],
        )
        self.assertEqual(seen[0]['research']['rounds'], 3)
        shown = engine.describe(found['id'])
        self.assertEqual(shown['status'], 'failed')
        self.assertIsNone(shown['research']['round'], 'no round is under way after a stop')
        last = shown['research']['last']
        self.assertEqual(
            (last['jobs'], last['rounds'], last['tokens'], last['dollars']), (4, 2, 4000, 0.04)
        )
        self.assertIsInstance(last['seconds'], float)
        # Try again starts a new attempt: what it took replaces the last one's figures.
        FakeWorkflow.rounds = 1
        self.addCleanup(setattr, FakeWorkflow, 'rounds', 2)
        runner.dispatch(self.root, 'retry', {'id': found['id'], 'expected': shown['expected']})
        engine._once(found['id'])
        last = engine.describe(found['id'])['research']['last']
        self.assertEqual((last['jobs'], last['rounds'], last['tokens']), (2, 1, 2000))

    def test_a_cli_that_reports_nothing_leaves_tokens_and_cost_unsaid(self):
        found = self.research_run()
        engine = self.engine()

        def quiet(engine_name, data, guidance, **options):
            if 'review_template' in data:
                return {'content': json.dumps(REFUSED), 'notes': ''}
            capture = data['sources'][0]
            value = dossier(data['worker'], capture['file'], capture['origin'], 'selected')
            return {'content': json.dumps(value), 'notes': ''}

        engine.worker = quiet
        engine.control(found['id'], 'resume')
        engine._once(found['id'])
        last = engine.describe(found['id'])['research']['last']
        self.assertEqual((last['jobs'], last['tokens'], last['dollars']), (4, None, None))


class MeteredWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.binary = Path(self.temp.name) / 'fixture-agent'
        environment = patch.dict(
            os.environ, {'STUDIOS_CONFIG': str(Path(self.temp.name) / 'shared.json')}
        )
        environment.start()
        self.addCleanup(environment.stop)

    def executable(self, body):
        self.binary.write_text(
            '#!' + sys.executable + '\nimport sys,json\nfrom pathlib import Path\n' + body
        )
        self.binary.chmod(0o700)

    def generate(self, agent):
        with (
            patch.object(blog_worker.source_curator, 'executable', return_value=str(self.binary)),
            patch.object(blog_worker.source_curator, 'codex_options', return_value=[]),
        ):
            return blog_worker.generate(agent, {}, 'Synthetic job', seconds=5)

    def test_the_cli_reports_tokens_and_cost_where_it_says_them(self):
        self.executable(
            'args=sys.argv[1:]\n'
            "value={'content':'# Synthetic','notes':'Fixture CLI; no account.'}\n"
            "if '--output-last-message' in args:\n"
            " Path(args[args.index('--output-last-message')+1]).write_text(json.dumps(value))\n"
            'else:\n'
            " print(json.dumps({'structured_output':value,'total_cost_usd':0.0125,"
            "'usage':{'input_tokens':100,'cache_read_input_tokens':900,"
            "'cache_creation_input_tokens':0,'output_tokens':50}}))\n"
        )
        with blog_worker.metered() as jobs:
            self.generate('claude')
            self.generate('codex')
        self.assertEqual(
            jobs, [{'tokens': 1050, 'dollars': 0.0125}, {'tokens': None, 'dollars': None}]
        )
        self.generate('claude')  # Outside a metered block nothing is kept.
        self.assertEqual(len(jobs), 2)


class StageMeterTests(ResearchCase):
    """Every stage job is metered through the real worker, with a scripted CLI in place of
    the assistant: its seconds, and the tokens and dollars it reported, kept on this
    computer's run state. Nothing real runs."""

    def setUp(self):
        super().setUp()
        self.binary = self.base / 'fixture-agent'
        self.binary.write_text(
            '#!' + sys.executable + '\nimport sys,json,time\nfrom pathlib import Path\n'
            'time.sleep(0.05)\n'
            'args=sys.argv[1:]\n'
            "value={'content':'# Outline\\nSynthetic.','notes':'Fixture CLI; no account.'}\n"
            "if '--output-last-message' in args:\n"
            " Path(args[args.index('--output-last-message')+1]).write_text(json.dumps(value))\n"
            'else:\n'
            " print(json.dumps({'structured_output':value,'total_cost_usd':0.42,"
            "'usage':{'input_tokens':100,'output_tokens':50}}))\n"
        )
        self.binary.chmod(0o700)
        for patcher in (
            patch.object(blog_worker.source_curator, 'executable', return_value=str(self.binary)),
            patch.object(blog_worker.source_curator, 'codex_options', return_value=[]),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_every_stage_job_is_metered(self):
        for agent, dollars in (('claude', 0.42), ('codex', None)):
            with self.subTest(agent=agent):
                found = self.create(page=True, stop='draft', engine=agent, title='Metered ' + agent)
                engine = runner.Engine(self.root, worker=blog_worker.generate)
                self.addCleanup(engine.close)
                engine.control(found['id'], 'resume')
                engine._once(found['id'])
                job = engine.local(found['id'])['jobs'][-1]
                self.assertEqual((job['stage'], job['dollars']), ('outline', dollars))
                self.assertGreater(job['seconds'], 0)
                ahead = engine.describe(found['id'])['ahead']
                self.assertEqual(ahead['jobs'], 1)
                self.assertEqual(ahead['dollars'], dollars)
                self.assertTrue(ahead['spent'].endswith(
                    'and about $0.42' if dollars else '; the assistant reported no cost'),
                    ahead['spent'])


class ContinueWithoutResearchTests(ResearchCase):
    def stopped_at_research(self):
        found = self.research_run()
        engine = self.engine()

        def refusing(case_root, run, payload, worker, *, seconds, stop, progress=None):
            refused_case(case_root / research_contract.CASE)
            raise research_contract.ReviewRefused(
                research_contract.objections(case_root / research_contract.CASE), 3
            )

        engine.control(found['id'], 'resume')
        with patch('synthesis_research.generate', refusing):
            engine._once(found['id'])
        return engine, engine.describe(found['id'])

    def test_the_outline_then_runs_without_research_and_the_run_says_so(self):
        engine, shown = self.stopped_at_research()
        directory = Path(shown['directory'])
        self.assertTrue((directory / DRAFT).is_dir())
        shown = runner.dispatch(
            self.root, 'skip-research', {'id': shown['id'], 'expected': shown['expected']}
        )
        self.assertEqual(
            [row['stage'] for row in shown['stages']], ['outline', 'draft', 'review', 'package']
        )
        self.assertEqual(shown['next'], 'outline')
        self.assertEqual(shown['status'], 'queued', 'it resumes')
        self.assertEqual(shown['error'], '')
        self.assertIsNone(shown['research'])
        self.assertEqual(shown['decisions'][-1]['event'], 'Continued without research')
        self.assertFalse((directory / DRAFT).exists(), 'the kept research draft is let go')
        _, record, run = runner.load(self.root, shown['id'])
        self.assertEqual(run['pipeline'], ['outline', 'draft', 'review', 'package'])
        self.assertNotIn('research', run['stages'])
        self.assertNotIn('research-plan', run['stages'])
        self.assertEqual(run['research_skipped']['from'], 'research')
        self.assertEqual(record['research_policy'], 'supplied-only', 'the blog keeps its policy')
        # The later stages get no bundle and are told there is none.
        _, payload, guidance = runner.job(self.root, shown['id'])
        self.assertNotIn('research_bundle', payload)
        self.assertEqual(payload['research_policy'], 'none')
        self.assertIn('continued without research', guidance)
        seen = []

        def worker(*args, **kwargs):
            seen.append(args[1])
            return {'content': '# Outline\nSynthetic writing.', 'notes': 'Synthetic.'}

        engine.worker = worker
        engine._once(shown['id'])
        shown = engine.describe(shown['id'])
        self.assertEqual(shown['next'], 'outline')
        self.assertEqual(shown['status'], 'waiting-for-approval', shown['error'])
        self.assertNotIn('research_bundle', seen[0])
        self.assertEqual(seen[0]['research_policy'], 'none')

    def test_research_questions_that_failed_can_be_skipped_too(self):
        found = self.research_run()
        engine = self.engine()
        # Back to the plan: ask for changes, then let its job fail.
        found = runner.decide(
            self.root,
            found['id'],
            found['expected'],
            'changes',
            'Narrow it.',
            True,
            'research-plan',
        )
        engine.keep_local(
            found['id'], {'enabled': False, 'status': 'failed', 'error': 'The selected CLI failed.'}
        )
        shown = engine.describe(found['id'])
        self.assertEqual(shown['next'], 'research-plan')
        shown = runner.dispatch(
            self.root, 'skip-research', {'id': shown['id'], 'expected': shown['expected']}
        )
        self.assertEqual(shown['next'], 'outline')
        self.assertEqual(
            runner.load(self.root, shown['id'])[2]['research_skipped']['from'], 'research-plan'
        )

    def test_it_is_refused_away_from_research_while_working_and_from_chat(self):
        found = self.create(page=True)
        with self.assertRaisesRegex(ValueError, 'not waiting on research'):
            runner.dispatch(
                self.root, 'skip-research', {'id': found['id'], 'expected': found['expected']}
            )
        engine, shown = self.stopped_at_research()
        engine.current = shown['id']
        self.addCleanup(setattr, engine, 'current', None)
        runner.ENGINES[str(self.root)] = engine
        with self.assertRaisesRegex(ValueError, 'Stop the research first'):
            runner.dispatch(
                self.root, 'skip-research', {'id': shown['id'], 'expected': shown['expected']}
            )
        engine.current = None
        chat = runner.decide(self.root, shown['id'], shown['expected'], 'handoff', page=True)
        with self.assertRaisesRegex(ValueError, 'decided in chat'):
            runner.dispatch(
                self.root, 'skip-research', {'id': chat['id'], 'expected': chat['expected']}
            )


class WorkerFailureTests(MeteredWorkerTests):
    def test_a_failed_cli_names_status_and_keeps_its_last_twenty_lines(self):
        self.executable(
            "for n in range(25):\n print('synthetic stderr line', n, file=sys.stderr)\nsys.exit(1)\n"
        )
        for agent in ('codex', 'claude'):
            with self.subTest(agent=agent), self.assertRaises(blog_worker.WorkerFailure) as caught:
                self.generate(agent)
            self.assertEqual(caught.exception.reason, 'cli')
            self.assertIn('Status → Check this computer', str(caught.exception))
            self.assertEqual(
                caught.exception.said, ['synthetic stderr line ' + str(n) for n in range(5, 25)]
            )

    def test_a_cli_that_reports_an_error_says_it(self):
        self.executable(
            "print(json.dumps({'is_error': True, 'result': 'Synthetic usage limit reached.'}))\n"
        )
        with self.assertRaises(blog_worker.WorkerFailure) as caught:
            self.generate('claude')
        self.assertEqual(caught.exception.reason, 'cli')
        self.assertIn('Status → Check this computer', str(caught.exception))
        self.assertEqual(caught.exception.said, ['Synthetic usage limit reached.'])

    def test_an_unreadable_answer_names_status_too(self):
        self.executable(
            "print('not the JSON the schema asks for')\nprint('stderr detail', file=sys.stderr)\n"
        )
        with self.assertRaises(blog_worker.WorkerFailure) as caught:
            self.generate('claude')
        self.assertIn('did not return a readable document', str(caught.exception))
        self.assertIn('Status → Check this computer', str(caught.exception))
        self.assertEqual(caught.exception.said, ['stderr detail'])

    def test_a_step_out_of_time_says_how_long_a_step_may_take(self):
        self.executable('import time\ntime.sleep(30)\n')
        with (
            patch.object(blog_worker.source_curator, 'executable', return_value=str(self.binary)),
            self.assertRaises(blog_worker.WorkerFailure) as caught,
        ):
            blog_worker.generate('claude', {}, 'Synthetic', seconds=1)
        self.assertEqual(caught.exception.reason, 'time-limit')
        self.assertEqual(
            str(caught.exception), 'This step ran out of the time a step may take (1 second).'
        )
        self.assertEqual(
            [blog_worker.minutes(value) for value in (30, 60, 90, 600, 3600)],
            ['30 seconds', '1 minute', '1.5 minutes', '10 minutes', '60 minutes'],
        )


class RunFailureTests(ResearchCase):
    def failing(self, error):
        def worker(*args, **kwargs):
            raise error

        return worker

    def test_a_cli_failure_keeps_what_the_assistant_said_on_this_computer_only(self):
        found = self.create(page=True, stop='draft')
        engine = self.engine()
        engine.worker = self.failing(
            blog_worker.WorkerFailure(
                'The selected CLI failed. Check its sign-in and usage under Status → Check this '
                'computer, then try again.',
                'cli',
                ['Synthetic: not signed in.', 'Synthetic: run the login command.'],
            )
        )
        engine.control(found['id'], 'resume')
        engine._once(found['id'])
        shown = engine.describe(found['id'])
        self.assertEqual(shown['status'], 'failed')
        self.assertEqual(shown['reason'], 'cli')
        self.assertIn('Status → Check this computer', shown['error'])
        self.assertEqual(
            shown['said'], ['Synthetic: not signed in.', 'Synthetic: run the login command.']
        )
        kept = self.root / '.blog-runs' / 'diagnostics' / 'cli' / (found['id'] + '.json')
        self.assertEqual(kept.stat().st_mode & 0o777, 0o600)
        self.assertEqual(kept.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(json.loads(kept.read_text())['stage'], 'outline')
        directory = Path(shown['directory'])
        self.assertFalse(
            [
                path
                for path in directory.rglob('*')
                if path.is_file() and 'not signed in' in path.read_text(errors='ignore')
            ],
            'nothing the assistant said is kept with the blog',
        )
        from hub_workspace import Workspace

        shared = Workspace.read_artifacts(None, directory, 'articles')
        self.assertFalse(
            [
                name
                for name in shared
                if 'not signed in' in (directory / name).read_text(errors='ignore')
            ]
        )
        # The next job's start lets the old lines go; what it says replaces them.
        engine.worker = lambda *a, **k: {'content': '# Outline\nSynthetic.', 'notes': 'Synthetic.'}
        runner.dispatch(self.root, 'retry', {'id': found['id'], 'expected': shown['expected']})
        engine._once(found['id'])
        shown = engine.describe(found['id'])
        self.assertIsNone(shown['said'])
        self.assertIsNone(shown['reason'])
        self.assertFalse(kept.exists())

    def test_deleting_the_blog_removes_what_the_assistant_said(self):
        found = self.create(page=True, stop='draft')
        engine = self.engine()
        runner.ENGINES[str(self.root)] = engine
        engine.worker = self.failing(
            blog_worker.WorkerFailure('The selected CLI failed.', 'cli', ['x'])
        )
        engine.control(found['id'], 'resume')
        engine._once(found['id'])
        kept = self.root / '.blog-runs' / 'diagnostics' / 'cli' / (found['id'] + '.json')
        self.assertTrue(kept.is_file())
        import blog_delete

        shown = engine.describe(found['id'])
        blog_delete.delete(
            self.root, {'id': found['id'], 'expected': shown['expected'], 'title': shown['title']}
        )
        self.assertFalse(kept.exists())

    def test_a_step_out_of_time_says_the_limit_this_blog_has(self):
        found = self.create(page=True, stop='draft')
        engine = self.engine()
        engine.worker = self.failing(
            blog_worker.WorkerFailure(
                'This step ran out of the time a step may take (3 seconds).', 'time-limit'
            )
        )
        engine.control(found['id'], 'resume')
        engine._once(found['id'])
        shown = engine.describe(found['id'])
        self.assertEqual(shown['reason'], 'time-limit')
        self.assertEqual(
            shown['error'], 'This step ran out of the time a step may take (10 minutes).'
        )
        self.assertIsNone(shown['said'], 'nothing kept when nothing was said')

    def test_research_out_of_time_says_so_and_keeps_its_draft(self):
        found = self.research_run()
        engine = self.engine()

        def timing_out(case_root, run, payload, worker, *, seconds, stop, progress=None):
            refused_case(case_root / research_contract.CASE)
            raise blog_worker.WorkerFailure(
                'Research ran out of the time a step may take.', 'time-limit'
            )

        engine.control(found['id'], 'resume')
        with patch('synthesis_research.generate', timing_out):
            engine._once(found['id'])
        shown = engine.describe(found['id'])
        self.assertEqual(shown['reason'], 'time-limit')
        self.assertTrue(
            shown['error'].startswith('Research ran out of the time a step may take (10 minutes).'),
            shown['error'],
        )
        self.assertIn('kept on this computer', shown['error'])

    def test_research_itself_stops_at_the_steps_limit(self):
        found = self.research_run()
        directory, _, run = runner.load(self.root, found['id'])
        _, payload, _ = runner.job(self.root, found['id'])
        with (
            patch.object(research_contract, 'Workflow', FakeWorkflow),
            patch.object(research_contract, 'runtime_for', lambda saved, runtime=None: '/x'),
            tempfile.TemporaryDirectory() as temp,
            self.assertRaises(blog_worker.WorkerFailure) as caught,
        ):
            synthesis_research.generate(
                Path(temp), run, payload, research_worker(), seconds=0, stop=threading.Event()
            )
        self.assertEqual(caught.exception.reason, 'time-limit')
        self.assertIn('ran out of the time a step may take', str(caught.exception))


class MissingAssistantTests(MeteredWorkerTests):
    """An assistant that is not installed or cannot start points at Status, like any CLI
    failure, and never says "analysis" in a writing step."""

    def assertPointsAtStatus(self, caught, name):
        self.assertEqual(caught.exception.reason, 'cli')
        self.assertEqual(
            str(caught.exception),
            name + ' is not installed or cannot start here. Check it under Status → Check '
            'this computer, then try again.',
        )

    def test_a_missing_cli_points_at_status(self):
        for agent, name in (('codex', 'Codex'), ('claude', 'Claude Code')):
            with (
                self.subTest(agent=agent),
                patch('computer.cli_path', return_value=None),
                self.assertRaises(blog_worker.WorkerFailure) as caught,
            ):
                blog_worker.generate(agent, {'x': 1}, 'Synthetic job', seconds=5)
            self.assertPointsAtStatus(caught, name)

    def test_a_cli_that_cannot_start_points_at_status(self):
        missing = str(Path(self.temp.name) / 'no-such-agent')
        with (
            patch.object(blog_worker.source_curator, 'executable', return_value=missing),
            patch.object(blog_worker.source_curator, 'codex_options', return_value=[]),
            self.assertRaises(blog_worker.WorkerFailure) as caught,
        ):
            blog_worker.generate('claude', {}, 'Synthetic job', seconds=5)
        self.assertPointsAtStatus(caught, 'Claude Code')

    def test_a_codex_profile_it_cannot_use_points_at_status(self):
        self.executable('print("unused")\n')
        with (
            patch.object(blog_worker.source_curator, 'executable', return_value=str(self.binary)),
            patch.object(
                blog_worker.source_curator,
                'codex_options',
                side_effect=ValueError('Select a direct model configuration.'),
            ),
            self.assertRaises(blog_worker.WorkerFailure) as caught,
        ):
            blog_worker.generate('codex', {}, 'Synthetic job', seconds=5)
        self.assertPointsAtStatus(caught, 'Codex')


class MissingAssistantRunTests(ResearchCase):
    def test_the_run_offers_status_for_an_assistant_that_is_not_installed(self):
        found = self.create(page=True, stop='draft')
        engine = runner.Engine(self.root, worker=blog_worker.generate)
        self.addCleanup(engine.close)
        engine.control(found['id'], 'resume')
        with patch('computer.cli_path', return_value=None):
            engine._once(found['id'])
        shown = engine.describe(found['id'])
        self.assertEqual(shown['status'], 'failed')
        self.assertEqual(shown['reason'], 'cli')
        self.assertIn('is not installed or cannot start here', shown['error'])
        self.assertNotIn('analysis', shown['error'])


PRIVATE = 'PRIVATE SOURCE TEXT about a fictional gateway that must stay on this computer'
TOKEN = 'sk-synthetic-0123456789abcdef'


class SaidTests(MeteredWorkerTests):
    """What the assistant said keeps its own errors, never the job it was given or a secret."""

    def failing_cli(self, after=''):
        # Like `codex exec`: the prompt read from stdin is echoed in a `user` block, then the
        # CLI's own lines, a bearer token among them, then an error.
        self.executable(
            'data=sys.stdin.read()\n'
            "print('user', file=sys.stderr)\n"
            'print(data, file=sys.stderr)\n'
            "print('Authorization: Bearer " + TOKEN + "', file=sys.stderr)\n"
            "print('thinking', file=sys.stderr)\n"
            "print('retrying with Authorization: Bearer " + TOKEN + "', file=sys.stderr)\n"
            "print('debug: ' + " + repr(PRIVATE[5:60]) + ', file=sys.stderr)\n'
            "print('ERROR: synthetic sign-in expired', file=sys.stderr)\n" + after + 'sys.exit(1)\n'
        )

    def said(self, agent='codex', seconds=5):
        with (
            patch.object(blog_worker.source_curator, 'executable', return_value=str(self.binary)),
            patch.object(blog_worker.source_curator, 'codex_options', return_value=[]),
            self.assertRaises(blog_worker.WorkerFailure) as caught,
        ):
            blog_worker.generate(
                agent, {'sources': [{'text': PRIVATE}]}, 'Synthetic job', seconds=seconds
            )
        return caught.exception

    def test_the_job_and_its_secrets_never_reach_what_the_assistant_said(self):
        for agent in ('codex', 'claude'):
            with self.subTest(agent=agent):
                self.failing_cli()
                said = self.said(agent).said
                text = '\n'.join(said)
                for kept_out in ('DOCUMENT DATA', 'Do the job in your instructions', TOKEN):
                    self.assertNotIn(kept_out, text)
                self.assertNotIn(PRIVATE[10:50], text)
                self.assertIn('ERROR: synthetic sign-in expired', said)
                self.assertIn('retrying with Authorization: Bearer [redacted]', said)

    def test_a_step_out_of_time_keeps_nothing_it_said(self):
        self.executable(
            "print('synthetic progress', file=sys.stderr, flush=True)\nimport time\ntime.sleep(30)\n"
        )
        failure = self.said('claude', seconds=1)
        self.assertEqual(failure.reason, 'time-limit')
        self.assertEqual(failure.said, [])


class KeptSaidTests(ResearchCase):
    def run_failing(self, failure):
        found = self.create(page=True, stop='draft')
        engine = self.engine()

        def worker(*args, **kwargs):
            raise failure

        engine.worker = worker
        engine.control(found['id'], 'resume')
        engine._once(found['id'])
        return engine.describe(found['id'])

    def test_what_is_kept_is_redacted_again_and_never_echoes_the_prompt(self):
        shown = self.run_failing(
            blog_worker.WorkerFailure(
                'The selected CLI failed.',
                'cli',
                ['token: Bearer ' + TOKEN, 'DOCUMENT DATA:', 'ERROR: synthetic sign-in expired'],
            )
        )
        kept = (
            self.root / '.blog-runs' / 'diagnostics' / 'cli' / (shown['id'] + '.json')
        ).read_text()
        for place in (kept, json.dumps(shown['said'])):
            self.assertNotIn(TOKEN, place)
            self.assertNotIn('DOCUMENT DATA', place)
        self.assertEqual(
            shown['said'], ['token: Bearer [redacted]', 'ERROR: synthetic sign-in expired']
        )

    def test_only_a_cli_failure_keeps_what_was_said(self):
        shown = self.run_failing(
            blog_worker.WorkerFailure('This step ran out of time.', 'time-limit', ['progress'])
        )
        self.assertIsNone(shown['said'])
        self.assertFalse((self.root / '.blog-runs' / 'diagnostics' / 'cli').exists())


class DraftTieTests(ResearchCase):
    """The kept draft belongs to the research stage it came from: its inputs and its saved
    version. Research saved any other way, or changed inputs, let it go."""

    def refused(self):
        found = self.research_run()
        engine = self.engine()

        def refusing(case_root, run, payload, worker, *, seconds, stop, progress=None):
            refused_case(case_root / research_contract.CASE)
            raise research_contract.ReviewRefused([], 3)

        engine.control(found['id'], 'resume')
        with patch('synthesis_research.generate', refusing):
            engine._once(found['id'])
        directory = Path(found['directory'])
        self.assertTrue((directory / DRAFT).is_dir())
        return engine, found['id'], directory

    def resumed_from(self, engine, ident):
        """The synthesis state the next research attempt starts from, or None."""
        seen = []

        def recording(case_root, run, payload, worker, *, seconds, stop, progress=None):
            state = case_root / research_contract.CASE / '.harness-research/synthesis.json'
            seen.append(json.loads(state.read_text()) if state.is_file() else None)
            names = {path.name for path in (case_root / research_contract.CASE).glob('*')}
            seen.append(names)
            raise ValueError('Synthetic stop after reading the case.')

        shown = engine.describe(ident)
        runner.dispatch(self.root, 'retry', {'id': ident, 'expected': shown['expected']})
        with patch('synthesis_research.generate', recording):
            engine._once(ident)
        return seen

    def test_research_accepted_another_way_wins_over_a_stale_draft(self):
        engine, ident, directory = self.refused()
        # Accepted elsewhere (chat, another computer): a newer case and bundle, submitted here.
        case = directory / research_contract.CASE
        (case / '.harness-research').mkdir(parents=True, exist_ok=True)
        accepted = {'owner': research_contract.OWNER, 'dossier': {'topic': 'ACCEPTED'}}
        (case / '.harness-research/synthesis.json').write_text(json.dumps(accepted))
        result = reviewed_bundle(case)
        research_contract.publish(case, directory / 'research')
        shown = runner.survey(self.root, ident)
        shown = runner.submit(self.root, ident, 'research', result, shown['expected'], page=True)
        self.assertFalse((directory / DRAFT).exists(), 'a saved research lets the draft go')
        shown = runner.decide(self.root, ident, shown['expected'], 'approve', page=True)
        shown = runner.decide(
            self.root, ident, shown['expected'], 'changes', 'Tighten it.', True, 'research'
        )
        self.assertEqual(engine.describe(ident)['research']['from'], 'accepted')
        state, _ = self.resumed_from(engine, ident)
        self.assertEqual(state['dossier']['topic'], 'ACCEPTED')

    def test_a_draft_whose_research_was_saved_elsewhere_is_let_go_here(self):
        engine, ident, directory = self.refused()
        # Another computer saved and shared the research, then asked for changes to it: its
        # case and bundle arrive with a new research version, and this computer's draft
        # (never shared) is still on disk.
        case = directory / research_contract.CASE
        (case / '.harness-research').mkdir(parents=True, exist_ok=True)
        elsewhere = {'owner': research_contract.OWNER, 'dossier': {'topic': 'ELSEWHERE'}}
        (case / '.harness-research/synthesis.json').write_text(json.dumps(elsewhere))
        result = reviewed_bundle(case)
        research_contract.publish(case, directory / 'research')
        _, record, run = runner.load(self.root, ident)
        run['stages']['research'] = {
            'status': 'pending',
            'hash': runner.studio.digest(result['content'].encode()),
            'request': 'Again.',
        }
        runner.save(self.root, directory, record, run, 'Synthetic research saved elsewhere')
        shown = engine.describe(ident)
        self.assertFalse(shown['research']['kept'], 'the page does not promise the draft')
        self.assertEqual(shown['research']['from'], 'accepted')
        self.assertTrue(runner.survey(self.root, ident)['research_contract'])
        state, _ = self.resumed_from(engine, ident)
        self.assertEqual(state['dossier']['topic'], 'ELSEWHERE', 'the stale draft is not used')
        # What that attempt kept is its own case, tied to the research version it ran for.
        kept = json.loads((directory / DRAFT / '.harness-research/synthesis.json').read_text())
        self.assertEqual(kept['dossier']['topic'], 'ELSEWHERE')
        self.assertTrue(engine.describe(ident)['research']['kept'])

    def test_a_changed_brief_or_sources_lets_the_draft_go(self):
        for change in ('brief', 'sources'):
            with self.subTest(change=change):
                engine, ident, directory = self.refused()
                _, record, run = runner.load(self.root, ident)
                if change == 'brief':
                    run['brief']['goal'] = 'Explain a different fictional gateway'
                else:
                    extra = self.source('A second synthetic source about the gateway.')
                    _, source = runner.studio.item(self.root, 'sources', extra['id'])
                    record['sources'].append(
                        {
                            'source_id': extra['id'],
                            'revision': source['revision'],
                            'purposes': ['reference'],
                        }
                    )
                runner.save(self.root, directory, record, run, 'Synthetic change: ' + change)
                # New inputs bring the approved research plan back for review first.
                shown = engine.describe(ident)
                self.assertEqual(shown['next'], 'research-plan')
                self.assertFalse(shown['research']['kept'])
                shown = runner.dispatch(
                    self.root, 'adopt', {'id': ident, 'expected': shown['expected']}
                )
                shown = self.approve(shown, page=True)
                self.assertEqual(shown['next'], 'research')
                self.assertTrue((directory / DRAFT).exists(), 'still on disk until research runs')
                state, _ = self.resumed_from(engine, ident)
                self.assertIsNone(state)
                self.assertFalse((directory / DRAFT).exists())

    def test_the_draft_is_private_and_its_tie_stays_out_of_the_case(self):
        engine, ident, directory = self.refused()
        kept = directory / DRAFT
        self.assertEqual(kept.stat().st_mode & 0o777, 0o700)
        for path in kept.rglob('*'):
            self.assertEqual(path.stat().st_mode & 0o777, 0o700 if path.is_dir() else 0o600, path)
        self.assertTrue((kept / 'kept.json').is_file())
        self.assertEqual(engine.describe(ident)['research']['from'], 'kept')
        state, names = self.resumed_from(engine, ident)
        self.assertEqual(state, STATE)
        self.assertFalse({'kept.json', '.gitignore'} & names, names)

    def test_leftovers_are_swept_and_a_failed_keep_lets_an_older_draft_go(self):
        engine, ident, directory = self.refused()
        leftover = directory / (DRAFT + '-' + 'f' * 32)
        leftover.mkdir()
        (leftover / 'review.json').write_text('{}')
        with patch.object(
            runner.research_contract, 'copy_case', side_effect=OSError('synthetic disk full')
        ):
            kept = runner.keep_research(
                directory, directory / DRAFT, runner.survey(self.root, ident)['research_tie']
            )
        self.assertEqual(kept, 'synthetic disk full')
        self.assertFalse(leftover.exists(), 'a leftover from an interrupted keep is swept')
        self.assertFalse((directory / DRAFT).exists(), 'no older draft makes the message untrue')
        self.assertFalse(list(directory.glob(DRAFT + '-*')))


class MinorReviewTests(ResearchCase):
    def test_a_refusal_counts_rounds_of_writing_and_checking(self):
        refusal = runner.research_refusal(research_contract.ReviewRefused([], 3), self.base)
        self.assertEqual(
            runner.refusal_words(refusal),
            'The research check still objected after 3 rounds of writing and checking, and did '
            'not say what.',
        )

    def test_continue_without_research_waits_for_a_decision_on_research_first(self):
        found = self.research_run()
        engine = self.engine()
        runner.ENGINES[str(self.root)] = engine

        def finished(case_root, run, payload, worker, *, seconds, stop, progress=None):
            return reviewed_bundle(case_root / research_contract.CASE)

        engine.control(found['id'], 'resume')
        with patch('synthesis_research.generate', finished):
            engine._once(found['id'])
        shown = engine.describe(found['id'])
        self.assertEqual(shown['status'], 'waiting-for-approval')
        with self.assertRaisesRegex(ValueError, 'Decide on the research findings first'):
            runner.dispatch(
                self.root, 'skip-research', {'id': found['id'], 'expected': shown['expected']}
            )

    def test_right_after_stop_it_says_research_is_stopping(self):
        found = self.research_run()
        engine = self.engine()
        runner.ENGINES[str(self.root)] = engine
        engine.keep_local(found['id'], {'enabled': False, 'status': 'stopped', 'error': ''})
        engine.current = found['id']
        engine.stop.set()
        self.addCleanup(setattr, engine, 'current', None)
        shown = engine.describe(found['id'])
        with self.assertRaisesRegex(ValueError, '^Research is stopping; try again in a moment.$'):
            runner.dispatch(
                self.root, 'skip-research', {'id': found['id'], 'expected': shown['expected']}
            )

    def test_status_says_research_was_skipped(self):
        found = self.research_run()
        self.engine().keep_local(found['id'], {'enabled': False, 'status': 'failed', 'error': 'x'})
        self.assertIsNone(runner.survey(self.root, found['id'])['research_skipped'])
        runner.dispatch(
            self.root, 'skip-research', {'id': found['id'], 'expected': found['expected']}
        )
        skipped = runner.survey(self.root, found['id'])['research_skipped']
        self.assertEqual(skipped['from'], 'research')

    def test_usage_reported_for_some_jobs_only_is_counted(self):
        jobs = [
            {'phase': 'author', 'round': 1, 'seconds': 2.0, 'tokens': 100, 'dollars': 0.01},
            {'phase': 'review', 'round': 1, 'seconds': 3.0, 'tokens': None, 'dollars': None},
        ]
        self.assertEqual(
            runner.research_cost(jobs),
            {
                'jobs': 2,
                'rounds': 1,
                'seconds': 5.0,
                'tokens': None,
                'dollars': None,
                'reported': 1,
            },
        )

    def test_the_run_says_whether_finish_has_a_draft_to_keep(self):
        found = self.create(page=True, stop='draft')
        self.assertFalse(runner.survey(self.root, found['id'])['keeps_draft'])
        found = self.approve(self.submit(found, page=True), page=True)
        found = self.submit(found, '# Draft\nSynthetic writing.', page=True)
        self.assertTrue(runner.survey(self.root, found['id'])['keeps_draft'])
        ideas = self.create(page=True, mode='ideas')
        self.assertFalse(runner.survey(self.root, ideas['id'])['keeps_draft'])


if __name__ == '__main__':
    unittest.main()
