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
import runner_support
from runner_support import DeskCase
from studio_core import document_library
from synthesis_fixture import published_bundle

from runner import engine as engines
from runner import library_keep

PICKED = {'id': 'launch-post', 'revision': 2}
# The link Marketing Studio gives: the key, the way home, and the item.
LINK = ('#token=the-test-key&home=http%3A%2F%2F127.0.0.1%3A8900'
        '&homeToken=home-key-1234&library=')
READ = {'id': 'launch-post', 'revision': 2, 'title': 'Launch post', 'readable': True,
        'text': '# Launch post\n\nWhat changed.\n'}


@unittest.skipUnless(test_desk.NODE, 'Node is needed to run the page scripts without a browser')
class LibraryLinkTests(test_desk_page.DeskPageCase):
    """`library=<id>@<revision>` in the link opens New deck with that revision picked, and a
    delivered deck the library kept offers Continue in another studio."""

    def opened(self, given, steps, **answers):
        return self.run_page(self.answers(**answers), steps,
                             hash=LINK + given)

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

    def test_the_link_is_forgotten_once_read_so_a_reload_does_not_open_it_again(self):
        first = self.opened('launch-post@2', [{'snapshot': 'sheet'}],
                            **{'POST /api/library-document': [test_desk.ok(READ)]})
        address = first['address']
        self.assertNotIn('library=', address)
        self.assertIn('token=the-test-key', address)
        self.assertIn('home=', address)
        # A reload of the tab opens with the address as it is now: nothing is read again.
        again = self.run_page(self.answers(), [{'snapshot': 'home'}], **({'research': True} if False else {}),
                              hash=address[address.index('#'):])
        self.assertEqual([one for one in self.posts(again) if one[0] == '/api/library-document'],
                         [])
        self.assertNotIn('Starting from:', again['snapshots']['home']['text'])

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

    def test_a_failure_while_keeping_never_fails_the_research_step(self):
        root = self.deck()
        record = self.record(root)
        record['research_contract'] = {'schema': 2}
        tool = mock.Mock(_json=mock.Mock(return_value={'status': 'complete'}))
        from studio_core import research_contract
        step = next(one for one in engines.stages.PIPELINE if one.name == 'research-report')
        with mock.patch.object(engines.Engine, '_load', return_value=record), \
                mock.patch.object(self.engine, 'research', return_value=tool), \
                mock.patch.object(research_contract, 'matching', return_value=tool), \
                mock.patch.object(research_contract, 'publish',
                                  return_value=({}, {'digest': 'd'})), \
                mock.patch.object(engines.Engine, '_done'), \
                mock.patch.object(library_keep, '_key', side_effect=RuntimeError('broken')):
            self.engine._research_report(root, None, step)
        noted = library_keep.research_noted(root)
        self.assertEqual(noted['state'], 'failed')
        self.assertIn('could not keep this research', noted['problem'])

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


def xlsx_fixture():
    """The repository's synthetic workbook builder (tests/xlsx_fixture.py)."""
    import importlib.util
    from pathlib import Path
    place = Path(__file__).resolve().parents[3] / 'tests' / 'xlsx_fixture.py'
    spec = importlib.util.spec_from_file_location('xlsx_fixture', place)
    found = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(found)
    return found


