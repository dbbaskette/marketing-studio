"""Durable intent, duplicate prevention, late-result and cancellation acceptance."""
from copy import deepcopy
from unittest import mock

from helpers import Isolated, project
from graphics_fixtures import png
from runner.contracts import Invalid, basis
from runner.image_jobs import Jobs
from runner.images.base import result, save_asset
from runner.workspace import Store


class ImageJobTests(Isolated):
    def setUp(self):
        super().setUp()
        self.store = Store.setup(self.workspace, data=self.data)
        initial = self.store.create('Image attempts')
        self.ident = initial['id']
        p = project()
        p.update(id=self.ident, owner=self.store.owner, revision=1)
        p['image_briefs'][0]['basis'] = basis(p)
        with self.store.locked():
            self.store.commit_locked(initial, p)
        self.calls = []
        self.behavior = None
        test = self
        class Adapter:
            def __init__(self, folder): self.folder = folder
            def generate(self, *, attempt_id, brief):
                test.calls.append(attempt_id)
                if test.behavior: return test.behavior(attempt_id, brief)
                return result('gemini', 'generate', attempt_id, state='complete',
                              assets=[save_asset(self.folder, png(), 'image/png')])
        self.jobs = Jobs(self.store, {'gemini': Adapter})

    def intent(self, key='request1', **extra):
        return self.jobs.intent(self.ident, expected_revision=1, brief_id='image1',
                                provider='gemini', request_id=key, **extra)

    def test_intent_is_persisted_before_provider_and_duplicate_key_never_executes(self):
        saved = self.intent()
        self.assertEqual(self.calls, [])
        self.assertEqual(self.intent(), saved)
        self.assertEqual(len(self.store.read(self.ident)['attempts']), 1)
        with self.assertRaises(Invalid):
            self.jobs.intent(self.ident, expected_revision=1, brief_id='image1', provider='codex', request_id='request1')
        self.assertEqual(self.jobs.execute(self.ident, 'request1')['state'], 'complete')
        self.assertEqual(self.calls, ['request1'])
        self.assertEqual(self.intent(), saved)
        with self.assertRaises(Invalid): self.jobs.execute(self.ident, 'request1')
        current = self.store.read(self.ident)
        self.assertEqual(current['attempts'][0]['state'], 'complete')
        self.assertEqual(len(current['assets']), 1)
        self.assertIsNone(current['approval'])

    def test_restart_and_unknown_outcome_do_not_resubmit(self):
        self.intent()
        restarted = Jobs(self.store, {'gemini': mock.Mock(side_effect=AssertionError('No provider'))})
        self.assertEqual(restarted.recovery(self.ident)[0]['state'], 'queued')
        self.behavior = lambda attempt_id, brief: result('gemini', 'generate', attempt_id, state='unknown', reason='timeout')
        self.assertEqual(self.jobs.execute(self.ident, 'request1')['state'], 'unknown')
        self.assertFalse(restarted.recovery(self.ident)[0]['automatic_retry'])
        with self.assertRaises(Invalid):
            self.jobs.intent(self.ident, expected_revision=self.store.read(self.ident)['revision'],
                             brief_id='image1', provider='gemini', request_id='request2')
        self.assertEqual(self.calls, ['request1'])

    def test_cancel_during_provider_prevents_late_asset_adoption(self):
        self.intent()
        def cancel(attempt_id, brief):
            current = self.store.read(self.ident)
            self.jobs.cancel(self.ident, attempt_id, expected_revision=current['revision'])
            folder = self.store._project(self.ident) / 'jobs' / attempt_id
            return result('gemini', 'generate', attempt_id, state='complete',
                          assets=[save_asset(folder, png(), 'image/png')])
        self.behavior = cancel
        answer = self.jobs.execute(self.ident, 'request1')
        self.assertFalse(answer['adopted'])
        current = self.store.read(self.ident)
        self.assertEqual(current['attempts'][0]['state'], 'cancelled')
        self.assertEqual(current['assets'], [])
        self.assertEqual(current['attempts'][0]['remote_cancellation'], 'unknown')

    def test_changed_inputs_prevent_result_adoption_and_keep_the_newer_content(self):
        self.intent()
        def change(attempt_id, brief):
            current = self.store.read(self.ident)
            self.store.update(self.ident, {'brief': {**current['brief'], 'title': 'Newer user content'}},
                              expected_revision=current['revision'])
            folder = self.store._project(self.ident) / 'jobs' / attempt_id
            return result('gemini', 'generate', attempt_id, state='complete',
                          assets=[save_asset(folder, png(), 'image/png')])
        self.behavior = change
        self.assertFalse(self.jobs.execute(self.ident, 'request1')['adopted'])
        self.assertEqual(self.store.read(self.ident)['brief']['title'], 'Newer user content')
        self.assertEqual(self.store.read(self.ident)['assets'], [])

    def test_stale_intent_cannot_call_provider(self):
        with self.assertRaises(Invalid):
            self.jobs.intent(self.ident, expected_revision=0, brief_id='image1', provider='gemini', request_id='request1')
        self.assertEqual(self.calls, [])
        self.assertEqual(self.store.read(self.ident)['attempts'], [])

    def test_provider_exception_remains_unknown_without_exception_text(self):
        self.intent()
        def failure(*args): raise RuntimeError('synthetic-private-key')
        self.behavior = failure
        answer = self.jobs.execute(self.ident, 'request1')
        self.assertEqual(answer['state'], 'unknown')
        current = self.store.read(self.ident)
        self.assertNotIn('synthetic-private-key', str(current))
        self.assertEqual(self.calls, ['request1'])

    def test_pending_intent_survives_content_invalidation_and_can_be_cancelled(self):
        self.intent()
        current = self.store.read(self.ident)
        changed = self.store.update(self.ident, {'brief': {**current['brief'], 'title': 'Changed story'}}, expected_revision=current['revision'])
        self.assertEqual(changed['attempts'], [])
        recovered = Jobs(self.store, {}).recovery(self.ident)
        self.assertEqual(recovered[0]['state'], 'unknown')
        cancelled = self.jobs.cancel(self.ident, 'request1', expected_revision=changed['revision'])
        self.assertEqual(self.jobs.recovery(self.ident), [])
        self.assertEqual(cancelled['brief']['title'], 'Changed story')
        self.assertEqual(self.calls, [])

    def test_http_style_duplicate_intent_lookup_cannot_repeat_provider(self):
        from runner.api import action
        from runner.engine import Engine
        engine = Engine(self.store, adapters=self.jobs.adapters)
        sent = {'action': 'image-start', 'id': self.ident, 'expected_revision': 1,
                'brief_id': 'image1', 'provider': 'gemini', 'request_id': 'request1'}
        self.assertEqual(action(engine, sent)['state'], 'complete')
        self.assertEqual(action(engine, sent)['state'], 'existing')
        self.assertEqual(self.calls, ['request1'])
