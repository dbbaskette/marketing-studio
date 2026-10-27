"""The parts of the runner's `worker_tools` both deck studios share. A studio binds them
into its own module with `studio_core.modules.bind`; they read that module's names.

The tools a worker calls stay in each studio: `tool` wraps each in a closure that bind
cannot rebuild, and so does `turn`, a context manager. So do the constants that hold
a module's functions (VALIDATORS, TOOLS), `Shown.__new__` and `command`, which starts
the studio's own file.
"""
from __future__ import annotations

import re
import urllib.request


SCHEMA = 1
PART = 20_000           # characters of an input in one read
WINDOW = 12_000         # characters of a source in one read
MAX_BYTES = 8_000_000   # the largest page or PDF that is kept
MAX_SOURCES = 30        # the most sources one job may save
MAX_HOPS = 5            # redirects followed for one page
TIMEOUT = 40            # seconds for one request
SUBMISSIONS = 6         # times one draft or finding may be handed back
QUOTE = (20, 900)       # the shortest and longest quote, in characters
SUMMARY = 1500
NOTES = 4000
QUESTION = 1000
PLAN_MOST = 8
PASSAGES = 20
ADDRESS = 2000
ICONS = 8               # the most icons one search returns
RENDER_WAIT = 900       # seconds a preview waits for its turn at the renderer
PNG = b'\x89PNG\r\n\x1a\n'
PICTURE = 12_000_000    # bytes: the largest picture that is shown
STATUSES = ('supported', 'contradicted', 'insufficient', 'unavailable')
SCOPES = ('public-web', 'supplied-only')
QUESTION_ID = re.compile(r'^[a-z0-9][a-z0-9-]{0,63}$')
NOT_A_QUERY = re.compile(r'https?://|[/\\@]')
CHARSET = re.compile(r'charset\s*=\s*["\']?([\w.:-]+)', re.IGNORECASE)
META_CHARSET = re.compile(rb'<meta[^>]+charset\s*=\s*["\']?([\w.:-]+)', re.IGNORECASE)
REDIRECTS = (301, 302, 303, 307, 308)
TEXT_TYPES = ('application/xhtml+xml', 'application/xml', 'application/json')
# What a saved source's original is, by its ending, as the checker is told it. The
# first are text, and are read as they are; a PDF or a Word file is not.
ORIGINAL_TEXT = {'.md': 'Markdown', '.txt': 'text', '.html': 'a web page',
                 '.htm': 'a web page', '.raw': 'text'}
ORIGINAL_FILES = {'.pdf': 'a PDF', '.docx': 'a Word document'}
# A person's browser sends these; some sites refuse a request without them.
HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 '
                   '(KHTML, like Gecko) Version/17.0 Safari/605.1.15'),
    'Accept': 'text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}
# Characters an agent may write one of in place of another when it copies a quote.
ALIKE = ("'‘’`", '"“”', '-‐‑–—')
ENDED = ('This job ended when you asked your question. Stop now: nothing more can be done '
         'until a person answers.')


