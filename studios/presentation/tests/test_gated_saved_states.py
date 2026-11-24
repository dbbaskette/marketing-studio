"""Every saved state the earlier gated flow leaves, in its original format, and what the
explicit migration says of each: opened on the desk, kept in its saved flow, or shown as a
read-only record. Each fixture is made by the real saved-run dispatch (`saved_start`, the
gates decided as a person decided them), never by the migration itself."""
import copy
import json

import runner_support
from runner import decks, desk_chat
from studio_core import research_session
from test_flow_routes import DECK

PASTE = {'kind': 'paste', 'text': 'Notes on rolling restarts.'}
UPLOAD = {'kind': 'upload', 'name': 'old.pptx'}
LEVELS = ('brand-only', 'polish', 'redesign', 'rework', 'selected')


class GatedSavedStateTests(runner_support.DeskCase):
    def snapshot(self, root):
        return {p.relative_to(root).as_posix(): p.read_bytes()
                for p in root.rglob('*') if p.is_file()}

    def preview(self, root):
        before = self.snapshot(self.space.root)
        found = desk_chat.migration_preview(self.engine, root)
        self.assertEqual(self.snapshot(self.space.root), before, 'a preview wrote')
        return found

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
                self.assertEqual(self.preview(root)['blockers'],
                                 ['A required shared Presentation Studio record cannot be read.'])
                self.assertIsNotNone(self.view(root)['gate'])   # it continues as it was saved

    def test_a_saved_worker_question_keeps_its_saved_flow(self):
        root = self.saved_start(title='Asked')
        record = self.record(root)
        record['question'] = {'id': 'q1', 'text': 'Which audience?', 'from': 'outline'}
        decks.write_run(root, record)
        self.assertEqual(self.preview(root)['blockers'], [
            'Resolve the saved runner question in its saved flow before opening it on the desk.'])
        self.assertEqual(self.view(root)['question']['id'], 'q1')

    def test_a_paused_run_is_not_opened_on_the_desk_yet(self):
        root = self.gated(title='Paused')
        record = self.record(root)
        record['halted'] = {'state': 'paused', 'step': 'build-render', 'why': 'You paused it.',
                            'kept': '', 'action': 'resume', 'at': '2026-01-01T00:00:00+00:00'}
        decks.write_run(root, record)
        self.assertEqual(self.preview(root)['blockers'], [
            'This saved runner stop cannot be interpreted. Continue with its saved flow first.'])
        self.assertEqual(self.view(root)['state'], 'paused')

    def test_parallel_research_records_keep_their_saved_flow(self):
        root = self.saved_start(title='Parallel research', research=True)
        record = self.record(root)
        record.update(schema=4, research_contract={'schema': 2, 'version': '1.0.0', 'digest': '1' * 64},
                      research_execution={'schema': 1, 'protocol': research_session.PROTOCOL,
                                          'workers': 2, 'capability': {
                                              'protocol': research_session.PROTOCOL}})
        decks.write_run(root, record)
        # The shared worker scan reads only schemas 1 to 3 as Presentation Studio records, so
        # it cannot vouch for this workspace; the migration's own reader refuses schema 4 too.
        self.assertEqual(self.preview(root)['blockers'], [
            'The repository could not be checked for running Studio steps. Check its saved '
            'worker records and folder permissions, then share again.'])
        from runner import desk_migration
        self.assertFalse(desk_migration.format.supported(record))
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

    def test_records_the_runner_refuses_cannot_be_opened_or_continued(self):
        corrupt = self.saved_start(title='Corrupt')
        (corrupt / 'run.json').write_text('{not json')
        unleveled = self.saved_start(title='Unleveled')
        record = self.record(unleveled)
        record['schema'] = 2
        record.pop('review_policy', None)
        decks.write_run(unleveled, record)
        for root in (corrupt, unleveled):
            with self.subTest(root.name):
                self.assertTrue(self.preview(root)['blockers'])
                with self.assertRaises(desk_chat.WorkspaceError):
                    self.view(root)

    def test_a_preview_never_rewrites_the_original_record(self):
        root = self.gated(title='Untouched')
        raw = (root / 'run.json').read_bytes()
        record = copy.deepcopy(json.loads(raw))
        self.preview(root)
        self.assertEqual((root / 'run.json').read_bytes(), raw)
        self.assertEqual(json.loads(raw), record)
