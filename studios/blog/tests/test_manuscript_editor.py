"""Manuscript workflows with synthetic writing and provider boundaries."""

import json
import unittest
from unittest.mock import patch

from test_editorial_tools import Fixture
import blog_runner as runner
import manuscript_editor as editor
import studio
import team_workspace


class ManuscriptTests(Fixture):
    def setUp(self):
        super().setUp()
        self.ident = self.article()
        self.addCleanup(lambda: runner.ENGINES.pop(str(self.root), None))

    def action(self, name, **values):
        current = editor.read(self.root, self.ident)
        return editor.dispatch(
            self.root, name, {'id': self.ident, 'expected': current['expected'], **values}
        )

    def test_save_keeps_history_and_refuses_stale_editor(self):
        old = editor.read(self.root, self.ident)
        saved = self.action('save', content='The gateway handles 12 requests.')
        self.assertTrue(saved['preservation']['needs_review'])
        directory, _ = studio.item(self.root, 'articles', self.ident)
        self.assertTrue(list((directory / 'history').glob('draft-*.md')))
        with self.assertRaisesRegex(ValueError, 'changed'):
            editor.dispatch(
                self.root,
                'save',
                {'id': self.ident, 'expected': old['expected'], 'content': 'Stale'},
            )
        self.assertEqual((directory / 'DRAFT.md').read_text(), saved['content'])

    def test_edit_action_skips_research_and_preserves_other_author_voice(self):
        with patch.object(runner.Engine, 'control', return_value={'status': 'queued'}):
            self.action('check', check='humanization', request='Only improve repetitive openings')
        _, record, run = runner.load(self.root, self.ident)
        self.assertEqual(run['pipeline'], ['review'])
        self.assertEqual(record['author'], 'Avery')
        _, payload, guidance = runner.job(self.root, self.ident)
        self.assertIn('repetitive openings', payload['changes'])
        self.assertIn('Humanization capability', guidance)
        self.assertIn('Factual support capability', guidance)
        self.assertIn('JSON in content', guidance)

    def test_proofread_and_copyedit_replace_failed_research_without_research(self):
        for check in ('polish', 'proofread', 'copyedit'):
            with self.subTest(check=check), patch.object(runner.Engine, 'control', return_value={}):
                self.action('check', check=check, research='web-allowed')
                _, record, run = runner.load(self.root, self.ident)
                self.assertEqual(run['pipeline'], ['review'])
                self.assertEqual(run['editor_check'], check)
                self.assertEqual(record['author'], 'Avery')
                self.assertEqual(run['mode'], 'review')
                if check == 'polish':
                    _, payload, guidance = runner.job(self.root, self.ident)
                    self.assertIn('humanize formulaic wording', payload['changes'])
                    self.assertIn('AI', guidance)
                    self.assertIn('Do not research', payload['changes'])

    def test_scoped_findings_are_saved_and_become_stale_after_edit(self):
        with patch.object(runner.Engine, 'control', return_value={}):
            self.action('check', check='polish')
        found = runner.survey(self.root, self.ident)
        value = {
            'summary': 'Opening checked; editorial assessment only.',
            'findings': [
                {
                    'id': 'opening',
                    'kind': 'edit',
                    'before': 'Clients send requests to a gateway.',
                    'after': 'Clients call a gateway.',
                    'reason': 'Shorter opening.',
                    'evidence': 'Editorial judgment',
                    'verdict': 'editorial',
                }
            ],
        }
        runner.submit(
            self.root,
            self.ident,
            'review',
            {'content': json.dumps(value), 'notes': ''},
            found['expected'],
            page=True,
        )
        self.assertEqual(
            editor.read(self.root, self.ident)['checks']['polish']['status'], 'current'
        )
        self.action('save', content='A changed manuscript.')
        self.assertEqual(editor.read(self.root, self.ident)['checks']['polish']['status'], 'stale')

    def test_polish_repairs_invalid_feedback_once_without_research_or_draft_changes(self):
        for repair in (True, False):
            with self.subTest(repair=repair):
                with patch.object(runner.Engine, 'control', return_value={}):
                    self.action('check', check='polish')
                original = editor.read(self.root, self.ident)['content']
                calls = []

                def worker(engine, data, guidance, *, calls=calls, repair=repair, **options):
                    calls.append(options)
                    quoted = (
                        'Clients send requests to a gateway.'
                        if repair and len(calls) == 2
                        else 'Missing passage.'
                    )
                    return {
                        'content': json.dumps(
                            {
                                'summary': 'Writing polish only.',
                                'findings': [
                                    {
                                        'id': 'opening',
                                        'kind': 'edit',
                                        'before': quoted,
                                        'after': 'Clients call a gateway.',
                                        'reason': 'Concise wording.',
                                        'evidence': 'Editorial judgment',
                                        'verdict': 'editorial',
                                    }
                                ],
                            }
                        ),
                        'notes': '',
                    }

                engine = runner.Engine(self.root, worker)
                engine.control(self.ident, 'resume')
                engine._once(self.ident)
                self.assertEqual(len(calls), 2)
                self.assertTrue(all(not c['web'] for c in calls))
                self.assertEqual(editor.read(self.root, self.ident)['content'], original)
                self.assertEqual(
                    engine.local(self.ident)['status'],
                    'waiting-for-approval' if repair else 'failed',
                )

    def test_applying_feedback_finishes_without_requeuing_the_review(self):
        with patch.object(runner.Engine, 'control', return_value={}):
            self.action('check', check='polish')

        def worker(*args, **kwargs):
            return {
                'content': json.dumps(
                    {
                        'summary': 'Synthetic polish',
                        'findings': [
                            {
                                'id': 'one',
                                'kind': 'edit',
                                'before': 'Clients send',
                                'after': 'Clients route',
                                'reason': 'Precise wording.',
                                'verdict': 'editorial',
                                'evidence': 'Editorial judgment',
                            }
                        ],
                    }
                ),
                'notes': '',
            }

        engine = runner.Engine(self.root, worker)
        runner.ENGINES[str(self.root)] = engine
        engine.control(self.ident, 'resume')
        engine._once(self.ident)
        self.assertFalse(engine.local(self.ident)['enabled'])
        # Simulate a completed pass saved by an older page version.
        engine.keep_local(self.ident, {**engine.local(self.ident), 'enabled': True})
        finding = editor.read(self.root, self.ident)['findings'][0]
        self.action(
            'proposals',
            proposals=[{k: v for k, v in finding.items() if k not in ('evidence', 'verdict')}],
        )
        result = self.action('apply-selected', proposals=['one'])
        self.assertFalse(result['working'])
        self.assertEqual(
            result['content'], 'Clients route requests to a gateway. The gateway calls the service.'
        )
        self.assertFalse(engine.local(self.ident)['enabled'])

    def test_invalid_located_findings_do_not_replace_the_manuscript(self):
        with patch.object(runner.Engine, 'control', return_value={}):
            self.action('check', check='factual-support')
        found = runner.survey(self.root, self.ident)
        with self.assertRaisesRegex(ValueError, 'located findings'):
            runner.submit(
                self.root,
                self.ident,
                'review',
                {'content': '{}', 'notes': ''},
                found['expected'],
                page=True,
            )
        self.assertIn('Clients send', editor.read(self.root, self.ident)['content'])

    def test_local_proposals_do_not_call_google(self):
        with patch('google_drive.Client', side_effect=AssertionError('No provider')):
            result = self.action(
                'proposals',
                proposals=[{'kind': 'comment', 'before': 'Clients', 'reason': 'Which clients?'}],
            )
        self.assertEqual(len(result['proposals']), 1)

    def test_batch_application_applies_only_selected_edits_and_retains_history(self):
        self.action(
            'proposals',
            proposals=[
                {
                    'id': 'first',
                    'kind': 'edit',
                    'before': 'Clients send',
                    'after': 'Clients route',
                    'reason': 'Precise verb.',
                },
                {
                    'id': 'second',
                    'kind': 'edit',
                    'before': 'calls the service',
                    'after': 'invokes the service',
                    'reason': 'Consistent verb.',
                },
                {
                    'id': 'question',
                    'kind': 'comment',
                    'before': 'gateway',
                    'reason': 'Which gateway?',
                },
            ],
        )
        saved = self.action('apply-selected', proposals=['first', 'second'])
        self.assertEqual(saved['applied'], 2)
        self.assertEqual(
            saved['content'],
            'Clients route requests to a gateway. The gateway invokes the service.',
        )
        directory, _ = studio.item(self.root, 'articles', self.ident)
        self.assertTrue(list((directory / 'history').glob('draft-*.md')))

    def test_batch_refuses_overlaps_ambiguous_and_missing_quotes_without_partial_save(self):
        original = editor.read(self.root, self.ident)['content']
        for before in ('Clients send requests', 'gateway', 'Missing text'):
            with self.subTest(before=before):
                self.action(
                    'proposals',
                    proposals=[
                        {
                            'id': 'one',
                            'kind': 'edit',
                            'before': 'Clients send',
                            'after': 'Clients route',
                            'reason': 'One.',
                        },
                        {
                            'id': 'two',
                            'kind': 'edit',
                            'before': before,
                            'after': 'Another wording',
                            'reason': 'Two.',
                        },
                    ],
                )
                with self.assertRaises(ValueError):
                    self.action('apply-selected', proposals=['one', 'two'])
                self.assertEqual(editor.read(self.root, self.ident)['content'], original)

    def test_queued_editing_operation_blocks_mutation_and_exposes_recovery_state(self):
        with patch.object(runner.Engine, 'control', return_value={}):
            self.action('check', check='polish')
        engine = runner.engine(self.root)
        engine.keep_local(self.ident, {'enabled': True, 'status': 'queued'})
        shown = editor.read(self.root, self.ident)
        self.assertTrue(shown['working'])
        self.assertEqual(shown['operation']['editor_check'], 'polish')
        self.assertEqual(runner.catalog(self.root)['items'][0]['editor_check'], 'polish')
        with self.assertRaisesRegex(ValueError, 'Pause or stop'):
            self.action('save', content='An unsafe concurrent edit.')

    def test_from_outline_starts_at_draft_and_ideas_stop_before_draft(self):
        found = runner.create(
            self.root,
            {
                'title': 'Synthetic outline',
                'audience': 'Developers',
                'goal': 'Explain',
                'mode': 'from-outline',
                'outline_text': '# First\n## Then',
                'research': 'none',
                'stop': 'draft',
            },
        )
        self.assertEqual(found['next'], 'draft')
        _, data, _ = runner.job(self.root, found['id'])
        self.assertEqual(data['documents']['outline'], '# First\n## Then')
        ideas = runner.create(
            self.root,
            {
                'title': 'Synthetic ideas',
                'audience': 'Developers',
                'goal': 'Find an angle',
                'mode': 'ideas',
            },
        )
        self.assertEqual([v['stage'] for v in ideas['stages']], ['outline'])
        self.assertIn('three distinct blog angles', runner.job(self.root, ideas['id'])[2])

    def test_local_workspace_is_not_joined_and_has_no_false_changed_notice(self):
        root = self.base / 'local' / 'blogs'
        root.mkdir(parents=True)
        (root / 'hub.json').write_text(
            json.dumps(
                {
                    'schema': 1,
                    'tool': 'blog-studio',
                    'name': 'local',
                    'repository': None,
                    'branch': 'main',
                    'folder': 'blogs',
                    'minimum_runtime': '4.0.0',
                }
            )
        )
        status = team_workspace.status(root)
        self.assertFalse(status['joined'])
        self.assertIsNone(status.get('configuration_notice'))