class RemoteCallerTests(test_desk_page.DeskPageCase):
    """#514: a request the network bridge carried says so (X-Marketing-Studio-Via: network),
    and a phone may not read a folder on this computer: not in the shared source editor's
    Add a folder, nor in the New deck form's folder. A Google Drive folder link and uploads
    are still taken. A deck from a document takes a folder or a spreadsheet through
    source_intake when it holds one document."""

    def send(self, endpoint, sent, remote=False):
        import json
        from email.message import Message  # noqa: F401
        import server
        headers = self.headers(origin=self.origin, kind='application/json')
        if remote:
            headers['X-Marketing-Studio-Via'] = 'network'
        try:
            status, _, data = self.page.answer('/api/' + endpoint, headers, 'POST',
                                               json.dumps(sent).encode())[:3]
        except server.Refusal as refusal:
            return int(refusal.status), {'error': str(refusal)}
        return int(status), json.loads(data)

    def folder(self, *names):
        import tempfile
        from pathlib import Path
        place = Path(tempfile.mkdtemp(prefix='deck-folder-'))
        self.addCleanup(shutil.rmtree, place, True)
        for name in names:
            (place / name).write_text(f'# {name}\n\nCapacity holds with two instances.\n')
        return str(place)

    def test_the_source_editor_refuses_a_folder_here_to_a_phone_only(self):
        from studio_core import source_intake
        status, draft = self.send('research-sources', {'action': 'create'})
        self.assertEqual(status, 200, draft)
        folder = self.folder('notes.md')
        asked = {'action': 'folder', 'id': draft['id'], 'expected': draft['revision'],
                 'location': folder}
        status, refused = self.send('research-sources', asked, remote=True)
        self.assertEqual((status, refused['error']), (403, source_intake.REMOTE))
        # Nothing was read: the draft is as it was.
        status, same = self.send('research-sources', {'action': 'read', 'id': draft['id']})
        self.assertEqual(same['sources'], draft['sources'])
        # At this computer the same folder is read.
        status, added = self.send('research-sources', asked)
        self.assertEqual(status, 200, added)
        self.assertEqual([one['name'] for one in added['sources']], ['notes.md'])

    def test_a_drive_link_or_an_upload_is_never_refused_as_a_folder_here(self):
        from studio_core.shared_runner import caller
        from email.message import Message
        phone = Message()
        phone['X-Marketing-Studio-Via'] = 'network'
        with caller.answering(phone):
            self.assertTrue(caller.remote())
            for given in ('https://drive.google.com/drive/folders/abcdefghijklmnopqrstuv',
                          'abcdefghijklmnopqrstuv'):
                self.assertIsNone(caller.folder_refused({'action': 'folder', 'location': given}))
            self.assertIsNone(caller.folder_refused({'action': 'capture', 'kind': 'file'}))
            self.assertIsNotNone(caller.folder_refused({'action': 'folder', 'location': '~/x'}))
        # Another value, or none, is this computer's own caller.
        other = Message()
        other['X-Marketing-Studio-Via'] = 'loopback'
        with caller.answering(other):
            self.assertFalse(caller.remote())
        self.assertFalse(caller.remote())

    def test_a_folder_with_one_document_is_the_deck_s_document(self):
        import base64
        status, found = self.send('document-intake', {'location': self.folder('talk.md')})
        self.assertEqual(status, 200, found)
        self.assertEqual(found['name'], 'talk.md')
        self.assertIn(b'Capacity holds', base64.b64decode(found['content']))
        # More than one is refused, naming them; a phone may not read a folder here.
        status, refused = self.send('document-intake', {'location': self.folder('a.md', 'b.md')})
        self.assertEqual(status, 409)
        self.assertIn('This folder holds more than one document, among them a.md and b.md.',
                      refused['error'])
        from studio_core import source_intake
        status, refused = self.send('document-intake', {'location': self.folder('talk.md')},
                                    remote=True)
        self.assertEqual((status, refused['error']), (403, source_intake.REMOTE))
        status, refused = self.send('document-intake', {'location': 1})
        self.assertEqual(status, 400)

    def test_a_spreadsheet_is_read_as_text_from_a_phone_too(self):
        import base64
        sheets = xlsx_fixture()
        data = base64.b64encode(sheets.workbook(sheets.SAMPLE)).decode()
        status, found = self.send('document-intake', {'file': {'name': 'Plan.xlsx',
                                                               'data': data}}, remote=True)
        self.assertEqual(status, 200, found)
        self.assertEqual(found['name'], 'Plan.xlsx.md')
        self.assertIn('Pipeline', base64.b64decode(found['content']).decode())
        # The deck starts from it as its uploaded document.
        started = self.post('decks', {'form': {**runner_support.FORM, 'flow': 'desk',
                                               'route': 'document', 'source': {
                                                   'kind': 'upload', 'name': found['name']}},
                                      'uploads': {found['name']: found['content']}})
        self.assertTrue(started['path'])


