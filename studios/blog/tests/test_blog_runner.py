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
        if content is None and found['next'] == 'claims-map':
            directory, record, run = runner.load(self.root, found['id'])
            source = runner.inputs(self.root, record, run)['sources'][0]
            content = (
                f'- **Synthetic claim** — {source["name"]} (`{source["id"]}`): "{source["text"]}"'
            )
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
    def test_a_developed_idea_is_reviewed_and_packaged(self):
        found = self.submit(self.create(page=True, mode='ideas', stop='outline'), page=True)
        found = self.approve(found, page=True)
        with studio.locked(self.root), patch.object(runner.Engine, 'control', return_value={}):
            runner.dispatch(
                self.root,
                'develop',
                {
                    'id': found['id'],
                    'expected': found['expected'],
                    'request': 'Develop the first angle.',
                },
            )
        _, record, run = runner.load(self.root, found['id'])
        self.assertEqual(run['pipeline'], ['outline', 'draft', 'review', 'package'])
        self.assertEqual(record['stop_point'], 'package')

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

    def test_developing_an_idea_finishes_review_and_package(self):
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
        self.assertEqual(run['pipeline'], ['outline', 'draft', 'review', 'package'])
        self.assertEqual(record['stop_point'], 'package')
        self.assertIn('second idea', run['stages']['outline']['request'])
        self.assertEqual((directory / 'OUTLINE.md').read_text(), ideas)
        found = runner.survey(self.root, found['id'])
        for stage in ('outline', 'draft', 'review', 'package'):
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
        found = self.create(research='web-allowed', stop='outline', sources=[source['id']])
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

    def test_marking_a_pinned_source_as_a_sample_keeps_its_runs_open(self):
        import management

        source = self.source('A fictional gateway routes synthetic requests.')
        found = self.approve(self.submit(self.create(sources=[source['id']])))
        before = runner.survey(self.root, found['id'])
        _, payload, _ = runner.job(self.root, found['id'])
        for purpose in ('voice-sample', 'style-sample'):
            management.dispatch(
                self.root,
                'tool-action',
                {
                    'action': 'source-purpose',
                    'source': source['id'],
                    'purpose': purpose,
                    'author': 'Avery',
                },
            )
        self.assertEqual(studio.item(self.root, 'sources', source['id'])[1]['revision'], 3)
        after = runner.survey(self.root, found['id'])
        self.assertEqual(after['stages'], before['stages'], 'a sample mark is not a change')
        self.assertEqual(after['expected'], before['expected'], 'stage pins hold')
        self.assertEqual(runner.job(self.root, found['id'])[1], payload)
        # New words in a later revision do not reach the blog: it reads the revision it pinned.
        self.file.write_text('Changed synthetic words.')
        self.command('source', 'update', '--id', source['id'], '--text-file', str(self.file))
        self.assertEqual(runner.survey(self.root, found['id'])['expected'], before['expected'])
        self.assertEqual(runner.job(self.root, found['id'])[1], payload)

    def test_a_pinned_source_without_its_saved_revision_still_refuses(self):
        import management

        source = self.source('A fictional gateway routes synthetic requests.')
        found = self.approve(self.submit(self.create(sources=[source['id']])))
        management.dispatch(
            self.root,
            'tool-action',
            {'action': 'source-purpose', 'source': source['id'], 'purpose': 'style-sample'},
        )
        directory, _ = studio.item(self.root, 'sources', source['id'])
        shutil.rmtree(directory / 'revisions' / '1')
        with self.assertRaisesRegex(ValueError, 'selected source changed'):
            runner.survey(self.root, found['id'])

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
        self.assertEqual([item['stage'] for item in shown['bundle']], ['claims-map'])
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
        # An oversized source is excerpted to the budget, and the run says so by name.
        source = self.source('Synthetic evidence ' * 20_000)
        found = self.create(sources=[source['id']])
        self.assertEqual(
            runner.engine(self.root).describe(found['id'])['excerpted'], ['Specification']
        )
        _, record, run = runner.load(self.root, found['id'])
        kept = runner.inputs(self.root, record, run)['sources'][0]
        self.assertTrue(kept['excerpted'])
        self.assertEqual(kept['total_chars'], 19 * 20_000)
        self.assertLess(kept['kept_chars'], kept['total_chars'])

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
        self.assertEqual(shown['status'], 'stale')
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
            with self.assertRaisesRegex(ValueError, 'time a step may take'):
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

    def test_a_tone_nudge_travels_with_the_voice_and_older_projections_hold(self):
        from hub_fixtures import FakeProvider
        from hub import Registry
        from hub_workspace import Workspace
        import hub_workspace

        provider = FakeProvider(self.base / 'remotes')
        a, b = Registry(self.base / 'a-hubs', provider), Registry(self.base / 'b-hubs', provider)
        ident = a.create('fixture/voice-tone', 'Voice tone')['hub']
        b.join('fixture/voice-tone')
        other = self.base / 'other-author'
        studio.initialize(other)
        wa, wb = Workspace(self.root, a.hub(ident)), Workspace(other, b.hub(ident))
        self.file.write_text('Use short direct sentences.')
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
            shared = {}
            for tone in ('Warm', ''):
                found = runner.create(
                    self.root,
                    {
                        'title': 'Tone ' + (tone or 'none'),
                        'audience': 'Authors',
                        'goal': 'Explain a fixture',
                        'research': 'none',
                        'profile': profile['id'],
                        'tone': tone,
                    },
                )
                shared[tone] = wa.publish_selected({'articles': [found['id']]})['items'][0]
            revisions = wa.hub.graph()['revisions']
            projected = {
                tone: revisions[ref['revision']]['data']['studio']['voice']
                for tone, ref in shared.items()
            }
            self.assertEqual(projected['Warm']['tone'], 'Warm')
            self.assertEqual(set(projected['']), {'mode', 'ref'}, 'no tone, the same projection')
            wb.hub.refresh()
            local_id = wb.checkout_selected({'articles': [shared['Warm']['item']]})['items'][0][
                'local_id'
            ]
            voice = studio.item(other, 'articles', local_id)[1]['voice']
            self.assertEqual((voice['mode'], voice['tone']), ('profile', 'Warm'))
            runner.ENGINES.pop(str(other), None)
            runner.ENGINES.pop(str(self.root), None)


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

    def test_the_view_says_steps_left_and_the_next_stop(self):
        import studios_config

        studios_config.update({'review': {'level': 'balanced'}})
        found = self.create(page=True)
        self.assertEqual(found['ahead']['steps_left'], 4)
        self.assertEqual(found['ahead']['next_stop'], 'Outline')
        self.assertEqual(found['ahead']['next_gate'], 'outline')
        found = self.approve(self.submit(found, page=True), page=True)
        self.assertEqual(found['ahead']['steps_left'], 3)
        self.assertEqual(found['ahead']['next_gate'], 'package', 'Balanced reads the handoff next')
        self.assertEqual(found['ahead']['next_stop'], runner.STAGES['package'][0])
        # A saved run with no jobs recorded says nothing of what it spent.
        engine = runner.Engine(self.root, worker=self.worker())
        self.addCleanup(engine.close)
        shown = engine.describe(found['id'])['ahead']
        self.assertEqual((shown['jobs'], shown['spent']), (0, None))

    def test_redo_says_what_a_change_draws_again(self):
        found = self.create(page=True, stop='package')
        engine = runner.Engine(self.root, worker=self.worker())
        self.addCleanup(engine.close)
        redo = engine.describe(found['id'])['redo']
        self.assertEqual(redo['draft']['stages'], ['draft', 'review', 'package'])
        self.assertEqual(
            redo['draft']['says'],
            (
                'Drawn again: the draft and every step after it, 3 steps; this computer has no '
                'record of what they cost.'
            ),
        )
        state = engine.local(found['id'])
        state['jobs'] = [
            {'stage': stage, 'seconds': 300, 'tokens': None, 'dollars': 0.5}
            for stage in ('outline', 'draft', 'review', 'package')
        ]
        engine.keep_local(found['id'], state)
        redo = engine.describe(found['id'])['redo']
        self.assertEqual(
            redo['review']['says'],
            (
                'Drawn again: the review and every step after it, 2 steps. Last time they took '
                '10 minutes and about $1.00.'
            ),
        )

    def test_stage_labels(self):
        self.assertEqual(runner.STAGES['package'][0], 'Handoff')
        found = self.create(page=True)
        self.assertEqual(found['stages'][-1]['label'], 'Handoff')
        with self.assertRaisesRegex(ValueError, 'or the handoff'):
            self.create(page=True, title='Stopped nowhere', stop='angles')

    def blogs(self):
        folder = self.root / 'articles'
        return sorted(path.name for path in folder.iterdir()) if folder.is_dir() else []

    def test_a_blog_keeps_the_level_its_form_chose(self):
        import studios_config
        from studio_core import review_policy

        studios_config.update({'review': {'level': 'balanced'}})
        found = self.create(page=True, review_level='step_by_step', review_seen='balanced')
        _, _, run = runner.load(self.root, found['id'])
        self.assertEqual(review_policy.level(run), 'step_by_step')
        self.assertEqual(found['review_level'], 'step_by_step')
        self.assertEqual(studios_config.read()[0]['review'], {'level': 'balanced'})
        with self.assertRaisesRegex(
            ValueError, 'Choose Balanced, Automatic draft, or Step by step'
        ):
            self.create(page=True, review_level='fast', review_seen='balanced')

    def test_the_default_is_written_only_with_the_chip_and_refused_when_stale(self):
        import studios_config
        from studio_core import review_policy

        studios_config.update({'review': {'level': 'balanced'}})
        self.create(
            page=True, review_level='step_by_step', review_seen='balanced', review_default=True
        )
        self.assertEqual(studios_config.read()[0]['review'], {'level': 'step_by_step'})
        studios_config.update({'review': {'level': 'automatic'}})
        made = self.blogs()
        with self.assertRaises(ValueError) as caught:
            self.create(
                page=True,
                title='Another synthetic guide',
                review_level='balanced',
                review_seen='step_by_step',
                review_default=True,
            )
        self.assertEqual(str(caught.exception), review_policy.STALE)
        self.assertEqual(self.blogs(), made, 'a refused start makes no blog')
        self.assertEqual(studios_config.read()[0]['review'], {'level': 'automatic'})

    def test_an_unreadable_shared_file_still_starts_a_blog_at_its_level(self):
        import studios_config
        from studio_core import review_policy

        studios_config.path().write_text('{', encoding='utf-8')
        found = self.create(page=True, review_level='balanced', review_seen='step_by_step')
        _, _, run = runner.load(self.root, found['id'])
        self.assertEqual(review_policy.level(run), 'balanced')
        found = self.create(page=True, title='No level chosen')
        _, _, run = runner.load(self.root, found['id'])
        self.assertEqual(review_policy.level(run), 'step_by_step', 'never more autonomy')
        made = self.blogs()
        with self.assertRaises(ValueError):
            self.create(
                page=True,
                title='With the chip',
                review_level='automatic',
                review_seen='step_by_step',
                review_default=True,
            )
        self.assertEqual(self.blogs(), made)
        self.assertEqual(studios_config.path().read_text(), '{')

    def test_review_level_route_saves_and_refuses(self):
        import studios_config
        from studio_core import review_policy

        studios_config.update({'review': {'level': 'balanced'}})
        shown = management.dispatch(
            self.root, 'review-level', {'level': 'automatic', 'seen': 'balanced'}
        )
        self.assertEqual(shown['review_level'], 'automatic')
        self.assertEqual(studios_config.read()[0]['review'], {'level': 'automatic'})
        with self.assertRaises(ValueError) as caught:
            management.dispatch(
                self.root, 'review-level', {'level': 'balanced', 'seen': 'balanced'}
            )
        self.assertEqual(str(caught.exception), review_policy.STALE)
        with self.assertRaisesRegex(
            ValueError, 'Choose Balanced, Automatic draft, or Step by step'
        ):
            management.dispatch(self.root, 'review-level', {'level': 'fast', 'seen': 'automatic'})
        self.assertEqual(studios_config.read()[0]['review'], {'level': 'automatic'})

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


