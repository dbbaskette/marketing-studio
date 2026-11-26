"""Research progress shows the units doing the work (issue #379), through the real Harness
Research runtime with a scripted worker: each area, section, the final brief, each review
unit and the final whole-research check, with how many work now, wait, are kept and failed,
how long each took, and a failure or stop that names the unit it happened in."""
import json
import os
import threading
import unittest
from types import SimpleNamespace

import marketing_studio  # noqa: F401
from studio_core import research_run, research_sections as sections, research_transport as transport
from studio_core import research_units as units
import test_research_sections as section_cases
import test_research_units as unit_cases

RUNTIME = os.environ.get('STUDIO_TEST_RESEARCH_RUNTIME')


class Borrowed:
    """The scripted worker and runs of the review-units tests."""
    invoke = unit_cases.UnitCheckTests.invoke
    run_units = unit_cases.UnitCheckTests.run_units
    case = unit_cases.UnitCheckTests.case
    units_status = unit_cases.UnitCheckTests.units_status
    fail_first = unit_cases.UnitCheckTests.fail_first

    def setUp(self):
        unit_cases.UnitCheckTests.setUp(self)

    def history(self, ident):
        """Every status one review unit was shown with, each change once."""
        seen = []
        for state in self.states:
            for unit in state.get('review_units') or ():
                if unit['id'] == ident and (not seen or seen[-1] != unit['status']):
                    seen.append(unit['status'])
        return seen


