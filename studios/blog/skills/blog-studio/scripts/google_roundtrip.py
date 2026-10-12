#!/usr/bin/env python3
"""Private Google snapshots and guarded paragraph wording patches (no credentials stored)."""

import argparse
import copy
from datetime import datetime, timezone
import difflib
import json
import os
from pathlib import Path
import sys
import uuid

from google_drive import (
    Client,
    GoogleError,
    account_for,
    digest,
    discard,
    encoded,
    identifier,
    require_linked,
    staging_path,
    staging_root,
    write_new,
)

# Markdown written by this package's own renderer, the same with or without pending suggestions.
PROJECTION = 'blog-studio/1'
# Google's Markdown export, used only when the renderer cannot represent a structure and nothing is pending.
EXPORT_PROJECTION = 'google-export'
# Version 2 covers tab content only. Version 1 also hashed the Doc and tab titles.
FORMAT_VERSION = 2


def tabs(document):
    result = []

    def walk(items):
        for tab in items:
            result.append(tab)
            walk(tab.get('childTabs', []))

    walk(document.get('tabs', []))
    if not result:
        raise GoogleError('Native tab content is required; reread with includeTabsContent.')
    return result


def suggestions(value):
    if isinstance(value, dict):
        return any(
            (key.startswith('suggested') and bool(child)) or suggestions(child)
            for key, child in value.items()
        )
    return isinstance(value, list) and any(suggestions(child) for child in value)


def suggestion_ids(value, found=None):
    """Distinct pending suggestion IDs from inline markers; needs no comment or thread readback."""
    found = set() if found is None else found
    if isinstance(value, dict):
        for key, child in value.items():
            if key.startswith('suggested') and child:
                if isinstance(child, dict):
                    found.update(str(name) for name in child)
                elif isinstance(child, list):
                    found.update(str(name) for name in child if isinstance(name, str))
            suggestion_ids(child, found)
    elif isinstance(value, list):
        for child in value:
            suggestion_ids(child, found)
    return found


def identified(document, file_id):
    if document.get('documentId') != file_id or not document.get('revisionId'):
        raise GoogleError('A native document identity and revision are required.')
    return document


def inline_read(client, file_id):
    """Current content with true indexes. Pending suggestions, if any, appear as inline markers."""
    return identified(client.native_read(file_id, inline=True), file_id)


def accepted_read(client, file_id):
    """Accepted text only: pending suggestions are left out and never accepted or rejected."""
    document = identified(client.native_read(file_id), file_id)
    if document.get('suggestionsViewMode') != 'PREVIEW_WITHOUT_SUGGESTIONS' or suggestions(
        document
    ):
        raise GoogleError(
            'Google did not return accepted text separately from pending suggestions. '
            'Nothing was saved and no suggestion was accepted.'
        )
    return document


def read_views(client, file_id):
    """Return (inline, accepted) at one revision. They are the same object when nothing is pending."""
    inline = inline_read(client, file_id)
    if not suggestions(inline):
        return inline, inline
    accepted = accepted_read(client, file_id)
    if accepted['revisionId'] != inline['revisionId']:
        raise GoogleError('Google changed during the read. Read again.')
    return inline, accepted


def semantic(value, _named=None):
    """Compare text/style per character, independent of provider run fragmentation."""
    if isinstance(value, dict):
        if 'namedStyles' in value:
            _named = {
                n.get('namedStyleType'): n.get('textStyle', {})
                for n in value['namedStyles'].get('styles', [])
            }
        if 'elements' in value:  # Paragraph
            result = {k: semantic(v, _named) for k, v in value.items() if k != 'elements'}
            inherited = dict((_named or {}).get('NORMAL_TEXT', {}))
            inherited.update(
                (_named or {}).get(
                    value.get('paragraphStyle', {}).get('namedStyleType', 'NORMAL_TEXT'), {}
                )
            )
            items = []
            for element in value['elements']:
                if set(element) <= {'startIndex', 'endIndex', 'textRun'} and 'textRun' in element:
                    run = element['textRun']
                    style = dict(run.get('textStyle', {}))
                    # Only normalize booleans with an observed inherited value. Unknown
                    # editor defaults and table inheritance stay representation-sensitive.
                    for key in ('italic', 'bold', 'underline', 'strikethrough'):
                        if (
                            type(inherited.get(key)) is bool
                            and type(style.get(key)) is bool
                            and style[key] == inherited[key]
                        ):
                            del style[key]
                    items.extend({'char': c, 'style': style} for c in run['content'])
                else:
                    items.append(semantic(element, _named))
            result['elements'] = items
            return result
        return {
            k: semantic(v, {} if k == 'table' else _named)
            for k, v in value.items()
            if k
            not in (
                'startIndex',
                'endIndex',
                'revisionId',
                'suggestionsViewMode',
                'contentUri',
                'comments',
                'suggestions',
                'commentAnchors',
                'commentsViewMode',
            )
        }
    if isinstance(value, list):
        return [semantic(v, _named) for v in value]
    return value