class StyleTests(RunnerCase):
    """A run pins a style beside its voice, and the writing job reads that revision."""

    def test_a_run_pins_its_style_and_the_job_carries_it(self):
        self.assertIn(
            'product-announcement', [row['id'] for row in runner.options(self.root)['styles']]
        )
        found = self.create(page=True, style='product-announcement')
        _, record = studio.item(self.root, 'articles', found['id'])
        self.assertEqual(record['style'], {'style_id': 'product-announcement', 'revision': 1})
        self.assertEqual((found['style_name'], found['voice_name']), ('Product announcement', None))
        _, payload, guidance = runner.job(self.root, found['id'])
        self.assertEqual(payload['style']['name'], 'Product announcement')
        self.assertIn('The news is in the first sentence.', payload['style']['guide'])
        self.assertIn('the style wins', guidance)
        self.assertIn('the style wins', blog_worker.POLICY)
        directory, _, run = runner.load(self.root, found['id'])
        for check, carried in (('polish', False), ('shape', True)):
            studio.write_json(
                studio.inside(directory, runner.STATE), {**run, 'editor_check': check}
            )
            _, checked, guidance = runner.job(self.root, found['id'])
            self.assertEqual('SELECTED STYLE' in guidance, carried)
            self.assertEqual(checked['style'] is not None, carried, check)
            self.assertEqual('Product announcement' in guidance.split('\n', 1)[0], carried)
        studio.write_json(studio.inside(directory, runner.STATE), run)
        guide = self.base / 'style.md'
        guide.write_text('Changed later.')
        self.command('style', 'save', '--id', 'product-announcement', '--guide-file', str(guide))
        _, payload, _ = runner.job(self.root, found['id'])
        self.assertNotIn(
            'Changed later.', payload['style']['guide'], 'a later save does not move the pin'
        )
        self.command(
            'style',
            'retire',
            '--id',
            'product-announcement',
            '--expected-revision',
            '2',
            '--confirmed',
        )
        with self.assertRaisesRegex(ValueError, 'retired'):
            self.create(page=True, style='product-announcement')
        with self.assertRaisesRegex(ValueError, 'Unknown styles'):
            self.create(page=True, style='no-such-style')
        plain = self.create(page=True)
        self.assertNotIn('style', studio.item(self.root, 'articles', plain['id'])[1])
        self.assertIsNone(runner.job(self.root, plain['id'])[1]['style'])
        _, record, run = runner.load(self.root, plain['id'])
        self.assertNotIn(
            'style', runner.inputs(self.root, record, run), 'stage pins saved before styles hold'
        )
        self.assertIsNone(plain['style_name'])

    def test_a_minimal_edit_keeps_to_its_request_without_the_style(self):
        found = self.approve(self.submit(self.create(page=True, style='how-to'), page=True), True)
        self.assertIsNotNone(runner.job(self.root, found['id'])[1]['style'])
        found = self.submit(found, '# Draft\nA fictional paragraph.', page=True)
        found = runner.decide(
            self.root, found['id'], found['expected'], 'changes', 'Shorten it.', page=True
        )
        _, payload, guidance = runner.job(self.root, found['id'])
        self.assertIn('minimal edit, not a rewrite', guidance)
        self.assertIsNone(payload['style'])
        self.assertNotIn('SELECTED STYLE', guidance)
        self.assertNotIn('How-to', guidance.split('\n', 1)[0])

    def test_a_saved_blog_keeps_its_style_when_none_is_sent(self):
        ident = self.article()
        directory, record = studio.item(self.root, 'articles', ident)
        record['style'] = {'style_id': 'how-to', 'revision': 1}
        studio.persist(directory, 'articles', record)
        found = self.create(page=True, id=ident, style='', mode='review', stop='review')
        _, record = studio.item(self.root, 'articles', found['id'])
        self.assertEqual(record['style'], {'style_id': 'how-to', 'revision': 1})
        self.assertEqual(found['style_name'], 'How-to and tutorial')

    def test_a_refused_run_leaves_no_copied_starter(self):
        with self.assertRaises(ValueError):
            self.create(page=True, style='how-to', sources=['no-such-source'])
        large = self.source('Synthetic gateway detail. ' * 12_000)  # over one job's context
        # Sources are excerpted to their budget on every path; a larger one lets this source
        # through whole, so the job's context check refuses it after the style was checked.
        with (
            patch.object(runner, 'SOURCE_BUDGET', 400_000),
            self.assertRaisesRegex(ValueError, 'too large'),
        ):
            self.create(page=True, style='how-to', sources=[large['id']])
        self.assertFalse((self.root / 'styles' / 'how-to').exists())
        self.assertEqual(runner.catalog(self.root)['items'], [])

    def test_a_listing_names_a_style_from_its_current_record_or_starter(self):
        import styles

        self.assertEqual(styles.name_of(self.root, 'how-to'), 'How-to and tutorial')
        self.assertIsNone(styles.name_of(self.root, 'no-such-style'))
        self.assertEqual(
            runner.style_name(self.root, {'style': {'style_id': 'how-to', 'revision': 1}}),
            'How-to and tutorial',
        )
        self.assertFalse((self.root / 'styles' / 'how-to').exists(), 'naming copies nothing')


