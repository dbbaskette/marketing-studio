"""A fake published site on 127.0.0.1, for reading a post by its link with no real network.

Blog Studio's bounded fetcher (blog_library.fetch) only connects to public addresses over
HTTPS, pinning the address it resolved. A test runs a plain local HTTP server, then makes the
fetcher resolve every host to a documentation address and connect that pinned connection to
the local server instead: the request, status, headers, redirects, size and time limits all
go through the fetcher's own code against a real HTTP exchange.
"""

from contextlib import contextmanager
import http.client
import json
import re
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
from unittest.mock import patch

import blog_library

PUBLIC = [(2, 1, 6, '', ('192.0.2.10', 443))]  # TEST-NET-1, read as public by the patch below


class Site:
    """Pages by path: {path: (status, headers, body bytes)}; a path not listed is 404."""

    def __init__(self, pages=None):
        self.pages = dict(pages or {})
        self.requests = []
        self.accepts = {}  # path: the Accept header it was asked with
        site = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                site.requests.append((self.headers.get('Host'), self.path))
                site.accepts[self.path] = self.headers.get('Accept')
                status, headers, body = site.pages.get(
                    self.path, (404, {'Content-Type': 'text/plain'}, b'Not found')
                )
                self.send_response(status)
                for key, value in headers.items():
                    self.send_header(key, value)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        class Server(ThreadingHTTPServer):
            daemon_threads = True

            def handle_error(self, request, client_address):
                pass  # A client that stops reading a large page is expected here.

        self.server = Server(('127.0.0.1', 0), Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def page(self, path, body, kind='text/html; charset=utf-8', status=200, **headers):
        self.pages[path] = (
            status,
            {'Content-Type': kind, **headers},
            body if isinstance(body, bytes) else body.encode(),
        )

    @contextmanager
    def serving(self):
        """Serve, with the fetcher's pinned HTTPS connection sent to this local server."""
        port = self.port

        class Local(http.client.HTTPConnection):
            def __init__(self, hostname, address):
                super().__init__('127.0.0.1', port, timeout=15)
                self._host_header = hostname

            def connect(self):
                # Straight to the local server: getaddrinfo is the patched, public one.
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.settimeout(self.timeout)
                self.sock.connect(('127.0.0.1', port))

            def putrequest(self, method, url, **named):
                super().putrequest(method, url, skip_host=True, **named)
                self.putheader('Host', self._host_header)

        public = patch.object(blog_library.socket, 'getaddrinfo', return_value=PUBLIC)
        pinned = patch.object(blog_library, 'PinnedHTTPS', Local)
        global_address = patch.object(
            blog_library.ipaddress.IPv4Address, 'is_global', property(lambda self: True)
        )
        self.thread.start()
        with public, pinned, global_address:
            try:
                yield self
            finally:
                self.server.shutdown()
                self.server.server_close()


def modules(title, summary, sections, extra=None):
    """A response shaped like a headless CMS's: the post's title and summary, and its sections
    as a list of modules, each a plain heading and an HTML body, with a module that holds no
    text between them. Nothing on the page or in its scripts names these fields."""
    listed = [
        {'kind': 'section', 'heading': heading, 'body': ''.join(f'<p>{p}</p>' for p in body)}
        for heading, body in sections
    ]
    listed.insert(1, {'kind': 'image', 'src': '/img/diagram.png', 'alt': ''})
    post = {'title': title, 'summary': summary, 'modules': listed}
    return json.dumps({'post': post, **(extra or {})})


OUTLINE_LINE = re.compile(r'(?P<pointer>/\S*): (?P<kind>[a-z]+)')


class Assistant:
    """A stand-in assistant for a find-text job. `first` answers the page's evidence and
    `second` the second look at a response's outline: each a value, or a function of the
    payload. With no `second`, it reads the outline as a person would: the fields a list's
    items hold as strings, under the names given in `fields`."""

    def __init__(self, first, second=None, fields=None):
        self.first, self.second, self.payloads = first, second, []
        self.fields = fields or {'text': 'body', 'headings': 'heading', 'title': 'title'}

    def __call__(self, payload):
        self.payloads.append(payload)
        if payload['response_kind'] == 'content-address':
            answer = self.first
        else:
            answer = self.second or self.from_outline
        return answer(payload) if callable(answer) else answer

    def from_outline(self, payload):
        strings = [
            found['pointer']
            for found in map(OUTLINE_LINE.match, payload['outline'])
            if found and found['kind'] == 'string'
        ]
        listed = {re.sub(r'/\d+/', '/*/', p) for p in strings if re.search(r'/\d+/', p)}

        def named(field, among):
            return sorted(p for p in among if p.rsplit('/', 1)[1] == self.fields[field])

        title = [p for p in named('title', strings) if not re.search(r'/\d+/', p)]
        return {
            'found': True,
            'text': named('text', listed),
            'headings': named('headings', listed),
            'title': title[0] if title else '',
        }
