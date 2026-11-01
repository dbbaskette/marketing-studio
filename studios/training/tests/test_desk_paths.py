"""Paths the Training Studio desk offers, each working or saying why not (issues #253, #254).

A level's materials download as one ZIP with the index; a Document Library document is
pinned at Start; a training made in conversation is said as such on every list. Every
training is disposable (runner_support), every worker is scripted, and the Document Library
is a disposable folder (STUDIOS_LIBRARY). Nothing reaches Google, an assistant or the network.
"""
import io
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode

import helpers  # noqa: F401  puts the runner on the import path
import desk
import workspace
from runner_support import FORM
from test_runner_deck import PageCase
from workspace import WorkspaceError

import test_desk_chat
import test_runner_team
from runner import documents as real_documents
from runner import drafts, page, pipeline
from studio_core import document_library, research_sources

NOTES = b'# Capacity\n\nCapacity holds only when more than one instance is running.\n'


class LevelDownloadTests(PageCase):
    """Download level 101 (.zip): every material of the level, and the index once written."""

    def setUp(self):
        super().setUp()
        self.root = self.start(materials=['document', 'brief'], levels=['101', '201'])
        self.assertEqual(self.to_end(self.root), [])
        self.path = str(self.root)

    def bundle(self, level, path=None):
        target = '/api/download?' + urlencode({'path': path or self.path, 'bundle': 'level',
                                                'level': level})
        return self.page.answer(target, self.headers(), 'GET')

    def test_a_level_downloads_as_one_zip_named_by_its_level(self):
        before = workspace.person_statuses(self.root, workspace.load(self.root))
        commits = self.git('rev-list', '--count', 'HEAD')
        status, kind, data, headers = self.bundle('101')
        self.assertEqual((status, kind), (200, 'application/zip'))
        self.assertEqual(headers['Content-Disposition'],
                         f'attachment; filename="{self.root.name}-level-101-materials.zip"')
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = archive.namelist()
            guide = archive.read('101-learner-guide.md')
        self.assertEqual(sorted(names), ['101-brief.md', '101-learner-guide.md', '101-plan.md'])
        session = workspace.load(self.root)
        saved = workspace.artifact(self.root, session, 'document@101')['file']
        self.assertEqual(guide, (self.root / saved).read_bytes())
        # Once the index is written, it goes in too, named by the level like the rest.
        (self.root / pipeline.INDEX).write_text('# Rolling restarts\n', encoding='utf-8')
        with zipfile.ZipFile(io.BytesIO(self.bundle('201')[2])) as archive:
            self.assertEqual(sorted(archive.namelist()), ['201-brief.md', '201-index.md',
                                                          '201-learner-guide.md', '201-plan.md'])
            self.assertEqual(archive.read('201-index.md'), b'# Rolling restarts\n')
        self.assertTrue(self.get('drafts', path=self.path)['index_written'])
        # Downloading marks nothing ready and changes nothing.
        self.assertEqual(workspace.person_statuses(self.root, workspace.load(self.root)), before)
        self.assertEqual(self.git('rev-list', '--count', 'HEAD'), commits)

    def test_a_level_it_does_not_have_and_a_wrong_bundle_are_refused(self):
        with self.assertRaises(desk.Refusal) as refused:
            self.bundle('301')
        self.assertEqual(refused.exception.status, 404)
        target = '/api/download?' + urlencode({'path': self.path, 'bundle': 'all', 'level': '101'})
        with self.assertRaises(desk.Refusal) as refused:
            self.page.answer(target, self.headers(), 'GET')
        self.assertEqual(refused.exception.status, 400)
        target = '/api/download?' + urlencode({'path': self.path, 'bundle': 'level', 'level': '101'})
        with self.assertRaises(desk.Refusal) as refused:
            self.page.answer(target, self.headers(token=False), 'GET')
        self.assertEqual(refused.exception.status, 403)


class StartLibraryTests(PageCase):
    """Add from library in New training: a library document is pinned at Start, without
    being uploaded again, and research reads it from the first."""

    def setUp(self):
        super().setUp()
        self.engine.documents = real_documents
        self.library = document_library.opened(create=True)
        self.row = self.library.add_upload('capacity.md', NOTES)

    def editor(self):
        """The sources editor's draft as New training leaves it: the public web only."""
        store = research_sources.Sources(self.space.root / '.research-sources')
        made = store.create()
        made = store.mutate(made['id'], made['revision'], 'configure', external=True)
        return {'id': made['id'], 'expected': made['revision']}

    def body(self, reference, **more):
        return {**{key: value for key, value in FORM.items() if key != 'source_scope'},
                'title': 'Library start', 'flow': 'desk',
                'research_from': {'documents': True, 'sites': [], 'web': True},
                'research_inputs': reference, **more}

    def test_row_205_a_library_document_is_pinned_at_start_and_read_by_research(self):
        reference = self.editor()
        held = self.library.catalog()['total']
        picks = [{'id': self.row['id'], 'revision': 1}]
        with patch.object(self.engine, 'wake'):
            started = self.post('trainings', self.body(reference, library=picks))
        root = Path(started['path'])
        listed = real_documents.listed(root)
        self.assertEqual([(entry['name'], entry['library']['id']) for entry in listed],
                         [('capacity.md', self.row['id'])])
        record = self.engine._load(root)
        self.assertEqual(record['research_from'], {'documents': True, 'sites': [], 'web': True})
        # Nothing waits for documents: research starts with the pinned one.
        self.assertFalse(self.engine.view(root)['documents']['waiting'])
        self.assertNotEqual(self.engine._survey_files(root, record).next.kind, 'documents')
        supplied = self.engine._sources(root, record)[1]
        self.assertTrue(any('more than one instance' in one['text'] for one in supplied))
        # Pinned, not uploaded again: the library has no new document.
        self.assertEqual(self.library.catalog()['total'], held)
        # The same form sent again is the same training.
        with patch.object(self.engine, 'wake'):
            again = self.post('trainings', self.body(reference, library=picks))
        self.assertEqual(again['path'], started['path'])

    def test_row_205_a_pick_that_cannot_be_read_or_without_sources_makes_nothing(self):
        reference = self.editor()
        before = sorted(path.name for path in self.space.root.iterdir())
        with patch.object(self.engine, 'wake'):
            refused = self.post('trainings', self.body(
                reference, library=[{'id': self.row['id'], 'revision': 7}]), expect=409)
        self.assertTrue(refused['error'])
        with self.assertRaisesRegex(WorkspaceError, 'added at the start with its sources'):
            self.engine.start(pipeline.check_form({**FORM, 'flow': 'desk'}),
                              library=[{'id': self.row['id'], 'revision': 1}])
        self.assertEqual(sorted(path.name for path in self.space.root.iterdir()), before)


