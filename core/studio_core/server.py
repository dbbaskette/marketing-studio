"""Shared loopback HTTP security and page server."""
from __future__ import annotations

import json
import os
import re
import secrets
import socketserver
import sys
import threading
import time
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from studio_core.modules import fresh_module

computer = globals().get("computer")
WorkspaceError = globals().get("WorkspaceError", ValueError)
PRODUCT = globals().get("PRODUCT", "Studio")

HOST = '127.0.0.1'
TOKEN_HEADER = globals().get('TOKEN_HEADER', 'X-Studio-Token')
PAGE_DIR = globals().get('PAGE_DIR')
PAGE = globals().get('PAGE', {})

JSON = 'application/json; charset=utf-8'
SECURITY_HEADERS = {
    'Content-Security-Policy': "default-src 'self'; img-src 'self' blob:",
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'Referrer-Policy': 'no-referrer',
    'Cache-Control': 'no-store',
}
# A page the studio's own page frames, such as a deck's wireframe draft: never able to run a
# script, reach the page's key or its API, or load anything, even from this origin.
FRAMED_HEADERS = {
    'Content-Security-Policy': "sandbox; default-src 'none'; style-src 'unsafe-inline'; "
                               "img-src data:; font-src data:; frame-ancestors 'self'",
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'SAMEORIGIN',
    'Referrer-Policy': 'no-referrer',
    'Cache-Control': 'no-store',
}
TICKET_SECONDS = 120     # how long a ticket for a framed page may be used
BODY_LIMIT = 64_000      # bytes a POST may carry
NOTE_LIMIT = 10_000      # characters in one text field
COMPUTER_CACHE = 60      # seconds a look at this computer is reused
READS = ('/api/computer',)
WRITES = ('/api/computer',)
NOT_A_PERSON = ('The link that opens the page carries its key, and the key is shown only to a '
                'person. To get the link, run this command in a terminal of your own.')
# Marketing Studio names the port of its home page when it starts a studio, so the studio's
# page can offer the way back however that page was reached.
SUITE_PORT = 'MARKETING_STUDIO_HOME_PORT'


def suite_port(environ=None) -> int | None:
    """The Marketing Studio home port this studio was started with, if it is a valid one."""
    value = (os.environ if environ is None else environ).get(SUITE_PORT, '')
    if not (isinstance(value, str) and value.isascii() and value.isdigit() and len(value) <= 5):
        return None
    port = int(value)
    return port if 0 < port < 65536 else None


def with_suite_port(page: bytes, port: int | None) -> bytes:
    """The HTML page with the Marketing Studio home port on its body, when there is one."""
    start = page.find(b'<body')
    if port is None or start < 0 or page[start + 5:start + 6] not in (b' ', b'>', b'\n', b'\t'):
        return page
    return page[:start + 5] + b' data-suite-port="%d"' % port + page[start + 5:]


class Refusal(Exception):
    """A request the page will not answer, with the HTTP status to refuse it with."""

    def __init__(self, status: int, message: str, allow: str | None = None):
        super().__init__(message)
        self.status = status
        self.allow = allow


def describe(failure: Exception) -> str:
    """An error as a sentence: a refusal's own, else its kind and what it said."""
    if isinstance(failure, (WorkspaceError, Refusal)):
        return str(failure)
    return f'{type(failure).__name__}: {failure}'


def as_json(status: int, value) -> tuple[int, str, bytes]:
    # "<" never leaves as itself, so no reader can take an answer for markup.
    text = json.dumps(value, sort_keys=True).replace('<', '\\u003c')
    return status, JSON, text.encode('utf-8')


def allowed(target: str, reads=READS, writes=WRITES) -> str:
    """The methods an address answers, for the `Allow` header of a refusal."""
    path = target.partition('?')[0]
    methods = [method for method, paths in (('GET', (*PAGE, *reads)), ('POST', writes))
               if path in paths]
    return ', '.join(methods) or 'GET'


def text(sent: dict, name: str, needed: bool = True) -> str | None:
    """One field of a change, which must be text of a sensible length."""
    value = sent.get(name)
    if value is None and not needed:
        return None
    if not isinstance(value, str) or (needed and not value) or len(value) > NOTE_LIMIT:
        raise Refusal(HTTPStatus.BAD_REQUEST, f'Give {name} as text.')
    return value


# --- the command's words ---------------------------------------------------------------

def interrupt(*_):
    raise KeyboardInterrupt


def port(text: str) -> int:
    number = int(text)
    if not 0 <= number <= 65535:
        raise ValueError(text)
    return number


def has_a_screen() -> bool:
    """Whether a browser with a window can be expected. A text browser is never started:
    it would take over the output the command is printing to."""
    return (sys.platform in ('darwin', 'win32')
            or any(os.environ.get(name) for name in ('BROWSER', 'DISPLAY', 'WAYLAND_DISPLAY')))


