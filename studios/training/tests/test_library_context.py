"""The shared Document Library in Training Studio: documents a training pins from it, a
newer revision taken only on request, uploads kept there when the person chooses, and a
learner guide or brief marked ready kept there as Markdown.

Every library here is a disposable folder (STUDIOS_LIBRARY, set by runner_support). Nothing
here runs pdftotext, the slides tool, an assistant of its own or the network: research
and writing are the scripted stand-ins every StudioCase uses.
"""
import json
import shutil
from pathlib import Path
from unittest import mock

import helpers  # noqa: F401  puts the runner on the import path
import workspace
from runner_support import StudioCase
from test_runner_deck import DeckCase
from workspace import WorkspaceError

from runner import documents as real_documents
from runner import library
from runner import page as pages
from studio_core import document_library
from studio_core.document_library import context

NOTES = b'# Notes\n\nCapacity holds only when more than one instance is running.\n'


def tiny_workbook():
    """A one-cell synthetic .xlsx, built with zipfile: a file the source editor reads and the
    Document Library does not keep."""
    import io
    import zipfile
    main = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    rel = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    rels = 'xmlns="http://schemas.openxmlformats.org/package/2006/relationships"'
    parts = {
        '_rels/.rels': f'<Relationships {rels}><Relationship Id="r1" Type="{rel}/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        'xl/workbook.xml': f'<workbook {main} xmlns:r="{rel}"><sheets><sheet name="Numbers" sheetId="1" r:id="r1"/></sheets></workbook>',
        'xl/_rels/workbook.xml.rels': f'<Relationships {rels}><Relationship Id="r1" Type="{rel}/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        'xl/worksheets/sheet1.xml': f'<worksheet {main}><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>Synthetic count</t></is></c><c r="B1"><v>12</v></c></row></sheetData></worksheet>',
    }
    held = io.BytesIO()
    with zipfile.ZipFile(held, 'w') as archive:
        for name, text in parts.items():
            archive.writestr(name, text)
    return held.getvalue()


class LibraryCase(StudioCase):
    def setUp(self):
        super().setUp()
        # The real documents module, which pins library revisions; it reads text only here.
        self.engine.documents = real_documents
        self.library = document_library.opened(create=True)

    def offered(self, root):
        return [one['text'] for one in self.engine._sources(root, self.record(root))[1]]


class DeskTests(DeckCase):
    def setUp(self):
        super().setUp()
        self.engine.documents = real_documents
        self.library = document_library.opened(create=True)

    def test_a_desk_training_pins_then_updates_the_research_as_add_a_source_does(self):
        root = self.start(flow='desk', materials=['document', 'brief'], source_scope='supplied-only')
        self.send(root, 'handbook.md')
        self.engine.supply(root, 'done')
        self.to_end(root)
        row = self.library.add_upload('capacity.md', NOTES)
        before = len(self.workers.of('research-result'))
        self.engine.library_add(root, [{'id': row['id'], 'revision': 1}])
        self.assertEqual(len(self.workers.of('research-result')), before)
        self.assertEqual([one['name'] for one in self.view(root)['documents']['later']],
                         ['capacity.md'])
        self.engine.update_research(root)
        self.to_end(root)
        self.assertGreater(len(self.workers.of('research-result')), before)
        self.assertIsNone(self.record(root)['problem'])
        self.assertTrue(any(source['title'] == 'capacity'
                            for source in self.engine._sources(root, self.record(root))[0]))

    def test_row_206_a_public_web_desk_training_takes_a_library_document_unread_until_updated(self):
        # Issue #254: Add from library on a training researched from the public web, as Add
        # a source does: research reads documents from now on, once the person updates it.
        root = self.start(flow='desk')
        self.to_end(root)
        self.assertIsNone(self.record(root)['documents'])
        row = self.library.add_upload('capacity.md', NOTES)
        held = self.library.catalog()['total']
        before = len(self.workers.of('research-result'))
        self.engine.library_add(root, [{'id': row['id'], 'revision': 1}])
        record = self.record(root)
        self.assertTrue(record['research_from']['documents'])
        self.assertTrue(record['research_from']['widened_at'])
        self.assertEqual([one['name'] for one in record['documents']['later']], ['capacity.md'])
        # Pinning starts nothing, uploads nothing and adds nothing to the library.
        self.assertEqual(len(self.workers.of('research-result')), before)
        self.assertEqual(self.library.catalog()['total'], held)
        self.assertEqual(self.engine.view(root)['documents']['later'][0]['name'], 'capacity.md')
        self.assertTrue((root / 'sources/.all-added').is_file())
        self.engine.update_research(root)
        self.to_end(root)
        self.assertGreater(len(self.workers.of('research-result')), before)
        self.assertIsNone(self.record(root)['problem'])
        self.assertTrue(any(source['title'] == 'capacity'
                            for source in self.engine._sources(root, self.record(root))[0]))


