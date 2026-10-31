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
        # The phone is given the home without the private link; this computer's home has it.
        self.assertEqual(json.loads(body)['network'], {'address': self.link.split('#')[0]})
        with contextlib.closing(http.client.HTTPConnection('127.0.0.1', self.desk.port, timeout=3)) as direct:
            direct.request('GET', '/api/home', headers={server.TOKEN_HEADER: self.desk.token,
                                                         'Host': f'127.0.0.1:{self.desk.port}'})
            self.assertEqual(json.loads(direct.getresponse().read())['network']['url'], self.link)
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


ROOT = Path(__file__).resolve().parents[1]
# Reads one studio's own server class and prints the limit its body_limit gives every address
# it writes to, with the page key taken as sent. Nothing is started and no folder is read.
NATIVE_LIMITS = r'''
import importlib, json, sys
sys.path[:0] = [sys.argv[1], sys.argv[2]]
kind = getattr(importlib.import_module(sys.argv[3]), sys.argv[4])
page = object.__new__(kind)
page.check_token = lambda headers: None
print(json.dumps({path: page.body_limit(path, None) for path in sorted(set(kind.writes))}))
'''


class Upstream:
    """A synthetic loopback studio server: it answers every POST with the bytes it read,
    after `delay` seconds, and holds nothing else."""

    def __init__(self, delay=0.0):
        import http.server
        import threading
        import time

        class Answer(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                size = int(self.headers.get('Content-Length', '0'))
                read = len(self.rfile.read(size))
                time.sleep(delay)
                body = json.dumps({'read': read}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Answer)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, args=(0.05,), daemon=True)
        self.thread.start()
        self.target = f'127.0.0.1:{self.server.server_address[1]}'

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)


