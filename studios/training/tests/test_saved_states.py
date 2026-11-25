"""Every stop the saved gated flow leaves on disk, in its original format, against the
explicit migration and the saved-record screen (#519, #542). Each training here was made by
the saved flow itself, with scripted workers, and stopped where a person would find it; it
is loaded from its stored copy (saved_fixtures.py). The earlier flow no longer continues:
each saved training opens on its saved record, which either opens it on the desk through the
explicit migration (its preview pure, every original byte, pin and approval kept and none
invented), keeps the finished Open on the desk, waits for something that clears, or is
read-only with its reason and a way to start new work from it.
"""
import json
import shutil

import helpers
import saved_fixtures
from runner_support import StudioCase
import home
import workspace
from runner import desk_chat, desk_migration, engine as engines, gitstate, page

SESSION = '.training-studio/session.json'
RUN = '.training-studio/run.json'
EARLY = ('No usable teaching plan or supported deck outline is saved, so there is nothing to '
         'open on the desk.')
FAILED = ('It stopped on a failure or a worker’s question before its teaching plan was '
          'written, so there is nothing to open on the desk.')
FINISHED = 'Use the existing finished Open on the desk action.'
EVERY = ['document', 'brief', 'scenario']
# The stored state for each gate a saved training waits at (made with EVERY material).
GATES = {'research-plan': 'research-plan-gate', 'research': 'research-gate',
         'blueprint': 'blueprint-gate', 'document': 'document-gate', 'brief': 'brief-gate',
         'scenario:main': 'scenario-gate'}


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

    def saved(self, state):
        """A saved training as the saved flow left it (a stored fixture, see
        saved_fixtures.py), in this test's workspace."""
        return saved_fixtures.load(self, state)

    def stopped_at(self, gate):
        """A saved training the saved flow ran until `gate` waits for the person. It opens
        on its saved record, never on a gate."""
        root = self.saved(GATES[gate])
        self.assertEqual(workspace.status(root)['gate'], gate)
        self.assertEqual(self.view(root)['state'], 'saved')
        self.assertIsNone(self.view(root)['flow'])
        return root

    def record_of(self, root):
        """The saved record the page shows: read twice, it says the same and changes nothing."""
        before = self.workspace_state(root)
        shown = self.engine.view(root)
        self.assertEqual(shown['state'], 'saved')
        self.assertEqual(self.engine.view(root), shown)
        self.assertEqual(self.workspace_state(root), before)
        return shown

    def assert_refused(self, root, reason):
        shown = self.preview(root)
        self.assertIn(reason, shown['blockers'])
        self.assertEqual(shown['writes'], [])
        # Its record never offers the explicit opening the preview refuses.
        self.assertFalse(self.record_of(root)['can_migrate_desk'])
        return shown

    def assert_read_only(self, root, reason, next_action):
        shown = self.record_of(root)
        self.assertEqual((shown['saved_record']['outcome'], shown['saved_record']['why'],
                          shown['saved_record']['next']), ('read-only', reason, next_action))
        self.assertFalse(shown['can_migrate_desk'] or shown['can_open_desk'])
        return shown

    def assert_migrates(self, root, targets):
        """Apply the previewed migration and check nothing saved is lost or invented."""
        # Its record offers Open on the desk, and lists what the preview lists.
        record = self.record_of(root)
        self.assertEqual(record['saved_record']['outcome'], 'migrates')
        self.assertTrue(record['can_migrate_desk'])
        self.assertEqual(record['sentence'], engines.SAVED_MIGRATES)
        shown = self.preview(root)
        self.assertEqual(record['saved_record']['retained'], shown['retained'])
        self.assertEqual(record['saved_record']['targets'],
                         [workspace.label(name) for name in shown['targets']])
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
        # No Ready mark and no delivery is invented either: the desk's Ready marks, the
        # exports and Docs made, a delivered Google deck and the finished adoption are as
        # the saved flow left them, and only what a person approved reads as Ready.
        for key in ('desk_ready', 'exports', 'google_docs', 'pending_local_decks'):
            self.assertEqual(effective.get(key), session.get(key), key)
        original, record = json.loads(before[RUN]), self.engine._load(root)
        for key in ('opened_on_desk', 'delivered_restore', 'copies'):
            self.assertEqual(record.get(key), original.get(key), key)
        from runner import drafts
        cards = drafts.view(self.engine, root)['cards']
        self.assertTrue(cards)
        ready = {card['name'] for card in cards if card['state'] == 'ready'}
        self.assertLessEqual(ready, {name for name, status in statuses.items()
                                     if status == 'approved'})
        return shown


class EarlyStopTests(SavedStopTests):
    def test_research_plan_gate_is_a_read_only_record(self):
        root = self.stopped_at('research-plan')
        self.assert_refused(root, EARLY)
        self.assert_read_only(root, desk_migration.NOTHING_MADE, 'copy')

    def test_research_gate_is_a_read_only_record(self):
        root = self.stopped_at('research')
        self.assert_refused(root, EARLY)
        self.assert_read_only(root, desk_migration.NOTHING_MADE, 'copy')

    def test_worker_question_before_a_plan_is_a_read_only_record(self):
        root = self.saved('question-before-plan')
        self.assertTrue(self.record(root)['question'])
        self.assert_refused(root, FAILED)
        self.assert_read_only(root, desk_migration.NOTHING_MADE, 'copy')

    def test_failure_before_a_plan_is_a_read_only_record(self):
        root = self.saved('failure-before-plan')
        self.assertTrue(self.record(root)['problem'])
        self.assert_refused(root, FAILED)
        self.assert_read_only(root, desk_migration.NOTHING_MADE, 'copy')


