"""Every stop the saved step-by-step Blog Studio flow leaves on disk, in its original format.

Each stop is a static fixture (saved_fixtures.py, fixtures/saved/) the saved flow itself wrote
(runner.create, submit, decide, the page's develop and Continue without research, the
runner's worker record) while it ran, kept as it wrote it; none is written as a desk record. For each stop the explicit migration preview is checked to change nothing and to
start nothing, and its one classification is pinned; a stop that migrates is applied and every
original byte, approval fact and publishing gap is checked; a stop that cannot be moved is
refused. The earlier flow continues none of them: the page shows each as a saved record (its
run view), and every way that flow continued a blog is refused with the two exits, Open on the
desk and new work from it. Only the manuscript editor's own runs still go on.
"""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
from contextlib import contextmanager
import json
from unittest.mock import patch

import blog_runner as runner
import desk_chat
import desk_migration
import saved_fixtures
from saved_fixtures import MANUSCRIPT, NOTES
import studio
from test_blog_runner import RunnerCase

# Stopped before an outline or draft: read-only, and new work can start from its start form.
EARLY = ('read-only', 'stopped before an outline or draft was saved', 'copy')


class SavedStateCase(RunnerCase):
    """A disposable workspace whose blogs are saved step-by-step runs."""

    def tree(self):
        """Every saved byte in the workspace; the write lock's own marker is not work."""
        return {
            str(path.relative_to(self.root)): path.read_bytes()
            for path in self.root.rglob('*')
            if path.is_file() and path.name != '.studio.lock'
        }

    @contextmanager
    def nothing_starts(self):
        with (
            patch.object(runner.Engine, 'start', side_effect=AssertionError('runner started')),
            patch('desk_jobs.begin', side_effect=AssertionError('desk job started')),
            patch('team_workspace.before', side_effect=AssertionError('fetched')),
        ):
            yield

    def preview(self, ident):
        """The preview, checked to change nothing anywhere in the workspace."""
        before = self.tree()
        with self.nothing_starts():
            shown = desk_chat.migration_preview(self.root, ident)
        self.assertEqual(self.tree(), before)
        return shown

    def saved(self, state):
        """One saved stop, loaded from its original-format fixture, as the saved flow shows it."""
        return runner.survey(self.root, saved_fixtures.load(self.root, state))

    def outcome(self, shown, outcome, reason, next_action=None):
        """The one classification of this saved blog, the same in the preview and classify,
        decided without changing anything."""
        self.assertEqual((shown['outcome'], shown['next']), (outcome, next_action), shown['reason'])
        self.assertRegex(shown['reason'], reason)
        before = self.tree()
        with self.nothing_starts():
            said = desk_migration.classify(self.root, shown['id'])
        self.assertEqual(self.tree(), before)
        self.assertEqual(said, {key: shown[key] for key in ('outcome', 'reason', 'next', 'start')})
        if next_action == 'copy':
            self.assertTrue(shown['start']['title'])
        else:
            self.assertIsNone(shown['start'])

    def refused(self, ident, words, outcome, errors=ValueError):
        """Not eligible, saying nothing was changed; applying changes nothing. `outcome` is
        (outcome, reason pattern, next action) as classify gives it."""
        directory = studio.inside(self.root, 'articles', ident)
        shown = self.preview(ident)
        self.assertFalse(shown['eligible'], shown)
        self.outcome(shown, *outcome)
        self.assertRegex(' '.join(shown['blockers']), words)
        self.assertEqual(shown['notice'], desk_migration.REFUSAL)
        before = self.tree()
        with self.nothing_starts(), self.assertRaises(errors):
            desk_chat.migrate(self.root, ident, shown['expected'] or 'bm1.' + 'x' * 43)
        self.assertEqual(self.tree(), before)
        self.assertFalse((directory / 'desk').exists())
        return shown

    def record(self, ident, outcome, next_action=None):
        """The page's saved record of this blog (its run view), read without changing or
        starting anything, with its outcome and its next action."""
        import management

        before = self.tree()
        with self.nothing_starts():
            shown = management.view(self.root, 'run', {'id': [ident]})
        self.assertEqual(self.tree(), before)
        saved = shown['saved_record']
        self.assertEqual((saved['outcome'], saved['next']), (outcome, next_action), saved['why'])
        return shown

    def page(self, found, action, **data):
        """One of the page's run actions for a saved blog (Resume, Approve, Ask for changes)."""
        with studio.locked(self.root):
            return runner.dispatch(
                self.root, action, {'id': found['id'], 'expected': found['expected'], **data}
            )

    def chat(self, found, *command):
        """One of the command line's run commands for a saved blog (parsed as the CLI does)."""
        with patch('sys.stderr'):
            return self.command('run', *command, '--id', found['id'])

    def not_continued(self, ident, *attempts):
        """Each way the earlier flow continued this blog from the page is refused with the two
        exits, the command line has no run decision left to continue it, and its worker never
        starts a step: nothing in the workspace changes."""
        before = self.tree()
        for attempt in attempts:
            with self.nothing_starts(), self.assertRaisesRegex(ValueError, 'no longer continues'):
                attempt()
        for command in ('submit', 'approve', 'changes', 'handoff', 'choose'):
            with self.nothing_starts(), self.assertRaises(SystemExit):
                self.chat({'id': ident}, command)
        engine = runner.engine(self.root)
        with (
            self.nothing_starts(),
            patch.object(engine, 'worker', side_effect=AssertionError('step ran')),
        ):
            engine._once(ident)
        self.assertEqual(self.tree(), before)

    def migrates(self, ident):
        """Eligible; applied, every original byte stays and no approval is invented."""
        directory = studio.inside(self.root, 'articles', ident)
        shown = self.preview(ident)
        self.assertTrue(shown['eligible'], shown['blockers'])
        self.outcome(shown, 'migrates', 'can be opened on the writing desk')
        before = {
            name: raw
            for name, raw in self.tree().items()
            if name.startswith('articles/' + ident + '/')
        }
        run = json.loads(before['articles/' + ident + '/' + runner.STATE])
        if not runner.continues(run):
            # The page shows it as a saved record whose one action is Open on the desk.
            self.record(ident, 'migrates')
        with self.nothing_starts():
            result = desk_chat.migrate(self.root, ident, shown['expected'])
        for name, raw in before.items():
            self.assertEqual((self.root / name).read_bytes(), raw, name)
        meta = studio.read_json(directory / 'desk/migration.json')
        self.assertEqual(meta['historical_stages'], run['stages'])
        self.assertEqual(meta['historical_pipeline'], run['pipeline'])
        self.assertEqual(result['execution'], 'conversation')
        draft = studio.read_json(directory / 'desk/draft.json')
        self.assertIs(draft['unfinished_migration'], True)
        described = runner.engine(self.root).describe(ident)
        self.assertTrue(described['on_desk'])
        self.assertFalse(described['complete'])
        # Only stages the saved run approved read approved; nothing is approved for it.
        approved = {name for name, state in run['stages'].items() if state['status'] == 'approved'}
        self.assertEqual(
            {row['stage'] for row in described['stages'] if row['status'] == 'approved'}, approved
        )
        return result, meta, draft


