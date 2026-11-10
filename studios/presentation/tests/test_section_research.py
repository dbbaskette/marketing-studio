"""New saved flow uses actual transport, tools, helper and scoped limits."""
import json
from unittest import mock
import test_slide_story as story_tests
from synthesis_fixture import section_value
from runner import slide_story, agents
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
        self.engine.story_first = self.engine.parallel_research = self.engine.content_first = True
        self.research = research.Research(Path(os.environ['STUDIO_TEST_RESEARCH_RUNTIME']))
        self.web.page(URL, TEXT, 'text/plain')
        self.phases, self.caps, self.questions, self.tasks = [], [], [], []
        self.barrier = None
        self.workers.then('scan', self.scanner)
        self.workers.then('research-result', *([self.worker] * 20))
        self.engine.section_synthesis = True
        self.section_jobs = []
        self.fail_one = False

    scanner = story_tests.SlideStoryTests.scanner

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
        return story_tests.SlideStoryTests.worker(self, tools, job)

    def _complete_section_work(self):
        root = self.start(research=True)
        view = self.view(root)
        record = self.engine._load(root)
        self.assertEqual(record['schema'], 6)
        self.assertTrue(research_sections.enabled(record))
        story = view['gate']
        self.engine.decide(root, slide_story.GATE, 'approve', extra={'outline': story['outline']}, expected=story['expected'])
        shown = self.view(root)
        self.assertIsNone(shown['problem'], shown['problem'])
        self.assertEqual(shown['research_progress']['phase'], 'complete')
        self.assertEqual(len(self.section_jobs), len(story['outline']['sections']) + 1)
        self.assertLessEqual(self.section_jobs[-1][1], research_sections.SECONDS)

        return root

    def test_new_schema_and_section_transport_pass_complete_check(self):
        self._complete_section_work()

    def test_section_work_is_given_time_limits_and_no_spending_limit(self):
        root=self._complete_section_work()
        self.assertNotIn('spending', self.view(root))
        self.assertTrue(self.workers.jobs)
        self.assertTrue(all(not hasattr(item[1].limits, 'dollars') and item[1].limits.seconds > 0
                            for item in self.workers.jobs))

    def test_timeout_grants_only_the_failed_contribution_more_time(self):
        self.fail_one = True
        root = self.start(research=True)
        view = self.view(root)
        story = view['gate']
        self.engine.decide(root, slide_story.GATE, 'approve', extra={'outline': story['outline']}, expected=story['expected'])
        record = self.engine._load(root)
        halted = record.get('halted') or record.get('problem')
        self.assertEqual(halted['action'], 'more-time')
        ident = halted['section']
        before = record['limits']['step_seconds']
        previous = list(self.section_jobs)
        self.engine.act(root, 'more-time')
        record = self.engine._load(root)
        self.assertEqual(record['limits']['step_seconds'], before)
        self.assertEqual(record['section_synthesis']['more_time'][ident], 600)
        subsequent = self.section_jobs[len(previous):]
        self.assertEqual(subsequent, [(ident, 600), ('final', research_sections.SECONDS)])

    def test_preview_polling_reuses_local_metadata_but_confirmation_rehashes_sources(self):
        from studio_core import research_impact
        root = self.start(research=True)
        story = self.view(root)['gate']
        self.engine.decide(root, slide_story.GATE, 'approve', extra={'outline': story['outline']}, expected=story['expected'])
        self.engine._research_impact_cache = {}
        record = self.engine._load(root)
        jobs = len(self.workers.jobs)
        with mock.patch.object(research_impact, 'native_sources', wraps=research_impact.native_sources) as read:
            one = research_impact.native(self.engine, root, record, "presentation")
            self.assertIsNotNone(one)
            self.assertEqual(research_impact.native(self.engine, root, record, "presentation"), one)
            self.assertEqual(read.call_count, 1)
            research_impact.native(self.engine, root, record, "presentation", {'expected': one['expected'], 'sections': [row['id'] for row in one['sections']]})
            self.assertEqual(read.call_count, 2)
        self.assertEqual(len(self.workers.jobs), jobs)
