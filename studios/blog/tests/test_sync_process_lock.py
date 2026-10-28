"""Blog Studio and deck Studio synchronization share repository write exclusion."""
import isolation  # noqa: F401
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import studio
from studio_core.process_lock import ProcessRLock
from studio_sync import gitstate, support


class SyncProcessLockTests(unittest.TestCase):
    def test_existing_blog_repository_lock_excludes_deck_process_and_nests(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary).resolve()
            (repo / '.git').mkdir()
            ready, release = repo / 'ready', repo / 'release'
            code = '''from pathlib import Path
import sys, time
from studio_sync import support
repo = Path(sys.argv[1])
with support.locked(repo / '.git/blog-studio.lock'):
 with support.locked(repo / '.git/blog-studio.lock'):
  (repo / 'ready').touch()
  end = time.monotonic() + 5
  while not (repo / 'release').exists() and time.monotonic() < end:
   time.sleep(.01)
'''
            env = {**os.environ, 'PYTHONPATH': str(isolation.SCRIPTS),
                   'HOME': str(repo / 'home'), 'TMPDIR': str(repo)}
            child = subprocess.Popen([sys.executable, '-c', code, str(repo)], env=env,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                deadline = time.monotonic() + 5
                while not ready.exists() and time.monotonic() < deadline:
                    time.sleep(.01)
                self.assertTrue(ready.exists())
                deck = ProcessRLock(lambda: repo / '.git/studios-write.lock')
                self.assertFalse(deck.acquire(timeout=.1))
                release.touch()
                out, err = child.communicate(timeout=10)
                self.assertEqual(child.returncode, 0, out + err)
                with deck:
                    self.assertTrue(deck._is_owned())
            finally:
                if child.poll() is None:
                    child.kill()
                    child.communicate()

    def test_blog_sync_defers_for_deck_worker_then_reconciles_after_release(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary).resolve()
            (repo / '.git').mkdir()
            root = repo / 'blogs'
            root.mkdir()
            space = gitstate.Workspace('Disposable Test', repo, 'blogs', 'main', 'fake-local-only')
            marker = repo / 'presentations/one/work/step.lock'
            marker.parent.mkdir(parents=True)
            marker.write_text('active worker')
            learned = mock.Mock()
            # Existing callers already hold studio.locked: shared -> Blog -> workspace.
            with mock.patch('team_workspace.space', return_value=space):
                with studio.locked(root):
                    deferred = gitstate.sync(space, before=learned)
                    self.assertIn('Stop', deferred['notice'])
                    learned.assert_not_called()
                marker.unlink()
                with studio.locked(root), mock.patch.object(gitstate, 'on_branch', return_value='main'), \
                        mock.patch.object(gitstate.hub, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')), \
                        mock.patch.object(gitstate, '_tip', return_value='upstream'), \
                        mock.patch.object(gitstate.hub, 'apart', return_value=(0, 1)), \
                        mock.patch.object(gitstate.hub, 'ahead', return_value=0), \
                        mock.patch.object(gitstate, '_replay', return_value=None) as replay:
                    resumed = gitstate.sync(space, before=learned)
                self.assertTrue(resumed['shared'])
                learned.assert_called_once_with('upstream')
                replay.assert_called_once()

    def test_generic_blog_lock_does_not_create_a_shared_repository_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with support.locked(root / 'unrelated.lock'):
                self.assertFalse((root / 'studios-write.lock').exists())
