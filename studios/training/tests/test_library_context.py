"""The shared Document Library in Training Studio: documents a training pins from it, a
newer revision taken only on request, uploads kept there when the person chooses, and a
learner guide or brief marked ready kept there as Markdown.

Every library here is a disposable folder (STUDIOS_LIBRARY, set by runner_support). Nothing
here runs pdftotext, the slides tool, an assistant of its own or the network: research
and writing are the scripted stand-ins every StudioCase uses.
"""
import json
import shutil
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


class LibraryCase(StudioCase):
    def setUp(self):
        super().setUp()
        # The real documents module, which pins library revisions; it reads text only here.
        self.engine.documents = real_documents
        self.library = document_library.opened(create=True)

    def waiting(self):
        """A saved training researched from documents alone, waiting for them."""
        root = self.saved_start(source_scope='supplied-only')
        self.assertTrue(self.view(root)['documents']['waiting'])
        return root

    def researched(self):
        """The same training once its documents are all added and its research planned."""
        root = self.waiting()
        self.engine.supply(root, 'add', 'handbook.txt', b'Capacity holds with two.\n')
        self.engine.supply(root, 'done')
        self.to_end(root)
        self.assertFalse(self.view(root)['documents']['waiting'])
        return root

    def offered(self, root):
        return [one['text'] for one in self.engine._sources(root, self.record(root))[1]]


class WaitingTests(LibraryCase):
    def test_pinned_while_waiting_is_read_with_the_rest_and_starts_nothing(self):
        root = self.waiting()
        row = self.library.add_upload('brief.md', NOTES, studio='blog')
        jobs, commits = len(self.workers.jobs), self.log()
        shown = self.engine.library_add(root, [{'id': row['id'], 'revision': 1}])['documents']
        # Pinning asks nothing of an assistant and commits nothing: the documents are local.
        self.assertEqual((len(self.workers.jobs), self.log()), (jobs, commits))
        self.assertTrue(shown['waiting'])
        self.assertEqual(shown['added'][0]['library'], {'id': row['id'], 'revision': 1})
        self.assertEqual((shown['added'][0]['title'], shown['added'][0]['update']), ('brief', False))
        self.assertNotIn('later', shown)
        self.engine.supply(root, 'done')
        self.assertIn('Capacity holds only when', ''.join(self.offered(root)))
        # The training reads its own copy when the library is gone.
        shutil.rmtree(self.library.root)
        self.assertIn('Capacity holds only when', ''.join(self.offered(root)))

    def test_a_newer_revision_is_said_and_taken_only_when_asked(self):
        root = self.waiting()
        kept = self.library.retain('blog:launch', 'blog', 'blog', 'Launch post', 'First words.\n')
        self.engine.library_add(root, [{'id': kept['document'], 'revision': 1}])
        self.library.retain('blog:launch', 'blog', 'blog', 'Launch post', 'Second words.\n')
        added = self.view(root)['documents']['added'][0]
        self.assertEqual((added['update'], added['library_head']), (True, 2))
        entry = real_documents.listed(root)[0]
        self.assertEqual(real_documents.text_of(root, entry), 'First words.\n')
        added = self.engine.library_update(root, kept['document'])['documents']['added'][0]
        self.assertEqual((added['library']['revision'], added['update']), (2, False))
        self.assertEqual(real_documents.text_of(root, real_documents.listed(root)[0]),
                         'Second words.\n')
        with self.assertRaisesRegex(WorkspaceError, 'newest'):
            self.engine.library_update(root, kept['document'])

    def test_refusals_change_nothing(self):
        row = self.library.add_upload('brief.md', NOTES)
        picks = [{'id': row['id'], 'revision': 1}]
        # Research that does not read documents takes none, and is not widened to.
        web = self.saved_start(title='Web only')
        with self.assertRaisesRegex(WorkspaceError, 'does not read documents'):
            self.engine.library_add(web, picks)
        self.assertEqual(real_documents.listed(web), [])
        self.assertIsNone(self.record(web)['documents'])
        # A job running keeps the documents it started with.
        root = self.waiting()
        self.engine._run(root).busy = True
        with self.assertRaisesRegex(WorkspaceError, 'job that is running'):
            self.engine.library_add(root, picks)
        self.engine._run(root).busy = False
        self.assertEqual(real_documents.listed(root), [])
        # An unreadable revision cannot be chosen, and one refusal adds nothing.
        scan = self.library.add_upload('broken.docx', b'not a zip')
        with self.assertRaisesRegex(WorkspaceError, 'cannot be added'):
            self.engine.library_add(root, [*picks, {'id': scan['id'], 'revision': 1}])
        self.assertEqual(real_documents.listed(root), [])


