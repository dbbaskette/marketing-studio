"""The same blog, gates and edits through chat commands and the authenticated page."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import json
import http.client
import os
from pathlib import Path
import shutil
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


def manuscript(root, text, title='Gateway guide'):
    """A saved manuscript with no run, registered as a draft brought in by chat is: what the
    manuscript editor's check works on."""
    args = studio.parser().parse_args(
        ['--root', str(root), 'article', 'create', '--title', title, '--mode', 'first-draft']
    )
    article = studio.article_command(root, args)
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'draft.md'
        path.write_text(text)
        args = studio.parser().parse_args(
            ['--root', str(root), 'article', 'save', '--id', article['id']]
            + ['--kind', 'draft', '--file', str(path)]
        )
        studio.article_command(root, args)
    return article['id']


def editor_check(root, ident, check='revise', **values):
    """The manuscript editor's check on a saved manuscript, as Edit manuscript starts it: the
    run it makes (or, on a blog with one, makes again), before its worker runs."""
    import manuscript_editor

    shown = manuscript_editor.read(root, ident)
    with patch.object(runner.Engine, 'control', return_value={}):
        manuscript_editor.dispatch(
            root, 'check', {'id': ident, 'expected': shown['expected'], 'check': check, **values}
        )
    return runner.survey(root, ident)


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

    # The earlier flow continues no saved run but the manuscript editor's own, so the runner
    # code those runs use (the worker, its stage jobs, failures, research) is tested on the
    # runs the editor's check really makes: Edit manuscript on a saved manuscript.
    MANUSCRIPT = 'Clients send requests to a gateway. The gateway calls the service.'

    def editor_check(self, ident, check='revise', **values):
        return editor_check(self.root, ident, check, **values)

    def editor_run(self, check='revise', text=None, **values):
        """A saved manuscript and the run the editor's `check` makes for it: revise has a
        draft and its review; any other check its review alone; research comes first."""
        return self.editor_check(self.article(text or self.MANUSCRIPT), check, **values)

    def review_of(self, ident):
        """A located editing review of the blog's saved manuscript, as the worker returns it."""
        directory, _ = studio.item(self.root, 'articles', ident)
        line = next(
            part.strip()
            for part in (directory / 'DRAFT.md').read_text().splitlines()
            if part.strip().strip('#').strip()
        )
        return json.dumps(
            {
                'summary': 'Synthetic review; editorial assessment only.',
                'findings': [
                    {
                        'id': 'first',
                        'kind': 'comment',
                        'before': line,
                        'reason': 'Synthetic note.',
                        'evidence': 'Editorial judgment',
                        'verdict': 'editorial',
                    }
                ],
            }
        )

    def submit(self, found, content=None, page=None):
        page = found.get('approval') == 'page' if page is None else page
        if content is None and found['next'] == 'review' and found.get('editor_check'):
            content = self.review_of(found['id'])
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

    def approve(self, found, page=None):
        page = found.get('approval') == 'page' if page is None else page
        return runner.decide(self.root, found['id'], found['expected'], 'approve', page=page)

    DESK_DRAFT = 'An opening paragraph.\n\n## First part\n\nFirst text.\n'

    def desk(self, manuscript=None, **extra):
        """A blog on the writing desk, started through the page route as a person starts
        one now. Returns its ID, title and the version its detail shows, which the delete,
        schedule and Google routes take."""
        import uuid

        made = management.dispatch(
            self.root,
            'desk-create',
            {
                'operation': uuid.uuid4().hex,
                'title': 'Synthetic gateway guide',
                'manuscript': manuscript or self.DESK_DRAFT,
                **extra,
            },
        )
        return self.shown(made['id'])

    def shown(self, ident):
        """A blog as its detail shows it now: ID, title and version."""
        found = management.detail(self.root, ident)
        return {'id': ident, 'title': found['title'], 'expected': found['expected']}

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
                            ('research', 'medium'),
                            ('combining', 'medium'),
                            ('checking', 'medium'),
                            ('writing', 'medium'),
                            ('fixing', 'high'),
                        ]
                    },
                },
            }
        )


