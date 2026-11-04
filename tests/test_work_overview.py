"""Bounded saved metadata and direct-resume links do not launch or read content."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlsplit
import marketing_studio
from marketing_studio import work_overview
from studio_core import work_summary


class OverviewTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        patch=mock.patch.object(work_overview.workspaces,'remembered',return_value={'root':str(self.root)})
        patch.start();self.addCleanup(patch.stop)

    def item(self, ident, state='needs-you'):
        root=self.root/ident;root.mkdir()
        work_summary.save(root,'Synthetic '+ident,state,'Review the training outline')
        (root/'private-content.txt').write_text('Never read this content for the overview')
        return root

    def test_saved_decisions_progress_and_recent_rows_are_metadata_only(self):
        for ident,state in [('outline','needs-you'),('running','in-progress'),('done','recent')]:self.item(ident,state)
        rows=work_overview.listing('training')['items']
        self.assertEqual({row['state'] for row in rows},{'needs-you','in-progress','recent'})
        self.assertNotIn(str(self.root),json.dumps(rows))
        self.assertNotIn('Never read',json.dumps(rows))
        self.assertEqual({row['id'] for row in rows},{'outline','running','done'})

    def test_summary_work_directory_links_are_neither_read_nor_written(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'owned';root.mkdir()
            outside = Path(temporary) / 'outside';outside.mkdir()
            (root / 'work').symlink_to(outside, target_is_directory=True)
            work_summary.save(root, 'Synthetic title')
            self.assertEqual(list(outside.iterdir()), [])
            self.assertIsNone(work_summary.read(root))

    def test_resume_preserves_session_fragment_and_refuses_missing_or_escaping_work(self):
        self.item('outline')
        link=work_overview.link('training','outline','http://127.0.0.1:8000/#token=synthetic&home=local')
        self.assertEqual(parse_qs(urlsplit(link).fragment),{'token':['synthetic'],'home':['local'],'resume':['outline']})
        blog=work_overview.link('training','outline','http://127.0.0.1:8000/#opaque-blog-token&home=local')
        self.assertTrue(urlsplit(blog).fragment.startswith('opaque-blog-token&'))
        with self.assertRaises(ValueError):work_overview.check('unknown','outline')
        for ident in ['../escape','missing']:
            with self.assertRaises(ValueError):work_overview.check('training',ident)

    def test_large_workspace_is_capped_without_reading_whole_tree(self):
        for number in range(5000):(self.root/f'item-{number}').mkdir()
        with mock.patch.object(work_summary,'read',return_value=None) as read:
            shown=work_overview.listing('training')
        self.assertLessEqual(read.call_count,100)
        self.assertLessEqual(shown['folders_read'],100)
        self.assertTrue(shown['limited'])

    def test_missing_metadata_and_symlinks_are_honest_and_read_only(self):
        item=self.item('source');(self.root/'linked').symlink_to(item,target_is_directory=True)
        (item/work_summary.FILE).write_bytes(b'x'*13000)
        before=sorted(self.root.iterdir())
        self.assertEqual(work_overview.listing('training')['items'],[])
        self.assertEqual(sorted(self.root.iterdir()),before)
        with mock.patch.object(work_overview.workspaces,'remembered',return_value=None):
            with mock.patch.object(work_overview.workspaces,'data_root',return_value=self.root):
                (self.root/'workspace.json').write_text('{}')
                self.assertEqual(work_overview.listing('presentation')['state'],'unavailable')

    def test_old_pending_outline_is_projected_without_writes_or_content_walks(self):
        root=self.root/'older';(root/'.training-studio').mkdir(parents=True)
        record={'title':'Old synthetic training','outline_first':{'outline':{'sections':[]}},'training_plan':{'approved':None}}
        (root/'.training-studio/run.json').write_text(json.dumps(record))
        before=sorted(root.rglob('*'))
        row=work_overview.listing('training')['items'][0]
        self.assertEqual(row['action'],'Review the training outline')
        self.assertEqual(sorted(root.rglob('*')),before)
        self.assertFalse((root/work_summary.FILE).exists())
