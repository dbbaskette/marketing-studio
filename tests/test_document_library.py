"""The shared Document Library: its frozen location, records, revisions, lock and catalog.

Every test uses a disposable HOME, studios config and library folder. Nothing here starts a
studio, an assistant, a reader program or the network.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import marketing_studio  # noqa: F401  puts the core on the import path
from studio_core import document_library as library
from studio_core.document_library import context, store

ROOT = Path(__file__).resolve().parents[1]
OPERATION = 'a' * 32


class LibraryCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.config = self.base / 'studios-config.json'
        patcher = mock.patch.dict(os.environ, {'HOME': str(self.base / 'home'),
                                               'STUDIOS_CONFIG': str(self.config)})
        patcher.start()
        self.addCleanup(patcher.stop)
        # These tests find the library from the config, as a person's computer does: a
        # library named for the whole run (STUDIOS_LIBRARY) is set aside until they end.
        os.environ.pop('STUDIOS_LIBRARY', None)

    def write_config(self, values):
        self.config.write_text(json.dumps(values, indent=4) + '\n')

    def made(self):
        return library.opened(create=True)


class LocationTests(LibraryCase):
    def test_browsing_writes_nothing_and_first_use_freezes_the_location(self):
        self.write_config({'schema': 1, 'local': {'root': str(self.base / 'work')},
                           'person': {'name': 'Pat'}, 'unknown': {'kept': True}})
        before = self.config.read_text()
        found = library.location()
        self.assertEqual(found['root'], self.base / 'work' / 'library')
        self.assertFalse(found['saved'])
        self.assertIsNone(library.opened())
        self.assertEqual(self.config.read_text(), before)
        self.assertFalse((self.base / 'work').exists())

        made = self.made()
        self.assertEqual(made.root, self.base / 'work' / 'library')
        values = json.loads(self.config.read_text())
        self.assertEqual(values['library'], {'root': str(self.base / 'work' / 'library')})
        self.assertEqual(values['person'], {'name': 'Pat'})
        self.assertEqual(values['unknown'], {'kept': True})
        self.assertIn('    "person"', self.config.read_text())    # its formatting is kept

        # A later change to the work folder never moves the library.
        values['local']['root'] = str(self.base / 'elsewhere')
        self.config.write_text(json.dumps(values))
        self.assertEqual(library.opened().root, self.base / 'work' / 'library')
        self.assertFalse((self.base / 'work' / 'library' / '..' / '..' / 'elsewhere').exists())

    def test_default_location_and_no_config_file(self):
        self.assertEqual(library.location()['root'], self.base / 'home' / 'Studios' / 'library')
        made = self.made()
        self.assertTrue((made.root / 'library.json').is_file())
        self.assertEqual(json.loads(self.config.read_text())['library']['root'], str(made.root))

    def test_another_studio_saving_first_wins(self):
        other = self.base / 'theirs'
        real = store.studios_config.update

        def racing(changes, guard=None):
            # Another studio saves its location while this one waits for the lock.
            real({'library': {'root': str(other)}})
            return real(changes, guard)
        with mock.patch.object(store.studios_config, 'update', racing):
            made = self.made()
        self.assertEqual(made.root, other)

    def test_a_saved_folder_that_is_gone_is_said_and_not_made_again(self):
        made = self.made()
        made.add_upload('notes.md', b'Words.')
        moved = self.base / 'unplugged'
        made.root.rename(moved)          # a drive not connected, a folder moved away
        before = self.config.read_text()
        with self.assertRaisesRegex(library.LibraryError, 'not there now'):
            self.made()
        self.assertFalse(made.root.exists())
        self.assertEqual(self.config.read_text(), before)
        found = context.answer('/api/library', {}, 'blog')
        self.assertFalse(found['available'])
        self.assertIn('not there now', found['problem'])

    def test_unreadable_config_refuses_and_leaves_it(self):
        self.config.write_text('{not json')
        with self.assertRaises(library.LibraryError):
            self.made()
        self.assertEqual(self.config.read_text(), '{not json')

    def test_refuses_a_linked_or_occupied_folder(self):
        target = self.base / 'target'
        target.mkdir()
        (self.base / 'linked').symlink_to(target)
        self.write_config({'schema': 1, 'library': {'root': str(self.base / 'linked')}})
        with self.assertRaises(library.LibraryError):
            self.made()
        occupied = self.base / 'occupied'
        occupied.mkdir()
        (occupied / 'private.txt').write_text('mine')
        self.write_config({'schema': 1, 'library': {'root': str(occupied)}})
        with self.assertRaises(library.LibraryError):
            self.made()
        self.assertEqual((occupied / 'private.txt').read_text(), 'mine')


class RecordTests(LibraryCase):
    def test_large_unchanged_catalog_is_reused_and_corruption_is_rebuilt(self):
        made = self.made()
        for index in range(65):
            made.add_upload(f'document-{index}.txt', b'word ' * 900)
        expected = made.catalog()
        cache = made._state() / 'catalog.json'
        self.assertGreater(cache.stat().st_size, store.RECORD_LIMIT)
        with mock.patch.object(store, '_atomic', wraps=store._atomic) as write:
            self.assertEqual(made.catalog(), expected)
            write.assert_not_called()
            cache.write_bytes(b'broken')
            self.assertEqual(made.catalog(), expected)
            write.assert_called_once()

    def test_upload_keeps_original_and_markdown_and_retries_idempotently(self):
        made = self.made()
        row = made.add_upload('Field notes.md', b'# Notes\n\nCapacity holds.\n', operation=OPERATION)
        self.assertEqual((row['kind'], row['origin'], row['state']), ('upload', 'upload', 'readable'))
        self.assertEqual(row['formats'], ['markdown', 'original'])
        again = made.add_upload('Field notes.md', b'# Notes\n\nCapacity holds.\n', operation=OPERATION)
        self.assertEqual(again['id'], row['id'])
        self.assertEqual(made.catalog()['total'], 1)
        with self.assertRaisesRegex(library.LibraryError, 'different upload'):
            made.add_upload('Other.md', b'other', operation=OPERATION)
        name, media, data = made.download(row['id'], 1, 'original')
        self.assertEqual((name, media, data), ('Field notes.md', 'text/markdown',
                                               b'# Notes\n\nCapacity holds.\n'))
        self.assertNotIn(str(made.root), json.dumps(made.catalog()))   # no local path shown

    def test_html_and_word_are_converted_without_trusting_markup(self):
        made = self.made()
        row = made.add_upload('page.html', b'<p>One</p><script>alert(1)</script><p>Two</p>')
        text = made.preview(row['id'])['text']
        self.assertIn('One', text)
        self.assertNotIn('alert', text)

    def test_unreadable_and_image_only_documents_are_kept_but_not_selectable(self):
        made = self.made()
        with mock.patch.object(store.source_documents, 'pdf_text', return_value='\f'):
            scan = made.add_upload('scan.pdf', b'%PDF-1.4 pictures only')
        self.assertEqual(scan['state'], 'needs-text')
        self.assertIn('text', scan['problem'])
        broken = made.add_upload('broken.docx', b'not a zip')
        self.assertEqual(broken['state'], 'unreadable')
        for row in (scan, broken):
            with self.assertRaisesRegex(library.LibraryError, 'cannot be added'):
                made.snapshot(row['id'], 1)
        self.assertEqual(made.matching(), [])     # all matching never takes an unreadable one

    def test_refuses_unsafe_names_oversized_and_empty_input(self):
        made = self.made()
        for name in ('../x.md', 'a/b.md', '.hidden.md', 'c:x.md', 'a\\b.png', '.png', '', None,
                     'x' * 200 + '.md', 'x' * 200 + '.bin'):
            with self.assertRaisesRegex(library.LibraryError, 'Add a file by its own name'):
                made.add_upload(name, b'text')
        with self.assertRaises(library.LibraryError):
            made.add_upload('big.txt', b'x' * (store.LIMITS['bytes'] + 1))
        with self.assertRaises(library.LibraryError):
            made.add_upload('empty.txt', b'')
        self.assertEqual(made.catalog()['total'], 0)

    def test_retained_work_reuses_its_document_and_revises_only_on_change(self):
        made = self.made()
        first = made.retain('blog:launch-post', 'blog', 'blog', 'Launch post', '# Launch\n',
                            project={'id': 'launch-post', 'revision': 3})
        self.assertEqual(first['revision'], 1)
        self.assertEqual(made.retain('blog:launch-post', 'blog', 'blog', 'Launch post', '# Launch\n'),
                         {**first, 'changed': False})
        second = made.retain('blog:launch-post', 'blog', 'blog', 'Launch post', '# Launch v2\n')
        self.assertEqual((second['document'], second['revision']), (first['document'], 2))
        # Old revisions stay readable: a project pinned to one keeps it.
        self.assertEqual(made.snapshot(first['document'], 1)['text'], '# Launch\n')
        self.assertEqual(made.snapshot(first['document'], 2)['text'], '# Launch v2\n')
        self.assertEqual(made.heads([first['document'], 'gone-1234']),
                         {first['document']: 2, 'gone-1234': None})
        pdf = made.retain('presentation:deck', 'presentation', 'presentation', 'Deck', '# Deck\n',
                          pdf={'state': 'needs-export', 'reason': 'Not exported yet.'})
        row = made.describe(pdf['document'])
        self.assertEqual((row['pdf'], row['formats']), ('needs-export', ['markdown']))
        with self.assertRaises(library.LibraryError):
            made.retain('presentation:deck', 'presentation', 'presentation', 'Deck', '# Deck\n',
                        pdf={'state': 'saved'})
        with self.assertRaises(library.LibraryError):
            made.retain('presentation:deck', 'presentation', 'presentation', 'Deck', '# Deck\n',
                        pdf={'state': 'saved', 'data': b'not a PDF'})

    def test_a_saved_pdf_is_kept_beside_the_markdown_and_checked_like_it(self):
        made = self.made()
        exported = b'%PDF-1.7\n% the deck\n%%EOF\n'
        first = made.retain('presentation:deck-1', 'presentation', 'presentation', 'Deck',
                            '# Deck\n', pdf={'state': 'needs-export', 'reason': 'Not yet.'})
        saved = made.retain('presentation:deck-1', 'presentation', 'presentation', 'Deck',
                            '# Deck\n', pdf={'state': 'saved', 'data': exported})
        # The same text with a PDF now is a new revision, and the PDF is offered with it.
        self.assertEqual((saved['document'], saved['revision'], saved['changed']),
                         (first['document'], 2, True))
        row = made.describe(saved['document'])
        self.assertEqual((row['pdf'], row['pdf_note'], row['formats']),
                         ('saved', None, ['markdown', 'pdf']))
        self.assertEqual(made.download(saved['document'], 2, 'pdf'),
                         ('deck.pdf', 'application/pdf', exported))
        # The same PDF again adds nothing; another PDF of the same text is a revision.
        self.assertEqual(made.retain('presentation:deck-1', 'presentation', 'presentation',
                                     'Deck', '# Deck\n', pdf={'state': 'saved', 'data': exported}),
                         {**saved, 'changed': False})
        other = made.retain('presentation:deck-1', 'presentation', 'presentation', 'Deck',
                            '# Deck\n', pdf={'state': 'saved', 'data': exported + b'\n'})
        self.assertEqual(other['revision'], 3)
        # Revision 1 never had a PDF; a changed PDF file is refused as any changed file is.
        with self.assertRaisesRegex(library.LibraryError, 'no PDF version'):
            made.download(saved['document'], 1, 'pdf')
        place = made.root / 'documents' / saved['document'] / 'revisions' / '2'
        (place / 'content.pdf').write_bytes(b'%PDF-1.7\n% changed\n')
        with self.assertRaisesRegex(library.LibraryError, 'changed'):
            made.download(saved['document'], 2, 'pdf')

    def test_a_kept_pdf_that_went_missing_or_changed_is_kept_again(self):
        made = self.made()
        exported = b'%PDF-1.7\n% the deck\n%%EOF\n'

        def keep():
            return made.retain('presentation:deck-2', 'presentation', 'presentation', 'Deck',
                               '# Deck\n', pdf={'state': 'saved', 'data': exported})

        first = keep()
        place = made.root / 'documents' / first['document'] / 'revisions' / '1'
        (place / 'content.pdf').unlink()
        healed = keep()
        self.assertEqual((healed['document'], healed['revision'], healed['changed']),
                         (first['document'], 2, True))
        self.assertEqual(made.download(first['document'], 2, 'pdf')[2], exported)
        (made.root / 'documents' / first['document'] / 'revisions' / '2' / 'content.pdf') \
            .write_bytes(b'%PDF-1.7\n% edited\n')
        self.assertEqual(keep()['revision'], 3)
        self.assertEqual(keep(), {'document': first['document'], 'revision': 3, 'changed': False})

    def test_only_a_saved_pdf_may_be_larger_than_markdown_and_originals(self):
        made = self.made()
        large = b'%PDF-1.7\n' + b'0' * 30_000_000 + b'\n%%EOF\n'
        kept = made.retain('presentation:big-deck', 'presentation', 'presentation', 'Big deck',
                           '# Big deck\n', pdf={'state': 'saved', 'data': large})
        self.assertEqual(made.download(kept['document'], 1, 'pdf')[2], large)
        with self.assertRaisesRegex(library.LibraryError, 'longer than the library keeps'):
            made.retain('presentation:big-text', 'presentation', 'presentation', 'Big text',
                        '#' + 'x' * 30_000_000)
        # A 30 MB Markdown file is refused even with a matching hash: only content.pdf is read
        # up to the PDF limit.
        place = made.root / 'documents' / kept['document'] / 'revisions' / '1'
        grown = b'x' * 30_000_000
        (place / 'content.md').write_bytes(grown)
        said = json.loads((place / 'revision.json').read_text())
        said['markdown']['sha256'] = hashlib.sha256(grown).hexdigest()
        (place / 'revision.json').write_text(json.dumps(said))
        with self.assertRaisesRegex(library.LibraryError, 'changed'):
            made.download(kept['document'], 1, 'markdown')
        with self.assertRaisesRegex(library.LibraryError, 'larger than the library keeps'):
            made.retain('presentation:huge', 'presentation', 'presentation', 'Huge', '# Huge\n',
                        pdf={'state': 'saved', 'data': b'%PDF-' + b'0' * (library.LIMITS['pdf'])})
        with self.assertRaises(library.LibraryError):
            made.retain('blog:x', 'presentation', 'blog', 'X', 'text')   # key names another studio

    def test_changed_missing_or_linked_files_are_refused(self):
        made = self.made()
        row = made.add_upload('notes.txt', b'original words')
        place = made.root / 'documents' / row['id'] / 'revisions' / '1'
        (place / 'content.md').write_text('tampered words')
        with self.assertRaisesRegex(library.LibraryError, 'changed'):
            made.snapshot(row['id'], 1)
        (place / 'content.md').unlink()
        (place / 'content.md').symlink_to(self.base / 'elsewhere.md')
        shown = made.preview(row['id'])
        self.assertEqual((shown['state'], shown['text']), ('missing', ''))
        with self.assertRaises(library.LibraryError):
            made.snapshot(row['id'], 1)
        with self.assertRaises(library.LibraryError):
            made.snapshot('../escape', 1)

    def test_interrupted_write_and_damaged_index_are_recovered(self):
        made = self.made()
        row = made.add_upload('notes.txt', b'words here')
        # A revision a crash left half made is never the head.
        pending = made.root / 'documents' / row['id'] / 'revisions' / '.pending-dead'
        pending.mkdir()
        (pending / 'content.md').write_text('half')
        broken = made.root / 'documents' / row['id'] / 'revisions' / '2'
        broken.mkdir()
        (broken / 'content.md').write_text('no record')
        self.assertEqual(made.describe(row['id'])['revision'], 1)
        self.assertEqual(made.catalog()['total'], 1)
        (made.root / '.state' / 'catalog.json').write_text('{damaged')
        self.assertEqual(made.catalog()['total'], 1)
        self.assertEqual(json.loads((made.root / '.state' / 'catalog.json').read_text())['schema'], 1)

    def test_catalog_filters_search_and_paging(self):
        made = self.made()
        made.add_upload('alpha.md', b'Rolling restarts keep capacity.')
        made.retain('blog:b', 'blog', 'blog', 'Beta blog', 'About capacity planning.')
        made.retain('presentation:c', 'presentation', 'presentation', 'Gamma deck', 'Slides.')
        self.assertEqual(made.catalog()['total'], 3)
        self.assertEqual([r['title'] for r in made.catalog(kind='blog')['items']], ['Beta blog'])
        self.assertEqual(made.catalog(studio='presentation')['total'], 1)
        self.assertEqual(made.catalog(query='capacity')['total'], 2)
        page = made.catalog(limit=2)
        self.assertEqual((len(page['items']), page['total']), (2, 3))
        self.assertEqual(len(made.catalog(limit=2, offset=2)['items']), 1)
        with self.assertRaises(library.LibraryError):
            made.catalog(kind='secret')
        with self.assertRaises(library.LibraryError):
            made.catalog(limit=500)
        self.assertEqual(len(made.matching(query='capacity')), 2)

    def test_filters_are_per_studio_and_never_a_selection(self):
        made = self.made()
        made.remember('blog', {'kind': 'presentation'})
        made.remember('presentation', {'studio': 'blog', 'kind': None})
        self.assertEqual(made.filters('blog'), {'kind': 'presentation'})
        self.assertEqual(made.filters('presentation'), {'studio': 'blog'})
        self.assertEqual(made.filters('training'), {})
        with self.assertRaises(library.LibraryError):
            made.remember('blog', {'id': 'something'})


class AnyTypeTests(LibraryCase):
    """The library keeps a file of any type: read where a reader exists, else kept as a file."""

    def test_a_file_with_no_reader_is_kept_whole_marked_and_never_a_source(self):
        made = self.made()
        png = b'\x89PNG\r\n\x1a\n' + bytes(range(256)) * 5
        given = {'photo.png': png, 'bundle.zip': b'PK\x03\x04 not opened', 'Old report.doc': b'\xd0\xcf\x11\xe0 old word',
                 'Launch.key': b'keynote bytes', 'Makefile': b'all:\n\ttrue\n', 'notes.tar gz': b'odd ending',
                 'tool.exe': b'MZ never run', 'data.csv': b'a,b\n1,2\n', 'page.svg': b'<svg onload="alert(1)"/>'}
        rows = {name: made.add_upload(name, data) for name, data in given.items()}
        for name, row in rows.items():
            with self.subTest(name=name):
                self.assertEqual((row['state'], row['state_label'], row['readable']), ('kept', 'Kept as a file', False))
                self.assertEqual(row['problem'], store.KEPT)
                self.assertEqual((row['formats'], row['original_name'], row['bytes']), (['original'], name, len(given[name])))
                self.assertEqual(made.download(row['id'], 1, 'original'), (name, 'application/octet-stream', given[name]))
                with self.assertRaisesRegex(library.LibraryError, 'no Markdown version'):
                    made.download(row['id'], 1, 'markdown')
                with self.assertRaisesRegex(library.LibraryError, 'cannot be added: It is kept as the file it is'):
                    made.snapshot(row['id'], 1)
                shown = made.preview(row['id'])
                self.assertEqual((shown['text'], shown['characters'], shown['state']), ('', 0, 'kept'))
        self.assertEqual(store.KEPT, 'It is kept as the file it is. The library cannot read text from this type of file, '
                         'so it cannot be used as a source. To use its words, add a text, Word, PowerPoint, Excel or PDF version.')
        self.assertEqual({name: row['type'] for name, row in rows.items()}, {
            'photo.png': 'PNG file', 'bundle.zip': 'ZIP file', 'Old report.doc': 'DOC file', 'Launch.key': 'KEY file',
            'Makefile': 'File', 'notes.tar gz': 'File', 'tool.exe': 'EXE file', 'data.csv': 'CSV file', 'page.svg': 'SVG file'})
        # Kept under the library's own name, with its ending only when that is plain.
        kept = lambda name: sorted(p.name for p in (made.root / 'documents' / rows[name]['id'] / 'revisions' / '1').iterdir())
        self.assertEqual(kept('photo.png'), ['original.png', 'revision.json'])
        self.assertEqual(kept('Makefile'), ['original', 'revision.json'])
        self.assertEqual(kept('notes.tar gz'), ['original', 'revision.json'])
        self.assertEqual(os.stat(made.root / 'documents' / rows['tool.exe']['id'] / 'revisions/1/original.exe').st_mode & 0o111, 0,
                         'a kept file is never made runnable')
        # Listed and found, never chosen: all matching leaves every one out.
        self.assertEqual(made.catalog()['total'], len(given))
        self.assertEqual(made.catalog(state='kept')['total'], len(given))
        self.assertEqual([item['title'] for item in made.catalog(query='launch')['items']], ['Launch'])
        self.assertEqual(made.matching(), [])
        self.assertEqual(len(made.matching(readable_only=False)), len(given))
        self.assertEqual(context.answer('/api/library', {}, 'training')['states']['kept'], 'Kept as a file')
        with self.assertRaisesRegex(library.LibraryError, 'cannot be added'):
            context.snapshots([{'id': rows['photo.png']['id'], 'revision': 1}])
        # The same file again is the one already kept, and it is removed and restored like any other.
        again = made.add_upload('photo.png', png)
        self.assertEqual((again['id'], again['already']), (rows['photo.png']['id'], True))
        self.assertTrue(made.hide(rows['photo.png']['id'], True)['hidden'])
        self.assertEqual(made.catalog()['total'], len(given) - 1)
        self.assertFalse(made.hide(rows['photo.png']['id'], False)['hidden'])
        # Its bytes are checked like any other kept file's.
        (made.root / 'documents' / rows['bundle.zip']['id'] / 'revisions/1/original.zip').write_bytes(b'changed')
        with self.assertRaisesRegex(library.LibraryError, 'changed'):
            made.download(rows['bundle.zip']['id'], 1, 'original')

    def test_powerpoint_and_excel_files_are_kept_and_read(self):
        import pptx_fixture
        import xlsx_fixture
        made = self.made()
        deck = made.add_upload('Field deck.pptx', pptx_fixture.deck(pptx_fixture.SAMPLE))
        book = made.add_upload('Pipeline.xlsx', xlsx_fixture.workbook(xlsx_fixture.SAMPLE))
        notes = made.add_upload('notes.markdown', b'# Notes\n\nSynthetic.\n')
        for row, kind in ((deck, 'PowerPoint'), (book, 'Excel'), (notes, 'Markdown')):
            self.assertEqual((row['state'], row['readable'], row['formats'], row['type']), ('readable', True, ['markdown', 'original'], kind))
        said = made.preview(deck['id'])['text']
        self.assertTrue(said.startswith('## Slide 1\n\nSynthetic opening\n\nFirst point.\nSecond\npoint.\n\n## Slide 1 speaker notes\n\nOpening speaker context.'))
        self.assertIn('## Slide 3 speaker notes\n\nClosing speaker context.', said)
        self.assertNotIn('Slide image placeholder', said)
        self.assertEqual(deck['gaps'], ['Images, charts, video and WordArt are not interpreted. Supply their meaningful text or data separately.'])
        self.assertEqual(made.preview(book['id'])['text'], xlsx_fixture.SAMPLE_TEXT)
        self.assertEqual(made.snapshot(book['id'], 1)['name'], 'Pipeline.xlsx')
        self.assertEqual(made.snapshot(deck['id'], 1)['original'], pptx_fixture.deck(pptx_fixture.SAMPLE))
        self.assertEqual(made.download(deck['id'], 1, 'original')[1], 'application/vnd.openxmlformats-officedocument.presentationml.presentation')
        self.assertEqual(made.download(book['id'], 1, 'original')[1], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertEqual(sorted(row['id'] for row in made.matching()), sorted(row['id'] for row in (deck, book, notes)))
        # A file with a reader that cannot be read stays a problem to put right, as before.
        broken = made.add_upload('broken.pptx', b'not a deck')
        self.assertEqual((broken['state'], broken['state_label']), ('unreadable', 'Cannot be read'))
        self.assertIn('could not be read safely', broken['problem'])
        self.assertEqual(made.download(broken['id'], 1, 'original')[2], b'not a deck')

    def test_a_library_kept_before_any_type_opens_unchanged(self):
        # Records and a search index exactly as the library wrote them before: no `kept`
        # state, no index number, rows with no type or size.
        made = self.made()
        folder = made.root / 'documents' / 'field-notes-0123456789'
        place = folder / 'revisions' / '1'
        place.mkdir(parents=True)
        original, markdown = b'# Notes\n\nCapacity holds.\n', b'# Notes\n\nCapacity holds.\n'
        sha = lambda data: __import__('hashlib').sha256(data).hexdigest()
        record = {'schema': 1, 'id': folder.name, 'revision': 1, 'title': 'Field notes', 'kind': 'upload',
                  'origin': 'upload', 'studio': 'marketing', 'key': None, 'project': None, 'author': None,
                  'operation': OPERATION, 'fingerprint': sha(json.dumps(['Field notes.md', sha(original), 'Field notes', 'marketing']).encode()),
                  'original': {'file': 'original.md', 'filename': 'Field notes.md', 'media': 'text/markdown',
                               'bytes': len(original), 'sha256': sha(original)},
                  'markdown': {'file': 'content.md', 'bytes': len(markdown), 'sha256': sha(markdown), 'characters': 26},
                  'pdf': None, 'conversion': {'method': 'utf8-text-v1', 'state': 'readable', 'gaps': [], 'problem': None},
                  'created_at': '2026-10-01T00:00:00+00:00', 'scope': 'local'}
        scan = {**record, 'id': 'scan-0123456789', 'title': 'Scan', 'operation': None, 'fingerprint': 'e' * 64,
                'original': {'file': 'original.pdf', 'filename': 'scan.pdf', 'media': 'application/pdf', 'bytes': 5, 'sha256': sha(b'%PDF-')},
                'markdown': None, 'conversion': {'method': None, 'state': 'needs-text', 'gaps': [], 'problem': None}}
        (place / 'revision.json').write_text(json.dumps(record, indent=2))
        (place / 'original.md').write_bytes(original)
        (place / 'content.md').write_bytes(markdown)
        other = made.root / 'documents' / scan['id'] / 'revisions' / '1'
        other.mkdir(parents=True)
        (other / 'revision.json').write_text(json.dumps(scan, indent=2))
        (other / 'original.pdf').write_bytes(b'%PDF-')
        state = made.root / '.state'
        state.mkdir()
        old_index = {'schema': 1, 'signature': [[folder.name, 1, False], [scan['id'], 1, False]], 'entries': [
            {'id': folder.name, 'revision': 1, 'title': 'STALE ROW FROM THE OLD INDEX', 'kind': 'upload', 'studio': 'marketing',
             'origin': 'upload', 'state': 'readable', 'readable': True, 'search': 'stale', 'updated_at': '2026-10-01'}]}
        (state / 'catalog.json').write_text(json.dumps(old_index))
        before = {path: path.read_bytes() for path in (made.root / 'documents').rglob('*') if path.is_file()}
        opened = library.opened()
        rows = {row['title']: row for row in opened.catalog()['items']}
        self.assertEqual(sorted(rows), ['Field notes', 'Scan'], 'the index is read again from the records')
        self.assertEqual((rows['Field notes']['state'], rows['Field notes']['type'], rows['Field notes']['bytes']), ('readable', 'Markdown', len(original)))
        self.assertEqual((rows['Scan']['state'], rows['Scan']['state_label'], rows['Scan']['type']), ('needs-text', 'Needs text', 'PDF'))
        self.assertEqual(rows['Scan']['problem'], store.NO_TEXT)
        self.assertEqual(opened.preview(folder.name)['text'], '# Notes\n\nCapacity holds.\n')
        self.assertEqual(opened.snapshot(folder.name, 1)['original'], original)
        self.assertEqual(opened.download(folder.name, 1, 'original'), ('Field notes.md', 'text/markdown', original))
        self.assertEqual(opened.download(scan['id'], 1, 'original')[1], 'application/pdf')
        self.assertEqual({path: path.read_bytes() for path in before}, before, 'no record or kept file was rewritten')
        self.assertEqual(json.loads((place / 'revision.json').read_text())['schema'], store.SCHEMA)
        self.assertEqual(store.SCHEMA, 1)
        # The same upload, by its operation ID or by its bytes, is still the document kept before.
        for operation in (OPERATION, 'c' * 32):
            again = opened.add_upload('Field notes.md', original, operation=operation)
            self.assertEqual((again['id'], again['revision']), (folder.name, 1))
        self.assertEqual(opened.describe(folder.name)['revisions'], [1])
        self.assertEqual({path: path.read_bytes() for path in before}, before)
        # A state this code does not know (a record from a later version) reads as it always has.
        later = {**record, 'id': 'later-0123456789', 'title': 'Later', 'conversion': {**record['conversion'], 'state': 'something-new'}}
        after = made.root / 'documents' / later['id'] / 'revisions' / '1'
        after.mkdir(parents=True)
        (after / 'revision.json').write_text(json.dumps(later))
        (after / 'original.md').write_bytes(original)
        (after / 'content.md').write_bytes(markdown)
        self.assertEqual(opened.describe(later['id'])['state'], 'unreadable')

    def test_an_original_only_ever_leaves_as_a_plain_download(self):
        made = self.made()
        page = made.add_upload('page.html', b'<p>One</p><script>alert(1)</script>')
        self.assertEqual(made.download(page['id'], 1, 'original')[1], 'text/html')     # a type the library reads
        picture = made.add_upload('drawing.svg', b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>')
        self.assertEqual(made.download(picture['id'], 1, 'original')[1], 'application/octet-stream')
        # Whatever a record says its media type is, an unknown one goes out as a plain download.
        record = made.root / 'documents' / picture['id'] / 'revisions' / '1' / 'revision.json'
        held = json.loads(record.read_text())
        held['original']['media'] = 'image/svg+xml'
        record.write_text(json.dumps(held))
        self.assertEqual(made.download(picture['id'], 1, 'original')[1], 'application/octet-stream')
        self.assertEqual(made.describe(picture['id'])['state'], 'kept')

    def test_existing_work_keeps_its_original_whatever_its_type(self):
        made = self.made()
        kept = made.adopt(key='blog:synthetic-post', studio='blog', kind='blog', origin='imported', title='Synthetic post',
                          text='Words of the post.\n', original=b'\x89PNG cover', filename='cover.png')
        row = made.describe(kept['document'])
        self.assertEqual((row['state'], row['formats'], row['type']), ('readable', ['markdown', 'original'], 'PNG file'))
        self.assertEqual(made.download(kept['document'], 1, 'original'), ('cover.png', 'application/octet-stream', b'\x89PNG cover'))
        for name in ('../cover.png', '.cover.png', 'a/b.png', None):
            with self.assertRaisesRegex(library.LibraryError, 'has no file the library can keep'):
                made.adopt(key='blog:other-post', studio='blog', kind='blog', origin='imported', title='Other',
                           text='Words.', original=b'x', filename=name)


class ConcurrencyTests(LibraryCase):
    def test_concurrent_processes_never_lose_a_revision(self):
        made = self.made()
        made.retain('blog:shared', 'blog', 'blog', 'Shared', 'start')
        code = ('import sys; sys.path.insert(0, sys.argv[1]);'
                'from studio_core import document_library as l;'
                'lib = l.opened();'
                '[lib.retain("blog:shared", "blog", "blog", "Shared", f"{sys.argv[2]}-{n}") '
                'for n in range(5)]')
        env = {**os.environ}
        children = [subprocess.Popen([sys.executable, '-c', code, str(ROOT / 'core'), name],
                                     env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    for name in ('one', 'two', 'three')]
        for child in children:
            _, errors = child.communicate(timeout=60)
            self.assertEqual(child.returncode, 0, errors.decode())
        ident = made.catalog()['items'][0]['id']
        self.assertEqual(made.describe(ident)['revision'], 16)
        texts = {made.snapshot(ident, n)['text'] for n in range(2, 17)}
        self.assertEqual(len(texts), 15)        # each revision holds its own text


class RouteTests(LibraryCase):
    def test_routes_before_and_after_the_library_exists(self):
        found = context.answer('/api/library', {'filters': {}}, 'blog')
        self.assertFalse(found['available'])
        self.assertFalse(self.config.exists())     # browsing made nothing
        with self.assertRaisesRegex(library.LibraryError, 'nothing in it yet'):
            context.answer('/api/library-document', {'id': 'x'}, 'blog')
        made = self.made()
        row = made.add_upload('notes.md', b'Some words')
        found = context.answer('/api/library', {'filters': {'kind': 'upload'}}, 'blog')
        self.assertEqual([item['id'] for item in found['items']], [row['id']])
        self.assertEqual(found['kinds']['blog'], 'Blog')
        context.answer('/api/library-filters', {'filters': {'kind': 'upload'}}, 'blog')
        self.assertEqual(context.answer('/api/library', {}, 'blog')['remembered'], {'kind': 'upload'})
        preview = context.answer('/api/library-document', {'id': row['id']}, 'blog')
        self.assertEqual(preview['text'], 'Some words\n')
        with self.assertRaises(library.LibraryError):
            context.answer('/api/library', {'filters': {'id': 'x'}}, 'blog')

    def test_pin_validates_every_revision_before_changing_anything(self):
        made = self.made()
        good = made.add_upload('good.md', b'Readable words')
        broken = made.add_upload('broken.docx', b'not a zip')
        calls = []
        fake = mock.Mock(add_snapshots=lambda root, snaps: calls.append(snaps) or snaps)
        with self.assertRaises(library.LibraryError):
            context.pin(fake, self.base, [{'id': good['id'], 'revision': 1},
                                         {'id': broken['id'], 'revision': 1}])
        self.assertEqual(calls, [])
        pinned = context.pin(fake, self.base, [{'id': good['id'], 'revision': 1}])
        self.assertEqual(pinned[0]['text'], 'Readable words\n')
        for bad in ([], [{'id': good['id']}], [{'id': good['id'], 'revision': 1}] * 2,
                    [{'id': good['id'], 'revision': 1, 'extra': 1}]):
            with self.assertRaises(library.LibraryError):
                context.pin(fake, self.base, bad)


class RemoveTests(LibraryCase):
    """Remove from library hides a document; nothing is deleted and Restore undoes it."""

    def files(self, made):
        return sorted(str(path.relative_to(made.root)) for path in (made.root / 'documents').rglob('*')
                      if path.name != 'document.json')

    def test_a_hidden_document_leaves_browsing_and_add_from_library_and_comes_back(self):
        made = self.made()
        kept = made.add_upload('alpha.md', b'Alpha words.')
        other = made.add_upload('beta.md', b'Beta words.')
        before = self.files(made)
        row = made.hide(kept['id'], True)
        self.assertTrue(row['hidden'])
        self.assertEqual(self.files(made), before, 'no revision or file is deleted or changed')
        self.assertEqual([r['id'] for r in made.catalog()['items']], [other['id']])
        self.assertEqual({r['id'] for r in made.catalog(hidden=True)['items']}, {kept['id'], other['id']})
        self.assertEqual(made.matching(), [{'id': other['id'], 'revision': 1}])
        self.assertEqual(made.summary(), {'hidden': 1, 'imported': False})
        with self.assertRaisesRegex(library.LibraryError, 'removed from the library'):
            made.snapshot(kept['id'], 1)
        self.assertEqual(made.heads([kept['id'], other['id']]), {kept['id']: None, other['id']: 1})
        # It can still be previewed and downloaded, to decide whether to restore it.
        self.assertEqual(made.preview(kept['id'])['text'], 'Alpha words.\n')
        self.assertEqual(made.download(kept['id'], 1, 'original')[2], b'Alpha words.')
        # Only Marketing Studio's Library lists it, under Show hidden.
        shown = context.answer('/api/library', {'filters': {}, 'hidden': True}, 'marketing')
        self.assertEqual((shown['total'], shown['hidden']), (2, 1))
        sheet = context.answer('/api/library', {'filters': {}, 'hidden': True}, 'blog')
        self.assertEqual(sheet['total'], 1)
        self.assertNotIn('hidden', sheet)
        self.assertEqual(made.hide(kept['id'], False)['hidden'], False)
        self.assertEqual(made.catalog()['total'], 2)
        self.assertEqual(made.snapshot(kept['id'], 1)['text'], 'Alpha words.\n')
        with self.assertRaises(library.LibraryError):
            made.hide(kept['id'], 'yes')
        with self.assertRaises(library.LibraryError):
            made.hide('../escape', True)

    def test_a_project_that_pinned_it_keeps_working(self):
        made = self.made()
        kept = made.add_upload('alpha.md', b'Alpha words.')
        held = []
        fake = mock.Mock(add_snapshots=lambda root, snaps: held.extend(snaps) or snaps,
                         listed=lambda root: [{'title': 'Alpha', 'library': {'id': kept['id'], 'revision': 1}}])
        context.pin(fake, self.base, [{'id': kept['id'], 'revision': 1}])
        made.hide(kept['id'], True)
        self.assertEqual(held[0]['text'], 'Alpha words.\n')     # the project's own copy
        marked = context.marked(fake.listed(self.base))
        self.assertEqual((marked[0]['library_head'], marked[0]['update']), (None, False))
        with self.assertRaisesRegex(library.LibraryError, 'keeps the revision it pinned'):
            context.update(fake, self.base, kept['id'])
        with self.assertRaisesRegex(library.LibraryError, 'removed from the library'):
            context.pin(fake, self.base, [{'id': kept['id'], 'revision': 1}])

    def test_the_same_file_again_is_already_there_and_restores_a_hidden_one(self):
        made = self.made()
        first = made.add_upload('alpha.md', b'Alpha words.', operation='a' * 32)
        self.assertEqual((first['already'], first['restored']), (False, False))
        again = made.add_upload('alpha.md', b'Alpha words.', operation='b' * 32)
        self.assertEqual((again['id'], again['already']), (first['id'], True))
        retried = made.add_upload('alpha.md', b'Alpha words.', operation='a' * 32)
        self.assertEqual((retried['id'], retried['already']), (first['id'], False))
        self.assertEqual(made.catalog()['total'], 1)
        made.add_upload('alpha.md', b'Other words.')            # a different file is its own
        self.assertEqual(made.catalog()['total'], 2)
        made.hide(first['id'], True)
        back = made.add_upload('alpha.md', b'Alpha words.')
        self.assertEqual((back['id'], back['restored'], back['hidden']), (first['id'], True, False))

    def test_uploading_again_repairs_a_document_whose_files_changed_or_went_missing(self):
        made = self.made()
        first = made.add_upload('alpha.md', b'# Alpha\nhello\n', operation='a' * 32)
        place = made.root / 'documents' / first['id'] / 'revisions' / '1'
        (place / 'content.md').write_text('changed behind the library')
        with self.assertRaisesRegex(library.LibraryError, 'Upload it again'):
            made.snapshot(first['id'], 1)
        made.hide(first['id'], True)
        again = made.add_upload('alpha.md', b'# Alpha\nhello\n', operation='c' * 32)
        self.assertEqual((again['id'], again['revision'], again['already'], again['repaired'], again['restored']),
                         (first['id'], 2, False, True, True))
        self.assertEqual(made.snapshot(first['id'], 2)['text'], '# Alpha\nhello\n')
        # Once whole, the same file is the document already kept, by either operation ID.
        for operation in ('a' * 32, 'c' * 32, 'd' * 32):
            same = made.add_upload('alpha.md', b'# Alpha\nhello\n', operation=operation)
            self.assertEqual((same['id'], same['revision'], same['repaired']), (first['id'], 2, False))
        (made.root / 'documents' / first['id'] / 'revisions' / '2' / 'original.md').unlink()
        retried = made.add_upload('alpha.md', b'# Alpha\nhello\n', operation='c' * 32)
        self.assertEqual((retried['revision'], retried['repaired']), (3, True))
        self.assertEqual(made.catalog()['total'], 1)

    def test_remove_refuses_a_document_with_no_complete_revision(self):
        made = self.made()
        kept = made.add_upload('alpha.md', b'Alpha words.')
        (made.root / 'documents' / kept['id'] / 'revisions' / '1' / 'revision.json').unlink()
        with self.assertRaisesRegex(library.LibraryError, 'no complete revision.*cannot be removed or restored'):
            made.hide(kept['id'], True)

    def test_a_refused_file_is_named(self):
        made = self.made()
        with self.assertRaisesRegex(library.LibraryError, '"big.txt" is larger than 8 MB'):
            made.add_upload('big.txt', b'x' * (store.LIMITS['bytes'] + 1))
        # A file of a type with no reader is held to the same limits, and named the same way.
        with self.assertRaisesRegex(library.LibraryError, '"big.png" is larger than 8 MB'):
            made.add_upload('big.png', b'x' * (store.LIMITS['bytes'] + 1))
        with self.assertRaisesRegex(library.LibraryError, '"empty.zip" is empty'):
            made.add_upload('empty.zip', b'')
        self.assertEqual(made.catalog()['total'], 0)

    def test_a_damaged_document_record_hides_nothing(self):
        made = self.made()
        kept = made.add_upload('alpha.md', b'Alpha words.')
        made.hide(kept['id'], True)
        (made.root / 'documents' / kept['id'] / 'document.json').write_text('{damaged')
        self.assertEqual(made.catalog()['total'], 1)


class HomeLibraryTests(LibraryCase):
    """Marketing Studio's Library screen: upload, browse, preview and download."""

    def setUp(self):
        super().setUp()
        from marketing_studio.launcher import Launcher
        from marketing_studio.page import Home
        data = mock.patch.dict(os.environ, {'MARKETING_STUDIO_DATA': str(self.base / 'data')})
        data.start()
        self.addCleanup(data.stop)
        self.launcher = Launcher()
        self.addCleanup(self.launcher.close)
        self.page = Home(8000, self.launcher)

    def write(self, path, sent):
        return json.loads(self.page.write(path, sent)[2])

    def test_upload_browse_preview_download_and_selects_nothing(self):
        import base64
        from marketing_studio.errors import WorkspaceError
        self.assertFalse(self.write('/api/library', {})['available'])
        self.assertFalse(self.config.exists())
        sent = {'operation': OPERATION, 'name': 'brief.md',
                'content': base64.b64encode(b'# Brief\n\nShip it.').decode()}
        kept = self.write('/api/library-upload', sent)
        self.assertEqual(kept['location'], '~/Studios/library')
        self.assertEqual(self.write('/api/library-upload', sent)['document']['id'], kept['document']['id'])
        listed = self.write('/api/library', {'filters': {'kind': 'upload'}})
        self.assertEqual(listed['total'], 1)
        found = self.write('/api/library-download', {'id': kept['document']['id'], 'revision': 1,
                                                     'format': 'original'})
        self.assertEqual(base64.b64decode(found['content']), b'# Brief\n\nShip it.')
        with self.assertRaises(WorkspaceError):
            self.write('/api/library-upload', {**sent, 'content': 'not base64!'})
        # A file of any type is kept through the same route, and only ever comes back as a download.
        picture = self.write('/api/library-upload', {'operation': 'b' * 32, 'name': 'photo.png',
                                                     'content': base64.b64encode(b'\x89PNG synthetic').decode()})['document']
        self.assertEqual((picture['state'], picture['type'], picture['bytes'], picture['readable']), ('kept', 'PNG file', 14, False))
        sent_back = self.write('/api/library-download', {'id': picture['id'], 'revision': 1, 'format': 'original'})
        self.assertEqual((sent_back['name'], sent_back['media']), ('photo.png', 'application/octet-stream'))
        self.assertEqual(base64.b64decode(sent_back['content']), b'\x89PNG synthetic')
        self.assertEqual(self.write('/api/library', {'filters': {'state': 'kept'}})['total'], 1)
        self.assertTrue(self.write('/api/library-hide', {'id': picture['id'], 'hidden': True})['document']['hidden'])
        self.assertTrue(self.write('/api/library-hide', {'id': picture['id'], 'hidden': False})['document']['id'])
        script = (Path(store.__file__).resolve().parents[1] / 'setup_web' / 'app.js').read_text()
        saved = script[script.index("api('library-download'"):][:700]
        self.assertIn('link.download = found.name', saved, 'a kept file is saved by its name, never opened in the page')
        self.assertNotIn('window.open', saved)
        self.assertNotIn('location', saved)
        form = (Path(store.__file__).resolve().parents[1] / 'setup_web' / 'index.html').read_text()
        self.assertIn('<input id="library-files" class="input" type="file" multiple>', form, 'the picker offers every type')
        self.assertIn('Any type of file, up to 8 MB each.', form)
        with self.assertRaises(WorkspaceError):
            self.write('/api/library', {'filters': {'kind': 'nothing'}})
        self.assertEqual(self.page.body_limit('/api/library-upload', {}), 12_000_000)
        self.assertEqual(self.page.body_limit('/api/library', {}), 64_000)

    def test_remove_from_library_and_restore(self):
        import base64
        from marketing_studio.errors import WorkspaceError
        with self.assertRaisesRegex(WorkspaceError, 'nothing in it yet'):
            self.write('/api/library-hide', {'id': 'x', 'hidden': True})
        sent = {'operation': OPERATION, 'name': 'brief.md',
                'content': base64.b64encode(b'# Brief\n\nShip it.').decode()}
        ident = self.write('/api/library-upload', sent)['document']['id']
        self.assertTrue(self.write('/api/library-hide', {'id': ident, 'hidden': True})['document']['hidden'])
        listed = self.write('/api/library', {'filters': {}})
        self.assertEqual((listed['total'], listed['hidden'], listed['imported']), (0, 1, False))
        self.assertEqual(self.write('/api/library', {'filters': {}, 'hidden': True})['items'][0]['hidden'], True)
        self.assertFalse(self.write('/api/library-hide', {'id': ident, 'hidden': False})['document']['hidden'])
        self.assertEqual(self.write('/api/library', {'filters': {}})['total'], 1)
        with self.assertRaises(WorkspaceError):
            self.write('/api/library-hide', {'id': ident})


if __name__ == '__main__':
    unittest.main()
