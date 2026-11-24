"""Every stop the saved step-by-step Blog Studio flow leaves on disk, in its original format.

Each fixture is made by the saved flow itself (runner.create, submit, decide, the page's
develop and Continue without research), never by writing a desk record. For each stop the
explicit migration preview is checked to change nothing and to start nothing; a stop that
migrates is applied and every original byte, approval fact and publishing gap is checked; a
stop that cannot be moved is refused with the saved flow still able to continue it.
"""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
from contextlib import contextmanager
import json
from unittest.mock import patch

import blog_runner as runner
import desk_chat
import studio
from test_blog_runner import FilesCase

OUTLINE = '# Synthetic outline\n\nOpening brief.\n\n## First\n\nFirst brief.\n\n## Second\n\nSecond brief.\n'
MANUSCRIPT = (
    '# Synthetic draft\n\nAn opening.\n\n## First\n\nSaved words.\n\n## Second\n\nMore words.\n'
)
REVIEW = '# Review\n\n- Tighten the opening.\n'
HANDOFF = '# Handoff\n\nTitle: Synthetic draft\n'
IDEAS = '# Ideas\n\nThree ways in.\n\n## One way\n\nReaders · A point\n\n## Another way\n\nReaders · Another point\n'


class SavedStateCase(FilesCase):
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

    def submit(self, found, content=None, page=False, **extra):
        if content is None and not extra:
            return super().submit(found, page=page)  # A claims map quotes its material.
        return runner.submit(
            self.root,
            found['id'],
            found['next'],
            {
                'content': content or '# ' + found['next'] + '\nSynthetic writing.',
                'notes': 'Synthetic worker judgment.',
                **extra,
            },
            found['expected'],
            page=page,
        )

    def written(self, found, stage, content, page=False, **extra):
        """Submit and approve every stage before `stage`, then submit `stage` itself."""
        while found['next'] != stage:
            found = self.approve(self.submit(found, page=page), page=page)
        return self.submit(found, content, page=page, **extra)

    def research_execution_run(self):
        """A page run saved with a research execution record (schema 4), research skipped."""
        from studio_core import research_contract, research_session

        contract = {'schema': 2, 'name': 'synthetic'}
        protocol = research_session.PROTOCOL
        execution = {
            'schema': 1,
            'protocol': protocol,
            'workers': 1,
            'capability': {'protocol': protocol},
        }
        with (
            patch.object(research_contract, 'snapshot', return_value=contract),
            patch.object(research_contract, 'runtime_for', return_value=self.base),
            patch.object(research_session, 'execution', return_value=execution),
        ):
            found = self.create(page=True, research='web-allowed', sources=[self.source()['id']])
        _, _, run = runner.load(self.root, found['id'])
        self.assertEqual(run['schema'], 4)
        with studio.locked(self.root), patch.object(runner.Engine, 'control', return_value={}):
            runner.dispatch(
                self.root, 'skip-research', {'id': found['id'], 'expected': found['expected']}
            )
        return runner.survey(self.root, found['id'])

    def refused(self, ident, words, errors=ValueError):
        """Not eligible, with the saved flow named; applying changes nothing."""
        directory = studio.inside(self.root, 'articles', ident)
        shown = self.preview(ident)
        self.assertFalse(shown['eligible'], shown)
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
        found = self.from_files()
        self.refused(found['id'], 'no usable manuscript or supported outline')
        self.assertEqual(runner.survey(self.root, found['id'])['next'], 'angles')
        found = self.submit(runner.survey(self.root, found['id']), self.ANGLES, page=True)
        self.assertEqual(found['awaits'], 'decision')

    def test_angles_waiting_for_a_choice_keep_their_saved_flow(self):
        found = self.submit(self.from_files(), self.ANGLES, page=True)
        self.refused(found['id'], 'no usable manuscript or supported outline')
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
        found = self.submit(
            self.create(page=True, research='web-allowed', sources=[self.source()['id']]),
            page=True,
        )
        self.assertEqual((found['next'], found['awaits']), ('research-plan', 'decision'))
        self.refused(found['id'], 'no usable manuscript or supported outline')
        found = self.approve(runner.survey(self.root, found['id']), page=True)
        self.assertEqual(found['next'], 'research')

    def test_research_findings_stop_keeps_its_saved_flow(self):
        found = self.create(page=True, research='web-allowed', sources=[self.source()['id']])
        found = self.written(found, 'research', '# Findings\n\nSynthetic evidence.', page=True)
        self.assertEqual((found['next'], found['awaits']), ('research', 'decision'))
        self.refused(found['id'], 'no usable manuscript or supported outline')
        self.assertEqual(
            self.approve(runner.survey(self.root, found['id']), page=True)['next'], 'outline'
        )

    def test_claims_map_gate_keeps_its_saved_flow(self):
        found = self.create(sources=[self.source()['id']], research='supplied-only')
        self.assertEqual(found['next'], 'claims-map')
        found = self.submit(found)
        self.assertEqual(found['awaits'], 'decision')
        self.refused(found['id'], 'no usable manuscript or supported outline')
        self.assertEqual(self.approve(runner.survey(self.root, found['id']))['next'], 'outline')

    def test_brief_only_start_keeps_its_saved_flow(self):
        found = self.create()
        self.assertEqual((found['next'], found['awaits']), ('outline', 'submission'))
        self.refused(found['id'], 'no usable manuscript or supported outline')
        self.assertEqual(self.submit(runner.survey(self.root, found['id']))['awaits'], 'decision')


