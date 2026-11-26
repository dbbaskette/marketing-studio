"""What research progress calls kept is never done again (issue #379, fix round), through the
real Harness Research runtime with a scripted worker.

Every snapshot of a two-round run (a correction after the first check) is walked, with stops
at each stage and research continued after each stop: an area, a section draft, the final
brief or a part of the check shown as kept is not done again until a later snapshot has said
it will be (a correction round: phase needs-revision). How a run ended is one sentence, said
once every peer has ended, and it is what the studio's error says too."""
import os
import threading
import unittest
from unittest import mock

import marketing_studio  # noqa: F401
from studio_core import research_run, research_transport as transport
from studio_core import research_units as units
import test_research_units as unit_cases

RUNTIME = os.environ.get('STUDIO_TEST_RESEARCH_RUNTIME')


@unittest.skipUnless(RUNTIME and units.capability(RUNTIME), 'Harness Research 1.6.0 or newer required.')
class KeptWalkTests(unittest.TestCase):
    """The run of test_research_units: four sections, a check in five units."""
    run_units = unit_cases.UnitCheckTests.run_units
    case = unit_cases.UnitCheckTests.case

    def setUp(self):
        unit_cases.UnitCheckTests.setUp(self)
        self.pause = 0.02
        self.events, self.stop_at, self.stopped = [], None, False
        self.walk_lock = threading.Lock()
        corrected = unit_cases.area_of('question-1')
        def change(unit, answer, payload):
            # The first check narrows one fact of question-1: a correction round follows.
            if payload['_execution']['round'] == 1 and payload['assignment']['unit']['areas'] == [corrected]:
                answer['facts'][0].update(verdict='narrow', note='Synthetic located fact correction.')
        self.change = change
        self.states = Recorder(self)

    def invoke(self, phase, guidance, payload, offered, fetch):
        execution = payload['_execution']
        mode = execution.get('mode')
        done = (('final',) if mode == 'compose-final' else ('section', execution['section']) if mode == 'compose-section'
                else ('unit', execution['unit']) if execution.get('unit') else ('area', execution['stream'])
                if phase == 'investigate' else (phase,))
        with self.walk_lock:
            self.events.append(('do', done))
            if self.stop_at and not self.stopped and self.stop_at(phase, execution, done):
                self.stopped = True
                self.cancel.set()   # the run stops once this job hands back
        return unit_cases.UnitCheckTests.invoke(self, phase, guidance, payload, offered, fetch)

    def kept(self, state):
        return ({('area', row['id']) for row in state.get('streams') or () if row['status'] == 'kept'}
                | {('section', row['id']) for row in state.get('combining') or () if row['status'] == 'kept'}
                | ({('final',)} if (state.get('final_brief') or {}).get('status') == 'kept' else set())
                | {('unit', row['id']) for row in state.get('review_units') or () if row['status'] == 'kept'})

    def assert_kept_holds(self):
        """P1 at every snapshot: what it calls kept is not done again before a later snapshot
        decided a correction round; and what it counts is what it lists."""
        events = self.events
        for at, (kind, state) in enumerate(events):
            if kind != 'state':
                continue
            for stage, rows in (('gather', state['streams']), ('check', state.get('review_units') or [])):
                if stage in state['counts']:
                    self.assertEqual(state['counts'][stage]['kept'], sum(row['status'] == 'kept' for row in rows))
            kept = self.kept(state)
            for later in events[at + 1:]:
                # What a later decision redoes (a correction round, a stop) may be done again
                # after that decision's own snapshot, which must already say so.
                if later[0] == 'state' and later[1]['phase'] in DECIDED and later[1] is not state:
                    break
                if later[0] == 'do':
                    self.assertNotIn(later[1], kept, f'snapshot {at} ({state["phase"]}, round {state["round"]}) '
                                     f'called {later[1]} kept, and it was done again')

    def stop_then_go_on(self, stop_at, limit=3):
        self.stop_at = stop_at
        with self.assertRaises(InterruptedError) as raised:
            self.run_units(limit=limit)
        self.assertTrue(self.stopped)
        last = self.states[-1]
        self.assertEqual(last['phase'], 'stopped')
        ended = last['ended_in']
        self.assertEqual(ended['how'], 'stopped')
        self.assertEqual(raised.exception.research_ended['said'], ended['said'])
        self.assertEqual(transport.describe(last), ended['said'], 'describe says the same sentence')
        if ended['part'] == 'research':
            self.assertEqual(ended['said'], 'Research stopped. ' + (transport.kept_summary(last) or
                             'Going on gathers the evidence again; your sources are kept.'))
        self.cancel.clear()
        # Research goes on as Training Studio, Presentation Studio and Infographic Studio go
        # on after a stop: a stopped collection starts its next generation.
        facts, _ = self.run_units(restart_stopped=True)
        self.assertTrue(facts['review']['accepted'])
        self.assert_kept_holds()
        return ended

    def test_a_correction_round_never_shows_what_it_does_again_as_kept(self):
        facts, _ = self.run_units()
        self.assertTrue(facts['review']['accepted'])
        self.assert_kept_holds()
        revision = next(state for kind, state in self.events if kind == 'state' and state['phase'] == 'needs-revision')
        self.assertEqual(revision['final_brief'], {**revision['final_brief'], 'status': 'waiting', 'again': True})
        self.assertEqual({(row['status'], row.get('again')) for row in revision['review_units']}, {('waiting', True)},
                         'which parts hold is not known until the corrected dossier is planned')
        self.assertEqual(revision['counts']['check']['kept'], 0)
        self.assertEqual(revision['counts']['combine']['kept'], 3, 'three section drafts are kept, one is written again')
        again = [row for row in revision['combining'] if row.get('again')]
        self.assertEqual([row['id'] for row in again], [unit_cases.area_of('question-1')])
        # Once planned, the parts Harness Research keeps are kept and say so.
        last = self.states[-1]
        self.assertEqual({row['status'] for row in last['review_units']}, {'kept'})

    def test_a_stop_while_gathering_again_keeps_only_what_is_kept(self):
        ended = self.stop_then_go_on(lambda phase, execution, done: done[0] == 'area' and execution['round'] == 2)
        self.assertEqual(ended['part'], 'research')
        self.assertNotIn('parts of the check', ended['said'])
        self.assertNotIn('final brief', ended['said'])

    def test_a_stop_while_writing_a_section_again_keeps_only_what_is_kept(self):
        self.stop_then_go_on(lambda phase, execution, done: done[0] == 'section' and execution['round'] == 2)

    def test_a_stop_while_writing_the_final_brief_again_keeps_only_what_is_kept(self):
        # A stop outside the check stops the collection: going on gathers the evidence again,
        # so no section draft is called kept.
        ended = self.stop_then_go_on(lambda phase, execution, done: done == ('final',) and execution['round'] == 2)
        self.assertEqual(ended['said'], 'Research stopped. Going on gathers the evidence again; your sources are kept.')

    def test_a_stop_while_checking_again_names_the_part(self):
        ended = self.stop_then_go_on(lambda phase, execution, done: done[0] == 'unit' and execution['round'] == 2)
        self.assertIn(ended['part'], ('review-unit', 'whole-check'))

    def test_a_stop_in_the_first_check_keeps_its_accepted_parts(self):
        self.change = None
        ended = self.stop_then_go_on(lambda phase, execution, done: done[0] == 'unit'
                                     and sum(event[1][0] == 'unit' for event in self.events if event[0] == 'do') == 3, limit=1)
        self.assertEqual(ended['part'], 'review-unit')
        self.assertIn('The checks of the other 2 parts are kept', ended['said'])

    def test_a_pause_is_called_a_pause(self):
        self.change = None
        paused = threading.Event()
        # The first part's job pauses research: allowed() turns False, nothing is stopped.
        self.stop_at = lambda phase, execution, done: done[0] == 'unit' and (paused.set() or False)
        with self.assertRaisesRegex(InterruptedError, 'paused'):
            self.workflow.run(self.root, self.task, self.invoke, progress=self.states.append,
                              section_policy=unit_cases.sections.pin(), section_context={'combining': 'synthetic-medium'},
                              review_units=self.units, limit=1, cancelled=lambda: False, allowed=lambda: not paused.is_set())
        ended = self.states[-1]['ended_in']
        self.assertEqual(ended['how'], 'paused')
        self.assertTrue(ended['said'].startswith('Research paused during the independent check of “'), ended['said'])


