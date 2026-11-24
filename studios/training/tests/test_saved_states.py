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
from runner import desk_chat, desk_migration, engine as engines, gitstate, page

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
        self.assertEqual(shown['outcome'], {'outcome': 'migrates'})
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

    def test_failure_after_the_plan_migrates_and_keeps_the_failure_in_history(self):
        self.workers.then('document', fails(), fails(), fails())
        root = self.stopped_at('blueprint', materials=EVERY)
        self.decide(root, 'blueprint')
        self.assertEqual(self.view(root)['state'], 'failed')
        before = self.record(root)
        shown = self.assert_migrates(root, ['blueprint'])
        self.assertIn(desk_migration.KEPT_FAILURE, shown['retained'])
        self.assert_kept_in_history(root, before, 'problem', 'document')

    def test_worker_question_after_the_plan_migrates_and_keeps_the_question_in_history(self):
        self.workers.then('document', asks('Which platform is this about?'))
        root = self.stopped_at('blueprint', materials=EVERY)
        self.decide(root, 'blueprint')
        self.assertTrue(self.view(root)['question'])
        before = self.record(root)
        shown = self.assert_migrates(root, ['blueprint'])
        self.assertIn(desk_migration.KEPT_QUESTION, shown['retained'])
        self.assert_kept_in_history(root, before, 'question', 'document')

    def assert_kept_in_history(self, root, before, key, step):
        """The failure or question is History: the original run record keeps it, the desk
        carries it only as saved status, its step stays unfinished, and nothing is retried."""
        self.assertEqual(json.loads((root / RUN).read_bytes())[key], before[key])
        effective = self.engine._load(root)
        self.assertIsNone(effective[key])
        self.assertEqual(effective['migration_saved_status'][key], before[key])
        self.assertEqual(effective['steps'], before['steps'])
        self.assertFalse((effective['steps'].get(step) or {}).get('done'))
        self.assertNotIn('document', workspace.load(root)['artifacts'])
        shown = self.engine.view(root)
        self.assertIsNone(shown['problem'])
        self.assertIsNone(shown['question'])

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
        """The record the runner refuses opens as a read-only record: it is named, says
        why, lists its saved files readable in place, and changes nothing."""
        root = self.stopped_at('blueprint', materials=EVERY)
        (root / RUN).write_text('{not a run record')
        before, jobs = self.workspace_state(root), len(self.workers.jobs)
        native = page.RunnerPage(8765, self.engine)
        detail = native.detail(str(root))
        self.assertEqual(detail['run'], {'state': 'saved', 'sentence': engines.SAVED_BRIEF,
                                         'read_only': True})
        self.assertEqual(native.with_run({'path': str(root)})['run']['read_only'], True)
        shown = self.engine.view(root)
        self.assertEqual(shown['title'], 'Stop blueprint')
        self.assertEqual(shown['sentence'], engines.SAVED_RECORD)
        self.assertEqual(shown['saved_record']['why'], desk_migration.UNREADABLE)
        self.assertIn('Expecting property name', shown['saved_record']['refusal'])
        self.assertEqual(shown['saved_record']['next'], 'new')
        self.assertFalse(shown['can_migrate_desk'] or shown['can_open_desk'])
        self.assertEqual(shown['saved_record']['files'],
                         ['intake.md', 'research-report.md', 'blueprint.md'])
        status, _, body = native.read('/api/saved-file', lambda key: {'path': str(root), 'name': 'blueprint.md'}[key])
        self.assertEqual(status, 200, body)
        self.assertIn('Rolling restarts', json.loads(body)['text'])
        status, _, body = native.read('/api/file', lambda key: {'path': str(root), 'artifact': 'blueprint'}.get(key))
        self.assertEqual(status, 200, body)
        self.assertIn('Rolling restarts', json.loads(body)['text'])
        for name in (RUN, 'reviews/blueprint.md', '../outside.md'):
            with self.assertRaises(page.desk.Refusal):
                native.read('/api/saved-file', lambda key: {'path': str(root), 'name': name}[key])
        self.assertEqual(self.workspace_state(root), before)
        self.assertEqual(len(self.workers.jobs), jobs)