class MaterialStopTests(SavedStopTests):
    def test_blueprint_gate_migrates_with_its_plan(self):
        self.assert_migrates(self.stopped_at('blueprint'), ['blueprint'])

    def test_document_gate_migrates_with_the_plan_and_the_guide(self):
        self.assert_migrates(self.stopped_at('document'), ['blueprint', 'document'])

    def test_brief_gate_migrates_with_every_material_made(self):
        self.assert_migrates(self.stopped_at('brief'), ['blueprint', 'document', 'brief'])

    def test_scenario_gate_migrates_with_every_material_made(self):
        self.assert_migrates(self.stopped_at('scenario:main'),
                             ['blueprint', 'document', 'brief', 'scenario:main'])

    def test_failure_after_the_plan_migrates_and_keeps_the_failure_in_history(self):
        root = self.saved('failure-after-plan')
        self.assertTrue(self.record(root)['problem'])
        before = self.record(root)
        shown = self.assert_migrates(root, ['blueprint'])
        self.assertIn(desk_migration.KEPT_FAILURE, shown['retained'])
        self.assert_kept_in_history(root, before, 'problem', 'document')

    def test_worker_question_after_the_plan_migrates_and_keeps_the_question_in_history(self):
        root = self.saved('question-after-plan')
        self.assertTrue(self.record(root)['question'])
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
        root = self.stopped_at('blueprint')
        record = self.record(root)
        record['halt'] = 'paused'
        (root / RUN).write_text(json.dumps(record))
        gitstate.commit(self.space, 'a saved pause', [root])
        self.assert_migrates(root, ['blueprint'])
        self.assertEqual(self.engine._load(root)['migration_saved_status']['halt'], 'paused')

    def test_review_layout_1_run_migrates_with_its_record_unchanged(self):
        root = self.stopped_at('blueprint')
        record = self.record(root)
        record.pop('review_layout', None)
        (root / RUN).write_text(json.dumps(record))
        gitstate.commit(self.space, 'a layout 1 record', [root])
        self.assert_migrates(root, ['blueprint'])
        self.assertNotIn('review_layout', json.loads((root / RUN).read_text()))

    def test_finished_training_keeps_the_finished_open_on_the_desk_action(self):
        root = self.saved('finished')
        shown = self.record_of(root)
        self.assertEqual(shown['saved_record']['outcome'], 'finished')
        self.assertEqual(shown['sentence'], engines.SAVED_FINISHED)
        self.assertFalse(shown['can_migrate_desk'])
        self.assertTrue(shown['can_open_desk'])
        self.assert_refused(root, FINISHED)
        # The finished Open on the desk itself is unchanged: it opens it on the desk.
        self.engine.open_on_desk(root)
        self.assertEqual(self.engine.view(root)['flow'], 'desk')