def fingerprint(document, version=FORMAT_VERSION):
    """Text, character styles and structure of the tabs' content.

    Version 2 leaves out the Doc title and tab titles, so renaming either is not a
    formatting change. Version 1 is kept so baselines saved by older runtimes still
    compare equal until the next accepted pull or confirmed handoff rewrites them.
    """
    if version == 1:
        return digest(encoded(semantic(document)))
    if version != FORMAT_VERSION:
        raise GoogleError('This formatting baseline needs a newer Blog Studio runtime.')
    return digest(
        encoded(
            [
                {
                    'tabId': tab['tabProperties']['tabId'],
                    'documentTab': semantic(tab.get('documentTab', {})),
                }
                for tab in tabs(document)
            ]
        )
    )


def structure(document):
    """A small inventory, so a capture can be checked without loading its files into context."""
    counts = dict.fromkeys(
        ('paragraphs', 'headings', 'list_items', 'links', 'tables', 'images', 'footnotes'), 0
    )
    for tab in tabs(document):
        native = tab.get('documentTab', {})
        counts['footnotes'] += len(native.get('footnotes', {}))
        for block in native.get('body', {}).get('content', []):
            if 'table' in block:
                counts['tables'] += 1
            paragraph = block.get('paragraph')
            if not paragraph:
                continue
            counts['paragraphs'] += 1
            named = paragraph.get('paragraphStyle', {}).get('namedStyleType', '')
            if named.startswith('HEADING_') or named in ('TITLE', 'SUBTITLE'):
                counts['headings'] += 1
            if paragraph.get('bullet'):
                counts['list_items'] += 1
            previous = None
            for element in paragraph.get('elements', []):
                if 'inlineObjectElement' in element:
                    counts['images'] += 1
                link = element.get('textRun', {}).get('textStyle', {}).get('link')
                if link and link != previous:
                    counts['links'] += 1
                previous = link
    return counts


def redacted(document):
    """A copy without expiring image-download URLs, which are neither portable nor needed."""
    value = copy.deepcopy(document)

    def strip(item):
        if isinstance(item, dict):
            item.pop('contentUri', None)
            for child in item.values():
                strip(child)
        elif isinstance(item, list):
            for child in item:
                strip(child)

    strip(value)
    return value


