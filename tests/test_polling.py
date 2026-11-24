import os
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from studio_core import polling


def rested(engine):
    """As if the idle cooldown after the last completed walk had passed."""
    engine._polling_scan.completed_at-=polling.IDLE_SECONDS


class PollingTests(unittest.TestCase):
    def test_metadata_detects_changes_without_opening_content_or_following_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); data=root/'private';data.mkdir();space=root/'workspace';space.mkdir()
            source=space/'words.md';source.write_text('first')
            engine=SimpleNamespace(workspace=SimpleNamespace(root=space),_lock=threading.RLock(),_runs={})
            with patch.dict('os.environ',{'STUDIOS_CONFIG':str(root/'settings.json')}):
                first=polling.snapshot(engine,data)
                with patch.object(Path,'read_text',side_effect=AssertionError('No content reads')):
                    rested(engine)
                    self.assertEqual(polling.snapshot(engine,data),first)
                source.write_text('other')
                rested(engine)
                self.assertNotEqual(polling.snapshot(engine,data)['revision'],first['revision'])
                (space/'outside').symlink_to(root,target_is_directory=True)
                rested(engine)
                self.assertTrue(polling.snapshot(engine,data)['complete'])
                (root/'settings.json').write_text('{}')
                rested(engine)
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
            with patch.dict('os.environ',{'STUDIOS_CONFIG':str(root/'settings.json')}), \
                    patch.object(polling,'IDLE_SECONDS',0):
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
            with patch.dict('os.environ',{'STUDIOS_CONFIG':str(root/'settings')}), \
                    patch.object(polling,'IDLE_SECONDS',0):
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

    def test_pages_ask_nothing_while_hidden_and_keep_what_is_open(self):
        # Infographic Studio's research sheet and activity recovery, and Marketing Studio's
        # Brands working copy, over a disposable stand-in page.
        import shutil
        import subprocess
        if not shutil.which('node'):
            self.skipTest('Node.js required for the page polling check')
        done=subprocess.run(['node',str(Path(__file__).with_name('page_polling_check.js'))],
                            capture_output=True,text=True,timeout=30)
        self.assertEqual(done.returncode,0,done.stderr or done.stdout)

    def test_overlapping_roots_do_not_cancel_metadata_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);settings=root/'settings.json';settings.write_text('{}')
            engine=SimpleNamespace(workspace=SimpleNamespace(root=root),_lock=threading.RLock(),_runs={})
            with patch.dict('os.environ',{'STUDIOS_CONFIG':str(settings)}):
                first=polling.snapshot(engine,root)
                settings.write_text('[]')
                rested(engine)
                self.assertNotEqual(polling.snapshot(engine,root)['revision'],first['revision'])

    def test_concurrent_probes_share_one_serialized_scan(self):
        from concurrent.futures import ThreadPoolExecutor
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for number in range(40):(root/str(number)).write_text('Synthetic')
            engine=SimpleNamespace(workspace=None,_lock=threading.RLock(),_runs={})
            with patch.dict('os.environ',{'STUDIOS_CONFIG':str(root/'settings')}), \
                    patch.object(polling,'IDLE_SECONDS',0):
                with ThreadPoolExecutor(max_workers=4) as pool:
                    values=list(pool.map(lambda _:polling.snapshot(engine,root,maximum=8),range(30)))
                complete=[value['revision'] for value in values if value['complete']]
                self.assertGreater(len(complete),1)
                self.assertEqual(len(set(complete)),1)
                engine._polling_scan.close()


