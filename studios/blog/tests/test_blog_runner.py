"""The same blog, gates and edits through chat commands and the authenticated page."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import json
import http.client
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import tempfile
import unittest
from unittest.mock import patch

from test_editorial_tools import Fixture
import studio
import blog_runner as runner
import blog_worker
import management


class RunnerCase(Fixture):
    """A disposable workspace with the runner helpers every test uses."""

    def setUp(self):
        super().setUp()
        environment = patch.dict(
            os.environ,
            {
                'BLOG_STUDIO_DATA': str(self.base / 'runner-data'),
                'BRAND_SKILL_RUNTIME': str(self.base / 'no-brand'),
                'STUDIOS_CONFIG': str(self.base / 'studios.json'),
            },
        )
        environment.start()
        self.addCleanup(environment.stop)
        import studios_config

        studios_config.update({'review': {'level': 'step_by_step'}})
        self.addCleanup(lambda: runner.ENGINES.pop(str(self.root), None))

    def create(self, page=False, **extra):
        return runner.create(
            self.root,
            {
                'title': 'Synthetic gateway guide',
                'audience': 'New authors',
                'goal': 'Explain a fictional gateway',
                'research': 'none',
                **extra,
            },
            'page' if page else 'conversation',
        )

    def submit(self, found, content=None, page=False):
        return runner.submit(
            self.root,
            found['id'],
            found['next'],
            {
                'content': content or '# ' + found['next'] + '\nSynthetic writing.',
                'notes': 'Synthetic worker judgment.',
            },
            found['expected'],
            page=page,
        )

    def approve(self, found, page=False):
        return runner.decide(self.root, found['id'], found['expected'], 'approve', page=page)

    def profiles(self, agent='codex'):
        from studio_core import studios_config

        studios_config.update(
            {
                'assistant': {'agent': agent},
                'models': {
                    'schema': 1,
                    'agent': agent,
                    'mode': 'by_task',
                    'profiles': {
                        name: {'selection': 'explicit', 'model': name + '-model', 'effort': effort}
                        for name, effort in [
                            ('quick', 'low'),
                            ('main', 'medium'),
                            ('complex', 'high'),
                        ]
                    },
                },
            }
        )


class BlogRunnerTests(RunnerCase):
    def test_profiles_are_saved_and_background_worker_gets_the_saved_main(self):
        from studio_core import studios_config

        self.profiles()
        found = self.create(page=True)
        studios_config.update({'models': {'profiles': {'main': {'model': 'later'}}}})
        calls = []

        def worker(*args, **kwargs):
            calls.append(kwargs)
            return {'content': '# Synthetic outline', 'notes': 'Fake worker only.'}

        engine = runner.Engine(self.root, worker=worker)
        self.addCleanup(engine.close)
        engine.keep_local(found['id'], {'enabled': True})
        engine.once(found['id'])
        self.assertEqual(calls[0]['model_selection']['model'], 'main-model')
        _, _, run = runner.load(self.root, found['id'])
        self.assertEqual(run['model_jobs'][0]['profile'], 'main')
        self.assertIsNone(run['model_jobs'][0]['actual_model'])
        self.assertEqual(engine.describe(found['id'])['status'], 'waiting-for-approval')

    def test_review_return_to_draft_uses_complex_without_routing_from_request_text(self):
        self.profiles()
        found = self.create()
        for _ in range(2):
            found = self.approve(self.submit(found))
        self.assertEqual(found['next'], 'review')
        found = self.submit(found)
        found = runner.decide(
            self.root,
            found['id'],
            found['expected'],
            'changes',
            'Synthetic review correction',
            target='draft',
        )
        choice = runner.job(self.root, found['id'])[0]['model_selection']
        self.assertEqual((choice['profile'], choice['model']), ('complex', 'complex-model'))
        self.profiles('claude')
        # The existing Codex run still owns its saved profiles.
        self.assertEqual(runner.job(self.root, found['id'])[0]['model_selection'], choice)

    def test_source_classification_uses_quick_for_both_assistants(self):
        import source_curator

        for agent in ('codex', 'claude'):
            self.profiles(agent)
            options = source_curator.shared_options(agent, task='source-classification')
            self.assertEqual(options[options.index('--model') + 1], 'quick-model')

    def test_conversation_pipeline_enforces_gates_and_stop(self):
        found = self.create(stop='draft')
        with self.assertRaisesRegex(ValueError, 'current submitted'):
            self.approve(found)
        with self.assertRaisesRegex(ValueError, 'current stage'):
            runner.submit(
                self.root,
                found['id'],
                'draft',
                {'content': 'Early', 'notes': ''},
                found['expected'],
            )
        for stage in ('outline', 'draft'):
            self.assertEqual(found['next'], stage)
            found = self.submit(found)
            found = self.approve(found)
        self.assertTrue(found['complete'])
        self.assertEqual([row['stage'] for row in found['stages']], ['outline', 'draft'])

    def test_page_approval_is_unavailable_from_cli_and_worker_schema(self):
        found = self.create(page=True)
        found = self.submit(found, page=True)
        with self.assertRaisesRegex(ValueError, 'decided on the page'):
            self.approve(found)
        with self.assertRaises(ValueError):
            blog_worker.validate({'content': 'A draft', 'notes': '', 'approve': True})
        found = self.approve(found, page=True)
        self.assertEqual(found['next'], 'draft')

    def test_developing_an_idea_stops_at_an_editable_draft(self):
        ideas = '# Three angles\n\n1. Ownership\n2. Feedback\n3. Context'
        found = self.submit(self.create(page=True, mode='ideas', stop='outline'), ideas, page=True)
        with studio.locked(self.root), patch.object(runner.Engine, 'control', return_value={}):
            runner.dispatch(
                self.root,
                'develop',
                {
                    'id': found['id'],
                    'expected': found['expected'],
                    'request': 'Develop the second idea for technical authors.',
                },
            )
        directory, record, run = runner.load(self.root, found['id'])
        self.assertEqual(run['pipeline'], ['outline', 'draft'])
        self.assertEqual(record['stop_point'], 'draft')
        self.assertIn('second idea', run['stages']['outline']['request'])
        self.assertEqual((directory / 'OUTLINE.md').read_text(), ideas)
        found = runner.survey(self.root, found['id'])
        for stage in ('outline', 'draft'):
            self.assertEqual(found['next'], stage)
            found = self.submit(found, page=True)
            found = self.approve(found, page=True)
        self.assertTrue(found['complete'])
        self.assertIsNone(found['next'])
        self.assertEqual(record['research_policy'], 'supplied-only')
        self.assertNotIn('research', run['pipeline'])

    def test_old_page_decision_and_manual_edit_do_not_renew_approval(self):
        found = self.submit(self.create())
        old = found['expected']
        directory, _, _ = runner.load(self.root, found['id'])
        (directory / 'OUTLINE.md').write_text('My local edit')
        with self.assertRaisesRegex(ValueError, 'changed'):
            runner.decide(self.root, found['id'], old, 'approve')
        latest = runner.survey(self.root, found['id'])
        self.assertEqual(latest['stages'][0]['status'], 'stale')

    def test_downstream_stages_are_invalidated_after_outline_changes(self):
        found = self.create()
        for _ in range(4):
            found = self.approve(self.submit(found))
        found = runner.decide(
            self.root,
            found['id'],
            found['expected'],
            'changes',
            'Change the thesis',
            target='outline',
        )
        self.assertEqual(found['next'], 'outline')
        self.assertEqual(found['stages'][1]['status'], 'pending')
        found = self.submit(found, 'New thesis')
        self.assertIn('Change the thesis', found['stages'][0]['request'])
        self.assertEqual(found['stages'][0]['status'], 'draft')

    def test_change_request_is_an_instruction_for_a_minimal_edit(self):
        draft = '# Draft\nThe first fictional paragraph.\n\nThe second fictional paragraph.'
        found = self.approve(self.submit(self.create()))
        found = self.submit(found, draft)
        found = runner.decide(
            self.root, found['id'], found['expected'], 'changes', 'Shorten the second paragraph.'
        )
        _, payload, guidance = runner.job(self.root, found['id'])
        self.assertIn('Shorten the second paragraph.', guidance)
        self.assertIn('minimal edit, not a rewrite', guidance)
        self.assertIn('verbatim', guidance)
        self.assertNotIn('Write the blog from the approved outline', guidance)
        self.assertEqual(payload['documents']['draft'], draft)
        # A review that sends the draft back is an edit of that draft too.
        found = self.approve(self.submit(found, draft))
        found = self.submit(found)
        found = runner.decide(
            self.root,
            found['id'],
            found['expected'],
            'changes',
            'Fix the review finding about the title.',
            target='draft',
        )
        guidance = runner.job(self.root, found['id'])[2]
        self.assertIn('Fix the review finding about the title.', guidance)
        self.assertIn('minimal edit, not a rewrite', guidance)

    def test_request_for_a_new_document_directs_the_step_without_an_edit(self):
        ideas = '# Three angles\n\n1. Ownership\n2. Feedback\n3. Context'
        found = self.submit(self.create(page=True, mode='ideas', stop='outline'), ideas, page=True)
        with studio.locked(self.root), patch.object(runner.Engine, 'control', return_value={}):
            runner.dispatch(
                self.root,
                'develop',
                {
                    'id': found['id'],
                    'expected': found['expected'],
                    'request': 'Develop the second idea for technical authors.',
                },
            )
        guidance = runner.job(self.root, found['id'])[2]
        self.assertIn('Develop the second idea for technical authors.', guidance)
        self.assertIn('Make an argument outline', guidance)
        self.assertNotIn('minimal edit', guidance)

    def test_revising_a_manuscript_does_not_ask_for_an_outline_based_draft(self):
        found = self.create(mode='revise', id=self.article(), stop='draft')
        guidance = runner.job(self.root, found['id'])[2]
        self.assertNotIn('approved outline', guidance)
        self.assertIn('Revise the supplied manuscript', guidance)

    def test_research_questions_and_findings_each_wait_for_approval(self):
        source = self.source('A fictional gateway routes synthetic requests.')
        found = self.create(research='supplied-only', stop='outline', sources=[source['id']])
        self.assertEqual(
            [row['stage'] for row in found['stages']], ['research-plan', 'research', 'outline']
        )
        for stage in ('research-plan', 'research', 'outline'):
            self.assertEqual(found['next'], stage)
            found = self.approve(self.submit(found))
        self.assertTrue(found['complete'])

    def test_skill_to_page_and_back_preserves_writing_and_decisions(self):
        found = self.approve(self.submit(self.create()))
        found = runner.decide(self.root, found['id'], found['expected'], 'handoff')
        self.assertEqual(found['approval'], 'page')
        found = runner.dispatch(
            self.root, 'start', {'id': found['id'], 'expected': found['expected']}
        )
        found = runner.dispatch(
            self.root, 'handoff', {'id': found['id'], 'expected': found['expected']}
        )
        self.assertEqual(found['approval'], 'conversation')
        self.assertEqual(found['stages'][0]['status'], 'approved')
        self.assertFalse(runner.engine(self.root).local(found['id'])['enabled'])
        with self.assertRaisesRegex(ValueError, 'decided in chat'):
            runner.dispatch(
                self.root, 'approve', {'id': found['id'], 'expected': found['expected']}
            )

    def test_imported_draft_starts_at_review_and_is_not_rewritten(self):
        ident = self.article('A fictional manuscript written by Avery.')
        directory, _ = studio.item(self.root, 'articles', ident)
        original = (directory / 'DRAFT.md').read_bytes()
        found = self.create(id=ident)
        self.assertEqual(found['next'], 'review')
        found = self.submit(found)
        self.assertEqual((directory / 'DRAFT.md').read_bytes(), original)
        self.assertIn(
            'A fictional manuscript', runner.job(self.root, ident)[1]['documents']['manuscript']
        )

    def test_supplied_only_research_without_sources_is_no_research(self):
        for research in ('supplied-only', None):
            with self.subTest(research=research):
                data = {
                    'title': 'Synthetic gateway guide',
                    'audience': 'New authors',
                    'goal': 'Explain a fictional gateway',
                }
                if research:
                    data['research'] = research
                found = runner.create(self.root, data)
                self.assertEqual(
                    [row['stage'] for row in found['stages']],
                    ['outline', 'draft', 'review', 'package'],
                )
                _, record, run = runner.load(self.root, found['id'])
                self.assertNotIn('research_contract', run)
                self.assertEqual(record['research_policy'], 'supplied-only')

    def test_polling_reads_selected_context_once_per_run(self):
        source = self.source('A fictional gateway routes synthetic requests.')
        ids = []
        for _ in range(3):
            found = self.approve(self.submit(self.create(sources=[source['id']])))
            found = self.approve(self.submit(found))
            ids.append(self.submit(found)['id'])
        with patch.object(runner, 'inputs', wraps=runner.inputs) as counted:
            detail = runner.survey(self.root, ids[0])
        self.assertEqual(counted.call_count, 1)
        self.assertTrue(detail['expected'])
        with patch.object(runner, 'inputs', wraps=runner.inputs) as counted:
            listed = runner.catalog(self.root)
        self.assertEqual(counted.call_count, len(ids))
        self.assertEqual(
            [row['stages'] for row in listed['items'] if row['id'] == ids[0]], [detail['stages']]
        )
        # List views skip the version token; decisions still need the exact one.
        self.assertIsNone(runner.survey(self.root, ids[0], listing=True)['expected'])

    def test_list_and_detail_views_agree_when_inputs_change(self):
        found = self.approve(self.submit(self.create()))
        directory, record = studio.item(self.root, 'articles', found['id'])
        record['title'] = 'A changed synthetic title'
        studio.persist(directory, 'articles', record)
        detail = runner.survey(self.root, found['id'])
        self.assertEqual(detail['stages'][0]['status'], 'stale')
        self.assertNotEqual(detail['expected'], found['expected'])
        listed = next(row for row in runner.catalog(self.root)['items'] if row['id'] == found['id'])
        self.assertEqual(listed['stages'], detail['stages'])

    def test_input_pins_keep_their_saved_format(self):
        found = self.approve(self.submit(self.create()))
        directory, record, run = runner.load(self.root, found['id'])
        context = runner.inputs(self.root, record, run)
        original = studio.artifact_fingerprint(directory, 'ORIGINAL.md')

        def pin(previous):
            return studio.digest(json.dumps([context, previous, original], sort_keys=True).encode())

        self.assertEqual(run['stages']['outline']['basis'], pin({}))
        outline = studio.artifact_fingerprint(directory, 'OUTLINE.md')
        self.assertEqual(
            runner.basis(self.root, directory, record, run, 'draft'), pin({'outline': outline})
        )

    def test_only_steps_that_use_evidence_receive_sources(self):
        source = self.source('A fictional gateway routes synthetic requests.')
        found = self.create(sources=[source['id']])
        while found['next'] != 'package':
            self.assertEqual(len(runner.job(self.root, found['id'])[1]['sources']), 1)
            found = self.approve(self.submit(found))
        _, payload, _ = runner.job(self.root, found['id'])
        self.assertEqual(payload['sources'], [])
        self.assertIn('review', payload['documents'])

    def test_page_creation_retry_is_idempotent(self):
        data = {
            'operation': 'a' * 32,
            'title': 'Page blog',
            'audience': 'Authors',
            'goal': 'Explain a fictional process',
            'research': 'none',
        }
        one = runner.dispatch(self.root, 'create', data)
        two = runner.dispatch(self.root, 'create', data)
        self.assertEqual(one['id'], two['id'])
        self.assertEqual(len(list((self.root / 'articles').iterdir())), 1)

    def test_balanced_combines_research_and_outline_then_final_package(self):
        import studios_config

        studios_config.update({'review': {'level': 'balanced'}})
        source = self.source('A fictional gateway routes synthetic requests.')
        found = self.create(page=True, research='supplied-only', sources=[source['id']])
        ident = found['id']
        while found['next'] != 'outline':
            found = self.submit(found, page=True)
        found = self.submit(found, page=True)
        self.assertEqual(found['next'], 'outline')
        self.assertEqual(found['review_level'], 'balanced')
        shown = runner.document(self.root, ident, 'outline')
        self.assertEqual([item['stage'] for item in shown['bundle']], ['research-plan', 'research'])
        found = self.approve(found, page=True)
        while found['next'] != 'package':
            found = self.submit(found, page=True)
        found = self.submit(found, page=True)
        self.assertEqual(found['next'], 'package')
        self.assertIn(
            'draft',
            [item['stage'] for item in runner.document(self.root, ident, 'package')['bundle']],
        )
        self.assertTrue(self.approve(found, page=True)['complete'])
        _, _, saved = runner.load(self.root, ident)
        self.assertEqual(saved['stages']['draft']['accepted_by'], 'review-policy')

    def test_status_says_whether_a_step_was_accepted_or_awaits_a_decision(self):
        import studios_config

        studios_config.update({'review': {'level': 'balanced'}})
        found = self.create()
        self.assertEqual(found['awaits'], 'submission')
        found = self.submit(found)
        self.assertEqual((found['next'], found['awaits']), ('outline', 'decision'))
        found = self.approve(found)
        self.assertFalse(found['stages'][0]['auto_accepted'])
        found = self.submit(found)
        # Balanced accepts the draft; nothing waits for the person, so approve is refused.
        self.assertEqual((found['next'], found['awaits']), ('review', 'submission'))
        self.assertTrue(found['stages'][1]['auto_accepted'])
        with self.assertRaisesRegex(ValueError, 'need no approval'):
            self.approve(found)
        status = runner.engine(self.root).describe(found['id'])
        self.assertEqual(status['awaits'], 'submission')
        self.assertTrue(status['stages'][1]['auto_accepted'])
        found = self.submit(self.submit(found))
        self.assertEqual((found['next'], found['awaits']), ('package', 'decision'))
        found = self.approve(found)
        self.assertIsNone(found['awaits'])

    def test_automatic_worker_continues_until_final_review(self):
        import studios_config

        studios_config.update({'review': {'level': 'automatic'}})
        found = self.create(page=True)
        engine = runner.Engine(
            self.root, lambda *args, **kwargs: {'content': '# Synthetic stage', 'notes': 'Checked.'}
        )
        engine.control(found['id'], 'resume')
        for _ in range(6):
            engine.once(found['id'])
        found = engine.describe(found['id'])
        self.assertEqual(found['status'], 'waiting-for-approval')
        self.assertEqual(found['next'], 'package')
        self.assertEqual(
            [row['status'] for row in found['stages']],
            ['approved', 'approved', 'approved', 'draft'],
        )
        self.assertTrue(self.approve(found, page=True)['complete'])

    def test_worker_saves_one_stage_and_never_crosses_gate(self):
        calls = []

        def worker(*args, **kwargs):
            calls.append(kwargs)
            return {'content': '# Outline\nA fictional outline.', 'notes': 'Synthetic.'}

        found = self.create(page=True, stop='draft')
        engine = runner.Engine(self.root, worker)
        engine.control(found['id'], 'resume')
        engine.once(found['id'])
        engine.once(found['id'])
        self.assertEqual(len(calls), 1)
        self.assertFalse(calls[0]['web'])
        found = engine.describe(found['id'])
        self.assertEqual(found['status'], 'waiting-for-approval')
        self.assertEqual(found['next'], 'outline')
        found = self.approve(found, page=True)
        self.assertEqual(engine.describe(found['id'])['status'], 'queued')
        engine.once(found['id'])
        self.assertEqual(engine.describe(found['id'])['status'], 'waiting-for-approval')
        self.assertEqual(len(calls), 2)

    def test_late_worker_result_cannot_overwrite_local_edit(self):
        found = self.create(page=True)
        directory, _ = studio.item(self.root, 'articles', found['id'])

        def worker(*args, **kwargs):
            (directory / 'OUTLINE.md').write_text('My newer outline')
            return {'content': 'Late model outline', 'notes': ''}

        engine = runner.Engine(self.root, worker)
        engine.control(found['id'], 'resume')
        engine.once(found['id'])
        self.assertEqual((directory / 'OUTLINE.md').read_text(), 'My newer outline')
        self.assertEqual(engine.describe(found['id'])['status'], 'failed')

    def test_background_runner_does_not_regenerate_a_manual_edit(self):
        calls = []

        def worker(*args, **kwargs):
            calls.append(True)
            return {'content': 'Generated outline', 'notes': ''}

        found = self.create(page=True)
        engine = runner.Engine(self.root, worker)
        engine.control(found['id'], 'resume')
        engine.once(found['id'])
        directory, _ = studio.item(self.root, 'articles', found['id'])
        (directory / 'OUTLINE.md').write_text('My edited outline')
        engine.once(found['id'])
        self.assertEqual(len(calls), 1)
        self.assertEqual((directory / 'OUTLINE.md').read_text(), 'My edited outline')
        self.assertEqual(engine.describe(found['id'])['status'], 'needs-attention')
        found = engine.describe(found['id'])
        found = runner.dispatch(
            self.root, 'adopt', {'id': found['id'], 'expected': found['expected']}
        )
        self.assertEqual(found['stages'][0]['status'], 'draft')
        self.assertEqual((directory / 'OUTLINE.md').read_text(), 'My edited outline')

    def test_restart_only_resumes_explicitly_started_local_runs(self):
        found = self.create(page=True)
        one = runner.Engine(self.root)
        self.assertFalse(one.local(found['id'])['enabled'])
        one.control(found['id'], 'resume')
        two = runner.Engine(
            self.root, lambda *a, **kw: {'content': 'Recovered outline', 'notes': ''}
        )
        two.once(found['id'])
        self.assertEqual(two.describe(found['id'])['status'], 'waiting-for-approval')
        self.assertEqual(one.local(found['id'])['status'], 'waiting-for-approval')

    def test_stop_cancels_worker_without_a_late_save(self):
        entered, release = threading.Event(), threading.Event()

        def worker(*args, **kwargs):
            entered.set()
            release.wait(3)
            return {'content': 'A late outline', 'notes': ''}

        found = self.create(page=True)
        engine = runner.Engine(self.root, worker)
        engine.control(found['id'], 'resume')
        thread = threading.Thread(target=engine.once, args=(found['id'],))
        thread.start()
        try:
            self.assertTrue(entered.wait(2))
            with studio.locked(self.root):
                engine.control(found['id'], 'stop')
            release.set()
            thread.join(3)
            self.assertFalse(thread.is_alive())
            self.assertEqual(engine.describe(found['id'])['status'], 'stopped')
            directory, _ = studio.item(self.root, 'articles', found['id'])
            self.assertFalse((directory / 'OUTLINE.md').exists())
        finally:
            release.set()
            thread.join(3)

    def test_cli_conversation_flow_uses_same_state(self):
        script = Path(studio.__file__)

        def cli(*args):
            result = subprocess.run(
                [sys.executable, str(script), '--root', str(self.root), 'run', *args],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)

        found = cli(
            'create',
            '--title',
            'A synthetic CLI blog',
            '--audience',
            'Authors',
            '--goal',
            'Explain a fixture',
            '--research',
            'none',
            '--stop',
            'outline',
        )
        self.file.write_text('# Outline\nSynthetic fixture.')
        found = cli(
            'submit',
            '--id',
            found['id'],
            '--stage',
            'outline',
            '--file',
            str(self.file),
            '--expected',
            found['expected'],
        )
        found = cli('approve', '--id', found['id'], '--expected', found['expected'])
        self.assertTrue(found['complete'])

    def test_read_only_hub_cannot_start_page_work(self):
        with patch.object(management, 'authorize_write', side_effect=ValueError('Read-only')):
            with self.assertRaisesRegex(ValueError, 'Read-only'):
                management.dispatch(self.root, 'run-create', {})

    def test_context_does_not_silently_truncate_sources(self):
        source = self.source('Synthetic evidence ' * 20_000)
        before = list((self.root / 'articles').iterdir())
        with self.assertRaisesRegex(ValueError, 'too large'):
            self.create(sources=[source['id']])
        self.assertEqual(list((self.root / 'articles').iterdir()), before)

    def test_authenticated_http_pipeline_completes_all_gates(self):
        from urllib.parse import urlsplit

        engine = runner.Engine(
            self.root,
            lambda *a, **kw: {'content': '# Synthetic writing', 'notes': 'Fixture worker.'},
        )
        runner.ENGINES[str(self.root)] = engine
        server, url = management.server(self.root)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        token = urlsplit(url).fragment

        def api(route, data=None, authenticated=True):
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
            headers = {'X-Blog-Studio-Token': token} if authenticated else {}
            if data is not None:
                headers['Content-Type'] = 'application/json'
            connection.request(
                'POST' if data is not None else 'GET',
                '/api/' + route,
                json.dumps(data) if data is not None else None,
                headers,
            )
            response = connection.getresponse()
            value = json.loads(response.read())
            status = response.status
            connection.close()
            return status, value

        self.assertNotEqual(api('runs', authenticated=False)[0], 200)
        status, found = api(
            'run-create',
            {
                'operation': 'c' * 32,
                'title': 'HTTP fixture',
                'audience': 'Authors',
                'goal': 'Explain synthetic writing',
                'research': 'none',
            },
        )
        self.assertEqual(status, 200, found)
        for stage in ('outline', 'draft', 'review', 'package'):
            self.assertEqual(found['next'], stage)
            self.assertEqual(found['status'], 'queued')
            engine.once(found['id'])
            status, found = api('run?id=' + found['id'])
            self.assertEqual(found['status'], 'waiting-for-approval')
            status, downloaded = api('run-file?id=' + found['id'] + '&stage=' + stage)
            self.assertEqual(downloaded['content'], '# Synthetic writing')
            status, found = api('run-approve', {'id': found['id'], 'expected': found['expected']})
            self.assertEqual(status, 200, found)
        self.assertTrue(found['complete'])
        self.assertEqual(found['status'], 'complete')

    def test_writing_modes_select_real_pipelines(self):
        source = self.source('# A supplied manuscript\nA fictional gateway routes requests.')
        for mode, expected in (
            ('write', ['outline', 'draft', 'review', 'package']),
            ('outline', ['outline']),
            ('revise', ['draft', 'review', 'package']),
            ('review', ['review']),
        ):
            with self.subTest(mode=mode):
                extra = {'manuscript': source['id']} if mode in ('revise', 'review') else {}
                found = self.create(mode=mode, **extra)
                self.assertEqual([row['stage'] for row in found['stages']], expected)
                self.assertEqual(found['mode'], mode)
                if extra:
                    directory, _ = studio.item(self.root, 'articles', found['id'])
                    original = (directory / 'ORIGINAL.md').read_text()
                    found = self.submit(found, '# Revised\nA clearer fictional explanation.')
                    self.assertEqual((directory / 'ORIGINAL.md').read_text(), original)
                    if mode == 'review':
                        self.assertEqual((directory / 'DRAFT.md').read_text(), original)

    def test_revision_mode_can_stop_at_draft(self):
        found = self.create(mode='revise', id=self.article(), stop='draft')
        self.assertEqual([row['stage'] for row in found['stages']], ['draft'])
        found = self.approve(self.submit(found))
        self.assertTrue(found['complete'])

    def test_completed_page_revision_returns_to_a_resumable_stage(self):
        found = self.create(page=True, stop='outline')
        engine = runner.engine(self.root)
        engine.control(found['id'], 'resume')
        found = self.approve(self.submit(found, page=True), page=True)
        engine.once(found['id'])
        found = runner.dispatch(
            self.root,
            'changes',
            {
                'id': found['id'],
                'expected': found['expected'],
                'stage': 'outline',
                'request': 'Clarify the fictional argument',
            },
        )
        self.assertFalse(found['complete'])
        self.assertEqual(found['next'], 'outline')
        self.assertEqual(found['status'], 'paused')
        self.assertFalse(found['enabled'])

    def test_modes_reject_missing_or_competing_manuscripts_before_writing(self):
        with self.assertRaisesRegex(ValueError, 'upload a draft'):
            self.create(mode='review')
        source = self.source('A synthetic original')
        with self.assertRaisesRegex(ValueError, 'Choose revise or review'):
            self.create(mode='write', manuscript=source['id'])
        with self.assertRaisesRegex(ValueError, 'revision starts at draft'):
            self.create(mode='revise', manuscript=source['id'], stop='outline')
        ident = self.article()
        directory, _ = studio.item(self.root, 'articles', ident)
        before = (directory / 'DRAFT.md').read_bytes()
        with self.assertRaisesRegex(ValueError, 'not both'):
            self.create(mode='revise', id=ident, manuscript=source['id'])
        self.assertEqual((directory / 'DRAFT.md').read_bytes(), before)
        (directory / 'DRAFT.md').unlink()
        with self.assertRaisesRegex(ValueError, 'no saved manuscript'):
            self.create(mode='review', id=ident)
        self.assertFalse((directory / runner.STATE).exists())

    def test_settings_are_local_defaults_and_do_not_change_existing_runs(self):
        found = self.create()
        defaults = dict(runner.DEFAULTS, engine='claude', seconds=120, author='Avery')
        with patch.object(
            management,
            'authorize_write',
            side_effect=AssertionError('Local defaults must not need Hub contribution rights'),
        ):
            saved = management.dispatch(self.root, 'run-settings', defaults)
        self.assertTrue(saved['configured'])
        self.assertEqual(saved['defaults'], defaults)
        self.assertEqual(runner.survey(self.root, found['id'])['engine'], 'codex')
        self.assertFalse(list((self.root / 'articles').glob('*/derived/*settings*')))
        with self.assertRaises(ValueError):
            runner.settings(self.root, dict(defaults, seconds=0))
        self.assertEqual(runner.settings(self.root)['defaults'], defaults)

    def test_review_document_compares_against_last_approved_version(self):
        found = self.approve(self.submit(self.create(), '# Outline\nThe first argument.'))
        found = runner.decide(
            self.root,
            found['id'],
            found['expected'],
            'changes',
            'Clarify the argument',
            target='outline',
        )
        found = self.submit(found, '# Outline\nA clearer argument.')
        shown = runner.document(self.root, found['id'], 'outline')
        self.assertEqual(shown['previous'], '# Outline\nThe first argument.')
        self.assertIn('-The first argument.', shown['diff'])
        self.assertIn('+A clearer argument.', shown['diff'])
        self.assertEqual(shown['expected'], found['expected'])
        self.assertTrue(all(check['passed'] for check in shown['checks']))
        directory, _ = studio.item(self.root, 'articles', found['id'])
        (directory / 'OUTLINE.md').write_text('A local change outside the runner')
        shown = runner.document(self.root, found['id'], 'outline')
        self.assertFalse(shown['checks'][1]['passed'])
        history = next((directory / 'history').glob('derived-blog-approved-outline-*.md'))
        history.write_text('Changed outside the runner')
        self.assertIsNone(runner.document(self.root, found['id'], 'outline')['previous'])

    def test_pause_keeps_current_stage_but_prevents_next_job(self):
        found = self.create(page=True)
        engine = runner.Engine(self.root)
        engine.control(found['id'], 'resume')

        def worker(*args, **kwargs):
            engine.control(found['id'], 'pause')
            return {'content': 'Finished current job', 'notes': ''}

        engine.worker = worker
        engine.once(found['id'])
        found = engine.describe(found['id'])
        self.assertEqual(found['status'], 'waiting-for-approval')
        self.assertFalse(found['enabled'])
        found = self.approve(found, page=True)
        self.assertFalse(engine.local(found['id'])['enabled'])

    def test_imported_draft_can_be_revised_after_review(self):
        ident = self.article('My original synthetic draft')
        found = self.submit(self.create(id=ident))
        found = runner.decide(
            self.root,
            ident,
            found['expected'],
            'changes',
            'Clarify the introduction',
            target='draft',
        )
        self.assertEqual(found['next'], 'draft')
        # The author's own manuscript is edited, not rewritten from the brief.
        guidance = runner.job(self.root, ident)[2]
        self.assertIn('minimal edit, not a rewrite', guidance)
        self.assertIn('Clarify the introduction', guidance)
        found = self.submit(found, 'My revised synthetic draft')
        self.assertEqual(found['stages'][0]['status'], 'draft')
        found = self.approve(found)
        self.assertEqual(found['next'], 'review')


class WorkerProcessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.binary = self.base / 'fixture-agent'
        self.capture = self.base / 'command.json'
        environment = patch.dict(os.environ, {'STUDIOS_CONFIG': str(self.base / 'shared.json')})
        environment.start()
        self.addCleanup(environment.stop)

    def executable(self, body):
        self.binary.write_text(
            '#!' + sys.executable + '\nimport sys,json,time\nfrom pathlib import Path\n' + body
        )
        self.binary.chmod(0o700)

    def test_both_cli_adapters_return_only_structured_writing(self):
        self.executable(
            """args=sys.argv[1:]
