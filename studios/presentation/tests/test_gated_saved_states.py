"""Every saved state the earlier gated flow leaves, in its original format, and what becomes
of each now that nothing continues it (GitHub issue #542): opened on the desk, waiting for what
stops that to clear, or shown as a read-only record. Each deck is loaded from tests/fixtures/saved/ (`load_saved`): the
files the real saved-run dispatch wrote for that state, captured by tests/saved_fixtures.py
and checked against the flow by tests/test_saved_fixtures.py. Where the stand-ins cannot
reach a saved shape (an unreadable record), the capture edited the record the dispatch
saved, and saved_fixtures.EDITED names those states. Only the pause taken while a
step works runs the saved flow here: what it tests is the running step itself."""
import copy
import json
from pathlib import Path
from unittest import mock

import runner_support
import saved_fixtures
import test_desk_page
import test_runner_page
from runner import decks, desk, desk_chat, desk_migration
from studio_core.sync_guard import SYNC_WAIT
from studio_core import research_session, sync_guard
import test_running_check_records as running_check

LEVELS = ('brand-only', 'polish', 'redesign', 'rework', 'selected')
NOTHING = ('research-plan', 'research', 'document-classify', 'question-early', 'parallel-research',
           *('existing-' + level for level in LEVELS[:-1]))
MIGRATES = ('outline', 'document-outline', 'look', 'build', 'balanced', 'selected',
            'selected-automatic', 'paused', 'failed', 'question', 'researched',
            'researched-parallel')
# What the migration adds to the effective record, or changes in it: everything else of the
# original record is kept exactly.
MIGRATION_KEYS = {'flow', 'execution', 'conversation_scope', 'unfinished_migration',
                  'halted', 'migration_saved_status', 'question', 'migration_saved_question'}
USE_DESK = 'Use this deck’s existing desk or finished Open on the desk action.'
METADATA = 'This deck already has desk metadata or pending recovery.'
UNSUPPORTED = 'This saved run format is not supported.'