class BlogRunnerTests(RunnerCase):
    def test_profiles_are_saved_and_background_worker_gets_the_saved_kind(self):
        from studio_core import studios_config

        self.profiles()
        found = self.editor_run('revise')
        studios_config.update(
            {'models': {'profiles': {kind: {'model': 'later'} for kind in ('research', 'writing')}}}
        )
        calls = []

        def worker(*args, **kwargs):
            calls.append(kwargs)
            return {'content': '# Synthetic draft', 'notes': 'Fake worker only.'}

        engine = runner.Engine(self.root, worker=worker)
        self.addCleanup(engine.close)
        engine.keep_local(found['id'], {'enabled': True})
        engine.once(found['id'])
        _, _, run = runner.load(self.root, found['id'])
        kind = run['model_jobs'][0]['profile']
        self.assertIn(kind, ('research', 'writing'))
        self.assertEqual(calls[0]['model_selection']['model'], kind + '-model')
        self.assertIsNone(run['model_jobs'][0]['actual_model'])
        # The revision's draft is saved and the check goes on to its review.
        self.assertEqual(engine.describe(found['id'])['status'], 'queued')

    def test_review_return_to_draft_uses_fixing_without_routing_from_request_text(self):
        self.profiles()
        found = self.submit(self.submit(self.editor_run('revise')))  # its draft, then its review
        self.assertEqual(found['next'], 'review')
        found = runner.decide(
            self.root,
            found['id'],
            found['expected'],
            'changes',
            'Synthetic review correction',
            page=True,
            target='draft',
        )
        choice = runner.job(self.root, found['id'])[0]['model_selection']
        self.assertEqual((choice['profile'], choice['model']), ('fixing', 'fixing-model'))
        self.profiles('claude')
        # The existing Codex run still owns its saved profiles.
        self.assertEqual(runner.job(self.root, found['id'])[0]['model_selection'], choice)

    def test_source_classification_uses_quick_for_both_assistants(self):
        import source_curator

        for agent in ('codex', 'claude'):
            self.profiles(agent)
            options = source_curator.shared_options(agent, task='source-classification')
            self.assertEqual(options[options.index('--model') + 1], 'quick-model')

    def test_the_pipeline_enforces_its_gates(self):
        found = self.editor_run('revise')
        with self.assertRaisesRegex(ValueError, 'current submitted'):
            self.approve(found)
        with self.assertRaisesRegex(ValueError, 'current stage'):
            runner.submit(
                self.root,
                found['id'],
                'review',
                {'content': self.review_of(found['id']), 'notes': ''},
                found['expected'],
                page=True,
            )
        for stage in ('draft', 'review'):
            self.assertEqual(found['next'], stage)
            found = self.submit(found)
        found = self.approve(found)
        self.assertTrue(found['complete'])
        self.assertEqual([row['stage'] for row in found['stages']], ['draft', 'review'])

    def test_page_approval_is_unavailable_from_cli_and_worker_schema(self):
        found = self.submit(self.editor_run('proofread'))
        with self.assertRaisesRegex(ValueError, 'decided on the page'):
            self.approve(found, page=False)
        with self.assertRaises(ValueError):
            blog_worker.validate({'content': 'A draft', 'notes': '', 'approve': True})
        self.assertTrue(self.approve(found, page=True)['complete'])

    def test_old_page_decision_and_manual_edit_do_not_renew_approval(self):
        found = self.submit(self.editor_run('proofread'))
        old = found['expected']
        directory, _, _ = runner.load(self.root, found['id'])
        (directory / 'DRAFT.md').write_text('My local edit')
        with self.assertRaisesRegex(ValueError, 'changed'):
            runner.decide(self.root, found['id'], old, 'approve', page=True)
        latest = runner.survey(self.root, found['id'])
        self.assertEqual(latest['stages'][0]['status'], 'stale')

    def test_downstream_stages_are_invalidated_after_the_draft_changes(self):
        found = self.approve(self.submit(self.submit(self.editor_run('revise'))))
        self.assertTrue(found['complete'])
        found = runner.decide(
            self.root,
            found['id'],
            found['expected'],
            'changes',
            'Change the thesis',
            page=True,
            target='draft',
        )
        self.assertEqual(found['next'], 'draft')
        self.assertEqual(found['stages'][1]['status'], 'pending')
        found = self.submit(found, 'New thesis')
        self.assertIn('Change the thesis', found['stages'][0]['request'])
        self.assertEqual(found['stages'][0]['status'], 'approved', 'the check goes on past it')

    def test_change_request_is_an_instruction_for_a_minimal_edit(self):
        draft = '# Draft\nThe first fictional paragraph.\n\nThe second fictional paragraph.'
        found = self.submit(self.editor_run('revise'), draft)
        found = runner.decide(
            self.root,
            found['id'],
            found['expected'],
            'changes',
            'Shorten the second paragraph.',
            page=True,
            target='draft',
        )
        _, payload, guidance = runner.job(self.root, found['id'])
        self.assertIn('Shorten the second paragraph.', guidance)
        self.assertIn('minimal edit, not a rewrite', guidance)
        self.assertIn('verbatim', guidance)
        self.assertNotIn('Revise the supplied manuscript', guidance)
        self.assertEqual(payload['documents']['draft'], draft)
        # A review that sends the draft back is an edit of that draft too.
        found = self.submit(self.submit(found, draft))
        found = runner.decide(
            self.root,
            found['id'],
            found['expected'],
            'changes',
            'Fix the review finding about the title.',
            page=True,
            target='draft',
        )
        guidance = runner.job(self.root, found['id'])[2]
        self.assertIn('Fix the review finding about the title.', guidance)
        self.assertIn('minimal edit, not a rewrite', guidance)

    def test_revising_a_manuscript_does_not_ask_for_an_outline_based_draft(self):
        found = self.editor_run('revise')
        _, payload, guidance = runner.job(self.root, found['id'])
        self.assertNotIn('approved outline', guidance)
        # The editor's revision is the author's request applied to their own manuscript.
        self.assertIn('Edit the saved draft in documents.draft', guidance)
        self.assertIn('minimal edit, not a rewrite', guidance)
        self.assertEqual(payload['documents']['draft'], self.MANUSCRIPT)

    def test_imported_draft_starts_at_review_and_is_not_rewritten(self):
        ident = self.article('A fictional manuscript written by Avery.')
        directory, _ = studio.item(self.root, 'articles', ident)
        original = (directory / 'DRAFT.md').read_bytes()
        found = self.editor_check(ident, 'shape')
        self.assertEqual(found['next'], 'review')
        found = self.submit(found)
        self.assertEqual((directory / 'DRAFT.md').read_bytes(), original)
        self.assertIn(
            'A fictional manuscript', runner.job(self.root, ident)[1]['documents']['manuscript']
        )

    def test_polling_reads_selected_context_once_per_run(self):
        source = self.source('A fictional gateway routes synthetic requests.')
        ids = []
        # A list describes runs that still go on, the manuscript editor's (a saved run of the
        # earlier flow lists from its small records).
        for _ in range(3):
            found = self.editor_run('revise', sources=[source['id']])
            ids.append(self.submit(self.submit(found))['id'])
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
        found = self.submit(self.editor_run('revise'))  # its draft, continued to the review
        self.assertEqual(found['stages'][0]['status'], 'approved')
        directory, record = studio.item(self.root, 'articles', found['id'])
        record['title'] = 'A changed synthetic title'
        studio.persist(directory, 'articles', record)
        detail = runner.survey(self.root, found['id'])
        self.assertEqual(detail['stages'][0]['status'], 'stale')
        self.assertNotEqual(detail['expected'], found['expected'])
        listed = next(row for row in runner.catalog(self.root)['items'] if row['id'] == found['id'])
        self.assertEqual(listed['stages'], detail['stages'])

    def test_input_pins_keep_their_saved_format(self):
        found = self.submit(self.editor_run('revise'))
        directory, record, run = runner.load(self.root, found['id'])
        context = runner.inputs(self.root, record, run)
        original = studio.artifact_fingerprint(directory, 'ORIGINAL.md')

        def pin(previous):
            return studio.digest(json.dumps([context, previous, original], sort_keys=True).encode())

        self.assertEqual(run['stages']['draft']['basis'], pin({}))
        draft = studio.artifact_fingerprint(directory, 'DRAFT.md')
        self.assertEqual(
            runner.basis(self.root, directory, record, run, 'review'),
            pin({'draft': draft, 'manuscript': draft}),
        )

    def test_marking_a_pinned_source_as_a_sample_keeps_its_runs_open(self):
        isolation.voices_on(self.root)  # These exercise the older voice tools.
        import management

        source = self.source('A fictional gateway routes synthetic requests.')
        found = self.submit(self.editor_run('factual-support', sources=[source['id']]))
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
        found = self.submit(self.editor_run('factual-support', sources=[source['id']]))
        management.dispatch(
            self.root,
            'tool-action',
            {'action': 'source-purpose', 'source': source['id'], 'purpose': 'style-sample'},
        )
        directory, _ = studio.item(self.root, 'sources', source['id'])
        shutil.rmtree(directory / 'revisions' / '1')
        with self.assertRaisesRegex(ValueError, 'selected source changed'):
            runner.survey(self.root, found['id'])

    def test_status_says_whether_a_step_was_accepted_or_awaits_a_decision(self):
        found = self.editor_run('factual-support', research='web-allowed')
        self.assertEqual((found['next'], found['awaits']), ('research-plan', 'submission'))
        found = self.submit(found)
        # The check goes on past its research plan: nothing waits for the person, so approve
        # is refused.
        self.assertEqual((found['next'], found['awaits']), ('research', 'submission'))
        self.assertTrue(found['stages'][0]['auto_accepted'])
        with self.assertRaisesRegex(ValueError, 'need no approval'):
            self.approve(found)
        status = runner.engine(self.root).describe(found['id'])
        self.assertEqual(status['awaits'], 'submission')
        self.assertTrue(status['stages'][0]['auto_accepted'])
        found = self.submit(self.submit(found, '# Research\nSynthetic findings.'))
        self.assertEqual((found['next'], found['awaits']), ('review', 'decision'))
        self.assertFalse(found['stages'][2]['auto_accepted'])
        found = self.approve(found)
        self.assertIsNone(found['awaits'])

    def test_late_worker_result_cannot_overwrite_local_edit(self):
        found = self.editor_run('revise')
        directory, _ = studio.item(self.root, 'articles', found['id'])

        def worker(*args, **kwargs):
            (directory / 'DRAFT.md').write_text('My newer draft')
            return {'content': 'Late model draft', 'notes': ''}

        engine = runner.Engine(self.root, worker)
        engine.control(found['id'], 'resume')
        engine.once(found['id'])
        self.assertEqual((directory / 'DRAFT.md').read_text(), 'My newer draft')
        self.assertEqual(engine.describe(found['id'])['status'], 'failed')

    def test_worker_saves_each_step_and_stops_at_the_review(self):
        calls = []
        found = self.editor_run('revise')

        def worker(engine_name, payload, guidance, **kwargs):
            calls.append(kwargs)
            if payload.get('response_kind') == 'editing-review':
                return {'content': self.review_of(found['id']), 'notes': 'Synthetic.'}
            return {'content': '# Draft\nA fictional draft.', 'notes': 'Synthetic.'}

        engine = runner.Engine(self.root, worker)
        engine.control(found['id'], 'resume')
        engine.once(found['id'])
        self.assertEqual(len(calls), 1)
        self.assertFalse(calls[0]['web'])
        # The draft is saved and the check goes on by itself to its review.
        self.assertEqual(engine.describe(found['id'])['status'], 'queued')
        engine.once(found['id'])
        engine.once(found['id'])
        self.assertEqual(len(calls), 2)
        found = engine.describe(found['id'])
        self.assertEqual((found['status'], found['next']), ('waiting-for-approval', 'review'))
        self.assertFalse(found['enabled'])

    def test_background_runner_does_not_regenerate_a_manual_edit(self):
        calls = []

        def worker(*args, **kwargs):
            calls.append(True)
            return {'content': 'Generated draft', 'notes': ''}

        found = self.editor_run('revise')
        engine = runner.Engine(self.root, worker)
        engine.control(found['id'], 'resume')
        engine.once(found['id'])
        directory, _ = studio.item(self.root, 'articles', found['id'])
        # Edited outside the runner between the check's steps: it meets the edit and stops.
        (directory / 'DRAFT.md').write_text('My edited draft')
        engine.once(found['id'])
        self.assertEqual(len(calls), 1)
        self.assertEqual((directory / 'DRAFT.md').read_text(), 'My edited draft')
        shown = engine.describe(found['id'])
        self.assertEqual((shown['status'], shown['error']), ('failed', runner.STALE_CHECK))

    def test_restart_only_resumes_explicitly_started_local_runs(self):
        found = self.editor_run('proofread')
        one = runner.Engine(self.root)
        self.assertFalse(one.local(found['id'])['enabled'])
        one.control(found['id'], 'resume')
        two = runner.Engine(
            self.root,
            lambda *a, **kw: {'content': self.review_of(found['id']), 'notes': ''},
        )
        two.once(found['id'])
        self.assertEqual(two.describe(found['id'])['status'], 'waiting-for-approval')
        self.assertEqual(one.local(found['id'])['status'], 'waiting-for-approval')

    def test_stop_cancels_worker_without_a_late_save(self):
        entered, release = threading.Event(), threading.Event()

        def worker(*args, **kwargs):
            entered.set()
            release.wait(3)
            return {'content': 'A late draft', 'notes': ''}

        found = self.editor_run('revise')
        directory, _ = studio.item(self.root, 'articles', found['id'])
        before = (directory / 'DRAFT.md').read_text()
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
            self.assertEqual((directory / 'DRAFT.md').read_text(), before)
        finally:
            release.set()
            thread.join(3)

    def test_read_only_hub_cannot_start_page_work(self):
        with patch.object(management, 'authorize_write', side_effect=ValueError('Read-only')):
            with self.assertRaisesRegex(ValueError, 'Read-only'):
                management.dispatch(self.root, 'desk-create', {})

    def test_context_does_not_silently_truncate_sources(self):
        # An oversized source is excerpted to the budget, and the run says so by name.
        source = self.source('Synthetic evidence ' * 20_000)
        found = self.editor_run('factual-support', sources=[source['id']])
        self.assertEqual(
            runner.engine(self.root).describe(found['id'])['excerpted'], ['Specification']
        )
        _, record, run = runner.load(self.root, found['id'])
        kept = runner.inputs(self.root, record, run)['sources'][0]
        self.assertTrue(kept['excerpted'])
        self.assertEqual(kept['total_chars'], 19 * 20_000)
        self.assertLess(kept['kept_chars'], kept['total_chars'])

    def post_to_the_page(self, route, data):
        """POST one authenticated request to a disposable page server: (status, reply)."""
        from urllib.parse import urlsplit

        server, url = management.server(self.root)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
            connection.request(
                'POST',
                '/api/' + route,
                json.dumps(data),
                {'X-Blog-Studio-Token': urlsplit(url).fragment, 'Content-Type': 'application/json'},
            )
            response = connection.getresponse()
            reply = response.status, json.loads(response.read())
            connection.close()
            return reply
        finally:
            server.shutdown()
            server.server_close()

    def test_the_page_has_no_run_create_route(self):
        unknown = self.post_to_the_page('no-such-route', {'operation': 'c' * 32})
        self.assertEqual(unknown, (400, {'error': 'Unknown management action.'}))
        data = {
            'operation': 'c' * 32,
            'title': 'HTTP fixture',
            'audience': 'Authors',
            'goal': 'Explain synthetic writing',
            'research': 'none',
        }
        self.assertEqual(self.post_to_the_page('run-create', data), unknown)
        self.assertFalse(
            (self.root / 'articles').exists() and any((self.root / 'articles').iterdir())
        )
        self.assertFalse((self.root / '.blog-runs' / 'creations').exists())

    def test_the_page_has_no_source_keep_route(self):
        unknown = self.post_to_the_page('no-such-route', {'id': 'x'})
        self.assertEqual(self.post_to_the_page('source-keep', {'id': 'x', 'keep': True}), unknown)

    def test_writing_defaults_have_no_stop(self):
        self.assertNotIn('stop', runner.DEFAULTS)
        # A stop saved by an older version is read past, and dropped at the next save.
        saved = dict(runner.DEFAULTS, stop='draft')
        (self.root / '.blog-run-settings.json').write_text(json.dumps({'defaults': saved}))
        self.assertNotIn('stop', runner.settings(self.root)['defaults'])

    def test_create_makes_only_the_editors_review(self):
        ident = self.article()
        directory, _ = studio.item(self.root, 'articles', ident)
        before = sorted(path.relative_to(self.root) for path in self.root.rglob('*'))
        asked = {
            'id': ident,
            'goal': 'Edit the saved manuscript',
            'audience': 'Readers',
            'research': 'none',
            'stop': 'review',
        }
        for mode in ('write', 'outline', 'from-outline', 'ideas', 'revise', 'from-files', None):
            with self.subTest(mode=mode):
                data = {**asked, 'mode': mode} if mode else asked
                with self.assertRaises(ValueError) as refused:
                    runner.create(self.root, data, 'page')
                self.assertEqual(str(refused.exception), runner.EDITOR_ONLY)
        # A new blog (no saved manuscript named) and a stop other than the review are refused.
        for data in (
            {key: value for key, value in asked.items() if key != 'id'},
            {**asked, 'stop': 'draft'},
        ):
            with self.subTest(data=data), self.assertRaises(ValueError) as refused:
                runner.create(self.root, {**data, 'mode': 'review'}, 'page')
            self.assertEqual(str(refused.exception), runner.EDITOR_ONLY)
        for field, value in (('title', 'A new blog'), ('outline_text', '# An outline')):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'Unknown'):
                runner.create(self.root, {**asked, 'mode': 'review', field: value}, 'page')
        self.assertEqual(
            sorted(path.relative_to(self.root) for path in self.root.rglob('*')), before
        )
        self.assertEqual(runner.MODES, ('review',))
        # The editor's own: its review of the saved manuscript.
        found = runner.create(self.root, {**asked, 'mode': 'review'}, 'page')
        self.assertEqual(
            (found['mode'], [row['stage'] for row in found['stages']]), ('review', ['review'])
        )

    def test_completed_page_revision_returns_to_a_resumable_stage(self):
        found = self.editor_run('proofread')
        found = self.approve(self.submit(found))
        self.assertTrue(found['complete'])
        found = runner.dispatch(
            self.root,
            'changes',
            {
                'id': found['id'],
                'expected': found['expected'],
                'stage': 'review',
                'request': 'Clarify the fictional argument',
            },
        )
        self.assertFalse(found['complete'])
        self.assertEqual(found['next'], 'review')
        self.assertEqual(found['status'], 'paused')
        self.assertFalse(found['enabled'])

    def test_the_editors_run_needs_a_saved_manuscript_and_no_run(self):
        ident = self.article()
        directory, _ = studio.item(self.root, 'articles', ident)
        asked = {
            'id': ident,
            'mode': 'review',
            'goal': 'Edit the saved manuscript',
            'audience': 'Readers',
            'research': 'none',
        }
        draft = (directory / 'DRAFT.md').read_bytes()
        (directory / 'DRAFT.md').unlink()
        with self.assertRaisesRegex(ValueError, 'no saved manuscript'):
            runner.create(self.root, asked, 'page')
        self.assertFalse((directory / runner.STATE).exists())
        (directory / 'DRAFT.md').write_bytes(draft)
        runner.create(self.root, asked, 'page')
        with self.assertRaisesRegex(ValueError, 'already has a guided run'):
            runner.create(self.root, asked, 'page')

    def test_settings_are_local_defaults_and_do_not_change_existing_runs(self):
        found = self.editor_run('proofread')
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
        found = self.editor_run('shape')
        first = self.review_of(found['id'])
        found = self.approve(self.submit(found, first))
        directory, _ = studio.item(self.root, 'articles', found['id'])
        before = (directory / 'derived/blog-review.md').read_text()
        found = runner.decide(
            self.root,
            found['id'],
            found['expected'],
            'changes',
            'Clarify the argument',
            page=True,
            target='review',
        )
        found = self.submit(found, first.replace('Synthetic note.', 'A clearer note.'))
        shown = runner.document(self.root, found['id'], 'review')
        self.assertEqual(shown['previous'], before)
        self.assertIn('-Synthetic note.', shown['diff'])
        self.assertIn('+A clearer note.', shown['diff'])
        self.assertEqual(shown['expected'], found['expected'])
        (directory / 'derived/blog-review.md').write_text('A local change outside the runner')
        shown = runner.document(self.root, found['id'], 'review')
        self.assertEqual(shown['status'], 'stale')
        history = next((directory / 'history').glob('derived-blog-approved-review-*.md'))
        history.write_text('Changed outside the runner')
        self.assertIsNone(runner.document(self.root, found['id'], 'review')['previous'])

    def test_pause_keeps_current_stage_but_prevents_next_job(self):
        found = self.editor_run('revise')
        engine = runner.Engine(self.root)
        engine.control(found['id'], 'resume')
        calls = []

        def worker(*args, **kwargs):
            calls.append(True)
            engine.control(found['id'], 'pause')
            return {'content': 'Finished current job', 'notes': ''}

        engine.worker = worker
        engine.once(found['id'])
        engine.once(found['id'])
        found = engine.describe(found['id'])
        # The draft the step was making is kept; the review never starts.
        self.assertEqual((found['status'], found['next']), ('paused', 'review'))
        self.assertFalse(found['enabled'])
        self.assertEqual(found['stages'][0]['status'], 'approved')
        self.assertEqual(len(calls), 1)

    def test_imported_draft_can_be_revised_after_review(self):
        ident = self.article('My original synthetic draft')
        found = self.submit(self.editor_check(ident, 'proofread'))
        found = runner.decide(
            self.root,
            ident,
            found['expected'],
            'changes',
            'Clarify the introduction',
            page=True,
            target='draft',
        )
        self.assertEqual(found['next'], 'draft')
        # The author's own manuscript is edited, not rewritten from the brief.
        guidance = runner.job(self.root, ident)[2]
        self.assertIn('minimal edit, not a rewrite', guidance)
        self.assertIn('Clarify the introduction', guidance)
        found = self.submit(found, 'My revised synthetic draft')
        # The check goes on past the revised draft to its review.
        self.assertEqual(found['stages'][0]['status'], 'approved')
        self.assertEqual(found['next'], 'review')


