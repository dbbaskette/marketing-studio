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
