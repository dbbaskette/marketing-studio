"""Synthetic network boundary checks; never expose a real workspace or LAN port."""
import contextlib
import http.client
import io
import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest import mock
from urllib.parse import urlsplit

from marketing_studio import cli, network, server
from marketing_studio.errors import WorkspaceError
from marketing_studio.launcher import Launcher
from marketing_studio.page import Home


class NetworkTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='marketing-network-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        patcher = mock.patch.dict(os.environ, {'MARKETING_STUDIO_DATA': str(self.root / 'data'),
                                               'STUDIOS_CONFIG': str(self.root / 'settings.json')})
        patcher.start()
        self.addCleanup(patcher.stop)
        # Only tests substitute loopback, so no LAN listener contains real data.
        with mock.patch.object(network, 'private_address', return_value='127.0.0.1'):
            self.lan = network.Network('synthetic-private-address')
        self.launcher = Launcher(self.lan)
        self.addCleanup(self.launcher.close)
        self.desk = server.Desk(page=lambda port: Home(port, self.launcher))
        self.desk.start()
        self.addCleanup(self.desk.stop)
        self.link = self.lan.share('marketing', self.desk.url)
        self.addCleanup(self.lan.close)
        self.url = urlsplit(self.link)
        self.auth = {server.TOKEN_HEADER: self.desk.token, 'Origin': 'http://' + self.url.netloc,
                     'Content-Type': 'application/json'}

    def request(self, path='/api/home', method='GET', body=None, headers=None):
        with contextlib.closing(http.client.HTTPConnection(self.url.hostname, self.url.port, timeout=3)) as connection:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, response.headers, response.read()

    def test_home_link_stays_private_and_auth_survives_bridge(self):
        status, headers, body = self.request('/', headers={})
        self.assertEqual(status, 200)
        self.assertNotIn(self.desk.token.encode(), body)
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertEqual(headers['X-Frame-Options'], 'DENY')
        self.assertEqual(self.request()[0], 403)
        status, _, body = self.request(headers=self.auth)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['network']['url'], self.link)
        self.assertNotIn('url', self.lan.snapshot(private=False))
        self.assertNotIn(self.desk.token, json.dumps(self.lan.snapshot(private=False)))
        # Enabling network access does not relax the native loopback Host rules.
        with contextlib.closing(http.client.HTTPConnection('127.0.0.1', self.desk.port)) as direct:
            direct.request('GET', '/api/home', headers={**self.auth, 'Host': 'untrusted.example'})
            response = direct.getresponse()
            self.assertEqual(response.status, 403)
            response.read()

    def test_same_origin_write_reaches_native_settings_with_conflict_checks(self):
        change = {'changes': {'person': {'name': 'Synthetic Writer'}}, 'seen': {}}
        status, _, body = self.request('/api/shared', 'POST', json.dumps(change), self.auth)
        self.assertEqual(status, 200, body)
        self.assertEqual(json.loads(body)['shared']['person']['name'], 'Synthetic Writer')
        change['changes']['person']['name'] = 'Conflicting Writer'
        self.assertEqual(self.request('/api/shared', 'POST', json.dumps(change), self.auth)[0], 409)

    def test_host_origin_auth_and_cross_site_refusals(self):
        for update in ({'Host': 'evil.example'}, {'Origin': 'http://evil.example'},
                       {server.TOKEN_HEADER: 'wrong'}, {'Sec-Fetch-Site': 'cross-site'},
                       {'Sec-Fetch-Site': 'same-site'}):
            with self.subTest(update=update):
                self.assertEqual(self.request(headers={**self.auth, **update})[0], 403)
        missing = {key: value for key, value in self.auth.items() if key != 'Origin'}
        self.assertEqual(self.request('/api/shared', 'POST', '{}', missing)[0], 403)
        self.assertEqual(self.request('/', headers={'Sec-Fetch-Site': 'same-site',
                         'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Dest': 'document'})[0], 200)
        self.assertEqual(self.request('/app.js', headers={'Sec-Fetch-Site': 'cross-site'})[0], 403)

    def test_proxy_targets_methods_and_payload_bounds(self):
        for path, expected in (('http://evil.example/', 400), ('//evil.example/', 404),
                               ('/#token=private', 400)):
            # BaseHTTPRequestHandler normalizes a leading // to a single /.
            self.assertEqual(self.request(path, headers={**self.auth, 'Host': self.url.netloc})[0], expected)
        self.assertEqual(self.request('/', 'CONNECT', headers=self.auth)[0], 405)
        self.assertEqual(self.request('/api/shared', 'POST', 'x' * 64001, self.auth)[0], 413)
        self.assertEqual(self.request('/api/shared', 'POST', '{}',
                         {**self.auth, 'Transfer-Encoding': 'chunked'})[0], 400)
        self.assertEqual(self.request('/api/shared', 'POST', '{}',
                         {**self.auth, 'Content-Type': 'text/plain'})[0], 415)
        self.assertEqual(self.request('/../../etc/passwd', headers=self.auth)[0], 404)

    def test_duplicate_security_headers_are_refused(self):
        for name, value in (('Host', self.url.netloc), ('Origin', self.auth['Origin']),
                            (server.TOKEN_HEADER, self.desk.token), ('Content-Length', '2')):
            with self.subTest(name=name), contextlib.closing(http.client.HTTPConnection('127.0.0.1', self.url.port)) as connection:
                connection.putrequest('POST', '/api/shared', skip_host=True)
                for key, member in {**self.auth, 'Host': self.url.netloc, 'Content-Length': '2'}.items():
                    connection.putheader(key, member)
                connection.putheader(name, value)
                connection.endheaders(b'{}')
                response = connection.getresponse()
                self.assertIn(response.status, (400, 403))
                response.read()

    def test_only_validated_children_can_be_shared_and_links_are_reused(self):
        self.assertEqual(self.lan.share('marketing', self.desk.url), self.link)
        self.assertEqual(len(self.lan.bridges), 1)
        for link in ('http://evil.example/#' + 'a' * 40,
                     'http://127.0.0.1:9000/private#' + 'a' * 40):
            with self.assertRaises(WorkspaceError):
                self.lan.share('blog', link)
        with self.assertRaises(WorkspaceError):
            self.lan.share('unknown', self.desk.url)
        self.lan.close()
        self.assertIsNone(self.lan.snapshot())
        with self.assertRaises(OSError), socket.create_connection(('127.0.0.1', self.url.port), timeout=1):
            pass
        with self.assertRaises(WorkspaceError):
            self.lan.share('marketing', self.desk.url)

    def test_chosen_network_port_can_be_reused_after_shutdown(self):
        self.assertEqual(self.request('/', headers={})[0], 200)
        self.assertTrue(self.lan.bridges['marketing'][1].socket.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR))
        self.lan.close()
        with mock.patch.object(network, 'private_address', return_value='127.0.0.1'):
            replacement = network.Network('synthetic-private-address')
        self.addCleanup(replacement.close)
        renewed = replacement.share('marketing', self.desk.url, port=self.url.port)
        self.assertEqual(renewed, self.link)

    def test_child_relaunch_rotates_link_and_stops_prior_listener(self):
        second = server.Desk()
        second.start()
        self.addCleanup(second.stop)
        replacement = self.lan.share('marketing', second.url)
        self.assertNotEqual(replacement, self.link)
        with self.assertRaises(OSError), socket.create_connection(('127.0.0.1', self.url.port), timeout=1):
            pass
        self.assertEqual(self.lan.snapshot()['url'], replacement)

    def test_stopped_native_server_gives_safe_failure(self):
        self.desk.stop()
        status, _, body = self.request(headers=self.auth)
        self.assertEqual(status, 502)
        self.assertNotIn(self.desk.token.encode(), body)


