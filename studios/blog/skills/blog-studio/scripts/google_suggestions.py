#!/usr/bin/env python3
"""Native Google review proposals. Exact anchors, fresh revisions, one submission."""

import argparse
import copy
import json
from pathlib import Path
import re
import sys

import studio
import google_roundtrip as rt
from google_drive import (
    Client,
    GoogleError,
    ReviewUnavailable,
    account_for,
    digest,
    discard,
    encoded,
    staging_path,
    write_new,
)
from hub_store import HubError, contained, locked, write_json

BUILD_KEYS = (
    'requests',
    'comments',
    'expected_sha256',
    'before_sha256',
    'targets',
    'expected_text_sha256',
    'before_text_sha256',
)
MONOSPACE = frozenset(
    (
        'courier new',
        'courier',
        'courier prime',
        'consolas',
        'roboto mono',
        'source code pro',
        'inconsolata',
        'menlo',
        'monaco',
        'jetbrains mono',
        'fira code',
        'fira mono',
        'ubuntu mono',
        'ibm plex mono',
        'space mono',
        'cousine',
        'anonymous pro',
        'pt mono',
        'dm mono',
    )
)


def document(client, file_id, **kwargs):
    value = client.native_read(file_id, **kwargs)
    if value.get('documentId') != file_id or not value.get('revisionId'):
        raise GoogleError('Google document identity or revision is unavailable.')
    return value


def review_read(client, file_id):
    value = document(client, file_id, inline=True, comments=True)
    if (
        value.get('commentsViewMode') != 'COMMENTS_VIEW_MODE_INCLUDED'
        or value.get('suggestionsViewMode') != 'SUGGESTIONS_INLINE'
    ):
        raise ReviewUnavailable(
            'Native Google review readback is unavailable; use readable review comments.'
        )
    if rt.suggestions(value) and not summary(value)['pending']:
        raise ReviewUnavailable(
            'Google did not list the pending suggestion threads; native review readback is unavailable.'
        )
    return value


def content(value):
    """Thread metadata is separate from manuscript text and formatting."""
    if isinstance(value, dict):
        threads = ('comments', 'suggestions', 'commentAnchors', 'commentsViewMode')
        return {key: content(child) for key, child in value.items() if key not in threads}
    if isinstance(value, list):
        return [content(child) for child in value]
    return value


def text_signature(value):
    """Every body character with its style, in order, and any other block as it is, leaving out
    paragraph properties: a split or merged paragraph compares by its text and its styles."""
    found = []
    for tab in rt.tabs(content(value)):
        native = rt.semantic(tab.get('documentTab', {}))
        for block in native.get('body', {}).get('content', []):
            if 'paragraph' in block:
                # A paragraph break's own style is left out, as are paragraph properties.
                found.extend(
                    {'char': '\n'} if element.get('char') == '\n' else element
                    for element in block['paragraph'].get('elements', [])
                )
            elif 'sectionBreak' not in block:
                found.append(block)
    return digest(encoded(found))


def signature(value):
    """Current-version formatting fingerprint: tab text, styles and structure, without titles or threads."""
    return rt.fingerprint(content(value))


def summary(value):
    threads = value.get('suggestions', [])
    return {
        'pending': sum(t.get('status') == 'OPEN' for t in threads),
        'accepted': sum(t.get('status') == 'ACCEPTED' for t in threads),
        'rejected': sum(t.get('status') == 'REJECTED' for t in threads),
        'unresolved_comments': sum(t.get('status') == 'OPEN' for t in value.get('comments', [])),
    }


def review_counts(client, file_id, inline):
    """Return (review document or None, counts, source).

    Thread counts are used when Google returns review threads. Otherwise pending
    suggestions are counted from inline markers, so a capture or status check
    never depends on comment readback.
    """
    try:
        review = review_read(client, file_id)
    except GoogleError:
        review = None
    if review is not None:
        if review['revisionId'] != inline['revisionId']:
            raise GoogleError('Google changed during the read. Read again.')
        return review, summary(review), 'threads'
    counts = {
        'pending': len(rt.suggestion_ids(inline)),
        'accepted': 0,
        'rejected': 0,
        'unresolved_comments': 0,
    }
    return None, counts, 'markers'


def escape(text):
    """Escape only the characters that would change how Markdown reads this text."""
    text = text.replace('\\', '\\\\').replace('`', '\\`').replace('*', '\\*')
    # Underscores inside a word are literal in Markdown; only edge underscores can start emphasis.
    text = re.sub(r'(?<![A-Za-z0-9])_|_(?![A-Za-z0-9])', r'\\_', text)
    text = text.replace('~~', '\\~\\~')
    text = re.sub(r'\](?=[(\[:])', r'\\]', text)
    text = re.sub(r'!(?=\[)', r'\\!', text)
    text = re.sub(r'<(?=[A-Za-z/!?])', r'\\<', text)
    return re.sub(r'&(?=#?[A-Za-z0-9]+;)', r'\\&', text)


def escape_line_start(line):
    """A paragraph that merely begins like a heading, quote, list item or rule stays a paragraph."""
    line = re.sub(r'^(\s*)(#{1,6})(?=\s|$)', lambda m: m[1] + '\\' + m[2], line)
    line = re.sub(r'^(\s*)>', r'\1\\>', line)
    line = re.sub(r'^(\s*\d+)([.)])(?=\s|$)', r'\1\\\2', line)
    line = re.sub(r'^(\s*)([-+])(?=\s|$)', r'\1\\\2', line)
    return re.sub(r'^(\s*)(-{3,}|={3,})(\s*)$', r'\1\\\2\3', line)


def run_features(style):
    """The parts of a text style that Markdown can say. Colour, size and font face stay in the DOCX."""
    link = style.get('link')
    url = None
    if link:
        url = link.get('url', '') if isinstance(link, dict) else ''
        if not url.startswith(('https://', 'http://', 'mailto:')) or any(
            c.isspace() or c in '<>' for c in url
        ):
            raise GoogleError('Review pull needs inspection of an unsupported link.')
    family = style.get('weightedFontFamily', {}).get('fontFamily', '').lower()
    script = {'SUPERSCRIPT': 'sup', 'SUBSCRIPT': 'sub'}.get(style.get('baselineOffset'))
    return (
        bool(style.get('bold')),
        bool(style.get('italic')),
        bool(style.get('strikethrough')),
        bool(style.get('underline')) and not url,
        script,
        family in MONOSPACE or family.endswith(' mono'),
        url,
    )


def render_run(plain, features, export=False):
    bold, italic, strike, underline, script, code, url = features
    # Markdown delimiters cannot include leading/trailing whitespace.
    leading = plain[: len(plain) - len(plain.lstrip())]
    trailing = plain[len(plain.rstrip()) :] if plain.strip() else ''
    core = plain.strip()
    if not core:
        return leading + trailing
    if code:
        fence = '``' if '`' in core else '`'
        text = fence + core + fence
    else:
        text = escape(core)
    if strike:
        text = '~~' + text + '~~'
    if bold:
        text = '**' + text + '**'
    if italic:
        text = '*' + text + '*'
    if underline:
        text = '<u>' + text + '</u>'
    if script:
        text = '<' + script + '>' + text + '</' + script + '>'
    if url:
        # Google's export writes a plain address; one with spaces or brackets is enclosed.
        plain_url = export and not any(c in url for c in ' ()<>')
        text = '[' + text + '](' + (url if plain_url else '<' + url + '>') + ')'
    return leading + text + trailing


class Objects:
    """What a lenient read of a Doc meets besides text: images numbered in document order with
    their data (keyed by object id, or a list by number), and footnotes in reference order."""

    def __init__(self, native, images):
        self.native = native
        self.images = images
        self.number = 0
        self.definitions = []
        self.footnotes = []

    def image(self, object_id):
        self.number += 1
        label = 'image' + str(self.number)
        found = (self.native.get('inlineObjects') or {}).get(object_id) or {}
        embedded = (found.get('inlineObjectProperties') or {}).get('embeddedObject') or {}
        alt = ' '.join(str(embedded.get('description') or embedded.get('title') or '').split())
        if isinstance(self.images, list):
            data = self.images[self.number - 1] if self.number <= len(self.images) else None
        else:
            data = (self.images or {}).get(object_id)
        if not data:
            # Kept visible where it was, so the reader sees an image was there.
            return (
                '!['
                + escape(alt or 'An image Blog Studio could not read from the Doc')
                + ']['
                + label
                + ']'
            )
        self.definitions.append('[' + label + ']: <' + data + '>')
        return '![' + escape(alt) + '][' + label + ']'

    def footnote(self, footnote_id):
        if footnote_id not in self.footnotes:
            self.footnotes.append(footnote_id)
        return '[^' + str(self.footnotes.index(footnote_id) + 1) + ']'