def capture(client, file_id, tab_id, output, include_review=False):
    """Capture a whole single-tab Doc at one revision.

    Accepted text comes from Google's suggestions-excluded view, so a teammate's
    pending suggestion never blocks a capture and is never accepted or rejected.
    Thread counts are added when Google returns them; inline markers are counted
    otherwise.
    """
    from google_suggestions import accepted_markdown, review_counts

    output = Path(output)
    if output.exists():
        raise GoogleError('Choose a new snapshot directory.')
    before = client.metadata(file_id)
    inline, accepted = read_views(client, file_id)
    pending = accepted is not inline
    selected = tabs(inline)
    only = selected[0]['tabProperties']['tabId'] if len(selected) == 1 else None
    if only is None or tab_id not in (None, only):
        raise GoogleError(
            'Markdown/DOCX exports cover a document. Automatic snapshots require a single-tab Doc '
            'so other tabs are not copied.'
        )
    native, review_state, threads = inline, None, None
    if pending or include_review:
        review, review_state, threads = review_counts(client, file_id, inline)
        native = review or inline
    try:
        markdown = accepted_markdown(accepted)
        projection = PROJECTION
    except GoogleError as exc:
        if pending:
            raise GoogleError(
                str(exc) + ' Suggestions are pending, so Google’s own export cannot stand in for '
                'accepted text. Local work is unchanged.'
            ) from None
        markdown = client.export(file_id, 'md')
        projection = EXPORT_PROJECTION
    word = client.export(file_id, 'docx')
    after_doc = inline_read(client, file_id)
    after = client.metadata(file_id)
    if (
        not before.get('version')
        or before['version'] != after.get('version')
        or inline['revisionId'] != after_doc['revisionId']
    ):
        raise GoogleError(
            'Google changed during export. No snapshot saved; reread before retrying.'
        )
    files = {
        'document.md': markdown,
        'document.docx': word,
        'native.json': encoded(redacted(native)),
    }
    if pending:
        files['accepted.json'] = encoded(redacted(accepted))
    stamp = datetime.now(timezone.utc).isoformat()
    shared = {
        'document_id': file_id,
        'tab_ids': [only],
        'revision_id': inline['revisionId'],
        'observed_at': stamp,
        'content_sha256': digest(markdown),
        'format_sha256': fingerprint(accepted),
        'format_version': FORMAT_VERSION,
        'legacy_format_sha256': fingerprint(accepted, 1),
        'projection': projection,
    }
    if review_state is not None:
        shared['review_state'] = review_state
    meta = {
        'schema': 3,
        **shared,
        'drive_version': before['version'],
        'structure': structure(accepted),
        'files': {name: digest(data) for name, data in files.items()},
    }
    if threads:
        meta['review_threads'] = threads
    observation = {
        'schema': 1,
        **shared,
        'url': 'https://docs.google.com/document/d/' + file_id + '/edit',
        'suggestions': 'excluded' if pending else 'none',
        'structure_verified': False,
    }
    output.mkdir(mode=0o700)
    for name, data in files.items():
        write_new(output / name, data)
    write_new(output / 'snapshot.json', encoded(meta))
    write_new(output / 'observation.json', encoded(observation))
    summary = {
        'projection': projection,
        'pending_suggestions': len(suggestion_ids(inline)),
        'review_threads': threads,
        'structure': meta['structure'],
    }
    step = (
        'Check this summary against what you expect of the Doc and read only the Markdown passages you need. '
        'Then set structure_verified in the observation when a start or handoff confirmation requires it, and '
        'pass --observation, --file and --snapshot to google compare / accept / start.'
    )
    if projection == EXPORT_PROJECTION:
        step = (
            'This Doc has structure the built-in renderer cannot represent, so the text is Google’s own '
            'Markdown export. ' + step
        )
    return {
        'status': 'captured-unreviewed',
        'directory': str(output),
        'observation': str(output / 'observation.json'),
        'markdown': str(output / 'document.md'),
        'summary': summary,
        'next_step': step,
    }


def utf16(text):
    return len(text.encode('utf-16-le')) // 2


def paragraphs(document):
    result = {}
    for tab in tabs(document):
        tab_id = tab['tabProperties']['tabId']
        # Wording patches intentionally operate on body paragraphs, not tables/footnotes.
        for block in tab.get('documentTab', {}).get('body', {}).get('content', []):
            if 'paragraph' in block:
                result[(tab_id, block['startIndex'])] = block['paragraph']
    return result


def paragraph_at(document, tab_id, index):
    for tab in tabs(document):
        if tab['tabProperties']['tabId'] != tab_id:
            continue
        for block in tab.get('documentTab', {}).get('body', {}).get('content', []):
            if 'paragraph' in block and block.get('startIndex', -1) <= index < block.get(
                'endIndex', -1
            ):
                return (tab_id, block['startIndex']), block['paragraph']
    raise GoogleError('Anchor is outside supported body paragraphs; use a scoped native review.')


def paragraph_text(paragraph):
    return ''.join(
        element.get('textRun', {}).get('content', '') for element in paragraph.get('elements', [])
    )


