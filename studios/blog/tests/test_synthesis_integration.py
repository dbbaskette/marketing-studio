import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from unittest.mock import patch

from test_editorial_tools import Fixture
import blog_runner
import synthesis_research
from studio_core import research_contract
from synthesis_fixture import TEXT, dossier, review

RUNTIME = os.environ.get('STUDIO_TEST_RESEARCH_RUNTIME')


def saved_selected_research(root, data, approval):
    """A pre-claims-map run whose saved supplied-only synthesis still continues."""
    shown = blog_runner.create(root, data, approval)
    directory, record, run = blog_runner.load(root, shown['id'])
    run['pipeline'] = ['research-plan', 'research'] + [
        name for name in run['pipeline'] if name != 'claims-map'
    ]
    run['research_contract'] = research_contract.snapshot()
    run['schema'] = 3
    run.pop('research_execution', None)
    __import__('studio').write_json(directory / blog_runner.STATE, run)
    return blog_runner.survey(root, shown['id'])


@unittest.skipUnless(RUNTIME, 'Set STUDIO_TEST_RESEARCH_RUNTIME for helper integration.')
class SynthesisIntegrationTests(Fixture):
    def setUp(self):
        super().setUp()
        env = patch.dict(os.environ, {'HARNESS_RESEARCH_RUNTIME': RUNTIME})
        env.start()
        self.addCleanup(env.stop)

    def test_browser_research_handoff_and_downstream_bundle_use(self):
        source = self.source(TEXT)
        shown = saved_selected_research(
            self.root,
            {
                'title': 'Synthetic explanation',
                'audience': 'New learners',
                'goal': 'Explain bounded examples',
                'sources': [source['id']],
                'research': 'supplied-only',
            },
            'page',
        )
        ident = shown['id']
        directory, record, run = blog_runner.load(self.root, ident)
        self.assertEqual(run['research_contract']['schema'], 2)
        self.assertEqual(run['schema'], 3)
        shown = blog_runner.submit(
            self.root,
            ident,
            'research-plan',
            {'content': '# Research plan\nExplain the synthetic concept.', 'notes': ''},
            shown['expected'],
            page=True,
        )
        # Default Balanced review continues the research plan automatically.
        self.assertEqual(shown['next'], 'research')
        _, payload, _ = blog_runner.job(self.root, ident)
        calls = []

        def worker(engine, data, guidance, **options):
            calls.append((data['worker'], options))
            if 'review_template' in data:
                value = review(data['review_template'])
            else:
                capture = data['sources'][0]
                value = dossier(data['worker'], capture['file'], capture['origin'], 'selected')
            return {'content': json.dumps(value), 'notes': 'Synthetic only'}

        result = synthesis_research.generate(
            directory, run, payload, worker, seconds=60, stop=threading.Event()
        )
        shown = blog_runner.submit(
            self.root, ident, 'research', result, shown['expected'], page=True
        )
        self.assertEqual(shown['next'], 'outline')
        self.assertEqual(len(calls), 2)
        self.assertNotEqual(calls[0][0], calls[1][0])
        self.assertFalse(any(c[1]['web'] for c in calls))
        _, data, _ = blog_runner.job(self.root, ident)
        self.assertIn('blog', data['research_bundle']['brief'].lower())
        self.assertIn('What to explain first', data['research_bundle']['brief'])
        from hub_workspace import Workspace

        included = Workspace.read_artifacts(None, directory, 'articles')
        self.assertIn('research/output.json', included)
        self.assertIn('research/brief.md', included)
        self.assertTrue(any(name.startswith('research/sources/revisions/') for name in included))
        import deep_research
        from types import SimpleNamespace

        fresh = self.article()
        imported = deep_research.command(
            self.root,
            SimpleNamespace(action='import', id=fresh, case=directory / research_contract.CASE),
        )
        self.assertEqual(imported['status'], 'complete')
        self.assertEqual(deep_research.status(self.root, fresh)['status'], 'complete')
        (directory / 'research/evidence.md').write_text('Changed')
        with self.assertRaisesRegex(ValueError, 'changed'):
            blog_runner.job(self.root, ident)

    def test_rejected_research_never_becomes_an_approved_blog_stage(self):
        from studio_core.research_contract import check_json

        self.assertTrue(check_json('{"schema":1}', {})[0])
        self.assertTrue(check_json('not JSON', {})[0])

    def test_actual_browser_worker_path_commits_only_after_the_session_guard(self):
        source = self.source(TEXT)
        shown = saved_selected_research(
            self.root,
            {
                'title': 'Synthetic explanation',
                'goal': 'Explain the bounded example',
                'audience': 'New learners',
                'sources': [source['id']],
                'research': 'supplied-only',
            },
            'page',
        )
        ident = shown['id']
        blog_runner.submit(
            self.root,
            ident,
            'research-plan',
            {'content': '# Plan\nExplain this synthetic example.', 'notes': ''},
            shown['expected'],
            page=True,
        )

        def worker(engine, data, guidance, **options):
            if 'review_template' in data:
                value = review(data['review_template'])
            else:
                captured = data['sources'][0]
                value = dossier(data['worker'], captured['file'], captured['origin'], 'selected')
            return {'content': json.dumps(value), 'notes': ''}

        engine = blog_runner.Engine(self.root, worker)
        engine.control(ident, 'resume')
        engine._once(ident)
        self.assertEqual(engine.describe(ident)['next'], 'outline', engine.local(ident))
        directory, _, _ = blog_runner.load(self.root, ident)
        research_contract.read_bundle(directory / 'research')

    def test_a_refused_page_research_is_kept_and_try_again_continues_from_it(self):
        source = self.source(TEXT)
        shown = saved_selected_research(
            self.root,
            {
                'title': 'Synthetic explanation',
                'goal': 'Explain the bounded example',
                'audience': 'New learners',
                'sources': [source['id']],
                'research': 'supplied-only',
            },
            'page',
        )
        ident = shown['id']
        blog_runner.submit(
            self.root,
            ident,
            'research-plan',
            {'content': '# Plan\nExplain this synthetic example.', 'notes': ''},
            shown['expected'],
            page=True,
        )
        authors, accept = [], [False]

        def worker(engine, data, guidance, **options):
            if 'review_template' in data:
                value = review(data['review_template'], accepted=accept[0])
            else:
                authors.append(data)
                captured = data['sources'][0]
                value = dossier(data['worker'], captured['file'], captured['origin'], 'selected')
            return {'content': json.dumps(value), 'notes': ''}

        engine = blog_runner.Engine(self.root, worker)
        self.addCleanup(engine.close)
        engine.control(ident, 'resume')
        engine._once(ident)
        found = engine.describe(ident)
        directory, _, _ = blog_runner.load(self.root, ident)
        self.assertEqual(found['status'], 'failed')
        self.assertIn('after 3 rounds of writing and checking', found['error'])
        self.assertIn('kept on this computer', found['error'])
        self.assertEqual(len(authors), 3)
        kept = directory / '.studio-research-draft'
        self.assertTrue((kept / '.harness-research/synthesis.json').is_file())
        groups = found['research']['refusal']['groups']
        self.assertEqual({group['verdict'] for group in groups}, {'narrow'})
        self.assertEqual(
            found['research']['refusal']['count'], sum(group['count'] for group in groups)
        )
        self.assertFalse((directory / 'research').exists(), 'nothing unreviewed is published')
        accept[0] = True
        blog_runner.dispatch(self.root, 'retry', {'id': ident, 'expected': found['expected']})
        engine._once(ident)
        found = engine.describe(ident)
        self.assertEqual(found['next'], 'outline', found['error'])
        # The first author of the retry corrected the kept dossier against the kept review.
        self.assertIsNotNone(authors[3]['previous_dossier'])
        self.assertEqual(authors[3]['previous_review']['facts'][0]['verdict'], 'narrow')
        self.assertFalse(kept.exists())
        research_contract.read_bundle(directory / 'research')

    def test_unfinished_research_continues_with_the_retained_helper_after_an_update(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        shared = Path(holder.name).resolve() / 'Harness Research'
        version = json.loads((Path(RUNTIME) / 'package.json').read_text())['version']
        old = shared / 'versions' / (version + '-' + 'a' * 20)
        newer = shared / 'versions' / ('9.9.9-' + 'b' * 20)
        for folder in (old, newer):
            shutil.copytree(RUNTIME, folder, ignore=shutil.ignore_patterns('tests', 'docs'))
        (newer / 'scripts/harness-research.mjs').write_text(
            "console.error('This updated helper must not be used.'); process.exit(3);\n"
        )
        (shared / 'current').symlink_to('versions/' + old.name)
        os.environ['HARNESS_RESEARCH_RUNTIME'] = str(shared / 'current')
        source = self.source(TEXT)
        shown = saved_selected_research(
            self.root,
            {
                'title': 'Synthetic explanation',
                'goal': 'Explain the bounded example',
                'audience': 'New learners',
                'sources': [source['id']],
                'research': 'supplied-only',
            },
            'page',
        )
        ident = shown['id']
        blog_runner.submit(
            self.root,
            ident,
            'research-plan',
            {'content': '# Plan\nExplain this synthetic example.', 'notes': ''},
            shown['expected'],
            page=True,
        )
        # The helper is updated before research runs; the old version stays retained.
        (shared / 'current').unlink()
        (shared / 'current').symlink_to('versions/' + newer.name)
        directory, _, run = blog_runner.load(self.root, ident)
        _, payload, _ = blog_runner.job(self.root, ident)

        def worker(engine, data, guidance, **options):
            if 'review_template' in data:
                value = review(data['review_template'])
            else:
                captured = data['sources'][0]
                value = dossier(data['worker'], captured['file'], captured['origin'], 'selected')
            return {'content': json.dumps(value), 'notes': ''}

        result = synthesis_research.generate(
            directory, run, payload, worker, seconds=60, stop=threading.Event()
        )
        from studio_core import research_view

        self.assertIn(research_view.CHECKED, result['notes'])
        self.assertIn('Explicit synthetic scope and usable brief.', result['notes'])
        research_contract.read_bundle(directory / 'research')
        shutil.rmtree(old)
        with self.assertRaisesRegex(ValueError, 'Restore the saved Harness Research version'):
            synthesis_research.generate(
                directory, run, payload, worker, seconds=60, stop=threading.Event()
            )

    def test_malformed_sections_are_repaired_using_real_helper_validation(self):
        for repair in (True, False):
            with self.subTest(repair=repair):
                directory = self.base / ('repaired' if repair else 'refused')
                directory.mkdir()
                run = {
                    'engine': 'codex',
                    'brief': {},
                    'research_contract': research_contract.snapshot(),
                }
                payload = {
                    'title': 'Synthetic',
                    'documents': {},
                    'research_policy': 'supplied-only',
                    'sources': [
                        {
                            'id': 'one',
                            'origin': 'https://example.invalid/docs',
                            'name': 'Synthetic',
                            'purposes': ['reference'],
                            'status': 'ready',
                            'text': TEXT,
                        }
                    ],
                }
                authors = []
                reviewers = []

                def worker(
                    engine,
                    data,
                    guidance,
                    *,
                    authors=authors,
                    reviewers=reviewers,
                    repair=repair,
                    **options,
                ):
                    if 'review_template' in data:
                        reviewers.append(data['worker'])
                        return {'content': json.dumps(review(data['review_template']))}
                    authors.append(data)
                    capture = data['sources'][0]
                    value = dossier(data['worker'], capture['file'], capture['origin'], 'selected')
                    if len(authors) == 1 or not repair:
                        value['sections'] = {'wrong': 'an object instead of an array'}
                    return {'content': json.dumps(value)}

                if repair:
                    synthesis_research.generate(
                        directory, run, payload, worker, seconds=60, stop=threading.Event()
                    )
                    research_contract.read_bundle(directory / 'research')
                    self.assertEqual(len(reviewers), 1)
                    self.assertNotEqual(authors[0]['worker'], reviewers[0])
                else:
                    with self.assertRaisesRegex(ValueError, 'one correction attempt'):
                        synthesis_research.generate(
                            directory, run, payload, worker, seconds=60, stop=threading.Event()
                        )
                    self.assertEqual(reviewers, [])
                    self.assertFalse((directory / 'research').exists())
                self.assertEqual(len(authors), 2)
                self.assertIn('sections must be an array', authors[1]['validation_error'])
                self.assertIn('previous_output', authors[1])


class PlanningTaskTests(Fixture):
    def test_the_author_is_given_the_plan_s_questions(self):
        from synthesis_fixture import research_stop

        directory = self.base / 'synthetic-research'
        directory.mkdir()
        research_stop(directory / 'research')
        seen = []

        def run(workflow, folder, task, invoke, sources):
            seen.append(task)

        with (
            patch.object(research_contract, 'runtime_for', return_value=directory),
            patch.object(research_contract.Workflow, 'run', run),
            patch.object(research_contract, 'publish'),
        ):
            synthesis_research.generate(
                directory,
                {'brief': {}, 'research_contract': {}},
                {
                    'title': 'Synthetic',
                    'sources': [],
                    'documents': {'research-plan': '- **instance-min**: Minimum?'},
                    'research_policy': 'supplied-only',
                },
                lambda *a, **k: self.fail('No provider job'),
                seconds=60,
                stop=threading.Event(),
            )
        self.assertEqual(
            seen[0]['planning_questions'], [{'id': 'instance-min', 'question': 'Minimum?'}]
        )
