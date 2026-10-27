"""The one deck flow both studios follow: its helpers, against disposable files only."""
import tempfile
import unittest
from pathlib import Path

from test_home import IsolatedHome  # noqa: F401  puts the core on the import path
from studio_core import deck_flow as flow


class FlowTests(unittest.TestCase):
    def test_samples_and_previews_go_only_through_the_slides_tools_preview(self):
        self.assertEqual(flow.route('local')['preview'], 'local')
        plain = flow.route('drive')
        self.assertEqual((plain['preview'], plain['pool']), ('google', False))
        self.assertIn('the way this computer renders every preview', plain['says'])
        pooled = flow.route('drive', lambda name: name == flow.POOL)
        self.assertEqual((pooled['preview'], pooled['pool']), ('google', True))
        self.assertIn('reusable preview decks', pooled['says'])

    def test_the_looks_a_brand_drew_are_kept_with_pictures_from_inside_their_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            (base / 'a').mkdir()
            (base / 'a' / 'slide-01.png').write_bytes(b'png')
            manifest = {'samples': [
                {'id': 'a', 'name': 'A', 'useWhen': 'Always.', 'image': str(base / 'a' / 'slide-01.png'),
                 'direction': {'focal': 'x'}, 'layouts': {'closing': 'End'}},
                {'id': 'b', 'image': '/etc/passwd'}, 'junk']}
            looks = flow.sampled(manifest, base)
            self.assertEqual([(look['id'], look['number'], bool(look['image'])) for look in looks],
                             [('a', 1, True), ('b', 2, False)])
            self.assertEqual(looks[1]['name'], 'b')
            with self.assertRaises(ValueError):
                flow.sampled({'samples': []}, base)

    def test_the_look_a_brand_wrote_into_an_outline(self):
        written = {'direction': {'focal': 'headingPrimary', 'neutral': 'canvasSecondary'},
                   'house': ['Fill cards.', ''], 'layouts': {'closing': 'Big Statement',
                                                           'picture': 'x'}}
        self.assertEqual(flow.chosen_from(written), {
            'direction': written['direction'], 'house': ['Fill cards.'],
            'layouts': {'closing': 'Big Statement'}})
        self.assertIsNone(flow.chosen_from({'slides': []}))
        contract = {'design': {'colors': {'headingPrimary': '#000', 'canvasSecondary': '#EEE'}}}
        self.assertIsNotNone(flow.chosen_from(written, contract))
        self.assertIsNone(flow.chosen_from({'direction': {'focal': 'nope', 'neutral': 'x'}},
                                           contract))

    def test_what_a_worker_reads_of_the_brands_own(self):
        self.assertEqual(flow.for_workers(True), (flow.BRAND_WORKER,))
        self.assertEqual(flow.for_workers(False), flow.BRAND_OWN)
        self.assertEqual(flow.STEPS[2:5], ('draft', 'look-samples', 'look'))


class HeldWhereTheRunStopsTests(unittest.TestCase):
    def test_balanced_holds_the_direction_at_the_look_when_there_is_no_outline_stop(self):
        redesign = ('gate:classify', 'gate:look', 'gate:build')
        self.assertTrue(flow.stops('presentation', 'balanced', 'gate:look', gates=redesign))
        self.assertFalse(flow.stops('presentation', 'balanced', 'gate:look',
                                    gates=redesign + ('gate:outline',)))
        self.assertFalse(flow.stops('presentation', 'balanced', 'gate:look', gates=None))
        self.assertTrue(flow.stops('presentation', 'balanced', 'gate:build', gates=redesign))

    def test_training_is_unchanged_by_the_gate_names(self):
        names = ('review:direction', 'gate:deck-outline@101', 'gate:deck-look@101',
                 'gate:deck@101')
        for level in flow.PAUSES:
            for gate in [g + '@101' for g in flow.GATES['training']] + ['review:direction']:
                with self.subTest(level=level, gate=gate):
                    self.assertEqual(flow.stops('training', level, gate),
                                     flow.stops('training', level, gate, gates=names))

    def test_the_kept_default_says_no_look_was_picked(self):
        self.assertEqual(flow.DEFAULT_KEPT, "The brand's default look, {name}, was used: no "
                         'look was picked in the direction review.')


class PanelServingTests(unittest.TestCase):
    def test_every_studio_page_is_served_the_shared_deck_panels(self):
        from pathlib import Path
        from studio_core import server
        made = server.for_product('_deck_panel_probe', 'Probe', 'X-Probe', Path('/nowhere'),
                                  {'/': ('index.html', 'text/html')}, None, ValueError)
        for path in ('/deck-panels.js', '/deck-panels.css', '/lists.js'):
            name, kind = made.PAGE[path]
            self.assertTrue(Path(name).is_file(), name)
            self.assertIn('charset=utf-8', kind)
        self.assertIn('/', made.PAGE)