class VoiceChoiceTests(RunnerCase):
    """The page's Write as: the default voice applies unless the person chose another."""

    def voice(self, name='Avery', guide='Short direct sentences.', status='confirmed'):
        self.file.write_text(guide)
        return self.command(
            'profile', 'create', '--name', name, '--guide-file', str(self.file), '--status', status
        )

    def default(self, profile):
        import writing_defaults

        words = ['defaults', 'set', '--scope', 'personal', '--key', 'voice', '--value']
        value = json.dumps({'profile_id': profile['id'], 'revision': 1})
        args = studio.parser().parse_args(['--root', str(self.root), *words, value])
        writing_defaults.command(self.root, args)

    def voice_of(self, found):
        return studio.item(self.root, 'articles', found['id'])[1]['voice']

    def files(self):
        return {
            path.relative_to(self.root): path.read_bytes()
            for path in self.root.rglob('*')
            if path.is_file()
        }

    def test_the_default_voice_applies_unless_the_person_chose_another(self):
        self.assertEqual(
            self.voice_of(self.create(page=True, tone='Warm')), {'mode': 'tone', 'tone': 'Warm'}
        )
        mine, other = self.voice(), self.voice('Blake', 'Long, careful sentences.')
        self.default(mine)
        absent = self.voice_of(self.create(page=True))
        self.assertEqual(
            (absent['mode'], absent['profile_id'], absent['revision']), ('profile', mine['id'], 1)
        )
        nudged = self.voice_of(self.create(page=True, tone='Warm'))
        self.assertEqual((nudged['mode'], nudged['profile_id']), ('profile', mine['id']))
        self.assertEqual(
            self.voice_of(self.create(page=True, profile='', tone='Warm')),
            {'mode': 'tone', 'tone': 'Warm'},
            'No particular voice uses the described tone',
        )
        chosen = self.voice_of(self.create(page=True, profile=other['id']))
        self.assertEqual((chosen['mode'], chosen['profile_id']), ('profile', other['id']))

    def test_a_tone_beside_a_voice_is_kept_as_a_nudge(self):
        import writing_defaults

        mine = self.voice()
        found = self.create(page=True, profile=mine['id'], tone='Warm')
        pinned = {'mode': 'profile', 'profile_id': mine['id'], 'revision': 1}
        self.assertEqual(self.voice_of(found), {**pinned, 'tone': 'Warm'})
        _, record, run = runner.load(self.root, found['id'])
        payload = runner.inputs(self.root, record, run)
        self.assertEqual(payload['voice']['tone'], 'Warm')
        self.assertIn('Short direct sentences.', payload['voice']['guide'])
        resolved = writing_defaults.resolve(self.root, record)
        self.assertEqual(resolved['problems'], [])
        self.assertEqual(
            resolved['values']['voice']['value'], {'profile_id': mine['id'], 'revision': 1}
        )
        self.assertEqual(
            self.voice_of(self.create(page=True, profile=mine['id'])),
            pinned,
            'without a tone the voice has no tone key, so earlier pins hold',
        )
        self.default(mine)
        self.assertEqual(
            self.voice_of(self.create(page=True, tone='Warm')), {**pinned, 'tone': 'Warm'}
        )
        chat = self.command(
            'article',
            'create',
            '--title',
            'Chat',
            '--mode',
            'first-draft',
            '--profile',
            mine['id'],
            '--tone',
            'Warm',
        )
        self.assertEqual(chat['voice'], {**pinned, 'tone': 'Warm'})

    def test_the_worker_brief_names_the_voice_style_and_tone(self):
        mine = self.voice()
        found = self.create(page=True, profile=mine['id'], tone='Warm', style='how-to')
        _, record, run = runner.load(self.root, found['id'])
        pins = runner.inputs(self.root, record, run)
        guidance = runner.job(self.root, found['id'])[2]
        self.assertTrue(
            guidance.startswith(
                'Write as Avery (voice guide revision 1, confirmed), in the shape of How-to '
                'and tutorial. Tone nudge: Warm.\n\n'
            ),
            guidance[:200],
        )
        self.assertEqual(runner.inputs(self.root, record, run), pins, 'the line is not an input')
        self.file.write_text('A later guide.')
        self.command(
            'profile',
            'save',
            '--id',
            mine['id'],
            '--name',
            'Avery Later',
            '--guide-file',
            str(self.file),
            '--status',
            'provisional',
        )
        self.assertTrue(
            runner.job(self.root, found['id'])[2].startswith(
                'Write as Avery (voice guide revision 1, confirmed)'
            ),
            'the pinned revision is named, not the latest',
        )
        plain = self.create(page=True, profile='', tone='Warm')
        self.assertTrue(
            runner.job(self.root, plain['id'])[2].startswith(
                'No author voice is pinned; follow voice.tone.\n\n'
            )
        )
        bare_tone = self.create(page=True, profile='', tone='')
        self.assertTrue(
            runner.job(self.root, bare_tone['id'])[2].startswith(
                'No author voice is pinned; write plainly in the house style.\n\n'
            )
        )
        bare = self.create(page=True, profile=mine['id'])
        self.assertTrue(
            runner.job(self.root, bare['id'])[2].startswith(
                'Write as Avery Later (voice guide revision 2, provisional).\n\n'
            )
        )

    def test_options_name_the_personal_default_voice_and_write_nothing(self):
        self.assertIsNone(runner.options(self.root)['default_voice'])
        mine = self.voice(status='provisional')
        self.default(mine)
        before = self.files()
        self.assertEqual(
            runner.options(self.root)['default_voice'],
            {
                'scope': 'personal',
                'profile': mine['id'],
                'name': 'Avery',
                'revision': 1,
                'status': 'provisional',
            },
        )
        self.assertEqual(self.files(), before)

    def team(self, status='confirmed', competing=False):
        """A stub Team Hub whose only team default is a shared voice."""
        from types import SimpleNamespace

        item, revision = 'a' * 32, 'b' * 32
        rows = ['c' * 32, 'e' * 32] if competing else ['c' * 32]
        revisions = {
            row: {
                'item': 'd' * 32,
                'kind': 'context',
                'scope': {'level': 'team', 'key': ''},
                'status': 'active',
                'data': {
                    'key': 'writing-default:voice',
                    'value': {'item': item, 'revision': revision},
                },
            }
            for row in rows
        }
        revisions[revision] = {
            'item': item,
            'revision': revision,
            'kind': 'voice',
            'status': 'active',
            'title': 'Team voice',
            'data': {'studio': {'name': 'Team voice', 'status': status}},
        }
        graph = {'heads': {'d' * 32: rows}, 'revisions': revisions}
        return SimpleNamespace(hub=SimpleNamespace(graph=lambda: graph))

    def test_options_name_no_default_voice_they_cannot_use(self):
        from hub_store import HubError

        for adapter, why in (
            (self.team(competing=True), 'competing team defaults'),
            (self.team(status='retired'), 'a retired shared voice'),
        ):
            with patch('hub_workspace.active', return_value=adapter):
                self.assertIsNone(runner.options(self.root)['default_voice'], why)
        with patch('hub_workspace.active', side_effect=HubError('This Team Hub is not joined.')):
            shown = runner.options(self.root)
        self.assertIsNone(shown['default_voice'], 'the wizard opens without its Team Hub')
        self.assertIn('profiles', shown)

    def test_a_manuscript_keeps_its_own_voice_unless_the_person_picks_one(self):
        mine = self.voice()
        self.default(mine)
        draft = self.source('# A synthetic draft\n\nThe gateway routes requests.')
        found = self.create(page=True, mode='review', manuscript=draft['id'], tone='Warm')
        self.assertEqual(self.voice_of(found)['mode'], 'preserve')
        self.assertTrue(
            runner.job(self.root, found['id'])[2].startswith(
                'No author voice is pinned; keep the manuscript’s own voice. Tone nudge: Warm.\n\n'
            )
        )
        existing = self.command(
            'article', 'create', '--title', 'Imported', '--mode', 'existing', '--voice', 'preserve'
        )
        self.file.write_text('# Imported\n\nAn original sentence.')
        self.command(
            'article',
            'save',
            '--id',
            existing['id'],
            '--kind',
            'original',
            '--file',
            str(self.file),
        )
        found = self.create(page=True, id=existing['id'], mode='review')
        self.assertEqual(self.voice_of(found)['mode'], 'preserve')
        self.assertTrue(
            runner.job(self.root, found['id'])[2].startswith(
                'No author voice is pinned; keep the manuscript’s own voice.\n\n'
            )
        )
        picked = self.create(page=True, mode='review', manuscript=draft['id'], profile=mine['id'])
        self.assertEqual(self.voice_of(picked)['profile_id'], mine['id'])

    def test_a_run_says_how_its_voice_was_chosen(self):
        mine = self.voice()
        pinned = self.create(page=True, profile=mine['id'])
        self.assertEqual(
            (
                pinned['voice_mode'],
                pinned['voice_profile'],
                pinned['voice_revision'],
                pinned['voice_name'],
            ),
            ('profile', mine['id'], mine['revision'], 'Avery'),
        )
        toned = self.create(page=True, profile='', tone='Warm')
        self.assertEqual(
            (toned['voice_mode'], toned['voice_profile'], toned['voice_revision']),
            ('tone', None, None),
        )
        draft = self.source('# A synthetic draft\n\nThe gateway routes requests.')
        kept = self.create(page=True, mode='review', manuscript=draft['id'])
        self.assertEqual((kept['voice_mode'], kept['voice_profile']), ('preserve', None))
        self.assertEqual(runner.engine(self.root).describe(kept['id'])['voice_mode'], 'preserve')

    def test_the_settings_default_tone_is_no_nudge(self):
        mine = self.voice()
        usual = runner.settings(self.root)['defaults']['tone']
        self.assertNotIn(
            'tone', self.voice_of(self.create(page=True, profile=mine['id'], tone=usual))
        )
        self.assertEqual(
            self.voice_of(self.create(page=True, profile='', tone=usual)),
            {'mode': 'tone', 'tone': usual},
            'without a voice the tone is the description',
        )
        self.default(mine)
        self.assertNotIn('tone', self.voice_of(self.create(page=True, tone=usual)))
        self.assertEqual(self.voice_of(self.create(page=True, tone='Warm'))['tone'], 'Warm')

    def test_options_read_a_team_default_voice_without_checking_it_out(self):
        from types import SimpleNamespace

        item, revision, row = 'a' * 32, 'b' * 32, 'c' * 32
        graph = {
            'heads': {'d' * 32: [row]},
            'revisions': {
                row: {
                    'item': 'd' * 32,
                    'kind': 'context',
                    'scope': {'level': 'team', 'key': ''},
                    'status': 'active',
                    'data': {
                        'key': 'writing-default:voice',
                        'value': {'item': item, 'revision': revision},
                    },
                },
                revision: {
                    'item': item,
                    'revision': revision,
                    'kind': 'voice',
                    'status': 'active',
                    'title': 'Team voice',
                    'data': {'studio': {'name': 'Team voice', 'status': 'confirmed'}},
                },
            },
        }

        def checkout(*args):
            raise AssertionError('reading options checks nothing out')

        adapter = SimpleNamespace(hub=SimpleNamespace(graph=lambda: graph), _checkout=checkout)
        before = self.files()
        with patch('hub_workspace.active', return_value=adapter):
            shown = runner.options(self.root)['default_voice']
        self.assertEqual(
            shown,
            {
                'scope': 'team',
                'profile': None,
                'name': 'Team voice',
                'revision': revision,
                'status': 'confirmed',
            },
        )
        self.assertEqual(self.files(), before)


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
        # A blog from a brief reads the same files, excerpted the same way and pinned to it.
        found = self.create(sources=sources)
        _, record, run = runner.load(self.root, found['id'])
        self.assertEqual(record['material'], sources)
        payload = runner.inputs(self.root, record, run)
        self.assertLess(len(json.dumps(payload)), 300_000)
        self.assertTrue(
            next(source for source in payload['sources'] if source['name'] == 'big')['excerpted']
        )
        self.assertEqual(runner.engine(self.root).describe(found['id'])['excerpted'], ['big'])

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


