import json
import os
from pathlib import Path
import unittest
from unittest import mock
from runner_support import StudioCase, URL
from runner import research
from studio_core import research_contract, review_policy
from synthesis_fixture import TEXT, dossier, review

RUNTIME = os.environ.get('STUDIO_TEST_RESEARCH_RUNTIME')

@unittest.skipUnless(RUNTIME, 'Set STUDIO_TEST_RESEARCH_RUNTIME for the real helper integration.')
class SynthesisIntegrationTests(StudioCase):
    def setUp(self):
        super().setUp()
        self.research = research.Research(Path(RUNTIME))
        self.web.page(URL, TEXT, 'text/plain')
        self.workers.then('research-result', self.author, self.checker)

    def author(self, tools, job):
        payload = json.loads(tools.read_input('research-task')[1])
        self.assertTrue(tools.save_source(URL)[0])
        source = tools._index()[0]
        value = dossier(payload['worker'], source['file'], source['url'])
        accepted = tools.submit_artifact('research-result', json.dumps(value))
        self.assertTrue(accepted[0], accepted)

    def checker(self, tools, job):
        payload = json.loads(tools.read_input('research-task')[1])
        self.assertTrue(tools.read_source('s1')[0])
        accepted = tools.submit_artifact('research-result', json.dumps(review(payload['review_template'])))
        self.assertTrue(accepted[0], accepted)

    def test_new_deck_uses_reviewed_report_then_combined_direction_gate(self):
        with mock.patch.object(review_policy, 'capture', return_value={'schema': 1, 'level': 'balanced'}):
            root = self.start(research=True)
        shown = self.view(root)
        self.assertIsNone(shown['problem'], shown)
        self.assertEqual(shown['gate']['name'], 'gate:outline')
        self.assertEqual(self.engine._load(root)['schema'], 3)
        facts, manifest = research_contract.read_bundle(root / 'research')
        self.assertIn('presentation', facts['purpose'])
        self.assertEqual(len(self.workers.of('research-result')), 2)
        self.assertFalse((root / '.harness-research/research.json').exists())
        self.assertIn('What to explain first', (root / 'research/brief.md').read_text())
        self.assertNotEqual(facts['review']['worker'], self.engine._load(root).get('author'))
        self.assertEqual(facts['review']['digest'], manifest['digest'])

    def test_existing_record_does_not_switch_formats_on_resume(self):
        from stand_ins.research import stand_in
        self.research = stand_in()
        root = self.start(research=True)
        self.assertNotIn('research_contract', self.engine._load(root))
        self.research = research.Research(Path(RUNTIME))
        self.assertNotIn('research_contract', self.engine._load(root))

    def test_stopping_a_research_worker_keeps_the_draft_without_a_failure(self):
        from runner.agents import Outcome
        self.workers.queued['research-result'] = [lambda tools, job: Outcome(False, 'stopped', 'Stopped')]
        with mock.patch.object(review_policy, 'capture', return_value={'schema': 1, 'level': 'automatic'}):
            root = self.start(research=True)
        self.assertIsNone(self.view(root)['problem'], self.view(root))
        self.assertFalse((root / 'research/output.json').exists())
        entry = self.engine._load(root)['steps']['research-author']
        self.assertIn('stopped', str(entry))

    def test_finding_marks_use_synthesis_ids_and_never_rewrite_the_checked_report(self):
        def authored(tools, job):
            payload = json.loads(tools.read_input('research-task')[1])
            self.assertTrue(tools.save_source(URL)[0])
            source = tools._index()[0]
            value = dossier(payload['worker'], source['file'], source['url'])
            value['findings'][0]['id'] = 'finding-first'
            value['findings'][1]['id'] = 'finding-second'
            value['brief'][0]['blocks'][0]['refs'] = ['finding-first']
            self.assertTrue(tools.submit_artifact('research-result', json.dumps(value))[0])
        self.workers.queued['research-result'] = [authored, self.checker, authored, self.checker]
        root = self.start(research=True)
        self.decide(root)  # research plan
        self.assertEqual(self.waiting(root), 'gate:research')
        self.decide(root, decision='changes', note='Explain this boundary.',
                    extra={'again': {'finding-first': 'Clarify the boundary.'}})
        self.assertIsNone(self.view(root)['problem'], self.view(root))
        self.assertEqual(self.waiting(root), 'gate:research')
        facts, before = research_contract.read_bundle(root / 'research')
        self.decide(root, extra={'left_out': ['finding-second']})
        self.assertIsNone(self.view(root)['problem'], self.view(root))
        self.assertEqual(self.waiting(root), 'gate:outline')
        self.assertEqual(research_contract.read_bundle(root / 'research')[1], before)
        self.assertEqual(self.engine._load(root)['research']['left_out'], ['finding-second'])
        self.assertEqual(self.engine._marked_ids(root, 'gate:research', {}), ['finding-first', 'finding-second'])
