"""Shared Harness Research 1.1 controller, using synthetic data and the real helper."""
import copy
import hashlib
import json
import os
from pathlib import Path
import secrets
import tempfile
import threading
import unittest
from unittest import mock
import marketing_studio  # noqa: F401
from studio_core import research_session as session, research_contract as rc
from studio_core.shared_runner.worker_tools import tidy
from synthesis_fixture import TEXT, dossier, review

# Text as a Google Slides deck can arrive: double spaces, trailing spaces and blank lines.
UNTIDY = ('Overview of  Synthetic  Queues   \n' + TEXT.replace('. More', '.  More')
          + '  \n\n\n\nDATA TSL \n')
# How an earlier version registered captures: the text exactly as it came.
AS_IT_CAME = mock.patch.object(session, 'capture_text', lambda text, kept: text)

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
        self.fail_area = self.refuse_fact = self.refuse_prose = self.fail_synthesis = False
        self.handed = None
        self.workflow = session.Workflow(RUNTIME)

    def invoke(self, phase, guidance, payload, offered, fetch):
        area = payload['_execution'].get('stream')
        self.calls.append((phase, area))
        if phase == 'investigate':
            if self.barrier: self.barrier.wait(10)
            if self.fail_area and area == 'area2':
                self.fail_area = False
                raise ValueError('Synthetic area failure')
            if self.handed:
                return self.cite_every(payload, self.handed(offered))
            source = offered[0] if offered else {'file': 'sources/source.txt', 'origin': 'https://example.invalid/docs', 'permission': 'public', 'path': self.capture}
            value = dossier(payload['worker'], source['file'], source['origin'], source['permission'])
            if source.get('original'): value['sources'][0]['original_file'] = source['original']
            value = {k: value[k] for k in ('schema', 'sources', 'facts')}
            return json.dumps(value), [source]
        if phase == 'synthesize':
            if self.fail_synthesis:
                self.fail_synthesis = False
                raise ValueError('Synthetic synthesis failure')
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

    def cite_every(self, payload, captures):
        """An investigator's evidence, citing every source its job handed back."""
        value = dossier(payload['worker'])
        value['sources'] = [{**value['sources'][0], 'id': 'source-' + str(number), 'file': capture['file'],
            'origin': capture.get('origin', capture.get('url')), 'permission': capture['permission'],
            **({'original_file': capture['original']} if capture.get('original') else {})}
            for number, capture in enumerate(captures, 1)]
        value['facts'][0]['citations'] = [{'source': source['id'], 'quote': 'More than one instance keeps capacity.'}
                                          for source in value['sources']]
        return json.dumps({k: value[k] for k in ('schema', 'sources', 'facts')}), captures

    def worker_job(self, offered):
        """What Training Studio's and Presentation Studio's worker tools hand back: each source
        kept tidied in the job's own folder, the copy the assistant reads and quotes."""
        folder, handed = self.root / 'jobs' / secrets.token_hex(6), []
        for number, source in enumerate(offered, 1):
            if not getattr(self, 'as_it_came', False):
                self.assertEqual(Path(source['path']).read_bytes(), tidy(source['text']).encode(),
                                 'The registered capture is the text the assistant is given')
            local = 'sources/offered-' + str(number) + '.txt'
            rc.write(folder, local, tidy(source['text']))
            if source.get('original_path'):
                rc.write(folder, source['original'], Path(source['original_path']).read_bytes())
            handed.append({'id': 's' + str(number), 'url': source['origin'], 'title': source['title'],
                'file': source['file'], 'local': local, 'offered': True, 'permission': source['permission'],
                'original': source.get('original'), 'path': folder / local,
                'original_path': folder / source['original'] if source.get('original') else None})
        return handed

    def text_job(self, offered):
        """What Blog Studio's and Infographic Studio's text transport hands back: the offered
        sources themselves, whose text the assistant reads and its quotes are checked in."""
        for source in offered:
            self.assertEqual(Path(source['path']).read_text(), source['text'])
        return list(offered)

    @staticmethod
    def untidy_sources(permissions=('selected', 'public')):
        return [{'file': 'sources/deck.txt', 'text': UNTIDY, 'title': 'Synthetic deck',
                 'origin': 'Supplied synthetic deck', 'permission': 'selected'},
                {'file': 'sources/page.txt', 'text': UNTIDY, 'title': 'Synthetic page',
                 'origin': 'https://example.invalid/untidy', 'permission': 'public'}][:len(permissions)]

    def registered(self):
        """The capture hash of each studio-registered source, by origin."""
        entries = json.loads((session.case_for(self.root) / 'sources.json').read_text())['entries']
        return {e['origin']: e['capture_sha256'] for e in entries
                if e.get('capture_sha256') and not e['id'].startswith('source-')}

    @staticmethod
    def sha(text):
        return hashlib.sha256(text.encode()).hexdigest()

    def test_untidy_selected_and_public_sources_pass_the_dossier_check(self):
        self.task['source_mode'] = 'mixed'; self.barrier = None; self.handed = self.worker_job
        facts, manifest = self.run_session(self.untidy_sources())
        self.assertEqual(manifest['status'], 'complete')
        self.assertEqual({s['permission'] for s in facts['sources']}, {'selected', 'public'})
        self.assertEqual(set(self.registered().values()), {self.sha(tidy(UNTIDY))})
        integrity = json.loads((session.case_for(self.root) / 'asset-manifest.json').read_text())['integrity']
        self.assertEqual(integrity, 'verified')

    def test_already_tidy_sources_keep_their_capture_hash(self):
        self.task['source_mode'] = 'mixed'; self.barrier = None; self.handed = self.worker_job
        tidied = TEXT + '\n'
        self.assertEqual(tidy(tidied), tidied)
        _, manifest = self.run_session([{**s, 'text': tidied} for s in self.untidy_sources()])
        self.assertEqual(manifest['status'], 'complete')
        self.assertEqual(set(self.registered().values()), {self.sha(tidied)})

    def test_untidied_registration_recovers_on_try_again_without_reinvestigating(self):
        # The shape #295 left behind: the capture registered untidied, kept investigations
        # holding the tidied copy, and the dossier check refusing the synthesis.
        self.task['source_mode'] = 'selected'; self.barrier = None; self.handed = self.worker_job
        sources = self.untidy_sources(['selected'])
        self.as_it_came = True
        with AS_IT_CAME, self.assertRaisesRegex(ValueError, 'capture differs from the accepted asset inventory'):
            self.run_session(sources)
        self.as_it_came = False
        self.assertEqual(list(self.registered().values()), [self.sha(UNTIDY)])
        self.assertEqual([phase for phase, _ in self.calls], ['investigate'] * 3 + ['synthesize'])
        self.calls.clear()
        _, manifest = self.run_session(sources)
        self.assertEqual(manifest['status'], 'complete')
        self.assertEqual([phase for phase, _ in self.calls], ['synthesize', 'review'],
                         'The kept investigations are reused; synthesis and review run again')
        self.assertEqual(list(self.registered().values()), [self.sha(tidy(UNTIDY))])
        self.calls.clear()
        self.run_session(sources)
        self.assertFalse(self.calls, 'The recovered research resumes complete')

    def test_text_transport_kept_untidied_evidence_stays_valid(self):
        # Blog Studio and Infographic Studio gave investigators the registered text as it came.
        # Their kept investigations hold it, so it stays registered and their work stays valid.
        self.task['source_mode'] = 'mixed'; self.barrier = None; self.handed = self.text_job
        sources = self.untidy_sources()
        self.fail_synthesis = True
        with AS_IT_CAME, self.assertRaisesRegex(ValueError, 'Synthetic synthesis failure'):
            self.run_session(sources)
        self.calls.clear()
        _, manifest = self.run_session(sources)
        self.assertEqual(manifest['status'], 'complete')
        self.assertEqual([phase for phase, _ in self.calls], ['synthesize', 'review'])
        self.assertEqual(set(self.registered().values()), {self.sha(UNTIDY)})
        self.calls.clear()
        self.run_session(sources)
        self.assertFalse(self.calls, 'Completed research resumes without another provider job')

    def test_text_transport_registers_and_offers_tidied_text_for_new_research(self):
        self.task['source_mode'] = 'mixed'; self.barrier = None; self.handed = self.text_job
        _, manifest = self.run_session(self.untidy_sources())
        self.assertEqual(manifest['status'], 'complete')
        self.assertEqual(set(self.registered().values()), {self.sha(tidy(UNTIDY))})

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

    def test_live_agents_follow_actual_invocations_in_every_phase(self):
        original = self.invoke
        def observed(phase, guidance, payload, offered, fetch):
            active = self.states[-1]['agents']['active']
            self.assertIn(payload['worker'], [a['id'] for a in active])
            if phase != 'investigate':
                self.assertEqual(self.states[-1]['agents']['count'], 1)
                self.assertEqual(active[0]['phase'], phase)
            return original(phase, guidance, payload, offered, fetch)
        self.invoke = observed
        self.run_session()
        self.assertEqual(max(s['agents']['count'] for s in self.states), 3)
        self.assertEqual(self.states[-1]['agents'], {'count': 0, 'unconfirmed': 0, 'active': []})

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
        next_round = [s for s in self.states if s['round'] == 2]
        self.assertNotIn('investigate', [s['phase'] for s in next_round])
        self.assertTrue(all(s['status'] == 'kept' for s in next_round[0]['streams']))
        self.assertEqual(next_round[0]['correction']['areas'], [])

    def test_fact_correction_recollects_only_affected_area(self):
        self.refuse_fact = True; self.barrier = None
        self.run_session()
        self.assertEqual(sum(p == 'investigate' for p, _ in self.calls), 4)
        self.assertEqual(sum(p == 'review' for p, _ in self.calls), 2)
        next_round = [s for s in self.states if s['round'] == 2 and s['phase'] == 'investigate']
        self.assertEqual(len(next_round[0]['correction']['areas']), 1)
        self.assertIn('Synthetic located fact correction', next_round[0]['correction']['notes'])
        self.assertEqual(sum(a['status'] == 'kept' for a in next_round[0]['streams']), 2)
        self.assertEqual(next_round[0]['round_limit'], rc.ROUNDS)

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
        self.assertIsNone(self.states[-1]['agents']['count'])
        self.assertGreater(self.states[-1]['agents']['unconfirmed'], 0)
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


