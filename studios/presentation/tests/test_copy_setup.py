"""Copy as new: a deck's setup and material, read for the start form to make another from.
Disposable workspaces and stand-ins: nothing here reaches a provider or the network."""
import base64
import shutil
from pathlib import Path
from unittest import mock

import runner_support
from test_runner_page import PageCase
from runner import copy_setup, documents
from runner.steps import intake
from workspace import WorkspaceError

NOTES = b'# Rolling restarts\n\nDrain one instance, then the next.\n'


class CopyCase(PageCase):
    def quiet_start(self, uploads=None, **changes) -> Path:
        """A deck started and left where the start put it: no step is run."""
        with mock.patch.object(self.engine, 'wake'):
            return self.start(uploads=uploads, **changes)


class CopyTests(CopyCase):
    def test_an_idea_is_copied_with_its_answers_and_the_deck_is_only_read(self):
        root = self.quiet_start(notes='Cover capacity first.', look='pick')
        before = (root / 'run.json').read_bytes()
        found = self.engine.copy_setup(root)
        self.assertEqual(found['title'], 'Rolling restarts copy')
        form = found['form']
        self.assertEqual(form['route'], 'scratch')
        self.assertEqual(form['audience'], runner_support.FORM['audience'])
        self.assertEqual(form['goal'], runner_support.FORM['goal'])
        self.assertEqual(form['minutes'], 20)
        self.assertEqual(form['notes'], 'Cover capacity first.')
        self.assertEqual(form['look'], 'pick')
        self.assertNotIn('flow', form)
        self.assertIsNone(found['upload'])
        self.assertIsNone(found['text'])
        self.assertEqual(found['sources']['sources'], [])
        self.assertEqual(found['left'], [])
        self.assertEqual((root / 'run.json').read_bytes(), before)

    def test_an_uploaded_document_comes_back_before_and_after_it_is_taken_in(self):
        root = self.quiet_start(uploads={'notes.md': NOTES}, route='document',
                                source={'kind': 'upload', 'name': 'notes.md'})
        waiting = self.engine.copy_setup(root)
        self.assertEqual(waiting['upload']['name'], 'notes.md')
        self.assertEqual(base64.b64decode(waiting['upload']['encoded']), NOTES)
        intake.take_document(root, {'kind': 'upload', 'name': 'notes.md', 'data': NOTES})
        shutil.rmtree(root / 'sources/incoming')
        found = self.engine.copy_setup(root)
        self.assertEqual(found['form']['source'], {'kind': 'upload', 'name': 'notes.md'})
        self.assertEqual(base64.b64decode(found['upload']['encoded']), NOTES)
        self.assertEqual(found['upload']['size'], len(NOTES))
        # The document it started from is its material, not a research source of the copy.
        self.assertEqual(found['sources']['sources'], [])
        self.assertEqual(found['left'], [])

    def test_pasted_text_comes_back_as_text(self):
        root = self.quiet_start(route='document',
                                source={'kind': 'paste', 'text': 'The talk, slide by slide.'})
        self.assertEqual(self.engine.copy_setup(root)['text'], 'The talk, slide by slide.')
        intake.take_document(root, {'kind': 'paste', 'text': 'The talk, slide by slide.'})
        shutil.rmtree(root / 'sources/incoming')
        found = self.engine.copy_setup(root)
        self.assertEqual(found['form']['source'], {'kind': 'paste'})
        self.assertIn('The talk, slide by slide.', found['text'])

    def test_a_source_added_on_the_desk_comes_as_a_file_beside_the_document(self):
        root = self.quiet_start(uploads={'notes.md': NOTES}, route='document',
                                source={'kind': 'upload', 'name': 'notes.md'})
        intake.take_document(root, {'kind': 'upload', 'name': 'notes.md', 'data': NOTES})
        documents.add(root, 'runbook.md', b'# Runbook\n\nDrain first.\n')
        found = self.engine.copy_setup(root)
        self.assertEqual([one['name'] for one in found['sources']['sources']], ['runbook.md'])
        self.assertEqual(found['sources']['sources'][0]['status'], 'ready')

    def test_material_that_is_not_here_is_said_and_asked_for_again(self):
        root = self.quiet_start(uploads={'notes.md': NOTES}, route='document',
                                source={'kind': 'upload', 'name': 'notes.md'})
        shutil.rmtree(root / 'sources/incoming')
        found = self.engine.copy_setup(root)
        self.assertIsNone(found['upload'])
        self.assertEqual(len(found['left']), 1)
        self.assertIn('notes.md', found['left'][0])
        self.assertIn('Choose it again in step 1', found['left'][0])

    def test_an_existing_deck_from_a_link_keeps_its_link_and_has_no_sources(self):
        root = self.quiet_start(route='existing', level='polish', research=False,
                                source={'kind': 'google', 'link': 'https://docs.google.com/'
                                        'presentation/d/abc123/edit'})
        found = self.engine.copy_setup(root)
        self.assertEqual(found['form']['level'], 'polish')
        self.assertEqual(found['form']['source']['link'],
                         'https://docs.google.com/presentation/d/abc123/edit')
        self.assertIsNone(found['sources'])

    def test_a_folder_that_is_no_deck_is_refused(self):
        with self.assertRaisesRegex(WorkspaceError, 'no deck'):
            copy_setup.of(self.engine, self.engine.space().root / 'nothing-here')


class CopyPageTests(CopyCase):
    def test_what_research_read_is_copied_into_a_draft_of_its_own(self):
        draft = self.post('research-sources', {'action': 'create'})
        draft = self.post('research-sources', {
            'action': 'capture', 'id': draft['id'], 'expected': draft['revision'],
            'kind': 'text', 'name': 'Reference notes', 'text': 'Capacity holds with two.'})
        with mock.patch.object(self.engine, 'wake'):
            made = self.post('decks', {
                'form': {**runner_support.FORM, 'flow': 'desk', 'research': True},
                'uploads': {},
                'research_inputs': {'id': draft['id'], 'expected': draft['revision']}})
        found = self.post('deck-copy', {'path': made['path']})
        self.assertTrue(found['form']['research'])
        self.assertNotEqual(found['sources']['id'], draft['id'])
        self.assertEqual([one['name'] for one in found['sources']['sources']],
                         ['Reference notes'])
        self.assertFalse(found['sources']['external'])
        self.assertEqual(found['left'], [])

    def test_a_folder_the_page_does_not_know_is_not_found(self):
        self.post('deck-copy', {'path': str(self.engine.space().root / 'elsewhere')},
                  expect=404)
