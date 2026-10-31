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
        for name in ('../x.md', 'a/b.md', '.hidden.md', 'x.exe', '', None, 'x' * 200 + '.md'):
            with self.assertRaises(library.LibraryError):
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
        with self.assertRaisesRegex(library.LibraryError, '"beta.png" is not a text'):
            made.add_upload('beta.png', b'png')
        with self.assertRaisesRegex(library.LibraryError, '"big.txt" is larger than 8 MB'):
            made.add_upload('big.txt', b'x' * (store.LIMITS['bytes'] + 1))

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