import test_google_start
import google_drive
import google_suggestions


class GoogleDeliveryTests(unittest.TestCase):
    start = test_google_start.GoogleStartTests.start

    def setUp(self):
        test_google_start.GoogleStartTests.setUp(self)
        self.ident = self.start()['id']
        self.addCleanup(lambda: runner.ENGINES.pop(str(self.root), None))

    def action(self, action, **data):
        current = editor.read(self.root, self.ident)
        with patch.object(google_drive, 'Client', return_value=self.client):
            return editor.dispatch(
                self.root, action, {'id': self.ident, 'expected': current['expected'], **data}
            )

    def test_plan_is_read_only_and_send_reuses_cli_revision_checks(self):
        self.action(
            'proposals',
            proposals=[
                {
                    'id': 'wording',
                    'kind': 'edit',
                    'before': 'Hello',
                    'after': 'Welcome',
                    'reason': 'Clearer greeting.',
                }
            ],
        )
        with patch.object(google_suggestions, 'plan') as plan:

            def save(client, root, ident, kind, findings, output, mode):
                studio.write_json(output, {'article': ident})
                return {'mode': mode, 'findings': len(findings)}

            plan.side_effect = save
            preview = self.action('google-plan', mode='auto')
        with patch.object(
            google_suggestions, 'apply', return_value={'status': 'verified-pending'}
        ) as send:
            result = self.action('google-send', plan=preview['plan'], confirmed=True)
            self.assertEqual(result['status'], 'verified-pending')
            send.assert_called_once()
        self.action('proposals', proposals=[])
        with patch.object(google_suggestions, 'apply', side_effect=AssertionError('No stale send')):
            with self.assertRaisesRegex(ValueError, 'changed'):
                self.action('google-send', plan=preview['plan'], confirmed=True)

    def test_delivery_requires_explicit_confirmation(self):
        with self.assertRaisesRegex(ValueError, 'confirm'):
            self.action('google-send', plan='a' * 32, confirmed=False)

    def test_real_suggestions_plan_send_and_idempotent_retry(self):
        self.action(
            'proposals',
            proposals=[
                {
                    'id': 'plain',
                    'kind': 'edit',
                    'before': 'delay',
                    'after': 'wait',
                    'reason': 'Use a plainer word.',
                }
            ],
        )
        preview = self.action('google-plan', mode='auto')
        self.assertEqual(self.client.writes, 0)
        result = self.action('google-send', plan=preview['plan'], confirmed=True)
        self.assertEqual(result['status'], 'verified-pending')
        writes = self.client.writes
        result = self.action('google-send', plan=preview['plan'], confirmed=True)
        self.assertEqual(self.client.writes, writes)

    def test_comments_fallback_keeps_author_text(self):
        from test_google_review_comments import CommentProvider

        self.client = CommentProvider()
        self.action(
            'proposals',
            proposals=[
                {
                    'id': 'plain',
                    'kind': 'edit',
                    'before': 'delay',
                    'after': 'wait',
                    'reason': 'Use a plainer word.',
                }
            ],
        )
        before = google_suggestions.signature(self.client.doc)
        preview = self.action('google-plan', mode='auto')
        self.assertEqual(preview['mode'], 'comments')
        result = self.action('google-send', plan=preview['plan'], confirmed=True)
        self.assertEqual(result['status'], 'verified-comments')
        self.assertEqual(google_suggestions.signature(self.client.doc), before)

    def test_changed_google_revision_refuses_delivery(self):
        self.action(
            'proposals',
            proposals=[
                {
                    'id': 'plain',
                    'kind': 'edit',
                    'before': 'delay',
                    'after': 'wait',
                    'reason': 'Use a plainer word.',
                }
            ],
        )
        preview = self.action('google-plan', mode='auto')
        self.client.doc['revisionId'] = 'another-revision'
        with self.assertRaises(google_drive.GoogleError):
            self.action('google-send', plan=preview['plan'], confirmed=True)
        self.assertEqual(self.client.writes, 0)

    def test_local_wording_changes_become_precise_google_suggestions(self):
        current = editor.read(self.root, self.ident)
        self.action('save', content=current['content'].replace('delay', 'wait'))
        result = self.action('changes')
        self.assertEqual(result['proposals'][0]['before'], 'delay')
        self.assertEqual(result['proposals'][0]['after'], 'wait')
        self.action('changes')
        self.assertEqual(len(editor.read(self.root, self.ident)['proposals']), 1)
        preview = self.action('google-plan', mode='auto')
        self.assertEqual(preview['count'], 1)

    def test_selected_suggestion_can_be_applied_locally_before_google(self):
        self.action(
            'proposals',
            proposals=[
                {
                    'id': 'plain',
                    'kind': 'edit',
                    'before': 'delay',
                    'after': 'wait',
                    'reason': 'Use a plainer word.',
                }
            ],
        )
        saved = self.action('apply-proposal', proposal='plain')
        self.assertIn('The wait is', saved['content'])
        self.assertEqual(self.client.writes, 0)
        self.assertIn('The delay is', saved['baseline'])
        preview = self.action('google-plan', mode='auto')
        self.assertEqual(
            self.action('google-send', plan=preview['plan'], confirmed=True)['status'],
            'verified-pending',
        )


