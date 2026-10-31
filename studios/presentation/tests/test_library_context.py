"""The shared Document Library in Presentation Studio: documents a deck pins from it, a newer
revision taken only on request, and a delivered deck's slide Markdown kept there.

Every library here is a disposable folder (STUDIOS_LIBRARY, set by helpers). Nothing here
runs pdftotext, the slides tool, an assistant or the network.
"""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import runner_support  # noqa: F401  puts the runner on the import path
from runner_support import DeckCase
from workspace import WorkspaceError

from runner import documents, library_keep
from runner import page as pages
from studio_core import document_library
from studio_core.document_library import context


class LibraryCase(DeckCase):
    def setUp(self):
        super().setUp()
        place = tempfile.TemporaryDirectory()
        self.addCleanup(place.cleanup)
        self.place = Path(place.name)
        patcher = mock.patch.dict(os.environ, {
            'STUDIOS_LIBRARY': str(self.place / 'library'),
            'STUDIOS_CONFIG': str(self.place / 'studios-config.json')})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.library = document_library.opened(create=True)


class PinTests(LibraryCase):
    def test_pinned_revision_is_the_decks_own_copy(self):
        brief = self.library.add_upload('brief.md', b'# Brief\n\nCapacity holds with two instances.\n')
        word = self.library.retain('blog:launch', 'blog', 'blog', 'Launch post', '# Launch\n\nIt shipped.\n')
        added = context.pin(documents, self.root, [{'id': brief['id'], 'revision': 1},
                                                   {'id': word['document'], 'revision': 1}])
        self.assertEqual([entry['library']['id'] for entry in added], [brief['id'], word['document']])
        listed = documents.listed(self.root)
        self.assertEqual([entry['title'] for entry in listed], ['brief', 'Launch post'])
        self.assertIn('Capacity holds', documents.text_of(self.root, listed[0]))
        # The research plan reads them as it reads any supplied document.
        plan, offered = documents.sources(self.root)
        self.assertEqual(len(plan), 2)
        self.assertEqual(offered[1]['text'], '# Launch\n\nIt shipped.\n')
        # The deck keeps reading its copy when the library is gone.
        shutil.rmtree(self.library.root)
        self.assertIn('It shipped.', documents.text_of(self.root, documents.listed(self.root)[1]))
        marked = context.marked(documents.listed(self.root))
        self.assertEqual((marked[0]['library_head'], marked[0]['update']), (None, False))

    def test_newer_revision_is_offered_and_taken_only_on_request(self):
        kept = self.library.retain('blog:launch', 'blog', 'blog', 'Launch post', 'First words.\n')
        context.pin(documents, self.root, [{'id': kept['document'], 'revision': 1}])
        self.library.retain('blog:launch', 'blog', 'blog', 'Launch post', 'Second words.\n')
        marked = context.marked(documents.listed(self.root))
        self.assertEqual((marked[0]['library_head'], marked[0]['update']), (2, True))
        self.assertEqual(documents.text_of(self.root, marked[0]), 'First words.\n')
        context.update(documents, self.root, kept['document'])
        listed = documents.listed(self.root)
        self.assertEqual((len(listed), listed[0]['library']['revision']), (1, 2))
        self.assertEqual(documents.text_of(self.root, listed[0]), 'Second words.\n')
        self.assertEqual(sorted(p.name for p in (self.root / documents.FOLDER).iterdir()),
                         sorted(['index.json', Path(listed[0]['file']).name,
                                 Path(listed[0]['original']).name]))
        with self.assertRaisesRegex(document_library.LibraryError, 'newest'):
            context.update(documents, self.root, kept['document'])

    def test_refusals_change_nothing(self):
        good = self.library.add_upload('good.md', b'Words.\n')
        scan = self.library.add_upload('broken.docx', b'not a zip')
        context.pin(documents, self.root, [{'id': good['id'], 'revision': 1}])
        before = (self.root / documents.INDEX).read_text()
        with self.assertRaisesRegex(WorkspaceError, 'already in'):
            context.pin(documents, self.root, [{'id': good['id'], 'revision': 1}])
        with self.assertRaisesRegex(document_library.LibraryError, 'cannot be added'):
            context.pin(documents, self.root, [{'id': scan['id'], 'revision': 1}])
        self.assertEqual((self.root / documents.INDEX).read_text(), before)
        many = [self.library.add_upload(f'n{n}.md', f'Note {n}.\n'.encode()) for n in range(40)]
        with self.assertRaisesRegex(WorkspaceError, 'more'):
            context.pin(documents, self.root, [{'id': one['id'], 'revision': 1} for one in many])
        self.assertEqual((self.root / documents.INDEX).read_text(), before)

    def test_a_name_already_supplied_here_is_kept_apart(self):
        documents.add(self.root, 'brief.md', b'Supplied here.\n')
        row = self.library.add_upload('brief.md', b'From the library.\n')
        added = context.pin(documents, self.root, [{'id': row['id'], 'revision': 1}])
        self.assertEqual(added[0]['name'], 'brief (2).md')
        self.assertNotIn('library', documents.listed(self.root)[0])

    def test_page_answers_the_library_routes_and_desk_changes(self):
        for route in context.ROUTES:
            self.assertIn(route, pages.WRITES)
        self.assertEqual(pages.DESK['/api/desk-library'], ('desk_library', ('picks',)))
        self.assertIn('picks', pages.RAW)
        self.assertEqual(pages.DESK['/api/desk-library-update'][0], 'desk_library_update')
        self.assertEqual(pages.DESK['/api/desk-library-keep'][0], 'desk_library_keep')


