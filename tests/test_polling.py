import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from studio_core import polling


class PollingTests(unittest.TestCase):
    def test_metadata_detects_changes_without_opening_content_or_following_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); data=root/'private';data.mkdir();space=root/'workspace';space.mkdir()
            source=space/'words.md';source.write_text('first')
            engine=SimpleNamespace(workspace=SimpleNamespace(root=space),_lock=threading.RLock(),_runs={})
            with patch.dict('os.environ',{'STUDIOS_CONFIG':str(root/'settings.json')}):
                first=polling.snapshot(engine,data)
                with patch.object(Path,'read_text',side_effect=AssertionError('No content reads')):
                    self.assertEqual(polling.snapshot(engine,data),first)
                source.write_text('other')
                self.assertNotEqual(polling.snapshot(engine,data)['revision'],first['revision'])
                (space/'outside').symlink_to(root,target_is_directory=True)
                self.assertTrue(polling.snapshot(engine,data)['complete'])
                (root/'settings.json').write_text('{}')
                self.assertNotEqual(polling.snapshot(engine,data)['revision'],first['revision'])

    def test_active_or_incomplete_signals_require_authoritative_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);engine=SimpleNamespace(workspace=None,_lock=threading.RLock(),_runs={})
            self.assertFalse(polling.snapshot(engine,root)['active'])
            engine._runs['active']=SimpleNamespace(busy=True,workers={},thread=None)
            self.assertTrue(polling.snapshot(engine,root)['active'])
            one=polling.snapshot(engine,root,maximum=0);two=polling.snapshot(engine,root,maximum=0)
            self.assertFalse(one['complete']);self.assertNotEqual(one['revision'],two['revision'])

    def test_incremental_scan_reaches_stable_revision_and_detects_nonselected_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);space=root/'workspace';space.mkdir();data=root/'private';data.mkdir()
            for n in range(30):
                folder=space/f'project-{n}';folder.mkdir()
                for asset in range(10):(folder/f'asset-{asset}').write_text('synthetic')
            engine=SimpleNamespace(workspace=SimpleNamespace(root=space),_lock=threading.RLock(),_runs={})
            with patch.dict('os.environ',{'STUDIOS_CONFIG':str(root/'settings.json')}):
                def cycle():
                    for _ in range(20):
                        value=polling.snapshot(engine,data,maximum=40)
                        if value['complete']:return value
                    self.fail('Incremental traversal did not complete')
                first=cycle();pending=polling.snapshot(engine,data,maximum=40)
                self.assertFalse(pending['complete']);self.assertTrue(pending['cached'])
                self.assertEqual(pending['revision'],first['revision'])
                self.assertEqual(cycle()['revision'],first['revision'])
                for action in ('edit','add','delete'):
                    file=space/'project-29'/'asset-9'
                    if action=='edit':file.write_text('External correction')
                    elif action=='add':(space/'project-29'/'new').write_text('New')
                    else:file.unlink()
                    changed=cycle();self.assertNotEqual(changed['revision'],first['revision']);first=changed
                scan=engine._polling_scan
                scan.completed_at-=polling.CACHE_SECONDS+1
                expired=polling.snapshot(engine,data,maximum=1)
                self.assertFalse(expired['complete']);self.assertFalse(expired['cached'])
                with patch.object(Path,'lstat',side_effect=PermissionError('Unreadable')):
                    failed=polling.snapshot(engine,data,maximum=40)
                self.assertFalse(failed['cached']);self.assertIsNone(scan.revision)

    def test_time_exhaustion_resumes_and_depth_failure_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'file').write_text('Synthetic')
            engine=SimpleNamespace(workspace=None,_lock=threading.RLock(),_runs={})
            with patch.dict('os.environ',{'STUDIOS_CONFIG':str(root/'settings')}):
                with patch.object(polling.time,'monotonic',side_effect=[0,1]):
                    exhausted=polling.snapshot(engine,root,seconds=.1)
                self.assertFalse(exhausted['complete']);self.assertFalse(exhausted['cached'])
                self.assertTrue(polling.snapshot(engine,root)['complete'])
                with patch.object(polling,'MAX_DEPTH',0):
                    failed=polling.snapshot(engine,root)
                self.assertFalse(failed['complete']);self.assertFalse(failed['cached'])

    def test_both_native_clients_preserve_authoritative_catchup(self):
        import shutil
        import subprocess
        if not shutil.which('node'):
            self.skipTest('Node.js required for native client contract')
        done=subprocess.run(['node',str(Path(__file__).with_name('polling_client_check.js'))],
                            capture_output=True,text=True,timeout=30)
        self.assertEqual(done.returncode,0,done.stderr or done.stdout)

    def test_overlapping_roots_do_not_cancel_metadata_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);settings=root/'settings.json';settings.write_text('{}')
            engine=SimpleNamespace(workspace=SimpleNamespace(root=root),_lock=threading.RLock(),_runs={})
            with patch.dict('os.environ',{'STUDIOS_CONFIG':str(settings)}):
                first=polling.snapshot(engine,root)
                settings.write_text('[]')
                self.assertNotEqual(polling.snapshot(engine,root)['revision'],first['revision'])

    def test_concurrent_probes_share_one_serialized_scan(self):
        from concurrent.futures import ThreadPoolExecutor
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for number in range(40):(root/str(number)).write_text('Synthetic')
            engine=SimpleNamespace(workspace=None,_lock=threading.RLock(),_runs={})
            with patch.dict('os.environ',{'STUDIOS_CONFIG':str(root/'settings')}):
                with ThreadPoolExecutor(max_workers=4) as pool:
                    values=list(pool.map(lambda _:polling.snapshot(engine,root,maximum=8),range(30)))
                complete=[value['revision'] for value in values if value['complete']]
                self.assertGreater(len(complete),1)
                self.assertEqual(len(set(complete)),1)
                engine._polling_scan.close()
