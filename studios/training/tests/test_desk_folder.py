"""A folder of sources given in a conversation: disposable folders and a stand-in Google
Drive. No network, no assistant and no real studio state."""
import io
import json
import tempfile
from pathlib import Path
from unittest import mock

import helpers  # noqa: F401
from runner_support import FORM
from runner import desk_chat, desk_folder, documents, studio
from studio_core import google_api, research_sources, source_folders
from test_runner_deck import DeckCase
from workspace import WorkspaceError

FOLDER, DOC, SHEET = google_api.FOLDER_MIME, google_api.DOC_MIME, google_api.SHEET_MIME
ROOT = 'synthetic_root_folder_0001'


class StandInDrive:
    """What the Google client answers for one synthetic folder; nothing is fetched."""
    TREE = {ROOT: [{'id': 'doc_plan', 'name': 'Plan', 'mimeType': DOC},
                   {'id': 'file_notes', 'name': 'notes.md', 'mimeType': 'text/markdown', 'size': '21'},
                   {'id': 'form_one', 'name': 'Survey', 'mimeType': 'application/vnd.google-apps.form'},
                   {'id': 'folder_compete', 'name': 'Compete', 'mimeType': FOLDER}],
            'folder_compete': [{'id': 'doc_card', 'name': 'EDB battlecard', 'mimeType': DOC}]}

    def __init__(self):
        self.asked = []

    def entry(self, ident):
        self.asked.append(('entry', ident))
        return {'id': ident, 'name': 'Field kit', 'mimeType': FOLDER, 'trashed': False}

    def children(self, ident, token=None):
        self.asked.append(('children', ident))
        return {'files': self.TREE[ident]}

    def download(self, ident):
        self.asked.append(('download', ident))
        return b'Synthetic notes file.'


def read_document(url, **options):
    ident = url.split('/d/')[1].split('/')[0]
    return {'name': ident, 'kind': 'google-doc', 'origin': url, 'tabs': [], 'selected_tabs': [],
            'raw': ('{"document_id": "' + ident + '"}').encode(),
            'extracted': {'text': 'Synthetic text of ' + ident + '.\n', 'warnings': []}}


