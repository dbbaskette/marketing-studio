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

    def test_new_training_saves_schema_two_and_retains_stable_citations(self):
        root = self.start()
        self.to_gate(root, 'research')
        shown = self.view(root)
        self.assertIsNone(shown['problem'], shown)
        self.assertEqual(self.engine._load(root)['schema'], 3)
        facts, manifest = research_contract.read_bundle(root / 'research')
        self.assertEqual(facts['topic'], 'Rolling restarts on the platform')
        self.assertIn('Selected materials:', facts['scope'])
        self.assertIn('learner tasks', facts['purpose'])
        self.assertIn('training', facts['purpose'])
        self.assertEqual(len(self.workers.of('research-result')), 2)
        self.assertFalse((root / '.harness-research/research.json').exists())
        import workspace
        self.assertEqual(workspace.research_record(root)['schema'], 2)
        self.decide(root, 'research')
        self.assertEqual(workspace.load(root)['findings']['instance-min'], 'supported')
        self.assertTrue(workspace.research_intact(root, workspace.load(root)))
        capture = root / 'research' / facts['sources'][0]['snapshot'].removeprefix('research/')
        capture.write_text('Changed evidence')
        self.assertFalse(workspace.research_intact(root, workspace.load(root)))

    def test_research_change_request_gets_a_new_review_and_returns_to_gate(self):
        root = self.start()
        self.to_gate(root, 'research')
        before = research_contract.read_bundle(root / 'research')[1]['digest']
        self.workers.then('research-result', self.author, self.checker)
        self.decide(root, 'research', 'revise', 'Explain the limits more clearly.')
        self.assertIsNone(self.view(root)['problem'], self.view(root))
        after = research_contract.read_bundle(root / 'research')[1]['digest']
        self.assertNotEqual(before, after)
        self.assertEqual(len(self.workers.of('research-result')), 4)

    def test_explicit_conversation_import_uses_typed_findings(self):
        import workspace
        root = self.start()
        self.to_gate(root, 'research')
        session = workspace.load(root)
        session['settings']['approval'] = 'chat'
        workspace.store(root, session)
        with mock.patch.dict(os.environ, {'HARNESS_RESEARCH_RUNTIME': RUNTIME}):
            imported = workspace.import_research(root, root / research_contract.CASE)
        self.assertEqual(imported['status'], 'ready-for-review')
        self.assertEqual(workspace.research_record(root)['schema'], 2)

    def test_stopping_a_research_worker_keeps_the_draft_without_a_failure(self):
        from runner.agents import Outcome
        self.workers.queued['research-result'] = [lambda tools, job: Outcome(False, 'stopped', 'Stopped')]
        with mock.patch.object(review_policy, 'capture', return_value={'schema': 1, 'level': 'automatic'}):
            root = self.start()
        self.assertIsNone(self.view(root)['problem'], self.view(root))
        self.assertFalse((root / 'research/output.json').exists())
        entry = self.engine._load(root)['steps']['research-author']
        self.assertIn('stopped', str(entry))
