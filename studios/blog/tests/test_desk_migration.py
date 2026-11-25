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
import desk_migration
import management
import saved_fixtures
import studio
from test_blog_runner import RunnerCase

OUTLINE = '# Synthetic outline\n\nOpening brief.\n\n## First\n\nFirst brief.\n\n## Second\n\nSecond brief.\n'
MANUSCRIPT = '# Synthetic draft\n\nAn opening.\n\n## First\n\nSaved words.\n'


class MigrationTests(RunnerCase):
    def eligible(self, material='draft'):
        # A page run just created by the saved flow, in its original format (a static
        # fixture), with its material written here: not a new-work command or a worker.
        ident = saved_fixtures.load(self.root, 'page-created')
        directory, _, run = runner.load(self.root, ident)
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
        return ident, directory

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

    def attached_material(self):
        from test_blog_runner import FilesCase

        ident, directory = self.eligible()
        self.apply(ident)
        original = (directory / 'session.json').read_bytes()
        source = FilesCase.material(self, ('synthetic.md', 'Synthetic material.'))[0]
        with studio.locked(self.root):
            desk.add_sources(self.root, ident, {'sources': [source]})
        self.assertEqual((directory / 'session.json').read_bytes(), original)
        return ident, directory, source

    def test_deletion_retains_material_added_to_another_migrated_blog(self):
        import blog_delete

        ident, directory, source = self.attached_material()
        other = self.desk(title='Another synthetic blog', sources=[source])
        before = self.snapshot(directory)
        management.dispatch(
            self.root,
            'blog-delete',
            {'id': other['id'], 'expected': other['expected'], 'title': other['title']},
        )
        self.assertEqual(studio.item(self.root, 'sources', source)[1]['id'], source)
        self.assertFalse((blog_delete.folder(self.root) / other['id'] / 'material').exists())
        self.assertEqual(self.snapshot(directory), before)
        self.assertIn(source, studio.item(self.root, 'articles', ident)[1]['material'])

    def test_source_role_and_location_see_post_migration_pins(self):
        _, _, source = self.attached_material()
        before = self.snapshot()
        for operation, data in (
            (management.source_role, {'id': source, 'role': 'example'}),
            (management.source_keep, {'id': source, 'keep': True}),
        ):
            with self.subTest(operation=operation.__name__):
                with self.assertRaisesRegex(ValueError, 'started blog'):
                    operation(self.root, data)
                self.assertEqual(self.snapshot(), before)

    def test_uncertain_article_references_refuse_source_changes_and_deletion(self):
        from test_blog_runner import FilesCase

        source = FilesCase.material(self, ('unclaimed.md', 'Synthetic file.'))[0]
        other = self.desk(title='Another synthetic blog', sources=[source])
        broken = studio.inside(self.root, 'articles', 'unreadable')
        broken.mkdir()
        for raw in (b'{', b'{"schema":999,"sources":[]}', None):
            with self.subTest(raw=raw):
                session = broken / 'session.json'
                if raw is None:
                    session.unlink()
                else:
                    session.write_bytes(raw)
                before = self.snapshot()
                for operation in (
                    lambda: management.source_role(self.root, {'id': source, 'role': 'example'}),
                    lambda: management.source_keep(self.root, {'id': source, 'keep': True}),
                    lambda: management.dispatch(
                        self.root,
                        'blog-delete',
                        {'id': other['id'], 'expected': other['expected'], 'title': other['title']},
                    ),
                ):
                    with self.assertRaises(ValueError):
                        operation()
                    self.assertEqual(self.snapshot(), before)

    def test_google_link_added_after_migration_requires_its_live_team_owner(self):
        import google_drive

        ident, directory = self.eligible()
        self.apply(ident)
        original = self.snapshot(directory)
        record = studio.item(self.root, 'articles', ident)[1]
        record['google'] = {
            'baselines': {'draft': {'document': {'document_id': 'synthetic-linked-doc'}}}
        }
        studio.persist(directory, 'articles', record)
        self.assertIn('synthetic-linked-doc', google_drive.linked_documents(self.root))
        before = self.snapshot()
        with (
            patch('team_workspace.space', return_value=object()),
            patch('team_workspace.before') as sync,
            patch(
                'team_workspace.guard', side_effect=ValueError('Another computer drives this blog')
            ) as guard,
            patch('google_drive.token', side_effect=AssertionError('credentials')),
            patch('google_drive.Client.native_update', side_effect=AssertionError('Google')),
        ):
            with self.assertRaisesRegex(ValueError, 'Another computer'):
                google_drive.require_linked(self.root, 'synthetic-linked-doc')
        sync.assert_called_once_with(self.root)
        guard.assert_called_once_with(self.root, ident)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual((directory / 'session.json').read_bytes(), original['session.json'])
        self.assertEqual((directory / runner.STATE).read_bytes(), original[runner.STATE])

    def test_published_migrated_blog_leaves_in_progress(self):
        import editorial

        ident, directory = self.eligible()
        self.apply(ident)
        originals = (
            (directory / 'session.json').read_bytes(),
            (directory / runner.STATE).read_bytes(),
        )
        editorial.schedule(
            self.root,
            ident,
            {
                'stage': 'published',
                'confirm_stage': True,
                'publication_url': 'https://example.test/synthetic',
            },
            desk=True,
        )
        row = next(row for row in runner.catalog(self.root)['items'] if row['id'] == ident)
        self.assertEqual((row['complete'], row['status']), (True, 'complete'))
        self.assertEqual(
            ((directory / 'session.json').read_bytes(), (directory / runner.STATE).read_bytes()),
            originals,
        )

    def test_google_mapping_refuses_unreadable_live_records_and_guards_every_owner(self):
        import google_drive

        first, directory = self.eligible()
        self.apply(first)
        second = saved_fixtures.load(self.root, 'outline-gate')  # Another saved page run.
        for ident in (first, second):
            folder, record = studio.item(self.root, 'articles', ident)
            record['google'] = {'baselines': {'draft': {'document': {'document_id': 'shared-doc'}}}}
            studio.persist(folder, 'articles', record)
        with (
            patch('team_workspace.space', return_value=object()),
            patch('team_workspace.before'),
            patch('team_workspace.guard') as guard,
        ):
            google_drive.require_linked(self.root, 'shared-doc')
        self.assertEqual({call.args[1] for call in guard.call_args_list}, {first, second})
        marker = directory / 'desk/migration.json'
        marker.write_text('{"schema":999}')
        before = self.snapshot()
        with self.assertRaises(ValueError):
            google_drive.require_linked(self.root, 'shared-doc')
        self.assertEqual(self.snapshot(), before)

    def test_restore_already_back_uses_effective_title(self):
        import blog_delete
        import shutil

        ident, directory = self.eligible()
        self.apply(ident)
        record = studio.item(self.root, 'articles', ident)[1]
        record['title'] = 'Changed synthetic title'
        studio.persist(directory, 'articles', record)
        originals = (
            (directory / 'session.json').read_bytes(),
            (directory / runner.STATE).read_bytes(),
        )
        shown = runner.engine(self.root).describe(ident)
        management.dispatch(
            self.root,
            'blog-delete',
            {'id': ident, 'expected': shown['expected'], 'title': record['title']},
        )
        kept = blog_delete.folder(self.root) / ident
        shutil.copytree(kept / 'blog', directory)
        result = management.dispatch(self.root, 'blog-restore', {'id': ident})
        self.assertEqual(result['notice'], blog_delete.ALREADY_BACK)
        self.assertEqual(studio.item(self.root, 'articles', ident)[1]['title'], record['title'])
        self.assertEqual(
            ((directory / 'session.json').read_bytes(), (directory / runner.STATE).read_bytes()),
            originals,
        )

    def tool_record(self, ident, kind='desk-draft'):
        request = {
            'kind': kind,
            'payload': {},
            'basis': 'synthetic',
            'metadata': {'article': ident, 'desk': {}}
            if kind.startswith('desk-')
            else {'article': ident},
        }
        return {
            'id': 'a' * 32,
            **request,
            'fingerprint': studio.digest(json.dumps(request, sort_keys=True).encode()),
            'guidance': '',
            'status': 'failed',
            'created_at': studio.now(),
            'attempts': 1,
            'engine': 'codex',
            'seconds': 60,
            'result': None,
            'error': '',
        }

    def test_unsupported_worker_and_tool_records_refuse_without_changes(self):
        ident, directory = self.eligible()
        local = self.root / '.blog-runs' / (ident + '.json')
        tool = self.root / '.blog-runs/tools' / ('a' * 32 + '.json')
        cases = [
            (local, {'schema': 999, 'enabled': False, 'status': 'future-working'}),
            (local, {'enabled': False, 'status': 'future-working'}),
            (local, {'enabled': False}),
            (local, {'enabled': 0, 'status': 'paused'}),
            (local, {'enabled': False, 'status': 'paused', 'owner': 'unknown-computer'}),
            (local, {'enabled': False, 'status': 'paused', 'notes': []}),
        ]
        for field, value in (
            ('schema', 999),
            ('status', 'future-working'),
            ('metadata', []),
            ('kind', 'unknown'),
            ('owner', 'unknown-computer'),
            ('applied', 'unknown'),
            ('settled_at', True),
        ):
            job = self.tool_record(ident)
            job[field] = value
            cases.append((tool, job))
        job = self.tool_record(ident)
        job['metadata']['article'] = ['unknown-owner']
        request = {key: job[key] for key in ('kind', 'payload', 'basis', 'metadata')}
        job['fingerprint'] = studio.digest(json.dumps(request, sort_keys=True).encode())
        cases.append((tool, job))
        job = self.tool_record(ident)
        job['metadata']['owner'] = 'future-owner'
        request = {key: job[key] for key in ('kind', 'payload', 'basis', 'metadata')}
        job['fingerprint'] = studio.digest(json.dumps(request, sort_keys=True).encode())
        cases.append((tool, job))
        cases.append((tool, {'id': 'a' * 32, 'status': 'failed', 'metadata': {'article': ident}}))
        for path, value in cases:
            with self.subTest(value=value):
                studio.write_json(path, value)
                before = self.snapshot()
                shown = self.preview(ident)
                self.assertFalse(shown['eligible'])
                with self.assertRaises(ValueError):
                    self.apply(ident, shown)
                self.assertEqual(self.snapshot(), before)
                self.assertFalse((directory / 'desk').exists())
                path.unlink()
        # Known markers the earlier flow left, which no runner picks up again, are idle.
        for value in (
            {'enabled': False, 'status': 'working'},
            {'enabled': True, 'status': 'paused'},
        ):
            with self.subTest(idle=value):
                studio.write_json(local, value)
                self.assertTrue(self.preview(ident)['eligible'])
                local.unlink()

    def test_known_worker_states_and_settled_tools_have_explicit_eligibility(self):
        ident, _ = self.eligible()
        local = self.root / '.blog-runs' / (ident + '.json')
        for status in (
            'paused',
            'stopped',
            'failed',
            'complete',
            'waiting-for-approval',
            'needs-attention',
            'in-chat',
        ):
            with self.subTest(status=status):
                studio.write_json(local, {'enabled': False, 'status': status})
                self.assertTrue(self.preview(ident)['eligible'])
        local.unlink()
        tool = self.root / '.blog-runs/tools' / ('a' * 32 + '.json')
        for kind, status, settlement, allowed in (
            ('desk-draft', 'failed', {}, True),
            ('desk-draft', 'cancelled', {}, True),
            ('desk-draft', 'queued', {}, False),
            ('desk-draft', 'working', {}, False),
            ('desk-draft', 'ready', {}, False),
            ('desk-draft', 'ready', {'applied': True}, False),
            ('desk-draft', 'ready', {'applied': False, 'settled_at': 'synthetic-time'}, True),
            ('repurpose', 'ready', {'applied': {'id': ident, 'status': 'saved'}}, True),
            ('repurpose', 'ready', {}, False),
        ):
            with self.subTest(kind=kind, status=status, settlement=settlement):
                job = self.tool_record(ident, kind)
                job.update(status=status, **settlement)
                if status == 'ready':
                    job['result'] = {'content': 'Synthetic result.'}
                studio.write_json(tool, job)
                before = self.snapshot()
                self.assertEqual(self.preview(ident)['eligible'], allowed)
                self.assertEqual(self.snapshot(), before)

    def test_indexed_jobs_and_in_process_cancelled_tool_must_be_understood_and_idle(self):
        ident, directory = self.eligible()
        job = self.tool_record(ident)
        tool = self.root / '.blog-runs/tools' / (job['id'] + '.json')
        studio.write_json(tool, job)
        index = self.root / '.blog-runs/desk-jobs' / (ident + '.json')
        for value in (
            {},
            {'schema': 999, 'jobs': []},
            {'jobs': ['b' * 32]},
            {'jobs': [job['id'], job['id']]},
        ):
            with self.subTest(index=value):
                studio.write_json(index, value)
                before = self.snapshot()
                shown = self.preview(ident)
                self.assertFalse(shown['eligible'])
                with self.assertRaises(ValueError):
                    self.apply(ident, shown)
                self.assertEqual(self.snapshot(), before)
                self.assertFalse((directory / 'desk').exists())
        studio.write_json(index, {'jobs': [job['id']]})
        preview = self.preview(ident)
        self.assertTrue(preview['eligible'])
        job['status'] = 'cancelled'
        studio.write_json(tool, job)
        with studio.locked(self.root):
            pass  # The existing process-lock file is operational, not migrated saved work.
        before = self.snapshot()
        with patch.dict(runner.ENGINES, {str(self.root): Mock(current='tool:' + job['id'])}):
            self.assertFalse(self.preview(ident)['eligible'])
            with self.assertRaises(ValueError):
                self.apply(ident, preview)
        self.assertEqual(self.snapshot(), before)
        self.assertTrue(self.preview(ident)['eligible'])

    def test_current_tool_writer_produces_supported_inactive_records(self):
        import tool_jobs

        ident, _ = self.eligible()
        job_id = 'a' * 32
        tool_jobs.create(
            self.root, job_id, 'desk-draft', {}, '', 'synthetic', {'article': ident, 'desk': {}}
        )
        self.assertFalse(self.preview(ident)['eligible'])
        job = tool_jobs.read(self.root, job_id)
        job.update(status='failed', error='Synthetic interrupted job', finished_at=studio.now())
        tool_jobs.write(self.root, job)
        self.assertTrue(self.preview(ident)['eligible'])
        job.update(
            status='ready',
            result={'content': 'Synthetic saved result.'},
            applied=False,
            settled_at=studio.now(),
        )
        tool_jobs.write(self.root, job)
        self.assertTrue(self.preview(ident)['eligible'])

    def test_saved_driver_formats_refuse_without_guessing_or_repair(self):
        ident, directory = self.eligible()
        driver = directory / 'run.json'
        for value in (
            {'schema': 999, 'driver': None},
            {'schema': 1, 'driver': []},
            {'schema': 1, 'driver': {'computer': 'a' * 16}},
            {'schema': 1, 'driver': None, 'owner': 'future-owner'},
        ):
            with self.subTest(value=value):
                studio.write_json(driver, value)
                before = self.snapshot()
                shown = self.preview(ident)
                self.assertFalse(shown['eligible'])
                with self.assertRaises(ValueError):
                    self.apply(ident, shown)
                self.assertEqual(self.snapshot(), before)
        studio.write_json(driver, {'schema': 1, 'driver': None})
        self.assertTrue(self.preview(ident)['eligible'])

    def test_workspace_and_local_identity_formats_are_read_only_and_known(self):
        from studio_sync import support

        ident, directory = self.eligible()
        # Team-style layout, synthetic metadata only: no application, Git or sync operation.
        directory.rename(self.root / ident)
        marker = {
            'schema': 1,
            'tool': 'blog-studio',
            'name': 'Synthetic workspace',
            'folder': self.root.name,
            'branch': 'synthetic',
            'minimum_runtime': '4.9.0',
            'repository': None,
        }
        studio.write_json(self.root / 'hub.json', marker)
        self.assertTrue(self.preview(ident)['eligible'])
        identity = support.data_root() / 'computer.json'
        for value in ({'schema': 999, 'id': 'a' * 16}, {'schema': 1, 'id': []}):
            with self.subTest(value=value):
                studio.write_json(identity, value)
                before = self.snapshot(), identity.read_bytes()
                self.assertFalse(self.preview(ident)['eligible'])
                self.assertEqual((self.snapshot(), identity.read_bytes()), before)
        studio.write_json(identity, {'schema': 1, 'id': 'a' * 16})
        self.assertTrue(self.preview(ident)['eligible'])
        marker['schema'] = 999
        studio.write_json(self.root / 'hub.json', marker)
        before = self.snapshot(), identity.read_bytes()
        self.assertFalse(self.preview(ident)['eligible'])
        self.assertEqual((self.snapshot(), identity.read_bytes()), before)

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
                self.assertEqual(preview['notice'], desk_migration.REFUSAL)
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
                    # Unstructured outline notes move as notes (test_saved_states); notes
                    # holding image data cannot be kept as a start's notes, so they refuse.
                    (directory / 'DRAFT.md').unlink()
                    run['stages'].pop('draft')
                    (directory / 'OUTLINE.md').write_text(
                        'Unstructured notes only.\n\n![a](data:image/png;base64,iVBORw0KGgo=)\n'
                    )
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
                    studio.write_json(
                        target,
                        {
                            'schema': 1,
                            'driver': {
                                'computer': 'a' * 16,
                                'name': 'Synthetic driver',
                                'since': 'synthetic-time',
                            },
                        },
                    )
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
        ident, directory = self.eligible()
        # Only the manuscript editor's own runs still reach a worker: this one is the editor's.
        run = studio.read_json(directory / runner.STATE)
        run['editor_check'] = 'proofread'
        studio.write_json(directory / runner.STATE, run)
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
        import manuscript_editor
        from test_editorial_tools import Fixture

        # The runner settles only the manuscript editor's own runs now: a revise check.
        ident = Fixture.article(self, MANUSCRIPT)
        shown = manuscript_editor.read(self.root, ident)
        with studio.locked(self.root), patch.object(runner.Engine, 'control', return_value={}):
            manuscript_editor.dispatch(
                self.root, 'check', {'id': ident, 'expected': shown['expected'], 'check': 'revise'}
            )
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
        self.assertEqual((directory / 'DRAFT.md').read_text(), MANUSCRIPT)

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

    def test_every_refusal_has_one_outcome_and_classifying_changes_nothing(self):
        """Each refused saved state is read-only (cannot be read or understood) or waits
        (ends by itself, by Stop or by Take, or by its own recovery), never both."""
        import desk_migration

        def tool(ident, status):
            job = self.tool_record(ident)
            job['status'] = status
            return job

        driver = {'computer': 'a' * 16, 'name': 'Synthetic driver', 'since': 'synthetic-time'}
        cases = {
            'worker-format': (
                'read-only',
                lambda d, i: studio.write_json(
                    self.root / '.blog-runs' / (i + '.json'), {'enabled': False, 'status': 'future'}
                ),
            ),
            # A step running now waits; a marker no runner picks up again does not (below).
            'worker-busy': ('wait', lambda d, i: setattr(runner.engine(self.root), 'current', i)),
            'tool-format': (
                'read-only',
                lambda d, i: studio.write_json(
                    self.root / '.blog-runs/tools' / ('a' * 32 + '.json'), {'id': 'a' * 32}
                ),
            ),
            'tool-busy': (
                'wait',
                lambda d, i: studio.write_json(
                    self.root / '.blog-runs/tools' / ('a' * 32 + '.json'), tool(i, 'queued')
                ),
            ),
            'driver-format': (
                'read-only',
                lambda d, i: studio.write_json(d / 'run.json', {'schema': 999, 'driver': None}),
            ),
            # A condition of the workspace is never this blog's outcome: it waits.
            'older-hub': (
                'wait',
                lambda d, i: studio.write_json(self.root / '.team-hub.json', {'schema': 1}),
            ),
            'pipeline': (
                'read-only',
                lambda d, i: studio.write_json(
                    d / runner.STATE,
                    {**studio.read_json(d / runner.STATE), 'pipeline': ['unknown']},
                ),
            ),
            'missing-file': ('read-only', lambda d, i: (d / 'DRAFT.md').unlink()),
            'session-shape': (
                'read-only',
                lambda d, i: studio.write_json(
                    d / 'session.json', {**studio.read_json(d / 'session.json'), 'mode': 'future'}
                ),
            ),
            'desk-records': (
                'read-only',
                lambda d, i: studio.write_json(d / 'desk/start.json', {'schema': 1}),
            ),
            'link': ('read-only', lambda d, i: (d / 'linked').symlink_to(self.base)),
        }
        for name, (outcome, change) in cases.items():
            with self.subTest(case=name):
                ident, directory = self.eligible()
                (directory / 'desk').mkdir(exist_ok=name != 'desk-records')
                change(directory, ident)
                before = self.snapshot()
                said = desk_migration.classify(self.root, ident)
                self.assertEqual(said['outcome'], outcome, said)
                self.assertTrue(said['reason'])
                self.assertEqual(said['next'], 'copy' if outcome == 'read-only' else None)
                self.assertEqual(said, {k: self.preview(ident)[k] for k in said})
                self.assertEqual(self.snapshot(), before)
                for path in (
                    self.root / '.blog-runs' / (ident + '.json'),
                    self.root / '.blog-runs/tools' / ('a' * 32 + '.json'),
                    self.root / '.team-hub.json',
                ):
                    path.unlink(missing_ok=True)
                runner.engine(self.root).current = None
        # A queued marker the earlier flow left, which no runner picks up again, is idle.
        ident, directory = self.eligible()
        studio.write_json(
            self.root / '.blog-runs' / (ident + '.json'), {'enabled': True, 'status': 'queued'}
        )
        self.assertEqual(desk_migration.classify(self.root, ident)['outcome'], 'migrates')
        # A team driver on another computer waits until this computer takes the blog.
        ident, directory = self.eligible()
        directory.rename(self.root / ident)
        studio.write_json(
            self.root / 'hub.json',
            {
                'schema': 1,
                'tool': 'blog-studio',
                'name': 'Synthetic workspace',
                'folder': self.root.name,
                'branch': 'synthetic',
                'minimum_runtime': '4.9.0',
                'repository': 'synthetic-remote',
            },
        )
        studio.write_json(self.root / ident / 'run.json', {'schema': 1, 'driver': driver})
        self.assertEqual(desk_migration.classify(self.root, ident)['outcome'], 'wait')

    def test_workspace_and_computer_conditions_wait_and_say_what_clears_them(self):
        """An older Team Hub connection, a workspace needing a newer Blog Studio and an
        unreadable computer identity belong to the workspace or this computer, not to the
        blog: they wait, naming the condition and what clears it, never read-only."""
        import desk_migration
        from studio_sync import support

        ident, directory = self.eligible()
        studio.write_json(self.root / '.team-hub.json', {'schema': 1})
        said = desk_migration.classify(self.root, ident)
        self.assertEqual((said['outcome'], said['next']), ('wait', None))
        self.assertIn('older Team Hub', said['reason'])
        self.assertIn('hub leave', said['reason'])
        (self.root / '.team-hub.json').unlink()
        directory.rename(self.root / ident)
        marker = {
            'schema': 1,
            'tool': 'blog-studio',
            'name': 'Synthetic workspace',
            'folder': self.root.name,
            'branch': 'synthetic',
            'minimum_runtime': '999.0.0',
            'repository': None,
        }
        studio.write_json(self.root / 'hub.json', marker)
        said = desk_migration.classify(self.root, ident)
        self.assertEqual(said['outcome'], 'wait')
        self.assertIn('Update Blog Studio', said['reason'])
        marker['minimum_runtime'] = '4.9.0'
        studio.write_json(self.root / 'hub.json', marker)
        identity = support.data_root() / 'computer.json'
        studio.write_json(identity, {'schema': 999, 'id': 'a' * 16})
        before = self.snapshot(), identity.read_bytes()
        said = desk_migration.classify(self.root, ident)
        self.assertEqual(said['outcome'], 'wait')
        self.assertIn('Take this blog', said['reason'])
        self.assertEqual((self.snapshot(), identity.read_bytes()), before)

    def test_a_waiting_tool_job_is_named_with_the_way_to_it(self):
        """A tool job of the blog that waits for the person (ready, not applied) is named on
        the record, which opens it where it is finished; once it is, the blog opens on the
        desk. Reading the record writes nothing."""
        import desk_migration

        ident, directory = self.eligible()
        tool = self.root / '.blog-runs/tools' / ('a' * 32 + '.json')
        job = self.tool_record(ident, 'repurpose')
        job.update(status='ready', result={'content': 'Synthetic channel copy.'})
        studio.write_json(tool, job)
        with studio.locked(self.root):
            pass  # The page view takes the lock; its marker file is not saved work.
        before = self.snapshot()
        shown = management.view(self.root, 'run', {'id': [ident]})
        self.assertEqual(self.snapshot(), before)
        saved = shown['saved_record']
        self.assertEqual((saved['outcome'], saved['clear'], saved['next']), ('wait', 'job', None))
        self.assertEqual(saved['job'], {'id': 'a' * 32, 'kind': 'repurpose', 'status': 'ready'})
        job['applied'] = {'id': ident, 'status': 'saved'}
        studio.write_json(tool, job)
        self.assertEqual(desk_migration.classify(self.root, ident)['outcome'], 'migrates')

    def test_an_identity_recorded_by_taking_the_blog_offers_take(self):
        """In a team workspace, an unreadable computer identity is recorded again by taking
        the blog, as its reason says: the record offers Take."""
        from types import SimpleNamespace

        from studio_sync import support
        import team_workspace

        ident, directory = self.eligible()
        directory.rename(self.root / ident)
        studio.write_json(
            self.root / 'hub.json',
            {
                'schema': 1,
                'tool': 'blog-studio',
                'name': 'Synthetic workspace',
                'folder': self.root.name,
                'branch': 'synthetic',
                'minimum_runtime': '4.9.0',
                'repository': 'synthetic-remote',
            },
        )
        studio.write_json(support.data_root() / 'computer.json', {'schema': 999, 'id': 'a' * 16})
        (self.base / 'team-repo' / '.git').mkdir(parents=True)
        joined = SimpleNamespace(address='synthetic-remote', repo=self.base / 'team-repo')
        with (
            patch.object(team_workspace, 'space', return_value=joined),
            patch.object(team_workspace, 'driver', return_value=None),
        ):
            shown = management.view(self.root, 'run', {'id': [ident]})
        saved = shown['saved_record']
        self.assertIn('Take this blog', saved['why'])
        self.assertEqual((saved['outcome'], saved['clear'], shown['team']), ('wait', 'take', True))
        # Outside a team repository taking records nothing: new work is offered meanwhile.
        with patch.object(team_workspace, 'space', return_value=None):
            shown = management.view(self.root, 'run', {'id': [ident]})
        said = shown['saved_record']
        self.assertEqual((said['clear'], said['next']), (None, 'copy'))

    def test_a_run_record_that_is_not_an_object_is_read_only(self):

        for value in ([], 'x', 3, None):
            with self.subTest(value=value):
                ident, directory = self.eligible()
                (directory / runner.STATE).write_text(json.dumps(value))
                with studio.locked(self.root):
                    pass  # The page view takes the lock; its marker file is not saved work.
                before = self.snapshot()
                shown = self.preview(ident)
                self.assertFalse(shown['eligible'])
                self.assertTrue(shown['blockers'])
                self.assertEqual((shown['outcome'], shown['next']), ('read-only', 'copy'))
                self.assertIn('run record', shown['reason'])
                page = management.view(self.root, 'run', {'id': [ident]})
                self.assertEqual(page['saved_record']['why'], shown['reason'])
                self.assertEqual(self.snapshot(), before)

    def test_a_moved_research_execution_run_stays_readable_whatever_the_protocol(self):
        """The migration keeps the run's research execution record without interpreting it,
        so a later Harness Research protocol never makes the moved blog unreadable."""
        import desk_migration
        from studio_core import research_session
        from studio_core.blog_migration import run_supported
        from studio_core.sync_guard import worker_in_progress

        ident = saved_fixtures.load(self.root, 'research-execution-drafted')
        directory = studio.inside(self.root, 'articles', ident)
        self.apply(ident)
        with patch.object(research_session, 'PROTOCOL', 'harness-collection-v9'):
            self.assertIsNotNone(desk_migration.metadata(directory))
            self.assertFalse(worker_in_progress(self.root))
            self.assertTrue(runner.engine(self.root).describe(ident)['on_desk'])
            self.assertEqual(desk_migration.classify(self.root, ident)['outcome'], 'desk')
        run = studio.read_json(directory / runner.STATE)
        held = run['research_execution']
        self.assertTrue(run_supported(run))
        for broken in (
            None,
            [],
            {**held, 'schema': 2},
            {**held, 'protocol': ''},
            {**held, 'protocol': 7},
            {**held, 'workers': 0},
            {**held, 'workers': 4},
            {**held, 'workers': True},
            {**held, 'capability': []},
            {**held, 'capability': {'protocol': 'another-protocol'}},
        ):
            with self.subTest(execution=broken):
                self.assertFalse(run_supported({**run, 'research_execution': broken}))
        self.assertFalse(run_supported({k: v for k, v in run.items() if k != 'research_execution'}))

    def test_the_saved_files_view_serves_only_a_saved_record(self):
        ident, directory = self.eligible()
        # A saved blog that opens on the desk shows its saved files on its record too.
        shown = management.view(self.root, 'saved-file', {'id': [ident], 'name': ['DRAFT.md']})
        self.assertEqual(shown['text'], MANUSCRIPT)
        (directory / runner.STATE).write_text('{not json')
        shown = management.view(self.root, 'saved-file', {'id': [ident], 'name': ['DRAFT.md']})
        self.assertEqual(shown['text'], MANUSCRIPT)
        # Once it is on the desk it is desk work, with its own views: refused here.
        other, _ = self.eligible()
        self.apply(other)
        with self.assertRaisesRegex(ValueError, 'saved file'):
            management.view(self.root, 'saved-file', {'id': [other], 'name': ['DRAFT.md']})
        # A folder that is no blog (in a team workspace any top-level folder) is refused.
        for name in ('sources', 'profiles', 'no-such-blog'):
            with self.subTest(folder=name):
                (self.root / 'articles' / name).mkdir(exist_ok=True)
                (self.root / 'articles' / name / 'DRAFT.md').write_text('Not a blog.')
                with self.assertRaisesRegex(ValueError, 'saved file'):
                    management.view(self.root, 'saved-file', {'id': [name], 'name': ['DRAFT.md']})

    def test_an_interrupted_opening_waits_and_a_damaged_one_is_read_only(self):
        import desk_migration

        ident, directory = self.eligible()
        (directory / 'desk').mkdir()
        studio.write_json(directory / 'desk/migration.pending.json', {'schema': 1})
        said = desk_migration.classify(self.root, ident)
        self.assertEqual((said['outcome'], said['reason']), ('wait', desk_migration.PENDING))
        (directory / 'desk/migration.pending.json').unlink()
        self.apply(ident)
        self.assertEqual(desk_migration.classify(self.root, ident)['outcome'], 'desk')
        (directory / 'desk/migration.json').write_text('{bad')
        said = desk_migration.classify(self.root, ident)
        self.assertEqual((said['outcome'], said['next']), ('read-only', 'copy'))
        self.assertIn('incomplete or unreadable', said['reason'])
        self.assertEqual(said['start']['title'], 'Synthetic gateway guide')

    def test_the_editors_own_run_is_current_work_or_waits_never_read_only(self):
        import desk_migration
        import manuscript_editor

        from test_editorial_tools import Fixture

        ident = Fixture.article(self, MANUSCRIPT)
        shown = manuscript_editor.read(self.root, ident)
        with studio.locked(self.root), patch.object(runner.Engine, 'control', return_value={}):
            manuscript_editor.dispatch(
                self.root,
                'check',
                {'id': ident, 'expected': shown['expected'], 'check': 'proofread'},
            )
        directory = studio.inside(self.root, 'articles', ident)
        local = self.root / '.blog-runs' / (ident + '.json')
        studio.write_json(local, {'enabled': True, 'status': 'queued'})
        self.assertEqual(desk_migration.classify(self.root, ident)['outcome'], 'wait')
        studio.write_json(local, {'enabled': False, 'status': 'paused'})
        self.assertEqual(desk_migration.classify(self.root, ident)['outcome'], 'migrates')
        record = studio.read_json(directory / 'session.json')
        record['hub_context'] = {'synthetic': True}
        studio.write_json(directory / 'session.json', record)
        said = desk_migration.classify(self.root, ident)
        self.assertEqual((said['outcome'], said['next']), ('current', None))
        self.assertIn('Edit manuscript', said['reason'])

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