class MaterialStopTests(SavedStateCase):
    """Stops with a usable manuscript or heading outline migrate losslessly."""

    def test_outline_gate_migrates_with_its_briefs_and_no_prose(self):
        found = self.submit(self.create(page=True), OUTLINE, page=True)
        self.assertEqual((found['next'], found['awaits']), ('outline', 'decision'))
        result, meta, draft = self.migrates(found['id'])
        self.assertEqual(meta['material'], 'outline')
        self.assertEqual([s['brief'] for s in draft['sections']], ['First brief.', 'Second brief.'])
        self.assertTrue(all(not s['text'] for s in draft['sections']))
        self.assertEqual(meta['historical_stages']['outline']['status'], 'draft')
        self.assertEqual(result['scope'], 'draft')

    def test_outline_approved_before_drafting_migrates(self):
        found = self.approve(self.submit(self.create(), OUTLINE))
        self.assertEqual((found['next'], found['awaits']), ('draft', 'submission'))
        _, meta, _ = self.migrates(found['id'])
        self.assertEqual(meta['historical_stages']['outline']['accepted_by'], 'conversation')

    def test_draft_gate_migrates_with_the_saved_draft(self):
        found = self.written(self.create(page=True), 'draft', MANUSCRIPT, page=True)
        self.assertEqual((found['next'], found['awaits']), ('draft', 'decision'))
        result, meta, draft = self.migrates(found['id'])
        self.assertEqual(meta['material'], 'draft')
        self.assertEqual(draft['opening'], 'An opening.')
        self.assertEqual([s['text'] for s in draft['sections']], ['Saved words.', 'More words.'])
        self.assertEqual(meta['historical_stages']['outline']['accepted_by'], 'page')
        self.assertEqual(meta['historical_stages']['draft']['status'], 'draft')

    def test_review_gate_migrates(self):
        found = self.create()
        found = self.written(found, 'draft', MANUSCRIPT)
        found = self.written(self.approve(found), 'review', REVIEW)
        self.assertEqual((found['next'], found['awaits']), ('review', 'decision'))
        _, meta, _ = self.migrates(found['id'])
        self.assertEqual(meta['historical_stages']['draft']['status'], 'approved')

    def test_handoff_gate_migrates_and_keeps_every_publishing_gap_unresolved(self):
        found = self.written(self.create(), 'draft', MANUSCRIPT, gaps=['Supply a release date.'])
        found = self.written(self.approve(found), 'package', HANDOFF, gaps=['Name the owner.'])
        self.assertEqual((found['next'], found['awaits']), ('package', 'decision'))
        _, _, draft = self.migrates(found['id'])
        self.assertEqual(draft['gaps'], ['Supply a release date.', 'Name the owner.'])

    def test_automatic_continuation_is_not_turned_into_approval(self):
        import studios_config

        studios_config.update({'review': {'level': 'balanced'}})
        found = self.approve(self.submit(self.create(), OUTLINE))
        found = self.submit(found, MANUSCRIPT)
        self.assertEqual(found['next'], 'review')
        _, meta, _ = self.migrates(found['id'])
        self.assertEqual(meta['historical_stages']['draft']['accepted_by'], 'review-policy')
        described = runner.engine(self.root).describe(found['id'])
        row = next(row for row in described['stages'] if row['stage'] == 'draft')
        self.assertTrue(row['auto_accepted'])

    def test_unstructured_outline_migrates_as_outline_notes_with_its_step_still_to_do(self):
        notes = 'Unstructured notes only, no headings.'
        found = self.submit(self.create(), notes)
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
        found = self.approve(self.submit(self.create(page=True), OUTLINE, page=True), page=True)
        self.assertEqual((found['next'], found['awaits']), ('draft', 'submission'))
        engine = runner.engine(self.root)
        engine.keep_local(
            found['id'],
            {'enabled': False, 'status': 'failed', 'error': 'Synthetic failure.', 'reason': 'cli'},
        )
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
        found = self.research_execution_run()
        found = self.written(found, 'draft', MANUSCRIPT, page=True)
        _, meta, _ = self.migrates(found['id'])
        self.assertEqual(meta['material'], 'draft')
        # The repository replay guard reads the moved blog as the domain reader does.
        from studio_core.sync_guard import worker_in_progress

        self.assertFalse(worker_in_progress(self.root))

    def test_finished_ideas_or_outline_migrate_with_outline_scope_only(self):
        for mode, text in (('ideas', IDEAS), ('outline', OUTLINE)):
            with self.subTest(mode=mode):
                found = self.approve(
                    self.submit(self.create(page=True, mode=mode, stop='outline'), text, page=True),
                    page=True,
                )
                self.assertTrue(found['complete'])
                # No DRAFT.md: there is no finished Open on the desk for it.
                self.assertFalse(runner.engine(self.root).describe(found['id'])['desk_open'])
                result, meta, draft = self.migrates(found['id'])
                self.assertEqual((meta['material'], result['scope']), ('outline', 'outline'))
                self.assertIsNone(result['start'])
                self.assertTrue(draft['sections'])
                self.assertTrue(all(not s['text'] for s in draft['sections']))

    def test_ideas_waiting_at_their_gate_migrate_with_outline_scope_only(self):
        found = self.submit(self.create(mode='ideas', stop='outline'), IDEAS)
        self.assertEqual((found['next'], found['awaits']), ('outline', 'decision'))
        result, meta, _ = self.migrates(found['id'])
        self.assertEqual(result['scope'], 'outline')
        self.assertIsNone(result['start'])

    def test_author_outline_run_migrates_ready_to_draft(self):
        found = self.create(mode='from-outline', outline_text=OUTLINE)
        self.assertEqual((found['next'], found['awaits']), ('draft', 'submission'))
        result, meta, _ = self.migrates(found['id'])
        self.assertEqual((meta['material'], result['scope']), ('outline', 'draft'))

    def test_review_of_a_supplied_manuscript_migrates_with_part_scope(self):
        source = self.source(MANUSCRIPT)
        found = self.submit(self.create(mode='review', manuscript=source['id']), REVIEW)
        self.assertEqual((found['next'], found['awaits']), ('review', 'decision'))
        result, meta, _ = self.migrates(found['id'])
        self.assertEqual(result['scope'], 'part')
        self.assertEqual(meta['material'], 'draft')

    def test_revision_of_a_supplied_manuscript_migrates(self):
        source = self.source(MANUSCRIPT)
        found = self.create(mode='revise', manuscript=source['id'])
        self.assertEqual((found['next'], found['awaits']), ('draft', 'submission'))
        result, _, _ = self.migrates(found['id'])
        self.assertEqual(result['scope'], 'draft')

    def test_continued_without_research_then_drafted_migrates(self):
        found = self.create(page=True, research='web-allowed', sources=[self.source()['id']])
        with studio.locked(self.root), patch.object(runner.Engine, 'control', return_value={}):
            runner.dispatch(
                self.root, 'skip-research', {'id': found['id'], 'expected': found['expected']}
            )
        found = self.written(runner.survey(self.root, found['id']), 'draft', MANUSCRIPT, page=True)
        _, meta, _ = self.migrates(found['id'])
        self.assertNotIn('research', meta['historical_pipeline'])

    def test_paused_stopped_and_failed_page_runs_migrate_with_their_worker_record(self):
        for state in (
            {'enabled': False, 'status': 'paused'},
            {'enabled': False, 'status': 'stopped'},
            {'enabled': False, 'status': 'failed', 'error': 'Synthetic failure.', 'reason': 'cli'},
        ):
            with self.subTest(status=state['status']):
                found = self.written(self.create(page=True), 'draft', MANUSCRIPT, page=True)
                engine = runner.engine(self.root)
                engine.keep_local(found['id'], state)
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
        found = self.written(self.create(), 'draft', MANUSCRIPT)
        found = self.written(self.approve(found), 'package', HANDOFF)
        found = self.approve(found)
        self.assertTrue(found['complete'])
        self.refused(found['id'], 'already finished')
        self.assertTrue(runner.engine(self.root).describe(found['id'])['desk_open'])

    def test_working_or_queued_page_run_waits_for_its_step(self):
        for state in (
            {'enabled': True, 'status': 'queued'},
            {'enabled': True, 'status': 'working'},
        ):
            with self.subTest(status=state['status']):
                found = self.written(self.create(page=True), 'draft', MANUSCRIPT, page=True)
                runner.engine(self.root).keep_local(found['id'], state)
                self.refused(found['id'], 'under way')

    def test_unreadable_run_or_session_record_keeps_every_file(self):
        for name in (runner.STATE, 'session.json'):
            with self.subTest(record=name):
                found = self.written(self.create(title='Unreadable ' + name), 'draft', MANUSCRIPT)
                directory = studio.inside(self.root, 'articles', found['id'])
                (directory / name).write_text('{not json')
                # The preview says the record cannot be read (today in the JSON reader's
                # own words) and offers no token; nothing can drive or move it until restored.
                shown = self.refused(found['id'], 'line 1')
                self.assertEqual(shown['expected'], '')
                self.assertEqual((directory / 'DRAFT.md').read_text(), MANUSCRIPT)
                self.assertEqual((directory / name).read_text(), '{not json')

    def test_unsupported_run_schema_keeps_its_saved_flow(self):
        found = self.written(self.create(), 'draft', MANUSCRIPT)
        directory = studio.inside(self.root, 'articles', found['id'])
        run = studio.read_json(directory / runner.STATE)
        run['schema'] = 99
        studio.write_json(directory / runner.STATE, run)
        self.refused(found['id'], 'supported saved Blog Studio run')

    def test_registered_manuscript_without_a_run_keeps_the_editor_exception(self):
        ident = self.article(MANUSCRIPT)
        self.assertFalse((studio.inside(self.root, 'articles', ident) / runner.STATE).exists())
        # The preview and applying it give the same refusal sentence, and write nothing.
        shown = self.refused(ident, 'no saved step-by-step run')
        with self.assertRaisesRegex(ValueError, 'no saved step-by-step run'):
            desk_chat.migrate(self.root, ident, shown['expected'] or 'bm1.' + 'x' * 43)