class EarlyStopTests(SavedStateCase):
    """Stops before any usable manuscript or outline: read-only records, never continued."""

    def test_angles_not_yet_written_are_a_read_only_record(self):
        found = self.saved('angles-unwritten')
        self.refused(found['id'], 'no usable manuscript or supported outline', EARLY)
        self.assertEqual(self.record(found['id'], 'read-only', 'copy')['title'], found['title'])
        self.not_continued(
            found['id'],
            lambda: self.page(found, 'resume'),
        )

    def test_new_work_from_files_without_an_angle_carries_no_placeholder(self):
        # The run holds placeholders until an angle is chosen; they are not a point or audience.
        found = self.saved('angles-unwritten')
        directory, _, run = runner.load(self.root, found['id'])
        self.assertEqual(run['brief']['audience'], 'To be chosen with the angle.')
        said = desk_migration.classify(self.root, found['id'])
        # The person's own note about the files is carried; the audience placeholder is not.
        self.assertEqual(
            said['start'], {'title': found['title'], 'point': 'A post for the team blog'}
        )
        # Started with no note, the run's goal is a placeholder too: no point is carried.
        run['brief']['goal'] = 'Write a blog from the uploaded files.'
        studio.write_json(directory / runner.STATE, run)
        said = desk_migration.classify(self.root, found['id'])
        self.assertEqual(said['start'], {'title': found['title']})

    def test_angles_waiting_for_a_choice_are_a_read_only_record(self):
        found = self.saved('angles-waiting')
        self.refused(found['id'], 'no usable manuscript or supported outline', EARLY)
        self.record(found['id'], 'read-only', 'copy')

        self.not_continued(found['id'], lambda: self.page(found, 'approve'))

    def test_research_questions_gate_is_a_read_only_record(self):
        found = self.saved('research-questions')
        self.assertEqual((found['next'], found['awaits']), ('research-plan', 'decision'))
        self.refused(found['id'], 'no usable manuscript or supported outline', EARLY)
        self.record(found['id'], 'read-only', 'copy')
        self.not_continued(found['id'], lambda: self.page(found, 'approve'))

    def test_research_findings_stop_is_a_read_only_record(self):
        found = self.saved('research-findings')
        self.assertEqual((found['next'], found['awaits']), ('research', 'decision'))
        self.refused(found['id'], 'no usable manuscript or supported outline', EARLY)
        self.record(found['id'], 'read-only', 'copy')
        self.not_continued(found['id'], lambda: self.page(found, 'approve'))

    def test_claims_map_gate_is_a_read_only_record(self):
        found = self.saved('claims-map-gate')
        self.assertEqual(found['next'], 'claims-map')
        self.assertEqual(found['awaits'], 'decision')
        self.refused(found['id'], 'no usable manuscript or supported outline', EARLY)
        self.record(found['id'], 'read-only', 'copy')
        self.not_continued(found['id'], lambda: self.page(found, 'approve'))

    def test_brief_only_start_is_a_read_only_record(self):
        found = self.saved('brief-only')
        self.assertEqual((found['next'], found['awaits']), ('outline', 'submission'))
        self.refused(found['id'], 'no usable manuscript or supported outline', EARLY)
        self.record(found['id'], 'read-only', 'copy')
        self.not_continued(found['id'], lambda: self.page(found, 'resume'))