def show(url: str) -> bool:
    """Open the page in the default browser. False if there is none to open it in."""
    if not has_a_screen():
        return False
    try:
        return bool(webbrowser.open(url))
    except Exception:  # no browser after all: the person runs the command themselves
        return False


def announce(desk, to_a_person: bool, opener=show) -> dict:
    """What the command prints, once. A terminal is a person and is given the link, whole.

    Anything else, an assistant or a pipe, is given the address without its key. The page is
    then opened in the browser instead, so that only the person ever holds the key.
    """
    if to_a_person:
        return {'url': desk.url}
    return {'address': desk.address, 'opened': opener(desk.url), 'note': NOT_A_PERSON}


# --- the server ------------------------------------------------------------------------

class Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        """A reader that hangs up early gets no traceback: the command's output stays one line."""

    def server_bind(self):
        # The base class looks its own name up, which can ask the network. Nothing here does.
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]


class Handler(BaseHTTPRequestHandler):
    timeout = 30  # seconds a connection may sit idle before it is dropped

    def version_string(self):
        return PRODUCT.replace(' ', '')

    def respond(self, body: bytes | None = None):
        allow, extra = None, None
        try:
            reply = self.server.desk.answer(self.path, self.headers, self.command, body)
        except Refusal as refusal:
            reply, allow = as_json(refusal.status, {'error': str(refusal)}), refusal.allow
        except WorkspaceError as refusal:
            reply = as_json(HTTPStatus.CONFLICT, {'error': str(refusal)})
        except Exception as failure:  # answered like any other, never a dropped connection
            reply = as_json(HTTPStatus.INTERNAL_SERVER_ERROR, {'error': describe(failure)})
        if len(reply) == 4:
            *reply, extra = reply
        self.reply(*reply, allow=allow, extra=extra)

    def do_GET(self):
        self.respond()

    def do_POST(self):
        """Read the body, up to the limit, and hand it over. A body that is too long, or
        whose length is not stated, is never read: the request is refused and the line closed."""
        length = self.headers.get('Content-Length', '')
        limit = self.server.desk.page.body_limit(self.path, self.headers)
        if not length.isdigit() or int(length) > limit:
            self.close_connection = True
            return self.respond(None)
        self.respond(self.rfile.read(int(length)))

    def refuse_method(self):
        allow = self.server.desk.page.allowed(self.path)
        self.close_connection = True
        self.reply(*as_json(HTTPStatus.METHOD_NOT_ALLOWED,
                            {'error': 'The page reads with GET and sends a change with POST. '
                                      'Nothing else is answered.'}), allow=allow)

    do_HEAD = do_PUT = do_PATCH = do_DELETE = refuse_method
    do_OPTIONS = do_TRACE = do_CONNECT = refuse_method

    def reply(self, status: int, kind: str | None, body: bytes, allow: str | None = None,
              extra: dict | None = None):
        self._own = {name.lower() for name in (extra or {})}
        self.send_response(status)
        if kind:
            self.send_header('Content-Type', kind)
        if allow:
            self.send_header('Allow', allow)
        for name, value in (extra or {}).items():
            self.send_header(name, value)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def end_headers(self):
        """Every response leaves through here, so every response carries these, unless it
        set a stricter one of its own: a framed page has its own policy."""
        own = getattr(self, '_own', set())
        for name, value in SECURITY_HEADERS.items():
            if name.lower() not in own:
                self.send_header(name, value)
        self._own = set()
        super().end_headers()

    def send_error(self, code, message=None, explain=None):
        """The base class's own refusals, as JSON like the rest rather than as a page."""
        self.close_connection = True
        self.reply(*as_json(code, {'error': message or HTTPStatus(code).phrase}))

    def log_message(self, format, *args):
        """Nothing is logged: the command's output is one line, and stays one line."""


# What in a framed page could take the frame somewhere else: a link's address or target, a
# form's action, a base address, or a refresh. Each is taken out before the page is served.
LEAVING = (re.compile(rb'\s(?:href|xlink:href|target|action|formaction)\s*=\s*'
                      rb'(?:"[^"]*"|\'[^\']*\'|[^\s>]+)', re.I),
           re.compile(rb'<base\b[^>]*>', re.I),
           re.compile(rb'<meta\b[^>]*http-equiv\s*=\s*["\']?refresh[^>]*>', re.I))


def neutralised(body: bytes) -> bytes:
    """A page with nothing in it that could take its frame to another page when clicked."""
    for pattern in LEAVING:
        body = pattern.sub(b'', body)
    return body


def framed_html(body: bytes) -> tuple:
    """A page for a frame of the studio's own page: HTML with its links taken out, under
    FRAMED_HEADERS, which sandbox it as if it came from nowhere."""
    return HTTPStatus.OK, 'text/html; charset=utf-8', neutralised(body), dict(FRAMED_HEADERS)