Path("""
            + repr(str(self.capture))
            + """).write_text(json.dumps(args))
value={'content':'# Synthetic output','notes':'Fixture CLI; no account.'}
if '--output-last-message' in args:
 Path(args[args.index('--output-last-message')+1]).write_text(json.dumps(value))
else:
 print(json.dumps({'structured_output':value}))
"""
        )
        for agent in ('codex', 'claude'):
            with (
                self.subTest(agent=agent),
                patch.object(
                    blog_worker.source_curator, 'executable', return_value=str(self.binary)
                ),
                patch.object(
                    blog_worker.source_curator,
                    'codex_options',
                    return_value=['--ignore-user-config', '-c', 'features.shell_tool=false'],
                ),
            ):
                found = blog_worker.generate(
                    agent, {'title': 'Synthetic'}, 'Write an outline', seconds=5
                )
                self.assertEqual(found['content'], '# Synthetic output')
                args = json.loads(self.capture.read_text())
                if agent == 'codex':
                    self.assertIn('features.unified_exec=false', args)
                    self.assertIn('web_search="disabled"', args)
                    self.assertIn('--ignore-user-config', args)
                else:
                    self.assertEqual(args[args.index('--tools') + 1], '')
                    self.assertIn('--strict-mcp-config', args)

    def test_policy_and_job_guidance_are_sent_once(self):
        self.executable(
            'args=sys.argv[1:]\n'
            "system=args[args.index('--system-prompt')+1] if '--system-prompt' in args else Path(json.loads([a for a in args if a.startswith('model_instructions_file=')][0].split('=',1)[1])).read_text()\n"
            'Path('
            + repr(str(self.capture))
            + ').write_text(json.dumps({"system":system,"stdin":sys.stdin.read()}))\n'
            "value={'content':'Synthetic output','notes':'Fixture CLI; no account.'}\n"
            "if '--output-last-message' in args:\n Path(args[args.index('--output-last-message')+1]).write_text(json.dumps(value))\n"
            "else:\n print(json.dumps({'structured_output':value}))\n"
        )
        for agent in ('codex', 'claude'):
            with (
                self.subTest(agent=agent),
                patch.object(
                    blog_worker.source_curator, 'executable', return_value=str(self.binary)
                ),
                patch.object(blog_worker.source_curator, 'codex_options', return_value=[]),
            ):
                blog_worker.generate(
                    agent, {'title': 'Synthetic title'}, 'Write the fixture outline', seconds=5
                )
                seen = json.loads(self.capture.read_text())
                sent = seen['system'] + seen['stdin']
                for text in (blog_worker.POLICY, 'Write the fixture outline'):
                    self.assertEqual(sent.count(text), 1)
                    self.assertIn(text, seen['system'])
                self.assertIn('"title": "Synthetic title"', seen['stdin'])

    def test_editing_reviews_use_a_typed_schema_in_both_cli_adapters(self):
        self.executable(
            'args=sys.argv[1:]\n'
            "schema=json.loads(Path(args[args.index('--output-schema')+1]).read_text()) if '--output-schema' in args else json.loads(args[args.index('--json-schema')+1])\n"
            'Path(' + repr(str(self.capture)) + ').write_text(json.dumps(schema))\n'
            "value={'summary':'Synthetic polish, no research.','findings':[{'id':'wording','kind':'edit','before':'Utilize it.','after':'Use it.','context':'','reason':'Prefer the familiar word.','evidence':'Editorial judgment','verdict':'editorial'}],'notes':'No account or provider used.'}\n"
            "if '--output-last-message' in args:\n Path(args[args.index('--output-last-message')+1]).write_text(json.dumps(value))\n"
            "else:\n print(json.dumps({'structured_output':value}))\n"
        )
        for agent in ('codex', 'claude'):
            with (
                self.subTest(agent=agent),
                patch.object(
                    blog_worker.source_curator, 'executable', return_value=str(self.binary)
                ),
                patch.object(blog_worker.source_curator, 'codex_options', return_value=[]),
            ):
                found = blog_worker.generate(
                    agent, {'response_kind': 'editing-review'}, 'Polish writing', seconds=5
                )
                schema = json.loads(self.capture.read_text())
                self.assertEqual(set(schema['required']), {'summary', 'findings', 'notes'})
                self.assertNotIn('content', schema['properties'])
                items = schema['properties']['findings']['items']
                self.assertFalse(items['additionalProperties'])
                self.assertEqual(set(items['required']), set(items['properties']))
                self.assertEqual(items['properties']['kind']['enum'], ['edit', 'comment'])
                review = json.loads(found['content'])
                self.assertEqual(review['findings'][0]['before'], 'Utilize it.')
                self.assertEqual(review['findings'][0]['after'], 'Use it.')
                self.assertIn('No account', found['notes'])

    def test_saved_profile_selection_reaches_both_cli_commands(self):
        self.executable(
            'args=sys.argv[1:]\nPath('
            + repr(str(self.capture))
            + ').write_text(json.dumps(args))\n'
            "value={'content':'Synthetic output','notes':'Fixture CLI; no account.'}\n"
            "if '--output-last-message' in args:\n Path(args[args.index('--output-last-message')+1]).write_text(json.dumps(value))\n"
            "else:\n print(json.dumps({'structured_output':value}))\n"
        )
        for agent in ('codex', 'claude'):
            with (
                patch.object(
                    blog_worker.source_curator, 'executable', return_value=str(self.binary)
                ),
                patch.object(blog_worker.source_curator, 'codex_options', return_value=[]),
            ):
                blog_worker.generate(
                    agent,
                    {},
                    'Synthetic',
                    seconds=5,
                    model_selection={'model': 'saved-profile', 'effort': 'high'},
                )
            args = json.loads(self.capture.read_text())
            self.assertEqual(args[args.index('--model') + 1], 'saved-profile')
            if agent == 'codex':
                self.assertIn('model_reasoning_effort="high"', args)
            else:
                self.assertEqual(args[args.index('--effort') + 1], 'high')

    def test_shared_model_and_reasoning_reach_both_worker_clis(self):
        self.executable(
            'args=sys.argv[1:]\nPath('
            + repr(str(self.capture))
            + ').write_text(json.dumps(args))\n'
            "value={'content':'Synthetic output','notes':'Fixture CLI; no account.'}\n"
            "if '--output-last-message' in args:\n Path(args[args.index('--output-last-message')+1]).write_text(json.dumps(value))\n"
            "else:\n print(json.dumps({'structured_output':value}))\n"
        )
        for agent in ('codex', 'claude'):
            config = Path(os.environ['STUDIOS_CONFIG'])
            config.write_text(
                json.dumps(
                    {
                        'schema': 1,
                        'assistant': {'agent': agent, 'model': 'fixture-model', 'effort': 'high'},
                    }
                )
            )
            with (
                patch.object(
                    blog_worker.source_curator, 'executable', return_value=str(self.binary)
                ),
                patch.object(blog_worker.source_curator, 'codex_options', return_value=[]),
            ):
                blog_worker.generate(agent, {}, 'Synthetic job', seconds=5)
            args = json.loads(self.capture.read_text())
            self.assertEqual(args[args.index('--model') + 1], 'fixture-model')
            if agent == 'codex':
                self.assertIn('model_reasoning_effort="high"', args)
            else:
                self.assertEqual(args[args.index('--effort') + 1], 'high')

    def test_timeout_ends_the_cli_process(self):
        self.executable('time.sleep(30)\n')
        with patch.object(blog_worker.source_curator, 'executable', return_value=str(self.binary)):
            with self.assertRaisesRegex(ValueError, 'time limit'):
                blog_worker.generate('claude', {}, 'Synthetic', seconds=0.1)

    def test_stop_ends_the_cli_process(self):
        self.executable('time.sleep(30)\n')
        stop = threading.Event()
        stop.set()
        with patch.object(blog_worker.source_curator, 'executable', return_value=str(self.binary)):
            with self.assertRaisesRegex(ValueError, 'stopped'):
                blog_worker.generate('claude', {}, 'Synthetic', seconds=5, stop=stop)


class RunnerHubTests(Fixture):
    def test_decisions_and_selected_context_survive_a_second_clone(self):
        from hub_fixtures import FakeProvider
        from hub import Registry
        from hub_workspace import Workspace
        import hub_workspace

        provider = FakeProvider(self.base / 'remotes')
        a, b = Registry(self.base / 'a-hubs', provider), Registry(self.base / 'b-hubs', provider)
        ident = a.create('fixture/guided-blogs', 'Guided blogs')['hub']
        b.join('fixture/guided-blogs')
        other = self.base / 'other-author'
        studio.initialize(other)
        wa, wb = Workspace(self.root, a.hub(ident)), Workspace(other, b.hub(ident))
        source = self.source('A fictional gateway routes synthetic requests.')
        self.file.write_text('Use short direct sentences. No invented experience.')
        profile = self.command(
            'profile',
            'create',
            '--name',
            'Avery',
            '--guide-file',
            str(self.file),
            '--status',
            'confirmed',
        )
        with patch.object(
            hub_workspace, 'active', side_effect=lambda root: wa if root == self.root else wb
        ):
            found = runner.create(
                self.root,
                {
                    'title': 'A synthetic shared blog',
                    'audience': 'Authors',
                    'goal': 'Explain a fixture',
                    'research': 'none',
                    'sources': [source['id']],
                    'profile': profile['id'],
                },
            )
            found = runner.submit(
                self.root,
                found['id'],
                'outline',
                {'content': '# Outline\nSynthetic argument.', 'notes': ''},
                found['expected'],
            )
            found = runner.decide(self.root, found['id'], found['expected'], 'approve')
            shared = wa.publish_selected({'articles': [found['id']]})['items'][0]
            wb.hub.refresh()
            local_id = wb.checkout_selected({'articles': [shared['item']]})['items'][0]['local_id']
            resumed = runner.engine(other).describe(local_id)
            self.assertEqual(resumed['stages'][0]['status'], 'approved')
            self.assertEqual(resumed['next'], 'draft')
            self.assertFalse(resumed['enabled'])
            self.assertEqual(resumed['approval'], 'conversation')
            previous = runner.document(other, local_id, 'outline')['previous']
            self.assertEqual(previous, '# Outline\nSynthetic argument.')
            runner.ENGINES.pop(str(other), None)


class SharedPatternTests(RunnerCase):
    """What every studio's run screen says the same way: the stops, the "now" line, honest
    retries and a note for the next job."""

    def worker(self, calls=None):
        def worker(*args, **kwargs):
            if calls is not None:
                calls.append(kwargs)
            return {'content': '# Synthetic stage\nSynthetic writing.', 'notes': 'Checked.'}

        return worker

    def test_settings_say_the_shared_review_level(self):
        import studios_config

        self.assertEqual(runner.settings(self.root)['review_level'], 'step_by_step')
        studios_config.update({'review': {'level': 'balanced'}})
        self.assertEqual(runner.settings(self.root)['review_level'], 'balanced')

    def test_the_worker_records_when_it_started_and_the_page_reads_it(self):
        found = self.create(page=True, stop='draft')
        engine = runner.Engine(self.root, worker=self.worker())
        self.addCleanup(engine.close)
        seen = []

        def worker(*args, **kwargs):
            seen.append(engine.describe(found['id']))
            return self.worker()(*args, **kwargs)

        engine.worker = worker
        engine.control(found['id'], 'resume')
        self.assertIsNone(engine.describe(found['id'])['started_at'])
        engine.once(found['id'])
        self.assertEqual(seen[0]['status'], 'working')
        self.assertRegex(seen[0]['started_at'], r'^\d{4}-\d\d-\d\dT')
        self.assertIsNone(
            engine.describe(found['id'])['started_at'], 'a job that ended is not still timed'
        )

    def test_the_listing_puts_the_blog_that_changed_last_first(self):
        first = self.create(page=True)
        second = self.create(page=True, title='A later synthetic blog')
        listed = [row['id'] for row in runner.catalog(self.root)['items']]
        self.assertEqual(listed, [second['id'], first['id']])
        self.approve(self.submit(first, page=True), page=True)
        listed = [row['id'] for row in runner.catalog(self.root)['items']]
        self.assertEqual(listed, [first['id'], second['id']])
        self.assertTrue(all(row['touched'] for row in runner.catalog(self.root)['items']))

    def test_try_again_with_more_time_raises_the_step_limit(self):
        found = self.create(page=True, stop='draft')
        engine = runner.engine(self.root)
        self.addCleanup(engine.close)
        engine.keep_local(
            found['id'],
            {'enabled': False, 'status': 'failed', 'error': 'This step reached its time limit.'},
        )
        shown = engine.describe(found['id'])
        again = runner.dispatch(
            self.root, 'retry', {'id': found['id'], 'expected': shown['expected'], 'seconds': 1200}
        )
        self.assertEqual(again['seconds'], 1200)
        self.assertEqual(again['status'], 'queued')
        self.assertEqual(runner.load(self.root, found['id'])[2]['seconds'], 1200)
        shown = engine.describe(found['id'])
        with self.assertRaisesRegex(ValueError, 'between 30 and 3600'):
            runner.dispatch(
                self.root,
                'retry',
                {'id': found['id'], 'expected': shown['expected'], 'seconds': 9999},
            )
        with self.assertRaisesRegex(ValueError, 'Unknown run field'):
            runner.dispatch(
                self.root,
                'approve',
                {'id': found['id'], 'expected': shown['expected'], 'seconds': 1200},
            )

    def test_a_note_goes_with_the_next_job_without_stopping_it(self):
        calls = []

        def worker(*args, **kwargs):
            calls.append(args)
            return {'content': '# Synthetic stage\nSynthetic writing.', 'notes': 'Checked.'}

        found = self.create(page=True, stop='draft')
        engine = runner.engine(self.root)
        self.addCleanup(engine.close)
        engine.worker = worker
        engine.control(found['id'], 'resume')
        engine.once(found['id'])
        found = self.approve(engine.describe(found['id']), page=True)
        shown = engine.describe(found['id'])
        self.assertEqual((shown['status'], shown['note_stage']), ('queued', 'draft'))
        noted = runner.dispatch(
            self.root,
            'note',
            {
                'id': found['id'],
                'expected': found['expected'],
                'request': 'Mention the fictional gateway.',
            },
        )
        self.assertEqual(noted['status'], 'queued', 'a note stops nothing')
        self.assertEqual(noted['noted'], 'draft')
        self.assertEqual(noted['expected'], found['expected'], 'a note is not a new version')
        self.assertEqual(noted['notes'], {'draft': 'Mention the fictional gateway.'})
        noted = runner.dispatch(
            self.root,
            'note',
            {'id': found['id'], 'expected': noted['expected'], 'request': 'Keep it short.'},
        )
        self.assertEqual(noted['notes']['draft'], 'Mention the fictional gateway.\nKeep it short.')
        engine.once(found['id'])
        # The worker takes (engine, payload, guidance): the note rides in the payload.
        self.assertEqual(calls[-1][1]['changes'], 'Mention the fictional gateway.\nKeep it short.')
        self.assertEqual(engine.describe(found['id'])['status'], 'waiting-for-approval')
        with self.assertRaisesRegex(ValueError, 'up to 8000'):
            runner.dispatch(
                self.root,
                'note',
                {
                    'id': found['id'],
                    'expected': engine.describe(found['id'])['expected'],
                    'request': '',
                },
            )

    def test_a_note_left_while_a_worker_runs_lands_and_the_submission_still_lands(self):
        found = self.create(page=True, stop='draft')
        engine = runner.engine(self.root)
        self.addCleanup(engine.close)
        seen = []

        def worker(*args, **kwargs):
            # Mid-job, from the page: the note goes to the stage after the one being written.
            shown = engine.describe(found['id'])
            seen.append(shown['note_stage'])
            runner.dispatch(
                self.root,
                'note',
                {
                    'id': found['id'],
                    'expected': shown['expected'],
                    'request': 'Lead with the restart story.',
                },
            )
            return {'content': '# Outline\nSynthetic argument.', 'notes': 'Checked.'}

        engine.worker = worker
        engine.control(found['id'], 'resume')
        engine.once(found['id'])
        shown = engine.describe(found['id'])
        self.assertEqual(seen, ['draft'])
        self.assertEqual(
            (shown['status'], shown['error']),
            ('waiting-for-approval', ''),
            'the submission landed: a note changed no version',
        )
        self.assertEqual(shown['notes'], {'draft': 'Lead with the restart story.'})
        self.assertEqual(runner.job(self.root, found['id'])[1]['changes'], '')
        self.approve(shown, page=True)
        self.assertEqual(
            runner.job(self.root, found['id'])[1]['changes'], 'Lead with the restart story.'
        )

    def test_a_note_while_a_decision_waits_goes_to_the_stage_after_it(self):
        found = self.create(page=True, stop='draft')
        found = self.submit(found, page=True)
        shown = runner.engine(self.root).describe(found['id'])
        self.assertEqual((shown['awaits'], shown['note_stage']), ('decision', 'draft'))
        noted = runner.dispatch(
            self.root,
            'note',
            {'id': found['id'], 'expected': found['expected'], 'request': 'Shorter sentences.'},
        )
        self.assertEqual((noted['noted'], noted['expected']), ('draft', found['expected']))
        # With nothing after the stage that waits, there is nowhere for a note to go.
        last = self.submit(self.create(page=True, mode='outline'), page=True)
        self.assertIsNone(runner.engine(self.root).describe(last['id'])['note_stage'])
        with self.assertRaisesRegex(ValueError, 'no later step'):
            runner.dispatch(
                self.root,
                'note',
                {'id': last['id'], 'expected': last['expected'], 'request': 'Too late.'},
            )


class FinishTests(RunnerCase):
    def test_the_final_stop_carries_the_approved_draft_beside_the_package(self):
        found = self.create(page=True)
        for _ in range(3):
            found = self.approve(self.submit(found, page=True), page=True)
        self.assertEqual(found['next'], 'package')
        found = self.submit(found, content='# Handoff', page=True)
        shown = runner.document(self.root, found['id'], 'package')
        self.assertEqual([item['stage'] for item in shown['bundle']], ['draft'])
        self.assertIn('Synthetic writing', shown['bundle'][0]['content'])
        # Step by step reviews each stage alone; only the final stop opens the draft again.
        self.assertEqual(runner.document(self.root, found['id'], 'draft')['bundle'], [])


class DeleteTests(RunnerCase):
    """Delete stops the job, takes the blog out of the lists and keeps it for 30 days."""

    def plant(self, ident):
        import tool_jobs

        studio.write_json(studio.inside(self.root, '.active-article.json'), {'id': ident})
        for receipt, local in (('a' * 64, ident), ('b' * 64, 'other-blog')):
            studio.write_json(
                studio.inside(self.root, '.desk-receipts', receipt + '.json'),
                {'id': receipt, 'local_id': local, 'group': 'article'},
            )
        studio.write_json(
            studio.inside(self.root, '.blog-runs', 'diagnostics', ident + '.json'), {'at': 'x'}
        )
        for job, article in (('c' * 32, ident), ('d' * 32, 'other-blog')):
            tool_jobs.write(
                self.root,
                {
                    'id': job,
                    'kind': 'repurpose',
                    'status': 'queued',
                    'attempts': 0,
                    'created_at': studio.now(),
                    'metadata': {'article': article},
                    'result': None,
                    'error': '',
                },
            )

    def delete(self, found, **changes):
        return management.dispatch(
            self.root,
            'blog-delete',
            {'id': found['id'], 'expected': found['expected'], 'title': found['title'], **changes},
        )

    def test_delete_needs_the_shown_version_and_the_typed_title(self):
        found = self.create(page=True)
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.delete(found, expected='stale')
        with self.assertRaisesRegex(ValueError, 'title'):
            self.delete(found, title='Another title')
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            self.delete(found, extra=True)
        self.assertTrue(studio.item(self.root, 'articles', found['id']))
        self.assertEqual(runner.catalog(self.root)['deleted'], [])

    def test_delete_accepts_the_title_as_a_person_types_it(self):
        # Curly quotes, an en dash and a double space in the stored title; plain typing deletes it.
        found = self.create(page=True, title='From agent “pilots” to governed  production – 2026')
        with self.assertRaisesRegex(ValueError, 'title'):
            self.delete(found, title='From agent pilots to production')
        result = self.delete(found, title='  from agent "pilots" to governed production - 2026 ')
        self.assertTrue(result['deleted'])
        self.assertEqual([row['id'] for row in runner.catalog(self.root)['deleted']], [found['id']])

    def test_delete_ignores_a_byte_order_mark_at_the_start_of_the_stored_title(self):
        # The page's \s counts U+FEFF as a space, so the server must agree.
        found = self.create(page=True, title='\ufeffMarked gateway guide')
        result = self.delete(found, title='Marked gateway guide')
        self.assertTrue(result['deleted'])

    def test_delete_stops_the_worker_and_removes_what_this_computer_kept(self):
        entered = threading.Event()

        def worker(*args, **kwargs):
            entered.set()
            engine.stop.wait(5)  # the worker ends once the delete asks it to stop
            return {'content': 'A late outline', 'notes': ''}

        found = self.create(page=True)
        ident = found['id']
        self.plant(ident)
        engine = runner.Engine(self.root, worker)
        runner.ENGINES[str(self.root)] = engine
        engine.control(ident, 'resume')
        thread = threading.Thread(target=engine.once, args=(ident,))
        thread.start()
        try:
            self.assertTrue(entered.wait(2))
            shown = engine.describe(ident)
            self.assertEqual(shown['status'], 'working')
            result = self.delete(shown)
        finally:
            engine.stop.set()
            thread.join(5)
        self.assertNotIn('id', result, 'no post-action may recreate the blog')
        self.assertTrue(result['deleted'])
        self.assertEqual(result['title'], found['title'])
        self.assertFalse(studio.inside(self.root, 'articles', ident).exists())
        self.assertFalse(studio.inside(self.root, '.blog-runs', ident + '.json').exists())
        self.assertFalse(studio.inside(self.root, '.active-article.json').exists())
        self.assertFalse(
            studio.inside(self.root, '.blog-runs', 'diagnostics', ident + '.json').exists()
        )
        receipts = sorted(p.name for p in studio.inside(self.root, '.desk-receipts').glob('*'))
        self.assertEqual(receipts, ['b' * 64 + '.json'])
        import tool_jobs

        self.assertEqual(tool_jobs.read(self.root, 'd' * 32)['status'], 'queued')
        self.assertFalse(
            studio.inside(self.root, '.blog-runs', 'tools', 'c' * 32 + '.json').exists()
        )
        self.assertIsNone(engine.current)
        listing = runner.catalog(self.root)
        self.assertEqual([row['id'] for row in listing['items']], [])
        self.assertEqual(
            [(row['id'], row['title']) for row in listing['deleted']], [(ident, found['title'])]
        )
        self.assertTrue(listing['deleted'][0]['deleted_at'])
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            studio.item(self.root, 'articles', ident)

    def test_a_deleted_blog_can_be_restored_for_thirty_days(self):
        found = self.create(page=True)
        ident = found['id']
        found = self.approve(self.submit(found, page=True), page=True)
        self.delete(found)
        restored = management.dispatch(self.root, 'blog-restore', {'id': ident})
        self.assertEqual(restored['id'], ident)
        self.assertTrue(restored['restored'])
        directory, record = studio.item(self.root, 'articles', ident)
        self.assertEqual(record['title'], 'Synthetic gateway guide')
        self.assertTrue((directory / 'OUTLINE.md').is_file())
        shown = runner.engine(self.root).describe(ident)
        self.assertEqual(shown['status'], 'stopped', 'nothing starts by itself after a restore')
        self.assertFalse(shown['enabled'])
        self.assertEqual(shown['stages'][0]['status'], 'approved')
        self.assertEqual(runner.catalog(self.root)['deleted'], [])
        with self.assertRaisesRegex(ValueError, 'recently deleted'):
            management.dispatch(self.root, 'blog-restore', {'id': ident})
        # An old record and whatever it kept are let go of when the list is read.
        import blog_delete

        self.delete(runner.engine(self.root).describe(ident))
        record_path = studio.inside(self.root, '.blog-runs', 'deleted', ident + '.json')
        old = studio.read_json(record_path)
        old['deleted_at'] = '2020-01-01T00:00:00+00:00'
        studio.write_json(record_path, old)
        self.assertEqual(runner.catalog(self.root)['deleted'], [])
        self.assertFalse(record_path.exists())
        self.assertFalse(studio.inside(self.root, '.blog-runs', 'deleted', ident).exists())
        self.assertEqual(blog_delete.KEEP_DAYS, 30)

    def test_delete_waits_for_a_working_tool_job_and_the_loop_goes_on(self):
        import tool_jobs

        entered = threading.Event()

        def worker(*args, **kwargs):
            entered.set()
            kwargs['stop'].wait(5)  # the tool job ends once the delete cancels it
            return {'content': 'late copy', 'notes': ''}

        found = self.create(page=True)
        ident = found['id']
        engine = runner.Engine(self.root, worker)
        runner.ENGINES[str(self.root)] = engine
        tool_jobs.write(
            self.root,
            {
                'id': 'c' * 32,
                'kind': 'repurpose',
                'status': 'queued',
                'attempts': 0,
                'created_at': studio.now(),
                'metadata': {'article': ident},
                'result': None,
                'error': '',
                'engine': 'codex',
                'payload': {},
                'guidance': '',
                'seconds': 5,
            },
        )
        outcome = {}

        def serve_once():
            try:
                tool_jobs.once(engine)
                outcome['ok'] = True
            except Exception as exc:  # noqa: BLE001 - the loop must never see one
                outcome['error'] = repr(exc)

        thread = threading.Thread(target=serve_once)
        thread.start()
        try:
            self.assertTrue(entered.wait(3))
            self.assertEqual(engine.current, 'tool:' + 'c' * 32)
            result = self.delete(engine.describe(ident))
        finally:
            engine.stop.set()
            thread.join(5)
        self.assertTrue(result['deleted'])
        self.assertEqual(outcome, {'ok': True}, 'the serve loop survives the deletion')
        self.assertIsNone(engine.current)
        self.assertFalse(tool_jobs.path(self.root, 'c' * 32).exists())
        self.assertFalse(studio.inside(self.root, 'articles', ident).exists())
        # A job whose file went while it worked is let go of without a word.
        tool_jobs.write(
            self.root,
            {
                'id': 'e' * 32,
                'kind': 'repurpose',
                'status': 'queued',
                'attempts': 0,
                'created_at': studio.now(),
                'metadata': {'article': 'elsewhere'},
                'result': None,
                'error': '',
                'engine': 'codex',
                'payload': {},
                'guidance': '',
                'seconds': 5,
            },
        )
        engine.stop.clear()
        engine.worker = lambda *a, **k: (
            tool_jobs.path(self.root, 'e' * 32).unlink(),
            {'content': 'copy', 'notes': ''},
        )[1]
        tool_jobs.once(engine)
        self.assertIsNone(engine.current)

    def test_a_worker_that_does_not_end_in_time_leaves_the_blog_stopped_and_kept(self):
        import blog_delete

        entered, release = threading.Event(), threading.Event()

        def worker(*args, **kwargs):
            entered.set()
            release.wait(5)  # ignores the stop
            return {'content': 'late', 'notes': ''}

        found = self.create(page=True)
        ident = found['id']
        engine = runner.Engine(self.root, worker)
        runner.ENGINES[str(self.root)] = engine
        engine.control(ident, 'resume')
        thread = threading.Thread(target=engine.once, args=(ident,))
        thread.start()
        try:
            self.assertTrue(entered.wait(2))
            with patch.object(blog_delete, 'STOP_WAIT', 0.2):
                with self.assertRaisesRegex(ValueError, 'not ended yet'):
                    self.delete(engine.describe(ident))
        finally:
            release.set()
            thread.join(5)
        self.assertTrue(studio.inside(self.root, 'articles', ident, 'session.json').is_file())
        self.assertFalse(engine.local(ident)['enabled'], 'it was stopped all the same')
        self.assertEqual(runner.catalog(self.root)['deleted'], [])

    def test_restore_finds_the_blog_already_back_and_drops_the_record(self):
        import blog_delete

        found = self.create(page=True)
        ident = found['id']
        self.delete(found)
        kept = studio.inside(self.root, '.blog-runs', 'deleted', ident)
        shutil.copytree(kept / 'blog', studio.inside(self.root, 'articles', ident))
        restored = management.dispatch(self.root, 'blog-restore', {'id': ident})
        self.assertEqual((restored['id'], restored['notice']), (ident, blog_delete.ALREADY_BACK))
        self.assertFalse(kept.exists())
        self.assertEqual(runner.catalog(self.root)['deleted'], [])
        # A different blog under the same ID is never overwritten.
        other = self.create(page=True)
        self.delete(other)
        session = studio.inside(self.root, 'articles', other['id'], 'session.json')
        studio.write_json(session, {'id': other['id'], 'title': 'Another blog'})
        with self.assertRaisesRegex(ValueError, 'different blog'):
            management.dispatch(self.root, 'blog-restore', {'id': other['id']})

    def test_a_kept_copy_refuses_a_second_delete_and_a_bad_record_is_left_out(self):
        found = self.create(page=True)
        studio.inside(self.root, '.blog-runs', 'deleted', found['id'], 'blog').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, 'still kept'):
            self.delete(found)
        self.assertTrue(studio.inside(self.root, 'articles', found['id']).is_dir())
        folder = studio.inside(self.root, '.blog-runs', 'deleted')
        (folder / 'broken.json').write_text('{"deleted_at": "yesterday", "title": "Broken"}')
        (folder / 'naive.json').write_text(
            '{"deleted_at": "2099-01-01T00:00:00", "title": "Naive"}'
        )
        (folder / 'list.json').write_text('[1, 2]')
        listed = runner.catalog(self.root)['deleted']
        self.assertEqual([row['title'] for row in listed], ['Naive'])
        self.assertTrue((folder / 'broken.json').exists(), 'what cannot be read is left alone')

    def test_a_saved_draft_without_a_run_is_deleted_against_its_detail_version(self):
        ident = self.article()
        shown = management.detail(self.root, ident)
        result = management.dispatch(
            self.root,
            'blog-delete',
            {'id': ident, 'expected': shown['expected'], 'title': shown['title']},
        )
        self.assertTrue(result['deleted'])
        self.assertFalse(studio.inside(self.root, 'articles', ident).exists())
        self.assertEqual(runner.catalog(self.root)['deleted'][0]['title'], 'Gateway guide')

    def test_the_finished_run_says_where_it_was_published(self):
        found = self.create(page=True)
        for _ in range(4):
            found = self.approve(self.submit(found, page=True), page=True)
        self.assertTrue(found['complete'])
        self.assertIsNone(runner.engine(self.root).describe(found['id'])['publication'])
        detail = management.detail(self.root, found['id'])
        management.dispatch(
            self.root,
            'schedule',
            {
                'id': found['id'],
                'expected': detail['expected'],
                'stage': 'published',
                'confirm_stage': True,
                'publication_url': 'https://example.com/post',
            },
        )
        self.assertEqual(
            runner.engine(self.root).describe(found['id'])['publication'],
            'https://example.com/post',
        )


class FilesCase(RunnerCase):
    """Uploaded material and a from-files run, for the tests below."""

    ANGLES = (
        '# Three angles\n\n'
        '## Retries are a budget\n\n'
        'Platform engineers · Retries cost more than they save without a budget · Leans on notes.md\n\n'
        '## The gateway is a contract\n\n'
        'API authors · Treat the gateway as the public contract · Leans on notes.md, plain.txt\n\n'
        '## Fewer hops, fewer surprises\n\n'
        'Team leads · Every hop is a failure mode · Leans on plain.txt\n'
    )

    def material(self, *files, keep=False):
        import base64
        import blog_library

        with patch.object(blog_library.shutil, 'which', return_value=None):
            result = management.dispatch(
                self.root,
                'upload',
                {
                    'operation': studio.digest(repr(files).encode())[:32],
                    'purpose': 'material',
                    'keep': keep,
                    'analyze': False,
                    'files': [
                        {'filename': name, 'content': base64.b64encode(body.encode()).decode()}
                        for name, body in files
                    ],
                },
            )
        return [row['source']['id'] for row in result['files']]

    def from_files(self, page=True, **extra):
        sources = extra.pop(
            'sources',
            self.material(
                ('notes.md', 'Retries cost money. ' * 40), ('plain.txt', 'Hops add latency. ' * 40)
            ),
        )
        return runner.create(
            self.root,
            {'mode': 'from-files', 'sources': sources, 'goal': 'A post for the team blog', **extra},
            'page' if page else 'conversation',
        )


class FromFilesTests(FilesCase):
    """Write from my files: uploaded material, three angles, then the normal run."""

    def test_from_files_starts_with_the_angles_step(self):
        found = self.from_files()
        self.assertEqual([row['stage'] for row in found['stages']], ['angles'])
        self.assertEqual(found['mode'], 'from-files')
        self.assertEqual(found['next'], 'angles')
        _, record, run = runner.load(self.root, found['id'])
        self.assertEqual(record['research_policy'], 'supplied-only')
        self.assertNotIn('research_contract', run)
        self.assertEqual(run['after_angles'], {'research': 'none', 'stop': 'package'})
        self.assertEqual(len(record['sources']), 2)
        self.assertEqual(record['title'], 'From my files')
        self.assertEqual(run['brief']['goal'], 'A post for the team blog')
        # The files, not the empty brief, are what the worker reads.
        found, payload, guidance = runner.job(self.root, found['id'])
        self.assertEqual([source['name'] for source in payload['sources']], ['notes', 'plain'])
        self.assertIn('## ', guidance)
        self.assertIn('three', guidance.lower())
        self.assertIn('Leans on', guidance)
        with self.assertRaisesRegex(ValueError, 'file'):
            self.from_files(sources=[])
        pending = self.material(('scan.pdf', '%PDF-fixture'))
        with self.assertRaisesRegex(ValueError, 'text'):
            self.from_files(sources=pending)
        web = self.from_files(research='web-allowed', stop='draft')
        _, _, run = runner.load(self.root, web['id'])
        self.assertEqual(run['after_angles'], {'research': 'web-allowed', 'stop': 'draft'})
        self.assertEqual([row['stage'] for row in web['stages']], ['angles'])

    def test_the_angles_always_wait_for_the_person(self):
        import studios_config

        studios_config.update({'review': {'level': 'automatic'}})
        found = self.from_files()
        found = self.submit(found, self.ANGLES, page=True)
        self.assertEqual(found['awaits'], 'decision')
        self.assertEqual(found['stages'][0]['status'], 'draft')
        self.assertFalse(found['stages'][0]['auto_accepted'])

    def test_picking_an_angle_starts_the_normal_run_from_the_outline(self):
        found = self.submit(self.from_files(), self.ANGLES, page=True)
        with studio.locked(self.root), patch.object(runner.Engine, 'control', return_value={}):
            runner.dispatch(
                self.root,
                'develop',
                {
                    'id': found['id'],
                    'expected': found['expected'],
                    'request': 'The gateway is a contract\nKeep it under 900 words.',
                },
            )
        directory, record, run = runner.load(self.root, found['id'])
        self.assertEqual(record['title'], 'The gateway is a contract')
        self.assertEqual(run['brief']['audience'], 'API authors')
        self.assertIn('Treat the gateway as the public contract', run['brief']['goal'])
        self.assertEqual(record['writing_preferences']['audience'], 'API authors')
        self.assertEqual(run['pipeline'], ['angles', 'outline', 'draft', 'review', 'package'])
        self.assertEqual(run['mode'], 'from-files')
        self.assertEqual(run['stages']['outline']['status'], 'pending')
        self.assertIn('Keep it under 900 words.', run['stages']['outline']['request'])
        self.assertIn('notes.md, plain.txt', run['stages']['outline']['request'])
        self.assertTrue((directory / 'derived/blog-angles.md').is_file())
        found = runner.survey(self.root, found['id'])
        self.assertEqual(found['next'], 'outline')
        self.assertEqual(found['title'], 'The gateway is a contract')
        _, payload, guidance = runner.job(self.root, found['id'])
        self.assertEqual(len(payload['sources']), 2)
        self.assertIn('The gateway is a contract', guidance)
        self.assertNotIn('minimal edit', guidance)
        # A heading that is not one of the saved angles is refused.
        other = self.submit(self.from_files(), self.ANGLES, page=True)
        with studio.locked(self.root), self.assertRaisesRegex(ValueError, 'one of the'):
            runner.dispatch(
                self.root,
                'develop',
                {'id': other['id'], 'expected': other['expected'], 'request': 'Something else'},
            )

    def test_web_research_comes_before_the_outline_when_asked(self):
        found = self.submit(self.from_files(research='web-allowed'), self.ANGLES, page=True)
        with studio.locked(self.root), patch.object(runner.Engine, 'control', return_value={}):
            runner.dispatch(
                self.root,
                'develop',
                {
                    'id': found['id'],
                    'expected': found['expected'],
                    'request': 'Retries are a budget',
                },
            )
        _, record, run = runner.load(self.root, found['id'])
        self.assertEqual(
            run['pipeline'],
            ['angles', 'research-plan', 'research', 'outline', 'draft', 'review', 'package'],
        )
        self.assertEqual(record['research_policy'], 'web-allowed')
        self.assertEqual(runner.survey(self.root, found['id'])['next'], 'research-plan')

    def test_none_of_these_asks_for_three_different_angles(self):
        found = self.submit(self.from_files(), self.ANGLES, page=True)
        found = runner.decide(
            self.root,
            found['id'],
            found['expected'],
            'changes',
            'Closer to the on-call experience.',
            page=True,
            target='angles',
        )
        self.assertEqual(found['next'], 'angles')
        _, payload, guidance = runner.job(self.root, found['id'])
        self.assertEqual(payload['documents']['angles'], self.ANGLES)
        self.assertIn('three different angles', guidance)
        self.assertNotIn('minimal edit', guidance)
        self.assertIn('Closer to the on-call experience.', guidance)

    def test_oversized_files_are_excerpted_and_named_instead_of_refused(self):
        big = 'Retries cost money. ' * 16_000  # 320,000 characters
        sources = self.material(('big.md', big), ('small.txt', 'Hops add latency.'))
        found = self.from_files(sources=sources)
        self.assertEqual(found['excerpted'], ['big'])
        _, record, run = runner.load(self.root, found['id'])
        payload = runner.inputs(self.root, record, run)
        self.assertLess(len(json.dumps(payload)), 300_000)
        big_source = next(source for source in payload['sources'] if source['name'] == 'big')
        self.assertTrue(big_source['excerpted'])
        self.assertEqual(big_source['total_chars'], len(big))
        self.assertLess(len(big_source['text']), len(big))
        self.assertTrue(big_source['text'].startswith('Retries cost money.'))
        small = next(source for source in payload['sources'] if source['name'] == 'small')
        self.assertNotIn('excerpted', small)
        self.assertEqual(small['text'], 'Hops add latency.')
        self.assertIn('big', runner.engine(self.root).describe(found['id'])['excerpted'])
        # Other modes still refuse rather than silently cutting a source.
        with self.assertRaisesRegex(ValueError, 'too large'):
            self.create(sources=sources)

    def test_a_chat_run_can_write_from_files_too(self):
        sources = self.material(('notes.md', 'Retries cost money.'))
        args = studio.parser().parse_args(
            [
                '--root',
                str(self.root),
                'run',
                'create',
                '--mode',
                'from-files',
                '--source',
                sources[0],
                '--goal',
                'A short post',
                '--audience',
                '',
            ]
        )
        found = runner.command(self.root, args)
        self.assertEqual(found['next'], 'angles')
        self.assertEqual(found['approval'], 'conversation')
        found = self.submit(found, self.ANGLES)
        chosen = studio.parser().parse_args(
            [
                '--root',
                str(self.root),
                'run',
                'choose',
                '--id',
                found['id'],
                '--expected',
                found['expected'],
                '--angle',
                'Fewer hops, fewer surprises',
                '--note',
                'Name the hops.',
            ]
        )
        found = runner.command(self.root, chosen)
        self.assertEqual(found['next'], 'outline')
        self.assertEqual(found['title'], 'Fewer hops, fewer surprises')
        self.assertEqual(found['brief']['audience'], 'Team leads')
        with self.assertRaisesRegex(ValueError, 'changed'):
            runner.command(self.root, chosen)


class FromFilesReviewTests(FilesCase):
    """The angles gate keeps its decision, and a deleted blog takes its files with it."""

    def chosen(self, angle='The gateway is a contract'):
        found = self.submit(self.from_files(), self.ANGLES, page=True)
        with studio.locked(self.root), patch.object(runner.Engine, 'control', return_value={}):
            runner.dispatch(
                self.root,
                'develop',
                {'id': found['id'], 'expected': found['expected'], 'request': angle},
            )
        return runner.survey(self.root, found['id'])

    def test_the_angles_cannot_be_approved_as_if_they_were_the_blog(self):
        found = self.submit(self.from_files(page=False), self.ANGLES)
        with self.assertRaisesRegex(ValueError, 'run choose'):
            self.approve(found)
        page = self.submit(self.from_files(), self.ANGLES, page=True)
        with studio.locked(self.root), self.assertRaisesRegex(ValueError, 'run choose'):
            runner.dispatch(self.root, 'approve', {'id': page['id'], 'expected': page['expected']})
        self.assertFalse(runner.survey(self.root, page['id'])['complete'])

    def test_choosing_keeps_the_angles_decided_at_the_head_of_the_run(self):
        found = self.chosen()
        self.assertEqual(
            [row['stage'] for row in found['stages']],
            ['angles', 'outline', 'draft', 'review', 'package'],
        )
        angles = found['stages'][0]
        self.assertEqual((angles['status'], angles['accepted_by']), ('approved', 'page'))
        self.assertEqual(found['next'], 'outline')
        _, _, run = runner.load(self.root, found['id'])
        self.assertEqual(run['chosen_angle']['title'], 'The gateway is a contract')
        self.assertEqual(run['chosen_angle']['says'].split(' · ')[0], 'API authors')
        # The outline is next and reads the angles it came from.
        _, payload, _ = runner.job(self.root, found['id'])
        self.assertEqual(payload['documents']['angles'], self.ANGLES)
        found = self.submit(found, page=True)
        self.assertEqual(self.approve(found, page=True)['next'], 'draft')

    def test_the_worker_must_return_exactly_three_distinct_angles(self):
        found = self.from_files()
        for content in (
            '# Angles\n\n## Only one\n\nReaders · A point · Leans on notes.md',
            self.ANGLES + '\n## A fourth\n\nMore · More · Leans on notes.md\n',
        ):
            with self.subTest(content=content[:40]):
                with self.assertRaisesRegex(ValueError, 'exactly three'):
                    self.submit(found, content, page=True)
        twice = self.ANGLES.replace('Fewer hops, fewer surprises', 'Retries are a budget')
        found = self.submit(found, twice, page=True)
        with studio.locked(self.root), self.assertRaisesRegex(ValueError, 'share a heading'):
            runner.dispatch(
                self.root,
                'develop',
                {
                    'id': found['id'],
                    'expected': found['expected'],
                    'request': 'Retries are a budget',
                },
            )

    def test_excerpts_follow_the_persons_words_not_the_defaults(self):
        found = self.from_files(goal='')
        _, record, run = runner.load(self.root, found['id'])
        self.assertEqual(runner.run_terms(record, run), [])
        found = self.from_files(goal='Why the gateway retries matter for our team')
        _, record, run = runner.load(self.root, found['id'])
        words = runner.run_terms(record, run)
        self.assertIn('gateway', words)
        self.assertIn('retries', words)
        for common in ('why', 'the', 'for', 'our', 'with', 'from', 'files', 'uploaded'):
            self.assertNotIn(common, words)

    def test_deleting_a_blog_keeps_its_files_with_it_and_restore_brings_them_back(self):
        import base64

        ours, shared = self.material(('mine.md', 'Only mine. ' * 20), ('both.md', 'Shared. ' * 20))
        single = management.dispatch(
            self.root,
            'upload',
            {
                'operation': 'c' * 32,
                'filename': 'single.md',
                'content': base64.b64encode(b'One file on its own.').decode(),
                'purpose': 'material',
                'analyze': False,
            },
        )['source']['id']
        found = runner.create(
            self.root,
            {'mode': 'from-files', 'sources': [ours, shared, single], 'goal': 'A post'},
            'page',
        )
        _, record, _ = runner.load(self.root, found['id'])
        self.assertEqual(record['material'], [ours, shared, single])
        self.create(page=True, sources=[shared])  # another blog pins the second file
        material = self.root / '.uploads' / 'material'
        ledgers = sorted((self.root / '.uploads').glob('*.json'))
        self.assertEqual(len(ledgers), 2)
        management.dispatch(
            self.root,
            'blog-delete',
            {'id': found['id'], 'expected': found['expected'], 'title': found['title']},
        )
        self.assertFalse((material / ours).exists())
        self.assertTrue((material / shared).is_dir(), 'a file another blog pins stays')
        self.assertEqual(list((self.root / '.uploads').glob('*.json')), [])
        import blog_delete

        kept = blog_delete.folder(self.root) / found['id'] / 'material' / ours
        self.assertTrue(kept.is_dir(), 'kept for restore')
        management.dispatch(self.root, 'blog-restore', {'id': found['id']})
        self.assertTrue((material / ours / 'content.md').is_file())
        _, payload, _ = runner.job(self.root, found['id'])
        self.assertEqual(len(payload['sources']), 3)