# Snapshots at which what will be done again is decided and said: a correction round, a stop
# or pause, changed originals, and an attention stop that retries every area.
DECIDED = ('needs-revision', 'stopped', 'paused', 'invalidated', 'needs-attention', 'check-incomplete')


class Recorder(list):
    """The progress callback: each snapshot, in order with the jobs the run starts."""

    def __init__(self, test):
        super().__init__()
        self.test = test

    def append(self, state):
        with self.test.walk_lock:
            super().append(state)
            self.test.events.append(('state', state))


@unittest.skipUnless(RUNTIME and units.capability(RUNTIME), 'Harness Research 1.6.0 or newer required.')
class OneSentenceTests(unittest.TestCase):
    """P2: one ending, one sentence, computed once every peer has ended."""
    run_units = unit_cases.UnitCheckTests.run_units
    invoke = unit_cases.UnitCheckTests.invoke
    case = unit_cases.UnitCheckTests.case
    units_status = unit_cases.UnitCheckTests.units_status
    fail_first = unit_cases.UnitCheckTests.fail_first

    def setUp(self):
        unit_cases.UnitCheckTests.setUp(self)

    def test_a_failed_part_is_said_once_with_what_its_peers_finished(self):
        # The failing part ends first, while its peers still work: the sentence waits for them.
        slow = unit_cases.area_of('question-2')
        def before(unit, payload):
            if payload['assignment']['unit']['areas'] == [slow] and not getattr(self, 'failed', False):
                self.failed = True
                raise ValueError('Synthetic reviewer failure')
        self.before = before
        with self.assertRaises(ValueError) as raised:
            self.run_units()
        last = self.states[-1]
        said = ('The independent check of “Synthetic question 2” could not finish: Synthetic reviewer failure. '
                'The checks of the other 3 parts are kept; only what is left is checked again, then the whole research.')
        self.assertEqual(last['ended_in']['said'], said)
        self.assertEqual(str(raised.exception), said, 'what a studio shows of the failure is the same sentence')
        self.assertEqual(transport.describe(last), said)
        self.assertEqual(last['counts']['check']['kept'], 3)

    def test_showing_a_unit_can_never_change_the_check(self):
        real = research_run.Run.unit_seen
        def broken(run, action, value, result):
            real(run, action, value, result)
            if isinstance(result, dict):
                result.clear()          # what is shown is a copy: the helper's answer is untouched
            raise RuntimeError('Synthetic: the page could not be told.')
        with mock.patch.object(research_run.Run, 'unit_seen', broken):
            facts, _ = self.run_units()
        self.assertTrue(facts['review']['accepted'])
        self.assertEqual({row['status'] for row in self.units_status()['units']}, {'accepted'})

    def test_a_report_that_raises_while_a_unit_is_shown_changes_nothing(self):
        real = research_run.Run.report
        def report(run, *args, **kwargs):
            if any(frame.f_code.co_name == 'unit_seen' for frame in _frames()):
                raise RuntimeError('Synthetic: the progress could not be saved.')
            return real(run, *args, **kwargs)
        with mock.patch.object(research_run.Run, 'report', report):
            facts, _ = self.run_units()
        self.assertTrue(facts['review']['accepted'])
        self.assertEqual({row['status'] for row in self.units_status()['units']}, {'accepted'})