class ExampleTests(FilesCase):
    """An example of the kind of post shows its shape and never supplies facts."""

    def example(self, *files):
        import base64
        import blog_library

        with patch.object(blog_library.shutil, 'which', return_value=None):
            result = management.dispatch(
                self.root,
                'upload',
                {
                    'operation': studio.digest(repr(('example', files)).encode())[:32],
                    'purpose': 'material',
                    'analyze': False,
                    'files': [
                        {
                            'filename': name,
                            'content': base64.b64encode(body.encode()).decode(),
                            'purpose': 'inspiration',
                        }
                        for name, body in files
                    ],
                },
            )
        return [row['source']['id'] for row in result['files']]

    def develop(self, found, angle='The gateway is a contract'):
        found = self.submit(found, self.ANGLES, page=True)
        with studio.locked(self.root), patch.object(runner.Engine, 'control', return_value={}):
            runner.dispatch(
                self.root,
                'develop',
                {'id': found['id'], 'expected': found['expected'], 'request': angle},
            )
        return runner.survey(self.root, found['id'])

    def test_examples_leave_the_sources_and_reach_the_worker_as_examples(self):
        facts = self.material(('notes.md', 'Retries cost money. ' * 40))
        examples = self.example(('launch.md', 'We shipped the gateway in March. ' * 40))
        found = self.from_files(sources=facts + examples)
        _, record, run = runner.load(self.root, found['id'])
        self.assertEqual(set(record['material']), set(facts + examples))
        payload = runner.inputs(self.root, record, run)
        self.assertEqual([source['name'] for source in payload['sources']], ['notes'])
        self.assertEqual([source['name'] for source in payload['examples']], ['launch'])
        self.assertEqual(set(payload['examples'][0]), set(payload['sources'][0]) - {'id'})
        self.assertEqual(payload['examples'][0]['purposes'], ['material', 'inspiration'])
        # A run without examples keeps its payload, and its saved pins, as they were.
        plain = self.from_files()
        _, record, run = runner.load(self.root, plain['id'])
        self.assertNotIn('examples', runner.inputs(self.root, record, run))
        found = self.develop(found)
        self.assertEqual(found['next'], 'outline')
        _, payload, guidance = runner.job(self.root, found['id'])
        self.assertEqual([source['name'] for source in payload['examples']], ['launch'])
        self.assertIn('take their shape, not their facts', guidance)
        while found['next'] != 'package':
            _, payload, guidance = runner.job(self.root, found['id'])
            self.assertEqual(len(payload['examples']), 1, found['next'])
            self.assertEqual(
                'take their shape, not their facts' in guidance,
                found['next'] in ('outline', 'draft'),
                found['next'],
            )
            found = self.approve(self.submit(found, page=True), page=True)
        _, payload, _ = runner.job(self.root, found['id'])
        self.assertEqual(payload['examples'], [])
        self.assertEqual(payload['sources'], [])
        self.assertIn('shape, length, moves and register', blog_worker.POLICY)

    def test_examples_are_excerpted_under_the_same_budget_and_named(self):
        big = 'We shipped the gateway in March. ' * 10_000  # 330,000 characters
        facts = self.material(('small.txt', 'Hops add latency.'))
        examples = self.example(('big.md', big))
        found = self.from_files(sources=facts + examples)
        self.assertEqual(found['excerpted'], ['big'])
        _, record, run = runner.load(self.root, found['id'])
        payload = runner.inputs(self.root, record, run)
        self.assertLess(len(json.dumps(payload)), 300_000)
        example = payload['examples'][0]
        self.assertTrue(example['excerpted'])
        self.assertEqual(example['total_chars'], len(big))
        self.assertNotIn('excerpted', payload['sources'][0])
        self.assertIn('big', runner.engine(self.root).describe(found['id'])['excerpted'])

    def test_research_reads_facts_and_references_but_never_an_example(self):
        import synthesis_research

        for purposes, expected in (
            (['reference'], True),
            (['material'], True),
            (['material', 'inspiration'], False),
            (['reference', 'inspiration'], False),
            (['inspiration'], False),
            (['voice-sample'], False),
        ):
            with self.subTest(purposes=purposes):
                self.assertEqual(
                    synthesis_research.offered({'purposes': purposes, 'status': 'ready'}),
                    expected,
                )
        self.assertFalse(
            synthesis_research.offered({'purposes': ['material'], 'status': 'pending'})
        )

    def test_the_draft_and_review_say_what_was_carried_over_from_an_example(self):
        example = (
            'When we launched Gateway Prime in March, requests dropped by 42 percent. '
            'Read https://example.invalid/launch for the numbers. Retries cost money.'
        )
        facts = self.material(('notes.md', 'Retries cost money. ' * 40))
        examples = self.example(('launch.md', example))
        found = self.develop(self.from_files(sources=facts + examples))
        found = self.approve(self.submit(found, page=True), page=True)  # outline
        self.assertEqual(found['next'], 'draft')
        _, payload, _ = runner.job(self.root, found['id'])
        self.assertEqual(payload['mechanical_checks']['findings'], [])
        draft = (
            '# Draft\n\nRequests dropped by 42 percent, as Gateway Prime showed; '
            'see https://example.invalid/launch. Retries cost money.\n'
        )
        found = self.submit(found, draft, page=True)
        shown = runner.document(self.root, found['id'], 'draft')
        row = next(check for check in shown['checks'] if 'example' in check['label'])
        self.assertFalse(row['passed'])
        self.assertEqual(row['label'], 'Carried over from an example')
        self.assertIn('https://example.invalid/launch', row['detail'])
        self.assertTrue(any('42 percent' in line for line in row['detail']), row['detail'])
        self.assertTrue(all(len(line) <= 120 for line in row['detail']))
        found = self.approve(found, page=True)
        _, payload, guidance = runner.job(self.root, found['id'])
        rules = [finding['rule'] for finding in payload['mechanical_checks']['findings']]
        self.assertIn('from-example', rules)
        self.assertIn('unsupported', guidance)
        self.assertIn('from-example', guidance)
        found = self.submit(found, page=True)  # the review
        shown = runner.document(self.root, found['id'], 'review')
        self.assertFalse(
            next(check for check in shown['checks'] if 'example' in check['label'])['passed']
        )
        # A draft that takes only the example's shape passes, and a run without examples
        # has no such row.
        clean = self.develop(
            self.from_files(
                sources=self.material(('n.md', 'Retries cost money.'))
                + self.example(('l.md', example))
            )
        )
        clean = self.approve(self.submit(clean, page=True), page=True)
        clean = self.submit(clean, '# Draft\n\nRetries cost money, as our notes say.\n', page=True)
        row = next(
            check
            for check in runner.document(self.root, clean['id'], 'draft')['checks']
            if 'example' in check['label']
        )
        self.assertTrue(row['passed'])
        self.assertEqual(row['label'], 'No passage carried over from an example')
        self.assertEqual(row['detail'], [])
        plain = self.develop(self.from_files())
        plain = self.submit(self.approve(self.submit(plain, page=True), page=True), page=True)
        self.assertFalse(
            any(
                'example' in check['label']
                for check in runner.document(self.root, plain['id'], 'draft')['checks']
            )
        )


