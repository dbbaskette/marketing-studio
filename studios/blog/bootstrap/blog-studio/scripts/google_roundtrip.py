#!/usr/bin/env python3
"""Private Google snapshots and guarded paragraph wording patches (no credentials stored)."""
import argparse
import copy
from datetime import datetime, timezone
import difflib
import json
from pathlib import Path
import sys

from google_drive import Client, GoogleError, digest, encoded, identifier, write_new


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
        return any((key.startswith('suggested') and bool(child)) or suggestions(child) for key, child in value.items())
    return isinstance(value, list) and any(suggestions(child) for child in value)


def clean_read(client, file_id):
    doc = client.native_read(file_id, inline=True)
    if doc.get('documentId') != file_id or not doc.get('revisionId'):
        raise GoogleError('A native document identity and revision are required.')
    if suggestions(doc):
        raise GoogleError('Pending suggestions need reconciliation before a formatted snapshot or wording patch. No suggestions were accepted.')
    return doc


def semantic(value):
    """Compare text/style per character, independent of provider run fragmentation."""
    if isinstance(value, dict):
        if 'elements' in value:  # Paragraph
            result = {k: semantic(v) for k, v in value.items() if k != 'elements'}
            items = []
            for element in value['elements']:
                if set(element) <= {'startIndex', 'endIndex', 'textRun'} and 'textRun' in element:
                    run = element['textRun']
                    items.extend({'char': c, 'style': run.get('textStyle', {})} for c in run['content'])
                else:
                    items.append(semantic(element))
            result['elements'] = items
            return result
        return {k: semantic(v) for k, v in value.items()
                if k not in ('startIndex', 'endIndex', 'revisionId', 'suggestionsViewMode', 'contentUri',
                             'comments', 'suggestions', 'commentAnchors', 'commentsViewMode')}
    if isinstance(value, list):
        return [semantic(v) for v in value]
    return value


def capture(client, file_id, tab_id, output, include_review=False):
    """Capture whole single-tab Doc, checking revision/version across both exports."""
    output = Path(output)
    if output.exists():
        raise GoogleError('Choose a new snapshot directory.')
    before = client.metadata(file_id)
    if include_review:
        from google_suggestions import review_read, document, summary, accepted_markdown
        doc = review_read(client, file_id)
        accepted = document(client, file_id)
        if accepted.get('suggestionsViewMode') != 'PREVIEW_WITHOUT_SUGGESTIONS':
            raise GoogleError('Accepted-text preview is unavailable; no snapshot saved.')
        if accepted['revisionId'] != doc['revisionId']:
            raise GoogleError('Google changed during review capture; reread.')
    else:
        doc = clean_read(client, file_id)
        accepted = doc
    selected = tabs(doc)
    if len(selected) != 1 or selected[0]['tabProperties']['tabId'] != tab_id:
        raise GoogleError('Markdown/DOCX exports cover a document. Automatic snapshots require a single-tab Doc so other tabs are not copied.')
    markdown = accepted_markdown(accepted) if include_review else client.export(file_id, 'md')
    word = client.export(file_id, 'docx')
    after_doc = review_read(client, file_id) if include_review else clean_read(client, file_id)
    after = client.metadata(file_id)
    if (not before.get('version') or before['version'] != after.get('version')
            or doc['revisionId'] != after_doc['revisionId']):
        raise GoogleError('Google changed during export. No snapshot saved; reread before retrying.')
    # Native structure is useful for fidelity inspection, but expiring image fetch URLs are not portable.
    native = copy.deepcopy(doc)
    def redact(value):
        if isinstance(value, dict):
            for key in list(value):
                if key == 'contentUri': del value[key]
                else: redact(value[key])
        elif isinstance(value, list):
            for child in value: redact(child)
    redact(native)
    files = {'document.md': markdown, 'document.docx': word, 'native.json': encoded(native)}
    if include_review:
        redact(accepted)
        files['accepted.json'] = encoded(accepted)
    stamp = datetime.now(timezone.utc).isoformat()
    meta = {'schema': 2 if include_review else 1, 'document_id': file_id, 'tab_ids': [tab_id],
            'revision_id': doc['revisionId'], 'drive_version': before['version'], 'observed_at': stamp,
            'content_sha256': digest(markdown), 'format_sha256': digest(encoded(semantic(accepted))),
            'files': {name: digest(data) for name, data in files.items()}}
    if include_review:
        meta['review_state'] = summary(doc)
    output.mkdir(mode=0o700)
    for name, data in files.items(): write_new(output / name, data)
    write_new(output / 'snapshot.json', encoded(meta))
    obs = {'schema': 1, 'document_id': file_id, 'url': 'https://docs.google.com/document/d/' + file_id + '/edit',
           'tab_ids': [tab_id], 'revision_id': doc['revisionId'], 'observed_at': stamp,
           'content_sha256': digest(markdown), 'format_sha256': meta['format_sha256'],
           'suggestions': 'none', 'structure_verified': False}
    if include_review:
        obs.update(suggestions='excluded', review_state=summary(doc))
    write_new(output / 'observation.json', encoded(obs))
    return {'status': 'captured-unreviewed', 'directory': str(output),
            'next_step': 'Inspect Markdown, native structure and DOCX fidelity. Use observation and document.md for compare/accept with --snapshot; confirm requires actual structure inspection.'}


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