# What becomes of each stored state (`desk_migration.outcome`): migrates through the
# migration or the finished Open on the desk, or a read-only record with its reason.
OUTCOMES = {
    **dict.fromkeys(MIGRATES, 'migration'),
    **dict.fromkeys(('delivered', 'delivered-pptx', 'delivered-balanced', 'delivered-automatic',
                     'delivered-document-balanced', 'delivered-document-automatic',
                     'delivered-selected'), 'finished'),
    **dict.fromkeys(NOTHING, desk_migration.NOTHING_MADE),
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
        """The stop its saved flow left is kept in its record; the page shows a saved record,
        never the stop (GitHub issue #542)."""
        self.assertEqual(self.record(root)['gates'][gate]['state'], 'waiting')
        shown = self.view(root)
        self.assertIsNone(shown['gate'])
        self.assertEqual(shown['state'], 'saved')

    def checked(self, root):
        """What becomes of a saved deck, as its screen asks when it opens (`saved_check`)."""
        return self.engine.saved_check(root)

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

    def test_every_saved_state_is_a_saved_record_that_nothing_continues(self):
        # GitHub issue #542: the page shows each one as a saved record in its outcome's state,
        # never a stop to decide, a question to answer or a problem to try again; the routes
        # that continued it refuse, naming its two ways on; and a list says how it stands.
        states = {'migration': 'migrates', 'finished': 'finished'}
        for state, expected in OUTCOMES.items():
            with self.subTest(state):
                root = self.load_saved(state)
                before = self.snapshot(self.space.root)
                shown = self.checked(root)
                saved = shown['saved_record']
                self.assertEqual(saved['state'], states.get(expected, 'read-only'))
                self.assertEqual((shown['gate'], shown['desk']), (None, None))
                self.assertIsNone(shown.get('question'))
                self.assertIsNone(shown.get('problem'))
                self.assertTrue(saved['files'])
                if saved['state'] == 'read-only' and state not in saved_fixtures.EDITED:
                    # (A record the runner refuses gives the runner's refusal as its reason.)
                    self.assertEqual(saved['why'], expected)
                if saved['state'] == 'migrates':
                    self.assertEqual(saved['waiting'], [])
                    self.assertIn('Original files, History, source and guidance pins, Google '
                                  'records and earlier decisions', saved['retained'])
                if state == 'corrupt':
                    continue        # its record cannot be read: the runner refuses it first
                for ask in (lambda: self.engine.act(root, 'resume'),
                            lambda: self.engine.act(root, 'retry'),
                            lambda: self.engine.answer(root, 'q1', 'An answer.'),
                            lambda: self.engine.decide(root, 'gate:outline', 'approve')):
                    with self.assertRaises(desk_chat.WorkspaceError) as refused:
                        ask()
                    if state != 'unleveled':
                        self.assertEqual(str(refused.exception), self.engines.SAVED_FLOW_ENDED)
                # The desk's own routes are for desk work: they refuse it with their sentence.
                with self.assertRaises(desk_chat.WorkspaceError) as refused:
                    self.engine.desk_stop(root)
                if state != 'unleveled':
                    self.assertEqual(str(refused.exception), desk.NOT_ON_DESK)
                self.assertEqual(self.snapshot(self.space.root), before)
        listed = {brief['id']: brief for kind in self.engine.decks().values() for brief in kind}
        self.assertEqual(listed['unleveled']['title'], 'Unleveled')
        self.assertEqual(listed['unleveled']['sentence'], 'Read-only: This run is missing its '
                         'saved review level. Restore its run record.')
        self.assertEqual(listed['corrupt']['state'], 'saved')
        for brief in listed.values():
            # A list says what a current check found, or only that the earlier flow saved it.
            if brief.get('saved') in ('migrates', 'unchecked', 'waiting'):
                self.assertEqual(brief['sentence'], self.engines.SAVED_SAYS[brief['saved']])
            elif brief['state'] != 'finished':
                self.assertTrue(brief['sentence'].startswith('Read-only: '), brief)

    def test_a_saved_deck_that_waits_says_what_for_and_what_clears_it(self):
        # A step in hand ends by itself; a record elsewhere in the workspace that cannot be
        # understood is cleared by nothing in the studio, so new work may start from it.
        root = self.load_saved('build', title='Waits')
        with mock.patch.object(desk_migration, 'worker_in_progress', return_value=True):
            saved = self.checked(root)['saved_record']
        # A step in hand nowhere this computer can see: it ends by itself; check again then.
        self.assertEqual((saved['state'], saved['waiting'], saved['action']),
                         ('waiting', [SYNC_WAIT], 'check'))
        refused = self.load_saved('unleveled', title='No review level')
        saved = self.checked(root)['saved_record']
        self.assertEqual((saved['state'], saved['waiting'], saved['action']),
                         ('waiting', [self.refused(refused)], 'copy'))
        self.assertEqual(saved['next'], 'copy')

    def test_the_runners_refusal_is_the_read_only_reason(self):
        root = self.load_saved('unleveled')
        with self.assertRaises(desk_chat.WorkspaceError) as refused:
            self.engine._load(root)
        found = desk_migration.outcome(self.record(root), desk_chat._files(root), refused.exception)
        self.assertEqual((found['outcome'], found['why'], found['next']),
                         ('read-only', str(refused.exception), 'copy'))
        self.assertEqual(self.view(root)['saved_record']['why'], found['why'])

    def test_desk_work_is_never_a_saved_flow_outcome(self):
        # Defect 1: desk work, at any schema (a newer version's too), and a deck with desk
        # metadata, a receipt or a pending opening, is desk work, whatever else is said.
        root = self.load_saved('build')
        files = desk_chat._files(root)
        record = self.record(root)
        refusal = desk_chat.WorkspaceError('The runner will not drive this deck.')
        for schema in (3, 6, 99):
            on_desk = {**record, 'flow': 'desk', 'schema': schema}
            shaped = {**files, 'run.json': json.dumps(on_desk).encode()}
            for given in (None, refusal):
                with self.subTest(schema=schema, refusal=given is not None):
                    self.assertEqual(desk_migration.outcome(on_desk, shaped, given)['outcome'], 'desk')
        for name in (desk_migration.format.RECORD, desk_migration.format.ORIGIN,
                     desk_migration.format.PENDING):
            for given in (None, refusal):
                with self.subTest(name=name, refusal=given is not None):
                    found = desk_migration.outcome(record, {**files, name: b'{}'}, given)
                    self.assertEqual(found['outcome'], 'desk')
        # A record nobody can read: the neutral reason, which names no flow, and a new deck.
        for given in (None, refusal):
            with self.subTest(unreadable=True, refusal=given is not None):
                found = desk_migration.outcome(None, {**files, 'run.json': b'{oops'})
                self.assertEqual((found['outcome'], found['why'], found['next']),
                                 ('read-only', desk_migration.UNREAD, 'new'))
                self.assertNotIn('step-by-step', found['why'])
                self.assertNotIn('earlier', found['why'])

    def test_finished_and_opened_decks_keep_their_preview_sentences(self):
        # Defect 2: a delivered deck or one with desk metadata is told what it always was,
        # even when its saved runner stop cannot be read; the finished Open on the desk
        # reads no stop, so the delivered deck still opens through it.
        delivered = self.load_saved('delivered')
        record = {**self.record(delivered), 'halted': 'not a stop'}
        files = {**desk_chat._files(delivered), 'run.json': json.dumps(record).encode()}
        self.assertEqual(desk_chat.prepare_migration(record, files)['blockers'], [USE_DESK])
        found = desk_migration.outcome(record, files)
        self.assertEqual((found['outcome'], found['by']), ('migrates', 'finished'))
        build = self.load_saved('build')
        record = {**self.record(build), 'halted': 'not a stop'}
        files = {**desk_chat._files(build), 'run.json': json.dumps(record).encode(),
                 desk_migration.format.PENDING: b'{}'}
        self.assertEqual(desk_chat.prepare_migration(record, files)['blockers'], [METADATA])
        self.assertEqual(desk_migration.outcome(record, files)['outcome'], 'desk')

    def test_a_missing_dependency_is_a_read_only_reason_in_plain_words(self):
        # Defect 8: what is missing, and where it can be opened, without internal names.
        root = self.load_saved('selected')
        original = (root / 'sources/original.pptx').read_bytes()
        (root / 'sources/original.pptx').unlink()
        found = self.outcome_of(root)
        self.assertEqual((found['outcome'], found['why']), ('read-only', desk_migration.NOT_HERE))
        self.assertEqual(found['preview'], desk_migration.NOT_HERE)
        (root / 'sources/original.pptx').write_bytes(b'not a deck')
        self.assertEqual(self.outcome_of(root)['why'], desk_migration.UNREADABLE_DECK)
        (root / 'sources/original.pptx').write_bytes(original)
        inventory = (root / 'classify.json').read_bytes()
        (root / 'classify.json').unlink()    # stopped before the deck given was read
        found = self.outcome_of(root)
        self.assertEqual(found['why'], desk_migration.NOTHING_READ)
        self.assertEqual(found['preview'], desk_migration.NOTHING_READ)
        (root / 'classify.json').write_bytes(inventory)
        build = self.load_saved('build', title='Unreadable drawing')
        (build / 'work/build/state.json').write_text('[]')
        found = self.outcome_of(build)
        self.assertEqual(found['why'], desk_migration.UNREADABLE_DRAWING)
        self.assertEqual(found['preview'], desk_migration.UNREADABLE_DRAWING)
        for said in (desk_migration.NOT_HERE, desk_migration.UNREADABLE_DECK,
                     desk_migration.NOTHING_READ, desk_migration.UNREADABLE_DRAWING):
            self.assertNotIn('.json', said)
            self.assertNotIn('.pptx', said)

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
        """Open `root` on the desk; assert every original byte is kept, the effective record
        is the original one but for exactly the keys the migration adds or changes
        (MIGRATION_KEYS), and nothing is approved, marked ready or delivered."""
        before, record = self.snapshot(root), self.record(root)
        found = self.preview(root)
        self.assertEqual(found['blockers'], [])
        with mock.patch.object(self.engine, 'wake', side_effect=AssertionError('resumed')), \
                mock.patch.object(self.engine, 'ready', side_effect=AssertionError('readiness')):
            shown = desk_chat.migrate(self.engine, root, found['expected'])
        for name, data in before.items():
            self.assertEqual((root / name).read_bytes(), data, name)
        effective = decks.read_run(root)
        self.assertEqual({key: value for key, value in effective.items() if key not in MIGRATION_KEYS},
                         {key: value for key, value in record.items() if key not in MIGRATION_KEYS})
        self.assertEqual((effective['flow'], effective['execution'], effective['conversation_scope'],
                          effective['unfinished_migration']), ('desk', 'conversation', ['part'], True))
        self.assertEqual(effective.get('migration_saved_status'), record.get('halted') or None)
        self.assertEqual(effective.get('migration_saved_question'), record.get('question') or None)
        self.assertFalse(effective.get('halted'))
        self.assertFalse(effective.get('question'))
        # Nothing invented: no approval, no Ready mark, no delivery.
        self.assertEqual(shown['execution'], 'conversation')
        self.assertFalse(shown['desk']['ready'])
        self.assertIsNone(shown['deliver'])
        self.assertFalse((root / 'deliver.json').exists())
        self.assertNotIn('ready', effective.get('desk') or {})
        return found, record, effective, shown

    def test_every_migrating_state_opens_losslessly(self):
        # Defect 5: the whole record, for every state that migrates.
        for state in MIGRATES:
            with self.subTest(state):
                self.opened_losslessly(self.load_saved(state))

    def test_researched_decks_open_with_their_research_byte_for_byte(self):
        from studio_core import research_contract
        for state, schema in (('researched', 3), ('researched-parallel', 4)):
            with self.subTest(state):
                root = self.load_saved(state)
                record = self.record(root)
                self.assertEqual(record['schema'], schema)
                self.assertTrue(record['steps']['research-report']['done'])
                self.assertEqual(record['research_contract']['schema'], 2)
                if schema == 4:
                    self.assertTrue(research_session.protocol(record))
                research = {name: data for name, data in self.snapshot(root).items()
                            if name.startswith(('research/', '.studio-research/', 'sources/'))}
                self.assertIn('research/output.json', research)
                pinned = research_contract.read_bundle(root / 'research')
                found, record, effective, shown = self.opened_losslessly(root)
                # The bundle, its sources and the helper's own records are as the run left them,
                # and the contract and the execution record are the ones it pinned.
                for name, data in research.items():
                    self.assertEqual((root / name).read_bytes(), data, name)
                self.assertEqual(research_contract.read_bundle(root / 'research'), pinned)
                self.assertEqual(effective['research_contract'], record['research_contract'])
                self.assertEqual(effective.get('research_execution'), record.get('research_execution'))

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

    # --- states that are read-only records ---------------------------------------------------

    def test_stops_before_an_outline_are_read_only_records(self):
        for state in NOTHING:
            with self.subTest(state):
                root = self.load_saved(state)
                why = desk_migration.NOTHING_MADE
                self.assertEqual(self.preview(root)['blockers'], [why])
                shown = self.checked(root)
                # Read-only: no stop, no question to answer, nothing to continue.
                self.assertIsNone(shown['gate'])
                self.assertIsNone(shown['question'])
                self.assertEqual(shown['saved_record']['state'], 'read-only')
                self.assertEqual(shown['saved_record']['why'], why)
                self.assertEqual(shown['saved_record']['next'], 'copy')

    def test_a_pause_taken_mid_step_then_opens_losslessly(self):
        root = self.load_saved('paused')
        # The step ended: the pause is what the runner saved, with the outline it made.
        record = self.record(root)
        halted = record['halted']
        self.assertEqual((halted['state'], halted['step'], halted['why']),
                         ('paused', None, 'Paused on the page.'))
        self.assertTrue(record['steps']['outline']['done'])
        self.assertFalse((root / self.engines.IN_HAND).exists())
        self.assertEqual(self.checked(root)['saved_record']['state'], 'migrates')
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
        self.waits_at(ready, 'gate:outline')    # its saved stop is kept as it was

    def test_parallel_research_opens_once_its_outline_is_drafted(self):
        # Schema 4: at its research plan nothing is made yet, and it is read-only; with its
        # research done and its outline drafted it opens on the desk.
        root = self.load_saved('parallel-research')
        self.assertEqual(self.record(root)['schema'], 4)
        self.assertEqual(self.preview(root)['blockers'], [desk_migration.NOTHING_MADE])
        self.waits_at(root, 'gate:research-plan')
        drafted = self.load_saved('researched-parallel')
        self.waits_at(drafted, 'gate:outline')
        self.assertEqual(self.preview(drafted)['blockers'], [])

    def test_a_missing_pinned_research_bundle_is_a_read_only_record(self):
        root = self.load_saved('build', title='Research pinned')
        record = self.record(root)
        record.update(schema=3, research_contract={'schema': 2, 'version': '1.0.0', 'digest': '1' * 64})
        record['steps']['research-report'] = {'done': True}
        decks.write_run(root, record)
        # The pinned bundle is read before anything else, and its absence is the one blocker.
        blockers = self.preview(root)['blockers']
        self.assertEqual(len(blockers), 1)
        self.assertIn('output.json', blockers[0])
        saved = self.checked(root)['saved_record']
        self.assertEqual((saved['state'], saved['why']),
                         ('read-only', 'The pinned research bundle is missing.'))

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
        # An interrupted opening is a waiting record that says so (the fix round's ruling 1).
        shown = self.view(root)
        self.assertEqual((shown['title'], shown['saved_record']['state'],
                          shown['saved_record']['action']), ('Interrupted', 'interrupted', 'finish'))
        self.assertIsNone(shown['gate'])
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


class SavedRecordScreenTests(test_desk_page.DeskPageCase):
    """GitHub issue #542: each saved state's screen says what is happening and offers its one
    way on, and never Continue, Try again, Answer or a stop to decide."""

    CONTINUING = ('Approve', 'Resume', 'Try again', 'Answer', 'Ask for changes',
                  'Change what they say')

    def screen(self, root, view=None) -> dict:
        path = str(root)
        view = view or self.post('saved-check', {'path': path})   # as the screen asks on opening
        shot = self.open_deck(path, view, [{'snapshot': 'saved'}])
        shot = shot['snapshots']['saved']
        for name in self.CONTINUING:
            self.assertNotIn(name, shot['buttons'])
        self.assertLayout(shot)
        return shot

    def test_a_deck_that_opens_on_the_desk_offers_it_as_its_one_filled_action(self):
        shot = self.screen(self.load_saved('question'))
        self.assertEqual(shot['filled'], ['Open on the desk'])
        self.assertIn('It continues on the desk: open it there to carry on.', shot['text'])
        self.assertIn('What opening it keeps', shot['text'])
        self.assertIn('A worker asked: “' + saved_fixtures.QUESTION + '”', shot['text'])
        self.assertIn('Read saved outline', shot['buttons'])

    def test_a_read_only_deck_offers_new_work_from_it(self):
        shot = self.screen(self.load_saved('research-plan'))
        self.assertEqual(shot['filled'], ['Start new work from this'])
        self.assertIn(desk_migration.NOTHING_MADE, shot['text'])
        self.assertNotIn('Open on the desk', shot['buttons'])

    def test_a_waiting_deck_says_what_it_waits_for(self):
        root = self.load_saved('build', title='Waits')
        with mock.patch.object(desk_migration, 'worker_in_progress', return_value=True):
            view = self.post('saved-check', {'path': str(root)})
        shot = self.screen(root, view)
        # A step in hand ends by itself: Check again is the one filled action (fix round).
        self.assertEqual(shot['filled'], ['Check again'])
        self.assertIn('What it waits for', shot['text'])
        self.assertIn(SYNC_WAIT, shot['text'])
        self.assertNotIn('Open on the desk', shot['buttons'])
        # Nothing in the studio clears a record elsewhere it cannot understand: new work
        # starts from this one meanwhile, as its one filled action.
        self.load_saved('unleveled', title='No review level')
        shot = self.screen(root)
        self.assertEqual(shot['filled'], ['Start new work from this'])


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
