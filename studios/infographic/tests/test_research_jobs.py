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

    def run_job(self, during=None):
        """Start research, call `during(project)` while its investigation runs, and wait."""
        import threading
        reached, release = threading.Event(), threading.Event()
        author = self.jobs.author
        original = type(author).research
        def research(this, phase, payload, guidance, **options):
            if phase == 'investigate' and not reached.is_set():
                reached.set()
                release.wait(10)
            return original(this, phase, payload, guidance, **options)
        ref = {'id': self.draft['id'], 'expected': self.draft['revision']}
        with patch.object(type(author), 'research', research), \
                patch.object(research_jobs.settings, 'snapshot', return_value={'assistant': {'agent': 'codex'}}):
            self.jobs.start(self.p['id'], self.store.read(self.p['id'])['revision'], ref)
            self.assertTrue(reached.wait(10))
            if during:
                during(self.store.read(self.p['id']))
            release.set()
            deadline = time.monotonic() + 25
            while self.jobs.active and time.monotonic() < deadline: time.sleep(.025)
        return self.jobs.read(self.p['id'])

    def test_a_rename_does_not_stop_running_research_and_verified_research_is_kept(self):
        renamed = []
        def rename(project):
            renamed.append(self.store.edit_brief(project['id'], {**project['brief'], 'title': 'Renamed research'},
                                                 expected_revision=project['revision']))
        state = self.run_job(rename)
        self.assertEqual(renamed[0]['revision'], 1)
        self.assertEqual(state['state'], 'complete', state)
        # Kept in the (disposable) Document Library as soon as it was verified.
        self.assertEqual(state['kept']['state'], 'kept', state)
        from studio_core.document_library.store import opened
        kept = opened().describe(state['kept']['document'])
        self.assertEqual(kept['kind'], 'research')
        # Use research adds the findings as a source in one step.
        used = self.jobs.control(self.p['id'], 'use')
        self.assertEqual(used['project']['sources'][-1]['kind'], 'research')

    def test_an_edit_to_what_research_reads_still_stops_it(self):
        def audience(project):
            self.store.edit_brief(project['id'], {**project['brief'], 'audience': 'Another audience'},
                                  expected_revision=project['revision'])
        state = self.run_job(audience)
        self.assertEqual(state['state'], 'failed', state)
        self.assertNotIn('kept', state)

    def test_research_from_the_library_made_for_something_else_is_imported_and_says_so(self):
        from runner import research, sources
        state = self.run_job()
        self.assertEqual(state['kept']['state'], 'kept', state)
        other = self.store.create('Another infographic')
        other = self.store.edit_brief(other['id'], {**other['brief'], 'audience': 'Finance leads',
                                                    'purpose': 'Explain a budget'}, expected_revision=0)
        task = research.task(other)
        # The character-for-character check still stands for a research case folder.
        case = research_jobs.research_session.case_for(self.jobs.folder(self.p['id']) / state['request'])
        with self.assertRaisesRegex(Exception, 'differs from this infographic task'):
            research.prepare(case, expected_task=task, runtime=RUNTIME)
        preview = research.from_library(state['kept']['document'], state['kept']['revision'], expected_task=task)
        self.assertTrue(preview['different'])
        self.assertEqual(preview['made_for']['audience'], 'General readers; explain unfamiliar terminology.')
        self.assertEqual(preview['provenance']['task'], preview['made_for'], 'The bundle’s own task is recorded.')
        self.assertEqual(preview['provenance']['library'], {'id': state['kept']['document'],
                                                           'revision': state['kept']['revision']})
        adopted = intake.adopt(self.store, other['id'], preview['id'], expected_revision=other['revision'])
        source = adopted['sources'][-1]
        self.assertEqual(source['kind'], 'research')
        self.assertTrue(sources.read(self.store, adopted, source).strip())
