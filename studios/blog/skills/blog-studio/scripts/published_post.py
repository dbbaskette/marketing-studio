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
from urllib import robotparser
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


def _clean(text):
    return ' '.join(text.split())


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
        self.bylines, self.times = [], []
        self.marked = []  # (tag, kind) for an element whose class says byline or date

    # Blocks
    def flush(self):
        text = _clean(''.join(self.line))
        self.line = []
        if not text:
            return
        if self.lists:
            depth = len(self.lists) - 1
            mark = '- ' if self.lists[-1][0] == 'ul' else str(self.lists[-1][1]) + '. '
            text = '  ' * depth + mark + text
        if self.quote:
            text = '\n'.join('> ' * self.quote + line for line in text.split('\n'))
        if self.lists and self.blocks and self.blocks[-1][0] == 'item':
            self.blocks[-1][1].append(text)
        else:
            self.blocks.append(('item', [text]) if self.lists else ('text', [text]))

    def reading(self):
        return self.depth > 0 and not self.skip and not self.furniture

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
            self.stack.append(tag)
        if tag == self.region and not self.skip and not self.done:
            self.depth += 1
            self.entered = True
        if self.depth and (tag in SKIPPED or (self.region == 'body' and tag in PAGE_CHROME)):
            self.skip += 1
            if tag in VOID:
                self.skip -= 1
            return
        if not self.depth or self.skip:
            return
        hint = ' '.join([attrs.get('class', ''), attrs.get('id', ''), attrs.get('itemprop', '')])
        if tag == 'a' and 'author' in attrs.get('rel', '').lower():
            hint += ' author'
        # A byline or a date line is the page's furniture, read for Page access and left out
        # of the post's text; a whole region or section is never taken for one.
        holder = tag not in VOID and tag not in ('article', 'main', 'body', 'section', 'html')
        if tag == 'time':
            self.times.append(attrs.get('datetime', ''))
        if holder and BYLINE_HINT.search(hint):
            self.marked.append([tag, 'byline', len(self.stack), []])
            self.flush()
            self.furniture += 1
        elif holder and tag != 'time' and DATE_HINT.search(hint):
            self.marked.append([tag, 'date', len(self.stack), []])
            self.flush()
            self.furniture += 1
        if self.furniture:
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
        if tag in VOID or tag not in self.stack:
            return
        while self.stack:
            open_tag = self.stack.pop()
            self._close(open_tag)
            if open_tag == tag:
                break

    def _close(self, tag):
        level = len(self.stack) + 1
        for found in [m for m in self.marked if m[2] == level and m[0] == tag]:
            self.marked.remove(found)
            self.furniture = max(0, self.furniture - 1)
            text = _clean(''.join(found[3]))
            if text and len(text) <= 200:
                (self.bylines if found[1] == 'byline' else self.times).append(text)
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
            text = _clean(''.join(self.line))
            self.line = []
            if text:
                if self.heading == 1:
                    self.h1.append(text)
                self.blocks.append(('heading', [self.heading, text]))
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
                self.blocks.append(('code', [code]))
        elif tag in ('td', 'th') and self.table is not None:
            text = _clean(''.join(self.line))
            self.line = []
            if self.table:
                self.table[-1].append(_escape_table(text))
        elif tag == 'table' and self.table is not None:
            rows = [row for row in self.table if any(cell for cell in row)]
            self.table = None
            if rows:
                self.blocks.append(('table', rows))
        elif tag == 'a' and self.link is not None:
            href, words = self.link
            self.link = None
            text = _clean(''.join(words))
            if text and href:
                self.links.append({'url': href, 'text': text[:300]})
                self.line.append('[' + text.replace(']', '\\]') + '](' + href + ')')
            elif text:
                self.line.append(text)
        elif tag == 'code':
            self.line.append('`')
        elif tag in BLOCKS and self.table is None:
            self.flush()

    def handle_data(self, data):
        if self.in_title:
            self.title_tag += data
        if self.ld_text is not None:
            self.ld_text.append(data)
            return
        for found in self.marked:
            found[3].append(data)
        if not self.reading():
            return
        if self.pre is not None:
            self.pre.append(data)
        elif self.link is not None:
            self.link[1].append(data)
        else:
            self.line.append(data)

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
        if not source.startswith(('https://', 'http://')) or len(source) > 2000:
            return
        alt = _clean(attrs.get('alt', ''))[:300]
        self.images.append({'src': source, 'alt': alt})
        self.flush()
        image = '![' + alt.replace(']', '') + '](' + source.replace(' ', '%20') + ')'
        self.blocks.append(('text', [image]))

    def markdown(self, title):
        """The post as Markdown: its title, then each block, a blank line between."""
        self.flush()
        out, dropped = [], False
        for kind, value in self.blocks:
            if kind == 'heading':
                level, text = value
                if level == 1 and not dropped and text == title:
                    dropped = True  # The title heads the Markdown already.
                    continue
                out.append('#' * max(2, level) + ' ' + text)
            elif kind == 'code':
                out.append('```\n' + value[0] + '\n```')
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
        return ('# ' + title + '\n\n' + body).strip() + '\n'


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
        (parser.h1[0] if parser.h1 else '')
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
        'headings': [value[1] for kind, value in parser.blocks if kind == 'heading'][:200],
        'links': parser.links[:500],
        'images': parser.images[:200],
        'parser': parser,
    }