@unittest.skipUnless(test_desk.NODE, 'Node is needed to run the page scripts without a browser')
class DocumentFolderPageTests(test_desk_page.DeskPageCase):
    """The New deck form's "A folder or a spreadsheet", for a deck from a document."""

    def test_a_folder_read_becomes_the_chosen_document_and_starts_the_deck(self):
        read = {'name': 'talk.md', 'content': 'IyBUYWxrCg==', 'bytes': 7, 'said': 'Added 1.'}
        result = self.new_deck([
            {'click': 'A document'}, {'click': 'A folder or a spreadsheet'},
            {'snapshot': 'folder'},
            {'click': 'Read the folder'}, {'snapshot': 'empty'},
            {'fill': 'A folder on this computer, or a Google Drive folder link',
             'value': '/Users/someone/talk'}, {'click': 'Read the folder'},
            {'snapshot': 'read'}, {'fill': 'A short title', 'value': 'Synthetic deck'},
            {'click': 'Start'}],
            **{'POST /api/document-intake': [test_desk.ok(read)]})
        shots = result['snapshots']
        self.assertIn('Or a spreadsheet (.xlsx)', shots['folder']['sheet'])
        self.assertIn('Give a folder path or a Google Drive folder link first.',
                      shots['empty']['sheet'])
        self.assertIn('Chosen: talk.md', shots['read']['sheet'])
        self.assertIn('Upload a file', shots['read']['pressed'])
        posted = self.posts(result)
        self.assertEqual(posted[0], ('/api/document-intake', {'location': '/Users/someone/talk'}))
        body = next(body for address, body in posted if address == '/api/decks')
        self.assertEqual(body['form']['source'], {'kind': 'upload', 'name': 'talk.md'})
        self.assertEqual(body['uploads'], {'talk.md': 'IyBUYWxrCg=='})

    def test_a_refusal_is_said_beside_the_folder(self):
        refused = {'status': 409, 'body': {'error': 'This folder holds 2 documents: a.md, b.md.'}}
        result = self.new_deck([
            {'click': 'A document'}, {'click': 'A folder or a spreadsheet'},
            {'fill': 'A folder on this computer, or a Google Drive folder link', 'value': '/x'},
            {'click': 'Read the folder'}, {'snapshot': 'refused'}],
            **{'POST /api/document-intake': [refused]})
        self.assertIn('This folder holds 2 documents: a.md, b.md.',
                      result['snapshots']['refused']['sheet'])
        self.assertNotIn('Chosen:', result['snapshots']['refused']['sheet'])


class DocumentIntakeBoundTests(test_desk_page.DeskPageCase):
    """#514 review: a folder is read only as far as telling one document from more than one."""

    def test_at_most_two_documents_are_read_from_a_folder(self):
        import tempfile
        from pathlib import Path
        from studio_core import source_intake
        place = Path(tempfile.mkdtemp(prefix='deck-folder-'))
        self.addCleanup(shutil.rmtree, place, True)
        for name in ('a.md', 'b.md', 'c.md', 'd.md'):
            (place / name).write_text(f'# {name}\n')
        real, asked = source_intake.take, []

        def counted(*given, **named):
            asked.append(named)
            return real(*given, **named)

        with mock.patch.object(source_intake, 'take', counted):
            refused = self.post('document-intake', {'location': str(place)}, expect=409)
        self.assertEqual((asked[0]['room'], asked[0]['spare']), (2, 16_000_000))
        self.assertIn('This folder holds more than one document, among them', refused['error'])