# What each kind of element in a Doc is called, for a message that names it.
NAMED = {
    'equation': 'an equation',
    'table': 'a table',
    'tableOfContents': 'a table of contents',
    'inlineObjectElement': 'an image',
    'richLink': 'a smart chip',
    'person': 'a person chip',
    'footnoteReference': 'a footnote',
    'horizontalRule': 'a horizontal line',
}


def _unreadable(kind):
    return GoogleError(
        'This Google Doc holds '
        + NAMED.get(kind, 'something (' + kind + ')')
        + ' that Blog Studio cannot read yet. Replace it with text or an image in the Doc, '
        'then read the Doc again.'
    )


def render_paragraph(paragraph, objects=None):
    """One paragraph's inline Markdown, before any heading or list prefix. Without `objects`
    only text is read and anything else refuses; with them, images, chips, breaks and
    footnote markers are read as Google's own export writes them."""
    elements = paragraph.get('elements', [])
    lenient = objects is not None
    if any('horizontalRule' in element for element in elements):
        rest = ''.join(
            e.get('textRun', {}).get('content', '') for e in elements if 'horizontalRule' not in e
        )
        if not rest.strip() and not any(
            set(e) - {'startIndex', 'endIndex', 'textRun', 'horizontalRule'} for e in elements
        ):
            return '---', True
        if not lenient:
            raise GoogleError(
                'Review pull cannot project embedded objects; use a scoped accepted-text conversion.'
            )
    plain = rt.paragraph_text(paragraph)
    if not lenient and any(c in plain.rstrip('\n') for c in ('\n', '\r', ' ', ' ')):
        raise GoogleError('Embedded line breaks need a scoped accepted-text conversion.')
    merged = []

    def add(text, features):
        if merged and merged[-1][1] == features and features is not None:
            merged[-1][0] += text
        else:
            merged.append([text, features])

    rule = False
    for element in elements:
        kinds = set(element) - {'startIndex', 'endIndex'}
        if kinds == {'textRun'}:
            run = element['textRun']
            add(run.get('content', ''), run_features(run.get('textStyle', {})))
            continue
        if not lenient:
            raise GoogleError(
                'Review pull cannot project embedded objects; use a scoped accepted-text conversion.'
            )
        kind = next(iter(kinds), '')
        value = element.get(kind) or {}
        if kind == 'inlineObjectElement':
            add(objects.image(value.get('inlineObjectId')), None)
        elif kind == 'richLink':
            props = value.get('richLinkProperties') or {}
            title, uri = str(props.get('title') or ''), str(props.get('uri') or '')
            if uri.startswith(('https://', 'http://')) and not any(
                c.isspace() or c in '<>()' for c in uri
            ):
                add('[' + escape(title or uri) + '](' + uri + ')', None)
            else:
                add(escape(title or uri), None)
        elif kind == 'person':
            props = value.get('personProperties') or {}
            add(escape(str(props.get('name') or props.get('email') or '')), None)
        elif kind == 'footnoteReference':
            add(objects.footnote(value.get('footnoteId')), None)
        elif kind in ('pageBreak', 'columnBreak', 'autoText'):
            continue  # A blog has no pages or columns, nor page numbers.
        elif kind == 'horizontalRule':
            rule = True
        else:
            raise _unreadable(kind)
    pieces = [
        render_run(text, features, lenient) if features is not None else text
        for text, features in merged
    ]
    line = ''.join(pieces).rstrip('\n')
    # A line break inside a paragraph (Shift+Enter) is a Markdown line break, as Google's
    # export writes it.
    lines = re.split('[\x0b\r  \n]', line)
    line = '  \n'.join([escape_line_start(lines[0]), *lines[1:]])
    if rule:
        line = (line.rstrip() + '\n\n---') if line.strip() else '---'
    return line, False


def _cell(cell, objects):
    texts = []
    for block in cell.get('content', []):
        if 'paragraph' not in block:
            raise _unreadable(next(iter(set(block) - {'startIndex', 'endIndex'}), 'table'))
        text, _ = render_paragraph(block['paragraph'], objects)
        texts.append(text.replace('  \n', ' ').replace('\n', ' '))
    return ' '.join(t for t in texts if t.strip()).replace('|', '\\|') or ' '


def _table(table, objects):
    """A table as a Markdown pipe table, its first row the header, as Google's export writes
    it."""
    rows = [
        '| ' + ' | '.join(_cell(cell, objects) for cell in row.get('tableCells', [])) + ' |'
        for row in table.get('tableRows', [])
    ]
    if not rows:
        return ''
    columns = len(table['tableRows'][0].get('tableCells', []))
    return '\n'.join([rows[0], '| ' + ' | '.join(['---'] * columns) + ' |', *rows[1:]])


def accepted_markdown(value, images=None):
    """The one Markdown projection of accepted text, used with or without pending suggestions.

    DOCX and native structure remain the formatting record. Without `images` this bounded
    renderer reads only text and raises on anything else, for Google's own export to stand
    in. With `images` (data URIs by inline object id, or a list by number) it reads what the
    export would: images as `![alt][imageN]` with their data defined at the end, numbered in
    document order, smart chips as their text or link, footnotes as Markdown footnotes and
    tables as pipe tables; page breaks, headers and footers are no part of a blog. Anything
    else is named in a plain message.
    """
    if rt.suggestions(value):
        raise GoogleError('A suggestions-excluded native preview is required.')
    selected = rt.tabs(value)
    if len(selected) != 1:
        raise GoogleError('Review snapshots require a single-tab document.')
    native = selected[0].get('documentTab', {})
    objects = None if images is None else Objects(native, images)
    if objects is None and any(native.get(k) for k in ('headers', 'footers', 'footnotes')):
        raise GoogleError(
            'Review pull needs a scoped native conversion for headers, footers or footnotes.'
        )
    output, listed = [], []
    counters = {}
    widths = {}
    for block in native.get('body', {}).get('content', []):
        if 'sectionBreak' in block:
            continue
        if objects is not None and 'table' in block:
            output.append(_table(block['table'], objects))
            listed.append(False)
            continue
        if objects is not None and 'tableOfContents' in block:
            continue  # Made by Google from the headings, which are read as they are.
        if 'paragraph' not in block:
            if objects is not None:
                raise _unreadable(next(iter(set(block) - {'startIndex', 'endIndex'}), 'block'))
            raise GoogleError(
                'Review pull cannot project this structure. Use a scoped accepted-text conversion; preserve DOCX.'
            )
        paragraph = block['paragraph']
        line, rule = render_paragraph(paragraph, objects)
        named = paragraph.get('paragraphStyle', {}).get('namedStyleType', 'NORMAL_TEXT')
        level = {'TITLE': 1, 'SUBTITLE': 2}.get(named)
        if named.startswith('HEADING_') and named[-1:] in '123456':
            level = int(named[-1])
        if level and not rule:
            line = '#' * level + ' ' + line
        bullet = paragraph.get('bullet')
        if bullet and not rule:
            line = list_prefix(native, bullet, counters, widths, objects is not None) + line
        output.append(line)
        listed.append(bool(bullet and not rule))
    if objects is not None:
        for number, footnote_id in enumerate(objects.footnotes, 1):
            found = (native.get('footnotes') or {}).get(footnote_id) or {}
            words = ' '.join(
                render_paragraph(block['paragraph'], objects)[0].replace('  \n', ' ')
                for block in found.get('content', [])
                if 'paragraph' in block
            ).strip()
            output.append('[^' + str(number) + ']: ' + (words or ' '))
            listed.append(False)
        output += objects.definitions
        listed += [False] * len(objects.definitions)
    result = ''
    if objects is None:
        result = '\n\n'.join(line for line in output if line.strip())
    else:
        # As Google's export writes them: list items one per line, each but the last ending in
        # a line break (two spaces); everything else a paragraph of its own.
        last = None
        for line, item in zip(output, listed, strict=True):
            if not line.strip():
                continue
            if last is not None:
                result += '  \n' if last and item else '\n\n'
            result += line
            last = item
    # Google's export ends without a final line break.
    result = result.rstrip() + ('' if objects is not None else '\n')
    if not result.strip():
        raise GoogleError('No accepted body text to pull.')
    return result.encode()


