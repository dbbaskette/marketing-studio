"""The new story decision is local and precedes the real pinned research transport."""
import copy
import json
import os
from pathlib import Path
import unittest
from unittest import mock

from runner_support import StudioCase, URL
from runner import agents, research, slide_story, stages
from workspace import WorkspaceError
import test_parallel_research as parallel_tests
from synthesis_fixture import TEXT


@unittest.skipUnless(os.environ.get('STUDIO_TEST_RESEARCH_RUNTIME'), 'Pinned research helper required.')
class SlideStoryTests(StudioCase):
    def setUp(self):
        super().setUp()
        self.engine.story_first = self.engine.parallel_research = self.engine.content_first = True
        self.research = research.Research(Path(os.environ['STUDIO_TEST_RESEARCH_RUNTIME']))
        self.web.page(URL, TEXT, 'text/plain')
        self.phases, self.caps, self.questions, self.tasks = [], [], [], []
        self.barrier = None
        self.workers.then('scan', self.scanner)
        self.workers.then('research-result', *([self.worker] * 12))

    def scanner(self, tools, job):
        self.assertLessEqual(job.limits.seconds, 180)
        self.assertFalse(hasattr(job.limits, 'dollars'))
        self.assertFalse(tools.job.get('fetch'))
        self.assertFalse(tools.job.get('ask'))
        value = slide_story.seed({'title': 'Synthetic story', 'form': {}})
        okay, said = tools.submit_artifact('scan', json.dumps(value))
        self.assertTrue(okay, said)
        return agents.Outcome(True, cost=0.02, seconds=1)

    def worker(self, tools, job):
        payload = json.loads(tools.read_input('research-task')[1])
        if 'questions' in payload:
            self.questions.extend(payload['questions'])
            self.tasks.append(payload)
        return parallel_tests.ParallelNativeTests.worker(self, tools, job)

    def test_one_scan_then_local_edit_and_exact_approved_research(self):
        root = self.start(research=True)
        shown = self.view(root)
        self.assertIsNone(shown['problem'], shown['problem'])
        self.assertEqual(shown['gate']['name'], slide_story.GATE)
        self.assertEqual(len(self.workers.of('scan')), 1)
        from studio_core import model_profiles
        self.assertEqual(model_profiles.route(self.engine._load(root), 'Presentation Studio', 'scan')['profile'], 'quick')
        self.assertEqual(self.phases, [])
        plan = shown['gate']
        edited = copy.deepcopy(plan['outline'])
        edited['sections'] = [edited['sections'][0]]
        edited['sections'][0]['title'] = 'Approved context'
        saved = self.engine.decide(root, slide_story.GATE, 'save', extra={'outline': edited}, expected=plan['expected'])
        self.assertEqual(saved['gate']['outline'], edited)
        self.assertEqual(self.phases, [])
        with self.assertRaises(WorkspaceError):
            self.engine.decide(root, slide_story.GATE, 'approve', extra={'outline': edited}, expected=plan['expected'])
        after = self.engine.decide(root, slide_story.GATE, 'approve', extra={'outline': edited}, expected=saved['gate']['expected'])
        self.assertIsNone(after['problem'], after['problem'])
        self.assertEqual({q['id'] for q in self.questions}, {'section-context'})
        self.assertEqual(len(self.workers.of('scan')), 1)
        self.assertEqual(after['gate']['name'], 'gate:outline')
        self.assertEqual(self.workers.of('section'), [])
        self.assertIn('Approved context', self.questions[0]['question'])

    def test_timeout_keeps_fallback_and_resume_never_rescans(self):
        self.workers.queued['scan'] = [lambda tools, job: agents.Outcome(False, 'timeout', seconds=180)]
        root = self.start(research=True)
        shown = self.view(root)
        self.assertTrue(shown['gate']['scan']['fallback'])
        self.engine.act(root, 'stop')
        saved = slide_story.decide(self.engine, root, shown['gate']['expected'], 'save', shown['gate']['outline'])
        with self.assertRaises(WorkspaceError):
            slide_story.decide(self.engine, root, shown['gate']['expected'], 'approve', shown['gate']['outline'])
        self.engine.act(root, 'resume')
        self.assertEqual(len(self.workers.of('scan')), 1)

    def test_saved_old_flow_and_ready_script_skip_scan(self):
        self.engine.story_first = False
        root = self.start(research=True)
        self.assertNotIn('scan', [s.name for s in stages.steps(self.engine._load(root))])
        self.engine.story_first = True
        self.questions.clear()
        self.workers.classified = {'kind': 'spec', 'reason': 'A finished script.', 'slides': 3}
        root = self.start(title='Ready script', route='document', research=True,
                          source={'kind': 'paste', 'text': '# Complete script\nSynthetic words.'})
        self.assertIsNone(self.view(root)['problem'])
        self.assertNotIn('scan', [s.name for s in stages.steps(self.engine._load(root))])
        self.assertEqual(self.questions, [])

    def test_changed_intake_and_active_work_refuse_old_decisions(self):
        root = self.start(research=True)
        plan = self.view(root)['gate']
        with mock.patch.object(self.engine._run(root), 'busy', True), self.assertRaises(WorkspaceError):
            slide_story.decide(self.engine, root, plan['expected'], 'approve', plan['outline'])
        record = self.engine._load(root)
        record['form']['goal'] = 'Changed goal'
        self.engine._store(root, record)
        with self.assertRaises(WorkspaceError):
            slide_story.decide(self.engine, root, plan['expected'], 'approve', plan['outline'])

    def test_new_flow_is_versioned_and_malformed_pins_refused(self):
        root = self.start(research=True)
        record = self.engine._load(root)
        self.assertEqual(record['schema'], 5)
        record.pop('slide_story')
        with mock.patch('runner.engine.decks.read_run', return_value=record), self.assertRaises(WorkspaceError):
            self.engine._load(root)

    def test_a_story_saved_with_a_dollar_scan_limit_still_opens(self):
        root = self.start(research=True)
        with self.engine.files:
            record = self.engine._load(root)
            record['slide_story']['limits'] = {'seconds': 180, 'dollars': 0.25, 'input_chars': 48000}
            self.engine._store(root, record)
            self.engine._commit(root, 'as an older runner left it')
        self.assertTrue(slide_story.valid(self.engine._load(root)))
        shown = self.view(root)
        self.assertIsNone(shown['problem'], shown['problem'])
        self.assertEqual(shown['gate']['limits'], {'seconds': 180, 'input_chars': 48000, 'searches': 0})
        self.assertEqual(self.engine._load(root)['slide_story']['limits']['dollars'], 0.25)

    def test_scan_budget_can_be_reduced_and_never_exceeds_the_hard_cap(self):
        # A scan budget saved with a dollar amount is still read; the amount is ignored.
        self.engine.story_budget = slide_story.budget({'seconds': 10, 'dollars': 0.05, 'input_chars': 1000})
        self.assertEqual(self.engine.story_budget, {'seconds': 10, 'input_chars': 1000})
        root = self.start(research=True)
        job = self.workers.of('scan')[0]
        self.assertEqual(job.limits, agents.Limits(seconds=10))
        self.assertNotIn('dollars', self.view(root)['gate']['limits'])
        self.assertEqual(self.view(root)['gate']['limits']['input_chars'], 1000)
        self.assertEqual(slide_story.budget({'seconds': 900})['seconds'], 180)
        with self.assertRaises(WorkspaceError): slide_story.budget(False)
        from studio_core import research_contract, scope_scan
        scope = scope_scan.research_scope('x' * 20_000,
            [{'title': '😀' * 160} for _ in range(8)], 'task.approved_slide_story')
        self.assertLessEqual(research_contract.js_length(scope), 4000)

    def test_supplied_only_source_policy_survives_story_approval(self):
        from runner_support import FORM
        from studio_core import research_sources
        self.supplied = True
        store = research_sources.Sources(self.space.root / '.research-sources')
        source = store.create()
        source = store.mutate(source['id'], source['revision'], 'capture', kind='text', name='Synthetic notes', text=TEXT)
        root = Path(self.engine.start({**FORM, 'flow': 'desk', 'research': True},
            research_inputs={'id': source['id'], 'expected': source['revision']})['path'])
        shown = self.view(root)['gate']
        after = slide_story.decide(self.engine, root, shown['expected'], 'approve', shown['outline'])
        self.assertIsNone(after['problem'], after['problem'])
        self.assertEqual(len(self.tasks), 2)
        self.assertTrue(all(task['task']['source_mode'] == 'selected' for task in self.tasks))

    def test_stop_during_scan_keeps_an_accepted_partial_and_resume_does_not_rescan(self):
        import threading
        import time
        self.engine = self.make(background=True, parallel_research=True, story_first=True, content_first=True)
        root = None
        started, ready = threading.Event(), threading.Event()
        def stopped(tools, job):
            started.set()
            self.assertTrue(ready.wait(10))
            self.assertTrue(self.engine._run(root).stop.wait(10))
            self.assertTrue(tools.submit_artifact('scan', json.dumps(slide_story.seed({'title': 'Partial'})))[0])
            return agents.Outcome(False, 'stopped', seconds=1)
        self.workers.queued['scan'] = [stopped]
        root = self.start(title='Stopped story', research=True)
        ready.set()
        self.assertTrue(started.wait(10))
        self.engine.act(root, 'stop')
        deadline = time.monotonic() + 10
        while self.engine._run(root).busy and time.monotonic() < deadline: time.sleep(0.01)
        self.assertFalse(self.engine._run(root).busy)
        self.assertFalse(self.engine._load(root)['slide_story']['scan']['fallback'])
        calls = len(self.workers.of('scan'))
        self.engine.act(root, 'resume')
        deadline = time.monotonic() + 10
        while self.engine._run(root).busy and time.monotonic() < deadline: time.sleep(0.01)
        self.assertEqual(len(self.workers.of('scan')), calls)