class MaterialStopTests(SavedStateCase):
    """Stops with a usable manuscript or heading outline migrate losslessly."""

    def test_outline_gate_migrates_with_its_briefs_and_no_prose(self):
        found = self.saved('outline-gate')
        self.assertEqual((found['next'], found['awaits']), ('outline', 'decision'))
        result, meta, draft = self.migrates(found['id'])
        self.assertEqual(meta['material'], 'outline')
        self.assertEqual([s['brief'] for s in draft['sections']], ['First brief.', 'Second brief.'])
        self.assertTrue(all(not s['text'] for s in draft['sections']))
        self.assertEqual(meta['historical_stages']['outline']['status'], 'draft')
        self.assertEqual(result['scope'], 'draft')

    def test_outline_approved_before_drafting_migrates(self):
        found = self.saved('outline-approved')
        self.assertEqual((found['next'], found['awaits']), ('draft', 'submission'))
        _, meta, _ = self.migrates(found['id'])
        self.assertEqual(meta['historical_stages']['outline']['accepted_by'], 'conversation')

    def test_draft_gate_migrates_with_the_saved_draft(self):
        found = self.saved('draft-gate')
        self.assertEqual((found['next'], found['awaits']), ('draft', 'decision'))
        result, meta, draft = self.migrates(found['id'])
        self.assertEqual(meta['material'], 'draft')
        self.assertEqual(draft['opening'], 'An opening.')
        self.assertEqual([s['text'] for s in draft['sections']], ['Saved words.', 'More words.'])
        self.assertEqual(meta['historical_stages']['outline']['accepted_by'], 'page')
        self.assertEqual(meta['historical_stages']['draft']['status'], 'draft')

    def test_review_gate_migrates(self):
        found = self.saved('review-gate')
        self.assertEqual((found['next'], found['awaits']), ('review', 'decision'))
        _, meta, _ = self.migrates(found['id'])
        self.assertEqual(meta['historical_stages']['draft']['status'], 'approved')

    def test_handoff_gate_migrates_and_keeps_every_publishing_gap_unresolved(self):
        found = self.saved('handoff-gate')
        self.assertEqual((found['next'], found['awaits']), ('package', 'decision'))
        _, _, draft = self.migrates(found['id'])
        self.assertEqual(draft['gaps'], ['Supply a release date.', 'Name the owner.'])

    def test_automatic_continuation_is_not_turned_into_approval(self):
        found = self.saved('balanced-draft')  # Saved at the Balanced review level.
        self.assertEqual(found['next'], 'review')
        _, meta, _ = self.migrates(found['id'])
        self.assertEqual(meta['historical_stages']['draft']['accepted_by'], 'review-policy')
        described = runner.engine(self.root).describe(found['id'])
        row = next(row for row in described['stages'] if row['stage'] == 'draft')
        self.assertTrue(row['auto_accepted'])

    def test_unstructured_outline_migrates_as_outline_notes_with_its_step_still_to_do(self):
        notes = NOTES
        found = self.saved('unstructured-outline')
        self.assertEqual((found['next'], found['awaits']), ('outline', 'decision'))
        result, meta, draft = self.migrates(found['id'])
        self.assertEqual((meta['material'], result['scope']), ('outline', 'draft'))
        # Every word is kept as the start's notes; no brief or prose is invented from them.
        self.assertEqual(
            (draft['opening'], draft['opening_brief'], draft['sections']), ('', '', [])
        )
        self.assertEqual(result['start']['notes'], notes)
        self.assertEqual(
            (result['start']['step'], result['start']['steps']), ('outline', ['outline', 'draft'])
        )
        # The desk page shows the kept notes, to shape the outline from.
        import desk_jobs

        self.assertEqual(desk_jobs.view(self.root, found['id'])['kept_notes'], notes)
        self.assertEqual(meta['historical_stages']['outline']['status'], 'draft')

    def test_approved_outline_notes_stay_approved_and_the_draft_is_next(self):
        found = self.saved('unstructured-outline-approved')
        self.assertEqual((found['next'], found['awaits']), ('draft', 'submission'))
        result, meta, draft = self.migrates(found['id'])
        # The person's real approval is kept; the finished outline step is not offered again.
        self.assertEqual(meta['historical_stages']['outline']['status'], 'approved')
        self.assertEqual((result['start']['step'], result['start']['steps']), ('draft', ['draft']))
        self.assertEqual(result['start']['notes'], NOTES)
        self.assertEqual(draft['sections'], [])
        context = desk_chat.context(self.root, found['id'], 'draft')
        self.assertEqual(context['scope'], 'draft')

    def test_failed_drafting_after_an_approved_outline_migrates_with_the_failure_kept(self):
        found = self.saved('outline-approved-failed')
        self.assertEqual((found['next'], found['awaits']), ('draft', 'submission'))
        local = self.root / '.blog-runs' / (found['id'] + '.json')
        kept = local.read_bytes()
        result, meta, _ = self.migrates(found['id'])
        # The failure stays in the run's history; the step stays unfinished; nothing retries it.
        self.assertEqual(local.read_bytes(), kept)
        self.assertNotIn('draft', meta['historical_stages'])
        self.assertEqual(result['start']['step'], 'draft')
        self.assertIsNone(result['start']['job'])
        described = runner.engine(self.root).describe(found['id'])
        self.assertEqual(described['error'], 'Synthetic failure.')

    def test_research_that_ran_moves_with_its_bundle_contract_and_execution_record(self):
        """A run whose research really ran with the pinned Harness Research stand-in, then
        drafted: the research bundle and the contract are kept byte for byte. (A schema 4 run
        whose parallel research ran cannot be a stable fixture: see saved_fixtures.py.)"""
        from studio_core import research_contract

        for state, schema in (('research-ran-schema3', 3),):
            with self.subTest(schema=schema):
                found = self.saved(state)
                directory, _, run = runner.load(self.root, found['id'])
                self.assertEqual(run['schema'], schema)
                self.assertEqual(run['stages']['research']['status'], 'approved')
                self.assertTrue(run['stages']['research'].get('hash'))
                self.assertEqual('research_execution' in run, schema == 4)
                research_contract.read_bundle(directory / 'research')
                bundle = {
                    str(p.relative_to(directory)): p.read_bytes()
                    for p in (directory / 'research').rglob('*')
                    if p.is_file()
                }
                self.assertTrue(bundle)
                result, meta, _ = self.migrates(found['id'])  # Every original byte is checked.
                self.assertEqual(meta['material'], 'draft')
                self.assertEqual(meta['historical_stages']['research']['status'], 'approved')
                kept = studio.read_json(directory / runner.STATE)
                self.assertEqual(kept['research_contract'], run['research_contract'])
                self.assertEqual(kept.get('research_execution'), run.get('research_execution'))
                for name, raw in bundle.items():
                    self.assertEqual((directory / name).read_bytes(), raw, name)

    def test_research_execution_run_migrates_with_its_record_kept(self):
        """A run saved with a research execution record (schema 4): its drafting reached a
        usable manuscript, and the record is kept with the run's bytes, uninterpreted."""
        found = self.saved('research-execution-drafted')
        self.assertEqual(runner.load(self.root, found['id'])[2]['schema'], 4)
        _, meta, _ = self.migrates(found['id'])
        self.assertEqual(meta['material'], 'draft')
        # The repository replay guard reads the moved blog as the domain reader does.
        from studio_core.sync_guard import worker_in_progress

        self.assertFalse(worker_in_progress(self.root))

    def test_finished_ideas_or_outline_migrate_with_outline_scope_only(self):
        for mode in ('ideas', 'outline'):
            with self.subTest(mode=mode):
                found = self.saved('finished-' + mode)
                self.assertTrue(found['complete'])
                # No DRAFT.md: there is no finished Open on the desk for it.
                self.assertFalse(runner.engine(self.root).describe(found['id'])['desk_open'])
                result, meta, draft = self.migrates(found['id'])
                self.assertEqual((meta['material'], result['scope']), ('outline', 'outline'))
                self.assertIsNone(result['start'])
                self.assertTrue(draft['sections'])
                self.assertTrue(all(not s['text'] for s in draft['sections']))

    def test_ideas_waiting_at_their_gate_migrate_with_outline_scope_only(self):
        found = self.saved('ideas-gate')
        self.assertEqual((found['next'], found['awaits']), ('outline', 'decision'))
        result, meta, _ = self.migrates(found['id'])
        self.assertEqual(result['scope'], 'outline')
        self.assertIsNone(result['start'])

    def test_author_outline_run_migrates_ready_to_draft(self):
        found = self.saved('author-outline')
        self.assertEqual((found['next'], found['awaits']), ('draft', 'submission'))
        result, meta, _ = self.migrates(found['id'])
        self.assertEqual((meta['material'], result['scope']), ('outline', 'draft'))

    def test_review_of_a_supplied_manuscript_migrates_with_part_scope(self):
        found = self.saved('review-supplied')
        self.assertEqual((found['next'], found['awaits']), ('review', 'decision'))
        result, meta, _ = self.migrates(found['id'])
        self.assertEqual(result['scope'], 'part')
        self.assertEqual(meta['material'], 'draft')

    def test_revision_of_a_supplied_manuscript_migrates(self):
        found = self.saved('revise-supplied')
        self.assertEqual((found['next'], found['awaits']), ('draft', 'submission'))
        result, _, _ = self.migrates(found['id'])
        self.assertEqual(result['scope'], 'draft')

    def test_continued_without_research_then_drafted_migrates(self):
        found = self.saved('skipped-research-drafted')
        _, meta, _ = self.migrates(found['id'])
        self.assertNotIn('research', meta['historical_pipeline'])

    def test_paused_stopped_and_failed_page_runs_migrate_with_their_worker_record(self):
        for status in ('paused', 'stopped', 'failed'):
            with self.subTest(status=status):
                found = self.saved('draft-gate-' + status)
                local = self.root / '.blog-runs' / (found['id'] + '.json')
                kept = local.read_bytes()
                self.migrates(found['id'])
                self.assertEqual(local.read_bytes(), kept)

    def test_a_paused_review_the_manuscript_editor_made_migrates(self):
        import manuscript_editor

        ident = self.article(MANUSCRIPT)
        shown = manuscript_editor.read(self.root, ident)
        with studio.locked(self.root), patch.object(runner.Engine, 'control', return_value={}):
            manuscript_editor.dispatch(
                self.root,
                'check',
                {'id': ident, 'expected': shown['expected'], 'check': 'proofread'},
            )
        runner.engine(self.root).keep_local(ident, {'enabled': False, 'status': 'paused'})
        found = runner.survey(self.root, ident)
        self.assertEqual((found['next'], found['editor_check']), ('review', 'proofread'))
        result, meta, _ = self.migrates(ident)
        self.assertEqual((meta['material'], result['scope']), ('draft', 'part'))