def image_data(client, value):
    """{inline object id: data URI} for every image a Doc view holds, read through the
    client; one Google does not send is left out, so the reader shows it as not read."""
    import base64

    found = {}
    for tab in rt.tabs(value):
        for object_id, item in (tab.get('documentTab', {}).get('inlineObjects') or {}).items():
            embedded = (item.get('inlineObjectProperties') or {}).get('embeddedObject') or {}
            uri = (embedded.get('imageProperties') or {}).get('contentUri')
            reader = getattr(client, 'image', None)
            if not uri or reader is None:
                continue
            try:
                data = reader(uri)
            except GoogleError:
                continue
            kind = (
                'png'
                if data.startswith(b'\x89PNG')
                else 'jpeg'
                if data.startswith(b'\xff\xd8')
                else 'gif'
                if data[:4] == b'GIF8'
                else 'webp'
                if data[:4] == b'RIFF' and data[8:12] == b'WEBP'
                else None
            )
            if kind:
                found[object_id] = (
                    'data:image/' + kind + ';base64,' + base64.b64encode(data).decode()
                )
    return found


def image_order(value):
    """The inline object ids of a Doc view's body, in document order."""
    found = []

    def walk(item):
        if isinstance(item, dict):
            if 'inlineObjectElement' in item:
                found.append(item['inlineObjectElement'].get('inlineObjectId'))
            for child in item.values():
                walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)

    for tab in rt.tabs(value):
        walk(tab.get('documentTab', {}).get('body', {}))
    return found


def images_in(markdown):
    """The image data a lenient read defined, by number: [data URI or None]."""
    found = {}
    for match in re.finditer(r'(?m)^\[image([0-9]+)\]: <(data:[^>]+)>$', markdown):
        found[int(match[1])] = match[2]
    return [found.get(number) for number in range(1, max(found, default=0) + 1)]


def list_prefix(native, bullet, counters, widths, export=False):
    """Bullet or running number for a list paragraph, indented under its parent item."""
    list_id = bullet.get('listId')
    depth = bullet.get('nestingLevel', 0)
    levels = (
        native.get('lists', {}).get(list_id, {}).get('listProperties', {}).get('nestingLevels', [])
    )
    if type(depth) is not int or not 0 <= depth < len(levels):
        raise GoogleError('List structure is unavailable for accepted-text projection.')
    shape = levels[depth]
    ordered = shape.get('glyphType') not in (
        None,
        'GLYPH_TYPE_UNSPECIFIED',
        'NONE',
    ) and not shape.get('glyphSymbol')
    for key in [k for k in counters if k[0] == list_id and k[1] > depth]:
        del counters[key]
    if ordered:
        start = shape.get('startNumber', 1)
        number = counters.get((list_id, depth), (start if type(start) is int else 1) - 1) + 1
        counters[(list_id, depth)] = number
        mark = str(number) + '. '
    else:
        mark = '* ' if export else '- '
    widths[(list_id, depth)] = len(mark)
    # Google's export indents each level four spaces.
    indent = (
        4 * depth if export else sum(widths.get((list_id, parent), 2) for parent in range(depth))
    )
    return ' ' * indent + mark


def linked(root, article_id, kind):
    """Review writes go only to the Doc this blog is linked to; an unlinked blog has no target."""
    directory, record = studio.item(root, 'articles', article_id)
    target = record.get('google', {}).get('baselines', {}).get(kind, {}).get('document')
    if not target:
        raise GoogleError(
            'Link the unedited manuscript to a Google Doc first, then propose the selected findings.'
        )
    return directory, record, target


def position(text, units):
    """Character position for a UTF-16 offset within a paragraph."""
    for count in range(len(text) + 1):
        if rt.utf16(text[:count]) == units:
            return count
    raise GoogleError('The anchor splits a character or is outside the paragraph.')


def quote_positions(document_value, selected_tabs, before, context=None, tab_id=None):
    """Every place an exact quote occurs in plain body paragraphs, as (tab, UTF-16 start)."""
    found = []
    for (tab, start), paragraph in rt.paragraphs(document_value).items():
        if tab not in selected_tabs or tab_id not in (None, tab):
            continue
        if any('textRun' not in element for element in paragraph.get('elements', [])):
            continue
        text = rt.paragraph_text(paragraph)[:-1]
        needle = context if context is not None else before
        offset = text.find(needle)
        while offset != -1:
            inner = offset + (context.find(before) if context is not None else 0)
            found.append((tab, start + rt.utf16(text[:inner])))
            offset = text.find(needle, offset + 1)
    return found


def locate(document_value, finding, selected_tabs):
    """Fill in tab_id and start_index from the finding's exact quote.

    The author's tool supplies words, not offsets: `before` alone when the quote is
    unique, otherwise with `context` (a longer exact snippet around it) or
    `occurrence` (1 for the first match in document order).
    """
    if not isinstance(finding, dict):
        raise GoogleError('Each finding needs id, kind, before, reason and optional after.')
    result = {k: v for k, v in finding.items() if k not in ('context', 'occurrence')}
    if type(finding.get('start_index')) is int and isinstance(finding.get('tab_id'), str):
        return result
    before, context, occurrence = (
        finding.get('before'),
        finding.get('context'),
        finding.get('occurrence'),
    )
    if not isinstance(before, str) or not before:
        raise GoogleError('Anchor findings to nonempty text within a body paragraph.')
    if context is not None and (not isinstance(context, str) or before not in context):
        raise GoogleError('context must be an exact snippet that contains the quoted text.')
    found = quote_positions(document_value, selected_tabs, before, context, finding.get('tab_id'))
    label = repr(before[:60])
    if not found:
        raise GoogleError(
            'The quoted text ' + label + ' is not in the current Google Doc. Pull the latest text '
            'and refresh this finding.'
        )
    if occurrence is not None:
        if type(occurrence) is not int or not 1 <= occurrence <= len(found):
            raise GoogleError(
                'occurrence must be between 1 and ' + str(len(found)) + ' for ' + label + '.'
            )
        found = [found[occurrence - 1]]
    if len(found) > 1:
        raise GoogleError(
            'The quoted text ' + label + ' appears ' + str(len(found)) + ' times. Add context '
            '(a longer exact snippet around it) or occurrence.'
        )
    result['tab_id'], result['start_index'] = found[0]
    return result


def trimmed(before, after):
    """How many characters a replacement shares with its quote at the start and at the end,
    each cut back so no word is split: only the words between are deleted and inserted, so a
    suggestion shows just what changes."""

    def splits(text, at):
        return 0 < at < len(text) and text[at - 1].isalnum() and text[at].isalnum()

    start = 0
    while start < min(len(before), len(after)) and before[start] == after[start]:
        start += 1
    while start and (splits(before, start) or splits(after, start)):
        start -= 1
    end = 0
    while end < min(len(before), len(after)) - start and before[-end - 1] == after[-end - 1]:
        end += 1
    while end and (splits(before, len(before) - end) or splits(after, len(after) - end)):
        end -= 1
    # Inserted text lands after the words deleted. Inside the quote it would sit within the
    # comment's range and change what it quotes, so text goes in only at the quote's very start
    # (nothing deleted before it) or at its end.
    inserted = after[start : len(after) - end]
    if inserted and end and (start or before[start : len(before) - end]):
        end = 0
    return start, end


