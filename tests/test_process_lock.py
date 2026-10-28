"""Persistent workspace write locks, exercised by independent interpreters."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

import marketing_studio  # noqa: F401
from studio_core.process_lock import ProcessRLock, workspace_lock_path


class ProcessLockTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.path = self.root / 'private' / 'studios-write.lock'

    def child(self, code, *args):
        env = {**os.environ, 'HOME': str(self.root / 'home'),
               'STUDIOS_CONFIG': str(self.root / 'studios-config.json'), 'PYTHONPATH': str(Path(__file__).resolve().parents[1] / 'core')}
        return subprocess.run([sys.executable, '-c', code, *map(str, args)], env=env,
                              capture_output=True, text=True, timeout=10)

    def test_nested_and_exception_release_and_changed_path(self):
        current = [self.path]
        lock = ProcessRLock(lambda: current[0])
        self.assertFalse(lock._is_owned())
        with self.assertRaisesRegex(ValueError, 'test'):
            with lock:
                with lock:
                    self.assertTrue(lock._is_owned())
                self.assertTrue(lock._is_owned())
                raise ValueError('test')
        self.assertFalse(lock._is_owned())
        current[0] = self.root / 'other.lock'
        with lock:
            self.assertTrue(current[0].exists())
        with self.assertRaises(RuntimeError):
            lock.release()

    def test_other_process_refuses_then_acquires_and_other_workspace_is_independent(self):
        code = '''from pathlib import Path
import sys
from studio_core.process_lock import ProcessRLock
lock = ProcessRLock(lambda: Path(sys.argv[1]), timeout=0.15)
print(lock.acquire(timeout=0.15))
if lock._is_owned(): lock.release()
'''
        with ProcessRLock(lambda: self.path):
            blocked = self.child(code, self.path)
            self.assertEqual((blocked.returncode, blocked.stdout.strip()), (0, 'False'), blocked.stderr)
            independent = self.child(code, self.root / 'other.lock')
            self.assertEqual(independent.stdout.strip(), 'True', independent.stderr)
        released = self.child(code, self.path)
        self.assertEqual(released.stdout.strip(), 'True', released.stderr)
        self.assertTrue(self.path.exists(), 'never unlink a persistent lock inode')

    def test_processes_serialize_a_read_modify_write(self):
        count = self.root / 'count'
        count.write_text('0')
        code = '''from pathlib import Path
import sys, time
from studio_core.process_lock import ProcessRLock
lock = ProcessRLock(lambda: Path(sys.argv[1]))
count = Path(sys.argv[2])
for _ in range(15):
 with lock:
  before = int(count.read_text())
  time.sleep(.002)
  count.write_text(str(before + 1))
'''
        env = {**os.environ, 'HOME': str(self.root / 'home'),
               'STUDIOS_CONFIG': str(self.root / 'studios-config.json'), 'PYTHONPATH': str(Path(__file__).resolve().parents[1] / 'core')}
        children = [subprocess.Popen([sys.executable, '-c', code, str(self.path), str(count)],
                    env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
        for child in children:
            out, err = child.communicate(timeout=10)
            self.assertEqual(child.returncode, 0, out + err)
        self.assertEqual(count.read_text(), '30')

    def test_git_indirection_and_unconfigured_fallback(self):
        repo = self.root / 'repo'
        repo.mkdir()
        gitdir = self.root / 'metadata'
        gitdir.mkdir()
        (repo / '.git').write_text('gitdir: ../metadata\n')
        self.assertEqual(workspace_lock_path(repo, self.root / 'data'), gitdir / 'studios-write.lock')
        self.assertEqual(workspace_lock_path(None, self.root / 'data'), self.root / 'data/studios-write.lock')

    def test_thread_wait_is_bounded_and_failure_releases_the_thread_lock(self):
        lock = ProcessRLock(lambda: self.path)
        results = []
        with lock:
            thread = threading.Thread(target=lambda: results.append(lock.acquire(timeout=.05)))
            thread.start()
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
            self.assertEqual(results, [False])
        with lock:
            self.assertTrue(lock._is_owned())
        missing_repo = self.root / 'missing-repository'
        with self.assertRaises(FileNotFoundError):
            workspace_lock_path(missing_repo, self.root / 'data')
        self.assertFalse(missing_repo.exists(), 'locking must never initialize a repository')

    def test_process_exit_releases_persistent_lock(self):
        env = {**os.environ, 'HOME': str(self.root / 'home'),
               'PYTHONPATH': str(Path(__file__).resolve().parents[1] / 'core')}
        code = """from pathlib import Path
import sys, time
from studio_core.process_lock import ProcessRLock
with ProcessRLock(lambda: Path(sys.argv[1])):
 print('held', flush=True)
 time.sleep(10)
"""
        child = subprocess.Popen([sys.executable, '-c', code, str(self.path)], env=env,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(), 'held')
            inode = self.path.stat().st_ino
            child.terminate()
            child.communicate(timeout=5)
            with ProcessRLock(lambda: self.path, timeout=.2):
                self.assertEqual(self.path.stat().st_ino, inode)
        finally:
            if child.poll() is None:
                child.kill()
                child.communicate()

    def test_open_failure_does_not_leave_the_thread_lock_owned(self):
        self.path.parent.mkdir()
        self.path.symlink_to(self.root / 'elsewhere')
        lock = ProcessRLock(lambda: self.path)
        with self.assertRaises(OSError):
            lock.acquire()
        self.assertFalse(lock._is_owned())
        self.path.unlink()
        with lock:
            self.assertTrue(lock._is_owned())

    def test_path_changed_while_waiting_refuses_and_releases_the_old_scope(self):
        from studio_core.process_lock import LockPathChanged
        current = [self.path]
        started = threading.Event()
        def path():
            chosen = current[0]
            started.set()
            return chosen
        lock = ProcessRLock(path)
        errors = []
        def waiting():
            try:
                lock.acquire()
            except LockPathChanged as error:
                errors.append(str(error))
        with ProcessRLock(lambda: self.path):
            thread = threading.Thread(target=waiting)
            thread.start()
            self.assertTrue(started.wait(timeout=2))
            current[0] = self.root / 'changed.lock'
        thread.join(timeout=2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(errors), 1)
        with lock:
            self.assertTrue(current[0].exists())
        with ProcessRLock(lambda: self.path, timeout=.1):
            pass
