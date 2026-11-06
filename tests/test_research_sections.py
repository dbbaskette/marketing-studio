"""Durable section contributions through the real supported collection helper."""
import copy
import json
import os
import threading
import time
import unittest

import marketing_studio  # noqa: F401
from studio_core import research_sections as sections, research_session as session, research_quality
import test_research_session as cases
from synthesis_fixture import dossier, review


@unittest.skipUnless(os.environ.get('STUDIO_TEST_RESEARCH_RUNTIME'), 'Pinned helper required.')
class SectionWorkflowTests(unittest.TestCase):
    def setUp(self):
        cases.SessionTests.setUp(self)
        self.barrier = None
        self.section_calls = []
        self.fail_section = None
        self.active = self.peak = 0
        self.lock = threading.Lock()
        self.combining_times = []
        self.final_seconds = []
        self.fail_final = False

    def invoke(self, phase, guidance, payload, offered, fetch):
        execution = payload['_execution']
        if phase == 'investigate':
            return cases.SessionTests.invoke(self, phase, guidance, payload, offered, fetch)
        if phase == 'review':
            self.calls.append((phase, None))
            return json.dumps(review(payload['review_template'])), []
        if execution['mode'] == 'compose-section':
            ident = payload['section']['questions'][0]['id']
            with self.lock:
                self.active += 1; self.peak = max(self.peak, self.active)
                self.section_calls.append(ident); self.combining_times.append(('start', time.monotonic()))
            try:
                time.sleep(0.15)
                if self.fail_section == ident:
                    self.fail_section = None
                    raise ValueError('Synthetic section timeout')
                fact = payload['evidence']['facts'][0]['id']
                template = dossier(payload['worker'])['findings'][0]
                value = {'schema': 2, 'findings': [{**copy.deepcopy(template), 'id': ident,
                    'summary': {'text': 'More than one instance keeps capacity.', 'kind': 'summary', 'refs': [fact]},
                    'support': [fact], 'counter': [], 'conditions': [], 'implications': [], 'gaps': []}],
                    'sections': [{'id': ident, 'title': 'Section ' + ident,
                        'blocks': [{'text': 'More than one instance keeps capacity.', 'kind': 'summary', 'refs': [ident]}]}]}
                return json.dumps(session.preparation(value, {**execution, 'research_mode': execution['mode']})), []
            finally:
                with self.lock:
                    self.active -= 1; self.combining_times.append(('end', time.monotonic()))
        self.assertEqual(execution['mode'], 'compose-final')
        self.assertNotIn('evidence', payload, 'the final author reads contributions, not every fact')
        self.calls.append(('final', None))
        self.final_seconds.append(execution['seconds'])
        self.assertEqual(guidance, sections.FINAL_GUIDANCE)
        if self.fail_final:
            self.fail_final = False
            raise ValueError('Synthetic final brief timeout')
        first = payload['completed_sections']['findings'][0]['id']
        value = {'schema': 2, 'sections': [], 'brief': [{'id': 'takeaway', 'title': 'Takeaway',
            'blocks': [{'text': 'More than one instance keeps capacity.', 'kind': 'summary', 'refs': [first]}]}]}
        return json.dumps(session.preparation(value, {**execution, 'research_mode': execution['mode']})), []

    def run_sections(self, policy=None):
        return self.workflow.run(self.root, self.task, self.invoke, progress=self.states.append,
            section_policy=policy or sections.pin(), section_context={'combining': 'synthetic-medium'})

    def test_four_sections_combine_with_at_most_three_authors_then_verify_complete(self):
        facts, manifest = self.run_sections()
        self.assertTrue(facts['review']['accepted'])
        self.assertEqual(len(self.section_calls), 4)
        self.assertEqual(self.peak, 3)
        starts = [at for kind, at in self.combining_times if kind == 'start']
        ends = [at for kind, at in self.combining_times if kind == 'end']
        self.assertLess(sorted(starts)[1], min(ends), 'a second author starts before the first completes')
        self.assertEqual(len(facts['sections']), 4)
        self.assertTrue(any(len(state.get('combining', [])) == 4 for state in self.states))
        self.assertEqual([phase for phase, _ in self.calls].count('final'), 1)
        first = next(state for state in self.states if state.get('first_readable_seconds') is not None)
        self.assertNotEqual(first['phase'], 'complete')
        preview = next(row['preview'] for row in first['combining'] if row.get('preview'))
        self.assertIn('More than one instance', preview['sections'][0]['text'])
        self.assertTrue(preview['basis']);self.assertTrue(preview['sources'])
        self.assertLessEqual(first['first_readable_seconds'], self.states[-1]['checked_result_seconds'])
        calls = len(self.calls), len(self.section_calls)
        self.run_sections()
        self.assertEqual((len(self.calls), len(self.section_calls)), calls, 'complete unchanged research starts no new author/reviewer')

    def test_creator_review_stops_after_one_check_and_explicit_retry_keeps_final_feedback(self):
        from studio_core import research_decisions
        invoke = self.invoke
        def flagged(phase, guidance, payload, offered, fetch):
            text, sources = invoke(phase, guidance, payload, offered, fetch)
            if phase == 'review':
                value = json.loads(text)
                value['prose'][0].update(verdict='narrow', note='Narrow the section claim.')
                value['prose'][-1].update(verdict='narrow', note='Keep the final qualification.')
                text = json.dumps(value)
            return text, sources
        with self.assertRaises(research_decisions.CreatorReview):
            self.workflow.run(self.root, self.task, flagged, section_policy=sections.pin(), creator_review=True)
        self.assertEqual([p for p, _ in self.calls].count('review'), 1)
        before = list(self.section_calls)
        feedback = []
        def corrected(phase, guidance, payload, offered, fetch):
            if payload['_execution'].get('mode') == 'compose-final':
                feedback.append(payload.get('previous_review'))
                self.assertIn('sections', payload['previous_final'])
            return invoke(phase, guidance, payload, offered, fetch)
        result, _ = self.workflow.run(self.root, self.task, corrected,
            section_policy=sections.pin(), creator_review=True)
        self.assertTrue(result['review']['accepted'])
        self.assertEqual(self.section_calls[len(before):], ['question-0'])
        self.assertIn('Keep the final qualification.', json.dumps(feedback))
        self.assertEqual([p for p, _ in self.calls].count('investigate'), 4)

    def test_timeout_keeps_three_contributions_and_retry_only_calls_the_unfinished_section(self):
        self.fail_section = 'question-2'
        with self.assertRaisesRegex(ValueError, 'Synthetic section timeout'): self.run_sections()
        case = session.case_for(self.root)
        saved = json.loads((case / '.harness-research/studio-combining.json').read_bytes())
        self.assertEqual(len(saved['sections']), 3)
        self.assertEqual(sum(bool(row.get('preview')) for row in self.states[-1]['combining']), 3)
        self.assertNotIn('checked_result_seconds', self.states[-1])
        self.assertEqual([phase for phase, _ in self.calls].count('final'), 0)
        prior = list(self.section_calls)
        facts, _ = self.run_sections()
        self.assertTrue(facts['review']['accepted'])
        self.assertEqual(self.section_calls[len(prior):], ['question-2'])
        self.assertEqual([phase for phase, _ in self.calls].count('investigate'), 4)

    def test_final_timeout_keeps_every_section_and_retry_honors_only_its_time_grant(self):
        self.fail_final = True
        policy = sections.pin()
        with self.assertRaisesRegex(ValueError, 'Synthetic final brief timeout'):
            self.run_sections(policy)
        self.assertEqual(self.final_seconds, [policy['seconds']])
        sections_before = list(self.section_calls)
        investigations = [call for call in self.calls if call[0] == 'investigate']
        policy['more_time']['final'] = 600
        facts, _ = self.run_sections(policy)
        self.assertTrue(facts['review']['accepted'])
        self.assertEqual(self.final_seconds, [300, 600])
        self.assertEqual(self.section_calls, sections_before)
        self.assertEqual([call for call in self.calls if call[0] == 'investigate'], investigations)

    def test_final_uses_the_saved_combining_allowance(self):
        policy = sections.pin()
        policy['seconds'] = 180
        self.run_sections(policy)
        self.assertEqual(self.final_seconds, [180])

    def test_incomplete_check_keeps_all_authors_and_retries_only_review(self):
        invoke = self.invoke
        def incomplete(phase, guidance, payload, offered, fetch):
            text, sources = invoke(phase, guidance, payload, offered, fetch)
            if phase == 'review':
                value = json.loads(text)
                for original in value['originals']:
                    original.update(read_original=False, access_error='Synthetic reviewer allowance exhausted before reading.')
                for fact in value['facts']:
                    fact.update(verdict='unsupported', note='Unverified: this source has not been read.')
                value['assessment'].update(coverage='needs-revision', usefulness='needs-revision', note='Checking did not finish.')
                text = json.dumps(value)
            return text, sources
        self.invoke = incomplete
        with self.assertRaises(research_quality.IncompleteCheck):
            self.run_sections()
        self.assertEqual(self.states[-1]['phase'], 'check-incomplete')
        self.assertGreater(self.states[-1]['review_coverage']['unread'], 0)
        self.assertNotIn('correction', self.states[-1])
        before = list(self.calls), list(self.section_calls)
        self.invoke = invoke
        result, _ = self.run_sections()
        self.assertTrue(result['review']['accepted'])
        self.assertEqual(self.section_calls, before[1])
        self.assertEqual(self.calls[len(before[0]):], [('review', None)])

    def test_focused_introductory_database_scope_reaches_checked_output(self):
        self.task['topic'] = 'Minimal basics of PostgreSQL HA/DR, Helm and operators, and self-support responsibilities'
        self.task['research_policy'] = dict(research_quality.FOCUSED)
        result, _ = self.run_sections()
        self.assertTrue(result['review']['accepted'])
        self.assertEqual(len(self.section_calls), 4)
        self.assertEqual([p for p, _ in self.calls].count('final'), 1)
        first = next(s for s in self.states if s.get('first_readable_seconds') is not None)
        self.assertNotEqual(first['phase'], 'complete')
        self.assertLessEqual(len(result['facts']), 32)

    def test_saved_placeholder_is_replaced_without_rewriting_good_sections(self):
        invoke = self.invoke
        def fail_review(phase, *args):
            if phase == 'review':
                raise ValueError('Synthetic check interruption')
            return invoke(phase, *args)
        self.invoke = fail_review
        with self.assertRaisesRegex(ValueError, 'Synthetic check interruption'):
            self.run_sections()
        case = session.case_for(self.root)
        path = case / '.harness-research/studio-combining.json'
        saved = json.loads(path.read_text())
        saved['final']['content']['brief'][0]['blocks'][0]['text'] = 'test'
        saved['final']['digest'] = sections.fingerprint(saved['final']['content'])
        path.write_text(json.dumps(saved))
        before = list(self.section_calls)
        self.invoke = invoke
        result, _ = self.run_sections()
        self.assertTrue(result['review']['accepted'])
        self.assertEqual(self.section_calls, before)
        self.assertEqual([p for p, _ in self.calls].count('final'), 2)


class SectionContractTests(unittest.TestCase):
    def test_deduplication_retains_distinct_claims_quotes_and_sources(self):
        one = {'id': 'a', 'statement': 'Capacity stays available.', 'author': 'reader',
            'citations': [{'source': 's1', 'quote': 'Capacity stays available.'}]}
        same = {**copy.deepcopy(one), 'id': 'b', 'statement': 'Capacity  stays available.'}
        different = {**copy.deepcopy(one), 'id': 'c', 'statement': 'Capacity may become unavailable.'}
        other = copy.deepcopy(one); other['id'] = 'd'; other['citations'][0]['source'] = 's2'
        self.assertEqual([row['id'] for row in sections.deduplicate([one, same, different, other])], ['a', 'c', 'd'])

    def test_more_time_changes_only_the_failed_section(self):
        record = {'section_synthesis': sections.pin()}
        self.assertTrue(sections.grant(record, {'section': 'area-a', 'seconds': 300}))
        self.assertEqual(record['section_synthesis']['more_time'], {'area-a': 600})
        self.assertEqual(record['section_synthesis']['seconds'], 300)
        self.assertFalse(sections.grant(record, {'seconds': 900}))