def insertions(findings):
    """(tab, UTF-16 index, UTF-16 length) of the text each suggested edit inserts. Suggested
    deletions stay inline, so text is inserted after the words it replaces, at the quote's end
    or at its very start."""
    found = []
    for f in findings:
        if f.get('kind') != 'edit' or not f.get('after'):
            continue
        start, end = trimmed(f['before'], f['after'])
        text = f['after'][start : len(f['after']) - end]
        if text:
            at = f['start_index'] + rt.utf16(f['before'][: len(f['before']) - end])
            found.append((f['tab_id'], at, rt.utf16(text)))
    return found


LOOKS = ('bold', 'italic', 'underline', 'link')


def _looks(finding, keep_start, keep_end):
    """[(text, look)] for the text an edit inserts, from its `styles` ([[length, {bold,
    italic, underline, link}]] over its whole replacement), or None when it has none."""
    found = finding.get('styles')
    if found is None:
        return None
    after = finding['after']
    if (
        not isinstance(found, list)
        or any(
            not isinstance(run, list)
            or len(run) != 2
            or type(run[0]) is not int
            or run[0] < 1
            or not isinstance(run[1], dict)
            or set(run[1]) - set(LOOKS)
            or not isinstance(run[1].get('link') or '', str)
            for run in found
        )
        or sum(run[0] for run in found) != len(after)
    ):
        raise GoogleError('Give each run of a replacement its length and look.')
    each = [look for length, look in found for _ in range(length)]
    pieces = []
    for at in range(keep_start, len(after) - keep_end):
        if pieces and pieces[-1][1] == each[at]:
            pieces[-1][0] += after[at]
        else:
            pieces.append([after[at], each[at]])
    return [(text, look) for text, look in pieces]


def _restyled(style, look):
    """A Doc text style with the desk's bold, italic, underline and link: its font, size and
    colour stay as the words beside it have them."""
    result = copy.deepcopy(style)
    for key in ('bold', 'italic', 'underline'):
        if look.get(key):
            result[key] = True
        elif result.get(key):
            result[key] = False
    if look.get('link'):
        result['link'] = {'url': look['link']}
    else:
        result.pop('link', None)
    return result


def stretched(space, following):
    """Whether a space carries a link or bold that the words after it lack."""
    return bool(
        (space.get('link') and space.get('link') != following.get('link'))
        or (space.get('bold') and not following.get('bold'))
    )


def _next_is_paragraph(document_value, tab_id, end):
    """Whether a body paragraph starts where this one ends, so its break can be deleted."""
    return any(
        'paragraph' in block and block.get('startIndex') == end
        for block in _body(document_value, tab_id)
    )


def _kind_of(paragraph):
    """A paragraph's settings: its style (without its heading's own id) and its list."""
    style = {k: v for k, v in paragraph.get('paragraphStyle', {}).items() if k != 'headingId'}
    style.setdefault('namedStyleType', 'NORMAL_TEXT')
    return (encoded(style), encoded(paragraph.get('bullet') or {}))


def _previous_alike(document_value, tab_id, start, paragraph):
    """Whether a body paragraph with the same settings ends where this one starts: the last
    paragraph's own break cannot be deleted, so the one before it can be instead, and the
    paragraph before keeps its settings."""
    return any(
        'paragraph' in block
        and block.get('endIndex') == start
        and _kind_of(block['paragraph']) == _kind_of(paragraph)
        for block in _body(document_value, tab_id)
    )


def validate(document_value, findings, selected_tabs):
    """Check scope, exact quotes, overlaps and style boundaries. Returns one resolved item per finding."""
    if not isinstance(findings, list) or not 1 <= len(findings) <= 100:
        raise GoogleError('Select 1–100 proofreading findings.')
    required = {'id', 'tab_id', 'start_index', 'before', 'reason', 'kind'}
    ids = set()
    occupied = {}
    items = []
    foreign = rt.suggestions(document_value)
    for f in findings:
        if (
            not isinstance(f, dict)
            or set(f) - required - {'after', 'minor', 'remove', 'styles'}
            or required - set(f)
        ):
            raise GoogleError(
                'Each finding needs id, kind, tab_id, start_index, before, reason and optional after.'
            )
        if (
            not isinstance(f['id'], str)
            or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', f['id'])
            or f['id'] in ids
        ):
            raise GoogleError('Use unique stable finding IDs from the saved review.')
        if 'minor' in f and type(f['minor']) is not bool:
            raise GoogleError('minor must be true or false.')
        if 'remove' in f and (f['remove'] is not True or f['kind'] != 'edit' or f.get('after')):
            raise GoogleError('Only a deletion of a whole paragraph removes it.')
        ids.add(f['id'])
        marker = '[Blog Studio ' + f['id'] + ']'
        if any(
            marker in t.get('headPost', {}).get('content', '')
            for t in document_value.get('comments', [])
        ):
            raise GoogleError(
                'This finding already has a Google thread. Reconcile the existing review instead of reposting.'
            )
        if (
            f['kind'] not in ('edit', 'comment')
            or f['tab_id'] not in selected_tabs
            or type(f['start_index']) is not int
        ):
            raise GoogleError('Choose an edit/comment anchored in a selected tab.')
        if (
            not isinstance(f['before'], str)
            or not f['before']
            or any(ord(c) < 32 for c in f['before'])
        ):
            raise GoogleError('Anchor findings to nonempty text within a body paragraph.')
        if not isinstance(f['reason'], str) or not f['reason'].strip():
            raise GoogleError('Each finding needs a reason.')
        note = marker + ' ' + f['reason']
        if f['kind'] == 'edit':
            after = f.get('after')
            # A line break in the replacement starts a new paragraph, as a suggestion too.
            if (
                not isinstance(after, str)
                or any((ord(c) < 32 and c != '\n') or c in '  ' for c in after)
                or after == f['before']
            ):
                raise GoogleError(
                    'Provide a changed replacement, with a line break only between paragraphs '
                    '(empty means deletion).'
                )
        elif 'after' in f:
            raise GoogleError('Comments cannot also replace text.')
        (tab, start), paragraph = rt.paragraph_at(document_value, f['tab_id'], f['start_index'])
        if f['kind'] == 'comment':
            # A comment changes no words: it may sit beside an image or a chip, or in a
            # paragraph someone else's suggestion waits in, on words that are all plain text
            # no suggestion touches.
            text, quiet = _quiet_text(paragraph, start)
            a = position(text, f['start_index'] - start)
            b = a + len(f['before'])
            if text[a:b] != f['before'] or b >= len(text):
                if quote_positions(document_value, selected_tabs, f['before']):
                    raise GoogleError(
                        'That quote is not at the supplied start_index, although the Doc still '
                        'contains it. Leave out start_index (add context if the quote repeats) so '
                        'the helper locates it.'
                    )
                raise GoogleError(
                    'Google wording changed since review. Pull/reconcile and refresh this finding first.'
                )
            if not all(quiet[a:b]):
                raise GoogleError(
                    'A comment goes on plain words no suggestion touches; no proposal submitted.'
                )
            end = f['start_index'] + rt.utf16(f['before'])
            for left, right in occupied.setdefault(tab, []):
                if f['start_index'] < right and end > left:
                    raise GoogleError('Overlapping findings must be combined before submission.')
            occupied[tab].append((f['start_index'], end))
            if len(note.encode()) > 2048:
                raise GoogleError('Comment exceeds Google’s 2048-byte limit.')
            items.append(
                {
                    'finding': f,
                    'tab': tab,
                    'paragraph_start': start,
                    'a': a,
                    'b': b,
                    'end': end,
                    'style': None,
                    'note': note,
                    'cut': None,
                    'deleted': None,
                    'inserted': '',
                    'joined': False,
                }
            )
            continue
        # An edit goes by the Doc's own indexes, where an image or chip is one character and
        # someone else's pending suggestion keeps its place: it changes only plain words no
        # suggestion touches, and never goes inside their suggested insertion.
        text, quiet = _quiet_text(paragraph, start)
        a = position(text, f['start_index'] - start)
        b = a + len(f['before'])
        if text[a:b] != f['before'] or b >= len(text):
            if quote_positions(document_value, selected_tabs, f['before']):
                raise GoogleError(
                    'That quote is not at the supplied start_index, although the Doc still contains it. '
                    'Leave out start_index (add context if the quote repeats) so the helper locates it.'
                )
            raise GoogleError(
                'Google wording changed since review. Pull/reconcile and refresh this finding first.'
            )
        if not all(quiet[a:b]):
            raise GoogleError(
                'Those words are beside an image or chip, or under someone else’s pending '
                'suggestion, so they are not changed here; no proposal submitted.'
            )
        end = f['start_index'] + rt.utf16(f['before'])
        for left, right in occupied.setdefault(tab, []):
            if f['start_index'] < right and end > left:
                raise GoogleError('Overlapping findings must be combined before submission.')
        occupied[tab].append((f['start_index'], end))
        style, cut, inserted, joined, runs = None, None, '', False, []
        if f['kind'] == 'edit':
            keep_start, keep_end = trimmed(f['before'], f['after'])
            da, db = a + keep_start, b - keep_end
            inserted = f['after'][keep_start : len(f['after']) - keep_end]
            styles = [
                e['textRun'].get('textStyle', {}) if 'textRun' in e else {}
                for e in paragraph['elements']
                for _ in (e['textRun']['content'] if 'textRun' in e else '\ufffc')
            ]
            # Inserted text takes the style of the words it replaces, or of the word it follows.
            style = styles[da] if da < db else styles[max(a, da - 1)]
            if (
                da == db
                and a < da < len(text) - 1
                and text[da - 1].isspace()
                and stretched(styles[da - 1], styles[da])
            ):
                # A link or bold the Doc stretches over the space after its words stays there:
                # text after that space takes the style of the words it comes before.
                style = styles[da]
            looks = _looks(f, keep_start, keep_end)
            if inserted and looks is None and any(v != style for v in styles[da:db]):
                raise GoogleError('Split replacements at style or link boundaries.')
            # Each run of inserted text in its own look, over the style it takes from the Doc.
            runs = (
                [(inserted, style)]
                if looks is None
                else [(piece, _restyled(style, look)) for piece, look in looks]
            )
            cut = (start + rt.utf16(text[:da]), start + rt.utf16(text[:db]))
            if f.get('remove'):
                if text[:a].strip() or text[b:-1].strip():
                    raise GoogleError('A paragraph is removed only with all of its words.')
                da, db = 0, len(text) - 1
                joined = _next_is_paragraph(document_value, tab, start + rt.utf16(text))
                cut = (start, start + rt.utf16(text if joined else text[:-1]))
                if (
                    not joined
                    and not foreign
                    and _previous_alike(document_value, tab, start, paragraph)
                ):
                    # The Doc's last paragraph: the break before it goes with its words.
                    joined = 'previous'
                    cut = (start - 1, start + rt.utf16(text[:-1]))
                elif not joined:
                    note += ' The paragraph’s break stays, so an empty paragraph is left to remove.'
        if len(note.encode()) > 2048:
            raise GoogleError('Comment exceeds Google’s 2048-byte limit.')
        items.append(
            {
                'finding': f,
                'tab': tab,
                'paragraph_start': start,
                'a': a,
                'b': b,
                'end': end,
                'style': style,
                'note': note,
                'cut': cut,
                'deleted': (da, db) if f['kind'] == 'edit' else None,
                'inserted': inserted,
                'runs': runs,
                'joined': joined,
            }
        )
    for item in items:
        # The break before the last paragraph is not taken where another change in this plan
        # deletes it already: an empty paragraph is left instead, and said.
        if item['joined'] == 'previous' and any(
            other is not item
            and other['tab'] == item['tab']
            and other['cut']
            and other['cut'][0] < item['cut'][0] + 1 <= other['cut'][1]
            for other in items
        ):
            item['joined'] = False
            item['cut'] = (item['cut'][0] + 1, item['cut'][1])
            item['note'] += ' The paragraph’s break stays, so an empty paragraph is left to remove.'
            if len(item['note'].encode()) > 2048:
                raise GoogleError('Comment exceeds Google’s 2048-byte limit.')
        elif item['joined'] == 'previous':
            item['note'] += (
                ' The break before it goes too, so no empty paragraph is left; the paragraph '
                'before keeps its settings.'
            )
            if len(item['note'].encode()) > 2048:
                raise GoogleError('Comment exceeds Google’s 2048-byte limit.')
    return items