class UnreadableStopTests(SavedStopTests):
    def test_unreadable_session_keeps_every_file_and_is_refused(self):
        root = self.stopped_at('blueprint')
        (root / SESSION).write_text('{not a saved session')
        shown = self.preview(root)
        self.assertTrue(shown['blockers'])
        self.assertEqual(shown['writes'], [])

    def test_unreadable_run_record_keeps_every_file_and_is_refused(self):
        root = self.stopped_at('blueprint')
        (root / RUN).write_text('{not a run record')
        shown = self.preview(root)
        self.assertTrue(shown['blockers'])
        self.assertEqual(shown['writes'], [])

    def test_unreadable_record_says_why_and_its_files_stay_readable(self):
        """The record the runner refuses opens as a read-only record: it is named, says
        why, lists its saved files readable in place, and changes nothing."""
        root = self.stopped_at('blueprint')
        (root / RUN).write_text('{not a run record')
        before, jobs = self.workspace_state(root), len(self.workers.jobs)
        native = page.RunnerPage(8765, self.engine)
        detail = native.detail(str(root))
        self.assertEqual(detail['run'], {'state': 'saved', 'sentence': engines.UNREAD_BRIEF,
                                         'saved': 'unread'})
        self.assertEqual(native.with_run({'path': str(root)})['run']['saved'], 'unread')
        shown = self.engine.view(root)
        self.assertEqual(shown['title'], 'Stop blueprint')
        # Nobody can tell which flow wrote a record that is not even JSON: the record says
        # so neutrally, never that the earlier flow saved it, and offers a new training.
        self.assertEqual(shown['sentence'], engines.UNREAD_RECORD)
        self.assertNotIn('earlier', shown['sentence'])
        self.assertEqual(shown['saved_record']['why'], desk_migration.UNREAD)
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
    its reason and its next action. Asking only reads. The saved record the page shows says
    the same, for every saved training."""

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
        asked = self.saved('question-before-plan')
        self.assertEqual(self.assert_class(asked, 'read-only', desk_migration.NOTHING_MADE,
                                           'copy')['said'], FAILED)

    def test_failure_before_a_plan_is_a_read_only_record(self):
        root = self.saved('failure-before-plan')
        self.assert_class(root, 'read-only', desk_migration.NOTHING_MADE, 'copy')

    def test_stops_with_material_migrate(self):
        self.assert_class(self.stopped_at('blueprint'), 'migrates')
        self.assert_class(self.stopped_at('scenario:main'), 'migrates')
        self.assert_class(self.saved('failure-after-plan'), 'migrates')

    def test_finished_work_keeps_its_own_open_on_the_desk(self):
        self.assert_class(self.saved('finished'), 'finished')

    def test_records_and_dependencies_that_cannot_be_read_are_read_only(self):
        root = self.stopped_at('blueprint')
        original = {name: (root / name).read_bytes() for name in (RUN, SESSION)}
        record = json.loads(original[RUN])
        for change, next_action in (({'halt': 'unknown'}, 'copy'), ({'schema': 99}, 'copy'),
                                    ({'drafts': {'update_chain': {'status': 'unknown'}}}, 'copy')):
            with self.subTest(change=change):
                (root / RUN).write_text(json.dumps({**record, **change}))
                self.assert_class(root, 'read-only', desk_migration.UNREADABLE, next_action)
        for unread in ('{not a run record', '[1, 2]'):
            (root / RUN).write_text(unread)
            self.assert_class(root, 'read-only', desk_migration.UNREAD, 'new')
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
        root = self.stopped_at('blueprint')
        (root / engines_module.IN_HAND).write_text('blueprint')
        self.assertEqual(self.outcome(root)['outcome'], 'migrates')
        self.assertTrue(self.preview(root)['blockers'])
        # Its record says what it waits for and what clears it, and offers new work
        # meanwhile, since nothing on the page clears a marker.
        shown = self.record_of(root)
        self.assertEqual(shown['saved_record']['outcome'], 'waiting')
        self.assertEqual(shown['sentence'], engines.SAVED_WAITING)
        self.assertEqual([(wait['kind'], wait['take']) for wait in shown['saved_record']['waits']],
                         [('busy', False)])
        self.assertEqual(shown['saved_record']['next'], 'copy')
        self.assertFalse(shown['can_migrate_desk'])
        # A leftover marker is cleared by the next start, without the saved flow; it then
        # opens on the desk.
        self.engine._tidy()
        self.assertFalse((root / engines_module.IN_HAND).exists())
        self.assertEqual(self.record_of(root)['saved_record']['outcome'], 'migrates')

    def test_desk_work_and_an_opening_s_recovery_are_not_saved_flow_work(self):
        root = self.stopped_at('blueprint')
        shown = self.preview(root)
        desk_chat.migrate(self.engine, root, shown['expected'])
        self.assertEqual(self.outcome(root)['outcome'], 'desk')
        self.assertEqual(self.outcome(self.start(title='Desk work'))['outcome'], 'desk')


class ReadOnlyRecordTests(SavedStopTests):
    """Every saved training opens on its saved record, whether the runner reads its records
    or not; one the classification calls read-only lists its saved files to read in place."""

    def test_a_record_the_runner_reads_opens_on_its_saved_record_too(self):
        root = self.stopped_at('research-plan')
        self.assertEqual(desk_migration.outcome(self.engine, root)['outcome'], 'read-only')
        shown = self.assert_read_only(root, desk_migration.NOTHING_MADE, 'copy')
        self.assertIsNone(shown['saved_record']['refusal'])
        self.assertEqual(self.engine.saved_record(root), shown)
        native = page.RunnerPage(8765, self.engine)
        status, _, body = native.read('/api/saved-file', lambda key: {'path': str(root), 'name': 'intake.md'}[key])
        self.assertEqual(status, 200, body)

    def test_an_unsupported_record_starts_new_work_from_its_start_form(self):
        root = self.stopped_at('blueprint')
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
        root = self.stopped_at('blueprint')
        (root / SESSION).write_text('{not a saved session')
        before = self.workspace_state(root)
        shown = self.engine.view(root)
        self.assertEqual(shown['saved_record']['next'], 'new')
        self.assertEqual(shown['title'], root.name)
        with self.assertRaisesRegex(workspace.WorkspaceError, copy_setup.UNREAD_FORM):
            self.engine.copy_setup(root)
        self.assertEqual(self.workspace_state(root), before)

    def test_a_linked_file_is_never_listed_or_read(self):
        root = self.stopped_at('blueprint')
        (root / RUN).write_text('{not a run record')
        outside = self.base / 'outside.md'
        outside.write_text('Not the training’s own file.')
        (root / 'document.md').symlink_to(outside)
        shown = self.engine.view(root)
        self.assertNotIn('document.md', shown['saved_record']['files'])
        native = page.RunnerPage(8765, self.engine)
        with self.assertRaises(page.desk.Refusal):
            native.read('/api/saved-file', lambda key: {'path': str(root), 'name': 'document.md'}[key])

    def test_a_saved_file_removed_while_it_is_read_is_a_refusal(self):
        from unittest import mock
        root = self.stopped_at('blueprint')
        (root / RUN).write_text('{not a run record')
        native = page.RunnerPage(8765, self.engine)
        with mock.patch.object(page.desk, 'text_of', side_effect=FileNotFoundError('gone')), \
                self.assertRaises(page.desk.Refusal):
            native.read('/api/saved-file', lambda key: {'path': str(root), 'name': 'blueprint.md'}[key])

    def test_a_list_read_reads_only_the_two_small_records(self):
        """Lists, polling and reading one saved file decide from the run and session
        records alone: the training's folder, however large, is not read for them."""
        from unittest import mock
        root = self.stopped_at('blueprint')
        (root / 'work').mkdir(exist_ok=True)
        (root / 'work/large-capture.bin').write_bytes(b'\0' * 4_000_000)
        native = page.RunnerPage(8765, self.engine)
        record = self.record(root)
        for damage, kind in ((json.dumps(record), 'saved'), ('{not a run record', 'unread'),
                             (json.dumps({**record, 'schema': 99}), 'saved')):
            with self.subTest(damage=damage[:12]):
                (root / RUN).write_text(damage)
                with mock.patch.object(desk_chat, '_files', side_effect=AssertionError('the whole folder was read')), \
                        mock.patch.object(desk_migration, 'classify', side_effect=AssertionError('classified')):
                    self.assertEqual(self.engine.brief(root)['saved'], kind)
                    self.assertEqual(native.with_run({'path': str(root)})['run']['saved'], kind)
                    # Nothing of a saved record waits for the person in its row of stages.
                    listed = native.detail(str(root))
                    self.assertFalse([stage for stage in listed.get('stages') or ()
                                      if stage.get('state') in ('current', 'review')])
                    self.assertEqual(self.engine.standing()['runs'][0]['state'], 'saved')
                    status, _, body = native.read('/api/saved-file', lambda key: {'path': str(root), 'name': 'blueprint.md'}[key])
                    self.assertEqual(status, 200, body)


