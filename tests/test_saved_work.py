from pathlib import Path
import unittest

import marketing_studio  # noqa: F401  puts the shared core on the import path
from studio_core import saved_work


class SavedWorkTests(unittest.TestCase):
    """The words and shape of `studio saved-work`, the same in each deck studio."""

    def test_a_path_no_item_needs_is_listed_as_unused(self):
        said = saved_work.report(('research-queue', 'old-harness-slides'), {}, scope={'product': 'Test Studio', 'roots': ['/synthetic'], 'local_only': True})
        self.assertEqual(said['unused'], ['research-queue', 'old-harness-slides'])
        self.assertEqual([entry['needed_by'] for entry in said['paths']], [[], []])

    def test_items_are_listed_under_their_path_in_path_order(self):
        later = saved_work.needs(Path('/work/b-deck'), 'B deck', 'Why b.')
        earlier = saved_work.needs(Path('/work/a-deck'), 'A deck', 'Why a.')
        self.assertEqual(earlier, {'path': '/work/a-deck', 'title': 'A deck', 'why': 'Why a.'})
        said = saved_work.report(('research-queue', 'cover-sample', 'old-harness-slides'),
                                 {'cover-sample': [later, earlier],
                                  'research-queue': [earlier]}, scope={'product': 'Test Studio', 'roots': ['/synthetic']})
        self.assertEqual([entry['id'] for entry in said['paths']],
                         ['research-queue', 'cover-sample', 'old-harness-slides'])
        self.assertEqual(said['paths'][1], {'id': 'cover-sample',
                                            'about': saved_work.PATHS['cover-sample'],
                                            'needed_by': [earlier, later], 'status': 'needed', 'unknown_by': []})
        self.assertEqual(said['unused'], ['old-harness-slides'])

    def test_unconfigured_and_issues_never_certify_unused(self):
        for kwargs in ({}, {'scope': {'roots': ['/synthetic']}, 'issues': [{'path': '/synthetic', 'why': 'Unreadable.'}]}):
            said = saved_work.report(('gated-flow',), {}, **kwargs)
            self.assertFalse(said['complete'])
            self.assertEqual(said['unused'], [])
            self.assertEqual(said['paths'][0]['status'], 'unknown')

    def test_every_path_has_its_sentence_and_names_no_studio(self):
        self.assertEqual(set(saved_work.PATHS), {'research-queue', 'cover-sample',
                                                 'review-layout-1', 'old-harness-slides', 'gated-flow'})
        for about in saved_work.PATHS.values():
            self.assertTrue(about.endswith('.'), about)
            for name in ('Presentation Studio', 'Training Studio'):
                self.assertNotIn(name, about)
        self.assertIn('No saved work needs these.', saved_work.PATHS['old-harness-slides'])
        self.assertIn('Only this computer is looked at', saved_work.PATHS['cover-sample'])


if __name__ == '__main__':
    unittest.main()
