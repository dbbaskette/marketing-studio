"""Repository sync uses disposable local remotes and synthetic Git identities."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import sync_repos


class SyncRepositoriesTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='studio-repo-sync-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.home = self.base / 'home'
        self.home.mkdir()
        self.environment = {**os.environ, 'HOME': str(self.home), 'GIT_CONFIG_GLOBAL': os.devnull,
                            'GIT_CONFIG_NOSYSTEM': '1', 'GIT_AUTHOR_NAME': 'Test',
                            'GIT_AUTHOR_EMAIL': 'test@example.invalid', 'GIT_COMMITTER_NAME': 'Test',
                            'GIT_COMMITTER_EMAIL': 'test@example.invalid'}
        patcher = mock.patch.dict(os.environ, self.environment, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.projects = self.base / 'Projects with spaces'
        self.projects.mkdir()
        self.main = self.projects / 'marketing-studio'
        self.git(self.projects, 'init', '-q', '-b', 'main', str(self.main))
        self.git(self.main, 'commit', '-q', '--allow-empty', '-m', 'Initial')
        self.remote = self.base / 'remote.git'
        self.git(self.base, 'clone', '-q', '--bare', str(self.main), str(self.remote))
        self.git(self.main, 'remote', 'add', 'origin', str(self.remote))
        self.git(self.main, 'branch', '--set-upstream-to=origin/main', 'main', success=False)
        self.git(self.main, 'fetch', '-q', 'origin')
        self.git(self.main, 'branch', '--set-upstream-to=origin/main', 'main')

    def git(self, path, *args, success=True):
        done = subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', '-c', 'gc.auto=0',
                               '-C', str(path), *args], env=self.environment,
                              capture_output=True, text=True, timeout=20)
        if success:
            self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout.strip()

    def advance_remote(self):
        writer = self.base / 'writer'
        self.git(self.base, 'clone', '-q', str(self.remote), str(writer))
        (writer / 'new.txt').write_text('upstream change')
        self.git(writer, 'add', 'new.txt')
        self.git(writer, 'commit', '-q', '-m', 'Upstream')
        self.git(writer, 'push', '-q', 'origin', 'main')
        return self.git(writer, 'rev-parse', 'HEAD')

    def update(self, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return sync_repos.Sync(timeout=20, **kwargs).update(
                sync_repos.Repository('Marketing Studio', self.main))

    def test_clean_checkout_fast_forwards_and_preserves_current_branch(self):
        expected = self.advance_remote()
        status, _ = self.update()
        self.assertEqual(status, 'UPDATED')
        self.assertEqual(self.git(self.main, 'rev-parse', 'HEAD'), expected)
        self.assertEqual(self.git(self.main, 'branch', '--show-current'), 'main')

    def test_dirty_detached_and_untracked_work_is_kept_without_fetching(self):
        tracking = self.git(self.main, 'rev-parse', 'origin/main')
        self.advance_remote()
        (self.main / 'private.txt').write_text('keep local work')
        status, detail = self.update()
        self.assertEqual(status, 'SKIPPED')
        self.assertIn('Local changes kept', detail)
        self.assertEqual(self.git(self.main, 'rev-parse', 'origin/main'), tracking)
        self.assertEqual((self.main / 'private.txt').read_text(), 'keep local work')
        (self.main / 'private.txt').unlink()
        self.git(self.main, 'checkout', '-q', '--detach')
        self.assertIn('Detached HEAD', self.update()[1])

    def test_diverged_branch_fails_without_rebase_or_losing_local_commits(self):
        self.advance_remote()
        self.git(self.main, 'commit', '-q', '--allow-empty', '-m', 'Local commit')
        original = self.git(self.main, 'rev-parse', 'HEAD')
        with self.assertRaises(ValueError):
            self.update()
        self.assertEqual(self.git(self.main, 'rev-parse', 'HEAD'), original)
        self.assertEqual(self.git(self.main, 'status', '--porcelain'), '')

    def test_clean_local_commits_ahead_of_upstream_are_kept_and_reported(self):
        self.git(self.main, 'commit', '-q', '--allow-empty', '-m', 'Unpublished work')
        original = self.git(self.main, 'rev-parse', 'HEAD')
        status, detail = self.update()
        self.assertEqual(status, 'AHEAD')
        self.assertIn('1 local commit', detail)
        self.assertEqual(self.git(self.main, 'rev-parse', 'HEAD'), original)

    def test_missing_clone_is_a_sibling_and_dry_run_makes_no_network_request(self):
        target = self.projects / 'harness-test'
        repository = sync_repos.Repository('Test', target, self.remote.as_uri())
        with contextlib.redirect_stdout(io.StringIO()):
            status, _ = sync_repos.Sync(dry_run=True).update(repository)
            self.assertEqual(status, 'PLAN')
            self.assertFalse(target.exists())
            status, _ = sync_repos.Sync(timeout=20).update(repository)
        self.assertEqual(status, 'CLONED')
        self.assertEqual(self.git(target, 'rev-parse', '--show-toplevel'), str(target))
        self.assertEqual(target.parent, self.main.parent)

    def test_config_paths_from_another_host_use_folder_names_beside_marketing_studio(self):
        config = self.main / 'studio-package.local.json'
        config.write_text(json.dumps({'schema': 1, 'sources': {
            'brand': {'path': '/another/computer/Projects/tanzu-brand'},
            'harness-slides': {'git': 'https://example.com/custom-slides.git', 'ref': 'v1.0.0'}}}))
        extra = self.projects / 'harness-extra'
        extra.mkdir()
        self.git(extra, 'init', '-q')
        selected = sync_repos.repositories(self.main)
        self.assertTrue(all(repo.path.parent == self.projects for repo in selected))
        self.assertEqual(selected[0].path, self.main)
        self.assertIn(extra, [repo.path for repo in selected])
        self.assertIn(self.projects / 'tanzu-brand', [repo.path for repo in selected])
        self.assertIn(self.projects / 'custom-slides', [repo.path for repo in selected])
        self.assertNotIn('v1.0.0', [repo.url for repo in selected])

    def test_a_failed_repository_does_not_prevent_the_remaining_updates(self):
        repositories = [sync_repos.Repository('First', self.main),
                        sync_repos.Repository('Second', self.projects / 'harness-second')]
        with mock.patch.object(sync_repos, 'repositories', return_value=repositories), \
                mock.patch.object(sync_repos.Sync, 'update', side_effect=[ValueError('offline'), ('CURRENT', 'abc')]) as update, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(sync_repos.main([]), 1)
        self.assertEqual(update.call_count, 2)
        self.assertIn('FAILED', output.getvalue())
        self.assertIn('CURRENT', output.getvalue())

    def test_no_upstream_is_left_unchanged_and_nonrepository_folders_are_preserved(self):
        self.git(self.main, 'branch', '--unset-upstream')
        self.assertIn('no upstream', self.update()[1])
        plain = self.projects / 'tanzu-brand'
        plain.mkdir()
        sentinel = plain / 'keep.txt'
        sentinel.write_text('keep')
        with self.assertRaises(ValueError), contextlib.redirect_stdout(io.StringIO()):
            sync_repos.Sync().update(sync_repos.Repository('Tanzu Brand', plain, self.remote.as_uri()))
        self.assertEqual(sentinel.read_text(), 'keep')

    def test_timeout_stops_the_git_process_and_reports_the_timeout(self):
        fakebin = self.base / 'bin'
        fakebin.mkdir()
        tool = fakebin / 'git'
        tool.write_text('#!/bin/sh\nexec /bin/sleep 10\n')
        tool.chmod(0o755)
        with mock.patch.dict(os.environ, {'PATH': str(fakebin)}), \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, 'timed out'):
            sync_repos.Sync(timeout=0.05).git(self.main, 'fetch')


if __name__ == '__main__':
    unittest.main()
