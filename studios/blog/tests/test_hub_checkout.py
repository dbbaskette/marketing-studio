"""Normal Hub checkouts and lossless local migration; no live accounts."""
import tempfile
import shutil
from pathlib import Path
import unittest
from hub_fixtures import FakeProvider
from hub import Registry
from hub_store import git, read_json, write_json, HubError

class CheckoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.registry = Registry(self.base / 'registry', FakeProvider(self.base / 'remotes'), self.base / 'blogs')
        self.id = self.registry.create('fixture/team', 'Team')['hub']
        self.hub = self.registry.hub(self.id)

    def legacy(self):
        old = self.base / 'legacy';old.mkdir()
        git(old / 'repository.git', 'init', '--bare', '--quiet', '--initial-branch=main')
        commit = self.hub.status()['revision']
        git(old / 'repository.git', 'fetch', '--quiet', str(self.hub.repository), commit)
        git(old / 'repository.git', 'update-ref', 'refs/heads/main', commit)
        for child in self.hub.root.iterdir():
            dest = old / child.name
            if child.is_dir():shutil.copytree(child, dest)
            else:shutil.copy2(child, dest)
        state = self.registry.state();entry = state['hubs'][self.id]
        entry.pop('layout');entry['path'] = str(old)
        config = read_json(old / 'config.json');config.pop('layout', None);config['path'] = str(old)
        write_json(old / 'config.json', config);write_json(self.registry.root / 'registry.json', state)
        self.hub = self.registry.hub(self.id)
        return old

    def test_standard_checkout_is_visible_and_local_state_is_ignored(self):
        root = self.base / 'blogs/team'
        self.assertEqual(self.hub.status()['clone'], str(root))
        self.assertTrue((root / 'README.md').is_file())
        self.assertEqual(git(self.hub.repository, 'rev-parse', '--is-bare-repository').strip(), b'false')
        self.assertEqual(git(self.hub.repository, 'status', '--porcelain').strip(), b'')
        self.assertEqual(git(self.hub.repository, 'rev-parse', '--abbrev-ref', 'main@{upstream}').strip(), b'origin/main')
        self.assertEqual(self.registry.selected(root / '.blog-studio').id, self.id)
        self.assertTrue((root / '.blog-studio/studio.json').exists())
        result = self.hub.save('note', 'Visible note', 'Team context')
        self.assertEqual(result['status'], 'shared')
        self.assertTrue((root / '.blog-studio/items' / result['item']).exists())

    def test_existing_writing_workspace_does_not_change_standard_clone_location(self):
        workspace = self.base / 'existing-writing/.blog-studio'
        workspace.mkdir(parents=True);(workspace.parent / 'keep.txt').write_text('Existing work')
        result = self.registry.create('fixture/second', 'Second', workspace=workspace)
        self.assertEqual(result['clone'], str(self.base / 'blogs/second'))
        self.assertEqual((workspace.parent / 'keep.txt').read_text(), 'Existing work')
        self.assertEqual(self.registry.selected(workspace).id, result['hub'])

    def test_dirty_checkout_and_untracked_files_are_preserved(self):
        path = self.hub.checkout / 'README.md';path.write_text('Local edits')
        with self.assertRaisesRegex(HubError, 'local edits'):self.hub.refresh()
        self.assertEqual(path.read_text(), 'Local edits')
        git(self.hub.repository, 'checkout', '--', 'README.md')
        path = self.hub.checkout / 'personal.txt';path.write_text('Private note')
        with self.assertRaisesRegex(HubError, 'local edits'):self.hub.sync()
        self.assertEqual(path.read_text(), 'Private note')

    def test_legacy_migration_preserves_queued_work_and_old_copy_offline(self):
        old = self.legacy()
        queued = self.hub.save('note', 'Offline note', 'Keep me', offline=True)
        self.registry.provider.unavailable = True
        result = self.registry.migrate(self.id, self.base / 'new-team')
        self.assertEqual(result['queued'], 1)
        self.assertEqual(result['preserved_legacy_copy'], str(old))
        self.assertTrue((old / 'repository.git').exists())
        migrated = self.registry.hub(self.id)
        self.assertEqual(git(migrated.repository, 'status', '--porcelain').strip(), b'')
        self.assertEqual(migrated.read(queued['item'])['record']['title'], 'Offline note')
        self.registry.provider.unavailable = False
        self.assertEqual(migrated.sync()['status'], 'shared')
        self.assertEqual(migrated.status()['queued'], 0)
        self.assertEqual(self.registry.migrate(self.id)['status'], 'already-migrated')

    def test_existing_selected_workspace_is_preserved(self):
        self.legacy()
        target = self.base / 'existing-team';workspace = target / '.blog-studio'
        self.registry.select(self.id, workspace)
        marker = workspace / 'draft.md';marker.write_text('Unsaved writing')
        self.registry.migrate(self.id, target)
        self.assertEqual(marker.read_text(), 'Unsaved writing')
        self.assertTrue((target / '.git').exists())

    def test_migration_refuses_unrelated_destination(self):
        old = self.legacy()
        target = self.base / 'occupied';target.mkdir();(target / 'keep').write_text('Keep')
        with self.assertRaisesRegex(HubError, 'preserved'):self.registry.migrate(self.id, target)
        self.assertEqual(self.registry.hub(self.id).root, old)
        self.assertEqual((target / 'keep').read_text(), 'Keep')
