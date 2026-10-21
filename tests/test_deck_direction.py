"""A deck's direction and house rules from its brand contract: disposable files only."""
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
    def test_a_brand_that_says_nothing_gets_three_meanings_from_its_accents(self):
        made = looks.direction(contract())
        self.assertEqual((made['focal'], made['neutral']), ('headingPrimary', 'canvasSecondary'))
        self.assertEqual(list(made['meanings']), ['accentAqua', 'accentPurple', 'accentGreen'])
        self.assertTrue(all(made['meanings'].values()))
        self.assertNotIn('motif', made)

    def test_a_brand_without_the_standard_roles_keeps_the_two_colours(self):
        bare = {'schema': 1, 'design': {'colors': {'headingPrimary': '#000',
                                                   'canvasSecondary': '#EEE'}}}
        self.assertEqual(looks.direction(bare), looks.LEGACY)
        self.assertEqual(looks.direction({}), looks.LEGACY)
        self.assertEqual(looks.direction(None), looks.LEGACY)

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

    def test_an_unusable_direction_falls_back_to_the_built_in_one(self):
        for given in ({'focal': 'missing', 'neutral': 'canvasSecondary'},
                      {'focal': 'headingPrimary', 'neutral': 'headingPrimary'},
                      'not an object', {'neutral': 'canvasSecondary'}):
            with self.subTest(given=given):
                self.assertEqual(looks.direction(contract(deckDirection=given)),
                                 looks.built_in(contract()))

    def test_a_meaning_in_the_focal_colour_is_left_out(self):
        same = contract()
        same['design']['colors']['accentAqua'] = '#005c8a'
        self.assertNotIn('accentAqua', looks.direction(same)['meanings'])

    def test_corners_and_house_rules_follow_the_brand(self):
        self.assertIs(looks.square(contract(geometry={'rectangularRadiusPx': 0})), True)
        self.assertIs(looks.square(contract(geometry={'rectangularRadiusPx': 6})), False)
        self.assertIsNone(looks.square(contract()))
        self.assertIn(looks.SQUARE, looks.house(True))
        for said in (None, False):
            self.assertNotIn(looks.SQUARE, looks.house(said))
        rules = ' '.join(looks.house())
        self.assertNotIn('in another colour', rules)
        self.assertIn('may share a light fill', rules)
        self.assertIn('functional icon library', rules)
        self.assertNotIn('An icon is optional', rules)

    def test_of_file_reads_the_contract_and_the_direction_beside_it(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'brand-contract.json'
            path.write_text(json.dumps(contract(geometry={'rectangularRadiusPx': 0})))
            made = looks.of_file(path)
            self.assertEqual(made['direction'], looks.built_in(contract()))
            self.assertIs(made['square'], True)
            (Path(folder) / looks.FILE).write_text(json.dumps(
                {'focal': 'accentAzure', 'neutral': 'canvasSecondary'}))
            self.assertEqual(looks.of_file(path)['direction']['focal'], 'accentAzure')
            (Path(folder) / looks.FILE).write_text('{not json')
            self.assertEqual(looks.of_file(path)['direction'], looks.built_in(contract()))
            self.assertEqual(looks.of_file(Path(folder) / 'missing.json'),
                             {'direction': looks.LEGACY, 'square': None})

    def test_told_names_each_meaning(self):
        text = looks.told(looks.direction(contract()))
        self.assertIn('`accentPurple`: Another product', text)
        self.assertIn('`headingPrimary` marks the one node', text)