def parts(text: str, size: int = PART) -> list[str]:
    """A long text in pieces of at most `size`, each ending at a line end where it can."""
    pieces, start = [], 0
    while len(text) - start > size:
        cut = text.rfind('\n', start + size // 2, start + size) + 1 or start + size
        pieces.append(text[start:cut])
        start = cut
    pieces.append(text[start:])
    return pieces


def tidy(text: str) -> str:
    """Text as it is kept: one space between words, no more than one blank line, and none
    of the characters that would shift where a quote is counted from."""
    text = text.replace('\x00', '').replace('﻿', '')
    lines = [' '.join(line.split()) for line in text.splitlines()]
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip() + '\n'


def word_text(data: bytes, ident: str) -> str:
    """The text of a Word file, read as a supplied document is read when it is added."""
    from runner import documents   # it reads Word files, and imports this module
    try:
        return documents._word(data)
    except Exception:   # whatever a Word file does to the reader, it is only not read
        raise Refusal(f'The original of {ident}, a Word document, could not be read. Say so '
                      'in your review.') from None


def flag(value) -> bool:
    """A yes or no an agent sent, which may have arrived as text."""
    if isinstance(value, str):
        return value.strip().lower() in ('true', 'yes', '1')
    return bool(value)


def whole(value, label: str) -> int:
    """A whole number an agent sent, which may have arrived as text."""
    try:
        return int(value)
    except (TypeError, ValueError):
        raise Refusal(f'{label} must be a whole number.')


def slug(text: str, length: int = 40) -> str:
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')[:length].strip('-') or 'x'


def clip(value, length: int = 200) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= length else text[:length] + '…'


def _loose(character: str) -> str:
    for group in ALIKE:
        if character in group:
            return '[' + re.escape(group) + ']'
    return re.escape(character)


def place(text: str, quote: str) -> tuple[int, str] | None:
    """Where a quote sits in a source, and the source's own wording of it.

    A quote that differs only in spacing, line breaks or the style of its quotation marks
    and dashes is found too, and the wording returned is the source's, character for
    character. None when the quote is not there.
    """
    at = text.find(quote)
    if at >= 0 and quote:
        return at, quote
    pattern = r'\s+'.join(''.join(map(_loose, word)) for word in quote.split())
    found = re.search(pattern, text) if pattern else None
    return (found.start(), found.group(0)) if found else None


def decode(data: bytes, content_type: str) -> str:
    """A page's bytes as text, in the encoding it declares, or UTF-8."""
    declared = CHARSET.search(content_type)
    name = declared.group(1) if declared else None
    if name is None:
        found = META_CHARSET.search(data[:4096])
        name = found.group(1).decode('ascii', 'replace') if found else 'utf-8'
    try:
        return data.decode(name, 'replace')
    except LookupError:
        return data.decode('utf-8', 'replace')


def page_text(data: bytes, content_type: str) -> tuple[str, str]:
    """The text and title of a fetched page that is not a PDF."""
    text = decode(data, content_type)
    kind = content_type.partition(';')[0].strip().lower()
    if kind == 'application/json' or (kind.startswith('text/') and kind != 'text/html'):
        return tidy(text), ''
    parser = _Page()
    parser.feed(text)
    parser.close()
    return tidy(''.join(parser.parts)), ' '.join(parser.title.split())


def pdf_text(path: Path) -> str | None:
    """The text of a PDF, read with pdftotext. None when pdftotext is not installed."""
    program = shutil.which('pdftotext')
    if program is None:
        return None
    try:
        done = subprocess.run([program, '-layout', str(path), '-'], capture_output=True,
                              stdin=subprocess.DEVNULL, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        raise Refusal('That PDF could not be read. It was not saved.')
    if done.returncode != 0:
        raise Refusal('That PDF could not be read. It was not saved.')
    return done.stdout.decode('utf-8', 'replace')


def public(address: str) -> bool:
    """True for an address on the public internet: not private, loopback, link-local,
    shared, reserved or unspecified, in either address family."""
    try:
        found = ipaddress.ip_address(address.partition('%')[0])
    except ValueError:
        return False
    return (getattr(found, 'ipv4_mapped', None) or found).is_global


def resolve(host: str) -> list[str]:
    """Every address a host name has."""
    found = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return list(dict.fromkeys(info[4][0] for info in found))


def _pinned(address: str) -> list:
    """Handlers that connect to one address, already checked, whatever the name resolves to
    by the time the connection is made."""
    context = ssl.create_default_context()
    context.set_alpn_protocols(['http/1.1'])

    class Plain(http.client.HTTPConnection):
        def connect(self):
            self.sock = socket.create_connection((address, self.port), self.timeout)

    class Secure(http.client.HTTPSConnection):
        def connect(self):
            plain = socket.create_connection((address, self.port), self.timeout)
            self.sock = context.wrap_socket(plain, server_hostname=self.host)

    class Http(urllib.request.HTTPHandler):
        def http_open(self, request):
            return self.do_open(Plain, request)

    class Https(urllib.request.HTTPSHandler):
        def https_open(self, request):
            return self.do_open(Secure, request)

    return [Http(), Https()]


def fetch_once(url: str, address: str, limit: int) -> tuple[int, dict, bytes]:
    """Ask for one address once, following nothing: (status, headers, at most limit + 1
    bytes of body). Connects to `address`, which the caller has checked, unless this
    computer reaches the web through a proxy, which then makes the connection itself."""
    target = urllib.parse.urlsplit(url)
    proxied = (target.scheme in urllib.request.getproxies()
               and not urllib.request.proxy_bypass(target.hostname))
    opener = urllib.request.build_opener(_NoRedirect(), *([] if proxied else _pinned(address)))
    try:
        reply = opener.open(urllib.request.Request(url, headers=HEADERS), timeout=TIMEOUT)
    except urllib.error.HTTPError as answered:
        reply = answered
    with reply:
        headers = {name.lower(): value for name, value in reply.headers.items()}
        return reply.code, headers, reply.read(limit + 1)


def unpacked(data: bytes, encoding: str) -> bytes:
    """A body as sent, or unpacked when the site compressed it without being asked to."""
    if encoding.strip().lower() in ('', 'identity'):
        return data
    try:
        return zlib.decompressobj(47).decompress(data, MAX_BYTES + 1)
    except zlib.error:
        raise Refusal('The site sent that page in a form that could not be read. It was '
                      'not saved.')


def _question(item, scope, problems: list[str]):
    """One question as harness-research takes it. Problems it would refuse are added."""
    if not isinstance(item, dict):
        return item
    query = item.get('public_query') if scope == 'public-web' else None
    label = item.get('id') or 'a question'
    if query is not None and (not isinstance(query, str) or not query.strip()
                              or len(query) > 500 or NOT_A_QUERY.search(query)):
        problems.append(f'{label}: "public_query" is a few public search words, at most 500 '
                        'characters, with no address, path or email address in it.')
    if isinstance(item.get('question'), str) and len(item['question']) > 4000:
        problems.append(f'{label}: the question is too long; ask one thing.')
    return {'id': item.get('id'), 'question': item.get('question'), 'public_query': query,
            'claim': None}


def held(outcomes: list[dict]) -> list[str]:
    """What the checks hold against a draft: the problems of each one that failed. A check
    that could not run holds nothing against it."""
    return [problem for outcome in outcomes if outcome['status'] == 'failed'
            for problem in outcome['problems']]


def as_json(value, what: str) -> tuple[object, str]:
    """Something a worker sent as JSON, and as the text it is kept as. An agent may send
    the text or the object itself."""
    if isinstance(value, (dict, list)):
        given = value
    elif not isinstance(value, str) or not value.strip():
        raise Refusal(f'Send the whole {what} as JSON text.')
    else:
        try:
            given = json.loads(value)
        except ValueError as failure:
            raise Refusal(f'The {what} is not valid JSON ({failure}).')
    return given, json.dumps(given, indent=2, ensure_ascii=False) + '\n'


def said_no(refusal: WorkspaceError) -> list[str]:
    """The lines the slides tool or the brand skill gave when it said no. Anything else,
    such as a tool that is not on this computer, is not the worker's to fix: it is raised."""
    lines = getattr(refusal, 'problems', None)
    if not isinstance(lines, list):
        raise refusal
    return [str(line) for line in lines] or [str(refusal)]


def _draft(scratch: Path, name: str, text: str) -> Path:
    """Keep one draft where the slides tool can read it, under a name of its own."""
    path = scratch / f'{name}-{secrets.token_hex(4)}.json'
    _write(path, text)
    return path


DRAWN = ('outline', 'section')      # the kinds whose check asks the slides tool
EXTENSIONS = {'research-json': '.json', 'research-plan': '.json', 'outline': '.json', 'section': '.json'}


def picture(path: Path) -> bytes:
    """A picture as it is shown: a PNG of a sensible size, and nothing else."""
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > PICTURE:
        raise Refusal('That picture cannot be shown.')
    data = path.read_bytes()
    if not data.startswith(PNG):
        raise Refusal('That picture cannot be shown.')
    return data


def one_at_a_time(lock: Path, wait: float = RENDER_WAIT):
    """Hold a computer's one turn at the renderer: `turn` with one slot."""
    return turn(lock, 1, wait)


def turn_file(how: dict, slides) -> Path:
    """The file a render's turns are taken from: `how['lock']` for LibreOffice and an unpooled
    Drive, and one beside it for the Google preview pool, so that neither waits on the
    other's turns."""
    lock = Path(how['lock'])
    return lock.with_name(lock.stem + '-google' + lock.suffix) if slots(how, slides) > 1 \
        else lock


def slots(how: dict, slides) -> int:
    """The turns a render may take side by side on this computer: the slides tool's Google
    preview pool for a render through Google Drive on a tool that has one, else one."""
    from runner import slides as slides_tool
    pooled = how.get('renderer') == 'drive' and getattr(slides, 'has', lambda name: False)(
        'google-preview-pool')
    return slides_tool.pool_size() if pooled else 1


def pictures(found: dict, folder: Path, target: Path) -> list[dict]:
    """Keep the pictures of one preview under `target`, one a slide, named by its number.
    Only a PNG the renderer wrote inside `folder` is taken. Returns each slide as
    {'number', 'id', 'title', 'findings'}."""
    folder, kept = Path(folder).resolve(), []
    shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True)
    for slide in found.get('slides') or ():
        image = Path(str(slide.get('image'))).resolve()
        if folder not in image.parents or type(slide.get('number')) is not int:
            raise WorkspaceError('The renderer named a picture outside its own folder, so '
                                 'the preview was not kept.')
        (target / f"{slide['number']}.png").write_bytes(picture(image))
        kept.append({'number': slide['number'], 'id': str(slide.get('id')),
                     'title': str(slide.get('title') or ''),
                     'findings': [finding for finding in slide.get('findings') or ()
                                  if isinstance(finding, dict)]})
    return kept


def the_slides(runtime: str | None = None):
    """The slides tool on this computer. Imported here, so a job with no deck never
    loads it."""
    from runner import slides
    return slides.Slides(runtime=runtime) if runtime else slides.Slides()


def the_brand(runtime: str | None = None):
    """The brand skill on this computer."""
    from runner import brand
    return brand.Brand(runtime=runtime) if runtime else brand.Brand()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode('utf-8'))


