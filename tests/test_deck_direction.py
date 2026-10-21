"""A deck's direction as its brand gives it: disposable files only."""
import json
import tempfile
import unittest
from pathlib import Path

from test_home import IsolatedHome  # noqa: F401  puts the core on the import path
from studio_core import deck_direction as looks

COLOURS = {'canvasPrimary': '#FFFFFF', 'canvasSecondary': '#E2E3E4', 'inkDeep': '#1B1D36',
           'headingPrimary': '#005C8A', 'accentAqua': '#007B8C', 'accentPurple': '#6C4B94',
           'accentGreen': '#61A60E', 'accentAzure': '#0098C7'}


def contract(**design):
    return {'schema': 1, 'design': {'colors': dict(COLOURS), **design}}


class DirectionTests(unittest.TestCase):
    def test_a_brand_that_says_nothing_gives_no_direction(self):
        # The studio does not choose one: the brand's look step, or the fallback, does.
        for given in (contract(), {}, None):
            self.assertIsNone(looks.direction(given))

    def test_the_brands_own_direction_is_used_wherever_it_says_it(self):
        given = {'focal': 'accentAqua', 'neutral': 'canvasSecondary',
                 'meanings': {'accentPurple': 'Competitors', 'notARole': 'x',
                              'accentGreen': '  ', 'accentAqua': 'focal cannot mean'},
                 'motif': 'A shared base under every comparison.'}
        expected = {'focal': 'accentAqua', 'neutral': 'canvasSecondary',
                    'meanings': {'accentPurple': 'Competitors'},
                    'motif': 'A shared base under every comparison.'}
        for made in (looks.direction(contract(), given),
                     looks.direction(contract(deckDirection=given)),
                     looks.direction(contract(direction=given)),
                     looks.direction(contract(slides={'direction': given}))):
            self.assertEqual(made, expected)
        # Beside the contract wins over the contract.
        other = {'focal': 'headingPrimary', 'neutral': 'canvasPrimary'}
        self.assertEqual(looks.direction(contract(deckDirection=given), other), other)

    def test_an_unusable_direction_is_passed_over(self):
        for given in ({'focal': 'missing', 'neutral': 'canvasSecondary'},
                      {'focal': 'headingPrimary', 'neutral': 'headingPrimary'},
                      'not an object', {'neutral': 'canvasSecondary'}):
            with self.subTest(given=given):
                self.assertIsNone(looks.direction(contract(deckDirection=given)))

    def test_a_meaning_in_the_focal_colour_is_left_out(self):
        same = contract()
        same['design']['colors']['accentAqua'] = '#005c8a'
        made = looks.checked({'focal': 'headingPrimary', 'neutral': 'canvasSecondary',
                              'meanings': {'accentAqua': 'Tanzu'}}, same)
        self.assertNotIn('meanings', made)

    def test_of_file_reads_the_contract_and_the_direction_beside_it(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'brand-contract.json'
            path.write_text(json.dumps(contract()))
            self.assertIsNone(looks.of_file(path))
            (Path(folder) / looks.FILE).write_text(json.dumps(
                {'focal': 'accentAzure', 'neutral': 'canvasSecondary'}))
            self.assertEqual(looks.of_file(path)['focal'], 'accentAzure')
            (Path(folder) / looks.FILE).write_text('{not json')
            self.assertIsNone(looks.of_file(path))
            self.assertIsNone(looks.of_file(Path(folder) / 'missing.json'))
            self.assertEqual(looks.contract_of(Path(folder) / 'missing.json'), {})

    def test_told_names_each_meaning(self):
        text = looks.told({'focal': 'headingPrimary', 'neutral': 'canvasSecondary',
                           'meanings': {'accentPurple': 'Competitors'}, 'motif': 'A base.'})
        self.assertIn('- `accentPurple`: Competitors', text)
        self.assertIn('`headingPrimary` marks the one node', text)
        self.assertIn("The deck's recurring device: A base.", text)