class PointTests(FilesCase):
    """I know the point: a blog from files that starts at the outline, with no angles."""

    def point(self, page=True, **extra):
        return self.from_files(
            page=page,
            **{
                'point': True,
                'title': 'Announcing the gateway',
                'goal': 'The gateway is generally available and retries are budgeted.',
                'audience': 'Platform engineers',
                **extra,
            },
        )

    def test_the_point_builds_the_usual_pipeline_without_angles(self):
        found = self.point()
        self.assertEqual(
            [row['stage'] for row in found['stages']], ['outline', 'draft', 'review', 'package']
        )
        self.assertEqual(found['mode'], 'from-files')
        self.assertEqual(found['next'], 'outline')
        self.assertEqual(found['title'], 'Announcing the gateway')
        _, record, run = runner.load(self.root, found['id'])
        self.assertIs(run['angles'], False)
        self.assertNotIn('after_angles', run)
        self.assertEqual(
            run['brief']['goal'], 'The gateway is generally available and retries are budgeted.'
        )
        self.assertEqual(run['brief']['audience'], 'Platform engineers')
        self.assertEqual(len(record['material']), 2)
        self.assertEqual(record['stop_point'], 'package')
        _, payload, guidance = runner.job(self.root, found['id'])
        self.assertEqual([source['name'] for source in payload['sources']], ['notes', 'plain'])
        self.assertNotIn('three', guidance.lower())
        # The person's title and point steer which passages of a large file are kept.
        self.assertIn('gateway', runner.run_terms(record, run))
        web = self.point(research='web-allowed', stop='draft')
        self.assertEqual(
            [row['stage'] for row in web['stages']],
            ['research-plan', 'research', 'outline', 'draft'],
        )
        _, record, run = runner.load(self.root, web['id'])
        self.assertEqual(record['research_policy'], 'web-allowed')
        # An angles run says it has angles.
        _, _, run = runner.load(self.root, self.from_files()['id'])
        self.assertIs(run['angles'], True)

    def test_the_point_needs_a_title_a_point_and_a_reader(self):
        for missing in ('title', 'goal', 'audience'):
            with self.subTest(missing=missing), self.assertRaisesRegex(ValueError, missing):
                self.point(**{missing: ''})
        with self.assertRaisesRegex(ValueError, 'from files'):
            self.create(point=True)
        with self.assertRaisesRegex(ValueError, 'point'):
            self.from_files(point='yes')

    def test_develop_refuses_a_blog_without_angles(self):
        found = self.point()
        with (
            studio.locked(self.root),
            self.assertRaisesRegex(ValueError, 'no angles to choose from'),
        ):
            runner.dispatch(
                self.root,
                'develop',
                {'id': found['id'], 'expected': found['expected'], 'request': 'Any heading'},
            )
        self.assertEqual(runner.survey(self.root, found['id'])['next'], 'outline')
        chat = self.point(page=False)
        args = studio.parser().parse_args(
            [
                '--root',
                str(self.root),
                'run',
                'choose',
                '--id',
                chat['id'],
                '--expected',
                chat['expected'],
                '--angle',
                'Any',
            ]
        )
        with self.assertRaisesRegex(ValueError, 'no angles to choose from'):
            runner.command(self.root, args)

    def test_balanced_reads_the_draft_when_a_run_has_no_outline_stage(self):
        import studios_config

        studios_config.update({'review': {'level': 'balanced'}})
        found = self.create(mode='from-outline', outline_text='## Supplied outline', page=True)
        self.assertEqual([row['stage'] for row in found['stages']], ['draft', 'review', 'package'])
        found = self.submit(found, page=True)
        self.assertEqual(found['awaits'], 'decision')
        self.assertFalse(found['stages'][0]['auto_accepted'])
        found = self.submit(self.approve(found, page=True), page=True)  # the review
        self.assertEqual(found['awaits'], 'submission')
        self.assertTrue(found['stages'][1]['auto_accepted'])
        found = self.submit(found, page=True)  # the package
        self.assertEqual(found['awaits'], 'decision')
        # A run with an outline still reads the outline and continues through the draft.
        found = self.submit(self.create(page=True), page=True)
        self.assertEqual(found['awaits'], 'decision')
        found = self.submit(self.approve(found, page=True), page=True)
        self.assertEqual(found['awaits'], 'submission')
        self.assertTrue(found['stages'][1]['auto_accepted'])
        # The point from files has an outline, so Balanced stops there and at the end.
        found = self.submit(self.point(), page=True)
        self.assertEqual(found['awaits'], 'decision')


class WriteAsTests(RunnerCase):
    """The page's Write as select: Me is the personal default voice, when one is set."""

    def test_options_name_the_personal_default_voice(self):
        self.assertIsNone(runner.options(self.root)['default_voice'])
        self.file.write_text('Use short direct sentences. No invented experience.')
        profile = self.command(
            'profile', 'create', '--name', 'Avery', '--guide-file', str(self.file)
        )
        import writing_defaults

        args = studio.parser().parse_args(
            [
                '--root',
                str(self.root),
                'defaults',
                'set',
                '--scope',
                'personal',
                '--key',
                'voice',
                '--value',
                json.dumps({'profile_id': profile['id'], 'revision': 1}),
            ]
        )
        writing_defaults.command(self.root, args)
        found = runner.options(self.root)
        self.assertEqual(
            found['default_voice'],
            {
                'scope': 'personal',
                'profile': profile['id'],
                'name': 'Avery',
                'revision': 1,
                'status': 'provisional',
            },
        )
        self.assertEqual([p['status'] for p in found['profiles']], ['provisional'])
        # Me writes with the pinned revision; an unknown or malformed one is refused.
        pinned = self.create(profile=profile['id'], revision=1)
        _, record, _ = runner.load(self.root, pinned['id'])
        self.assertEqual(
            record['voice'], {'mode': 'profile', 'profile_id': profile['id'], 'revision': 1}
        )
        with self.assertRaisesRegex(ValueError, 'revision'):
            self.create(profile=profile['id'], revision=99)
        with self.assertRaisesRegex(ValueError, 'revision'):
            self.create(profile=profile['id'], revision='1')
        with self.assertRaisesRegex(ValueError, 'profile'):
            self.create(revision=1)
        # A default that no longer resolves is simply no default.
        import shutil

        shutil.rmtree(self.root / 'profiles' / profile['id'])
        self.assertIsNone(runner.options(self.root)['default_voice'])


class ResearchAccountTests(RunnerCase):
    def research_run(self):
        found = self.create(research='web-allowed')
        found = self.submit(found, '- **instance-min**: Minimum?')
        found = self.approve(found)
        return self.submit(found, '# Synthetic research')

    def test_the_research_stage_view_carries_the_account(self):
        from synthesis_fixture import research_stop

        found = self.research_run()
        directory, record, run = runner.load(self.root, found['id'])
        run['research_contract'] = {'schema': 2}
        studio.write_json(directory / runner.STATE, run)
        self.assertIsNone(runner.document(self.root, found['id'], 'research')['research'])
        research_stop(directory / 'research')
        shown = runner.document(self.root, found['id'], 'research')
        self.assertEqual(shown['research']['brief'], '# Prioritized handoff\n')
        self.assertEqual(shown['research']['questions'][0]['findings'], ['instance-min--capacity'])
        self.assertNotIn('synthetic-digest', json.dumps(shown['research']))

    def test_the_research_notes_say_what_the_check_said(self):
        from synthesis_fixture import research_stop
        from studio_core import research_contract, research_view
        import synthesis_research

        directory = self.base / 'synthetic-research'
        directory.mkdir()
        research_stop(directory / 'research')

        def never(*args, **kwargs):
            raise AssertionError('No provider job')

        with (
            patch.object(research_contract, 'runtime_for', return_value=directory),
            patch.object(research_contract.Workflow, 'run'),
            patch.object(research_contract, 'publish'),
        ):
            found = synthesis_research.generate(
                directory,
                {'brief': {}, 'research_contract': {}},
                {
                    'title': 'Synthetic',
                    'sources': [],
                    'documents': {},
                    'research_policy': 'supplied-only',
                },
                never,
                seconds=60,
                stop=threading.Event(),
            )
        self.assertEqual(found['notes'], research_view.CHECKED + ' An honest account.')
        self.assertNotIn('retained in research/', found['notes'])

    def test_a_research_change_is_priced(self):
        found = self.research_run()
        for _ in range(2):
            found = self.approve(found)
            found = self.submit(found)
        directory, record, run = runner.load(self.root, found['id'])
        run['research_contract'] = {'schema': 2}
        studio.write_json(directory / runner.STATE, run)
        runner.engine(self.root).keep_local(
            found['id'],
            {
                'research': {
                    'jobs': [
                        dict(phase='author', round=1, seconds=1800, dollars=6),
                        dict(phase='review', round=1, seconds=1080, dollars=3.8),
                    ]
                }
            },
        )
        words = runner.survey(self.root, found['id'])['research_price']['words']
        self.assertIn('48 minutes and $9.80', words)
        self.assertTrue(words.endswith('Then it makes again: the outline and the draft.'))
        runner.engine(self.root).keep_local(
            found['id'],
            {
                'research': {
                    'jobs': [
                        dict(phase='discovery', round=0, seconds=60, dollars=1),
                        dict(phase='author', round=1, seconds=1800, dollars=6),
                        dict(phase='review', round=1, seconds=1080, dollars=3.8),
                    ]
                }
            },
        )
        price = runner.survey(self.root, found['id'])['research_price']
        self.assertEqual(price['jobs'], 3)
        self.assertIn('49 minutes and $10.80', price['words'])


