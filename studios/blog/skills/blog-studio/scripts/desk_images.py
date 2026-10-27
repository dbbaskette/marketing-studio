"""Images in a desk draft, kept beside its text rather than in it.

A Google Doc's Markdown export writes each image as a short reference where it sits
(`![][image1]`) and a reference-style definition with the image's base64 data at the end
(`[image1]: <data:image/png;base64,...>`). On the desk a part's text keeps only the
references, so nobody types among walls of base64 and no job sends image data to the
assistant. The draft record's `images` lists each image, {label: {'alt', 'key', 'size'[,
'title']}}; its data is kept apart in `desk/images.json`, {label: data URI}, read only to
write DRAFT.md or to serve the page once. An entry just taken from text also carries its
`uri` until it is stored (`stored`, `data_of`). `desk.join` writes the definitions back at
the end, so DRAFT.md, Copy and Download keep every image exactly. An inline
`![alt](data:image/...)` becomes a reference to a new `imageN` the same way.

Ordinary http(s) images stay as they are, and so does image data the text holds as text:
in fenced, indented or inline code, raw HTML or a quoted definition. A job sees each such
piece of data as a named token (`scrub`), and a result must give every token back unchanged
for it to land (`restored`).
"""

from collections import Counter
import hashlib
import re

FENCE = re.compile(r' {0,3}(`{3,}|~{3,})')
LIST_LINE = re.compile(r'[ \t]*(?:[-*+]|\d{1,3}[.)])[ \t]')
CODE_SPAN = re.compile(r'(?<!`)(`+)(?!`)((?:[^\n]|\n(?![ \t]*\n))+?)(?<!`)\1(?!`)')
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
LEFTOVER = re.compile(_DATA + r'[^\s<>()"\'`]*')
TOKEN = 'image-data-kept:'  # A job sees image data kept as text as this and its digest.
TOKENS = re.compile(re.escape(TOKEN) + r'([0-9a-f]{16})(?![0-9A-Za-z+/=])')
OURS = re.compile(r'image\d+', re.I)  # The labels Google's export and the desk give images.
EACH = 5 * 1024 * 1024  # characters of image data in one image
TOTAL = 12 * 1024 * 1024  # and in all of a draft's images, under the page's request limit
TOO_BIG = 'An image in this draft is larger than 5 MB. Use a smaller image.'
TOO_MANY = 'The images in this draft come to more than 12 MB together. Use fewer or smaller images.'
CHANGED = (
    'The rewrite lost or changed image data kept in the text (such as in code), so it was '
    'not applied. Run it again.'
)
GUIDANCE = (
    'Images in the text are short references such as ![][image1] or ![alt][image2]; the images '
    'themselves are not sent. Keep every ![…][imageN] reference exactly as it is written and '
    'where it belongs in the text, and add no new one. Image data the text holds as text, '
    'such as in code, is sent as ' + TOKEN + ' and a code: keep each one exactly as it is.'
)


def key(label):
    """A label as Markdown matches it: case and runs of spaces do not count."""
    return ' '.join(str(label).split()).casefold()


def digest(uri):
    return hashlib.sha256(uri.encode()).hexdigest()[:16]


def holds(text):
    return isinstance(text, str) and 'data:image/' in text.lower()


def _blank(text):
    return re.sub(r'[^\n]', ' ', text)


def _masked(text):
    """The text with code blanked to spaces (fenced and indented blocks, and inline code
    spans), so matches outside code keep their places."""
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
    # Indented code: four spaces or a tab after a blank line, outside a list.
    lines, code, listed, blank = [], False, False, True
    for line in out:
        indented = line.startswith(('    ', '\t'))
        if not line.strip():
            lines.append(line)
            blank = True
            continue
        if indented and (code or (blank and not listed)):
            code, blank = True, False
            lines.append(' ' * len(line))
            continue
        code = False
        if LIST_LINE.match(line):
            listed = True
        elif not indented:
            listed = False
        lines.append(line)
        blank = False
    return CODE_SPAN.sub(lambda found: _blank(found.group(0)), '\n'.join(lines))


