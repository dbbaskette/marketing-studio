"""Every stop the saved gated flow leaves on disk, in its original format, against the
explicit migration (#519). Each training here is made by the saved flow itself, with
scripted workers, and stopped where a person would find it. For each stop the preview is
pure (nothing in the workspace changes), and it either opens the work on the desk with
every original byte, pin and approval kept and none invented, or refuses with the reason
the person is shown and leaves the saved flow as it was.
"""
import json
import shutil

import helpers
from runner_support import StudioCase, asks, fails
import home
import workspace
from runner import desk_chat, gitstate, page

SESSION = '.training-studio/session.json'
RUN = '.training-studio/run.json'
EARLY = 'No usable teaching plan or supported deck outline is saved yet. Continue with the saved flow first.'
FAILED = 'Resolve the saved failure or question in its saved flow before opening it on the desk.'
FINISHED = 'Use the existing finished Open on the desk action.'
EVERY = ['document', 'brief', 'scenario']


class SavedStopTests(StudioCase):
    def snapshot(self, root):
        return {path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob('*') if path.is_file()}

    def workspace_state(self, root):
        marker = (self.space.root / gitstate.MARKER).read_bytes()
        return self.snapshot(root), marker, self.git('ls-files', '--stage', '-z'), self.git('rev-parse', 'HEAD')

    def preview(self, root):
        """The preview, checked to change nothing at all."""
        before = self.workspace_state(root)
        jobs = len(self.workers.jobs)
        shown = desk_chat.migration_preview(self.engine, root)
        self.assertEqual(self.workspace_state(root), before)
        self.assertEqual(len(self.workers.jobs), jobs)
        return shown

    def stopped_at(self, gate, **form):
        """A saved training run by the saved flow until `gate` waits for the person."""
        root = self.saved_start(title='Stop ' + gate.replace(':', ' '), **form)
        self.to_gate(root, gate)
        self.assertEqual(self.view(root)['state'], 'waiting')
        self.assertIsNone(self.view(root)['flow'])
        return root

    def assert_refused(self, root, reason):
        shown = self.preview(root)
        self.assertIn(reason, shown['blockers'])
        self.assertEqual(shown['writes'], [])
        self.assertTrue(self.view(root)['can_migrate_desk'] or self.view(root)['state'] == 'done')
        return shown

    def assert_migrates(self, root, targets):
        """Apply the previewed migration and check nothing saved is lost or invented."""
        shown = self.preview(root)
        self.assertEqual(shown['blockers'], [])
        self.assertEqual(shown['targets'], targets)
        before = self.snapshot(root)
        session = workspace.load(root)
        statuses = workspace.person_statuses(root, session)
        jobs = len(self.workers.jobs)
        desk_chat.migrate(self.engine, root, shown['expected'])
        after = self.snapshot(root)
        for name, data in before.items():
            self.assertEqual(after.get(name), data, name)
        effective = workspace.load(root)
        self.assertEqual(effective['flow'], 'desk')
        self.assertEqual(effective['artifacts'], session['artifacts'])
        self.assertEqual(effective.get('pins'), session.get('pins'))
        now = workspace.person_statuses(root, effective)
        # No approval is invented: nothing becomes approved that was not.
        self.assertEqual({name for name, status in now.items() if status == 'approved'},
                         {name for name, status in statuses.items() if status == 'approved'})
        self.assertEqual(len(self.workers.jobs), jobs)
        self.assertEqual(self.engine.view(root)['flow'], 'desk')
        return shown


class EarlyStopTests(SavedStopTests):
    def test_research_plan_gate_keeps_its_saved_flow(self):
        self.assert_refused(self.stopped_at('research-plan'), EARLY)

    def test_research_gate_keeps_its_saved_flow(self):
        self.assert_refused(self.stopped_at('research'), EARLY)

    def test_worker_question_before_a_plan_keeps_its_saved_flow(self):
        self.workers.then('research-plan', asks('Which platform is this about?'))
        root = self.saved_start(title='Asked early')
        self.assertTrue(self.view(root)['question'])
        self.assert_refused(root, FAILED)

    def test_failure_before_a_plan_keeps_its_saved_flow(self):
        self.workers.then('research-plan', fails(), fails(), fails())
        root = self.saved_start(title='Failed early')
        self.assertEqual(self.view(root)['state'], 'failed')
        self.assert_refused(root, FAILED)


