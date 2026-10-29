"""Synthetic evidence only: parallelism, pinned-helper validation and recovery."""
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest

import marketing_studio  # noqa: F401
from studio_core import research_contract as rc, research_parallel as parallel, research_timing
from studio_core.research_parallel_native import Reservations
from synthesis_fixture import TEXT, dossier, review

RUNTIME = os.environ.get('STUDIO_TEST_RESEARCH_RUNTIME')


class TimingTests(unittest.TestCase):
    def test_union_is_not_the_sum_and_gaps_are_not_called_pauses(self):
        rows = [{'started_at': '2026-01-01T00:00:10Z', 'ended_at': '2026-01-01T00:00:30Z', 'seconds': 20},
                {'started_at': '2026-01-01T00:00:20Z', 'ended_at': '2026-01-01T00:00:40Z', 'seconds': 20}]
        got = research_timing.account('2026-01-01T00:00:00Z', rows,
            [{'started_at': '2026-01-01T00:00:35Z'}], datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc))
        self.assertEqual([got[k] for k in ('active_seconds', 'assistant_seconds', 'elapsed_seconds', 'not_working_seconds')], [50, 65, 60, 10])

    def test_missing_history_is_explicit(self):
        got = research_timing.account('2026-01-01T00:00:00Z', [{'seconds': 20}],
                                      now=datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc))
        self.assertTrue(got['incomplete'])
        self.assertIsNone(got['not_working_seconds'])
        self.assertEqual(got['assistant_seconds'], 20)


class BudgetAndProtocolTests(unittest.TestCase):
    def test_concurrent_reservations_do_not_duplicate_the_remaining_budget(self):
        budget = Reservations(lambda: 12)
        barrier = threading.Barrier(3)
        held = []
        def reserve():
            token, cap = budget.take('investigate', 3)
            held.append((token, cap))
            barrier.wait(3)
        threads = [threading.Thread(target=reserve) for _ in range(3)]
        for t in threads: t.start()
        for t in threads: t.join(4)
        self.assertEqual(len(held), 3)
        self.assertLessEqual(sum(cap for _, cap in held), 6)
        token, cap = budget.take('review')
        self.assertAlmostEqual(sum(budget.held.values()), 12)
        with self.assertRaisesRegex(ValueError, 'reserved or exhausted'):
            budget.take('review')
        budget.release(token)
        for token, _ in held: budget.release(token)
        self.assertEqual(budget.held, {})

    def test_old_runs_and_single_questions_stay_serial(self):
        task = {'planning_questions': ['a', 'b']}
        self.assertFalse(parallel.enabled({}, task))
        self.assertTrue(parallel.enabled({'research_execution': parallel.PROTOCOL}, task))
        self.assertFalse(parallel.enabled({'research_execution': parallel.PROTOCOL}, {'planning_questions': ['a']}))
        self.assertEqual([len(a['questions']) for a in parallel.streams({'planning_questions': list(range(8))})], [3, 3, 2])
        self.assertFalse(parallel.protocol({'research_execution': {**parallel.PROTOCOL, 'workers': 9}}))

    def test_job_identity_and_retry_grouping(self):
        self.assertEqual(rc.job_round('research:investigate-2-area3'), ('investigate', 2))
        self.assertEqual(rc.job_round('research:synthesize-1'), ('synthesize', 1))
        self.assertEqual(rc.job_round('research:review-1'), ('review', 1))
        got = rc.last_rounds({'research:investigate-1-area1': [
            {'research_attempt': 'old', 'started_at': '1', 'seconds': 60},
            {'research_attempt': 'new', 'started_at': '3', 'seconds': 5}],
            'research:investigate-1-area2': [{'research_attempt': 'new', 'started_at': '2', 'seconds': 6}]})
        self.assertEqual((got['jobs'], got['seconds']), (2, 11))