# Page access: advice only.
def _noindex(value):
    words = re.split(r'[\s,:;]+', (value or '').lower())
    return 'noindex' in words or 'none' in words


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


def _day(value):
    found = re.search(r'\d{4}-\d{2}-\d{2}', value or '')
    return found.group(0) if found else None


def _same(left, right):
    left, right = _clean(left).casefold().strip(' .'), _clean(right).casefold().strip(' .')
    return bool(left and right) and (left == right or left in right or right in left)


def access(read, headers, robots):
    """Page access, as the report says it: each check and what it found. Advice only."""
    parser = read['parser']
    byline = next((BY.sub('', text).strip() for text in parser.bylines if BY.sub('', text)), '')
    days = [day for day in (_day(value) for value in parser.times) if day]
    checks = []
    meta = any(_noindex(value) for value in parser.robots_meta)
    header = _noindex(headers.get('x_robots_tag'))
    where = [w for w, on in (('a robots meta tag', meta), ('an X-Robots-Tag header', header)) if on]
    checks.append(
        {
            'key': 'noindex',
            'status': 'problem' if where else 'ok',
            'said': 'The page asks not to be indexed, in ' + ' and '.join(where) + '. Search and '
            'AI assistants that respect it will leave the page out.'
            if where
            else 'The page does not ask to be left out of search (no noindex in its robots meta '
            'tag or X-Robots-Tag header).',
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
    items, unreadable = _ld_items(parser)
    if not items:
        checks.append(
            {
                'key': 'structured',
                'status': 'note',
                'said': 'The page has no article structured data (JSON-LD)'
                + (', and ' + str(unreadable) + ' block could not be read.' if unreadable else '.')
                + ' It is optional; when it is added it should match what the page shows.',
            }
        )
    else:
        item = items[0]
        disagree, agree = [], []
        headline = item.get('headline') or item.get('name')
        if isinstance(headline, str) and headline.strip():
            (agree if _same(headline, read['title']) else disagree).append(
                ('title', headline.strip()[:300], read['title'])
            )
        names = [name.strip() for name in _names(item.get('author')) if name.strip()]
        if names and byline:
            matched = any(_same(name, byline) for name in names)
            (agree if matched else disagree).append(('author', ', '.join(names)[:300], byline))
        for key, label in (('datePublished', 'published date'), ('dateModified', 'updated date')):
            day = _day(item.get(key) if isinstance(item.get(key), str) else '')
            if day and days:
                (agree if day in days else disagree).append((label, day, ', '.join(days)))
        said = []
        for field, data, shown in disagree:
            said.append('Its ' + field + ' is “' + data + '”, but the page shows “' + shown + '”.')
        checks.append(
            {
                'key': 'structured',
                'status': 'problem' if disagree else 'ok',
                'said': (
                    'The page’s structured data (JSON-LD) does not agree with what it shows. '
                    + ' '.join(said)
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
    missing = [
        w
        for w, have in (('an author byline', byline), ('a published or updated date', days))
        if not have
    ]
    checks.append(
        {
            'key': 'byline',
            'status': 'problem' if missing else 'ok',
            'said': 'The page shows no '
            + ' and no '.join(m.split(' ', 1)[1] for m in missing)
            + '. A visible author and date help readers and assistants judge the post.'
            if missing
            else 'The page shows its author ('
            + byline[:200]
            + ') and a date ('
            + ', '.join(days[:2])
            + ').',
            'byline': byline or None,
            'dates': days[:4],
        }
    )
    return {'checks': checks, 'eligibility': ELIGIBILITY, 'site_owner': SITE_OWNER}


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
        if kind and not kind.split(';')[0].strip().lower().startswith('text/'):
            return unknown
        lines = content.decode('utf-8', 'replace').splitlines()
    except (ValueError, OSError):
        return unknown
    rules = robotparser.RobotFileParser()
    rules.parse(lines)
    blocked = [
        label + ' (' + agent + ')'
        for agent, label in SEARCH_AGENTS
        if not rules.can_fetch(agent, url)
    ]
    training = not rules.can_fetch(TRAINING_AGENT, url)
    said = (
        'The site’s robots.txt blocks this page for ' + ', '.join(blocked) + '. Those crawlers '
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
        'blocked': [agent for agent, _ in SEARCH_AGENTS if not rules.can_fetch(agent, url)],
        'training_blocked': training,
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
        text = content.decode('utf-8', 'replace').strip()
        title = _clean(text.split('\n', 1)[0].lstrip('# '))[:500] or parts_title(final)
        body = text if text.startswith('# ') else '# ' + title + '\n\n' + text
        found = {
            'title': title,
            'markdown': body.rstrip() + '\n',
            'words': _words(text),
            'headings': [],
            'links': [],
            'images': [],
            'parser': Article(final, 'html'),
        }
    else:
        raise ValueError(NOT_A_PAGE.format(kind=media or 'of an unknown type'))
    parser = found['parser']
    if parser.password and found['words'] < WORDS_FOR_LOGIN:
        raise ValueError(LOGIN)
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


def from_library(root, ident, location='local'):
    """A post in a team collection (Import old blogs) as the desk and a report read it: its
    saved page read again from the copy kept on this computer, or its saved text. The
    collection's entry is only read, never changed."""
    import blog_library

    if not isinstance(ident, str) or location not in ('local', 'hub'):
        raise ValueError('Choose a post from a team collection.')
    local = blog_library.local_item(root, ident, location)
    directory, record = studio.item(root, 'sources', local)
    library = record.get('library') or {}
    if not library.get('historical') and not library.get('collections'):
        raise ValueError('Choose a post imported from one of your team collections.')
    url = library.get('canonical_url') or ''
    original = record.get('original_path') or ''
    found = None
    if original.endswith(('.html', '.htm')) and (directory / original).is_file():
        found = article((directory / original).read_bytes(), url)
        found.pop('parser')
    if found is None or found['words'] < 1:
        text_path = directory / 'content.md'
        if record.get('status') != 'ready' or not text_path.is_file():
            raise ValueError('This post has no readable text saved yet.')
        text = text_path.read_text().strip()
        title = _clean(record.get('name') or '')[:500] or 'Imported post'
        found = {
            'title': title,
            'markdown': ('# ' + title + '\n\n' + text).rstrip() + '\n',
            'words': _words(text),
            'headings': [],
            'links': [],
            'images': [],
        }
    if len(found['markdown']) > LIMIT:
        raise ValueError(TOO_LONG)
    return {
        **found,
        'url': url,
        'final_url': url,
        'read_at': record.get('retrieved_at') or studio.now(),
        'collection_item': {'id': ident, 'location': location, 'source': local},
        'access': None,  # Saved earlier: no page access is checked from a saved copy.
    }


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