class RefreshResearchTests(RunnerCase):
    """The research, asked for again with its evidence brought up to date."""

    def test_a_change_request_may_bring_the_research_up_to_date(self):
        import synthesis_research

        found = self.create(research='web-allowed', page=True)
        directory, record, run = runner.load(self.root, found['id'])
        run['pipeline'] = [stage for stage in run['pipeline'] if stage != 'research-plan']
        studio.write_json(directory / runner.STATE, run)
        found = runner.survey(self.root, found['id'])
        self.assertEqual(found['next'], 'research')
        found = runner.decide(
            self.root,
            found['id'],
            found['expected'],
            'changes',
            '',
            page=True,
            target='research',
            refresh=True,
        )
        _, _, run = runner.load(self.root, found['id'])
        self.assertIs(run['stages']['research']['refresh'], True)
        self.assertEqual(run['stages']['research']['request'], 'Bring the evidence up to date.')
        _, payload, _ = runner.job(self.root, found['id'])
        self.assertIs(payload['refresh'], True)
        tasks = []

        def workflow(root, task, invoke, sources):
            tasks.append(task)
            raise ValueError('Stopped by the test.')

        with (
            patch.object(
                synthesis_research.research_contract, 'runtime_for', return_value=self.root
            ),
            patch.object(
                synthesis_research.research_contract.Workflow, 'run', side_effect=workflow
            ),
        ):
            with self.assertRaises(ValueError):
                synthesis_research.generate(
                    self.root / 'scratch',
                    run,
                    payload,
                    lambda engine, data, guidance, **kwargs: {
                        'content': '{"urls": []}',
                        'notes': '',
                    },
                    seconds=30,
                    stop=__import__('threading').Event(),
                )
        self.assertIs(tasks[0]['refresh'], True)
        found = runner.survey(self.root, found['id'])
        found = runner.decide(
            self.root,
            found['id'],
            found['expected'],
            'changes',
            'Shorter.',
            page=True,
            target='research',
        )
        self.assertIs(
            runner.job(self.root, found['id'])[1]['refresh'],
            False,
            'a later change asks for no refresh',
        )
        with self.assertRaisesRegex(ValueError, 'Only the research'):
            runner.decide(
                self.root,
                found['id'],
                found['expected'],
                'changes',
                'Shorter.',
                page=True,
                target='outline',
                refresh=True,
            )


class ResearchPlanningTests(RunnerCase):
    def test_the_research_plan_job_uses_its_own_module(self):
        found = self.create(research='web-allowed')
        _, payload, guidance = runner.job(self.root, found['id'])
        self.assertEqual(runner.GUIDES['research-plan'], 'modules/blog-research-plan.md')
        self.assertIn('You have no tools.', guidance)
        self.assertIn('at most 8 questions', guidance)

    def test_planning_questions_are_read_from_the_plan(self):
        self.assertEqual(
            runner.planning_questions(
                '- **why-now**: Why now?\n- **Bad id**: x\n- **cost**: What does it cost?\n- **cost**: Duplicate?'
            ),
            [
                {'id': 'why-now', 'question': 'Why now?'},
                {'id': 'cost', 'question': 'What does it cost?'},
            ],
        )
        self.assertEqual(
            len(runner.planning_questions('\n'.join(f'- **q-{i}**: Why?' for i in range(9)))), 8
        )

    def test_the_research_module_documents_the_synthesis_path_only(self):
        path = Path(runner.__file__).parents[1] / 'references/modules'
        main = (path / 'blog-deep-research.md').read_text()
        self.assertNotIn('deep_research.py research', main)
        self.assertIn('modules/blog-legacy-research.md', main)
        self.assertIn('research record', (path / 'blog-legacy-research.md').read_text())


class ClaimsMapTests(RunnerCase):
    PASSAGE = 'The gateway calls the service.'

    def role_source(self, role, status='ready'):
        source = self.source(self.PASSAGE + ' ' + role)
        folder, record = studio.item(self.root, 'sources', source['id'])
        record.update(purposes=[role], status=status)
        studio.write_json(folder / 'record.json', record)
        return source['id']

    def test_no_claims_map_runs_without_readable_factual_material(self):
        for role, status in [
            ('inspiration', 'ready'),
            ('voice-sample', 'ready'),
            ('reference', 'pending'),
        ]:
            with self.subTest(role=role, status=status):
                ident = self.role_source(role, status)
                found = self.create(title=role + status, research='supplied-only', sources=[ident])
                self.assertNotIn('claims-map', [row['stage'] for row in found['stages']])

    def test_only_factual_material_reaches_the_map_and_direct_validation(self):
        fact = self.role_source('reference')
        voice = self.role_source('voice-sample')
        example = self.role_source('inspiration')
        found = self.create(research='supplied-only', sources=[fact, voice, example])
        directory, record, run = runner.load(self.root, found['id'])
        all_sources = runner.inputs(self.root, record, run)['sources']
        sample = next(source for source in all_sources if source['purposes'] == ['voice-sample'])
        _, payload, _ = runner.job(self.root, found['id'])
        self.assertEqual([source['purposes'] for source in payload['sources']], [['reference']])
        options = {source['id']: source for source in runner.options(self.root)['sources']}
        self.assertEqual(options[voice]['purposes'], ['voice-sample'])
        with self.assertRaisesRegex(ValueError, 'not in your material'):
            self.submit(found, self.line(sample))
        self.submit(found, self.line(payload['sources'][0]))

    def test_a_worker_cannot_make_a_voice_sample_into_claims(self):
        fact, voice = self.role_source('reference'), self.role_source('voice-sample')
        found = self.create(page=True, research='supplied-only', sources=[fact, voice])
        directory, record, run = runner.load(self.root, found['id'])
        sample = next(
            source
            for source in runner.inputs(self.root, record, run)['sources']
            if source['purposes'] == ['voice-sample']
        )
        calls = []

        def worker(engine, payload, guidance, **options):
            calls.append(payload)
            return {'content': self.line(sample), 'notes': ''}

        engine = runner.Engine(self.root, worker=worker)
        self.addCleanup(engine.close)
        engine.keep_local(found['id'], {'enabled': True})
        engine.once(found['id'])
        self.assertEqual(len(calls), 2)
        self.assertEqual(engine.describe(found['id'])['status'], 'failed')
        self.assertTrue(
            all(
                [source['purposes'] for source in payload['sources']] == [['reference']]
                for payload in calls
            )
        )

    def mapped(self, page=False, **extra):
        source = self.source(self.PASSAGE)
        found = self.create(page=page, research='supplied-only', sources=[source['id']], **extra)
        directory, record, run = runner.load(self.root, found['id'])
        offered = runner.inputs(self.root, record, run)['sources'][0]
        return found, {**offered, 'selected_id': source['id']}

    def line(self, source, passage=None):
        return (
            '- **Gateway call** — Specification (`'
            + source['id']
            + '`): "'
            + (passage or self.PASSAGE)
            + '"'
        )

    def test_supplied_only_research_maps_claims_instead(self):
        found, source = self.mapped()
        self.assertEqual(
            [s['stage'] for s in found['stages']],
            ['claims-map', 'outline', 'draft', 'review', 'package'],
        )
        web = self.create(research='web-allowed', sources=[source['selected_id']])
        self.assertEqual([s['stage'] for s in web['stages']][:2], ['research-plan', 'research'])
        empty = self.create(research='supplied-only')
        self.assertNotIn('claims-map', [s['stage'] for s in empty['stages']])

    def test_a_claims_map_passage_must_be_in_its_source(self):
        import claims_map

        sources = [{'id': 's1', 'text': 'The gateway\n calls the service.'}]
        valid = '- **Gateway call** — Notes (`s1`): "The gateway calls the service."'
        self.assertEqual(claims_map.problems(valid, sources), [])
        self.assertEqual(
            claims_map.problems(valid.replace('calls', 'called'), sources),
            ['The passage for "Gateway call" is not in s1.'],
        )
        self.assertEqual(
            claims_map.problems(valid.replace('`s1`', '`s2`'), sources),
            ['"s2" is not one of the sources this blog reads.'],
        )
        self.assertEqual(
            claims_map.problems('No claims.', sources),
            ['List at least one claim, one a line, as the guidance shows.'],
        )
        self.assertEqual(
            claims_map.problems(valid.replace('gateway calls', 'gateway\n calls'), sources), []
        )
        self.assertTrue(
            claims_map.problems(valid + '\n- **An unchecked claim** — missing passage', sources)
        )

    def test_unquoted_prose_cannot_add_claims_to_a_valid_map(self):
        import claims_map

        valid = '- **Gateway call** — Notes (`s1`): "The gateway calls the service."'
        self.assertTrue(
            claims_map.problems(
                valid + '\nAn additional unsupported claim.', [{'id': 's1', 'text': self.PASSAGE}]
            )
        )

    def test_a_claims_map_gets_one_correction(self):
        for corrected in (True, False):
            found, source = self.mapped(page=True, title='Correction ' + str(corrected))
            calls = []

            def worker(
                engine,
                payload,
                guidance,
                source=source,
                corrected=corrected,
                calls=calls,
                **options,
            ):
                calls.append(payload)
                self.assertFalse(options['web'])
                return {
                    'content': self.line(source)
                    if corrected and len(calls) == 2
                    else self.line(source, 'The gateway invents a service.'),
                    'notes': '',
                }

            engine = runner.Engine(self.root, worker=worker)
            self.addCleanup(engine.close)
            engine.keep_local(found['id'], {'enabled': True})
            engine.once(found['id'])
            shown = engine.describe(found['id'])
            self.assertEqual(len(calls), 2)
            self.assertIn('validation_error', calls[1])
            if corrected:
                self.assertEqual(shown['status'], 'waiting-for-approval')
            else:
                self.assertEqual(shown['status'], 'failed')
                self.assertIn(
                    'The claims map quoted passages that are not in your material: ', shown['error']
                )

    def test_balanced_continues_past_the_claims_map(self):
        found, source = self.mapped(review_level='balanced')
        found = self.submit(found, self.line(source))
        self.assertEqual(found['next'], 'outline')
        self.assertEqual(found['stages'][0]['accepted_by'], 'review-policy')
        strict, source = self.mapped(review_level='step_by_step')
        self.assertEqual(self.submit(strict, self.line(source))['next'], 'claims-map')

    def test_later_stages_receive_the_claims_map(self):
        found, source = self.mapped()
        found = self.approve(self.submit(found, self.line(source)))
        _, payload, _ = runner.job(self.root, found['id'])
        self.assertEqual(payload['documents']['claims-map'], self.line(source))
        self.assertIn('claims-map', blog_worker.POLICY)

    def test_the_worker_is_told_what_the_research_bundle_is(self):
        from studio_core import research_contract

        self.assertIn('`research_bundle`', blog_worker.POLICY)
        self.assertIn(research_contract.HANDOFF, blog_worker.POLICY)

    def test_direct_submissions_also_validate_exact_sources(self):
        found, source = self.mapped()
        with self.assertRaisesRegex(ValueError, 'not in your material'):
            self.submit(found, self.line(source, 'A different claim.'))

    def test_continue_without_research_drops_the_claims_map(self):
        found, source = self.mapped(page=True)
        shown = runner.dispatch(
            self.root, 'skip-research', {'id': found['id'], 'expected': found['expected']}
        )
        self.assertNotIn('claims-map', [s['stage'] for s in shown['stages']])


