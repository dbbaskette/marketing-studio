"""Images in a desk draft, kept beside its text rather than in it.

A Google Doc's Markdown export writes each image as a short reference where it sits
(`![][image1]`) and a reference-style definition with the image's base64 data at the end
(`[image1]: <data:image/png;base64,...>`). On the desk a part's text keeps only the
references: the definitions move to the draft record's `images`, {label: {'uri', 'alt'[,
'title']}}, so nobody types among walls of base64 and no job sends image data to the
assistant. `desk.join` writes them back at the end, so DRAFT.md, Copy and Download keep every
image exactly. An inline `![alt](data:image/...)` becomes a reference to a new `imageN` the
same way. Ordinary http(s) images, and anything inside fenced code, stay as they are.
"""

from collections import Counter
import hashlib
import re

FENCE = re.compile(r' {0,3}(`{3,}|~{3,})')
_DATA = r'(?i:data:image/)'
# A reference-style definition of an image held as data, on a line of its own.
DEFINITION = re.compile(
    r' {0,3}\[([^\[\]\n]{1,200})\]:[ \t]*(?:<(' + _DATA + r'[^<>\n]+)>|(' + _DATA + r'[^\s<>]+))'
    r'(?:[ \t]+("[^"\n]*"|\'[^\'\n]*\'|\([^()\n]*\)))?[ \t]*'
)
INLINE = re.compile(
    r'!\[([^\[\]\n]*)\]\([ \t]*(?:<(' + _DATA + r'[^<>\n]+)>|(' + _DATA + r'[^\s<>()]+))'
    r'(?:[ \t]+("[^"\n]*"|\'[^\'\n]*\'))?[ \t]*\)'
)
# A full or collapsed image reference: ![alt][label] or ![label][].
REFERENCE = re.compile(r'!\[([^\[\]\n]*)\]\[([^\[\]\n]*)\]')
LABELS = re.compile(r'^ {0,3}\[([^\[\]\n]{1,200})\]:', re.M)
LEFTOVER = re.compile(_DATA + r'[^\s<>()"\']*')
OURS = re.compile(r'image\d+', re.I)  # The labels Google's export and the desk give images.
EACH = 5 * 1024 * 1024  # characters of image data in one image
TOTAL = 12 * 1024 * 1024  # and in all of a draft's images, under the page's request limit
TOO_BIG = 'An image in this draft is larger than 5 MB. Use a smaller image.'
TOO_MANY = 'The images in this draft come to more than 12 MB together. Use fewer or smaller images.'
GUIDANCE = (
    'Images in the text are short references such as ![][image1] or ![alt][image2]; the images '
    'themselves are not sent. Keep every ![…][imageN] reference exactly as it is written and '
    'where it belongs in the text, and add no new one.'
)


def key(label):
    """A label as Markdown matches it: case and runs of spaces do not count."""
    return ' '.join(str(label).split()).casefold()


def holds(text):
    return isinstance(text, str) and 'data:image/' in text.lower()


def _masked(text):
    """The text with lines in fenced code blanked to spaces, so matches keep their places."""
    out, fence = [], None
    for line in text.split('\n'):
        marker = FENCE.match(line)
        if marker:
            if fence is None:
                fence = marker.group(1)
            elif marker.group(1).startswith(fence[0] * len(fence)):
                fence = None
            out.append(' ' * len(line))
        else:
            out.append(line if fence is None else ' ' * len(line))
    return '\n'.join(out)


def _entry(uri, alt='', title=None):
    entry = {'uri': uri, 'alt': alt}
    if title:
        entry['title'] = title
    return entry


def take(text, images=None):
    """The text with its image data moved out, and the images with it added.

    Each data definition outside code leaves its line (and the blank line it leaves behind);
    each inline data image becomes a reference to the label already holding the same data,
    or to a new `imageN` no other label in the text or the images uses. A label defined
    again takes the data defined last. `images` is not changed; a copy comes back."""
    images = dict(images or {})
    if not holds(text):
        return text, images
    lines = text.replace('\r\n', '\n').split('\n')
    masked = _masked('\n'.join(lines)).split('\n')
    names = {key(label): label for label in images}
    out, removed = [], False
    for line, shown in zip(lines, masked, strict=True):
        found = DEFINITION.fullmatch(shown) if shown.strip() else None
        if found:
            label = found.group(1).strip()
            name = names.setdefault(key(label), label)
            alt = (images.get(name) or {}).get('alt', '')
            images[name] = _entry(found.group(2) or found.group(3), alt, found.group(4))
            removed = True
            continue
        if removed and not line.strip() and (not out or not out[-1].strip()):
            continue  # The blank line a removed definition leaves.
        removed = False
        out.append(line)
    while removed and out and not out[-1].strip():
        out.pop()
    text = '\n'.join(out)
    shown = _masked(text)
    taken = set(names) | {key(m.group(2) or m.group(1)) for m in REFERENCE.finditer(shown)}
    taken |= {key(label) for label in LABELS.findall(shown)}
    held = {entry['uri']: name for name, entry in images.items()}

    def inline(found):
        alt, uri, title = found.group(1), found.group(2) or found.group(3), found.group(4)
        name = held.get(uri)
        if name is None:
            number = 1
            while key('image' + str(number)) in taken:
                number += 1
            name = 'image' + str(number)
            taken.add(key(name))
            images[name] = _entry(uri, alt, title)
            held[uri] = name
            names[key(name)] = name
        return '![' + alt + '][' + name + ']'

    pieces, at = [], 0
    for found in INLINE.finditer(shown):
        pieces += [text[at : found.start()], inline(found)]
        at = found.end()
    text = ''.join(pieces) + text[at:]
    # A definition's alt text is the alt of the first reference to it.
    for found in REFERENCE.finditer(_masked(text)):
        name = names.get(key(found.group(2) or found.group(1)))
        if name and found.group(1) and found.group(2) and not images[name].get('alt'):
            images[name] = {**images[name], 'alt': found.group(1)}
    return text, images