class MaterialStopTests(SavedStopTests):
    def test_blueprint_gate_migrates_with_its_plan(self):
        self.assert_migrates(self.stopped_at('blueprint', materials=EVERY), ['blueprint'])

    def test_document_gate_migrates_with_the_plan_and_the_guide(self):
        self.assert_migrates(self.stopped_at('document', materials=EVERY), ['blueprint', 'document'])

    def test_brief_gate_migrates_with_every_material_made(self):
        self.assert_migrates(self.stopped_at('brief', materials=EVERY), ['blueprint', 'document', 'brief'])

    def test_scenario_gate_migrates_with_every_material_made(self):
        self.assert_migrates(self.stopped_at('scenario:main', materials=EVERY),
                             ['blueprint', 'document', 'brief', 'scenario:main'])

    def test_failure_after_the_plan_keeps_its_saved_flow(self):
        self.workers.then('document', fails(), fails(), fails())
        root = self.stopped_at('blueprint', materials=EVERY)
        self.decide(root, 'blueprint')
        self.assertEqual(self.view(root)['state'], 'failed')
        self.assert_refused(root, FAILED)

    def test_paused_after_the_plan_migrates_and_keeps_the_pause_in_history(self):
        root = self.stopped_at('blueprint', materials=EVERY)
        record = self.record(root)
        record['halt'] = 'paused'
        (root / RUN).write_text(json.dumps(record))
        gitstate.commit(self.space, 'a saved pause', [root])
        self.assert_migrates(root, ['blueprint'])
        self.assertEqual(self.engine._load(root)['migration_saved_status']['halt'], 'paused')

    def test_review_layout_1_run_migrates_with_its_record_unchanged(self):
        root = self.stopped_at('blueprint', materials=EVERY)
        record = self.record(root)
        record.pop('review_layout', None)
        (root / RUN).write_text(json.dumps(record))
        gitstate.commit(self.space, 'a layout 1 record', [root])
        self.assert_migrates(root, ['blueprint'])
        self.assertNotIn('review_layout', json.loads((root / RUN).read_text()))

    def test_finished_training_keeps_the_finished_open_on_the_desk_action(self):
        root = self.saved_start(title='Finished saved', materials=['document'])
        self.to_end(root)
        self.assertEqual(self.view(root)['state'], 'done')
        self.assertFalse(self.view(root)['can_migrate_desk'])
        self.assertTrue(self.view(root)['can_open_desk'])
        self.assert_refused(root, FINISHED)


class UnreadableStopTests(SavedStopTests):
    def test_unreadable_session_keeps_every_file_and_is_refused(self):
        root = self.stopped_at('blueprint', materials=EVERY)
        (root / SESSION).write_text('{not a saved session')
        shown = self.preview(root)
        self.assertTrue(shown['blockers'])
        self.assertEqual(shown['writes'], [])

    def test_unreadable_run_record_keeps_every_file_and_is_refused(self):
        root = self.stopped_at('blueprint', materials=EVERY)
        (root / RUN).write_text('{not a run record')
        shown = self.preview(root)
        self.assertTrue(shown['blockers'])
        self.assertEqual(shown['writes'], [])

    def test_unreadable_record_says_why_and_its_files_stay_readable(self):
        root = self.stopped_at('blueprint', materials=EVERY)
        (root / RUN).write_text('{not a run record')
        before = self.snapshot(root)
        native = page.RunnerPage(8765, self.engine)
        with self.assertRaisesRegex(workspace.WorkspaceError, 'Expecting property name'):
            native.detail(str(root))
        status, _, body = native.read('/api/file', lambda key: {'path': str(root), 'artifact': 'blueprint'}.get(key))
        self.assertEqual(status, 200, body)
        self.assertIn('Rolling restarts', json.loads(body)['text'])
        self.assertEqual(self.snapshot(root), before)


