"""Engine stores and Git commits share one persistent lock across processes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import helpers
import runner_support  # noqa: F401
from runner import engine as engines, gitstate
from studio_core.process_lock import ProcessRLock


class EngineProcessLockTests(unittest.TestCase):
    def test_two_engine_processes_preserve_updates_and_git_history(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary).resolve()
            def git(*args):
                return subprocess.run(['git', *args], cwd=repo, capture_output=True,
                                      text=True, check=True).stdout.strip()
            git('init', '--quiet', '--initial-branch=main')
            git('config', 'user.name', 'Disposable Test')
            git('config', 'user.email', 'test@example.invalid')
            root = repo / 'items' / 'one'
            root.mkdir(parents=True)
            record = root / engines.RECORD
            record.parent.mkdir(parents=True, exist_ok=True)
            record.write_text(json.dumps({'schema': 1, 'steps': {}, 'count': 0,
                                         'unrelated': {'original': True}}))
            (repo / 'unrelated.txt').write_text('preserve me')
            git('add', '.')
            git('commit', '--quiet', '-m', 'initial')
            code = r"""
import sys, time
from pathlib import Path
import helpers, runner_support
from runner import engine as engines, gitstate
repo, root = map(Path, sys.argv[1:])
space = gitstate.Workspace('Disposable Test', repo, 'items', 'main')
gitstate.current = lambda: space
engine = engines.Engine(background=False)
for _ in range(8):
 with engine.files:
  with engine.files:
   record = engine._load(root)
   record['count'] += 1
   time.sleep(.005)
   engine._store(root, record)
   gitstate.commit(space, 'keep update', [root])
"""
            env = {**os.environ, 'HOME': str(repo / 'home'),
                   'PYTHONPATH': str(helpers.REPO / 'tests')}
            children = [subprocess.Popen([sys.executable, '-c', code, str(repo), str(root)],
                        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                        for _ in range(2)]
            for child in children:
                out, err = child.communicate(timeout=30)
                self.assertEqual(child.returncode, 0, out + err)
            saved = json.loads(record.read_text())
            self.assertEqual(saved['count'], 16)
            self.assertEqual(saved['unrelated'], {'original': True})
            self.assertEqual(git('rev-list', '--count', 'HEAD'), '17')
            self.assertEqual(git('status', '--porcelain'), '')
            self.assertEqual((repo / 'unrelated.txt').read_text(), 'preserve me')
            self.assertTrue((repo / '.git/studios-write.lock').is_file())

    def test_inventory_never_acquires_the_write_lock(self):
        engine = engines.Engine(background=False)
        self.assertIsInstance(engine.files, ProcessRLock)
        with mock.patch.object(engine.files, 'acquire', side_effect=AssertionError('write lock')), \
                mock.patch.object(gitstate, 'current', return_value=None):
            engine.saved_work()

    def test_existing_engine_follows_changed_workspace(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            for name in ('first', 'second'):
                repo = base / name
                (repo / '.git').mkdir(parents=True)
                space = gitstate.Workspace('Disposable Test', repo, 'items', 'main')
                if name == 'first':
                    engine = engines.Engine(background=False)
                with mock.patch.object(gitstate, 'current', return_value=space):
                    with engine.files:
                        self.assertTrue((repo / '.git/studios-write.lock').exists())

    def test_standalone_sync_waits_for_engine_transaction(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary).resolve()
            (repo / '.git').mkdir()
            entered, started = repo / 'entered', repo / 'started'
            code = r"""
import sys, subprocess
from pathlib import Path
from unittest import mock
import helpers, runner_support
from runner import gitstate
repo = Path(sys.argv[1])
space = gitstate.Workspace('Disposable Test', repo, 'items', 'main', 'fake-local-only')
def branch(_):
 (repo / 'entered').write_text('yes')
 return 'main'
(repo / 'started').write_text('yes')
with mock.patch.object(gitstate, 'on_branch', side_effect=branch), mock.patch.object(
 gitstate.hub, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'synthetic refusal')):
 gitstate.sync(space)
