"""Change settings on a stopped Training Studio training (#296), with disposable workspaces,
the scripted agent and the research stand-in: nothing here reaches a provider or the network."""
import json
from pathlib import Path
from unittest import mock

import hashlib
import os
import unittest

from test_runner_deck import DeckCase, PageCase
import test_parallel_research  # its scripted worker, borrowed by name so its tests run once
from studio_core import research_contract as contract
import test_desk  # its screen tests' helpers, borrowed by name so its tests are not run here
from test_desk import NODE, ScriptedPage, a_desk, a_desk_run, ok
from test_desk import PageCase as DeskPageCase
import helpers
from runner_support import FORM, fails
import workspace
from runner import pipeline, settings_change
from studio_core import research_session, research_sources
from workspace import WorkspaceError

QUESTIONS = ['How many instances keep capacity during a restart?',
             'What starts the next batch?',
             'Do rolling restarts guarantee zero downtime?']
THREE = {'topic': 'Rolling restarts', 'items': [
    {'id': f'question-{number}', 'question': text, 'public_query': f'rolling restart {number}'}
    for number, text in enumerate(QUESTIONS, 1)]}
NOTES = 'Capacity holds only when more than one instance is running.'


class SettingsCase(DeckCase):
    def supplied(self, **changes) -> Path:
        """A desk training researched from its documents only, as the start form's default
        leaves it, whose research stopped after one paid try."""
        store = research_sources.Sources(self.space.root / '.research-sources')
        draft = store.create()
        draft = store.mutate(draft['id'], draft['revision'], 'capture', kind='text',
                             name='Reference notes', text=NOTES)
        form = pipeline.check_form({**FORM, 'flow': 'desk', 'materials': ['document'], **changes})
        self.workers.then('research-result', fails(cost=1.25))
        started = self.engine.start(form, research_inputs={'id': draft['id'],
                                                           'expected': draft['revision']})
        return Path(started['path'])

    def form(self, root: Path) -> dict:
        return self.engine.settings_form(root)

    def sent(self, shown: dict, **changes) -> dict:
        return {**shown['values'], 'expected': shown['revision'], **changes}

    def external(self, root: Path) -> dict:
        """The source panel's draft of what the training reads, with external search on."""
        draft = self.engine.settings_sources(root)
        store = research_sources.Sources(self.space.root / '.research-sources')
        draft = store.mutate(draft['id'], draft['revision'], 'configure', external=True)
        return {'id': draft['id'], 'expected': draft['revision']}

    def researched_jobs(self) -> int:
        return len(self.workers.of('research-result')) + len(self.workers.of('research-plan'))