class ResearchMetadataTests(Fixture):
    def test_capture_permissions_are_explicit_and_malformed_output_is_repaired_once(self):
        import threading
        import synthesis_research

        calls = []
        directory = self.base / 'research-blog'
        directory.mkdir()
        payload = {
            'title': 'Synthetic',
            'research_policy': 'supplied-only',
            'sources': [
                {
                    'id': 'one',
                    'name': 'Evidence',
                    'origin': 'https://example.invalid',
                    'purposes': ['reference'],
                    'status': 'ready',
                    'text': 'Synthetic fact.',
                }
            ],
            'documents': {'manuscript': 'A claim to check.'},
        }
        run = {'engine': 'codex', 'brief': {'goal': 'Check a claim'}, 'research_contract': {}}

        def worker(engine, data, guidance, **kwargs):
            calls.append(data)
            source = data['sources'][0]
            return {
                'content': json.dumps(
                    {
                        'sources': [
                            {**source, 'permission': 'public' if len(calls) == 1 else 'selected'}
                        ]
                    }
                ),
                'notes': '',
            }

        def workflow(root, task, invoke, sources):
            self.assertEqual(task['manuscript'], 'A claim to check.')
            text, _ = invoke(
                'author', 'Synthetic guidance', {'worker': 'author-test'}, sources, False
            )
            self.assertEqual(json.loads(text)['sources'][0]['permission'], 'selected')
            (root / 'research').mkdir()
            (root / 'research/report.md').write_text('Synthetic research')

        with (
            patch.object(synthesis_research.research_contract, 'snapshot', return_value={}),
            patch.object(
                synthesis_research.research_contract, 'find_runtime', return_value=self.base
            ),
            patch.object(
                synthesis_research.research_contract.Workflow, 'run', side_effect=workflow
            ),
            patch.object(synthesis_research.research_contract, 'publish'),
            patch.object(synthesis_research.research_contract.Workflow, 'command'),
        ):
            synthesis_research.generate(
                directory, run, payload, worker, seconds=30, stop=threading.Event()
            )
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]['sources'][0]['permission'], 'selected')