class DeskRunViewTests(RunnerCase):
    def test_the_run_view_of_a_desk_blog_says_it_is_on_the_desk(self):
        made = management.dispatch(
            self.root,
            'desk-create',
            {'operation': 'f' * 32, 'title': 'Desk', 'manuscript': '# Desk\n\n## One\n\nText.\n'},
        )
        shown = management.view(self.root, 'run', {'id': [made['id']]})
        self.assertEqual(shown, {'id': made['id'], 'on_desk': True})
        with self.assertRaisesRegex(
            ValueError, '^This blog has no step-by-step run. Open it from Blogs.$'
        ):
            runner.load(self.root, made['id'])


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
            # A saved manuscript written as Avery, and the run the editor's revision makes.
            ident = self.article()
            self.command('article', 'voice', '--id', ident, '--profile', profile['id'])
            found = editor_check(self.root, ident, 'revise', sources=[source['id']])
            found = runner.submit(
                self.root,
                found['id'],
                'draft',
                {'content': '# Draft\nSynthetic argument.', 'notes': ''},
                found['expected'],
                page=True,
            )
            shared = wa.publish_selected({'articles': [found['id']]})['items'][0]
            wb.hub.refresh()
            local_id = wb.checkout_selected({'articles': [shared['item']]})['items'][0]['local_id']
            resumed = runner.engine(other).describe(local_id)
            self.assertEqual(resumed['stages'][0]['status'], 'approved')
            self.assertEqual(resumed['stages'][0]['accepted_by'], runner.EDITOR_CHECK)
            self.assertEqual(resumed['next'], 'review')
            self.assertFalse(resumed['enabled'])
            self.assertEqual(resumed['approval'], 'page')
            previous = runner.document(other, local_id, 'draft')['previous']
            self.assertEqual(previous, '# Draft\nSynthetic argument.')
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
                # A blog registered in chat with the voice, and a tone nudge or none.
                found = self.command(
                    'article',
                    'create',
                    '--title',
                    'Tone ' + (tone or 'none'),
                    '--mode',
                    'first-draft',
                    '--profile',
                    profile['id'],
                    *(['--tone', tone] if tone else []),
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
        found = self.editor_run('factual-support', research='web-allowed')
        self.assertEqual(found['ahead']['steps_left'], 3)
        # The check stops only at its review, which the view names as its next stop.
        self.assertEqual(found['ahead']['next_gate'], 'review')
        self.assertEqual(found['ahead']['next_stop'], runner.STAGES['review'][0])
        found = self.submit(found)
        self.assertEqual(found['ahead']['steps_left'], 2)
        self.assertEqual(found['ahead']['next_gate'], 'review')
        # A saved run with no jobs recorded says nothing of what it spent.
        engine = runner.Engine(self.root, worker=self.worker())
        self.addCleanup(engine.close)
        shown = engine.describe(found['id'])['ahead']
        self.assertEqual((shown['jobs'], shown['spent']), (0, None))

    def test_redo_says_what_a_change_draws_again(self):
        found = self.editor_run('revise')
        engine = runner.Engine(self.root, worker=self.worker())
        self.addCleanup(engine.close)
        redo = engine.describe(found['id'])['redo']
        self.assertEqual(redo['draft']['stages'], ['draft', 'review'])
        self.assertEqual(
            redo['draft']['says'],
            (
                'Drawn again: the draft and every step after it, 2 steps; this computer has no '
                'record of what they cost.'
            ),
        )
        state = engine.local(found['id'])
        state['jobs'] = [
            {'stage': stage, 'seconds': 300, 'tokens': None, 'dollars': 0.5}
            for stage in ('draft', 'review')
        ]
        engine.keep_local(found['id'], state)
        redo = engine.describe(found['id'])['redo']
        self.assertEqual(
            redo['draft']['says'],
            (
                'Drawn again: the draft and every step after it, 2 steps. Last time they took '
                '10 minutes and about $1.00.'
            ),
        )
        self.assertEqual(
            redo['review']['says'],
            'Drawn again: the review. Last time it took 5 minutes and about $0.50.',
        )

    def test_stage_labels(self):
        self.assertEqual(runner.STAGES['package'][0], 'Handoff')  # Read in saved runs.
        found = self.editor_run('revise')
        self.assertEqual([row['label'] for row in found['stages']], ['Draft', 'Review'])

    def test_an_unreadable_shared_file_still_starts_a_check_step_by_step(self):
        import studios_config
        from studio_core import review_policy

        studios_config.path().write_text('{', encoding='utf-8')
        found = self.editor_run('proofread')
        _, _, run = runner.load(self.root, found['id'])
        self.assertEqual(review_policy.level(run), 'step_by_step', 'never more autonomy')
        self.assertEqual(studios_config.path().read_text(), '{')

    def test_review_level_route_is_removed_without_writing(self):
        import studios_config

        studios_config.update({'review': {'level': 'balanced'}})
        before = studios_config.read()[0]
        with self.assertRaises(ValueError):
            management.dispatch(
                self.root, 'review-level', {'level': 'automatic', 'seen': 'balanced'}
            )
        self.assertEqual(studios_config.read()[0], before)

    def test_the_worker_records_when_it_started_and_the_page_reads_it(self):
        found = self.editor_run('revise')
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
        import desk

        first = self.desk()
        second = self.desk(title='A later synthetic blog')
        listed = [row['id'] for row in runner.catalog(self.root)['items']]
        self.assertEqual(listed, [second['id'], first['id']])
        part = desk.read(self.root, first['id'])['sections'][0]['id']
        management.dispatch(
            self.root,
            'desk-save',
            {'id': first['id'], 'seen': 1, 'part': part, 'text': 'Typed.', 'session': 'b' * 16},
        )
        listed = [row['id'] for row in runner.catalog(self.root)['items']]
        self.assertEqual(listed, [first['id'], second['id']])
        self.assertTrue(all(row['touched'] for row in runner.catalog(self.root)['items']))


class FinishTests(RunnerCase):
    def test_the_final_stop_carries_the_approved_draft_beside_the_review(self):
        found = self.submit(self.editor_run('revise'), '# Draft\nSynthetic writing.')
        self.assertEqual(found['next'], 'review')
        found = self.submit(found)
        shown = runner.document(self.root, found['id'], 'review')
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

    def job_for(self, ident, job, created_at=None):
        """A queued desk tool job of the blog, with what a worker needs to run it."""
        import tool_jobs

        tool_jobs.write(
            self.root,
            {
                'id': job,
                'kind': 'repurpose',
                'status': 'queued',
                'attempts': 0,
                'created_at': created_at or studio.now(),
                'metadata': {'article': ident},
                'result': None,
                'error': '',
                'engine': 'codex',
                'payload': {},
                'guidance': '',
                'seconds': 5,
            },
        )

    def delete(self, found, **changes):
        return management.dispatch(
            self.root,
            'blog-delete',
            {'id': found['id'], 'expected': found['expected'], 'title': found['title'], **changes},
        )

    def test_delete_needs_the_shown_version_and_the_typed_title(self):
        found = self.desk()
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
        found = self.desk(title='From agent “pilots” to governed  production – 2026')
        self.assertEqual(found['title'], 'From agent “pilots” to governed  production – 2026')
        with self.assertRaisesRegex(ValueError, 'title'):
            self.delete(found, title='From agent pilots to production')
        result = self.delete(found, title='  from agent "pilots" to governed production - 2026 ')
        self.assertTrue(result['deleted'])
        self.assertEqual([row['id'] for row in runner.catalog(self.root)['deleted']], [found['id']])

    def test_delete_ignores_a_byte_order_mark_at_the_start_of_the_stored_title(self):
        # The page's \s counts U+FEFF as a space, so the server must agree.
        found = self.desk(title='\ufeffMarked gateway guide')
        self.assertEqual(found['title'], '\ufeffMarked gateway guide')
        result = self.delete(found, title='Marked gateway guide')
        self.assertTrue(result['deleted'])

    def test_delete_stops_the_worker_and_removes_what_this_computer_kept(self):
        import tool_jobs

        entered = threading.Event()

        def worker(*args, **kwargs):
            entered.set()
            kwargs['stop'].wait(5)  # the worker ends once the delete asks it to stop
            return {'content': 'A late section', 'notes': ''}

        found = self.desk()
        ident = found['id']
        self.job_for(ident, 'f' * 32, created_at='2001-01-01T00:00:00+00:00')  # runs first
        self.plant(ident)
        engine = runner.Engine(self.root, worker)
        runner.ENGINES[str(self.root)] = engine
        thread = threading.Thread(target=tool_jobs.once, args=(engine,))
        thread.start()
        try:
            self.assertTrue(entered.wait(2))
            self.assertEqual(engine.current, 'tool:' + 'f' * 32)
            result = self.delete(self.shown(ident))
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
        self.assertEqual(tool_jobs.read(self.root, 'd' * 32)['status'], 'queued')
        self.assertFalse(
            studio.inside(self.root, '.blog-runs', 'tools', 'c' * 32 + '.json').exists()
        )
        self.assertFalse(tool_jobs.path(self.root, 'f' * 32).exists(), 'its working job too')
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
        import blog_delete
        import desk

        found = self.desk()
        ident = found['id']
        part = desk.read(self.root, ident)['sections'][0]['id']
        management.dispatch(
            self.root,
            'desk-save',
            {'id': ident, 'seen': 1, 'part': part, 'text': 'Kept text.', 'session': 'b' * 16},
        )
        self.delete(self.shown(ident))
        restored = management.dispatch(self.root, 'blog-restore', {'id': ident})
        self.assertEqual(restored['id'], ident)
        self.assertTrue(restored['restored'])
        self.assertTrue(restored['on_desk'])
        directory, record = studio.item(self.root, 'articles', ident)
        self.assertEqual(record['title'], 'Synthetic gateway guide')
        self.assertIn('Kept text.', (directory / 'DRAFT.md').read_text())
        self.assertEqual(desk.read(self.root, ident)['sections'][0]['text'], 'Kept text.')
        self.assertEqual(blog_delete._jobs(self.root, ident), [], 'nothing starts by itself')
        self.assertEqual(runner.catalog(self.root)['deleted'], [])
        with self.assertRaisesRegex(ValueError, 'recently deleted'):
            management.dispatch(self.root, 'blog-restore', {'id': ident})
        # An old record and whatever it kept are let go of when the list is read.
        self.delete(self.shown(ident))
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

        found = self.desk()
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
            result = self.delete(self.shown(ident))
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
        import tool_jobs

        entered, release = threading.Event(), threading.Event()

        def worker(*args, **kwargs):
            entered.set()
            release.wait(5)  # ignores the stop
            return {'content': 'late', 'notes': ''}

        found = self.desk()
        ident = found['id']
        engine = runner.Engine(self.root, worker)
        runner.ENGINES[str(self.root)] = engine
        self.job_for(ident, 'c' * 32)
        thread = threading.Thread(target=tool_jobs.once, args=(engine,))
        thread.start()
        try:
            self.assertTrue(entered.wait(2))
            self.assertEqual(engine.current, 'tool:' + 'c' * 32)
            with patch.object(blog_delete, 'STOP_WAIT', 0.2):
                with self.assertRaisesRegex(ValueError, 'not ended yet'):
                    self.delete(self.shown(ident))
        finally:
            release.set()
            thread.join(5)
        self.assertTrue(studio.inside(self.root, 'articles', ident, 'session.json').is_file())
        self.assertFalse(engine.local(ident)['enabled'], 'it was stopped all the same')
        self.assertEqual(runner.catalog(self.root)['deleted'], [])

    def test_restore_finds_the_blog_already_back_and_drops_the_record(self):
        import blog_delete

        found = self.desk()
        ident = found['id']
        self.delete(found)
        kept = studio.inside(self.root, '.blog-runs', 'deleted', ident)
        shutil.copytree(kept / 'blog', studio.inside(self.root, 'articles', ident))
        restored = management.dispatch(self.root, 'blog-restore', {'id': ident})
        self.assertEqual((restored['id'], restored['notice']), (ident, blog_delete.ALREADY_BACK))
        self.assertFalse(kept.exists())
        self.assertEqual(runner.catalog(self.root)['deleted'], [])
        # A different blog under the same ID is never overwritten.
        other = self.desk()
        self.delete(other)
        session = studio.inside(self.root, 'articles', other['id'], 'session.json')
        studio.write_json(session, {'id': other['id'], 'title': 'Another blog'})
        with self.assertRaisesRegex(ValueError, 'different blog'):
            management.dispatch(self.root, 'blog-restore', {'id': other['id']})

    def test_a_kept_copy_refuses_a_second_delete_and_a_bad_record_is_left_out(self):
        found = self.desk()
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
        found = self.desk()
        shown = management.view(self.root, 'desk', {'id': [found['id']]})
        self.assertIsNone(shown['publication'])
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
            management.view(self.root, 'desk', {'id': [found['id']]})['publication'],
            'https://example.com/post',
        )


