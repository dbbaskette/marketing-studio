"""Complete offline author-to-approval journeys; rendering/provider seams are explicit."""
from copy import deepcopy
import json
from pathlib import Path
import struct
import zlib
from unittest import mock

from helpers import Isolated, visual_answer
from test_composition import contract
from runner import brand, evidence, exports, history, scene, sources, stories
from runner.contracts import Invalid, basis, digest
from runner.engine import Engine
from runner.render import dimensions
from runner.workspace import Store


def fake_renderer(svg, *, preset, fonts, executable, destination):
    """Produce structurally valid fixtures, not visual-quality evidence."""
    d = dimensions(preset)
    width, height = d['width_px'], d['height_px']
    def chunk(kind, raw):
        return struct.pack('>I', len(raw)) + kind + raw + struct.pack('>I', zlib.crc32(kind + raw))
    png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress((b'\x00' + b'\xff\xff\xff\xff' * width) * height)) + chunk(b'IEND', b'')
    destination.mkdir()
    (destination / 'page.png').write_bytes(png)
    (destination / 'page.pdf').write_bytes(('%PDF-1.4\n1 0 obj << /Type /Page /MediaBox [0 0 '
        + str(d['width_pt']) + ' ' + str(d['height_pt']) + '] >> endobj\n%%EOF').encode())
    (destination / 'page.svg').write_text(svg)
    (destination / 'measurements.json').write_text(json.dumps({'complete': True, 'overflow': [],
        'missing_fonts': [], 'invalid_assets': [], 'boxes': []}))
    return {'pdf_pages': 1}


