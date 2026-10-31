"""Brief and source changes on finished work (issue #249): a rename clears nothing, any other
brief change clears the story, page and approval and says so, and an infographic's own kept
export is never a source for itself.

Every test uses a disposable library (STUDIOS_LIBRARY), studios config and workspace. The
renderer is the structural fake; no assistant, image provider, research or Google runs.
"""
import hashlib

from test_library import REVIEW, LibraryCase    # first: its helpers put the runner on the path
from runner import exports, history, library, progress
from runner.contracts import Invalid


class FinishedWorkTests(LibraryCase):
    def approved(self):
        manifest = self.engine.preview(self.ident, expected_revision=self.current()['revision'])
        self.engine.check_after(self.ident, self.engine.manual_review(
            self.ident, manifest['id'], REVIEW, expected_revision=self.current()['revision']),
            expected_revision=self.current()['revision'])
        return self.engine.approve_and_export(self.ident, expected_revision=self.current()['revision'])

    def files(self, export_id):
        return {kind: hashlib.sha256(exports.read(self.store, self.ident, export_id, kind)[1]).hexdigest()
                for kind in exports.FORMATS}

    def brief(self, **changes):
        project = self.current()
        return self.store.edit_brief(self.ident, {**project['brief'], **changes},
                                     expected_revision=project['revision'])

    def test_renaming_keeps_the_story_page_and_approval_and_the_earlier_files(self):
        done = self.approved()
        before, files = self.current(), self.files(done['export']['id'])
        renamed = self.brief(title='Restart one instance at a time')
        self.assertEqual(renamed['revision'], before['revision'] + 1)
        for key in ('sources', 'facts', 'stories', 'selected_story', 'scene', 'brand', 'assets'):
            self.assertEqual(renamed[key], before[key], key)
        # The approval moves to the renamed revision, naming the revision the person approved.
        self.assertEqual((renamed['approval']['revision'], renamed['approval']['carried']),
                         (renamed['revision'], {'from_revision': before['revision'], 'reason': 'rename'}))
        # The checks and the visual review move too, each naming the revision they came from.
        moved = {'from_revision': before['revision'], 'reason': 'rename'}
        self.assertTrue(renamed['checks'] and all(c['carried'] == moved for c in renamed['checks']))
        inspected = self.engine.inspect(self.ident)
        self.assertEqual(inspected['visual_review']['carried'], moved)
        self.assertTrue(inspected['review_checked'])
        self.assertEqual(inspected['roadmap']['stage'], 'export')
        self.assertIn('Renaming kept the approval for revision ' + str(renamed['revision']),
                      inspected['roadmap']['complete'])
        self.assertEqual(inspected['history'][0]['summary'], 'Renamed to “Restart one instance at a time”')
        # The earlier approved files stay downloadable and unchanged.
        earlier = next(d for d in inspected['deliveries'] if d['id'] == done['export']['id'])
        self.assertFalse(earlier['approved_current'])
        self.assertEqual(self.files(done['export']['id']), files)
        # Preparing the files again uses the local renderer only and carries the new title.
        again = self.act('export', draft=False)
        self.assertNotEqual(again['id'], done['export']['id'])
        text = exports.read(self.store, self.ident, again['id'], 'text')[1].decode()
        self.assertTrue(text.startswith('Restart one instance at a time\n'))
        self.assertTrue(next(d for d in self.engine.deliveries(self.ident) if d['id'] == again['id'])['approved_current'])
        kept = library.status(self.store, self.ident)
        self.assertEqual((kept['state'], kept['document'], kept['library_revision']),
                         ('kept', done['library']['document'], 2))
        self.assertEqual(self.library().describe(kept['document'])['title'], 'Restart one instance at a time')

    def test_renaming_twice_still_names_the_revision_the_person_approved(self):
        self.approved()
        approved_at = self.current()['revision']
        self.brief(title='Second title')
        back = self.brief(title='Restart one instance')
        self.assertEqual(back['approval']['carried']['from_revision'], approved_at)
        self.assertTrue(all(c['carried']['from_revision'] == approved_at for c in back['checks']))
        self.assertTrue(self.engine.inspect(self.ident)['review_checked'])
        self.assertEqual(history.entries(self.store, self.ident)[0]['summary'], 'Renamed to “Restart one instance”')

    def test_a_rename_waits_for_pending_image_work(self):
        self.approved()
        project = self.current()
        pending = {**project, 'attempts': [{'state': 'unknown'}]}
        with self.assertRaisesRegex(Invalid, 'Image work needs attention'):
            self.store._rename_locked(pending, 'Another title', project['revision'])
        self.assertEqual(self.current(), project)

    def test_changing_the_audience_clears_the_story_page_and_approval_and_says_so(self):
        done = self.approved()
        before, files = self.current(), self.files(done['export']['id'])
        edited = self.brief(audience='Site reliability engineers')
        self.assertEqual(edited['facts'], before['facts'], 'Captured facts stay.')
        self.assertEqual((edited['stories'], edited['scene'], edited['approval']), ([], None, None))
        self.assertEqual(history.entries(self.store, self.ident)[0]['summary'],
                         'Edited the brief: audience; cleared the story, page and approval')
        self.assertEqual(progress.roadmap(edited, self.engine.deliveries(self.ident))['stage'], 'story')
        self.assertEqual(self.files(done['export']['id']), files)

    def test_a_source_change_names_what_it_cleared(self):
        self.approved()
        source = self.current()['sources'][0]
        self.act('source', data='VXBkYXRlZCBzdXBwbGllZCB0ZXh0Lg==', kind='text', name='Pasted notes',
                 replace_id=source['id'])
        self.assertEqual(history.entries(self.store, self.ident)[0]['summary'],
                         'Added or updated sources; cleared the facts, story, page and approval')

    def test_its_own_kept_export_is_refused_as_a_source(self):
        done = self.approved()
        own = self.engine.inspect(self.ident)['library']['own']
        self.assertEqual(own, done['library']['document'])
        before = self.current()
        with self.assertRaisesRegex(Invalid, 'cannot be a source for itself'):
            self.act('library', picks=[{'id': own, 'revision': 1}])
        self.assertEqual(self.current(), before)
        # Another infographic may use it: only its own export is circular.
        other = self.store.create('Another infographic')
        self.assertIsNone(library.own(self.store, other['id']))