class DiscardTests(SettingsCase):
    def test_documents_only_becomes_documents_and_web_with_three_questions(self):
        root = self.supplied()
        drafts_before = set((self.space.root / '.research-sources').iterdir())
        stopped = self.view(root)
        self.assertEqual(stopped['state'], 'failed')
        self.assertTrue(stopped['settings']['may'], stopped['settings'])
        shown = self.form(root)
        self.assertTrue(shown['may'])
        self.assertEqual(shown['values']['research_from'], {'documents': True, 'sites': [], 'web': False})
        self.assertEqual(shown['values']['research_questions'], [])
        # The source panel opens holding the training's own capture.
        draft = self.engine.settings_sources(root)
        self.assertEqual([source['name'] for source in draft['sources']], ['Reference notes'])
        reference = self.external(root)
        sent = self.sent(shown, research_questions=QUESTIONS, research_inputs=reference)
        said = self.engine.change_settings(root, sent, preview=True)
        self.assertEqual(said['research'], 'replanned')
        self.assertTrue(said['confirm'])
        self.assertEqual(said['discards']['tries'], 1)
        self.assertEqual(said['discards']['dollars'], 1.25)
        words = ' '.join(said['words'])
        self.assertIn('$1.25', words)
        self.assertIn('cannot be undone', words)
        self.assertIn('Nothing starts until you press Continue.', words)
        self.assertEqual(set(said['changed']), {'research_questions', 'search'})
        # A preview changes nothing.
        self.assertEqual(self.form(root)['revision'], shown['revision'])
        with self.assertRaisesRegex(WorkspaceError, 'confirm'):
            self.engine.change_settings(root, sent)
        jobs = self.researched_jobs()
        commits = len(self.log())
        changed = self.engine.change_settings(root, {**sent, 'confirmed': True})
        self.assertEqual(changed['state'], 'waiting')
        self.assertEqual(changed['problem']['label'], 'Continue')
        self.assertIn('Nothing starts until you press Continue', changed['problem']['what'])
        self.assertEqual(self.researched_jobs(), jobs, 'Nothing starts before Continue')
        self.assertEqual(len(self.log()), commits + 1)
        self.assertTrue(self.log()[-1].endswith("change the training's settings: the research "
                                                'questions and where research may search'),
                        self.log()[-1])
        record = self.record(root)
        self.assertEqual(record['research_from'], {'documents': True, 'sites': [], 'web': True})
        self.assertEqual(record['documents']['scope'], 'both')
        self.assertEqual(record['research_questions'], QUESTIONS)
        self.assertIsNone(record['research'])
        self.assertFalse((root / pipeline.PLAN).exists(), 'The plan is planned again')
        self.assertIn('The public web and your documents', (root / 'intake.md').read_text())
        self.assertEqual(record['settings_changes'][-1]['research'], 'replanned')
        # The sheet's source drafts are taken away once the change is saved; only the
        # start's own draft is left.
        self.assertEqual({path for path in (self.space.root / '.research-sources').iterdir()
                          if len(path.name) == 32}, {path for path in drafts_before
                                                       if len(path.name) == 32})
        # Continue plans with three questions and researches with web access allowed.
        self.workers.plan = THREE
        self.engine.act(root, 'retry')
        plan = json.loads((root / pipeline.PLAN).read_text())
        self.assertEqual([item['question'] for item in plan['items']], QUESTIONS)
        planned = self.workers.of('research-plan')[-1]
        asked = next(spec for kind, job, spec in self.workers.jobs if kind == 'research-plan')
        self.assertTrue(planned)
        self.assertEqual(asked['artifacts']['research-plan']['scope'], 'public-web')
        authors = [spec for kind, job, spec in self.workers.jobs if kind == 'research-result']
        self.assertFalse(authors[0]['fetch'], 'The first research read documents only')
        self.assertTrue(authors[1]['fetch'], 'Research may now fetch public pages')
        self.assertEqual(workspace.statuses(root, workspace.load(root))['research'], 'approved')

    def test_cancel_changes_nothing(self):
        root = self.supplied()
        before = {name: (root / name).read_bytes() for name in (
            'intake.md', '.training-studio/run.json', '.training-studio/session.json', pipeline.PLAN)}
        commits = self.log()
        shown = self.form(root)
        self.external(root)   # the sheet opened its source draft, then was put away
        self.engine.change_settings(root, self.sent(shown, topic='Another topic'), preview=True)
        self.assertEqual({name: (root / name).read_bytes() for name in before}, before)
        self.assertEqual(self.log(), commits)

    def test_a_failed_save_puts_everything_back(self):
        root = self.supplied()
        shown = self.form(root)
        before = {name: (root / name).read_bytes() for name in (
            'intake.md', '.training-studio/run.json', '.training-studio/session.json', pipeline.PLAN)}
        sent = self.sent(shown, research_questions=QUESTIONS, research_inputs=self.external(root),
                         confirmed=True)
        with mock.patch.object(self.engine, '_commit', side_effect=RuntimeError('Synthetic')):
            with self.assertRaises(RuntimeError):
                self.engine.change_settings(root, sent)
        self.assertEqual({name: (root / name).read_bytes() for name in before}, before)

    def test_another_level_restarts_unaccepted_research_with_the_plan_kept(self):
        root = self.supplied(levels=['101'])
        record = self.record(root)
        record['research_execution'] = {'progress': {'phase': 'investigate'}}
        self.engine._store(root, record)
        plan = (root / pipeline.PLAN).read_bytes()
        shown = self.form(root)
        with mock.patch.object(research_session, 'protocol', return_value=True):
            said = self.engine.change_settings(root, self.sent(shown, levels=['101', '201']),
                                               preview=True)
            self.assertEqual(said['research'], 'restarted')
            self.assertEqual(said['discards']['tries'], 1)
            self.engine.change_settings(root, self.sent(shown, levels=['101', '201'],
                                                        confirmed=True))
        self.assertEqual((root / pipeline.PLAN).read_bytes(), plan)
        session = workspace.load(root)
        self.assertEqual(session['levels'], ['101', '201'])
        self.assertEqual(workspace.statuses(root, session)['research-plan'], 'approved')
        self.assertNotIn('progress', self.record(root)['research_execution'])
        self.assertIsNotNone(self.record(root)['research'], 'The plan stays handed over')


