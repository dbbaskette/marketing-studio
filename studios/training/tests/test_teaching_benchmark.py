"""Exercise the offline paired evaluation with synthetic, independently scored exports."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/evaluation'))
import teaching


class TeachingBenchmarkTests(unittest.TestCase):
    def test_paired_git_lab_checks_inputs_and_requires_evidence_before_comparison(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / 'base'
            next_run = base.with_name('candidate')
            pair = SimpleNamespace(baseline=base, candidate=next_run, output=base.with_name('pair'))
            teaching.prepare(SimpleNamespace(case='git', output=base, source=[], model='test',
                                             effort='high', brand='example'))
            transcript = (base / 'sources/observations.txt').read_text()
            self.assertIn('$ git show HEAD:banner.txt\ngreen', transcript)
            teaching.store(base / 'approved-outline.json', {'sections': ['Inspect both states']})
            with ZipFile(base / 'deck.pptx', 'w') as deck:
                deck.writestr('ppt/presentation.xml', '<presentation/>')
            shutil.copytree(base, next_run)
            source = next_run / 'sources/observations.txt'
            source.write_text('different input')
            with self.assertRaisesRegex(ValueError, 'Research inputs differ'):
                teaching.blind(pair)
            source.write_text(transcript)
            teaching.blind(pair)
            self.assertFalse((pair.output / 'review/key.json').exists())
            with self.assertRaisesRegex(ValueError, 'cite slide'):
                teaching.compare(pair)
            key = json.loads((pair.output / 'key.json').read_text())
            scores = {label: {c: {'score': i, 'evidence': 'Slide 2, staged value.'}
                              for c in teaching.RUBRIC}
                      for i, label in enumerate((key['baseline'], key['candidate']), 1)}
            teaching.store(pair.output / 'review/scores.json', scores)
            result = teaching.compare(pair)
            self.assertEqual((result['baseline'], result['candidate'], result['change']), (5, 10, 5))
