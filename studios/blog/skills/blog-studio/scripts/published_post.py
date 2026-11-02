"""A published blog post, read by its link (or from a team collection) for a GEO review.

The page is read once, on the person's press, through Blog Studio's bounded fetcher
(blog_library.fetch: public addresses only on every hop, the link's own site, a deadline,
limited redirects and a size limit). Nothing on the page runs: its HTML is read with the
standard library's html.parser into the post's Markdown (title, headings, text, lists,
quotations, tables, links and images with their alt text). The live page is never changed;
what was read is staged on this computer (.blog-runs/published-posts) for the person to
check before anything starts, and the desk or a GEO report works on that copy.

Page access is advice only: whether the page says noindex (meta tag or X-Robots-Tag), sits
behind a login, is blocked for search crawlers by the site's robots.txt (one extra small
fetch on the same press), whether its JSON-LD agrees with what the page shows, and whether
it has a byline and a date. These are eligibility checks, never ranking promises.
"""

from html.parser import HTMLParser
import json
import re
import time
from urllib.parse import urljoin, urlsplit, urlunsplit

import studio

STAGE = ('.blog-runs', 'published-posts')
KEEP_SECONDS = 24 * 60 * 60  # A read nobody started from is let go after a day.
LIMIT = 200_000  # characters a desk draft holds (desk.LIMIT), image data aside
ROBOTS_BYTES = 256 * 1024
ROBOTS_SECONDS = 10
WORDS_FOR_LOGIN = 150  # A page with a password box and fewer words than this is a login.
# The crawlers Page access asks robots.txt about: Google's, and the AI search crawlers.
# GPTBot crawls only for training, so it is asked about and said apart from search.
SEARCH_AGENTS = (
    ('Googlebot', 'Google Search'),
    ('OAI-SearchBot', 'ChatGPT search'),
    ('PerplexityBot', 'Perplexity'),
)
TRAINING_AGENT = 'GPTBot'
LOGIN = (
    'This page asks for a sign-in, so Blog Studio could not read the post. Paste its text '
    'or upload it instead.'
)
NOT_A_PAGE = (
    'This link is not a web page Blog Studio can read (it is {kind}). Link to the post’s '
    'page, or upload the file instead.'
)
TOO_LARGE = (
    'This page is larger than Blog Studio reads from a link (2 MB). Paste the post’s text '
    'or upload it instead.'
)
TOO_LONG = 'This post is longer than the desk holds (200,000 characters). Paste a shorter part.'
NO_TEXT = (
    'No article text was found on this page. It may be built by scripts, which Blog Studio '
    'never runs. Paste the post’s text instead.'
)
NOT_FOUND = 'This page was not found (HTTP {status}). Check the link.'
REFUSED = 'The site refused to send this page (HTTP {status}). Check the link.'
BAD_LINK = 'Use the post’s public https link, without a password or port.'
STALE = 'This read of the page is no longer kept here. Read the page again.'
CHANGED = 'This read of the page changed. Read the page again.'
ELIGIBILITY = (
    'These are eligibility checks: they say whether search and AI assistants may read the '
    'page, never how it will rank or whether it will be cited.'
)
SITE_OWNER = (
    'Site-level settings, such as Search Console’s AI inclusion setting, IndexNow, crawler '
    'IP checks and measurement, belong to the site owner; Blog Studio does not check them.'
)


# The article as Markdown. Only one region is read: the page's <article>, else its <main>,
# else its <body> without the site's header, navigation, sidebars and footer.
SKIPPED = {'script', 'style', 'noscript', 'template', 'svg', 'iframe', 'canvas', 'object'}
SKIPPED |= {'form', 'button', 'select', 'textarea', 'nav', 'aside', 'dialog'}
PAGE_CHROME = {'header', 'footer'}  # Left out unless they are inside the article.
BLOCKS = {'p', 'div', 'section', 'figure', 'figcaption', 'article', 'main', 'header'}
BLOCKS |= {'footer', 'dl', 'dt', 'dd', 'address', 'details', 'summary', 'hr'}
HEADINGS = {'h1': 1, 'h2': 2, 'h3': 3, 'h4': 4, 'h5': 5, 'h6': 6}
VOID = {'br', 'img', 'hr', 'input', 'meta', 'link', 'source', 'wbr', 'col', 'area', 'base'}
ARTICLE_TYPES = {'article', 'blogposting', 'newsarticle', 'techarticle', 'report', 'webpage'}
BYLINE_HINT = re.compile(r'(?:^|[\s_-])(?:author|byline|by-line|writer)(?:$|[\s_-])', re.I)
DATE_HINT = re.compile(r'(?:^|[\s_-])(?:date|published|posted|updated|modified|meta)', re.I)
BY = re.compile(r'^\s*(?:by|written by|posted by)\s+', re.I)
# A short line that is only a byline, as "By Jane Doe" or "By Jane Doe · 1 March 2025".
BY_LINE = re.compile(r'(?:by|written by|posted by)\s+([^.!?\n]{2,80})', re.I)
# A hostile page is read in bounded time and space: open tags, list and quotation depth, a
# table's size, a byline's words and the Markdown made are each capped as they are read.
MAX_DEPTH = 200  # open elements kept; deeper ones are read as text
MAX_INDENT = 8  # list and quotation levels shown
MAX_COLUMNS = 30
MAX_ROWS = 500
MAX_MARKED = 200  # characters kept of a byline or a date line
MAX_TEXT = 2 * LIMIT  # characters of Markdown made; past it the rest is not read
# Page text is kept as written; only what could become HTML, a link or an image is escaped.
TAG_START = re.compile(r'<(?=[A-Za-z/!?])')
LINK_CLOSE = re.compile(r'\](?=[(\[:])')
IMAGE_START = re.compile(r'!(?=\[)')
UNESCAPE = re.compile(r'\\([\\`*_{}\[\]()#+\-.!|<>~])')