class ConversationFolderTests(DeckCase):
    def setUp(self):
        super().setUp()
        self.engine.documents = documents
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.kit = self.base / 'Field kit'
        (self.kit / 'Compete/Battlecards').mkdir(parents=True)
        (self.kit / '.git').mkdir()
        (self.kit / 'Compete/Battlecards/EDB battlecard.md').write_text('Synthetic battlecard.')
        (self.kit / 'Compete/notes.txt').write_text('Synthetic compete notes.')
        (self.kit / 'notes.txt').write_text('Synthetic top notes.')
        (self.kit / 'page.html').write_text('<html><body><p>Synthetic page.</p></body></html>')
        (self.kit / 'picture.png').write_bytes(b'not a document')
        (self.kit / '.git/config.md').write_text('HIDDEN')
        self.form = {**FORM, 'materials': [], 'scope': ['text'], 'source_scope': 'supplied-only'}

    def run_create(self, data):
        output = io.StringIO()
        args = studio.parser().parse_args(['desk', 'create', '--input', '-'])
        with mock.patch('sys.stdin', io.StringIO(json.dumps(data))):
            code = studio.desk_command(args, make=lambda: self.engine, out=output)
        return code, json.loads(output.getvalue())

    def test_a_folder_on_this_computer_becomes_the_trainings_own_documents(self):
        with mock.patch.object(google_api, 'Client', side_effect=AssertionError('a local folder asks nothing of Google')):
            code, result = self.run_create({**self.form, 'folder': str(self.kit)})
        self.assertEqual(code, 0)
        root = Path(result['path'])
        kept = {entry['name']: entry for entry in documents.listed(root)}
        self.assertEqual(sorted(kept), ['Compete - Battlecards - EDB battlecard.md', 'Compete - notes.txt', 'notes.txt', 'page.html'])
        self.assertTrue(all(entry['readable'] for entry in kept.values()))
        self.assertEqual((root / kept['page.html']['original']).read_bytes(), (self.kit / 'page.html').read_bytes())
        said = result['folder']
        self.assertEqual((said['where'], said['title'], said['added'], said['hidden']), ('local', 'Field kit', 4, 1))
        self.assertEqual(said['skipped'], [{'name': 'picture.png', 'code': 'unsupported', 'reason': 'Not a type that can be read.'}])
        self.assertEqual([(row['name'], row['from']) for row in said['documents']], [
            ('notes.txt', 'notes.txt'), ('page.html', 'page.html'), ('Compete - notes.txt', 'Compete/notes.txt'),
            ('Compete - Battlecards - EDB battlecard.md', 'Compete/Battlecards/EDB battlecard.md')])
        sources = str(desk_chat.context(self.engine, root, 'research-plan')['inputs']['sources'])
        for text in ('Synthetic battlecard.', 'Synthetic compete notes.', 'Synthetic top notes.', 'Synthetic page.'):
            self.assertIn(text, sources)
        self.assertNotIn('HIDDEN', sources)
        self.assertNotIn(str(self.base), json.dumps(result['folder']), 'the path on this computer is not repeated')
        self.assertEqual(self.workers.jobs, [])

    def test_a_google_drive_folder_is_read_and_google_files_are_kept_as_their_text(self):
        drive = StandInDrive()
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        store = research_sources.Sources(Path(temp.name) / 'sources', google=read_document, drive=lambda account: drive)
        found, said = desk_folder.uploads('https://drive.google.com/drive/folders/' + ROOT + '?lfhs=2',
                                          room=desk_chat.MOST_UPLOADS, spare=desk_chat.UPLOAD_BYTES, store=store)
        self.assertEqual(found, {'notes.md': b'Synthetic notes file.', 'Plan.md': b'Synthetic text of doc_plan.\n',
                                 'Compete - EDB battlecard.md': b'Synthetic text of doc_card.\n'})
        self.assertEqual((said['where'], said['title'], said['added']), ('drive', 'Field kit', 3))
        self.assertEqual({row['name']: row['origin'] for row in said['documents']}, {
            'notes.md': 'https://drive.google.com/file/d/file_notes/view',
            'Plan.md': 'https://docs.google.com/document/d/doc_plan/edit',
            'Compete - EDB battlecard.md': 'https://docs.google.com/document/d/doc_card/edit'})
        self.assertEqual([row['code'] for row in said['skipped']], ['unsupported'])
        self.assertIn(('children', 'folder_compete'), drive.asked)
        root = Path(desk_chat.create(self.engine, self.form, found)['path'])
        self.assertEqual(sorted(entry['name'] for entry in documents.listed(root)), ['Compete - EDB battlecard.md', 'Plan.md', 'notes.md'])
        self.assertIn('Synthetic text of doc_card.', str(desk_chat.context(self.engine, root, 'research-plan')['inputs']['sources']))

    def test_a_larger_folder_is_cut_at_what_a_training_takes_and_every_one_left_is_named(self):
        found, said = desk_folder.uploads(str(self.kit), room=2, spare=desk_chat.UPLOAD_BYTES, taken={'NOTES.txt': b''})
        self.assertEqual(list(found), ['notes (2).txt', 'page.html'])
        over = [row for row in said['skipped'] if row['code'] == 'over-limit']
        self.assertEqual([row['name'] for row in over], ['Compete/notes.txt', 'Compete/Battlecards/EDB battlecard.md'])
        self.assertEqual(over[0]['reason'], 'Over the limit. A training started in a conversation takes 40 documents. '
                         'Give a smaller folder for the rest.')
        self.assertEqual((said['again'], said['next']), (False, 'A training started in a conversation takes 40 documents. '
                                                         'Give a smaller folder for the rest.'))
        found, said = desk_folder.uploads(str(self.kit), room=40, spare=30)
        self.assertEqual(list(found), ['notes.txt'])
        heavy = [row for row in said['skipped'] if row['code'] == 'over-limit']
        self.assertEqual(len(heavy), 3)
        self.assertEqual(heavy[0]['reason'], 'Over the limit. A training started in a conversation takes 64 MB of documents in all.')
        self.assertEqual((said['added'], said['skipped_count'], said['reasons']), (1, 4, {'unsupported': 1, 'over-limit': 3}))
        self.assertEqual(said['next'], 'A training started in a conversation takes 64 MB of documents in all. '
                         'Give a smaller folder for the rest.')
        ticks = iter([0, 0] + [10_000] * 20)
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        slow = research_sources.Sources(Path(temp.name) / 'sources', clock=lambda: next(ticks))
        found, said = desk_folder.uploads(str(self.kit), room=40, spare=desk_chat.UPLOAD_BYTES, store=slow)
        self.assertEqual((list(found), said['reasons'].get('out-of-time'), said['again']), (['notes.txt'], 3, False))
        self.assertEqual(said['next'], 'Not every document was read in time. Create the work again with the same folder '
                         'to read them all.')
        whole = desk_folder.uploads(str(self.kit), room=40, spare=desk_chat.UPLOAD_BYTES)[1]
        self.assertEqual((whole['added'], whole['next']), (4, None))
        self.assertEqual((desk_chat.MOST_UPLOADS, desk_chat.UPLOAD_BYTES), (documents.LIMITS['files'], 64_000_000))

    def test_a_name_says_where_a_document_was_found_and_is_always_a_plain_file_name(self):
        self.assertEqual(desk_folder.flat('Compete/Battlecards/EDB: battle card.pdf', set()), 'Compete - Battlecards - EDB- battle card.pdf')
        long = desk_folder.flat('a' * 100 + '/' + 'b' * 100 + '/.c‮\n.md', set())
        self.assertEqual(long, 'b' * 100 + ' - c.md')
        self.assertLessEqual(len(desk_folder.flat('x/' + 'y' * 300 + '.pdf', {'z'})), documents.NAME)
        self.assertEqual(desk_folder.flat('Plan.md', {'plan.md', 'plan (2).md'}), 'Plan (3).md')

    def test_nothing_is_read_or_made_when_the_folder_cannot_be_used(self):
        before = sorted(p.name for p in self.space.root.iterdir())
        with mock.patch.object(desk_folder, 'uploads', side_effect=AssertionError('nothing is scanned')):
            with self.assertRaisesRegex(WorkspaceError, 'Explicitly select supplied documents'):
                self.run_create({**self.form, 'source_scope': 'public-web', 'folder': str(self.kit)})
        empty = self.base / 'empty'; empty.mkdir()
        (empty / 'picture.png').write_bytes(b'x')
        with self.assertRaisesRegex(WorkspaceError, 'No document in this folder could be added, so nothing was created. '
                                    'picture.png: Not a type that can be read.'):
            self.run_create({**self.form, 'folder': str(empty)})
        with self.assertRaisesRegex(WorkspaceError, 'was not found on this computer'):
            self.run_create({**self.form, 'folder': str(self.base / 'missing')})
        with self.assertRaisesRegex(WorkspaceError, 'starts with https://drive.google.com/drive/folders/'):
            self.run_create({**self.form, 'folder': 'https://docs.google.com/document/d/synthetic_document_1/edit'})
        self.assertEqual(sorted(p.name for p in self.space.root.iterdir()), before)
        self.assertEqual(self.workers.jobs, [])

    def test_the_command_says_when_it_uses_the_network(self):
        said = ' '.join(studio.DESK_HELP['create'].split())
        self.assertIn('Only a Google Drive folder uses the network', said)
        self.assertIn('only because the form names it', said)
        self.assertEqual(source_folders.location(str(self.kit))[0], 'local')