def _entry(uri, alt='', title=None):
    entry = {'alt': alt, 'key': digest(uri), 'size': len(uri), 'uri': uri}
    if title:
        entry['title'] = title
    return entry


def _key_of(entry):
    """An image entry's key, or None for an entry that is malformed (no key and no data)."""
    if not isinstance(entry, dict):
        return None
    if isinstance(entry.get('key'), str):
        return entry['key']
    return digest(entry['uri']) if isinstance(entry.get('uri'), str) else None


def entries(images):
    """The image entries that are entries at all: anything else is left out, so the image it
    stood for shows as missing rather than breaking a read."""
    return {label: entry for label, entry in (images or {}).items() if isinstance(entry, dict)}


def _fresh(taken):
    number = 1
    while key('image' + str(number)) in taken:
        number += 1
    taken.add(key('image' + str(number)))
    return 'image' + str(number)


def _unchanged(previous, text):
    """The stretches of `text` (start, end) that are as they were in `previous`: lines the
    two share, and within lines that changed, the characters they share."""
    import difflib

    if not previous:
        return []
    old, new = previous.replace('\r\n', '\n').split('\n'), text.split('\n')
    starts = [0]
    for line in new:
        starts.append(starts[-1] + len(line) + 1)
    spans = []
    lines = difflib.SequenceMatcher(None, old, new, autojunk=False)
    for tag, i1, i2, j1, j2 in lines.get_opcodes():
        if tag == 'equal':
            spans.append((starts[j1], starts[j2]))
        elif tag == 'replace':
            was, now = '\n'.join(old[i1:i2]), '\n'.join(new[j1:j2])
            if len(was) * len(now) > 4_000_000:
                continue  # Too much changed at once to compare: all of it is new.
            chars = difflib.SequenceMatcher(None, was, now, autojunk=False)
            for part, _, _, k1, k2 in chars.get_opcodes():
                if part == 'equal':
                    spans.append((starts[j1] + k1, starts[j1] + k2))
    return spans


def take(text, images=None, rename=False, previous='', touched=None):
    """The text with its image data moved out, and the images with it added.

    Each data definition outside code leaves its line (and the blank line it leaves behind);
    of two definitions of one label in the text the first counts, as in Markdown. Each inline
    data image becomes a reference to the label already holding the same data, or to a new
    `imageN` no other label in the text or the images uses. A label the images already hold
    with other data takes the text's data, as a whole draft brought in defines its images;
    with `rename`, as for one part typed, pasted or rewritten, the text's image gets a label
    of its own instead, and the text's references follow it, so no other part's image ever
    changes; a reference where the part's `previous` text already had it (in a stretch the
    two share) stays with the image it named, so only what was pasted or written anew moves.
    `touched`, a set, is given each label the text's references now name because of this
    take: a new image's, or one a clashing label moved to. An entry that is not an image entry is left out (and so shows as missing).
    `images` is not changed; a copy comes back."""
    images = {label: entry for label, entry in (images or {}).items() if isinstance(entry, dict)}
    if not holds(text):
        return text, images
    lines = text.replace('\r\n', '\n').split('\n')
    whole = '\n'.join(lines)
    masked = _masked(whole).split('\n')
    names = {key(label): label for label in images}
    held = {_key_of(entry): name for name, entry in images.items() if _key_of(entry)}
    shown = '\n'.join(masked)
    taken = set(names) | {key(m.group(2) or m.group(1)) for m in REFERENCE.finditer(shown)}
    taken |= {key(label) for label in LABELS.findall(shown)}
    out, removed, here, renamed = [], False, set(), {}
    for line, seen in zip(lines, masked, strict=True):
        found = DEFINITION.fullmatch(seen) if seen.strip() else None
        if found:
            label, uri = found.group(1).strip(), found.group(2) or found.group(3)
            removed = True
            if key(label) in here:
                continue  # A second definition of one label: the first counts.
            here.add(key(label))
            name = names.get(key(label), label)
            entry = images.get(name)
            if rename and entry and _key_of(entry) != digest(uri):
                name = held.get(digest(uri)) or _fresh(taken)
                renamed[key(label)] = name
                entry = images.get(name)
            images[name] = _entry(uri, (entry or {}).get('alt', ''), found.group(4))
            names[key(name)] = name
            held[digest(uri)] = name
            continue
        if removed and not line.strip() and (not out or not out[-1].strip()):
            continue  # The blank line a removed definition leaves.
        removed = False
        out.append(line)
    while removed and out and not out[-1].strip():
        out.pop()
    text = '\n'.join(out)
    touched = set() if touched is None else touched
    touched.update(renamed.values())
    if renamed:
        shown = _masked(text)
        kept_spans = _unchanged(previous or '', text)
        pieces, at = [], 0
        for found in REFERENCE.finditer(shown):
            label = found.group(2) or found.group(1)
            if key(label) not in renamed:
                continue
            if any(a <= found.start() and found.end() <= b for a, b in kept_spans):
                continue  # Where the part had it before: it keeps its image.
            alt = found.group(1) if found.group(2) else ''
            pieces += [text[at : found.start()], '![' + alt + '][' + renamed[key(label)] + ']']
            at = found.end()
        text = ''.join(pieces) + text[at:]
    shown = _masked(text)

    def inline(found):
        alt, uri, title = found.group(1), found.group(2) or found.group(3), found.group(4)
        name = held.get(digest(uri))
        if name is None:
            name = _fresh(taken)
            images[name] = _entry(uri, alt, title)
            held[digest(uri)] = name
            names[key(name)] = name
        touched.add(name)
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
    """Text for an assistant with no image data in it: data that can leave the text does,
    and each piece the text keeps as text (in code, say) is a token naming it (`restored`)."""
    if not holds(text):
        return text
    return LEFTOVER.sub(lambda found: TOKEN + digest(found.group(0)), take(text)[0])