class RestingPollTests(unittest.TestCase):
    """Idle polls reuse a completed walk for a short cooldown; counted, never timed."""

    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.data=self.root/'private';self.data.mkdir()
        self.space=self.root/'workspace';self.space.mkdir()
        for number in range(5):(self.space/f'part-{number}').write_text('Synthetic')
        self.engine=SimpleNamespace(workspace=SimpleNamespace(root=self.space),_lock=threading.RLock(),_runs={})
        env=patch.dict('os.environ',{'STUDIOS_CONFIG':str(self.root/'settings.json')})
        env.start();self.addCleanup(env.stop)
        self.walks=0
        real=polling._walk
        def counted(roots):
            self.walks+=1
            return real(roots)
        walk=patch.object(polling,'_walk',side_effect=counted)
        walk.start();self.addCleanup(walk.stop)

    def poll(self):
        return polling.snapshot(self.engine,self.data)

    def test_an_idle_poll_within_the_cooldown_starts_no_walk(self):
        first=self.poll()
        self.assertTrue(first['complete']);self.assertEqual(self.walks,1)
        for _ in range(5):
            again=self.poll()
            self.assertEqual((again['revision'],again['complete'],again['cached']),(first['revision'],False,True))
        self.assertEqual(self.walks,1)
        rested(self.engine)
        self.assertTrue(self.poll()['complete']);self.assertEqual(self.walks,2)

    def test_children_are_read_from_the_listing_not_looked_up_again(self):
        looked=[]
        real=Path.lstat
        def lstat(path,*args,**kwargs):
            looked.append(str(path))
            return real(path,*args,**kwargs)
        with patch.object(Path,'lstat',lstat):
            self.assertTrue(self.poll()['complete'])
        # Only the three roots; every file and folder below comes from scandir's entry.
        self.assertEqual(sorted(looked),sorted([str(self.data),str(self.root/'settings.json'),str(self.space)]))

    def test_an_external_edit_shows_once_the_cooldown_has_passed(self):
        first=self.poll()
        (self.space/'part-0').write_text('Edited outside the studio')
        self.assertEqual(self.poll()['revision'],first['revision'])
        rested(self.engine)
        self.assertNotEqual(self.poll()['revision'],first['revision'])

    def test_a_server_write_is_seen_at_once(self):
        first=self.poll()
        (self.space/'part-1').write_text('Saved by the studio itself')
        polling.invalidate(self.engine)
        changed=self.poll()
        self.assertTrue(changed['complete']);self.assertNotEqual(changed['revision'],first['revision'])
        self.assertEqual(self.walks,2)

    def test_a_write_during_a_walk_keeps_the_next_poll_walking(self):
        polling.snapshot(self.engine,self.data,maximum=1)
        polling.invalidate(self.engine)   # written while the walk was half done
        while not polling.snapshot(self.engine,self.data,maximum=1)['complete']:pass
        walks=self.walks
        self.assertTrue(self.poll()['complete'])
        self.assertEqual(self.walks,walks+1)

    def test_working_jobs_always_walk_and_so_does_the_first_idle_poll_after(self):
        run=SimpleNamespace(busy=True,workers={},thread=None)
        self.engine._runs['training']=run
        for _ in range(3):
            self.assertTrue(self.poll()['active'])
        self.assertEqual(self.walks,3)
        run.busy=False
        (self.space/'part-2').write_text('The last thing the job wrote')
        idle=self.poll()
        self.assertTrue(idle['complete']);self.assertEqual(self.walks,4)
        self.assertTrue(self.poll()['cached']);self.assertEqual(self.walks,4)

    def test_a_replaced_scan_is_closed_before_it_is_dropped(self):
        held=[]
        real=os.scandir
        class Tracked:
            def __init__(self,path):
                self.inner=real(path);held.append(self)
            def __enter__(self):
                self.inner.__enter__();return self
            def __iter__(self):
                return iter(self.inner)
            def __exit__(self,*exc):
                held.remove(self);return self.inner.__exit__(*exc)
        with patch.object(polling.os,'scandir',Tracked):
            # The data folder, the settings file, the workspace, then into the workspace.
            partial=polling.snapshot(self.engine,self.data,maximum=4)
            self.assertFalse(partial['complete'])
            self.assertTrue(held,'The half-done walk holds a directory open')
            old=self.engine._polling_scan
            moved=self.root/'moved';moved.mkdir()
            self.engine.workspace=SimpleNamespace(root=moved)
            self.poll()
            self.assertIsNot(self.engine._polling_scan,old)
            self.assertIsNone(old.walk)
            self.assertEqual(held,[])
