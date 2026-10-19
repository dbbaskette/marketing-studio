"""Text-only Markdown previews; saved manuscripts and image payloads are never changed."""

import re

FENCE = re.compile(r'^ {0,3}(`{3,}|~{3,})')
REFERENCE = re.compile(r'^ {0,3}\[([^\]]+)\]:[ \t]*(.*)')
TOKEN = re.compile(r'(?<!\\)(`+|!\[|<img\b[^>]*>)', re.I)


def reference(value):
    return ' '.join(value.split()).casefold()


def closing(text, start, left, right):
    depth = 1
    at = start + 1
    while at < len(text):
        if text[at] == '\\':
            at += 2
            continue
        if text[at] == left:
            depth += 1
        elif text[at] == right:
            depth -= 1
            if not depth:
                return at + 1
        at += 1
    return None


def inline(text, references):
    kept, at = [], 0
    while found := TOKEN.search(text, at):
        kept.append(text[at : found.start()])
        if found[1].startswith('`'):
            end = re.search(r'(?<!`)' + found[1] + r'(?!`)', text[found.end() :])
            at = found.end() + end.end() if end else len(text)
            kept.append(text[found.start() : at])
            continue
        if found[1].startswith('<'):
            at = found.end()
            continue
        end = closing(text, found.start() + 1, '[', ']')
        if end is None:
            at = found.end()
            kept.append(found[0])
            continue
        label = text[found.end() : end - 1]
        next_at = end
        while next_at < len(text) and text[next_at] in ' \t':
            next_at += 1
        if next_at < len(text) and text[next_at] in '([':
            left = text[next_at]
            stop = closing(text, next_at, left, ')' if left == '(' else ']')
            if stop is not None:
                if left == '[':
                    references.add(reference(text[next_at + 1 : stop - 1] or label))
                end = stop
            else:
                references.add(reference(label))
        else:
            references.add(reference(label))
        at = end
    kept.append(text[at:])
    return ''.join(kept)


def text_only(source):
    references, lines, fence = set(), [], ''
    for line in source.splitlines(keepends=True):
        found = FENCE.match(line)
        if found and (not fence or (found[1][0] == fence[0] and len(found[1]) >= len(fence))):
            fence = '' if fence else found[1]
            lines.append((True, line))
        else:
            lines.append((bool(fence), line if fence else inline(line, references)))
    kept, continuation = [], False
    for fenced, line in lines:
        if fenced:
            continuation = False
            kept.append(line)
            continue
        definition = REFERENCE.match(line)
        if definition and (
            reference(definition[1]) in references
            or definition[2].lstrip('<').lower().startswith('data:image/')
        ):
            continuation = '<' in definition[2] and '>' not in definition[2]
            continue
        if continuation:
            continuation = '>' not in line
            continue
        kept.append(line)
    return ''.join(kept)


def fields(content):
    preview = text_only(content)
    return {'preview_content': preview, 'images_omitted': True} if preview != content else {}