def _offered(folder: Path, number: int, source: dict) -> dict:
    """Keep a document the runner offers, and describe it as a saved source."""
    missing = [key for key in ('title', 'origin', 'text', 'file') if not source.get(key)]
    if missing:
        raise WorkspaceError('An offered source needs: ' + ', '.join(missing) + '.')
    text, local = tidy(source['text']), f'sources/offered-{number}.txt'
    original = source.get('original') if source.get('original_path') else None
    if original:
        target = folder / original
        if Path(original).is_absolute() or '..' in Path(original).parts:
            raise WorkspaceError('A supplied original must stay inside the job folder.')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(Path(source['original_path']).read_bytes())

    _write(folder / local, text)
    return {'id': f's{number}', 'url': source['origin'], 'title': source['title'],
            'chars': len(text), 'file': source['file'], 'local': local, 'original': original,
            'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(), 'offered': True,
            **({'permission': source['permission']} if source.get('permission') else {}),
            'supplied': source.get('supplied')}


def _job(folder: Path) -> dict:
    job = home.read_json(Path(folder) / 'job.json', None)
    if not isinstance(job, dict) or job.get('schema') != SCHEMA:
        raise WorkspaceError(f'{folder} is not a job folder this version can use. Set one up '
                             'with prepare first.')
    return job