class ClassificationTests(SavedStopTests):
    """`desk_migration.classify`, for every saved stop: migrates, or a read-only record with
    its reason and its next action. Asking only reads. In phase A the page shows a read-only
    record only where the runner already refuses the records; the rest keep their screen."""

    def outcome(self, root):
        before = self.workspace_state(root)
        found = desk_migration.outcome(self.engine, root)
        self.assertEqual(self.workspace_state(root), before)
        return found

    def assert_class(self, root, outcome, reason=None, next_action=None):
        found = self.outcome(root)
        self.assertEqual(found['outcome'], outcome, found)
        if outcome == 'read-only':
            self.assertEqual((found['reason'], found['next']), (reason, next_action))
        # The preview carries the same classification beside its blockers, and its refusal
        # is the classification's own sentence.
        shown = self.preview(root)
        self.assertEqual(shown['outcome'], {key: found[key] for key in
                                            ('outcome', 'reason', 'next') if key in found})
        if outcome == 'migrates':
            self.assertEqual(shown['blockers'], [])
        else:
            self.assertIn(found['said'], shown['blockers'])
        return found

    def test_stops_before_a_plan_are_read_only_records(self):
        self.assert_class(self.stopped_at('research-plan'), 'read-only',
                          desk_migration.NOTHING_MADE, 'copy')
        self.assert_class(self.stopped_at('research'), 'read-only',
                          desk_migration.NOTHING_MADE, 'copy')
        self.workers.then('research-plan', asks('Which platform is this about?'))
        asked = self.saved_start(title='Asked early')
        self.assertEqual(self.assert_class(asked, 'read-only', desk_migration.NOTHING_MADE,
                                           'copy')['said'], FAILED)

    def test_failure_before_a_plan_is_a_read_only_record(self):
        self.workers.then('research-plan', fails(), fails(), fails())
        root = self.saved_start(title='Failed early')
        self.assert_class(root, 'read-only', desk_migration.NOTHING_MADE, 'copy')

    def test_stops_with_material_migrate(self):
        self.assert_class(self.stopped_at('blueprint', materials=EVERY), 'migrates')
        self.assert_class(self.stopped_at('scenario:main', materials=EVERY), 'migrates')
        self.workers.then('document', fails(), fails(), fails())
        failed = self.saved_start(title='Failed later', materials=['document'])
        self.to_gate(failed, 'blueprint')
        self.decide(failed, 'blueprint')
        self.assert_class(failed, 'migrates')

    def test_finished_work_keeps_its_own_open_on_the_desk(self):
        root = self.saved_start(title='Finished saved', materials=['document'])
        self.to_end(root)
        self.assert_class(root, 'finished')

    def test_records_and_dependencies_that_cannot_be_read_are_read_only(self):
        root = self.stopped_at('blueprint', materials=EVERY)
        original = {name: (root / name).read_bytes() for name in (RUN, SESSION)}
        record = json.loads(original[RUN])
        for change, next_action in (({'halt': 'unknown'}, 'copy'), ({'schema': 99}, 'copy'),
                                    ({'drafts': {'update_chain': {'status': 'unknown'}}}, 'copy')):
            with self.subTest(change=change):
                (root / RUN).write_text(json.dumps({**record, **change}))
                self.assert_class(root, 'read-only', desk_migration.UNREADABLE, next_action)
        (root / RUN).write_text('{not a run record')
        self.assert_class(root, 'read-only', desk_migration.UNREADABLE, 'new')
        (root / RUN).write_bytes(original[RUN])
        (root / SESSION).write_text('{not a saved session')
        self.assert_class(root, 'read-only', desk_migration.UNREADABLE, 'new')
        (root / SESSION).write_bytes(original[SESSION])
        research = root / '.harness-research/research.json'
        kept = research.read_bytes()
        research.unlink()
        found = self.assert_class(root, 'read-only', desk_migration.MISSING + ' '
                                  + 'The saved research bundle or its approved copy is missing.', 'copy')
        self.assertEqual(found['said'], 'The saved research bundle or its approved copy is missing.')
        research.write_bytes(kept)
        self.assert_class(root, 'migrates')

    def test_a_worker_in_hand_still_migrates_once_it_is_done(self):
        from runner import engine as engines_module
        root = self.stopped_at('blueprint', materials=EVERY)
        (root / engines_module.IN_HAND).write_text('blueprint')
        self.assertEqual(self.outcome(root)['outcome'], 'migrates')
        self.assertTrue(self.preview(root)['blockers'])

    def test_desk_work_and_an_opening_s_recovery_are_not_saved_flow_work(self):
        root = self.stopped_at('blueprint', materials=EVERY)
        shown = self.preview(root)
        desk_chat.migrate(self.engine, root, shown['expected'])
        self.assertEqual(self.outcome(root)['outcome'], 'desk')
        self.assertEqual(self.outcome(self.start(title='Desk work'))['outcome'], 'desk')


