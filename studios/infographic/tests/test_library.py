"""The shared Document Library in Infographic Studio: library documents as context, and the
approved page's text and PDF kept in the library.

Every test uses a disposable library (STUDIOS_LIBRARY), studios config and workspace. The
renderer is the structural fake; no assistant, image provider, research or Google runs.
"""
import contextlib
import io
import json
import shutil
from unittest import mock

from helpers import Isolated
import test_desk_engine as desk
from runner import api, exports, library, sources, studio
from runner.contracts import Invalid
from studio_core import document_library

REVIEW = ['Inspected the actual page, its reading order and conceptual relationships.']


class LibraryCase(Isolated):
    current = desk.DeskEngineTests.current

    def setUp(self):
        super().setUp()
        desk.setup_desk(self)

    def act(self, verb, **values):
        return api.action(self.engine, {'action': verb, 'id': self.ident,
                                        'expected_revision': self.current()['revision'], **values})

    def library(self):
        return document_library.opened(create=True)


class ApprovedExportTests(LibraryCase):
    def approved(self):
        manifest = self.engine.preview(self.ident, expected_revision=self.current()['revision'])
        self.engine.check_after(self.ident, self.engine.manual_review(
            self.ident, manifest['id'], REVIEW, expected_revision=self.current()['revision']),
            expected_revision=self.current()['revision'])
        return self.engine.approve_and_export(self.ident, expected_revision=self.current()['revision'])

    def test_approved_files_keep_their_text_and_pdf_and_drafts_keep_nothing(self):
        self.engine.preview(self.ident, expected_revision=self.current()['revision'])
        self.assertIsNone(document_library.opened(), 'A draft preview keeps nothing in the library.')
        self.assertIsNone(library.status(self.store, self.ident))
        done = self.approved()
        kept = done['library']
        self.assertEqual((kept['state'], kept['export'], kept['revision'], kept['pdf']),
                         ('kept', done['export']['id'], done['page_revision'], 'saved'))
        row = self.library().describe(kept['document'])
        self.assertEqual((row['kind'], row['studio'], row['formats'], row['readable']),
                         ('infographic', 'infographic', ['markdown', 'pdf'], True))
        self.assertEqual(row['project'], {'studio': 'infographic', 'title': 'Restart one instance',
                                          'revision': done['page_revision']})
        text = exports.read(self.store, self.ident, done['export']['id'], 'text')[1]
        pdf = exports.read(self.store, self.ident, done['export']['id'], 'pdf')[1]
        self.assertEqual(self.library().download(kept['document'], 1, 'markdown')[2], text)
        self.assertEqual(self.library().download(kept['document'], 1, 'pdf')[2], pdf)
        self.assertEqual(self.engine.inspect(self.ident)['library']['kept']['document'], kept['document'])

    def test_preparing_or_keeping_again_reuses_the_document_and_never_renders(self):
        done = self.approved()
        renders = self.renderer.call_count
        again = self.act('export', draft=False)
        self.assertEqual(again['id'], done['export']['id'])
        retried = self.act('library-keep', export_id=done['export']['id'])
        self.assertEqual((retried['state'], retried['document'], retried['library_revision']),
                         ('kept', done['library']['document'], 1))
        self.assertEqual(self.renderer.call_count, renders, 'Keeping reads the saved files only.')
        self.assertEqual(self.library().catalog()['total'], 1)

    def test_a_library_failure_keeps_the_approval_and_keep_again_retries_it(self):
        blocked = self.temp / 'library'
        blocked.write_text('not a folder')
        done = self.approved()
        self.assertTrue(done['approved'])
        self.assertIsNotNone(done['export'])
        self.assertEqual(done['library']['state'], 'failed')
        self.assertIn('file', done['library']['problem'])
        self.assertTrue(self.engine.deliveries(self.ident)[0]['approved_current'])
        blocked.unlink()
        renders = self.renderer.call_count
        retried = self.act('library-keep', export_id=done['export']['id'])
        self.assertEqual(retried['state'], 'kept')
        self.assertEqual(self.renderer.call_count, renders)
        self.assertEqual(library.status(self.store, self.ident)['state'], 'kept')

    def test_only_the_current_approved_export_is_kept(self):
        draft = self.engine.preview(self.ident, expected_revision=self.current()['revision'])
        refused = self.act('library-keep', export_id=draft['id'])
        self.assertEqual((refused['state'], refused['problem']), ('failed', library.NOT_APPROVED))
        done = self.approved()
        self.engine.edit_text(self.ident, 'b1_heading', 'One instance', expected_revision=done['revision'])
        stale = self.act('library-keep', export_id=done['export']['id'])
        self.assertEqual(stale['state'], 'failed', 'An edit after approval is not the approved page.')
        self.assertEqual(self.library().describe(done['library']['document'])['revision'], 1)