class KeepTests(SettingsCase):
    def finished(self, **changes) -> Path:
        """Research accepted, the plan and the guide made, and the brief stopped after its
        three tries: a stop well past research."""
        self.workers.then('brief', fails(), fails(), fails())
        root = self.start(flow='desk', materials=['document', 'brief'], **changes)
        self.to_end(root)
        self.assertEqual(self.view(root)['state'], 'failed')
        return root

    def test_levels_and_brief_kind_keep_research_and_remake_only_what_depends(self):
        root = self.finished(levels=['101'])
        competitive = (helpers.EXAMPLES / 'competitive-brief.md').read_text(encoding='utf-8')

        def compared(tools, job):
            accepted = tools.submit_artifact('brief', competitive)
            assert accepted[0], accepted[1]
        self.workers.then('brief', compared, compared)
        session = workspace.load(root)
        report = (root / pipeline.REPORT).read_bytes()
        blueprint = (root / '101/blueprint.md').read_bytes()
        researched = len(self.workers.of('research-result'))
        written = len(self.workers.of('brief'))
        shown = self.form(root)
        self.assertTrue(shown['research']['accepted'])
        sent = self.sent(shown, levels=['101', '201'], brief_kind='competitive')
        said = self.engine.change_settings(root, sent, preview=True)
        self.assertEqual(said['research'], 'kept')
        self.assertFalse(said['confirm'])
        self.engine.change_settings(root, sent)
        session = workspace.load(root)
        state = workspace.statuses(root, session)
        self.assertEqual(state['research'], 'approved')
        self.assertEqual(state['blueprint@101'], 'approved', 'An added level keeps 101 as it is')
        self.assertEqual(state['brief@101'], 'not-started')
        self.assertEqual(session['settings']['brief_kind'], 'competitive')
        # What stopped is not about these settings: the brief's stop stays, saying they changed.
        problem = self.view(root)['problem']
        self.assertEqual((problem['action'], problem['label']), ('retry', 'Try again'))
        self.assertIn('Its settings were changed', problem['what'])
        self.engine.act(root, 'retry')
        self.assertEqual((root / pipeline.REPORT).read_bytes(), report)
        self.assertEqual((root / '101/blueprint.md').read_bytes(), blueprint)
        self.assertEqual(len(self.workers.of('research-result')), researched, 'Research is kept')
        self.assertGreater(len(self.workers.of('brief')), written)
        # The brief is asked for again, as a comparison, at its new file.
        self.assertEqual(workspace.artifact(root, workspace.load(root), 'brief@101')['file'],
                         '101/competitive-brief.md')
        self.assertTrue((root / '201/blueprint.md').is_file())

    def test_a_research_change_keeps_the_report_unless_research_again(self):
        root = self.finished()
        shown = self.form(root)
        # The source panel opens on what the public web training reads, and changes nothing.
        draft = self.engine.settings_sources(root)
        self.assertTrue(draft['external'])
        said = self.engine.change_settings(root, self.sent(
            shown, audience='Platform operators',
            research_inputs={'id': draft['id'], 'expected': draft['revision']}), preview=True)
        self.assertEqual(said['changed'], ['audience'])
        self.assertEqual(said['research'], 'kept')
        self.assertIn('Research again', ' '.join(said['words']))
        again = self.engine.change_settings(root, self.sent(
            shown, audience='Platform operators', research_again=True), preview=True)
        self.assertEqual(again['research'], 'again')
        self.assertTrue(again['confirm'])
        self.assertGreater(again['discards']['tries'], 0)
        self.engine.change_settings(root, self.sent(shown, audience='Platform operators'))
        session = workspace.load(root)
        self.assertEqual(workspace.statuses(root, session)['research'], 'approved')
        self.assertIn('Platform operators', (root / 'intake.md').read_text())
        held = settings_change.drafts.held(root, session, self.record(root))
        self.assertIn('blueprint', held, 'What is built from the intake waits for the person')

    def test_research_again_is_not_offered_when_research_is_given_nothing_new(self):
        root = self.finished()
        draft = self.engine.settings_sources(root)
        store = research_sources.Sources(self.space.root / '.research-sources')
        draft = store.mutate(draft['id'], draft['revision'], 'configure', workers=2)
        said = self.engine.change_settings(root, self.sent(
            self.form(root), research_again=True,
            research_inputs={'id': draft['id'], 'expected': draft['revision']}), preview=True)
        self.assertEqual(said['changed'], ['workers'])
        self.assertEqual(said['research'], 'kept')
        self.assertFalse(said['confirm'])
        self.assertIn('researching again would repeat it', ' '.join(said['words']))

    def test_research_again_sets_the_report_aside_and_researches_on_continue(self):
        root = self.finished()
        researched = len(self.workers.of('research-result'))
        shown = self.form(root)
        sent = self.sent(shown, audience='Platform operators', research_again=True)
        with self.assertRaisesRegex(WorkspaceError, 'confirm'):
            self.engine.change_settings(root, sent)
        self.engine.change_settings(root, {**sent, 'confirmed': True})
        self.assertFalse((root / pipeline.REPORT).exists())
        self.assertTrue(any((root / '.training-studio/history/research').iterdir()),
                        'A copy of the earlier report is kept in its history')
        self.assertEqual(len(self.workers.of('research-result')), researched)
        self.engine.act(root, 'retry')
        session = workspace.load(root)
        self.assertEqual(workspace.statuses(root, session)['research'], 'approved')
        self.assertGreater(len(self.workers.of('research-result')), researched)
        self.assertIn('blueprint', settings_change.drafts.held(root, session, self.record(root)))


