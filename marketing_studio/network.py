"""Opt-in LAN bridges to fixed, authenticated loopback studio servers.

Each studio gets its own origin so existing assets, uploads, and session storage
work unchanged. This is not an arbitrary forward proxy. Native session keys and
all native authorization checks remain in force; no provider credentials live here.
"""
import http.client
import ipaddress
import json
import secrets
import socket
import socketserver
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from .errors import WorkspaceError
from .launcher import local_link

PRIVATE_NETWORKS = tuple(ipaddress.ip_network(value) for value in
                         ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))
TOKEN_HEADERS = {identifier: 'X-' + name + '-Studio-Token' for identifier, name in
                 (('marketing', 'Marketing'), ('blog', 'Blog'),
                  ('presentation', 'Presentation'), ('training', 'Training'), ('infographic', 'Infographic'))}
# Native upload handlers retain their smaller, per-route limits.
MAX_BODY = 120_000_000
STATIC = frozenset(('/', '/index.html', '/app.js', '/style.css', '/home.css',
                    '/blog.css', '/runner.js', '/desk.js', '/drafting.js', '/markdown.js',
                    '/deck.css', '/infographic.css', '/favicon.ico',
                    '/onboarding/', '/onboarding/app.js', '/onboarding/style.css',
                    '/onboarding/home.css', '/deck-panels.js', '/deck-panels.css',
                    '/lists.js', '/deck-desk.js', '/drafts.js'))
# GET addresses a studio's page opens in a frame, which cannot send the key: the studio
# server checks the one-page ticket in its address instead. Every other check still holds.
FRAMED = {'presentation': frozenset(('/api/deck-draft',)),
          'training': frozenset(('/api/deck-draft',))}


def private_address(value):
    try:
        address = ipaddress.IPv4Address(value)
        if any(address in network for network in PRIVATE_NETWORKS):
            return str(address)
    except ipaddress.AddressValueError:
        pass
    raise WorkspaceError('Choose this computer’s private IPv4 address (10.x, 172.16–31.x, or 192.168.x).')