class ApplyReviewTests(RunnerCase):
    def test_feedback_only_can_explicitly_apply_findings_and_finish_a_package(self):
        found = self.submit(
            self.create(page=True, mode='review', id=self.article(), stop='review'), page=True
        )
        with studio.locked(self.root), patch.object(runner.Engine, 'control', return_value={}):
            runner.dispatch(
                self.root, 'apply-review', {'id': found['id'], 'expected': found['expected']}
            )
        _, record, run = runner.load(self.root, found['id'])
        self.assertEqual(run['pipeline'], ['draft', 'review', 'package'])
        self.assertEqual(record['stop_point'], 'package')
        self.assertEqual(runner.survey(self.root, found['id'])['next'], 'draft')

    def at_package(self):
        found = self.create(page=True)
        for stage in ('outline', 'draft', 'review'):
            self.assertEqual(found['next'], stage)
            found = self.approve(self.submit(found, page=True), page=True)
        return self.submit(found, page=True)

    def test_apply_review_edits_only_for_the_findings_then_reviews_and_packages(self):
        found = self.at_package()
        directory, _, _ = runner.load(self.root, found['id'])
        review = (directory / 'derived/blog-review.md').read_text()
        before = (directory / 'DRAFT.md').read_text()
        with studio.locked(self.root), patch.object(runner.Engine, 'control', return_value={}):
            runner.dispatch(
                self.root, 'apply-review', {'id': found['id'], 'expected': found['expected']}
            )
        _, payload, guidance = runner.job(self.root, found['id'])
        self.assertTrue(
            payload['changes'].startswith('Apply only the findings in the review below.')
        )
        self.assertIn(review, payload['changes'])
        self.assertIn('change nothing else', payload['changes'])
        self.assertIn('minimal edit, not a rewrite', guidance)
        found = runner.survey(self.root, found['id'])
        self.assertEqual(found['next'], 'draft')
        found = self.approve(
            self.submit(found, before + '\nRequested correction.', page=True), page=True
        )
        for stage in ('review', 'package'):
            self.assertEqual(found['next'], stage)
            found = self.approve(self.submit(found, page=True), page=True)
        self.assertTrue(found['complete'])
        self.assertTrue(
            any(path.read_text() == before for path in (directory / 'history').glob('*.md'))
        )

    def test_apply_review_needs_a_review(self):
        found = self.create(page=True)
        with (
            studio.locked(self.root),
            self.assertRaisesRegex(ValueError, 'There is no review to apply yet'),
        ):
            runner.dispatch(
                self.root, 'apply-review', {'id': found['id'], 'expected': found['expected']}
            )

    def test_apply_review_is_revision_bound_and_survives_recovery(self):
        found = self.at_package()
        with studio.locked(self.root):
            with self.assertRaisesRegex(ValueError, 'changed'):
                runner.dispatch(self.root, 'apply-review', {'id': found['id'], 'expected': 'old'})
            with patch.object(runner.Engine, 'control', return_value={}):
                runner.dispatch(
                    self.root, 'apply-review', {'id': found['id'], 'expected': found['expected']}
                )
        _, _, run = runner.load(self.root, found['id'])
        self.assertTrue(run['stages']['draft']['apply_review'])
        self.assertIn('Keep the author', runner.job(self.root, found['id'])[1]['changes'])


class GateCheckTests(RunnerCase):
    def drafted(self, text='# Draft\n\nSynthetic writing.', **settings):
        found = self.approve(self.submit(self.create(page=True, **settings), page=True), page=True)
        return self.submit(found, text, page=True)

    def test_checks_show_what_lint_found(self):
        guide, rules = self.base / 'voice.md', self.base / 'rules.json'
        guide.write_text('Short direct sentences.')
        rules.write_text(json.dumps({'no_em_dashes': True}))
        voice = self.command(
            'profile',
            'create',
            '--name',
            'Avery',
            '--guide-file',
            str(guide),
            '--rules-file',
            str(rules),
            '--status',
            'confirmed',
        )
        found = self.drafted('# Draft\n\nTwo — pauses — here.', profile=voice['id'])
        shown = runner.document(self.root, found['id'], 'draft')
        row = next(row for row in shown['checks'] if row['label'] == '2 em dashes')
        self.assertFalse(row['passed'])
        self.assertIn('line 3: —', row['detail'])

    def test_old_preservation_notes_are_read_as_a_check(self):
        found = self.drafted()
        directory, record, run = runner.load(self.root, found['id'])
        run['stages']['draft']['notes'] = 'Useful note.\nPreservation check: ' + json.dumps(
            {'needs_review': True, 'changes': {'numbers': {'before': ['12'], 'after': ['13']}}}
        )
        runner.save(self.root, directory, record, run, 'Synthetic old note')
        shown = runner.document(self.root, found['id'], 'draft')
        self.assertEqual(shown['notes'], 'Useful note.')
        self.assertTrue(
            any(row['label'] == 'Numbers, links or quotations changed' for row in shown['checks'])
        )

    def test_preservation_is_data_and_survives_into_the_review(self):
        found = self.approve(self.drafted('# Draft\n\nKeep 12 units.'), page=True)
        found = runner.decide(
            self.root,
            found['id'],
            found['expected'],
            'changes',
            'Correct the number.',
            page=True,
            target='draft',
        )
        found = self.submit(found, '# Draft\n\nKeep 13 units.', page=True)
        _, _, run = runner.load(self.root, found['id'])
        self.assertTrue(run['stages']['draft']['preservation']['needs_review'])
        self.assertNotIn('Preservation check:', run['stages']['draft']['notes'])
        found = self.submit(self.approve(found, page=True), page=True)
        rows = runner.document(self.root, found['id'], 'review')['checks']
        self.assertTrue(any(row['label'] == 'Numbers, links or quotations changed' for row in rows))

    def test_no_always_true_rows(self):
        found = self.submit(self.create(page=True), page=True)
        labels = [
            row['label'] for row in runner.document(self.root, found['id'], 'outline')['checks']
        ]
        self.assertNotIn('Saved document contains readable text', labels)
        self.assertNotIn('Document matches its submitted version and selected inputs', labels)
        self.assertEqual(labels, ['No automatic checks apply to Outline.'])