def scrub(text):
    """Text for an assistant with any image data left out: a source or copy read as it is."""
    if not holds(text):
        return text
    return LEFTOVER.sub('(image)', take(text)[0])


def scrubbed(value):
    """A job payload with image data left out of every text in it."""
    if isinstance(value, str):
        return scrub(value)
    if isinstance(value, list):
        return [scrubbed(item) for item in value]
    if isinstance(value, dict):
        return {name: scrubbed(item) for name, item in value.items()}
    return value


def _texts(draft):
    yield draft.get('title') or ''
    yield draft.get('opening') or ''
    for section in draft.get('sections') or []:
        yield section.get('text') or ''


def inside(draft):
    """Whether a desk record still holds image data in its text that can move out, as one
    kept before images moved out does. Data inside code is text and stays."""
    parts = [draft.get('opening') or ''] + [
        s.get('text') or '' for s in draft.get('sections') or []
    ]
    return any(holds(text) and take(text)[0] != text for text in parts)


def moved_out(draft):
    """A desk record with every part's image data moved to its images."""
    images = draft.get('images') or {}
    opening, images = take(draft.get('opening') or '', images)
    sections = []
    for section in draft.get('sections') or []:
        text, images = take(section.get('text') or '', images)
        sections.append({**section, 'text': text.strip()})
    return {**draft, 'opening': opening.strip(), 'sections': sections, 'images': images}


def _referenced(draft):
    found = set()
    for text in _texts(draft):
        found |= {key(m.group(2) or m.group(1)) for m in REFERENCE.finditer(_masked(text))}
    return found


def written(draft):
    """The labels of the images the text refers to, in the order they are kept."""
    used = _referenced(draft)
    return [label for label in draft.get('images') or {} if key(label) in used]


def definitions(draft):
    """The definition lines DRAFT.md ends with, one for each image the text refers to."""
    images = draft.get('images') or {}
    return [
        '['
        + label
        + ']: <'
        + images[label]['uri']
        + '>'
        + (' ' + images[label]['title'] if images[label].get('title') else '')
        for label in written(draft)
    ]


def digest(uri):
    return hashlib.sha256(uri.encode()).hexdigest()[:16]


def shown(draft):
    """The images as a desk view lists them, without their data: the page reads the data once
    (`served`) and keeps it."""
    images = draft.get('images') or {}
    return [
        {
            'label': label,
            'alt': images[label].get('alt', ''),
            'title': images[label].get('title', ''),
            'key': digest(images[label]['uri']),
            'size': len(images[label]['uri']),
        }
        for label in written(draft)
    ]


def served(draft):
    images = draft.get('images') or {}
    return [{'key': digest(entry['uri']), 'uri': entry['uri']} for entry in images.values()]


def fitted(draft):
    """The draft within the image limits: an image no part refers to any longer is let go
    first when they come to more than the total; a refusal says which limit it meets."""
    images = draft.get('images') or {}
    if any(len(entry['uri']) > EACH for entry in images.values()):
        raise ValueError(TOO_BIG)
    if sum(len(entry['uri']) for entry in images.values()) <= TOTAL:
        return draft
    used = _referenced(draft)
    images = {label: entry for label, entry in images.items() if key(label) in used}
    if sum(len(entry['uri']) for entry in images.values()) > TOTAL:
        raise ValueError(TOO_MANY)
    return {**draft, 'images': images}


def _references(text, known):
    """(start, end, reference) for each reference to a known image, outside code."""
    return [
        (m.start(), m.end(), m.group(0))
        for m in REFERENCE.finditer(_masked(text))
        if key(m.group(2) or m.group(1)) in known
    ]


BREAK = re.compile(r'\n[ \t]*\n(?:[ \t]*\n)*')


def kept(before, after, images):
    """A job's text with the image references the text before it had: a reference it left
    out goes back as its own paragraph where it was (the same paragraph number), and one it
    changed or made up is taken out. The images themselves never reach a job, so a result
    can lose a reference but never an image."""
    known = {key(label) for label in images or {}}
    if not known:
        return after
    # The images kept, and labels named as images are (imageN) that a job may make up.
    for text in (before, after):
        known |= {
            key(m.group(2) or m.group(1))
            for m in REFERENCE.finditer(text)
            if OURS.fullmatch((m.group(2) or m.group(1)).strip())
        }
    want, have = _references(before, known), _references(after, known)
    if Counter(ref for *_, ref in want) == Counter(ref for *_, ref in have):
        return after
    left = Counter(ref for *_, ref in want)
    cut = []
    for start, end, ref in have:
        if left[ref] > 0:
            left[ref] -= 1
        else:
            cut.append((start, end))
    for start, end in reversed(cut):
        after = after[:start] + after[end:]
    after = BREAK.sub('\n\n', after).strip() if cut else after
    missing = []
    for start, _, ref in want:
        if left[ref] > 0:
            left[ref] -= 1
            missing.append((len(BREAK.findall(before[:start])), ref))
    if not missing:
        return after
    pieces = re.split('(' + BREAK.pattern + ')', after) if after.strip() else []
    paragraphs, breaks = pieces[0::2], pieces[1::2]
    for offset, (at, ref) in enumerate(missing):
        at = min(at + offset, len(paragraphs))
        paragraphs.insert(at, ref)
        breaks.insert(min(at, len(breaks)), '\n\n')
    out = paragraphs[0]
    for gap, paragraph in zip(breaks, paragraphs[1:], strict=False):
        out += gap + paragraph
    return out.strip()
