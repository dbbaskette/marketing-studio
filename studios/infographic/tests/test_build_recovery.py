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

    def test_two_projects_keep_their_own_concurrent_failed_stage(self):
        from concurrent.futures import ThreadPoolExecutor
        import threading
        second=self.store.create('Second synthetic page',preset='digital')
        barrier=threading.Barrier(2)
        def fail(ident,**kwargs):
            checkpoint=kwargs['checkpoint']
            checkpoint['step']='preview' if ident==self.ident else 'font-check'
            barrier.wait(5)
            raise RuntimeError('synthetic concurrent failure')
        def build(item):
            with self.assertRaises(RuntimeError):self.engine.build(item['id'],expected_revision=item['revision'],request_id='concurrent-build')
        with mock.patch.object(self.engine,'_build',side_effect=fail),ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(build,[self.store.read(self.ident),second]))
        self.assertEqual(build_recovery.read(self.store,self.ident)['step'],'preview')
        self.assertEqual(build_recovery.read(self.store,second['id'])['step'],'font-check')

    def test_saved_artwork_placement_retry_does_not_generate_again(self):
        from copy import deepcopy
        from runner import stories
        from runner.images.base import result,save_asset
        from graphics_fixtures import png
        proposal=deepcopy(self.proposal);proposal['blocks'][0].update(illustration=True,illustration_role='Show a restarting instance beside serving instances.')
        current=stories.adopt(self.store,self.ident,[proposal],expected_revision=6)
        current=stories.select(self.store,self.ident,'story1',expected_revision=current['revision'])
        calls=[]
        class Adapter:
            def __init__(self,folder):self.folder=folder
            def generate(self,*,attempt_id,brief):
                calls.append(attempt_id)
                return result('gemini','generate',attempt_id,state='complete',assets=[save_asset(self.folder,png(),'image/png')])
        def direction(project):
            region=project['scene']['art_regions'][0]['id']
            return {'style':'Coherent explanatory shapes.','reading_order':'Restarting then serving instances.','acceptance':'Exact counts and clear label regions.',
                'objects':[{'id':'instances','region_id':region,'count':3,'description':'Three service instances.','relationships':'One restarts; two serve.','preserve':'Leave labels empty.'}]}
        self.engine.assistant.art_direction.side_effect=direction
        self.engine.adapters={'gemini':Adapter};self.engine.configuration={'image_provider':'gemini'}
        with mock.patch.object(self.engine,'compose_asset',side_effect=RuntimeError('synthetic placement failure')):
            with self.assertRaises(RuntimeError):self.engine.build(self.ident,expected_revision=current['revision'],request_id='one-image')
        recovery=build_recovery.read(self.store,self.ident)
        self.assertEqual(recovery['step'],'place-artwork')
        self.engine.compose_asset(self.ident,recovery['next_values']['asset_id'],expected_revision=recovery['revision'])
        self.assertEqual(calls,['one-image'])
        self.assertEqual(self.engine.assistant.art_direction.call_count,1)
        self.assertEqual(build_recovery.read(self.store,self.ident)['state'],'complete')