def require_settled(paragraph):
    """A passage with someone's pending suggestion is theirs to review first; other paragraphs stay editable."""
    if suggestions(paragraph):
        raise GoogleError(
            'That paragraph already has a pending suggestion. Review it in Google Docs first, '
            'or choose another passage; nothing was planned for it.'
        )


def neighbour_style(characters, styles, position, text):
    """Style for text inserted between two existing characters.

    New text continues the word it extends; otherwise it follows the character on
    its left, as typing would. A link is carried over only when both neighbours
    share it, so inserting next to a link never lengthens the link.
    """
    left_char = characters[position - 1] if position > 0 else ''
    right_char = characters[position] if position < len(characters) else ''
    continues_left = left_char.isalnum() and text[:1].isalnum()
    continues_right = right_char.isalnum() and text[-1:].isalnum()
    left = styles[position - 1] if position > 0 else None
    right = styles[position] if position < len(styles) else None
    if left is None or (continues_right and not continues_left):
        chosen, other = right, left
    else:
        chosen, other = left, right
    chosen = chosen or {}
    if chosen.get('link') and (other or {}).get('link') != chosen['link']:
        if other is not None and not other.get('link'):
            return other
        return {
            k: v for k, v in chosen.items() if k not in ('link', 'underline', 'foregroundColor')
        }
    return chosen


def resolve_edits(document, edits):
    """Fill in tab and paragraph offsets from the paragraph's exact current text."""
    if not isinstance(edits, list) or not edits or len(edits) > 200:
        raise GoogleError('Supply 1–200 selected paragraph edits.')
    lookup = paragraphs(document)
    resolved = []
    for edit in edits:
        if (
            not isinstance(edit, dict)
            or set(edit) - {'tab_id', 'start_index', 'before', 'after'}
            or not {'before', 'after'} <= set(edit)
            or not isinstance(edit['before'], str)
        ):
            raise GoogleError(
                'Each edit needs before and after, with optional tab_id and start_index.'
            )
        found = [
            key
            for key, paragraph in lookup.items()
            if edit.get('tab_id') in (None, key[0])
            and edit.get('start_index') in (None, key[1])
            and paragraph_text(paragraph) == edit['before'] + '\n'
        ]
        if len(found) > 1:
            raise GoogleError(
                'That paragraph text appears '
                + str(len(found))
                + ' times. Add start_index to choose one.'
            )
        if not found:
            raise GoogleError('The paragraph changed or includes breaks. Reread before planning.')
        resolved.append(
            {
                'tab_id': found[0][0],
                'start_index': found[0][1],
                'before': edit['before'],
                'after': edit['after'],
            }
        )
    return resolved