class DeskEngineTests(Isolated):
    def setUp(self):
        super().setUp()
        self.store = Store.setup(self.workspace, data=self.data)
        self.project = self.store.create('Restart one instance', preset='digital')
        self.ident = self.project['id']
        self.project = sources.capture(self.store, self.ident, b'One instance restarts while the others serve.', expected_revision=0)
        source = self.project['sources'][0]
        quote = sources.read(self.store, self.project, source)
        fact = {'id': 'f1', 'statement': quote, 'value': quote, 'unit': '', 'status': 'supplied',
                'evidence': [{'source_id': source['id'], 'start': 0, 'end': len(quote), 'quote': quote}]}
        self.project = evidence.adopt(self.store, self.ident, [fact], expected_revision=1)
        self.project = brand.adopt(self.store, self.ident, contract(), expected_revision=2)
        self.proposal = {'id': 'story1', 'headline': 'Restart one instance', 'takeaway': 'Keep the other instances serving.',
                         'rationale': 'Explain a conceptual relationship.', 'qualifications': [], 'omissions': [],
                         'blocks': [{'id': 'b1', 'kind': 'concept', 'title': 'One at a time',
                                     'text': 'The remaining instances continue serving requests.', 'fact_ids': ['f1'],
                                     'required_ids': [], 'illustration': False, 'illustration_role': ''}]}
        self.project = stories.adopt(self.store, self.ident, [self.proposal], expected_revision=3)
        self.project = stories.select(self.store, self.ident, 'story1', expected_revision=4)
        self.project = scene.adopt(self.store, self.ident, expected_revision=5)
        self.renderer = mock.Mock(side_effect=fake_renderer)
        self.engine = Engine(self.store, renderer=self.renderer)

    def current(self): return self.store.read(self.ident)

    def review_and_approve(self):
        manifest = self.engine.preview(self.ident, expected_revision=self.current()['revision'])
        self.engine.manual_review(self.ident, manifest['id'], ['Inspected the actual page, reading order and conceptual relationships.'],
                                   expected_revision=self.current()['revision'])
        self.engine.check(self.ident, expected_revision=self.current()['revision'])
        return self.engine.approve(self.ident, expected_revision=self.current()['revision'])

    def test_final_approval_requires_actual_preview_and_explicit_visual_review(self):
        checked = self.engine.check(self.ident, expected_revision=self.current()['revision'])
        statuses = {c['kind']: c['status'] for c in checked['checks']}
        self.assertEqual(statuses['layout'], 'incomplete')
        self.assertEqual(statuses['visual'], 'incomplete')
        with self.assertRaises(Invalid): self.engine.approve(self.ident, expected_revision=checked['revision'])
        approved = self.review_and_approve()
        self.assertEqual(approved['approval']['basis'], basis(approved))
        self.assertEqual(approved['approval']['revision'], approved['revision'])
        self.assertTrue(all(c['status'] == 'passed' for c in approved['checks']))

    def test_approved_delivery_is_immutable_retryable_and_contains_all_four_formats(self):
        self.review_and_approve()
        before = deepcopy(self.current())
        self.renderer.reset_mock()
        manifest = self.engine.preview(self.ident, expected_revision=before['revision'], draft=False)
        self.assertFalse(manifest['draft'])
        self.assertEqual({f['format'] for f in manifest['files']}, {'png', 'pdf', 'svg', 'text'})
        self.assertNotIn('DRAFT', exports.read(self.store, self.ident, manifest['id'], 'text')[1].decode())
        self.assertEqual(self.engine.preview(self.ident, expected_revision=before['revision'], draft=False), manifest)
        self.renderer.assert_called_once()
        self.assertEqual(self.current(), before, 'Export must not mutate or move the approved content revision')
        self.assertEqual(manifest['scene_digest'], digest(before['scene']))

    def test_generation_success_does_not_approve_and_draft_delivery_is_marked(self):
        with self.assertRaises(Invalid): self.engine.preview(self.ident, expected_revision=6, draft=False)
        manifest = self.engine.preview(self.ident, expected_revision=6)
        self.assertTrue(manifest['draft'])
        for kind in ('svg', 'text'):
            self.assertIn('DRAFT', exports.read(self.store, self.ident, manifest['id'], kind)[1].decode())
        self.assertIsNone(self.current()['approval'])

    def test_focused_text_edit_preserves_unaffected_scene_and_invalidates_approval(self):
        approved = self.review_and_approve()
        before = deepcopy(approved['scene']['elements'])
        changed = self.engine.edit_text(self.ident, 'b1_heading', 'One instance', expected_revision=approved['revision'])
        self.assertIsNone(changed['approval'])
        self.assertEqual(changed['checks'], [])
        self.assertEqual([e for e in before if e['id'] != 'b1_heading'],
                         [e for e in changed['scene']['elements'] if e['id'] != 'b1_heading'])
        with self.assertRaises(Invalid): self.engine.edit_text(self.ident, 'b1_heading', 'Stale', expected_revision=approved['revision'])
        with self.assertRaises(Invalid): self.engine.edit_text(self.ident, 'b1_heading', 'Very long text ' * 200, expected_revision=changed['revision'])
        self.assertEqual(self.current(), changed)

    def test_restore_creates_new_revision_without_approval_and_retains_old_delivery(self):
        approved = self.review_and_approve()
        manifest = self.engine.preview(self.ident, expected_revision=approved['revision'], draft=False)
        changed = self.engine.edit_text(self.ident, 'b1_heading', 'One instance', expected_revision=approved['revision'])
        restored = history.restore(self.store, self.ident, approved['revision'], expected_revision=changed['revision'])
        self.assertGreater(restored['revision'], changed['revision'])
        self.assertEqual(restored['scene'], approved['scene'])
        self.assertIsNone(restored['approval'])
        self.assertEqual(restored['checks'], [])
        self.assertEqual(exports.read(self.store, self.ident, manifest['id'], 'png')[0], 'image/png')

    def test_failed_render_and_wrong_dimensions_preserve_last_good_revision(self):
        manifest = self.engine.preview(self.ident, expected_revision=6)
        self.engine.renderer = mock.Mock(side_effect=ValueError('Renderer unavailable'))
        changed = self.engine.edit_text(self.ident, 'b1_heading', 'One instance', expected_revision=6)
        with self.assertRaises(ValueError): self.engine.preview(self.ident, expected_revision=changed['revision'])
        self.assertEqual(self.current(), changed)
        self.assertEqual(exports.read(self.store, self.ident, manifest['id'], 'png')[0], 'image/png')
        self.assertEqual(len(self.engine.deliveries(self.ident)), 1)

    def test_open_inspect_and_stale_approval_start_no_provider_or_assistant_work(self):
        self.engine.assistant = mock.Mock(side_effect=AssertionError('No assistant on inspection'))
        self.engine.adapters = {'codex': mock.Mock(side_effect=AssertionError('No provider on inspection'))}
        before = deepcopy(self.current())
        self.engine.inspect(self.ident)
        self.assertEqual(self.current(), before)
        with self.assertRaises(Invalid): self.engine.approve(self.ident, expected_revision=0)
        self.engine.assistant.assert_not_called()
        self.engine.adapters['codex'].assert_not_called()

    def test_build_reuses_saved_page_and_inspection_is_bound_to_actual_png(self):
        self.engine.build(self.ident, expected_revision=6, request_id='build1')
        self.renderer.assert_called_once()
        self.engine.build(self.ident, expected_revision=6, request_id='build2')
        self.renderer.assert_called_once()
        assistant = mock.Mock()
        assistant.inspect_images.return_value = visual_answer()
        self.engine.assistant = assistant
        review = self.engine.inspect_images(self.ident, expected_revision=6)
        self.assertEqual(review['status'], 'passed')
        self.assertEqual(assistant.inspect_images.call_args.args[1][0][:8], b'\x89PNG\r\n\x1a\n')
        checked = self.engine.check(self.ident, expected_revision=6)
        self.assertEqual(next(c for c in checked['checks'] if c['kind'] == 'visual')['status'], 'passed')
        changed = self.engine.edit_text(self.ident, 'b1_heading', 'One instance', expected_revision=checked['revision'])
        checked = self.engine.check(self.ident, expected_revision=changed['revision'])
        self.assertEqual(next(c for c in checked['checks'] if c['kind'] == 'visual')['status'], 'incomplete')

    def test_invalid_or_unlocated_image_inspection_is_not_adopted(self):
        self.engine.preview(self.ident, expected_revision=6)
        self.engine.assistant = mock.Mock()
        bad = visual_answer()
        bad['findings'] = [{'region_id': 'invented_region', 'blocking': True, 'message': 'Wrong', 'correction': 'Change it'}]
        self.engine.assistant.inspect_images.return_value = bad
        with self.assertRaises(Invalid): self.engine.inspect_images(self.ident, expected_revision=6)
        self.assertIsNone(self.engine.inspect(self.ident)['visual_review'])
        self.assertEqual(self.current()['revision'], 6)

    def test_shared_repair_budget_survives_history_restore_and_restarts(self):
        from runner.visual_review import consume_repair
        consume_repair(self.store, self.ident, expected_revision=6, kind='layout')
        consume_repair(self.store, self.ident, expected_revision=6, kind='image')
        restored = history.restore(self.store, self.ident, 5, expected_revision=6)
        with self.assertRaises(Invalid):
            consume_repair(self.store, self.ident, expected_revision=restored['revision'], kind='layout')

    def test_named_story_revision_refuses_changes_outside_scope(self):
        self.engine.assistant = mock.Mock()
        changed = deepcopy(self.proposal)
        changed['headline'] = 'Unexpected headline'
        changed['blocks'][0]['text'] = 'Another supplied explanation.'
        self.engine.assistant.revise_story.return_value = changed
        with self.assertRaises(Invalid): self.engine.revise_story(self.ident, 'story1', 'b1', 'Shorten this block', expected_revision=6)
        self.assertEqual(self.current()['revision'], 6)
        changed['headline'] = self.proposal['headline']
        self.engine.assistant.revise_story.return_value = changed
        updated = self.engine.revise_story(self.ident, 'story1', 'b1', 'Shorten this block', expected_revision=6)
        self.assertIsNone(updated['scene'])
        self.assertIsNone(updated['selected_story'])
        self.assertEqual(updated['stories'][0]['blocks'][0]['text'], 'Another supplied explanation.')

    def test_illustrated_build_and_reference_revision_never_approve_or_repeat_generation(self):
        from graphics_fixtures import png
        from runner.images.base import result, save_asset
        proposal = deepcopy(self.proposal)
        proposal['blocks'][0].update(illustration=True, illustration_role='Show one restarting instance beside the serving instances.')
        current = self.current()
        current = stories.adopt(self.store, self.ident, [proposal], expected_revision=current['revision'])
        current = stories.select(self.store, self.ident, 'story1', expected_revision=current['revision'])
        calls = []
        class Adapter:
            def __init__(self, folder): self.folder = folder
            def generate(self, *, attempt_id, brief):
                calls.append(('generate', brief))
                return result('gemini', 'generate', attempt_id, state='complete', assets=[save_asset(self.folder, png(), 'image/png')])
            def edit(self, *, attempt_id, brief, reference_assets):
                calls.append(('edit', reference_assets))
                return result('gemini', 'edit', attempt_id, state='complete', assets=[save_asset(self.folder, png(), 'image/png')])
        assistant = mock.Mock()
        def direction(project):
            region = project['scene']['art_regions'][0]['id']
            return {'style': 'Coherent flat explanatory shapes.', 'reading_order': 'One restarting instance, then serving instances.',
                    'acceptance': 'Exact counts, correct relationships and clear label regions.',
                    'objects': [{'id': 'instances', 'region_id': region, 'count': 3,
                                 'description': 'Three illustrative service instances.', 'relationships': 'One restarts; two continue serving.',
                                 'preserve': 'All labels and chart regions stay empty.'}]}
        assistant.art_direction.side_effect = direction
        self.engine.assistant = assistant
        self.engine.adapters = {'gemini': Adapter}
        self.engine.configuration = {'image_provider': 'gemini'}
        self.engine.build(self.ident, expected_revision=current['revision'], request_id='build1')
        self.assertIsNone(self.current()['approval'])
        self.assertTrue(any(e['kind'] == 'artwork' for e in self.current()['scene']['elements']))
        self.engine.build(self.ident, expected_revision=self.current()['revision'], request_id='build2')
        self.assertEqual(len(calls), 1)
        self.engine.revise_art(self.ident, 'Separate the three instances.', 'Keep the counts and empty labels.',
                               expected_revision=self.current()['revision'], request_id='edit1')
        self.assertEqual([c[0] for c in calls], ['generate', 'edit'])
        self.assertEqual(calls[-1][1][0]['data'], png())
        self.assertEqual(len(self.engine.inspect(self.ident)['image_history']), 2)
        self.assertIsNone(self.current()['approval'])

    def test_an_unbacked_numeric_copy_edit_blocks_factual_approval(self):
        current = self.engine.edit_text(self.ident, 'b1_heading', '99 instances', expected_revision=6)
        self.engine.preview(self.ident, expected_revision=current['revision'])
        self.engine.manual_review(self.ident, self.engine.deliveries(self.ident)[0]['id'], ['Inspected the actual fixture.'], expected_revision=current['revision'])
        checked = self.engine.check(self.ident, expected_revision=current['revision'])
        self.assertEqual(next(c for c in checked['checks'] if c['kind'] == 'facts')['status'], 'failed')

    def test_parallel_build_is_refused_before_renderer_or_assistant_work(self):
        from runner.workspace import file_lock
        with file_lock(self.store._project(self.ident) / 'jobs/build.lock'):
            with self.assertRaises(Invalid): self.engine.build(self.ident, expected_revision=6, request_id='second_build')
        self.renderer.assert_not_called()
        self.assertEqual(self.current()['revision'], 6)

    def test_final_delivery_wins_a_same_revision_draft_but_old_approval_is_labeled(self):
        approved = self.review_and_approve()
        self.engine.preview(self.ident, expected_revision=approved['revision'], draft=True)
        self.engine.preview(self.ident, expected_revision=approved['revision'], draft=False)
        latest = self.engine.deliveries(self.ident)[0]
        self.assertFalse(latest['draft'])
        self.assertTrue(latest['approved_current'])
        self.engine.check(self.ident, expected_revision=approved['revision'])
        old = self.engine.deliveries(self.ident)[0]
        self.assertTrue(old['current'], 'The actual scene/content remains the same')
        self.assertFalse(old['approved_current'], 'Earlier final files must not claim current exact-revision approval')

    def test_late_assistant_inspection_cannot_replace_a_newer_manual_review(self):
        delivery = self.engine.preview(self.ident, expected_revision=6)
        assistant = mock.Mock()
        def inspect(context, images):
            self.engine.manual_review(self.ident, delivery['id'], ['A newer manual decision on the actual page.'], expected_revision=6)
            return visual_answer()
        assistant.inspect_images.side_effect = inspect
        self.engine.assistant = assistant
        with self.assertRaises(Invalid): self.engine.inspect_images(self.ident, expected_revision=6)
        self.assertEqual(self.engine.inspect(self.ident)['visual_review']['by'], 'user')

    def failing_review(self):
        answer = visual_answer()
        answer['findings'] = [{'region_id': 'page', 'blocking': True,
                               'message': 'The latest inspection found a misleading relationship.',
                               'correction': 'Correct the relationship before approval.'}]
        self.engine.assistant = mock.Mock()
        self.engine.assistant.inspect_images.return_value = answer
        return self.engine.inspect_images(self.ident, expected_revision=self.current()['revision'])

    def test_new_review_supersedes_checked_or_approved_decision_and_saved_delivery(self):
        approved = self.review_and_approve()
        final = self.engine.preview(self.ident, expected_revision=approved['revision'], draft=False)
        self.failing_review()
        with self.assertRaisesRegex(Invalid, 'visual review'):
            self.engine.approve(self.ident, expected_revision=approved['revision'])
        with self.assertRaisesRegex(Invalid, 'visual review'):
            self.engine.preview(self.ident, expected_revision=approved['revision'], draft=False)
        self.assertFalse(next(d for d in self.engine.deliveries(self.ident) if d['id'] == final['id'])['approved_current'])
        self.assertEqual(exports.read(self.store, self.ident, final['id'], 'png')[0], 'image/png',
                         'Keep the earlier immutable delivery available as history')
        self.engine.manual_review(self.ident, final['id'], ['Inspected the disputed relationship myself.'],
                                  expected_revision=approved['revision'])
        with self.assertRaisesRegex(Invalid, 'visual review'):
            self.engine.approve(self.ident, expected_revision=approved['revision'])
        checked = self.engine.check(self.ident, expected_revision=approved['revision'])
        self.engine.approve(self.ident, expected_revision=checked['revision'])

    def test_review_changed_during_final_render_cannot_land_a_delivery(self):
        approved = self.review_and_approve()
        def review_during_render(*args, **kwargs):
            self.failing_review()
            return fake_renderer(*args, **kwargs)
        self.engine.renderer = review_during_render
        with self.assertRaisesRegex(Invalid, 'visual review changed during export'):
            self.engine.preview(self.ident, expected_revision=approved['revision'], draft=False)
        self.assertTrue(all(d['draft'] for d in self.engine.deliveries(self.ident)))