class ReadOnlyRecordTests(SavedStopTests):
    """The read-only record serves only records the runner already refuses to read."""

    def test_a_record_the_runner_reads_keeps_its_own_screen(self):
        root = self.stopped_at('research-plan')
        self.assertEqual(desk_migration.outcome(self.engine, root)['outcome'], 'read-only')
        shown = self.engine.view(root)
        self.assertNotIn('saved_record', shown)
        self.assertTrue(shown['can_migrate_desk'])
        self.assertIsNone(self.engine.saved_record(root))
        native = page.RunnerPage(8765, self.engine)
        with self.assertRaises(page.desk.Refusal):
            native.read('/api/saved-file', lambda key: {'path': str(root), 'name': 'intake.md'}[key])

    def test_an_unsupported_record_starts_new_work_from_its_start_form(self):
        root = self.stopped_at('blueprint', materials=EVERY)
        record = self.record(root)
        record['schema'] = 99
        (root / RUN).write_text(json.dumps(record))
        before = self.workspace_state(root)
        shown = self.engine.view(root)
        self.assertEqual(shown['saved_record']['next'], 'copy')
        copied = self.engine.copy_setup(root)
        self.assertEqual(copied['title'], 'Stop blueprint copy')
        self.assertEqual(copied['values']['materials'], EVERY)
        self.assertEqual(copied['values']['research_questions'], record['research_questions'])
        self.assertEqual(self.workspace_state(root), before)

    def test_a_record_whose_start_form_cannot_be_read_starts_a_new_training(self):
        from runner import copy_setup
        root = self.stopped_at('blueprint', materials=EVERY)
        (root / SESSION).write_text('{not a saved session')
        before = self.workspace_state(root)
        shown = self.engine.view(root)
        self.assertEqual(shown['saved_record']['next'], 'new')
        self.assertEqual(shown['title'], root.name)
        with self.assertRaisesRegex(workspace.WorkspaceError, copy_setup.UNREAD_FORM):
            self.engine.copy_setup(root)
        self.assertEqual(self.workspace_state(root), before)

    def test_a_linked_file_is_never_listed_or_read(self):
        root = self.stopped_at('blueprint', materials=EVERY)
        (root / RUN).write_text('{not a run record')
        outside = self.base / 'outside.md'
        outside.write_text('Not the training’s own file.')
        (root / 'document.md').symlink_to(outside)
        shown = self.engine.view(root)
        self.assertNotIn('document.md', shown['saved_record']['files'])
        native = page.RunnerPage(8765, self.engine)
        with self.assertRaises(page.desk.Refusal):
            native.read('/api/saved-file', lambda key: {'path': str(root), 'name': 'document.md'}[key])


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
        self.assertEqual(shown['outcome'], {'outcome': 'bring', 'reason': desk_migration.BRING})
        self.assertEqual(desk_migration.outcome(self.engine, top)['outcome'], 'bring')
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
        said = 'blueprint.md is required to interpret the saved deck outline. Restore it first.'
        shown = self.assert_refused(root, said)
        self.assertEqual(shown['outcome'], {'outcome': 'read-only', 'next': 'copy',
                                            'reason': desk_migration.MISSING + ' ' + said})

    def test_unreadable_deck_outline_keeps_its_saved_flow(self):
        root = self.saved_begin(title='Deck outline unreadable')
        self.to_outline(root)
        outline = json.loads((root / pipeline.OUTLINE).read_text())
        outline['slides'][0]['title'] = 7
        (root / pipeline.OUTLINE).write_text(json.dumps(outline))
        said = 'The shared saved deck outline cannot be read losslessly.'
        shown = self.assert_refused(root, said)
        self.assertEqual(shown['outcome'], {'outcome': 'read-only', 'next': 'copy',
                                            'reason': desk_migration.MISSING + ' ' + said})