def build_plan(document, edits):
    if not isinstance(edits, list) or not edits or len(edits) > 200:
        raise GoogleError('Supply 1–200 selected paragraph edits.')
    if suggestions(document):
        raise GoogleError('Reconcile suggestions before planning wording edits.')
    expected = copy.deepcopy(document)
    lookup = paragraphs(expected)
    seen = set(); requests = []
    for edit in sorted(edits, key=lambda e: (e['tab_id'], e['start_index']), reverse=True):
        if set(edit) != {'tab_id', 'start_index', 'before', 'after'}:
            raise GoogleError('Each edit needs tab_id, start_index, before and after only.')
        key = (edit['tab_id'], edit['start_index'])
        if key in seen or key not in lookup:
            raise GoogleError('Select each existing body paragraph at most once.')
        seen.add(key)
        paragraph = lookup[key]
        chars, styles = [], []
        offset = key[1]
        for element in paragraph['elements']:
            if set(element) - {'startIndex', 'endIndex', 'textRun'} or 'textRun' not in element:
                raise GoogleError('This paragraph includes objects or unsupported elements. Use a scoped native edit instead.')
            run = element['textRun']; text = run['content']
            if set(run) - {'content', 'textStyle'} or element['startIndex'] != offset or element['endIndex'] != offset + utf16(text):
                raise GoogleError('Unsupported run or inconsistent native indexes.')
            offset = element['endIndex']
            chars.extend(text); styles.extend([run.get('textStyle', {})] * len(text))
        text = ''.join(chars)
        before, after = edit['before'], edit['after']
        if not isinstance(after, str) or not after or any(ord(c) < 32 for c in after) or '\u2028' in after or '\u2029' in after:
            raise GoogleError('Wording patches require nonempty single-paragraph text; structural changes need a separate native edit.')
        if text != before + '\n' or '\n' in before:
            raise GoogleError('The paragraph changed or includes breaks. Reread before planning.')
        opcodes = difflib.SequenceMatcher(a=before, b=after, autojunk=False).get_opcodes()
        for tag, a, b, c, d in reversed(opcodes):
            if tag == 'equal': continue
            start, end = key[1] + utf16(before[:a]), key[1] + utf16(before[:b])
            replacement = after[c:d]
            chosen = styles[min(a, max(0, len(before) - 1))]
            if replacement and b > a and any(s != chosen for s in styles[a:b]):
                raise GoogleError('A replacement spans different text styles or links. Split the edit at style boundaries.')
            if b > a:
                requests.append({'deleteContentRange': {'range': {'tabId': key[0], 'startIndex': start, 'endIndex': end}}})
            if replacement:
                requests.append({'insertText': {'location': {'tabId': key[0], 'index': start}, 'text': replacement}})
                requests.append({'updateTextStyle': {'range': {'tabId': key[0], 'startIndex': start, 'endIndex': start + utf16(replacement)},
                                                    'textStyle': chosen, 'fields': '*'}})
            chars[a:b] = list(replacement)
            styles[a:b] = [chosen] * len(replacement)
        # Expected readback preserves every unchanged character's original style and all paragraph properties.
        paragraph['elements'] = [{'textRun': {'content': c, 'textStyle': s}} for c, s in zip(chars, styles)]
    if len(requests) > 900:
        raise GoogleError('Too many native operations; split into smaller reviewed patches.')
    return {'schema': 1, 'document_id': document['documentId'], 'revision_id': document['revisionId'],
            'edits': edits, 'requests': requests, 'expected_sha256': digest(encoded(semantic(expected)))}


