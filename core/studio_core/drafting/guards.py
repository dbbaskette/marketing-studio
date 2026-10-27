"""Whether a rewrite keeps what it must: facts (numbers, links, quotations, names) and the
part's structure (code exactly, image references, and its blocks).

`flags(before, after)` is every reason, as one line ("Check the facts: this changes a
number."), or ''. Finishing flags a proposal with it, and every desk rewrite records it.
An image reference (`![alt][label]` by default; a studio may pass its own pattern) is not
text: it is never read as a name, and dropping or changing one changes the structure.
"""

import re

from .. import text_checks
from .proofread import LIST_LINE, mask_indented

NAME = re.compile(r'\b[A-Z][A-Za-z0-9]+\b')
# A full or collapsed reference-style image: ![alt][label] or ![label][].
REFERENCE = re.compile(r'!\[([^\[\]\n]*)\]\[([^\[\]\n]*)\]')
STRUCTURE = 'Check the structure: this changes code or the part’s shape.'
FENCE = re.compile(r'^[ \t]*(```|~~~)')
INLINE_CODE = re.compile(r'(`+)(.+?)\1', re.S)
TABLE_LINE = re.compile(r'^[ \t]*\|')
QUOTE_LINE = re.compile(r'^\s{0,3}>')
WORDS = {'numbers': 'a number', 'links': 'a link', 'quotes': 'a quotation', 'names': 'a name'}


def names(text, reference=REFERENCE):
    """Capitalised words that are not the first word of a sentence: likely names. An image
    reference is not text: its alt and label are left out, and a word after it starts afresh."""
    text = reference.sub('. ', text)
    found = set()
    for match in NAME.finditer(text):
        before = text[: match.start()].rstrip()
        if before and before[-1] not in '.!?:"“(]' and len(match.group()) > 1:
            found.add(match.group())
    return found


def named(name, text):
    return re.search(r'(?<![A-Za-z0-9])' + re.escape(name) + r'(?![A-Za-z0-9])', text) is not None


def changes_facts(before, after, anywhere=False, reference=REFERENCE):
    """What a rewrite changes that it should keep: numbers, links, quotes or names.

    `anywhere` (a whole part rewritten in a voice) compares which names there are, not
    where they sit: a name that only moves to the start of a sentence is kept, and one
    added or dropped is flagged."""
    changed = list(text_checks.preserve(before, after)['changes'])
    if anywhere:
        dropped = {name for name in names(before, reference) if not named(name, after)}
        added = {name for name in names(after, reference) if not named(name, before)}
        if (dropped | added) - {'I'}:
            changed.append('names')
    elif names(before, reference) - names(after, reference) - {'I'}:
        changed.append('names')
    if not changed:
        return ''
    return 'Check the facts: this changes ' + ' and '.join(WORDS[key] for key in changed) + '.'


def shape(text, paragraphs=True, reference=REFERENCE):
    """The code and quotations a part holds, exactly (fenced blocks with their opening
    line, indented code, inline code spans, blockquote lines), its image references in
    order, and the count of its blocks: paragraphs, list items, fenced blocks and tables."""
    fences, outside = [], []
    block, inside = None, False
    for line in text.splitlines():
        if FENCE.match(line):
            if inside:
                fences.append('\n'.join(block))
                inside = False
            else:
                inside, block = True, [line.strip()]  # The language tag is part of the code.
            outside.append('')
            continue
        if inside:
            block.append(line)
        else:
            outside.append(line)
    if inside:
        fences.append('\n'.join(block))
    # Indented code by the same rules the proofread uses: its lines exactly, then masked.
    shown = '\n'.join(outside)
    masked = mask_indented(shown)
    indented = [
        line
        for line, mask in zip(shown.split('\n'), masked.split('\n'), strict=True)
        if line.strip() and not mask.strip()
    ]
    prose = masked
    inline = [match.group(2) for match in INLINE_CODE.finditer(prose)]
    lines = prose.splitlines()
    quotes = [line.strip() for line in lines if QUOTE_LINE.match(line)]
    items = sum(1 for line in lines if LIST_LINE.match(line))
    tables = sum(
        1
        for at, line in enumerate(lines)
        if TABLE_LINE.match(line) and (at == 0 or not TABLE_LINE.match(lines[at - 1]))
    )
    count = (
        sum(
            1
            for chunk in re.split(r'\n[ \t]*\n', prose)
            if chunk.strip()
            and not all(
                LIST_LINE.match(row) or TABLE_LINE.match(row) for row in chunk.strip().splitlines()
            )
        )
        if paragraphs
        else 0
    )
    images = [match.group(0) for match in reference.finditer(prose)]
    return fences, indented, inline, quotes, images, (count, items, len(fences), tables)


def changes_structure(before, after, paragraphs=True, reference=REFERENCE):
    """STRUCTURE when a rewrite changes code (fenced blocks or inline code spans, exactly),
    drops, adds or alters an image reference, or changes the part's block structure; ''
    otherwise."""
    same = shape(before, paragraphs, reference) == shape(after, paragraphs, reference)
    return '' if same else STRUCTURE


def flags(before, after, anywhere=False, paragraphs=True, reference=REFERENCE):
    """Every reason a rewrite waits to be checked, as one line, or ''."""
    return ' '.join(
        flag
        for flag in (
            changes_facts(before, after, anywhere, reference),
            changes_structure(before, after, paragraphs, reference),
        )
        if flag
    )