class RefusalTests(SettingsCase):
    def test_an_outdated_form_is_refused(self):
        root = self.supplied()
        shown = self.form(root)
        self.engine.change_settings(root, self.sent(shown, time_limit='40 minutes'))
        with self.assertRaisesRegex(WorkspaceError, 'changed since this form was opened'):
            self.engine.change_settings(root, self.sent(shown, time_limit='50 minutes'))

    def test_a_working_run_is_refused(self):
        root = self.supplied()
        shown = self.form(root)
        run = self.engine._run(root)
        run.busy = True
        try:
            self.assertFalse(self.view(root)['settings']['may'])
            with self.assertRaisesRegex(WorkspaceError, 'working now'):
                self.engine.change_settings(root, self.sent(shown, time_limit='40 minutes'))
        finally:
            run.busy = False

    def test_nothing_changed_is_refused(self):
        root = self.supplied()
        with self.assertRaisesRegex(WorkspaceError, 'Nothing has changed'):
            self.engine.change_settings(root, self.sent(self.form(root)))

    def test_a_saved_run_says_why_it_cannot_be_changed(self):
        root = self.saved_start()
        self.assertEqual(self.view(root)['settings'], {'may': False, 'why': settings_change.OLDER})
        with self.assertRaisesRegex(WorkspaceError, 'started before its settings'):
            self.engine.change_settings(root, {'expected': 'x'})

    def test_a_serial_draft_keeps_what_research_reads(self):
        root = self.supplied()
        case = root / '.studio-research/.harness-research'
        case.mkdir(parents=True)
        (case / 'synthesis.json').write_text('{}')
        shown = self.form(root)
        self.assertIn('topic', shown['locked'])
        with self.assertRaisesRegex(WorkspaceError, 'earlier research workflow'):
            self.engine.change_settings(root, self.sent(shown, topic='Another topic'), preview=True)
        said = self.engine.change_settings(root, self.sent(shown, time_limit='40 minutes'),
                                           preview=True)
        self.assertEqual(said['research'], 'continues')

    def test_a_finished_training_keeps_its_settings(self):
        root = self.start(flow='desk', materials=['document'])
        self.to_end(root)
        if self.view(root)['state'] != 'done':
            self.skipTest('The scripted desk training waits for Mark ready here.')
        self.assertEqual(self.view(root)['settings'], {'may': False, 'why': settings_change.FINISHED})


