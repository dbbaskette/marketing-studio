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

BUILD_KEYS = ('requests', 'comments', 'expected_sha256', 'before_sha256', 'targets')
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


def render_run(plain, features):
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
        text = '[' + text + '](<' + url + '>)'
    return leading + text + trailing


def render_paragraph(paragraph):
    """One paragraph's inline Markdown, before any heading or list prefix."""
    elements = paragraph.get('elements', [])
    if any('horizontalRule' in element for element in elements):
        rest = ''.join(
            e.get('textRun', {}).get('content', '') for e in elements if 'horizontalRule' not in e
        )
        if rest.strip() or any(
            set(e) - {'startIndex', 'endIndex', 'textRun', 'horizontalRule'} for e in elements
        ):
            raise GoogleError(
                'Review pull cannot project embedded objects; use a scoped accepted-text conversion.'
            )
        return '---', True
    plain = rt.paragraph_text(paragraph)
    if any(c in plain.rstrip('\n') for c in ('\n', '\r', ' ', ' ')):
        raise GoogleError('Embedded line breaks need a scoped accepted-text conversion.')
    merged = []
    for element in elements:
        if set(element) - {'startIndex', 'endIndex', 'textRun'} or 'textRun' not in element:
            raise GoogleError(
                'Review pull cannot project embedded objects; use a scoped accepted-text conversion.'
            )
        run = element['textRun']
        features = run_features(run.get('textStyle', {}))
        if merged and merged[-1][1] == features:
            merged[-1][0] += run.get('content', '')
        else:
            merged.append([run.get('content', ''), features])
    line = ''.join(render_run(text, features) for text, features in merged).rstrip('\n')
    return escape_line_start(line), False


def accepted_markdown(value):
    """The one Markdown projection of accepted text, used with or without pending suggestions.

    DOCX and native structure remain the formatting record. Structures this bounded
    renderer cannot represent faithfully raise instead of being dropped.
    """
    if rt.suggestions(value):
        raise GoogleError('A suggestions-excluded native preview is required.')
    selected = rt.tabs(value)
    if len(selected) != 1:
        raise GoogleError('Review snapshots require a single-tab document.')
    native = selected[0].get('documentTab', {})
    if any(native.get(k) for k in ('headers', 'footers', 'footnotes')):
        raise GoogleError(
            'Review pull needs a scoped native conversion for headers, footers or footnotes.'
        )
    output = []
    counters = {}
    widths = {}
    for block in native.get('body', {}).get('content', []):
        if 'sectionBreak' in block:
            continue
        if 'paragraph' not in block:
            raise GoogleError(
                'Review pull cannot project this structure. Use a scoped accepted-text conversion; preserve DOCX.'
            )
        paragraph = block['paragraph']
        line, rule = render_paragraph(paragraph)
        named = paragraph.get('paragraphStyle', {}).get('namedStyleType', 'NORMAL_TEXT')
        level = {'TITLE': 1, 'SUBTITLE': 2}.get(named)
        if named.startswith('HEADING_') and named[-1:] in '123456':
            level = int(named[-1])
        if level and not rule:
            line = '#' * level + ' ' + line
        bullet = paragraph.get('bullet')
        if bullet and not rule:
            line = list_prefix(native, bullet, counters, widths) + line
        output.append(line)
    result = '\n\n'.join(output).rstrip() + '\n'
    if not result.strip():
        raise GoogleError('No accepted body text to pull.')
    return result.encode()


def list_prefix(native, bullet, counters, widths):
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
        mark = '- '
    widths[(list_id, depth)] = len(mark)
    indent = sum(widths.get((list_id, parent), 2) for parent in range(depth))
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


def validate(document_value, findings, selected_tabs):
    """Check scope, exact quotes, overlaps and style boundaries. Returns one resolved item per finding."""
    if not isinstance(findings, list) or not 1 <= len(findings) <= 100:
        raise GoogleError('Select 1–100 proofreading findings.')
    required = {'id', 'tab_id', 'start_index', 'before', 'reason', 'kind'}
    ids = set()
    occupied = {}
    items = []
    for f in findings:
        if not isinstance(f, dict) or set(f) - required - {'after', 'minor'} or required - set(f):
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
        if len(note.encode()) > 2048:
            raise GoogleError('Comment exceeds Google’s 2048-byte limit.')
        if f['kind'] == 'edit':
            after = f.get('after')
            if (
                not isinstance(after, str)
                or any(ord(c) < 32 or c in '  ' for c in after)
                or after == f['before']
            ):
                raise GoogleError(
                    'Provide a changed, single-paragraph replacement (empty means deletion).'
                )
        elif 'after' in f:
            raise GoogleError('Comments cannot also replace text.')
        (tab, start), paragraph = rt.paragraph_at(document_value, f['tab_id'], f['start_index'])
        if any(
            set(e) - {'startIndex', 'endIndex', 'textRun'} or 'textRun' not in e
            for e in paragraph['elements']
        ):
            raise GoogleError('Paragraph contains unsupported objects; no proposal submitted.')
        rt.require_settled(paragraph)
        text = rt.paragraph_text(paragraph)
        offset = start
        for element in paragraph['elements']:
            run = element['textRun']
            if (
                set(run) - {'content', 'textStyle'}
                or element.get('startIndex') != offset
                or element.get('endIndex') != offset + rt.utf16(run['content'])
            ):
                raise GoogleError(
                    'Unsupported native run or inconsistent indexes; no proposal submitted.'
                )
            offset = element['endIndex']
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
        end = f['start_index'] + rt.utf16(f['before'])
        for left, right in occupied.setdefault(tab, []):
            if f['start_index'] < right and end > left:
                raise GoogleError('Overlapping findings must be combined before submission.')
        occupied[tab].append((f['start_index'], end))
        style = None
        if f['kind'] == 'edit':
            styles = [
                e['textRun'].get('textStyle', {})
                for e in paragraph['elements']
                for _ in e['textRun']['content']
            ]
            style = styles[a]
            if any(v != style for v in styles[a:b]):
                raise GoogleError('Split replacements at style or link boundaries.')
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
            }
        )
    return items


