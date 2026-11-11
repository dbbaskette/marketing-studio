"""New saved flow uses actual transport, tools, helper and scoped limits."""
import json
from unittest import mock
import test_parallel_research as parallel_tests
from runner import outline_first, training_plan
from synthesis_fixture import section_value
from runner import agents
from studio_core import research_sections


from runner_support import StudioCase


import os
import unittest


@unittest.skipUnless(os.environ.get('STUDIO_TEST_RESEARCH_RUNTIME'), 'Pinned helper required.')
class SectionResearchTests(StudioCase):
    def setUp(self):
        super().setUp()
        from runner import research
        from runner_support import URL
        from synthesis_fixture import TEXT
        from pathlib import Path
        import os
        self.engine.plan_first = self.engine.outline_first = self.engine.parallel_research = True
        self.research = research.Research(Path(os.environ['STUDIO_TEST_RESEARCH_RUNTIME']))
        self.web.page(URL, TEXT, 'text/plain')
        self.phases, self.caps = [], []
        self.barrier = None
        self.workers.then('scan', self.scanner)
        self.workers.then('research-result', *([self.worker] * 20))
        self.engine.section_synthesis = True
        self.section_jobs = []
        self.fail_one = False

    def scanner(self, tools, job):
        okay, said = tools.submit_artifact('scan', json.dumps(outline_first.seed('Synthetic training')))
        self.assertTrue(okay, said)
        return agents.Outcome(True, cost=0.01, seconds=1)

    def worker(self, tools, job):
        payload = json.loads(tools.read_input('research-task')[1])
        if 'section' in payload or 'completed_sections' in payload:
            self.section_jobs.append((payload.get('section', {}).get('id', 'final'), job.limits.seconds))
            self.assertFalse(tools.job.get('fetch'))
            self.assertFalse(tools.job.get('ask'))
            if self.fail_one:
                self.fail_one = False
                return agents.Outcome(False, 'timeout', 'Synthetic timeout', seconds=300, cost=0.01)
            accepted = tools.submit_artifact('research-result', json.dumps(section_value(payload)))
            self.assertTrue(accepted[0], accepted)
            return agents.Outcome(True, cost=0.01, seconds=1)
        return parallel_tests.ParallelNativeTests.worker(self, tools, job)

    def _complete_section_work(self):
        root = self.start()
        view = self.view(root)
        record = self.engine._load(root)
        self.assertEqual(record['schema'], 8)
        self.assertTrue(research_sections.enabled(record))
        story = view['training_plan']
        original = self.engine._research
        def finish_research(*args):
            original(*args)
            args[1].stop.set()  # This fixture covers research, not material authors.
        with mock.patch.object(self.engine, '_research', side_effect=finish_research):
            training_plan.decide(self.engine, root, story['expected'], 'approve', outline=story['outline'])
        shown = self.view(root)
        from studio_core import research_contract
        from studio_core import research_session
        facts, _ = research_contract.read_bundle(research_contract.output_root(research_session.case_for(root)))
        self.assertTrue(facts['review']['accepted'])
        self.assertEqual(shown['research_progress']['phase'], 'complete')
        self.assertEqual(len(self.section_jobs), len(story['outline']['sections']) + 1)
        self.assertEqual(self.section_jobs[-1], ('final', None))

        return root

    def test_new_schema_and_section_transport_pass_complete_check(self):
        self._complete_section_work()

    def test_no_section_job_is_given_a_spending_limit_and_nothing_warns(self):
        root=self._complete_section_work()
        self.assertNotIn('spending', self.view(root))
        self.assertFalse(any(hasattr(item[1].limits, 'dollars') for item in self.workers.jobs))

    def test_timeout_grants_only_the_failed_contribution_more_time(self):
        self.fail_one = True
        root = self.start()
        view = self.view(root)
        story = view['training_plan']
        training_plan.decide(self.engine, root, story['expected'], 'approve', outline=story['outline'])
        record = self.engine._load(root)
        halted = record.get('halted') or record.get('problem')
        self.assertEqual(halted['action'], 'more-time')
        ident = halted['section']
        before = record['limits']['step_seconds']
        previous = list(self.section_jobs)
        self.engine.act(root, 'more-time')
        record = self.engine._load(root)
        self.assertEqual(record['limits']['step_seconds'], before)
        self.assertEqual(record['section_synthesis']['more_time'][ident], 2 * research_sections.SECONDS)
        subsequent = self.section_jobs[len(previous):]
        self.assertEqual(subsequent, [(ident, None), ('final', None)])

    def test_preview_polling_reuses_local_metadata_but_confirmation_rehashes_sources(self):
        from studio_core import research_impact
        root = self.start()
        story = self.view(root)['training_plan']
        original = self.engine._research
        def finish(*args):
            original(*args); args[1].stop.set()
        with mock.patch.object(self.engine, '_research', side_effect=finish):
            training_plan.decide(self.engine, root, story['expected'], 'approve', outline=story['outline'])
        self.engine._research_impact_cache = {}
        record = self.engine._load(root)
        jobs = len(self.workers.jobs)
        with mock.patch.object(research_impact, 'native_sources', wraps=research_impact.native_sources) as read:
            one = research_impact.native(self.engine, root, record, "training")
            self.assertIsNotNone(one)
            self.assertEqual(research_impact.native(self.engine, root, record, "training"), one)
            self.assertEqual(read.call_count, 1)
            research_impact.native(self.engine, root, record, "training", {'expected': one['expected'], 'sections': [row['id'] for row in one['sections']]})
            self.assertEqual(read.call_count, 2)
        self.assertEqual(len(self.workers.jobs), jobs)
