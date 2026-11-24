"""Every saved state the earlier gated flow leaves, in its original format, and what the
explicit migration says of each: opened on the desk, kept in its saved flow for now, or shown
as a read-only record. Each deck is loaded from tests/fixtures/saved/ (`load_saved`): the
files the real saved-run dispatch wrote for that state, captured by tests/saved_fixtures.py
and checked against the flow by tests/test_saved_fixtures.py. Where the stand-ins cannot
reach a saved shape (schema 4, an unreadable record), the capture edited the record the
dispatch saved, and saved_fixtures.EDITED names those states. Only the pause taken while a
step works runs the saved flow here: what it tests is the running step itself."""
import copy
import json
from pathlib import Path
from unittest import mock

import runner_support
import saved_fixtures
import test_runner_page
from runner import decks, desk_chat, desk_migration
from studio_core.sync_guard import SYNC_WAIT
from studio_core import research_session, sync_guard
import test_running_check_records as running_check

LEVELS = ('brand-only', 'polish', 'redesign', 'rework', 'selected')
NOTHING = ('research-plan', 'research', 'document-classify', 'question-early',
           *('existing-' + level for level in LEVELS[:-1]))
UNSUPPORTED = 'This saved run format is not supported. Keep using its saved flow.'

# What becomes of each stored state (`desk_migration.outcome`): migrates through the
# migration or the finished Open on the desk, or a read-only record with its reason.
OUTCOMES = {
    **dict.fromkeys(('outline', 'document-outline', 'look', 'build', 'balanced', 'selected',
                     'selected-automatic', 'paused', 'failed', 'question'), 'migration'),
    **dict.fromkeys(('delivered', 'delivered-pptx', 'delivered-balanced', 'delivered-automatic',
                     'delivered-document-balanced', 'delivered-document-automatic',
                     'delivered-selected'), 'finished'),
    **dict.fromkeys(NOTHING, desk_migration.NOTHING_MADE),
    # Schema 4 (parallel research) stays out of the migration until the shared reader in
    # core accepts it (presentation_migration.supported; see the report of GitHub issue #542).
    'parallel-research': desk_migration.UNSUPPORTED,
    'parallel-outline': desk_migration.UNSUPPORTED,
    'unleveled': desk_migration.UNSUPPORTED,
    'corrupt': desk_migration.UNREAD,
}