class ConversationTrainingTests(SavedStopTests):
    def conversation(self, title='Conversation saved'):
        """A training a conversation kept outside the workspace, at its blueprint gate."""
        from runner_support import BLUEPRINT, FORM
        from runner import pipeline
        top = self.base / 'conversation' / workspace.slugify(title)
        top.mkdir(parents=True)
        form = pipeline.check_form({**FORM, 'title': title, 'levels': [], 'deck_target': None})
        workspace.init(top, title, approval='chat')
        (top / 'intake.md').write_text(pipeline.intake_text(form))
        workspace.save(top, 'intake', built=True)
        workspace.approve(top, 'intake', by='chat')
        (top / '.training-studio/research-plan.json').write_text(json.dumps({'topic': 'Synthetic', 'items': []}))
        workspace.save(top, 'research-plan', built=True)
        workspace.approve(top, 'research-plan', by='chat')
        research = top / '.harness-research'
        research.mkdir()
        (research / 'research.json').write_text(json.dumps(helpers.RESEARCH))
        (research / 'research-report.md').write_text('# Research\n\nSynthetic findings.\n')
        workspace.save(top, 'research', built=True)
        workspace.approve(top, 'research', by='chat')
        (top / 'blueprint.md').write_text(BLUEPRINT)
        workspace.save(top, 'blueprint', built=True)
        workspace.checkpoint(top, stage='blueprint', gate='blueprint')
        home.remember(top, title, [])
        return top

    def test_outside_the_workspace_is_refused_until_brought_in(self):
        top = self.conversation()
        before = self.snapshot(top)
        shown = self.preview_outside(top)
        self.assertEqual(shown['blockers'], ['There is no saved training there.'])
        self.assertEqual(self.snapshot(top), before)

    def preview_outside(self, top):
        jobs = len(self.workers.jobs)
        shown = desk_chat.migration_preview(self.engine, top)
        self.assertEqual(len(self.workers.jobs), jobs)
        return shown

    def test_brought_in_it_is_a_saved_run_that_migrates(self):
        top = self.conversation('Brought saved')
        before = self.snapshot(top)
        brought = self.engine.bring(top)
        self.assertEqual(self.snapshot(top), before)
        root = self.engine.driven(brought['path'])
        self.assertIsNone(self.view(root)['flow'])
        self.assert_migrates(root, ['blueprint'])
        shutil.rmtree(top)


from runner import pipeline  # noqa: E402
from test_runner_deck import DeckCase  # noqa: E402


class DeckStopTests(DeckCase):
    snapshot = SavedStopTests.snapshot
    workspace_state = SavedStopTests.workspace_state
    preview = SavedStopTests.preview
    assert_refused = SavedStopTests.assert_refused
    assert_migrates = SavedStopTests.assert_migrates

    MADE = ['blueprint', 'document', 'brief']

    def migrated_deck_record(self, root, before):
        """The deck's saved run entry is kept as it was: nothing of it is approved or
        delivered by the migration."""
        record = self.engine._load(root)
        self.assertEqual(record['deck'], before['deck'])
        self.assertEqual(record['execution'], 'conversation')

    def test_what_the_deck_says_waiting_migrates_with_the_outline_kept_undecided(self):
        root = self.saved_begin(title='Deck outline waits')
        self.to_outline(root)
        self.assertIsNone(self.view(root)['flow'])
        before = self.record(root)
        shown = self.assert_migrates(root, self.MADE)
        self.assertIn(pipeline.OUTLINE, shown['required'])
        self.migrated_deck_record(root, before)

    def test_deck_look_waiting_migrates_with_no_look_chosen(self):
        self.brand.offers_looks = True
        root = self.saved_begin(title='Deck look waits')
        self.drawn(root)
        self.assertTrue(self.view(root)['look']['waiting'])
        before = self.record(root)
        self.assert_migrates(root, self.MADE)
        self.migrated_deck_record(root, before)

    def test_deck_gate_migrates_with_the_saved_deck(self):
        root = self.saved_begin(title='Deck gate waits')
        self.drawn(root)
        self.to_gate(root, 'deck')
        before = self.record(root)
        self.assert_migrates(root, [*self.MADE, 'deck'])
        self.migrated_deck_record(root, before)

    def test_deck_outline_without_its_plan_keeps_its_saved_flow(self):
        root = self.saved_begin(title='Deck outline alone')
        self.to_outline(root)
        (root / 'blueprint.md').unlink()
        self.assert_refused(root, 'blueprint.md is required to interpret the saved deck outline. Restore it first.')

    def test_unreadable_deck_outline_keeps_its_saved_flow(self):
        root = self.saved_begin(title='Deck outline unreadable')
        self.to_outline(root)
        outline = json.loads((root / pipeline.OUTLINE).read_text())
        outline['slides'][0]['title'] = 7
        (root / pipeline.OUTLINE).write_text(json.dumps(outline))
        self.assert_refused(root, 'The shared saved deck outline cannot be read losslessly.')
