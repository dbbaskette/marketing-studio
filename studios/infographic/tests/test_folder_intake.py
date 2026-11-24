"""A folder on this computer, a Google Drive folder link and a spreadsheet in the primary picker."""
import base64
import http.client
import json
import sys
from unittest import mock

from helpers import Isolated, ROOT
from runner import folder_intake, server
from runner.workspace import Store

sys.path.insert(0, str(ROOT / 'tests'))
from xlsx_fixture import workbook   # noqa: E402


class FolderIntakeTests(Isolated):
    def setUp(self):
        super().setUp()
        self.store = Store.setup(self.workspace)
        self.desk = server.desk(self.store)
        self.desk.start()
        self.addCleanup(self.desk.stop)
        self.folder = self.temp / 'notes'
        (self.folder / 'Plans').mkdir(parents=True)
        (self.folder / 'Overview.md').write_text('# Overview\n\nOne instance restarts at a time.\n')
        (self.folder / 'Plans' / 'Steps.txt').write_text('Drain, restart, check, return.\n')
        (self.folder / 'figures.csv').write_text('a,b\n1,2\n')

    def request(self, path, value, *, local=True, via=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.desk.port, timeout=30)
        self.addCleanup(connection.close)
        headers = {'Host': f'127.0.0.1:{self.desk.port}', 'Origin': f'http://127.0.0.1:{self.desk.port}',
                   'X-Infographic-Studio-Token': self.desk.token, 'Content-Type': 'application/json'}
        if local:
            headers['X-Infographic-Studio-Local'] = '1'
        if via:
            headers['X-Marketing-Studio-Via'] = via
        connection.request('POST', path, body=json.dumps(value), headers=headers)
        response = connection.getresponse()
        return response.status, json.loads(response.read())

    def test_a_folder_on_this_computer_becomes_previews_to_review(self):
        status, found = self.request('/api/source-folder', {'folder': str(self.folder), 'taken': []})
        self.assertEqual(status, 200, found)
        self.assertEqual(sorted(p['name'] for p in found['previews']), ['Overview.md', 'Plans - Steps.txt'])
        self.assertTrue(all(p['readable'] for p in found['previews']))
        self.assertIn('figures.csv', [s['name'] for s in found['skipped']])
        self.assertTrue(found['said'])
        # Nothing was saved: a preview becomes a source only when the brief is saved.
        self.assertEqual(self.store.listing(), [])

    def test_a_folder_path_is_refused_to_a_caller_not_at_this_computer(self):
        for headers in ({'local': False}, {'local': True, 'via': 'network'}):
            with self.subTest(**headers):
                status, refused = self.request('/api/source-folder', {'folder': str(self.folder)}, **headers)
                self.assertEqual(status, 409)
                self.assertIn('only on this computer', refused['error'])

    def test_a_drive_folder_link_is_still_taken_from_afar(self):
        seen = []
        def take(given, **options):
            seen.append((given, options['local']))
            return {'uploads': {'Brief.md': b'# Brief\n\nSynthetic.\n'}, 'documents': [], 'skipped': [],
                    'said': 'Found 1 document.', 'next': None, 'report': {}}
        link = 'https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOp'
        with mock.patch.object(folder_intake.source_intake, 'take', side_effect=take):
            status, found = self.request('/api/source-folder', {'folder': link}, local=False)
        self.assertEqual(status, 200, found)
        self.assertEqual(seen, [(link, False)])
        self.assertEqual([p['name'] for p in found['previews']], ['Brief.md'])

    def test_a_spreadsheet_is_read_into_text_under_each_sheet(self):
        raw = workbook([('Budget', [['Item', 'Cost'], ['Servers', 12]]), ('Notes', [['Restart one at a time']])])
        status, preview = self.request('/api/source-preview', {'kind': 'xlsx', 'name': 'Plan.xlsx',
                                                                'data': base64.b64encode(raw).decode()}, local=False)
        self.assertEqual(status, 200, preview)
        self.assertEqual(preview['kind'], 'markdown')
        self.assertIn('Servers', preview['excerpt'])
        self.assertIn('Restart one at a time', preview['excerpt'])
