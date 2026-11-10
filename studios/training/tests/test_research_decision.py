"""Actual runner and helper; scripted semantic verdicts and no external jobs."""
import json
import os
from pathlib import Path
import unittest
from unittest import mock

from runner_support import StudioCase, URL
from runner import agents, research, research_decision, pipeline
from studio_core import research_contract as rc, research_session, research_decisions
import test_parallel_research as native
from synthesis_fixture import TEXT, review
from workspace import WorkspaceError


@unittest.skipUnless(os.environ.get('STUDIO_TEST_RESEARCH_RUNTIME'), 'Pinned helper required.')
class CreatorDecisionTests(StudioCase):
    def setUp(self):
        super().setUp()
        self.engine.parallel_research = True
        self.research = research.Research(Path(os.environ['STUDIO_TEST_RESEARCH_RUNTIME']))
        self.web.page(URL, TEXT, 'text/plain')
        self.workers.then('research-result', *([self.worker] * 16))
        self.barrier = None
        self.phases, self.caps = [], []
        self.unread = False

    def worker(self, tools, job):
        payload = json.loads(tools.read_input('research-task')[1])
        if 'review_template' not in payload:
            return native.ParallelNativeTests.worker(self, tools, job)
        self.phases.append('review')
        if getattr(self, 'no_verdict', False):
            return agents.Outcome(False, 'timeout', 'Synthetic check timed out before returning verdicts.', seconds=300)
        value = review(payload['review_template'])
        value['prose'][0].update(verdict='narrow', note='This source supports a narrower scope.')
        if self.unread:
            value['originals'][0].update(read_original=False, access_error='Synthetic allowance ended before this source.')
        accepted = tools.submit_artifact('research-result', json.dumps(value))
        self.assertTrue(accepted[0], accepted)
        return agents.Outcome(True, cost=0.01, seconds=1)

    def decide(self, root, choice='include'):
        shown = research_decision.dispatch(self.engine, root, {'action':'read'})
        return research_decision.dispatch(self.engine, root, {'action':'save','expected':shown['expected'],
            'choices':{row['id']:choice for row in shown['items']}})

    def test_one_check_creator_save_no_jobs_and_continue_reaches_materials(self):
        root = self.start()
        self.assertEqual(self.phases.count('review'),1)
        self.assertTrue(self.view(root)['problem']['creator_review'])
        before=len(self.workers.jobs)
        shown=self.decide(root)
        self.assertEqual(len(self.workers.jobs),before)
        self.assertEqual(shown['problem']['label'],'Continue')
        facts, manifest = rc.read_bundle(root/'research')
        self.assertEqual(manifest['owner'],research_decisions.OWNER)
        self.assertFalse(facts['review']['accepted'])
        self.assertIn('Creator included with warning', (root/pipeline.REPORT).read_text())
        self.assertTrue(research_decision.current(root,self.engine._load(root)))
        self.assertTrue(pipeline.findings_text(root).startswith('# Creator-approved research'))
        self.engine.act(root,'resume')
        shown=self.view(root)
        self.assertIsNone(shown['problem'],shown['problem'])
        self.assertEqual(self.phases.count('review'),1)
        self.assertNotIn('cleared', self.engine._load(root))
        self.assertTrue(self.workers.of('blueprint'), 'Creator-qualified research reaches material authoring')

    def test_source_access_gap_also_offers_creator_choice(self):
        self.unread=True
        root=self.start()
        shown=research_decision.dispatch(self.engine,root,{'action':'read'})
        self.assertTrue(any(row['kind']=='source' for row in shown['items']))
        self.decide(root)
        self.assertFalse(rc.read_bundle(root/'research')[0]['review']['originals'][0]['read_original'])

    def test_plain_include_reaches_material_author_without_forced_warning(self):
        root = self.start()
        before = len(self.workers.jobs)
        self.decide(root, 'include-plain')
        self.assertEqual(len(self.workers.jobs), before)
        facts, _ = rc.read_bundle(root/'research')
        self.assertFalse(facts['review']['accepted'])
        self.assertNotIn('Creator included with warning', pipeline.findings_text(root))
        self.assertNotIn('independent-check notes', (root/'research/brief.md').read_text())
        self.assertIn('**Included**', (root/'research/evidence.md').read_text())
        self.engine.act(root, 'resume')
        self.assertIsNone(self.view(root)['problem'])
        self.assertTrue(self.workers.of('blueprint'))

    def test_checker_timeout_offers_whole_draft_as_explicitly_unverified(self):
        self.no_verdict=True
        root=self.start()
        self.assertTrue(self.view(root)['problem']['creator_review'])
        shown=research_decision.dispatch(self.engine,root,{'action':'read'})
        self.assertEqual([row['id'] for row in shown['items']],['assessment:unreviewed'])
        before=len(self.workers.jobs)
        self.decide(root)
        self.assertEqual(len(self.workers.jobs),before)
        facts,_=rc.read_bundle(root/'research')
        self.assertIsNone(facts['review'])
        self.assertTrue(all('verification is unresolved' in fact['statement'] for fact in facts['facts']))

    def test_stale_or_active_form_is_refused_without_publishing(self):
        root=self.start()
        shown=research_decision.dispatch(self.engine,root,{'action':'read'})
        sent={'action':'save','expected':shown['expected'],'choices':{row['id']:'include' for row in shown['items']}}
        with mock.patch.object(self.engine,'_desk_change_busy',return_value=True):
            with self.assertRaisesRegex(WorkspaceError,'active work'):research_decision.dispatch(self.engine,root,sent)
        record=self.engine._load(root);record['research_inputs']={'focus':'Changed scope'};self.engine._store(root,record)
        with self.assertRaisesRegex(WorkspaceError,'changed'):research_decision.dispatch(self.engine,root,sent)
        self.assertFalse((root/'research/creator.json').exists())

    def test_excluded_prose_is_omitted_and_duplicate_save_is_refused(self):
        root=self.start()
        shown=research_decision.dispatch(self.engine,root,{'action':'read'})
        sent={'action':'save','expected':shown['expected'],'choices':{row['id']:'exclude' for row in shown['items']}}
        research_decision.dispatch(self.engine,root,sent)
        self.assertIn('Omitted by the creator',(root/pipeline.REPORT).read_text())
        with self.assertRaises(WorkspaceError):research_decision.dispatch(self.engine,root,sent)
