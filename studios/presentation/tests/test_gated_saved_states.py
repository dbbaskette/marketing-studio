"""Every saved state the earlier gated flow leaves, in its original format, and what the
explicit migration says of each: opened on the desk, kept in its saved flow, or shown as a
read-only record. Each deck is made and driven by the real saved-run dispatch (`saved_start`,
the gates decided and a pause taken as a person takes them), never by the migration itself.
Where the stand-ins cannot reach a saved shape (a worker's pending question, schema 4, a
pinned research bundle, an unreadable record), the record the dispatch saved is then edited
into that shape, and the test says which."""
import copy
import json
from pathlib import Path
from unittest import mock

import runner_support
import test_runner_page
from runner import decks, desk_chat, desk_migration
from studio_core.sync_guard import SYNC_WAIT
from studio_core import research_session, sync_guard
from test_flow_routes import DECK
import test_running_check_records as running_check

PASTE = {'kind': 'paste', 'text': 'Notes on rolling restarts.'}
UPLOAD = {'kind': 'upload', 'name': 'old.pptx'}
LEVELS = ('brand-only', 'polish', 'redesign', 'rework', 'selected')


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

    def existing(self, level, **changes):
        return self.saved_start(route='existing', level=level, title='Old ' + level,
                                source=UPLOAD, uploads={'old.pptx': DECK},
                                **({'selected': 'Shorten slide 2'} if level == 'selected' else {}),
                                **changes)

    # --- states that open on the desk ------------------------------------------------------

    def test_every_stop_with_a_drafted_outline_can_be_opened_on_the_desk(self):
        scratch = self.saved_start(title='At the outline')
        self.waits_at(scratch, 'gate:outline')
        document = self.saved_start(title='Document outline', route='document', source=PASTE)
        self.decide(document, 'gate:classify', extra={'kind': 'material'})
        self.waits_at(document, 'gate:outline')
        look = self.saved_start(title='At the look')
        self.decide(look, 'gate:outline')
        self.waits_at(look, 'gate:look')
        build = self.gated(title='At the deck')
        self.waits_at(build, 'gate:build')
        for root in (scratch, document, look, build):
            with self.subTest(root.name):
                self.assertEqual(self.preview(root)['blockers'], [])

    def test_selected_changes_opens_from_its_inventory(self):
        root = self.existing('selected')
        self.waits_at(root, 'gate:classify')
        self.assertEqual(self.preview(root)['blockers'], [])

    # --- states that keep their saved flow ----------------------------------------------------

    def test_stops_before_an_outline_keep_their_saved_flow(self):
        research = self.saved_start(title='Research plan', research=True)
        self.waits_at(research, 'gate:research-plan')
        found = self.saved_start(title='Research found', research=True)
        self.decide(found, 'gate:research-plan')
        self.waits_at(found, 'gate:research')
        document = self.saved_start(title='Document read', route='document', source=PASTE)
        self.waits_at(document, 'gate:classify')
        early = [research, found, document]
        for level in LEVELS[:-1]:
            root = self.existing(level)
            self.waits_at(root, 'gate:classify')
            early.append(root)
        for root in early:
            with self.subTest(root.name):
                self.assertEqual(self.preview(root)['blockers'], [desk_migration.NO_OUTLINE])
                self.assertIsNotNone(self.view(root)['gate'])   # it continues as it was saved

    def test_a_saved_worker_question_keeps_its_saved_flow(self):
        root = self.saved_start(title='Asked')
        record = self.record(root)
        record['question'] = {'id': 'q1', 'text': 'Which audience?', 'from': 'outline'}
        decks.write_run(root, record)
        self.assertEqual(self.preview(root)['blockers'], [
            'Resolve the saved runner question in its saved flow before opening it on the desk.'])
        self.assertEqual(self.view(root)['question']['id'], 'q1')

    def test_a_pause_taken_mid_step_waits_for_its_step_then_opens_losslessly(self):
        # A real pause: Pause on the page (`act`) while the outline step is working. The
        # worker carries on after it, as a real one does; while it does, the step's lock is
        # in hand and the run is busy, so the preview says to wait.
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
        ready = self.saved_start(title='Ready to open')
        self.waits_at(ready, 'gate:outline')
        engine = self.make(**running_check.PRODUCTION)
        self.workers.then('scan', self.scanner)
        with mock.patch.object(research_session, 'execution', return_value=running_check.COLLECTION):
            researched = self.start_desk(title='Researched', research=True, engine=engine)
        self.assertEqual(self.record(researched)['schema'], 6)
        self.assertEqual(self.preview(ready)['blockers'], [])
        # A record Presentation Studio does not write still stops every preview, and now
        # says which deck's folder holds it.
        refused = self.saved_start(title='No review level')
        record = self.record(refused)
        record['schema'] = 2
        record.pop('review_policy', None)
        decks.write_run(refused, record)
        self.assertEqual(self.preview(ready)['blockers'], [self.refused(refused)])
        self.waits_at(ready, 'gate:outline')    # it still continues in its saved flow

    def test_parallel_research_records_keep_their_saved_flow(self):
        root = self.saved_start(title='Parallel research', research=True)
        record = self.record(root)
        record.update(schema=4, research_contract={'schema': 2, 'version': '1.0.0', 'digest': '1' * 64},
                      research_execution={'schema': 1, 'protocol': research_session.PROTOCOL,
                                          'workers': 2, 'capability': {
                                              'protocol': research_session.PROTOCOL}})
        decks.write_run(root, record)
        # Its own reason: the migration's reader does not support schema 4.
        files = self.snapshot(root)
        self.assertEqual(desk_chat.prepare_migration(record, files)['blockers'],
                         ['This saved run format is not supported. Keep using its saved flow.'])
        # The engine writes schema 4, so the shared running-step check knows the deck and the
        # preview gives that reason alone (GitHub issue #541).
        self.assertEqual(self.preview(root)['blockers'],
                         ['This saved run format is not supported. Keep using its saved flow.'])
        self.waits_at(root, 'gate:research-plan')

    def test_a_missing_pinned_research_bundle_keeps_its_saved_flow(self):
        root = self.gated(title='Research pinned')
        record = self.record(root)
        record.update(schema=3, research_contract={'schema': 2, 'version': '1.0.0', 'digest': '1' * 64})
        record['steps']['research-report'] = {'done': True}
        decks.write_run(root, record)
        # The pinned bundle is read before anything else, and its absence is the one blocker.
        blockers = self.preview(root)['blockers']
        self.assertEqual(len(blockers), 1)
        self.assertIn('output.json', blockers[0])

    # --- records the runner cannot read ------------------------------------------------------

    def unleveled(self, title='Unleveled'):
        root = self.saved_start(title=title)
        record = self.record(root)
        record['schema'] = 2
        record.pop('review_policy', None)
        decks.write_run(root, record)
        return root

    def test_records_the_runner_refuses_open_as_read_only_records(self):
        corrupt = self.saved_start(title='Corrupt')
        (corrupt / 'run.json').write_text('{not json')
        unleveled = self.unleveled()
        # What the preview says of each: the record that cannot be parsed, its parser's
        # words; the one with no review level, the shared running-step check's refusal
        # naming its folder, as its own reason, the unsupported format, comes after it.
        self.assertEqual(self.preview(corrupt)['blockers'],
                         ['Expecting property name enclosed in double quotes: line 1 column 2 (char 1)'])
        self.assertEqual(self.preview(unleveled)['blockers'], [self.refused(unleveled)])
        self.assertEqual(desk_chat.prepare_migration(self.record(unleveled), self.snapshot(unleveled))['blockers'],
                         ['This saved run format is not supported. Keep using its saved flow.'])
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
        root = self.unleveled()
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
        root = self.gated(title='Interrupted')
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
        root = self.gated(title='Untouched')
        raw = (root / 'run.json').read_bytes()
        record = copy.deepcopy(json.loads(raw))
        self.preview(root)
        self.assertEqual((root / 'run.json').read_bytes(), raw)
        self.assertEqual(json.loads(raw), record)


class ReadOnlyRecordPageTests(test_runner_page.PageCase):
    """A read-only record through the page: its listed files are served, and nothing
    continues it."""

    def test_listed_files_are_served_and_act_decide_and_drive_refuse(self):
        root = self.saved_start(title='Unleveled')
        record = self.record(root)
        record['schema'] = 2
        record.pop('review_policy', None)
        decks.write_run(root, record)
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