def scrubbed(value):
    """A job payload with image data left out of every text in it."""
    if isinstance(value, str):
        return scrub(value)
    if isinstance(value, list):
        return [scrubbed(item) for item in value]
    if isinstance(value, dict):
        return {name: scrubbed(item) for name, item in value.items()}
    return value


def without(text):
    """Text kept with no image data at all, such as a start's notes."""
    if not holds(text):
        return text
    return LEFTOVER.sub('(image)', take(text)[0])


def restored(before, after, strict=True):
    """A returned text with each token put back as the data `before` held. Refused
    (CHANGED) when a token is not one `before` had or was altered, and, `strict`, when the
    data in it is not the data `before` had, piece for piece."""
    after = after.replace('\r\n', '\n')
    if TOKEN not in after and not (strict and holds(before)):
        return after
    datas = {digest(found.group(0)): found.group(0) for found in LEFTOVER.finditer(before)}
    # The word itself, as the text before already had it, is text, not a token.
    literal = Counter(found.group(1) for found in TOKENS.finditer(before))
    loose = before.count(TOKEN) - sum(literal.values())
    tokens = [found.group(1) for found in TOKENS.finditer(after)]
    if after.count(TOKEN) - len(tokens) > loose:
        raise ValueError(CHANGED)  # A token cut short or run into other text.
    if Counter(name for name in tokens if name not in datas) - literal:
        raise ValueError(CHANGED)  # A token for data the text did not have.
    if strict:
        want = Counter(digest(found.group(0)) for found in LEFTOVER.finditer(before))
        have = Counter(name for name in tokens if name in datas)
        have += Counter(digest(found.group(0)) for found in LEFTOVER.finditer(after))
        if want != have:
            raise ValueError(CHANGED)
    return TOKENS.sub(lambda found: datas.get(found.group(1), found.group(0)), after)


def _texts(draft):
    yield draft.get('title') or ''
    yield draft.get('opening') or ''
    for section in draft.get('sections') or []:
        yield section.get('text') or ''


def inside(draft):
    """Whether a desk record still holds image data in its text that can move out, as one
    kept before images moved out does. Data kept as text, such as in code, stays."""
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


