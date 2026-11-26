"""Optional research uses real pinned collection acceptance and synthetic isolated authors."""
import os
import sys
import time
import unittest
from unittest.mock import patch
from helpers import Isolated, ROOT
from runner import research_jobs, intake
from runner.workspace import Store
from studio_core import research_sources, research_units
sys.path.insert(0, str(ROOT/'tests'))
from synthesis_fixture import TEXT, dossier, review
RUNTIME = os.environ.get('STUDIO_TEST_RESEARCH_RUNTIME')
# A new request on Harness Research 1.6.0 checks its one source's unit, then the final unit
# (#378); on an older one, one review.
CHECKS = ['review'] * (2 if RUNTIME and research_units.capability(RUNTIME) else 1)


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
        self.assertEqual(self.calls,['investigate','synthesize']+CHECKS)
        self.assertEqual(self.store.read(self.p['id'])['revision'],0)
        preview = self.jobs.control(self.p['id'],'preview')
        adopted = intake.adopt(self.store,self.p['id'],preview['id'],expected_revision=0)
        self.assertEqual(adopted['sources'][0]['kind'],'research')
        # #550: the research bundle built from supplied notes names no folder of this computer.
        import tempfile
        from pathlib import Path
        from studio_core import research_contract, research_session
        root, saved = self.jobs._state(self.p['id'])
        self.assertEqual(saved['execution'].get('review'), research_units.entry(RUNTIME))
        output = research_contract.output_root(research_session.case_for(root))
        facts, manifest = research_contract.read_bundle(output)
        self.assertTrue(all(s['origin'].startswith('supplied:') for s in facts['sources'] if s['permission'] == 'selected')
                        or not research_units.capability(RUNTIME))
        places = {str(self.workspace), str(Path(self.workspace).resolve()), tempfile.gettempdir(),
                  str(Path(tempfile.gettempdir()).resolve()), str(Path.home())}
        for name in [entry['file'] for entry in manifest['artifacts']] + ['output.json']:
            said = (output / name).read_bytes().decode('utf-8', 'replace')
            for place in places:
                self.assertNotIn(place, said, name)
        self.assertEqual(self.calls,['investigate','synthesize']+CHECKS)

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
        self.assertEqual(self.calls,['investigate','synthesize']+CHECKS)
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

    def test_research_is_retried_after_a_rename_against_the_current_revision(self):
        self.assertEqual(self.run_job()['state'], 'complete')
        project = self.store.read(self.p['id'])
        self.store.edit_brief(project['id'], {**project['brief'], 'title': 'Renamed before retry'},
                              expected_revision=project['revision'])
        with patch.object(research_jobs.settings, 'snapshot', return_value={'assistant': {'agent': 'codex'}}):
            self.jobs.control(self.p['id'], 'retry')
            deadline = time.monotonic() + 25
            while self.jobs.active and time.monotonic() < deadline: time.sleep(.025)
        self.assertEqual(self.jobs.read(self.p['id'])['state'], 'complete')

    def test_use_research_asks_before_acknowledging_its_gaps(self):
        from runner import research
        self.assertEqual(self.run_job()['state'], 'complete')
        prepare = research.prepare
        with patch.object(research, 'prepare', side_effect=lambda *a, **k: {**prepare(*a, **k), 'warnings': ['Synthetic gap.']}):
            asked = self.jobs.control(self.p['id'], 'use')
            self.assertTrue(asked['needs_acknowledgement'])
            self.assertEqual(asked['warnings'], ['Synthetic gap.'])
            self.assertEqual(self.store.read(self.p['id'])['sources'], [], 'Nothing is added until the person acknowledges.')
            used = self.jobs.control(self.p['id'], 'use', acknowledge_warnings=True)
        self.assertEqual(used['project']['sources'][-1]['kind'], 'research')
