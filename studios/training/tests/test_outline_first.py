"""Outline approval precedes research; no real providers or user state."""
import copy
import json
from unittest import mock

from runner_support import StudioCase
from runner import agents, outline_first as outline, pipeline, training_plan
from studio_core import model_profiles
import workspace
from workspace import WorkspaceError


class OutlineTests(StudioCase):
    def test_focused_scan_cannot_expand_to_six_research_areas(self):
        value = outline.seed('Synthetic introductory database training')
        value['sections'] = [dict(value['sections'][0], id='section-' + str(i)) for i in range(6)]
        problems, _, _, _ = outline.validate(json.dumps(value), {'max_sections': 4})
        self.assertIn('at most 4', problems[0])
        self.assertEqual(outline.validate(json.dumps(value), {})[0], [])

    def setUp(self):
        super().setUp()
        self.engine.plan_first = self.engine.outline_first = self.engine.parallel_research = True
        pin = {'schema': 1, 'protocol': 'harness-collection-v1', 'workers': 3, 'capability': {'protocol': 'harness-collection-v1'}}
        patcher = mock.patch('runner.engine.research_parallel.execution', return_value=pin)
        patcher.start();self.addCleanup(patcher.stop)
        self.workers.then('scan', self.scanner)

    def scanner(self, tools, job):
        self.assertEqual(job.profile, 'write')
        self.assertLessEqual(job.limits.seconds, outline.SECONDS)
        self.assertLessEqual(job.limits.dollars, outline.DOLLARS)
        self.assertFalse(tools.job['fetch'])
        self.assertFalse(tools.job['ask'])
        self.assertIn('minimal basics', job.guidance)
        self.assertIn('not a checklist of topics to add', job.guidance)
        payload = json.loads(tools.read_input('source-excerpts')[1])
        self.assertLessEqual(sum(len(one['excerpt']) for one in payload), outline.INPUT_CHARS)
        result = outline.seed('Synthetic subject')
        self.assertTrue(tools.submit_artifact('scan', json.dumps(result))[0])
        return agents.Outcome(True, cost=0.02, seconds=1)

    def test_one_quick_scan_waits_for_local_outline_approval(self):
        root = self.start(research_questions=['What are the failure limits?'])
        shown = self.view(root)
        self.assertEqual(shown['state'], 'waiting')
        from runner import drafts
        standing = drafts.standing(self.engine, root)
        self.assertEqual(standing['sentence'], drafts.OUTLINE_WAITS)
        self.assertEqual(standing['next']['label'], 'Review the training outline')
        self.assertEqual(len(self.workers.of('scan')), 1)
        self.assertEqual(len(self.workers.jobs), 1)
        self.assertFalse((root / pipeline.PLAN).exists())
        self.assertFalse((root / pipeline.REPORT).exists())
        plan = shown['training_plan']
        self.assertTrue(plan['outline_first'])
        self.assertGreaterEqual(len(plan['outline']['sections']), 2)
        self.assertEqual(plan['outline']['personal_questions'], ['What are the failure limits?'])
        record = self.engine._load(root)
        self.assertEqual(record['outline_first']['research_policy'], outline.research_quality.FOCUSED)
        self.assertEqual(model_profiles.route(record, 'Training Studio', 'scan')['profile'], 'quick')
        self.assertEqual(record['outline_first']['scan']['searches'], 0)
        self.engine.wake(root)
        self.view(root)
        self.assertEqual(len(self.workers.jobs), 1)
        edited = copy.deepcopy(plan['outline'])
        edited['sections'].pop()
        edited['sections'][0]['title'] = 'Only approved section'
        saved = training_plan.decide(self.engine, root, plan['expected'], 'save', outline=edited)
        self.assertEqual(len(self.workers.jobs), 1)
        self.assertNotEqual(saved['training_plan']['expected'], plan['expected'])
        with self.assertRaises(WorkspaceError):
            training_plan.decide(self.engine, root, plan['expected'], 'approve', outline=edited)
        with mock.patch.object(self.engine, 'carry_on') as continue_work:
            training_plan.decide(self.engine, root, saved['training_plan']['expected'], 'approve', outline=edited)
            continue_work.assert_called_once_with(root)
        record = self.engine._load(root)
        found = self.engine._survey(root, record)
        generated = json.loads(outline.research_plan(root, found, record, []))
        self.assertEqual(len(generated['items']), 1)
        self.assertIn('Only approved section', generated['items'][0]['question'])
        self.assertIn('What are the failure limits?', generated['items'][0]['question'])
        self.assertEqual(record['training_plan']['approved']['signature'], outline.signature(root, found.session, record))
        # Checked evidence added later cannot invalidate the already approved supplied scope.
        (root / 'sources/collection').mkdir(parents=True, exist_ok=True)
        (root / 'sources/collection/new.md').write_text('Synthetic checked research capture')
        self.assertEqual(record['training_plan']['approved']['signature'], outline.signature(root, found.session, record))

    def test_scan_uses_the_saved_quick_model_and_effort(self):
        from test_model_settings import earlier
        earlier(effort='high')
        root=self.start()
        job=self.workers.of('scan')[0]
        self.assertEqual((job.model,job.effort),('big-model','low'))
        self.assertEqual(self.view(root)['spent']['dollars'],0.02)

    def test_source_input_is_bounded_and_marks_partial_captures(self):
        root=self.start()
        record=self.engine._load(root);record['documents']={'done':'synthetic'}
        offered=[{'title':'Source '+str(i),'text':'x'*100_000} for i in range(50)]
        with mock.patch.object(self.engine,'_sources',return_value=([],offered)):
            work,_=outline.work(self.engine,root,self.engine._survey(root,record),record)
        sources=json.loads(work.prepared['inputs']['source-excerpts'])
        self.assertLessEqual(sum(len(one['excerpt']) for one in sources),outline.INPUT_CHARS)
        self.assertLessEqual(len(sources),40)
        self.assertTrue(all(one['partial'] for one in sources))

    def test_time_cap_keeps_an_editable_fallback_without_escalation(self):
        self.workers.queued['scan'] = [lambda tools, job: agents.Outcome(False, 'timeout', 'Synthetic timeout', seconds=180, cost=0.03)]
        root = self.start()
        plan = self.view(root)['training_plan']
        self.assertTrue(plan['scan']['fallback'])
        self.assertEqual(len(plan['outline']['sections']), 2)
        self.assertEqual(len(self.workers.jobs), 1)
        self.engine.wake(root)
        self.assertEqual(len(self.workers.jobs), 1)
        self.assertEqual(self.engine._load(root)['steps']['scan']['failed'], 0)

    def test_stopped_outline_can_save_but_cannot_start_research(self):
        root = self.start()
        self.engine.act(root, 'stop')
        plan = self.view(root)['training_plan']
        edited = copy.deepcopy(plan['outline']);edited['sections'][0]['title'] = 'Saved while stopped'
        saved = training_plan.decide(self.engine, root, plan['expected'], 'save', outline=edited)
        with self.assertRaises(WorkspaceError):
            training_plan.decide(self.engine, root, saved['training_plan']['expected'], 'approve', outline=edited)
        self.assertEqual(len(self.workers.jobs), 1)
        self.engine.act(root, 'resume')
        self.assertEqual(self.view(root)['training_plan']['outline']['sections'][0]['title'], 'Saved while stopped')
        self.assertEqual(len(self.workers.jobs), 1)

    def test_changed_inputs_and_active_workers_reject_approval(self):
        root = self.start();plan = self.view(root)['training_plan']
        self.engine._run(root).workers['synthetic-active'] = {}
        try:
            with self.assertRaises(WorkspaceError):
                training_plan.decide(self.engine, root, plan['expected'], 'approve', outline=plan['outline'])
        finally:
            self.engine._run(root).workers.clear()
        (root / 'intake.md').write_text((root / 'intake.md').read_text()+'\nChanged goal.\n')
        with self.assertRaises(WorkspaceError):
            training_plan.decide(self.engine, root, plan['expected'], 'approve', outline=plan['outline'])
        self.assertEqual(len(self.workers.jobs), 1)

    def test_stop_during_scan_keeps_partial_or_fallback_and_never_repeats_it(self):
        import threading,time
        for partial in (False,True):
            with self.subTest(partial=partial):
                engine=self.make(background=True,plan_first=True,outline_first=True,parallel_research=True)
                self.engine=engine
                title='Stopped scan '+str(int(partial))
                root=self.space.training(workspace.slugify(title))
                started=threading.Event()
                def blocked(tools,job):
                    started.set()
                    self.assertTrue(engine._run(root).stop.wait(10))
                    if partial:
                        self.assertTrue(tools.submit_artifact('scan',json.dumps(outline.seed('Kept partial')))[0])
                    return agents.Outcome(False,'stopped','Synthetic stop',cost=0.01,seconds=1)
                self.workers.queued['scan']=[blocked]
                self.start(title=title)
                self.assertTrue(started.wait(10))
                engine.act(root,'stop')
                deadline=time.monotonic()+10
                while engine._run(root).busy and time.monotonic()<deadline:time.sleep(0.01)
                self.assertFalse(engine._run(root).busy)
                record=engine._load(root)
                self.assertEqual(record['halt'],'stopped')
                self.assertEqual(record['outline_first']['scan']['fallback'],not partial)
                calls=len(self.workers.jobs)
                engine.act(root,'resume')
                deadline=time.monotonic()+10
                while engine._run(root).busy and time.monotonic()<deadline:time.sleep(0.01)
                self.assertEqual(len(self.workers.jobs),calls)
                self.assertTrue(engine.view(root)['training_plan']['outline'])
                engine.close()

    def test_approval_basis_reuses_hashes_until_a_selected_input_changes(self):
        root=self.start();record=self.engine._load(root);session=workspace.load(root)
        outline._digest.cache_clear()
        with mock.patch.object(workspace,'sha256_file',wraps=workspace.sha256_file) as hashing:
            before=outline.signature(root,session,record)
            first=hashing.call_count
            for _ in range(20):self.assertEqual(outline.signature(root,session,record),before)
            self.assertEqual(hashing.call_count,first)
            (root/'intake.md').write_text((root/'intake.md').read_text()+'\nNew learner goal.\n')
            self.assertNotEqual(outline.signature(root,session,record),before)
            self.assertGreater(hashing.call_count,first)

    def test_new_flow_has_a_record_version_older_runners_refuse(self):
        from runner import engine as engines
        root=self.start();record=self.engine._load(root)
        self.assertEqual(record['schema'],7)
        bad=[]
        old=copy.deepcopy(record);old['schema']=6;bad.append(old)
        missing=copy.deepcopy(record);missing.pop('outline_first');bad.append(missing)
        serial=copy.deepcopy(record);serial.pop('research_execution');bad.append(serial)
        for changed in bad:
            with mock.patch.object(workspace,'read_run',return_value=changed), self.assertRaises(WorkspaceError):
                engines.read_record(root)
        old.pop('outline_first')
        old.pop('material_flow')  # the saved pre-outline flow has neither new policy
        with mock.patch.object(workspace,'read_run',return_value=old):
            self.assertEqual(engines.read_record(root),old)
            self.assertFalse(outline.enabled(old))

    def test_full_approved_outline_is_not_pushed_into_bounded_helper_metadata(self):
        from studio_core import research_contract
        value=outline.seed('Synthetic')
        value['sections']=[{'id':'section-'+str(i),'title':'T'*160,
            'objectives':['O'*500]*6,'questions':['Q'*400]*3} for i in range(8)]
        value['personal_questions']=['P'*300]*8
        record={'outline_first':{'outline':value}}
        scope=outline.research_scope(record,'G'*10_000)
        self.assertLessEqual(research_contract.js_length(scope),4000)
        items=outline.research_items(value)
        self.assertEqual(len(items),8)
        self.assertTrue(all(research_contract.wrong_text(item['question']) is None for item in items))
        self.assertEqual(value['sections'][0]['objectives'],['O'*500]*6)
        value['personal_questions']=['😀'*300]*8
        with self.assertRaises(WorkspaceError):outline.research_items(value)

    def test_shape_and_template_are_checked(self):
        value = outline.seed('Synthetic')
        self.assertEqual(outline.checked(value), value)
        for edit in [lambda v: v.update(schema=True), lambda v: v.update(sections=[]),
                     lambda v: v['sections'][0].update(questions=[]),
                     lambda v: v['sections'][1].update(id=v['sections'][0]['id'])]:
            invalid = copy.deepcopy(value);edit(invalid)
            with self.assertRaises(WorkspaceError):
                outline.checked(invalid)
        template = json.loads((__import__('helpers').EXAMPLES / 'provisional-outline.json').read_text())
        self.assertTrue(outline.checked(template, minimum=2))