def _clean(text):
    return ' '.join(text.split())


def _md(text):
    """Page text as Markdown text: its words as written, with only what could become markup
    or a link escaped: a < that could open a tag (before a letter, /, ! or ?), a ] that could
    close a link or a reference (before (, [ or :) and a ! before [. *, _, >, backslashes and
    backticks stay as they are, so the draft reads as the page did."""
    text = TAG_START.sub(r'\\<', text)
    text = LINK_CLOSE.sub(r'\\]', text)
    return IMAGE_START.sub(r'\\!', text)


class Words(str):
    """A piece of a line that is the page's own words (not Markdown Blog Studio wrote)."""


def _joined(pieces, piece, words):
    """Add a piece to a line's pieces. Where the page's words end and the next piece begins
    (across a tag, say), the end is escaped if the two together could make a tag, a link or
    an image, as _md escapes them within one piece."""
    if pieces and piece and isinstance(pieces[-1], Words):
        before, first = pieces[-1], piece[0]
        if (
            (before.endswith(']') and first in '([:')
            or (before.endswith('!') and first == '[')
            or (before.endswith('<') and (first.isalpha() or first in '/!?'))
        ):
            pieces[-1] = Words(before[:-1] + '\\' + before[-1])
    pieces.append(Words(piece) if words else piece)


def plain(text):
    """Markdown text with its escapes taken out, as a reader sees it."""
    return UNESCAPE.sub(r'\1', text or '')


def _target(url):
    """A link or image address as Markdown takes it: only http(s), and nothing in it can
    end the link early."""
    if not url.startswith(('https://', 'http://')):
        return ''
    for character, code in (('(', '%28'), (')', '%29'), (' ', '%20'), ('<', '%3C'), ('>', '%3E')):
        url = url.replace(character, code)
    return url.replace('"', '%22').replace('\\', '%5C')


SAFE_LINK = re.compile(r'(!?)\[((?:\\.|[^\[\]\n\\])*)\]\(\s*<?([^()\s>]*)>?(?:\s+"[^"\n]*")?\s*\)')


def safe_markdown(text, download=False):
    """Markdown from a page or an assistant with no raw HTML (each < escaped) and no link or
    image to anything but http(s); such a link keeps its words. For a `download`, read by
    whatever Markdown viewer the person has, < and > become entities, so no tag is spelled
    out at all, and a script scheme spelled in the text loses its colon (&#58;): each reads
    the same."""
    text = str(text or '')

    def link(found):
        if found.group(3).startswith(('https://', 'http://')):
            return found.group(0)
        return found.group(2)

    text = SAFE_LINK.sub(link, text)
    # Whatever the link pattern missed (a target with parentheses, say) is no link at all
    # unless it goes to http(s).
    text = re.sub(r'(?<!\\)\]\((?!https?://)', r']\\(', text)
    if not download:
        return re.sub(r'(?<!\\)<', r'\\<', text)
    text = re.sub(r'\\?<', '&lt;', text)
    text = re.sub(r'\\>', '&gt;', text)
    text = re.sub(r'(?<=[^\s>])>', '&gt;', text)  # A quotation's > stays.
    return re.sub(r'(?i)(javascript|vbscript)\s*:', r'\1&#58;', text)


def _escape_table(text):
    return text.replace('|', '\\|')


