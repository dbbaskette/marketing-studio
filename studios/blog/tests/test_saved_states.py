"""Every stop the saved step-by-step Blog Studio flow leaves on disk, in its original format.

Each stop is a static fixture (saved_fixtures.py, fixtures/saved/) captured from the saved
flow itself (runner.create, submit, decide, the page's develop and Continue without research,
the runner's worker record) and proven against it by test_saved_fixtures.py; none is written as
a desk record. For each stop the explicit migration preview is checked to change nothing and to
start nothing, and its one classification is pinned; a stop that migrates is applied and every
original byte, approval fact and publishing gap is checked; a stop that cannot be moved is
refused with the saved flow still able to continue it (until that flow is retired).
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

# Stopped before an outline or draft: read-only, and new work can start from its start form.
EARLY = ('read-only', 'stopped before an outline or draft was saved', 'copy')


class SavedStateCase(saved_fixtures.Maker):
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
        """Not eligible, with the saved flow named; applying changes nothing. `outcome` is
        (outcome, reason pattern, next action) as classify gives it."""
        directory = studio.inside(self.root, 'articles', ident)
        shown = self.preview(ident)
        self.assertFalse(shown['eligible'], shown)
        self.outcome(shown, *outcome)
        self.assertRegex(' '.join(shown['blockers']), words)
        self.assertIn('saved flow', shown['notice'])
        before = self.tree()
        with self.nothing_starts(), self.assertRaises(errors):
            desk_chat.migrate(self.root, ident, shown['expected'] or 'bm1.' + 'x' * 43)
        self.assertEqual(self.tree(), before)
        self.assertFalse((directory / 'desk').exists())
        return shown

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
    """Stops before any usable manuscript or outline: the saved flow keeps them."""

    def test_angles_not_yet_written_keep_their_saved_flow(self):
        found = self.saved('angles-unwritten')
        self.refused(found['id'], 'no usable manuscript or supported outline', EARLY)
        self.assertEqual(runner.survey(self.root, found['id'])['next'], 'angles')
        found = self.submit(runner.survey(self.root, found['id']), self.ANGLES, page=True)
        self.assertEqual(found['awaits'], 'decision')

    def test_angles_waiting_for_a_choice_keep_their_saved_flow(self):
        found = self.saved('angles-waiting')
        self.refused(found['id'], 'no usable manuscript or supported outline', EARLY)
        with studio.locked(self.root), patch.object(runner.Engine, 'control', return_value={}):
            runner.dispatch(
                self.root,
                'develop',
                {
                    'id': found['id'],
                    'expected': found['expected'],
                    'request': 'Retries are a budget',
                },
            )
        self.assertEqual(runner.survey(self.root, found['id'])['next'], 'outline')

    def test_research_questions_gate_keeps_its_saved_flow(self):
        found = self.saved('research-questions')
        self.assertEqual((found['next'], found['awaits']), ('research-plan', 'decision'))
        self.refused(found['id'], 'no usable manuscript or supported outline', EARLY)
        found = self.approve(runner.survey(self.root, found['id']), page=True)
        self.assertEqual(found['next'], 'research')

    def test_research_findings_stop_keeps_its_saved_flow(self):
        found = self.saved('research-findings')
        self.assertEqual((found['next'], found['awaits']), ('research', 'decision'))
        self.refused(found['id'], 'no usable manuscript or supported outline', EARLY)
        self.assertEqual(
            self.approve(runner.survey(self.root, found['id']), page=True)['next'], 'outline'
        )

    def test_claims_map_gate_keeps_its_saved_flow(self):
        found = self.saved('claims-map-gate')
        self.assertEqual(found['next'], 'claims-map')
        self.assertEqual(found['awaits'], 'decision')
        self.refused(found['id'], 'no usable manuscript or supported outline', EARLY)
        self.assertEqual(self.approve(runner.survey(self.root, found['id']))['next'], 'outline')

    def test_brief_only_start_keeps_its_saved_flow(self):
        found = self.saved('brief-only')
        self.assertEqual((found['next'], found['awaits']), ('outline', 'submission'))
        self.refused(found['id'], 'no usable manuscript or supported outline', EARLY)
        self.assertEqual(self.submit(runner.survey(self.root, found['id']))['awaits'], 'decision')


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
        self.assertEqual(meta['historical_stages']['outline']['status'], 'draft')

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

    def test_working_or_queued_page_run_waits_for_its_step(self):
        for status in ('queued', 'working'):
            with self.subTest(status=status):
                found = self.saved('draft-gate-' + status)
                self.refused(found['id'], 'under way', ('wait', 'under way'))

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
                self.assertEqual((directory / 'DRAFT.md').read_text(), MANUSCRIPT)
                self.assertEqual((directory / name).read_text(), '{not json')

    def test_unsupported_run_schema_keeps_its_saved_flow(self):
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
    """The page's read-only record: today only for saved blogs its run screen refuses."""

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

    def test_records_the_run_screen_reads_keep_their_screen_until_the_flow_is_retired(self):
        # A brief-only start will be a read-only record once the saved flow is retired; until
        # then its run screen, and its Continue, stay.
        found = self.saved('brief-only')
        self.assertEqual(desk_migration.classify(self.root, found['id'])['outcome'], 'read-only')
        shown = self.run_view(found['id'])
        self.assertNotIn('saved_record', shown)
        self.assertEqual(shown['next'], 'outline')

    def test_a_transient_refusal_is_said_as_before(self):
        import management

        found = self.saved('draft-gate-chat')
        directory = studio.inside(self.root, 'articles', found['id'])
        (directory / 'desk').mkdir()
        studio.write_json(directory / 'desk' / desk_migration.JOURNAL, {'schema': 1})
        with self.assertRaisesRegex(ValueError, 'interrupted'):
            management.view(self.root, 'run', {'id': [found['id']]})
