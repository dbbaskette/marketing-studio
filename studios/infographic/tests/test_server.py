from email.message import Message
import hashlib
import http.client
import json
import threading

from helpers import Isolated
from graphics_fixtures import png
from runner import server
from runner.workspace import Store


class NativeServerTests(Isolated):
    def setUp(self):
        super().setUp()
        self.store = Store.setup(self.workspace)
        self.desk = server.desk(self.store)
        self.desk.start()
        self.addCleanup(self.desk.stop)

    def request(self, method, path, value=None, *, token=True, origin=True, host=None, raw=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.desk.port, timeout=5)
        self.addCleanup(connection.close)
        values = {'Host': host or f'127.0.0.1:{self.desk.port}'}
        if token:
            values['X-Infographic-Studio-Token'] = self.desk.token
        if origin:
            values['Origin'] = f'http://127.0.0.1:{self.desk.port}'
        if value is not None:
            raw = json.dumps(value)
            values['Content-Type'] = 'application/json'
        values.update(headers or {})
        connection.request(method, path, body=raw, headers=values)
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()

    def test_real_loopback_rejects_bad_host_missing_token_and_foreign_origin(self):
        self.assertEqual(self.request('GET', '/api/projects', token=False)[0], 403)
        self.assertEqual(self.request('GET', '/api/projects', host='example.invalid')[0], 403)
        self.assertEqual(self.request('POST', '/api/projects', {'title': 'Blocked'}, origin=False)[0], 403)
        self.assertEqual(self.request('POST', '/api/projects', {'title': 'Blocked'},
                                      headers={'Origin': 'https://example.invalid'})[0], 403)
        self.assertEqual(self.store.listing(), [])
        headers = Message()
        headers['Host'] = f'127.0.0.1:{self.desk.port}'
        headers['X-Infographic-Studio-Token'] = self.desk.token
        headers['X-Infographic-Studio-Token'] = self.desk.token
        with self.assertRaises(server.shared.Refusal):
            self.desk.page.answer('/api/projects', headers)

    def test_create_edit_and_conflict_are_bounded_and_authenticated(self):
        status, headers, raw = self.request('POST', '/api/projects', {'title': 'Synthetic draft'})
        self.assertEqual(status, 201)
        project = json.loads(raw)['project']
        sent = {'id': project['id'], 'expected_revision': 0,
                'brief': {**project['brief'], 'title': 'Edited draft'}}
        self.assertEqual(self.request('POST', '/api/project', sent)[0], 200)
        self.assertEqual(self.request('POST', '/api/project', sent)[0], 409)
        self.assertEqual(self.request('POST', '/api/projects', {'title': 'X' * 70_000})[0], 413)
        self.assertEqual(self.request('POST', '/api/projects', raw='not-json',
                                      headers={'Content-Type': 'application/json'})[0], 400)
        self.assertEqual(self.request('POST', '/api/projects', {'title': 'Test', 'approval': {}})[0], 409)
        self.assertEqual(self.request('GET', '/api/project?id=..%2Fprivate')[0], 409)
        self.assertEqual(self.request('GET', '/api/project?id=a&id=b')[0], 400)
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')

    def test_status_and_static_page_are_honest_and_contain_no_keys(self):
        status, headers, raw = self.request('GET', '/api/status')
        self.assertEqual(status, 200)
        value = json.loads(raw)
        self.assertFalse(value['generation_available'])
        self.assertEqual(value['providers'], 'not-checked')
        self.assertNotIn(self.desk.token.encode(), raw)
        status, _, raw = self.request('GET', '/', token=False)
        self.assertEqual(status, 200)
        self.assertIn(b'Infographic Studio', raw)
        self.assertNotIn(self.desk.token.encode(), raw)
        self.assertIn('Content-Security-Policy', headers)
        self.assertEqual(self.request('PUT', '/api/projects')[0], 405)

    def test_assets_require_the_page_key_and_owned_captured_bytes(self):
        project = self.store.create('Synthetic asset')
        raw = png()
        asset = {'id': 'a1', 'file': 'assets/marker.png', 'mime': 'image/png',
                 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw), 'width': 4, 'height': 4}
        project['assets'] = [asset]
        folder = self.store.root / 'projects' / project['id'] / 'assets'
        folder.mkdir()
        (folder / 'marker.png').write_bytes(raw)
        with self.store.locked():
            self.store._publish(project)
        path = f"/api/asset?id={project['id']}&asset=a1"
        self.assertEqual(self.request('GET', path, token=False)[0], 403)
        status, headers, returned = self.request('GET', path)
        self.assertEqual((status, headers['Content-Type'], returned), (200, 'image/png', raw))
        (folder / 'marker.png').unlink()
        (folder / 'marker.png').symlink_to(self.settings)
        self.assertEqual(self.request('GET', path)[0], 409)
