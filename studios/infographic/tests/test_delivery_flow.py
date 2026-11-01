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
        page = self.current()['revision']    # the revision the person reviews
        drafted = self.stage()
        self.assertEqual(drafted['stage'], 'review')
        self.assertEqual(drafted['downloads'], 'Draft files for revision ' + str(page) + ', marked as drafts.')
        self.engine.manual_review(self.ident, manifest['id'], REVIEW, expected_revision=self.current()['revision'])
        self.assertEqual(self.stage()['stage'], 'check', 'A recorded review still needs its checks.')
        self.engine.check(self.ident, expected_revision=self.current()['revision'])
        ready = self.stage()
        self.assertEqual(ready['stage'], 'approve')
        # Checks saved a revision of their own, but the page is the one the person reviewed.
        self.assertEqual(self.current()['revision'], page + 1)
        self.assertEqual((ready['action'], ready['revision']), ('Approve revision ' + str(page), page))
        self.assertTrue(ready['needs'].startswith('Approve revision ' + str(page) + '.'))
        self.assertEqual(ready['downloads'], drafted['downloads'])
        done = self.engine.approve_and_export(self.ident, expected_revision=self.current()['revision'])
        self.assertEqual((done['revision'], done['page_revision']), (page + 2, page))
        delivered = self.stage()
        self.assertEqual((delivered['stage'], [s['state'] for s in delivered['steps']]),
                         ('deliver', ['done', 'done', 'done', 'done']))
        self.assertEqual(delivered['downloads'], 'Approved files for revision ' + str(page)
                         + ': PNG, PDF, SVG and text.')
        self.assertIn('You approved revision ' + str(page) + '.', delivered['complete'])
        desk = self.engine.inspect(self.ident)
        self.assertEqual(desk['page_revision'], page)
        self.assertEqual(desk['approval_words'], 'You approved revision ' + str(page) + '.')
        self.assertEqual({d['page_revision'] for d in desk['deliveries']}, {page}, 'Draft and approved files name one revision')
        self.assertEqual((desk['library']['kept']['revision'], desk['library']['kept']['page_revision']),
                         (done['revision'], page), 'The kept entry keeps the saved revision and names the page')
        self.assertEqual([e['page_revision'] for e in desk['history'][:3]], [page] * 3)
        edited = self.engine.edit_text(self.ident, 'b1_heading', 'One instance', expected_revision=done['revision'])
        after = self.stage()
        self.assertEqual(after['stage'], 'preview')
        self.assertEqual(after['revision'], edited['revision'], 'An edit is a new page revision')
        self.assertIn('Earlier approved files for revision ' + str(page), after['downloads'])
        self.assertIsNone(edited['approval'])

    def test_checking_again_after_approval_says_the_approval_was_withdrawn(self):
        self.reviewed()
        page = self.current()['revision'] - 1
        done = self.engine.approve_and_export(self.ident, expected_revision=self.current()['revision'])
        self.engine.check(self.ident, expected_revision=done['revision'])
        again = self.stage()
        self.assertIsNone(self.current()['approval'])
        self.assertEqual((again['stage'], again['revision']), ('approve', page))
        self.assertEqual(again['downloads'], 'The files approved earlier for revision ' + str(page)
                         + ' stay unchanged in Saved files. A new review withdrew the approval until you approve again.')

    def test_needs_you_always_names_the_toolbar_action(self):
        manifest = self.engine.preview(self.ident, expected_revision=self.current()['revision'])
        seen = []
        def look():
            found = self.stage()
            self.assertIn(found['action'], found['needs'], found['stage'])
            seen.append(found['stage'])
        look()
        self.engine.manual_review(self.ident, manifest['id'], REVIEW, expected_revision=self.current()['revision'])
        look()
        self.engine.check(self.ident, expected_revision=self.current()['revision'])
        look()
        self.engine.approve(self.ident, expected_revision=self.current()['revision'])
        look()
        self.engine.preview(self.ident, expected_revision=self.current()['revision'], draft=False)
        look()
        self.engine.edit_text(self.ident, 'b1_heading', 'One instance', expected_revision=self.current()['revision'])
        look()
        self.assertEqual(seen, ['review', 'check', 'approve', 'export', 'deliver', 'preview'])
        empty = progress.roadmap(self.store.create('Synthetic empty'), [])
        self.assertIn(empty['action'], empty['needs'])

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
        self.assertTrue(waiting['needs'].startswith('Prepare approved files'))
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

    def test_reconciling_a_saved_request_keeps_its_own_folder_and_account(self):
        from runner import settings
        settings.save({'google_folder': 'default_folder_1', 'google_account': 'default@example.invalid'},
                      expected=settings.snapshot()['native_revision'])
        self.reviewed()
        done = self.engine.approve_and_export(self.ident, expected_revision=self.current()['revision'])
        client = mock.Mock()
        client.create_document.side_effect = GoogleError('Synthetic timeout', uncertain=True)
        first = google_delivery.execute(self.store, self.ident, expected_revision=done['revision'],
                                        export_id=done['export']['id'], request_id='chosen_folder_request',
                                        account='editor@example.invalid', folder='chosen_folder_1', client=client)
        self.assertEqual(first['state'], 'unknown')
        intent = google_delivery.listing(self.store, self.ident)[0]
        self.assertEqual((intent['folder'], intent['account']), ('chosen_folder_1', 'editor@example.invalid'))
        client.find_delivery.return_value = [{'id': 'recovered_doc', 'mimeType': google_delivery.DOC_MIME, 'appProperties': {
            'infographic_request': 'chosen_folder_request', 'infographic_payload': intent['payload_sha256']}}]
        # The receipt's check names only the request: the saved destination is used, not the defaults.
        checked = google_delivery.execute(self.store, self.ident, expected_revision=done['revision'],
                                          export_id=done['export']['id'], request_id='chosen_folder_request',
                                          reconcile=True, client=client)
        self.assertEqual((checked['state'], checked['document_id']), ('delivered', 'recovered_doc'))
        client.create_document.assert_called_once()
        with self.assertRaisesRegex(Invalid, 'different destination'):
            google_delivery.execute(self.store, self.ident, expected_revision=done['revision'],
                                    export_id=done['export']['id'], request_id='chosen_folder_request',
                                    folder='another_folder_1', reconcile=True, client=client)

    def test_approve_and_review_run_through_the_configured_server_engine(self):
        import json
        from runner import server
        configured = mock.Mock(side_effect=lambda store: Engine(store, renderer=desk.fake_renderer))
        page = server.Page(0, self.store)
        manifest = self.engine.preview(self.ident, expected_revision=self.current()['revision'])
        with mock.patch.object(server.api, 'engine', configured):
            status, _, raw = page.write('/api/action', {
                'action': 'review', 'id': self.ident, 'expected_revision': self.current()['revision'],
                'export_id': manifest['id'], 'observations': REVIEW, 'then_check': True})
            self.assertEqual(status, 200)
            self.assertEqual(page.activity.snapshot(self.ident)['state'], 'complete')
            status, _, raw = page.write('/api/action', {
                'action': 'approve', 'id': self.ident, 'expected_revision': self.current()['revision'],
                'then_export': True})
        result = json.loads(raw)['result']
        self.assertEqual(status, 200)
        self.assertEqual((result['approved'], result['problem']), (True, None))
        self.assertEqual([call.args[0] for call in configured.call_args_list], [self.store, self.store])
        self.assertTrue(any(d['approved_current'] for d in self.engine.deliveries(self.ident)))
