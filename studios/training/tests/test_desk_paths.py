"""Paths the Training Studio desk offers, each working or saying why not (issues #253, #254).

A level's materials download as one ZIP with the index. Every training is disposable
(runner_support), every worker is scripted, and the Document Library is a disposable folder
(STUDIOS_LIBRARY). Nothing reaches Google, an assistant or the network.
"""
import io
import unittest
import zipfile
from urllib.parse import urlencode

import helpers  # noqa: F401  puts the runner on the import path
import desk
import workspace
from test_runner_deck import PageCase

from runner import pipeline


class LevelDownloadTests(PageCase):
    """Download level 101 (.zip): every material of the level, and the index once written."""

    def setUp(self):
        super().setUp()
        self.root = self.start(materials=['document', 'brief'], levels=['101', '201'])
        self.assertEqual(self.to_end(self.root), [])
        self.path = str(self.root)

    def bundle(self, level, path=None):
        target = '/api/download?' + urlencode({'path': path or self.path, 'bundle': 'level',
                                                'level': level})
        return self.page.answer(target, self.headers(), 'GET')

    def test_a_level_downloads_as_one_zip_named_by_its_level(self):
        before = workspace.person_statuses(self.root, workspace.load(self.root))
        commits = self.git('rev-list', '--count', 'HEAD')
        status, kind, data, headers = self.bundle('101')
        self.assertEqual((status, kind), (200, 'application/zip'))
        self.assertEqual(headers['Content-Disposition'],
                         f'attachment; filename="{self.root.name}-level-101-materials.zip"')
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = archive.namelist()
            guide = archive.read('101-learner-guide.md')
        self.assertEqual(sorted(names), ['101-brief.md', '101-learner-guide.md', '101-plan.md'])
        session = workspace.load(self.root)
        saved = workspace.artifact(self.root, session, 'document@101')['file']
        self.assertEqual(guide, (self.root / saved).read_bytes())
        # Once the index is written, it goes in too, named by the level like the rest.
        (self.root / pipeline.INDEX).write_text('# Rolling restarts\n', encoding='utf-8')
        with zipfile.ZipFile(io.BytesIO(self.bundle('201')[2])) as archive:
            self.assertEqual(sorted(archive.namelist()), ['201-brief.md', '201-index.md',
                                                          '201-learner-guide.md', '201-plan.md'])
            self.assertEqual(archive.read('201-index.md'), b'# Rolling restarts\n')
        self.assertTrue(self.get('drafts', path=self.path)['index_written'])
        # Downloading marks nothing ready and changes nothing.
        self.assertEqual(workspace.person_statuses(self.root, workspace.load(self.root)), before)
        self.assertEqual(self.git('rev-list', '--count', 'HEAD'), commits)

    def test_a_level_it_does_not_have_and_a_wrong_bundle_are_refused(self):
        with self.assertRaises(desk.Refusal) as refused:
            self.bundle('301')
        self.assertEqual(refused.exception.status, 404)
        target = '/api/download?' + urlencode({'path': self.path, 'bundle': 'all', 'level': '101'})
        with self.assertRaises(desk.Refusal) as refused:
            self.page.answer(target, self.headers(), 'GET')
        self.assertEqual(refused.exception.status, 400)
        target = '/api/download?' + urlencode({'path': self.path, 'bundle': 'level', 'level': '101'})
        with self.assertRaises(desk.Refusal) as refused:
            self.page.answer(target, self.headers(token=False), 'GET')
        self.assertEqual(refused.exception.status, 403)


if __name__ == '__main__':
    unittest.main()