class StopTests(SettingsCase):
    """What the stop before a change asked for is kept: more time, the spending limit, and
    originals a check could not read."""

    def stopped_as(self, root: Path, **problem) -> None:
        record = self.record(root)
        record['problem'] = {**record['problem'], **problem}
        self.engine._store(root, record)

    def test_a_stop_for_time_keeps_its_own_action_when_research_carries_on(self):
        root = self.supplied()
        self.stopped_as(root, action='more-time', label='Give it more time and try again',
                        seconds=900)
        self.engine.change_settings(root, self.sent(self.form(root), time_limit='40 minutes'))
        problem = self.record(root)['problem']
        self.assertEqual((problem['action'], problem['seconds']), ('more-time', 900))
        with mock.patch.object(self.engine, 'wake'):
            self.engine.act(root, 'more-time')
        self.assertEqual(self.record(root)['more_time'], 1800)

    def test_a_stop_for_time_gives_research_planned_again_the_same_room(self):
        root = self.supplied()
        self.stopped_as(root, action='more-time', label='Give it more time and try again',
                        seconds=900)
        self.engine.change_settings(root, self.sent(self.form(root), research_questions=QUESTIONS,
                                                    confirmed=True))
        problem = self.record(root)['problem']
        self.assertEqual((problem['label'], problem['carried']), ('Continue', 'more-time'))
        with mock.patch.object(self.engine, 'wake'):
            self.engine.act(root, 'retry')
        self.assertEqual(self.record(root)['more_time'], 1800)

    def test_continue_after_a_change_never_lifts_the_spending_limit(self):
        import dataclasses
        from runner import engine as engines
        root = self.supplied()
        record = self.record(root)
        record['spending_policy'] = 'hard-stop'
        self.engine._store(root, record)
        self.stopped_as(root, action='resume', label='Carry on', step=None)
        self.engine.change_settings(root, self.sent(self.form(root), research_questions=QUESTIONS,
                                                    confirmed=True))
        problem = self.record(root)['problem']
        self.assertNotIn('carried', problem)
        self.assertNotIn('twice the time', problem['what'])
        # The limit is under what was spent: Continue runs into it and stops with Carry on.
        tight = dataclasses.replace(engines.settings.load(), training_dollars=1.0)
        with mock.patch.object(engines.settings, 'load', return_value=tight):
            self.engine.act(root, 'retry')
        record = self.record(root)
        self.assertEqual(record['cleared'], 0.0, 'Only Carry on lifts the spending limit')
        self.assertEqual((record['problem']['action'], record['problem']['label']),
                         ('resume', 'Carry on'))

    def test_a_carried_stop_for_time_says_so_and_survives_a_second_change(self):
        root = self.supplied()
        self.stopped_as(root, action='more-time', label='Give it more time and try again',
                        seconds=900)
        self.engine.change_settings(root, self.sent(self.form(root), research_questions=QUESTIONS,
                                                    confirmed=True))
        first = self.record(root)['problem']
        self.assertIn('Continue also gives each step twice the time.', first['what'])
        self.assertIn('plans the research again', first['what'])
        # A second change, which on its own would carry research on, keeps both.
        self.engine.change_settings(root, self.sent(self.form(root), time_limit='40 minutes'))
        second = self.record(root)['problem']
        self.assertEqual((second['carried'], second['seconds']), ('more-time', 900))
        self.assertIn('plans the research again', second['what'])
        self.assertEqual(second['what'].count('twice the time'), 1)
        with mock.patch.object(self.engine, 'wake'):
            self.engine.act(root, 'retry')
        self.assertEqual(self.record(root)['more_time'], 1800)

    def test_two_changes_that_leave_a_stop_say_so_once(self):
        root = self.supplied()
        stopped = self.record(root)['problem']['what']
        self.engine.change_settings(root, self.sent(self.form(root), time_limit='40 minutes'))
        self.engine.change_settings(root, self.sent(self.form(root), time_limit='50 minutes'))
        problem = self.record(root)['problem']
        self.assertEqual(problem['what'].count('Its settings were changed'), 1)
        self.assertTrue(problem['what'].endswith(stopped))
        self.assertEqual(problem['action'], 'retry')

    def test_a_draft_that_cannot_be_tidied_still_reports_the_change_saved(self):
        root = self.supplied()
        sent = self.sent(self.form(root), research_questions=QUESTIONS,
                         research_inputs=self.external(root), confirmed=True)
        with mock.patch.object(settings_change, '_forget_draft', side_effect=OSError('Synthetic')):
            made = self.engine.change_settings(root, sent)
        self.assertEqual(made['changed_settings']['research'], 'replanned')
        self.assertEqual(self.record(root)['research_questions'], QUESTIONS)

    def test_unreadable_originals_are_checked_again_when_research_restarts(self):
        root = self.supplied(levels=['101'])
        self.stopped_as(root, unreadable=['sources/research-inputs/missing.original.raw'])
        with mock.patch.object(research_session, 'protocol', return_value=True):
            self.engine.change_settings(root, self.sent(self.form(root), levels=['101', '201'],
                                                        confirmed=True))
        self.assertEqual(self.record(root)['problem']['unreadable'],
                         ['sources/research-inputs/missing.original.raw'])