"""
            env = {**os.environ, 'HOME': str(repo / 'home'),
                   'PYTHONPATH': str(helpers.REPO / 'tests')}
            space = gitstate.Workspace('Disposable Test', repo, 'items', 'main')
            engine = engines.Engine(background=False)
            import time
            with mock.patch.object(gitstate, 'current', return_value=space):
                with engine.files:
                    child = subprocess.Popen([sys.executable, '-c', code, str(repo)], env=env,
                                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    try:
                        deadline = time.monotonic() + 5
                        while not started.exists() and time.monotonic() < deadline:
                            time.sleep(.01)
                        self.assertTrue(started.exists())
                        time.sleep(.15)
                        self.assertFalse(entered.exists(), 'sync read/mutation must wait for engine')
                    except BaseException:
                        child.kill()
                        child.communicate()
                        raise
                out, err = child.communicate(timeout=10)
                self.assertEqual(child.returncode, 0, out + err)
                self.assertTrue(entered.exists())

    def test_standalone_sync_refuses_worker_marker_before_any_git_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary).resolve()
            (repo / '.git').mkdir(exist_ok=True)
            space = gitstate.Workspace('Disposable Test', repo, 'items', 'main', 'fake-local-only')
            marker = space.root / 'one' / '.training-studio/step.lock'
            marker.parent.mkdir(parents=True)
            marker.write_text('canonical-worker')
            with mock.patch.object(gitstate.hub, 'run', side_effect=AssertionError('Git mutation')):
                report = gitstate.sync(space)
            self.assertFalse(report['shared'])
            self.assertIn('step', report['notice'])
            self.assertEqual(marker.read_text(), 'canonical-worker')

    def test_standalone_sync_rechecks_marker_after_fetch_before_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary).resolve()
            (repo / '.git').mkdir(exist_ok=True)
            space = gitstate.Workspace('Disposable Test', repo, 'items', 'main', 'fake-local-only')
            space.root.mkdir()
            marker = space.root / 'one' / '.training-studio/step.lock'
            def fetch(*args, **kwargs):
                marker.parent.mkdir(parents=True)
                marker.write_text('new worker')
                return subprocess.CompletedProcess([], 0, '', '')
            with mock.patch.object(gitstate, 'on_branch', return_value='main'), \
                    mock.patch.object(gitstate.hub, 'run', side_effect=fetch), \
                    mock.patch.object(gitstate, '_replay', side_effect=AssertionError('replay')):
                report = gitstate.sync(space)
            self.assertFalse(report['shared'])
            self.assertIn('step', report['notice'])

    def test_engine_reconciliation_defers_until_marker_is_released(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary).resolve()
            (repo / '.git').mkdir()
            space = gitstate.Workspace('Disposable Test', repo, 'items', 'main', 'fake-local-only')
            marker = repo / 'another-studio' / 'one' / 'work/step.lock'
            marker.parent.mkdir(parents=True)
            marker.write_text('worker')
            engine = engines.Engine(background=False)
            learned = mock.Mock()
            with mock.patch.object(gitstate, 'current', return_value=space):
                deferred = gitstate.sync(space, before=learned, held=engine.files)
                self.assertIn('Stop', deferred['notice'])
                learned.assert_not_called()
                marker.unlink()
                with mock.patch.object(gitstate, 'on_branch', return_value='main'), \
                        mock.patch.object(gitstate.hub, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')), \
                        mock.patch.object(gitstate, '_tip', return_value='upstream'), \
                        mock.patch.object(gitstate.hub, 'apart', return_value=(0, 1)), \
                        mock.patch.object(gitstate.hub, 'ahead', return_value=0), \
                        mock.patch.object(gitstate, '_replay', return_value=None) as replay:
                    resumed = gitstate.sync(space, before=learned, held=engine.files)
                self.assertTrue(resumed['shared'])
                learned.assert_called_once_with('upstream')
                replay.assert_called_once()

    def test_gitfile_worktree_uses_deck_lock_and_checks_copied_blog_status(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary).resolve()
            gitdir = repo / 'metadata'
            gitdir.mkdir()
            (repo / '.git').write_text('gitdir: metadata\n')
            space = gitstate.Workspace('Disposable Test', repo, 'items', 'main', 'fake-local-only')
            with mock.patch.object(gitstate, 'on_branch', return_value='main'), \
                    mock.patch.object(gitstate.hub, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'offline')), \
                    mock.patch.object(gitstate.hub, 'ahead', return_value=0):
                gitstate.sync(space)
            self.assertTrue((gitdir / 'studios-write.lock').exists())
            self.assertFalse((gitdir / 'blog-studio.lock').exists())
            record = repo / 'blogs/.blog-runs/one.json'
            record.parent.mkdir(parents=True)
            record.write_text('{"status":"working"}')
            with mock.patch.object(gitstate.hub, 'run', side_effect=AssertionError('Git mutation')):
                self.assertIn('step', gitstate.sync(space)['notice'])

class ChangedWorkspaceStartTests(runner_support.StudioCase):
    def test_creation_refuses_workspace_changed_during_lock_acquisition(self):
        from dataclasses import replace
        from workspace import WorkspaceError
        original = self.engine.space()
        before = {str(path.relative_to(original.root)): path.read_bytes()
                  for path in original.root.rglob('*') if path.is_file()}
        with mock.patch.object(gitstate, 'current', return_value=original) as configured:
            def path():
                configured.return_value = replace(original, folder='different-workspace')
                return gitstate.write_lock_path()
            self.engine.files = ProcessRLock(path)
            with mock.patch.object(self.engine, 'wake', side_effect=AssertionError('scheduled')):
                with self.assertRaisesRegex(WorkspaceError, 'workspace changed'):
                    self.start()
        after = {str(path.relative_to(original.root)): path.read_bytes()
                 for path in original.root.rglob('*') if path.is_file()}
        self.assertEqual(after, before)
        self.assertFalse((original.repo / 'different-workspace').exists())
