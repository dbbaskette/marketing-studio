"""Report-only manuscript readiness checks; no network, rewrite or publication."""

import re
from urllib.parse import urlsplit

import studio


def report(root, ident, title_limit=80):
    if type(title_limit) is not int or not 20 <= title_limit <= 300:
        raise ValueError('Choose a title limit from 20 to 300 characters.')
    directory, record = studio.item(root, 'articles', ident)
    file = directory / 'DRAFT.md'
    if not file.is_file():
        raise ValueError('Save a manuscript before checking readiness.')
    body = file.read_text()
    findings, previous, titles, fenced = [], 0, 0, False

    def finding(line, code, detail):
        findings.append({'line': line, 'code': code, 'detail': detail})

    if len(record.get('title', '')) > title_limit:
        finding(
            1,
            'title-length',
            f'The working title exceeds the chosen {title_limit}-character limit.',
        )
    # Labels a reference may name: link and image definitions, as a Google Doc's Markdown
    # export defines each image with its data at the end.
    defined = {
        ' '.join(found[1].split()).casefold()
        for found in re.finditer(r'(?m)^ {0,3}\[([^\]\n]+)\]:[ \t]*\S', body)
    }
    for number, line in enumerate(body.splitlines(), 1):
        if re.match(r'^\s*(```|~~~)', line):
            fenced = not fenced
            continue
        if fenced:
            continue
        if re.match(r'^ {0,3}\[[^\]\n]+\]:[ \t]*\S', line):
            continue  # A definition: its target, such as an image's data, is not prose.
        for image in re.finditer(r'!\[([^\]\n]*)\]\[([^\]\n]*)\]', line):
            if not image[1].strip():
                finding(number, 'image-alt', 'An image has no descriptive alt text.')
            if ' '.join((image[2] or image[1]).split()).casefold() not in defined:
                finding(number, 'image-source', 'An image source is missing or unfinished.')
        heading = re.match(r'^(#{1,6})\s+(.+)', line)
        if heading:
            depth, text = len(heading[1]), heading[2].strip()
            titles += depth == 1
            if previous and depth > previous + 1:
                finding(number, 'heading-order', 'A heading skips a level.')
            if depth == 1 and len(text) > title_limit:
                finding(
                    number,
                    'title-length',
                    f'The manuscript title exceeds {title_limit} characters.',
                )
            previous = depth
        if re.search(
            r'\b(?:TODO|TBD|FIXME|TK)\b|\[(?:citation needed|insert .+?|add .+?)\]', line, re.I
        ):
            finding(
                number, 'unfinished-note', 'Resolve the unfinished editorial note or placeholder.'
            )
        for image in re.finditer(r'!\[([^\]]*)\]\(([^)]*)\)', line):
            if not image[1].strip():
                finding(number, 'image-alt', 'An image has no descriptive alt text.')
            if not image[2].strip() or image[2].strip().startswith(('TODO', 'TBD')):
                finding(number, 'image-source', 'An image source is missing or unfinished.')
        for link in re.finditer(r'(?<!!)\[[^\]]+\]\(([^)]*)\)', line):
            target = link[1].strip().strip('<>').split(' "', 1)[0]
            try:
                parsed = urlsplit(target)
                valid = bool(target) and (
                    target.startswith('#') or parsed.scheme in ('http', 'https') and parsed.hostname
                )
            except ValueError:
                valid = False
            if not valid:
                finding(
                    number,
                    'link-target',
                    'Check this empty, local or unsupported link target before public handoff.',
                )
        for citation in re.finditer(r'\[source:([^\]]+)\]', line, re.I):
            if citation[1] not in {item['source_id'] for item in record.get('sources', [])}:
                finding(
                    number, 'evidence-reference', 'This source ID is not attached to the article.'
                )
    if titles > 1:
        finding(1, 'multiple-titles', 'The manuscript has more than one top-level heading.')
    if not body.strip():
        finding(1, 'empty-manuscript', 'The manuscript is empty.')
    return {
        'id': ident,
        'status': 'findings' if findings else 'no-findings',
        'manuscript_sha256': studio.digest(body.encode()),
        'title_limit': title_limit,
        'findings': findings,
        'report_only': True,
        'google_written': False,
        'coverage': 'Local text, heading, placeholder, link syntax and selected evidence IDs. Remote link availability, factual accuracy and image rights are not verified.',
    }


def add_parser(groups):
    parser = groups.add_parser(
        'prepublish', help='Report local manuscript readiness without changing or publishing it'
    )
    parser.add_argument('--id', required=True)
    parser.add_argument('--title-limit', type=int, default=80)