class FramedDraftBridgeTests(unittest.TestCase):
    """A studio's deck panels and its framed draft page reach a phone through the bridge: the
    panels as the page's own files, the draft by its one-page ticket, which a frame sends in
    place of the key. Every other check still holds. A disposable data root and a synthetic
    studio server; no real workspace and no LAN address."""

    def setUp(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'core'))
        from studio_core import server as core
        temporary = tempfile.TemporaryDirectory(prefix='marketing-framed-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'index.html').write_text('<!doctype html><title>Probe</title>')
        patcher = mock.patch.dict(os.environ, {'MARKETING_STUDIO_DATA': str(self.root / 'data'),
                                               'STUDIOS_CONFIG': str(self.root / 'settings.json')})
        patcher.start()
        self.addCleanup(patcher.stop)
        module = core.for_product('_bridge_probe', 'Training Studio', 'X-Training-Studio-Token',
                                  self.root, {'/': ('index.html', 'text/html; charset=utf-8')},
                                  None, ValueError, reads=('/api/run',), writes=())

        class Probe(module.Page):
            framed = ('/api/deck-draft',)

            def read_framed(self, path, scope):
                return module.framed_html(b'<p>draft</p>')

        self.studio = module.Desk(page=Probe)
        self.studio.start()
        self.addCleanup(self.studio.stop)
        with mock.patch.object(network, 'private_address', return_value='127.0.0.1'):
            self.lan = network.Network('synthetic-private-address')
        self.addCleanup(self.lan.close)
        self.url = urlsplit(self.lan.share('training', self.studio.url))
        self.ticket = self.studio.page.ticket('/api/deck-draft', 'scope')

    def request(self, path, headers=None):
        with contextlib.closing(http.client.HTTPConnection(self.url.hostname, self.url.port,
                                                           timeout=3)) as connection:
            connection.request('GET', path, headers=headers or {})
            response = connection.getresponse()
            return response.status, response.headers, response.read()

    def test_the_panels_and_the_draft_reach_a_phone_without_the_key(self):
        for path in ('/deck-panels.js', '/deck-panels.css', '/lists.js'):
            with self.subTest(path=path):
                status, _, body = self.request(path)
                self.assertEqual(status, 200)
                self.assertTrue(body)
        status, headers, body = self.request(f'/api/deck-draft?ticket={self.ticket}',
                                             {'Sec-Fetch-Site': 'same-origin',
                                              'Sec-Fetch-Dest': 'iframe'})
        self.assertEqual((status, body), (200, b'<p>draft</p>'))
        self.assertTrue(headers['Content-Security-Policy'].startswith('sandbox;'))
        # The studio still checks the ticket, and the bridge every other rule.
        self.assertEqual(self.request('/api/deck-draft?ticket=made-up')[0], 403)
        self.assertEqual(self.request(f'/api/deck-draft?ticket={self.ticket}',
                                      {'Sec-Fetch-Site': 'cross-site'})[0], 403)
        self.assertEqual(self.request(f'/api/deck-draft?ticket={self.ticket}',
                                      {'Origin': 'http://evil.example'})[0], 403)
        self.assertEqual(self.request('/api/run')[0], 403, 'any other read still needs the key')


class NetworkCliTests(unittest.TestCase):
    def test_only_explicit_private_ipv4_interfaces_are_allowed(self):
        for value in ('10.0.0.2', '172.16.1.2', '172.31.255.1', '192.168.1.2'):
            self.assertEqual(network.private_address(value), value)
        for value in ('0.0.0.0', '127.0.0.1', 'localhost', 'example.com', '8.8.8.8',
                      '172.32.0.1', '169.254.1.2', '::', '::1', '100.64.0.1'):
            with self.subTest(value=value), self.assertRaises(WorkspaceError):
                network.private_address(value)

    def test_cli_network_mode_is_explicit_and_never_silently_reuses_local_server(self):
        self.assertIsNone(cli.parser().parse_args(['serve']).lan)
        self.assertEqual(cli.parser().parse_args(['serve', '--lan']).lan, 'auto')
        self.assertEqual(cli.parser().parse_args(['open', 'blog', '--lan', '192.168.1.2']).lan, '192.168.1.2')
        with mock.patch.object(cli, 'singleton', side_effect=WorkspaceError('Already running')), \
                mock.patch.object(cli.control, 'request') as reuse, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(['open', '--lan']), 2)
            reuse.assert_not_called()

    def test_cli_json_does_not_disclose_private_lan_link(self):
        lan = mock.Mock()
        lan.snapshot.return_value = {'address': 'http://192.168.1.2:9000/'}
        desk = mock.Mock(url='http://127.0.0.1:9000/#token=private', port=9000)
        desk.serve.side_effect = KeyboardInterrupt
        with mock.patch.object(cli, 'singleton'), mock.patch.object(cli.network, 'Network', return_value=lan), \
                mock.patch.object(cli.server, 'Desk', return_value=desk), mock.patch.object(cli.control, 'Control'), \
                mock.patch.object(cli.server, 'announce', return_value={'address': 'http://127.0.0.1:9000/'}), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cli.main(['serve', '--lan', '192.168.1.2', '--no-open', '--json']), 0)
        lan.snapshot.assert_called_once_with(private=False)
        self.assertNotIn('token', output.getvalue())
        lan.close.assert_called_once()
        desk.stop.assert_called_once()


if __name__ == '__main__':
    unittest.main()