class CaptureTextTests(unittest.TestCase):
    """Which text a source is registered with, decided from that source's kept copies alone."""
    def test_each_source_decides_from_its_own_kept_copies(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            first, second = 'sources/selected/first.txt', 'sources/selected/second.txt'
            # The first source's legacy investigation kept it untidied; another source's
            # kept copy happens to hold exactly the first one's tidied text.
            rc.write(target, 'sources/collection/area1/1/' + first, UNTIDY)
            rc.write(target, 'sources/collection/area2/1/' + second, tidy(UNTIDY))
            rc.write(target, 'sources/collection/area1/1/documents/original.txt', tidy(UNTIDY))
            self.assertEqual(session.kept_copies(target, first), {hashlib.sha256(UNTIDY.encode()).hexdigest()})
            self.assertEqual(session.capture_text(UNTIDY, session.kept_copies(target, first)), UNTIDY)
            self.assertEqual(session.capture_text(tidy(UNTIDY), session.kept_copies(target, second)), tidy(UNTIDY))
            rc.write(target, 'sources/collection/area1/2/' + first, tidy(UNTIDY))
            self.assertEqual(session.capture_text(UNTIDY, session.kept_copies(target, first)), tidy(UNTIDY),
                             'Once the tidied text is kept, it is the one registered')
            self.assertEqual(session.capture_text(UNTIDY, session.kept_copies(target, 'sources/selected/new.txt')),
                             tidy(UNTIDY))