def _quiet_text(paragraph, start):
    """A paragraph's characters as Google indexes them (an object is one character) and, for
    each, whether it is plain text no suggestion touches."""
    chars, quiet = [], []
    offset = start
    for element in paragraph.get('elements', []):
        if element.get('startIndex') != offset:
            raise GoogleError(
                'Unsupported native run or inconsistent indexes; no proposal submitted.'
            )
        run = element.get('textRun')
        if run is None:
            chars.append('\ufffc')
            quiet.append(False)
        else:
            plain = not (
                run.get('suggestedInsertionIds') or run.get('suggestedDeletionIds')
            ) and not any(key.startswith('suggested') and value for key, value in run.items())
            chars.extend(run.get('content', ''))
            quiet.extend([plain] * len(run.get('content', '')))
        offset = element.get('endIndex', offset)
    return ''.join(chars), quiet


def _body(document_value, tab_id):
    for tab in rt.tabs(document_value):
        if tab['tabProperties']['tabId'] == tab_id:
            return tab.get('documentTab', {}).get('body', {}).get('content', [])
    return []


def build(document_value, findings, selected_tabs, accepted=None):
    """Suggest-mode requests plus the states that verification expects afterwards.

    document_value is the inline view, whose indexes are the document's real ones.
    accepted is the suggestions-excluded view; it may be left out only when
    nothing is pending. Paragraphs that already carry someone's pending
    suggestion are refused one by one; the rest of the Doc stays open for review.
    A replacement with a line break splits its paragraph, and a whole paragraph
    removed takes its break with it where Google allows.
    """
    foreign = rt.suggestions(document_value)
    if foreign and accepted is None:
        raise GoogleError(
            'Existing suggestions need review before another submission; pull accepted text and '
            'inspect pending items.'
        )
    accepted = document_value if accepted is None else accepted
    items = validate(document_value, findings, selected_tabs)
    expected = content(copy.deepcopy(document_value))
    paragraphs = rt.paragraphs(expected)
    requests = []
    comments = []
    changes = {}
    for item in items:
        f, tab, end = item['finding'], item['tab'], item['end']
        span = {'tabId': tab, 'startIndex': f['start_index'], 'endIndex': end}
        group = []
        comments.append(
            {'id': f['id'], 'content': item['note'], 'quote': f['before'], 'range': span}
        )
        if f['kind'] == 'edit':
            left, right = item['cut']
            if right > left:
                group.append(
                    {
                        'deleteContentRange': {
                            'range': {**span, 'startIndex': left, 'endIndex': right}
                        }
                    }
                )
            if item['inserted']:
                # Suggested deletions retain inline indexes. Insert AFTER the retained old range.
                at = right
                group.append(
                    {
                        'insertText': {
                            'location': {'tabId': tab, 'index': at},
                            'text': item['inserted'],
                        }
                    }
                )
                position = at
                for piece, look in item['runs']:
                    if not piece:
                        continue
                    group.append(
                        {
                            'updateTextStyle': {
                                'range': {
                                    'tabId': tab,
                                    'startIndex': position,
                                    'endIndex': position + rt.utf16(piece),
                                },
                                'textStyle': look,
                                'fields': '*',
                            }
                        }
                    )
                    position += rt.utf16(piece)
            changes.setdefault((tab, item['paragraph_start']), []).append(item)
        requests.append((tab, f['start_index'], group))
    targets = []
    structural = False
    merged = []
    for key, edits in changes.items():
        paragraph = paragraphs[key]
        # Each character with its style, the object it is (an image or chip is one), and
        # whether someone else's suggestion inserted it.
        theirs_ids = sorted(rt.suggestion_ids(paragraph))
        cells = []
        for e in paragraph['elements']:
            run = e.get('textRun')
            if run is None:
                value = {k: v for k, v in e.items() if k not in ('startIndex', 'endIndex')}
                inner = next(iter(value.values()), {}) if value else {}
                cells.append(
                    ('\ufffc', {}, value, bool((inner or {}).get('suggestedInsertionIds')))
                )
            else:
                theirs = bool(run.get('suggestedInsertionIds'))
                cells += [(c, run.get('textStyle', {}), None, theirs) for c in run['content']]
        original = ''.join(c for c, _, _, theirs in cells if not theirs)[:-1]
        chars = [(c, style) for c, style, _, _ in cells]
        removed = False
        for item in sorted(edits, key=lambda edit: edit['a'], reverse=True):
            da, db = item['deleted']
            if item['finding'].get('remove'):
                # Its break deleted, or the one before it (the same kind of paragraph): either
                # way the paragraph is gone. Otherwise an empty paragraph is left.
                removed = item['joined']
                chars = [] if removed is True else chars[-1:]
                cells = [] if removed is True else cells[-1:]
                structural = True
                continue
            chars[da:db] = [(c, look) for piece, look in item['runs'] for c in piece]
            cells[da:db] = [(c, look, None, False) for piece, look in item['runs'] for c in piece]
            structural = structural or '\n' in item['inserted']
        if len(chars) == 1 and not any(item['finding'].get('remove') for item in edits):
            raise GoogleError(
                'Deleting an entire paragraph is a structural edit; remove it as a whole paragraph '
                'or use a comment instead.'
            )
        # The accepted view: each line break ends a paragraph that keeps this one's style.
        pieces, current = [], []
        for cell in cells:
            current.append(cell)
            if cell[0] == '\n':
                pieces.append(current)
                current = []
        blocks = []
        for piece in pieces:
            copied = copy.deepcopy(paragraph)
            copied['elements'] = [
                copy.deepcopy(element)
                if element is not None
                else {'textRun': {'content': c, 'textStyle': style}}
                for c, style, element, _ in piece
            ]
            blocks.append({'paragraph': copied})
        body = _body(expected, key[0])
        at = next(i for i, block in enumerate(body) if block.get('paragraph') is paragraph)
        body[at : at + 1] = blocks
        if removed == 'previous':
            merged.append((key[0], blocks[0]))
        target = {
            'tab_id': key[0],
            'start_index': key[1],
            'before': original,
            # As the Doc's owner would see ours accepted and theirs still to decide.
            'after': ''.join(c for c, _, _, theirs in cells if not theirs)[:-1],
        }
        if theirs_ids:
            target['foreign'] = theirs_ids
        if removed:
            target['removed'] = removed
        targets.append(target)
    for tab, kept in merged:
        # The last paragraph's words and the break before it went: the paragraph before ends
        # at this one's break.
        body = _body(expected, tab)
        at = next(i for i, block in enumerate(body) if block is kept)
        elements = next(b for b in reversed(body[:at]) if 'paragraph' in b)['paragraph']['elements']
        run = elements[-1]['textRun']
        run['content'] = run['content'][:-1]
        if not run['content']:
            elements.pop()
    native_requests = [
        r
        for _, _, group in sorted(requests, key=lambda entry: entry[:2], reverse=True)
        for r in group
    ]
    for comment in comments:
        span = comment['range']
        comment['range'] = {
            **span,
            'startIndex': span['startIndex']
            + inserted_before(findings, span['tabId'], span['startIndex']),
            'endIndex': span['endIndex']
            + inserted_before(findings, span['tabId'], span['endIndex'], strict=True),
        }
        native_requests.append(
            {'insertComment': {'content': comment['content'], 'range': comment['range']}}
        )
    return {
        'requests': native_requests,
        'comments': comments,
        # With other people's suggestions pending, an accept-all view would include their changes too,
        # so the edited paragraphs are checked one by one instead (see targets_show). A paragraph
        # split or removed is checked the same way: its text, not Google's paragraph details.
        'expected_sha256': None if foreign or structural else signature(expected),
        'before_sha256': signature(accepted),
        # Split or removed paragraphs: every character and its style, in order, without the
        # paragraphs' own properties, which Google sets for a new paragraph its own way.
        'expected_text_sha256': text_signature(expected) if structural and not foreign else None,
        'before_text_sha256': text_signature(accepted) if structural and not foreign else None,
        'targets': sorted(targets, key=lambda target: (target['tab_id'], target['start_index'])),
    }