class BridgeLimitTests(unittest.TestCase):
    """The bridge lets each studio address carry what the studio's own server allows, and no
    more. A loopback bridge before a synthetic upstream; no studio, workspace or LAN port."""

    def bridge(self, identifier, upstream):
        token = 'synthetic-' + 'k' * 40
        bridge = network.BridgeServer(('127.0.0.1', 0), upstream.target, token,
                                      network.TOKEN_HEADERS[identifier], identifier)
        import threading
        thread = threading.Thread(target=bridge.serve_forever, args=(0.05,), daemon=True)
        thread.start()

        def stop():
            bridge.shutdown()
            bridge.server_close()
            thread.join(timeout=3)
        self.addCleanup(stop)
        return bridge, token

    def post(self, bridge, token, identifier, path, size, send=True, timeout=10):
        with contextlib.closing(http.client.HTTPConnection('127.0.0.1', bridge.server_port,
                                                           timeout=timeout)) as connection:
            connection.putrequest('POST', path, skip_host=True)
            for name, value in {'Host': bridge.authority, 'Origin': 'http://' + bridge.authority,
                                network.TOKEN_HEADERS[identifier]: token,
                                'Content-Type': 'application/json',
                                'Content-Length': str(size)}.items():
                connection.putheader(name, value)
            connection.endheaders()
            if send:
                # Sent in parts, as a browser would, so a large body stays cheap to make.
                part = b'x' * min(size, 1 << 20)
                left = size
                while left:
                    connection.send(part[:left])
                    left -= min(left, len(part))
            response = connection.getresponse()
            return response.status, json.loads(response.read() or b'{}')

    def test_every_bridge_limit_matches_the_studios_own(self):
        studios = {'training': ('studios/training', 'runner.page', 'RunnerPage'),
                   'presentation': ('studios/presentation', 'runner.page', 'RunnerPage'),
                   'infographic': ('studios/infographic', 'runner.server', 'Page')}
        import subprocess
        import sys
        with tempfile.TemporaryDirectory(prefix='marketing-limits-') as home:
            env = {**os.environ, 'HOME': home, 'STUDIOS_CONFIG': str(Path(home) / 'settings.json'),
                   'BROWSER': 'false'}
            for identifier, (folder, module, kind) in studios.items():
                with self.subTest(studio=identifier):
                    done = subprocess.run([sys.executable, '-I', '-c', NATIVE_LIMITS, str(ROOT / folder),
                                           str(ROOT / 'core'), module, kind], env=env, cwd=home,
                                          capture_output=True, text=True, timeout=60)
                    self.assertEqual(done.returncode, 0, done.stderr)
                    native = json.loads(done.stdout)
                    self.assertGreater(len(native), 5)
                    # Every address the studio writes to, and every one the bridge raises.
                    for path in sorted({*native, *network.BODY_LIMITS[identifier]}):
                        self.assertEqual(network.body_limit(identifier, path),
                                         native.get(path, network.SHARED_LIMIT), path)
        # Blog Studio's server takes MAX_BODY on every address, and its shared setup the usual limit.
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            '_blog_management_limits', ROOT / 'studios/blog/skills/blog-studio/scripts/management.py')
        source = spec.loader.get_source(spec.name)
        self.assertIn('MAX_BODY = 15 * 1024 * 1024\n', source)
        self.assertEqual(network.body_limit('blog', '/api/desk-save'), network.BLOG_LIMIT)
        self.assertEqual(network.body_limit('blog', '/onboarding/api/shared'), network.SHARED_LIMIT)
        # Marketing Studio's own: its Document Library upload, and the usual limit elsewhere.
        home = object.__new__(Home)
        for path in Home.writes:
            with self.subTest(path=path):
                self.assertEqual(network.body_limit('marketing', path), home.body_limit(path, None))

    def test_large_sources_saves_and_pictures_pass_and_larger_ones_are_refused_kindly(self):
        upstream = Upstream()
        self.addCleanup(upstream.close)
        for identifier, path, size in (('training', '/api/drafts/source', 5_000_000),
                                       ('training', '/api/drafts/save', 500_000),
                                       ('presentation', '/api/desk-source', 5_000_000),
                                       ('presentation', '/api/picture', 10_000_000)):
            with self.subTest(studio=identifier, path=path):
                bridge, token = self.bridge(identifier, upstream)
                self.assertEqual(self.post(bridge, token, identifier, path, size), (200, {'read': size}))
                limit = network.body_limit(identifier, path)
                status, answer = self.post(bridge, token, identifier, path, limit + 1, send=False)
                self.assertEqual(status, 413)
                self.assertIn('too large to send over the private network link', answer['error'])
                self.assertIn('Send something smaller, or do this on the computer.', answer['error'])
        # Said in file terms: a page sends a file base64-encoded, a third larger.
        self.assertIn('a file of at most about 48 KB', network.too_large(network.SHARED_LIMIT))
        self.assertIn('a file of at most about 21 MB', network.too_large(28_000_000))
        self.assertIn('a file of at most about 9 MB', network.too_large(12_000_000))
        self.assertIn('a file of at most about 750 KB', network.too_large(1_000_000))

    def test_blog_studios_long_routes_wait_as_long_as_their_google_and_link_work(self):
        upstream = Upstream(delay=0.4)
        self.addCleanup(upstream.close)
        bridge, token = self.bridge('blog', upstream)
        with mock.patch.object(network, 'UPSTREAM_TIMEOUT', 0.1), \
                mock.patch.object(network, 'BLOG_REMOTE_TIMEOUT', 5):
            for path in ('/api/desk-google-send', '/api/google-preview', '/api/library-add'):
                with self.subTest(path=path):
                    self.assertEqual(self.post(bridge, token, 'blog', path, 2), (200, {'read': 2}))
            status, answer = self.post(bridge, token, 'blog', '/api/desk-save', 2)
            self.assertEqual(status, 504)
            self.assertIn('No request was resubmitted', answer['error'])
        self.assertEqual(network.upstream_timeout('blog', 'POST', '/api/desk-google-send'), 600)
        self.assertEqual(network.upstream_timeout('blog', 'POST', '/api/library-add'), 600)
        self.assertEqual(network.upstream_timeout('blog', 'GET', '/api/desk-google-send'), 100)
        self.assertEqual(network.upstream_timeout('presentation', 'POST', '/api/library-add'), 100)