class StyleTests(RunnerCase):
    """A run pins a style beside its voice, and the writing job reads that revision."""

    def styled(self, style):
        """A saved manuscript pinned to a kind of post, as one written with it was."""
        ident = self.article()
        directory, record = studio.item(self.root, 'articles', ident)
        record['style'] = studio.style_pin(self.root, style)
        studio.persist(directory, 'articles', record)
        return ident

    def test_a_run_pins_its_style_and_the_job_carries_it(self):
        self.assertIn(
            'product-announcement', [row['id'] for row in runner.options(self.root)['styles']]
        )
        ident = self.styled('product-announcement')
        found = self.editor_check(ident, 'shape')
        _, record = studio.item(self.root, 'articles', ident)
        self.assertEqual(record['style'], {'style_id': 'product-announcement', 'revision': 1})
        self.assertEqual((found['style_name'], found['voice_name']), ('Product announcement', None))
        _, payload, guidance = runner.job(self.root, ident)
        self.assertEqual(payload['style']['name'], 'Product announcement')
        self.assertIn('The news is in the first sentence.', payload['style']['guide'])
        self.assertIn('the style wins', guidance)
        self.assertIn('the style wins', blog_worker.POLICY)
        # Only feedback on the shape reads the kind of post; a polish keeps to its own scope.
        for check, carried in (('polish', False), ('shape', True)):
            self.editor_check(ident, check)
            _, checked, guidance = runner.job(self.root, ident)
            self.assertEqual('SELECTED STYLE' in guidance, carried)
            self.assertEqual(checked['style'] is not None, carried, check)
            self.assertEqual('Product announcement' in guidance.split('\n', 1)[0], carried)
        guide = self.base / 'style.md'
        guide.write_text('Changed later.')
        self.command('style', 'save', '--id', 'product-announcement', '--guide-file', str(guide))
        _, payload, _ = runner.job(self.root, ident)
        self.assertNotIn(
            'Changed later.', payload['style']['guide'], 'a later save does not move the pin'
        )
        plain = self.editor_run('shape')
        self.assertNotIn('style', studio.item(self.root, 'articles', plain['id'])[1])
        self.assertIsNone(runner.job(self.root, plain['id'])[1]['style'])
        _, record, run = runner.load(self.root, plain['id'])
        self.assertNotIn(
            'style', runner.inputs(self.root, record, run), 'stage pins saved before styles hold'
        )
        self.assertIsNone(plain['style_name'])

    def test_a_minimal_edit_keeps_to_its_request_without_the_style(self):
        found = self.submit(self.editor_check(self.styled('how-to'), 'shape'))
        self.assertIsNotNone(runner.job(self.root, found['id'])[1]['style'])
        found = runner.decide(
            self.root,
            found['id'],
            found['expected'],
            'changes',
            'Shorten it.',
            page=True,
            target='draft',
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
        found = self.editor_check(ident, 'proofread')
        _, record = studio.item(self.root, 'articles', found['id'])
        self.assertEqual(record['style'], {'style_id': 'how-to', 'revision': 1})
        self.assertEqual(found['style_name'], 'How-to and tutorial')

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

    def setUp(self):
        super().setUp()
        isolation.voices_on(self.root)  # These exercise the older voice tools.

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

    def voiced(self, *words, title='Gateway guide'):
        """A saved manuscript registered in chat with the voice the words give it."""
        found = self.command('article', 'create', '--title', title, '--mode', 'first-draft', *words)
        self.file.write_text(self.MANUSCRIPT)
        self.command(
            'article', 'save', '--id', found['id'], '--kind', 'draft', '--file', str(self.file)
        )
        return found['id']

    def test_a_tone_beside_a_voice_is_kept_as_a_nudge(self):
        import writing_defaults

        mine = self.voice()
        found = self.editor_check(self.voiced('--profile', mine['id'], '--tone', 'Warm'), 'shape')
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
            self.voice_of(self.editor_check(self.voiced('--profile', mine['id']), 'shape')),
            pinned,
            'without a tone the voice has no tone key, so earlier pins hold',
        )

    def test_the_worker_brief_names_the_voice_style_and_tone(self):
        mine = self.voice()
        ident = self.voiced('--profile', mine['id'], '--tone', 'Warm')
        directory, record = studio.item(self.root, 'articles', ident)
        record['style'] = studio.style_pin(self.root, 'how-to')
        studio.persist(directory, 'articles', record)
        found = self.editor_check(ident, 'shape')  # Feedback on the shape reads the style.
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
        plain = self.editor_check(self.voiced('--voice', 'tone', '--tone', 'Warm'), 'shape')
        self.assertTrue(
            runner.job(self.root, plain['id'])[2].startswith(
                'No author voice is pinned; follow voice.tone.\n\n'
            )
        )
        bare_tone = self.editor_check(self.voiced('--voice', 'tone'), 'shape')
        self.assertTrue(
            runner.job(self.root, bare_tone['id'])[2].startswith(
                'No author voice is pinned; write plainly in the house style.\n\n'
            )
        )
        bare = self.editor_check(self.voiced('--profile', mine['id']), 'shape')
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
        self.assertIsNone(shown['default_voice'], 'the run options answer without its Team Hub')
        self.assertIn('profiles', shown)

    def test_a_manuscript_keeps_its_own_voice_unless_the_person_picks_one(self):
        mine = self.voice()
        self.default(mine)
        existing = self.command(
            'article', 'create', '--title', 'Imported', '--mode', 'existing', '--voice', 'preserve'
        )
        self.file.write_text('# Imported\n\nAn original sentence.')
        for kind in ('original', 'draft'):
            self.command(
                'article', 'save', '--id', existing['id'], '--kind', kind, '--file', str(self.file)
            )
        found = self.editor_check(existing['id'], 'shape')
        self.assertEqual(self.voice_of(found)['mode'], 'preserve')
        self.assertTrue(
            runner.job(self.root, found['id'])[2].startswith(
                'No author voice is pinned; keep the manuscript’s own voice.\n\n'
            )
        )
        nudged = self.editor_check(self.voiced('--voice', 'preserve', '--tone', 'Warm'), 'shape')
        self.assertTrue(
            runner.job(self.root, nudged['id'])[2].startswith(
                'No author voice is pinned; keep the manuscript’s own voice. Tone nudge: Warm.\n\n'
            )
        )
        picked = self.editor_check(self.voiced('--profile', mine['id']), 'shape')
        self.assertEqual(self.voice_of(picked)['profile_id'], mine['id'])

    def test_a_run_says_how_its_voice_was_chosen(self):
        mine = self.voice()
        pinned = self.editor_check(self.voiced('--profile', mine['id']), 'shape')
        self.assertEqual(
            (
                pinned['voice_mode'],
                pinned['voice_profile'],
                pinned['voice_revision'],
                pinned['voice_name'],
            ),
            ('profile', mine['id'], mine['revision'], 'Avery'),
        )
        toned = self.editor_check(self.voiced('--voice', 'tone', '--tone', 'Warm'), 'shape')
        self.assertEqual(
            (toned['voice_mode'], toned['voice_profile'], toned['voice_revision']),
            ('tone', None, None),
        )
        kept = self.editor_check(self.voiced('--voice', 'preserve'), 'shape')
        self.assertEqual((kept['voice_mode'], kept['voice_profile']), ('preserve', None))
        self.assertEqual(runner.engine(self.root).describe(kept['id'])['voice_mode'], 'preserve')

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
    """Uploaded material, for the tests below."""

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