class ContextTests(LibraryCase):
    def setUp(self):
        super().setUp()
        made = self.library()
        self.note = made.add_upload('capacity.txt', b'Synthetic capacity: 4 instances, one restarts at a time.')
        self.blog = made.retain('blog:synthetic-post', 'blog', 'blog', 'Rolling restarts', '# Rolling\n\nOne at a time.\n')

    def picks(self, *rows):
        return [{'id': row.get('id') or row['document'], 'revision': row['revision']} for row in rows]

    def test_chosen_revisions_become_sources_in_one_revision_and_start_nothing(self):
        before = self.current()
        with mock.patch('runner.research_jobs.Jobs.start') as research, \
                mock.patch('runner.image_jobs.Jobs.execute') as images:
            project = self.act('library', picks=self.picks(self.note, self.blog))
        research.assert_not_called()
        images.assert_not_called()
        self.renderer.assert_not_called()
        self.assertEqual(project['revision'], before['revision'] + 1)
        added = project['sources'][len(before['sources']):]
        self.assertEqual([s['kind'] for s in added], ['handoff', 'handoff'])
        self.assertEqual([s['provenance']['library']['id'] for s in added], [self.note['id'], self.blog['document']])
        self.assertEqual([s['provenance']['studio'] for s in added], ['Marketing Studio', 'Blog Studio'])
        self.assertEqual(sources.read(self.store, project, added[1]), '# Rolling\n\nOne at a time.\n')
        # The upload's original bytes are kept beside its readable text.
        raw = (self.store._project(self.ident) / added[0]['file']).read_bytes()
        self.assertEqual(raw, b'Synthetic capacity: 4 instances, one restarts at a time.')
        # A source change follows the existing input rules: what was built on the old sources goes.
        self.assertEqual((project['facts'], project['scene'], project['approval']), ([], None, None))
        marked = self.engine.inspect(self.ident)['library']['sources']
        self.assertEqual(marked[added[1]['id']], {'id': self.blog['document'], 'revision': 1,
                                                  'head': 1, 'update': False, 'state': 'current',
                                                  'note': None})

    def test_one_refusal_changes_nothing(self):
        with mock.patch.object(document_library.store.source_documents, 'pdf_text', return_value='\f'):
            scan = self.library().add_upload('scan.pdf', b'%PDF-1.4 pictures only')
        before = self.current()
        for picks, words in ((self.picks(self.note, scan), 'cannot be added'),
                             ([{'id': self.note['id'], 'revision': 9}], 'revision'),
                             ([], 'Choose between'),
                             ([{'id': self.note['id']}], 'library ID and revision')):
            with self.subTest(words=words), self.assertRaisesRegex(Invalid, words):
                self.act('library', picks=picks)
            self.assertEqual(self.current(), before)
        self.act('library', picks=self.picks(self.note))
        with self.assertRaisesRegex(Invalid, 'already in this infographic'):
            self.act('library', picks=self.picks(self.note))
        with self.assertRaisesRegex(Invalid, 'changed'):
            api.action(self.engine, {'action': 'library', 'id': self.ident, 'expected_revision': before['revision'],
                                     'picks': self.picks(self.blog)})

    def test_a_document_with_gaps_needs_readable_only_coverage_confirmed(self):
        gappy = {'readable': True, 'text': 'Readable synthetic words.', 'extractor': 'synthetic',
                 'locations': [], 'warnings': ['Page 2 contains no readable text.']}
        with mock.patch.object(document_library.store.source_documents, 'extract', return_value=gappy):
            gaps = self.library().add_upload('gappy.txt', b'Readable synthetic words.')
        self.assertEqual(gaps['gaps'], ['Page 2 contains no readable text.'])
        before = self.current()
        with self.assertRaisesRegex(Invalid, 'extraction gaps'):
            self.act('library', picks=self.picks(gaps))
        self.assertEqual(self.current(), before)
        with self.assertRaisesRegex(Invalid, 'explicitly'):
            self.act('library', picks=self.picks(gaps), acknowledge_warnings='yes')
        project = self.act('library', picks=self.picks(gaps), acknowledge_warnings=True)
        coverage = project['sources'][-1]['coverage']
        self.assertEqual((coverage['warnings'], coverage['acknowledged']),
                         (['Page 2 contains no readable text.'], True))

    def test_use_revision_n_takes_exactly_that_revision_only_when_asked(self):
        project = self.act('library', picks=self.picks(self.note, self.blog))
        source = project['sources'][-1]
        made = self.library()
        self.assertEqual(made.retain('blog:synthetic-post', 'blog', 'blog', 'Rolling restarts',
                                     '# Rolling\n\nTwo at a time.\n')['revision'], 2)
        self.assertEqual(made.retain('blog:synthetic-post', 'blog', 'blog', 'Rolling restarts',
                                     '# Rolling\n\nThree at a time.\n')['revision'], 3)
        self.assertEqual(sources.read(self.store, self.current(), source), '# Rolling\n\nOne at a time.\n',
                         'The pinned copy is read until a newer revision is taken.')
        marked = self.engine.inspect(self.ident)['library']['sources'][source['id']]
        self.assertEqual((marked['head'], marked['update'], marked['state']), (3, True, 'update'))
        taken = self.act('library-update', document=self.blog['document'], revision=2)
        self.assertEqual(len(taken['sources']), len(project['sources']))
        self.assertEqual(taken['sources'][-1]['provenance']['library']['revision'], 2)
        self.assertEqual(sources.read(self.store, taken, taken['sources'][-1]), '# Rolling\n\nTwo at a time.\n')
        for older in (1, 2):
            with self.assertRaisesRegex(Invalid, 'already uses revision 2'):
                self.act('library-update', document=self.blog['document'], revision=older)
        with self.assertRaisesRegex(Invalid, 'the revision to take'):
            self.act('library-update', document=self.blog['document'])

    def test_pinned_sources_keep_working_and_say_why_no_newer_one_is_shown(self):
        project = self.act('library', picks=self.picks(self.blog))
        source = project['sources'][-1]['id']
        # Another computer's library: the document is not in it.
        with mock.patch.dict('os.environ', {'STUDIOS_LIBRARY': str(self.temp / 'teammate-library')}):
            document_library.opened(create=True)
            elsewhere = self.engine.inspect(self.ident)['library']['sources'][source]
        self.assertEqual((elsewhere['state'], elsewhere['head']), ('not-here', None))
        self.assertIn("teammate's computer", elsewhere['note'])
        shutil.rmtree(self.temp / 'library')
        self.assertEqual(sources.read(self.store, project, project['sources'][-1]), '# Rolling\n\nOne at a time.\n')
        gone = self.engine.inspect(self.ident)['library']['sources'][source]
        self.assertEqual((gone['state'], gone['head'], gone['update']), ('no-library', None, False))
        with self.assertRaisesRegex(Invalid, 'no Document Library on this computer'):
            self.act('library-update', document=self.blog['document'], revision=2)

    def test_a_removed_document_offers_no_update(self):
        project = self.act('library', picks=self.picks(self.blog))
        source = project['sources'][-1]
        made = self.library()
        made.retain('blog:synthetic-post', 'blog', 'blog', 'Rolling restarts', '# Rolling\n\nTwo at a time.\n')
        made.hide(self.blog['document'], True)
        marked = self.engine.inspect(self.ident)['library']['sources'][source['id']]
        self.assertEqual((marked['update'], marked['state']), (False, 'removed'))
        self.assertIn('removed from the Document Library', marked['note'])
        self.assertEqual(sources.read(self.store, self.current(), source), '# Rolling\n\nOne at a time.\n')
        made.hide(self.blog['document'], False)
        marked = self.engine.inspect(self.ident)['library']['sources'][source['id']]
        self.assertEqual((marked['update'], marked['state']), (True, 'update'))

    def test_context_is_refused_while_work_runs(self):
        before = self.current()
        running = {'state': 'running', 'action': 'suggest'}
        with self.assertRaisesRegex(Invalid, 'working now'):
            library.choose(self.store, self.ident, self.picks(self.note), expected_revision=before['revision'],
                           activity=running)
        with mock.patch('runner.image_jobs.Jobs.recovery', return_value=[{'state': 'unknown'}]), \
                self.assertRaisesRegex(Invalid, 'working now'):
            self.act('library', picks=self.picks(self.note))
        research = mock.Mock(**{'read.return_value': {'state': 'working'}})
        with self.assertRaisesRegex(Invalid, 'working now'):
            library.update(self.store, self.ident, self.blog['document'], 2,
                           expected_revision=before['revision'], research=research)
        self.assertEqual(self.current(), before)

    def test_the_page_answers_the_library_routes_for_infographic_studio(self):
        from runner import server
        page = server.Page(0, self.store, self.engine)
        found = json.loads(page.write('/api/library', {'filters': {'kind': 'blog'}})[2])
        self.assertEqual([row['title'] for row in found['items']], ['Rolling restarts'])
        page.write('/api/library-filters', {'filters': {'kind': 'blog'}})
        self.assertEqual(self.library().filters('infographic'), {'kind': 'blog'})
        self.assertEqual(self.library().filters('presentation'), {})
        self.assertEqual(self.current()['revision'], 6, 'Browsing changes no infographic.')

    def test_the_command_line_browses_and_adds_without_starting_anything(self):
        def run(*argv):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(studio.main(list(argv)), 0)
            return json.loads(out.getvalue())
        found = run('library-browse', '--kind', 'blog')
        self.assertEqual([(row['id'], row['revision']) for row in found['items']], [(self.blog['document'], 1)])
        picks = self.temp / 'picks.json'
        picks.write_text(json.dumps(self.picks(self.blog)))
        project = run('library', self.ident, '--expected-revision', str(self.current()['revision']), '--file', str(picks))
        self.assertEqual(project['sources'][-1]['provenance']['library']['id'], self.blog['document'])
        self.renderer.assert_not_called()