def plan(client, file_id, edits, output):
    result = build_plan(clean_read(client, file_id), edits)
    write_new(output, encoded(result))
    return {'status': 'planned', 'file': str(output), 'paragraphs': len(edits), 'operations': len(result['requests'])}


def apply(client, saved, receipt):
    current = clean_read(client, saved['document_id'])
    if current['revisionId'] != saved['revision_id']:
        raise GoogleError('Document changed after planning. Reread and make a fresh plan.')
    rebuilt = build_plan(current, saved['edits'])
    if rebuilt != saved:
        raise GoogleError('Plan differs from the current native content; no write performed.')
    if not saved['requests']:
        return {'status': 'unchanged'}
    # Reserve before POST. Uncertain attempts are reconciled read-only, never resubmitted.
    write_new(receipt, encoded({'status': 'submitting', 'document_id': saved['document_id'],
                               'plan_sha256': digest(encoded(saved)), 'expected_sha256': saved['expected_sha256']}))
    client.native_update(saved['document_id'], saved['revision_id'], saved['requests'])
    return verify(client, saved)


def verify(client, saved):
    current = clean_read(client, saved['document_id'])
    matched = digest(encoded(semantic(current))) == saved['expected_sha256']
    return {'status': 'verified' if matched else 'written-unverified', 'document_id': saved['document_id'],
            'revision_id': current['revisionId'], 'text_and_format_verified': matched,
            'next_step': 'Capture fresh exports and confirm the prepared transfer.' if matched else 'Inspect current content and styles. Do not retry the write.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--account')
    commands = parser.add_subparsers(dest='action', required=True)
    p = commands.add_parser('capture'); p.add_argument('--file-id', required=True); p.add_argument('--tab-id', required=True); p.add_argument('--output', type=Path, required=True); p.add_argument('--include-review', action='store_true')
    p = commands.add_parser('plan'); p.add_argument('--file-id', required=True); p.add_argument('--edits', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    for action in ('apply', 'verify'):
        p = commands.add_parser(action); p.add_argument('--plan', type=Path, required=True)
        if action == 'apply': p.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    try:
        client = Client(args.account)
        if args.action == 'capture': result = capture(client, identifier(args.file_id), args.tab_id, args.output, args.include_review)
        elif args.action == 'plan': result = plan(client, identifier(args.file_id), json.loads(args.edits.read_text()), args.output)
        elif args.action == 'apply': result = apply(client, json.loads(args.plan.read_text()), args.receipt)
        else: result = verify(client, json.loads(args.plan.read_text()))
        print(json.dumps(result, indent=2)); return 0
    except GoogleError as exc:
        error = str(exc)
    except (OSError, ValueError, KeyError, TypeError):
        error = 'Invalid local input or output. Preserve existing receipts and reconcile uncertain writes.'
    print(json.dumps({'status': 'unavailable', 'error': error}), file=sys.stderr); return 1


if __name__ == '__main__':
    sys.exit(main())
