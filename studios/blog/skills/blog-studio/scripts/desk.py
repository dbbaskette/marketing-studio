"""The writing desk: a blog's draft as title, opening and sections, kept with versions.

DRAFT.md is rewritten on every save so Copy, Download, Google Docs, the team library and the
pre-publish check read the same text as before.
"""

import re
import secrets

FENCE = re.compile(r' {0,3}(`{3,}|~{3,})')
TITLE = re.compile(r'# (?!#)(.*\S)\s*')
HEADING = re.compile(r'## (?!#)(.*\S)\s*')


def _id(taken):
    while True:
        value = secrets.token_hex(4)
        if value not in taken:
            taken.add(value)
            return value


def _tidy(lines):
    """Lines as one text without blank lines around it; a first line keeps its indent."""
    return re.sub(r'^(?:[ \t]*\n)+', '', '\n'.join(lines)).rstrip()


def split(markdown, title=''):
    """Title, opening and sections of a Markdown draft.

    The first line is the title when it is a `# ` heading. Each `## ` heading starts a
    section; text before the first one is the opening. A heading inside a fenced code block
    is text, and deeper headings stay inside their section.
    """
    lines = markdown.replace('\r\n', '\n').strip('\n').split('\n')
    found = TITLE.fullmatch(lines[0]) if lines else None
    if found:
        title, lines = found.group(1), lines[1:]
    opening, sections, current, fence, taken = [], [], None, None, set()
    for line in lines:
        marker = FENCE.match(line)
        if marker:
            if fence is None:
                fence = marker.group(1)
            elif marker.group(1).startswith(fence[0] * len(fence)):
                fence = None
        heading = None if fence is not None or marker else HEADING.fullmatch(line)
        if heading:
            current = {'id': _id(taken), 'heading': heading.group(1), 'brief': '', 'lines': []}
            sections.append(current)
        else:
            (current['lines'] if current else opening).append(line)
    return {
        'title': title.strip(),
        'opening': _tidy(opening),
        'sections': [
            {
                'id': section['id'],
                'heading': section['heading'].strip(),
                'brief': '',
                'text': _tidy(section['lines']),
            }
            for section in sections
        ],
    }


def join(draft):
    """The Markdown the parts make, as DRAFT.md keeps it."""
    parts = []
    if draft.get('title'):
        parts.append('# ' + draft['title'])
    if draft.get('opening'):
        parts.append(draft['opening'])
    for section in draft['sections']:
        parts.append(
            '## ' + section['heading'] + ('\n\n' + section['text'] if section['text'] else '')
        )
    return '\n\n'.join(parts) + '\n'