def _frames():
    import sys
    frame = sys._getframe(1)
    while frame:
        yield frame
        frame = frame.f_back


class ListingTests(unittest.TestCase):
    def test_a_listing_before_the_corrected_dossier_is_planned_calls_nothing_kept(self):
        run = object.__new__(research_run.Run)
        run.state_lock, run.tracked, run.units_plan = threading.RLock(), {'streams': []}, None
        run.units_shown = {'unit-a': {'id': 'unit-a', 'kind': 'content', 'label': 'A', 'status': 'kept', 'attempt': 1}}
        run.report = lambda *args, **kwargs: None
        stale = {'phase': 'needs-plan', 'units': [{'id': 'unit-a', 'kind': 'content', 'status': 'accepted'},
                                                 {'id': 'final', 'kind': 'final', 'status': 'accepted'}]}
        run.unit_seen('status', None, stale)
        self.assertEqual({(unit['status'], unit['again']) for unit in run.units_shown.values()}, {('waiting', True)})
        planned = {**stale, 'phase': 'reviewing', 'plan_file': '.harness-research/plan.json',
                   'units': [{'id': 'unit-a', 'kind': 'content', 'status': 'kept'}, {'id': 'final', 'kind': 'final', 'status': 'pending'}]}
        run.unit_seen('plan', None, planned)
        self.assertEqual({ident: (unit['status'], unit['again']) for ident, unit in run.units_shown.items()},
                         {'unit-a': ('kept', False), 'final': ('waiting', True)})
        self.assertEqual(run.units_plan, '.harness-research/plan.json')