@unittest.skipUnless(RUNTIME, 'Set STUDIO_TEST_RESEARCH_RUNTIME for pinned helper tests.')
class ParallelWorkflowTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name).resolve()
        self.cache = self.root / 'private-cache'
        self.task = {k: v for k, v in dossier('unused').items() if k in rc.TASK_FIELDS}
        self.task['planning_questions'] = [{'id': 'question-' + str(i), 'question': 'Synthetic question ' + str(i)} for i in range(4)]
        self.calls, self.states, self.workers = [], [], []
        self.previous = []
        self.active = self.most = 0
        self.lock = threading.Lock()
        self.barrier = None
        self.fail_area = self.refuse_fact = self.refuse_prose = self.cancel = False
        self.cancelled = threading.Event()
        self.capture = self.root / 'capture.txt'
        self.capture.write_text(TEXT)
        self.workflow = parallel.Workflow(RUNTIME)

    def invoke(self, phase, guidance, payload, offered, fetch):
        execution = payload['_execution']
        stream = execution.get('stream')
        with self.lock:
            self.calls.append((phase, stream))
            self.workers.append(payload['worker'])
        if phase == 'investigate':
            if payload['previous_evidence']['facts']:
                self.previous.append(payload['previous_evidence'])
            with self.lock:
                self.active += 1
                self.most = max(self.most, self.active)
            try:
                if self.barrier: self.barrier.wait(5)
                time.sleep(.025)
                if self.fail_area and stream == 'area2':
                    self.fail_area = False
                    raise ValueError('Synthetic investigator failed')
                value = dossier(payload['worker'])
                value = parallel.preparation({k: value[k] for k in ('schema', 'sources', 'facts')},
                    {'research_mode': 'evidence', 'task': self.task})
                if self.cancel: self.cancelled.set()
                return json.dumps(value), [{'file': 'sources/source.txt', 'path': self.capture,
                    'origin': value['sources'][0]['origin'], 'permission': 'public'}]
            finally:
                with self.lock: self.active -= 1
        if phase == 'synthesize':
            base = payload['evidence']
            ref = base['facts'][0]['id']
            result = dossier(payload['worker'])
            result['findings'] = [{**result['findings'][0], 'id': q['id'],
                'summary': {'text': 'More than one instance keeps capacity.', 'refs': [ref], 'kind': 'summary'},
                'support': [ref], 'conditions': []} for q in self.task['planning_questions']]
            result['sections'][0]['blocks'][0]['refs'] = [ref]
            result['brief'][0]['blocks'][0]['refs'] = [self.task['planning_questions'][0]['id']]
            compact = {k: result[k] for k in ('schema', 'findings', 'sections', 'brief')}
            value = parallel.preparation(compact, {'research_mode': 'compose', 'evidence_base': base})
            return json.dumps(value), []
        value = review(payload['review_template'])
        if self.refuse_fact:
            self.refuse_fact = False
            value['facts'][0].update(verdict='narrow', note='Synthetic located correction')
        if self.refuse_prose:
            self.refuse_prose = False
            value['prose'][0].update(verdict='narrow', note='Synthetic prose correction')
        return json.dumps(value), []

    def run_workflow(self, **options):
        return self.workflow.run(self.root, self.task, self.invoke, cache_root=self.cache,
            progress=self.states.append, cancelled=self.cancelled.is_set, **options)

    def test_real_helper_keeps_actual_authors_and_separate_reviewer(self):
        self.barrier = threading.Barrier(3)
        facts, _ = self.run_workflow()
        self.assertEqual(self.most, 3)
        self.assertEqual(len(facts['facts']), 3)
        self.assertEqual(len(facts['sources']), 1)  # Exact duplicate captures can coalesce.
        authors = {f['author'] for f in facts['facts']}
        self.assertEqual(len(authors), 3)
        self.assertTrue(authors.isdisjoint(self.workers[-2:]))
        self.assertTrue(facts['review']['accepted'])
        self.assertEqual(self.states[-1]['phase'], 'complete')
        self.assertEqual(len({f['id'] for f in facts['facts']}), 3)
        self.assertTrue(all(len(f['id']) <= 64 for f in facts['facts']))

    def test_failed_area_reuses_other_checkpointed_areas_after_restart(self):
        self.fail_area = True
        with self.assertRaisesRegex(ValueError, 'Synthetic investigator failed'): self.run_workflow()
        self.assertEqual(sum(s['status'] == 'kept' for s in self.states[-1]['streams']), 2)
        self.workflow = parallel.Workflow(RUNTIME)
        self.calls.clear()
        self.run_workflow()
        self.assertEqual([s for p, s in self.calls if p == 'investigate'], ['area2'])

    def test_fact_objection_reinvestigates_only_its_owner(self):
        self.refuse_fact = True
        self.run_workflow()
        self.assertCountEqual([s for p, s in self.calls if p == 'investigate'], ['area1', 'area2', 'area3', 'area1'])
        self.assertEqual(sum(p == 'review' for p, _ in self.calls), 2)
        self.assertEqual(len(self.previous), 1)
        self.assertTrue(all(f['id'].startswith('f-area1-') for f in self.previous[0]['facts']))
        self.assertTrue(self.previous[0]['sources'])

    def test_prose_objection_keeps_all_evidence(self):
        self.refuse_prose = True
        self.run_workflow()
        self.assertEqual(sum(p == 'investigate' for p, _ in self.calls), 3)
        self.assertEqual(sum(p == 'synthesize' for p, _ in self.calls), 2)

    def test_cancelled_response_never_becomes_an_adopted_checkpoint(self):
        self.cancel = True
        with self.assertRaises(InterruptedError): self.run_workflow()
        self.assertFalse(list(self.cache.glob('*/area[123].json')))

    def test_changed_capture_invalidates_only_that_packet(self):
        self.fail_area = True
        with self.assertRaises(ValueError): self.run_workflow()
        receipt = next(self.cache.glob('*/area1-*/receipt.json'))
        (receipt.parent / 'sources/source.txt').write_text('Changed source bytes')
        self.calls.clear()
        self.run_workflow()
        self.assertEqual({s for p, s in self.calls if p == 'investigate'}, {'area1', 'area2'})

    def test_explicit_refresh_has_new_generation_but_its_retry_can_reuse(self):
        self.run_workflow()
        self.task['refresh'] = True
        self.task['requested_changes'] = {'at': 'synthetic-refresh'}
        self.calls.clear()
        self.fail_area = True
        with self.assertRaises(ValueError): self.run_workflow()
        self.assertEqual(sum(p == 'investigate' for p, _ in self.calls), 3)
        self.calls.clear()
        self.run_workflow()
        self.assertEqual([s for p, s in self.calls if p == 'investigate'], ['area2'])

    def test_quote_and_permission_checks_still_refuse_invalid_evidence(self):
        spec = {'research_mode': 'evidence', 'task': self.task}
        value = parallel.preparation({k: v for k, v in dossier('actual').items() if k in ('schema', 'sources', 'facts')}, spec)
        captures = [{'file': 'sources/source.txt', 'path': self.capture, 'origin': value['sources'][0]['origin'], 'permission': 'public'}]
        cache = parallel.PacketCache(self.cache, 'synthetic', self.workflow.helper)
        value['facts'][0]['citations'][0]['quote'] = 'This quote is invented.'
        with self.assertRaisesRegex(ValueError, 'quote|Quote'): cache.keep('area1', self.task, 'actual', json.dumps(value), captures)
        value['facts'][0]['author'] = 'forged'
        with self.assertRaisesRegex(ValueError, 'actual investigator'): cache.keep('area1', self.task, 'actual', json.dumps(value), captures)
        value['facts'][0]['author'] = 'actual'
        value['sources'][0]['permission'] = 'selected'
        with self.assertRaisesRegex(ValueError, 'permission'): cache.keep('area1', self.task, 'actual', json.dumps(value), captures)

    def test_pause_can_checkpoint_but_does_not_begin_synthesis(self):
        self.fail_area = True
        with self.assertRaises(ValueError): self.run_workflow()
        # A pause after investigator completion preserves its packet.
        allowed = lambda: not any(s['phase'] == 'investigate' and all(a['status'] == 'kept' for a in s['streams']) for s in self.states)
        with self.assertRaises(InterruptedError): self.run_workflow(allowed=allowed)
        self.assertFalse(any(p == 'synthesize' for p, _ in self.calls))
        self.calls.clear()
        self.run_workflow()
        self.assertFalse(any(p == 'investigate' for p, _ in self.calls))

    def test_synthesis_cannot_add_rewrite_or_reassign_a_fact(self):
        base = dossier('actual-investigator')
        spec = {'evidence_base': base}
        self.assertEqual(parallel.check_frozen(copy.deepcopy(base), spec), [])
        for field, value in (('author', 'synthesizer'), ('statement', 'Unverified claim')):
            changed = copy.deepcopy(base)
            changed['facts'][0][field] = value
            self.assertTrue(parallel.check_frozen(changed, spec))
        with self.assertRaisesRegex(ValueError, 'Evidence is kept unchanged'):
            parallel.preparation({'schema': 2, 'facts': base['facts']},
                {'research_mode': 'compose', 'evidence_base': base})

    def test_selected_original_is_pinned_and_different_capture_is_not_coalesced(self):
        selected_task = {**self.task, 'source_mode': 'selected'}
        original = self.root / 'original.md'
        original.write_text(TEXT)
        cache = parallel.PacketCache(self.cache, 'selected-test', self.workflow.helper)
        packets = []
        for area, suffix in (('area1', ''), ('area2', ' Extra context.')):
            capture = self.root / (area + '.txt')
            capture.write_text(TEXT + suffix)
            value = dossier('worker-' + area, permission='selected', origin='Selected original')
            value = parallel.preparation({k: value[k] for k in ('schema', 'sources', 'facts')},
                {'research_mode': 'evidence', 'task': selected_task})
            packets.append(cache.keep(area, selected_task, 'worker-' + area, json.dumps(value),
                [{'file': 'sources/source.txt', 'path': capture, 'origin': 'Selected original',
                  'permission': 'selected', 'original': 'sources/original.md', 'original_path': original}]))
        base, _, _ = parallel.assemble(self.root / 'assembled', selected_task, packets)
        self.assertEqual(len(base['sources']), 2)
        self.assertTrue(all(s['permission'] == 'selected' for s in base['sources']))
        self.assertTrue(all((self.root / 'assembled' / s['original_file']).read_text() == TEXT for s in base['sources']))
        original_capture = packets[0]['folder'] / 'sources/original.md'
        original_capture.write_text('Changed original')
        self.assertIsNone(cache.get('area1'))

    def test_changed_approved_scope_never_reuses_an_earlier_generation(self):
        self.run_workflow()
        self.calls.clear()
        self.task['scope'] += ' with another approved question'
        self.run_workflow()
        self.assertEqual(sum(p == 'investigate' for p, _ in self.calls), 3)

    def test_independent_review_rejects_every_investigator_identity(self):
        self.run_workflow()
        case = self.root / rc.CASE
        value = json.loads((case / 'dossier.json').read_text())
        for author in {f['author'] for f in value['facts']}:
            with self.assertRaisesRegex(ValueError, 'independent worker'):
                self.workflow.helper.command(case, 'review', 'review.json', author)

    def test_all_missing_evidence_stops_before_repeated_synthesis(self):
        invoke = self.invoke
        def empty(phase, guidance, payload, offered, fetch):
            if phase != 'investigate': return invoke(phase, guidance, payload, offered, fetch)
            return json.dumps(parallel.preparation({'schema': 2, 'sources': [], 'facts': [], 'gaps': ['No evidence available.']},
                {'research_mode': 'evidence', 'task': self.task})), []
        self.invoke = empty
        with self.assertRaisesRegex(ValueError, 'no cited facts'): self.run_workflow()
        self.assertFalse(self.calls)
