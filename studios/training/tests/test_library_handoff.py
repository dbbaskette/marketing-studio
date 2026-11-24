"""Training Studio and the Document Library handoff (issue #514): verified research kept in
the library, a folder or a spreadsheet taken by the New training form's sources, and a
training started from a library item.

Every library is a disposable folder (STUDIOS_LIBRARY, set by runner_support), every worker
is scripted and every bundle synthetic (synthesis_fixture). Nothing reaches Google, an
assistant or the network."""
import shutil
import unittest
from unittest import mock

import helpers  # noqa: F401  puts the runner on the import path
from studio_core import document_library
from synthesis_fixture import published_bundle
import test_desk
from test_runner_deck import DeckCase

from runner import engine as engines
from runner import library

PICKED = {'id': 'launch-post', 'revision': 2}
READ = {'id': 'launch-post', 'revision': 2, 'title': 'Launch post', 'readable': True,
        'text': '# Launch post\n\nWhat changed.\n'}


@unittest.skipUnless(test_desk.NODE, 'Node is needed to run the page scripts without a browser')
class LibraryLinkTests(test_desk.ScriptedPage, test_desk.PageCase):
    """`library=<id>@<revision>` in the link opens New training with that revision picked."""

    answers = test_desk.RunnerScreenTests.answers
    posts = test_desk.RunnerScreenTests.posts
    started = test_desk.RunnerScreenTests.started

    def opened(self, given, steps, **answers):
        if not getattr(self, 'begun', False):
            self.started()
            self.begun = True
        return self.run_page(self.answers(**answers), steps, research=True,
                             hash='#token=the-test-key&library=' + given)

    def test_the_item_is_picked_and_said_and_goes_with_start(self):
        result = self.opened('launch-post@2', [
            {'snapshot': 'sheet'},
            {'fill': 'A short title', 'value': 'Launch training'},
            {'fill': 'What should it teach?', 'value': 'What the launch changed.'},
            {'fill': 'Who is it for?', 'value': 'Field engineers'},
            {'intakePage': 1}, {'snapshot': 'sources'}],
            **{'POST /api/library-document': [test_desk.ok(READ)]})
        sheet = result['snapshots']['sheet']
        self.assertIn('New training', sheet['text'])
        self.assertIn('Starting from: Launch post, from the Document Library.', sheet['text'])
        self.assertIn('Nothing is made until you choose Start.', sheet['text'])
        sources = result['snapshots']['sources']
        self.assertIn('From the Document Library, revision 2', sources['text'])
        # Only the item was read; nothing was made.
        posted = self.posts(result)
        self.assertEqual([one for one in posted if one[0] == '/api/library-document'],
                         [('/api/library-document', PICKED)])
        self.assertNotIn('/api/trainings', [address for address, _ in posted])

    def test_an_item_that_cannot_be_opened_is_said_and_the_sheet_opens_empty(self):
        refused = {'status': 409, 'body': {'error': 'That document was removed from the library.'}}
        result = self.opened('launch-post@2', [{'snapshot': 'sheet'}],
                             **{'POST /api/library-document': [refused]})
        text = result['snapshots']['sheet']['text']
        self.assertIn('The Document Library item you chose could not be opened: That document '
                      'was removed from the library. Start as usual', text)
        self.assertNotIn('Starting from:', text)
        self.assertNotIn('From the Document Library, revision', text)

    def test_a_malformed_value_is_left_alone(self):
        for given in ('Launch@2', 'launch-post@0', 'launch-post@1001', 'launch-post', 'x@1x'):
            with self.subTest(given=given):
                result = self.opened(given, [{'snapshot': 'home'}])
                self.assertEqual([one for one in self.posts(result)
                                  if one[0] == '/api/library-document'], [])
                self.assertNotIn('Starting from:', result['snapshots']['home']['text'])