class Article(HTMLParser):
    """The page read for its article: Markdown blocks, plus what Page access needs."""

    def __init__(self, base, region):
        super().__init__(convert_charrefs=True)
        self.base, self.region = base, region
        self.blocks, self.line = [], []
        self.depth = 0  # inside the region read (or 1 throughout for a fragment)
        self.entered = self.done = False
        self.furniture = 0  # inside a byline or a date line
        self.skip = 0
        self.stack = []
        self.lists = []
        self.quote = 0
        self.pre = None
        self.heading = None
        self.link = None
        self.table = None
        self.title_tag, self.in_title = '', False
        self.meta = {}
        self.robots_meta = []
        self.ld = []
        self.ld_text = None
        self.password = False
        self.links, self.images = [], []
        self.h1 = []
        self.bylines, self.times, self.updated = [], [], []
        # An element whose class says byline or date, by its place in the open elements:
        # [tag, kind, words, length, updated]. Its words stop once MAX_MARKED are kept.
        self.marked = {}
        self.open = {}  # how many of each tag are open, for an end tag's O(1) check
        self.size = 0  # characters of Markdown made so far
        self.full = False  # past MAX_TEXT: the rest of the page is not read
        self.code = False  # inside inline code

    # Blocks
    def add(self, kind, value, size):
        """Keep a block, counting what the Markdown holds; past MAX_TEXT nothing more is read."""
        self.size += size + 2
        if self.size > MAX_TEXT:
            self.full = True
            return
        self.blocks.append((kind, value))

    def flush(self):
        text = _clean(''.join(self.line))
        self.line = []
        if not text or self.full:
            return
        if not self.lists and not self.quote and len(self.blocks) < 12:
            found = BY_LINE.fullmatch(plain(text))
            name = re.split(r'\s+(?:·|\||•|-|–|—|on)\s+', found.group(1))[0] if found else ''
            if found and name[:1].isupper() and len(name.split()) <= 5:
                # A short "By Jane Doe" line is the page's byline, not the post's text.
                self.bylines.append(name.strip()[:MAX_MARKED])
                self.times.append(plain(text)[:MAX_MARKED])
                return
        if self.lists:
            depth = min(len(self.lists), MAX_INDENT) - 1
            mark = '- ' if self.lists[-1][0] == 'ul' else str(self.lists[-1][1]) + '. '
            text = '  ' * depth + mark + text
        if self.quote:
            text = '> ' * min(self.quote, MAX_INDENT) + text
        if self.lists and self.blocks and self.blocks[-1][0] == 'item':
            self.size += len(text) + 1
            if self.size > MAX_TEXT:
                self.full = True
                return
            self.blocks[-1][1].append(text)
        else:
            self.add('item' if self.lists else 'text', [text], len(text))

    def reading(self):
        return self.depth > 0 and not self.skip and not self.furniture and not self.full

    def handle_starttag(self, tag, attrs):
        attrs = {key: value or '' for key, value in attrs}
        if tag == 'title':
            self.in_title = True
        if tag == 'meta':
            self._meta(attrs)
        if tag == 'script' and 'ld+json' in attrs.get('type', '').lower():
            self.ld_text = []
        if tag == 'input' and attrs.get('type', '').lower() == 'password':
            self.password = True
        if tag not in VOID:
            if len(self.stack) >= MAX_DEPTH:
                return  # Too deep: its words are read in the element that holds it.
            self.stack.append(tag)
            self.open[tag] = self.open.get(tag, 0) + 1
        if tag == self.region and not self.skip and not self.done:
            self.depth += 1
            self.entered = True
        if self.depth and (tag in SKIPPED or (self.region == 'body' and tag in PAGE_CHROME)):
            self.skip += 1
            if tag in VOID:
                self.skip -= 1
            return
        if self.skip:
            return
        hint = ' '.join([attrs.get('class', ''), attrs.get('id', ''), attrs.get('itemprop', '')])
        if tag == 'a' and 'author' in attrs.get('rel', '').lower():
            hint += ' author'
        # A byline or a date line is the page's furniture, read for Page access (in the
        # post's header too, outside the article) and left out of the post's text; a whole
        # region or section is never taken for one.
        holder = tag not in VOID and tag not in ('article', 'main', 'body', 'section', 'html')
        level = len(self.stack)
        if tag == 'time':
            when = attrs.get('datetime', '')[:MAX_MARKED]
            self.times.append(when)
            if any(entry[4] for entry in self.marked.values()):
                self.updated.append(when)
        if holder and level not in self.marked and BYLINE_HINT.search(hint):
            self.marked[level] = [tag, 'byline', [], 0, False]
            if self.depth:
                self.flush()
                self.furniture += 1
        elif holder and level not in self.marked and tag != 'time' and DATE_HINT.search(hint):
            updated = bool(re.search(r'updat|modif', hint, re.I))
            self.marked[level] = [tag, 'date', [], 0, updated]
            if self.depth:
                self.flush()
                self.furniture += 1
        if not self.depth or self.furniture:
            return
        if tag in HEADINGS:
            self.flush()
            self.heading = HEADINGS[tag]
        elif tag in ('ul', 'ol'):
            self.flush()
            self.lists.append([tag, 0])
        elif tag == 'li':
            self.flush()
            if self.lists:
                self.lists[-1][1] += 1
        elif tag == 'blockquote':
            self.flush()
            self.quote += 1
        elif tag == 'pre':
            self.flush()
            self.pre = []
        elif tag == 'table':
            self.flush()
            self.table = []
        elif tag == 'tr' and self.table is not None:
            if len(self.table) < MAX_ROWS:
                self.table.append([])
        elif tag in ('td', 'th') and self.table is not None:
            self.flush()
        elif tag == 'br':
            if self.pre is not None:
                self.pre.append('\n')
            else:
                self.line.append(' ')
        elif tag == 'a':
            href = urljoin(self.base, attrs.get('href', '').strip())
            self.link = [href if href.startswith(('https://', 'http://')) else '', []]
        elif tag == 'img':
            self._image(attrs)
        elif tag == 'code' and self.pre is None:
            self.line.append('`')
            self.code = True
        elif tag in BLOCKS and self.table is None:
            self.flush()

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False
        if tag == 'script' and self.ld_text is not None:
            self.ld.append(''.join(self.ld_text))
            self.ld_text = None
        if tag in VOID or not self.open.get(tag):
            return  # A stray end tag: nothing open to close (an O(1) check).
        while self.stack:
            open_tag = self.stack.pop()
            self.open[open_tag] -= 1
            self._close(open_tag)
            if open_tag == tag:
                break

    def _close(self, tag):
        level = len(self.stack) + 1  # Its place as it was pushed (popped already).
        found = self.marked.get(level)
        if found and found[0] == tag:
            del self.marked[level]
            if self.depth or self.furniture:
                self.furniture = max(0, self.furniture - 1)
            text = _clean(''.join(found[2]))[:MAX_MARKED]
            if text:
                if found[1] == 'byline':
                    self.bylines.append(text)
                else:
                    self.times.append(text)
                    if found[4] or re.match(r'\s*(?:last\s+)?(?:updated|modified)', text, re.I):
                        self.updated.append(text)
        if self.depth and (tag in SKIPPED or (self.region == 'body' and tag in PAGE_CHROME)):
            if self.skip:
                self.skip -= 1
            return
        if tag == self.region and self.depth and not self.skip:
            self.flush()
            self.depth -= 1
            # Only the first region is the post: a later <article> is a related post.
            self.done = self.entered and not self.depth
            return
        if not self.reading():
            return
        if tag in HEADINGS and self.heading:
            text = _clean(''.join(self.line))[:1000]
            self.line = []
            if text:
                if self.heading == 1 and len(self.h1) < 5:
                    self.h1.append(text)
                self.add('heading', [self.heading, text], len(text) + 7)
            self.heading = None
        elif tag in ('ul', 'ol'):
            self.flush()
            if self.lists:
                self.lists.pop()
        elif tag == 'li':
            self.flush()
        elif tag == 'blockquote':
            self.flush()
            self.quote = max(0, self.quote - 1)
        elif tag == 'pre' and self.pre is not None:
            code = ''.join(self.pre).strip('\n')
            self.pre = None
            if code.strip():
                self.add('code', [code], len(code) + 8)
        elif tag in ('td', 'th') and self.table is not None:
            text = _clean(''.join(self.line))[:1000]
            self.line = []
            if self.table and len(self.table[-1]) < MAX_COLUMNS:
                self.table[-1].append(_escape_table(text))
        elif tag == 'table' and self.table is not None:
            rows = [row for row in self.table if any(cell for cell in row)]
            self.table = None
            if rows:
                width = max(len(row) for row in rows)
                self.add('table', rows, sum(len(c) + 3 for row in rows for c in row) + 6 * width)
        elif tag == 'a' and self.link is not None:
            href, words = self.link
            self.link = None
            text = _clean(''.join(words))
            target = _target(href) if href else ''
            if text and target:
                if len(self.links) < 500:
                    self.links.append({'url': href, 'text': plain(text)[:300]})
                _joined(self.line, '[' + text + '](' + target + ')', False)
            elif text:
                _joined(self.line, text, True)
        elif tag == 'code':
            if self.code:
                self.line.append('`')
            self.code = False
        elif tag in BLOCKS and self.table is None:
            self.flush()

    def handle_data(self, data):
        if self.in_title and len(self.title_tag) < 1000:
            self.title_tag += data[:1000]
        if self.ld_text is not None:
            if len(self.ld) < 20:
                self.ld_text.append(data)
            return
        for found in self.marked.values():
            if found[3] < MAX_MARKED:  # Its words stop once enough are kept.
                found[2].append(data[: MAX_MARKED - found[3]])
                found[3] += len(data)
        if not self.reading():
            return
        if self.pre is not None:
            self.pre.append(data)
            return
        # The page's words are text: nothing in them is read as Markdown. Inside inline
        # code they are literal already; a backtick there would end it, so it is left out.
        text = data.replace('`', '') if self.code else _md(data)
        _joined(self.link[1] if self.link is not None else self.line, text, not self.code)

    def _meta(self, attrs):
        name = (attrs.get('name') or attrs.get('property') or '').lower()
        content = ' '.join((attrs.get('content') or '').split())[:1000]
        if name in ('robots', 'googlebot'):
            self.robots_meta.append(content)
        elif name in (
            'og:title',
            'author',
            'article:author',
            'article:published_time',
            'article:modified_time',
            'description',
        ):
            self.meta.setdefault(name, content)

    def _image(self, attrs):
        source = attrs.get('src') or attrs.get('data-src') or ''
        source = urljoin(self.base, source.strip()) if source else ''
        target = _target(source)
        if not target or len(source) > 2000 or len(self.images) >= 200:
            return
        alt = _clean(attrs.get('alt', ''))[:300]
        self.images.append({'src': source, 'alt': alt})
        self.flush()
        image = '![' + alt.replace('[', '').replace(']', '') + '](' + target + ')'
        self.add('text', [image], len(image))

    def markdown(self, title):
        """The post as Markdown: its title, then each block, a blank line between."""
        self.flush()
        out, dropped = [], False
        for kind, value in self.blocks:
            if kind == 'heading':
                level, text = value
                if level == 1 and not dropped and plain(text) == title:
                    dropped = True  # The title heads the Markdown already.
                    continue
                out.append('#' * max(2, level) + ' ' + text)
            elif kind == 'code':
                # A fence longer than any run of backticks in the code, so it cannot end early.
                runs = re.findall(r'`+', value[0])
                fence = '`' * max(3, max((len(run) for run in runs), default=0) + 1)
                out.append(fence + '\n' + value[0] + '\n' + fence)
            elif kind == 'table':
                width = max(len(row) for row in value)
                rows = [row + [''] * (width - len(row)) for row in value]
                lines = ['| ' + ' | '.join(rows[0]) + ' |', '|' + ' --- |' * width]
                lines += ['| ' + ' | '.join(row) + ' |' for row in rows[1:]]
                out.append('\n'.join(lines))
            elif kind == 'item':
                out.append('\n'.join(value))
            else:
                out.append(value[0])
        body = '\n\n'.join(out).strip()
        return ('# ' + _md(title) + '\n\n' + body).strip() + '\n'


