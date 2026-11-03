"""Change settings on a stopped Training Studio training (#296), with disposable workspaces,
the scripted agent and the research stand-in: nothing here reaches a provider or the network."""
import json
from pathlib import Path
from unittest import mock

from test_runner_deck import DeckCase, PageCase
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
        self.assertEqual(set(said['changed']), {'research_questions', 'sources'})
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
                                                'questions and the sources'), self.log()[-1])
        record = self.record(root)
        self.assertEqual(record['research_from'], {'documents': True, 'sites': [], 'web': True})
        self.assertEqual(record['documents']['scope'], 'both')
        self.assertEqual(record['research_questions'], QUESTIONS)
        self.assertIsNone(record['research'])
        self.assertFalse((root / pipeline.PLAN).exists(), 'The plan is planned again')
        self.assertIn('The public web and your documents', (root / 'intake.md').read_text())
        self.assertEqual(record['settings_changes'][-1]['research'], 'replanned')
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
        root = self.start(flow='desk', materials=['document', 'brief'], **changes)
        self.to_end(root)
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
        said = self.engine.change_settings(root, self.sent(shown, audience='Platform operators'),
                                           preview=True)
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
        self.assertEqual(made['problem']['label'], 'Continue')
        self.assertEqual(made['changed_settings']['changed'], ['time_limit'])
        refused = self.post('training-settings', sent, expect=409)
        self.assertIn('changed since this form was opened', refused['error'])