def inserted_before(findings, tab_id, index, strict=False):
    """UTF-16 units our suggested insertions add before an index (`strict`: an insertion at the
    index itself is after it). Suggested deletions stay inline."""
    return sum(
        length
        for tab, at, length in insertions(findings)
        if tab == tab_id and (at < index if strict else at <= index)
    )


def _cells_of(element):
    """(text, inserted ids, deleted ids) of one element: an image or chip is one character."""
    run = element.get('textRun')
    if run is not None:
        return (
            run.get('content', ''),
            set(run.get('suggestedInsertionIds') or []),
            set(run.get('suggestedDeletionIds') or []),
        )
    value = next((v for k, v in element.items() if k not in ('startIndex', 'endIndex')), {})
    value = value if isinstance(value, dict) else {}
    return (
        '\ufffc',
        set(value.get('suggestedInsertionIds') or []),
        set(value.get('suggestedDeletionIds') or []),
    )


def _runs_from(inline, tab_id, start):
    """The elements of the paragraph at `start` and of any paragraph a suggested line break
    split from it, as (text, inserted ids, deleted ids): up to the break it had before."""
    runs, going = [], False
    for block in _body(inline, tab_id):
        if 'paragraph' not in block:
            if going:
                return None
            continue
        if block.get('startIndex') == start:
            going = True
        if not going:
            continue
        found = [_cells_of(element) for element in block['paragraph'].get('elements', [])]
        if not found:
            return None
        runs += found
        text, inserted, _ = found[-1]
        if text.endswith('\n') and not inserted:
            return runs
    return runs if going else None


def targets_show(inline, saved, submitted):
    """Check the edited paragraphs directly in the inline view.

    submitted=True: each paragraph reads as its original text with every suggested insertion
    left out, and as the proposed text with our deletions and others' insertions left out
    (someone else's pending suggestions in it, named in the target, are theirs); a paragraph a
    suggested break splits is read on to the break it had before.
    submitted=False: each paragraph is untouched, proving nothing was sent.
    """
    for target in saved.get('targets', []):
        foreign = set(target.get('foreign') or [])
        shift = (
            inserted_before(saved['findings'], target['tab_id'], target['start_index'], strict=True)
            if submitted
            else 0
        )
        try:
            (_, start), paragraph = rt.paragraph_at(
                inline, target['tab_id'], target['start_index'] + shift
            )
        except GoogleError:
            return False
        if start != target['start_index'] + shift:
            return False
        if not submitted:
            found = [_cells_of(element) for element in paragraph.get('elements', [])]
            original = ''.join(text for text, inserted, _ in found if not inserted)
            if rt.suggestion_ids(paragraph) - foreign or original != target['before'] + '\n':
                return False
            continue
        runs = _runs_from(inline, target['tab_id'], start)
        if runs is None:
            return False
        original = ''.join(text for text, inserted, _ in runs if not inserted)
        proposed = ''.join(
            text
            for text, inserted, deleted in runs
            if not (inserted and inserted <= foreign) and not (deleted - foreign)
        )
        if original != target['before'] + '\n' or proposed != target['after'] + (
            '' if target.get('removed') is True else '\n'
        ):
            return False
    return True


def read_for_review(client, document_id, mode):
    """Return (inline view, accepted view, mode). Falls back to comment mode when threads are unavailable."""
    from google_review_comments import unavailable

    try:
        inline = review_read(client, document_id)
    except GoogleError as exc:
        if mode == 'native' or not unavailable(exc):
            raise
        inline = rt.inline_read(client, document_id)
        mode = 'comments'
    accepted = inline
    if rt.suggestions(inline):
        accepted = rt.accepted_read(client, document_id)
        if accepted['revisionId'] != inline['revisionId']:
            raise GoogleError('Google changed during the read. Read again.')
    return inline, accepted, mode


