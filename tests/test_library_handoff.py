"""Continue in another studio: /api/open with a Document Library item, and the link it gives.

The studio link carries one more fragment parameter, `library=<id>@<revision>`, built on the
server from a checked id and revision; nothing else from the request reaches it, and
local_link's check of a studio's own announced link is as strict as before. Every test uses
disposable settings, data and library folders; no studio is started (the launcher's open is
replaced) and no provider job runs.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import urlsplit

import marketing_studio  # noqa: F401  puts the core on the import path
from marketing_studio import shared
from marketing_studio.errors import WorkspaceError
from marketing_studio.launcher import Launcher, library_item, local_link, with_library
from marketing_studio.page import Home
from studio_core import document_library

TOKEN = 'a' * 43
STUDIO_LINK = 'http://127.0.0.1:9123/#token=' + TOKEN


class HandoffCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        env = mock.patch.dict(os.environ, {
            'HOME': str(self.root / 'home'),
            'STUDIOS_CONFIG': str(self.root / 'shared.json'),
            'STUDIOS_LIBRARY': str(self.root / 'library'),
            'MARKETING_STUDIO_DATA': str(self.root / 'data'),
            **{key: str(self.root / key.lower()) for key in ('BLOG_STUDIO_DATA', 'TRAINING_STUDIO_DATA',
                                                              'PRESENTATION_STUDIO_DATA', 'INFOGRAPHIC_STUDIO_DATA')}})
        env.start()
        self.addCleanup(env.stop)
        self.launcher = Launcher()
        self.addCleanup(self.launcher.close)
        self.page = Home(8000, self.launcher)
        shared.update({'local': {'root': str(self.root / 'work')}})
        self.page.write('/api/setup', {'done': True})
        self.library = document_library.opened(create=True)
        self.doc = self.library.retain(key='blog:launch-1', studio='blog', kind='blog', title='Launch',
                                       text='# Launch\n\nSynthetic words.\n')

    def open(self, sent):
        with mock.patch.object(self.launcher, 'open', return_value=STUDIO_LINK) as started:
            try:
                return json.loads(self.page.write('/api/open', sent)[2])['link'], started
            except WorkspaceError:
                self.assertFalse(started.called, 'a refused item starts no studio')
                raise


class OpenWithLibraryTests(HandoffCase):
    def test_the_link_carries_the_item_and_keeps_the_token(self):
        link, started = self.open({'studio': 'presentation', 'library': {'id': self.doc['document'], 'revision': 1}})
        started.assert_called_once()
        self.assertEqual(started.call_args.args[0], 'presentation')
        parts = urlsplit(link)
        self.assertEqual((parts.scheme, parts.hostname, parts.port, parts.path, parts.query),
                         ('http', '127.0.0.1', 9123, '/', ''))
        self.assertEqual(parts.fragment, f'token={TOKEN}&library={self.doc["document"]}@1')
        # Today's shapes are unchanged.
        plain, _ = self.open({'studio': 'presentation'})
        self.assertEqual(plain, STUDIO_LINK)

    def test_ids_revisions_and_items_outside_the_library_are_refused(self):
        ident = self.doc['document']
        upload = self.library.add_upload('scan.pdf', b'%PDF-1.4 not really a pdf', operation='b' * 32)
        hidden = self.library.retain(key='blog:old-1', studio='blog', kind='blog', title='Old', text='# Old\n')
        self.library.hide(hidden['document'])
        refused = [
            {'id': ident},                                   # no revision
            {'id': ident, 'revision': '1'},
            {'id': ident, 'revision': True},
            {'id': ident, 'revision': 0},
            {'id': ident, 'revision': 1001},
            {'id': ident, 'revision': 1.0},
            {'id': ident, 'revision': 2},                     # not in the library
            {'id': ident.upper(), 'revision': 1},
            {'id': '../' + ident, 'revision': 1},
            {'id': ident + '&token=other', 'revision': 1},
            {'id': ident + '#x', 'revision': 1},
            {'id': 'a' * 65, 'revision': 1},
            {'id': 'missing-document', 'revision': 1},
            {'id': ident, 'revision': 1, 'home': 'http://elsewhere.invalid'},
            {'id': upload['id'], 'revision': 1},             # no readable text
            {'id': hidden['document'], 'revision': 1},       # removed from the library
            f'{ident}@1', [ident, 1], {},
        ]
        for item in refused:
            with self.subTest(item=item):
                with self.assertRaises(WorkspaceError):
                    self.open({'studio': 'training', 'library': item})
        with self.assertRaisesRegex(WorkspaceError, 'not both'):
            self.open({'studio': 'training', 'resume': 'outline', 'library': {'id': ident, 'revision': 1}})
        with self.assertRaises(WorkspaceError):
            self.open({'studio': 'elsewhere', 'library': {'id': ident, 'revision': 1}})

    def test_no_library_yet_is_said_plainly(self):
        os.environ['STUDIOS_LIBRARY'] = str(self.root / 'not-made')
        with self.assertRaisesRegex(WorkspaceError, 'has not been made'):
            self.open({'studio': 'training', 'library': {'id': self.doc['document'], 'revision': 1}})


class LinkTests(unittest.TestCase):
    def test_with_library_builds_the_parameter_itself_and_replaces_an_earlier_one(self):
        link = 'http://127.0.0.1:9123/#token=abc&home=x&library=old@3'
        self.assertEqual(urlsplit(with_library(link, 'launch-0a1b2c3d4e', 2)).fragment,
                         'token=abc&home=x&library=launch-0a1b2c3d4e@2')
        for ident, revision in (('x&token=y', 1), ('UPPER', 1), ('ok', '1'), ('ok', True), ('ok', 0)):
            with self.subTest(ident=ident, revision=revision), self.assertRaises(WorkspaceError):
                with_library(link, ident, revision)

    def test_a_studio_announced_link_is_checked_as_strictly_as_before(self):
        self.assertTrue(local_link(STUDIO_LINK))
        self.assertFalse(local_link(STUDIO_LINK + '&library=launch-1@1'))
        self.assertFalse(local_link('http://127.0.0.1:9123/#library=launch-1@1'))

    def test_library_item_checks_shape_before_reading_the_library(self):
        with mock.patch('studio_core.document_library.opened', side_effect=AssertionError('read')):
            for item in ({'id': 'x y', 'revision': 1}, {'id': 'ok', 'revision': -1}, 'ok@1'):
                with self.subTest(item=item), self.assertRaises(WorkspaceError):
                    library_item(item)


if __name__ == '__main__':
    unittest.main()