def _region(html):
    lowered = html.lower()
    if re.search(r'<article[\s>]', lowered):
        return 'article'
    if re.search(r'<main[\s>]', lowered):
        return 'main'
    return 'body' if re.search(r'<body[\s>]', lowered) else None


def _words(text):
    return len(re.findall(r"[\w’']+", re.sub(r'\]\([^)]*\)', ']', text)))


def article(content, base):
    """The article on a page (bytes of HTML): its title, Markdown and what Page access reads."""
    html = content.decode('utf-8', 'replace')
    region = _region(html)
    parser = Article(base, region or 'html')
    if region is None:
        parser.depth = 1  # A fragment with no <body>: all of it is the article.
    try:
        parser.feed(html)
        parser.close()
    except (AssertionError, RecursionError, ValueError):
        raise ValueError(NO_TEXT) from None
    title = (
        (plain(parser.h1[0]) if parser.h1 else '')
        or parser.meta.get('og:title', '')
        or _clean(parser.title_tag)
    )
    title = _clean(title)[:500] or (urlsplit(base).netloc + urlsplit(base).path).rstrip('/')
    markdown = parser.markdown(title)
    body = markdown.split('\n', 1)[1] if '\n' in markdown else ''
    return {
        'title': title,
        'markdown': markdown,
        'words': _words(body),
        'headings': [plain(value[1]) for kind, value in parser.blocks if kind == 'heading'][:200],
        'links': parser.links[:500],
        'images': parser.images[:200],
        'parser': parser,
    }


# Page access: advice only.
# X-Robots-Tag directives that carry a value after a colon, never a crawler's name.
VALUED = {'max-snippet', 'max-image-preview', 'max-video-preview', 'unavailable_after'}
SEARCH_TOKENS = {'googlebot': 'Google Search', 'oai-searchbot': 'ChatGPT search'}
SEARCH_TOKENS['perplexitybot'] = 'Perplexity'


