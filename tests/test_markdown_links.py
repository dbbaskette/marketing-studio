"""Every relative link and #anchor in the repository's Markdown resolves.

The pages checked are the tracked `.md` files under README.md, docs/ and studios/. A link
counts when it is a Markdown link or image (`[text](target)`, `![alt](target)`), a reference
definition (`[name]: target`) or an HTML `href`/`src`, outside fenced code, inline code and
HTML comments. Web addresses (any `scheme:`) are not followed. A relative target must name a
file or folder that exists; an `#anchor` on a Markdown page (the page itself when the target
is only `#anchor`) must name one of its headings, as GitHub makes them, or an `id`/`name`
the page sets.

Standard library only, and nothing is fetched. SKIPPED lists the pages not checked and
ALLOWED the archived pages whose links are kept as they were written; each says why.
"""
import re
import shutil
import subprocess
import unittest
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]

# Pages that are not checked at all, with the reason.
SKIPPED = {
    # Vendored upstream pages, kept byte for byte as their authors wrote them: their links
    # point into the upstream repositories, not into this one.
    'studios/blog/skills/blog-studio/references/upstream/':
        'vendored upstream pages, kept unchanged; their links name the upstream repository',
}

# Archived pages whose broken links are kept as written (history is not rewritten), with
# the reason. A link that broke only because its target moved is fixed instead.
ALLOWED = {
    'docs/archive/superpowers/plans/2026-10-22-phase-3-research-stop.md':
        'quotes, as an instruction, a link written for a Blog Studio module '
        '(blog-legacy-research.md beside blog-deep-research.md); it was never a link from this plan',
}

# Placeholder targets in examples (`url`, `[N]`, `path`) all sit in fenced or inline code,
# which is not read, so none needs a skip of its own.

FENCE = re.compile(r'^ {0,3}(`{3,}|~{3,})')
COMMENT = re.compile(r'<!--.*?-->', re.S)
CODE = re.compile(r'(`+)(?:(?!\1).)+?\1', re.S)
INLINE = re.compile(r'!?\[(?:[^\[\]]|\[[^\[\]]*\])*\]\(\s*(<[^>]*>|(?:[^()\s]|\([^()\s]*\))+)(?:\s+(?:"[^"]*"|\'[^\']*\'|\([^)]*\)))?\s*\)')
DEFINITION = re.compile(r'^ {0,3}\[[^\]]+\]:\s*(<[^>]*>|\S+)', re.M)
HTML = re.compile(r'<(?:a|img|source)\b[^>]*?\s(?:href|src)\s*=\s*["\']([^"\']*)["\']', re.I)
SCHEME = re.compile(r'^[A-Za-z][A-Za-z0-9+.-]*:')
HEADING = re.compile(r'^ {0,3}(#{1,6})[ \t]+(.*?)[ \t]*#*[ \t]*$')
SETEXT = re.compile(r'^ {0,3}(=+|-+)[ \t]*$')
NAMED = re.compile(r'<[a-z][^>]*?\s(?:id|name)\s*=\s*["\']([^"\']+)["\']', re.I)


def tracked_pages():
    listed = subprocess.run(['git', 'ls-files', '-z', '--', 'README.md', 'docs', 'studios'],
                            cwd=ROOT, check=True, capture_output=True).stdout.split(b'\0')
    names = sorted(name.decode('utf-8') for name in listed if name.endswith(b'.md'))
    return [name for name in names if not any(name.startswith(skip) for skip in SKIPPED)]


def prose(text):
    """The page with fenced code blanked, line for line, and HTML comments removed."""
    lines, fence = [], None
    for line in COMMENT.sub(lambda found: '\n' * found.group(0).count('\n'), text).splitlines():
        opened = FENCE.match(line)
        if fence:
            if opened and opened.group(1)[0] == fence[0] and len(opened.group(1)) >= len(fence):
                fence = None
            lines.append('')
        elif opened:
            fence = opened.group(1)
            lines.append('')
        else:
            lines.append(line)
    return lines