class RefusedDeskWorkTests(SavedStopTests):
    """Desk work the runner refuses is never a saved-flow record: it keeps the screen and
    the refusal it had, and is never offered Start new work from this in place of it."""

    def assert_desk_refusal(self, root, refusal):
        with self.assertRaises(workspace.WorkspaceError) as caught:
            self.engine._load(root)
        self.assertEqual(str(caught.exception), refusal)
        self.assertIsNone(self.engine.saved_record(root))
        with self.assertRaisesRegex(workspace.WorkspaceError, '^' + refusal.replace('.', r'\.') + '$'):
            self.engine.view(root)
        brief = self.engine.brief(root)
        self.assertNotIn('saved', brief)
        self.assertEqual((brief['state'], brief['sentence']), ('failed', refusal))
        self.assertEqual(desk_migration.outcome(self.engine, root)['outcome'], 'desk')

    def test_refused_desk_work_keeps_its_own_refusal(self):
        root = self.start(title='Desk work')
        record = self.record(root)
        self.assertEqual(record['flow'], 'desk')
        for change, refusal in (
                ({'research_contract': None},
                 'This run is missing its saved research contract. Restore its run record.'),
                # Desk work a newer Training Studio wrote, in a form this one does not know.
                ({'schema': 99}, f'The run record in {root.name} cannot be read, so the runner '
                                 'will not drive this training.')):
            with self.subTest(change=change):
                (root / RUN).write_text(json.dumps({**record, **change}))
                self.assert_desk_refusal(root, refusal)

    def test_an_opened_training_and_an_interrupted_opening_are_desk_work(self):
        root = self.stopped_at('blueprint')
        shown = self.preview(root)
        desk_chat.migrate(self.engine, root, shown['expected'])
        self.assertEqual(desk_migration.outcome(self.engine, root)['outcome'], 'desk')
        (root / RUN).write_text('{a changed original')
        self.assertIsNone(self.engine.saved_record(root))
        self.assertEqual(desk_migration.outcome(self.engine, root)['outcome'], 'desk')
        other = self.stopped_at('research')
        pending = other / desk_migration.format.PENDING
        pending.parent.mkdir(parents=True, exist_ok=True)
        pending.write_text('{interrupted')
        (other / RUN).write_text('{not a run record')
        self.assertIsNone(self.engine.saved_record(other))
        self.assertEqual(desk_migration.outcome(self.engine, other)['outcome'], 'desk')