class KeptStopTests(SavedStateCase):
    """Saved stops that cannot be moved today, and why."""

    def test_finished_blog_keeps_the_finished_open_on_the_desk_action(self):
        found = self.saved('finished-chat')
        self.assertTrue(found['complete'])
        self.refused(found['id'], 'already finished', ('finished', 'already finished'))
        self.assertTrue(runner.engine(self.root).describe(found['id'])['desk_open'])
        # Its saved record carries the run as it ended, for its Done card and Open on the desk.
        shown = self.record(found['id'], 'finished')
        self.assertTrue(shown['desk_open'])
        self.assertTrue(shown['complete'])
        self.not_continued(
            found['id'],
            lambda: self.page(found, 'changes', request='Tighter.', stage='draft'),
        )

    def test_a_queued_or_working_marker_nothing_runs_is_idle_and_a_running_step_waits(self):
        for status in ('queued', 'working'):
            with self.subTest(status=status):
                found = self.saved('draft-gate-' + status)
                local = self.root / '.blog-runs' / (found['id'] + '.json')
                kept = local.read_bytes()
                # No runner picks the marker up again: it is idle, and the blog opens on the
                # desk by what it holds. Reading it writes nothing.
                self.record(found['id'], 'migrates')
                self.not_continued(found['id'], lambda found=found: self.page(found, 'resume'))
                self.assertEqual(local.read_bytes(), kept)
                # Only a step running now waits, and Stop ends it.
                engine = runner.engine(self.root)
                engine.current = found['id']
                try:
                    self.refused(found['id'], 'under way', ('wait', 'under way'))
                    shown = self.record(found['id'], 'wait')
                    self.assertEqual(shown['saved_record']['clear'], 'stop')
                    with studio.locked(self.root):
                        runner.dispatch(
                            self.root, 'stop', {'id': found['id'], 'expected': shown['expected']}
                        )
                    self.assertTrue(engine.stop.is_set())
                finally:
                    engine.current = None
                    engine.stop.clear()
                self.assertEqual(
                    desk_migration.classify(self.root, found['id'])['outcome'], 'migrates'
                )

    def test_a_gate_the_page_worker_left_is_idle_and_opens_on_the_desk(self):
        found = self.saved('draft-gate-paused')
        local = self.root / '.blog-runs' / (found['id'] + '.json')
        # The page worker's own marker once it saved a stage: still enabled, at the gate.
        studio.write_json(
            local,
            {
                'enabled': True,
                'status': 'waiting-for-approval',
                'error': '',
                'reason': None,
                'started_at': '2026-01-05T09:30:00+00:00',
                'jobs': [{'stage': 'draft', 'seconds': 1.0, 'tokens': None, 'dollars': None}],
            },
        )
        kept = local.read_bytes()
        shown = self.record(found['id'], 'migrates')
        self.assertEqual(shown['status'], 'migrates')
        self.migrates(found['id'])
        self.assertEqual(local.read_bytes(), kept)

    def test_nothing_made_is_read_only_whatever_its_workspace_waits_on(self):
        found = self.saved('brief-only')
        # An older Team Hub connection of the workspace, and a step of the blog running now.
        studio.write_json(self.root / '.team-hub.json', {'schema': 1})
        said = desk_migration.classify(self.root, found['id'])
        self.assertEqual((said['outcome'], said['next']), EARLY[::2])
        self.assertRegex(said['reason'], EARLY[1])
        (self.root / '.team-hub.json').unlink()
        engine = runner.engine(self.root)
        engine.current = found['id']
        try:
            self.record(found['id'], 'read-only', 'copy')
        finally:
            engine.current = None

    def test_unreadable_run_or_session_record_keeps_every_file(self):
        for name in (runner.STATE, 'session.json'):
            with self.subTest(record=name):
                found = self.saved('draft-gate-chat')
                directory = studio.inside(self.root, 'articles', found['id'])
                (directory / name).write_text('{not json')
                # The preview says the record cannot be read (today in the JSON reader's
                # own words) and offers no token; nothing can drive or move it until restored.
                said = {
                    runner.STATE: ('read-only', 'run record cannot be read', 'copy'),
                    'session.json': ('read-only', 'blog record cannot be read', 'new'),
                }[name]
                shown = self.refused(found['id'], 'line 1', said)
                self.assertEqual(shown['expected'], '')
                self.record(found['id'], 'read-only', said[2])
                self.assertEqual((directory / 'DRAFT.md').read_text(), MANUSCRIPT)
                self.assertEqual((directory / name).read_text(), '{not json')

    def test_unsupported_run_schema_is_a_read_only_record(self):
        found = self.saved('draft-gate-chat')
        directory = studio.inside(self.root, 'articles', found['id'])
        run = studio.read_json(directory / runner.STATE)
        run['schema'] = 99
        studio.write_json(directory / runner.STATE, run)
        self.refused(
            found['id'],
            'supported saved Blog Studio run',
            ('read-only', 'newer Blog Studio runtime', 'copy'),
        )
        self.record(found['id'], 'read-only', 'copy')

    def test_registered_manuscript_without_a_run_keeps_the_editor_exception(self):
        ident = self.article(MANUSCRIPT)
        self.assertFalse((studio.inside(self.root, 'articles', ident) / runner.STATE).exists())
        # The preview and applying it give the same refusal sentence, and write nothing.
        shown = self.refused(
            ident, 'no saved step-by-step run', ('current', 'no saved step-by-step run')
        )
        with self.assertRaisesRegex(ValueError, 'no saved step-by-step run'):
            desk_chat.migrate(self.root, ident, shown['expected'] or 'bm1.' + 'x' * 43)


