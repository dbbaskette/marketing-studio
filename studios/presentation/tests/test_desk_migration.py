"""Explicit unfinished conversion preserves originals and runs no provider work."""
import copy
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import runner_support
from runner import decks, desk_chat
from runner.steps import build
from workspace import WorkspaceError


class MigrationTests(runner_support.DeskCase):
    def snapshot(self, root):
        return {p.relative_to(root).as_posix(): p.read_bytes()
                for p in root.rglob('*') if p.is_file()}

    def preview(self, root):
        return desk_chat.migration_preview(self.engine, root)

    def migrate(self, root):
        preview = self.preview(root)
        self.assertEqual(preview['blockers'], [])
        return desk_chat.migrate(self.engine, root, preview['expected'])

    def test_preview_cancel_is_pure_even_older_document_index_and_no_identity(self):
        root = self.gated()
        index = root / 'sources/supplied/index.json'
        index.parent.mkdir(parents=True, exist_ok=True)
        index.write_text(json.dumps({'schema': 1, 'documents': []}))
        before = self.snapshot(self.base)
        with mock.patch.object(self.engine, 'hold', side_effect=AssertionError('hold')), \
                mock.patch.object(self.engine, 'view', side_effect=AssertionError('view')), \
                mock.patch.object(self.engine, 'wake', side_effect=AssertionError('wake')):
            preview = self.preview(root)
        self.assertEqual(preview['blockers'], [])
        self.assertEqual(preview['scope'], ['part'])
        self.assertIn('existing slide parts', preview['consequences'])
        self.assertEqual(before, self.snapshot(self.base))

    def test_migration_and_later_checked_edit_keep_original_and_history(self):
        root = self.gated()
        before = self.snapshot(root)
        with mock.patch.object(self.engine, 'ready', side_effect=AssertionError('readiness')), \
                mock.patch.object(self.engine, 'wake', side_effect=AssertionError('wake')):
            shown = self.migrate(root)
        self.assertEqual(shown['execution'], 'conversation')
        record = decks.read_run(root)
        self.assertEqual(record['flow'], 'desk')
        self.assertEqual(record['gates'], json.loads(before['run.json'])['gates'])
        self.assertFalse(shown['desk']['ready'])
        for name, data in before.items():
            self.assertEqual((root / name).read_bytes(), data, name)
        ident = runner_support.LONG_OUTLINE['slides'][1]['id']
        context = desk_chat.context(self.engine, root, ident + '/notes')
        desk_chat.save(self.engine, root, {'kind': 'part', 'target': ident + '/notes',
            'expected_basis': context['expected_basis'], 'payload': {'text': 'Explicit new notes.'}})
        self.assertEqual((root / 'run.json').read_bytes(), before['run.json'])
        self.assertTrue(desk_chat.show(self.engine, root)['history'][ident])
        self.assertEqual(decks.read_run(root)['conversation_scope'], ['part'])

    def test_early_missing_and_unsupported_inputs_refuse_without_changes(self):
        root = self.saved_start()
        (root / 'outline.json').unlink(missing_ok=True)
        before = self.snapshot(root)
        preview = self.preview(root)
        self.assertTrue(preview['blockers'])
        with self.assertRaises(WorkspaceError):
            desk_chat.migrate(self.engine, root, preview['expected'])
        self.assertEqual(before, self.snapshot(root))
        for value in ({}, {**self.record(root), 'schema': 99}):
            (root / 'run.json').write_text(json.dumps(value))
            before = self.snapshot(root)
            self.assertTrue(self.preview(root)['blockers'])
            self.assertEqual(before, self.snapshot(root))

    def test_marker_blocks_preview_apply_without_cleanup(self):
        root = self.gated()
        token = self.preview(root)['expected']
        marker = root / 'work/step.lock'
        marker.write_text('build-sections\n')
        before = self.snapshot(root)
        self.assertTrue(self.preview(root)['blockers'])
        with self.assertRaises(WorkspaceError):
            desk_chat.migrate(self.engine, root, token)
        self.assertEqual(before, self.snapshot(root))

    def test_preview_invalidated_by_material_source_record_worker_and_workspace(self):
        for change in ('outline', 'source', 'record', 'worker', 'workspace'):
            with self.subTest(change):
                root = self.gated(title='Change ' + change)
                token = self.preview(root)['expected']
                if change == 'outline':
                    with (root / 'outline.json').open('a') as stream:
                        stream.write(' ')
                elif change == 'source':
                    (root / 'sources').mkdir(exist_ok=True)
                    (root / 'sources/new.txt').write_text('New supplied material')
                elif change == 'record':
                    record = self.record(root)
                    record['title'] += ' changed'
                    decks.write_run(root, record)
                elif change == 'worker':
                    self.engine._run(root).queued = True
                before = self.snapshot(root)
                if change == 'workspace':
                    with mock.patch.object(self.engine, 'space', side_effect=WorkspaceError('changed')):
                        with self.assertRaises(WorkspaceError):
                            desk_chat.migrate(self.engine, root, token)
                else:
                    with self.assertRaises(WorkspaceError):
                        desk_chat.migrate(self.engine, root, token)
                self.engine._run(root).queued = False
                self.assertEqual(before, self.snapshot(root))

    def test_repeated_apply_is_same_and_restart_never_recovers_or_runs(self):
        root = self.gated()
        token = self.preview(root)['expected']
        first = desk_chat.migrate(self.engine, root, token)
        before = self.snapshot(root)
        again = desk_chat.migrate(self.engine, root, token)
        self.assertEqual(first['path'], again['path'])
        self.assertEqual(before, self.snapshot(root))
        with mock.patch.object(self.engine, '_original', side_effect=AssertionError('recover')), \
                mock.patch.object(self.engine, '_agent', side_effect=AssertionError('worker')):
            self.engine.resume()
            self.engine.wake(root)
        self.assertEqual(before, self.snapshot(root))

    def test_failure_after_journal_before_publication_rolls_back(self):
        from runner import desk_migration
        root = self.gated()
        token = self.preview(root)['expected']
        before = self.snapshot(root)
        original = desk_migration._write
        def fail(path, data):
            if Path(path).name == 'migration.json':
                raise OSError('synthetic publication failure')
            original(path, data)
        with mock.patch.object(desk_migration, '_write', side_effect=fail):
            with self.assertRaisesRegex(OSError, 'synthetic'):
                desk_chat.migrate(self.engine, root, token)
        self.assertEqual(before, self.snapshot(root))

    def test_pending_or_malformed_overlay_fails_closed_before_pickup(self):
        root = self.gated()
        original = (root / 'run.json').read_bytes()
        (root / 'desk').mkdir(exist_ok=True)
        (root / 'desk/migration.json').write_text('{}')
        with self.assertRaises(WorkspaceError):
            self.engine._load(root)
        before = self.snapshot(root)
        with mock.patch('runner.engine.gitstate.discard', side_effect=AssertionError('discard')):
            self.engine._tidy()
        self.assertEqual(before, self.snapshot(root))
        self.assertEqual((root / 'run.json').read_bytes(), original)

    def test_inventory_keeps_original_compatibility_and_reports_overlay_unknown(self):
        root = self.gated()
        self.migrate(root)
        report = self.engine.saved_work()
        self.assertTrue(next(p for p in report['paths'] if p['id'] == 'gated-flow')['needed_by'])
        (root / 'desk/migration.json').write_text('{}')
        self.assertFalse(self.engine.saved_work()['complete'])

    def test_shared_outline_structural_damage_refuses_domain_and_replay(self):
        from studio_core.sync_guard import worker_in_progress
        root = self.gated()
        original = json.loads((root / 'outline.json').read_bytes())
        for points in ('unreadable', [{'label': 4, 'text': 'Unsupported'}]):
            outline = copy.deepcopy(original)
            outline['slides'][0]['points'] = points
            (root / 'outline.json').write_text(json.dumps(outline))
            self.assertTrue(self.preview(root)['blockers'])
        (root / 'outline.json').write_text(json.dumps(original))
        self.migrate(root)
        (root / 'outline.json').write_text(json.dumps(outline))
        with self.assertRaises(ValueError):
            decks.read_run(root)
        with self.assertRaises(ValueError):
            worker_in_progress(self.space.repo)

    def test_cli_commands_are_json_without_launch(self):
        from runner import studio
        root = self.gated()
        args = studio.parser().parse_args(['desk', 'migration-preview', '--folder', str(root)])
        out = io.StringIO()
        studio.desk_command(args, make=lambda: self.engine, out=out)
        token = json.loads(out.getvalue())['expected']
        args = studio.parser().parse_args(['desk', 'migrate', '--folder', str(root), '--expected', token])
        studio.desk_command(args, make=lambda: self.engine, out=io.StringIO())

    def test_stopped_and_failed_runner_status_is_history_not_active_execution(self):
        for state in ('stopped', 'failed'):
            root = self.gated(title='Saved runner ' + state)
            record = self.record(root)
            record['halted'] = {'state': state, 'step': 'build-render', 'why': 'Saved synthetic failure'}
            decks.write_run(root, record)
            raw = (root / 'run.json').read_bytes()
            preview = self.preview(root)
            self.assertIn('History', ' '.join(preview['retained']))
            with mock.patch.object(self.engine, 'wake', side_effect=AssertionError('resume')):
                shown = desk_chat.migrate(self.engine, root, preview['expected'])
            self.assertIsNone(decks.read_run(root)['halted'])
            self.assertEqual(shown['desk']['saved_status'], record['halted'])
            self.assertFalse(shown['desk']['ready'])
            self.assertEqual(raw, (root / 'run.json').read_bytes())

    def test_either_missing_record_and_changed_original_are_unknown_not_legacy(self):
        from studio_core.sync_guard import worker_in_progress
        root = self.gated()
        self.migrate(root)
        before = self.snapshot(root)
        for name in ('desk/migration.json', 'desk/migration-origin.json', 'run.json'):
            with self.subTest(name):
                if name == 'run.json':
                    (root / name).write_bytes(before[name] + b' ')
                else:
                    (root / name).unlink()
                with self.assertRaises(WorkspaceError):
                    self.engine._load(root)
                with self.assertRaises(ValueError):
                    worker_in_progress(self.space.repo)
                (root / name).write_bytes(before[name])

    def test_strict_original_shapes_and_required_dependency_refusal(self):
        root = self.gated()
        original = (root / 'run.json').read_bytes()
        for key in ('agent', 'form', 'gates', 'id', 'revisions'):
            record = json.loads(original)
            record.pop(key)
            (root / 'run.json').write_text(json.dumps(record))
            self.assertTrue(self.preview(root)['blockers'], key)
        (root / 'run.json').write_bytes(original)
        (root / 'sources/supplied').mkdir(parents=True, exist_ok=True)
        (root / 'sources/supplied/index.json').write_text(json.dumps({'schema': 1, 'documents': [
            {'id': 'missing', 'name': 'missing.txt', 'readable': True}]}))
        self.assertTrue(self.preview(root)['blockers'])

    def test_crash_after_receipt_and_after_commit_has_explicit_safe_recovery(self):
        for boundary in ('receipt', 'commit'):
            root = self.gated(title='Crash ' + boundary)
            token = self.preview(root)['expected']
            raw = (root / 'run.json').read_bytes()
            code = '''import os, sys
from pathlib import Path
from runner import engine, desk_chat, desk_migration, gitstate
e=engine.Engine(background=False)
if sys.argv[3] == 'receipt':
 original=desk_migration._write
 def die(path,data):
  original(path,data)
  if Path(path).name == 'migration-origin.json': os._exit(71)
 desk_migration._write=die
else:
 original=gitstate.commit
 def die(*args,**kwargs):
  original(*args,**kwargs)
  os._exit(71)
 gitstate.commit=die
desk_chat.migrate(e,Path(sys.argv[1]),sys.argv[2])
'''
            process = subprocess.run([sys.executable, '-c', code, str(root), token, boundary],
                cwd=Path(__file__).resolve().parents[1], env={**os.environ, 'PYTHONPATH': '.:tests'},
                capture_output=True, text=True, timeout=20)
            self.assertEqual(process.returncode, 71, process.stderr)
            with self.assertRaises(WorkspaceError):
                self.engine._load(root)
            if boundary == 'receipt':
                with self.assertRaisesRegex(WorkspaceError, 'rolled back'):
                    desk_chat.migrate(self.engine, root, token)
                self.assertNotIn('flow', decks.read_run(root))
            else:
                self.assertEqual(desk_chat.migrate(self.engine, root, token)['execution'], 'conversation')
            self.assertEqual((root / 'run.json').read_bytes(), raw)

    def test_commit_then_raise_keeps_committed_ownership_until_explicit_retry(self):
        from runner import gitstate
        root = self.gated()
        token = self.preview(root)['expected']
        original = (root / 'run.json').read_bytes()
        commit = gitstate.commit
        def publish_then_fail(*args, **kwargs):
            commit(*args, **kwargs)
            raise OSError('synthetic post-commit failure')
        with mock.patch.object(gitstate, 'commit', side_effect=publish_then_fail):
            with self.assertRaisesRegex(OSError, 'post-commit'):
                desk_chat.migrate(self.engine, root, token)
        after = self.snapshot(root)
        self.assertIn('desk/migration-origin.json', after)
        self.assertIn('desk/migration.json', after)
        self.assertIn('work/desk/migration-transaction.json', after)
        with self.assertRaises(ValueError):
            decks.read_run(root)
        self.assertEqual(desk_chat.migrate(self.engine, root, token)['execution'], 'conversation')
        for name in ('run.json', 'desk/migration-origin.json', 'desk/migration.json'):
            self.assertEqual((root / name).read_bytes(), after[name])
        self.assertEqual(original, (root / 'run.json').read_bytes())
        self.assertFalse((root / 'work/desk/migration-transaction.json').exists())

    def recovery_state(self, root):
        return (self.snapshot(root), (self.space.root / 'hub.json').read_bytes(),
                self.git('ls-files', '--stage', '-z'), self.git('rev-parse', 'HEAD'))

    def publish_part(self, paths, kind):
        selected = paths[{'receipt': 0, 'record': 1, 'marker': 2,
                          'changed-receipt': 0, 'changed-marker': 2}[kind]]
        prepared = selected.read_bytes()
        if kind == 'changed-marker':
            value = json.loads(prepared)
            value['person_setting'] = 'A separately committed change'
            selected.write_text(json.dumps(value))
        elif kind == 'changed-receipt':
            selected.write_bytes(prepared + b' ')
        self.git('add', '--', *map(str, paths))
        self.git('commit', '--only', '-qm', 'Synthetic partial transaction publication', '--', str(selected))
        if kind.startswith('changed-'):
            selected.write_bytes(prepared)
            self.git('add', str(selected))

    def test_partial_publication_retry_preserves_journal_files_index_and_head(self):
        from runner import desk_migration, gitstate
        for kind in ('receipt', 'record', 'marker', 'changed-receipt', 'changed-marker'):
            with self.subTest(kind=kind):
                root = self.gated(title='Partial retry ' + kind)
                marker = self.space.root / gitstate.MARKER
                value = json.loads(marker.read_bytes())
                value['minimum_runtime'] = '4.8.0'
                marker.write_text(json.dumps(value))
                self.git('add', str(marker))
                self.git('commit', '--allow-empty', '-qm', 'Synthetic pre-publication marker')
                baseline = self.git('rev-parse', 'HEAD')
                token = self.preview(root)['expected']
                pending = root / 'work/desk/migration-transaction.json'
                try:
                    with mock.patch.object(gitstate, 'commit', side_effect=OSError('synthetic interruption')), \
                            mock.patch.object(desk_migration, '_committed', return_value=True):
                        with self.assertRaisesRegex(OSError, 'interruption'):
                            desk_chat.migrate(self.engine, root, token)
                    paths = [root / 'desk/migration-origin.json', root / 'desk/migration.json', marker]
                    self.publish_part(paths, kind)
                    before = self.recovery_state(root)
                    with self.assertRaisesRegex(WorkspaceError, 'publication|committed|HEAD'):
                        desk_chat.migrate(self.engine, root, token)
                    self.assertEqual(self.recovery_state(root), before)
                    self.assertTrue(pending.exists())
                finally:
                    self.git('reset', '--hard', baseline)
                    pending.unlink(missing_ok=True)

    def test_partial_publication_exception_preserves_journal_files_index_and_head(self):
        from runner import gitstate
        for kind in ('receipt', 'record', 'marker', 'changed-receipt', 'changed-marker'):
            with self.subTest(kind=kind):
                root = self.gated(title='Partial exception ' + kind)
                marker = self.space.root / gitstate.MARKER
                value = json.loads(marker.read_bytes())
                value['minimum_runtime'] = '4.8.0'
                marker.write_text(json.dumps(value))
                self.git('add', str(marker))
                self.git('commit', '--allow-empty', '-qm', 'Synthetic pre-publication marker')
                baseline = self.git('rev-parse', 'HEAD')
                token = self.preview(root)['expected']
                pending = root / 'work/desk/migration-transaction.json'
                before = []
                def fail(space, message, paths):
                    self.publish_part(paths, kind)
                    before.append(self.recovery_state(root))
                    raise OSError('synthetic partial commit')
                try:
                    with mock.patch.object(gitstate, 'commit', side_effect=fail):
                        with self.assertRaisesRegex(WorkspaceError, 'publication|committed|HEAD'):
                            desk_chat.migrate(self.engine, root, token)
                    self.assertEqual(self.recovery_state(root), before[0])
                    self.assertTrue(pending.exists())
                finally:
                    self.git('reset', '--hard', baseline)
                    pending.unlink(missing_ok=True)

    def test_recovery_never_discards_new_output_staging(self):
        for boundary in ('prepared', 'committed'):
            for change in ('staged', 'unmerged'):
                with self.subTest(boundary=boundary, change=change):
                    root = self.gated(title=f'Index {boundary} {change}')
                    token = self.preview(root)['expected']
                    code = '''import os, sys
from pathlib import Path
from runner import engine, desk_chat, desk_migration, gitstate
e=engine.Engine(background=False)
if sys.argv[3] == 'prepared':
 original=desk_migration._write
 def die(path,data):
  original(path,data)
  if Path(path).name == 'migration.json': os._exit(71)
 desk_migration._write=die
else:
 original=gitstate.commit
 def die(*args,**kwargs):
  original(*args,**kwargs)
  os._exit(71)
 gitstate.commit=die
desk_chat.migrate(e,Path(sys.argv[1]),sys.argv[2])
'''
                    process = subprocess.run([sys.executable, '-c', code, str(root), token, boundary],
                        cwd=Path(__file__).resolve().parents[1], env={**os.environ, 'PYTHONPATH': '.:tests'},
                        capture_output=True, text=True, timeout=20)
                    self.assertEqual(process.returncode, 71, process.stderr)
                    from runner import gitstate
                    output = root / 'desk/migration.json'
                    data = output.read_bytes()
                    output.write_bytes(data + b' ')
                    self.git('add', str(output))
                    output.write_bytes(data)
                    if change == 'unmerged':
                        relative = gitstate.inside(self.space, output)
                        digest = self.git('rev-parse', f':{relative}')
                        result = gitstate.hub.run(self.space.repo, 'update-index', '--index-info',
                            input=f'0 {"0" * 40}\t{relative}\n100644 {digest} 1\t{relative}\n')
                        self.assertEqual(result.returncode, 0, result.stderr)
                    before = self.snapshot(root), self.git('ls-files', '--stage', '-z'), self.git('rev-parse', 'HEAD')
                    with self.assertRaisesRegex(WorkspaceError, 'index|staging'):
                        desk_chat.migrate(self.engine, root, token)
                    self.assertEqual((self.snapshot(root), self.git('ls-files', '--stage', '-z'), self.git('rev-parse', 'HEAD')), before)
                    # Leave the deliberately unknown candidate alone; clean only its
                    # disposable index so another independent candidate can be seeded.
                    self.git('reset', '--mixed', 'HEAD')
                    (root / 'work/desk/migration-transaction.json').unlink()

    def test_exception_rollback_preserves_unexpected_staged_output(self):
        from runner import gitstate
        root = self.gated()
        token = self.preview(root)['expected']
        kept = {}
        def fail(*args, **kwargs):
            output = root / 'desk/migration.json'
            data = output.read_bytes()
            output.write_bytes(data + b' ')
            self.git('add', str(output))
            output.write_bytes(data)
            kept['index'] = self.git('ls-files', '--stage', '-z')
            raise OSError('synthetic changed staging')
        with mock.patch.object(gitstate, 'commit', side_effect=fail):
            with self.assertRaisesRegex(WorkspaceError, 'index|staging'):
                desk_chat.migrate(self.engine, root, token)
        self.assertEqual(self.git('ls-files', '--stage', '-z'), kept['index'])
        self.assertTrue((root / 'work/desk/migration-transaction.json').exists())

    def test_exception_rollback_keeps_changed_unstaged_outputs(self):
        from runner import gitstate
        root = self.gated()
        token = self.preview(root)['expected']
        kept = {}
        def fail(*args, **kwargs):
            output = root / 'desk/migration.json'
            output.write_bytes(output.read_bytes() + b' ')
            kept.update(self.snapshot(root))
            raise OSError('synthetic changed output')
        with mock.patch.object(gitstate, 'commit', side_effect=fail):
            with self.assertRaisesRegex(WorkspaceError, 'record changed'):
                desk_chat.migrate(self.engine, root, token)
        self.assertEqual(self.snapshot(root), kept)

    def test_legacy_local_journal_keeps_existing_readable_pair_and_recovers_exactly(self):
        import base64
        from runner import desk_migration, gitstate
        root = self.gated()
        marker = self.space.root / gitstate.MARKER
        value = json.loads(marker.read_bytes())
        value['minimum_runtime'] = '4.7.1'
        marker.write_text(json.dumps(value))
        self.git('add', str(marker))
        self.git('commit', '-qm', 'Synthetic committed legacy workspace marker')
        token = self.preview(root)['expected']
        with mock.patch.object(gitstate, 'commit', side_effect=OSError('synthetic interruption')), \
                mock.patch.object(desk_migration, '_committed', return_value=True):
            with self.assertRaisesRegex(OSError, 'interruption'):
                desk_chat.migrate(self.engine, root, token)
        pending = root / 'work/desk/migration-transaction.json'
        journal = json.loads(pending.read_bytes())
        journal.pop('shared')
        journal.pop('index_prepared')
        journal.pop('head_before')
        value['minimum_runtime'] = '4.8.0'
        data = json.dumps(value).encode()
        marker.write_bytes(data)
        journal['after'][desk_migration.WORKSPACE] = base64.b64encode(data).decode()
        pending.write_text(json.dumps(journal))
        # Existing 4.8.0 metadata uses the unchanged effective pair format.
        kept = pending.read_bytes()
        pending.unlink()
        self.assertEqual(decks.read_run(root)['execution'], 'conversation')
        pending.write_bytes(kept)
        with self.assertRaisesRegex(WorkspaceError, 'rolled back'):
            desk_chat.migrate(self.engine, root, token)
        self.assertEqual(json.loads(marker.read_bytes())['minimum_runtime'], '4.7.1')
        self.assertFalse(pending.exists())

    def test_exact_prepared_index_rolls_back_without_touching_unrelated_staging(self):
        from runner import gitstate
        root = self.gated()
        unrelated = self.space.repo / 'unrelated.txt'
        unrelated.write_text('Staged independently')
        self.git('add', str(unrelated))
        before = self.git('ls-files', '--stage', '-z')
        original = (root / 'run.json').read_bytes()
        token = self.preview(root)['expected']
        def fail(space, message, paths):
            self.git('add', '--', *map(str, paths))
            raise OSError('synthetic after staging')
        with mock.patch.object(gitstate, 'commit', side_effect=fail):
            with self.assertRaisesRegex(OSError, 'after staging'):
                desk_chat.migrate(self.engine, root, token)
        self.assertEqual(self.git('ls-files', '--stage', '-z'), before)
        self.assertEqual((root / 'run.json').read_bytes(), original)
        self.assertFalse((root / 'desk/migration.json').exists())
        self.assertFalse((root / 'work/desk/migration-transaction.json').exists())

    def test_legacy_dirty_marker_without_scoped_head_refuses_intact(self):
        from runner import desk_migration, gitstate
        root = self.gated()
        marker = self.space.root / gitstate.MARKER
        value = json.loads(marker.read_bytes())
        value['minimum_runtime'] = '4.8.0'
        marker.write_text(json.dumps(value))
        token = self.preview(root)['expected']
        with mock.patch.object(gitstate, 'commit', side_effect=OSError('synthetic interruption')), \
                mock.patch.object(desk_migration, '_committed', return_value=True):
            with self.assertRaisesRegex(OSError, 'interruption'):
                desk_chat.migrate(self.engine, root, token)
        pending = root / 'work/desk/migration-transaction.json'
        journal = json.loads(pending.read_bytes())
        journal.pop('head_before')
        pending.write_text(json.dumps(journal))
        before = self.recovery_state(root)
        with self.assertRaisesRegex(WorkspaceError, 'publication'):
            desk_chat.migrate(self.engine, root, token)
        self.assertEqual(self.recovery_state(root), before)

    def test_selected_changes_preserves_original_copy_and_google_preview_baseline(self):
        from test_desk_words import planned
        self.workers.then('patch', planned(2, '3', [(1, 'in minutes.')]))
        root = self.saved_existing_deck('automatic', 'selected', selected='Shorten slide 2')
        baseline = root / 'work/build/drive-preview.json'
        baseline.parent.mkdir(exist_ok=True)
        baseline.write_text('{"id":"synthetic-preview","pool":"prior-receipt"}')
        before = self.snapshot(root)
        self.migrate(root)
        for name, data in before.items():
            self.assertEqual((root / name).read_bytes(), data, name)

    def test_shared_guard_distinguishes_blog_and_presentation_same_named_record(self):
        from studio_core.sync_guard import worker_in_progress
        root = self.gated()
        self.migrate(root)
        self.assertFalse(worker_in_progress(self.space.repo))
        unrelated = self.space.repo / 'blog-fixture'
        (unrelated / 'desk').mkdir(parents=True)
        (unrelated / 'desk/migration.json').write_text('{"product":"Blog Studio"}')
        with self.assertRaises(ValueError):
            worker_in_progress(self.space.repo)

    def test_two_processes_apply_once_and_keep_original_bytes(self):
        root = self.gated()
        preview = self.preview(root)
        original = (root / 'run.json').read_bytes()
        code = 'from runner import engine,desk_chat; import sys; desk_chat.migrate(engine.Engine(background=False),sys.argv[1],sys.argv[2])'
        processes = [subprocess.Popen([sys.executable, '-c', code, str(root), preview['expected']],
            cwd=Path(__file__).resolve().parents[1], env={**os.environ, 'PYTHONPATH': '.:tests'},
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
        for process in processes:
            _, error = process.communicate(timeout=25)
            self.assertEqual(process.returncode, 0, error)
        self.assertEqual((root / 'run.json').read_bytes(), original)
        self.assertEqual(sum('open unfinished work on the desk' in line for line in self.log()), 1)

    def test_workspace_floor_preserves_values_and_staging_on_rollback(self):
        from runner import gitstate
        root = self.gated()
        marker = self.space.root / gitstate.MARKER
        values = json.loads(marker.read_bytes())
        values.update(minimum_runtime='4.7.1', unrelated={'keep': 'exactly'})
        marker.write_text(json.dumps(values))
        self.git('add', str(marker))
        before, index = marker.read_bytes(), self.git('ls-files', '--stage', '--', str(marker))
        preview = self.preview(root)
        self.assertIn('4.8.1', preview['consequences'])
        with mock.patch.object(gitstate, 'commit', side_effect=OSError('synthetic commit failure')):
            with self.assertRaisesRegex(OSError, 'synthetic'):
                desk_chat.migrate(self.engine, root, preview['expected'])
        self.assertEqual(marker.read_bytes(), before)
        self.assertEqual(self.git('ls-files', '--stage', '--', str(marker)), index)
        self.migrate(root)
        self.assertEqual(json.loads(marker.read_bytes())['minimum_runtime'], '4.8.1')
        self.assertEqual(json.loads(marker.read_bytes())['unrelated'], values['unrelated'])

    def test_higher_workspace_floor_is_not_lowered_and_configured_writers_check_it(self):
        from runner import gitstate
        root = self.gated()
        marker = self.space.root / gitstate.MARKER
        values = json.loads(marker.read_bytes())
        values['minimum_runtime'] = '4.9.0'
        marker.write_text(json.dumps(values))
        before = marker.read_bytes()
        with mock.patch.object(gitstate, 'installed', return_value='4.9.1'):
            self.migrate(root)
        self.assertEqual(marker.read_bytes(), before)
        with self.assertRaisesRegex(WorkspaceError, '4.9.0'):
            self.engine.hold(root, conversation=True)
        with self.assertRaisesRegex(WorkspaceError, '4.9.0'):
            with gitstate.workspace_locked(self.space, self.engine.files, configured=True):
                self.fail('older configured writer admitted')

    def test_policy_continuation_cannot_approve_after_migration(self):
        from runner import stages
        root = self.gated()
        self.migrate(root)
        before = self.snapshot(root)
        self.engine._policy_gate(root, stages.BY_NAME['gate:outline'])
        self.assertEqual(self.snapshot(root), before)

    def test_saved_schemas_one_two_three_prepare_without_rewriting_input(self):
        root = self.gated()
        original = (root / 'run.json').read_bytes()
        for schema in (1, 2, 3):
            record = json.loads(original)
            record['schema'] = schema
            if schema == 3:
                # A saved-format fixture, never a fabricated pin for new work or Ready.
                record['research_contract'] = {'schema': 2, 'version': '1.0.0', 'digest': '1' * 64}
            (root / 'run.json').write_text(json.dumps(record))
            files = self.snapshot(root)
            before = copy.deepcopy(record)
            prepared = desk_chat.prepare_migration(record, files)
            self.assertEqual(prepared['blockers'], [])
            self.assertEqual(record, before)
            self.assertEqual(self.snapshot(root), files)


class MigrationTeamTests(runner_support.DeskCase, runner_support.TeamCase):
    def evidence(self, root):
        marker = self.space.root / 'hub.json'
        return (MigrationTests.snapshot(self, root), self.git('rev-parse', 'HEAD'),
                self.git('ls-files', '--stage', '-z'), marker.read_bytes() if marker.exists() else None,
                {p.relative_to(root).as_posix(): p.stat().st_mode & 0o777 for p in root.rglob('*') if p.is_file()},
                marker.stat().st_mode & 0o777 if marker.exists() else None)

    def test_shared_retained_evidence_must_match_head_and_index(self):
        from runner import gitstate
        root = self.gated()
        binary = root / 'research/capture.bin'
        binary.parent.mkdir(exist_ok=True)
        binary.write_bytes(b'Captured evidence\x80\xff')
        self.git('add', str(binary))
        self.git('commit', '-qm', 'synthetic retained binary')
        baseline = self.git('rev-parse', 'HEAD')
        restored = self.evidence(root)
        for name in ('run.json', 'outline.json', '@marker', 'research/capture.bin'):
            for change in ('dirty', 'staged', 'untracked', 'deleted', 'mode', 'index-mode', 'conflicted'):
                with self.subTest(name=name, change=change):
                    path = self.space.root / gitstate.MARKER if name == '@marker' else root / name
                    data = path.read_bytes()
                    if change in ('dirty', 'staged'):
                        path.write_bytes(data + b' ')
                        if change == 'staged':
                            self.git('add', str(path))
                            path.write_bytes(data)  # diff HEAD alone would miss this
                    elif change == 'untracked':
                        self.git('rm', '--cached', str(path))
                        self.git('commit', '-qm', 'synthetic untracked retained input')
                    elif change == 'deleted':
                        path.unlink()
                    elif change == 'mode':
                        path.chmod(path.stat().st_mode | 0o111)
                    elif change == 'index-mode':
                        relative = gitstate.inside(self.space, path)
                        digest = self.git('rev-parse', f'HEAD:{relative}')
                        self.git('update-index', '--cacheinfo', f'120000,{digest},{relative}')
                    else:
                        relative = gitstate.inside(self.space, path)
                        digest = self.git('rev-parse', f'HEAD:{relative}')
                        result = gitstate.hub.run(self.space.repo, 'update-index', '--index-info',
                            input=f'0 {"0" * 40}\t{relative}\n100644 {digest} 1\t{relative}\n')
                        self.assertEqual(result.returncode, 0, result.stderr)
                    try:
                        before = self.evidence(root)
                        preview = desk_chat.migration_preview(self.engine, root)
                        self.assertTrue(preview['blockers'])
                        with self.assertRaises(WorkspaceError):
                            desk_chat.migrate(self.engine, root, preview['expected'])
                        self.assertEqual(self.evidence(root), before)
                    finally:
                        self.git('reset', '--hard', baseline)
                        # Git records executable mode, not the private read/write
                        # permissions used by native atomic JSON writes.
                        for relative, mode in restored[4].items():
                            (root / relative).chmod(mode)
                        (self.space.root / gitstate.MARKER).chmod(restored[5])
                        self.assertEqual(self.evidence(root), restored, 'synthetic baseline must be exact before the next subcase')

    def test_shared_private_ignored_and_unrelated_staging_survive_peer_readable_migration(self):
        root = self.gated()
        binary = root / 'research/capture.bin'
        binary.parent.mkdir(exist_ok=True)
        binary.write_bytes(b'Committed evidence\x80\xff')
        self.git('add', str(binary))
        self.git('commit', '-qm', 'synthetic committed binary')
        private = root / 'sources/private.bin'
        private.parent.mkdir(exist_ok=True)
        private.write_bytes(b'Private drawing\x80\xff')
        unrelated = self.space.root / 'unrelated.txt'
        unrelated.write_text('Unrelated staged work')
        self.git('add', str(unrelated))
        staged = self.git('ls-files', '--stage', '--', str(unrelated))
        original = (root / 'run.json').read_bytes()
        preview = desk_chat.migration_preview(self.engine, root)
        self.assertEqual(preview['blockers'], [])
        # An unrelated commit does not invalidate the relevant retained-entry basis.
        other = self.space.repo / 'other-product.txt'
        other.write_text('Other product commit')
        self.git('add', str(other))
        self.git('commit', '--only', '-qm', 'synthetic unrelated commit', '--', str(other))
        desk_chat.migrate(self.engine, root, preview['expected'])
        self.assertEqual(self.git('ls-files', '--stage', '--', str(unrelated)), staged)
        self.assertEqual(private.read_bytes(), b'Private drawing\x80\xff')
        self.engine.share()
        with self.be(self.blake):
            self.blake.engine.fetch()
            peer = self.theirs(self.blake, root)
            self.assertEqual(decks.read_run(peer)['execution'], 'conversation')
            self.assertEqual((peer / 'run.json').read_bytes(), original)
            self.assertEqual((peer / 'research/capture.bin').read_bytes(), binary.read_bytes())
            self.assertFalse((peer / 'sources/private.bin').exists())

    def test_shared_tracked_ignored_input_and_changed_preview_index_refuse(self):
        root = self.gated()
        private = root / 'sources/tracked.bin'
        private.parent.mkdir(exist_ok=True)
        private.write_bytes(b'Originally shared\x80\xff')
        self.git('add', '-f', str(private))
        self.git('commit', '-qm', 'synthetic tracked ignored input')
        token = desk_chat.migration_preview(self.engine, root)['expected']
        for change in ('index', 'content', 'committed'):
            with self.subTest(change=change):
                before_bytes = private.read_bytes()
                private.write_bytes(before_bytes + b' changed')
                if change != 'content':
                    self.git('add', '-f', str(private))
                if change == 'index':
                    private.write_bytes(before_bytes)
                if change == 'committed':
                    self.git('commit', '-qm', 'synthetic changed retained basis')
                before = self.evidence(root)
                with self.assertRaises(WorkspaceError):
                    desk_chat.migrate(self.engine, root, token)
                self.assertEqual(self.evidence(root), before)
                self.git('reset', '--hard', 'HEAD')

    def test_shared_recovery_binds_retained_evidence_and_requires_legacy_proof(self):
        from runner import desk_migration, gitstate
        for change in ('dirty', 'staged', 'committed', 'marker', 'legacy'):
            with self.subTest(change=change):
                root = self.gated(title='Recovery evidence ' + change)
                token = desk_chat.migration_preview(self.engine, root)['expected']
                with mock.patch.object(gitstate, 'commit', side_effect=OSError('synthetic interruption')), \
                        mock.patch.object(desk_migration, '_committed', return_value=True):
                    with self.assertRaisesRegex(OSError, 'interruption'):
                        desk_chat.migrate(self.engine, root, token)
                pending = root / 'work/desk/migration-transaction.json'
                if change == 'legacy':
                    value = json.loads(pending.read_bytes())
                    value.pop('shared')
                    value.pop('index_prepared')
                    value.pop('head_before')
                    pending.write_text(json.dumps(value))
                else:
                    path = self.space.root / gitstate.MARKER if change == 'marker' else root / 'outline.json'
                    data = path.read_bytes()
                    path.write_bytes(data + b' ')
                    if change != 'dirty':
                        self.git('add', str(path))
                    if change == 'staged':
                        path.write_bytes(data)
                    if change in ('committed', 'marker'):
                        self.git('commit', '--only', '-qm', 'synthetic changed recovery evidence', '--', str(path))
                before = self.evidence(root)
                try:
                    with self.assertRaisesRegex(WorkspaceError, 'shared|index|workspace'):
                        desk_chat.migrate(self.engine, root, token)
                    self.assertEqual(self.evidence(root), before)
                    self.assertTrue(pending.exists())
                finally:
                    self.git('reset', '--hard', 'HEAD')
                    pending.unlink(missing_ok=True)

    def test_shared_recovery_settles_committed_outputs_and_rolls_back_prepared_outputs(self):
        from runner import desk_migration, gitstate
        for committed in (False, True):
            with self.subTest(committed=committed):
                root = self.gated(title='Settle ' + str(committed))
                marker = self.space.root / gitstate.MARKER
                value = json.loads(marker.read_bytes())
                value.update(minimum_runtime='4.8.0', person_setting='keep')
                marker.write_text(json.dumps(value))
                self.git('add', str(marker))
                self.git('commit', '--allow-empty', '-qm', 'synthetic prior workspace floor')
                before_marker = marker.read_bytes()
                token = desk_chat.migration_preview(self.engine, root)['expected']
                commit = gitstate.commit
                def fail(*args, **kwargs):
                    if committed:
                        commit(*args, **kwargs)
                    raise OSError('synthetic interruption')
                with mock.patch.object(gitstate, 'commit', side_effect=fail), \
                        mock.patch.object(desk_migration, '_committed', return_value=True):
                    with self.assertRaisesRegex(OSError, 'interruption'):
                        desk_chat.migrate(self.engine, root, token)
                independent = self.space.repo / 'independent-commit.txt'
                independent.write_text('Unrelated recovery commit ' + str(committed))
                self.git('add', str(independent))
                self.git('commit', '--only', '-qm', 'Synthetic unrelated recovery commit', '--', str(independent))
                head = self.git('rev-parse', 'HEAD')
                unrelated = self.space.repo / 'unrelated-recovery.txt'
                unrelated.write_text('Keep my staging')
                self.git('add', str(unrelated))
                index = self.git('ls-files', '--stage', '--', str(unrelated))
                if committed:
                    self.assertEqual(desk_chat.migrate(self.engine, root, token)['execution'], 'conversation')
                    self.assertEqual(json.loads(marker.read_bytes())['minimum_runtime'], '4.8.1')
                else:
                    with self.assertRaisesRegex(WorkspaceError, 'rolled back'):
                        desk_chat.migrate(self.engine, root, token)
                    self.assertEqual(marker.read_bytes(), before_marker)
                self.assertEqual(self.git('ls-files', '--stage', '--', str(unrelated)), index)
                self.assertEqual(self.git('rev-parse', 'HEAD'), head)
                self.assertFalse((root / 'work/desk/migration-transaction.json').exists())
                self.git('reset', '--', str(unrelated))
                unrelated.unlink()

    def test_deleted_and_claimed_attribution_uses_effective_remote_driver(self):
        from runner import gitstate
        root = self.gated()
        preview = desk_chat.migration_preview(self.engine, root)
        desk_chat.migrate(self.engine, root, preview['expected'])
        original = (root / 'run.json').read_bytes()
        local = (root / 'desk/migration.json').read_bytes()
        value = json.loads(local)
        value['record']['driver'] = {'name': 'Effective teammate', 'computer': 'f' * 16,
                                     'since': '2026-10-28T12:00:00Z'}
        records = {'run.json': original.decode(), 'desk/migration.json': json.dumps(value),
                   'desk/migration-origin.json': (root / 'desk/migration-origin.json').read_text()}
        def theirs(space, path, at=None):
            return records.get(Path(path).relative_to(root).as_posix())
        space = self.engine.space()
        arrived = {gitstate.inside(space, root / 'run.json')}
        (root / 'run.json').unlink()
        with mock.patch.object(gitstate, 'theirs', side_effect=theirs), \
                mock.patch.object(gitstate, 'known', return_value=True), \
                mock.patch.object(gitstate, 'unshared', return_value=True), \
                mock.patch.object(gitstate, 'set_aside', return_value='synthetic-ref'), \
                mock.patch.object(self.engine, '_aside') as aside:
            self.engine._deleted(space, arrived, None)
        self.assertEqual(aside.call_args.args[2], 'Effective teammate')
        (root / 'run.json').write_bytes(original)
        self.engine._clash[root.name] = 'synthetic conflict'
        with mock.patch.object(gitstate, 'theirs', side_effect=theirs), \
                mock.patch.object(self.engine, '_step', return_value={'shared': True}), \
                mock.patch.object(self.engine, '_forget'), \
                mock.patch.object(self.engine, '_undo_start'):
            with self.assertRaisesRegex(WorkspaceError, 'Effective teammate'):
                self.engine._claimed(root, space)
        self.assertEqual((root / 'run.json').read_bytes(), original)
        self.assertEqual((root / 'desk/migration.json').read_bytes(), local)

    def test_malformed_existing_identity_refuses_without_initializing(self):
        import home
        root = self.gated()
        path = home.data_root() / 'computer.json'
        path.write_text('{"schema":1,"id":"invalid"}')
        record = self.record(root)
        record['driver']['computer'] = 'invalid'
        decks.write_run(root, record)
        before = MigrationTests.snapshot(self, self.base)
        self.assertTrue(desk_chat.migration_preview(self.engine, root)['blockers'])
        self.assertEqual(MigrationTests.snapshot(self, self.base), before)

    def test_preview_and_effective_team_takeover_refuse_the_old_driver(self):
        root = self.gated()
        preview = desk_chat.migration_preview(self.engine, root)
        desk_chat.migrate(self.engine, root, preview['expected'])
        original = (root / 'run.json').read_bytes()
        self.engine.share()
        other = self.theirs(self.blake, root)
        with self.be(self.blake):
            self.blake.engine.fetch()
            with mock.patch.object(self.blake.engine, 'wake', side_effect=AssertionError('wake')):
                # Taking explicitly changes only effective ownership before drive's wake.
                with self.assertRaisesRegex(AssertionError, 'wake'):
                    self.blake.engine.drive(other, 'take')
        self.engine.fetch()
        self.assertEqual(decks.read_run(root)['driver']['name'], 'Blake')
        self.assertEqual((root / 'run.json').read_bytes(), original)
        self.assertTrue(self.engine._run(root).gone)
        ident = runner_support.LONG_OUTLINE['slides'][1]['id']
        context = desk_chat.context(self.engine, root, ident + '/notes')
        with self.assertRaises(WorkspaceError):
            desk_chat.save(self.engine, root, {'kind': 'part', 'target': ident + '/notes',
                'expected_basis': context['expected_basis'], 'payload': {'text': 'Must refuse'}})


class ReadyTests(runner_support.DeskCase):
    def selected_migrated(self):
        from test_desk_words import planned
        self.workers.then('patch', planned(2, '3', [(1, 'in minutes.')]))
        root = self.saved_existing_deck('automatic', 'selected', selected='Shorten slide 2')
        preview = desk_chat.migration_preview(self.engine, root)
        desk_chat.migrate(self.engine, root, preview['expected'])
        return root

    def test_migrated_selected_ready_checks_current_copy_and_requires_explicit_ack(self):
        root = self.selected_migrated()
        before = MigrationTests.snapshot(self, root)
        self.assertNotIn('deckSha256', build.read_state(root))
        context = desk_chat.context(self.engine, root, 'ready')
        required = context['requirements']
        self.assertIn('historical', required['historical_proof'].lower())
        self.assertFalse(required['seen']['historical_proof_ack'])
        request = {'expected_basis': context['expected_basis'], 'seen': required['seen'],
                   'response': 'I inspected the current copy and acknowledge the missing historical byte proof.'}
        with self.assertRaises(WorkspaceError):
            desk_chat.ready(self.engine, root, request)
        with self.assertRaises(WorkspaceError):
            desk_chat.ready(self.engine, root, {**request, 'seen': {**request['seen'], 'historical_proof_ack': 1}})
        request['seen'] = {**request['seen'], 'historical_proof_ack': True}
        with mock.patch.object(self.engine, 'wake', side_effect=AssertionError('wake')), \
                mock.patch.object(build, 'render', side_effect=AssertionError('render')):
            shown = desk_chat.ready(self.engine, root, request)
        self.assertTrue(shown['desk']['ready'])
        self.assertIsNone(shown['deliver'])
        for name, data in before.items():
            if name != 'desk/migration.json':
                self.assertEqual((root / name).read_bytes(), data, name)
        with mock.patch.object(self.engine, 'slides', side_effect=AssertionError('polling checker')):
            self.assertTrue(self.engine.view(root)['desk']['ready'])
        record = decks.read_run(root)
        self.assertTrue(record['conversation_ready']['validation']['preservation']['preserved'])
        self.assertTrue(record['conversation_ready']['validation']['patch_matches'])

    def test_selected_refuses_changed_native_copy_outside_and_inside_allowed_patch(self):
        from stand_ins.slides import inventory, _pack
        root = self.selected_migrated()
        deck = root / build.read_state(root)['deck']
        original = deck.read_bytes()
        for slide, obj, run in ((0, 0, 0), (1, 1, 1)):
            current = inventory(deck)
            current['slides'][slide]['objects'][obj]['runs'][run] = 'Not the retained request'
            deck.unlink()
            _pack(deck, current)
            before = MigrationTests.snapshot(self, root)
            with self.assertRaises(WorkspaceError):
                self.request(root)
            self.assertEqual(MigrationTests.snapshot(self, root), before)
            deck.write_bytes(original)

    def test_selected_missing_preview_plan_checker_and_changed_basis_refuse(self):
        from runner.steps import existing
        root = self.selected_migrated()
        for path in (root / existing.PLAN, root / existing.ALLOW, next(build.shots(root).glob('*.png'))):
            original = path.read_bytes()
            path.unlink()
            before = MigrationTests.snapshot(self, root)
            with self.assertRaises(WorkspaceError):
                self.request(root)
            self.assertEqual(MigrationTests.snapshot(self, root), before)
            path.write_bytes(original)
        for report in ({}, {'preserved': False, 'failures': ['changed']}, {'preserved': True, 'failures': None}):
            with mock.patch.object(self.engine, 'slides') as slides:
                slides.return_value.pptx_compare.return_value = report
                with self.assertRaises(WorkspaceError):
                    self.request(root)
                slides.return_value.pptx_inspect.assert_not_called()
        with mock.patch.object(self.engine, 'slides', side_effect=WorkspaceError('Read-only checker unavailable')):
            with self.assertRaisesRegex(WorkspaceError, 'unavailable'):
                self.request(root)
        request = self.request(root)
        request['seen']['historical_proof_ack'] = True
        image = next(build.shots(root).glob('*.png'))
        original = image.read_bytes()
        other = next(path for path in build.shots(root).glob('*.png') if path != image)
        image.write_bytes(other.read_bytes())
        with self.assertRaises(WorkspaceError):
            desk_chat.ready(self.engine, root, request)
        request = self.request(root)
        request['seen']['historical_proof_ack'] = True
        desk_chat.ready(self.engine, root, request)
        image.write_bytes(original)
        self.assertFalse(self.engine.view(root)['desk']['ready'])

    def test_selected_existing_native_deck_hash_remains_mandatory(self):
        from test_desk_words import SelectedTests
        root = SelectedTests.deck(self)
        context = desk_chat.context(self.engine, root, 'ownership')
        desk_chat.take(self.engine, root, context['expected_basis'], ['part'])
        state = build.read_state(root)
        self.assertTrue(state['deckSha256'])
        self.assertTrue(self.request(root)['seen']['expected'])
        path = root / state['deck']
        path.write_bytes(path.read_bytes() + b'changed historical byte proof')
        with mock.patch.object(self.engine, 'slides', side_effect=AssertionError('ignore saved hash')):
            with self.assertRaises(WorkspaceError):
                self.request(root)

    def conversation(self):
        from test_desk_chat import ConversationTests
        root = ConversationTests.create(self, ['outline', 'drawing', 'part'], look='default')
        ConversationTests.submit(self, root, 'outline', 'outline', {'outline': runner_support.LONG_OUTLINE})
        from stand_ins.slides import sketch
        context = desk_chat.context(self.engine, root, 'drawing')
        by_id = {s['id']: s for s in runner_support.LONG_OUTLINE['slides']}
        sections = {ident: {'version': 1, 'title': spec['title'], 'direction': spec['direction'],
            'slides': [sketch(by_id[s['id']], spec['prefix']) for s in spec['slides']]}
            for ident, spec in context['requirements']['sections'].items()}
        desk_chat.submit(self.engine, root, {'kind': 'drawing', 'target': 'drawing',
            'expected_basis': context['expected_basis'], 'payload': {'sections': sections}})
        return root

    def request(self, root):
        context = desk_chat.context(self.engine, root, 'ready')
        return {'expected_basis': context['expected_basis'], 'seen': context['requirements']['seen'],
                'response': 'I reviewed this deck and approve it as ready.'}

    def test_explicit_ready_uses_checked_materials_not_upstream_approvals_or_jobs(self):
        root = self.conversation()
        previous = copy.deepcopy(decks.read_run(root)['gates'])
        self.assertFalse(self.engine.view(root)['desk']['ready'])
        request = self.request(root)
        with mock.patch.object(self.engine, 'ready', side_effect=AssertionError('runtime pin')), \
                mock.patch.object(self.engine, 'wake', side_effect=AssertionError('wake')), \
                mock.patch.object(self.engine, '_deliver', side_effect=AssertionError('delivery')):
            shown = desk_chat.ready(self.engine, root, request)
        self.assertTrue(shown['desk']['ready'])
        self.assertEqual(shown['state'], 'ready')
        self.assertIsNone(shown['deliver'])
        self.assertEqual(shown['execution'], 'conversation')
        after = decks.read_run(root)
        self.assertEqual(after['gates']['gate:build']['by'], 'Alex')
        self.assertEqual(after['gates']['gate:build']['note'], request['response'])
        for name, value in previous.items():
            if name != 'gate:build':
                self.assertEqual(after['gates'][name], value)

    def test_ready_invalidates_on_source_change_and_old_context_refuses(self):
        root = self.conversation()
        request = self.request(root)
        (root / 'sources').mkdir(exist_ok=True)
        (root / 'sources/new.txt').write_text('New evidence')
        with self.assertRaises(WorkspaceError):
            desk_chat.ready(self.engine, root, request)
        desk_chat.ready(self.engine, root, self.request(root))
        (root / 'sources/new.txt').write_text('Changed evidence')
        self.assertFalse(self.engine.view(root)['desk']['ready'])

    def test_ready_blocks_incomplete_missing_response_and_changed_blockers(self):
        root = self.conversation()
        request = self.request(root)
        with self.assertRaises(WorkspaceError):
            desk_chat.ready(self.engine, root, {**request, 'response': ''})
        state = build.read_state(root)
        state['audit']['messages'] = ['Slide 2: Synthetic brand blocker (error)']
        build.write_state(root, state)
        with self.assertRaises(WorkspaceError):
            desk_chat.ready(self.engine, root, request)
        context = self.request(root)
        with self.assertRaises(WorkspaceError):
            desk_chat.ready(self.engine, root, {**context, 'seen': {}})
        desk_chat.ready(self.engine, root, context)
        (root / build.DECK).unlink()
        with self.assertRaises(WorkspaceError):
            self.request(root)

    def test_migrated_person_approval_keeps_original_receipt_and_needs_no_jobs(self):
        root = self.gated()
        preview = desk_chat.migration_preview(self.engine, root)
        desk_chat.migrate(self.engine, root, preview['expected'])
        original = (root / 'run.json').read_bytes()
        receipt = (root / 'desk/migration-origin.json').read_bytes()
        request = self.request(root)
        with mock.patch.object(self.engine, 'ready', side_effect=AssertionError('runtime pin')), \
                mock.patch.object(self.engine, 'wake', side_effect=AssertionError('wake')), \
                mock.patch.object(self.engine, 'slides', side_effect=AssertionError('native job')), \
                mock.patch.object(self.engine, 'brand', side_effect=AssertionError('brand job')):
            shown = desk_chat.ready(self.engine, root, request)
        self.assertTrue(shown['desk']['ready'])
        self.assertIsNone(shown['deliver'])
        self.assertEqual((root / 'run.json').read_bytes(), original)
        self.assertEqual((root / 'desk/migration-origin.json').read_bytes(), receipt)

    def test_ready_refuses_unchecked_outline_contract_or_incomplete_audit(self):
        root = self.conversation()
        files = {name: (root / name).read_bytes() for name in ('outline.json', str(build.CONTRACT), str(build.STATE))}
        for name, data in files.items():
            value = json.loads(data)
            if name == 'outline.json':
                value['slides'][1]['title'] = 'Unchecked changed title'
            elif name == str(build.CONTRACT):
                value['synthetic_changed_contract'] = True
            else:
                value['audit'] = {}
            (root / name).write_text(json.dumps(value))
            with self.assertRaises(WorkspaceError):
                self.request(root)
            (root / name).write_bytes(data)

    def test_ready_requires_current_preview_images_and_recorded_hashes_without_repair(self):
        root = self.conversation()
        state = build.read_state(root)
        from runner import desk
        folders = (root / desk.last_round(state)['preview'], build.shots(root))
        for folder in folders:
            image = next(folder.glob('*.png'))
            original = image.read_bytes()
            other = next(path for path in folder.glob('*.png') if path != image)
            for changed in (None, other.read_bytes(), b'\x89PNG\r\n\x1a\ntruncated'):
                if changed is None:
                    image.unlink()
                else:
                    image.write_bytes(changed)
                before = MigrationTests.snapshot(self, root)
                with mock.patch.object(self.engine, 'slides', side_effect=AssertionError('render/repair')):
                    with self.assertRaises(WorkspaceError):
                        self.request(root)
                self.assertEqual(MigrationTests.snapshot(self, root), before)
                image.write_bytes(original)
        self.assertTrue(self.request(root)['seen']['expected'])
        state['rounds'][-1]['slides'][0].pop('sha256')
        build.write_state(root, state)
        with self.assertRaises(WorkspaceError):
            self.request(root)