class MessagingTests(FilesCase):
    """Approved messaging: the announcement's own claims, stated in the product's voice."""

    BRIEF = 'Gateway Prime retries a failed call twice. It is in preview, planned for March.'

    def messaging(self, *files):
        import base64
        import blog_library

        with patch.object(blog_library.shutil, 'which', return_value=None):
            result = management.dispatch(
                self.root,
                'upload',
                {
                    'operation': studio.digest(repr(('messaging', files)).encode())[:32],
                    'purpose': 'material',
                    'analyze': False,
                    'files': [
                        {
                            'filename': name,
                            'content': base64.b64encode(body.encode()).decode(),
                            'purpose': 'messaging',
                        }
                        for name, body in files
                    ],
                },
            )
        return [row['source']['id'] for row in result['files']]

    def test_the_stance_reaches_the_payload_only_with_messaging(self):
        facts = self.material(('notes.md', 'Retries cost money. ' * 40))
        brief = self.messaging(('launch-brief.md', self.BRIEF))
        found = self.create(sources=facts + brief, research='none')
        _, record, run = runner.load(self.root, found['id'])
        stances = {s['name']: s['stance'] for s in runner.inputs(self.root, record, run)['sources']}
        self.assertEqual(stances, {'notes': 'evidence', 'launch-brief': 'messaging'})
        # Without messaging, no source carries a stance, so saved pins hold byte for byte.
        plain = self.create(sources=facts, research='none', title='Plain')
        _, record, run = runner.load(self.root, plain['id'])
        self.assertTrue(
            all('stance' not in s for s in runner.inputs(self.root, record, run)['sources'])
        )

    def test_the_writer_is_told_what_messaging_means(self):
        self.assertIn("stance 'messaging'", blog_worker.POLICY)
        self.assertIn('without attribution hedges', blog_worker.POLICY)
        found = self.create(
            sources=self.messaging(('launch-brief.md', self.BRIEF)), research='none'
        )
        found = self.approve(self.submit(found))  # outline
        _, payload, guidance = runner.job(self.root, found['id'])
        self.assertEqual(payload['sources'][0]['stance'], 'messaging')
        self.assertIn('| Approved messaging |', guidance)
        self.assertIn('dates, versions and entitlements', guidance)
        self.assertIn('claim the messaging makes', guidance)

    def test_the_claims_map_reads_messaging_as_the_products_own_claims(self):
        found = self.create(
            sources=self.messaging(('launch-brief.md', self.BRIEF)), research='supplied-only'
        )
        self.assertEqual(found['next'], 'claims-map')
        _, payload, guidance = runner.job(self.root, found['id'])
        self.assertEqual([s['stance'] for s in payload['sources']], ['messaging'])
        self.assertIn('stance `messaging`', guidance)


class ReaderFacingNotesTests(RunnerCase):
    """Source IDs and editorial notes stay out of the reader's text."""

    EVIDENCE = [
        {'claim': 'Retries twice', 'source': 'source-abc', 'passage': 'retries a failed call twice'}
    ]
    GAPS = ['The confirmed release version and date.']

    def at_draft(self, page=False):
        found = self.approve(self.submit(self.create(page=page), page=page), page=page)
        self.assertEqual(found['next'], 'draft')
        return found

    def test_reader_facing_notes_finds_source_ids_and_placeholders(self):
        from text_checks import reader_facing_notes

        text = (
            'Gateway Prime retries twice [source-abc123].\n\n'
            '[Editorial placeholder: add the confirmed release version.]\n'
        )
        found = reader_facing_notes(text)
        self.assertEqual([f['rule'] for f in found], ['reader-facing-note'] * 2)
        self.assertEqual(
            [f['target'] for f in found],
            ['[source-abc123]', '[Editorial placeholder: add the confirmed release version.]'],
        )
        self.assertEqual(reader_facing_notes('A clean paragraph about sources.'), [])

    def test_the_gate_check_fails_on_a_note_in_the_draft(self):
        found = self.at_draft()
        found = self.submit(found, '# Draft\n\nIt retries twice [source-abc123].\n')
        row = next(
            c
            for c in runner.document(self.root, found['id'], 'draft')['checks']
            if 'editorial notes' in c['label']
        )
        self.assertEqual(
            (row['label'], row['passed']), ('Source IDs or editorial notes in the writing', False)
        )
        self.assertEqual(row['detail'], ['line 3: [source-abc123]'])
        # The review and the handoff check the draft too, and a clean draft passes.
        found = self.submit(
            runner.decide(
                self.root, found['id'], found['expected'], 'changes', 'Clean it.', target='draft'
            ),
            '# Draft\n\nIt retries twice.\n',
        )
        row = next(
            c
            for c in runner.document(self.root, found['id'], 'draft')['checks']
            if 'editorial notes' in c['label']
        )
        self.assertEqual(
            (row['label'], row['passed']),
            ('No source IDs or editorial notes in the writing', True),
        )

    def test_a_draft_job_asks_for_evidence_and_gaps_apart_from_the_writing(self):
        found = self.at_draft()
        _, payload, guidance = runner.job(self.root, found['id'])
        self.assertEqual(payload['response_kind'], 'writing-with-notes')
        self.assertIn('never in content', guidance)
        schema = blog_worker.schema_for(payload)
        self.assertEqual(schema['required'], ['content', 'notes', 'evidence', 'gaps'])
        self.assertIs(blog_worker.schema_for({}), blog_worker.SCHEMA)
        result = {'content': 'x', 'notes': '', 'evidence': self.EVIDENCE, 'gaps': self.GAPS}
        self.assertEqual(blog_worker.validate(result), result)
        for bad in ({'gaps': 'one'}, {'gaps': [3]}, {'evidence': [{'claim': 'x'}]}):
            with self.assertRaisesRegex(ValueError, 'notes'):
                blog_worker.validate({**result, **bad})
        self.assertIn('never in the words a reader reads', blog_worker.POLICY)

    def test_notes_are_saved_beside_the_stage_shown_and_handed_off(self):
        found = self.at_draft(page=True)
        calls = []

        def worker(engine, payload, guidance, **options):
            calls.append(payload)
            return {
                'content': '# Draft\n\nGateway Prime retries a failed call twice.\n',
                'notes': 'Judgment.',
                'evidence': self.EVIDENCE,
                'gaps': self.GAPS,
            }

        engine = runner.Engine(self.root, worker=worker)
        self.addCleanup(engine.close)
        engine.keep_local(found['id'], {'enabled': True})
        engine.once(found['id'])
        self.assertEqual(engine.describe(found['id'])['status'], 'waiting-for-approval')
        directory, _, _ = runner.load(self.root, found['id'])
        saved = json.loads((directory / 'derived/blog-draft-notes.json').read_text())
        self.assertEqual(saved, {'evidence': self.EVIDENCE, 'gaps': self.GAPS})
        self.assertNotIn('[source-', (directory / 'DRAFT.md').read_text())
        shown = runner.document(self.root, found['id'], 'draft')
        self.assertEqual(shown['gaps'], self.GAPS)
        found = runner.survey(self.root, found['id'])
        found = self.approve(found, page=True)  # draft
        found = self.approve(self.submit(found, page=True), page=True)  # review
        self.assertEqual(found['next'], 'package')
        _, payload, guidance = runner.job(self.root, found['id'])
        self.assertEqual(payload['gaps'], self.GAPS)
        self.assertIn('## Needs you before publishing', guidance)
        # The handoff shows the draft's gaps until it returns its own.
        found = self.submit(found, '# Handoff\n\nTitle.', page=True)
        self.assertEqual(runner.document(self.root, found['id'], 'package')['gaps'], self.GAPS)
        # A chat submission names its gaps with --gap; one without them keeps none.
        chat = self.at_draft()
        self.file.write_text('# Draft\n\nGateway Prime retries a failed call twice.\n')
        args = studio.parser().parse_args(
            ['--root', str(self.root), 'run', 'submit', '--id', chat['id']]
            + ['--expected', chat['expected'], '--stage', 'draft', '--file', str(self.file)]
            + ['--gap', 'A launch link.']
        )
        chat = runner.command(self.root, args)
        self.assertEqual(
            runner.document(self.root, chat['id'], 'draft')['gaps'], ['A launch link.']
        )
        self.submit(
            runner.decide(
                self.root, chat['id'], chat['expected'], 'changes', 'Again.', target='draft'
            )
        )
        self.assertEqual(runner.document(self.root, chat['id'], 'draft')['gaps'], [])