def build_plan(document, edits):
    edits = resolve_edits(document, edits)
    expected = copy.deepcopy(document)
    lookup = paragraphs(expected)
    seen = set()
    requests = []
    for edit in sorted(edits, key=lambda e: (e['tab_id'], e['start_index']), reverse=True):
        key = (edit['tab_id'], edit['start_index'])
        if key in seen or key not in lookup:
            raise GoogleError('Select each existing body paragraph at most once.')
        seen.add(key)
        paragraph = lookup[key]
        require_settled(paragraph)
        chars, styles = [], []
        offset = key[1]
        for element in paragraph['elements']:
            if set(element) - {'startIndex', 'endIndex', 'textRun'} or 'textRun' not in element:
                raise GoogleError(
                    'This paragraph includes objects or unsupported elements. Use a scoped native edit instead.'
                )
            run = element['textRun']
            text = run['content']
            if (
                set(run) - {'content', 'textStyle'}
                or element['startIndex'] != offset
                or element['endIndex'] != offset + utf16(text)
            ):
                raise GoogleError('Unsupported run or inconsistent native indexes.')
            offset = element['endIndex']
            chars.extend(text)
            styles.extend([run.get('textStyle', {})] * len(text))
        text = ''.join(chars)
        before, after = edit['before'], edit['after']
        if (
            not isinstance(after, str)
            or not after
            or any(ord(c) < 32 for c in after)
            or ' ' in after
            or ' ' in after
        ):
            raise GoogleError(
                'Wording patches require nonempty single-paragraph text; structural changes need a separate native edit.'
            )
        if text != before + '\n' or '\n' in before:
            raise GoogleError('The paragraph changed or includes breaks. Reread before planning.')
        # Neighbours are read from the paragraph as it is now, not from text this plan already inserted.
        original_chars, original_styles = list(chars), list(styles)
        opcodes = difflib.SequenceMatcher(a=before, b=after, autojunk=False).get_opcodes()
        for tag, a, b, c, d in reversed(opcodes):
            if tag == 'equal':
                continue
            start, end = key[1] + utf16(before[:a]), key[1] + utf16(before[:b])
            replacement = after[c:d]
            if b > a:
                chosen = original_styles[a]
                if replacement and any(s != chosen for s in original_styles[a:b]):
                    raise GoogleError(
                        'A replacement spans different text styles or links. Split the edit at style boundaries.'
                    )
                requests.append(
                    {
                        'deleteContentRange': {
                            'range': {'tabId': key[0], 'startIndex': start, 'endIndex': end}
                        }
                    }
                )
            else:
                chosen = neighbour_style(original_chars, original_styles, a, replacement)
            if replacement:
                requests.append(
                    {
                        'insertText': {
                            'location': {'tabId': key[0], 'index': start},
                            'text': replacement,
                        }
                    }
                )
                requests.append(
                    {
                        'updateTextStyle': {
                            'range': {
                                'tabId': key[0],
                                'startIndex': start,
                                'endIndex': start + utf16(replacement),
                            },
                            'textStyle': chosen,
                            'fields': '*',
                        }
                    }
                )
            chars[a:b] = list(replacement)
            styles[a:b] = [chosen] * len(replacement)
        # Expected readback preserves every unchanged character's original style and all paragraph properties.
        paragraph['elements'] = [
            {'textRun': {'content': c, 'textStyle': s}} for c, s in zip(chars, styles, strict=False)
        ]
    if len(requests) > 900:
        raise GoogleError('Too many native operations; split into smaller reviewed patches.')
    return {
        'schema': 1,
        'document_id': document['documentId'],
        'revision_id': document['revisionId'],
        'edits': edits,
        'requests': requests,
        'expected_sha256': fingerprint(expected),
    }


def plan(client, file_id, edits, output):
    result = build_plan(inline_read(client, file_id), edits)
    write_new(output, encoded(result))
    return {
        'status': 'planned',
        'file': str(output),
        'paragraphs': len(result['edits']),
        'operations': len(result['requests']),
    }


def record_outcome(receipt, value):
    """Replace the reserved receipt with the final outcome, atomically and privately."""
    receipt = Path(receipt)
    temp = receipt.with_name(receipt.name + '.' + uuid.uuid4().hex)
    try:
        write_new(temp, encoded(value))
        os.replace(temp, receipt)
    finally:
        temp.unlink(missing_ok=True)


def apply(client, saved, receipt):
    current = inline_read(client, saved['document_id'])
    if current['revisionId'] != saved['revision_id']:
        raise GoogleError('Document changed after planning. Reread and make a fresh plan.')
    rebuilt = build_plan(current, saved['edits'])
    if rebuilt != saved:
        raise GoogleError('Plan differs from the current native content; no write performed.')
    if not saved['requests']:
        return {'status': 'unchanged'}
    # Reserve before POST. Uncertain attempts are reconciled read-only, never resubmitted.
    reserved = {
        'status': 'submitting',
        'document_id': saved['document_id'],
        'plan_sha256': digest(encoded(saved)),
        'expected_sha256': saved['expected_sha256'],
    }
    write_new(receipt, encoded(reserved))
    try:
        client.native_update(saved['document_id'], saved['revision_id'], saved['requests'])
    except GoogleError as exc:
        if exc.definite:
            # Google refused the request, so nothing changed and the reservation can go.
            Path(receipt).unlink(missing_ok=True)
        raise
    result = verify(client, saved)
    try:
        record_outcome(
            receipt, {**reserved, 'status': result['status'], 'revision_id': result['revision_id']}
        )
    except OSError:
        pass  # The reserved receipt still blocks a repeat; the verified result below is what matters.
    return result