class KeepTests(LibraryCase):
    def test_delivered_deck_keeps_its_markdown_and_reports_the_pdf_still_needed(self):
        self.write('outline.md', '# Launch deck\n\n## 1. Why now\n')
        found = library_keep.keep(self.root, {'title': 'Launch deck'}, {'revision': 1})
        self.assertEqual((found['state'], found['revision'], found['pdf']), ('kept', 1, 'needs-export'))
        row = self.library.describe(found['document'])
        self.assertEqual((row['kind'], row['studio'], row['formats'], row['pdf']),
                         ('presentation', 'presentation', ['markdown'], 'needs-export'))
        self.assertEqual(row['project']['revision'], 1)
        self.assertEqual(library_keep.status(self.root)['state'], 'kept')
        # Delivering again with the same slides adds no revision; changed slides add one.
        again = library_keep.keep(self.root, {'title': 'Launch deck'}, {'revision': 2})
        self.assertEqual((again['document'], again['revision']), (found['document'], 1))
        self.write('outline.md', '# Launch deck\n\n## 1. Why now\n\n## 2. What changed\n')
        changed = library_keep.keep(self.root, {'title': 'Launch deck'}, {'revision': 3})
        self.assertEqual((changed['document'], changed['revision']), (found['document'], 2))

    def test_a_failure_is_recorded_and_retried_without_delivering_again(self):
        self.write('outline.md', '# Deck\n')
        with mock.patch.object(document_library, 'opened',
                               side_effect=document_library.LibraryError('The library is busy.')):
            failed = library_keep.keep(self.root, {'title': 'Deck'}, {'revision': 1})
        self.assertEqual((failed['state'], failed['problem']), ('failed', 'The library is busy.'))
        with self.assertRaisesRegex(WorkspaceError, 'not been delivered'):
            library_keep.again(self.root, {'title': 'Deck'})
        self.write('deliver.json', json.dumps({'revision': 1, 'output': 'pptx'}))
        self.assertEqual(library_keep.again(self.root, {'title': 'Deck'})['state'], 'kept')
        with mock.patch.object(document_library, 'opened', side_effect=RuntimeError('boom')):
            self.assertEqual(library_keep.keep(self.root, {}, {'revision': 1})['state'], 'failed')

    def test_no_outline_is_a_visible_failure(self):
        found = library_keep.keep(self.root, {'title': 'Deck'}, {'revision': 1})
        self.assertEqual(found['state'], 'failed')
        self.assertIn('no slide outline', found['problem'])


if __name__ == '__main__':
    unittest.main()