class ConversationPathsTests(PageCase):
    """A training made in conversation: its desk offers only what a conversation leaves to
    the page, and Home, Trainings and Status say In conversation, as its desk does."""

    WALKTHROUGH = True
    create = test_desk_chat.ConversationTests.create
    submit = test_desk_chat.ConversationTests.submit
    researched = test_desk_chat.ConversationTests.researched
    supply_research = test_desk_chat.ConversationTests.supply_research

    def guide(self):
        from runner_support import DOCUMENT
        from test_desk_chat import BLUEPRINT
        root = self.researched(materials=['document'], title='Ready guide')
        self.submit(root, 'blueprint', 'outline', {'text': BLUEPRINT})
        self.submit(root, 'document', 'text', {'text': DOCUMENT})
        return root

    def test_row_207_its_desk_says_it_is_a_conversation_and_offers_only_mark_ready(self):
        root = self.guide()
        found = self.get('drafts', path=str(root))
        self.assertEqual(found['execution'], 'conversation')
        self.assertEqual({card['name']: card['actions'] for card in found['cards']},
                         {'blueprint': ['ready', 'download'], 'document': ['ready', 'download']})
        # A training the runner drives says so too.
        runner = self.start(materials=['document'])
        self.assertEqual(self.get('drafts', path=str(runner))['execution'], 'runner')

    def test_row_207_a_refused_save_says_why_and_what_to_do(self):
        root = self.guide()
        card = self.get('drafts/card', path=str(root), name='document')
        refused = self.post('drafts/save', {'path': str(root), 'name': 'document',
                                            'part': card['sections'][0]['id'], 'text': 'Typed.',
                                            'seen': card['revision'], 'session': 's1'}, 409)
        self.assertIn('being worked on in conversation', refused['error'])
        self.assertIn('hand it to the runner', refused['error'])

    def test_row_207_home_trainings_and_status_say_in_conversation(self):
        root = self.guide()
        item = next(one for one in self.get('trainings')['trainings']
                    if one['path'] == str(root))
        self.assertEqual(item['run']['execution'], 'conversation')
        self.assertNotEqual(item['state'], 'needs-you')
        self.assertFalse(any(stage['state'] == 'current' for stage in item['stages']))
        self.assertEqual(next(stage for stage in item['stages']
                              if stage['stage'] == 'package')['words'], 'not started')
        status = next(one for one in self.get('status')['runs'] if one['path'] == str(root))
        self.assertEqual(status['execution'], 'conversation')
        self.assertFalse(status['needs'])


class DeskPublishTests(test_runner_team.Team):
    """A finished desk training is published from its desk, as the Published screen says,
    through a disposable team repository."""

    def test_row_208_a_finished_desk_training_is_published_from_its_desk(self):
        with self.be(self.alex):
            root = self.start(materials=['document'])
            self.to_end(root)
            for card in self.ask(self.alex, 'drafts', path=str(root))['cards']:
                if card['state'] == 'draft':
                    self.engine.mark_ready(root, card['name'], seen=card['seen'])
            self.to_end(root)
        self.assertTrue((root / pipeline.INDEX).is_file())
        run = self.ask(self.alex, 'run', path=str(root))
        self.assertTrue(run['finished']['ready'])
        self.assertEqual(run['finished']['index'], pipeline.INDEX)
        self.assertTrue(self.ask(self.alex, 'drafts', path=str(root))['index_written'])
        made = self.ask(self.alex, 'publish', {'path': str(root)})
        self.assertEqual(made, {'revision': 1, 'ready': True, 'shared': True, 'notice': None})
        self.assertEqual(self.tags(), [f'training-studio/trainings/{root.name}/1'])
        published = self.ask(self.alex, 'published')['published']
        self.assertEqual([(one['id'], one['revision'], one['ready']) for one in published],
                         [(root.name, 1, True)])


if __name__ == '__main__':
    unittest.main()
