"""A guided run that stops says what happened and what to do, and keeps what it made.

Research that the independent check refused is kept beside the blog, listed by what the
check objected to, and Try again continues from it. No provider runs: workers and the
research workflow are synthetic.
"""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import hashlib
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from test_blog_runner import RunnerCase
import blog_runner as runner
from studio_core import research_contract

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


if __name__ == '__main__':
    unittest.main()
