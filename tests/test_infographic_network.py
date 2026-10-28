"""Infographic document upload limits through the authenticated network bridge."""
import contextlib
import http.client
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import secrets
import threading
import unittest
from marketing_studio.network import BridgeServer


class InfographicNetworkTests(unittest.TestCase):
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
        def request(path,size,token=True):
            headers={'Origin':'http://'+bridge.authority,'Content-Type':'application/json'}
            if token:headers['X-Infographic-Studio-Token']=key
            with contextlib.closing(http.client.HTTPConnection('127.0.0.1',bridge.server_port,timeout=10)) as client:
                client.request('POST',path,body=b' '*size,headers=headers);response=client.getresponse();response.read();return response.status
        try:
            for path in ('/api/source-preview','/api/action','/api/csv-preview','/api/csv-selection'):
                self.assertEqual(request(path,100_000),200)
            self.assertEqual(request('/api/preferences',100_000),413)
            self.assertEqual(request('/api/source-preview',100_000,token=False),403)
            # Oversized headers are rejected before any upload is read or forwarded.
            with contextlib.closing(http.client.HTTPConnection('127.0.0.1',bridge.server_port,timeout=5)) as client:
                client.putrequest('POST','/api/source-preview');client.putheader('Origin','http://'+bridge.authority)
                client.putheader('X-Infographic-Studio-Token',key);client.putheader('Content-Length','24000001');client.endheaders()
                response=client.getresponse();self.assertEqual(response.status,413);response.read()
            self.assertEqual(len(received),4)
        finally:
            bridge.shutdown();bridge.server_close();native.shutdown();native.server_close()
