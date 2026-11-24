"""A build draws its page once: renderer (Chromium) launches are counted, not guessed."""
from copy import deepcopy
import html
import json
from pathlib import Path
import re
import struct
import sys
import zlib
from unittest import mock

from helpers import Isolated, NATIVE
import test_desk_engine as fixtures
from runner import render, stories
from runner.engine import Engine


class Launches:
    """Stands in for each Chromium launch and writes what that launch would."""
    def __init__(self):
        self.calls = []

    def __call__(self, executable, work, arguments, timeout):
        self.calls.append(next(a.split('=')[0] for a in arguments if a.startswith(('--dump-dom', '--screenshot', '--print-to-pdf'))))
        page = (Path(work) / 'scene.html').read_text()
        if '--dump-dom' in arguments:
            metrics = {'complete': True, 'missing_fonts': [], 'invalid_assets': [], 'overflow': [], 'boxes': []}
            return '<pre id="metrics">' + html.escape(json.dumps(metrics)) + '</pre>'
        shot = next((a for a in arguments if a.startswith('--screenshot=')), None)
        if shot:
            width, height = map(int, re.search(r'--window-size=(\d+),(\d+)', ' '.join(arguments)).groups())
            def chunk(kind, raw):
                return struct.pack('>I', len(raw)) + kind + raw + struct.pack('>I', zlib.crc32(kind + raw))
            Path(shot.split('=', 1)[1]).write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)))
            return ''
        target = next(a for a in arguments if a.startswith('--print-to-pdf='))
        width, height = re.search(r'@page\{size:([\d.]+)pt ([\d.]+)pt', page).groups()
        Path(target.split('=', 1)[1]).write_bytes(('%PDF-1.4\n1 0 obj << /Type /Page /MediaBox [0 0 ' + width + ' ' + height
                                                    + '] >> endobj\n%%EOF').encode())
        return ''


class RenderCountTests(Isolated):
    def setUp(self):
        super().setUp()
        fixtures.setup_desk(self)
        # The real renderer path: only each Chromium launch is stood in for.
        self.engine = Engine(self.store, executable=sys.executable)
        self.launches = Launches()
        patcher = mock.patch.object(render, '_run', side_effect=self.launches)
        patcher.start()
        self.addCleanup(patcher.stop)

    def with_artwork(self, state='complete'):
        from runner.images.base import result, save_asset
        from graphics_fixtures import png
        proposal = deepcopy(self.proposal)
        proposal['blocks'][0].update(illustration=True, illustration_role='Show a restarting instance beside serving instances.')
        current = stories.adopt(self.store, self.ident, [proposal], expected_revision=6)
        current = stories.select(self.store, self.ident, 'story1', expected_revision=current['revision'])

        class Adapter:
            def __init__(self, folder): self.folder = folder
            def generate(self, *, attempt_id, brief):
                if state != 'complete':
                    return result('gemini', 'generate', attempt_id, state=state, reason='provider-refusal')
                return result('gemini', 'generate', attempt_id, state='complete', assets=[save_asset(self.folder, png(), 'image/png')])

        def direction(project):
            region = project['scene']['art_regions'][0]['id']
            return {'style': 'Coherent explanatory shapes.', 'reading_order': 'Restarting then serving instances.',
                    'acceptance': 'Exact counts and clear label regions.',
                    'objects': [{'id': 'instances', 'region_id': region, 'count': 3, 'description': 'Three service instances.',
                                 'relationships': 'One restarts; two serve.', 'preserve': 'Leave labels empty.'}]}
        self.engine.assistant = mock.Mock()
        self.engine.assistant.art_direction.side_effect = direction
        self.engine.adapters = {'gemini': Adapter}
        self.engine.configuration = {'image_provider': 'gemini'}
        return current

    def test_a_page_without_artwork_is_drawn_once(self):
        # Before: a preflight preview, the final preview and the page's own preview call
        # (three launches, the later two read back from the first). After: one render.
        manifest = self.engine.build(self.ident, expected_revision=6, request_id='count-plain')
        self.assertEqual(self.launches.calls, ['--dump-dom', '--screenshot', '--print-to-pdf'])
        self.assertEqual(manifest['revision'], self.store.read(self.ident)['revision'])
        self.assertTrue(manifest['draft'])

    def test_a_page_with_new_artwork_measures_once_then_draws_once(self):
        # Before: six launches (a full preflight render and a full final render). After: four.
        current = self.with_artwork()
        manifest = self.engine.build(self.ident, expected_revision=current['revision'], request_id='count-art')
        self.assertEqual(self.launches.calls, ['--dump-dom', '--dump-dom', '--screenshot', '--print-to-pdf'])
        project = self.store.read(self.ident)
        self.assertTrue(any(e['kind'] == 'artwork' for e in project['scene']['elements']))
        self.assertEqual(manifest['revision'], project['revision'], 'The build returns the preview of what it made.')

    def test_artwork_that_did_not_arrive_still_shows_the_page(self):
        current = self.with_artwork(state='failed')
        answer = self.engine.build(self.ident, expected_revision=current['revision'], request_id='count-failed')
        self.assertEqual(answer['state'], 'failed')
        self.assertEqual(answer['preview']['revision'], self.store.read(self.ident)['revision'])
        self.assertEqual(self.launches.calls, ['--dump-dom', '--dump-dom', '--screenshot', '--print-to-pdf'])

    def test_the_page_asks_for_no_preview_after_a_build(self):
        script = (NATIVE / 'runner/web/app.js').read_text()
        compose = script[script.index('async function compose()'):]
        compose = compose[:compose.index('\n}\n')]
        self.assertIn("action('build'", compose)
        self.assertNotIn("action('preview'", compose)
