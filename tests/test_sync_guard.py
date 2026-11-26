"""Repository-wide worker exclusion fails closed on unreadable known records."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import marketing_studio  # noqa: F401
from studio_core import sync_guard
from studio_core.sync_guard import SYNC_WAIT, worker_in_progress


class SyncGuardTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)

    def presentation_item(self):
        item = self.repo / 'presentation'
        item.mkdir()
        (item / 'run.json').write_text(json.dumps({'schema': 1, 'id': item.name,
            'title': 'Synthetic saved Presentation Studio deck', 'created': '2026-10-28T12:00:00Z',
            'agent': 'test', 'route': 'scratch', 'form': {
                'route': 'scratch', 'title': 'Synthetic saved deck', 'output': 'pptx'},
            'steps': {}, 'gates': {}, 'limits': {}, 'revisions': []}))
        return item

    def test_recognized_item_linked_cache_roots_refuse_without_traversal(self):
        item = self.presentation_item()
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside)
            material = target / 'nested/desk/migration.json'
            material.parent.mkdir(parents=True)
            material.write_text('{unknown saved metadata')
            record = (item / 'run.json').read_bytes()
            from studio_core import sync_guard
            walk = sync_guard.os.walk
            for cache in ('work', 'sources'):
                for dangling in (False, True):
                    with self.subTest(cache=cache, dangling=dangling):
                        link = item / cache
                        destination = target / 'missing' if dangling else target
                        link.symlink_to(destination, target_is_directory=True)
                        walked = []
                        def tracked(folder, *args, **kwargs):
                            walked.append(Path(folder))
                            return walk(folder, *args, **kwargs)
                        try:
                            with mock.patch.object(sync_guard.os, 'walk', side_effect=tracked):
                                with self.assertRaisesRegex(ValueError, 'could not be checked'):
                                    worker_in_progress(self.repo)
                            self.assertNotIn(link, walked)
                            self.assertNotIn(target, walked)
                            self.assertEqual(link.readlink(), destination)
                            self.assertEqual((item / 'run.json').read_bytes(), record)
                            self.assertEqual(material.read_text(), '{unknown saved metadata')
                        finally:
                            link.unlink()

    def test_recognized_item_absent_optional_caches_are_idle_but_nested_migration_is_not(self):
        item = self.presentation_item()
        self.assertFalse(worker_in_progress(self.repo))
        for cache in ('work', 'sources'):
            folder = item / cache
            folder.mkdir()
            self.assertFalse(worker_in_progress(self.repo))
            nested = folder / 'nested/deck'
            pending = nested / 'work/desk/migration-transaction.json'
            pending.parent.mkdir(parents=True)
            pending.write_text('{interrupted')
            self.assertTrue(worker_in_progress(self.repo))
            self.assertEqual(pending.read_text(), '{interrupted')
            pending.unlink()
            marker = nested / 'desk/migration-origin.json'
            marker.parent.mkdir()
            marker.write_text('{unknown')
            with self.assertRaisesRegex(ValueError, 'could not be checked'):
                worker_in_progress(self.repo)
            self.assertEqual(marker.read_text(), '{unknown')
            marker.unlink()
            self.assertFalse(worker_in_progress(self.repo))

    def test_both_deck_marker_shapes_anywhere_in_repository_and_stale_markers(self):
        for shape in ('work/step.lock', '.training-studio/step.lock'):
            marker = self.repo / 'another' / 'workspace' / 'one' / shape
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text('left by an interrupted worker')
            self.assertTrue(worker_in_progress(self.repo))
            self.assertTrue(marker.exists(), 'checking must never repair or remove')
            marker.unlink()
            self.assertFalse(worker_in_progress(self.repo))

    def test_presentation_recovery_shape_exempts_only_its_exact_pending_target(self):
        item = self.presentation_item()
        pending = item / 'work/desk/migration-transaction.json'
        pending.parent.mkdir(parents=True)
        journal = {'schema': 1, 'expected': 'pm1.' + 'A' * 43, 'original': 'synthetic',
            'after': {}, 'before_workspace': '', 'index_before': '', 'index_prepared': '', 'shared': {}, 'head_before': {}}
        pending.write_text(json.dumps(journal))
        self.assertTrue(worker_in_progress(self.repo))
        self.assertFalse(worker_in_progress(self.repo, recovering_presentation=pending))
        self.assertTrue(worker_in_progress(self.repo, recovering_training=pending))
        prior = {name: value for name, value in journal.items() if name != 'head_before'}
        pending.write_text(json.dumps(prior))
        self.assertFalse(worker_in_progress(self.repo, recovering_presentation=pending))
        for changed in ({**journal, 'unknown': True}, {**journal, 'expected': 'tm1.' + 'A' * 43}):
            pending.write_text(json.dumps(changed))
            self.assertTrue(worker_in_progress(self.repo, recovering_presentation=pending))
        pending.write_text(json.dumps(journal))
        other = self.repo / 'other/work/step.lock'
        other.parent.mkdir(parents=True)
        other.write_text('drawing')
        self.assertTrue(worker_in_progress(self.repo, recovering_presentation=pending))
        other.unlink()
        unknown = self.repo / 'other/.blog-runs/unknown.json'
        unknown.parent.mkdir()
        unknown.write_text('{unreadable')
        with self.assertRaises(ValueError):
            worker_in_progress(self.repo, recovering_presentation=pending)

    def test_blog_run_and_tool_statuses_are_checked(self):
        for shape in ('.blog-runs/one.json', '.blog-runs/tools/abc.json'):
            record = self.repo / 'blogs' / shape
            record.parent.mkdir(parents=True, exist_ok=True)
            record.write_text(json.dumps({'status': 'working'}))
            self.assertTrue(worker_in_progress(self.repo))
            record.write_text(json.dumps({'status': 'stopped'}))
            self.assertFalse(worker_in_progress(self.repo))
            record.unlink()

    def test_unknown_scope_and_malformed_blog_records_refuse(self):
        def unreadable(*args, **kwargs):
            kwargs['onerror'](PermissionError('synthetic'))
            return iter(())
        with mock.patch('studio_core.sync_guard.os.walk', side_effect=unreadable):
            with self.assertRaisesRegex(ValueError, 'could not be checked'):
                worker_in_progress(self.repo)
        record = self.repo / '.blog-runs/one.json'
        record.parent.mkdir()
        record.write_text('{bad')
        with self.assertRaisesRegex(ValueError, 'could not be checked'):
            worker_in_progress(self.repo)

    def test_linked_directories_and_output_caches_are_not_traversed(self):
        with tempfile.TemporaryDirectory() as outside:
            other = Path(outside)
            (other / 'work').mkdir()
            (other / 'work/step.lock').touch()
            (self.repo / 'linked').symlink_to(other, target_is_directory=True)
            for record, data in (('deck/run.json', {'schema': 1, 'id': 'deck', 'title': 'Synthetic deck', 'steps': {}, 'route': 'idea', 'form': {}}),
                                 ('training/.training-studio/run.json', {'schema': 1, 'steps': {}, 'agent': 'test'})):
                item = self.repo / record.split('/')[0]
                path = self.repo / record
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(data))
                if item.name == 'training':
                    (item / '.training-studio/session.json').write_text(json.dumps({
                        'schema': 1, 'id': 'training', 'title': 'Synthetic training',
                        'levels': [], 'stage': 'intake', 'sizing': {}, 'settings': {
                            'deck_target': None, 'brand': None, 'brief_kind': 'product', 'stages': []},
                        'unavailable': {}, 'pins': {}, 'artifacts': {}, 'exports': {},
                        'decisions': [], 'events': []}))
                for cache in ('work', 'sources'):
                    (item / cache / 'deep/work').mkdir(parents=True)
                    (item / cache / 'deep/work/step.lock').touch()
            self.assertFalse(worker_in_progress(self.repo))

    def test_workspace_and_container_names_work_and_sources_do_not_hide_workers(self):
        for folder in ('work', 'sources', 'nested/work', 'nested/sources',
                       'work/nested/sources', 'sources/nested/work'):
            for shape in ('deck/work/step.lock', 'training/.training-studio/step.lock',
                          '.blog-runs/one.json', '.blog-runs/tools/abc.json'):
                with self.subTest(folder=folder, shape=shape):
                    marker = self.repo / folder / shape
                    marker.parent.mkdir(parents=True, exist_ok=True)
                    text = '{"status":"working"}' if marker.suffix == '.json' else 'active step'
                    marker.write_text(text)
                    self.assertTrue(worker_in_progress(self.repo))
                    self.assertEqual(marker.read_text(), text)
                    marker.unlink()
                    self.assertFalse(worker_in_progress(self.repo))

    def test_linked_training_metadata_does_not_hide_real_nested_workers(self):
        with tempfile.TemporaryDirectory() as outside:
            metadata = Path(outside)
            (metadata / 'run.json').write_text(json.dumps({
                'schema': 1, 'steps': {}, 'agent': 'test'}))
            (metadata / 'session.json').write_text(json.dumps({
                'schema': 1, 'id': 'training', 'title': 'Synthetic training',
                'levels': [], 'stage': 'intake', 'sizing': {}, 'settings': {
                    'deck_target': None, 'brand': None, 'brief_kind': 'product', 'stages': []},
                'unavailable': {}, 'pins': {}, 'artifacts': {}, 'exports': {},
                'decisions': [], 'events': []}))
            container = self.repo / 'container'
            container.mkdir()
            (container / '.training-studio').symlink_to(metadata, target_is_directory=True)

            def snapshot(root):
                return {str(path.relative_to(root)): (
                    ('link', str(path.readlink())) if path.is_symlink() else
                    ('directory',) if path.is_dir() else ('file', path.read_bytes()))
                    for path in root.rglob('*')}

            for cache in ('work', 'sources'):
                for shape in ('deck/work/step.lock', 'training/.training-studio/step.lock',
                              '.blog-runs/one.json'):
                    with self.subTest(cache=cache, shape=shape):
                        marker = container / cache / 'nested' / shape
                        marker.parent.mkdir(parents=True, exist_ok=True)
                        marker.write_text('{"status":"working"}' if marker.suffix == '.json'
                                          else 'active step')
                        before = snapshot(self.repo), snapshot(metadata)
                        self.assertTrue(worker_in_progress(self.repo))
                        self.assertEqual((snapshot(self.repo), snapshot(metadata)), before)
                        marker.unlink()
                        self.assertFalse(worker_in_progress(self.repo))

    def test_notice_explains_recovery_after_stop_or_interruption(self):
        self.assertIn('stopped', SYNC_WAIT.lower())
        self.assertIn('interrupted', SYNC_WAIT.lower())
        self.assertIn('reopen', SYNC_WAIT.lower())

    def test_pending_blog_migration_is_not_hidden_by_recognized_output_cache(self):
        container = self.repo / 'deck'
        container.mkdir()
        (container / 'run.json').write_text(json.dumps({'schema': 1, 'id': 'deck', 'title': 'Synthetic', 'steps': {}, 'route': 'idea', 'form': {}}))
        journal = container / 'sources/nested/blogs/one/desk/migration.pending.json'
        journal.parent.mkdir(parents=True)
        journal.write_text('{interrupted')
        self.assertTrue(worker_in_progress(self.repo))
        self.assertEqual(journal.read_text(), '{interrupted')
        journal.unlink()
        (journal.parent / 'migration.json').write_text('{broken')
        with self.assertRaisesRegex(ValueError, 'could not be checked'):
            worker_in_progress(self.repo)

    def test_unknown_item_records_do_not_hide_nested_workspaces(self):
        for record in ('container/run.json', 'container/.training-studio/run.json'):
            for text in ('{bad', '{}', '{"schema":999,"steps":{}}',
                         '{"schema":1,"steps":{},"route":"idea"}',
                         '{"schema":2,"id":"item","title":"Synthetic","steps":{},"form":{},"route":"idea"}',
                         '{"schema":3,"id":"item","title":"Synthetic","steps":{},"form":{},"route":"idea"}'):
                for shape in ('deck/work/step.lock', 'training/.training-studio/step.lock',
                              '.blog-runs/one.json'):
                    with self.subTest(record=record, text=text, shape=shape):
                        path = self.repo / record
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(text)
                        marker = self.repo / 'container/sources/nested/work' / shape
                        marker.parent.mkdir(parents=True, exist_ok=True)
                        marker.write_text('{"status":"working"}' if marker.suffix == '.json' else 'step')
                        self.assertTrue(worker_in_progress(self.repo))
                        marker.unlink()
                        path.unlink()

    def test_training_receipt_half_pair_and_product_bound_recovery(self):
        import base64
        from studio_core import training_migration as migration
        item = self.repo / 'training'
        item.mkdir()
        session = {'schema': 1, 'id': item.name, 'title': 'Synthetic Training Studio',
            'levels': [], 'sizing': {}, 'stage': 'blueprint', 'settings': {
                'deck_target': None, 'brand': None, 'brief_kind': 'product', 'stages': []},
            'unavailable': {}, 'pins': {}, 'artifacts': {}, 'exports': {}, 'decisions': [], 'events': []}
        run = {'schema': 1, 'agent': 'test', 'steps': {}, 'limits': {}, 'answers': {},
               'copies': {}, 'deck': {}, 'driver': None, 'halt': None}
        raw_session, raw_run = json.dumps(session).encode(), json.dumps(run).encode()
        for name, data in ((migration.SESSION, raw_session), (migration.RUN, raw_run)):
            file = item / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(data)
        plan = b'# Plan\n## M1 - Basics\n### O1 - Explain\n'
        (item / 'blueprint.md').write_bytes(plan)
        session['artifacts']['blueprint'] = {'file': 'blueprint.md', 'sha256': migration.digest(plan), 'built_from': {}}
        raw_session = json.dumps(session).encode()
        (item / migration.SESSION).write_bytes(raw_session)
        token = 'tm1.' + 'A' * 43
        origin = migration.receipt(raw_session, raw_run, item.name, token, [migration.SESSION, migration.RUN, 'blueprint.md'], ['blueprint'])
        session.update(flow='desk')
        run.update(flow='desk', execution='conversation', conversation_scope=['part'], migration_targets=['blueprint'], unfinished_migration=True)
        after = {migration.ORIGIN: json.dumps(origin).encode(),
                 migration.DESK_SESSION: json.dumps({'origin': origin, 'record': session}).encode(),
                 migration.DESK_RUN: json.dumps({'origin': origin, 'record': run}).encode(),
                 '@training-workspace/hub.json': b'{}'}
        for name in migration.WRITES:
            file = item / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(after[name])
        self.assertFalse(worker_in_progress(self.repo))
        for name in migration.WRITES:
            file = item / name
            file.unlink()
            with self.assertRaises(ValueError):
                worker_in_progress(self.repo)
            file.write_bytes(after[name])
        pending = item / migration.PENDING
        pending.parent.mkdir(parents=True)
        journal = {'schema': 1, 'product': 'Training Studio', 'id': item.name,
                   'expected': token, 'after': {name: base64.b64encode(data).decode() for name, data in after.items()},
                   'originals': {migration.SESSION: migration.digest(raw_session), migration.RUN: migration.digest(raw_run)},
                   'before_workspace': base64.b64encode(b'{}').decode(), 'index_before': '', 'index_prepared': '',
                   'head_before': {**dict.fromkeys(migration.WRITES, ''), '@training-workspace/hub.json': ''}}
        pending.write_text(json.dumps(journal))
        self.assertTrue(worker_in_progress(self.repo))
        self.assertFalse(worker_in_progress(self.repo, recovering_training=pending))
        for key in ('head_before', 'index_prepared', 'originals'):
            old = {name: value for name, value in journal.items() if name != key}
            pending.write_text(json.dumps(old))
            self.assertTrue(worker_in_progress(self.repo, recovering_training=pending))
        for head in ({}, {**journal['head_before'], migration.ORIGIN: 'unproven'},
                     {**journal['head_before'], '@training-workspace/hub.json': 'unknown'}):
            pending.write_text(json.dumps({**journal, 'head_before': head}))
            self.assertTrue(worker_in_progress(self.repo, recovering_training=pending))
        for key, value in (('product', 'Presentation Studio'), ('id', 'other')):
            changed = {**journal, key: value}
            pending.write_text(json.dumps(changed))
            self.assertTrue(worker_in_progress(self.repo, recovering_training=pending))
        pending.write_text(json.dumps(journal))
        other = self.repo / 'other/work/step.lock'
        other.parent.mkdir(parents=True)
        other.write_text('drawing')
        self.assertTrue(worker_in_progress(self.repo, recovering_training=pending))

    def test_training_unknown_update_chain_is_never_idle(self):
        path = self.repo / 'training/.training-studio/run.json'
        path.parent.mkdir(parents=True)
        for chain in ({'status': 'unknown'}, {'id': 'a' * 24, 'level': None},
                      {'id': 'a' * 24, 'level': None, 'status': 'done', 'blocked': 'blueprint'}):
            path.write_text(json.dumps({'schema': 1, 'steps': {}, 'drafts': {'update_chain': chain}}))
            with self.assertRaises(ValueError):
                worker_in_progress(self.repo)
        for status in ('done', 'stopped', 'working'):
            path.write_text(json.dumps({'schema': 1, 'steps': {}, 'drafts': {'update_chain': {
                'id': 'a' * 24, 'level': None, 'status': status, 'blocked': []}}}))
            self.assertEqual(worker_in_progress(self.repo), status == 'working')

    def test_training_declared_shared_inputs_and_effective_chain_are_validated(self):
        from studio_core import training_migration as migration
        item = self.repo / 'training'
        session = {'schema': 1, 'id': item.name, 'title': 'Synthetic Training Studio',
            'levels': [], 'sizing': {}, 'stage': 'blueprint', 'settings': {
                'deck_target': None, 'brand': None, 'brief_kind': 'product', 'stages': []},
            'unavailable': {}, 'pins': {}, 'artifacts': {
                'blueprint': {'file': 'blueprint.md', 'sha256': 'a' * 64, 'built_from': {'research': 'b' * 64}},
                'research': {'file': '.harness-research/research-report.md', 'sha256': 'c' * 64, 'built_from': {}}},
            'exports': {}, 'decisions': [], 'events': []}
        run = {'schema': 1, 'agent': 'test', 'steps': {}, 'limits': {}, 'answers': {}, 'copies': {}, 'deck': {}}
        files = {migration.SESSION: json.dumps(session).encode(), migration.RUN: json.dumps(run).encode(),
            'blueprint.md': b'# Plan\n## M1 - Basics\n### O1 - Explain\n',
            '.harness-research/research.json': json.dumps({'schema': 1, 'owner': 'harness-research', 'items': [], 'results': {}}).encode(),
            '.harness-research/research-report.md': b'# Research\n', 'research-report.md': b'# Approved research\n'}
        origin = migration.receipt(files[migration.SESSION], files[migration.RUN], item.name, 'tm1.' + 'A' * 43,
                                   [migration.SESSION, migration.RUN, 'blueprint.md'], ['blueprint'], sources=True)
        session = {**session, 'flow': 'desk'}
        run.update(flow='desk', execution='conversation', conversation_scope=['part'], migration_targets=['blueprint'], unfinished_migration=True)
        files.update({migration.ORIGIN: json.dumps(origin).encode(), migration.DESK_SESSION: json.dumps({'origin': origin, 'record': session}).encode(),
                      migration.DESK_RUN: json.dumps({'origin': origin, 'record': run}).encode()})
        for name, data in files.items():
            path = item / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.assertFalse(worker_in_progress(self.repo), 'Explicitly private source files need not exist in a peer clone.')
        for name in ('.harness-research/research.json', 'research-report.md'):
            path = item / name
            original = path.read_bytes()
            for data in (None, b'{}' if name.endswith('.json') else b''):
                if data is None:
                    path.unlink()
                else:
                    path.write_bytes(data)
                with self.assertRaises(ValueError):
                    worker_in_progress(self.repo)
                path.write_bytes(original)
        for chain in ({'status': 'unknown'}, {'id': 'a' * 24, 'level': None, 'status': 'working'},
                      {'id': 'a' * 24, 'level': None, 'status': 'stopped'}):
            changed = {**run, 'drafts': {'update_chain': chain}}
            (item / migration.DESK_RUN).write_text(json.dumps({'origin': origin, 'record': changed}))
            if chain['status'] == 'unknown':
                with self.assertRaises(ValueError):
                    worker_in_progress(self.repo)
            else:
                self.assertEqual(worker_in_progress(self.repo), chain['status'] == 'working')

    # --- GitHub issue #541: a refusal names its folder; recognition is not migration -------

    def test_the_refusal_names_the_folder_relative_to_the_repository_and_why(self):
        self.assertEqual(sync_guard.unchecked(), sync_guard.UNCHECKED + ' ' + sync_guard.UNCHECKED_NEXT)
        record = json.loads((self.presentation_item() / 'run.json').read_text())
        deck = self.repo / 'decks/odd deck'
        deck.mkdir(parents=True)
        for schema in (0, 7, '6'):
            with self.subTest(schema=schema):
                (deck / 'run.json').write_text(json.dumps({**record, 'id': deck.name, 'schema': schema}))
                with self.assertRaises(ValueError) as caught:
                    worker_in_progress(self.repo)
                said = str(caught.exception)
                self.assertEqual(said, sync_guard.unchecked('decks/odd deck', sync_guard.UNKNOWN_DECK))
                self.assertTrue(said.startswith(sync_guard.UNCHECKED))
                self.assertIn('In the folder decks/odd deck, its Presentation Studio run record', said)
                self.assertNotIn(str(self.repo), said)
        # A worker record the check cannot read names its item's folder too.
        (deck / 'run.json').unlink()
        status = self.repo / 'blogs/.blog-runs/one.json'
        status.parent.mkdir(parents=True)
        status.write_text('{"status": 1}')
        with self.assertRaises(ValueError) as caught:
            worker_in_progress(self.repo)
        self.assertEqual(str(caught.exception), sync_guard.unchecked('blogs', sync_guard.NO_STATUS))

    def test_an_unreadable_folder_is_named_and_the_top_folder_is_said_in_words(self):
        def unreadable(top, *args, **kwargs):
            kwargs['onerror'](PermissionError(13, 'Permission denied', str(Path(top) / 'private')))
            return iter(())
        with mock.patch('studio_core.sync_guard.os.walk', side_effect=unreadable):
            with self.assertRaises(ValueError) as caught:
                worker_in_progress(self.repo)
        said = str(caught.exception)
        self.assertEqual(said, sync_guard.unchecked('.', sync_guard.UNREADABLE.format(name='private')))
        self.assertIn("In the repository's top folder, private cannot be read.", said)
        self.assertNotIn(str(self.repo), said)

    def test_a_shaped_record_is_written_but_only_schemas_1_to_4_may_migrate(self):
        # Schemas 1 to 4 may be opened on the desk by the explicit migration when shaped;
        # 5 and 6 exist only on the desk and never migrate (GitHub issue #542).
        from studio_core import presentation_migration as migration, research_session
        base = json.loads((self.presentation_item() / 'run.json').read_text())
        contract = {'schema': 2, 'version': '1.0.0', 'digest': '1' * 64}
        execution = {'schema': 1, 'protocol': research_session.PROTOCOL, 'workers': 3,
                     'capability': {'protocol': research_session.PROTOCOL}}
        story = {'schema': 1, 'revision': 0, 'outline': None,
                 'limits': {'seconds': 270, 'input_chars': 48000}}
        sections = {'schema': 1, 'protocol': 'studio-section-combining-v1', 'seconds': 450,
                    'more_time': {}, 'reuse': None}
        four = {**base, 'schema': 4, 'research_contract': contract, 'research_execution': execution}
        five = {**four, 'schema': 5, 'flow': 'desk', 'slide_story': story}
        six = {**five, 'schema': 6, 'section_synthesis': sections}
        for record in (base, {**base, 'schema': 3, 'research_contract': contract}, four, five, six):
            with self.subTest(schema=record['schema']):
                self.assertTrue(migration.written(record))
                self.assertEqual(migration.supported(record), record['schema'] <= 4)
        for name, record in (('four without contract', {**four, 'research_contract': None}),
                             ('four without protocol', {**four, 'research_execution': {}}),
                             ('five off the desk', {**five, 'flow': None}),
                             ('five without story', {**five, 'slide_story': None}),
                             ('five with a bad outline', {**five, 'slide_story': {**story, 'outline': {}}}),
                             ('six without section combining', {**six, 'section_synthesis': {}}),
                             ('seven', {**six, 'schema': 7}),
                             ('two without review level', {**base, 'schema': 2})):
            with self.subTest(name):
                self.assertFalse(migration.written(record))
                self.assertFalse(migration.supported(record))

    def test_an_unrecognised_training_folder_is_walked_and_a_recognised_one_skipped(self):
        from studio_core import research_session
        item = self.repo / 'training'
        (item / '.training-studio').mkdir(parents=True)
        (item / '.training-studio/session.json').write_text(json.dumps({
            'schema': 1, 'id': 'training', 'title': 'Synthetic training',
            'levels': [], 'stage': 'intake', 'sizing': {}, 'settings': {
                'deck_target': None, 'brand': None, 'brief_kind': 'product', 'stages': []},
            'unavailable': {}, 'pins': {}, 'artifacts': {}, 'exports': {},
            'decisions': [], 'events': []}))
        execution = {'schema': 1, 'protocol': research_session.PROTOCOL, 'workers': 3,
                     'capability': {'protocol': research_session.PROTOCOL}}
        five = {'schema': 5, 'agent': 'test', 'steps': {}, 'flow': 'desk',
                'research_contract': {'schema': 2}, 'research_execution': execution}
        conversation = {'schema': 4, 'agent': 'test', 'steps': {}, 'flow': 'desk',
                        'execution': 'conversation'}
        odd = item / 'work/kept/.blog-runs/odd.json'
        odd.parent.mkdir(parents=True)
        odd.write_text('{"status":"working"}')
        for name, record, known in (
                ('five', five, True), ('five without protocol', {**five, 'research_execution': None}, False),
                ('nine', {**five, 'schema': 9}, False), ('conversation four', conversation, True),
                ('runner four without contract', {**conversation, 'execution': 'runner'}, False)):
            with self.subTest(name):
                (item / '.training-studio/run.json').write_text(json.dumps(record))
                self.assertEqual(sync_guard.training_written(record), known)
                # Skipped when known; walked, where the working-looking record counts, when not.
                self.assertEqual(worker_in_progress(self.repo), not known)

    def test_a_blog_run_saved_with_a_research_execution_record_is_never_refused(self):
        # Blog Studio's run record is read only through a desk migration's own markers, which
        # a saved schema 4 run never gets, so the check has no refusal path for it.
        from studio_core import research_session
        blog = self.repo / 'blogs/synthetic-post'
        (blog / 'derived').mkdir(parents=True)
        (blog / 'session.json').write_text(json.dumps({'schema': 1, 'id': blog.name, 'title': 'Synthetic post'}))
        (blog / 'derived/blog-run.json').write_text(json.dumps({
            'schema': 4, 'approval': 'page', 'engine': 'claude', 'pipeline': ['outline', 'draft'],
            'stages': {}, 'review_policy': {'schema': 1, 'level': 'step_by_step'},
            'research_contract': {'schema': 2, 'version': '1.0.0', 'digest': '1' * 64},
            'research_execution': {'schema': 1, 'protocol': research_session.PROTOCOL, 'workers': 3,
                                   'capability': {'protocol': research_session.PROTOCOL, 'digest': '0' * 64}}}))
        status = self.repo / 'blogs/.blog-runs/synthetic-post.json'
        status.parent.mkdir()
        for value, busy in (('paused', False), ('working', True)):
            status.write_text(json.dumps({'enabled': False, 'status': value}))
            self.assertEqual(worker_in_progress(self.repo), busy)


class BlogTeamMigrationTests(unittest.TestCase):
    """A Blog Studio blog moved to the desk in a team repository holds the team's run.json
    driver record beside its own desk/migration.json. The records say whose they are, so it
    is checked as Blog Studio's: idle when whole, busy while its migration is pending, refused
    when its record is damaged, and never read as a Presentation Studio deck."""

    def setUp(self):
        import os
        import shutil
        import subprocess
        import sys

        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name).resolve()
        self.repo = base / 'team'
        root = self.repo / 'blogs'
        studios = Path(__file__).resolve().parents[1] / 'studios/blog'
        tree = studios / 'tests/fixtures/saved/draft-gate'
        (self.ident,) = [path.name for path in (tree / 'articles').iterdir()]
        environment = {
            **os.environ,
            'HOME': str(base / 'home'),
            'BLOG_STUDIO_DATA': str(base / 'data'),
            'STUDIOS_CONFIG': str(base / 'studios-config.json'),
            'STUDIOS_LIBRARY': str(base / 'library'),
            'BRAND_SKILL_RUNTIME': str(base / 'no-brand'),
            'HARNESS_RESEARCH_RUNTIME': str(base / 'no-research'),
        }
        script = studios / 'skills/blog-studio/scripts/studio.py'

        def blog(*words):
            done = subprocess.run([sys.executable, str(script), '--root', str(root), *words],
                                  env=environment, capture_output=True, text=True, timeout=60)
            self.assertEqual(done.returncode, 0, done.stderr)
            return json.loads(done.stdout or 'null')

        blog('init')
        shutil.copytree(tree / 'articles', root / 'articles', dirs_exist_ok=True)
        shown = blog('desk', 'migration-preview', '--article', self.ident)
        self.assertTrue(shown['eligible'], shown)
        blog('desk', 'migrate', '--article', self.ident, '--expected', shown['expected'])
        self.folder = root / 'articles' / self.ident
        self.assertTrue((self.folder / 'desk/migration.json').is_file())
        # The team's driver record, as Blog Studio keeps one beside every blog it shares.
        (self.folder / 'run.json').write_text(json.dumps({'schema': 1, 'driver': None}))

    def test_a_whole_migration_beside_the_team_record_is_idle(self):
        self.assertFalse(worker_in_progress(self.repo))
        (self.folder / 'run.json').write_text(json.dumps(
            {'schema': 1, 'driver': {'name': 'Synthetic Author', 'computer': '0' * 16,
                                     'since': '2026-11-25T00:00:00+00:00'}}))
        self.assertFalse(worker_in_progress(self.repo))

    def test_a_pending_migration_is_busy(self):
        (self.folder / 'desk/migration.pending.json').write_text('{"interrupted": true}')
        self.assertTrue(worker_in_progress(self.repo))

    def test_a_damaged_or_unclear_record_is_refused(self):
        marker = self.folder / 'desk/migration.json'
        whole = marker.read_text()
        value = json.loads(whole)
        for damaged in ('{broken', json.dumps({**value, 'expected': 'bm1.short'}),
                        json.dumps({**value, 'id': 'another-blog'})):
            with self.subTest(record=damaged[:30]):
                marker.write_text(damaged)
                with self.assertRaisesRegex(ValueError, 'could not be checked'):
                    worker_in_progress(self.repo)
        marker.write_text(whole)
        # A Presentation Studio receipt beside a Blog Studio record: neither can be told apart.
        (self.folder / 'desk/migration-origin.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'could not be checked'):
            worker_in_progress(self.repo)

    def test_a_presentation_record_that_claims_blog_studio_is_still_refused(self):
        deck = self.repo / 'deck'
        deck.mkdir()
        (deck / 'run.json').write_text(json.dumps({'schema': 1, 'id': 'deck', 'title': 'Synthetic',
            'created': '2026-10-28T12:00:00Z', 'agent': 'test', 'route': 'scratch',
            'form': {'route': 'scratch', 'title': 'Synthetic', 'output': 'pptx'},
            'steps': {}, 'gates': {}, 'limits': {}, 'revisions': []}))
        (deck / 'desk').mkdir()
        (deck / 'desk/migration.json').write_text(json.dumps({'schema': 1, 'product': 'Blog Studio'}))
        with self.assertRaisesRegex(ValueError, 'could not be checked'):
            worker_in_progress(self.repo)