def definitions(draft, data=None):
    """The definition lines DRAFT.md ends with, one for each image the text refers to whose
    data is in hand: just taken from text, or in `data` as desk/images.json keeps it."""
    images, data = draft.get('images') or {}, data or {}
    lines = []
    for label in written(draft):
        uri = images[label].get('uri') or data.get(label)
        if uri:
            title = images[label].get('title')
            lines.append('[' + label + ']: <' + uri + '>' + (' ' + title if title else ''))
    return lines


def stored(draft):
    """The draft as desk/draft.json keeps it: each image's label, alt text, title, key and
    size, and no data."""
    images = draft.get('images') or {}
    return {
        **draft,
        'images': {
            label: {name: value for name, value in entry.items() if name != 'uri'}
            for label, entry in images.items()
        },
    }


def data_of(draft, data):
    """desk/images.json for this draft: the data kept for each of its images, with any just
    taken from text, and nothing for an image it no longer has."""
    images, data = draft.get('images') or {}, data or {}
    return {
        label: entry.get('uri') or data[label]
        for label, entry in images.items()
        if entry.get('uri') or label in data
    }


def usable(uri):
    """Whether a value from desk/images.json is image data that can be written back as is."""
    return (
        isinstance(uri, str)
        and uri[:11].lower() == 'data:image/'
        and not any(mark in uri for mark in '<>\n\r')
    )


def shown(draft):
    """The images as a desk view lists them, without their data: the page reads the data once
    (`served`) and keeps it."""
    images = draft.get('images') or {}
    return [
        {
            'label': label,
            'alt': images[label].get('alt', ''),
            'title': images[label].get('title', ''),
            'key': images[label].get('key') or digest(images[label].get('uri', '')),
            'size': images[label].get('size', 0),
        }
        for label in written(draft)
    ]


def served(data):
    """Each image's data with the key the desk view lists it by."""
    return [{'key': digest(uri), 'uri': uri} for uri in (data or {}).values()]


def unstored(draft):
    """Whether a record holds image data in its own file's place, as one written before
    images had their own file did."""
    return any('uri' in entry for entry in (draft.get('images') or {}).values())


def missing(draft, held=None):
    """The labels the text refers to as images that are kept nowhere, each once, as first
    written: no image listed, or (with `held`, the labels whose data is kept) listed with
    no data. A label the text itself defines, such as a link's, is not missing."""
    images = entries(draft.get('images'))
    kept_keys = {key(label) for label in images if held is None or label in held}
    kept_keys |= {key(label) for label, entry in images.items() if entry.get('uri')}
    shown_texts = [_masked(text) for text in _texts(draft)]
    defined = {key(label) for text in shown_texts for label in LABELS.findall(text)}
    found, seen = [], set()
    for text in shown_texts:
        for match in REFERENCE.finditer(text):
            label = (match.group(2) or match.group(1)).strip()
            name = key(label)
            if name in seen or name in kept_keys or name in defined:
                continue
            seen.add(name)
            found.append(label)
    return found


KEPT_ALT = 'Image kept in the Google Doc'  # as google_suggestions.KEPT_ALT writes it


def kept_in_doc(draft):
    """The labels of the images the text refers to as kept in the Google Doc (too large for
    the blog's shared files), each once, that the draft holds no data for."""
    images = entries(draft.get('images'))
    held = {key(label) for label in images}
    found = []
    for text in _texts(draft):
        for match in REFERENCE.finditer(_masked(text)):
            label = (match.group(2) or match.group(1)).strip()
            if match.group(1) == KEPT_ALT and key(label) not in held and label not in found:
                found.append(label)
    return found


def found_in(texts, labels):
    """{key: entry} for each label a text defines image data for, the first text to define
    it counting, read once over the texts and stopping when every label is found."""
    wanted, found = {key(label) for label in labels}, {}
    for text in texts:
        if not holds(text):
            continue
        for name, entry in take(text)[1].items():
            if key(name) in wanted and key(name) not in found:
                found[key(name)] = entry
        if len(found) == len(wanted):
            break
    return found


