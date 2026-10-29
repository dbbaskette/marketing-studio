"""Offline raw author responses across artwork, inspection and revision boundaries."""
from copy import deepcopy
import json
from pathlib import Path
from unittest import mock

from helpers import Isolated, visual_answer
from test_desk_engine import setup_desk, fake_renderer
from runner import image_brief, scene, stories
from runner.author import Author
from runner.contracts import Invalid
from runner.images.base import result, save_asset


def direction(project):
    return {'style': 'Coherent flat explanatory shapes.', 'reading_order': 'Restarting instance, then serving instances.',
            'acceptance': 'Correct relationships with clear label regions.', 'reference_assets': [],
            'objects': [{'id': 'instances', 'region_id': project['scene']['art_regions'][0]['id'], 'count': 3,
                         'description': 'Three illustrative instances.', 'relationships': 'One restarts; two serve.',
                         'preserve': 'Keep exact labels in the compositor.'}]}


class AuthoringContractTests(Isolated):
    def setUp(self):
        super().setUp(); setup_desk(self)

    def illustrated(self):
        proposal = deepcopy(self.proposal)
        proposal['blocks'][0].update(illustration=True, illustration_role='Show restarting and serving instances.')
        p = stories.adopt(self.store, self.ident, [proposal], expected_revision=self.project['revision'])
        return stories.select(self.store, self.ident, 'story1', expected_revision=p['revision'])

    def test_raw_art_direction_and_inspection_use_owned_response_schemas(self):
        p = self.illustrated()
        calls = []
        def run(command, prompt, folder, timeout):
            shape = json.loads(Path(command[command.index('--output-schema') + 1]).read_text())
            self.assertFalse(shape['additionalProperties'])
            self.assertEqual(command[command.index('-m') + 1], 'synthetic-model')
            current = self.store.read(self.ident)
            if 'objects' in shape['properties']:
                calls.append('art direction')
                self.assertEqual(shape['properties']['objects']['items']['properties']['region_id']['enum'],
                                 [r['id'] for r in current['scene']['art_regions']])
                self.assertEqual(shape['properties']['reference_assets']['maxItems'], 0)
                answer = direction(current)
            else:
                calls.append('inspection')
                self.assertIn('--image', command)
                regions = shape['properties']['observations']['items']['properties']['region_id']['enum']
                self.assertIn('page', regions); self.assertIn('artwork_layer', regions)
                answer = visual_answer()
            return {'state': 'complete', 'returncode': 0, 'events': json.dumps(
                {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': json.dumps(answer)}})}
        class Adapter:
            def __init__(self, folder): self.folder = folder
            def generate(self, *, attempt_id, brief):
                destination = self.folder / 'synthetic-page'
                fake_renderer('<svg/>', preset='digital', fonts=['Arial'], executable=None, destination=destination)
                return result('gemini', 'generate', attempt_id, state='complete', assets=[
                    save_asset(self.folder, (destination / 'page.png').read_bytes(), 'image/png')])
        self.engine.assistant = Author({'agent': 'codex', 'model': 'synthetic-model'}, run=run)
        self.engine.adapters = {'gemini': Adapter}; self.engine.configuration = {'image_provider': 'gemini'}
        self.engine.build(self.ident, expected_revision=p['revision'], request_id='synthetic_build')
        p = self.store.read(self.ident)
        self.assertIsNone(p['approval'])
        review = self.engine.inspect_images(self.ident, expected_revision=p['revision'])
        self.assertEqual(review['status'], 'passed')
        p = self.engine.check(self.ident, expected_revision=p['revision'])
        self.assertTrue(all(c['status'] == 'passed' for c in p['checks']), p['checks'])
        self.engine.approve(self.ident, expected_revision=p['revision'])
        self.assertEqual(calls, ['art direction', 'inspection'])

    def test_malformed_art_and_inspection_references_are_safe_validation_failures(self):
        p = self.illustrated()
        p = scene.adopt(self.store, self.ident, expected_revision=p['revision'])
        for field in ('region_id', 'count', 'relationships'):
            for value in (None, [], {}, True):
                answer = direction(p); answer['objects'][0][field] = value
                with self.assertRaises(Invalid): image_brief.make(p, answer)
        for references in ([{}], [[]], None):
            answer = direction(p); answer['reference_assets'] = references
            with self.assertRaises(Invalid): image_brief.make(p, answer)
        self.engine.preview(self.ident, expected_revision=p['revision'])
        assistant = mock.Mock(); self.engine.assistant = assistant
        for field in ('kind', 'region_id'):
            for value in (None, [], {}):
                answer = visual_answer(); answer['observations'][0][field] = value
                assistant.inspect_images.return_value = answer
                with self.assertRaises(Invalid): self.engine.inspect_images(self.ident, expected_revision=p['revision'])
        for value in (None, [], {}):
            answer = visual_answer(); answer['findings'] = [{'region_id': value, 'blocking': True, 'message': 'Synthetic', 'correction': 'Synthetic'}]
            assistant.inspect_images.return_value = answer
            with self.assertRaises(Invalid): self.engine.inspect_images(self.ident, expected_revision=p['revision'])
        self.assertEqual(self.store.read(self.ident), p)

    def test_malformed_scoped_story_revisions_leave_the_page_unchanged(self):
        assistant = mock.Mock(); self.engine.assistant = assistant
        for blocks in (None, 'words', [None], [{}], [{'id': []}]):
            answer = deepcopy(self.proposal); answer['blocks'] = blocks
            assistant.revise_story.return_value = answer
            with self.assertRaises(Invalid):
                self.engine.revise_story(self.ident, 'story1', 'b1', 'Shorten this block.', expected_revision=self.project['revision'])
        self.assertEqual(self.store.read(self.ident), self.project)

    def test_pages_without_planned_art_do_not_start_art_direction(self):
        assistant = mock.Mock(); self.engine.assistant = assistant
        with self.assertRaisesRegex(Invalid, 'needs no artwork'):
            self.engine.prepare_art(self.ident, expected_revision=self.project['revision'])
        assistant.art_direction.assert_not_called()
        self.assertEqual(self.store.read(self.ident), self.project)
