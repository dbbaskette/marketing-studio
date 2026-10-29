"""Production runner transport with fictional evidence and the real pinned helper."""
import copy
import inspect
import json
import os
from pathlib import Path
import threading
import unittest

from runner_support import StudioCase, URL
from runner import engine as engines, research
from studio_core import research_contract as contract, research_session as parallel
from synthesis_fixture import TEXT, dossier, review

RUNTIME = os.environ.get('STUDIO_TEST_RESEARCH_RUNTIME')


@unittest.skipUnless(RUNTIME, 'Set STUDIO_TEST_RESEARCH_RUNTIME for pinned helper tests.')
class ParallelNativeTests(StudioCase):
    def setUp(self):
        super().setUp()
        self.engine.parallel_research = True
        self.research = research.Research(Path(RUNTIME))
        self.web.page(URL, TEXT, 'text/plain')
        self.workers.then('research-result', *([self.worker] * 12))
        self.barrier = threading.Barrier(3)
        self.phases, self.caps = [], []
        self.reject_once = False

    def worker(self, tools, job):
        payload = json.loads(tools.read_input('research-task')[1])
        self.caps.append(job.limits.dollars)
        if 'questions' in payload:
            self.phases.append('investigate')
            if self.barrier: self.barrier.wait(10)
            self.assertTrue(tools.save_source(URL)[0])
            source = tools._index()[0]
            value = dossier(payload['worker'], source['file'], source['url'])
            value = {k: value[k] for k in ('schema', 'sources', 'facts')}
            value['gaps'] = []
        elif 'evidence' in payload and 'review_template' not in payload:
            self.phases.append('synthesize')
            evidence = payload['evidence']
            value = dossier(payload['worker'])
            first = evidence['facts'][0]['id']
            value['findings'] = [{**copy.deepcopy(value['findings'][0]), 'id': q['id'],
                'summary': {'text': 'More than one instance keeps capacity.', 'kind': 'summary', 'refs': [first]},
                'support': [first], 'conditions': []} for q in payload['task']['planning_questions']]
            value['sections'][0]['blocks'][0]['refs'] = [first]
            value['brief'][0]['blocks'][0]['refs'] = [value['findings'][0]['id']]
            value = {k: value[k] for k in ('schema', 'findings', 'sections', 'brief')}
        else:
            self.phases.append('review')
            for source in tools._index(): self.assertTrue(tools.read_source(source['id'])[0])
            value = review(payload['review_template'])
        accepted = tools.submit_artifact('research-result', json.dumps(value))
        self.assertTrue(accepted[0], accepted)

    def test_default_new_run_is_versioned_parallel_and_publishes_reviewed_bundle(self):
        self.assertIs(inspect.signature(engines.Engine).parameters['parallel_research'].default, True)
        root = self.start()
        shown = self.view(root)
        self.assertIsNone(shown['problem'], shown['problem'])
        record = self.engine._load(root)
        self.assertEqual(record['schema'], parallel.RECORD_SCHEMA)
        self.assertTrue(parallel.protocol(record))
        self.assertCountEqual(self.phases, ['investigate'] * 3 + ['synthesize', 'review'])
        facts, _ = contract.read_bundle(root / 'research')
        self.assertTrue(facts['review']['accepted'])
        self.assertEqual(len({f['author'] for f in facts['facts']}), 3)
        self.assertEqual(shown['research_progress']['phase'], 'complete')
        self.assertLessEqual(sum(self.caps[:3]), record['limits']['training_dollars'] / 2)
        self.assertTrue(all(a.get('research_attempt') for name, entry in record['steps'].items()
                            if contract.job_round(name) for a in entry['attempts']))
        self.assertIn('active_seconds', shown['timing'])

    def test_saved_serial_run_does_not_acquire_parallel_protocol(self):
        # Existing histories stay with their original transport even on the new engine.
        from test_synthesis_integration import SynthesisIntegrationTests
        serial = SynthesisIntegrationTests
        self.workers.queued['research-result'] = [lambda tools, job: serial.author(self, tools, job),
                                                 lambda tools, job: serial.checker(self, tools, job)]
        root = self.saved_start(saved_contract=contract.snapshot(self.research))
        self.to_gate(root, 'research')
        self.assertNotIn('research_execution', self.engine._load(root))
        self.assertEqual(len(self.workers.of('research-result')), 2)

    def test_missing_or_unknown_parallel_protocol_refuses_resume(self):
        self.barrier = None
        root = self.start()
        record = self.engine._load(root)
        record['research_execution']['schema'] = 99
        self.engine._store(root, record)
        from workspace import WorkspaceError
        with self.assertRaisesRegex(WorkspaceError, 'parallel research protocol'):
            engines.read_record(root)
