"""Presentation Studio and the Document Library handoff (issue #514): verified research kept
in the library, a deck started from a library item, and Continue in another studio on a
delivered deck the library kept.

Every library is a disposable folder (runner_support sets STUDIOS_LIBRARY), every worker is
scripted and every bundle synthetic (synthesis_fixture). Nothing reaches Google, an
assistant or the network."""
import shutil
import unittest
from unittest import mock

import helpers  # noqa: F401  puts the runner on the import path
import test_desk
import test_desk_page
from runner_support import DeskCase
from studio_core import document_library
from synthesis_fixture import published_bundle

from runner import engine as engines
from runner import library_keep

PICKED = {'id': 'launch-post', 'revision': 2}
READ = {'id': 'launch-post', 'revision': 2, 'title': 'Launch post', 'readable': True,
        'text': '# Launch post\n\nWhat changed.\n'}


@unittest.skipUnless(test_desk.NODE, 'Node is needed to run the page scripts without a browser')
class LibraryLinkTests(test_desk_page.DeskPageCase):
    """`library=<id>@<revision>` in the link opens New deck with that revision picked, and a
    delivered deck the library kept offers Continue in another studio."""

    def opened(self, given, steps, **answers):
        return self.run_page(self.answers(**answers), steps,
                             hash='#token=the-test-key&library=' + given)

    def test_the_item_is_picked_and_said_and_nothing_is_made(self):
        result = self.opened('launch-post@2', [{'snapshot': 'sheet'}],
                             **{'POST /api/library-document': [test_desk.ok(READ)]})
        sheet = result['snapshots']['sheet']['sheet']
        self.assertIn('New deck', sheet)
        self.assertIn('Starting from: Launch post, from the Document Library.', sheet)
        self.assertIn('Nothing is made until you choose Start.', sheet)
        posted = self.posts(result)
        self.assertEqual([one for one in posted if one[0] == '/api/library-document'],
                         [('/api/library-document', PICKED)])
        self.assertNotIn('/api/decks', [address for address, _ in posted])

    def test_an_item_that_cannot_be_opened_is_said_and_the_sheet_opens_empty(self):
        refused = {'status': 409, 'body': {'error': 'That document was removed from the library.'}}
        result = self.opened('launch-post@2', [{'snapshot': 'sheet'}],
                             **{'POST /api/library-document': [refused]})
        sheet = result['snapshots']['sheet']['sheet']
        self.assertIn('The Document Library item you chose could not be opened: That document '
                      'was removed from the library. Start as usual', sheet)
        self.assertNotIn('Starting from:', sheet)

    def test_a_malformed_value_is_left_alone(self):
        for given in ('Launch@2', 'launch-post@0', 'launch-post@1001', 'launch-post', 'x@1x'):
            with self.subTest(given=given):
                result = self.opened(given, [{'snapshot': 'home'}])
                self.assertEqual([one for one in self.posts(result)
                                  if one[0] == '/api/library-document'], [])
                self.assertNotIn('Starting from:', result['snapshots']['home']['text'])

    def test_a_delivered_deck_kept_in_the_library_offers_continue_in_another_studio(self):
        path = self.desk_deck()
        view = self.run_of(path)
        delivered = self.post('desk-deliver', {'path': path, 'expected': view['desk']['expected'],
                                               'blockers_seen': view['desk']['blockers_seen']})
        kept = delivered['desk']['library']
        self.assertEqual(kept['state'], 'kept')
        home = 'http://127.0.0.1:8900'
        shot = self.run_page(self.answers(**{'GET /api/run': [test_desk.ok(delivered)]}),
                             [{'snapshot': 'kept'}], state={'screen': 'deck', 'path': path},
                             shell=True, continueHome=home)['snapshots']['kept']
        link = next(one for one in shot['links']
                    if one['name'] == 'Continue in another studio: this deck')
        self.assertEqual(link['href'], home + '/#token=home-key&continue='
                         + kept['document'] + '@' + str(kept['revision']))
        self.assertEqual(link['target'], 'marketing-studio')
        alone = self.open_deck(path, delivered, [{'snapshot': 'kept'}])['snapshots']['kept']
        self.assertNotIn('Continue in another studio', str(alone['links']))


class ResearchKeptTests(DeskCase):

    def deck(self):
        root = self.start_desk(look='default')
        self.on_desk(root)
        shutil.rmtree(root / 'research', ignore_errors=True)
        published_bundle(root / 'research')
        return root

    def kept_rows(self) -> list:
        found = document_library.opened()
        return [] if found is None else found.catalog(kind='research')['items']

    def test_verified_research_is_kept_under_the_deck_s_key_and_said(self):
        root = self.deck()
        said = self.engine._keep_research(root)
        self.assertEqual(said['state'], 'kept')
        rows = [row for row in self.kept_rows() if row['id'] == said['document']]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['studio'], 'presentation')
        self.assertTrue(rows[0]['title'].endswith(': research'))
        self.assertEqual(library_keep.research_noted(root)['revision'], said['revision'])
        commits = self.log()
        self.assertEqual(self.engine._keep_research(root)['revision'], said['revision'])
        self.assertEqual(self.log(), commits)

    def test_research_that_does_not_pass_is_refused_and_never_raises(self):
        root = self.deck()
        shutil.rmtree(root / 'research')
        published_bundle(root / 'research', review={'accepted': False, 'digest': 'other'})
        before = self.kept_rows()
        said = self.engine._keep_research(root)
        self.assertEqual(said['state'], 'refused')
        self.assertIn('has not passed verification', said['problem'])
        self.assertEqual(self.kept_rows(), before)
        self.assertEqual(library_keep.research_noted(root)['state'], 'refused')

    def test_the_report_step_keeps_research_once_it_was_verified(self):
        root = self.deck()
        record = self.record(root)
        record['research_contract'] = {'schema': 2}
        verify = mock.Mock(return_value={'status': 'complete'})
        tool = mock.Mock(_json=verify)
        from studio_core import research_contract
        step = next(one for one in engines.stages.PIPELINE if one.name == 'research-report')
        with mock.patch.object(engines.Engine, '_load', return_value=record), \
                mock.patch.object(self.engine, 'research', return_value=tool), \
                mock.patch.object(research_contract, 'matching', return_value=tool), \
                mock.patch.object(research_contract, 'publish',
                                  return_value=({}, {'digest': 'd'})), \
                mock.patch.object(engines.Engine, '_done'), \
                mock.patch.object(engines.Engine, '_keep_research') as keep:
            self.engine._research_report(root, None, step)
        keep.assert_called_once_with(root)
        # Research the check did not pass is never kept.
        verify.return_value = {'status': 'incomplete'}
        with mock.patch.object(engines.Engine, '_load', return_value=record), \
                mock.patch.object(self.engine, 'research', return_value=tool), \
                mock.patch.object(research_contract, 'matching', return_value=tool), \
                mock.patch.object(engines.Engine, '_keep_research') as keep, \
                self.assertRaises(Exception):
            self.engine._research_report(root, None, step)
        keep.assert_not_called()