class OpenCallerTests(unittest.TestCase):
    """With phone access on, a studio opened on the computer keeps its loopback link and one
    opened from the phone gets its bridge. A disposable data root and settings, synthetic
    studio servers, and loopback bridges only."""

    def setUp(self):
        from marketing_studio import shared
        temporary = tempfile.TemporaryDirectory(prefix='marketing-open-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        patcher = mock.patch.dict(os.environ, {'MARKETING_STUDIO_DATA': str(self.root / 'data'),
                                               'STUDIOS_CONFIG': str(self.root / 'settings.json'),
                                               'BROWSER': 'false'})
        patcher.start()
        self.addCleanup(patcher.stop)
        shared.update({'local': {'root': str(self.root / 'work')}, 'assistant': {'agent': 'claude'},
                       'setup': {'version': 1}})
        with mock.patch.object(network, 'private_address', return_value='127.0.0.1'):
            self.lan = network.Network('synthetic-private-address')
        self.addCleanup(self.lan.close)
        self.launcher = Launcher(self.lan)
        self.addCleanup(self.launcher.close)
        self.desk = server.Desk(page=lambda port: Home(port, self.launcher))
        self.desk.start()
        self.addCleanup(self.desk.stop)
        self.home = urlsplit(self.lan.share('marketing', self.desk.url))
        # A running Blog Studio stand-in: a synthetic loopback server this launcher holds.
        self.studio = server.Desk()
        self.studio.start()
        self.addCleanup(self.studio.stop)
        process = mock.Mock()
        process.poll.return_value = None
        self.launcher.children['blog'] = (process, self.studio.url)
        self.addCleanup(self.launcher.children.clear)

    def open(self, host, port, authority):
        headers = {server.TOKEN_HEADER: self.desk.token, 'Origin': 'http://' + authority,
                   'Host': authority, 'Content-Type': 'application/json'}
        with contextlib.closing(http.client.HTTPConnection(host, port, timeout=5)) as connection:
            connection.request('POST', '/api/open', json.dumps({'studio': 'blog'}), headers)
            response = connection.getresponse()
            return response.status, json.loads(response.read())

    def test_the_computer_keeps_loopback_and_the_phone_gets_the_bridge(self):
        status, answer = self.open('127.0.0.1', self.desk.port, f'127.0.0.1:{self.desk.port}')
        self.assertEqual(status, 200, answer)
        self.assertEqual(answer['link'], self.studio.url)
        self.assertNotIn('blog', self.lan.bridges, 'the computer starts no bridge for a studio')
        status, answer = self.open(self.home.hostname, self.home.port, self.home.netloc)
        self.assertEqual(status, 200, answer)
        phone = urlsplit(answer['link'])
        self.assertIn('blog', self.lan.bridges, 'the phone starts the studio’s bridge')
        self.assertEqual(answer['link'], self.lan.bridges['blog'][3])
        self.assertEqual(phone.hostname, self.home.hostname)
        self.assertNotEqual(phone.port, self.studio.port)
        # The computer still gets loopback while the studio's bridge is up.
        status, answer = self.open('127.0.0.1', self.desk.port, f'127.0.0.1:{self.desk.port}')
        self.assertEqual(answer['link'], self.studio.url)

    def test_the_studios_way_back_accepts_both_homes(self):
        import shutil
        import subprocess
        if not shutil.which('node'):
            self.skipTest('needs Node.js')
        phone = self.open(self.home.hostname, self.home.port, self.home.netloc)[1]['link']
        computer = self.open('127.0.0.1', self.desk.port, f'127.0.0.1:{self.desk.port}')[1]['link']
        script = r'''const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const source = fs.readFileSync(process.argv[1], 'utf8');
const entry = /function suiteHome\(hash, here\) \{[\s\S]*?\n\}/.exec(source)[0];
for (const [home, link] of JSON.parse(process.argv[2])) {
  const here = new URL(link);
  const back = vm.runInNewContext(entry + '; suiteHome(hash, here);', {URLSearchParams, hash: '#home=' + encodeURIComponent(home), here});
  assert.equal(back, home, link + ' must offer the way back to ' + home);
}
'''
        pairs = [[f'http://127.0.0.1:{self.desk.port}', computer], [f'http://{self.home.netloc}', phone]]
        done = subprocess.run(['node', '-e', script,
                               str(ROOT / 'studios/blog/skills/blog-studio/assets/management/app.js'),
                               json.dumps(pairs)], text=True, capture_output=True, timeout=20)
        self.assertEqual(done.returncode, 0, done.stderr)


class NetworkCliTests(unittest.TestCase):
    def setUp(self):
        # `serve` cleans up studios an earlier session left running, from the data root's
        # records: a disposable root, so a real Marketing Studio's studios are never read or
        # stopped. The cleanup itself is a refusing stand-in as well.
        temporary = tempfile.TemporaryDirectory(prefix='marketing-network-cli-')
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        patcher = mock.patch.dict(os.environ, {'MARKETING_STUDIO_DATA': str(root / 'data'),
                                               'STUDIOS_CONFIG': str(root / 'settings.json'),
                                               'BROWSER': 'false'})
        patcher.start()
        self.addCleanup(patcher.stop)
        cleanup = mock.patch.object(Launcher, 'clean_orphans', return_value=[])
        cleanup.start()
        self.addCleanup(cleanup.stop)

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