class GatedSavedStateTests(runner_support.DeskCase):
    scanner = running_check.RunningCheckTests.scanner

    def snapshot(self, root):
        return {p.relative_to(root).as_posix(): p.read_bytes()
                for p in root.rglob('*') if p.is_file()}

    def preview(self, root):
        before = self.snapshot(self.space.root)
        found = desk_chat.migration_preview(self.engine, root)
        self.assertEqual(self.snapshot(self.space.root), before, 'a preview wrote')
        return found

    def refused(self, root):
        """The shared running-step check's refusal (core/studio_core/sync_guard.py) over a
        deck record Presentation Studio does not write: it names that deck's folder, and it
        stops every preview in the workspace until the record is restored."""
        return sync_guard.unchecked(root.relative_to(self.space.repo).as_posix(),
                                    sync_guard.UNKNOWN_DECK)

    def waits_at(self, root, gate):
        self.assertEqual((self.view(root)['gate'] or {}).get('name'), gate)

    def outcome_of(self, root):
        files = desk_chat._files(root)
        try:
            record = json.loads(files['run.json'])
        except ValueError:
            record = None
        return desk_migration.outcome(record, files)

    # --- one answer for every saved state ----------------------------------------------------

    def test_every_saved_state_has_one_outcome(self):
        self.assertEqual(sorted(OUTCOMES), sorted(saved_fixtures.STATES))
        for state, expected in OUTCOMES.items():
            with self.subTest(state):
                root = self.load_saved(state)
                before = self.snapshot(root)
                found = self.outcome_of(root)
                if expected in ('migration', 'finished'):
                    self.assertEqual((found['outcome'], found['by']), ('migrates', expected))
                else:
                    self.assertEqual((found['outcome'], found['why']), ('read-only', expected))
                    # Its start form can be read, so it offers Start new work from this.
                    self.assertEqual(found['next'], 'new' if state == 'corrupt' else 'copy')
                self.assertEqual(self.snapshot(root), before)

    def test_the_runners_refusal_is_the_read_only_reason(self):
        root = self.load_saved('unleveled')
        with self.assertRaises(desk_chat.WorkspaceError) as refused:
            self.engine._load(root)
        found = desk_migration.outcome(self.record(root), desk_chat._files(root), refused.exception)
        self.assertEqual(found, {'outcome': 'read-only', 'why': str(refused.exception),
                                 'next': 'copy', 'preview': str(refused.exception)})
        self.assertEqual(self.view(root)['saved_record']['why'], found['why'])

    def test_a_missing_dependency_is_a_read_only_reason(self):
        root = self.load_saved('selected')
        (root / 'sources/original.pptx').unlink()
        found = self.outcome_of(root)
        self.assertEqual((found['outcome'], found['why']),
                         ('read-only', 'The original deck is missing or unreadable.'))
        self.assertEqual(found['preview'], 'The original deck is missing or unreadable. '
                                           'Continue with its saved flow first.')

    # --- states that open on the desk ------------------------------------------------------

    def test_every_stop_with_a_drafted_outline_can_be_opened_on_the_desk(self):
        scratch = self.load_saved('outline')
        self.waits_at(scratch, 'gate:outline')
        document = self.load_saved('document-outline')
        self.waits_at(document, 'gate:outline')
        look = self.load_saved('look')
        self.waits_at(look, 'gate:look')
        build = self.load_saved('build', title='At the deck')
        self.waits_at(build, 'gate:build')
        for root in (scratch, document, look, build):
            with self.subTest(root.name):
                self.assertEqual(self.preview(root)['blockers'], [])

    def test_selected_changes_opens_from_its_inventory(self):
        root = self.load_saved('selected')
        self.waits_at(root, 'gate:classify')
        self.assertEqual(self.preview(root)['blockers'], [])

    def opened_losslessly(self, root):
        """Open `root` on the desk; assert every original byte, every gate and every step
        are as the saved flow left them, and nothing is approved, ready or delivered."""
        before, record = self.snapshot(root), self.record(root)
        found = self.preview(root)
        self.assertEqual(found['blockers'], [])
        with mock.patch.object(self.engine, 'wake', side_effect=AssertionError('resumed')), \
                mock.patch.object(self.engine, 'ready', side_effect=AssertionError('readiness')):
            shown = desk_chat.migrate(self.engine, root, found['expected'])
        for name, data in before.items():
            self.assertEqual((root / name).read_bytes(), data, name)
        effective = decks.read_run(root)
        self.assertEqual(effective['gates'], record['gates'])
        self.assertEqual(effective['steps'], record['steps'])
        self.assertEqual(shown['execution'], 'conversation')
        self.assertFalse(shown['desk']['ready'])
        self.assertFalse((root / 'deliver.json').exists())
        return found, record, effective, shown

    def test_a_failure_after_the_outline_opens_with_the_failure_kept_in_history(self):
        root = self.load_saved('failed')
        halted = self.record(root)['halted']
        self.assertEqual(halted['state'], 'failed')
        self.assertTrue(halted['step'].startswith('build-sections'))
        found, record, effective, shown = self.opened_losslessly(root)
        self.assertIn(desk_migration.HALTS['failed'], found['retained'])
        self.assertIsNone(effective['halted'])
        self.assertEqual(effective['migration_saved_status'], halted)
        self.assertEqual(shown['desk']['saved_status'], halted)
        # The failed step stays unfinished, and nothing was tried again.
        self.assertFalse((record['steps'].get('build-sections') or {}).get('done'))
        self.assertFalse(any(entry.get('done') for name, entry in record['steps'].items()
                             if name.startswith('build-sections')))
        self.assertNotIn('gate:build', effective['gates'])

    def test_a_worker_question_after_the_outline_opens_with_it_kept_in_history(self):
        root = self.load_saved('question')
        asked = self.record(root)['question']
        self.assertEqual(asked['text'], saved_fixtures.QUESTION)
        self.assertTrue((root / 'outline.json').is_file())   # the first draft was kept
        found, record, effective, shown = self.opened_losslessly(root)
        self.assertIn(desk_migration.QUESTION, found['retained'])
        self.assertIsNone(effective['question'])
        self.assertEqual(effective['migration_saved_question'], asked)
        self.assertEqual(shown['desk']['saved_question'], asked)
        self.assertIsNone(shown['desk']['saved_status'])
        # Nobody answered it, and its step stays as the saved flow left it.
        self.assertEqual(effective['answers'], record['answers'])
        self.assertFalse(record['steps'][asked['step']].get('done'))
        self.assertEqual(record['gates']['gate:outline']['state'], 'changes')

    # --- states that keep their saved flow for now ------------------------------------------

    def test_stops_before_an_outline_keep_their_saved_flow(self):
        for state in NOTHING:
            with self.subTest(state):
                root = self.load_saved(state)
                self.assertEqual(self.preview(root)['blockers'], [desk_migration.NO_OUTLINE])
                shown = self.view(root)
                # It continues as it was saved: at its stop, or with its question waiting.
                self.assertTrue(shown['gate'] is not None or shown['question'] is not None)

    def test_a_pause_taken_mid_step_waits_for_its_step(self):
        # A real pause: Pause on the page (`act`) while the outline step is working. The
        # worker carries on after it, as a real one does; while it does, the step's lock is
        # in hand and the run is busy, so the preview says to wait. This runs the saved
        # flow, as the running step is what it tests; it goes with the flow.
        seen = {}

        def pausing(tools, job):
            root = next(path.parent for path in self.space.root.rglob('run.json')
                        if json.loads(path.read_text()).get('title') == 'Paused mid-step')
            seen['root'] = root
            seen['shown'] = self.engine.act(root, 'pause')['state']
            seen['locked'] = (root / self.engines.IN_HAND).is_file()
            seen['preview'] = desk_chat.migration_preview(self.engine, root)
            return self.workers.outline(tools, job)

        self.workers.then('outline', pausing)
        root = self.saved_start(title='Paused mid-step')
        self.assertEqual(seen['root'], root)
        self.assertEqual(seen['shown'], 'paused')
        self.assertTrue(seen['locked'])
        self.assertIn(SYNC_WAIT, seen['preview']['blockers'])
        self.assertEqual(seen['preview']['writes'], [])

    def test_a_pause_taken_mid_step_then_opens_losslessly(self):
        root = self.load_saved('paused')
        # The step ended: the pause is what the runner saved, with the outline it made.
        record = self.record(root)
        halted = record['halted']
        self.assertEqual((halted['state'], halted['step'], halted['why']),
                         ('paused', None, 'Paused on the page.'))
        self.assertTrue(record['steps']['outline']['done'])
        self.assertFalse((root / self.engines.IN_HAND).exists())
        self.assertEqual(self.view(root)['state'], 'paused')
        before = self.snapshot(root)
        found = self.preview(root)
        self.assertEqual(found['blockers'], [])
        self.assertIn(desk_migration.HALTS['paused'], found['retained'])
        with mock.patch.object(self.engine, 'wake', side_effect=AssertionError('resumed')), \
                mock.patch.object(self.engine, 'ready', side_effect=AssertionError('readiness')):
            shown = desk_chat.migrate(self.engine, root, found['expected'])
        # Every original byte is kept; the pause is History, not an active runner.
        for name, data in before.items():
            self.assertEqual((root / name).read_bytes(), data, name)
        effective = decks.read_run(root)
        self.assertIsNone(effective['halted'])
        self.assertEqual(effective['migration_saved_status'], halted)
        self.assertEqual(shown['desk']['saved_status'], halted)
        self.assertEqual(shown['execution'], 'conversation')
        # No approval or delivery is invented: the gates are exactly as the person left them.
        self.assertEqual(effective['gates'], record['gates'])
        self.assertNotEqual((effective['gates'].get('gate:outline') or {}).get('state'), 'approved')
        self.assertFalse(shown['desk']['ready'])
        self.assertFalse((root / 'deliver.json').exists())

    def test_a_desk_deck_started_with_research_never_stops_a_preview(self):
        # GitHub issue #541: a desk deck started with research under the engine's production
        # options (record schema 6) is a deck the shared running-step check knows, so a
        # saved deck beside it previews with no blockers.
        ready = self.load_saved('outline', title='Ready to open')
        self.waits_at(ready, 'gate:outline')
        engine = self.make(**running_check.PRODUCTION)
        self.workers.then('scan', self.scanner)
        with mock.patch.object(research_session, 'execution', return_value=running_check.COLLECTION):
            researched = self.start_desk(title='Researched', research=True, engine=engine)
        self.assertEqual(self.record(researched)['schema'], 6)
        self.assertEqual(self.preview(ready)['blockers'], [])
        # A record Presentation Studio does not write still stops every preview, and now
        # says which deck's folder holds it.
        refused = self.load_saved('unleveled', title='No review level')
        self.assertEqual(self.preview(ready)['blockers'], [self.refused(refused)])
        self.waits_at(ready, 'gate:outline')    # it still continues in its saved flow

    def test_parallel_research_records_keep_their_saved_flow(self):
        root = self.load_saved('parallel-research')
        record = self.record(root)
        self.assertEqual(record['schema'], 4)
        # Its own reason: the migration's reader does not support schema 4.
        files = self.snapshot(root)
        self.assertEqual(desk_chat.prepare_migration(record, files)['blockers'], [UNSUPPORTED])
        # The engine writes schema 4, so the shared running-step check knows the deck and the
        # preview gives that reason alone (GitHub issue #541).
        self.assertEqual(self.preview(root)['blockers'], [UNSUPPORTED])
        self.waits_at(root, 'gate:research-plan')
        # With its outline drafted it is still refused, until the shared reader in core
        # accepts schema 4.
        drafted = self.load_saved('parallel-outline')
        self.assertEqual(self.preview(drafted)['blockers'], [UNSUPPORTED])
        self.waits_at(drafted, 'gate:outline')

    def test_a_missing_pinned_research_bundle_keeps_its_saved_flow(self):
        root = self.load_saved('build', title='Research pinned')
        record = self.record(root)
        record.update(schema=3, research_contract={'schema': 2, 'version': '1.0.0', 'digest': '1' * 64})
        record['steps']['research-report'] = {'done': True}
        decks.write_run(root, record)
        # The pinned bundle is read before anything else, and its absence is the one blocker.
        blockers = self.preview(root)['blockers']
        self.assertEqual(len(blockers), 1)
        self.assertIn('output.json', blockers[0])

    # --- records the runner cannot read ------------------------------------------------------

    def test_records_the_runner_refuses_open_as_read_only_records(self):
        corrupt = self.load_saved('corrupt')
        unleveled = self.load_saved('unleveled')
        # What the preview says of each: the record that cannot be parsed, its parser's
        # words; the one with no review level, the shared running-step check's refusal
        # naming its folder, as its own reason, the unsupported format, comes after it.
        self.assertEqual(self.preview(corrupt)['blockers'],
                         ['Expecting property name enclosed in double quotes: line 1 column 2 (char 1)'])
        self.assertEqual(self.preview(unleveled)['blockers'], [self.refused(unleveled)])
        self.assertEqual(desk_chat.prepare_migration(self.record(unleveled), self.snapshot(unleveled))['blockers'],
                         [UNSUPPORTED])
        for root, title, sentence, why, after in (
                (corrupt, 'corrupt', self.engines.UNREAD_RECORD,
                 'The run record in corrupt cannot be read, so the runner will not drive this deck.', 'new'),
                (unleveled, 'Unleveled', self.engines.SAVED_RECORD,
                 'This run is missing its saved review level. Restore its run record.', 'copy')):
            with self.subTest(root.name):
                before = self.snapshot(self.space.root)
                with self.assertRaises(desk_chat.WorkspaceError):
                    self.engine._load(root)     # the runner still never drives it
                shown = self.view(root)
                self.assertEqual(shown['title'], title)
                self.assertEqual(shown['state'], 'saved')
                self.assertEqual(shown['sentence'], sentence)
                # Read-only: no stop to decide, no desk, nothing to continue.
                self.assertIsNone(shown['gate'])
                self.assertIsNone(shown['desk'])
                record_view = shown['saved_record']
                self.assertEqual(record_view['why'], why)
                # Each saved file it holds is listed, to read as any deck's are.
                held = [name for name in self.engines.FILES if (root / name).is_file()]
                self.assertIn('outline.md', held)
                self.assertEqual(record_view['files'], held)
                self.assertEqual(record_view['next'], after)
                self.assertEqual(self.snapshot(self.space.root), before)
        # Start new work from this: the start form is read as it was saved.
        copied = self.engine.copy_setup(unleveled)
        self.assertEqual(copied['form']['title'], 'Unleveled')
        with self.assertRaises(desk_chat.WorkspaceError):
            self.engine.copy_setup(corrupt)

    def test_a_corrupt_desk_record_is_not_said_to_be_from_the_earlier_flow(self):
        root = self.start_desk(title='Desk deck')
        (root / 'run.json').write_text('{oops')
        shown = self.view(root)
        # Which flow made it cannot be known, so the earlier flow is not named.
        self.assertEqual(shown['sentence'], self.engines.UNREAD_RECORD)
        self.assertNotIn('step-by-step', shown['sentence'])
        self.assertEqual(shown['saved_record']['next'], 'new')
        self.assertIsNone(shown['desk'])

    def test_a_linked_folder_is_never_listed_among_a_records_files(self):
        import os
        import tempfile
        root = self.load_saved('unleveled')
        outside = Path(tempfile.mkdtemp(dir=self.base))
        (outside / 'plan.md').write_text('# Outside the deck')
        if (root / 'research').exists():
            import shutil
            shutil.rmtree(root / 'research')
        os.symlink(outside, root / 'research')
        (root / 'look.md').symlink_to(outside / 'plan.md')
        files = self.view(root)['saved_record']['files']
        self.assertNotIn('research/plan.md', files)
        self.assertNotIn('look.md', files)
        self.assertIn('outline.md', files)

    def test_a_desk_deck_or_an_interrupted_opening_is_never_shown_as_a_gated_record(self):
        root = self.load_saved('build', title='Interrupted')
        pending = root / desk_migration.format.PENDING
        pending.parent.mkdir(parents=True, exist_ok=True)
        pending.write_text('{}')
        with self.assertRaises(desk_chat.WorkspaceError):
            self.view(root)
        desk = self.start_desk(title='Desk deck')
        record = self.record(desk)
        record['schema'] = 2      # a desk deck with an unreadable level keeps its refusal
        decks.write_run(desk, record)
        with self.assertRaises(desk_chat.WorkspaceError):
            self.view(desk)

    def test_a_preview_never_rewrites_the_original_record(self):
        root = self.load_saved('build', title='Untouched')
        raw = (root / 'run.json').read_bytes()
        record = copy.deepcopy(json.loads(raw))
        self.preview(root)
        self.assertEqual((root / 'run.json').read_bytes(), raw)
        self.assertEqual(json.loads(raw), record)


