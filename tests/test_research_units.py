"""The independent check in review units (issue #378), through the real Harness Research
runtime with a scripted worker: bounded concurrency, retries of one unit, correction rounds,
stops, refusals, unread originals, independence, and the same result as one reviewer."""
import copy
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import time
import unittest
from unittest import mock

import marketing_studio  # noqa: F401
from studio_core import research_contract as rc, research_session as session, research_sections as sections
from studio_core import research_units as units, research_quality, research_text, research_jobs
import test_research_sections as section_cases
from synthesis_fixture import review

RUNTIME = os.environ.get('STUDIO_TEST_RESEARCH_RUNTIME')


def area_of(question):
    """The collection workstream a section research gives one approved question."""
    return 'area-' + session.digest(question)[:40]


@unittest.skipUnless(RUNTIME and units.capability(RUNTIME), 'Harness Research 1.6.0 or newer required.')
class UnitCheckTests(unittest.TestCase):
    def setUp(self):
        section_cases.SectionWorkflowTests.setUp(self)
        self.units = units.entry(RUNTIME)
        self.reviews = []          # every review unit job, in the order each started
        self.review_active = self.review_peak = 0
        self.pause = 0.15
        self.change = None         # change(unit, answer, payload) before an answer is handed back
        self.before = None         # before(unit, payload) as a reviewer starts
        self.cancel = threading.Event()

    def invoke(self, phase, guidance, payload, offered, fetch):
        if phase != 'review':
            return section_cases.SectionWorkflowTests.invoke(self, phase, guidance, payload, offered, fetch)
        execution = payload['_execution']
        self.assertEqual(execution['mode'], 'review-unit')
        unit = execution['unit']
        with self.lock:
            self.reviews.append({'unit': unit, 'worker': payload['worker'], 'round': execution['round'],
                                 'areas': payload['assignment']['unit']['areas'],
                                 'files': sorted(source['file'] for source in offered)})
            self.review_active += 1
            self.review_peak = max(self.review_peak, self.review_active)
        try:
            if self.before:
                self.before(unit, payload)
            time.sleep(self.pause)
            answer = review(payload['review_template'])
            for group in ('facts', 'findings', 'prose'):
                for item in answer[group]:
                    item['note'] = f'Synthetic reviewer checked {item["id"]} against its exact capture.'
            if self.change:
                self.change(unit, answer, payload)
            return json.dumps(answer), []
        finally:
            with self.lock:
                self.review_active -= 1

    def run_units(self, limit=3, **extra):
        return self.workflow.run(self.root, self.task, self.invoke, progress=self.states.append,
                                 section_policy=sections.pin(), section_context={'combining': 'synthetic-medium'},
                                 review_units=self.units, limit=limit, cancelled=self.cancel.is_set, **extra)

    def case(self):
        return session.case_for(self.root)

    def units_status(self):
        return self.workflow.command(self.case(), 'review-units', 'status')

    def test_at_most_three_units_at_once_each_given_only_its_own_captures(self):
        facts, manifest = self.run_units()
        self.assertEqual(manifest['status'], 'complete')
        self.assertTrue(facts['review']['accepted'])
        self.assertEqual(len(facts['review']['reviewers']), 5)
        content = [row for row in self.reviews if row['unit'] != units.FINAL]
        self.assertEqual(len(content), 4)
        self.assertEqual(self.review_peak, 3, 'three content units run at once, never more')
        self.assertEqual(self.reviews[-1]['unit'], units.FINAL, 'the final unit runs after every content unit')
        every = {file for row in content for file in row['files']}
        for row in content:
            # Each content unit is handed its own area's capture only.
            self.assertEqual(len(row['files']), 1, row)
            self.assertIn('/' + row['areas'][0] + '/', row['files'][0])
        self.assertEqual(set(self.reviews[-1]['files']), every, 'the final unit reads the whole dossier')
        # The assembled review is where every reader of a review looks.
        saved = json.loads((self.case() / 'review.json').read_text())
        self.assertEqual(saved['units']['protocol'], units.PROTOCOL)
        self.assertTrue(saved['accepted'])
        self.assertEqual(rc.objections(self.case()), [])
        # Progress: each active reviewer shown under its unit, the final apart from the final brief.
        shown = [agent for state in self.states for agent in state['agents']['active'] if agent['phase'] == 'review']
        self.assertTrue(shown)
        self.assertTrue(all(agent['section'] == units.section(agent['unit']) for agent in shown))
        self.assertIn(units.FINAL_SECTION, {agent['section'] for agent in shown})
        self.assertNotIn('final', {agent['section'] for agent in shown})
        reviewing = [state for state in self.states if state['phase'] == 'review']
        self.assertLessEqual(max(state['agents']['count'] for state in reviewing), 3)
        self.assertEqual(self.states[-1]['phase'], 'complete')
        calls = len(self.reviews)
        self.run_units()
        self.assertEqual(len(self.reviews), calls, 'an unchanged assembled review is not reviewed again')

    def test_a_case_handed_over_carries_its_plan_and_receipts_and_still_verifies(self):
        self.pause = 0
        self.run_units()
        _, files = rc.case_files(self.case())
        held = [name for name in files if name.startswith('.harness-research/review-units-data/')]
        self.assertEqual(len([name for name in held if '/receipt-' in name]), 5)
        self.assertEqual(len([name for name in held if '/plan-' in name]), 1)
        elsewhere = Path(tempfile.mkdtemp()).resolve(); self.addCleanup(shutil.rmtree, elsewhere, True)
        rc.adopt_case(self.case(), elsewhere)
        verified = rc.Workflow(RUNTIME).command(session.case_for(elsewhere), 'verify')
        self.assertEqual((verified['status'], verified['artifact_integrity']), ('complete', 'verified'))

    def test_never_more_units_at_once_than_the_limit(self):
        facts, _ = self.run_units(limit=2)
        self.assertTrue(facts['review']['accepted'])
        self.assertEqual(self.review_peak, 2)
        self.assertEqual(self.units_status()['max_reviewers'], 2)

    def test_a_retry_calls_only_the_unit_that_failed_and_no_label_is_reused(self):
        failing = area_of('question-2')
        def before(unit, payload):
            if payload['assignment']['unit']['areas'] == [failing] and not getattr(self, 'failed_once', False):
                self.failed_once = True
                raise ValueError('Synthetic reviewer failure')
        self.before = before
        with self.assertRaisesRegex(ValueError, 'Synthetic reviewer failure'):
            self.run_units()
        self.assertEqual(self.states[-1]['phase'], 'review', 'a failed unit leaves the run at its check, as a failed review does')
        first = list(self.reviews)
        self.assertEqual(len(first), 4, 'every content unit runs; the final waits')
        statuses = {row['id']: row['status'] for row in self.units_status()['units']}
        self.assertEqual(sorted(statuses.values()), ['accepted', 'accepted', 'accepted', 'failed', 'pending'])
        before_calls = list(self.calls), list(self.section_calls)
        facts, _ = self.run_units()
        self.assertTrue(facts['review']['accepted'])
        again = self.reviews[len(first):]
        self.assertEqual([row['areas'] for row in again], [[failing], []])
        self.assertEqual(again[-1]['unit'], units.FINAL)
        self.assertEqual((self.calls, self.section_calls), before_calls, 'nothing else runs again')
        labels = [row['worker'] for row in self.reviews]
        self.assertEqual(len(labels), len(set(labels)), 'no reviewer label is used twice in a case')
        investigators = {fact['author'] for fact in facts['facts']}
        self.assertFalse(investigators & set(labels))

    def test_a_correction_round_reviews_only_changed_units_and_the_final(self):
        corrected = area_of('question-1')
        def change(unit, answer, payload):
            if payload['_execution']['round'] == 1 and payload['assignment']['unit']['areas'] == [corrected]:
                answer['facts'][0].update(verdict='narrow', note='Synthetic located fact correction.')
        self.change = change
        facts, _ = self.run_units()
        self.assertTrue(facts['review']['accepted'])
        second = [row for row in self.reviews if row['round'] == 2]
        self.assertEqual([row['areas'] for row in second], [[corrected], []])
        receipts = facts['review']['units']['receipts']
        self.assertEqual(sum(receipt['kept'] for receipt in receipts), 3, 'three content units keep their receipts')
        self.assertEqual([phase for phase, _ in self.calls].count('investigate'), 5)

    def test_a_stopped_check_keeps_accepted_units_and_goes_on(self):
        def before(unit, payload):
            if len(self.reviews) == 3:
                self.cancel.set()
        self.before = before
        with self.assertRaises(InterruptedError):
            self.run_units(limit=1)
        self.assertEqual(self.states[-1]['phase'], 'stopped')
        status = self.units_status()
        self.assertEqual(status['phase'], 'stopped')
        self.assertEqual(sorted(row['status'] for row in status['units']),
                         ['accepted', 'accepted', 'cancelled', 'pending', 'pending'])
        collection = self.workflow.command(self.case(), 'collection', 'status')
        self.assertNotEqual(collection['status'], 'stopped', 'a stopped check keeps its evidence')
        accepted = {row['id'] for row in status['units'] if row['status'] == 'accepted'}
        self.cancel.clear(); self.before = None
        done = len(self.reviews), list(self.calls), list(self.section_calls)
        facts, _ = self.run_units()
        self.assertTrue(facts['review']['accepted'])
        again = [row['unit'] for row in self.reviews[done[0]:]]
        self.assertEqual(len(again), 3)
        self.assertFalse(accepted & set(again), 'accepted units are not reviewed again')
        self.assertEqual((self.calls, self.section_calls), done[1:])

    def test_an_answer_that_breaks_its_template_is_refused_and_only_it_is_retried(self):
        broken = area_of('question-3')
        def change(unit, answer, payload):
            if payload['assignment']['unit']['areas'] == [broken] and not getattr(self, 'broke', False):
                self.broke = True
                answer['facts'] = []
                answer['assessment'] = {'coverage': 'accurate', 'usefulness': 'adequate', 'note': 'Not mine.'}
        self.change = change
        with self.assertRaisesRegex(ValueError, 'facts must hold exactly one entry.*Leave out assessment|Leave out assessment.*facts must'):
            self.run_units()
        statuses = sorted(row['status'] for row in self.units_status()['units'])
        self.assertEqual(statuses, ['accepted', 'accepted', 'accepted', 'pending', 'refused'])
        first = len(self.reviews)
        facts, _ = self.run_units()
        self.assertTrue(facts['review']['accepted'])
        self.assertEqual([row['areas'] for row in self.reviews[first:]], [[broken], []])

    def test_a_unit_answer_is_corrected_inside_its_job_by_the_text_transport(self):
        """Blog Studio and Infographic Studio hand a unit to a worker through
        research_text.Transport, which checks the answer against the unit's template and asks
        for one correction within the job."""
        sent = []
        def call(phase, data, instruction):
            sent.append(copy.deepcopy(data))
            self.assertIn('review unit guide', instruction)
            self.assertNotIn('schema-2', instruction)
            answer = review(data['review_template'])
            if 'validation_error' not in data and data['review_template'].get('unit') != units.FINAL:
                answer['reviewer'] = 'someone-else'
            return {'content': json.dumps(answer)}
        transport = research_text.Transport(RUNTIME, call)
        def invoke(phase, guidance, payload, offered, fetch):
            if phase == 'review':
                return transport(phase, guidance, payload, offered, fetch)
            return section_cases.SectionWorkflowTests.invoke(self, phase, guidance, payload, offered, fetch)
        facts, _ = self.workflow.run(self.root, self.task, invoke, section_policy=sections.pin(),
                                     review_units=self.units)
        self.assertTrue(facts['review']['accepted'])
        corrected = [data for data in sent if 'validation_error' in data]
        self.assertEqual(len(corrected), 4, 'each content unit is corrected once in its job')
        self.assertIn('Set reviewer to', corrected[0]['validation_error'])
        self.assertEqual(len(sent), 9)

    def test_an_unread_original_in_one_unit_retries_only_that_unit_and_the_final(self):
        self.task['source_mode'] = 'selected'
        unread = area_of('question-0')
        def change(unit, answer, payload):
            if payload['assignment']['unit']['areas'] == [unread] and not getattr(self, 'unread_once', False):
                self.unread_once = True
                for original in answer['originals']:
                    original.update(read_original=False, access_error='Synthetic tool could not open the original.')
            if unit == units.FINAL and not getattr(self, 'assessed_once', False):
                self.assessed_once = True
                answer['assessment'].update(coverage='needs-revision', note='One original was not read.')
        self.change = change
        supplied = [{'file': 'sources/notes.txt', 'path': self.capture, 'text': section_cases.cases.TEXT,
                     'title': 'Synthetic notes', 'origin': 'Supplied notes', 'permission': 'selected'}]
        run = lambda: self.workflow.run(self.root, self.task, self.invoke, supplied, section_policy=sections.pin(),
                                        review_units=self.units, progress=self.states.append)
        with self.assertRaises(research_quality.IncompleteCheck):
            run()
        self.assertEqual(self.states[-1]['phase'], 'check-incomplete')
        first = len(self.reviews)
        before = list(self.calls), list(self.section_calls)
        facts, _ = run()
        self.assertTrue(facts['review']['accepted'])
        self.assertEqual([row['areas'] for row in self.reviews[first:]], [[unread], []])
        self.assertEqual((self.calls, self.section_calls), before, 'the dossier is kept; only the check runs')
        self.assertTrue(all(original['read_original'] for original in facts['review']['originals']))

    def test_the_assembled_review_equals_one_reviewer_giving_the_same_verdicts(self):
        def change(unit, answer, payload):
            for item in answer['prose']:
                item.update(verdict='narrow', note=f'Synthetic: {item["id"]} reads a little broadly.')
        self.change = change
        with self.assertRaises(rc.ReviewRefused):
            self.run_units()
        case = self.case()
        assembled = json.loads((case / '.harness-research/synthesis.json').read_text())['review']
        self.assertEqual(assembled, json.loads((case / 'review.json').read_text()))
        copy_root = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, copy_root, True)
        single_case = copy_root / 'topic'
        shutil.copytree(case, single_case, symlinks=True)
        helper = rc.Workflow(RUNTIME)
        template = json.loads(rc.run_helper([shutil.which('node') or 'node', str(Path(RUNTIME) / 'scripts/harness-research.mjs'), 'synthesis',
                                             'template', '--project', str(single_case)]).stdout)
        one = copy.deepcopy(template)
        by = {group: {item.get('id', item.get('source')): item for item in assembled[group]}
              for group in ('originals', 'facts', 'findings', 'prose')}
        for item in one['originals']:
            item.update({key: value for key, value in by['originals'][item['source']].items()})
        for group in ('facts', 'findings', 'prose'):
            for item in one[group]:
                item.update(by[group][item['id']])
        one['assessment'] = assembled['assessment']
        rc.write(single_case, 'single.json', json.dumps(one))
        helper.command(single_case, 'review', 'single.json', 'reviewer-single-synthetic')
        single = json.loads((single_case / '.harness-research/synthesis.json').read_text())['review']
        self.assertFalse(single['accepted'])
        for key in ('schema', 'digest', 'originals', 'facts', 'findings', 'prose', 'assessment', 'accepted'):
            self.assertEqual(assembled[key], single[key], key)
        self.assertNotIn('worker', assembled)
        self.assertEqual(len(assembled['reviewers']), len(assembled['units']['receipts']))


