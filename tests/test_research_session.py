"""Shared Harness Research 1.1 controller, using synthetic data and the real helper."""
import copy
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
import marketing_studio  # noqa: F401
from studio_core import research_session as session, research_contract as rc
from synthesis_fixture import TEXT, dossier, review

RUNTIME = os.environ.get('STUDIO_TEST_RESEARCH_RUNTIME')

@unittest.skipUnless(RUNTIME, 'Set STUDIO_TEST_RESEARCH_RUNTIME to the pinned disposable helper.')
class SessionTests(unittest.TestCase):
    def setUp(self):
        if session.capability(Path(RUNTIME)) is None: self.skipTest('This test needs collection protocol 1.')
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.task = {k: v for k, v in dossier('unused').items() if k in rc.TASK_FIELDS}
        self.task['planning_questions'] = [{'id': 'question-' + str(n), 'question': 'Synthetic question ' + str(n)} for n in range(4)]
        self.capture = self.root / 'capture.txt'; self.capture.write_text(TEXT)
        self.calls, self.states = [], []
        self.barrier = threading.Barrier(3)
        self.fail_area = self.refuse_fact = self.refuse_prose = False
        self.workflow = session.Workflow(RUNTIME)

    def invoke(self, phase, guidance, payload, offered, fetch):
        area = payload['_execution'].get('stream')
        self.calls.append((phase, area))
        if phase == 'investigate':
            if self.barrier: self.barrier.wait(10)
            if self.fail_area and area == 'area2':
                self.fail_area = False
                raise ValueError('Synthetic area failure')
            source = offered[0] if offered else {'file': 'sources/source.txt', 'origin': 'https://example.invalid/docs', 'permission': 'public', 'path': self.capture}
            value = dossier(payload['worker'], source['file'], source['origin'], source['permission'])
            if source.get('original'): value['sources'][0]['original_file'] = source['original']
            value = {k: value[k] for k in ('schema', 'sources', 'facts')}
            return json.dumps(value), [source]
        if phase == 'synthesize':
            ref = payload['evidence']['facts'][0]['id']
            value = dossier(payload['worker'])
            value['findings'] = [{**copy.deepcopy(value['findings'][0]), 'id': q['id'], 'support': [ref],
                'summary': {'text': 'More than one instance keeps capacity.', 'kind': 'summary', 'refs': [ref]}, 'conditions': []} for q in self.task['planning_questions']]
            value['sections'][0]['blocks'][0]['refs'] = [ref]
            value['brief'][0]['blocks'][0]['refs'] = [value['findings'][0]['id']]
            value = {k: value[k] for k in ('schema', 'findings', 'sections', 'brief')}
            return json.dumps(session.preparation(value, {'research_mode': 'compose', 'evidence_base': payload['evidence']})), []
        value = review(payload['review_template'])
        if self.refuse_fact:
            self.refuse_fact = False
            value['facts'][0].update(verdict='narrow', note='Synthetic located fact correction')
        if self.refuse_prose:
            self.refuse_prose = False
            value['prose'][0].update(verdict='narrow', note='Synthetic prose correction')
        return json.dumps(value), []

    def run_session(self, sources=()):
        return self.workflow.run(self.root, self.task, self.invoke, sources, progress=self.states.append)

    def test_concurrent_collection_uses_helper_registry_and_topic_handoff(self):
        facts, manifest = self.run_session()
        self.assertEqual(manifest['status'], 'complete')
        self.assertEqual(len(facts['facts']), 3)
        self.assertEqual(len({f['author'] for f in facts['facts']}), 3)
        case = session.case_for(self.root)
        registry = json.loads((case / '.harness-research/collection.json').read_text())
        self.assertEqual(registry['owner'], 'harness-research-collection')
        self.assertIsNotNone(registry['registry'])
        self.assertTrue((case / 'asset-manifest.json').is_file())
        self.assertEqual(self.states[-1]['phase'], 'complete')
        rc.publish(self.root / rc.CASE, self.root / 'research')
        self.assertEqual(rc.read_bundle(self.root / 'research')[1]['digest'], manifest['digest'])
        self.calls.clear(); self.barrier = None
        self.run_session()
        self.assertFalse(self.calls, 'A completed exact request resumes without another provider job')

    def test_failed_area_keeps_successful_helper_packets_for_retry(self):
        self.fail_area = True
        with self.assertRaisesRegex(ValueError, 'Synthetic area failure'): self.run_session()
        self.barrier = None; self.calls.clear()
        self.run_session()
        self.assertEqual([area for phase, area in self.calls if phase == 'investigate'], ['area2'])

    def test_selected_upload_retains_original_and_selected_permission(self):
        self.task['source_mode'] = 'selected'
        facts, _ = self.run_session([{'file': 'sources/notes.txt', 'path': self.capture, 'text': TEXT,
            'title': 'Synthetic notes', 'origin': 'Supplied notes', 'permission': 'selected'}])
        self.assertTrue(all(s['permission'] == 'selected' for s in facts['sources']))
        self.assertTrue(all(s.get('original_file') for s in facts['sources']))

    def test_prose_correction_does_not_recollect_evidence(self):
        self.refuse_prose = True; self.barrier = None
        self.run_session()
        self.assertEqual(sum(p == 'investigate' for p, _ in self.calls), 3)
        self.assertEqual(sum(p == 'review' for p, _ in self.calls), 2)

    def test_fact_correction_recollects_only_affected_area(self):
        self.refuse_fact = True; self.barrier = None
        self.run_session()
        self.assertEqual(sum(p == 'investigate' for p, _ in self.calls), 4)
        self.assertEqual(sum(p == 'review' for p, _ in self.calls), 2)

    def test_changed_original_stops_late_adoption_and_keeps_evidence(self):
        self.task['source_mode'] = 'selected'
        self.barrier = None
        original = self.invoke
        def change(phase, *args):
            result = original(phase, *args)
            if phase == 'investigate': self.capture.write_text('Changed source outside a decision')
            return result
        self.invoke = change
        with self.assertRaisesRegex(ValueError, 'selected original changed'):
            self.run_session([{'file':'sources/notes.txt','text':TEXT,'origin':'Supplied notes','title':'Notes',
                               'original_path':self.capture,'permission':'selected'}])
        self.assertFalse((self.root/'research/output.json').exists())

    def test_unconfirmed_terminal_invocation_blocks_generation_restart(self):
        self.barrier = None
        class Unconfirmed(ValueError): terminal_confirmed = False
        def uncertain(*args): raise Unconfirmed('Synthetic transport lost terminal confirmation')
        self.invoke = uncertain
        with self.assertRaisesRegex(ValueError, 'terminal confirmation'): self.run_session()
        with self.assertRaisesRegex(ValueError, 'no confirmed terminal'): self.run_session()
        self.task['scope'] = 'A changed synthetic scope must not release unresolved capacity.'
        with self.assertRaisesRegex(ValueError, 'no confirmed terminal'): self.run_session()

    def test_stop_requires_explicit_new_generation_after_terminal_confirmation(self):
        self.barrier = None
        self.run_session()
        case = session.case_for(self.root)
        self.workflow.command(case,'collection','stop')
        with self.assertRaisesRegex(ValueError,'explicitly retry'): self.run_session()
        self.workflow.run(self.root,self.task,self.invoke,restart_stopped=True)
        self.assertEqual(self.workflow.command(case,'collection','status')['generation'],2)
