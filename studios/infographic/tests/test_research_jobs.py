"""Optional research uses real pinned collection acceptance and synthetic isolated authors."""
import os
import sys
import time
import unittest
from unittest.mock import patch
from helpers import Isolated, ROOT
from runner import research_jobs, intake
from runner.workspace import Store
from studio_core import research_sources
sys.path.insert(0, str(ROOT/'tests'))
from synthesis_fixture import TEXT, dossier, review
RUNTIME = os.environ.get('STUDIO_TEST_RESEARCH_RUNTIME')


@unittest.skipUnless(RUNTIME, 'Select the pinned disposable Harness Research runtime.')
class ResearchJobsTests(Isolated):
    def setUp(self):
        super().setUp()
        self.store = Store.setup(self.workspace)
        self.p = self.store.create('Synthetic optional infographic research')
        source = research_sources.Sources(self.workspace / '.research-sources')
        draft = source.create()
        self.draft = source.mutate(draft['id'], draft['revision'], 'capture', kind='text', name='Synthetic notes', text=TEXT)
        self.calls = []
        parent = self
        class Author:
            def research(self, phase, payload, guidance, **options):
                parent.calls.append(phase)
                if phase == 'investigate':
                    source = payload['sources'][0]
                    value = dossier(payload['worker'], source['file'], source['origin'], source['permission'])
                    value['sources'][0]['original_file'] = source['original_file']
                    return {k:v for k,v in value.items() if k in ('schema','sources','facts')}
                if phase == 'synthesize':
                    parent.assertNotIn('Synthesis and independent review are pending.', str(payload.get('gaps')))
                    value = dossier(payload['worker'])
                    fact = payload['evidence']['facts'][0]['id']
                    value['sections'][0]['blocks'][0]['refs'] = [fact]
                    value['brief'][0]['blocks'][0]['refs'] = [fact]
                    value['findings'] = [{'id':'scope','title':'Synthetic scope','summary':{'text':TEXT,'kind':'summary','refs':[fact]},'support':[fact],'counter':[],'conditions':[],'implications':[],'gaps':[]}]
                    return {k:v for k,v in value.items() if k in ('schema','findings','sections','brief')}
                return review(payload['review_template'])
        self.jobs = research_jobs.Jobs(self.store, author=Author(), runtime=RUNTIME)

    def test_optional_job_checks_sources_and_preview_without_changing_project(self):
        ref = {'id':self.draft['id'], 'expected':self.draft['revision']}
        with patch.object(research_jobs.settings, 'snapshot', return_value={'assistant':{'agent':'codex'}}):
            first = self.jobs.start(self.p['id'], 0, ref)
            same = self.jobs.start(self.p['id'], 0, ref)
            self.assertEqual(first['request'], same['request'])
            deadline = time.monotonic()+25
            while self.jobs.active and time.monotonic()<deadline: time.sleep(.025)
        state = self.jobs.read(self.p['id'])
        self.assertEqual(state['state'],'complete',state)
        self.assertEqual(self.calls,['investigate','synthesize','review'])
        self.assertEqual(self.store.read(self.p['id'])['revision'],0)
        preview = self.jobs.control(self.p['id'],'preview')
        adopted = intake.adopt(self.store,self.p['id'],preview['id'],expected_revision=0)
        self.assertEqual(adopted['sources'][0]['kind'],'research')
        self.assertEqual(self.calls,['investigate','synthesize','review'])

    def test_captured_project_material_is_included_without_reupload_or_external_search(self):
        preview = intake.prepare(TEXT.encode(),kind='text',name='Primary synthetic material')
        self.p = intake.adopt(self.store,self.p['id'],preview['id'],expected_revision=0)
        draft = research_sources.Sources(self.workspace / '.research-sources').create()
        with patch.object(research_jobs.settings,'snapshot',return_value={'assistant':{'agent':'codex'}}):
            self.jobs.start(self.p['id'],self.p['revision'],{'id':draft['id'],'expected':draft['revision']})
            deadline=time.monotonic()+25
            while self.jobs.active and time.monotonic()<deadline: time.sleep(.025)
        result=self.jobs.read(self.p['id'])
        self.assertEqual(result['state'],'complete',result)
        self.assertEqual(self.calls,['investigate','synthesize','review'])
        self.assertEqual(self.store.read(self.p['id'])['revision'],self.p['revision'])