class FilesTests(FilesCase):
    """Uploaded files a run reads: excerpted to its budget and named, never refused."""

    def test_oversized_files_are_excerpted_and_named_instead_of_refused(self):
        big = 'Retries cost money. ' * 16_000  # 320,000 characters
        sources = self.material(('big.md', big), ('small.txt', 'Hops add latency.'))
        found = self.editor_run('factual-support', sources=sources)
        self.assertEqual(found['excerpted'], ['big'])
        _, record, run = runner.load(self.root, found['id'])
        self.assertEqual(record['material'], sources)
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
        self.assertEqual(runner.engine(self.root).describe(found['id'])['excerpted'], ['big'])


class FromFilesReviewTests(FilesCase):
    """What a saved run's excerpts follow, and a deleted blog takes its files with it."""

    def test_excerpts_follow_the_persons_words_not_the_defaults(self):
        # A run from files the earlier flow saved keeps the note the person wrote about them.
        self.assertEqual(runner.run_terms({}, {'files_note': '', 'brief': {'goal': ''}}), [])
        words = runner.run_terms(
            {}, {'files_note': 'Why the gateway retries matter for our team', 'brief': {}}
        )
        self.assertIn('gateway', words)
        self.assertIn('retries', words)
        for common in ('why', 'the', 'for', 'our', 'with', 'from', 'files', 'uploaded'):
            self.assertNotIn(common, words)
        # The editor's run keeps to its own brief.
        found = self.editor_run('factual-support')
        _, record, run = runner.load(self.root, found['id'])
        self.assertEqual(runner.run_terms(record, run), ['edit', 'saved', 'manuscript'])

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
        found = self.desk(sources=[ours, shared, single])
        _, record = studio.item(self.root, 'articles', found['id'])
        self.assertEqual(record['material'], [ours, shared, single])
        self.desk(title='Another blog', sources=[shared])  # another blog pins the second file
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
        import desk
        import desk_jobs

        payload, _ = desk_jobs._context(self.root, desk.read(self.root, found['id']))
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

    def test_examples_are_excerpted_under_the_same_budget_and_named(self):
        big = 'We shipped the gateway in March. ' * 10_000  # 330,000 characters
        facts = self.material(('small.txt', 'Hops add latency.'))
        examples = self.example(('big.md', big))
        found = self.editor_run('factual-support', sources=facts + examples)
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