@unittest.skipUnless(RUNTIME and units.capability(RUNTIME), 'Harness Research 1.6.0 or newer required.')
class UnitProgressTests(Borrowed, unittest.TestCase):
    def test_units_move_from_waiting_to_working_to_kept_each_with_its_name_and_time(self):
        facts, _ = self.run_units()
        self.assertTrue(facts['review']['accepted'])
        last = self.states[-1]
        shown = last['review_units']
        self.assertEqual(len(shown), 5)
        self.assertEqual([unit['kind'] for unit in shown].count('final'), 1)
        final = next(unit for unit in shown if unit['kind'] == 'final')
        self.assertEqual((final['id'], final['label']), (units.FINAL, 'the whole research'))
        questions = {question['question'] for question in self.task['planning_questions']}
        self.assertEqual({unit['label'] for unit in shown if unit['kind'] == 'content'}, questions,
                         'each part is named by the area it checks')
        for unit in shown:
            # A part is listed silently from its plan and shown once a part's job starts: the
            # first parts are shown working at once, the others wait their turn.
            self.assertIn(self.history(unit['id']), (['waiting', 'working', 'kept'], ['working', 'kept']))
            self.assertEqual(unit['attempts'], 1)
            self.assertGreaterEqual(unit['seconds'], 0.1, 'each review took the worker its pause')
            self.assertLess(unit['seconds'], 60)
            self.assertNotIn('started_at', unit, 'a kept unit is no longer timed')
        self.assertEqual(last['counts']['check'], {'working': 0, 'total': 5, 'waiting': 0, 'kept': 5,
                                                   'failed': 0, 'stopped': 0})
        # While a unit works, its start is shown for the page to time it from.
        working = [unit for state in self.states for unit in state.get('review_units') or ()
                   if unit['status'] == 'working' and unit.get('started_at')]
        self.assertTrue(working)
        # Areas and sections are timed too, from the host's own record of their attempts.
        for row in last['streams'] + last['combining']:
            self.assertEqual(row['attempts'], 1)
            self.assertGreaterEqual(row['seconds'], 0)
        # The final brief is its own entry, never one of the section drafts.
        self.assertEqual(last['final_brief']['status'], 'kept')
        self.assertEqual(last['final_brief']['attempts'], 1)
        self.assertEqual(len(last['combining']), 4)
        briefs = [state['final_brief']['status'] for state in self.states if state.get('final_brief')]
        self.assertEqual([s for i, s in enumerate(briefs) if not i or briefs[i - 1] != s], ['waiting', 'working', 'kept'])
        self.assertNotIn('ended_in', last)

    def test_working_now_is_observed_and_never_the_limit(self):
        self.run_units(limit=3)
        checking = [state['counts']['check'] for state in self.states if 'check' in state.get('counts', {})]
        self.assertTrue(checking)
        self.assertLessEqual(max(held['working'] for held in checking), 3)
        # The final unit is checked alone: with a limit of 3, one works.
        alone = [state['counts']['check']['working'] for state in self.states
                 if any(unit['kind'] == 'final' and unit['status'] == 'working' for unit in state.get('review_units') or ())]
        self.assertTrue(alone)
        self.assertEqual(set(alone) - {0}, {1}, 'one unit at work shows 1, not the limit of 3')
        combining = [state['counts']['combine'] for state in self.states
                     if (state.get('final_brief') or {}).get('status') == 'working']
        self.assertTrue(combining)
        self.assertEqual({held['working'] for held in combining} - {0}, {1}, 'the final brief is written by one author')
        self.assertEqual(transport.describe(self.states[-1]), 'The evidence, report and brief passed their independent check.')

    def test_a_failed_unit_is_failed_its_peers_kept_and_the_failure_names_it(self):
        self.before = self.fail_first('question-2')
        with self.assertRaisesRegex(ValueError, 'Synthetic reviewer failure') as raised:
            self.run_units()
        last = self.states[-1]
        statuses = {unit['label']: unit['status'] for unit in last['review_units']}
        self.assertEqual(statuses, {'Synthetic question 0': 'kept', 'Synthetic question 1': 'kept',
                                    'Synthetic question 2': 'failed', 'Synthetic question 3': 'kept',
                                    'the whole research': 'waiting'})
        self.assertEqual(last['counts']['check']['failed'], 1)
        said = ('The independent check of “Synthetic question 2” could not finish: Synthetic reviewer failure. '
                'The checks of the other 3 parts are kept; only what is left is checked again, then the whole research.')
        self.assertEqual(last['ended_in'], {'part': 'review-unit', 'how': 'failed', 'label': 'Synthetic question 2',
                                            'kept': 3, 'total': 5, 'said': said,
                                            'next': 'Next: go on when you are ready; what is kept is not done again.'})
        self.assertEqual(transport.describe(last), said)
        self.assertEqual(str(raised.exception), said, 'one ending, one sentence')
        # Tried again: the kept units read as kept, not as checked again.
        facts, _ = self.run_units()
        self.assertTrue(facts['review']['accepted'])
        again = self.states[-1]['review_units']
        self.assertEqual({unit['status'] for unit in again}, {'kept'})
        failed = next(unit for unit in again if unit['label'] == 'Synthetic question 2')
        self.assertEqual(failed['attempts'], 2)
        self.assertEqual(sorted(unit['attempts'] for unit in again), [1, 1, 1, 1, 2],
                         'the kept parts were not checked again')

    def test_a_stopped_check_says_which_unit_stopped_and_what_was_kept(self):
        def before(unit, payload):
            if len(self.reviews) == 3:
                self.cancel.set()
        self.before = before
        with self.assertRaises(InterruptedError):
            self.run_units(limit=1)
        last = self.states[-1]
        self.assertEqual(last['phase'], 'stopped')
        self.assertEqual(sorted(unit['status'] for unit in last['review_units']),
                         ['kept', 'kept', 'stopped', 'waiting', 'waiting'])
        self.assertEqual(last['ended_in']['how'], 'stopped')
        self.assertTrue(last['ended_in']['said'].startswith('Research stopped during the independent check of “Synthetic question'))
        self.assertIn('The checks of the other 2 parts are kept', last['ended_in']['said'])
        self.assertEqual(last['counts']['check']['working'], 0)

    def test_a_snapshot_stays_small(self):
        self.run_units()
        last = self.states[-1]
        added = {key: last[key] for key in ('review_units', 'counts', 'final_brief')}
        # Names, statuses and numbers only: never evidence, previews or review text.
        self.assertLess(len(json.dumps(added)), 2000)
        for unit in last['review_units']:
            self.assertLessEqual(set(unit), {'id', 'kind', 'label', 'status', 'attempts', 'seconds', 'started_at'})


