"""Review to approved delivery: one route, combined local steps and honest partial outcomes.

The renderer is the structural fake and Google is a mock client; nothing reaches a provider.
"""
from unittest import mock

from helpers import Isolated
import test_desk_engine as desk
from runner import api, exports, google_delivery, progress, visual_review
from runner.contracts import Invalid
from runner.engine import Engine
from studio_core.google_api import GoogleError

REVIEW = ['Inspected the actual page, its reading order and conceptual relationships.']


class DeliveryFlowTests(Isolated):
    current = desk.DeskEngineTests.current

    def setUp(self):
        super().setUp()
        desk.setup_desk(self)

    def stage(self):
        return self.engine.inspect(self.ident)['roadmap']

    def reviewed(self):
        manifest = self.engine.preview(self.ident, expected_revision=self.current()['revision'])
        return self.engine.check_after(self.ident, self.engine.manual_review(
            self.ident, manifest['id'], REVIEW, expected_revision=self.current()['revision']),
            expected_revision=self.current()['revision'])

    def test_one_route_says_what_is_complete_needed_and_downloadable_at_each_state(self):
        fresh = self.store.create('Synthetic empty brief')
        empty = progress.roadmap(fresh, [])
        self.assertEqual((empty['stage'], empty['steps'][0]['state']), ('story', 'current'))
        self.assertEqual(empty['downloads'], 'Nothing yet for the current revision.')
        built = self.stage()
        self.assertEqual(built['stage'], 'preview')
        self.assertEqual([s['state'] for s in built['steps']], ['done', 'current', 'upcoming', 'upcoming'])
        manifest = self.engine.preview(self.ident, expected_revision=self.current()['revision'])
        drafted = self.stage()
        self.assertEqual(drafted['stage'], 'review')
        self.assertIn('Draft files for revision', drafted['downloads'])
        self.engine.manual_review(self.ident, manifest['id'], REVIEW, expected_revision=self.current()['revision'])
        self.assertEqual(self.stage()['stage'], 'check', 'A recorded review still needs its checks.')
        self.engine.check(self.ident, expected_revision=self.current()['revision'])
        ready = self.stage()
        self.assertEqual(ready['stage'], 'approve')
        self.assertTrue(ready['needs'].startswith('Approve revision ' + str(self.current()['revision'])))
        done = self.engine.approve_and_export(self.ident, expected_revision=self.current()['revision'])
        delivered = self.stage()
        self.assertEqual((delivered['stage'], [s['state'] for s in delivered['steps']]),
                         ('deliver', ['done', 'done', 'done', 'done']))
        self.assertEqual(delivered['downloads'], 'Approved files for revision ' + str(done['revision'])
                         + ': PNG, PDF, SVG and text.')
        edited = self.engine.edit_text(self.ident, 'b1_heading', 'One instance', expected_revision=done['revision'])
        after = self.stage()
        self.assertEqual(after['stage'], 'preview')
        self.assertIn('Earlier approved files for revision ' + str(done['revision']), after['downloads'])
        self.assertIsNone(edited['approval'])

    def test_recording_a_review_runs_the_checks_in_the_same_action_without_approving(self):
        manifest = self.engine.preview(self.ident, expected_revision=self.current()['revision'])
        before = self.current()['revision']
        result = api.action(self.engine, {'action': 'review', 'id': self.ident, 'expected_revision': before,
                                          'export_id': manifest['id'], 'observations': REVIEW, 'then_check': True})
        self.assertEqual(result['revision'], before + 1)
        self.assertTrue(all(c['status'] == 'passed' for c in self.current()['checks']))
        self.assertIsNone(self.current()['approval'])
        with self.assertRaises(Invalid):
            api.action(self.engine, {'action': 'review', 'id': self.ident, 'expected_revision': result['revision'],
                                     'export_id': manifest['id'], 'observations': REVIEW, 'then_check': 'yes'})

    def test_checks_refused_after_a_review_keep_the_review_and_approve_nothing(self):
        manifest = self.engine.preview(self.ident, expected_revision=self.current()['revision'])
        stale = self.current()['revision']
        review = self.engine.manual_review(self.ident, manifest['id'], REVIEW, expected_revision=stale)
        # Someone changes the page before the checks run: they are refused, not run on old content.
        self.engine.edit_text(self.ident, 'headline', 'Keep going', expected_revision=stale)
        with self.assertRaises(Invalid):
            self.engine.check_after(self.ident, review, expected_revision=stale)
        saved = list((self.store._project(self.ident) / 'jobs').glob('visual_*/review.json'))
        self.assertEqual(len(saved), 1, 'The recorded review is kept.')
        self.assertIsNone(visual_review.latest(self.store, self.current()), 'It does not count for changed content.')
        self.assertIsNone(self.current()['approval'])
        with self.assertRaises(Invalid):
            self.engine.approve_and_export(self.ident, expected_revision=self.current()['revision'])
        self.assertIsNone(self.current()['approval'])

    def test_approval_and_files_are_one_action_and_a_stale_revision_approves_nothing(self):
        self.reviewed()
        checked = self.current()['revision']
        with self.assertRaises(Invalid):
            self.engine.approve_and_export(self.ident, expected_revision=checked - 1)
        self.assertIsNone(self.current()['approval'])
        result = api.action(self.engine, {'action': 'approve', 'id': self.ident, 'expected_revision': checked,
                                          'then_export': True})
        self.assertEqual((result['approved'], result['revision'], result['problem']), (True, checked + 1, None))
        self.assertFalse(result['export']['draft'])
        current = next(d for d in self.engine.deliveries(self.ident) if d['current'])
        self.assertTrue(current['approved_current'], 'The newest current files are the approved ones, never a draft.')

    def test_a_missing_renderer_keeps_the_approval_and_offers_a_local_retry(self):
        self.reviewed()
        bare = Engine(self.store)
        result = bare.approve_and_export(self.ident, expected_revision=self.current()['revision'])
        self.assertTrue(result['approved'])
        self.assertIsNone(result['export'])
        self.assertIn('renderer', result['problem'])
        self.assertIsNotNone(self.current()['approval'])
        self.assertFalse(any(d['approved_current'] for d in self.engine.deliveries(self.ident)))
        waiting = self.stage()
        self.assertEqual(waiting['stage'], 'export')
        self.assertTrue(waiting['needs'].startswith('Prepare the approved files'))
        self.assertIn('marked as drafts', waiting['downloads'])
        manifest = self.engine.preview(self.ident, expected_revision=self.current()['revision'], draft=False)
        self.assertFalse(manifest['draft'])
        self.assertEqual(self.stage()['stage'], 'deliver')

    def test_a_failed_render_during_export_adopts_nothing_and_keeps_the_approval(self):
        self.reviewed()
        broken = Engine(self.store, renderer=mock.Mock(side_effect=RuntimeError('synthetic renderer crash')))
        result = broken.approve_and_export(self.ident, expected_revision=self.current()['revision'])
        self.assertEqual((result['approved'], result['export']), (True, None))
        self.assertNotIn('synthetic renderer crash', result['problem'])
        self.assertIsNotNone(self.current()['approval'])
        exported = self.store._project(self.ident) / 'exports'
        self.assertEqual([p.name for p in exported.iterdir() if p.name.startswith('.pending_')], [])
        self.assertFalse(any(d['approved_current'] for d in self.engine.deliveries(self.ident)))

    def test_uncertain_google_delivery_keeps_the_local_pdf_and_never_resends(self):
        self.reviewed()
        done = self.engine.approve_and_export(self.ident, expected_revision=self.current()['revision'])
        pdf = exports.read(self.store, self.ident, done['export']['id'], 'pdf')
        client = mock.Mock()
        client.create_document.side_effect = GoogleError('Synthetic timeout', uncertain=True)
        send = dict(expected_revision=done['revision'], export_id=done['export']['id'],
                    request_id='synthetic_receipt', account='editor@example.invalid', client=client)
        self.assertEqual(google_delivery.execute(self.store, self.ident, **send)['state'], 'unknown')
        self.assertEqual(exports.read(self.store, self.ident, done['export']['id'], 'pdf'), pdf,
                         'Retrying the PDF is a local read of unchanged approved files.')
        again = google_delivery.execute(self.store, self.ident, **send)
        self.assertEqual(again['state'], 'unknown')
        client.find_delivery.return_value = []
        checked = google_delivery.execute(self.store, self.ident, **send, reconcile=True)
        self.assertIn('Nothing was resent', checked['message'])
        client.create_document.assert_called_once()
        self.assertEqual(self.stage()['stage'], 'deliver')