class LaterTests(LibraryCase):
    def test_pinned_after_the_research_waits_for_the_research_to_be_updated(self):
        root = self.researched()
        row = self.library.add_upload('brief.md', NOTES)
        jobs = len(self.workers.jobs)
        shown = self.engine.library_add(root, [{'id': row['id'], 'revision': 1}])['documents']
        self.assertEqual([one['name'] for one in shown['later']], ['brief.md'])
        self.assertIn('update_price', shown)
        self.assertEqual(len(self.workers.jobs), jobs, 'nothing is researched yet')
        self.assertNotIn('Capacity holds only when', ''.join(self.offered(root)))
        self.assertTrue(self.log()[-1].endswith('not read until the research is updated'))
        # Only Update the research reads it.
        with mock.patch.object(self.engine, 'carry_on'):
            self.engine.supply(root, 'update')
        self.assertEqual(self.record(root)['documents']['later'], [])
        self.assertIn('Capacity holds only when', ''.join(self.offered(root)))

    def test_a_newer_revision_after_the_research_waits_too(self):
        root = self.researched()
        kept = self.library.retain('blog:launch', 'blog', 'blog', 'Launch post', 'First.\n')
        self.engine.library_add(root, [{'id': kept['document'], 'revision': 1}])
        with mock.patch.object(self.engine, 'carry_on'):
            self.engine.supply(root, 'update')
        self.assertIn('First.\n', self.offered(root))
        self.library.retain('blog:launch', 'blog', 'blog', 'Launch post', 'Second.\n')
        later = self.engine.library_update(root, kept['document'])['documents']['later']
        self.assertEqual(len(later), 1)
        self.assertNotIn('Second.\n', self.offered(root))
        self.assertNotIn('First.\n', self.offered(root))


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

    def test_a_desk_training_that_reads_no_documents_is_not_widened(self):
        root = self.start(flow='desk')
        self.to_end(root)
        row = self.library.add_upload('capacity.md', NOTES)
        with self.assertRaisesRegex(WorkspaceError, 'Add a source reads documents too'):
            self.engine.library_add(root, [{'id': row['id'], 'revision': 1}])
        self.assertIsNone(self.record(root)['documents'])


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
        self.assertEqual(self.desk(root)['library'][guide], {'state': 'kept', 'revision': 1})
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

    def test_only_a_ready_guide_or_brief_is_kept(self):
        root, cards = self.ready()
        guide = next(name for name, card in cards.items() if card['kind'] == 'document')
        with self.assertRaisesRegex(WorkspaceError, 'not marked ready'):
            self.engine.library_keep(root, guide)
        plan = next(name for name, card in cards.items() if card['kind'] == 'blueprint')
        with self.assertRaisesRegex(WorkspaceError, 'learner guide or a brief'):
            self.engine.library_keep(root, plan)
        self.assertIsNone(document_library.opened(), 'nothing was kept, so no library was made')


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

    def test_the_page_keeps_only_what_the_person_chose_to(self):
        root = self.waiting()
        page = pages.RunnerPage(8765, self.engine)
        import base64
        content = base64.b64encode(NOTES).decode()
        only = page.supplied({'path': str(root), 'action': 'add', 'name': 'one.md',
                              'content': content, 'keep': False})
        self.assertNotIn('library_kept', only)
        both = page.supplied({'path': str(root), 'action': 'add', 'name': 'two.md',
                              'content': content, 'keep': True})
        self.assertEqual(both['library_kept']['state'], 'kept')
        self.assertEqual(self.library.catalog()['total'], 1)
        self.assertEqual([one['name'] for one in both['documents']['added']], ['one.md', 'two.md'])
        self.assertNotIn('library', both['documents']['added'][1], 'kept, not pinned')
        import desk
        with self.assertRaises(desk.Refusal):
            page.supplied({'path': str(root), 'action': 'add', 'name': 'three.md',
                           'content': content, 'keep': 'yes'})
        # A refused upload is not kept in the library either.
        with self.assertRaises(WorkspaceError):
            page.supplied({'path': str(root), 'action': 'add', 'name': 'two.md',
                           'content': content, 'keep': True})
        self.assertEqual(self.library.catalog()['total'], 1)

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