def tool(method):
    """Make a method a worker tool: fit the arguments an agent sent, refuse once the job
    has ended, turn a refusal into an answer, and log the call."""
    signature = inspect.signature(method)
    takes = ', '.join(list(signature.parameters)[1:]) or 'nothing'

    @functools.wraps(method)
    def called(self, *args, **given):
        shown = given
        try:
            bound = signature.bind(self, *args, **given)
        except TypeError:
            outcome = (False, f'Wrong arguments for {method.__name__}: it takes {takes}.')
        else:
            shown = dict(list(bound.arguments.items())[1:])
            try:
                if self._state().get('ended'):
                    raise Refusal(ENDED)
                outcome = method(*bound.args, **bound.kwargs)
            except (WorkspaceError, OSError) as refused:
                outcome = (False, str(refused))
        self._log(method.__name__, shown, outcome)
        return outcome
    called.is_tool = True
    return called


def _described(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {'name': name, 'description': description,
            'inputSchema': {'type': 'object', 'properties': properties,
                            'required': required}}


TEXT, NUMBER, FLAG = {'type': 'string'}, {'type': 'integer'}, {'type': 'boolean'}
EMPTY = {'resources/list': {'resources': []}, 'prompts/list': {'prompts': []},
         'resources/templates/list': {'resourceTemplates': []}, 'ping': {}}


def shown(outcome) -> dict:
    """A tool's answer as an agent is sent it: the text, then each picture it carries."""
    content = [{'type': 'text', 'text': outcome[1]}]
    try:
        content += [{'type': 'image', 'mimeType': 'image/png',
                     'data': base64.b64encode(picture(path)).decode('ascii')}
                    for path in getattr(outcome, 'pictures', ())]
    except (WorkspaceError, OSError) as failure:
        return {'content': [{'type': 'text', 'text': f'A picture could not be shown '
                             f'({failure}).'}], 'isError': True}
    return {'content': content, 'isError': not outcome[0]}


def answer(tools: WorkerTools, message) -> dict | None:
    """The reply to one message from an agent, or None when it expects none."""
    if not isinstance(message, dict) or message.get('id') is None:
        return None  # a notification, or nothing this server understands
    method, params = message.get('method'), message.get('params')
    params = params if isinstance(params, dict) else {}
    if method == 'initialize':
        result = {'protocolVersion': params.get('protocolVersion') or '2024-11-05',
                  'capabilities': {'tools': {}},
                  'serverInfo': {'name': 'runner', 'version': str(SCHEMA)}}
    elif method == 'tools/list':
        result = {'tools': tools.offered()}
    elif method == 'tools/call':
        result = shown(tools.call(params.get('name'), params.get('arguments')))
    elif method in EMPTY:
        result = EMPTY[method]
    else:
        return {'jsonrpc': '2.0', 'id': message['id'],
                'error': {'code': -32601, 'message': f'No such method: {method}'}}
    return {'jsonrpc': '2.0', 'id': message['id'], 'result': result}


def serve(tools: WorkerTools, lines, out) -> None:
    """Answer an agent over standard input and output until it closes the connection."""
    for line in lines:
        try:
            message = json.loads(line)
        except ValueError:
            continue
        reply = answer(tools, message)
        if reply is not None:
            out.write(json.dumps(reply) + '\n')
            out.flush()


def main(argv: list[str] | None = None) -> int:
    options = argparse.ArgumentParser(description='Serve one job\'s worker tools.')
    options.add_argument('--job', required=True)
    args = options.parse_args(argv)
    try:
        tools = WorkerTools(Path(args.job))
    except WorkspaceError as refusal:
        print(refusal, file=sys.stderr)
        return 2
    sys.stdin.reconfigure(encoding='utf-8', errors='replace')
    sys.stdout.reconfigure(encoding='utf-8', newline='\n')
    serve(tools, sys.stdin, sys.stdout)
    return 0


def check_plan(text: str, spec: dict) -> tuple[list[str], list[dict], list[str], str]:
    """A research plan: the worker's topic and questions, with the rest filled in here.
    Returns problems, the checks that ran, warnings, and the plan as it will be kept."""
    try:
        given = json.loads(text)
    except ValueError as failure:
        return [f'The plan is not valid JSON ({failure}).'], [], [], text
    if not isinstance(given, dict):
        return ['The plan must be a JSON object with "topic" and "items".'], [], [], text
    scope = spec.get('scope') or given.get('scope')
    items, problems = given.get('items'), []
    if isinstance(items, list):
        items = [_question(item, scope, problems) for item in items]
    plan = {'topic': given.get('topic'), 'purpose': 'planning', 'scope': scope,
            'sources': spec.get('sources') or [], 'items': items}
    topic = plan['topic']
    if not isinstance(topic, str) or not topic.strip() or len(topic) > 4000:
        problems.insert(0, f'"topic" must say what the {ITEM} is about, in a line or two.')
    outcome = check_research_plan(plan, most=spec.get('most', QUESTIONS))
    return (outcome['problems'] + problems, [outcome], [],
            json.dumps(plan, indent=2, ensure_ascii=False) + '\n')


class _Page:
    """The shared methods of the studio's _Page."""

    def __init__(self):
        super(_Page, self).__init__(convert_charrefs=True)
        self.parts, self.depth, self.title, self.in_title = [], 0, '', False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.depth += 1
        if tag == 'title':
            self.in_title = True
        if tag in self.BREAK:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.depth:
            self.depth -= 1
        if tag == 'title':
            self.in_title = False
        if tag in self.BREAK:
            self.parts.append('\n')

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if not self.depth:
            self.parts.append(data)


class _NoRedirect:
    """The shared methods of the studio's _NoRedirect."""

    def redirect_request(self, *args, **kwargs):
        return None


class WorkerTools:
    """The shared methods of the studio's WorkerTools."""

    def __init__(self, folder: Path, opener=None, resolver=None, pdf=None, slides=None,
                 brand=None):
        self.folder = Path(folder)
        self.job = _job(self.folder)
        self.opener = opener or fetch_once
        self.resolver = resolver or resolve
        self.pdf = pdf or pdf_text
        self._read: dict[str, str] = {}     # an original's text, by its SHA-256, read once
        self._slides, self._brand = slides, brand

    def slides(self):
        """The slides tool, found the first time a deck's job needs it."""
        if self._slides is None:
            self._slides = the_slides((self.job.get('runtimes') or {}).get('slides'))
        return self._slides

    def brand(self):
        """The brand skill, found the first time a composer searches its icons."""
        if self._brand is None:
            self._brand = the_brand((self.job.get('runtimes') or {}).get('brand'))
        return self._brand

    def _state(self) -> dict:
        state = home.read_json(self.folder / 'state.json', {})
        return {'submissions': {}, 'problems': {}, 'ended': None, **state}

    def _count(self, name: str, problems: list[str]) -> int:
        """Note one more hand-back of `name` and how it went. Returns how many remain."""
        state = self._state()
        state['submissions'][name] = state['submissions'].get(name, 0) + 1
        state['problems'][name] = problems
        home.write_json(self.folder / 'state.json', state)
        return SUBMISSIONS - state['submissions'][name]

    def _allowed(self, name: str, what: str) -> None:
        if self._state()['submissions'].get(name, 0) >= SUBMISSIONS:
            raise Refusal(f'{what} has been handed back {SUBMISSIONS} times, which is the '
                          'most a job may. Stop now, and say in your last message what you '
                          'could not put right.')

    def _log(self, name: str, given: dict, outcome: tuple[bool, str]) -> None:
        entry = {'at': home.now(), 'tool': name, 'ok': outcome[0],
                 'given': {key: clip(value) for key, value in given.items()},
                 'answer': clip(outcome[1], 300),
                 'pictures': len(getattr(outcome, 'pictures', ()))}
        with open(self.folder / 'tools.log', 'a', encoding='utf-8') as stream:
            stream.write(json.dumps(entry) + '\n')

    def _index(self) -> list[dict]:
        return home.read_json(self.folder / 'sources' / 'index.json', [])

    def _source(self, source_id) -> tuple[dict, str]:
        """A saved source's entry and its text."""
        index = self._index()
        entry = next((item for item in index if item['id'] == str(source_id).strip()), None)
        if entry is None:
            known = ', '.join(item['id'] for item in index) or 'none yet'
            raise Refusal(f'There is no source {source_id}. Saved sources: {known}.')
        return entry, (self.folder / entry['local']).read_text(encoding='utf-8')

    def _original_path(self, entry: dict) -> Path:
        """Where a saved source's original is in this job's folder. Refused for a path
        that would leave it."""
        name = str(entry.get('original') or '')
        path, here = self.folder / name, self.folder
        linked = False
        for piece in Path(name).parts:
            here = here / piece
            linked = linked or here.is_symlink()
        if (not name or Path(name).is_absolute() or '..' in Path(name).parts or linked
                or self.folder.resolve() not in path.resolve().parents or not path.is_file()):
            raise Refusal(f"The original of {entry['id']} is not in this job, so it "
                          'cannot be read. Say so in your review: it is not something '
                          'the research can correct.')
        return path

    def _original(self, source_id) -> tuple[dict, str]:
        """A saved source's original: its entry, and its text after a first line that
        says what it is, how large, and its SHA-256. A file that is not text is read as
        the text read from that file now, never as its capture, and the first line says so."""
        entry, capture = self._source(source_id)
        if not entry.get('original'):
            raise Refusal(f"{entry['id']} has no original apart from its capture: the "
                          'capture is the document itself. Read it with read_source '
                          'without original.')
        path = self._original_path(entry)
        data = path.read_bytes()
        ending = path.suffix.lower()
        kind = ORIGINAL_TEXT.get(ending) or ORIGINAL_FILES.get(ending) or 'a file'
        about = (f"{entry['id']} original: {entry['original']}, {kind}, {len(data):,} "
                 f'bytes, sha256 {hashlib.sha256(data).hexdigest()}')
        if ending in ORIGINAL_TEXT:
            return entry, f'[{about}. It is shown as it is.]\n\n' + data.decode('utf-8', 'replace')
        if ending not in ORIGINAL_FILES:
            raise Refusal(f"The original of {entry['id']} is {kind}, which cannot be shown as "
                          'text. Read its capture, and say so in your review.')
        # Read from the file itself, never served as its capture: a check may not attest to
        # an original by reading only its extraction. Read once a job.
        digest = hashlib.sha256(data).hexdigest()
        if digest not in self._read:
            self._read[digest] = self._file_text(entry, path, data, ending)
        how = ', with its layout' if ending == '.pdf' else ''
        return entry, (f'[{about}. {kind[0].upper()}{kind[1:]} is not text: this is the text '
                       f'read from that file now{how}.]\n\n' + self._read[digest])

    def _file_text(self, entry: dict, path: Path, data: bytes, ending: str) -> str:
        """The text of an original that is not text, read from the file itself."""
        if ending == '.pdf':
            try:
                text = self.pdf(path)
            except Refusal:
                raise Refusal(f"The original of {entry['id']}, a PDF, could not be read. Say "
                              'so in your review.') from None
            if text is None:
                raise Refusal(f"This computer has no PDF reader (pdftotext), so the original "
                              f"of {entry['id']} cannot be read. Say so in your review.")
            return text.replace('\x00', '')
        return word_text(data, entry['id'])

    def _refused(self, problems: list[str], left: int) -> tuple[bool, str]:
        """The answer to a hand-back the checks did not let through."""
        listed = '\n- '.join(problems)
        if left <= 0:
            return False, ('Not accepted, and it cannot be handed back again:\n- ' + listed
                           + '\n\nStop now, and say in your last message what you could '
                           'not put right.')
        more = f'\n\nIt can be handed back {left} more time(s).' if left <= 2 else ''
        return False, f'Not accepted. Fix these and hand it back again:\n- {listed}{more}'

    def call(self, name: str, given) -> tuple[bool, str]:
        """Run one tool by name with the arguments an agent sent. Never raises."""
        given = given if isinstance(given, dict) else {}
        if name not in NAMES:
            outcome = (False, f'There is no tool called {name}.')
        else:
            try:
                return getattr(self, name)(**given)
            except Exception as failure:  # the worker is told; the server keeps running
                outcome = (False, 'The tool failed and nothing was kept '
                           f'({type(failure).__name__}: {failure}).')
        self._log(str(name), given, outcome)
        return outcome

    def _original_named(self, entry: dict) -> str:
        """How list_inputs names a supplied source's original, when it has one."""
        if not entry.get('offered') or not entry.get('original'):
            return ''
        try:
            size = f"{self._original_path(entry).stat().st_size:,} bytes"
        except (Refusal, OSError):
            return f"; original: {entry['original']}, which cannot be read"
        return f"; original: {entry['original']}, {size} (read_source with original=true)"

    def _input(self, entry: dict) -> str:
        return (self.folder / entry['file']).read_text(encoding='utf-8')

    def _hand_in(self, name: str, text: str) -> tuple[bool, str]:
        """Check a draft and keep it if the checks let it through."""
        self._allowed(name, name)
        spec = self.job['artifacts'][name]
        problems, ran, warnings, kept = self._validate(spec, text)
        left = self._count(name, problems)
        if problems:
            return self._refused(problems, left)
        file = f"accepted/{slug(name)}{EXTENSIONS.get(spec['kind'], '.md')}"
        _write(self.folder / file, kept)
        index = home.read_json(self.folder / 'accepted' / 'artifacts.json', {})
        index[name] = {'kind': spec['kind'], 'file': file, 'checks': ran,
                       'warnings': warnings, 'at': home.now()}
        home.write_json(self.folder / 'accepted' / 'artifacts.json', index)
        noted = ('' if not warnings else ' Noted for the person who reviews it:\n- '
                 + '\n- '.join(warnings) + '\nHand it back again only if one of these is '
                 'a mistake you can put right.')
        return True, f'Accepted: {name}.{noted}'

    def _spec(self, kind: str) -> tuple[str, dict]:
        """The name and the particulars of the one draft of this kind the job hands in."""
        for name, spec in self.job['artifacts'].items():
            if spec['kind'] == kind:
                return name, spec
        raise Refusal(f'This job has no {kind} to work on.')

    def _tried(self, kind: str, given) -> tuple[bool, str]:
        """Check a draft and say what was found. Nothing is kept and nothing is counted."""
        _, spec = self._spec(kind)
        problems = self._validate(spec, as_json(given, kind)[1])[0]
        if problems:
            return True, 'To put right before you hand it in:\n- ' + '\n- '.join(problems)
        return True, (f'Nothing to put right. '
                      + ('Hand it in with submit_outline.' if kind == 'outline' else
                         'Preview it with preview_section before you hand it in.'))

    @staticmethod
    def _digest(drawn) -> str:
        return hashlib.sha256(json.dumps(drawn, sort_keys=True).encode('utf-8')).hexdigest()

    def _review(self) -> dict:
        review = self.job.get('review')
        if not review:
            raise Refusal('This job is not a review of a deck.')
        return review

    def _shown(self, entry: dict, verb: str) -> str:
        text = (self.folder / entry['local']).read_text(encoding='utf-8')
        more = '' if len(text) <= WINDOW else (
            f'\n\n[{len(text) - WINDOW:,} more characters. Use search_source to find a '
            'passage and read_source to read around it.]')
        return (f"{verb} as {entry['id']}: \"{entry['title']}\", {len(text):,} "
                f'characters.\n\n{text[:WINDOW]}{more}'
                + (f"\n\nCapture file: {entry['file']}. Origin: {entry['url']}."
                   if any(spec.get('kind') == 'research-json' for spec in self.job['artifacts'].values()) else ''))

    def _ask(self, url: str, addresses: list[str]) -> tuple[int, dict, bytes]:
        """One request, trying each of the host's addresses until one connects."""
        failure = None
        for address in addresses:
            try:
                return self.opener(url, address, MAX_BYTES)
            except (OSError, http.client.HTTPException) as failed:
                failure = getattr(failed, 'reason', None) or failed
        raise Refusal(f'Could not fetch the page ({failure}). It was not saved.')

    def _keep(self, asked: str, url: str, headers: dict, data: bytes, number: int) -> dict:
        """Store a fetched page and its text snapshot, and describe them."""
        kind = headers.get('content-type', 'text/html')
        base = kind.partition(';')[0].strip().lower()
        target = urllib.parse.urlsplit(url)
        digest = hashlib.sha256(data).hexdigest()
        stem = f'sources/{slug(target.hostname)}-{digest[:12]}'
        pdf = data[:5] == b'%PDF-' or base == 'application/pdf'
        if not pdf and not base.startswith('text/') and base not in TEXT_TYPES:
            raise Refusal(f'That address holds {base}, not a page or a PDF. It was not '
                          'saved.')
        original = stem + ('.pdf' if pdf else '.html' if 'html' in base else '.raw')
        (self.folder / 'sources').mkdir(exist_ok=True)
        (self.folder / original).write_bytes(data)
        try:
            text, title = (self._pdf(self.folder / original, target) if pdf
                           else page_text(data, kind))
            if not text.strip():
                raise Refusal('That page has no readable text; it may need a browser to '
                              'show it. It was not saved. Look for the same content '
                              'elsewhere.')
        except Refusal:
            (self.folder / original).unlink(missing_ok=True)
            raise
        _write(self.folder / (stem + '.txt'), text)
        return {'id': f's{number}', 'url': url, 'asked': asked,
                'title': clip(title or target.hostname, 300), 'chars': len(text),
                'file': stem + '.txt',
                'local': stem + '.txt', 'original': original, 'sha256': digest,
                'offered': False, 'supplied': None, 'saved_at': home.now()}

    def _pdf(self, path: Path, target) -> tuple[str, str]:
        """The text of a saved PDF, and the file name it goes by."""
        text = self.pdf(path)
        if text is None:
            raise Refusal('That is a PDF, and this computer has no PDF reader (pdftotext). '
                          'Look for the same content as a web page.')
        return tidy(text), urllib.parse.unquote(target.path.rsplit('/', 1)[-1])

    def _passages(self, evidence) -> list:
        """The passages an agent sent, which may have arrived as JSON text."""
        if isinstance(evidence, str) and evidence.strip():
            try:
                evidence = json.loads(evidence)
            except ValueError:
                raise Refusal('evidence must be a list of passages, each with source_id and '
                              'quote.')
        if evidence is None or evidence == '':
            return []
        if not isinstance(evidence, list):
            raise Refusal('evidence must be a list of passages, each with source_id and '
                          'quote.')
        return evidence

    def _placed(self, number: int, passage, problems: list[str]) -> dict | None:
        """One passage with its place in its source, or None with the problem added."""
        if not isinstance(passage, dict):
            problems.append(f'Passage {number} needs a source_id and a quote.')
            return None
        try:
            entry, text = self._source(passage.get('source_id'))
        except Refusal as missing:
            problems.append(f'Passage {number}: {missing}')
            return None
        quote = passage.get('quote') if isinstance(passage.get('quote'), str) else ''
        found = place(text, quote.strip())
        if found is None:
            problems.append(f"Passage {number}: the quote is not in {entry['id']} as "
                            'written. Copy it from the saved text with nothing left out '
                            'or added, and no "..." in it.')
            return None
        start, exact = found
        if not QUOTE[0] <= len(exact) <= QUOTE[1]:
            problems.append(f'Passage {number}: the quote is {len(exact)} characters. '
                            f'Quote the whole sentence that makes the point, between '
                            f'{QUOTE[0]} and {QUOTE[1]} characters.')
            return None
        placed = {'file': entry['file'], 'title': entry['title'] or entry['url'],
                  'origin': entry['url'], 'quote': exact, 'start': start,
                  'locator': f'characters {start} to {start + len(exact)}'}
        if entry.get('supplied'):
            placed['source_id'] = entry['supplied']
        return placed


NAMES = ('SCHEMA', 'PART', 'WINDOW', 'MAX_BYTES', 'MAX_SOURCES', 'MAX_HOPS', 'TIMEOUT',
         'SUBMISSIONS', 'QUOTE', 'SUMMARY', 'NOTES', 'QUESTION', 'PLAN_MOST', 'PASSAGES',
         'ADDRESS', 'ICONS', 'RENDER_WAIT', 'PNG', 'PICTURE', 'STATUSES', 'SCOPES', 'QUESTION_ID',
         'NOT_A_QUERY', 'CHARSET', 'META_CHARSET', 'REDIRECTS', 'TEXT_TYPES', 'ORIGINAL_TEXT',
         'ORIGINAL_FILES', 'HEADERS', 'ALIKE', 'ENDED', 'parts', 'tidy', 'word_text', 'flag',
         'whole', 'slug', 'clip', '_loose', 'place', 'decode', 'page_text', 'pdf_text', 'public',
         'resolve', '_pinned', 'fetch_once', 'unpacked', '_question', 'held', 'as_json', 'said_no',
         '_draft', 'DRAWN', 'EXTENSIONS', 'picture', 'one_at_a_time', 'turn_file', 'slots',
         'pictures', 'the_slides', 'the_brand', '_write', '_offered', '_job', 'tool', '_described',
         'TEXT', 'NUMBER', 'FLAG', 'EMPTY', 'shown', 'answer', 'serve', 'main', 'check_plan')
METHODS = {'_Page': ('__init__', 'handle_starttag', 'handle_endtag', 'handle_data'), '_NoRedirect':
           ('redirect_request',), 'WorkerTools': ('__init__', 'slides', 'brand', '_state',
           '_count', '_allowed', '_log', '_index', '_source', '_original_path', '_original',
           '_file_text', '_refused', 'call', '_original_named', '_input', '_hand_in', '_spec',
           '_tried', '_digest', '_review', '_shown', '_ask', '_keep', '_pdf', '_passages',
           '_placed')}