class DetailTests(SettingsCase):
    def test_an_unchanged_brand_is_not_checked_against_the_brand_skill(self):
        root = self.supplied()
        with workspace.locked(root):
            session = workspace.load(root)
            session['settings'].update(deck_target='pptx', brand='retired-brand/')
            workspace.store(root, session)
        shown = self.form(root)
        self.assertEqual(shown['values']['brand'], {'brand': 'retired-brand', 'variant': None})
        with mock.patch.object(self.engine, 'brands', return_value=[
                {'brand': 'example-co', 'variants': ['light']}]):
            said = self.engine.change_settings(root, self.sent(shown, time_limit='40 minutes'),
                                               preview=True)
            self.assertEqual(said['changed'], ['time_limit'])
            with self.assertRaisesRegex(WorkspaceError, 'The brand is one of'):
                self.engine.change_settings(root, self.sent(
                    shown, brand={'brand': 'other-brand', 'variant': None}), preview=True)

    def test_one_source_draft_a_training_at_a_time(self):
        root = self.supplied()
        first = self.engine.settings_sources(root)
        second = self.engine.settings_sources(root)
        folder = self.space.root / '.research-sources'
        self.assertFalse((folder / first['id']).exists())
        self.assertTrue((folder / second['id']).exists())

    def test_a_saved_change_is_reported_saved_when_the_run_cannot_be_read_after(self):
        root = self.supplied()
        shown = self.form(root)
        read, calls = self.engine.view, []

        def flaky(path):
            calls.append(path)
            if len(calls) > 1:
                raise RuntimeError('Synthetic read failure')
            return read(path)
        with mock.patch.object(self.engine, 'view', flaky):
            made = self.engine.change_settings(root, self.sent(shown, time_limit='40 minutes'))
        self.assertEqual(made, {'changed_settings': made['changed_settings']})
        self.assertIn('40 minutes', (root / 'intake.md').read_text())


class RouteTests(SettingsCase, PageCase):
    def test_the_form_its_preview_and_its_save_through_the_page(self):
        root = self.supplied()
        shown = self.get('training-settings', path=str(root))
        self.assertTrue(shown['may'])
        draft = self.post('training-settings/sources', {'path': str(root)})
        self.assertEqual(len(draft['sources']), 1)
        sent = {'path': str(root), **self.sent(shown, time_limit='40 minutes')}
        said = self.post('training-settings', {**sent, 'preview': True})
        self.assertEqual(said['changed'], ['time_limit'])
        self.post('training-settings', {**sent, 'preview': 'yes'}, expect=400)
        made = self.post('training-settings', sent)
        # Research carries on as it was, so the stop keeps its own Try again.
        self.assertEqual(made['problem']['label'], 'Try again')
        self.assertIn('Its settings were changed', made['problem']['what'])
        self.assertEqual(made['changed_settings']['changed'], ['time_limit'])
        refused = self.post('training-settings', sent, expect=409)
        self.assertIn('changed since this form was opened', refused['error'])


SHOWN = {'path': '', 'title': 'Rolling restarts', 'may': True, 'why': None, 'revision': 'r1',
         'values': {'topic': 'Rolling restarts on the platform', 'audience': 'Engineers',
                    'purpose': 'Field enablement', 'time_limit': '25 minutes',
                    'levels': ['101', '201'], 'brief_kind': 'product', 'research_questions': [],
                    'research_from': {'documents': True, 'sites': [], 'web': False},
                    'deck_target': None, 'brand': None, 'delivery': 'live', 'walkthrough': False},
         'locked': {}, 'made_levels': ['101'], 'documents': 0,
         'research': {'accepted': False, 'discards': {'tries': 1, 'seconds': 1260, 'dollars': 4.47}}}
DRAFT = {'id': 'a' * 32, 'revision': 'b' * 32, 'external': False, 'restricted': False,
         'sites': [], 'workers': 3, 'focus': '', 'formats': ['.txt'],
         'sources': [{'id': 'c' * 32, 'name': 'Reference notes', 'kind': 'text',
                      'origin': 'Reference notes', 'status': 'ready', 'warnings': [],
                      'problem': None, 'tabs': [], 'selected_tabs': []}]}