class ReadOnlyRecordPageTests(test_runner_page.PageCase):
    """A read-only record through the page: its listed files are served, and nothing
    continues it."""

    def test_listed_files_are_served_and_act_decide_and_drive_refuse(self):
        root = self.load_saved('unleveled')
        path = str(root)
        shown = self.get('run', path=path)
        self.assertTrue(shown['saved_record']['files'])
        for name in shown['saved_record']['files']:
            with self.subTest(name):
                served = self.get('file', path=path, name=name)
                self.assertEqual(served['text'], (root / name).read_text())
        before = self.on_disk()
        for endpoint, sent in (('run', {'path': path, 'action': 'resume'}),
                               ('run', {'path': path, 'action': 'pause'}),
                               ('decide', {'path': path, 'gate': 'gate:outline', 'decision': 'approve'}),
                               ('drive', {'path': path, 'action': 'take'})):
            with self.subTest(endpoint=endpoint, sent=sent):
                status, reply, _ = self.answer('POST', '/api/' + endpoint, json.dumps(sent).encode(),
                                               origin=self.origin, kind='application/json')
                self.assertGreaterEqual(status, 400, reply)
                # Act and decide read the record and say why; in a workspace on this computer
                # drive refuses before it, as there is nothing to take or hand over.
                self.assertIn('folder on this computer' if endpoint == 'drive' else 'review level',
                              reply['error'])
        self.assertEqual(self.on_disk(), before)
