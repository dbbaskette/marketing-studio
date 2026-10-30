"""Form captures are the document confirmation; fixtures never call a provider."""
from pathlib import Path
from unittest.mock import patch

from test_runner_deck import PageCase
from runner import drafts, pipeline
from runner_support import FORM
from studio_core import research_sources


class SourceStartTests(PageCase):
    def captured_start(self, *, external=False, text='Synthetic training reference.'):
        self.engine.plan_first = True
        store = research_sources.Sources(self.space.root / '.research-sources')
        draft = store.create()
        if text:
            draft = store.mutate(draft['id'], draft['revision'], 'capture',
                                 kind='text', name='Reference notes', text=text)
        if external:
            draft = store.mutate(draft['id'], draft['revision'], 'configure', external=True)
        form = pipeline.check_form({**FORM, 'title': 'Captured training ' + draft['id'],
                                    'flow': 'desk', 'deck_target': None, 'brand': None})
        reference = {'id': draft['id'], 'expected': draft['revision']}
        with patch.object(self.engine, 'wake'):
            first = self.engine.start(form, research_inputs=reference)
        return Path(first['path']), reference, form

    def test_start_confirms_captured_sources_and_shows_them_without_second_intake(self):
        root, reference, form = self.captured_start()
        shown = self.engine.view(root)
        self.assertFalse(shown['documents']['waiting'])
        self.assertEqual([s['name'] for s in shown['documents']['added']], ['Reference notes'])
        self.assertFalse((root / pipeline.ADDED).exists(), 'No legacy confirmation was needed')
        record = self.engine._load(root)
        self.assertNotEqual(self.engine._survey_files(root, record).next.kind, 'documents')
        desk = drafts.view(self.engine, root)
        self.assertEqual(desk['sources']['documents'][0]['name'], 'Reference notes')
        plan, supplied = self.engine._sources(root, record)
        self.assertEqual(len(plan), 1)
        self.assertEqual(supplied[0]['text'], 'Synthetic training reference.\n')
        self.assertEqual(record['research_from'], {'documents': True, 'sites': [], 'web': False})
        with patch.object(self.engine, 'wake'):
            retry = self.engine.start(form, research_inputs=reference)
        self.assertEqual(retry['path'], str(root))

    def test_external_search_without_captures_has_no_document_prompt(self):
        root, _, _ = self.captured_start(external=True, text=None)
        self.assertIsNone(self.engine.view(root)['documents'])
        self.assertTrue(self.engine._load(root)['research_from']['web'])

    def test_missing_or_changed_capture_blocks_research_even_with_legacy_documents(self):
        for missing in (False, True):
            with self.subTest(missing=missing):
                root, _, _ = self.captured_start()
                record = self.engine._load(root)
                file = next((root / 'sources/research-inputs').glob('*.txt'))
                if missing:
                    file.unlink()
                else:
                    file.write_text('Changed outside its captured revision.')
                self.documents.add(root, 'legacy.txt', b'Synthetic older upload.')
                (root / pipeline.ADDED).write_text('Synthetic legacy confirmation')
                self.assertEqual(self.engine._survey_files(root, record).next.kind, 'documents')
                shown = self.engine.view(root)['documents']
                self.assertTrue(shown['waiting'])
                self.assertTrue(any(not s['readable'] and s['problem'] for s in shown['added']))
                self.assertFalse(record['research_from']['web'])
