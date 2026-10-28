from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import threading
from unittest import mock

from helpers import Isolated
from graphics_fixtures import png
from runner.contracts import Invalid, canonical
from runner import workspace
from runner.workspace import Store


class WorkspaceTests(Isolated):
    def test_read_only_status_does_not_initialize_and_setup_preserves_shared_settings(self):
        self.assertIsNone(Store.current())
        self.assertFalse(self.data.exists())
        original = '{ "schema": 1, "local": {"root": "' + str(self.temp / 'shared-root') + '"}, "unrelated": [1,2] }\n'
        self.settings.write_text(original)
        store = Store.setup()
        self.assertEqual(store.root, self.temp / 'shared-root/infographic-workspace')
        self.assertTrue((store.root / '.git').is_dir())
        self.assertEqual(self.settings.read_text(), original)
        self.assertEqual(Store.current().root, store.root)
        self.settings.write_text('{"schema":1,"local":{"root":"' + str(self.temp / 'changed') + '"}}')
        self.assertEqual(Store.setup().root, store.root)
        with self.assertRaises(Invalid):
            Store.setup(self.workspace)
        self.assertFalse(self.workspace.exists())

    def test_existing_content_team_choice_and_application_directories_are_not_repurposed(self):
        self.workspace.mkdir()
        kept = self.workspace / 'keep.txt'
        kept.write_text('Existing synthetic file')
        with self.assertRaises(Invalid):
            Store.setup(self.workspace)
        self.assertEqual(kept.read_text(), 'Existing synthetic file')
        self.settings.write_text('{"schema":1,"team":{"repository":"https://example.invalid/team.git"}}')
        with self.assertRaisesRegex(Invalid, 'Team connection'):
            Store.setup()
        with self.assertRaisesRegex(Invalid, 'outside'):
            Store.setup(Path(__file__).resolve().parents[1] / 'forbidden-workspace')

    def test_stale_edits_and_concurrent_writers_cannot_overwrite_a_revision(self):
        store = Store.setup(self.workspace)
        initial = store.create('Original')
        other = Store.current()
        barrier, results = threading.Barrier(2), []

        def change(selected, title):
            barrier.wait()
            try:
                updated = selected.edit_brief(initial['id'], {**initial['brief'], 'title': title}, expected_revision=0)
                results.append(('saved', updated['revision']))
            except Invalid:
                results.append(('refused', None))

        workers = [threading.Thread(target=change, args=(selected, title))
                   for selected, title in [(store, 'First'), (other, 'Second')]]
        for thread in workers:
            thread.start()
        for thread in workers:
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
        self.assertEqual(sorted(result[0] for result in results), ['refused', 'saved'])
        saved = store.read(initial['id'])
        self.assertEqual(saved['revision'], 1)
        versions = list((store.root / 'projects' / initial['id'] / 'versions').glob('*.json'))
        self.assertEqual(len(versions), 2)
        self.assertIn('Original', [json.loads(v.read_text())['brief']['title'] for v in versions])

    def test_interrupted_pointer_save_preserves_current_work_and_retry_is_safe(self):
        store = Store.setup(self.workspace)
        initial = store.create('Original')
        real_atomic = workspace._atomic

        def interrupted(path, raw):
            if path.name == 'current.json':
                raise OSError('synthetic interrupted write')
            return real_atomic(path, raw)

        with mock.patch.object(workspace, '_atomic', side_effect=interrupted), self.assertRaises(OSError):
            store.edit_brief(initial['id'], {**initial['brief'], 'title': 'Interrupted'}, expected_revision=0)
        self.assertEqual(store.read(initial['id']), initial)
        result = store.edit_brief(initial['id'], {**initial['brief'], 'title': 'Retry'}, expected_revision=0)
        self.assertEqual(result['revision'], 1)
        self.assertEqual(store.read(initial['id'])['brief']['title'], 'Retry')

    def test_changed_owner_or_revision_bytes_are_refused(self):
        store = Store.setup(self.workspace)
        initial = store.create('Original')
        version = next((store.root / 'projects' / initial['id'] / 'versions').glob('*.json'))
        version.write_text('{}')
        with self.assertRaisesRegex(Invalid, 'changed unexpectedly'):
            store.read(initial['id'])
        marker = store.root / '.infographic-studio/workspace.json'
        marker.write_bytes(canonical({'schema': 1, 'product': 'Infographic Studio', 'owner': 'other'}))
        with self.assertRaisesRegex(Invalid, 'owner changed'):
            store.create('Unsafe')

    def test_links_traversal_and_nonregular_reads_are_refused(self):
        store = Store.setup(self.workspace)
        initial = store.create('Original')
        for ident in ('../workspace', '/absolute', 'one/two', ''):
            with self.subTest(ident=ident), self.assertRaises(Invalid):
                store.read(ident)
        other = self.temp / 'elsewhere'
        other.mkdir()
        folder = store.root / 'projects' / initial['id']
        (folder / 'current.json').unlink()
        (folder / 'current.json').symlink_to(other / 'record.json')
        with self.assertRaises(Invalid):
            store.read(initial['id'])
        (folder / 'current.json').unlink()
        os.mkfifo(folder / 'current.json')
        with self.assertRaises(Invalid):
            store.read(initial['id'])
        self.assertIn('problem', store.listing()[0])
        with self.assertRaisesRegex(Invalid, 'lock'):
            store._publish(initial)

    def test_explicit_recovery_of_existing_native_workspace_preserves_content(self):
        store = Store.setup(self.workspace)
        initial = store.create('Saved')
        (self.data / 'workspace.json').unlink()
        recovered = Store.setup(self.workspace)
        self.assertEqual(recovered.owner, store.owner)
        self.assertEqual(recovered.read(initial['id']), initial)

    def test_only_recorded_regular_hash_matching_assets_can_be_read(self):
        store = Store.setup(self.workspace)
        initial = store.create('Asset fixture')
        raw = png()
        initial['assets'] = [{'id': 'a1', 'file': 'assets/marker.png', 'mime': 'image/png',
                              'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw), 'width': 4, 'height': 4}]
        folder = store.root / 'projects' / initial['id'] / 'assets'
        folder.mkdir()
        (folder / 'marker.png').write_bytes(raw)
        with store.locked():
            store._publish(initial)
        self.assertEqual(store.read_asset(initial['id'], 'a1'), ('image/png', raw))
        with self.assertRaises(Invalid):
            store.read_asset(initial['id'], '../current.json')
        (folder / 'marker.png').write_bytes(b'changed')
        with self.assertRaisesRegex(Invalid, 'captured revision'):
            store.read_asset(initial['id'], 'a1')