def plan(client, root, article_id, kind, findings, output, mode='auto'):
    """Read Google once, resolve the findings' anchors and save everything apply will need."""
    from google_review_comments import build as comment_build, next_number

    directory, record, target = linked(root, article_id, kind)
    draft = kind.upper() + '.md'
    local = studio.artifact_fingerprint(directory, draft)
    if not local:
        raise GoogleError('Save the local manuscript before preparing review suggestions.')
    baseline = record['google']['baselines'][kind]
    if mode not in ('auto', 'native', 'comments'):
        raise GoogleError('Choose auto, native or comments.')
    if isinstance(findings, dict) and isinstance(findings.get('findings'), list):
        findings = findings['findings']  # The saved review file works here unchanged.
    if not isinstance(findings, list) or not 1 <= len(findings) <= 100:
        raise GoogleError('Select 1–100 proofreading findings.')
    inline, accepted, mode = read_for_review(client, target['document_id'], mode)
    # The proofread Google baseline must still match, including formatting.
    observed = rt.fingerprint(content(accepted), target.get('format_version', 1))
    if not target.get('format_sha256') or observed != target['format_sha256']:
        raise GoogleError(
            'Pull the latest Google Doc and reconcile local changes before refreshing findings '
            'and planning suggestions.'
        )
    tab_ids = target['tab_ids']
    findings = [locate(inline, finding, tab_ids) for finding in findings]
    first = next_number(client, root, directory, target['document_id'], inline)
    result = {
        'schema': 1,
        'article': article_id,
        'kind': kind,
        'document_id': target['document_id'],
        'tab_ids': tab_ids,
        'revision_id': inline['revisionId'],
        'local_sha256': local,
        'baseline_sha256': digest(encoded(baseline)),
        'findings': findings,
        'mode': mode,
        'number_start': first,
        'comment_plan': comment_build(inline, findings, tab_ids, first),
        **build(inline, findings, tab_ids, accepted),
    }
    if local != studio.artifact_fingerprint(directory, draft):
        raise GoogleError('Local writing changed during planning.')
    write_new(output, encoded(result))
    unsent = local != baseline.get('local_sha256')
    step = 'Submit only these selected findings. The helper rereads Google and requires this exact revision.'
    if unsent:
        step += ' The local draft has unsent edits of its own; they are not part of this review.'
    return {
        'status': 'planned',
        'file': str(output),
        'findings': len(findings),
        'mode': mode,
        'local_draft_has_unsent_edits': unsent,
        'next_step': step,
    }


def ledger(root):
    return contained(root, '.google-review-operations')


def operation_key(saved):
    return digest(encoded(saved))


def marker_paths(store, saved):
    return [
        contained(store, digest(encoded([saved['document_id'], f['id']])) + '.finding')
        for f in saved['findings']
    ]


def keep_plan(store, saved):
    """Keep the plan beside its receipt so verification never depends on a staging file."""
    path = contained(store, operation_key(saved) + '.plan.json')
    if not path.exists():
        write_new(path, encoded(saved))
    return path


def release(root, saved, forget_plan=True):
    """Drop a reservation after proof that nothing reached Google. Call with the ledger lock held."""
    store = ledger(root)
    key = operation_key(saved)
    for path in marker_paths(store, saved):
        if path.is_file() and path.read_text() == key:
            path.unlink()
    contained(store, key + '.json').unlink(missing_ok=True)
    if forget_plan:
        contained(store, key + '.plan.json').unlink(missing_ok=True)


def receipt_status(receipt):
    return json.loads(receipt.read_text()).get('status') if receipt.is_file() else None


def apply_native(client, root, saved):
    """Submit the planned suggestions once, after proving nothing changed since planning."""
    from team_workspace import before

    before(root, saved['article'])
    directory, record, target = linked(root, saved['article'], saved['kind'])
    draft = saved['kind'].upper() + '.md'
    if (
        target['document_id'] != saved['document_id']
        or target['tab_ids'] != saved['tab_ids']
        or digest(encoded(record['google']['baselines'][saved['kind']])) != saved['baseline_sha256']
        or studio.artifact_fingerprint(directory, draft) != saved['local_sha256']
    ):
        raise GoogleError(
            'Local writing or transfer baseline changed. Pull/reconcile and refresh the review.'
        )
    store = ledger(root)
    key = operation_key(saved)
    with locked(store):
        receipt = contained(store, key + '.json')
        markers = marker_paths(store, saved)
        if receipt.exists() or any(mark.exists() for mark in markers):
            raise GoogleError(
                'These findings were already submitted or have an uncertain attempt. '
                'Use verify; do not resubmit.'
            )
        inline, accepted, _ = read_for_review(client, saved['document_id'], 'native')
        rebuilt = build(inline, saved['findings'], saved['tab_ids'], accepted)
        if inline['revisionId'] != saved['revision_id'] or rebuilt != {
            k: saved.get(k) for k in BUILD_KEYS
        }:
            raise GoogleError(
                'Google changed after planning. Pull/reconcile and refresh findings before sending.'
            )
        if studio.artifact_fingerprint(directory, draft) != saved['local_sha256']:
            raise GoogleError('Local writing changed during preflight.')
        reservation = {'operation': key, 'document_id': saved['document_id']}
        write_new(receipt, encoded({'status': 'submitting', **reservation}))
        for mark in markers:
            write_new(mark, key.encode())
        keep_plan(store, saved)
        try:
            response = client.native_review_update(
                saved['document_id'], saved['revision_id'], saved['requests']
            )
        except GoogleError as exc:
            if exc.review_unavailable and saved.get('mode') == 'auto':
                # Kept only long enough for the comment fallback to take over this reservation.
                write_json(receipt, {'status': 'native-rejected', **reservation})
            elif exc.definite:
                # Google refused the request, so nothing was written and the findings stay usable.
                release(root, saved)
                raise GoogleError(
                    str(exc) + ' Nothing was submitted and this attempt was released; refresh and '
                    'plan again.',
                    status=exc.status,
                    review_unavailable=exc.review_unavailable,
                    labels=exc.labels,
                ) from None
            raise
        write_json(
            receipt,
            {
                'status': 'submitted-unverified',
                **reservation,
                'comment_update_state': response.get('commentUpdateState'),
            },
        )
    return verify(client, root, saved)


def apply(client, root, saved, repost_missing=False):
    """Suggestions first; readable comments when Google definitely cannot take suggestions, or when asked."""
    from team_workspace import before

    before(root, saved['article'])
    from google_review_comments import apply as comments_apply, unavailable

    if saved.get('mode') == 'comments':
        return comments_apply(client, root, saved, repost_missing=repost_missing)
    receipt = contained(ledger(root), operation_key(saved) + '.json')
    if receipt.is_file() and json.loads(receipt.read_text()).get('backend'):
        # The comment fallback already owns this plan; a repeated apply resumes it.
        return comments_apply(client, root, saved, repost_missing=repost_missing)
    try:
        return apply_native(client, root, saved)
    except GoogleError as exc:
        if saved.get('mode') != 'auto' or not unavailable(exc):
            raise
        reserved = receipt.exists()
        if reserved and receipt_status(receipt) != 'native-rejected':
            raise
    try:
        return comments_apply(client, root, saved, reserved=reserved)
    except GoogleError:
        with locked(ledger(root)):
            # No comment was attempted, so the rejected native reservation must not strand the findings.
            if receipt_status(receipt) == 'native-rejected':
                release(root, saved)
        raise


def native_anchors(document_value):
    """Keep native anchor ranges scoped to their enclosing tab."""
    found = []

    def walk(value, tab_id=None):
        if isinstance(value, dict):
            if 'tabProperties' in value:
                tab_id = value['tabProperties'].get('tabId')
            if 'anchorId' in value and 'ranges' in value:
                ranges = []
                for original in value['ranges']:
                    if tab_id and original.get('tabId', tab_id) != tab_id:
                        continue
                    r = dict(original)
                    if tab_id:
                        r.setdefault('tabId', tab_id)
                    ranges.append(r)
                found.append({**value, 'ranges': ranges})
            for child in value.values():
                walk(child, tab_id)
        elif isinstance(value, list):
            for child in value:
                walk(child, tab_id)

    walk(document_value)
    return found