def build(document_value, findings, selected_tabs, accepted=None):
    """Suggest-mode requests plus the states that verification expects afterwards.

    document_value is the inline view, whose indexes are the document's real ones.
    accepted is the suggestions-excluded view; it may be left out only when
    nothing is pending. Paragraphs that already carry someone's pending
    suggestion are refused one by one; the rest of the Doc stays open for review.
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
            group.append({'deleteContentRange': {'range': span}})
            if f['after']:
                # Suggested deletions retain inline indexes. Insert AFTER the retained old range.
                inserted = {'tabId': tab, 'startIndex': end, 'endIndex': end + rt.utf16(f['after'])}
                group.append(
                    {'insertText': {'location': {'tabId': tab, 'index': end}, 'text': f['after']}}
                )
                group.append(
                    {
                        'updateTextStyle': {
                            'range': inserted,
                            'textStyle': item['style'],
                            'fields': '*',
                        }
                    }
                )
            changes.setdefault((tab, item['paragraph_start']), []).append(
                (item['a'], item['b'], f['after'], item['style'])
            )
        requests.append((tab, f['start_index'], group))
    targets = []
    for key, edits in changes.items():
        paragraph = paragraphs[key]
        original = rt.paragraph_text(paragraph)[:-1]
        chars = [
            (c, e['textRun'].get('textStyle', {}))
            for e in paragraph['elements']
            for c in e['textRun']['content']
        ]
        for a, b, replacement, style in sorted(edits, key=lambda edit: edit[0], reverse=True):
            chars[a:b] = [(c, style) for c in replacement]
        if len(chars) == 1:
            raise GoogleError(
                'Deleting an entire paragraph is a structural edit; use a comment instead.'
            )
        paragraph['elements'] = [
            {'textRun': {'content': c, 'textStyle': style}} for c, style in chars
        ]
        targets.append(
            {
                'tab_id': key[0],
                'start_index': key[1],
                'before': original,
                'after': ''.join(c for c, _ in chars)[:-1],
            }
        )
    native_requests = [
        r
        for _, _, group in sorted(requests, key=lambda entry: entry[:2], reverse=True)
        for r in group
    ]
    for comment in comments:
        span = comment['range']
        shift = inserted_before(findings, span['tabId'], span['startIndex'])
        comment['range'] = {
            **span,
            'startIndex': span['startIndex'] + shift,
            'endIndex': span['endIndex'] + shift,
        }
        native_requests.append(
            {'insertComment': {'content': comment['content'], 'range': comment['range']}}
        )
    return {
        'requests': native_requests,
        'comments': comments,
        # With other people's suggestions pending, an accept-all view would include their changes too,
        # so the edited paragraphs are checked one by one instead (see targets_show).
        'expected_sha256': None if foreign else signature(expected),
        'before_sha256': signature(accepted),
        'targets': sorted(targets, key=lambda target: (target['tab_id'], target['start_index'])),
    }


def inserted_before(findings, tab_id, index):
    """UTF-16 units our suggested insertions add before an index. Suggested deletions stay inline."""
    return sum(
        rt.utf16(f['after'])
        for f in findings
        if f['kind'] == 'edit'
        and f['tab_id'] == tab_id
        and f['start_index'] + rt.utf16(f['before']) <= index
    )


def targets_show(inline, saved, submitted):
    """Check the edited paragraphs directly in the inline view.

    submitted=True: each paragraph reads as its original text with our insertions
    left out, and as the proposed text with our deletions left out.
    submitted=False: each paragraph is untouched, proving nothing was sent.
    """
    for target in saved.get('targets', []):
        shift = (
            inserted_before(saved['findings'], target['tab_id'], target['start_index'])
            if submitted
            else 0
        )
        try:
            (_, start), paragraph = rt.paragraph_at(
                inline, target['tab_id'], target['start_index'] + shift
            )
        except GoogleError:
            return False
        runs = [element.get('textRun') for element in paragraph.get('elements', [])]
        if start != target['start_index'] + shift or not all(runs):
            return False
        original = ''.join(run['content'] for run in runs if not run.get('suggestedInsertionIds'))
        proposed = ''.join(run['content'] for run in runs if not run.get('suggestedDeletionIds'))
        if not submitted and (rt.suggestions(paragraph) or original != target['before'] + '\n'):
            return False
        if submitted and (
            original != target['before'] + '\n' or proposed != target['after'] + '\n'
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
    proposed = (
        signature(after) == whole_doc if whole_doc else targets_show(inline, saved, submitted=True)
    )
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