class NothingContinuesTests(SavedStopTests):
    """The earlier flow no longer continues: every route that continued it refuses a saved
    training in one sentence naming the two ways on, and waking it runs nothing."""

    def test_routes_that_continued_saved_work_refuse_it_and_name_both_ways_on(self):
        root = self.stopped_at('blueprint')
        path = str(root)
        before, jobs = self.workspace_state(root), len(self.workers.jobs)
        native = page.RunnerPage(8765, self.engine)
        for target, sent in (
                ('/api/run', {'path': path, 'action': 'resume'}),
                ('/api/run', {'path': path, 'action': 'retry'}),
                ('/api/answer', {'path': path, 'id': 'asked', 'answer': 'Kubernetes.'}),
                ('/api/review', {'path': path}),
                ('/api/look', {'path': path, 'choice': 'default'}),
                ('/api/outline', {'path': path}),
                ('/api/note', {'path': path, 'text': 'More examples.', 'expected': ''}),
                ('/api/documents', {'path': path, 'action': 'done'}),
                ('/api/copies', {'path': path})):
            with self.subTest(target=target, sent=sent):
                with self.assertRaises(page.desk.Refusal) as caught:
                    native.apply(target, sent)
                self.assertEqual((caught.exception.status, str(caught.exception)),
                                 (409, engines.SAVED_ONLY))
        session = workspace.load(root)
        seen = workspace.sha256_file(root / workspace.artifact(root, session, 'blueprint')['file'])
        with self.assertRaises(page.desk.Refusal) as caught:
            native.decide(path, 'blueprint', 'approve', None, seen)
        self.assertEqual(str(caught.exception), engines.SAVED_ONLY)
        with self.assertRaises(page.desk.Refusal):
            native.read('/api/gate', lambda key: {'path': path, 'artifact': 'blueprint'}[key])
        self.engine.wake(root)
        self.engine.resume()
        self.assertEqual(len(self.workers.jobs), jobs)
        self.assertEqual(self.workspace_state(root), before)
        self.assertEqual(workspace.status(root)['gate'], 'blueprint')


class CarriedOverTests(SavedStopTests):
    """What the second review of the read-only record found (#542), each put right."""

    def test_the_list_and_the_opened_record_never_contradict_each_other(self):
        """The list says only what the two small records prove; the opened record says,
        from the whole classification, which way on it has, and the preview agrees."""
        policy = 'Restore this training’s saved material scheduling policy.'
        for state, damage, why, refusal in (
                ('blueprint-gate', lambda root: (root / RUN).write_text(json.dumps(
                    {**self.record(root), 'material_flow': {'order': 'other'}})),
                 desk_migration.UNREADABLE, policy),
                ('finished', lambda root: (root / RUN).write_text(json.dumps(
                    {**self.record(root), 'material_flow': {'order': 'other'}})),
                 desk_migration.UNREADABLE, policy),
                ('document-gate', lambda root: (root / SESSION).write_text('{bad'),
                 desk_migration.UNREADABLE, None)):
            with self.subTest(state=state):
                root = self.saved(state)
                damage(root)
                brief = self.engine.brief(root)
                self.assertEqual((brief['state'], brief['sentence'], brief['saved']),
                                 ('saved', engines.SAVED_BRIEF, 'saved'))
                listed = page.RunnerPage(8765, self.engine).with_run({'path': str(root)})
                self.assertEqual(listed['run']['saved'], 'saved')
                shown = self.record_of(root)
                self.assertEqual((shown['saved_record']['outcome'], shown['saved_record']['why']),
                                 ('read-only', why))
                if refusal:
                    self.assertEqual(shown['saved_record']['refusal'], refusal)
                self.assertFalse(shown['can_migrate_desk'] or shown['can_open_desk'])
                preview = self.preview(root)
                self.assertEqual(preview['outcome']['outcome'], 'read-only')
                self.assertTrue(preview['blockers'])

    def test_desk_work_whose_run_record_is_not_json_keeps_its_own_refusal(self):
        root = self.start(title='Desk work')
        (root / RUN).write_text('{not a run record')
        self.assertEqual(workspace.load(root)['flow'], 'desk')
        self.assertEqual(desk_migration.record_kind(root), 'desk')
        self.assertIsNone(self.engine.saved_record(root))
        with self.assertRaises(workspace.WorkspaceError):
            self.engine.view(root)
        self.assertEqual(self.engine.brief(root)['state'], 'failed')
        self.assertEqual(desk_migration.outcome(self.engine, root)['outcome'], 'desk')

    def test_a_large_refused_desk_run_record_is_still_desk_work(self):
        root = self.start(title='Large desk work')
        record = self.record(root)
        (root / RUN).write_text(json.dumps({**record, 'schema': 99, 'padding': 'x' * 1_100_000}))
        (root / SESSION).write_text(json.dumps({**workspace.load(root), 'flow': None}))
        self.assertEqual(desk_migration.record_kind(root), 'desk')
        self.assertIsNone(self.engine.saved_record(root))
        with self.assertRaises(workspace.WorkspaceError):
            self.engine.view(root)

    def test_a_folder_that_cannot_be_walked_says_so_and_new_work_still_starts_from_it(self):
        root = self.stopped_at('blueprint')
        outside = self.base / 'outside.md'
        outside.write_text('Not the training’s own file.')
        (root / 'notes.md').symlink_to(outside)
        found = desk_migration.outcome(self.engine, root)
        self.assertEqual((found['outcome'], found['reason'], found['next']),
                         ('read-only', desk_migration.UNWALKED, 'copy'))
        self.assert_read_only(root, desk_migration.UNWALKED, 'copy')
        self.assertEqual(self.engine.copy_setup(root)['title'], 'Stop blueprint copy')

    def test_no_single_record_takes_the_list_down(self):
        good = self.start(title='Good desk')
        worded = self.start(title='Worded contract')
        refused = self.start(title='Refused desk')
        (worded / RUN).write_text(json.dumps({**self.record(worded), 'research_contract': 'text'}))
        (refused / RUN).write_text(json.dumps({**self.record(refused), 'research_contract': None}))
        listing = {item['path']: item for item in page.RunnerPage(8765, self.engine).trainings()}
        self.assertNotEqual(listing[str(good)]['run']['state'], 'failed')
        for root, said in ((worded, f'The run record in {worded.name} cannot be read'),
                           (refused, 'This run is missing its saved research contract.')):
            with self.subTest(root=root.name):
                self.assertEqual(listing[str(root)]['run']['state'], 'failed')
                self.assertIn(said, listing[str(root)]['sentence'])