@unittest.skipUnless(RUNTIME, 'Pinned helper required.')
class FinalBriefProgressTests(unittest.TestCase):
    setUp = section_cases.SectionWorkflowTests.setUp
    invoke = section_cases.SectionWorkflowTests.invoke
    run_sections = section_cases.SectionWorkflowTests.run_sections

    def test_a_final_brief_failure_names_the_final_brief_and_keeps_every_section_draft(self):
        self.fail_final = True
        with self.assertRaisesRegex(ValueError, 'Synthetic final brief timeout') as raised:
            self.run_sections()
        last = self.states[-1]
        self.assertEqual(last['final_brief']['status'], 'failed')
        self.assertEqual({row['status'] for row in last['combining']}, {'kept'}, 'the section drafts are kept')
        said = ('The final brief could not finish: Synthetic final brief timeout. All 4 section drafts are kept; '
                'only the final brief is written again.')
        self.assertEqual(str(raised.exception), said, 'one ending, one sentence')
        self.assertEqual(last['ended_in']['said'], said)
        self.assertEqual(last['counts']['combine']['failed'], 1)
        self.assertEqual(last['counts']['combine']['kept'], 4)
        self.assertEqual(transport.describe(last), said)

    def test_a_check_by_one_reviewer_shows_no_units(self):
        facts, _ = self.run_sections()
        self.assertTrue(facts['review']['accepted'])
        for state in self.states:
            self.assertNotIn('review_units', state)
            self.assertNotIn('check', state['counts'])
        self.assertEqual(self.states[-1]['final_brief']['status'], 'kept')


