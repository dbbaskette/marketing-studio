"""Approved teaching sections through the pinned collection protocol, all synthetic."""
import copy
import json
import os
from pathlib import Path
import unittest

from runner_support import StudioCase, URL, BLUEPRINT, DOCUMENT
from runner import agents, outline_first as outline, research, training_plan
from studio_core import research_contract, research_session
from synthesis_fixture import TEXT, dossier, review

RUNTIME = os.environ.get('STUDIO_TEST_RESEARCH_RUNTIME')


@unittest.skipUnless(RUNTIME, 'Set STUDIO_TEST_RESEARCH_RUNTIME for pinned helper checks.')
class OutlineIntegrationTests(StudioCase):
    def setUp(self):
        super().setUp()
        self.engine.plan_first = self.engine.outline_first = self.engine.parallel_research = True
        self.research = research.Research(Path(RUNTIME))
        self.web.page(URL, TEXT, 'text/plain')
        self.phases, self.tasks, self.scans = [], [], []
        self.workers.then('scan', self.scanner)
        self.workers.then('research-result', *([self.researcher] * 12))
        self.workers.then('blueprint', self.blueprint)
        self.workers.then('document', self.document)
        self.supplied = False

    def read_all(self, tools, name):
        number=1;pieces=[]
        while True:
            okay,said=tools.read_input(name,part=number)
            self.assertTrue(okay,said)
            if not said.startswith('['):return said
            head,body=said.split('\n\n',1)
            pieces.append(body)
            if 'this is the last part' in head:return ''.join(pieces)
            number+=1

    def scanner(self, tools, job):
        self.scans.append(job)
        value = outline.seed('Synthetic restart')
        value['sections'].append({'id':'section-limits','title':'Limits',
            'objectives':['Recognize limitations.'],'questions':['What limits apply?']})
        accepted = tools.submit_artifact('scan', json.dumps(value))
        self.assertTrue(accepted[0], accepted)
        return agents.Outcome(True, cost=0.02, seconds=1)

    def researcher(self, tools, job):
        try:
            return self._researcher(tools,job)
        except Exception:
            import traceback
            traceback.print_exc()
            raise

    def _researcher(self, tools, job):
        payload = json.loads(self.read_all(tools,'research-task'))
        if 'questions' in payload:
            self.phases.append('investigate');self.tasks.append(payload)
            if not self.supplied:
                self.assertTrue(tools.save_source(URL)[0])
            source = next(s for s in tools._index() if s.get('offered')) if self.supplied else tools._index()[0]
            value = dossier(payload['worker'], source['file'], source['url'], 'selected' if self.supplied else 'public')
            if self.supplied:
                value['sources'][0]['original_file'] = source['original']
                self.assertEqual(job.profile,'write','supplied-only research has no web tools')
            value = {key:value[key] for key in ('schema','sources','facts')};value['gaps']=[]
        elif 'evidence' in payload and 'review_template' not in payload:
            self.phases.append('synthesize')
            evidence = payload['evidence'];fact = evidence['facts'][0]['id']
            value = dossier(payload['worker'])
            questions = payload['task']['planning_questions']
            value['findings'] = [{**copy.deepcopy(value['findings'][0]),'id':q['id'],
                'summary': {'text':'More than one instance keeps capacity.','kind':'summary','refs':[fact]},
                'support':[fact],'conditions':[]} for q in questions]
            value['sections'] = [{'id':q['id'],'title':q['question'].split('\n')[0].removeprefix('Teaching section: '),
                'blocks':[{'text':'More than one instance keeps capacity.','kind':'summary','refs':[fact]}]} for q in questions]
            value['brief'][0]['blocks'][0]['refs']=[questions[0]['id']]
            value={key:value[key] for key in ('schema','findings','sections','brief')}
        else:
            self.phases.append('review')
            for source in tools._index():self.assertTrue(tools.read_source(source['id'],original=bool(source.get('original')))[0])
            value=review(payload['review_template'])
        accepted=tools.submit_artifact('research-result',json.dumps(value))
        self.assertTrue(accepted[0], accepted)

    def material(self, tools, name, text):
        approved = json.loads(self.read_all(tools,'approved-teaching-outline'))
        first = approved['sections'][0]['id']
        self.assertTrue(approved['sections'])
        rewritten=text
        for name_id in ('availability','instance-min','health-checks','zero-downtime'):
            rewritten=rewritten.replace('[R:'+name_id+']','[R:'+first+']')
        accepted = tools.submit_artifact(name,rewritten)
        self.assertTrue(accepted[0],accepted)

    def blueprint(self, tools, job):
        self.material(tools,'blueprint',BLUEPRINT)

    def document(self, tools, job):
        self.material(tools,'document',DOCUMENT)

    def begin_outline(self, **changes):
        return self.start(materials=['document'], **changes)

    def test_removed_section_never_enters_research_and_materials_receive_scope(self):
        root = self.begin_outline(research_questions=['Which failure modes remain?'])
        before = self.view(root)
        self.assertEqual(len(self.scans),1)
        self.assertEqual(self.phases,[])
        self.assertEqual(before['spent']['dollars'],0.02)
        plan=before['training_plan'];value=copy.deepcopy(plan['outline'])
        value['sections']=[value['sections'][0],value['sections'][2]]
        value['sections'][0]['title']='Approved foundations'
        after=training_plan.decide(self.engine,root,plan['expected'],'approve',outline=value)
        self.assertFalse(after['problem'],after['problem'])
        self.assertEqual(after['state'],'done')
        self.assertCountEqual(self.phases,['investigate','investigate','synthesize','review'])
        questions=[q for task in self.tasks for q in task['questions']]
        self.assertEqual({q['id'] for q in questions},{'section-foundations','section-limits'})
        self.assertFalse(any(q['id']=='section-application' for q in questions))
        self.assertTrue(any('Which failure modes remain?' in q['question'] for q in questions))
        facts,_=research_contract.read_bundle(root/'research')
        self.assertTrue(facts['review']['accepted'])
        self.assertEqual([s['title'] for s in facts['sections']],['Approved foundations','Limits'])
        self.assertEqual(len(self.workers.of('blueprint')),1)
        self.assertEqual(len(self.workers.of('document')),1)
        self.assertEqual(len(self.scans),1)

    def test_introductory_database_request_produces_a_guide_with_bounded_research(self):
        root = self.begin_outline(topic='Minimal basics of PostgreSQL HA/DR, Helm and operators, and self-support responsibilities')
        plan = self.view(root)['training_plan']
        after = training_plan.decide(self.engine, root, plan['expected'], 'approve', outline=plan['outline'])
        self.assertIsNone(after['problem'], after['problem'])
        self.assertEqual(after['state'], 'done')
        self.assertEqual(len(self.workers.of('document')), 1)
        self.assertTrue(self.tasks)
        for task in self.tasks:
            self.assertEqual(task['task']['research_policy'], outline.research_quality.FOCUSED)
            self.assertIn('tutorial', task['return'])
            self.assertIn('at most 8 essential facts', task['return'])
        self.engine.wake(root)
        self.assertEqual(len(self.scans),1)

    def test_supplied_only_stays_selected_after_approval(self):
        self.supplied=True
        from runner_support import FORM
        from runner import pipeline
        from studio_core import research_sources
        store=research_sources.Sources(self.space.root/'.research-sources')
        draft=store.create()
        draft=store.mutate(draft['id'],draft['revision'],'capture',kind='text',name='Synthetic notes',text=TEXT)
        root=Path(self.engine.start(pipeline.check_form({**FORM,'flow':'desk','materials':['document']}),
            research_inputs={'id':draft['id'],'expected':draft['revision']})['path'])
        plan=self.view(root)['training_plan']
        after=training_plan.decide(self.engine,root,plan['expected'],'approve',outline=plan['outline'])
        self.assertFalse(after['problem'],after['problem'])
        self.assertEqual(after['state'],'done')
        self.assertEqual(len(self.tasks),3)
        self.assertTrue(all(task['task']['source_mode']=='selected' for task in self.tasks))
        self.assertEqual(self.engine._load(root)['outline_first']['scan']['searches'],0)

    def test_explicit_adoption_preserves_pending_case_and_spend_and_starts_nothing(self):
        from unittest import mock
        self.engine.outline_first=False
        with mock.patch.object(self.engine,'wake'):
            root=self.begin_outline()
        self.engine.act(root,'stop')
        record=self.engine._load(root)
        record['model_profiles']={'schema':1,'policy':2,'agent':record['agent'],'mode':'by_task','profiles':{
            'quick':{'model':'big-model','effort':'low','source':'explicit'},
            'main':{'model':'big-model','effort':'high','source':'explicit'},
            'complex':{'model':'big-model','effort':'max','source':'explicit'}}}
        self.engine._store(root,record)
        private=root/research_contract.CASE;private.mkdir(exist_ok=True)
        (private/'synthetic-progress.json').write_text('{"kept":"unfinished"}')
        before=len(self.workers.jobs)
        preview=outline.adoption(self.engine,root)
        self.assertTrue(preview['can_adopt'],preview)
        with self.assertRaises(Exception):outline.adoption(self.engine,root,'old-preview')
        result=outline.adoption(self.engine,root,preview['expected'])
        self.assertEqual(result['state'],'stopped')
        self.assertEqual(len(self.workers.jobs),before)
        self.assertFalse(private.exists())
        self.assertEqual(len(list((root/'work/outline-flow-history').glob('*/synthetic-progress.json'))),1)
        self.engine.act(root,'resume')
        self.assertEqual(len(self.scans),1)
        self.assertEqual((self.scans[0].model,self.scans[0].effort),('big-model','low'))
        self.assertTrue(self.view(root)['training_plan']['outline_first'])