class ReadOnlyRecordTests(SavedStateCase):
    """The page's saved records: read-only, and waiting on something that can clear."""

    def run_view(self, ident):
        import management

        before = self.tree()
        with self.nothing_starts():
            shown = management.view(self.root, 'run', {'id': [ident]})
        self.assertEqual(self.tree(), before)
        return shown

    def test_a_record_the_run_screen_refuses_opens_read_only_with_its_files(self):
        import management

        for name, sentence, start in (
            (runner.STATE, desk_migration.SAVED_RECORD, 'copy'),
            ('session.json', desk_migration.UNREAD_RECORD, 'new'),
        ):
            with self.subTest(record=name):
                found = self.saved('draft-gate-chat')
                directory = studio.inside(self.root, 'articles', found['id'])
                (directory / name).write_text('{not json')
                shown = self.run_view(found['id'])
                self.assertEqual((shown['status'], shown['sentence']), ('read-only', sentence))
                saved = shown['saved_record']
                self.assertEqual(saved['files'], ['DRAFT.md', 'OUTLINE.md'])
                self.assertEqual(saved['next'], start)
                self.assertIn('cannot be read', saved['why'])
                if start == 'copy':
                    # The run cannot be read, so only the blog's own title starts new work.
                    self.assertEqual(shown['title'], 'Synthetic gateway guide')
                    self.assertEqual(saved['start'], {'title': 'Synthetic gateway guide'})
                read = management.view(
                    self.root, 'saved-file', {'id': [found['id']], 'name': ['DRAFT.md']}
                )
                self.assertEqual((read['text'], read['truncated']), (MANUSCRIPT, False))

    def test_saved_files_are_read_only_in_place_and_never_through_a_link(self):
        import management

        found = self.saved('draft-gate-chat')
        directory = studio.inside(self.root, 'articles', found['id'])
        (directory / runner.STATE).write_text('{not json')
        outside = self.base / 'outside.md'
        outside.write_text('Not this blog’s file.')
        (directory / 'OUTLINE.md').unlink()
        (directory / 'OUTLINE.md').symlink_to(outside)
        self.assertEqual(self.run_view(found['id'])['saved_record']['files'], ['DRAFT.md'])
        for name in ('OUTLINE.md', 'session.json', '../../hub.json', 'derived/blog-run.json'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'saved file'):
                management.view(self.root, 'saved-file', {'id': [found['id']], 'name': [name]})

    def test_an_unsupported_run_is_read_only_and_says_why(self):
        found = self.saved('draft-gate-chat')
        directory = studio.inside(self.root, 'articles', found['id'])
        run = studio.read_json(directory / runner.STATE)
        run['schema'] = 99
        studio.write_json(directory / runner.STATE, run)
        shown = self.run_view(found['id'])
        self.assertIn('newer Blog Studio runtime', shown['saved_record']['why'])
        # Its start form reads: new work starts from its title, point and audience.
        self.assertEqual(
            shown['saved_record']['start'],
            {
                'title': 'Synthetic gateway guide',
                'point': 'Explain a fictional gateway',
                'audience': 'New authors',
            },
        )

    def test_a_record_the_run_screen_reads_is_a_saved_record_too(self):
        # A brief-only start is readable, and still a read-only record: the earlier flow does
        # not continue it, so its run screen and its Continue are gone.
        found = self.saved('brief-only')
        self.assertEqual(desk_migration.classify(self.root, found['id'])['outcome'], 'read-only')
        shown = self.run_view(found['id'])
        self.assertEqual(shown['saved_record']['outcome'], 'read-only')
        self.assertNotIn('next', shown)
        self.assertEqual(shown['saved_record']['files'], [])

    def test_lists_say_what_the_small_records_prove(self):
        """A list (polled on Home and Blogs) reads only a saved blog's session and run records:
        saved by the earlier flow, finished there, or cannot be read. What becomes of it is
        decided when its record is opened."""
        import desk_migration as migration

        made = {
            state: saved_fixtures.load(self.root, state)
            for state in ('brief-only', 'outline-gate', 'finished-chat', 'draft-gate-queued')
        }
        unread = saved_fixtures.load(self.root, 'draft-gate-chat')
        (self.root / 'articles' / unread / runner.STATE).write_text('{not json')
        # Its material files cannot even be opened: a list never reads them.
        material = [
            path
            for ident in [*made.values(), unread]
            for path in (self.root / 'articles' / ident).glob('*.md')
        ]
        for path in material:
            path.chmod(0)
        self.addCleanup(lambda: [path.chmod(0o644) for path in material])

        def small():
            return {
                str(path.relative_to(self.root)): path.read_bytes()
                for path in self.root.rglob('*')
                if path.is_file() and path.suffix != '.md' and path.name != '.studio.lock'
            }

        before = small()
        heavy = AssertionError('a list read more than the small records')
        with (
            self.nothing_starts(),
            patch.object(migration, 'migration_preview', side_effect=heavy),
            patch.object(runner, 'inputs', side_effect=heavy),
            patch.object(runner, 'survey', side_effect=heavy),
            patch.object(studio, 'artifact_fingerprint', side_effect=heavy),
        ):
            rows = {row['id']: row for row in runner.catalog(self.root)['items']}
        self.assertEqual(small(), before)
        for path in material:
            path.chmod(0o644)
        said = {state: rows[ident]['saved'] for state, ident in made.items()}
        self.assertEqual(
            said,
            {
                'brief-only': 'saved',
                'outline-gate': 'saved',
                'finished-chat': 'finished',
                'draft-gate-queued': 'saved',
            },
        )
        self.assertEqual((rows[unread]['saved'], rows[unread]['status']), ('unreadable', 'saved'))
        for ident in made.values():
            # Never a run waiting on a decision, and no step's error line in a list.
            self.assertEqual((rows[ident]['status'], rows[ident]['error']), ('saved', ''))
        self.assertTrue(rows[made['finished-chat']]['complete'])

    def test_the_board_says_a_saved_blog_is_a_saved_record(self):
        import editorial

        found = self.saved('draft-gate-paused')
        directory = studio.inside(self.root, 'articles', found['id'])
        session = (directory / 'session.json').read_bytes()
        row = next(
            row for row in editorial.board(self.root)['items'] if row.get('id') == found['id']
        )
        self.assertEqual(row['next_step'], desk_migration.BOARD_WORDS)
        self.assertEqual((directory / 'session.json').read_bytes(), session)  # Not rewritten.

    def test_the_editors_check_is_no_side_door_into_an_unfinished_saved_run(self):
        import manuscript_editor

        found = self.saved('draft-gate-paused')
        shown = manuscript_editor.read(self.root, found['id'])
        before = self.tree()
        with (
            self.nothing_starts(),
            studio.locked(self.root),
            self.assertRaisesRegex(ValueError, 'no longer continues'),
        ):
            manuscript_editor.dispatch(
                self.root,
                'check',
                {'id': found['id'], 'expected': shown['expected'], 'check': 'proofread'},
            )
        self.assertEqual(self.tree(), before)
        # A finished blog keeps the editor, as it always had: the check makes its own run.
        found = self.saved('finished-page')
        shown = manuscript_editor.read(self.root, found['id'])
        with studio.locked(self.root), patch.object(runner.Engine, 'control', return_value={}):
            manuscript_editor.dispatch(
                self.root,
                'check',
                {'id': found['id'], 'expected': shown['expected'], 'check': 'proofread'},
            )
        self.assertEqual(runner.survey(self.root, found['id'])['editor_check'], 'proofread')

    def test_an_interrupted_opening_waits_with_the_way_to_finish_it(self):
        import management

        found = self.saved('draft-gate-chat')
        directory = studio.inside(self.root, 'articles', found['id'])
        (directory / 'desk').mkdir()
        journal = directory / 'desk' / desk_migration.JOURNAL
        # A journal that cannot say its token: nothing on the page finishes it, so the
        # record waits and offers new work meanwhile.
        studio.write_json(journal, {'schema': 1})
        shown = management.view(self.root, 'run', {'id': [found['id']]})
        saved = shown['saved_record']
        self.assertEqual((saved['outcome'], saved['clear']), ('wait', None))
        self.assertRegex(saved['why'], 'interrupted')
        self.assertEqual((saved['next'], saved['start']['title']), ('copy', found['title']))
        # One that kept its token: Finish opening on the desk repeats the migration with it.
        token = 'bm1.' + 'x' * 43
        studio.write_json(journal, {'schema': 1, 'expected': token})
        saved = self.run_view(found['id'])['saved_record']
        self.assertEqual((saved['clear'], saved['token'], saved['next']), ('recover', token, None))
