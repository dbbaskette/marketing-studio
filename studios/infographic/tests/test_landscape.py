"""Landscape page sizes: laid out across the page, drawn and exported as PNG and PDF."""
from copy import deepcopy
import os
import sys
import unittest
from unittest import mock

from helpers import Isolated
import test_desk_engine as fixtures
from test_render_count import Launches
from runner import exports, render, scene, stories, svg
from runner.contracts import PRESETS, landscape
from runner.engine import Engine

TEST_RENDERER = os.environ.get('INFOGRAPHIC_STUDIO_TEST_RENDERER')
WIDE = ('widescreen', 'social')
# How many short blocks each size holds at the brand's smallest readable type: a social card
# is 628 pixels tall, so it holds two; more is refused as too dense, saying by how much.
HOLDS = {'widescreen': 3, 'social': 2}


class LandscapeTests(Isolated):
    def setUp(self):
        super().setUp()
        fixtures.setup_desk(self)

    def landscape_project(self, preset, blocks=None):
        """The desk fixture's story with `blocks` blocks, on a fresh infographic of `preset`."""
        blocks = blocks or HOLDS[preset]
        project = self.store.create('Landscape ' + preset, preset=preset)
        source = self.store.read(self.ident)
        from runner import brand, evidence, sources
        from test_composition import contract
        ident = project['id']
        project = sources.capture(self.store, ident, b'One instance restarts while the others serve.', expected_revision=0)
        quote = sources.read(self.store, project, project['sources'][0])
        fact = {'id': 'f1', 'statement': quote, 'value': quote, 'unit': '', 'status': 'supplied',
                'evidence': [{'source_id': project['sources'][0]['id'], 'start': 0, 'end': len(quote), 'quote': quote}]}
        project = evidence.adopt(self.store, ident, [fact], expected_revision=1)
        project = brand.adopt(self.store, ident, contract(), expected_revision=2)
        story = deepcopy(self.proposal)
        story['blocks'] = [{**story['blocks'][0], 'id': 'b' + str(n), 'title': 'Step ' + str(n),
                            'text': 'The remaining instances keep serving.'} for n in range(1, blocks + 1)]
        project = stories.adopt(self.store, ident, [story], expected_revision=3)
        return stories.select(self.store, ident, 'story1', expected_revision=4)

    def test_one_sizes_table_names_both_landscape_sizes(self):
        self.assertEqual({k: (v['width_px'], v['height_px']) for k, v in PRESETS.items() if landscape(k)},
                         {'widescreen': (1920, 1080), 'social': (1200, 628)})
        for preset in PRESETS:
            d = render.dimensions(preset)
            self.assertEqual((d['width_px'], d['height_px']), (PRESETS[preset]['width_px'], PRESETS[preset]['height_px']))
            self.assertEqual((d['width_pt'], d['height_pt']), (PRESETS[preset]['width_pt'], PRESETS[preset]['height_pt']))
        self.assertFalse(any(landscape(p) for p in ('a4', 'letter', 'digital')))

    def test_landscape_blocks_sit_side_by_side_in_both_layouts(self):
        for preset in WIDE:
            for arrangement in ('stack', 'infographic'):
                with self.subTest(preset=preset, arrangement=arrangement):
                    project = self.landscape_project(preset)
                    planned = scene.plan(project, arrangement=arrangement)
                    self.assertEqual((planned['width'], planned['height']), (PRESETS[preset]['width'], PRESETS[preset]['height']))
                    headings = [e for e in planned['elements'] if e['kind'] == 'text' and e.get('block_id')
                                and e['id'].endswith('_heading')]
                    tops = {round(e['bounds'][1]) for e in headings}
                    lefts = {round(e['bounds'][0]) for e in headings}
                    # Every block across one row, not a squeezed stack down the page.
                    self.assertEqual(len(headings), HOLDS[preset])
                    self.assertEqual(len(tops), 1, headings)
                    self.assertEqual(len(lefts), HOLDS[preset])
                    for element in planned['elements']:
                        x, y, w, h = element['bounds']
                        self.assertLessEqual(x + w, planned['width'] + .01)
                        self.assertLessEqual(y + h, planned['height'] + .01)

    def test_a_social_card_says_how_much_too_dense_three_blocks_are(self):
        from runner.contracts import TooDense
        with self.assertRaises(TooDense) as refused:
            scene.plan(self.landscape_project('social', blocks=3), arrangement='infographic')
        self.assertLess(refused.exception.over, 20)

    def test_both_landscape_sizes_render_and_export_png_and_pdf(self):
        launches = Launches()
        with mock.patch.object(render, '_run', side_effect=launches):
            for preset in WIDE:
                with self.subTest(preset=preset):
                    project = self.landscape_project(preset)
                    engine = Engine(self.store, executable=sys.executable)
                    manifest = engine.build(project['id'], expected_revision=project['revision'], request_id='wide-' + preset)
                    # exports.build checks the PNG's pixels and the PDF page's points itself.
                    png = exports.read(self.store, project['id'], manifest['id'], 'png')[1]
                    import struct
                    self.assertEqual(struct.unpack('>II', png[16:24]), (PRESETS[preset]['width_px'], PRESETS[preset]['height_px']))
                    pdf = exports.read(self.store, project['id'], manifest['id'], 'pdf')[1]
                    self.assertIn(('/MediaBox [0 0 ' + str(PRESETS[preset]['width_pt'])).encode(), pdf)
        self.assertEqual(launches.calls.count('--print-to-pdf'), 2)

    @unittest.skipUnless(TEST_RENDERER, 'Explicit installed renderer required.')
    def test_both_landscape_sizes_draw_at_actual_size_with_the_installed_renderer(self):
        for preset in WIDE:
            with self.subTest(preset=preset):
                project = self.landscape_project(preset)
                planned = scene.adopt_best(self.store, project['id'], expected_revision=project['revision'])
                output = self.temp / ('real-' + preset)
                result = render.render(svg.compose(self.store, planned), preset=preset, fonts=[planned['brand']['font']],
                                       executable=TEST_RENDERER, destination=output)
                self.assertEqual(result['pdf_pages'], 1)
                self.assertEqual(render.png_size(output / 'page.png'), (PRESETS[preset]['width_px'], PRESETS[preset]['height_px']))
                (width, height), = render.pdf_pages(output / 'page.pdf')
                self.assertAlmostEqual(width, PRESETS[preset]['width_pt'], delta=1)
                self.assertAlmostEqual(height, PRESETS[preset]['height_pt'], delta=1)