@unittest.skipUnless(RUNTIME and units.capability(RUNTIME), 'Harness Research 1.6.0 or newer required.')
class UnitChoiceTests(unittest.TestCase):
    """Which cases are checked in units: decided once, when the case starts."""

    def setUp(self):
        section_cases.cases.SessionTests.setUp(self)
        self.barrier = None

    def invoke(self, phase, guidance, payload, offered, fetch):
        return section_cases.cases.SessionTests.invoke(self, phase, guidance, payload, offered, fetch)

    def test_a_new_case_on_a_runtime_with_units_keeps_the_entry(self):
        execution = session.execution(RUNTIME)
        self.assertEqual(execution['review'], units.entry(RUNTIME))
        self.assertTrue(units.valid(execution['review']))
        self.assertTrue(session.protocol({'research_execution': execution}), 'the collection protocol is unchanged')

    def test_a_case_started_without_units_stays_on_the_single_review_after_an_update(self):
        with mock.patch.object(units, 'capability', return_value=None):
            execution = session.execution(RUNTIME)   # as Harness Research 1.5.1 left it
        self.assertNotIn('review', execution)
        seen = []
        def invoke(phase, guidance, payload, offered, fetch):
            seen.append((phase, sorted(payload)))
            return self.invoke(phase, guidance, payload, offered, fetch)
        facts, _ = self.workflow.run(self.root, self.task, invoke, review_units=units.of(execution))
        self.assertTrue(facts['review']['accepted'])
        reviews = [keys for phase, keys in seen if phase == 'review']
        self.assertEqual(len(reviews), 1)
        self.assertIn('dossier', reviews[0]); self.assertNotIn('assignment', reviews[0])
        self.assertIn('worker', facts['review'])
        self.assertFalse((session.case_for(self.root) / '.harness-research/review-units.json').exists())

    def test_a_case_started_with_units_is_refused_on_a_runtime_without_them(self):
        started = session.execution(RUNTIME)
        with mock.patch.object(units, 'capability', return_value=None):
            with self.assertRaisesRegex(ValueError, 'no longer offers them. Update Harness Research'):
                self.workflow.run(self.root, self.task, self.invoke, review_units=units.of(started))
        self.assertEqual(self.calls, [])
        self.assertFalse((self.root / '.studio-research').exists(), 'refused before anything is registered')

    def test_an_unreadable_entry_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'cannot be read'):
            self.workflow.run(self.root, self.task, self.invoke, review_units={'schema': 9})
        self.assertEqual(self.calls, [])


