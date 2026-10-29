"""A conservative manuscript view; the captured Google source is never changed.

Only leading, explicitly labelled approval fields containing readable chips are
administration. Ambiguous text, bylines, images and article tables stay visible.
Original native indexes survive so suggestions still address the original Doc.
"""

import copy
import re

import google_roundtrip as rt

PROJECTION = 'blog-studio-manuscript/1'
_LABEL = re.compile(
    r'(?i)^(?:(?:technical|legal|editorial|security|sme)\s+)?'
    r'(?:approvers?|reviewers?|approval status|review status|approved by|reviewed by)\s*:?\s*$'
)


def _field(paragraph):
    """(label, chip count), or None for anything beyond a label and readable chips."""
    text, chips, after_chip = [], 0, False
    for element in paragraph.get('elements', []):
        if 'textRun' in element:
            words = element['textRun'].get('content', '')
            if after_chip and words.strip(' \t\r\n,;/|'):
                return None
            if not after_chip:
                text.append(words)
        elif 'dropdown' in element or 'person' in element:
            kind = 'dropdown' if 'dropdown' in element else 'person'
            props = element[kind].get(kind + 'Properties') or {}
            readable = (
                isinstance(props.get('displayValue'), str)
                if kind == 'dropdown'
                else bool(rt.chip_text(kind, element[kind]))
            )
            if not readable:
                return None
            chips += 1
            after_chip = True
        else:
            return None
    label = ''.join(text).strip()
    if label and not _LABEL.fullmatch(label):
        return None
    return label, chips


def excluded(native):
    """Indexes of leading approval blocks. Never infer metadata from names alone."""
    blocks = native.get('body', {}).get('content', [])
    skipped, pending = [], []
    for index, block in enumerate(blocks):
        if 'sectionBreak' in block:
            continue
        if 'table' in block:
            fields = []
            for row in block['table'].get('tableRows', []):
                for cell in row.get('tableCells', []):
                    for part in cell.get('content', []):
                        fields.append(_field(part['paragraph']) if 'paragraph' in part else None)
            if (
                fields
                and all(f is not None for f in fields)
                and any(f[0] for f in fields)
                and any(f[1] for f in fields)
            ):
                skipped.extend([*pending, index])
                pending = []
                continue
            break
        paragraph = block.get('paragraph')
        if paragraph is None:
            break
        field = _field(paragraph)
        if field is not None:
            label, chips = field
            if label and not chips:
                pending.append(index)
            elif chips and (label or pending):
                skipped.extend([*pending, index])
                pending = []
            elif chips:
                # A second row of names is administration only after a labelled row.
                if skipped:
                    skipped.append(index)
                else:
                    break
            continue
        named = paragraph.get('paragraphStyle', {}).get('namedStyleType')
        if not skipped and not pending and named in ('TITLE', 'SUBTITLE'):
            continue
        break
    return set(skipped)


def view(value):
    """Return a private projection, preserving all source coordinates and other tab data."""
    result = copy.deepcopy(value)
    for tab in rt.tabs(result):
        native = tab.get('documentTab', {})
        skip = excluded(native)
        if skip:
            body = native['body']
            body['content'] = [b for i, b in enumerate(body['content']) if i not in skip]
    return result


def summary(value):
    count = sum(len(excluded(tab.get('documentTab', {}))) for tab in rt.tabs(value))
    return {'excluded_approval_blocks': count} if count else {}
