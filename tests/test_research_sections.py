"""Durable section contributions through the real supported collection helper."""
import copy
import json
import os
import threading
import time
import unittest

import marketing_studio  # noqa: F401
from studio_core import research_sections as sections, research_session as session
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
        first = payload['completed_sections']['findings'][0]['id']
        value = {'schema': 2, 'sections': [], 'brief': [{'id': 'takeaway', 'title': 'Takeaway',
            'blocks': [{'text': 'More than one instance keeps capacity.', 'kind': 'summary', 'refs': [first]}]}]}
        return json.dumps(session.preparation(value, {**execution, 'research_mode': execution['mode']})), []

    def run_sections(self):
        return self.workflow.run(self.root, self.task, self.invoke, progress=self.states.append,
            section_policy=sections.pin(), section_context={'combining': 'synthetic-medium'})

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
        calls = len(self.calls), len(self.section_calls)
        self.run_sections()
        self.assertEqual((len(self.calls), len(self.section_calls)), calls, 'complete unchanged research starts no new author/reviewer')

    def test_timeout_keeps_three_contributions_and_retry_only_calls_the_unfinished_section(self):
        self.fail_section = 'question-2'
        with self.assertRaisesRegex(ValueError, 'Synthetic section timeout'): self.run_sections()
        case = session.case_for(self.root)
        saved = json.loads((case / '.harness-research/studio-combining.json').read_bytes())
        self.assertEqual(len(saved['sections']), 3)
        self.assertEqual([phase for phase, _ in self.calls].count('final'), 0)
        prior = list(self.section_calls)
        facts, _ = self.run_sections()
        self.assertTrue(facts['review']['accepted'])
        self.assertEqual(self.section_calls[len(prior):], ['question-2'])
        self.assertEqual([phase for phase, _ in self.calls].count('investigate'), 4)


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