class UnitContractTests(unittest.TestCase):
    """The parts that need no runtime."""

    def test_review_unit_jobs_count_as_their_round_of_review(self):
        self.assertEqual(research_jobs.job_round('research:review-2-unit-0123456789abcdef'), ('review', 2))
        self.assertEqual(research_jobs.job_round('research:review-1-final'), ('review', 1))
        self.assertEqual(research_jobs.job_round('research:review-3'), ('review', 3))
        self.assertIsNone(research_jobs.job_round('research:review-1-unit-xyz'))
        tried = research_jobs.last_rounds({
            'research:investigate-1-area1': [{'started_at': '1', 'seconds': 4, 'dollars': 0.5}],
            'research:review-1-unit-0123456789abcdef': [{'started_at': '2', 'seconds': 3, 'dollars': 0.25}],
            'research:review-1-final': [{'started_at': '3', 'seconds': 2, 'dollars': 0.25}]})
        self.assertEqual(tried, {'rounds': 1, 'jobs': 3, 'seconds': 9, 'dollars': 1.0})

    def test_the_capability_is_read_strictly(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime = Path(temp)
            self.assertIsNone(units.capability(runtime))
            (runtime / 'references').mkdir()
            good = {'schema': 1, 'protocol': units.PROTOCOL, 'command': 'review-units', 'actions': list(units.ACTIONS),
                    'state_schema': 4, 'output_schema': 2, 'limits': {'max_units': 64, 'max_reviewers': 3}}
            for wrong in ({'protocol': 'harness-review-units-v2'}, {'state_schema': 5}, {'limits': {'max_units': 64, 'max_reviewers': 4}},
                          {'actions': ['plan']}):
                (runtime / units.CAPABILITY).write_text(json.dumps({**good, **wrong}))
                self.assertIsNone(units.capability(runtime), wrong)
            (runtime / units.CAPABILITY).write_text(json.dumps(good))
            self.assertEqual(units.capability(runtime), {'protocol': units.PROTOCOL, 'max_reviewers': 3, 'max_units': 64})
            self.assertEqual(units.entry(runtime)['max_units'], units.MAX_UNITS)
            self.assertFalse(units.valid({**units.entry(runtime), 'protocol': 'other'}))

    def test_a_unit_answer_is_checked_against_its_own_template(self):
        template = {'schema': 1, 'protocol': units.PROTOCOL, 'plan': 'p' * 64, 'digest': 'd' * 64, 'unit': 'unit-0123456789abcdef',
                    'attempt': 1, 'reviewer': 'reviewer-a',
                    'originals': [{'source': 's-1', 'sha256': 'a' * 64, 'read_original': False}],
                    'facts': [{'id': 'f-1', 'verdict': 'pending', 'note': ''}], 'findings': [], 'prose': []}
        good = review(template)
        self.assertNotIn('assessment', good)
        self.assertEqual(rc.unit_problems(good, template), [])
        wrong = {**copy.deepcopy(good), 'attempt': 2, 'assessment': {'coverage': 'accurate'}, 'worker': 'x'}
        wrong['facts'] = []
        said = ' '.join(rc.unit_problems(wrong, template))
        for part in ('Set attempt to 1', 'Leave out worker', 'Leave out assessment', 'facts must hold exactly one'):
            self.assertIn(part, said)
        final = {**template, 'unit': 'final', 'assessment': {'coverage': 'pending', 'usefulness': 'pending', 'note': ''}}
        self.assertEqual(rc.unit_problems(review(final), final), [])
        self.assertIn('assessment.coverage', ' '.join(rc.unit_problems({**review(final), 'assessment': {}}, final)))
        self.assertTrue(rc.unit_review(template)); self.assertFalse(rc.unit_review({'schema': 2}))

    def test_a_review_units_result_that_exits_1_is_still_read(self):
        self.assertTrue(rc.answered(['review-units', 'assemble'], 1, '{"status": "needs-revision"}'))
        self.assertTrue(rc.answered(['review-units', 'finish'], 1, '{"status": "stale"}'))
        self.assertFalse(rc.answered(['review-units', 'register'], 1, ''))
        self.assertFalse(rc.answered(['collection', 'status'], 1, '{}'))


if __name__ == '__main__':
    unittest.main()