def with_alts(draft):
    """Each image without alt text takes the alt of the first reference to it that has one."""
    images = dict(draft.get('images') or {})
    names = {key(label): label for label in images}
    for text in _texts(draft):
        for found in REFERENCE.finditer(_masked(text)):
            name = names.get(key(found.group(2) or found.group(1)))
            if name and found.group(1) and found.group(2) and not images[name].get('alt'):
                images[name] = {**images[name], 'alt': found.group(1)}
    return {**draft, 'images': images}


def fitted(draft, before=None):
    """The draft within the image limits. `before` is the images it had: only an image new
    since then is refused for its size or for taking the total over, and an image no part
    refers to any longer is let go first. A refusal says which limit it meets; images kept
    before the limits are left as they are."""
    images = entries(draft.get('images'))
    known = {_key_of(entry) for entry in entries(before).values()}

    def size(entry):
        return entry.get('size') or len(entry.get('uri') or '')

    def new(found):
        return [entry for entry in found.values() if _key_of(entry) not in known]

    if any(size(entry) > EACH for entry in new(images)):
        raise ValueError(TOO_BIG)
    if sum(size(entry) for entry in images.values()) <= TOTAL:
        return draft
    used = _referenced(draft)
    images = {label: entry for label, entry in images.items() if key(label) in used}
    if sum(size(entry) for entry in images.values()) > TOTAL and new(images):
        raise ValueError(TOO_MANY)
    return {**draft, 'images': images}


BREAK = re.compile(r'\n[ \t]*\n(?:[ \t]*\n)*')


def _references(text, known):
    """(start, end, reference) for each reference to a known image, outside code."""
    return [
        (m.start(), m.end(), m.group(0))
        for m in REFERENCE.finditer(_masked(text))
        if key(m.group(2) or m.group(1)) in known
    ]


def kept(before, after, images, own=()):
    """A job's text with the image references the text before it had: a reference it left
    out goes back where it was (into its list item, when it was in one, or as its own
    paragraph at the same paragraph number), and one it changed or made up is taken out.
    The images themselves never reach a job, so a result can lose a reference but never an
    image. `own` names labels the new text brought itself (`take`'s `touched`), whose
    references are not made up."""
    before, after = before.replace('\r\n', '\n'), after.replace('\r\n', '\n')
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
    # A label the new text defines itself, as pasted with its data, is its own and not made up.
    known -= {key(label) for label in LABELS.findall(_masked(after))}
    known -= {key(label) for label in own}
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
    missing_refs = []
    for start, _, ref in want:
        if left[ref] > 0:
            left[ref] -= 1
            breaks_before = list(BREAK.finditer(before[:start]))
            paragraph = len(breaks_before)
            opened = breaks_before[-1].end() if breaks_before else 0
            line = before[opened:start].count('\n')
            if before[opened:start].strip() and not LIST_LINE.match(before[opened:start]):
                paragraph += 1  # It followed words in its paragraph: it goes back after them.
            whole = before[before.rfind('\n', 0, start) + 1 : start]
            missing_refs.append((paragraph, line if LIST_LINE.match(whole) else None, ref))
    if not missing_refs:
        return after
    pieces = re.split('(' + BREAK.pattern + ')', after) if after.strip() else []
    paragraphs, breaks = pieces[0::2], pieces[1::2]
    loose = []
    for at, line, ref in missing_refs:
        rows = paragraphs[at].split('\n') if line is not None and at < len(paragraphs) else []
        if line is not None and line < len(rows) and LIST_LINE.match(rows[line]):
            rows[line] = rows[line].rstrip() + ' ' + ref
            paragraphs[at] = '\n'.join(rows)
        else:
            loose.append((at, ref))
    for offset, (at, ref) in enumerate(loose):
        at = min(at + offset, len(paragraphs))
        paragraphs.insert(at, ref)
        breaks.insert(min(at, len(breaks)), '\n\n')
    out = paragraphs[0]
    for gap, paragraph in zip(breaks, paragraphs[1:], strict=False):
        out += gap + paragraph
    return out.strip()