def links(text):
    """(line number, target) for each link on the page."""
    found = []
    lines = prose(text)
    for number, line in enumerate(lines, 1):
        line = CODE.sub(lambda code: ' ' * len(code.group(0)), line)
        for pattern in (INLINE, DEFINITION, HTML):
            for match in pattern.finditer(line):
                found.append((number, match.group(1)))
    return found


def slug(heading):
    """The anchor GitHub gives a heading's text."""
    text = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', heading)
    text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('`', '').replace('*', '')
    text = re.sub(r'(?<!\w)_+|_+(?!\w)', '', text)
    text = text.strip().lower()
    text = ''.join(ch for ch in text if ch.isalnum() or ch in ' -_')
    return text.replace(' ', '-')


def anchors(path):
    """Every anchor a Markdown page offers."""
    found, seen = set(), {}
    lines = prose(path.read_text(encoding='utf-8'))
    for index, line in enumerate(lines):
        heading = HEADING.match(line)
        text = heading.group(2) if heading else None
        if text is None and index and lines[index - 1].strip() and SETEXT.match(line) \
                and not HEADING.match(lines[index - 1]) and not lines[index - 1].lstrip().startswith(('|', '-', '*', '>')):
            text = lines[index - 1].strip()
        if text is not None:
            base = slug(text)
            count = seen.get(base, 0)
            seen[base] = count + 1
            found.add(base if not count else f'{base}-{count}')
        found.update(NAMED.findall(line))
    return found


def problems(name, cache):
    page = ROOT / name
    found = []
    for number, target in links(page.read_text(encoding='utf-8')):
        target = target.strip()
        if target.startswith('<') and target.endswith('>'):
            target = target[1:-1].strip()
        if not target or SCHEME.match(target) or target.startswith('//'):
            continue
        address, _, anchor = target.partition('#')
        address = unquote(address.split('?', 1)[0])
        if address.startswith('/'):
            found.append(f'{name}:{number}: {target} (a link from the root of a site, not a page here)')
            continue
        destination = (page.parent / address).resolve() if address else page
        if not destination.exists():
            found.append(f'{name}:{number}: {target} (no such file)')
            continue
        if anchor and destination.is_file() and destination.suffix == '.md':
            if destination not in cache:
                cache[destination] = anchors(destination)
            if unquote(anchor).lower() not in cache[destination]:
                found.append(f'{name}:{number}: {target} (no such heading)')
    return found


@unittest.skipUnless(shutil.which('git') and (ROOT / '.git').exists(),
                     'only a copy of the repository has its pages listed by git')
class MarkdownLinkTests(unittest.TestCase):
    def test_every_relative_link_and_anchor_resolves(self):
        cache, found = {}, []
        for name in tracked_pages():
            if name in ALLOWED:
                continue
            found += problems(name, cache)
        self.assertEqual(found, [], 'a Markdown link or anchor does not resolve')

    def test_every_skip_and_allowance_names_a_tracked_page(self):
        pages = set(tracked_pages())
        listed = subprocess.run(['git', 'ls-files', '--', *SKIPPED], cwd=ROOT, check=True,
                                capture_output=True, text=True).stdout.split()
        self.assertTrue(listed, 'a skipped folder no longer holds a tracked page')
        for name in ALLOWED:
            with self.subTest(page=name):
                self.assertIn(name, pages)
                self.assertTrue(problems(name, {}), 'an allowed page has no broken link left')

    def test_the_checker_finds_what_it_should(self):
        page = '# Top\n\n## A `code` heading\n\n## Top\n\n```\n[not](checked.md)\n```\n' \
               'See [here](#a-code-heading), [again](#top-1), `[not](here.md)` and [web](https://x.test).\n' \
               '[ref]: ./elsewhere.md\n<!-- [hidden](gone.md) -->\n'
        self.assertEqual([target for _, target in links(page)],
                         ['#a-code-heading', '#top-1', 'https://x.test', './elsewhere.md'])
        self.assertEqual(slug('Shared settings → Brand'), 'shared-settings--brand')
        self.assertEqual(slug('The `studio_core` part'), 'the-studio_core-part')


if __name__ == '__main__':
    unittest.main()
