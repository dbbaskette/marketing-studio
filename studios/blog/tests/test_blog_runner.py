"""The same blog, gates and edits through chat commands and the authenticated page."""

import json
import http.client
from pathlib import Path
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


class BlogRunnerTests(Fixture):
    def setUp(self):
        super().setUp()
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

    def test_research_questions_and_findings_each_wait_for_approval(self):
        found = self.create(research='supplied-only', stop='outline')
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