from runner_support import TeamCase  # noqa: E402


class ReadOnlyDriverTests(TeamCase):
    """A read-only record in a shared workspace says who drives it, as its record names."""

    def test_the_driver_a_readable_record_names_is_kept(self):
        from test_desk_migration import MigrationTests
        root = MigrationTests.saved(self, 'Driven elsewhere')
        record = self.record(root)
        record.update(schema=99, driver={'computer': 'f' * 16, 'name': 'Blake',
                                         'since': home.now()})
        (root / RUN).write_text(json.dumps(record))
        brief = self.engine.brief(root)
        self.assertEqual(brief['saved'], 'saved')
        self.assertEqual(brief['driver']['name'], 'Blake')
        self.assertFalse(brief['mine'])
        item = page.RunnerPage(8765, self.engine).with_run({'path': str(root)})
        self.assertEqual((item['driver']['name'], item['mine']), ('Blake', False))


class SavedTeamTests(TeamCase):
    """A saved training in a shared workspace waits for what clears it, then opens on the
    desk: taken over from another computer, or its shared originals committed."""

    def saved(self, title):
        from test_desk_migration import MigrationTests
        return MigrationTests.saved(self, title)

    def test_another_computers_saved_training_waits_to_be_taken_over(self):
        root = self.saved('Driven elsewhere')
        self.engine.share()
        self.as_(self.blake, self.blake.engine.fetch)
        self.as_(self.blake, self.blake.engine.drive, self.theirs(self.blake, root), 'take')
        self.engine.fetch()
        shown = self.engine.view(root)
        self.assertEqual(shown['saved_record']['outcome'], 'waiting')
        self.assertIn(('owner', True), [(wait['kind'], wait['take'])
                                        for wait in shown['saved_record']['waits']])
        self.assertFalse(shown['mine'])
        self.assertFalse(shown['can_migrate_desk'])
        # Taking it over clears it: it then opens on the desk from here.
        self.engine.drive(root, 'take')
        shown = self.engine.view(root)
        self.assertEqual(shown['saved_record']['outcome'], 'migrates')
        self.assertTrue(shown['can_migrate_desk'])

    def test_uncommitted_shared_originals_wait_until_they_are_committed(self):
        from runner_support import BLUEPRINT
        root = self.saved('Shared uncommitted')
        (root / 'blueprint.md').write_text(BLUEPRINT + '\nChanged shared plan.')
        shown = self.engine.view(root)
        self.assertEqual(shown['saved_record']['outcome'], 'waiting')
        self.assertEqual([wait['kind'] for wait in shown['saved_record']['waits']], ['shared'])
        # Nothing on the page commits it, so new work can start from it meanwhile.
        self.assertEqual(shown['saved_record']['next'], 'copy')
        gitstate.commit(self.space, 'keep shared saved inputs explicitly', [root])
        self.assertEqual(self.engine.view(root)['saved_record']['outcome'], 'migrates')


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
    record_of = SavedStopTests.record_of
    snapshot = SavedStopTests.snapshot
    workspace_state = SavedStopTests.workspace_state
    preview = SavedStopTests.preview
    assert_refused = SavedStopTests.assert_refused
    assert_migrates = SavedStopTests.assert_migrates

    MADE = ['blueprint', 'document', 'brief']
    saved = SavedStopTests.saved

    def migrated_deck_record(self, root, before):
        """The deck's saved run entry is kept as it was: nothing of it is approved or
        delivered by the migration."""
        record = self.engine._load(root)
        self.assertEqual(record['deck'], before['deck'])
        self.assertEqual(record['execution'], 'conversation')

    def test_what_the_deck_says_waiting_migrates_with_the_outline_kept_undecided(self):
        root = self.saved('deck-outline-waiting')
        # What the deck says waits for the person, as the saved flow left it.
        self.assertEqual(workspace.load(root)['next_step'],
                         'Waiting for your review of what the slide deck says')
        self.assertNotIn('approved', self.record(root)['deck']['']['outline'])
        self.assertIsNone(self.view(root)['flow'])
        before = self.record(root)
        shown = self.assert_migrates(root, self.MADE)
        self.assertIn(pipeline.OUTLINE, shown['required'])
        self.migrated_deck_record(root, before)

    def test_deck_look_waiting_migrates_with_no_look_chosen(self):
        self.brand.offers_looks = True
        root = self.saved('deck-look-waiting')
        self.assertNotIn('look', self.record(root)['deck'][''])
        before = self.record(root)
        self.assert_migrates(root, self.MADE)
        self.migrated_deck_record(root, before)

    def test_deck_gate_migrates_with_the_saved_deck(self):
        root = self.saved('deck-gate-waiting')
        self.assertEqual(workspace.status(root)['gate'], 'deck')
        before = self.record(root)
        self.assert_migrates(root, [*self.MADE, 'deck'])
        self.migrated_deck_record(root, before)

    def test_deck_outline_without_its_plan_is_a_read_only_record(self):
        root = self.saved('deck-outline-waiting')
        (root / 'blueprint.md').unlink()
        said = 'blueprint.md is required to interpret the saved deck outline. Restore it first.'
        shown = self.assert_refused(root, said)
        self.assertEqual(shown['outcome'], {'outcome': 'read-only', 'next': 'copy',
                                            'reason': desk_migration.MISSING + ' ' + said})
        SavedStopTests.assert_read_only(self, root, desk_migration.MISSING + ' ' + said, 'copy')

    def test_unreadable_deck_outline_is_a_read_only_record(self):
        root = self.saved('deck-outline-waiting')
        outline = json.loads((root / pipeline.OUTLINE).read_text())
        outline['slides'][0]['title'] = 7
        (root / pipeline.OUTLINE).write_text(json.dumps(outline))
        said = 'The shared saved deck outline cannot be read losslessly.'
        shown = self.assert_refused(root, said)
        self.assertEqual(shown['outcome'], {'outcome': 'read-only', 'next': 'copy',
                                            'reason': desk_migration.MISSING + ' ' + said})
        SavedStopTests.assert_read_only(self, root, desk_migration.MISSING + ' ' + said, 'copy')


