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


RECORD = {'schema': 1, 'default': 'tanzu-contrast',
          'direction': {'focal': 'headingPrimary', 'neutral': 'canvasSecondary',
                        'meanings': {'accentAqua': 'Tanzu', 'accentPurple': 'The alternative'},
                        'motif': 'A bar strip says whose side a card is on.'},
          'layouts': {'cover': 'Title Slide', 'section': 'Section Header',
                      'closing': 'Big Statement 2', 'thanks': 'Thank You'},
          'closing': {'withWords': {'layout': 'Big Statement 2', 'title': True, 'subtitles': 1}},
          'house': ['Fill cards.', '', 'Icons for each concrete concept.'],
          'directions': []}


class DefaultLookTests(unittest.TestCase):
    def test_the_brands_deck_direction_record_gives_the_default_look(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'brand-contract.json'
            path.write_text(json.dumps(contract()))
            self.assertIsNone(looks.default_look(path), 'an older brand writes none')
            (Path(folder) / looks.FILE).write_text(json.dumps(RECORD))
            made = looks.default_look(path)
            self.assertEqual(made['id'], 'tanzu-contrast')
            self.assertEqual(made['direction'], RECORD['direction'])
            self.assertEqual(made['house'], ['Fill cards.', 'Icons for each concrete concept.'])
            self.assertEqual(made['layouts']['closing'], 'Big Statement 2')
            self.assertEqual(made['closing']['withWords']['subtitles'], 1)
            self.assertEqual(looks.of_file(path), RECORD['direction'])
            # The same record inside the contract, as the brand also exports it.
            self.assertEqual(looks.direction(contract(slides={'deck': RECORD})),
                             RECORD['direction'])


class GuidanceTests(unittest.TestCase):
    def test_what_a_studio_keeps_and_forwards_of_the_brands_guidance_entry(self):
        from studio_core import brand_guidance as guidance
        with tempfile.TemporaryDirectory() as folder:
            snap = Path(folder) / 'tasks' / 'abc'
            (snap / 'references' / 'gallery').mkdir(parents=True)
            (snap / 'SKILL.md').write_text('# Slides')
            (snap / 'references' / 'draft.md').write_text('Choose the look from real slides.')
            (snap / 'references' / 'gallery' / 'order.json').write_text('{"slides": []}')
            (snap / 'references' / 'review.md').symlink_to(Path(folder) / 'tasks')
            answer = {'task': 'abc', 'revision': 'r1', 'runtime': '/opt/slides',
                      'guidance': str(snap / 'SKILL.md'), 'freshness': 'current-at-start',
                      'secret': {'x': 1},
                      'brand': {'worker': '# Tanzu slides: worker guidance\n',
                                'checkpoints': ['Draft approval.', 'Look.', 7]}}
            self.assertEqual(guidance.recorded(answer), {
                'task': 'abc', 'revision': 'r1', 'runtime': '/opt/slides',
                'freshness': 'current-at-start'})
            texts = guidance.snapshot(answer)
            self.assertEqual(texts['drafting guidance'], 'Choose the look from real slides.')
            self.assertEqual(texts['slides guidance'], '# Slides')
            self.assertIn(guidance.example('order'), texts)
            self.assertNotIn('review guidance', texts, 'a link is never followed')
            self.assertEqual(guidance.worker(answer), '# Tanzu slides: worker guidance\n')
            self.assertEqual(guidance.checkpoints(answer), ['Draft approval.', 'Look.'])
            self.assertIsNone(guidance.worker({'task': 'abc'}))
            self.assertEqual(guidance.snapshot({}), {})

    def test_the_brands_own_handoff_beside_its_contract(self):
        from studio_core import brand_guidance as guidance
        with tempfile.TemporaryDirectory() as folder:
            recipes = Path(folder) / 'slide-design-recipes.md'
            recipes.write_text('# Recipes')
            path = Path(folder) / 'export' / 'brand-contract.json'
            path.parent.mkdir()
            path.write_text(json.dumps(contract(references={
                'recipes': str(recipes), 'icons': 'Use tanzu-brand icons --query'})))
            (path.parent / 'DESIGN.md').write_text('# Design')
            self.assertEqual(guidance.brand_texts(path), {
                'brand design': '# Design', 'brand slide recipes': '# Recipes',
                'brand icons': 'Use tanzu-brand icons --query'})
            path.write_text(json.dumps(contract(references={'recipes': 'relative.md'})))
            self.assertEqual(guidance.brand_texts(path), {'brand design': '# Design'})
