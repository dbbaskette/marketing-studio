"""Failed local stages never replay assistant or image-provider work."""
import json
from unittest import mock
from helpers import Isolated
import test_desk_engine as fixtures
from runner import build_recovery, exports
from runner.contracts import Invalid


class BuildRecoveryTests(Isolated):
    def setUp(self):
        super().setUp()
        fixtures.setup_desk(self)
        self.engine.assistant = mock.Mock()
        self.provider = mock.Mock()
        self.engine.adapters = {'synthetic': self.provider}

    def test_font_preview_failure_keeps_scene_and_retry_only_renders(self):
        before = self.store.read(self.ident)
        self.renderer.side_effect = RuntimeError('private prompt /machine/path credential-value')
        with self.assertRaises(RuntimeError): self.engine.build(self.ident, expected_revision=6, request_id='build1')
        record = build_recovery.read(self.store, self.ident)
        self.assertEqual(record['step'], 'font-check')
        self.assertEqual(record['completed'], ['Page composition'])
        self.assertEqual(record['next_action'], 'preview')
        self.assertTrue(record['current'])
        self.assertEqual(self.store.read(self.ident), before)
        self.assertNotIn('private prompt', json.dumps(record))
        self.renderer.side_effect = fixtures.fake_renderer
        self.engine.preview(self.ident, expected_revision=6)
        self.assertEqual(build_recovery.read(self.store, self.ident)['state'], 'complete')
        self.assertEqual(self.engine.assistant.mock_calls, []);self.assertEqual(self.provider.mock_calls, [])

    def test_final_preview_failure_offers_only_local_preview_and_survives_reopen(self):
        with mock.patch.object(self.engine, 'preview', side_effect=[{}, RuntimeError('synthetic final preview')]):
            with self.assertRaises(RuntimeError): self.engine.build(self.ident, expected_revision=6, request_id='build2')
        record = build_recovery.read(self.store, self.ident)
        self.assertEqual(record['step'], 'preview')
        self.assertIn('Font and layout preflight', record['completed'])
        reopened = fixtures.Engine(self.store, renderer=self.renderer)
        self.assertEqual(reopened.inspect(self.ident)['workflow_recovery']['diagnostic'], record['diagnostic'])
        reopened.preview(self.ident, expected_revision=6)
        self.assertEqual(self.store.read(self.ident)['attempts'], [])
        self.assertEqual(self.engine.assistant.mock_calls, []);self.assertEqual(self.provider.mock_calls, [])

    def test_export_failure_preserves_revision_and_approval_and_exposes_local_retry(self):
        before = self.store.read(self.ident)
        with mock.patch.object(exports, 'build', side_effect=RuntimeError('synthetic export failure')):
            with self.assertRaises(RuntimeError): self.engine.preview(self.ident, expected_revision=6, draft=False)
        record = build_recovery.read(self.store, self.ident)
        self.assertEqual((record['next_action'], record['next_values']), ('export', {'draft': False}))
        self.assertEqual(self.store.read(self.ident), before)
        self.assertEqual(self.engine.assistant.mock_calls, []);self.assertEqual(self.provider.mock_calls, [])

    def test_edited_revision_or_tampered_retry_cannot_replay_an_operation(self):
        build_recovery.keep(self.store, self.ident, 'preview', ['Saved page'], state='failed')
        current = self.store.update(self.ident, {'brief': {**self.store.read(self.ident)['brief'], 'title': 'Changed title'}}, expected_revision=6)
        self.assertFalse(build_recovery.read(self.store, self.ident)['current'])
        self.assertIsNone(build_recovery.read(self.store, self.ident)['next_action'])
        path = self.store._project(self.ident)/build_recovery.FILE
        value = json.loads(path.read_bytes());value['next_action']='image-start';path.write_text(json.dumps(value))
        self.assertIsNone(build_recovery.read(self.store, self.ident))
        self.assertIsNone(current['approval'])

    def test_api_returns_safe_substep_receipt_for_a_failed_preview(self):
        from runner import server
        page=server.Page(8000,self.store,self.engine)
        self.renderer.side_effect=RuntimeError('private-key /machine/path secret-prompt')
        status,_,raw=page.write('/api/action',{'id':self.ident,'action':'build','expected_revision':6,'request_id':'build-api'})
        shown=json.loads(raw)
        self.assertEqual(status,422)
        self.assertEqual(shown['recovery']['next_action'],'preview')
        self.assertEqual(shown['recovery']['completed'],['Page composition'])
        self.assertNotIn('private-key',raw.decode())
        self.assertNotIn('/machine/path',raw.decode())
