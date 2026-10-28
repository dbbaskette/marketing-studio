"""Branded scene and self-contained artwork planning, without real providers."""
from copy import deepcopy
import xml.etree.ElementTree as ET
import os
import unittest
TEST_RENDERER = os.environ.get("INFOGRAPHIC_STUDIO_TEST_RENDERER")

from helpers import Isolated
from runner import brand, evidence, image_brief, scene, sources, stories, svg
from runner.contracts import Invalid, PRESETS, digest
from runner.workspace import Store


def contract():
    return {'schema': 1, 'revision': 'synthetic-brand-v1',
            'identity': {'id': 'example', 'name': 'Example Brand', 'variant': 'light'},
            'medium': {'kind': 'blog'}, 'design': {'fontFamily': 'Arial',
                'colors': {'canvasPrimary': '#FFFFFF', 'inkPrimary': '#18212B', 'headingPrimary': '#215B85'},
                'references': {'guide': '/not-a-portable-path/guide.md'},
                'imagery': {'policy': 'Explanatory illustrations, no synthetic product screenshots.'}}}


class CompositionTests(Isolated):
    def setUp(self):
        super().setUp()
        self.store = Store.setup(self.workspace, data=self.data)
        self.project = self.store.create('Synthetic comparison')
        self.ident = self.project['id']
        self.project = sources.capture(self.store, self.ident, b'Baseline 12. Comparison 24. Unit: requests. Period: 2026-01-01. Denominator: per second. Conditions: same test. Uncertainty: not reported.', expected_revision=0)
        source = self.project['sources'][0]
        facts = []
        for key, label, value in [('f1', 'Baseline', 12), ('f2', 'Comparison', 24)]:
            quote = label + ' ' + str(value)
            start = sources.read(self.store, self.project, source).index(quote)
            facts.append({'id': key, 'statement': label, 'value': value, 'unit': 'requests',
                          'status': 'supplied', 'period': '2026-01-01', 'denominator': 'per second',
                          'conditions': 'same test', 'uncertainty': 'not reported',
                          'evidence': [{'source_id': source['id'], 'start': start, 'end': start + len(quote), 'quote': quote}]})
        self.project = evidence.adopt(self.store, self.ident, facts, expected_revision=1)
        self.project = brand.adopt(self.store, self.ident, contract(), expected_revision=2)

    def prepare(self, kind='comparison', illustration=False, preset='a4'):
        p = deepcopy(self.project)
        p['brief']['preset'] = preset
        proposal = {'id': 'story1', 'headline': 'Compare supplied measurements', 'takeaway': 'Two supplied counts.',
                    'rationale': 'Use a faithful visual explanation.', 'qualifications': [], 'omissions': [],
                    'blocks': [{'id': 'b1', 'kind': kind, 'title': 'Supplied counts', 'text': 'Baseline and comparison, under the same conditions.',
                                'fact_ids': ['f1', 'f2'], 'required_ids': [], 'illustration': illustration,
                                'illustration_role': 'Explain the conceptual relationship between the two measured stages.' if illustration else ''}]}
        p['stories'] = stories.verify(p, [proposal])
        p['selected_story'] = 'story1'
        p['scene'] = scene.plan(p)
        return p

    def test_brand_is_pinned_without_slide_geometry_private_paths_or_default_identity(self):
        pinned = self.project['brand']
        self.assertEqual(pinned['identity']['id'], 'example')
        self.assertNotIn('references', pinned)
        self.assertNotIn('/not-a-portable-path', str(pinned))
        changed = contract()
        changed['design']['colors']['headingPrimary'] = '#333333'
        self.assertNotEqual(brand.snapshot(changed)['sha256'], pinned['sha256'])
        self.assertEqual(self.project['brand']['colors']['headingPrimary'], '#215B85')
        for bad in ({}, dict(contract(), design={}), dict(contract(), revision='')):
            with self.assertRaises(Invalid): brand.snapshot(bad)

    def test_every_visual_form_at_every_preset_has_readable_editable_geometry(self):
        for kind in ('comparison', 'process', 'timeline', 'numbers', 'parts', 'concept'):
            for preset in PRESETS:
                with self.subTest(kind=kind, preset=preset):
                    p = self.prepare(kind, preset=preset)
                    d = p['scene']
                    self.assertEqual((d['width'], d['height']), (PRESETS[preset]['width'], PRESETS[preset]['height']))
                    for element in d['elements']:
                        if element['kind'] == 'text':
                            floor = (18 if element['role'] == 'source' else 24) if preset == 'digital' else (9 if element['role'] == 'source' else 12)
                            self.assertGreaterEqual(element['font_size'], floor)
                    root = ET.fromstring(svg.compose(self.store, p))
                    self.assertGreater(len(root.findall('.//{*}text')), 2)
                    text = svg.accessible_text(p)
                    self.assertIn('Supplied counts', text)
                    self.assertIn('Source identities', text)
                    if kind in ('comparison', 'numbers', 'parts'):
                        self.assertIn('Baseline: 12 requests', text)

    def test_non_numeric_concept_needs_no_manufactured_metric(self):
        p = self.prepare('concept')
        p['facts'][0].update(value='Baseline', unit='')
        p['facts'][1].update(value='Comparison', unit='')
        p['scene'] = scene.plan(p)
        self.assertFalse(any(e['kind'] == 'chart' for e in p['scene']['elements']))
        self.assertEqual(p['attempts'], [])

    def test_concept_process_and_mixed_charts_reserve_meaningful_artwork_regions(self):
        for kind in ('concept', 'process', 'comparison'):
            p = self.prepare(kind, illustration=True)
            self.assertEqual(len(p['scene']['art_regions']), 1)
            region = p['scene']['art_regions'][0]
            self.assertGreater(region['bounds'][3], 36)
            self.assertIn('conceptual relationship', region['role'])
            direction = {'style': 'Flat explanatory illustration with clean shapes and a coherent palette.',
                         'reading_order': 'Top to bottom; compare the two stages.',
                         'acceptance': 'Both stages are legible; relationship is explicit; reserved text regions are empty.',
                         'objects': [{'id': 'stages', 'region_id': region['id'], 'count': 2,
                                      'description': 'Two illustrative system stages.',
                                      'relationships': 'Connect the first stage to the second as a process, not a measured flow.',
                                      'preserve': 'Leave text and chart regions empty.'}]}
            image = image_brief.make(p, direction)
            self.assertIn('Do not draw words, numbers, chart marks', image['prompt'])
            self.assertIn(p['brand']['colors']['headingPrimary'], image['prompt'])
            self.assertEqual(image['scene_id'], p['scene']['id'])
            self.assertNotIn('/not-a-portable-path', image['prompt'])
            self.assertEqual({r['owner'] for r in image['regions']}, {'image', 'compositor'})

    def test_dense_content_and_missing_art_direction_are_refused_instead_of_shrunk(self):
        p = self.prepare('concept', illustration=True)
        p['stories'][0]['blocks'][0]['text'] = 'Required content ' * 600
        with self.assertRaises(Invalid): scene.plan(p)
        p = self.prepare('concept', illustration=True)
        with self.assertRaises(Invalid): image_brief.make(p, {})
        p = self.prepare('comparison', illustration=False)
        with self.assertRaises(Invalid): image_brief.make(p, {})

    def test_svg_escapes_text_and_draft_has_an_explicit_marker(self):
        p = self.prepare('concept')
        p['scene']['elements'][0]['text'] = '<script>bad</script>'
        p['scene']['elements'][0]['lines'] = ['<script>bad</script>']
        text = svg.compose(self.store, p, draft=True)
        self.assertNotIn('<script>', text)
        self.assertIn('&lt;script&gt;', text)
        self.assertIn('DRAFT', text)
        self.assertIn('DRAFT', svg.accessible_text(p, draft=True))

    @unittest.skipUnless(TEST_RENDERER, 'Explicit installed renderer required.')
    def test_all_six_forms_and_three_presets_render_at_actual_size(self):
        import os
        from runner import render
        for preset in PRESETS:
            for kind in ('comparison', 'process', 'timeline', 'numbers', 'parts', 'concept'):
                with self.subTest(preset=preset, kind=kind):
                    planned = self.prepare(kind, preset=preset)
                    output = self.temp / (preset + '-' + kind)
                    result = render.render(svg.compose(self.store, planned), preset=preset,
                        fonts=[planned['brand']['font']], executable=TEST_RENDERER, destination=output)
                    self.assertEqual(result['pdf_pages'], 1)
                    self.assertGreater(len((output / 'page.svg').read_text()), 500)

    def test_number_callouts_preserve_negative_zero_and_explicit_positive_literals(self):
        raw = b'Change -12. Zero 0. Positive +12. Unit requests. Period 2026-01-01. Denominator per second. Conditions same test. Uncertainty not reported.'
        self.project = sources.capture(self.store, self.ident, raw, expected_revision=self.project['revision'])
        source = self.project['sources'][-1]
        facts = []
        for ident, label, literal in [('f1', 'Change', '-12'), ('f2', 'Zero', '0'), ('f3', 'Positive', '+12')]:
            start = raw.decode().index(label + ' ' + literal)
            quote = label + ' ' + literal
            facts.append({'id': ident, 'statement': label, 'value': int(literal), 'literal': literal,
                          'unit': 'requests', 'status': 'supplied', 'period': '2026-01-01', 'denominator': 'per second',
                          'conditions': 'same test', 'uncertainty': 'not reported',
                          'evidence': [{'source_id': source['id'], 'start': start, 'end': start + len(quote), 'quote': quote}]})
        self.project = evidence.adopt(self.store, self.ident, facts, expected_revision=self.project['revision'])
        p = self.prepare('numbers', preset='digital')
        p['stories'][0]['blocks'][0]['fact_ids'] = ['f1', 'f2', 'f3']
        p['scene'] = scene.plan(p)
        encoded = svg.compose(self.store, p)
        for literal in ('-12 requests', '0 requests', '+12 requests'): self.assertIn(literal, encoded)
        if TEST_RENDERER:
            from runner import render
            render.render(encoded, preset='digital', fonts=['Arial'], executable=TEST_RENDERER, destination=self.temp / 'signed-numbers')
        with self.assertRaises(Invalid): self.prepare('comparison')