def quote_matches(actual, expected):
    # Google may trim ASCII boundary whitespace from plainTextQuote. This is only
    # used together with exact native ranges and unchanged comment content.
    trimmed = expected.strip(' \t\r\n')
    return actual == expected or (bool(trimmed) and actual == trimmed)


def verify(client, root, saved):
    """Read-only check of a native submission; also settles an attempt whose response never arrived."""
    path = contained(ledger(root), operation_key(saved) + '.json')
    if not path.is_file():
        raise GoogleError('No recorded attempt exists for this plan.')
    receipt = json.loads(path.read_text())
    if receipt.get('backend'):
        from google_review_comments import verify as comments_verify

        return comments_verify(client, root, saved)
    document_id = saved['document_id']
    inline = review_read(client, document_id)
    before = document(client, document_id)
    after = document(client, document_id, accepted_preview=True)
    again = review_read(client, document_id)
    stable = len({view['revisionId'] for view in (inline, before, after, again)}) == 1
    threads = inline.get('comments', [])
    anchors = native_anchors(inline)
    comments = []
    for expected in saved['comments']:
        found = [thread for thread in threads if thread_matches(thread, expected, anchors)]
        only = found[0] if len(found) == 1 else None
        comments.append(
            {
                'id': expected['id'],
                'verified': only is not None,
                'thread_id': only['commentId'] if only else None,
            }
        )
    wants_edits = any(finding['kind'] == 'edit' for finding in saved['findings'])
    unchanged = stable and signature(before) == saved['before_sha256']
    whole_doc = saved.get('expected_sha256')
    if whole_doc:
        proposed = signature(after) == whole_doc
    elif saved.get('expected_text_sha256'):
        proposed = text_signature(after) == saved['expected_text_sha256']
    else:
        proposed = targets_show(inline, saved, submitted=True)
    complete = (
        unchanged
        and proposed
        and all(comment['verified'] for comment in comments)
        and (not wants_edits or summary(inline)['pending'] > 0)
    )
    # A response that never arrived leaves no acknowledgement; complete readback then settles the outcome.
    # A recorded response that was anything but ALL_SAVED is never overridden by readback.
    ack = receipt.get('comment_update_state')
    unanswered = receipt.get('status') == 'submitting' and ack is None
    good = complete and (ack == 'ALL_SAVED' or unanswered)
    common = {
        'operation': operation_key(saved),
        'document_id': document_id,
        'revision_id': inline['revisionId'],
        'checked_at': studio.now(),
    }
    if unanswered and not good and unchanged and nothing_landed(saved, inline, after, threads):
        with locked(ledger(root)):
            release(root, saved)
        return {
            'status': 'not-submitted',
            **common,
            'accepted_text_unchanged': True,
            'next_step': 'Nothing reached Google, so this attempt was released. Plan again when ready; '
            'the same finding IDs can be reused.',
        }
    if good:
        step = 'Review proposals in Google Docs, then pull accepted changes.'
    else:
        step = 'Inspect Google and the original attempt. Do not retry or accept/reject anything automatically.'
    result = {
        'status': 'verified-pending' if good else 'needs-reconciliation',
        **common,
        'accepted_text_unchanged': unchanged,
        'acknowledgement': 'inferred-from-readback' if good and unanswered else ack,
        'comments': comments,
        'review_state': summary(inline),
        'next_step': step,
    }
    write_json(path, {**receipt, 'verification': result})
    return result


def thread_matches(thread, expected, anchors):
    """An open thread with exactly the planned text, quote and native anchor range."""
    if (
        thread.get('headPost', {}).get('content') != expected['content']
        or thread.get('status') != 'OPEN'
    ):
        return False
    if not quote_matches(thread.get('plainTextQuote'), expected['quote']):
        return False
    return any(
        anchor['anchorId'] == thread.get('anchorId')
        and any(all(r.get(k) == v for k, v in expected['range'].items()) for r in anchor['ranges'])
        for anchor in anchors
    )


def nothing_landed(saved, inline, after, threads):
    """True when readback proves the submission left no comment and no suggested change."""
    markers = ['[Blog Studio ' + f['id'] + ']' for f in saved['findings']]
    if any(
        marker in t.get('headPost', {}).get('content', '') for t in threads for marker in markers
    ):
        return False
    if saved.get('expected_sha256'):
        # Nothing was pending before, so an accept-all view equal to accepted text means nothing is pending now.
        return signature(after) == saved['before_sha256']
    if saved.get('before_text_sha256'):
        return text_signature(after) == saved['before_text_sha256']
    return targets_show(inline, saved, submitted=False)


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument(
        '--account', help='Defaults to the Google account remembered for this workspace.'
    )
    actions = parser.add_subparsers(dest='action', required=True)
    prepare = actions.add_parser('plan')
    prepare.add_argument('--id', required=True)
    prepare.add_argument('--kind', choices=('draft', 'outline'), default='draft')
    prepare.add_argument(
        '--findings',
        type=Path,
        required=True,
        help='JSON list of findings, or the saved review object with a findings list.',
    )
    prepare.add_argument(
        '--output', type=Path, help='New plan file; defaults to the workspace staging folder.'
    )
    prepare.add_argument('--mode', choices=('auto', 'native', 'comments'), default='auto')
    send = actions.add_parser('apply')
    send.add_argument('--plan', type=Path, required=True)
    send.add_argument(
        '--repost-missing',
        action='store_true',
        help='When resuming a comment batch: also post a comment whose earlier result was uncertain '
        'and which is still not visible in Google Docs.',
    )
    actions.add_parser('verify').add_argument('--plan', type=Path, required=True)
    actions.add_parser('show-review').add_argument('--id', required=True)
    edit = actions.add_parser('apply-edits')
    source = edit.add_mutually_exclusive_group(required=True)
    source.add_argument('--plan', type=Path)
    source.add_argument(
        '--id', help='Blog ID; edit numbers are unique per blog across review batches.'
    )
    edit.add_argument('--numbers', type=int, nargs='+', required=True)
    actions.add_parser('verify-edits').add_argument('--plan', type=Path, required=True)
    return parser


def settle_plan(root, plan_path, saved, result):
    """After a verified submission the ledger copy is the plan of record; drop the staged one."""
    kept = contained(ledger(root), operation_key(saved) + '.plan.json')
    if result.get('status') in ('verified-pending', 'verified-comments') and kept.is_file():
        result['plan'] = str(kept)
        discard(root, plan_path)
    return result


def run(args):
    import google_review_comments as comments

    root = args.root
    if not root.is_absolute():
        raise GoogleError('Use an absolute writing workspace.')
    client = Client(account_for(root, args.account))
    if args.action == 'plan':
        output = args.output or staging_path(root, 'review-plan', '.json')
        findings = json.loads(args.findings.read_text())
        return plan(client, root, args.id, args.kind, findings, output, args.mode)
    if args.action == 'show-review':
        return comments.show(root, args.id)
    if args.action == 'apply-edits' and args.id:
        return comments.apply_selected(client, root, args.id, args.numbers)
    saved = json.loads(args.plan.read_text())
    if args.action == 'apply-edits':
        return comments.apply_edits(client, root, saved, args.numbers)
    if args.action == 'verify-edits':
        return comments.verify_edits(client, root, saved)
    if args.action == 'apply':
        return settle_plan(root, args.plan, saved, apply(client, root, saved, args.repost_missing))
    return settle_plan(root, args.plan, saved, verify(client, root, saved))


def main():
    args = build_parser().parse_args()
    try:
        print(json.dumps(run(args), indent=2))
        return 0
    except GoogleError as exc:
        error = str(exc)
    except HubError as exc:
        error = (
            'The local review record is busy or unavailable: '
            + str(exc)
            + ' Try again shortly; if a '
            'submission was already under way, run verify before anything else.'
        )
    except FileNotFoundError:
        error = (
            'A named file or blog was not found. Check the path or ID; nothing was sent to Google.'
        )
    except (OSError, ValueError, KeyError, TypeError):
        error = (
            'Local input could not be used: check the blog ID, file paths and JSON. If a submission was '
            'already recorded for this plan, run verify rather than sending it again.'
        )
    print(json.dumps({'status': 'unavailable', 'error': error}), file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