class WordsTests(unittest.TestCase):
    """The one sentence every studio shows, without a runtime."""

    def test_each_part_names_itself_and_what_is_kept(self):
        self.assertEqual(transport.ended_words('final-brief', 'timed-out', kept=3, detail='It ran out of time'),
                         'The final brief ran out of time: It ran out of time. All 3 section drafts are kept; '
                         'only the final brief is written again.')
        self.assertEqual(transport.ended_words('whole-check', 'failed', kept=4),
                         'The independent check of the whole research could not finish. The checks of all 4 parts '
                         'are kept; only the whole research is checked again.')
        self.assertEqual(transport.ended_words('review-unit', 'stopped', label='Costs', kept=1),
                         'Research stopped during the independent check of “Costs”. The checks of the other 1 part '
                         'are kept; only what is left is checked again, then the whole research.')
        self.assertEqual(transport.ended_words('final-brief', 'failed', kept=0),
                         'The final brief could not finish. Only the final brief is written again.',
                         'no section draft is called kept that is not counted')
        self.assertEqual(transport.ended_words('review-unit', 'failed', parts=2, kept=0),
                         'The independent check of 2 parts of the research could not finish. No other part of the '
                         'check had finished; evidence and drafts are kept.')

    def test_a_native_job_that_ended_is_named_from_the_progress_last_shown(self):
        progress = {'combining': [{'status': 'kept'}, {'status': 'kept'}],
                    'review_units': [{'id': 'unit-a', 'label': 'Costs', 'status': 'working'},
                                     {'id': 'unit-b', 'label': 'Risks', 'status': 'kept'},
                                     {'id': 'final', 'label': 'the whole research', 'status': 'waiting'}]}
        self.assertEqual(transport.job_ended({'section': 'final'}, progress), ('final-brief', None))
        self.assertEqual(transport.job_ended({'unit': 'unit-a'}, progress), ('review-unit', 'Costs'))
        self.assertEqual(transport.job_ended({'unit': 'final'}, progress), ('whole-check', None))
        self.assertIsNone(transport.job_ended({'stream': 'area1'}, progress))
        self.assertEqual(transport.job_words('review-unit', 'Costs', 'It failed.'),
                         'The independent check of “Costs” could not finish: It failed. The other parts carry on; '
                         'what they finish is kept.')

    def test_a_stopped_run_says_what_it_kept(self):
        progress = {'phase': 'stopped', 'streams': [{'status': 'kept'}] * 2,
                    'combining': [{'status': 'kept'}, {'status': 'waiting'}], 'final_brief': {'status': 'waiting'},
                    'review_units': [{'status': 'waiting'}] * 3}
        said = 'Research stopped. Kept: 2 of 2 research areas and 1 of 2 section drafts.'
        self.assertEqual(transport.ended_words('research', 'stopped', summary=transport.kept_summary(progress)), said)
        # describe says the run's one sentence, and counts nothing of its own.
        self.assertEqual(transport.describe({**progress, 'ended_in': {'said': said}}), said)
        self.assertNotIn('Kept', transport.describe(progress))
        # A snapshot saved before #379 says what it said.
        self.assertEqual(transport.describe({'phase': 'review', 'workstreams': []}),
                         'Independently checking the report against the captured sources.')
        self.assertEqual(transport.describe({'phase': 'synthesize', 'agents': {'active': [{'section': 'final'}]}}),
                         'Assembling the final brief from saved section drafts.')

    def test_a_final_brief_or_part_out_of_time_in_training_studio_is_the_run_s_one_sentence(self):
        problems = []
        engine = SimpleNamespace(
            _load=lambda root: {'section_synthesis': {'more_time': {}}, 'limits': {'step_seconds': 900}},
            _problem=lambda *args, **kwargs: problems.append((args, kwargs)))
        brief = ('The final brief ran out of time: Timed out. All 3 section drafts are kept; '
                 'only the final brief is written again.')
        error = Exception(brief)
        error.section, error.section_seconds = 'final', 450
        error.research_ended = {'part': 'final-brief', 'how': 'timed-out', 'said': brief}
        self.assertTrue(sections.timeout(engine, None, error, 'training'))
        (_, step, state, what, kept, action), extra = problems[0]
        self.assertEqual(what, brief, 'the stop says what the progress says')
        self.assertTrue(kept.startswith('It ran out of the time a step may take: it was stopped after 7.5 minutes.'))
        self.assertNotIn('Try again', what)
        self.assertEqual((action, extra['detail']), ('more-time', {'seconds': 450, 'section': 'final'}))
        # A part of the check out of time: named, with what is kept, and more time for the step.
        part = ('The independent check of “Costs” ran out of time: Timed out. The checks of the other 3 parts are '
                'kept; only what is left is checked again, then the whole research.')
        error = Exception(part)
        error.research_ended = {'part': 'review-unit', 'how': 'timed-out', 'label': 'Costs', 'said': part}
        self.assertTrue(sections.timeout(engine, None, error, 'training'))
        (_, _, _, what, kept, action), extra = problems[1]
        self.assertEqual(what, part)
        self.assertEqual((action, extra['detail']), ('more-time', {'seconds': 900}))
        # Neither: another step's timeout, said as before.
        self.assertFalse(sections.timeout(engine, None, Exception('x'), 'training'))

    def test_how_a_job_ended_is_read_from_the_error(self):
        self.assertTrue(research_run.timed_out(SimpleNamespace(outcome=SimpleNamespace(reason='timeout'))))
        self.assertTrue(research_run.timed_out(SimpleNamespace(reason='time-limit')))
        self.assertFalse(research_run.timed_out(ValueError('no')))


if __name__ == '__main__':
    unittest.main()
