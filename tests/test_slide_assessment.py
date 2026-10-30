"""Shared deck review adapter and new-run checkpoint contracts."""
import json
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'core'))
from studio_core import deck_content, slide_assessment

class AssessmentTests(unittest.TestCase):
    def test_complete_matrix_agrees_with_every_negative_finding_and_legacy_wire(self):
        with tempfile.TemporaryDirectory() as folder:
            review = {'deck': 'exact-render', 'preview': folder, 'slides': [
                {'id': 's1', 'number': 1, 'title': 'First', 'image': 'first.png'},
                {'id': 's2', 'number': 2, 'title': 'Second', 'image': 'second.png'}]}
            findings = [{'slide': 's2', 'question': 2, 'severity': 'major', 'note': 'This label overlaps the diagram.', 'fix': None}]
            rows = slide_assessment.coverage(review, findings, ['One', 'Two'], lambda image: image.encode())
            self.assertEqual([r['answers'] for r in rows], [[True, True], [True, False]])
            for schema in (1, 2):
                Path(folder, 'critic.json').write_text(json.dumps({'schema': schema}))
                answer = slide_assessment.payload(review, findings, ['s2'], rows)
                self.assertEqual('slides' in answer, schema == 2)
                if schema == 2:
                    self.assertEqual([s['id'] for s in answer['slides']], ['s1', 's2'])
                    self.assertEqual(set(answer['slides'][0]), {'id', 'answers', 'note'})
                self.assertNotIn('fix', answer['findings'][0])

    def test_only_marked_new_runs_hold_the_content_checkpoint(self):
        self.assertFalse(deck_content.checkpoint({}, 'gate:outline'))
        for gate in ('gate:outline', 'gate:deck-outline@101'):
            self.assertTrue(deck_content.checkpoint({'deck_content': deck_content.PROTOCOL}, gate))
        self.assertFalse(deck_content.checkpoint({'deck_content': deck_content.PROTOCOL}, 'gate:build'))