import unittest  # noqa: E402
from test_desk import NODE, ScriptedPage, ok, SET_UP, RUNNER, AGENTS_FOUND, MODELS  # noqa: E402
from test_runner_page import PageCase  # noqa: E402


@unittest.skipUnless(NODE, 'Node is needed to run the page scripts without a browser')
class ReadOnlyPageTests(ScriptedPage, PageCase):
    """The saved-record screen: its title, a bead with words for its way on, what is
    happening and the one filled action, and its saved files read in place. Nothing on it
    continues the training, and opening it sends nothing."""

    def fixture(self, state, damage=None):
        root = saved_fixtures.load(self, state)
        if damage:
            damage(root)
        self.root = root   # the page plan is written beside it
        path = str(root)
        return dict(path=path, run=self.get('run', path=path), detail=self.get('training', path=path),
                    listing=self.get('trainings'),
                    file=self.get('saved-file', path=path, name='blueprint.md'),
                    preview=self.get('drafts/migration-preview', path=path))

    def answers(self, fixture):
        return {'GET /api/capabilities': [RUNNER], 'GET /api/setup': [ok(SET_UP)],
                'GET /api/trainings': [ok(fixture['listing'])],
                'GET /api/training': [ok(fixture['detail'])],
                'GET /api/run': [ok(fixture['run'])],
                'GET /api/computer': [ok({'items': []})],
                'GET /api/agents': [ok(AGENTS_FOUND)], **MODELS,
                'GET /api/saved-file': [ok(fixture['file'])],
                'GET /api/drafts/migration-preview': [ok(fixture['preview'])]}

    def listed(self, fixture):
        return next(item for item in fixture['listing']['trainings']
                    if item['path'] == fixture['path'])

    def assert_no_continuing(self, shot, result):
        for word in ('Continue', 'Try again', 'Answer', 'Approve', 'Resume'):
            self.assertNotIn(word, shot['buttons'])
        self.assertEqual([r for r in result['requests'] if r['method'] == 'POST'], [])

    def test_desktop_and_phone_read_the_record_and_offer_one_way_on(self):
        unreadable = lambda root: (root / RUN).write_text('{not a run record')  # noqa: E731
        unsupported = lambda root: (root / RUN).write_text(  # noqa: E731
            json.dumps({**self.record(root), 'schema': 99}))
        made = ['Read intake', 'Read research report', 'Read teaching plan']
        for state, title, damage, action, reads, why, lede, kind in (
                ('blueprint-gate', 'Stop blueprint', unreadable, 'Start a new training', made,
                 desk_migration.UNREAD, engines.UNREAD_RECORD, 'unread'),
                ('document-gate', 'Stop document', unsupported, 'Start new work from this',
                 [*made, 'Read learner guide'], desk_migration.UNREADABLE, engines.SAVED_RECORD,
                 'saved')):
            fixture = self.fixture(state, damage)
            self.assertEqual(self.listed(fixture)['run']['saved'], kind)
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
                    self.assertIn(why, shot['text'])
                    self.assertIn(lede, shot['text'])
                    # The shared state bead with its words, not a bare label over the title.
                    self.assertIn('off', shot['beads'])
                    self.assertEqual(shot['text'].count('Read-only'), 1, shot['text'])
                    self.assertIn('Why it cannot be continued', shot['text'])
                    self.assertNotIn('Open on the desk', shot['buttons'])
                    self.assert_no_continuing(shot, result)
                    self.assertEqual([name for name in shot['buttons'] if name.startswith('Read ')],
                                     reads)
                    self.assertIn('Rolling restarts', result['snapshots']['read']['text'])

    def test_a_record_that_opens_on_the_desk_offers_the_preview(self):
        fixture = self.fixture('blueprint-gate')
        self.assertEqual(self.listed(fixture)['run']['saved'], 'saved')
        for narrow in (False, True):
            with self.subTest(narrow=narrow):
                result = self.run_page(self.answers(fixture), [
                    {'snapshot': 'record'}, {'click': 'Open on the desk'}, {'snapshot': 'sheet'}],
                    state={'screen': 'run', 'path': fixture['path']}, narrow=narrow)
                shot = result['snapshots']['record']
                self.assertEqual(shot['heading'], 'Stop blueprint')
                self.assertEqual(shot['filled'], ['Open on the desk'])
                self.assertIn(engines.SAVED_MIGRATES, shot['text'])
                self.assertIn('Opens on the desk', shot['text'])
                self.assertIn('What opens on the desk', shot['text'])
                self.assertIn('the blueprint', shot['text'])
                self.assertIn('Original files, History', shot['text'])
                self.assertIn('Read teaching plan', shot['buttons'])
                self.assert_no_continuing(shot, result)
                # The existing preview sheet: nothing is applied until the person says so.
                self.assertIn('Apply', result['snapshots']['sheet']['buttons'])

    def test_a_finished_record_keeps_its_finished_open_on_the_desk(self):
        fixture = self.fixture('finished')
        result = self.run_page(self.answers(fixture), [{'snapshot': 'record'}],
                               state={'screen': 'run', 'path': fixture['path']})
        shot = result['snapshots']['record']
        self.assertEqual(shot['filled'], ['Open on the desk'])
        self.assertIn(engines.SAVED_FINISHED, shot['text'])
        self.assertIn('Finished by the earlier flow', shot['text'])
        self.assert_no_continuing(shot, result)

    def test_a_waiting_record_says_what_clears_it_and_offers_new_work(self):
        from runner import engine as engines_module
        fixture = self.fixture('blueprint-gate', lambda root: (
            root / engines_module.IN_HAND).write_text('blueprint'))
        for narrow in (False, True):
            with self.subTest(narrow=narrow):
                result = self.run_page(self.answers(fixture), [{'snapshot': 'record'}],
                                       state={'screen': 'run', 'path': fixture['path']},
                                       narrow=narrow)
                shot = result['snapshots']['record']
                self.assertEqual(shot['filled'], ['Start new work from this'])
                self.assertIn(engines.SAVED_WAITING, shot['text'])
                self.assertIn('What it waits for', shot['text'])
                self.assertIn(engines.WAITS_FOR['busy'][0], shot['text'])
                self.assertIn(engines.WAITS_FOR['busy'][1], shot['text'])
                self.assertIn('Check again', shot['buttons'])
                self.assertNotIn('Open on the desk', shot['buttons'])
                self.assert_no_continuing(shot, result)

    def test_home_and_trainings_say_a_saved_record_in_words(self):
        """Home lists saved records apart, each with the words its two small records prove,
        and the Trainings filter offers them; nothing of them is said to wait for you."""
        fixture = self.fixture('blueprint-gate')
        for narrow in (False, True):
            with self.subTest(narrow=narrow):
                result = self.run_page(self.answers(fixture), [{'snapshot': 'home'}],
                                       state={'screen': 'home'}, narrow=narrow)
                text = result['snapshots']['home']['text']
                self.assertIn('Saved earlier', text)
                self.assertIn(engines.SAVED_BRIEF, text)
                self.assertNotIn('yours to review', text)
                self.assertNotIn('Review ', ' '.join(result['snapshots']['home']['buttons']))
        result = self.run_page(self.answers(fixture), [{'snapshot': 'list'}],
                               state={'screen': 'trainings'})
        self.assertIn('Saved earlier', result['snapshots']['list']['text'])
        self.assertNotIn('yours to review', result['snapshots']['list']['text'])

    def test_an_open_record_is_not_read_again_at_the_lists_pace(self):
        """An open saved record classifies its folder once: polling reads the list, not the
        record again, until its small records change or the person asks."""
        fixture = self.fixture('blueprint-gate')
        result = self.run_page(self.answers(fixture), [
            {'snapshot': 'record'}, {'poll': True}, {'poll': True}, {'poll': True},
            {'snapshot': 'later'}, {'click': 'Read teaching plan'}],
            state={'screen': 'run', 'path': fixture['path']})
        runs = [r for r in result['requests'] if r['address'].startswith('/api/run')]
        lists = [r for r in result['requests'] if r['address'].startswith('/api/trainings')]
        self.assertEqual(len(runs), 1, runs)
        self.assertGreater(len(lists), 3)
        self.assertEqual(result['snapshots']['later']['filled'], ['Open on the desk'])
        # Its small records changed in the list: the record is read again.
        moved = json.loads(json.dumps(fixture['listing']))
        self.listed({'listing': moved, 'path': fixture['path']})['run']['saved'] = 'unread'
        answers = {**self.answers(fixture),
                   'GET /api/trainings': [ok(fixture['listing']), ok(moved)]}
        result = self.run_page(answers, [{'snapshot': 'record'}, {'poll': True}],
                               state={'screen': 'run', 'path': fixture['path']})
        self.assertEqual(len([r for r in result['requests']
                              if r['address'].startswith('/api/run')]), 2)