def _directives(value):
    """[(crawler or None for every crawler, directive)] in one X-Robots-Tag value, as
    "noindex" or "googlebot: noindex, nofollow" (a name holds until another one)."""
    found, agent = [], None
    for token in (value or '').split(','):
        token = token.strip().lower()
        if ':' in token and token.split(':', 1)[0].strip() not in VALUED:
            agent, token = (part.strip() for part in token.split(':', 1))
        if token:
            found.append((agent, token.split(':', 1)[0].strip()))
    return found


def _noindexed(directives):
    """Whom noindex applies to among search crawlers: 'all', a list of their names, or []."""
    who = set()
    for agent, directive in directives:
        if directive not in ('noindex', 'none'):
            continue
        if agent is None:
            return 'all'
        if agent in SEARCH_TOKENS:
            who.add(SEARCH_TOKENS[agent])
    return sorted(who)


def _names(value):
    """Author names in a JSON-LD author value: a name, an object with a name, or a list."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return _names(value.get('name'))
    if isinstance(value, list):
        return [name for entry in value[:10] for name in _names(entry)]
    return []


def _ld_items(parser):
    """The article-like JSON-LD objects on the page, and how many scripts could not be read."""
    found, unreadable = [], 0

    def walk(value, depth=0):
        if depth > 6 or len(found) >= 10:
            return
        if isinstance(value, list):
            for entry in value[:50]:
                walk(entry, depth + 1)
        elif isinstance(value, dict):
            kinds = value.get('@type')
            kinds = kinds if isinstance(kinds, list) else [kinds]
            if any(isinstance(kind, str) and kind.lower() in ARTICLE_TYPES for kind in kinds):
                found.append(value)
            for key in ('@graph', 'mainEntity', 'mainEntityOfPage'):
                if key in value:
                    walk(value[key], depth + 1)

    for text in parser.ld[:20]:
        try:
            walk(json.loads(text[:500_000]))
        except (ValueError, RecursionError):
            unreadable += 1
    articles = [item for item in found if str(item.get('@type')).lower() != 'webpage']
    return articles or found, unreadable


MONTHS = {
    name: number
    for number, names in enumerate(
        (
            ('jan', 'january'),
            ('feb', 'february'),
            ('mar', 'march'),
            ('apr', 'april'),
            ('may',),
            ('jun', 'june'),
            ('jul', 'july'),
            ('aug', 'august'),
            ('sep', 'sept', 'september'),
            ('oct', 'october'),
            ('nov', 'november'),
            ('dec', 'december'),
        ),
        1,
    )
    for name in names
}
MONTH = r'(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)'
DAY_MONTH_YEAR = re.compile(r'\b(\d{1,2})(?:st|nd|rd|th)?\s+' + MONTH + r'\.?,?\s+(\d{4})\b', re.I)
MONTH_DAY_YEAR = re.compile(MONTH + r'\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b', re.I)
SLASHED = re.compile(r'\b(\d{4})[/.](\d{1,2})[/.](\d{1,2})\b')


def _day(value):
    """A date written in a page (ISO, "1 March 2025", "March 1, 2025" or 2025/03/01) as
    YYYY-MM-DD; None when it has none."""
    value = (value or '')[:MAX_MARKED]
    found = re.search(r'\b(\d{4})-(\d{2})-(\d{2})', value)
    if found:
        return found.group(0)[-10:]
    for pattern, order in ((DAY_MONTH_YEAR, 'dmy'), (MONTH_DAY_YEAR, 'mdy'), (SLASHED, 'ymd')):
        found = pattern.search(value)
        if not found:
            continue
        if order == 'dmy':
            day, month, year = found.group(1), MONTHS[found.group(2).lower()], found.group(3)
        elif order == 'mdy':
            month, day, year = MONTHS[found.group(1).lower()], found.group(2), found.group(3)
        else:
            year, month, day = found.group(1), found.group(2), found.group(3)
        if 1 <= int(month) <= 12 and 1 <= int(day) <= 31:
            return '%s-%02d-%02d' % (year, int(month), int(day))
    return None


def _same(left, right):
    left, right = _clean(left).casefold().strip(' .'), _clean(right).casefold().strip(' .')
    return bool(left and right) and (left == right or left in right or right in left)


def _ld_text(value):
    return value.strip()[:300] if isinstance(value, str) else ''


def access(read, headers, robots):
    """Page access, as the report says it: each check and what it found. Advice only; a
    check that finds nothing says what Blog Studio did not find, never more."""
    parser = read['parser']
    byline = next(
        (BY.sub('', text).strip() for text in parser.bylines if BY.sub('', text).strip()), ''
    )
    days = list(dict.fromkeys(day for day in (_day(value) for value in parser.times) if day))
    updated = list(dict.fromkeys(day for day in (_day(v) for v in parser.updated) if day))
    items, unreadable = _ld_items(parser)
    item = items[0] if items else {}
    # Not shown on the page, but said in its metadata: a date or an author is still found.
    hidden_days = [
        day
        for day in (
            _day(parser.meta.get('article:published_time')),
            _day(parser.meta.get('article:modified_time')),
            _day(_ld_text(item.get('datePublished'))),
            _day(_ld_text(item.get('dateModified'))),
        )
        if day
    ]
    hidden_author = parser.meta.get('author') or next(
        (name for name in _names(item.get('author')) if name.strip()), ''
    )
    checks = []
    in_meta = []
    for value in parser.robots_meta:
        in_meta += [(agent, directive) for agent, directive in _directives(value)]
    from_meta = _noindexed(in_meta)
    from_header = _noindexed(_directives(headers.get('x_robots_tag')))
    said = []
    for where, who in (
        ('its robots meta tag', from_meta),
        ('its X-Robots-Tag header', from_header),
    ):
        if who == 'all':
            said.append(
                'The page asks search engines and AI assistants not to index it, in ' + where + '.'
            )
        elif who:
            said.append(
                'The page asks ' + ' and '.join(who) + ' not to index it, in ' + where + '.'
            )
    checks.append(
        {
            'key': 'noindex',
            'status': 'problem' if said else 'ok',
            'said': ' '.join(said) + ' Those that respect it will leave the page out.'
            if said
            else 'Blog Studio didn’t find a noindex for search crawlers in the page’s robots '
            'meta tag or X-Robots-Tag header.',
        }
    )
    checks.append(
        {
            'key': 'login',
            'status': 'note' if parser.password else 'ok',
            'said': 'The post can be read without signing in, though the page also shows a '
            'sign-in form.'
            if parser.password
            else 'The post can be read without signing in.',
        }
    )
    checks.append(robots)
    if not items:
        checks.append(
            {
                'key': 'structured',
                'status': 'note',
                'said': 'Blog Studio didn’t find article structured data (JSON-LD) on the page'
                + (', and ' + str(unreadable) + ' block could not be read.' if unreadable else '.')
                + ' It is optional; when it is added it should match what the page shows.',
            }
        )
    else:
        disagree, agree = [], []
        headline = _ld_text(item.get('headline')) or _ld_text(item.get('name'))
        if headline:
            (agree if _same(headline, read['title']) else disagree).append(
                ('title', headline, read['title'])
            )
        names = [name.strip()[:300] for name in _names(item.get('author')) if name.strip()]
        if names and byline:
            matched = any(_same(name, byline) for name in names)
            (agree if matched else disagree).append(('author', ', '.join(names)[:300], byline))
        published = _day(_ld_text(item.get('datePublished')))
        if published and days:
            (agree if published in days else disagree).append(
                ('published date', published, ', '.join(days[:3]))
            )
        # An updated date is compared only when the page shows one: many sites keep
        # dateModified in their data without showing it, which is fine.
        modified = _day(_ld_text(item.get('dateModified')))
        if modified and updated:
            (agree if modified in updated else disagree).append(
                ('updated date', modified, ', '.join(updated[:3]))
            )
        lines = [
            'Its ' + field + ' is “' + data + '”, but the page shows “' + shown + '”.'
            for field, data, shown in disagree
        ]
        checks.append(
            {
                'key': 'structured',
                'status': 'problem' if disagree else 'ok',
                'said': (
                    'The page’s structured data (JSON-LD) does not agree with what it shows. '
                    + ' '.join(lines)
                    + ' Make them match.'
                )
                if disagree
                else 'The page’s structured data (JSON-LD) agrees with what it shows'
                + (' (' + ', '.join(field for field, _, _ in agree) + ').' if agree else '.'),
                'disagree': [
                    {'field': field, 'data': data, 'page': shown} for field, data, shown in disagree
                ],
            }
        )
    said, status = [], 'ok'
    if byline:
        said.append('The page shows its author (' + byline[:200] + ').')
    elif hidden_author:
        said.append(
            'Blog Studio didn’t find a byline on the page; its metadata names '
            + _clean(hidden_author)[:200]
            + ' as the author. Showing it helps readers and assistants judge the post.'
        )
        status = 'note'
    else:
        said.append('Blog Studio didn’t find an author byline on the page.')
        status = 'problem'
    if days:
        said.append('It shows a date (' + ', '.join(days[:2]) + ').')
    elif hidden_days:
        said.append(
            'Blog Studio didn’t find a date shown on the page; its metadata has '
            + hidden_days[0]
            + '.'
        )
        status = 'problem' if status == 'problem' else 'note'
    else:
        said.append('Blog Studio didn’t find a published or updated date.')
        status = 'problem'
    if said == [
        'Blog Studio didn’t find an author byline on the page.',
        'Blog Studio didn’t find a published or updated date.',
    ]:
        said = ['Blog Studio didn’t find an author byline or a published or updated date.']
    if status != 'ok':
        said.append('A visible author and date help readers and assistants judge the post.')
    checks.append(
        {
            'key': 'byline',
            'status': status,
            'said': ' '.join(said),
            'byline': byline or None,
            'dates': days[:4],
        }
    )
    return {'checks': checks, 'eligibility': ELIGIBILITY, 'site_owner': SITE_OWNER}


# robots.txt, read as RFC 9309 says and Google reads it, on every Python Blog Studio runs on:
# the group of the most specific product token (exact, case-insensitive), else `*`; of the
# rules that match the path, the longest wins and Allow wins a tie; `*` matches anything and
# a final `$` ends the path. urllib.robotparser before Python 3.14 takes the first match and
# has no wildcards, so it is not used.
ROBOTS_LINES = 5000
ROBOTS_RULES = 2000
ROBOTS_PATTERN = 2000


def robots_groups(text):
    """[{agents: [token, ...], rules: [(allow, pattern), ...]}] from a robots.txt."""
    groups, current, agents_open = [], None, False
    for raw in str(text or '').splitlines()[:ROBOTS_LINES]:
        line = raw.split('#', 1)[0].strip()
        if ':' not in line:
            continue
        key, value = (part.strip() for part in line.split(':', 1))
        key = key.lower()
        if key == 'user-agent':
            if current is None or not agents_open:
                current = {'agents': [], 'rules': []}
                groups.append(current)
            # The product token alone: "Googlebot/2.1" is googlebot.
            current['agents'].append(re.split(r'[/\s]', value, maxsplit=1)[0].lower())
            agents_open = True
        elif key in ('allow', 'disallow') and current is not None:
            agents_open = False
            if len(current['rules']) < ROBOTS_RULES:
                current['rules'].append((key == 'allow', robots_decoded(value[:ROBOTS_PATTERN])))
    return groups


PERCENT = re.compile(r'%([0-9A-Fa-f]{2})')


def robots_decoded(value):
    """A robots.txt path or rule with its percent-encoded unreserved characters decoded (as
    RFC 9309 compares them: %2D is -), and every other escape kept in one spelling."""

    def one(found):
        character = chr(int(found.group(1), 16))
        if re.fullmatch(r'[A-Za-z0-9._~-]', character):
            return character
        return '%' + found.group(1).upper()

    return PERCENT.sub(one, value)


def _robots_matches(pattern, path):
    """Whether a robots.txt path pattern matches: `*` any run of characters, a final `$` the
    end. Each literal part is found left to right, so it never backtracks."""
    anchored = pattern.endswith('$')
    if anchored:
        pattern = pattern[:-1]
    parts = pattern.split('*')
    if not path.startswith(parts[0]):
        return False
    at = len(parts[0])
    if len(parts) == 1:
        return at == len(path) if anchored else True
    for part in parts[1:-1]:
        found = path.find(part, at)
        if found < 0:
            return False
        at = found + len(part)
    last = parts[-1]
    if anchored:
        return len(path) - len(last) >= at and path.endswith(last)
    return path.find(last, at) >= 0


def robots_allowed(groups, agent, path):
    """Whether `agent` may fetch `path` (with its query) under these groups."""
    token = agent.lower()
    chosen = [group for group in groups if token in group['agents']]
    if not chosen:
        chosen = [group for group in groups if '*' in group['agents']]
    best = None  # (length, allow)
    for group in chosen:
        for allow, pattern in group['rules']:
            if not pattern or not _robots_matches(pattern, path):
                continue  # An empty Disallow allows everything; an empty Allow says nothing.
            length = len(pattern)
            if best is None or length > best[0] or (length == best[0] and allow):
                best = (length, allow)
    return best is None or best[1]


def robots_check(url, fetch=None):
    """What the site's robots.txt says about this page for search crawlers: one small fetch
    with a tight size and time limit. Missing or unreadable is "couldn't check"."""
    import blog_library
    import management

    fetch = fetch or blog_library.fetch
    parts = urlsplit(url)
    where = urlunsplit(('https', parts.netloc, '/robots.txt', '', ''))
    unknown = {
        'key': 'robots',
        'status': 'unknown',
        'said': 'Couldn’t check robots.txt: the site did not send a readable one. That is not '
        'a problem in itself.',
    }
    try:
        content, _, kind = fetch(
            where,
            management.LinkScope(url),
            deadline=time.monotonic() + ROBOTS_SECONDS,
            limit=ROBOTS_BYTES,
        )
        if kind and kind.split(';')[0].strip().lower() != 'text/plain':
            return unknown  # An HTML "not found" page is not a robots.txt.
        text = content.decode('utf-8-sig', 'replace')  # A byte order mark is not text.
        if re.match(r'\s*<(?:!doctype|html|head|body)\b', text, re.I):
            return unknown  # A web page sent as text, such as a "not found" page.
        groups = robots_groups(text)
    except (ValueError, OSError):
        return unknown
    path = robots_decoded((parts.path or '/') + ('?' + parts.query if parts.query else ''))
    blocked = [agent for agent, _ in SEARCH_AGENTS if not robots_allowed(groups, agent, path)]
    labels = [label + ' (' + agent + ')' for agent, label in SEARCH_AGENTS if agent in blocked]
    training = not robots_allowed(groups, TRAINING_AGENT, path)
    said = (
        'The site’s robots.txt blocks this page for ' + ', '.join(labels) + '. Those crawlers '
        'will not read it, so the post cannot appear in their results.'
        if blocked
        else 'The site’s robots.txt lets Google and the AI search crawlers (OAI-SearchBot, '
        'PerplexityBot) read this page.'
    )
    said += (
        ' It blocks GPTBot, which crawls only for training: a separate choice that does not '
        'affect search.'
        if training
        else ''
    )
    return {
        'key': 'robots',
        'status': 'problem' if blocked else 'ok',
        'said': said,
        'blocked': blocked,
        'training_blocked': training,
    }


def _text_page(text, base):
    """A page sent as text or Markdown: its words, kept as Markdown but with nothing that a
    download could run (no raw HTML, no link but http(s))."""
    text = safe_markdown(text.strip())
    title = plain(_clean(text.split('\n', 1)[0].lstrip('# ')))[:500] or parts_title(base)
    body = text if text.startswith('# ') else '# ' + _md(title) + '\n\n' + text
    return {
        'title': title,
        'markdown': body.rstrip() + '\n',
        'words': _words(text),
        'headings': [],
        'links': [],
        'images': [],
        'parser': Article(base, 'html'),
    }


def read(url, fetch=None):
    """Read a published post by its link: fetched once through the bounded fetcher, then its
    article extracted; and robots.txt, for Page access. Network: call it outside the lock.
    Refused plainly for a login, a type that is not a page, or a page too large."""
    import blog_library
    import management

    fetch = fetch or blog_library.fetch
    if not isinstance(url, str) or not re.fullmatch(r'https://\S{4,2000}', url.strip()):
        raise ValueError(BAD_LINK)
    url = url.strip()
    headers = {}
    try:
        content, final, kind = fetch(url, management.LinkScope(url), headers=headers)
    except ValueError as error:
        said = str(error)
        status = re.search(r'returned HTTP (\d{3})', said)
        if status:
            code = int(status.group(1))
            if code in (401, 407):
                raise ValueError(LOGIN) from None
            raise ValueError(
                (NOT_FOUND if code in (404, 410) else REFUSED).format(status=code)
            ) from None
        if said == blog_library.TOO_LARGE:
            raise ValueError(TOO_LARGE) from None
        raise ValueError(management.LINK_WORDS.get(said, said)) from None
    media = (kind or '').split(';')[0].strip().lower()
    if media in ('text/html', 'application/xhtml+xml'):
        found = article(content, final)
    elif media in ('text/plain', 'text/markdown'):
        found = _text_page(content.decode('utf-8', 'replace'), final)
    else:
        raise ValueError(NOT_A_PAGE.format(kind=media or 'of an unknown type'))
    parser = found['parser']
    if parser.password and found['words'] < WORDS_FOR_LOGIN:
        raise ValueError(LOGIN)
    if parser.full:
        raise ValueError(TOO_LONG)
    if found['words'] < 1:
        raise ValueError(NO_TEXT)
    if len(found['markdown']) > LIMIT:
        raise ValueError(TOO_LONG)
    page = access(found, headers, robots_check(final, fetch))
    found.pop('parser')
    return {**found, 'url': url, 'final_url': final, 'read_at': studio.now(), 'access': page}


def parts_title(url):
    parts = urlsplit(url)
    return (parts.netloc + parts.path).rstrip('/')[:500]


def library_copy(root, ident, location='local'):
    """What a post in a team collection (Import old blogs) keeps on this computer, read under
    the studio lock: its saved page or its saved text. Parsing it (from_copy) needs no lock.
    The collection's entry is only read, never changed."""
    import blog_library

    if not isinstance(ident, str) or location not in ('local', 'hub'):
        raise ValueError('Choose a post from a team collection.')
    local = blog_library.local_item(root, ident, location)
    directory, record = studio.item(root, 'sources', local)
    library = record.get('library') or {}
    if not library.get('historical') and not library.get('collections'):
        raise ValueError('Choose a post imported from one of your team collections.')
    original = record.get('original_path') or ''
    page = None
    if original.endswith(('.html', '.htm')) and (directory / original).is_file():
        page = (directory / original).read_bytes()[: blog_library.MAX_FETCH]
    text_path = directory / 'content.md'
    text = (
        text_path.read_text()[: 2 * LIMIT]
        if record.get('status') == 'ready' and text_path.is_file()
        else None
    )
    return {
        'page': page,
        'text': text,
        'name': record.get('name') or '',
        'url': library.get('canonical_url') or '',
        'retrieved_at': record.get('retrieved_at'),
        'collection_item': {'id': ident, 'location': location, 'source': local},
    }