def discover_address():
    """Ask the routing table for the outgoing interface; no packet is sent."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as route:
            route.connect(('192.0.2.1', 9))
            return private_address(route.getsockname()[0])
    except (OSError, WorkspaceError) as failure:
        raise WorkspaceError('A local network address could not be found. Use --lan with this computer’s private IPv4 address.') from failure


class BridgeServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 16

    def __init__(self, address, target, token, token_header, identifier='marketing'):
        self.identifier = identifier
        self.target = target
        self.token = token
        self.token_header = token_header
        self.slots = threading.BoundedSemaphore(24)
        super().__init__(address, BridgeHandler)
        self.authority = f'{address[0]}:{self.server_port}'

    def server_bind(self):
        # Avoid reverse DNS, and bind only the explicitly selected interface.
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()

    def handle_error(self, request, client_address):
        pass  # Never log headers, session keys, request bodies, or content.


class BridgeHandler(BaseHTTPRequestHandler):
    timeout = 30
    server_version = 'Marketing Studio'
    sys_version = ''

    def log_message(self, *args):
        pass

    def send_error(self, code, message=None, explain=None):
        self.close_connection = True
        body = json.dumps({'error': message or 'This network request could not be handled.'}).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'none'; frame-ancestors 'none'")
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def forward(self):
        own = self.server
        if self.headers.get_all('Host', []) != [own.authority]:
            return self.send_error(403, 'Open the private network link from Marketing Studio.')
        if self.command not in ('GET', 'POST'):
            return self.send_error(405, 'Use GET or POST.')
        try:
            url = urlsplit(self.path)
        except ValueError:
            return self.send_error(400, 'That address cannot be read.')
        if url.scheme or url.netloc or url.fragment or not self.path.startswith('/') or self.path.startswith('//'):
            return self.send_error(400, 'Use an address on this studio.')
        origins = self.headers.get_all('Origin', [])
        if origins and origins != ['http://' + own.authority]:
            return self.send_error(403, 'A request is accepted only from this studio.')
        if self.command == 'POST' and not origins:
            return self.send_error(403, 'A change is accepted only from this studio.')
        # Reject cross-site resource fetches even on browsers that omit Origin.
        site = self.headers.get('Sec-Fetch-Site', '')
        if site and site not in ('same-origin', 'none') and not (
                self.command == 'GET' and url.path == '/' and
                self.headers.get('Sec-Fetch-Mode') == 'navigate' and
                self.headers.get('Sec-Fetch-Dest') == 'document'):
            return self.send_error(403, 'Cross-site access is unavailable.')
        framed = self.command == 'GET' and url.path in FRAMED.get(own.identifier, ())
        if self.command == 'POST' or (url.path not in STATIC and not framed):
            tokens = self.headers.get_all(own.token_header, [])
            if len(tokens) != 1 or not secrets.compare_digest(tokens[0].encode(), own.token.encode()):
                return self.send_error(403, 'Reopen the private session link to connect.')
        lengths = self.headers.get_all('Content-Length', [])
        if self.headers.get_all('Transfer-Encoding') or len(lengths) > 1:
            return self.send_error(400, 'Use one bounded request body.')
        try:
            size = int(lengths[0]) if lengths else 0
        except ValueError:
            return self.send_error(400, 'Use one bounded request body.')
        limit = 64_000
        if own.identifier == 'blog' and not url.path.startswith('/onboarding/'):
            limit = 15 * 1024 * 1024
        elif own.identifier == 'presentation' and url.path == '/api/decks':
            limit = MAX_BODY
        elif own.identifier == 'infographic' and url.path in ('/api/source-preview','/api/action','/api/csv-preview','/api/csv-selection'):
            limit = 24_000_000
        elif own.identifier == 'training' and url.path in ('/api/documents', '/api/asset'):
            limit = 12_000_000
        if size < 0 or size > limit or (self.command == 'POST' and not lengths):
            return self.send_error(413, 'This request is too large or has no stated length.')
        if self.command == 'GET' and size:
            return self.send_error(400, 'A GET request has no body.')
        body = self.rfile.read(size) if size else None
        if size and len(body) != size:
            return self.send_error(400, 'The request body was incomplete.')
        # A strict allowlist prevents hop-by-hop, forwarding, or duplicate headers
        # from altering the loopback target or its native authorization boundary.
        headers = {}
        for name in ('Content-Type', own.token_header, 'Sec-Fetch-Site',
                     'Sec-Fetch-Mode', 'Sec-Fetch-Dest'):
            values = self.headers.get_all(name, [])
            if len(values) > 1:
                return self.send_error(400, 'Send each request header once.')
            if values:
                headers[name] = values[0]
        if origins:
            headers['Origin'] = 'http://' + own.target
        connection = http.client.HTTPConnection(own.target, timeout=100)
        begun = False
        try:
            connection.request(self.command, self.path, body=body, headers=headers)
            response = connection.getresponse()
            self.send_response(response.status)
            begun = True
            for name, value in response.getheaders():
                if name.lower() in ('content-type', 'content-length', 'content-disposition',
                                     'content-security-policy', 'x-content-type-options',
                                     'x-frame-options', 'referrer-policy', 'cross-origin-resource-policy', 'allow'):
                    self.send_header(name, value)
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            while chunk := response.read(64 * 1024):
                self.wfile.write(chunk)
        except (OSError, http.client.HTTPException):
            if not begun:
                self.send_error(502, 'The studio is unavailable. Open it again from Marketing Studio.')
        finally:
            connection.close()

    do_GET = do_POST = do_HEAD = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = do_TRACE = do_CONNECT = forward


class Network:
    """Own all network listeners for one explicit Marketing Studio session."""
    def __init__(self, host):
        self.host = private_address(host)
        self.lock = threading.RLock()
        self.bridges = {}
        self.closed = False

    def share(self, identifier, link, port=0):
        if identifier not in TOKEN_HEADERS or not local_link(link):
            raise WorkspaceError('Only a studio launched by Marketing Studio can be shared.')
        with self.lock:
            if self.closed:
                raise WorkspaceError('Local network access has stopped.')
            old = self.bridges.get(identifier)
            if old and old[0] == link:
                return old[3]
            if old:
                self._stop(old)
                del self.bridges[identifier]
            url = urlsplit(link)
            token = url.fragment.removeprefix('token=')
            bridge = BridgeServer((self.host, port), url.netloc, token, TOKEN_HEADERS[identifier], identifier)
            remote = f'http://{bridge.authority}/#{url.fragment}'
            thread = threading.Thread(target=bridge.serve_forever, args=(0.05,), daemon=True)
            thread.start()
            self.bridges[identifier] = (link, bridge, thread, remote)
            return remote

    def snapshot(self, private=True):
        with self.lock:
            home = self.bridges.get('marketing')
            if not home or self.closed:
                return None
            address = home[3].split('#')[0]
            return {'address': address, **({'url': home[3]} if private else {})}

    @staticmethod
    def _stop(bridge):
        _, server, thread, _ = bridge
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

    def close(self):
        with self.lock:
            self.closed = True
            bridges = list(self.bridges.values())
            self.bridges.clear()
        for bridge in bridges:
            self._stop(bridge)