class WordsTests(unittest.TestCase):
    def test_a_job_that_ends_while_its_peers_work_counts_nothing(self):
        progress = {'combining': [{'status': 'kept'}], 'review_units': [
            {'id': 'unit-a', 'label': 'Costs', 'status': 'failed'}, {'id': 'unit-b', 'label': 'Risks', 'status': 'kept'},
            {'id': 'final', 'status': 'waiting'}]}
        self.assertEqual(transport.job_ended({'unit': 'unit-a'}, progress), ('review-unit', 'Costs'))
        self.assertEqual(transport.job_ended({'unit': 'final'}, progress), ('whole-check', None))
        self.assertEqual(transport.job_ended({'section': 'final'}, progress), ('final-brief', None))
        self.assertEqual(transport.job_words('review-unit', 'Costs', 'It failed'),
                         'The independent check of “Costs” could not finish: It failed. The other parts carry on; '
                         'what they finish is kept.')
        for said in (transport.job_words('review-unit', 'Costs', 'x'), transport.job_words('final-brief', None, 'x')):
            self.assertNotRegex(said, r'\d', 'no count while peers may still work')

    def test_kept_is_said_only_of_what_is_kept(self):
        progress = {'streams': [{'status': 'kept'}, {'status': 'waiting'}, None],
                    'combining': [{'status': 'kept'}, {'status': 'waiting', 'again': True}],
                    'final_brief': {'status': 'waiting', 'again': True},
                    'review_units': [{'status': 'waiting', 'again': True}, {'status': 'waiting', 'again': True}]}
        self.assertEqual(transport.kept_summary(progress), 'Kept: 1 of 2 research areas and 1 of 2 section drafts.')
        self.assertEqual(transport.kept_summary({}), '')
        self.assertEqual(transport.ended_words('research', 'paused', summary=''),
                         'Research paused. Nothing had finished yet; your sources are kept.')

    def test_no_sentence_names_a_button(self):
        for part in ('final-brief', 'review-unit', 'whole-check'):
            for how in ('failed', 'timed-out', 'stopped', 'paused'):
                said = transport.ended_words(part, how, label='Costs', kept=2, total=5, detail='It ended.')
                self.assertNotIn('Try again', said)
                self.assertNotIn('more time', said)
        self.assertTrue(transport.ended_words('review-unit', 'paused', label='Costs', kept=1).startswith(
            'Research paused during the independent check of “Costs”.'))
        self.assertTrue(transport.ended_words('review-unit', 'stopped', label='Is it so?', kept=1).startswith(
            'Research stopped during the independent check of “Is it so?” The checks'), 'one mark ends a question')


if __name__ == '__main__':
    unittest.main()
