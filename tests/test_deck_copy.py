"""A slide shows none of a team's bookkeeping, and ordinary words are never taken for it."""
import unittest

from test_home import IsolatedHome  # noqa: F401  puts the core on the import path
from studio_core import deck_copy

IDS = ('O1', 'O2', 'O3', 'O9', 'M1', 'g1', 'g2', 'g4', 'g7', 'f3', 's8')
SLUGS = ('operating-model', 'main')


class InternalTests(unittest.TestCase):
    def test_ordinary_words_are_never_taken_for_bookkeeping(self):
        for text in ('O2 sensors', 'g5.xlarge', 'Model O3', 'Research 2024: what changed',
                     'Research 5G', 'Objectives 2 and 3', 'real-time: streaming',
                     'follow-up: owners', 'built-in: backups', 'x86-64: images',
                     'Research shows the gap', 'The main point', 'Tanzu for Postgres 4.5 '
                     'documentation', 'https://example.com/docs/O1-g7', 'Use g1 nodes'):
            with self.subTest(text=text):
                self.assertIsNone(deck_copy.internal(text, IDS, SLUGS))

    def test_the_runs_own_ids_after_a_bookkeeping_word_in_a_list_or_alone(self):
        for text, shown in (('Finding g4; Tanzu 4.5', 'Finding g4'),
                            ('Findings g1, g7; PostgreSQL 18', 'Findings g1, g7'),
                            ('Blueprint O1–O9; learner guide', 'Blueprint O1–O9'),
                            ('Blueprint M1; learner guide operating-model', 'Blueprint M1'),
                            ('Learner guide chapter 1; findings g1, g7', 'findings g1, g7'),
                            ('research findings g2', 'research findings g2'),
                            ('Learner guide; g1, g7', 'g1, g7'), ('O4', None), ('O1', 'O1'),
                            ('f3', 'f3'),
                            ('operating-model: EDB-operator platform lead', 'operating-model'),
                            ('main: the others carry the load.', 'main:')):
            with self.subTest(text=text):
                self.assertEqual(deck_copy.internal(text, IDS, SLUGS), shown)
        self.assertIsNone(deck_copy.internal('Finding g9', IDS), 'not one of the run\'s IDs')
        self.assertIsNone(deck_copy.internal('finding G4', IDS), 'an ID only as written')

    def test_problems_name_the_field_and_say_where_ids_go(self):
        slides = [{'id': 'model01', 'source': 'Findings g1, g7; PostgreSQL 18',
                   'points': [{'label': 'Profile', 'text': 'operating-model: a lead',
                               'parts': ['Blueprint M1']}]},
                  {'id': 'ok', 'title': 'O2 sensors report', 'provenance': 'Findings g1, g7'},
                  {'id': 'bad', 'provenance': ' '}]
        found = deck_copy.problems(slides, IDS, SLUGS)
        self.assertEqual([line.split(':', 1)[0] for line in found],
                         ['model01', 'model01', 'model01', 'bad'])
        self.assertIn('source shows "Findings g1, g7"', found[0])
        self.assertIn("put the IDs in the slide's `provenance`", found[0])
        self.assertIn('`provenance` is text', found[3])
