"""Training Studio unfinished migration over synthetic saved native formats."""
import copy
import io
import json
from pathlib import Path
from unittest import mock

import helpers
import home
import workspace
from runner import desk_chat, engine as engines, gitstate, pipeline, settings, studio, team
from runner_support import StudioCase, TeamCase, FORM, BLUEPRINT
from test_desk import ScriptedPage, ok, SET_UP, RUNNER, AGENTS_FOUND, MODELS
from test_runner_page import PageCase
from test_runner_deck import DeckCase
from test_desk_chat import ConversationTests
from workspace import WorkspaceError

SESSION = '.training-studio/session.json'
RUN = '.training-studio/run.json'
SIDES = ('.training-studio/desk/migration-origin.json', '.training-studio/desk/session.json', '.training-studio/desk/run.json')


class MigrationTests(StudioCase):
    def synthesis(self, root, capture_name='sources/capture.bin'):
        import hashlib
        from synthesis_fixture import published_bundle
        _, manifest = published_bundle(root / 'research', sources=[{'snapshot': 'research/' + capture_name}])
        capture = root / 'research' / capture_name
        capture.parent.mkdir()
        capture.write_bytes(b'Binary captured evidence\x80\xff')
        manifest['artifacts'].append({'file': capture_name, 'sha256': hashlib.sha256(capture.read_bytes()).hexdigest()})
        (root / 'research/output.json').write_text(json.dumps(manifest))
        session = workspace.load(root)
        session['research_contract'] = {'schema': 2, 'version': '1.0.0', 'digest': 'synthetic'}
        workspace.store(root, session)
        record = self.record(root)
        record.update(schema=3, research_contract=dict(session['research_contract']))
        self.engine._store(root, record)
        return capture

    def saved(self, title='Saved migration', halt=None):
        root = self.space.training(workspace.slugify(title))
        root.mkdir()
        form = pipeline.check_form({**FORM, 'title': title, 'levels': [], 'deck_target': None})
        workspace.init(root, title, approval='page')
        (root / 'intake.md').write_text(pipeline.intake_text(form))
        workspace.save(root, 'intake', built=True)
        workspace.approve(root, 'intake', by='page')
        file = root / '.training-studio/research-plan.json'
        file.write_text(json.dumps({'topic': 'Synthetic', 'items': []}))
        workspace.save(root, 'research-plan', built=True)
        workspace.approve(root, 'research-plan', by='page')
        research = root / '.harness-research'
        research.mkdir()
        (research / 'research.json').write_text(json.dumps(helpers.RESEARCH))
        (research / 'research-report.md').write_text('# Research\n\nSynthetic findings.\n')
        workspace.save(root, 'research', built=True)
        workspace.approve(root, 'research', by='page')
        (root / 'blueprint.md').write_text(BLUEPRINT)
        workspace.save(root, 'blueprint', built=True)
        record = engines.new_record('claude', None, settings.load())
        record['driver'] = team.claim(self.space)
        record['halt'] = halt
        self.engine._store(root, record)
        home.remember(root, title, [])
        gitstate.commit(self.space, 'synthetic saved training', [root])
        return root

    def snapshot(self, root):
        return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}

    def preview(self, root):
        return desk_chat.migration_preview(self.engine, root)

    def apply(self, root):
        preview = self.preview(root)
        self.assertEqual(preview['blockers'], [])
        return desk_chat.migrate(self.engine, root, preview['expected'])

    def test_unverified_index_restoration_keeps_recovery_journal(self):
        from runner import desk_migration, gitstate
        root = self.saved()
        marker = self.space.root / gitstate.MARKER
        relative = gitstate.inside(self.space, marker)
        self.git('rm', '--cached', '--', relative)
        token = self.preview(root)['expected']
        write = desk_migration._write
        run = gitstate.hub.run
        def fail(path, data):
            if Path(path).name == 'session.json':
                raise OSError('synthetic publication failure')
            write(path, data)
        def pretend_remove(repo, *args, **kwargs):
            if args[:2] == ('update-index', '--force-remove'):
                self.git('reset', '-q', 'HEAD', '--', relative)
                return run(repo, 'status', '--porcelain')
            return run(repo, *args, **kwargs)
        with mock.patch.object(desk_migration, '_write', side_effect=fail), \
                mock.patch.object(gitstate.hub, 'run', side_effect=pretend_remove):
            with self.assertRaisesRegex(WorkspaceError, 'index.*verified'):
                desk_chat.migrate(self.engine, root, token)
        self.assertTrue((root / desk_migration.format.PENDING).exists())

    def test_staged_marker_deletion_survives_failed_publication_and_recovery(self):
        import os
        import subprocess
        import sys
        from runner import desk_migration, gitstate
        for crash in (False, True):
            with self.subTest(crash=crash):
                root = self.saved('Deletion ' + str(crash))
                marker = self.space.root / gitstate.MARKER
                relative = gitstate.inside(self.space, marker)
                self.git('rm', '--cached', '--', relative)
                unrelated = self.space.repo / 'unrelated-staged.txt'
                unrelated.write_text('Unrelated staged content')
                self.git('add', '--', str(unrelated))
                before_index = self.git('ls-files', '--stage', '-z')
                before_marker = marker.read_bytes()
                before_files = self.snapshot(root)
                token = self.preview(root)['expected']
                self.assertEqual(self.preview(root)['blockers'], [])
                if crash:
                    code = """import os, sys
from pathlib import Path
from runner import desk_chat, desk_migration, engine
original = desk_migration._write
def crash(path, data):
    original(path, data)
    if Path(path).name == 'session.json': os._exit(71)
desk_migration._write = crash
desk_chat.migrate(engine.Engine(background=False), Path(sys.argv[1]), sys.argv[2])
"""
                    result = subprocess.run([sys.executable, '-c', code, str(root), token],
                        cwd=Path(__file__).resolve().parents[1], env={**os.environ, 'PYTHONPATH': '.:tests'},
                        capture_output=True, text=True, timeout=30)
                    self.assertEqual(result.returncode, 71, result.stderr)
                    self.assertTrue((root / desk_migration.format.PENDING).exists())
                    with self.assertRaisesRegex(WorkspaceError, 'rolled back'):
                        desk_chat.migrate(self.engine, root, token)
                else:
                    original = desk_migration._write
                    def fail(path, data):
                        if Path(path).name == 'session.json':
                            raise OSError('synthetic publication failure')
                        original(path, data)
                    with mock.patch.object(desk_migration, '_write', side_effect=fail), self.assertRaises(OSError):
                        desk_chat.migrate(self.engine, root, token)
                self.assertEqual(self.git('ls-files', '--stage', '-z'), before_index)
                self.assertEqual(marker.read_bytes(), before_marker)
                self.assertEqual(self.snapshot(root), before_files)
                self.assertFalse((root / desk_migration.format.PENDING).exists())
                self.git('reset', '-q', 'HEAD', '--', relative)
                self.git('reset', '-q', 'HEAD', '--', str(unrelated))
                unrelated.unlink()

    def test_row_190_preview_cancel_is_pure_and_bounded(self):
        root = self.saved()
        before = self.snapshot(self.base)
        with mock.patch.object(self.engine, 'view', side_effect=AssertionError('view')), mock.patch.object(self.engine, 'wake', side_effect=AssertionError('wake')):
            preview = self.preview(root)
        self.assertEqual(preview['blockers'], [])
        self.assertEqual(preview['scope'], ['part'])
        self.assertEqual(preview['targets'], ['blueprint'])
        self.assertEqual(self.snapshot(self.base), before)

    def test_row_191_original_pair_and_practice_history_survive_edit(self):
        root = self.saved(halt='stopped')
        before = self.snapshot(root)
        shown = self.apply(root)
        self.assertEqual(shown['execution'], 'conversation')
        self.assertIsNone(engines.read_record(root)['halt'])
        for name, data in before.items():
            self.assertEqual((root / name).read_bytes(), data, name)
        record = engines.read_record(root)
        self.assertEqual(record['steps'], json.loads(before[RUN])['steps'])
        card = self.engine.draft_card(root, 'blueprint')
        target = 'blueprint/' + card['sections'][0]['id']
        context = desk_chat.context(self.engine, root, target)
        desk_chat.save(self.engine, root, {'kind': 'part', 'target': target,
            'expected_basis': context['expected_basis'], 'payload': {'text': card['sections'][0]['text'] + '\nClearer.'}})
        self.assertEqual((root / SESSION).read_bytes(), before[SESSION])
        self.assertEqual((root / RUN).read_bytes(), before[RUN])
        self.assertTrue(self.engine.draft_versions(root, 'blueprint', card['sections'][0]['id'])['versions'])
        self.assertEqual(workspace.person_statuses(root, workspace.load(root))['blueprint'], 'draft')
        self.assertEqual(self.workers.jobs, [])

    def test_row_192_preview_changes_refuse_without_writes(self):
        for change in ('material', 'source', 'record', 'worker', 'floor'):
            root = self.saved('Change ' + change)
            token = self.preview(root)['expected']
            if change == 'material':
                (root / 'blueprint.md').write_text(BLUEPRINT + '\nChanged')
            elif change == 'source':
                (root / 'source-added.txt').write_text('Synthetic')
            elif change == 'record':
                session = workspace.load(root)
                session['next_step'] = 'Changed'
                workspace.store(root, session)
            elif change == 'worker':
                (root / engines.IN_HAND).write_text('blueprint')
            else:
                marker = self.space.root / gitstate.MARKER
                value = json.loads(marker.read_bytes())
                value['extra'] = 'changed'
                marker.write_text(json.dumps(value))
            before = self.snapshot(root)
            with self.assertRaises(WorkspaceError):
                desk_chat.migrate(self.engine, root, token)
            self.assertEqual(self.snapshot(root), before)
            (root / engines.IN_HAND).unlink(missing_ok=True)

    def test_local_only_uncommitted_input_stays_local_and_usable(self):
        root = self.saved()
        self.assertFalse(self.space.address)
        session = workspace.load(root)
        session['next_step'] = 'Uncommitted local original'
        workspace.store(root, session)
        (root / 'blueprint.md').write_text(BLUEPRINT + '\nUncommitted local plan.')
        original = self.snapshot(root)
        self.apply(root)
        self.assertEqual(self.engine._committed_session(root)['next_step'], 'Uncommitted local original')
        for name in (SESSION, RUN, 'blueprint.md'):
            self.assertEqual((root / name).read_bytes(), original[name])
        head = self.git('show', f'HEAD:{gitstate.inside(self.space, root / SESSION)}')
        self.assertNotIn('Uncommitted local original', head)

    def test_row_193_rollback_between_session_and_run_then_repeat(self):
        root = self.saved()
        token = self.preview(root)['expected']
        before = self.snapshot(root)
        marker = (self.space.root / gitstate.MARKER).read_bytes()
        from runner import desk_migration
        original = desk_migration._write
        def fail(path, data):
            if Path(path) == root / SIDES[2]:
                raise OSError('injected paired write failure')
            return original(path, data)
        with mock.patch.object(desk_migration, '_write', side_effect=fail), self.assertRaises(OSError):
            desk_chat.migrate(self.engine, root, token)
        self.assertEqual(self.snapshot(root), before)
        self.assertEqual((self.space.root / gitstate.MARKER).read_bytes(), marker)
        desk_chat.migrate(self.engine, root, token)
        applied = self.snapshot(root)
        desk_chat.migrate(self.engine, root, token)
        self.assertEqual(self.snapshot(root), applied)

    def test_missing_receipt_or_half_cannot_revert_to_legacy(self):
        root = self.saved()
        self.apply(root)
        for name in SIDES:
            data = (root / name).read_bytes()
            (root / name).unlink()
            with self.assertRaises(WorkspaceError):
                engines.read_record(root)
            with self.assertRaises(WorkspaceError):
                workspace.load(root)
            (root / name).write_bytes(data)

    def test_unsupported_early_and_missing_dependencies_stay_saved(self):
        root = self.saved()
        originals = self.snapshot(root)
        for name in ('blueprint.md', '.harness-research/research.json'):
            data = (root / name).read_bytes()
            (root / name).unlink()
            before = self.snapshot(root)
            self.assertTrue(self.preview(root)['blockers'])
            self.assertEqual(self.snapshot(root), before)
            (root / name).write_bytes(data)
        value = json.loads(originals[RUN])
        value['schema'] = 99
        (root / RUN).write_text(json.dumps(value))
        self.assertTrue(self.preview(root)['blockers'])

    def test_cli_preview_and_migrate_json(self):
        root = self.saved()
        out = io.StringIO()
        args = studio.parser().parse_args(['desk', 'migration-preview', '--folder', str(root)])
        studio.desk_command(args, make=lambda: self.engine, out=out)
        token = json.loads(out.getvalue())['expected']
        out = io.StringIO()
        args = studio.parser().parse_args(['desk', 'migrate', '--folder', str(root), '--expected', token])
        studio.desk_command(args, make=lambda: self.engine, out=out)
        self.assertEqual(json.loads(out.getvalue())['execution'], 'conversation')

    def test_strict_original_pair_and_shared_validation_agree(self):
        from studio_core.sync_guard import worker_in_progress
        for change in ('future', 'missing', 'worker', 'tool'):
            root = self.saved('Strict ' + change)
            record = self.record(root)
            if change == 'future':
                record['schema'] = True
            elif change == 'missing':
                record.pop('steps')
            elif change == 'worker':
                record['drafts'] = {'jobs': [{}]}
            else:
                record['deck'] = {'': {'notes': [{}]}}
            (root / RUN).write_text(json.dumps(record))
            before = self.snapshot(root)
            self.assertTrue(self.preview(root)['blockers'])
            self.assertEqual(self.snapshot(root), before)
        root = self.saved('Paired strict')
        self.apply(root)
        self.assertFalse(worker_in_progress(self.space.repo))
        original = (root / SIDES[2]).read_bytes()
        for key, replacement in (('steps', None), ('unfinished_migration', None), ('migration_scope_released', 'yes')):
            value = json.loads(original)
            if replacement is None:
                value['record'].pop(key)
            else:
                value['record'][key] = replacement
            (root / SIDES[2]).write_text(json.dumps(value))
            with self.assertRaises(WorkspaceError):
                engines.read_record(root)
            with self.assertRaises(ValueError):
                worker_in_progress(self.space.repo)
        (root / SIDES[2]).write_bytes(original)

    def test_missing_required_plan_blocks_domain_and_replay(self):
        from studio_core.sync_guard import worker_in_progress
        root = self.saved()
        self.apply(root)
        (root / 'blueprint.md').unlink()
        with self.assertRaises(WorkspaceError):
            engines.read_record(root)
        with self.assertRaises(ValueError):
            worker_in_progress(self.space.repo)

    def test_declared_research_and_retained_material_remain_required(self):
        from studio_core.sync_guard import worker_in_progress
        root = self.saved()
        from runner_support import DOCUMENT
        (root / 'document.md').write_text(DOCUMENT)
        workspace.save(root, 'document', built=True)
        self.apply(root)
        snapshots = {name: (root / name).read_bytes() for name in SIDES}
        origin = json.loads(snapshots[SIDES[0]])
        origin['required'].remove('.harness-research/research.json')
        (root / SIDES[0]).write_text(json.dumps(origin))
        for name in SIDES[1:]:
            value = json.loads(snapshots[name])
            value['origin'] = origin
            (root / name).write_text(json.dumps(value))
        with self.assertRaises(WorkspaceError):
            workspace.load(root)
        with self.assertRaises(ValueError):
            worker_in_progress(self.space.repo)
        for name, data in snapshots.items():
            (root / name).write_bytes(data)
        for name in ('.harness-research/research.json', '.training-studio/research-plan.json',
                     'research-report.md', 'intake.md', 'document.md'):
            file = root / name
            original = file.read_bytes()
            for changed in (None, b'{}' if file.suffix == '.json' else b''):
                if changed is None:
                    file.unlink()
                else:
                    file.write_bytes(changed)
                with self.assertRaises(WorkspaceError, msg=name):
                    workspace.load(root)
                with self.assertRaises(ValueError, msg=name):
                    worker_in_progress(self.space.repo)
                file.write_bytes(original)
        self.assertEqual(workspace.load(root)['flow'], 'desk')
        self.assertFalse(worker_in_progress(self.space.repo))

    def test_unknown_update_chain_refuses_original_and_effective_state(self):
        from studio_core.sync_guard import worker_in_progress
        for chain in ({'status': 'unknown'}, {'id': 'a' * 24, 'level': None},
                      {'id': 'a' * 24, 'level': None, 'status': 'done', 'blocked': 'blueprint'}):
            root = self.saved('Unknown chain ' + str(len(self.engine.trainings())))
            original = (root / RUN).read_bytes()
            record = self.record(root)
            record['drafts'] = {'update_chain': chain}
            (root / RUN).write_text(json.dumps(record))
            before = self.snapshot(root)
            self.assertTrue(self.preview(root)['blockers'])
            self.assertEqual(self.snapshot(root), before)
            with self.assertRaises(WorkspaceError):
                engines.read_record(root)
            with self.assertRaises(ValueError):
                worker_in_progress(self.space.repo)
            (root / RUN).write_bytes(original)
        root = self.saved('Effective chain')
        self.apply(root)
        file = root / SIDES[2]
        original = file.read_bytes()
        value = json.loads(original)
        value['record']['drafts'] = {'update_chain': {'status': 'unknown'}}
        file.write_text(json.dumps(value))
        with self.assertRaises(WorkspaceError):
            engines.read_record(root)
        with self.assertRaises(ValueError):
            worker_in_progress(self.space.repo)

    def test_native_inactive_update_chains_preserved_and_working_is_busy(self):
        from studio_core.sync_guard import worker_in_progress
        for status in ('done', 'stopped'):
            root = self.saved('Native chain ' + status)
            record = self.record(root)
            chain = {'id': 'a' * 24, 'level': None, 'status': status, 'blocked': ['blueprint']}
            record['drafts'] = {'update_chain': chain}
            (root / RUN).write_text(json.dumps(record))
            self.assertFalse(worker_in_progress(self.space.repo))
            self.apply(root)
            self.assertEqual(engines.read_record(root)['drafts']['update_chain'], chain)
        root = self.saved('Native chain active')
        record = self.record(root)
        record['drafts'] = {'update_chain': {'id': 'b' * 24, 'level': None, 'status': 'working'}}
        (root / RUN).write_text(json.dumps(record))
        self.assertTrue(self.preview(root)['blockers'])
        self.assertTrue(worker_in_progress(self.space.repo))

    def test_native_private_sources_and_profile_are_local_prerequisites(self):
        from studio_core.sync_guard import worker_in_progress
        from runner_support import BRIEF, SCENARIO, YOODLI
        from runner import documents
        root = self.saved()
        source = documents.add(root, 'supplied.txt', b'Synthetic private source.\n')
        (root / 'product-brief.md').write_text(BRIEF)
        workspace.save(root, 'brief', built=True)
        (root / 'scenario.md').write_text(SCENARIO)
        workspace.save(root, 'scenario:main', built=True)
        (root / 'yoodli').mkdir()
        (root / 'yoodli/main.md').write_text(YOODLI)
        workspace.save(root, 'yoodli:main', built=True)
        profile = self.base / 'private-profile.json'
        original_profile = workspace.profile_for(root).read_bytes()
        profile.write_bytes(original_profile)
        with mock.patch.object(workspace, 'profile_for', return_value=profile):
            token = self.preview(root)['expected']
            value = json.loads(original_profile)
            value['scope_note'] = 'Local profile changed after preview'
            profile.write_text(json.dumps(value))
            before = self.snapshot(root)
            with self.assertRaises(WorkspaceError):
                desk_chat.migrate(self.engine, root, token)
            self.assertEqual(self.snapshot(root), before)
            profile.write_text(json.dumps({'schema': 1, 'profile': 'yoodli', 'types': [], 'limits': {}}))
            self.assertTrue(self.preview(root)['blockers'])
        profile.write_bytes(original_profile)
        self.apply(root)
        origin = json.loads((root / SIDES[0]).read_bytes())
        self.assertTrue(origin['local']['sources'])
        self.assertTrue(origin['local']['profile'])
        self.assertNotIn(source['original'], origin['required'])
        for name in (source['original'], source['file'], documents.INDEX):
            original = (root / name).read_bytes()
            (root / name).unlink()
            with self.assertRaises(WorkspaceError):
                workspace.load(root)
            # A peer does not receive private sources or this computer's installed profile.
            self.assertFalse(worker_in_progress(self.space.repo))
            (root / name).write_bytes(original)
        with mock.patch.object(workspace, 'profile_for', return_value=self.base / 'missing-profile.json'):
            with self.assertRaises(WorkspaceError):
                workspace.load(root)
            self.assertFalse(worker_in_progress(self.space.repo))
        profile.write_text(json.dumps({'schema': 1, 'profile': 'yoodli', 'types': [], 'limits': {}}))
        with mock.patch.object(workspace, 'profile_for', return_value=profile):
            with self.assertRaises(WorkspaceError):
                workspace.load(root)
        self.assertEqual(workspace.load(root)['flow'], 'desk')

    def test_native_synthesis_bundle_is_checked_after_migration(self):
        from studio_core.sync_guard import worker_in_progress
        root = self.saved()
        capture = self.synthesis(root)
        self.apply(root)
        for file in (root / 'research/evidence.md', capture):
            original = file.read_bytes()
            file.write_bytes(original + b'Unreviewed change')
            with self.assertRaises(WorkspaceError):
                workspace.load(root)
            with self.assertRaises(ValueError):
                worker_in_progress(self.space.repo)
            file.write_bytes(original)
        self.assertEqual(workspace.load(root)['flow'], 'desk')

    def test_pending_journal_blocks_helper_recovery_and_replay(self):
        from studio_core.sync_guard import worker_in_progress
        import write_guard
        root = self.saved()
        journal = root / 'work/desk/migration-transaction.json'
        journal.parent.mkdir(parents=True)
        journal.write_text('{interrupted')
        before = self.snapshot(root)
        self.assertTrue(worker_in_progress(self.space.repo))
        for held in (None, self.engine.files):
            with self.engine.files, self.assertRaises(WorkspaceError), write_guard.admitted(root, held=held):
                self.fail('admitted')
        self.assertNotIn(root, self.engine._tidy())
        self.assertEqual(self.snapshot(root), before)

    def test_explicit_ready_uses_effective_facts_and_receipt_is_immutable(self):
        root = self.saved()
        before = (root / SESSION).read_bytes(), (root / RUN).read_bytes()
        self.apply(root)
        receipt = (root / SIDES[0]).read_bytes()
        context = desk_chat.context(self.engine, root, 'ready/blueprint')
        desk_chat.ready(self.engine, root, {'target': 'blueprint', 'expected_basis': context['expected_basis'],
            'seen': context['requirements']['seen'], 'response': 'I approve this saved teaching plan.'})
        self.assertEqual(workspace.person_statuses(root, workspace.load(root))['blueprint'], 'approved')
        self.assertEqual(((root / SESSION).read_bytes(), (root / RUN).read_bytes()), before)
        self.assertEqual((root / SIDES[0]).read_bytes(), receipt)
        self.assertEqual(engines.read_record(root)['execution'], 'conversation')
        self.assertEqual(self.workers.jobs, [])

    def test_effective_only_changes_invalidate_context_and_legacy_helper_writes(self):
        import write_guard
        root = self.saved()
        self.apply(root)
        card = self.engine.draft_card(root, 'blueprint')
        target = 'blueprint/' + card['sections'][0]['id']
        context = desk_chat.context(self.engine, root, target)
        original = (root / RUN).read_bytes()
        record = engines.read_record(root)
        record['answers']['new'] = 'A current answer'
        self.engine._store(root, record)
        before = self.snapshot(root)
        with self.assertRaises(WorkspaceError):
            desk_chat.save(self.engine, root, {'kind': 'part', 'target': target, 'expected_basis': context['expected_basis'], 'payload': {'text': 'Outdated'}})
        for held in (None, self.engine.files):
            with self.engine.files, self.assertRaises(WorkspaceError), write_guard.admitted(root, held=held):
                self.fail('legacy admitted')
        self.assertEqual(self.snapshot(root), before)
        self.assertEqual((root / RUN).read_bytes(), original)
        with self.assertRaises(WorkspaceError):
            desk_chat.context(self.engine, root, 'document/opening')
        current = desk_chat.context(self.engine, root, 'scope')
        desk_chat.set_scope(self.engine, root, current['expected_basis'], ['part', 'text'])
        self.assertTrue(engines.read_record(root)['migration_scope_released'])
        self.assertEqual((root / RUN).read_bytes(), original)

    def test_known_halts_preserve_history_but_failures_questions_and_jobs_block(self):
        for halt in ('paused', 'stopped'):
            root = self.saved('Halt ' + halt, halt)
            original = (root / RUN).read_bytes()
            self.apply(root)
            self.assertEqual(engines.read_record(root)['migration_saved_status']['halt'], halt)
            self.assertIsNone(engines.read_record(root)['halt'])
            self.assertEqual((root / RUN).read_bytes(), original)
        for key, value in (('halt', 'unknown'), ('problem', {'state': 'failed', 'what': 'Failed material'}),
                           ('question', {'text': 'A real question'}), ('drafts', {'jobs': [{'status': 'queued'}]})):
            root = self.saved('Block ' + key)
            record = self.record(root)
            record[key] = value
            (root / RUN).write_text(json.dumps(record))
            before = self.snapshot(root)
            self.assertTrue(self.preview(root)['blockers'])
            self.assertEqual(self.snapshot(root), before)

    def test_schema_policy_and_real_versus_automatic_approvals_preserved(self):
        for schema in (1, 2, 3):
            root = self.saved('Schema ' + str(schema))
            record = self.record(root)
            record['schema'] = schema
            if schema == 3:
                record['research_contract'] = {'schema': 2}
            (root / RUN).write_text(json.dumps(record))
            session = workspace.load(root)
            entry = session['artifacts']['blueprint']
            entry['approved'] = {'sha256': entry['sha256'], 'inputs': dict(entry['built_from']), 'at': home.now(), 'by': 'review-policy' if schema == 2 else 'page'}
            workspace.store(root, session)
            before = copy.deepcopy(session)
            self.apply(root)
            effective = workspace.load(root)
            self.assertEqual(effective['artifacts'], before['artifacts'])
            self.assertEqual(effective.get('practice_inputs'), before.get('practice_inputs'))
            self.assertEqual(workspace.person_statuses(root, effective)['blueprint'], 'draft' if schema == 2 else 'approved')

    def test_floor_rollback_preserves_higher_floor_unrelated_marker_and_staging(self):
        root = self.saved()
        marker = self.space.root / gitstate.MARKER
        value = json.loads(marker.read_bytes())
        value['minimum_runtime'] = '4.6.1'
        value['extra'] = {'keep': True}
        marker.write_text(json.dumps(value))
        unrelated = self.space.root / 'unrelated.txt'
        unrelated.write_text('Keep staged')
        self.git('add', str(unrelated))
        index = self.git('diff', '--cached')
        token = self.preview(root)['expected']
        with mock.patch.object(gitstate, 'commit', side_effect=OSError('commit refused')), self.assertRaises(OSError):
            desk_chat.migrate(self.engine, root, token)
        self.assertEqual(json.loads(marker.read_bytes()), value)
        self.assertEqual(self.git('diff', '--cached'), index)
        self.apply(root)
        self.assertEqual(json.loads(marker.read_bytes())['minimum_runtime'], '4.7.0')
        self.assertEqual(json.loads(marker.read_bytes())['extra'], {'keep': True})
        self.assertEqual(self.git('diff', '--cached'), index)
        # Future configured floor is enforced without changing any marker.
        value['minimum_runtime'] = '99.0.0'
        marker.write_text(json.dumps(value))
        self.assertTrue(self.preview(root)['blockers'])
        with self.assertRaises(WorkspaceError):
            self.engine.hold(root, conversation=True)

    def test_commit_then_raise_preserves_pair_until_explicit_recovery(self):
        root = self.saved()
        token = self.preview(root)['expected']
        commit = gitstate.commit
        def fail_after(*args, **kwargs):
            commit(*args, **kwargs)
            raise OSError('after durable commit')
        with mock.patch.object(gitstate, 'commit', side_effect=fail_after), self.assertRaises(OSError):
            desk_chat.migrate(self.engine, root, token)
        self.assertTrue((root / 'work/desk/migration-transaction.json').exists())
        with self.assertRaises(WorkspaceError):
            engines.read_record(root)
        desk_chat.migrate(self.engine, root, token)
        self.assertEqual(engines.read_record(root)['execution'], 'conversation')
        self.assertFalse((root / 'work/desk/migration-transaction.json').exists())

    def test_recovery_preserves_unexpected_staging_before_any_mutation(self):
        from runner import desk_migration
        for committed in (False, True):
            root = self.saved('Recovery index ' + str(committed))
            token = self.preview(root)['expected']
            commit = gitstate.commit
            def interrupt(*args, **kwargs):
                if committed:
                    commit(*args, **kwargs)
                raise OSError('interrupted commit inspection')
            inspection = mock.patch.object(desk_migration, '_committed', side_effect=OSError('inspection uncertain')) if not committed else mock.patch.object(desk_migration, '_committed', wraps=desk_migration._committed)
            with mock.patch.object(gitstate, 'commit', side_effect=interrupt), inspection, self.assertRaises(OSError):
                desk_chat.migrate(self.engine, root, token)
            file = root / SIDES[1]
            prepared = file.read_bytes()
            value = json.loads(prepared)
            value['record']['title'] = 'Different staged person work'
            file.write_text(json.dumps(value))
            self.git('add', str(file))
            file.write_bytes(prepared)
            before, index = self.snapshot(root), self.git('ls-files', '--stage', '-z')
            marker = (self.space.root / gitstate.MARKER).read_bytes()
            head = self.git('rev-parse', 'HEAD')
            with self.assertRaisesRegex(WorkspaceError, 'index|staging'):
                desk_chat.migrate(self.engine, root, token)
            self.assertEqual(self.snapshot(root), before)
            self.assertEqual(self.git('ls-files', '--stage', '-z'), index)
            self.assertEqual((self.space.root / gitstate.MARKER).read_bytes(), marker)
            self.assertEqual(self.git('rev-parse', 'HEAD'), head)
            self.git('add', '--', *(str(root / name) for name in SIDES), str(self.space.root / gitstate.MARKER))
            if committed:
                desk_chat.migrate(self.engine, root, token)
            else:
                with self.assertRaisesRegex(WorkspaceError, 'rolled back'):
                    desk_chat.migrate(self.engine, root, token)

    def publication_state(self):
        return (self.snapshot(self.space.root), self.git('ls-files', '--stage', '-z'), self.git('rev-parse', 'HEAD'))

    def partial_publication(self, selected):
        from runner import desk_migration
        root = self.saved()
        marker = self.space.root / gitstate.MARKER
        value = json.loads(marker.read_bytes())
        value['minimum_runtime'] = '4.6.1'
        marker.write_text(json.dumps(value))
        self.git('add', str(marker))
        self.git('commit', '-m', 'Synthetic prior floor', '--only', str(marker))
        unrelated = self.space.root / 'unrelated-staged.txt'
        unrelated.write_text('Unrelated person work')
        self.git('add', str(unrelated))
        paths = [root / name for name in SIDES] + [marker]
        token = self.preview(root)['expected']
        captured = []

        def partial(*args, **kwargs):
            self.git('add', '--', *(str(path) for path in paths))
            self.git('commit', '-m', 'Synthetic partial publication', '--only', str(paths[selected]))
            captured.append(self.publication_state())
            raise OSError('partial commit returned an error')

        with mock.patch.object(gitstate, 'commit', side_effect=partial), self.assertRaises((OSError, WorkspaceError)):
            desk_chat.migrate(self.engine, root, token)
        self.assertEqual(self.publication_state(), captured[0])
        with self.assertRaises(WorkspaceError):
            desk_chat.migrate(self.engine, root, token)
        self.assertEqual(self.publication_state(), captured[0])
        self.assertTrue((root / desk_migration.format.PENDING).exists())

    def test_partial_receipt_commit_preserves_exception_and_retry(self):
        self.partial_publication(0)

    def test_partial_session_commit_preserves_exception_and_retry(self):
        self.partial_publication(1)

    def test_partial_run_commit_preserves_exception_and_retry(self):
        self.partial_publication(2)

    def test_partial_marker_commit_preserves_exception_and_retry(self):
        self.partial_publication(3)

    def test_exception_preserves_changed_outputs_before_rollback(self):
        import shutil
        for selected in range(4):
            with self.subTest(selected=selected):
                root = self.saved('Changed output ' + str(selected))
                token = self.preview(root)['expected']
                paths = [root / name for name in SIDES] + [self.space.root / gitstate.MARKER]
                captured = []

                def change(*args, **kwargs):
                    paths[selected].write_bytes(paths[selected].read_bytes() + b'\nLater person bytes\n')
                    captured.append(self.publication_state())
                    raise OSError('changed output before failure')

                with mock.patch.object(gitstate, 'commit', side_effect=change), self.assertRaises((OSError, WorkspaceError)):
                    desk_chat.migrate(self.engine, root, token)
                self.assertEqual(self.publication_state(), captured[0])
                # Discard only this disposable fixture after preservation is proven.
                shutil.rmtree(root)
                if selected == 3:
                    paths[3].write_bytes(captured[0][0][gitstate.MARKER].split(b'\nLater person bytes\n')[0])

    def test_exception_preserves_missing_marker_and_durable_changed_output(self):
        import shutil
        for committed in (False, True):
            with self.subTest(committed=committed):
                root = self.saved('Exception complete ' + str(committed))
                token = self.preview(root)['expected']
                marker = self.space.root / gitstate.MARKER
                marker_bytes = marker.read_bytes()
                commit, captured = gitstate.commit, []

                def fail(*args, **kwargs):
                    if committed:
                        commit(*args, **kwargs)
                        (root / SIDES[1]).write_bytes((root / SIDES[1]).read_bytes() + b'\nLater bytes\n')
                    else:
                        marker.unlink()
                    captured.append(self.publication_state())
                    raise OSError('publication output uncertain')

                with mock.patch.object(gitstate, 'commit', side_effect=fail), self.assertRaises(WorkspaceError):
                    desk_chat.migrate(self.engine, root, token)
                self.assertEqual(self.publication_state(), captured[0])
                shutil.rmtree(root)
                marker.write_bytes(marker_bytes)

    def test_local_preview_binds_scoped_head_and_retains_dirty_support(self):
        root = self.saved()
        marker = self.space.root / gitstate.MARKER
        value = json.loads(marker.read_bytes())
        value['local_person_setting'] = 'Retain this local edit'
        marker.write_text(json.dumps(value))
        self.git('add', str(marker))
        token = self.preview(root)['expected']
        unrelated = self.space.root / 'unrelated-commit.txt'
        unrelated.write_text('Unrelated committed work')
        self.git('add', str(unrelated))
        self.git('commit', '-m', 'Unrelated local commit', '--only', str(unrelated))
        self.assertEqual(self.preview(root)['expected'], token)
        # Same worktree AND scoped index; only the scoped HEAD entry changes.
        index = self.git('ls-files', '--stage', '-z')
        self.git('commit', '-m', 'Explicit local marker commit', '--only', str(marker))
        self.assertEqual(self.git('ls-files', '--stage', '-z'), index)
        before = self.publication_state()
        with self.assertRaises(WorkspaceError):
            desk_chat.migrate(self.engine, root, token)
        self.assertEqual(self.publication_state(), before)
        self.apply(root)
        self.assertEqual(json.loads(marker.read_bytes())['local_person_setting'], value['local_person_setting'])

    def test_committed_recovery_requires_every_exact_current_output(self):
        from runner import desk_migration
        root = self.saved()
        marker = self.space.root / gitstate.MARKER
        value = json.loads(marker.read_bytes())
        value['minimum_runtime'] = '4.6.1'
        before_marker = json.dumps(value).encode()
        marker.write_bytes(before_marker)
        token = self.preview(root)['expected']
        commit = gitstate.commit

        def durable(*args, **kwargs):
            commit(*args, **kwargs)
            raise OSError('durable publication interrupted')

        with mock.patch.object(gitstate, 'commit', side_effect=durable), self.assertRaises(OSError):
            desk_chat.migrate(self.engine, root, token)
        paths = [root / name for name in SIDES] + [marker]
        for path in paths:
            prepared = path.read_bytes()
            for changed in (None, prepared + b'\nChanged\n') + ((before_marker,) if path == marker else ()):
                with self.subTest(path=path.name, changed=changed is not None):
                    if changed is None:
                        path.unlink()
                    else:
                        path.write_bytes(changed)
                    before = self.publication_state()
                    with self.assertRaises(WorkspaceError):
                        desk_chat.migrate(self.engine, root, token)
                    self.assertEqual(self.publication_state(), before)
                    path.write_bytes(prepared)
        self.assertTrue((root / desk_migration.format.PENDING).exists())
        desk_chat.migrate(self.engine, root, token)
        self.assertFalse((root / desk_migration.format.PENDING).exists())

    def test_older_journal_without_scoped_head_refuses_intact(self):
        from runner import desk_migration
        root = self.saved()
        token = self.preview(root)['expected']
        with mock.patch.object(gitstate, 'commit', side_effect=OSError('interrupted')), \
                mock.patch.object(desk_migration, '_committed', side_effect=OSError('uncertain')), self.assertRaises(OSError):
            desk_chat.migrate(self.engine, root, token)
        pending = root / desk_migration.format.PENDING
        journal = json.loads(pending.read_bytes())
        journal.pop('head_before', None)
        pending.write_text(json.dumps(journal))
        before = self.publication_state()
        with self.assertRaises(WorkspaceError):
            desk_chat.migrate(self.engine, root, token)
        self.assertEqual(self.publication_state(), before)

    def test_page_preview_apply_and_finished_adoption_stay_distinct(self):
        from runner import page
        root = self.saved()
        native = page.RunnerPage(8765, self.engine)
        before = self.snapshot(root)
        status, headers, body = native.read('/api/drafts/migration-preview', lambda key: str(root))
        preview = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(self.snapshot(root), before)
        with mock.patch.object(self.engine, 'ready', side_effect=AssertionError('probe')), mock.patch.object(self.engine, 'wake', side_effect=AssertionError('wake')):
            status, _, body = native.write('/api/drafts/migrate', {'path': str(root), 'expected': preview['expected']})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['flow'], 'desk')
        self.assertEqual(workspace.load(root)['artifacts'], json.loads(before[SESSION])['artifacts'])
        self.assertEqual((root / SESSION).read_bytes(), before[SESSION])

    def test_real_process_exit_between_pair_writes_and_explicit_rollback(self):
        import os
        import subprocess
        import sys
        root = self.saved()
        token = self.preview(root)['expected']
        before = self.snapshot(root)
        code = '''import os,sys
from pathlib import Path
from runner import desk_chat,desk_migration,engine
root=Path(sys.argv[1]); original=desk_migration._write
def crash(path,data):
 original(path,data)
 if Path(path)==root/'.training-studio/desk/session.json': os._exit(71)
desk_migration._write=crash
desk_chat.migrate(engine.Engine(background=False),root,sys.argv[2])
'''
        result = subprocess.run([sys.executable, '-c', code, str(root), token], env=os.environ.copy(), capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 71, result.stderr)
        with self.assertRaises(WorkspaceError):
            workspace.load(root)
        self.assertNotIn(root, self.engine._tidy())
        with self.assertRaisesRegex(WorkspaceError, 'rolled back'):
            desk_chat.migrate(self.engine, root, token)
        self.assertEqual(self.snapshot(root), before)

    def test_real_two_process_apply_registers_one_migration(self):
        import os
        import subprocess
        import sys
        root = self.saved()
        token = self.preview(root)['expected']
        code = '''import sys
from pathlib import Path
from runner import desk_chat,engine
desk_chat.migrate(engine.Engine(background=False),Path(sys.argv[1]),sys.argv[2])
'''
        processes = [subprocess.Popen([sys.executable, '-c', code, str(root), token], env=os.environ.copy(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
        for child in processes:
            try:
                stdout, stderr = child.communicate(timeout=25)
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait()
            self.assertEqual(child.returncode, 0, stderr)
        self.assertEqual(sum('open unfinished work' in message for message in self.log()), 1)

    def pending_google(self):
        import zipfile
        root = self.saved()
        session = workspace.load(root)
        session['settings']['deck_target'] = 'google'
        session['settings']['stages'] = ['deck']
        workspace.store(root, session)
        (root / 'deck-link.md').write_text('https://docs.google.com/presentation/d/synthetic\n')
        workspace.save(root, 'deck', built=True)
        before = desk_chat._files(root)
        desk_chat._capture_restore(root, before, 'deck')
        restore = (root / 'deck/delivered-state.json').read_bytes()
        source = self.base / 'checked-local.pptx'
        with zipfile.ZipFile(source, 'w') as archive:
            archive.writestr('ppt/slides/slide1.xml', '<synthetic/>')
        workspace.stage_local_deck(root, 'deck', source, restore_sha256=__import__('hashlib').sha256(restore).hexdigest())
        return root, restore, before

    def test_pending_google_replacement_preserves_state_on_failure(self):
        import zipfile
        root, restore, _ = self.pending_google()
        self.apply(root)
        first = workspace.load(root)['pending_local_decks']['deck']
        source = self.base / 'replacement.pptx'
        with zipfile.ZipFile(source, 'w') as archive:
            archive.writestr('ppt/slides/slide1.xml', '<changed-synthetic/>')
        original = self.snapshot(root)
        atomic = workspace.write_atomic
        session_path = root / SIDES[1]
        draft_path = root / 'deck/local-draft.pptx'
        history_path = workspace.history_file(root, 'deck', first['sha256'], '.pptx')
        for target, after in ((history_path, False), (history_path, True), (draft_path, False), (draft_path, True),
                              (session_path, False), (session_path, True)):
            with self.subTest(target=target.name, after=after):
                failed = False

                def failing(path, data):
                    nonlocal failed
                    if path == target and not failed:
                        failed = True
                        if after:
                            atomic(path, data)
                        raise OSError('synthetic local draft publication failure')
                    atomic(path, data)

                with mock.patch.object(workspace, 'write_atomic', side_effect=failing):
                    with self.assertRaisesRegex((OSError, WorkspaceError), 'synthetic local draft'):
                        workspace.stage_local_deck(root, 'deck', source, restore_sha256=first['restore_sha256'])
                self.assertEqual(self.snapshot(root), original)
                self.assertEqual(workspace.load(root)['pending_local_decks']['deck'], first)
                self.assertEqual(engines.read_record(root)['delivered_restore']['deck'], first['restore_sha256'])
        workspace.stage_local_deck(root, 'deck', source, restore_sha256=first['restore_sha256'])
        current = workspace.load(root)['pending_local_decks']['deck']
        self.assertEqual(draft_path.read_bytes(), source.read_bytes())
        self.assertNotEqual(current['sha256'], first['sha256'])
        self.assertEqual(current['restore_sha256'], first['restore_sha256'])
        self.assertEqual((root / 'deck/delivered-state.json').read_bytes(), restore)
        self.assertEqual(workspace.history_file(root, 'deck', first['sha256'], '.pptx').read_bytes(), original['deck/local-draft.pptx'])
        for path in (SESSION, RUN, SIDES[0], SIDES[2], 'deck-link.md'):
            self.assertEqual((root / path).read_bytes(), original[path])
        # Damaged current bytes remain a refusal; the replacement is no repair bypass.
        draft_path.write_bytes(b'PK\x03\x04 damaged current drawing')
        damaged = self.snapshot(root)
        with self.assertRaises(WorkspaceError):
            workspace.stage_local_deck(root, 'deck', source, restore_sha256=first['restore_sha256'])
        self.assertEqual(self.snapshot(root), damaged)

    def test_pending_google_restore_binding_and_return_use_effective_pair(self):
        from runner import desk_migration
        root, restore, before = self.pending_google()
        original_session, original_run = (root / SESSION).read_bytes(), (root / RUN).read_bytes()
        self.apply(root)
        self.assertEqual((root / 'deck/delivered-state.json').read_bytes(), restore)
        (root / 'deck/delivered-state.json').write_bytes(restore + b' ')
        with self.assertRaises(WorkspaceError):
            workspace.load(root)
        (root / 'deck/delivered-state.json').write_bytes(restore)
        self.assertEqual(engines.read_record(root)['delivered_restore']['deck'], __import__('hashlib').sha256(restore).hexdigest())
        context = desk_chat.context(self.engine, root, 'ready/deck')
        canonical = self.snapshot(root)
        with self.assertRaises(WorkspaceError):
            desk_chat.ready(self.engine, root, {'target': 'deck', 'expected_basis': context['expected_basis'], 'seen': context['requirements']['seen'], 'response': 'Approve'})
        self.assertEqual(self.snapshot(root), canonical)
        context = desk_chat.context(self.engine, root, 'return-delivered')
        desk_chat.return_delivered(self.engine, root, {'target': 'return-delivered', 'expected_basis': context['expected_basis'], 'seen': context['requirements']['seen'], 'response': 'Return to the saved delivered deck and retain local work.'})
        self.assertFalse(workspace.load(root).get('pending_local_decks'))
        self.assertFalse(engines.read_record(root).get('delivered_restore'))
        self.assertEqual((root / 'deck-link.md').read_bytes(), before['deck-link.md'])
        self.assertTrue(list((root / 'history/deck-local').rglob('local-draft.pptx')))
        self.assertEqual((root / SESSION).read_bytes(), original_session)
        self.assertEqual((root / RUN).read_bytes(), original_run)
        self.assertEqual(desk_migration.CONSEQUENCES.count('4.7.0'), 1)




class MigrationGoogleTests(DeckCase):
    snapshot = MigrationTests.snapshot
    preview = MigrationTests.preview
    apply = MigrationTests.apply
    submit = ConversationTests.submit

    def record(self, root):
        return engines.read_record(root)

    def test_checked_conversation_repeated_local_edits_preserve_delivered_state(self):
        root = self.saved_begin(deck_target='google')
        self.drawn(root)
        self.assertNotEqual(workspace.load(root)['stage'], 'done')
        (root / '.training-studio/google-baseline.json').write_text('{"revision":"synthetic-existing-google-revision"}\n')
        original = self.snapshot(root)
        self.apply(root)
        migrated = self.snapshot(root)
        with mock.patch.object(self.engine, '_deck_here', side_effect=AssertionError('passive tool probe')), \
                mock.patch.object(self.documents, 'listed', side_effect=AssertionError('passive source repair')):
            self.engine._survey(root, self.record(root))
            self.engine.view(root)
        self.assertEqual(self.snapshot(root), migrated)
        count = len(self.workers.jobs)
        survey = engines.Engine._deck_here
        checked = []

        def checked_survey(staged, path, record):
            self.assertTrue(staged._local_decks_only)
            self.assertNotEqual(path, root)
            self.assertEqual(path.name, root.name)
            checked.append(path)
            return survey(staged, path, record)

        with mock.patch.object(self.slides, 'drive_import', side_effect=AssertionError('delivery')), \
                mock.patch.object(engines.Engine, '_deck_here', checked_survey):
            self.submit(root, 'deck/check-yourself/notes', 'part', {'text': 'First checked local note.'})
            first = workspace.load(root)['pending_local_decks']['deck']
            first_bytes = (root / 'deck/local-draft.pptx').read_bytes()
            before = self.snapshot(root)
            from runner import gitstate
            with mock.patch.object(gitstate, 'commit', side_effect=WorkspaceError('synthetic checked publication failure')):
                with self.assertRaisesRegex(WorkspaceError, 'synthetic checked publication'):
                    self.submit(root, 'deck/check-yourself/notes', 'part', {'text': 'Second checked local note.'})
            self.assertEqual(self.snapshot(root), before)
            self.assertEqual(workspace.load(root)['pending_local_decks']['deck'], first)
            self.submit(root, 'deck/check-yourself/notes', 'part', {'text': 'Second checked local note.'})
        current = workspace.load(root)['pending_local_decks']['deck']
        self.assertNotEqual(current['sha256'], first['sha256'])
        self.assertNotEqual((root / 'deck/local-draft.pptx').read_bytes(), first_bytes)
        self.assertEqual(current['restore_sha256'], first['restore_sha256'])
        self.assertEqual(workspace.history_file(root, 'deck', first['sha256'], '.pptx').read_bytes(), first_bytes)
        for path in (SESSION, RUN, 'deck-link.md', '.training-studio/google-baseline.json'):
            self.assertEqual((root / path).read_bytes(), original[path])
        self.assertEqual(len(self.workers.jobs), count)
        self.assertFalse(self.record(root).get('drafts', {}).get('jobs'))
        self.assertEqual(workspace.person_statuses(root, workspace.load(root))['deck'], 'draft')
        self.assertTrue(checked)
        self.assertEqual((root / SIDES[0]).read_bytes(), migrated[SIDES[0]])


class MigrationTeamTests(TeamCase):
    synthesis = MigrationTests.synthesis
    saved = MigrationTests.saved
    snapshot = MigrationTests.snapshot
    preview = MigrationTests.preview
    apply = MigrationTests.apply

    def test_teammate_changed_owner_invalidates_preview(self):
        root = self.saved()
        token = self.preview(root)['expected']
        self.engine.share()
        self.as_(self.blake, self.blake.engine.fetch)
        self.as_(self.blake, self.blake.engine.drive, self.theirs(self.blake, root), 'take')
        self.engine.fetch()
        before = self.snapshot(root)
        with self.assertRaises(WorkspaceError):
            desk_chat.migrate(self.engine, root, token)
        self.assertEqual(self.snapshot(root), before)

    def test_shared_dirty_and_staged_originals_refuse_but_committed_input_succeeds(self):
        for dirty in ('record', 'plan', 'staged'):
            root = self.saved('Shared dirty ' + dirty)
            original = self.snapshot(root)
            if dirty == 'record':
                session = workspace.load(root)
                session['next_step'] = 'Changed shared record'
                workspace.store(root, session)
            elif dirty == 'plan':
                (root / 'blueprint.md').write_text(BLUEPRINT + '\nChanged shared plan.')
            else:
                session = workspace.load(root)
                session['next_step'] = 'Staged other original'
                workspace.store(root, session)
                self.git('add', str(root / SESSION))
                (root / SESSION).write_bytes(original[SESSION])
            before = self.snapshot(root)
            self.assertTrue(self.preview(root)['blockers'])
            self.assertEqual(self.snapshot(root), before)
            if dirty == 'staged':
                self.git('reset', '-q', 'HEAD', '--', str(root / SESSION))
            else:
                gitstate.commit(self.space, 'keep shared saved inputs explicitly', [root])
            self.assertEqual(self.preview(root)['blockers'], [])
            self.apply(root)

    def test_shared_dirty_or_staged_workspace_marker_refuses_until_committed(self):
        marker = self.space.root / gitstate.MARKER
        for kind in ('dirty', 'staged'):
            root = self.saved('Shared marker ' + kind)
            original = marker.read_bytes()
            changed = json.loads(original)
            changed['unrelated_person_value'] = kind
            marker.write_text(json.dumps(changed))
            if kind == 'staged':
                self.git('add', str(marker))
                marker.write_bytes(original)
            before = self.snapshot(root)
            self.assertTrue(self.preview(root)['blockers'])
            self.assertEqual(self.snapshot(root), before)
            if kind == 'staged':
                self.git('reset', '-q', 'HEAD', '--', str(marker))
                marker.write_text(json.dumps(changed))
            gitstate.commit(self.space, 'keep explicit shared workspace setting', [marker])
            self.assertEqual(self.preview(root)['blockers'], [])
            self.apply(root)
            self.assertEqual(json.loads(marker.read_bytes())['unrelated_person_value'], kind)

    def test_shared_head_change_invalidates_same_input_preview(self):
        root = self.saved()
        token = self.preview(root)['expected']
        self.git('commit', '--allow-empty', '-m', 'concurrent shared commit')
        before = self.snapshot(root)
        with self.assertRaises(WorkspaceError):
            desk_chat.migrate(self.engine, root, token)
        self.assertEqual(self.snapshot(root), before)

    def test_invalid_remote_required_plan_refuses_before_replay(self):
        root = self.saved()
        self.apply(root)
        self.engine.share()
        self.as_(self.blake, self.blake.engine.fetch)
        theirs = self.theirs(self.blake, root)
        (theirs / 'blueprint.md').write_text('Unsupported shared teaching plan')
        with self.be(self.blake):
            gitstate.commit(self.blake.space, 'synthetic unsupported remote plan', [theirs / 'blueprint.md'])
            self.git('push', '--quiet', 'origin', 'HEAD:main', repo=self.blake.space.repo)
        before = self.snapshot(root)
        head = self.git('rev-parse', 'HEAD')
        result = self.engine.fetch()
        self.assertFalse(result['reached'])
        self.assertIn('migration cannot be read', result['notice'])
        self.assertEqual(self.snapshot(root), before)
        self.assertEqual(self.git('rev-parse', 'HEAD'), head)

    def test_shared_native_bundle_binary_capture_is_checked_before_replay(self):
        root = self.saved()
        capture = self.synthesis(root, 'evidence/capture.bin')
        gitstate.commit(self.space, 'keep saved reviewed native bundle', [root])
        self.apply(root)
        self.engine.share()
        self.as_(self.blake, self.blake.engine.fetch)
        theirs = self.theirs(self.blake, root)
        shared = self.as_(self.blake, self.blake.engine._remote_record, self.blake.space, theirs)
        self.assertEqual(shared['schema'], 3)
        remote_capture = theirs / capture.relative_to(root)
        remote_capture.write_bytes(b'Unreviewed binary capture\x80\xff')
        with self.be(self.blake):
            gitstate.commit(self.blake.space, 'synthetic unreviewed capture only', [remote_capture])
            self.git('push', '--quiet', 'origin', 'HEAD:main', repo=self.blake.space.repo)
        before, head = self.snapshot(root), self.git('rev-parse', 'HEAD')
        result = self.engine.fetch()
        self.assertFalse(result['reached'])
        self.assertIn('migration cannot be read', result['notice'])
        self.assertEqual(self.snapshot(root), before)
        self.assertEqual(self.git('rev-parse', 'HEAD'), head)

    def test_migrated_effective_takeover_replay_blocks_old_driver(self):
        root = self.saved()
        original = (root / RUN).read_bytes()
        self.apply(root)
        self.engine.share()
        self.as_(self.blake, self.blake.engine.fetch)
        theirs = self.theirs(self.blake, root)
        self.as_(self.blake, self.blake.engine.drive, theirs, 'take')
        self.engine.fetch()
        self.assertFalse(self.engine.mine(root))
        self.assertTrue(self.engine._run(root).gone)
        with self.assertRaises(WorkspaceError):
            desk_chat.set_scope(self.engine, root, 'old', ['part'])
        self.assertEqual((root / RUN).read_bytes(), original)



class MigrationPageTests(ScriptedPage, PageCase):
    saved = MigrationTests.saved
    snapshot = MigrationTests.snapshot

    def fixture(self, review=False):
        self.root = self.saved()
        if review:
            workspace.checkpoint(self.root, stage='blueprint', gate='blueprint')
        path = str(self.root)
        before = self.get('run', path=path)
        detail = self.get('training', path=path)
        listing = self.get('trainings')
        preview = self.get('drafts/migration-preview', path=path)
        opened = self.post('drafts/migrate', {'path': path, 'expected': preview['expected']})
        desk = self.get('drafts', path=path)
        cards = {card['name']: self.get('drafts/card', path=path, name=card['name'])
                 for card in desk['cards'] if card['seen'] and card['kind'] == 'blueprint'}
        return dict(path=path, before=before, detail=detail, listing=listing, preview=preview, opened=opened, desk=desk, cards=cards)

    def answers(self, fixture, **more):
        return {'GET /api/capabilities': [RUNNER], 'GET /api/setup': [ok(SET_UP)],
                'GET /api/trainings': [ok(fixture['listing'])],
                'GET /api/training': [ok(fixture['detail'])],
                'GET /api/run': [ok(fixture['before'])],
                'GET /api/computer': [ok({'items': []})],
                'GET /api/agents': [ok(AGENTS_FOUND)], **MODELS,
                'GET /api/drafts/migration-preview': [ok(fixture['preview'])],
                'GET /api/drafts/card': [ok(fixture['cards']['blueprint'])],
                'GET /api/drafts': [ok(fixture['desk'])], **more}

    def test_desktop_phone_preview_cancel_and_exact_apply(self):
        fixture = self.fixture()
        for narrow in (False, True):
            result = self.run_page(self.answers(fixture), [
                {'click': 'Open on the desk'}, {'snapshot': 'preview'}, {'click': 'Cancel'},
                {'snapshot': 'saved'}], state={'screen': 'run', 'path': fixture['path']}, narrow=narrow)
            preview = result['snapshots']['preview']
            self.assertIn('listed existing material parts', preview['sheet'])
            self.assertNotIn(fixture['preview']['expected'], preview['sheet'])
            self.assertEqual(preview['filled'], ['Apply'])
            self.assertEqual([r for r in result['requests'] if r['method'] == 'POST'], [])
            result = self.run_page(self.answers(fixture, **{
                'POST /api/drafts/migrate': [ok(fixture['opened'])],
                'GET /api/run': [ok(fixture['before']), ok(fixture['before']), ok(fixture['opened'])]}), [
                {'click': 'Open on the desk'}, {'click': 'Apply'}, {'snapshot': 'desk'}],
                state={'screen': 'run', 'path': fixture['path']}, narrow=narrow)
            posts = [r for r in result['requests'] if r['method'] == 'POST']
            self.assertEqual([(p['address'], p['body']) for p in posts], [('/api/drafts/migrate', {'path': fixture['path'], 'expected': fixture['preview']['expected']})])
            self.assertNotIn('Apply', result['snapshots']['desk']['buttons'])
            self.assertNotIn('Stop training', result['snapshots']['desk']['buttons'])
            self.assertNotIn('Revise the plan', result['snapshots']['desk']['buttons'])
            self.assertNotIn('Note for the whole plan', result['snapshots']['desk']['text'])
            self.assertIn('Mark ready', result['snapshots']['desk']['buttons'])
            self.assertEqual(fixture['desk']['needs'], [])

    def test_detail_review_remains_the_only_primary_before_migration(self):
        fixture = self.fixture(review=True)
        self.assertTrue(fixture['detail']['run']['can_migrate_desk'])
        review = 'Review ' + fixture['detail']['waiting']['label']
        for narrow in (False, True):
            result = self.run_page(self.answers(fixture), [
                {'snapshot': 'detail'}, {'click': 'Open on the desk'}, {'snapshot': 'preview'},
                {'click': 'Cancel'}, {'snapshot': 'returned'}],
                state={'screen': 'training', 'path': fixture['path']}, narrow=narrow)
            self.assertEqual(result['snapshots']['detail']['filled'], [review])
            self.assertIn('Open on the desk', result['snapshots']['detail']['buttons'])
            self.assertEqual(result['snapshots']['preview']['filled'], ['Apply'])
            self.assertEqual(result['snapshots']['returned']['filled'], [review])
            self.assertEqual([request for request in result['requests'] if request['method'] == 'POST'], [])

    def test_blocker_and_changed_preview_keep_sheet_and_saved_work(self):
        fixture = self.fixture()
        blocked = {**fixture['preview'], 'blockers': ['Restore the saved dependency first.']}
        result = self.run_page(self.answers(fixture, **{'GET /api/drafts/migration-preview': [ok(blocked)]}), [
            {'click': 'Open on the desk'}, {'snapshot': 'blocked'}, {'click': 'Apply'}, {'snapshot': 'still'}],
            state={'screen': 'run', 'path': fixture['path']}, narrow=True)
        self.assertIn('Apply', result['snapshots']['blocked']['off'])
        self.assertEqual([r for r in result['requests'] if r['method'] == 'POST'], [])
        result = self.run_page(self.answers(fixture, **{'POST /api/drafts/migrate': [{'status': 409, 'body': {'error': 'The saved inputs changed. Preview again.'}}]}), [
            {'click': 'Open on the desk'}, {'click': 'Apply'}, {'snapshot': 'refused'}],
            state={'screen': 'run', 'path': fixture['path']}, narrow=True)
        self.assertIn('The saved inputs changed.', result['snapshots']['refused']['sheet'])
        self.assertIn('Cancel', result['snapshots']['refused']['buttons'])
