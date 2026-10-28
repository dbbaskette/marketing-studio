"""Explicit unfinished migration preserves saved records and never starts work."""

import isolation  # noqa: F401
import copy
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock, patch

import blog_runner as runner
import desk
import desk_chat
import management
import studio
from test_blog_runner import RunnerCase

OUTLINE = '# Synthetic outline\n\nOpening brief.\n\n## First\n\nFirst brief.\n\n## Second\n\nSecond brief.\n'
MANUSCRIPT = '# Synthetic draft\n\nAn opening.\n\n## First\n\nSaved words.\n'


class MigrationTests(RunnerCase):
    def eligible(self, material='draft'):
        # A saved-format fixture, not a public new-work command or a worker.
        found = self.create(page=True)
        directory, _, run = runner.load(self.root, found['id'])
        if material == 'draft':
            (directory / 'DRAFT.md').write_text(MANUSCRIPT)
            (directory / 'OUTLINE.md').write_text(OUTLINE)
            run['stages']['outline'] = {
                'status': 'approved',
                'accepted_by': 'person',
                'hash': 'old',
                'basis': 'old',
            }
            run['stages']['draft'] = {
                'status': 'draft',
                'hash': studio.digest(MANUSCRIPT.encode()),
                'basis': 'old',
            }
        elif material == 'outline':
            (directory / 'OUTLINE.md').write_text(OUTLINE)
        studio.write_json(directory / runner.STATE, run)
        return found['id'], directory

    def snapshot(self, directory=None):
        directory = directory or self.root
        return {
            str(p.relative_to(directory)): p.read_bytes()
            for p in directory.rglob('*')
            if p.is_file()
        }

    def preview(self, ident):
        return desk_chat.migration_preview(self.root, ident)

    def apply(self, ident, preview=None):
        return desk_chat.migrate(self.root, ident, (preview or self.preview(ident))['expected'])

    def test_preview_cancel_is_read_only_even_through_page_route(self):
        ident, _ = self.eligible()
        before = self.snapshot()
        with (
            patch('team_workspace.before', side_effect=AssertionError('fetch')),
            patch('team_workspace.saved', side_effect=AssertionError('share')),
            patch('desk.read', side_effect=AssertionError('repair')),
        ):
            shown = management.view(self.root, 'desk-migration-preview', {'id': [ident]})
        self.assertTrue(shown['eligible'])
        self.assertTrue(shown['expected'])
        self.assertEqual(self.snapshot(), before)

    def test_apply_preserves_every_old_byte_and_original_session_after_checked_save(self):
        ident, directory = self.eligible()
        record = studio.read_json(directory / 'session.json')
        record['google'] = {
            'baselines': {'draft': {'transfer': 'old-transfer', 'document': {'id': 'synthetic'}}}
        }
        studio.write_json(directory / 'session.json', record)
        (directory / 'history').mkdir(exist_ok=True)
        (directory / 'history/old.md').write_text('Kept history.')
        studio.write_json(
            directory / 'derived/blog-draft-notes.json',
            {'evidence': [], 'gaps': ['Supply a release date.']},
        )
        before = self.snapshot(directory)
        with (
            patch('desk_jobs.begin', side_effect=AssertionError('job')),
            patch.object(runner.Engine, 'start', side_effect=AssertionError('runner')),
        ):
            result = self.apply(ident)
        self.assertEqual(result['execution'], 'conversation')
        for name, raw in before.items():
            self.assertEqual((directory / name).read_bytes(), raw, name)
        self.assertEqual(result['draft']['opening'], 'An opening.')
        self.assertEqual(result['draft']['gaps'], ['Supply a release date.'])
        context = desk_chat.context(self.root, ident, 'opening')
        desk_chat.submit(
            self.root,
            ident,
            {
                'kind': 'part',
                'target': 'opening',
                'expected_basis': context['expected_basis'],
                'payload': {'text': 'A checked edit.'},
            },
        )
        self.assertEqual((directory / 'session.json').read_bytes(), before['session.json'])
        self.assertEqual((directory / runner.STATE).read_bytes(), before[runner.STATE])
        self.assertEqual(studio.item(self.root, 'articles', ident)[1]['google'], record['google'])
        self.assertTrue(desk.versions(self.root, ident, 'opening'))

    def test_outline_keeps_all_briefs_without_inventing_prose_or_progress(self):
        ident, directory = self.eligible('outline')
        before = self.snapshot(directory)
        result = self.apply(ident)
        draft = result['draft']
        self.assertEqual(draft['opening'], '')
        self.assertEqual(draft['opening_brief'], 'Opening brief.')
        self.assertEqual([s['brief'] for s in draft['sections']], ['First brief.', 'Second brief.'])
        self.assertTrue(all(not s['text'] for s in draft['sections']))
        self.assertFalse((directory / 'DRAFT.md').exists())
        for name, raw in before.items():
            self.assertEqual((directory / name).read_bytes(), raw)

    def test_focused_outline_and_review_do_not_gain_drafting_scope(self):
        for material, pipeline, scope in (
            ('outline', ['outline'], 'outline'),
            ('draft', ['review', 'package'], 'part'),
        ):
            with self.subTest(scope=scope):
                ident, directory = self.eligible(material)
                run = studio.read_json(directory / runner.STATE)
                run['pipeline'] = pipeline
                run['stages'] = {}
                studio.write_json(directory / runner.STATE, run)
                before = self.snapshot(directory)
                result = self.apply(ident)
                self.assertEqual(result['scope'], scope)
                self.assertIsNone(result['start'])
                with self.assertRaisesRegex(ValueError, 'scope'):
                    desk_chat.context(self.root, ident, 'draft')
                allowed = 'outline' if scope == 'outline' else 'opening'
                self.assertEqual(desk_chat.context(self.root, ident, allowed)['scope'], scope)
                for name, raw in before.items():
                    self.assertEqual((directory / name).read_bytes(), raw)

    def test_brief_only_and_interrupted_research_refuse_without_hidden_desk(self):
        for stage in ('outline', 'research', 'angles'):
            with self.subTest(stage=stage):
                ident, directory = self.eligible('none')
                run = studio.read_json(directory / runner.STATE)
                run['pipeline'] = [stage]
                studio.write_json(directory / runner.STATE, run)
                before = self.snapshot(directory)
                preview = self.preview(ident)
                self.assertFalse(preview['eligible'])
                self.assertIn('usable', ' '.join(preview['blockers']))
                self.assertIn('saved flow', preview['notice'])
                with self.assertRaises(ValueError):
                    self.apply(ident, preview)
                self.assertEqual(self.snapshot(directory), before)
                self.assertFalse((directory / 'desk').exists())

    def test_unknown_and_missing_declared_material_refuse(self):
        for change in ('schema', 'pipeline', 'missing', 'outline', 'link'):
            with self.subTest(change=change):
                ident, directory = self.eligible()
                run = studio.read_json(directory / runner.STATE)
                if change == 'schema':
                    run['schema'] = 999
                if change == 'pipeline':
                    run['pipeline'] = ['unknown']
                if change == 'missing':
                    (directory / 'DRAFT.md').unlink()
                if change == 'outline':
                    (directory / 'DRAFT.md').unlink()
                    run['stages'].pop('draft')
                    (directory / 'OUTLINE.md').write_text('Unstructured notes only.')
                if change == 'link':
                    (directory / 'linked').symlink_to(self.base)
                studio.write_json(directory / runner.STATE, run)
                before = (
                    self.snapshot(directory)
                    if change != 'link'
                    else (directory / 'session.json').read_bytes()
                )
                shown = self.preview(ident)
                self.assertFalse(shown['eligible'])
                with self.assertRaises(ValueError):
                    self.apply(ident, shown)
                self.assertFalse((directory / 'desk').exists())
                self.assertEqual(
                    self.snapshot(directory)
                    if change != 'link'
                    else (directory / 'session.json').read_bytes(),
                    before,
                )

    def test_preview_binds_content_record_dependencies_ownership_and_worker(self):
        for change in ('content', 'session', 'run', 'source', 'team', 'worker'):
            with self.subTest(change=change):
                ident, directory = self.eligible()
                source = studio.inside(self.root, 'sources', 'synthetic')
                source.mkdir()
                studio.write_json(
                    source / 'record.json',
                    {
                        'id': 'synthetic',
                        'revision': 1,
                        'name': 'Synthetic',
                        'status': 'ready',
                        'origin': {},
                        'purposes': ['reference'],
                    },
                )
                (source / 'content.md').write_text('Selected source.')
                record = studio.read_json(directory / 'session.json')
                record['sources'] = [
                    {'source_id': 'synthetic', 'revision': 1, 'purposes': ['reference']}
                ]
                studio.write_json(directory / 'session.json', record)
                shown = self.preview(ident)
                target = {
                    'content': directory / 'DRAFT.md',
                    'session': directory / 'session.json',
                    'run': directory / runner.STATE,
                    'source': source / 'content.md',
                    'team': directory / 'run.json',
                    'worker': self.root / '.blog-runs' / (ident + '.json'),
                }[change]
                target.parent.mkdir(parents=True, exist_ok=True)
                if change == 'worker':
                    target.write_text('{"enabled":true,"status":"working"}')
                elif change == 'team':
                    target.write_text('{"schema":1,"driver":{"computer":"other"}}')
                else:
                    target.write_bytes(target.read_bytes() + b'\n')
                before = self.snapshot(directory)
                with self.assertRaisesRegex(ValueError, 'changed|working|under way'):
                    self.apply(ident, shown)
                self.assertEqual(self.snapshot(directory), before)
                import shutil

                shutil.rmtree(source)

    def test_real_and_automatic_approvals_are_kept_and_unfinished_describe_is_honest(self):
        ident, directory = self.eligible()
        run = studio.read_json(directory / runner.STATE)
        run['stages']['outline']['accepted_by'] = 'review-policy'
        studio.write_json(directory / runner.STATE, run)
        before = (directory / runner.STATE).read_bytes()
        self.apply(ident)
        shown = runner.engine(self.root).describe(ident)
        self.assertTrue(shown['on_desk'])
        self.assertFalse(shown['complete'])
        self.assertNotEqual({s['status'] for s in shown['stages']}, {'approved'})
        self.assertEqual(shown['stages'][0]['accepted_by'], 'review-policy')
        self.assertTrue(shown['stages'][0]['auto_accepted'])
        self.assertEqual((directory / runner.STATE).read_bytes(), before)

    def test_repeat_apply_does_not_copy_or_overwrite_the_desk(self):
        ident, directory = self.eligible()
        preview = self.preview(ident)
        first = self.apply(ident, preview)
        before = self.snapshot(directory)
        again = self.apply(ident, preview)
        self.assertEqual(first['draft'], again['draft'])
        self.assertEqual(self.snapshot(directory), before)

    def test_partial_write_failure_rolls_back_and_old_flow_remains_usable(self):
        import desk_migration

        ident, directory = self.eligible()
        preview = self.preview(ident)
        before = self.snapshot(directory)
        real = studio.atomic

        def fail(path, raw):
            if Path(path) == directory / 'desk/draft.json':
                raise OSError('synthetic write failure')
            return real(path, raw)

        with patch('studio.atomic', side_effect=fail):
            with self.assertRaisesRegex(OSError, 'synthetic'):
                self.apply(ident, preview)
        self.assertEqual(self.snapshot(directory), before)
        self.assertFalse(desk_migration.pending(self.root, ident))
        self.assertFalse(runner.engine(self.root).describe(ident)['on_desk'])
        self.apply(ident)

    def test_pure_prepare_does_not_modify_inputs_or_take_user_paths(self):
        import desk_migration

        ident, directory = self.eligible()
        record = studio.read_json(directory / 'session.json')
        inputs = {
            'run': studio.read_json(directory / runner.STATE),
            'files': {'DRAFT.md': MANUSCRIPT.encode()},
            'at': 'synthetic',
        }
        original = copy.deepcopy((record, inputs))
        prepared = desk_migration.prepare_migration(record, inputs)
        self.assertEqual((record, inputs), original)
        self.assertEqual(set(prepared), {'blockers', 'retained', 'writes'})
        self.assertTrue(set(prepared['writes']) <= desk_migration.WRITES)

    def test_cli_preview_then_guarded_migrate(self):
        ident, directory = self.eligible('outline')
        script = isolation.SCRIPTS / 'studio.py'

        def cli(*args):
            done = subprocess.run(
                [sys.executable, str(script), '--root', str(self.root), 'desk', *args],
                text=True,
                capture_output=True,
                timeout=15,
            )
            self.assertEqual(done.returncode, 0, done.stderr)
            return json.loads(done.stdout)

        shown = cli('migration-preview', '--article', ident)
        result = cli('migrate', '--article', ident, '--expected', shown['expected'])
        self.assertEqual(result['execution'], 'conversation')
        self.assertFalse((directory / 'DRAFT.md').exists())

    def test_killed_apply_is_excluded_from_worker_recovery_and_sync_then_recovers(self):
        import desk_migration
        import tool_jobs
        from studio_core.sync_guard import worker_in_progress

        ident, directory = self.eligible('outline')
        shown = self.preview(ident)
        before = self.snapshot(directory)
        code = """import os, sys
from pathlib import Path
import desk_chat, studio
real=studio.atomic
def interrupt(path, raw):
 if Path(path).name == 'draft.json': os._exit(71)
 return real(path, raw)
studio.atomic=interrupt
desk_chat.migrate(Path(sys.argv[1]), sys.argv[2], sys.argv[3])
"""
        done = subprocess.run(
            [sys.executable, '-c', code, str(self.root), ident, shown['expected']],
            env={**os.environ, 'PYTHONPATH': str(isolation.SCRIPTS)},
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(done.returncode, 71, done.stderr)
        self.assertTrue(desk_migration.pending(self.root, ident))
        partial = self.snapshot(directory)
        self.assertFalse((directory / 'desk/draft.json').exists())
        self.assertEqual(
            json.loads((directory / 'desk/migration.json').read_text())['session']['execution'],
            'conversation',
        )
        worker = Mock(side_effect=AssertionError('provider'))
        engine = runner.Engine(self.root, worker=worker)
        with patch.object(engine, 'local', side_effect=AssertionError('worker pickup')):
            engine._once(ident)
        tool_records = []
        for letter, status in (('a', 'working'), ('b', 'queued')):
            path = self.root / '.blog-runs/tools' / (letter * 32 + '.json')
            value = {
                'id': letter * 32,
                'kind': 'desk-draft',
                'status': status,
                'metadata': {'article': ident, 'desk': {'start': True}},
            }
            studio.write_json(path, value)
            tool_records.append((path, path.read_bytes()))
        with studio.locked(self.root):
            tool_jobs.recover(self.root)
        tool_jobs.once(engine)
        for path, raw in tool_records:
            self.assertEqual(path.read_bytes(), raw, 'no queued pickup or interrupted-job cleanup')
        self.assertTrue(worker_in_progress(self.root))
        self.assertEqual(self.snapshot(directory), partial)
        preview = self.preview(ident)
        self.assertFalse(preview['eligible'])
        self.assertIn('interrupted', ' '.join(preview['blockers']))
        self.assertEqual(self.snapshot(directory), partial)
        for path, _ in tool_records:
            path.unlink()
        self.apply(ident, shown)
        self.assertFalse(desk_migration.pending(self.root, ident))
        self.assertFalse(worker_in_progress(self.root))
        for name, raw in before.items():
            self.assertEqual((directory / name).read_bytes(), raw)
        worker.assert_not_called()

    def test_worker_waiting_for_lock_rechecks_migration_ownership(self):
        ident, _ = self.eligible()
        shown = self.preview(ident)
        worker = Mock(side_effect=AssertionError('provider'))
        engine = runner.Engine(self.root, worker=worker)
        real_lock, local = studio.locked, engine.local
        entering = False

        @contextmanager
        def race(root):
            nonlocal entering
            if not entering:
                entering = True
                self.apply(ident, shown)
            with real_lock(root):
                yield

        reads = 0

        def enabled_once(article):
            nonlocal reads
            reads += 1
            return {'enabled': True} if reads == 1 else local(article)

        with patch('studio.locked', race), patch.object(engine, 'local', side_effect=enabled_once):
            engine._once(ident)
        worker.assert_not_called()
        self.assertEqual(studio.item(self.root, 'articles', ident)[1]['execution'], 'conversation')

    def test_two_process_applies_share_one_desk_and_changed_process_basis_refuses(self):
        ident, directory = self.eligible()
        shown = self.preview(ident)
        env = {**os.environ, 'PYTHONPATH': str(isolation.SCRIPTS)}
        code = 'from pathlib import Path; import sys, desk_chat; print(desk_chat.migrate(Path(sys.argv[1]), sys.argv[2], sys.argv[3])["id"])'
        commands = [sys.executable, '-c', code, str(self.root), ident, shown['expected']]
        children = [
            subprocess.Popen(
                commands, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            for _ in range(2)
        ]
        try:
            for child in children:
                out, err = child.communicate(timeout=15)
                self.assertEqual(child.returncode, 0, err)
                self.assertEqual(out.strip(), ident)
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                    child.communicate()
        self.assertEqual(len(list((directory / 'desk').glob('draft.json'))), 1)
        self.assertFalse((directory / 'desk/migration.pending.json').exists())

    def test_missing_or_changed_sidecar_fails_closed_and_inventory_keeps_old_dependency(self):
        import saved_work
        import desk_migration

        ident, directory = self.eligible()
        self.apply(ident)
        marker = directory / 'desk/migration.json'
        original = marker.read_bytes()
        for change in ('missing', 'malformed', 'original'):
            with self.subTest(change=change):
                marker.write_bytes(original)
                old = (directory / 'session.json').read_bytes()
                if change == 'missing':
                    marker.unlink()
                elif change == 'malformed':
                    marker.write_text('{bad')
                else:
                    (directory / 'session.json').write_bytes(old + b'\n')
                before = self.snapshot(directory)
                with self.assertRaises(ValueError):
                    studio.item(self.root, 'articles', ident)
                with self.assertRaises(ValueError):
                    desk_migration.blocked(self.root, ident)
                report = saved_work.scan(self.root)
                self.assertFalse(report['complete'])
                self.assertIn(
                    'gated-flow', [r['id'] for r in report['paths'] if r['status'] == 'needed']
                )
                self.assertEqual(self.snapshot(directory), before)
                (directory / 'session.json').write_bytes(old)

    def test_effective_record_tokens_refuse_old_forms_and_report_real_changes(self):
        import blog_delete
        import desk_jobs

        ident, directory = self.eligible()
        self.apply(ident)
        original = (directory / 'session.json').read_bytes()
        run = (directory / runner.STATE).read_bytes()
        expected = desk_jobs.expected(self.root, ident)
        self.assertEqual(management.detail(self.root, ident)['expected'], expected)
        with patch('management.share', wraps=management.share) as shared:
            saved = management.dispatch(
                self.root, 'schedule', {'id': ident, 'expected': expected, 'owner': 'First editor'}
            )
            self.assertNotEqual(saved.get('status'), 'unchanged')
            self.assertTrue(saved['receipts'])
            self.assertEqual(shared.call_count, 1)
            current = desk_jobs.expected(self.root, ident)
            self.assertNotEqual(current, expected)
            self.assertEqual(management.detail(self.root, ident)['expected'], current)
            before = self.snapshot(directory)
            with self.assertRaisesRegex(ValueError, 'changed'):
                management.dispatch(
                    self.root,
                    'schedule',
                    {'id': ident, 'expected': expected, 'owner': 'Outdated editor'},
                )
            with self.assertRaisesRegex(ValueError, 'changed'):
                blog_delete.check(
                    self.root,
                    {
                        'id': ident,
                        'expected': expected,
                        'title': studio.item(self.root, 'articles', ident)[1]['title'],
                    },
                )
            self.assertEqual(self.snapshot(directory), before)
            unchanged = management.dispatch(
                self.root, 'schedule', {'id': ident, 'expected': current, 'owner': 'First editor'}
            )
            self.assertEqual(unchanged['status'], 'unchanged')
            self.assertEqual(unchanged['receipts'], [])
            self.assertEqual(shared.call_count, 1)
            self.assertEqual(desk_jobs.expected(self.root, ident), current)
            marker = directory / 'desk/migration.json'
            marker.write_text(json.dumps(studio.read_json(marker), separators=(',', ':')))
            self.assertEqual(
                desk_jobs.expected(self.root, ident),
                current,
                'format-only writes do not change the effective record version',
            )
        self.assertEqual((directory / 'session.json').read_bytes(), original)
        self.assertEqual((directory / runner.STATE).read_bytes(), run)

    def test_ordinary_record_bytes_remain_the_raw_file_for_tokens(self):
        import desk_jobs

        ident, directory = self.eligible()
        raw = (directory / 'session.json').read_bytes() + b'\n'
        (directory / 'session.json').write_bytes(raw)
        self.assertEqual(studio.record_bytes(directory, 'articles'), raw)
        self.assertEqual(desk_jobs.expected(self.root, ident), studio.digest(raw))

    def test_runner_settlement_keeps_a_parallel_record_edit(self):
        import editorial

        found = self.create(page=True)
        ident = found['id']
        directory, _ = studio.item(self.root, 'articles', ident)

        def worker(*args, **kwargs):
            with studio.locked(self.root):
                editorial.schedule(self.root, ident, {'owner': 'New editor'})
            return {'content': '# Late synthetic outline\n\nOld result.', 'notes': ''}

        engine = runner.Engine(self.root, worker)
        engine.control(ident, 'resume')
        engine._once(ident)
        self.assertEqual(engine.local(ident)['status'], 'failed')
        self.assertIn('blog changed', engine.local(ident)['error'])
        self.assertEqual(
            studio.item(self.root, 'articles', ident)[1]['editorial']['owner'], 'New editor'
        )
        self.assertFalse((directory / 'OUTLINE.md').exists())

    def test_original_session_schema_and_required_shapes_refuse_in_pure_and_snapshot(self):
        import desk_migration

        for name, value in (
            ('schema', 999),
            ('schema', True),
            ('title', None),
            ('mode', 'future-mode'),
            ('voice', []),
            ('sources', {}),
            ('sources', [{'source_id': 'bad', 'revision': 'new', 'purposes': []}]),
            ('artifact_hashes', []),
            ('reviews', 'unknown'),
            ('created_at', None),
        ):
            with self.subTest(field=name, value=value):
                ident, directory = self.eligible()
                record = studio.read_json(directory / 'session.json')
                record[name] = value
                studio.write_json(directory / 'session.json', record)
                files = self.snapshot(directory)
                prepared = desk_migration.prepare_migration(
                    record, {'run': studio.read_json(directory / runner.STATE), 'files': files}
                )
                self.assertTrue(prepared['blockers'])
                self.assertEqual(prepared['writes'], {})
                shown = self.preview(ident)
                self.assertFalse(shown['eligible'])
                self.assertIn('session', ' '.join(shown['blockers']).lower())
                with self.assertRaises(ValueError):
                    self.apply(ident, shown)
                self.assertEqual(self.snapshot(directory), files)
                self.assertFalse((directory / 'desk').exists())

    def test_sync_and_domain_agree_on_valid_json_migration_damage(self):
        import desk_migration
        from studio_core.sync_guard import worker_in_progress

        ident, directory = self.eligible()
        self.apply(ident)
        marker = directory / 'desk/migration.json'
        draft_path = directory / 'desk/draft.json'
        meta = studio.read_json(marker)
        draft = studio.read_json(draft_path)
        self.assertFalse(worker_in_progress(self.root))
        for change in (
            'execution',
            'scope',
            'material',
            'expected',
            'schema',
            'history-missing',
            'history-changed',
            'pipeline-missing',
            'draft-schema',
            'draft-id',
            'draft-flag',
            'image-dependency',
        ):
            with self.subTest(change=change):
                damaged, changed_draft = copy.deepcopy(meta), copy.deepcopy(draft)
                if change == 'execution':
                    damaged['session'].pop('execution')
                elif change == 'scope':
                    damaged['session'].pop('conversation_scope')
                elif change == 'material':
                    damaged['material'] = 'future-format'
                elif change == 'expected':
                    damaged['expected'] = 'old'
                elif change == 'schema':
                    damaged['schema'] = True
                elif change == 'history-missing':
                    damaged.pop('historical_stages')
                elif change == 'history-changed':
                    damaged['historical_stages']['draft']['status'] = 'approved'
                elif change == 'pipeline-missing':
                    damaged.pop('historical_pipeline')
                elif change == 'draft-schema':
                    changed_draft['schema'] = 999
                elif change == 'draft-id':
                    changed_draft['id'] = 'another-blog'
                elif change == 'draft-flag':
                    changed_draft['unfinished_migration'] = 'yes'
                elif change == 'image-dependency':
                    changed_draft['images'] = {'image1': {'key': 'saved', 'size': 5}}
                studio.write_json(marker, damaged)
                studio.write_json(draft_path, changed_draft)
                before = self.snapshot(directory)
                with self.assertRaises(ValueError):
                    desk_migration.metadata(directory)
                with self.assertRaises(ValueError):
                    studio.record_bytes(directory, 'articles')
                with self.assertRaisesRegex(ValueError, 'could not be checked'):
                    worker_in_progress(self.root)
                self.assertEqual(self.snapshot(directory), before)

    def test_preparation_and_registered_reader_share_supported_run_formats(self):
        import desk_migration

        for change in ('schema-bool', 'policy', 'pipeline'):
            with self.subTest(change=change):
                ident, directory = self.eligible()
                record = studio.read_json(directory / 'session.json')
                run = studio.read_json(directory / runner.STATE)
                if change == 'schema-bool':
                    run['schema'] = True
                elif change == 'policy':
                    run.update(schema=2, review_policy={'schema': 1, 'level': 'future'})
                else:
                    run['pipeline'] = [{'future': 'step'}]
                studio.write_json(directory / runner.STATE, run)
                before = self.snapshot(directory)
                prepared = desk_migration.prepare_migration(record, {'run': run, 'files': before})
                self.assertTrue(prepared['blockers'])
                self.assertEqual(prepared['writes'], {})
                shown = self.preview(ident)
                self.assertFalse(shown['eligible'])
                with self.assertRaises(ValueError):
                    self.apply(ident, shown)
                self.assertEqual(self.snapshot(directory), before)