class WriteAsTests(RunnerCase):
    """The page's Write as select: Me is the personal default voice, when one is set."""

    def setUp(self):
        super().setUp()
        isolation.voices_on(self.root)  # These exercise the older voice tools.

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
        # A default that no longer resolves is simply no default.
        import shutil

        shutil.rmtree(self.root / 'profiles' / profile['id'])
        self.assertIsNone(runner.options(self.root)['default_voice'])


class ResearchAccountTests(RunnerCase):
    def research_run(self):
        """The editor's check of the facts with research: its plan and research saved, the
        check gone on past both to its review."""
        found = self.editor_run('factual-support', research='web-allowed')
        found = self.submit(found, '- **instance-min**: Minimum?')
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
        found = self.submit(self.research_run())  # its review, after the research
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
        self.assertTrue(words.endswith('Then it makes again: the review.'), words)
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

        found = self.submit(self.editor_run('factual-support', research='web-allowed'))
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
                target='review',
                refresh=True,
            )


class ResearchPlanningTests(RunnerCase):
    def test_the_research_plan_job_uses_its_own_module(self):
        found = self.editor_run('factual-support', research='web-allowed')
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
                found = self.editor_run(
                    'factual-support', research='supplied-only', sources=[ident]
                )
                self.assertNotIn('claims-map', [row['stage'] for row in found['stages']])

    def test_only_factual_material_reaches_the_map_and_direct_validation(self):
        fact = self.role_source('reference')
        voice = self.role_source('voice-sample')
        example = self.role_source('inspiration')
        found = self.editor_run(
            'factual-support', research='supplied-only', sources=[fact, voice, example]
        )
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
        found = self.editor_run('factual-support', research='supplied-only', sources=[fact, voice])
        self.assertEqual(found['next'], 'claims-map')
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

    def mapped(self):
        """The editor's check of the facts against supplied material: it maps their claims."""
        source = self.source(self.PASSAGE)
        found = self.editor_run('factual-support', research='supplied-only', sources=[source['id']])
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
        self.assertEqual([s['stage'] for s in found['stages']], ['claims-map', 'review'])
        web = self.editor_run(
            'factual-support', research='web-allowed', sources=[source['selected_id']]
        )
        self.assertEqual([s['stage'] for s in web['stages']][:2], ['research-plan', 'research'])
        empty = self.editor_run('factual-support', research='supplied-only')
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
            found, source = self.mapped()
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
                # The corrected map is saved and the check goes on to its review.
                self.assertEqual((shown['status'], shown['next']), ('queued', 'review'))
            else:
                self.assertEqual(shown['status'], 'failed')
                self.assertIn(
                    'The claims map quoted passages that are not in your material: ', shown['error']
                )

    def test_the_check_continues_past_the_claims_map_at_every_level(self):
        import studios_config

        # The editor's check goes on to its review whatever the saved review level.
        for level in ('balanced', 'step_by_step'):
            with self.subTest(level=level):
                studios_config.update({'review': {'level': level}})
                found, source = self.mapped()
                found = self.submit(found, self.line(source))
                self.assertEqual(found['next'], 'review')
                self.assertEqual(found['stages'][0]['accepted_by'], runner.EDITOR_CHECK)

    def test_later_stages_receive_the_claims_map(self):
        found, source = self.mapped()
        found = self.submit(found, self.line(source))
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