class KeepTests(DeckCase):
    @property
    def library(self):
        return document_library.opened()

    def ready(self):
        root = self.start(flow='desk', materials=['document', 'brief'])
        self.to_end(root)
        cards = {card['name']: card for card in self.desk(root)['cards']}
        return root, cards

    def desk(self, root):
        from runner import drafts
        return drafts.view(self.engine, root)

    def test_a_guide_marked_ready_is_kept_as_learners_read_it(self):
        root, cards = self.ready()
        guide = next(name for name, card in cards.items() if card['kind'] == 'document')
        file = root / workspace.artifact(root, workspace.load(root), guide)['file']
        file.write_text('# Guide\n\n## Why\n<!-- covers: O1 -->\nBecause.\n', encoding='utf-8')
        seen = workspace.sha256_file(file)
        self.engine.mark_ready(root, guide, seen)
        kept = library.status(root)['materials'][guide]
        self.assertEqual((kept['state'], kept['revision'], kept['sha256']), ('kept', 1, seen))
        row = self.library.describe(kept['document'])
        self.assertEqual((row['kind'], row['studio'], row['formats']), ('training', 'training', ['markdown']))
        text = self.library.preview(kept['document'])['text']
        self.assertEqual(text, '# Guide\n\n## Why\nBecause.\n')
        self.assertEqual(self.desk(root)['library'][guide], {'state': 'kept', 'revision': 1,
                                                           'document': kept['document']})
        # Nothing kept is shared: the training's record of it is local.
        self.assertFalse(any('library' in line for line in self.log()))
        self.assertIn('sources/', (root.parent / '.gitignore').read_text())
        # Marking ready again with the same words adds no revision; Keep in library again
        # reuses the document.
        self.engine.library_keep(root, guide)
        self.assertEqual(library.status(root)['materials'][guide]['revision'], 1)
        self.assertEqual(self.library.catalog(kind='training')['total'], 1)

    def test_a_failure_is_said_and_kept_again_on_request(self):
        root, cards = self.ready()
        brief = next(name for name, card in cards.items() if card['kind'] == 'brief')
        with mock.patch.object(document_library, 'opened',
                               side_effect=document_library.LibraryError('The library is busy.')):
            self.engine.mark_ready(root, brief, cards[brief]['seen'])
        self.assertEqual(self.desk(root)['library'][brief],
                         {'state': 'failed', 'problem': 'The library is busy.'})
        self.assertEqual(self.desk(root)['cards'][[c['name'] for c in self.desk(root)['cards']].index(brief)]['state'], 'ready')
        self.engine.library_keep(root, brief)
        self.assertEqual(self.desk(root)['library'][brief]['state'], 'kept')

    def test_a_lost_local_record_finds_the_same_library_document(self):
        root, cards = self.ready()
        guide = next(name for name, card in cards.items() if card['kind'] == 'document')
        self.engine.mark_ready(root, guide, cards[guide]['seen'])
        first = library.status(root)
        (root / library.STATUS).unlink()
        self.engine.library_keep(root, guide)
        again = library.status(root)
        self.assertEqual((again['key'], again['materials'][guide]['document']),
                         (first['key'], first['materials'][guide]['document']))
        self.assertEqual(self.library.catalog(kind='training')['total'], 1)

    def test_only_a_ready_guide_or_brief_is_kept(self):
        root, cards = self.ready()
        guide = next(name for name, card in cards.items() if card['kind'] == 'document')
        with self.assertRaisesRegex(WorkspaceError, 'not marked ready'):
            self.engine.library_keep(root, guide)
        plan = next(name for name, card in cards.items() if card['kind'] == 'blueprint')
        with self.assertRaisesRegex(WorkspaceError, 'learner guide or a brief'):
            self.engine.library_keep(root, plan)
        # Nothing of the training's own was kept: only its verified research is, as research.
        found = document_library.opened()
        self.assertEqual(found.catalog(kind='training')['total'] if found else 0, 0,
                         'no guide, brief or plan was kept')