PREVIEW = {'changed': ['sources'], 'names': ['the sources'], 'research': 'replanned',
           'discards': {'tries': 1, 'seconds': 1260, 'dollars': 4.47}, 'confirm': True,
           'words': ['You changed the sources.', 'Research that has not been accepted into a '
                     'finished report is discarded, and research is planned again with the new '
                     'settings. The discarded tries took 21 minutes and $4.47. This cannot be '
                     'undone.', 'Nothing starts until you press Continue.']}


@unittest.skipUnless(NODE, 'Node is needed to run the page scripts without a browser')
class SheetTests(ScriptedPage, DeskPageCase):
    """The Change settings sheet, run in the page harness: opened from the stop's card,
    reviewed, saved, or put away with nothing sent."""

    answers = test_desk.TrainingDeskScreenTests.answers
    posts = test_desk.TrainingDeskScreenTests.posts
    started = test_desk.TrainingDeskScreenTests.started
    listed = test_desk.TrainingDeskScreenTests.listed
    detail = test_desk.TrainingDeskScreenTests.detail
    on_desk = test_desk.TrainingDeskScreenTests.on_desk
    open_desk = test_desk.TrainingDeskScreenTests.open_desk

    def stopped(self, **more) -> dict:
        run = a_desk_run('failed', 'Research stopped.')
        run['body'].update(problem={'what': 'Research did not finish.', 'kept': 'Saved work is kept.',
                                    'action': 'retry', 'label': 'Try again'},
                           settings={'may': True, 'why': None})
        waiting = a_desk_run('waiting', 'Its settings were changed.')
        waiting['body'].update(problem={'what': 'Its settings were changed. Nothing starts until '
                                        'you press Continue.', 'kept': 'Everything else is kept.',
                                        'action': 'retry', 'label': 'Continue', 'settings': True},
                               settings={'may': True, 'why': None})
        return self.on_desk(a_desk(running=False), run, **{
            'GET /api/training-settings': [ok({**SHOWN, 'path': str(self.root)})],
            'POST /api/training-settings/sources': [ok(DRAFT)],
            'POST /api/research-sources': [ok({**DRAFT, 'external': True, 'revision': 'd' * 32})],
            'POST /api/training-settings': [ok(PREVIEW), ok(waiting['body'])], **more})

    def test_a_stop_opens_its_saved_settings_and_saves_after_review(self):
        result = self.open_desk(self.stopped(), [
            {'snapshot': 'stopped'},
            {'click': 'Change settings'}, {'snapshot': 'form'},
            {'fill': 'What should the research answer? (optional)', 'value': 'Why?\nHow?\nWhen?'},
            {'click': 'Review the change'}, {'snapshot': 'review'},
            {'click': 'Discard and save'}, {'snapshot': 'saved'}])
        shots = result['snapshots']
        self.assertIn('Change settings', shots['stopped']['buttons'])
        self.assertIn('Try again', shots['stopped']['buttons'])
        form = shots['form']['text']
        # The shared source panel is checked in a real browser and by its own tests: the
        # harness names only controls labelled by id.
        for said in ('1. What it teaches', '2. What is made', '3. Research',
                     'A level with work in it stays: 101.', 'Research from your documents.'):
            self.assertIn(said, form)
        self.assertIn('$4.47', shots['review']['text'])
        self.assertIn('cannot be undone', shots['review']['text'])
        posted = [body for address, body in self.posts(result) if address == '/api/training-settings']
        self.assertEqual(len(posted), 2)
        self.assertTrue(posted[0]['preview'])
        self.assertTrue(posted[1]['confirmed'])
        self.assertEqual(posted[1]['expected'], 'r1')
        self.assertEqual(posted[1]['research_questions'], ['Why?', 'How?', 'When?'])
        self.assertEqual(posted[1]['topic'], 'Rolling restarts on the platform')
        self.assertNotIn('research_inputs', posted[1], 'Without the panel the sources stay as they are')
        self.assertIn('Nothing starts until you press Continue.', shots['saved']['text'])
        self.assertNotIn('Discard and save', shots['saved']['buttons'], 'The sheet is put away')

    def test_sources_that_cannot_be_opened_leave_the_rest_of_the_form(self):
        answers = self.stopped(**{'POST /api/training-settings/sources': [
            {'status': 409, 'body': {'error': 'The sources this training reads could not be read.'}}]})
        result = self.open_desk(answers, [{'click': 'Change settings'}, {'snapshot': 'form'},
                                          {'click': 'Review the change'}], research=True)
        form = result['snapshots']['form']['text']
        self.assertIn('The sources this training reads could not be read. What research reads '
                      'stays as it is.', form)
        self.assertIn('1. What it teaches', form)
        posted = [body for address, body in self.posts(result) if address == '/api/training-settings']
        self.assertNotIn('research_inputs', posted[0])

    def test_cancel_sends_no_change(self):
        result = self.open_desk(self.stopped(), [
            {'click': 'Change settings'},
            {'fill': 'What should it teach?', 'value': 'Something else'},
            {'click': 'Cancel'}, {'snapshot': 'put away'}])
        self.assertEqual([address for address, _ in self.posts(result)
                          if address == '/api/training-settings'], [])
        self.assertNotIn('Review the change', result['snapshots']['put away']['buttons'])


