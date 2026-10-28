"""Real pinned helper, synthetic separate author/reviewer; no provider or public reads."""
import json
import os
from pathlib import Path
import sys
import unittest
from helpers import Isolated,ROOT
from runner import research,intake,sources
from runner.contracts import Invalid
from runner.workspace import Store
from studio_core import research_contract as contract
sys.path.insert(0,str(ROOT/'tests'))
from synthesis_fixture import TEXT,dossier,review
RUNTIME=os.environ.get('STUDIO_TEST_RESEARCH_RUNTIME')


@unittest.skipUnless(RUNTIME,'Select the exact local Harness Research source for integration.')
class ResearchTests(Isolated):
    def setUp(self):
        super().setUp();self.store=Store.setup(self.workspace);self.p=self.store.create('Synthetic infographic research')
        self.task=research.task(self.p);self.calls=[];self.source=self.temp/'source.txt';self.source.write_text(TEXT)
        def invoke(phase,guidance,payload,selected,fetch):
            self.calls.append((phase,fetch))
            answer=dossier(payload['worker'],permission='selected') if phase=='author' else review(payload['review_template'])
            return json.dumps(answer),[{'file':'sources/source.txt','path':self.source,'origin':'https://example.invalid/docs','offered':True}]
        contract.Workflow(RUNTIME).run(self.temp/'case',self.task,invoke)
        self.case=self.temp/'case'/contract.CASE

    def test_verified_complete_bundle_is_brief_first_and_keeps_exact_helper_review(self):
        preview=research.prepare(self.case,expected_task=self.task,runtime=RUNTIME)
        self.assertEqual(self.calls,[('author',False),('review',False)])
        p=intake.adopt(self.store,self.p['id'],preview['id'],expected_revision=0)
        source=p['sources'][0];value=sources.read(self.store,p,source)
        self.assertTrue(value.startswith((self.case/'research/brief.md').read_text()))
        self.assertEqual(source['provenance']['helper'],contract.capability(Path(RUNTIME)))
        self.assertEqual(source['provenance']['task']['source_mode'],'selected')
        original=self.workspace/'projects'/p['id']/source['file'];original.write_bytes(b'Changed capture')
        with self.assertRaises(Invalid):sources.read(self.store,p,source)

    def test_wrong_task_missing_capture_and_unreviewed_output_refused(self):
        with self.assertRaisesRegex(Invalid,'differs'):research.prepare(self.case,expected_task={**self.task,'source_mode':'public'},runtime=RUNTIME)
        (self.case/'sources/source.txt').unlink()
        with self.assertRaises(ValueError):research.prepare(self.case,expected_task=self.task,runtime=RUNTIME)

    def test_stale_review_or_helper_verification_cannot_feed_a_claim(self):
        with self.assertRaisesRegex(Invalid,'did not verify'):research.prepare(self.case,expected_task=self.task,runtime=RUNTIME,verifier=lambda root:{'status':'stale','digest':'changed'})
        facts_path=self.case/'research/facts.json';facts=json.loads(facts_path.read_text());facts['review']['accepted']=False;facts_path.write_text(json.dumps(facts))
        with self.assertRaises(ValueError):research.prepare(self.case,expected_task=self.task,runtime=RUNTIME)
        self.assertEqual(self.store.read(self.p['id'])['revision'],0)