class GateCheckTests(RunnerCase):
    def drafted(self, text='# Draft\n\nSynthetic writing.', profile=None):
        """The editor's revision with its draft saved, gone on to its review."""
        ident = self.article()
        if profile:
            self.command('article', 'voice', '--id', ident, '--profile', profile)
        return self.submit(self.editor_check(ident, 'revise'), text)

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
        # An older run kept its preservation check in its notes, not beside them.
        run['stages']['draft'].pop('preservation', None)
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
        found = self.drafted('# Draft\n\nKeep 12 units.')
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
        found = self.submit(found)  # its review
        rows = runner.document(self.root, found['id'], 'review')['checks']
        self.assertTrue(any(row['label'] == 'Numbers, links or quotations changed' for row in rows))

    def test_no_always_true_rows(self):
        found = self.submit(self.editor_run('factual-support', research='web-allowed'))
        labels = [
            row['label']
            for row in runner.document(self.root, found['id'], 'research-plan')['checks']
        ]
        self.assertNotIn('Saved document contains readable text', labels)
        self.assertNotIn('Document matches its submitted version and selected inputs', labels)
        self.assertEqual(labels, ['No automatic checks apply to Research questions.'])


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
        found = self.editor_run('factual-support', sources=facts + brief)
        _, record, run = runner.load(self.root, found['id'])
        stances = {s['name']: s['stance'] for s in runner.inputs(self.root, record, run)['sources']}
        self.assertEqual(stances, {'notes': 'evidence', 'launch-brief': 'messaging'})
        # Without messaging, no source carries a stance, so saved pins hold byte for byte.
        plain = self.editor_run('factual-support', sources=facts)
        _, record, run = runner.load(self.root, plain['id'])
        self.assertTrue(
            all('stance' not in s for s in runner.inputs(self.root, record, run)['sources'])
        )

    def test_the_writer_is_told_what_messaging_means(self):
        self.assertIn("stance 'messaging'", blog_worker.POLICY)
        self.assertIn('without attribution hedges', blog_worker.POLICY)
        # The editor's revision writes its draft with the messaging among its sources.
        found = self.editor_run('revise', sources=self.messaging(('launch-brief.md', self.BRIEF)))
        self.assertEqual(found['next'], 'draft')
        _, payload, guidance = runner.job(self.root, found['id'])
        self.assertEqual(payload['sources'][0]['stance'], 'messaging')
        self.assertIn('dates, versions and entitlements', guidance)
        self.assertIn("the messaging's other claims are the product's own", guidance)

    def test_the_claims_map_reads_messaging_as_the_products_own_claims(self):
        found = self.editor_run(
            'factual-support',
            research='supplied-only',
            sources=self.messaging(('launch-brief.md', self.BRIEF)),
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

    def at_draft(self):
        """The editor's revision, its draft step next."""
        found = self.editor_run('revise')
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

    def test_reader_facing_notes_finds_todo_tbd_and_placeholder_in_any_case(self):
        from text_checks import reader_facing_notes

        text = (
            'Ships in [TODO].\n'
            'Priced at [tbd].\n'
            '[Placeholder: the launch quote]\n'
            '[todo: confirm the region list]\n'
            'An unclosed [PLACEHOLDER: the date\n'
        )
        self.assertEqual(
            [f['target'] for f in reader_facing_notes(text)],
            [
                '[TODO]',
                '[tbd]',
                '[Placeholder: the launch quote]',
                '[todo: confirm the region list]',
                '[PLACEHOLDER: the date',
            ],
        )
        self.assertEqual([f['line'] for f in reader_facing_notes(text)], [1, 2, 3, 4, 5])

    def test_reader_facing_notes_leaves_markdown_link_text_alone(self):
        from text_checks import reader_facing_notes

        text = (
            'The core is [source-available](https://example.com/license) under a '
            'community licence, see [source-code][1] and [TODO list](https://example.com/todo).\n'
            'A todo, a TBD and a placeholder named in prose are fine.\n\n'
            '[1]: https://example.com/code\n'
        )
        self.assertEqual(reader_facing_notes(text), [])
        # A note still counts beside a link on the same line.
        self.assertEqual(
            [
                f['target']
                for f in reader_facing_notes(
                    'See [source-available](https://example.com) [source-abc123].'
                )
            ],
            ['[source-abc123]'],
        )
        # Two notes side by side are two notes, not link text and its reference.
        self.assertEqual(
            [f['target'] for f in reader_facing_notes('It retries [source-1][Source-2][TBD].')],
            ['[source-1]', '[Source-2]', '[TBD]'],
        )

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
                self.root,
                found['id'],
                found['expected'],
                'changes',
                'Clean it.',
                page=True,
                target='draft',
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

    def test_the_gap_list_has_its_own_styles_on_opaque_paper(self):
        import re

        assets = Path(runner.__file__).resolve().parents[1] / 'assets/management'
        script = (assets / 'runner.js').read_text()
        # The list sits in the aside's opaque paper section, never on material.
        self.assertIn(
            "sAdd(sNode('section','paper aside-part'),sNode('h2','aside-title','Needs you before "
            "publishing'),sAdd(sNode('ul','gap-items')",
            script,
        )
        css = re.sub(r'/\*.*?\*/', '', (assets / 'blog.css').read_text(), flags=re.S)
        rules = {
            selector.strip(): body
            for selector, body in re.findall(r'([^{}]+)\{([^{}]*)\}', css)
            if 'gap-items' in selector
        }
        self.assertEqual(
            sorted(rules),
            ['.gap-items', '.gap-items>li', '.gap-items>li+li', '.gap-items>li::marker'],
        )
        self.assertIn('padding-left:', rules['.gap-items'])
        # A long gap, such as a pasted link, wraps inside the pane at phone width.
        self.assertIn('overflow-wrap:anywhere', rules['.gap-items>li'])
        self.assertIn('min-width:0', rules['.gap-items>li'])
        # Quiet separators and the "needs you" colour, both from tokens; no glass.
        self.assertIn('border-top:1px solid var(--hair)', rules['.gap-items>li+li'])
        self.assertIn('color:var(--yours)', rules['.gap-items>li::marker'])
        self.assertNotIn('backdrop-filter', ''.join(rules.values()))
        self.assertNotIn('background', ''.join(rules.values()))

    def test_a_workers_extra_field_is_refused_in_the_current_words(self):
        with self.assertRaisesRegex(
            ValueError,
            r'^A worker returns content and notes, and with a draft or a handoff its evidence '
            r'and gaps; nothing else\.$',
        ):
            blog_worker.validate({'content': 'A draft', 'notes': '', 'approve': True})


class LengthAndQualificationTests(RunnerCase):
    """Qualify once, and a length is for new writing only."""

    def test_a_revision_is_written_to_no_length(self):
        # A run the earlier flow saved with a length keeps it in its record, and the editor's
        # check makes its run again over that record: its revision is an edit, never resized.
        ident = self.article()
        self.editor_check(ident, 'proofread')
        directory, _, run = runner.load(self.root, ident)
        studio.write_json(directory / runner.STATE, {**run, 'length': 'deep'})
        found = self.editor_check(ident, 'revise')
        self.assertEqual(runner.load(self.root, found['id'])[2]['length'], 'deep')
        guidance = runner.job(self.root, found['id'])[2]
        self.assertNotIn(runner.LENGTHS['deep'], guidance)
        self.assertIn('minimal edit, not a rewrite', guidance)

    def test_the_review_checks_a_limitation_is_qualified_once(self):
        guidance = runner.job(self.root, self.editor_run('shape')['id'])[2]
        self.assertIn('repeated in three or more sections', guidance)

    def test_the_point_is_the_angle_and_the_style_sets_the_register(self):
        plan = self.editor_run(
            'factual-support', research='web-allowed', sources=[self.source()['id']]
        )
        self.assertEqual(plan['next'], 'research-plan')
        self.assertIn('Read the point to make as the angle', runner.job(self.root, plan['id'])[2])
        ident = self.article()
        directory, record = studio.item(self.root, 'articles', ident)
        record['style'] = studio.style_pin(self.root, 'product-announcement')
        studio.persist(directory, 'articles', record)
        review = runner.job(self.root, self.editor_check(ident, 'shape')['id'])[2]
        self.assertIn('the house guide still decides mechanics', review)


class ReviewFixTests(RunnerCase):
    """Final review: notes survive edits, reach the review, and a saved handoff is checked."""

    EVIDENCE, GAPS = ReaderFacingNotesTests.EVIDENCE, ReaderFacingNotesTests.GAPS

    def drafted(self, **extra):
        """The editor's revision with a draft saved beside its notes, gone on to its review."""
        found = self.editor_run('revise', **extra)
        return runner.submit(
            self.root,
            found['id'],
            'draft',
            {
                'content': '# Draft\n\nGateway Prime retries twice.\n',
                'notes': '',
                'evidence': self.EVIDENCE,
                'gaps': self.GAPS,
            },
            found['expected'],
            page=True,
        )

    def test_the_review_reads_the_drafts_evidence(self):
        source = self.source()['id']
        found = self.drafted(sources=[source])
        self.assertEqual(found['next'], 'review')
        # A check of the facts on the revised blog reads the claims its draft noted.
        found = self.editor_check(found['id'], 'factual-support', sources=[source])
        self.assertEqual(found['next'], 'review')
        _, payload, guidance = runner.job(self.root, found['id'])
        self.assertEqual(payload['evidence'], self.EVIDENCE)
        self.assertIn('evidence lists', guidance)

    def test_a_saved_handoff_is_checked_for_notes_outside_its_gaps(self):
        import saved_fixtures

        # A handoff the earlier flow saved is still read with its checks.
        ident = saved_fixtures.load(self.root, 'handoff-gate')
        directory, _ = studio.item(self.root, 'articles', ident)
        (directory / 'derived/blog-package.md').write_text(
            '# Handoff\n\nDescription: Retries twice [source-abc123].\n\n'
            '## Needs you before publishing\n\n- [Editorial placeholder: the date]\n'
        )
        row = next(
            c
            for c in runner.document(self.root, ident, 'package')['checks']
            if 'handoff' in c['label']
        )
        self.assertEqual(
            (row['label'], row['passed'], row['detail']),
            ('Source IDs or editorial notes in the handoff', False, ['line 3: [source-abc123]']),
        )

    def test_notes_that_cannot_be_read_or_are_blank_lose_nothing(self):
        result = blog_worker.validate(
            {'content': 'x', 'notes': '', 'evidence': [], 'gaps': ['  ', 'A date.']}
        )
        self.assertEqual(result['gaps'], ['A date.'])
        self.assertEqual(blog_worker.WRITING_SCHEMA['properties']['gaps']['items']['minLength'], 1)
        found = self.drafted()
        directory, _, _ = runner.load(self.root, found['id'])
        for broken in ('not json', '["a list"]', '{"gaps": [3, "Kept."]}'):
            (directory / 'derived/blog-draft-notes.json').write_text(broken)
            shown = runner.document(self.root, found['id'], 'draft')
            self.assertEqual(shown['gaps'], ['Kept.'] if 'Kept' in broken else [])

    def test_the_policy_keeps_source_ids_for_notes(self):
        self.assertIn('Cite supplied sources by their IDs in notes or evidence', blog_worker.POLICY)


class SharedGuidanceTests(RunnerCase):
    """The writing desk reads the same house guide and style rule as a run's steps; pulling
    them into helpers left a run's guidance exactly as it was."""

    def test_a_styled_runs_review_guidance_is_unchanged(self):
        ident = self.article()
        self.command('article', 'voice', '--id', ident, '--voice', 'tone', '--tone', 'Warm')
        directory, record = studio.item(self.root, 'articles', ident)
        record['style'] = studio.style_pin(self.root, 'how-to')
        studio.persist(directory, 'articles', record)
        found = self.editor_check(ident, 'shape')  # Feedback on the shape reads the style.
        references = Path(runner.__file__).resolve().parents[1] / 'references'
        _, payload, guidance = runner.job(self.root, found['id'])
        tail = (
            '\n\n'
            + (references / 'style/house.md').read_text()
            + '\n\nSELECTED STYLE: '
            + payload['style']['name']
            + '. Its guide is in style.guide. The style says the shape of this kind of '
            'writing: structure, moves, length, headings and register. The selected voice '
            'says how its author sounds. Where they conflict on wording, the voice wins; '
            'where they conflict on structure, the style wins. Neither invents facts, '
            'experience or sources. Where the style’s register differs from the house '
            'guide’s tone defaults, the style wins; the house guide still decides mechanics.'
        )
        self.assertEqual(guidance.count(tail), 1)
        self.assertEqual(
            guidance.split(tail)[0],
            runner.brief_line(self.root, runner.load(self.root, found['id'])[1], payload)
            + '\n\n'
            + runner.STAGES['review'][2]
            + '\n\n'
            + (references / runner.GUIDES['review']).read_text(),
        )
        for length in runner.LENGTHS.values():
            if length:
                self.assertNotIn(length, guidance)