RUNTIME = os.environ.get('STUDIO_TEST_RESEARCH_RUNTIME')


@unittest.skipUnless(RUNTIME, 'Set STUDIO_TEST_RESEARCH_RUNTIME for pinned helper tests.')
class ParallelChangeTests(SettingsCase):
    """The person's shape on the real pinned Harness Research collection: research from the
    documents alone stopped, then documents and web search with three questions, then
    Continue. Scripted workers only; nothing reaches a provider or the network."""

    def setUp(self):
        super().setUp()
        from runner import research
        from runner_support import URL
        from synthesis_fixture import TEXT
        self.engine.parallel_research = True
        self.research = research.Research(Path(RUNTIME))
        self.web.page(URL, TEXT, 'text/plain')
        self.barrier, self.supplied_only, self.phases, self.caps = None, True, [], []
        self.fetched = []
        self.workers.queued['research-result'] = [fails(cost=1.0), *([self.investigate] * 12)]

    def investigate(self, tools, job):
        if 'questions' in json.loads(tools.read_input('research-task')[1]):
            self.fetched.append(tools.job['fetch'])
        self.supplied = True   # the borrowed worker reads the supplied capture
        return test_parallel_research.ParallelNativeTests.worker(self, tools, job)

    @staticmethod
    def kept(folder: Path) -> dict:
        return {str(path.relative_to(folder)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(folder.rglob('*')) if path.is_file()}

    def test_a_supplied_only_stop_researches_again_in_a_new_collection(self):
        from synthesis_fixture import TEXT
        store = research_sources.Sources(self.space.root / '.research-sources')
        draft = store.create()
        draft = store.mutate(draft['id'], draft['revision'], 'capture', kind='text',
                             name='Synthetic deck', text=TEXT)
        started = self.engine.start(pipeline.check_form({**FORM, 'flow': 'desk'}),
                                    research_inputs={'id': draft['id'], 'expected': draft['revision']})
        root = Path(started['path'])
        self.assertEqual(self.view(root)['state'], 'failed', self.view(root)['problem'])
        self.assertTrue(research_session.protocol(self.record(root)))
        case = root / '.studio-research'
        before = [folder for folder in case.iterdir() if folder.is_dir()]
        self.assertEqual(len(before), 1)
        old = self.kept(before[0])
        shown = self.form(root)
        sent = self.sent(shown, research_questions=QUESTIONS, research_inputs=self.external(root))
        said = self.engine.change_settings(root, sent, preview=True)
        self.assertEqual(said['research'], 'replanned')
        self.assertEqual(said['discards']['dollars'], 1.0)
        self.engine.change_settings(root, {**sent, 'confirmed': True})
        self.fetched.clear()
        self.workers.plan = THREE
        self.engine.act(root, 'retry')
        self.assertEqual(workspace.statuses(root, workspace.load(root))['research'], 'approved',
                         self.view(root)['problem'])
        after = [folder for folder in case.iterdir() if folder.is_dir()]
        self.assertEqual(len(after), 2, 'A new collection, beside the earlier one')
        self.assertEqual(self.kept(before[0]), old, 'The earlier collection is left as it was')
        current = json.loads((case / 'current.json').read_text())['basis']
        self.assertNotEqual(current, before[0].name)
        self.assertTrue(self.fetched and all(self.fetched), 'Investigators may fetch pages now')
        facts, _ = contract.read_bundle(root / 'research')
        self.assertTrue(facts['review']['accepted'])