class UploadTests(LibraryCase):
    def test_keep_in_library_keeps_the_upload_once_the_training_took_it(self):
        kept = library.upload('handbook.md', NOTES)
        self.assertEqual((kept['state'], kept['revision'], kept['readable']), ('kept', 1, True))
        again = library.upload('handbook.md', NOTES)
        self.assertEqual(again['document'], kept['document'], 'the same file is one document')
        row = self.library.describe(kept['document'])
        self.assertEqual((row['kind'], row['studio'], row['origin']), ('upload', 'training', 'upload'))
        with mock.patch.object(document_library, 'opened', side_effect=OSError('No room.')):
            self.assertEqual(library.upload('more.md', NOTES), {'state': 'failed', 'problem': 'No room.'})

    def test_a_spreadsheet_kept_from_the_source_editor_is_read_in_the_library_too(self):
        import base64
        import tempfile
        from studio_core.research_sources import Sources
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        store = Sources(Path(folder.name) / '.research-sources')
        draft = library.research_sources(store, {'action': 'create'})
        kept = library.research_sources(store, {
            'action': 'capture', 'id': draft['id'], 'expected': draft['revision'], 'keep': True,
            'kind': 'file', 'name': 'numbers.xlsx', 'content': base64.b64encode(tiny_workbook()).decode()})
        source = kept['sources'][0]
        self.assertEqual((source['status'], source['kind']), ('ready', 'file'))
        self.assertEqual((kept['library_kept']['state'], kept['library_kept']['source'], kept['library_kept']['readable']),
                         ('kept', source['id'], True))
        row = self.library.describe(kept['library_kept']['document'])
        self.assertEqual((row['state'], row['type'], row['studio'], row['formats']),
                         ('readable', 'Excel', 'training', ['markdown', 'original']))
        self.assertEqual(self.library.preview(row['id'])['text'], '# Numbers\nSynthetic count,12\n')
        self.assertEqual(self.library.download(row['id'], 1, 'original')[2], tiny_workbook())
        again = library.research_sources(store, {'action': 'library-keep', 'id': kept['id'],
                                                 'expected': kept['revision'], 'source': source['id']})
        self.assertEqual(again['library_kept']['document'], kept['library_kept']['document'])
        self.assertEqual(self.library.catalog()['total'], 1)

    def test_keep_in_library_keeps_a_file_of_any_type_and_says_when_it_has_no_text(self):
        kept = library.upload('diagram.png', b'\x89PNG synthetic picture')
        self.assertEqual((kept['state'], kept['readable']), ('kept', False))
        row = self.library.describe(kept['document'])
        self.assertEqual((row['state'], row['state_label'], row['type'], row['bytes']), ('kept', 'Kept as a file', 'PNG file', 22))
        self.assertIn('cannot be used as a source', row['problem'])
        self.assertEqual(self.library.matching(), [])
        with self.assertRaisesRegex(Exception, 'cannot be added'):
            self.library.snapshot(row['id'], 1)
        self.assertEqual(library.upload('diagram.png', b'\x89PNG synthetic picture')['document'], kept['document'])
        self.assertEqual(library.upload('../diagram.png', b'x')['state'], 'failed')

    def test_the_source_editor_keeps_an_accepted_file_only_when_asked(self):
        import base64
        import tempfile
        from studio_core.research_sources import Sources
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        store = Sources(Path(folder.name) / '.research-sources')
        draft = library.research_sources(store, {'action': 'create'})
        file = {'kind': 'file', 'name': 'brief.md', 'content': base64.b64encode(NOTES).decode()}
        kept = library.research_sources(store, {'action': 'capture', 'id': draft['id'],
                                                'expected': draft['revision'], 'keep': True, **file})
        self.assertEqual(kept['library_kept']['state'], 'kept')
        self.assertEqual(kept['library_kept']['source'], kept['sources'][0]['id'])
        only = library.research_sources(store, {'action': 'capture', 'id': kept['id'],
                                                'expected': kept['revision'], 'keep': False,
                                                **file, 'name': 'only.md'})
        self.assertNotIn('library_kept', only)
        # A file the draft could not read is not kept.
        broken = library.research_sources(store, {
            'action': 'capture', 'id': only['id'], 'expected': only['revision'], 'keep': True,
            'kind': 'file', 'name': 'scan.docx', 'content': base64.b64encode(b'not a zip').decode()})
        self.assertEqual(broken['sources'][-1]['status'], 'needs-attention')
        self.assertNotIn('library_kept', broken)
        self.assertEqual(self.library.catalog()['total'], 1)
        # Trying again keeps the same document.
        retried = library.research_sources(store, {'action': 'library-keep', 'id': broken['id'],
                                                   'expected': broken['revision'],
                                                   'source': kept['sources'][0]['id']})
        self.assertEqual((retried['library_kept']['document'], self.library.catalog()['total']),
                         (kept['library_kept']['document'], 1))
        failed = library.research_sources(store, {'action': 'library-keep', 'id': broken['id'],
                                                  'expected': broken['revision'],
                                                  'source': broken['sources'][-1]['id']})
        self.assertEqual(failed['library_kept']['state'], 'failed')
        with self.assertRaisesRegex(ValueError, 'Say whether'):
            library.research_sources(store, {'action': 'capture', 'id': draft['id'], 'keep': 'yes'})
        # Without `keep` the editor's requests are the shared component's own.
        self.assertEqual(library.research_sources(store, {'action': 'read', 'id': draft['id']})['id'],
                         draft['id'])

    def test_page_answers_the_library_routes(self):
        for route in (*context.ROUTES, pages.LIBRARY_ADD, pages.LIBRARY_UPDATE, pages.LIBRARY_KEEP):
            self.assertIn(route, pages.WRITES)
        page = pages.RunnerPage(8765, self.engine)
        self.library.add_upload('brief.md', NOTES)
        listed = json.loads(page.write('/api/library', {'filters': {}})[2])
        self.assertEqual((listed['available'], listed['total']), (True, 1))


if __name__ == '__main__':
    import unittest
    unittest.main()
