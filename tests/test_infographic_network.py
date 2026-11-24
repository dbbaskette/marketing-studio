"""Infographic document upload limits through the authenticated network bridge."""
import contextlib
import http.client
import json
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import secrets
import threading
import unittest
from unittest import mock
from marketing_studio import network
from marketing_studio.network import BridgeServer


class InfographicNetworkTests(unittest.TestCase):
    def test_long_waits_are_limited_to_the_native_infographic_operations(self):
        # Infographic Studio's long actions run in the background and answer at once, so its
        # actions take the ordinary limit; only a Google preview waits longer.
        self.assertFalse(hasattr(network, 'INFOGRAPHIC_ACTION_TIMEOUT'))
        self.assertEqual(network.upstream_timeout('infographic', 'POST', '/api/remote-preview'), 240)
        for studio, method, path in (
                ('infographic', 'POST', '/api/action'), ('infographic', 'POST', '/api/action-control'),
                ('marketing', 'POST', '/api/action'), ('blog', 'POST', '/api/action'),
                ('infographic', 'GET', '/api/action'), ('infographic', 'GET', '/api/desk'),
                ('infographic', 'POST', '/api/preferences'),
                ('infographic', 'POST', '/api/action/other')):
            with self.subTest(studio=studio, method=method, path=path):
                self.assertEqual(network.upstream_timeout(studio, method, path), 100)

    def test_slow_actions_finish_and_timeouts_do_not_resubmit_or_cancel_work(self):
        received = []
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()

        class Native(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                received.append(self.path)
                entered.set()
                release.wait(5)
                finished.set()
                try:
                    self.send_response(200)
                    self.send_header('Content-Length', '2')
                    self.end_headers()
                    self.wfile.write(b'{}')
                except OSError:
                    pass  # An expired bridge must not cancel the native operation.

            def log_message(self, *args):
                pass

        native = ThreadingHTTPServer(('127.0.0.1', 0), Native)
        bridge = BridgeServer(('127.0.0.1', 0), f'127.0.0.1:{native.server_port}',
                              'synthetic-key', 'X-Infographic-Studio-Token', 'infographic')
        for server in (native, bridge):
            threading.Thread(target=server.serve_forever, daemon=True).start()

        def request(path):
            with contextlib.closing(http.client.HTTPConnection('127.0.0.1', bridge.server_port, timeout=5)) as client:
                client.request('POST', path, body='{}', headers={
                    'Origin': 'http://' + bridge.authority,
                    'X-Infographic-Studio-Token': 'synthetic-key'})
                response = client.getresponse()
                return response.status, json.loads(response.read())

        try:
            # Ordinary requests expire first; the native Google preview must still
            # succeed after that threshold, through the real HTTP bridge.
            with mock.patch.object(network, 'UPSTREAM_TIMEOUT', .05), \
                    mock.patch.object(network, 'INFOGRAPHIC_REMOTE_TIMEOUT', 2):
                for path in ('/api/remote-preview',):
                    entered.clear(); release.clear(); finished.clear()
                    result = []
                    caller = threading.Thread(target=lambda: result.append(request(path)))
                    caller.start()
                    self.assertTrue(entered.wait(2))
                    self.assertFalse(finished.wait(.15))
                    self.assertTrue(caller.is_alive())
                    release.set()
                    caller.join(3)
                    self.assertEqual(result, [(200, {})])
                entered.clear(); release.clear(); finished.clear()
                status, body = request('/api/preferences')
                self.assertEqual(status, 504)
                self.assertIn('Work may still be running', body['error'])
                self.assertIn('No request was resubmitted', body['error'])
                self.assertNotIn('unavailable', body['error'])
                self.assertTrue(entered.is_set())
                self.assertFalse(finished.is_set())
                release.set()
                self.assertTrue(finished.wait(2))
                self.assertEqual(received, ['/api/remote-preview', '/api/preferences'])
        finally:
            release.set()
            bridge.shutdown(); bridge.server_close(); native.shutdown(); native.server_close()

    def test_the_page_local_mark_never_crosses_the_bridge(self):
        # Infographic Studio reads a folder path only for a request carrying its own local
        # mark, which the bridge never passes on: a phone cannot claim to be this computer.
        seen = []
        class Echo(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                seen.append(self.headers.get('X-Infographic-Studio-Local'))
                self.send_response(200); self.send_header('Content-Length', '2'); self.end_headers(); self.wfile.write(b'{}')
            def log_message(self, *args): pass
        native = ThreadingHTTPServer(('127.0.0.1', 0), Echo)
        threading.Thread(target=native.serve_forever, daemon=True).start()
        bridge = BridgeServer(('127.0.0.1', 0), f'127.0.0.1:{native.server_port}', 'synthetic-key',
                              'X-Infographic-Studio-Token', 'infographic')
        threading.Thread(target=bridge.serve_forever, daemon=True).start()
        try:
            with contextlib.closing(http.client.HTTPConnection('127.0.0.1', bridge.server_port, timeout=5)) as client:
                client.request('POST', '/api/source-folder', body='{}', headers={
                    'Origin': 'http://' + bridge.authority, 'Content-Type': 'application/json',
                    'X-Infographic-Studio-Token': 'synthetic-key', 'X-Infographic-Studio-Local': '1'})
                self.assertEqual(client.getresponse().status, 200)
            self.assertEqual(seen, [None])
        finally:
            bridge.shutdown(); bridge.server_close(); native.shutdown(); native.server_close()

    def test_document_routes_accept_bounded_uploads_without_widening_other_routes(self):
        received=[]
        class Echo(BaseHTTPRequestHandler):
            def do_POST(self):
                received.append((self.path,len(self.rfile.read(int(self.headers['Content-Length'])))))
                self.send_response(200);self.send_header('Content-Length','2');self.end_headers();self.wfile.write(b'{}')
            def log_message(self,*args):pass
        native=ThreadingHTTPServer(('127.0.0.1',0),Echo)
        thread=threading.Thread(target=native.serve_forever,daemon=True);thread.start()
        key=secrets.token_urlsafe(24)
        bridge=BridgeServer(('127.0.0.1',0),f'127.0.0.1:{native.server_port}',key,'X-Infographic-Studio-Token','infographic')
        threading.Thread(target=bridge.serve_forever,daemon=True).start()
        def request(path, size, *, upload=True, token=True):
            headers={'Origin':'http://'+bridge.authority,'Content-Type':'application/json',
                     'Content-Length': str(size)}
            if token:headers['X-Infographic-Studio-Token']=key
            with contextlib.closing(http.client.HTTPConnection('127.0.0.1',bridge.server_port,timeout=10)) as client:
                # A refusal is based on headers. Sending a large body at the same time can
                # race the server closing the socket before the client reads its response.
                client.request('POST', path, body=b' ' * size if upload else None, headers=headers)
                response = client.getresponse()
                response.read()
                return response.status
        try:
            for path in ('/api/source-preview','/api/action','/api/csv-preview','/api/csv-selection'):
                self.assertEqual(request(path,100_000),200)
            self.assertEqual(request('/api/preferences', 100_000, upload=False), 413)
            self.assertEqual(request('/api/source-preview', 100_000, upload=False, token=False), 403)
            self.assertEqual(request('/api/source-preview', 24_000_001, upload=False), 413)
            self.assertEqual(len(received),4)
        finally:
            bridge.shutdown();bridge.server_close();native.shutdown();native.server_close()
