"""Copy as new: a training's setup and documents, read for the start form to make another
from. Disposable workspaces, the scripted agent and the research stand-in: nothing here
reaches a provider or the network."""
import json
from pathlib import Path

from runner_support import FORM
from test_runner_deck import PageCase
from test_settings_change import NOTES, QUESTIONS, SettingsCase
from runner import copy_setup, pipeline
from studio_core import research_sources
from workspace import WorkspaceError


class CopyCase(SettingsCase):
    def store(self) -> research_sources.Sources:
        return research_sources.Sources(self.space.root / '.research-sources')


class CopyTests(CopyCase):
    def test_the_setup_and_what_research_read_are_copied_into_a_new_draft(self):
        root = self.supplied(research_questions=QUESTIONS, levels=['101'])
        before = (root / 'runner/run.json').read_bytes() if (root / 'runner/run.json').is_file() \
            else json.dumps(self.engine._load(root), sort_keys=True).encode()
        jobs = len(self.workers.jobs)
        found = self.engine.copy_setup(root)
        self.assertEqual(found['title'], 'Rolling restarts copy')
        values = found['values']
        self.assertEqual(values['topic'], FORM['topic'])
        self.assertEqual(values['audience'], FORM['audience'])
        self.assertEqual(values['levels'], ['101'])
        self.assertEqual(values['materials'], ['document'])
        self.assertEqual(values['research_questions'], QUESTIONS)
        self.assertEqual(found['left'], [])
        # A draft of its own, holding the capture: changing it leaves the training's alone.
        draft = found['sources']
        self.assertEqual([source['name'] for source in draft['sources']], ['Reference notes'])
        self.assertFalse(draft['external'])
        shown = self.store().preview(draft['id'], draft['sources'][0]['id'])
        self.assertEqual(shown['text'].strip(), NOTES)
        # The training copied is only read, and nothing is started.
        after = (root / 'runner/run.json').read_bytes() if (root / 'runner/run.json').is_file() \
            else json.dumps(self.engine._load(root), sort_keys=True).encode()
        self.assertEqual(after, before)
        self.assertEqual(len(self.workers.jobs), jobs)

    def test_a_copy_starts_as_a_new_training_from_the_same_documents(self):
        root = self.supplied()
        found = self.engine.copy_setup(root)
        draft = found['sources']
        form = pipeline.check_form({**FORM, 'flow': 'desk', 'materials': ['document'],
                                    'title': found['title'], 'topic': 'Canary releases'})
        started = self.engine.start(form, research_inputs={'id': draft['id'],
                                                           'expected': draft['revision']})
        new = Path(started['path'])
        self.assertNotEqual(new, root)
        self.assertTrue((root / 'intake.md').is_file())
        self.assertIn('Canary releases', (new / 'intake.md').read_text())
        self.assertIn('Rolling restarts on the platform', (root / 'intake.md').read_text())
        kept = json.loads((new / 'sources/research-inputs/manifest.json').read_text())
        self.assertEqual([source['name'] for source in kept['sources']], ['Reference notes'])

    def test_documents_added_since_the_start_come_as_files(self):
        root = self.supplied()
        self.engine.documents.add(root, 'runbook.md', b'# Runbook\n\nDrain one instance first.\n')
        found = self.engine.copy_setup(root)
        names = [source['name'] for source in found['sources']['sources']]
        self.assertEqual(names, ['Reference notes', 'runbook.md'])
        self.assertTrue(all(source['status'] == 'ready' for source in found['sources']['sources']))
        self.assertEqual(found['left'], [])

    def test_a_document_that_cannot_be_read_now_is_said_and_left_out(self):
        root = self.supplied()
        entry = self.engine.documents.add(root, 'runbook.md', b'# Runbook\n\nDrain first.\n')
        (root / entry['original']).write_bytes(b'')
        found = self.engine.copy_setup(root)
        self.assertEqual([source['name'] for source in found['sources']['sources']],
                         ['Reference notes'])
        self.assertEqual(len(found['left']), 1)
        self.assertIn('runbook.md', found['left'][0])
        self.assertIn('Add it again in step 2', found['left'][0])

    def test_captures_that_are_not_here_leave_the_setup_copied(self):
        root = self.supplied()
        manifest = root / 'sources/research-inputs/manifest.json'
        kept = json.loads(manifest.read_text())
        (root / kept['sources'][0]['file']).unlink()
        found = self.engine.copy_setup(root)
        self.assertEqual(found['values']['topic'], FORM['topic'])
        self.assertEqual(found['sources']['sources'], [])
        self.assertIn('could not be copied', found['left'][0])

    def test_a_folder_no_run_drives_is_refused(self):
        with self.assertRaisesRegex(WorkspaceError, 'No run is driving'):
            copy_setup.of(self.engine, self.space.root / 'nothing-here')


class CopyPageTests(CopyCase, PageCase):
    def test_the_page_answers_with_the_setup_and_refuses_what_it_does_not_know(self):
        root = self.supplied()
        found = self.post('training-copy', {'path': str(root)})
        self.assertEqual(found['title'], 'Rolling restarts copy')
        self.assertEqual(len(found['sources']['sources']), 1)
        self.post('training-copy', {'path': str(self.space.root / 'elsewhere')}, expect=403)
