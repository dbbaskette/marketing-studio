"""Shared test-only contracts for both deck Studio engine locks."""
from contextlib import contextmanager, ExitStack
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest import mock

from studio_core.process_lock import ProcessRLock


class EngineProcessLockCases:
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
            record = root / self.record_path
            record.parent.mkdir(parents=True, exist_ok=True)
            record.write_text(json.dumps({'schema': 1, 'steps': {}, 'count': 0,
                                         'unrelated': {'original': True}}))
            (repo / 'items/hub.json').write_text(json.dumps({
                'schema': 1, 'tool': self.gitstate.TOOL, 'name': 'Disposable Test',
                'folder': 'items', 'branch': 'main', 'minimum_runtime': self.gitstate.installed()}))
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
                   'PYTHONPATH': str(self.helpers.REPO / 'tests')}
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
        engine = self.engines.Engine(background=False)
        self.assertIsInstance(engine.files, ProcessRLock)
        with mock.patch.object(engine.files, 'acquire', side_effect=AssertionError('write lock')), \
                mock.patch.object(self.gitstate, 'current', return_value=None):
            engine.saved_work()

    def test_existing_engine_follows_changed_workspace(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            for name in ('first', 'second'):
                repo = base / name
                (repo / '.git').mkdir(parents=True)
                space = self.gitstate.Workspace('Disposable Test', repo, 'items', 'main')
                if name == 'first':
                    engine = self.engines.Engine(background=False)
                with mock.patch.object(self.gitstate, 'current', return_value=space):
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
                   'PYTHONPATH': str(self.helpers.REPO / 'tests')}
            space = self.gitstate.Workspace('Disposable Test', repo, 'items', 'main')
            engine = self.engines.Engine(background=False)
            import time
            with mock.patch.object(self.gitstate, 'current', return_value=space):
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
            space = self.gitstate.Workspace('Disposable Test', repo, 'items', 'main', 'fake-local-only')
            marker = space.root / 'one' / self.marker_path
            marker.parent.mkdir(parents=True)
            marker.write_text('canonical-worker')
            with mock.patch.object(self.gitstate.hub, 'run', side_effect=AssertionError('Git mutation')):
                report = self.gitstate.sync(space)
            self.assertFalse(report['shared'])
            self.assertIn('step', report['notice'])
            self.assertEqual(marker.read_text(), 'canonical-worker')

    def test_standalone_sync_rechecks_marker_after_fetch_before_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary).resolve()
            (repo / '.git').mkdir(exist_ok=True)
            space = self.gitstate.Workspace('Disposable Test', repo, 'items', 'main', 'fake-local-only')
            space.root.mkdir()
            marker = space.root / 'one' / self.marker_path
            def fetch(*args, **kwargs):
                marker.parent.mkdir(parents=True)
                marker.write_text('new worker')
                return subprocess.CompletedProcess([], 0, '', '')
            with mock.patch.object(self.gitstate, 'on_branch', return_value='main'), \
                    mock.patch.object(self.gitstate.hub, 'run', side_effect=fetch), \
                    mock.patch.object(self.gitstate, '_replay', side_effect=AssertionError('replay')):
                report = self.gitstate.sync(space)
            self.assertFalse(report['shared'])
            self.assertIn('step', report['notice'])

    def test_engine_reconciliation_defers_until_marker_is_released(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary).resolve()
            (repo / '.git').mkdir()
            space = self.gitstate.Workspace('Disposable Test', repo, 'items', 'main', 'fake-local-only')
            marker = repo / 'another-studio' / 'one' / self.marker_path
            marker.parent.mkdir(parents=True)
            marker.write_text('worker')
            engine = self.engines.Engine(background=False)
            learned = mock.Mock()
            with mock.patch.object(self.gitstate, 'current', return_value=space):
                deferred = self.gitstate.sync(space, before=learned, held=engine.files)
                self.assertIn('Stop', deferred['notice'])
                learned.assert_not_called()
                marker.unlink()
                with mock.patch.object(self.gitstate, 'on_branch', return_value='main'), \
                        mock.patch.object(self.gitstate.hub, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')), \
                        mock.patch.object(self.gitstate, '_tip', return_value='upstream'), \
                        mock.patch.object(self.gitstate.hub, 'apart', return_value=(0, 1)), \
                        mock.patch.object(self.gitstate.hub, 'ahead', return_value=0), \
                        mock.patch.object(self.gitstate, '_replay', return_value=None) as replay:
                    resumed = self.gitstate.sync(space, before=learned, held=engine.files)
                self.assertTrue(resumed['shared'])
                learned.assert_called_once_with('upstream')
                replay.assert_called_once()

    def test_gitfile_worktree_uses_deck_lock_and_checks_copied_blog_status(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary).resolve()
            gitdir = repo / 'metadata'
            gitdir.mkdir()
            (repo / '.git').write_text('gitdir: metadata\n')
            space = self.gitstate.Workspace('Disposable Test', repo, 'items', 'main', 'fake-local-only')
            with mock.patch.object(self.gitstate, 'on_branch', return_value='main'), \
                    mock.patch.object(self.gitstate.hub, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'offline')), \
                    mock.patch.object(self.gitstate.hub, 'ahead', return_value=0):
                self.gitstate.sync(space)
            self.assertTrue((gitdir / 'studios-write.lock').exists())
            self.assertFalse((gitdir / 'blog-studio.lock').exists())
            record = repo / 'blogs/.blog-runs/one.json'
            record.parent.mkdir(parents=True)
            record.write_text('{"status":"working"}')
            with mock.patch.object(self.gitstate.hub, 'run', side_effect=AssertionError('Git mutation')):
                self.assertIn('step', self.gitstate.sync(space)['notice'])

    @contextmanager
    def _external_workspace_lock(self, repo):
        """An independent interpreter holds the real target scope, never a mock lock."""
        code = '''from pathlib import Path
import sys
from studio_core.process_lock import ProcessRLock
with ProcessRLock(lambda: Path(sys.argv[1]), timeout=.5):
 print('held', flush=True)
 sys.stdin.readline()
'''
        env = {**os.environ, 'HOME': str(repo / 'home'),
               'PYTHONPATH': str(self.helpers.REPO.parents[1] / 'core')}
        child = subprocess.Popen([sys.executable, '-c', code,
                                  str(repo / '.git/studios-write.lock')], env=env,
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(), 'held')
            yield
            out, err = child.communicate(input='release\n', timeout=5)
            self.assertEqual(child.returncode, 0, out + err)
        finally:
            if child.poll() is None:
                child.kill()
                child.communicate()

    def _changed_sync_scope(self, when, engine_entry):
        from workspace import WorkspaceError
        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            base = Path(temporary).resolve()
            repos = [base / name for name in ('a', 'b')]
            for repo in repos:
                (repo / '.git').mkdir(parents=True)
                (repo / 'original.txt').write_text('preserve ' + repo.name)
            spaces = [self.gitstate.Workspace('Disposable Test', repo, 'items', 'main',
                                             'fake-local-only') for repo in repos]
            configured = stack.enter_context(mock.patch.object(self.gitstate, 'current',
                                                                return_value=spaces[0]))
            engine = self.engines.Engine(background=False)
            def change():
                configured.return_value = spaces[1]
                stack.enter_context(self._external_workspace_lock(repos[0]))
                # Prove the target's actual OS lock is held by the other process.
                probe = ProcessRLock(lambda: repos[0] / '.git/studios-write.lock')
                self.assertFalse(probe.acquire(timeout=0))
            def fetch(*args, **kwargs):
                if when == 'fetch':
                    change()
                return subprocess.CompletedProcess([], 0, '', '')
            def replay(*args):
                (repos[0] / 'original.txt').write_text('wrong-scope replay')
            stack.enter_context(mock.patch.object(self.gitstate, 'on_branch', return_value='main'))
            stack.enter_context(mock.patch.object(self.gitstate.hub, 'run', side_effect=fetch))
            stack.enter_context(mock.patch.object(self.gitstate, '_tip', return_value='upstream'))
            stack.enter_context(mock.patch.object(self.gitstate.hub, 'apart', return_value=(0, 1)))
            stack.enter_context(mock.patch.object(self.gitstate.hub, 'ahead', return_value=0))
            replayed = stack.enter_context(mock.patch.object(self.gitstate, '_replay', side_effect=replay))
            learned = stack.enter_context(mock.patch.object(engine, '_learn'))
            settled = stack.enter_context(mock.patch.object(engine, '_clashed', side_effect=lambda *args:
                (repos[0] / 'original.txt').write_text('wrong-scope settlement')))
            if when == 'before':
                change()
            if engine_entry:
                report = engine._step(spaces[0], push=False)
                self.assertFalse(report['shared'])
                self.assertIn('workspace changed', report['notice'])
            else:
                with self.assertRaisesRegex(WorkspaceError, 'workspace changed'):
                    self.gitstate.sync(spaces[0], push=False, held=engine.files)
            replayed.assert_not_called()
            learned.assert_not_called()
            settled.assert_not_called()
            for repo in repos:
                self.assertEqual((repo / 'original.txt').read_text(), 'preserve ' + repo.name)

    def test_sync_refuses_changed_workspace_before_acquisition(self):
        for engine_entry in (False, True):
            with self.subTest(engine_entry=engine_entry):
                self._changed_sync_scope('before', engine_entry)

    def test_sync_refuses_changed_workspace_during_fetch(self):
        for engine_entry in (False, True):
            with self.subTest(engine_entry=engine_entry):
                self._changed_sync_scope('fetch', engine_entry)

    def test_post_sync_settlement_rechecks_the_configured_workspace(self):
        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            base = Path(temporary).resolve()
            repos = [base / name for name in ('a', 'b')]
            for repo in repos:
                (repo / '.git').mkdir(parents=True)
                (repo / 'original.txt').write_text('preserve ' + repo.name)
            spaces = [self.gitstate.Workspace('Disposable Test', repo, 'items', 'main',
                                             'fake-local-only') for repo in repos]
            configured = stack.enter_context(mock.patch.object(self.gitstate, 'current', return_value=spaces[0]))
            engine = self.engines.Engine(background=False)
            def synced(*args, **kwargs):
                configured.return_value = spaces[1]
                stack.enter_context(self._external_workspace_lock(repos[0]))
                return {'shared': True, 'reached': True, 'received': 0, 'conflict': [], 'notice': None}
            stack.enter_context(mock.patch.object(self.gitstate, 'sync', side_effect=synced))
            settled = stack.enter_context(mock.patch.object(engine, '_clashed', side_effect=lambda *args:
                (repos[0] / 'original.txt').write_text('wrong-scope settlement')))
            report = engine._step(spaces[0], push=False)
            self.assertFalse(report['shared'])
            self.assertIn('workspace changed', report['notice'])
            settled.assert_not_called()
            for repo in repos:
                self.assertEqual((repo / 'original.txt').read_text(), 'preserve ' + repo.name)


    def test_recovery_refuses_roots_enumerated_before_workspace_switch(self):
        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            base = Path(temporary).resolve()
            repos = [base / name for name in ('a', 'b')]
            for repo in repos:
                (repo / '.git').mkdir(parents=True)
            spaces = [self.gitstate.Workspace('Disposable Test', repo, 'items', 'main')
                      for repo in repos]
            root = spaces[0].root / 'one'
            marker = root / self.marker_path
            marker.parent.mkdir(parents=True)
            marker.write_text('interrupted original')
            (root / self.record_path).parent.mkdir(parents=True, exist_ok=True)
            (root / self.record_path).write_text('{"schema":1,"steps":{}}')
            configured = stack.enter_context(mock.patch.object(self.gitstate, 'current', return_value=spaces[0]))
            engine = self.engines.Engine(background=False)
            enumerate_roots = getattr(engine, self.enumeration_name)
            def enumerated():
                found = enumerate_roots()
                self.assertEqual(found, [root])
                configured.return_value = spaces[1]
                stack.enter_context(self._external_workspace_lock(repos[0]))
                return found
            stack.enter_context(mock.patch.object(engine, self.enumeration_name, side_effect=enumerated))
            loaded = stack.enter_context(mock.patch.object(engine, '_load', return_value={
                'schema': 1, 'steps': {}, 'halted': True, 'halt': True}))
            # If reached, the old implementation is allowed through to marker cleanup.
            team = __import__('runner', fromlist=['team']).team
            stack.enter_context(mock.patch.object(team, 'ours', return_value=True))
            if hasattr(engine, '_survey'):
                from types import SimpleNamespace
                stack.enter_context(mock.patch.object(engine, '_survey', return_value=SimpleNamespace(
                    next=SimpleNamespace(kind='done'))))
                stack.enter_context(mock.patch.object(engine, '_waited'))
            self.assertEqual(engine._tidy(), [])
            loaded.assert_not_called()
            self.assertEqual(marker.read_text(), 'interrupted original')
            probe = ProcessRLock(lambda: repos[0] / '.git/studios-write.lock')
            self.assertFalse(probe.acquire(timeout=0))

    def test_marker_publication_and_completion_refuse_another_workspace(self):
        from workspace import WorkspaceError
        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            base = Path(temporary).resolve()
            repos = [base / name for name in ('a', 'b')]
            for repo in repos:
                (repo / '.git').mkdir(parents=True)
            spaces = [self.gitstate.Workspace('Disposable Test', repo, 'items', 'main')
                      for repo in repos]
            root = spaces[0].root / 'one'
            marker = root / self.marker_path
            marker.parent.mkdir(parents=True)
            marker.write_text('original marker')
            stack.enter_context(mock.patch.object(self.gitstate, 'current', return_value=spaces[1]))
            engine = self.engines.Engine(background=False)
            engine._active_steps.add(str(root))
            engine._deferred_share = True
            with self._external_workspace_lock(repos[0]):
                for step in ('next step', None):
                    with self.subTest(step=step):
                        with self.assertRaises(WorkspaceError):
                            engine._step_marker(root, step)
                        self.assertEqual(marker.read_text(), 'original marker')
                        self.assertEqual(engine._active_steps, {str(root)})
                        self.assertTrue(engine._deferred_share)
                marker.unlink()  # test-owned setup, while the independent process still holds A
                with self.assertRaises(WorkspaceError):
                    engine._step_marker(root, 'new marker')
                self.assertFalse(marker.exists())


class ChangedWorkspaceStartCases:
    def test_creation_refuses_workspace_changed_during_lock_acquisition(self):
        from dataclasses import replace
        from workspace import WorkspaceError
        original = self.engine.space()
        before = {str(path.relative_to(original.root)): path.read_bytes()
                  for path in original.root.rglob('*') if path.is_file()}
        with mock.patch.object(self.gitstate, 'current', return_value=original) as configured:
            def path():
                configured.return_value = replace(original, folder='different-workspace')
                return self.gitstate.write_lock_path()
            self.engine.files = ProcessRLock(path)
            with mock.patch.object(self.engine, 'wake', side_effect=AssertionError('scheduled')):
                with self.assertRaisesRegex(WorkspaceError, 'workspace changed'):
                    self.start()
        after = {str(path.relative_to(original.root)): path.read_bytes()
                 for path in original.root.rglob('*') if path.is_file()}
        self.assertEqual(after, before)
        self.assertFalse((original.repo / 'different-workspace').exists())