def verify(client, saved):
    current = inline_read(client, saved['document_id'])
    matched = fingerprint(current) == saved['expected_sha256']
    return {
        'status': 'verified' if matched else 'written-unverified',
        'document_id': saved['document_id'],
        'revision_id': current['revisionId'],
        'text_and_format_verified': matched,
        'next_step': 'Capture fresh exports and confirm the prepared transfer.'
        if matched
        else 'Inspect current content and styles. Do not retry the write.',
    }


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--account')
    parser.add_argument(
        '--root',
        type=Path,
        help='Writing workspace: its remembered Google account, private staging '
        'folder, and the linked Docs that writes are limited to.',
    )
    commands = parser.add_subparsers(dest='action', required=True)
    p = commands.add_parser('capture')
    p.add_argument('--file-id', required=True)
    p.add_argument('--tab-id', help='Optional; a single-tab Doc needs no tab ID.')
    p.add_argument(
        '--output',
        type=Path,
        help='New snapshot directory; defaults to the workspace staging folder.',
    )
    p.add_argument(
        '--include-review',
        action='store_true',
        help='Also record review thread counts when nothing is pending. '
        'Pending suggestions are detected automatically.',
    )
    p = commands.add_parser('plan')
    p.add_argument('--file-id', required=True)
    p.add_argument('--edits', type=Path, required=True)
    p.add_argument(
        '--output', type=Path, help='New plan file; defaults to the workspace staging folder.'
    )
    p.add_argument('--first-handoff', action='store_true')
    p = commands.add_parser('apply')
    p.add_argument('--plan', type=Path, required=True)
    p.add_argument(
        '--receipt', type=Path, help='New receipt file; defaults to the workspace staging folder.'
    )
    p.add_argument('--first-handoff', action='store_true')
    commands.add_parser('verify').add_argument('--plan', type=Path, required=True)
    return parser


def staged_default(args, value, prefix, suffix=''):
    if value:
        return value
    if not args.root:
        raise GoogleError(
            'Pass --root <workspace> so this goes to its private staging folder, or name a new path.'
        )
    return staging_path(args.root, prefix, suffix)


def run(args):
    client = Client(account_for(args.root, args.account))
    if args.action == 'capture':
        output = staged_default(args, args.output, 'capture')
        return capture(client, identifier(args.file_id), args.tab_id, output, args.include_review)
    if args.action == 'plan':
        require_linked(args.root, args.file_id, args.first_handoff)
        edits = json.loads(args.edits.read_text())
        return plan(
            client,
            identifier(args.file_id),
            edits,
            staged_default(args, args.output, 'patch-plan', '.json'),
        )
    saved = json.loads(args.plan.read_text())
    if args.action == 'apply':
        require_linked(args.root, saved['document_id'], args.first_handoff)
        receipt = args.receipt or plan_receipt(args, saved)
        try:
            result = apply(client, saved, receipt)
        except FileExistsError:
            raise GoogleError(
                'This plan already has a receipt (' + str(receipt) + '), so an earlier apply was '
                'attempted. Run verify; a plan is never applied twice.'
            ) from None
        if result['status'] == 'verified':
            discard(
                args.root, args.plan
            )  # Only a plan that sits in staging; the receipt stays as the record.
        return result
    return verify(client, saved)


def plan_receipt(args, saved):
    """One staged receipt per plan, so a repeated apply of the same plan is always stopped."""
    if not args.root:
        raise GoogleError(
            'Pass --root <workspace> so the receipt goes to its private staging folder, or name a new path.'
        )
    return staging_root(args.root, create=True) / (
        'patch-receipt-' + digest(encoded(saved))[:16] + '.json'
    )


def main():
    args = build_parser().parse_args()
    try:
        print(json.dumps(run(args), indent=2))
        return 0
    except GoogleError as exc:
        error = str(exc)
    except (OSError, ValueError, KeyError, TypeError):
        error = (
            'Local input or output failed: check the file paths and JSON, and use a new output path. '
            'This step sent nothing new to Google; keep any existing receipt.'
        )
    print(json.dumps({'status': 'unavailable', 'error': error}), file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