class ResearchKeptTests(DeckCase):

    def training(self):
        root = self.start(flow='desk', levels=['101'])
        self.assertEqual(self.to_end(root), [])
        shutil.rmtree(root / 'research', ignore_errors=True)
        published_bundle(root / 'research')
        return root

    def kept_rows(self) -> list:
        found = document_library.opened()
        return [] if found is None else found.catalog(kind='research')['items']

    def test_verified_research_is_kept_under_the_training_s_key_and_said(self):
        root = self.training()
        said = self.engine._keep_research(root)
        self.assertEqual(said['state'], 'kept')
        rows = [row for row in self.kept_rows() if row['id'] == said['document']]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['studio'], 'training')
        self.assertTrue(rows[0]['title'].endswith(': research'))
        self.assertEqual(library.research_noted(root)['revision'], said['revision'])
        # The desk's Sources says it.
        from runner import drafts
        self.assertEqual(drafts.view(self.engine, root)['sources']['library']['state'], 'kept')
        # Kept again unchanged, it adds no revision and no commit.
        commits = self.log()
        again = self.engine._keep_research(root)
        self.assertEqual(again['revision'], said['revision'])
        self.assertEqual(self.log(), commits)

    def test_research_that_does_not_pass_is_refused_and_never_raises(self):
        root = self.training()
        shutil.rmtree(root / 'research')
        published_bundle(root / 'research', review={'accepted': False, 'digest': 'other'})
        before = self.kept_rows()
        said = self.engine._keep_research(root)
        self.assertEqual(said['state'], 'refused')
        self.assertIn('has not passed verification', said['problem'])
        self.assertEqual(self.kept_rows(), before)
        self.assertEqual(library.research_noted(root)['state'], 'refused')

    def test_a_failure_while_keeping_never_fails_the_research_step(self):
        root = self.training()
        with mock.patch.object(engines.Engine, '_report_kept', return_value=True), \
                mock.patch.object(library, '_key', side_effect=RuntimeError('broken')):
            self.engine._report(root, None)
        noted = library.research_noted(root)
        self.assertEqual(noted['state'], 'failed')
        self.assertIn('could not keep this research', noted['problem'])

    def test_the_report_step_keeps_research_only_once_it_was_verified(self):
        root = self.training()
        step = None
        with mock.patch.object(engines.Engine, '_report_kept', return_value=True), \
                mock.patch.object(engines.Engine, '_keep_research') as keep:
            self.engine._report(root, step)
        keep.assert_called_once_with(root)
        with mock.patch.object(engines.Engine, '_report_kept', return_value=False), \
                mock.patch.object(engines.Engine, '_keep_research') as keep:
            self.engine._report(root, step)
        keep.assert_not_called()


from test_runner_deck import PageCase  # noqa: E402


class RemoteCallerTests(PageCase):
    """#514: a request the network bridge carried says so (X-Marketing-Studio-Via: network),
    and the New training form's source editor refuses a phone a folder on this computer,
    while a local caller adds the same folder. A Google Drive folder link and uploads are
    never refused as a folder here (studio_core.shared_runner.caller)."""

    def send(self, sent, remote=False):
        import json
        import desk
        headers = self.headers(True, True)
        if remote:
            headers['X-Marketing-Studio-Via'] = 'network'
        try:
            status, _, data = self.page.answer('/api/research-sources', headers, 'POST',
                                               json.dumps(sent).encode())
        except desk.Refusal as refusal:
            return int(refusal.status), {'error': str(refusal)}
        return int(status), json.loads(data)

    def test_the_page_class_keeps_its_description(self):
        from runner import page
        self.assertTrue(page.RunnerPage.__doc__.startswith('What the page may ask the runner'))

    def test_a_folder_here_is_refused_to_a_phone_and_read_for_this_computer(self):
        import tempfile
        from pathlib import Path
        from studio_core import source_intake
        place = Path(tempfile.mkdtemp(prefix='training-folder-'))
        self.addCleanup(shutil.rmtree, place, True)
        (place / 'notes.md').write_text('# Notes\n\nCapacity holds with two instances.\n')
        status, draft = self.send({'action': 'create'}, remote=True)
        self.assertEqual(status, 200, draft)
        asked = {'action': 'folder', 'id': draft['id'], 'expected': draft['revision'],
                 'location': str(place)}
        status, refused = self.send(asked, remote=True)
        self.assertEqual((status, refused['error']), (403, source_intake.REMOTE))
        status, added = self.send(asked)
        self.assertEqual(status, 200, added)
        self.assertEqual([one['name'] for one in added['sources']], ['notes.md'])