def from_copy(copy):
    """A team collection post as the desk and a report read it, from library_copy."""
    found = None
    if copy['page'] is not None:
        found = article(copy['page'], copy['url'])
        if found.pop('parser').full:
            raise ValueError(TOO_LONG)
    if found is None or found['words'] < 1:
        if copy['text'] is None:
            raise ValueError('This post has no readable text saved yet.')
        title = _clean(copy['name'])[:500] or 'Imported post'
        found = _text_page('# ' + _md(title) + '\n\n' + _md(copy['text'].strip()), copy['url'])
        found.pop('parser')
    if len(found['markdown']) > LIMIT:
        raise ValueError(TOO_LONG)
    return {
        **found,
        'url': copy['url'],
        'final_url': copy['url'],
        'read_at': copy['retrieved_at'] or studio.now(),
        'collection_item': copy['collection_item'],
        'access': None,  # Saved earlier: no page access is checked from a saved copy.
    }


def from_library(root, ident, location='local'):
    """library_copy then from_copy, for a caller already holding the lock (tests)."""
    return from_copy(library_copy(root, ident, location))


# Staging: what was read waits here for the person to check, then start.
def _stage(root):
    folder = studio.inside(root, *STAGE)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _prune(folder):
    cutoff = time.time() - KEEP_SECONDS
    for path in folder.glob('*.json'):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            continue