import unittest  # noqa: E402
from test_desk import NODE, ScriptedPage, ok, SET_UP, RUNNER, AGENTS_FOUND, MODELS  # noqa: E402
from test_runner_page import PageCase  # noqa: E402


@unittest.skipUnless(NODE, 'Node is needed to run the page scripts without a browser')
class ReadOnlyPageTests(ScriptedPage, PageCase):
    """The read-only record screen: its title, a Read-only bead with words, why, its saved
    files read in place, and one filled action. Nothing on it continues the training or
    opens it on the desk, and opening it sends nothing."""

    def fixture(self, title, damage):
        root = self.saved_start(title=title, materials=EVERY)
        self.to_gate(root, 'blueprint')
        damage(root)
        self.root = root   # the page plan is written beside it
        path = str(root)
        return dict(path=path, run=self.get('run', path=path), detail=self.get('training', path=path),
                    listing=self.get('trainings'),
                    file=self.get('saved-file', path=path, name='blueprint.md'))

    def answers(self, fixture):
        return {'GET /api/capabilities': [RUNNER], 'GET /api/setup': [ok(SET_UP)],
                'GET /api/trainings': [ok(fixture['listing'])],
                'GET /api/training': [ok(fixture['detail'])],
                'GET /api/run': [ok(fixture['run'])],
                'GET /api/computer': [ok({'items': []})],
                'GET /api/agents': [ok(AGENTS_FOUND)], **MODELS,
                'GET /api/saved-file': [ok(fixture['file'])]}

    def test_desktop_and_phone_read_the_record_and_offer_one_way_on(self):
        unreadable = lambda root: (root / RUN).write_text('{not a run record')  # noqa: E731
        unsupported = lambda root: (root / RUN).write_text(  # noqa: E731
            json.dumps({**self.record(root), 'schema': 99}))
        for title, damage, action in (('Unreadable record', unreadable, 'Start a new training'),
                                      ('Unsupported record', unsupported, 'Start new work from this')):
            fixture = self.fixture(title, damage)
            listed = next(item for item in fixture['listing']['trainings']
                          if item['path'] == fixture['path'])
            self.assertEqual(listed['run']['read_only'], True)
            for narrow in (False, True):
                with self.subTest(action=action, narrow=narrow):
                    result = self.run_page(self.answers(fixture), [
                        {'snapshot': 'record'}, {'click': 'Read teaching plan'},
                        {'snapshot': 'read'}], state={'screen': 'run', 'path': fixture['path']},
                        narrow=narrow)
                    shot = result['snapshots']['record']
                    self.assertEqual(shot['heading'], title)
                    self.assertEqual(shot['filled'], [action])
                    self.assertIn('Read-only: it is not continued and not opened on the desk',
                                  shot['text'])
                    self.assertIn(desk_migration.UNREADABLE, shot['text'])
                    self.assertIn('Why it cannot be continued', shot['text'])
                    for word in ('Continue', 'Open on the desk', 'Try again', 'Answer'):
                        self.assertNotIn(word, shot['buttons'])
                    self.assertEqual([name for name in shot['buttons'] if name.startswith('Read ')],
                                     ['Read intake', 'Read research report', 'Read teaching plan'])
                    self.assertIn('Rolling restarts', result['snapshots']['read']['text'])
                    self.assertEqual([r for r in result['requests'] if r['method'] == 'POST'], [])
