import os
import base64
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from helpers import NATIVE
from graphics_fixtures import scene
from runner import render


class RenderValidationTests(unittest.TestCase):
    def test_scripts_links_styles_external_images_and_entities_are_refused(self):
        for content in ['<script>alert(1)</script>', '<foreignObject/>',
                        '<image href="https://example.invalid/image.png"/>',
                        '<text onclick="anything()">x</text>', '<rect style="fill:red"/>',
                        '<image href="data:image/png;base64,AAAA"/>']:
            with self.subTest(content=content), self.assertRaises(ValueError):
                render.safe_svg('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 750">' + content + '</svg>')
        with self.assertRaises(ValueError):
            render.safe_svg('<!DOCTYPE svg><svg xmlns="http://www.w3.org/2000/svg"/>')

    def test_scene_fonts_and_presets_must_be_explicit(self):
        svg = scene('comparison', 'a4')
        ET.fromstring(render.safe_svg(svg))
        with self.assertRaises(ValueError):
            render.document(svg, 'a4', ['Unknown Font'])
        with self.assertRaises(ValueError):
            render.dimensions('unknown')
        with self.assertRaises(ValueError):
            render.safe_svg('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 NaN 10"/>')

    def test_pdf_inspection_handles_nested_resource_dictionaries(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'generated.pdf'
            path.write_bytes(b'%PDF-1.7\n1 0 obj\n<</Type /Page /Resources <</Font <</F1 2 0 R>>>> /MediaBox [0 0 612 792]>>\nendobj\n')
            self.assertEqual(render.pdf_pages(path), [(612.0, 792.0)])


@unittest.skipUnless(os.environ.get('INFOGRAPHIC_STUDIO_TEST_RENDERER'),
                     'Supply an installed headless renderer explicitly for graphics acceptance.')
class InstalledRendererTests(unittest.TestCase):
    def test_an_embedded_image_that_cannot_decode_blocks_output(self):
        executable = Path(os.environ['INFOGRAPHIC_STUDIO_TEST_RENDERER'])
        # Valid PNG signature/dimensions with no encoded pixels: metadata is not
        # evidence that the browser can actually render the asset.
        from graphics_fixtures import png
        invalid = base64.b64encode(png()[:24]).decode()
        svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 750"><image x="10" y="10" width="20" height="20" href="data:image/png;base64,' + invalid + '"/></svg>'
        with tempfile.TemporaryDirectory(prefix='infographic-decode-test-') as folder:
            destination = Path(folder) / 'invalid'
            with self.assertRaisesRegex(ValueError, 'invalid assets'):
                render.render(svg, preset='digital', fonts=['Arial'], executable=executable, destination=destination)
            self.assertFalse(destination.exists())

    def test_wrapped_text_spans_are_measured_without_shrinking(self):
        executable = Path(os.environ['INFOGRAPHIC_STUDIO_TEST_RENDERER'])
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 750">
<text x="40" y="100" font-family="Arial" font-size="24" data-id="wrapped" data-box="40 60 500 100">
<tspan x="40" dy="0">Synthetic first line</tspan><tspan x="40" dy="32">Synthetic second line</tspan></text></svg>'''
        with tempfile.TemporaryDirectory(prefix='infographic-wrap-test-') as folder:
            output = Path(folder) / 'wrapped'
            render.render(svg, preset='digital', fonts=['Arial'], executable=executable, destination=output)
            import json
            box = json.loads((output / 'measurements.json').read_text())['boxes'][0]
            self.assertGreater(box['height'], 32)
            self.assertIn('font-size="24"', (output / 'page.svg').read_text())

    def test_three_visual_forms_and_presets_have_exact_outputs_and_editable_text(self):
        executable = Path(os.environ['INFOGRAPHIC_STUDIO_TEST_RENDERER'])
        with tempfile.TemporaryDirectory(prefix='infographic-graphics-test-') as folder:
            for kind, preset in [('comparison', 'a4'), ('process', 'letter'), ('concept', 'digital')]:
                output = Path(folder) / preset
                result = render.render(scene(kind, preset), preset=preset, fonts=['Arial'],
                                       executable=executable, destination=output)
                self.assertEqual(render.png_size(output / 'page.png'),
                                 (result['width_px'], result['height_px']))
                self.assertEqual(len(render.pdf_pages(output / 'page.pdf')), 1)
                self.assertIn(b'/ToUnicode', (output / 'page.pdf').read_bytes())
                svg = ET.parse(output / 'page.svg')
                self.assertGreater(len(svg.findall('.//{http://www.w3.org/2000/svg}text')), 3)
                self.assertEqual(len(svg.findall('.//{http://www.w3.org/2000/svg}image')), 1)

    def test_missing_fonts_and_overflow_leave_no_published_output(self):
        executable = Path(os.environ['INFOGRAPHIC_STUDIO_TEST_RENDERER'])
        with tempfile.TemporaryDirectory(prefix='infographic-graphics-failure-') as folder:
            cases = [('font', scene('concept', 'digital').replace('Arial', 'DefinitelyMissingInfographicFont'),
                      ['DefinitelyMissingInfographicFont']),
                     ('overflow', scene('concept', 'digital').replace('Shared idea', 'A' * 150), ['Arial'])]
            for name, svg, fonts in cases:
                output = Path(folder) / name
                with self.subTest(name=name), self.assertRaises(ValueError):
                    render.render(svg, preset='digital', fonts=fonts,
                                  executable=executable, destination=output)
                self.assertFalse(output.exists())