def _summary(found):
    missing = [image for image in found.get('images') or [] if not image.get('alt')]
    return {
        'words': found.get('words', 0),
        'headings': len(found.get('headings') or []),
        'links': len(found.get('links') or []),
        'images': len(found.get('images') or []),
        'images_without_alt': len(missing),
    }


def stage(root, found):
    """Keep a read for the person to check; returns the preview the page shows."""
    import secrets

    folder = _stage(root)
    _prune(folder)
    token = secrets.token_hex(16)
    value = {'schema': 1, **found}
    studio.write_json(folder / (token + '.json'), value)
    return shown(token, value)


def shown(token, value):
    return {
        'status': 'preview',
        'preview': token,
        'expected': studio.digest(value['markdown'].encode())[:32],
        'title': value['title'],
        'content': value['markdown'],
        'url': value.get('url') or '',
        'final_url': value.get('final_url') or '',
        'read_at': value.get('read_at'),
        'collection_item': value.get('collection_item'),
        'summary': _summary(value),
        'access': value.get('access'),
    }


def staged(root, chosen):
    """A staged read the person checked: {preview, expected}, the same text as shown."""
    if (
        not isinstance(chosen, dict)
        or set(chosen) != {'preview', 'expected'}
        or not isinstance(chosen['preview'], str)
        or not re.fullmatch(r'[a-f0-9]{32}', chosen['preview'])
    ):
        raise ValueError('Read the page first, then start.')
    path = studio.inside(root, *STAGE, chosen['preview'] + '.json')
    if not path.is_file() or path.is_symlink():
        raise ValueError(STALE)
    value = studio.read_json(path)
    if studio.digest(value['markdown'].encode())[:32] != chosen['expected']:
        raise ValueError(CHANGED)
    return value


def origin(value):
    """What a post's record keeps about where its copy came from: the link, never the page."""
    kept = {
        'url': value.get('url') or '',
        'final_url': value.get('final_url') or '',
        'read_at': value.get('read_at'),
        'title': value.get('title'),
    }
    if value.get('collection_item'):
        kept['collection_item'] = {key: value['collection_item'][key] for key in ('id', 'location')}
    return kept