class Page:
    """What the page may ask for and what it is refused. It holds the key; it has no socket.

    A program that serves the page with more behind it makes a subclass: it adds addresses
    to `reads` and `writes` and answers them in `read` and `write`. Every rule about who may
    ask stays here, in `answer` and `change`.
    """
    reads, writes = READS, WRITES
    # GET addresses a frame of the page opens. A frame cannot send the key, so it is opened
    # with a ticket the page was given for one thing, by a request that did send the key.
    framed: tuple = ()

    def __init__(self, port: int):
        self.token = secrets.token_urlsafe(32)
        self._tickets: dict = {}
        self._ticketing = threading.Lock()
        self.port = port
        self.hosts = {f'{name}:{port}' for name in (HOST, 'localhost')}
        self._looking = threading.Lock()
        self._looked: tuple[float, dict] | None = None

    def uses_google(self) -> bool:
        """Whether Google matters here, so that its command line is not optional. A deck is
        made in Google Slides unless chosen otherwise."""
        return True

    def computer(self, look: bool) -> dict | None:
        """The last look at this computer. `look` takes a new one unless one was just taken."""
        if look:
            with self._looking:
                seen = self._looked
                if not seen or time.monotonic() - seen[0] >= COMPUTER_CACHE:
                    self._looked = (time.monotonic(), computer.check(google=self.uses_google()))
        return self._looked[1] if self._looked else None

    def answer(self, target: str, headers, method: str = 'GET',
               body: bytes | None = None) -> tuple:
        """Answer one request, or raise the refusal."""
        hosts = headers.get_all('Host') or []
        if len(hosts) != 1 or hosts[0].strip().lower() not in self.hosts:
            raise Refusal(HTTPStatus.FORBIDDEN, 'The page answers only at its own local address.')
        try:
            url = urlsplit(target)
        except ValueError:
            raise Refusal(HTTPStatus.BAD_REQUEST, 'That address cannot be read.')
        if method == 'POST':
            return self.change(url, hosts[0].strip().lower(), headers, body)
        if method != 'GET':
            raise Refusal(HTTPStatus.METHOD_NOT_ALLOWED, 'Nothing else is answered.',
                          self.allowed(url.path))
        if url.path in PAGE:
            name, kind = PAGE[url.path]
            try:
                body = (PAGE_DIR / name).read_bytes()
            except OSError:
                raise Refusal(HTTPStatus.NOT_FOUND, 'Nothing is served here.')
            if kind.startswith('text/html'):
                body = with_suite_port(body, suite_port())
            return HTTPStatus.OK, kind, body
        if url.path == '/favicon.ico':
            return HTTPStatus.NO_CONTENT, None, b''
        if url.path in self.framed:
            query = parse_qs(url.query, keep_blank_values=True)
            given = query.get('ticket', [])
            if len(given) != 1 or not given[0]:
                raise Refusal(HTTPStatus.BAD_REQUEST, 'Give one ticket.')
            return self.read_framed(url.path, self.redeem(url.path, given[0]))
        if url.path not in self.reads:
            if url.path in self.writes:
                raise Refusal(HTTPStatus.METHOD_NOT_ALLOWED,
                              'This is sent with POST, from the page.', self.allowed(url.path))
            raise Refusal(HTTPStatus.NOT_FOUND, 'Nothing is served here.')
        self.check_token(headers)
        query = parse_qs(url.query, keep_blank_values=True)

        def one(name: str) -> str:
            values = query.get(name, [])
            if len(values) != 1 or not values[0]:
                raise Refusal(HTTPStatus.BAD_REQUEST, f'Give one {name}.')
            return values[0]

        return self.read(url.path, one)

    def allowed(self, target: str) -> str:
        return allowed(target, self.reads, self.writes)

    def body_limit(self, target: str, headers) -> int:
        """The most bytes a POST to this address may carry. A subclass may let one address
        of its own carry more; nothing else about a request depends on this."""
        return BODY_LIMIT

    def read(self, path: str, one) -> tuple:
        """Answer one GET that passed every rule. `one(name)` is a query value."""
        return as_json(HTTPStatus.OK, {'computer': self.computer(look=False)})

    def ticket(self, path: str, scope) -> str:
        """A ticket for a frame to open `path` with, for `scope` and nothing else, for
        TICKET_SECONDS. Issue it only to a request that sent the key."""
        if path not in self.framed:
            raise ValueError(f'{path} is not opened by a frame.')
        made = secrets.token_urlsafe(24)
        now = time.monotonic()
        with self._ticketing:
            self._tickets = {key: held for key, held in self._tickets.items()
                             if held[2] > now}
            self._tickets[made] = (path, scope, now + TICKET_SECONDS)
        return made

    def redeem(self, path: str, ticket: str):
        """What a ticket was issued for, while it holds and only for its own address. A
        dictionary lookup is safe here, though its timing is not constant: a ticket is 192
        random bits (token_urlsafe(24)) that open one page for two minutes, so how long a
        miss takes says nothing that narrows a guess."""
        with self._ticketing:
            held = self._tickets.get(ticket)
        if not held or held[0] != path or held[2] <= time.monotonic():
            raise Refusal(HTTPStatus.FORBIDDEN, 'That ticket is not good here, or not any '
                                                'more. Show it again from the page.')
        return held[1]

    def read_framed(self, path: str, scope) -> tuple:
        """Answer a framed GET whose ticket held. A subclass that frames anything answers
        it, with framed_html for a page."""
        raise Refusal(HTTPStatus.NOT_FOUND, 'Nothing is served here.')

    def check_token(self, headers) -> None:
        supplied = headers.get(TOKEN_HEADER, '')
        if not secrets.compare_digest(supplied.encode('utf-8'), self.token.encode('utf-8')):
            raise Refusal(HTTPStatus.FORBIDDEN, 'This needs the key from the link the page '
                                                'was opened with.')

    def change(self, url, host: str, headers, body: bytes | None) -> tuple:
        """Answer one POST, once it has passed every rule."""
        if url.path not in self.writes:
            raise Refusal(HTTPStatus.METHOD_NOT_ALLOWED, 'This is read with GET.',
                          self.allowed(url.path))
        self.check_token(headers)
        origins = headers.get_all('Origin') or []
        if len(origins) != 1 or origins[0].strip().lower() != f'http://{host}':
            raise Refusal(HTTPStatus.FORBIDDEN, 'A change is accepted only from the page itself.')
        if url.query:
            raise Refusal(HTTPStatus.BAD_REQUEST, 'Send what is to change in the body.')
        if headers.get_content_type() != 'application/json':
            raise Refusal(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, 'Send the change as JSON.')
        if body is None:
            limit = self.body_limit(url.path, headers)
            raise Refusal(HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                          f'A change is at most {limit:,} bytes, with its length stated.')
        try:
            sent = json.loads(body.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            sent = None
        if not isinstance(sent, dict):
            raise Refusal(HTTPStatus.BAD_REQUEST, 'Send the change as one JSON object.')
        return self.write(url.path, sent)

    def write(self, path: str, sent: dict) -> tuple:
        """Answer one POST that passed every rule. `sent` is its JSON object."""
        return as_json(HTTPStatus.OK, {'computer': self.computer(look=True)})


class Desk:
    """The page's server. `start` serves on a thread, `serve` blocks, `stop` ends either.

    `page` makes what answers: Page here, or a subclass of it given the port.
    """

    def __init__(self, port: int = 0, page=Page):
        self.server = Server((HOST, port), Handler)
        self.server.desk = self
        self.port = self.server.server_address[1]
        self.page = page(self.port)
        self.token, self.hosts, self.answer = self.page.token, self.page.hosts, self.page.answer
        self._thread: threading.Thread | None = None

    @property
    def address(self) -> str:
        """Where the page is, without its key."""
        return f'http://{HOST}:{self.port}/'

    @property
    def url(self) -> str:
        """The link for the person. The key rides in the fragment, which is never sent."""
        return f'{self.address}#token={self.token}'

    def serve(self) -> None:
        self.server.serve_forever()

    def start(self) -> None:
        self._thread = threading.Thread(target=self.server.serve_forever, args=(0.05,),
                                        daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._thread is not None:
            self.server.shutdown()
            self._thread.join()
            self._thread = None
        self.server.server_close()


# The deck panels every studio page shows, served from the shared core beside each page.
DECK_WEB = Path(__file__).resolve().parent / 'deck_web'
DECK_PAGES = {'/deck-panels.js': (str(DECK_WEB / 'deck-panels.js'),
                                  'text/javascript; charset=utf-8'),
              '/deck-panels.css': (str(DECK_WEB / 'deck-panels.css'), 'text/css; charset=utf-8')}


def for_product(name, product, token_header, page_dir, pages, computer, error,
                reads=READS, writes=WRITES):
    pages = {**DECK_PAGES, **pages}
    module = fresh_module(__file__, name, {'PRODUCT': product, 'TOKEN_HEADER': token_header,
        'PAGE_DIR': page_dir, 'PAGE': pages, 'computer': computer, 'WorkspaceError': error})
    module.READS, module.WRITES = tuple(reads), tuple(writes)
    module.Page.reads, module.Page.writes = tuple(reads), tuple(writes)
    module.allowed.__defaults__ = (tuple(reads), tuple(writes))
    return module
