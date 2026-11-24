"""The desk's wording as Google Doc suggestions: each paragraph the desk changed, as the
places and words a suggestion changes (google_changes).

Part of desk_finish, which keeps every name its callers use.
"""

import re

import studio


def _aligned(before, opcodes):
    """Opcodes with a change among repeated paragraphs kept in place. Where copies of one
    paragraph repeat, the diff may read an edit to one copy as a line added before them and
    one removed after; the same lines read as that copy replaced."""
    out, at = [], 0
    while at < len(opcodes):
        three = opcodes[at : at + 3]
        if len(three) == 3 and [op[0] for op in three] == ['insert', 'equal', 'delete']:
            (_, a, _, c, d), (_, _, e, _, g), (_, _, f, _, _) = three
            k = d - c
            if f - e == k and before[a:f] == before[e:f] + before[a:e]:
                out += [('replace', a, a + k, c, d), ('equal', a + k, f, d, g)]
                at += 3
                continue
        if len(three) == 3 and [op[0] for op in three] == ['delete', 'equal', 'insert']:
            (_, a, b, c, _), (_, _, e, _, g), (_, _, _, h, i) = three
            k = b - a
            if i - h == k and before[a:e] == before[b:e] + before[a:b]:
                out += [('equal', a, a + (e - b), c, g), ('replace', a + (e - b), e, h, i)]
                at += 3
                continue
        out.append(opcodes[at])
        at += 1
    return out


ESCAPED = re.compile(r'\\([\\`*_{}\[\]()#+\-.!<>|~])')
LINE_MARK = re.compile(
    r'\s{0,3}(?P<heading>#{1,6})\s+|\s{0,3}>\s?|\s*(?P<bullet>[-*+])\s+|\s*\d{1,3}[.)]\s+'
)
INLINE = re.compile(
    r'(?P<image>!\[[^\]]*\]\([^)]*\)|!\[[^\]\n]*\]\[[^\]\n]*\])'  # images, also by reference
    r'|(?P<note>\[\^[^\]]+\])'  # footnote markers
    r'|\[(?P<text>[^\]]*)\]\((?P<url>[^)]*)\)'  # links show their text, not their target
    r'|<(?P<auto>https?://[^>\s]+)>'
    r'|(?P<tag></?(?:u|sup|sub)>)'
    r'|(?P<marks>[*`]+)'  # emphasis and code marks
)
ESCAPE_HOLD = '\x00\x01'  # an escaped mark's place, two characters as `\\*` is
DEFINITION = re.compile(r'\s*\[([^\]^][^\]]*)\]:')
TOKEN = re.compile(r"\w+(?:['’-]\w+)*|[^\S\n]+|.", re.S)
NOTE_LIMIT = 1000  # characters in one suggestion's or comment's reason
NOTE_BYTES = 1800  # and bytes, under Google's 2,048 for a comment with its marker
# A character's style as the Doc shows it: bold, italic, code, underline, raised or lowered,
# and the address it links to.
PLAIN = (False, False, False, False, None, None)
BREAK = ('\n', PLAIN)


def _inline(text, state, link, chars, images, base=0, escapes=None, at_=None):
    """The characters a run of inline Markdown shows, each with its style, and in `at_` where
    each sits in the line (`base` is where `text` starts there)."""
    escapes = escapes if escapes is not None else {}
    at_ = at_ if at_ is not None else []
    at = 0
    for found in INLINE.finditer(text):
        _literal(text[at : found.start()], state, link, chars, base + at, escapes, at_)
        at = found.end()
        if found['image']:
            images.append(found['image'])
        elif found['url'] is not None:
            target = found['url'].strip().split()[0] if found['url'].strip() else ''
            _inline(
                found['text'],
                state,
                target.strip('<>'),
                chars,
                images,
                base + found.start('text'),
                escapes,
                at_,
            )
        elif found['auto']:
            _literal(
                found['auto'], state, found['auto'], chars, base + found.start('auto'), escapes, at_
            )
        elif found['tag']:
            name = found['tag'].strip('</>')
            if name == 'u':
                state['underline'] = not found['tag'].startswith('</')
            else:
                state['script'] = None if found['tag'].startswith('</') else name
        elif found['marks']:
            for run in re.findall(r'\*+|`+', found['marks']):
                if run.startswith('`'):
                    state['code'] = not state['code']
                    continue
                if len(run) % 2:
                    state['italic'] = not state['italic']
                if len(run) // 2 % 2:
                    state['bold'] = not state['bold']
    _literal(text[at:], state, link, chars, base + at, escapes, at_)


def _literal(text, state, link, chars, base=0, escapes=None, at_=None):
    style = (
        state['bold'],
        state['italic'],
        state['code'],
        state['underline'],
        state['script'],
        link or None,
    )
    escapes = escapes or {}
    at = 0
    while at < len(text):
        if text.startswith(ESCAPE_HOLD, at) and base + at in escapes:
            chars.append((escapes[base + at], style))  # An escaped mark is the character.
            if at_ is not None:
                at_.append(base + at)
            at += len(ESCAPE_HOLD)
            continue
        chars.append((text[at], style))
        if at_ is not None:
            at_.append(base + at)
        at += 1


def _styled(line):
    """A Markdown line as the Doc's body paragraph shows it: its kind of paragraph, each
    character with its style (without the spaces around them), where each sits in the line
    (`at`), and its images. None for a line that is not a paragraph (a table row, a fence, a
    footnote's or a link's definition, such as an image's data)."""
    bare = line.strip()
    if bare.startswith('|') or bare.startswith(('```', '~~~')) or re.match(r'\[[^\]]+\]:', bare):
        return None
    # An escaped mark is the character itself, as Google's Markdown export writes it: held in
    # place by a mark of the same length, so every character keeps its place in the line.
    escapes = {found.start(): found.group(1) for found in ESCAPED.finditer(line)}
    line = ESCAPED.sub(ESCAPE_HOLD, line)
    block, mark, base = 'text', LINE_MARK.match(line), 0
    if mark:
        if mark['heading']:
            block = 'heading ' + str(len(mark['heading']))
        elif mark['bullet']:
            block = 'bullet'
        elif '>' in mark.group():
            block = 'quote'
        else:
            block = 'number'
        base = mark.end()
    chars, images, at = [], [], []
    state = {'bold': False, 'italic': False, 'code': False, 'underline': False, 'script': None}
    _inline(line[base:], state, None, chars, images, base, escapes, at)
    while chars and chars[0][0].isspace():
        chars.pop(0)
        at.pop(0)
    while chars and chars[-1][0].isspace():
        chars.pop()
        at.pop()
    return {'block': block, 'chars': chars, 'images': images, 'at': at}


def _visible(line):
    """A Markdown line's text as the Doc's body paragraph shows it, or None for a line that is
    not one."""
    found = _styled(line)
    return None if found is None else ''.join(character for character, _ in found['chars'])


def _count(text, needle):
    """How many times `needle` occurs in `text`, overlapping ones too, as Google's search finds
    them."""
    found, at = 0, text.find(needle) if needle else -1
    while at != -1:
        found += 1
        at = text.find(needle, at + 1)
    return found


def _uniform(chars, start, end):
    return len({style for _, style in chars[start:end]}) <= 1


def _tokens(chars):
    """Words, runs of spaces, line breaks and single marks, each cut where the style changes."""
    text = ''.join(character for character, _ in chars)
    spans = []
    for found in TOKEN.finditer(text):
        start = found.start()
        for at in range(found.start() + 1, found.end()):
            if chars[at][1] != chars[at - 1][1]:
                spans.append((start, at))
                start = at
        spans.append((start, found.end()))
    return text, spans


def _runs(old, new):
    """The separate changed runs between two paragraphs' shown text, word by word, as
    [old start, old end, new start, new end]. Runs a few words apart merge into one where the
    Doc's words between share one style, but a new paragraph stays a change of its own. The
    desk's formatting plays no part, so a word made bold later leaves the changes as sent."""
    import difflib

    old_text, old_tokens = _tokens(old)
    new_text, new_tokens = _tokens(new)

    def bounds(spans, low, high, length):
        if high > low:
            return spans[low][0], spans[high - 1][1]
        at = spans[low][0] if low < len(spans) else length
        return at, at

    runs = []
    for tag, a, b, c, d in difflib.SequenceMatcher(
        None,
        [old_text[x:y] for x, y in old_tokens],
        [new_text[x:y] for x, y in new_tokens],
        autojunk=False,
    ).get_opcodes():
        if tag == 'equal':
            continue
        run = [*bounds(old_tokens, a, b, len(old_text)), *bounds(new_tokens, c, d, len(new_text))]
        if runs:
            last = runs[-1]
            between = old_text[last[1] : run[0]]
            if (
                len(re.findall(r'\w+', between)) <= 3
                and len(between) <= 40
                and '\n' not in ''.join(c for c, _ in new[last[2] : run[3]])
                and _uniform(old, last[0], run[1])
            ):
                last[1], last[3] = run[1], run[3]
                continue
        runs.append(run)
    return runs


def _segments(chars, start, end):
    """(start, end) of each stretch of one style between start and end."""
    found, at = [], start
    for position in range(start + 1, end):
        if chars[position][1] != chars[position - 1][1]:
            found.append((at, position))
            at = position
    if end > start:
        found.append((at, end))
    return found


def _wanted(chars):
    """The style a run of new text should have: that of its first visible character."""
    return next((style for character, style in chars if not character.isspace()), None)


def _edits(old, new):
    """Minimal edits that turn one paragraph's shown text into the desk's, each as
    [start, end, replacement] on the old text. An edit inserts text in one style only, the
    style the Doc copies from the words it replaces or follows, so a run across a link or
    formatting is cut where the style changes and its words go with the part in the style
    they need; the other parts are deletions."""
    edits = []
    for start, end, low, high in _runs(old, new):
        # Spaces both keep at either end are no part of the change.
        while (
            start < end and low < high and old[start][0] == new[low][0] and old[start][0].isspace()
        ):
            start, low = start + 1, low + 1
        while (
            start < end
            and low < high
            and old[end - 1][0] == new[high - 1][0]
            and old[end - 1][0].isspace()
        ):
            end, high = end - 1, high - 1
        replacement = new[low:high]
        if start == end or _uniform(old, start, end):
            edits.append([start, end, replacement])
            continue
        parts = _segments(old, start, end)
        want = _wanted(replacement)
        pick = next(
            (i for i, (a, b) in enumerate(parts) if old[a][1] == want),
            next(
                (i for i, (a, b) in enumerate(parts) if ''.join(c for c, _ in old[a:b]).strip()), 0
            ),
        )
        a, b = parts[pick]
        if start < a:
            edits.append([start, a, []])
        edits.append([a, b, replacement])
        if b < end:
            edits.append([b, end, []])
    return edits


def _anchored(old, edits):
    """Each edit with whole words to locate it by: an insertion takes the word beside it, in
    the style its text needs where either side has that style, and a change of spaces only
    takes the word before it. [start, end, before, after] on the old text, or None when two
    would cover the same words."""
    text, tokens = _tokens(old)
    taken = [(start, end) for start, end, _ in edits if end > start]

    def side(at, previous):
        """The word just before (or after) `at`, with the spaces between, or None."""
        if previous:
            near = [span for span in tokens if span[1] <= at]
            if not near:
                return None
            a = near[-1][0]
            if not text[a:at].strip() and len(near) > 1:
                a = near[-2][0]
            return (a, at) if text[a:at].strip() else None
        near = [span for span in tokens if span[0] >= at]
        if not near:
            return None
        b = near[0][1]
        if not text[at:b].strip() and len(near) > 1:
            b = near[1][1]
        return (at, b) if text[at:b].strip() else None

    out = []
    for start, end, replacement in edits:
        added = ''.join(c for c, _ in replacement)
        if end > start and text[start:end].strip():
            out.append([start, end, text[start:end], added, [st for _, st in replacement]])
            continue
        if start == end:
            # Inserted text starting with the space already there goes in after that space, so
            # it neither starts with a space nor takes a link's or bold style from the left,
            # unless the words on the left are in the style it needs (more words in a link).
            while (
                replacement
                and replacement[0][0].isspace()
                and start < len(text)
                and text[start] == replacement[0][0]
                and (
                    not start
                    or old[start - 1][1] != _wanted(replacement)
                    or old[start][1] == _wanted(replacement)
                )
            ):
                replacement = replacement[1:] + replacement[:1]
                start = end = start + 1
            # Ending with the space just before it, and the words before that space in the
            # style it needs: it goes in before the space, beside those words.
            while (
                replacement
                and replacement[-1][0].isspace()
                and start > 1
                and text[start - 1] == replacement[-1][0]
                and old[start - 1][1] != _wanted(replacement)
                and old[start - 2][1] == _wanted(replacement)
            ):
                replacement = replacement[-1:] + replacement[:-1]
                start = end = start - 1
            added = ''.join(c for c, _ in replacement)
            want = _wanted(replacement)
            before, after = side(start, True), side(start, False)
            order = [before, after]
            if (
                after
                and want is not None
                and old[after[0]][1] == want
                and (before is None or old[before[1] - 1][1] != want)
            ):
                order = [after, before]
        else:
            order = [side(start, True), side(end, False)]
        for span in order:
            if span is None:
                continue
            a, b = min(span[0], start), max(span[1], end)
            taken_now = [t for t in taken if t != (start, end)]
            if any(a < y and x < b for x, y in taken_now):
                continue
            out.append(
                [
                    a,
                    b,
                    text[a:b],
                    text[a:start] + added + text[end:b],
                    [st for _, st in old[a:start]]
                    + [st for _, st in replacement]
                    + [st for _, st in old[end:b]],
                ]
            )
            taken = taken_now + [(a, b)]
            break
        else:
            return None
    return sorted(out)


def _stretched(space, following):
    """Whether a space carries a link or bold that the words after it lack (desk styles)."""
    return bool((space[5] and space[5] != following[5]) or (space[0] and not following[0]))


def _runs_of(looks):
    """A replacement's looks as Google's suggestion takes them: [[length, {bold, italic,
    underline, link}]]."""
    runs = []
    for look in looks:
        found = {'bold': look[0], 'italic': look[1], 'underline': look[3], 'link': look[5]}
        if runs and runs[-1][1] == found:
            runs[-1][0] += 1
        else:
            runs.append([1, found])
    return runs


def _simulated(old, edits):
    """The paragraph's characters and styles once every edit is accepted, as Google makes
    them: kept words keep their style, and inserted text takes the desk's look (bold, italic,
    underline, link) over the style of the first word it replaces, or of the word it follows. Each character says where it came from: ('old',
    position) or ('edit', number)."""
    import google_suggestions

    out, at = [], 0
    for number, (start, end, before, after, looks) in enumerate(edits):
        out += [(old[i][0], old[i][1], ('old', i)) for i in range(at, start)]
        keep_start, keep_end = google_suggestions.trimmed(before, after)
        a, b = start + keep_start, end - keep_end
        style = old[a][1] if a < b else old[max(start, a - 1)][1]
        if (
            a == b
            and start < a < len(old)
            and old[a - 1][0].isspace()
            and _stretched(old[a - 1][1], old[a][1])
        ):
            style = old[a][1]  # A link or bold over the space stays there, as Google keeps it.
        out += [(old[i][0], old[i][1], ('old', i)) for i in range(start, a)]
        # Inserted text takes the desk's bold, italic, underline and link; code and raised
        # text it takes from the Doc's words beside it.
        out += [
            (c, (look[0], look[1], style[2], look[3], style[4], look[5]), ('edit', number))
            for c, look in zip(
                after[keep_start : len(after) - keep_end],
                looks[keep_start : len(looks) - keep_end],
                strict=True,
            )
        ]
        out += [(old[i][0], old[i][1], ('old', i)) for i in range(b, end)]
        at = end
    return out + [(old[i][0], old[i][1], ('old', i)) for i in range(at, len(old))]


def _quoted(text, limit=200):
    text = ' '.join(text.split())
    return '“' + (text if len(text) <= limit else text[: limit - 1].rstrip() + '…') + '”'


def _restyle(words, have, want):
    """What to change by hand so `words` look as they do on the desk."""
    said = []
    if have[5] != want[5]:
        if want[5] and have[5]:
            said.append('Link changed: ' + words + ' now points to ' + want[5] + '.')
        elif want[5]:
            said.append('Link ' + words + ' to ' + want[5] + '.')
        else:
            said.append('Remove the link from ' + words + '.')
    names = (('bold', 0), ('italic', 1), ('code', 2), ('underlined', 3))
    on = [name for name, at in names if want[at] and not have[at]]
    off = [name for name, at in names if have[at] and not want[at]]
    if want[4] != have[4]:
        (on if want[4] else off).append(
            {'sup': 'superscript', 'sub': 'subscript'}.get(want[4] or have[4], 'raised')
        )
    if on:
        said.append('Make ' + words + ' ' + ' and '.join(on) + '.')
    if off:
        said.append('Make ' + words + ' not ' + ' or '.join(off) + '.')
    return ' '.join(said)


def _styles(simulated, new):
    """[(new start, new end, note, style)] where the paragraph's words, once its edits are accepted,
    look different from the desk: a link, its address or formatting."""
    found, group = [], None
    for at, ((character, have, _), (_, want)) in enumerate(zip(simulated, new, strict=True)):
        if character.isspace():
            continue
        if have == want:
            group = None
            continue
        if (
            group
            and group[2:] == [have, want]
            and not ''.join(c for c, _, _ in simulated[group[1] : at]).strip()
        ):
            group[1] = at + 1
            continue
        group = [at, at + 1, have, want]
        found.append(group)
    return [
        (start, end, _restyle(_quoted(''.join(c for c, _ in new[start:end]), 80), have, want), want)
        for start, end, have, want in found
    ]


KINDS_SAID = {
    'text': 'normal text',
    'bullet': 'a bulleted list item',
    'number': 'a numbered list item',
    'quote': 'a quotation',
}


def _kind(block):
    if block.startswith('heading'):
        return 'a heading (level ' + block.split()[1] + ')'
    return KINDS_SAID.get(block, 'normal text')


def _note(reason, notes):
    """A reason with notes added, kept under the length one Google comment allows."""
    text = ' '.join([reason, *notes]).strip()
    if len(text) <= NOTE_LIMIT and len(text.encode()) <= NOTE_BYTES:
        return text
    text = text[:NOTE_LIMIT]
    while len(text.encode()) > NOTE_BYTES - 3 or len(text) > NOTE_LIMIT - 1:
        text = text[:-1]
    return text.rstrip() + '…'


def _paragraph_change(old_line, new_lines):
    """How one Doc paragraph becomes the desk's lines: (edits, comments, notes, flat), with
    edits as {start, end, before, after, reason[, remove]} and comments as {start, end, key,
    reason} on the paragraph's shown text, notes [(key, text)] for the paragraph as a whole
    (each sent as a comment of its own, never riding on an edit), and flat True when the
    change cannot be made as edits and goes to the paragraph as one comment instead."""
    old = _styled(old_line)
    shown = ''.join(c for c, _ in old['chars'])
    lines = [(line, _styled(line)) for line in new_lines]
    texts = [(line, found) for line, found in lines if found is not None and found['chars']]
    notes = [
        (
            ('line', line.strip()),
            'The desk adds '
            + ('a table row' if line.strip().startswith('|') else 'a line')
            + ' here: '
            + _quoted(line)
            + '. Add it in the Doc by hand.',
        )
        for line, found in lines
        if found is None and not DEFINITION.match(line)
    ] + [
        (
            ('images', tuple(found['images'])),
            'The desk adds an image here; add it in the Doc by hand.',
        )
        for _, found in lines
        if found is not None and not found['chars'] and found['images']
    ]
    if not texts:
        removed = {
            'start': 0,
            'end': len(shown),
            'before': shown,
            'after': '',
            'reason': 'A paragraph removed on the writing desk.',
            'remove': True,
        }
        return [removed], [], notes, False
    new = []
    for number, (_, found) in enumerate(texts):
        if number:
            new.append(BREAK)
        new += found['chars']
    images = [image for _, found in texts for image in found['images']]
    if images and images != old['images']:
        notes.append(
            (
                ('images', tuple(images)),
                'The desk has an image in this paragraph; add it in the Doc by hand.',
            )
        )
    for _, found in texts:
        if found['block'] != old['block']:
            words = ''.join(c for c, _ in found['chars'])
            subject = 'this paragraph' if len(texts) == 1 else 'the paragraph ' + _quoted(words, 60)
            notes.append(
                (
                    ('kind', words, found['block']),
                    'Make ' + subject + ' ' + _kind(found['block']) + '.',
                )
            )
    if [c for c, _ in new] == [c for c, _ in old['chars']]:
        edits = []
    else:
        edits = _anchored(old['chars'], _edits(old['chars'], new))
        if edits is None:
            return [], [], notes, True
    simulated = _simulated(old['chars'], edits)
    if ''.join(c for c, _, _ in simulated) != ''.join(c for c, _ in new):
        return [], [], notes, True
    found_edits = [
        {
            'start': start,
            'end': end,
            'before': before,
            'after': after,
            'reason': 'A paragraph added or split on the writing desk.'
            if '\n' in after
            else 'Wording changed on the writing desk.',
            'styles': _runs_of(looks),
        }
        for start, end, before, after, looks in edits
    ]
    comments = []
    for low, high, said, want in _styles(simulated, new):
        words = ''.join(c for c, _ in new[low:high])
        key = ('style', words, want)
        places = [origin[1] for _, _, origin in simulated[low:high] if origin[0] == 'old']
        if places and all(origin[0] == 'old' for _, _, origin in simulated[low:high]):
            start, end = min(places), max(places) + 1
            if not any(start < e['end'] and e['start'] < end for e in found_edits):
                comments.append({'start': start, 'end': end, 'key': key, 'reason': said})
                continue
        # Words a suggestion brings in, or words beside one: said for the paragraph instead.
        notes.append((key, said))
    return found_edits, comments, notes, False


def _by_hand(old_line, found, lines):
    """A note for a change to a paragraph that cannot take a suggestion (it holds an image, or
    is a table row), to make by hand."""
    was = ''.join(c for c, _ in found['chars']) if found else old_line.strip()
    had = found['images'] if found else []
    now_found = [_styled(line) for line in lines]
    now = ' / '.join(
        ''.join(c for c, _ in item['chars']) if item else line.strip()
        for line, item in zip(lines, now_found, strict=True)
        if not item or item['chars']
    )
    if not found:
        what = ('The table row ' if was.startswith('|') else 'The line ') + _quoted(was)
    elif was:
        what = 'The paragraph with an image, ' + _quoted(was) + ','
    else:
        what = 'The image here'
    if not lines:
        return what + ' is removed on the writing desk; remove it in the Doc by hand.'
    images = [image for item in now_found if item for image in item['images']]
    if had and images != had:
        said = 'The image here changed on the writing desk; replace it in the Doc by hand.'
        return said + (' Its words read ' + _quoted(now) + '.' if now and now != was else '')
    return what + ' reads ' + _quoted(now) + ' on the writing desk; change it in the Doc by hand.'


def _place(texts, k, shown, start, quoted):
    """How a quote at `start` in paragraph `k`'s shown text is found in the Doc: its context,
    occurrence, the text counted and how many times the Doc should show it. Copies are
    counted in the paragraphs the Doc can take suggestions in."""
    countable = [text for text in texts if text]
    earlier = [text for text in texts[:k] if text]
    copy = sum(_count(text, shown) for text in earlier)
    copies = sum(_count(text, shown) for text in countable)
    quotes = sum(_count(text, quoted) for text in countable)
    if _count(shown, quoted) == 1 and (copies > 1 or quotes > 1):
        return shown, copy + 1 if copies > 1 else None, shown, copies, copy
    if quotes > 1:
        within = sum(1 for at in range(start) if shown.startswith(quoted, at))
        return (
            None,
            sum(_count(text, quoted) for text in earlier) + within + 1,
            quoted,
            quotes,
            copy,
        )
    return None, None, quoted, quotes, copy


def _anchorable(styled):
    """Whether the Doc's paragraph can take a suggestion or comment: it has words (an image
    beside them is stepped around by the Doc's own indexes)."""
    return bool(styled and styled['chars'])


def _without_title(before, after, title):
    """The desk's lines without its `# Title` line when the Doc has none (the Doc's name is
    its title), and a note when the desk's title is not the Doc's name or first heading."""
    if not after or not re.match(r'#\s', after[0]) or (before and re.match(r'#\s', before[0])):
        return after, None
    desk_title = _visible(after[0]) or ''

    def same(value):
        return ' '.join((value or '').split()).casefold() == ' '.join(desk_title.split()).casefold()

    heading = next((line for line in before if re.match(r'\s{0,3}#{1,6}\s', line)), None)
    shown = [_visible(line) for line in (before[:1] + ([heading] if heading else []))]
    if title is None or same(title) or any(same(text) for text in shown):
        return after[1:], None
    return after[1:], (desk_title, 'Suggested title: ' + _quoted(desk_title) + '.')


def _alike(old, new):
    """How alike two lines are, by characters or word by word, whichever is closer: a short
    line with a new link address and a long paragraph reworded in places both still pair, as
    does a paragraph that only gained words at its start or end."""
    import difflib

    # The words as the Doc shows them too, so formatting added on the desk changes nothing.
    shown_old, shown_new = _visible(old), _visible(new)
    if shown_old is not None and shown_new is not None and (shown_old, shown_new) != (old, new):
        score = _alike(shown_old, shown_new)
    else:
        score = 0
    score = max(
        score,
        difflib.SequenceMatcher(None, old, new).ratio(),
        difflib.SequenceMatcher(None, old.split(), new.split(), autojunk=False).ratio(),
    )
    short, long = sorted((old.strip(), new.strip()), key=len)
    if len(short) >= 4 and (long.startswith(short) or long.endswith(short)):
        score = max(score, 0.6 + 0.4 * len(short) / len(long))
    return score


def _pairs(olds, news):
    """The Doc paragraphs and desk lines that pair, never crossing, as alike as they can be
    taken together: one close pair never takes the place of two."""
    best = [[(0.0, ())] * (len(news) + 1) for _ in range(len(olds) + 1)]
    for i, old in enumerate(olds, 1):
        for j, new in enumerate(news, 1):
            choices = [best[i - 1][j], best[i][j - 1]]
            score = _alike(old, new)
            if score >= 0.6:
                total, chosen = best[i - 1][j - 1]
                choices.append((total + score, chosen + ((i - 1, j - 1),)))
            best[i][j] = max(choices, key=lambda found: (round(found[0], 9), -len(found[1])))
    return list(best[len(olds)][len(news)][1])


def _joins(paragraph, line, after):
    """Whether a new line inserted after (or before) this paragraph comes out as the desk has
    it: the same kind of paragraph, and its first words in the style of the words it joins."""
    if not paragraph or not paragraph['chars'] or not line or not line['chars']:
        return False
    beside = paragraph['chars'][-1 if after else 0][1]
    return paragraph['block'] == line['block'] and beside == _wanted(line['chars'])


def _attach(before, after, opcodes):
    """For each Doc paragraph, the desk lines it becomes: {old index: [new indexes]}. A desk
    line paired with a Doc paragraph replaces it; a desk line with none joins the paragraph
    before it as a new paragraph after it (or the one after it, when the paragraph before
    cannot take a suggestion or there is none). A Doc paragraph with no lines is removed."""

    becomes = {}
    anchorable = [_anchorable(_styled(line)) for line in before]
    for tag, a, b, c, d in opcodes:
        if tag == 'equal':
            for i in range(b - a):
                becomes.setdefault(a + i, []).append(c + i)
            continue
        olds, news = before[a:b], after[c:d]
        pairs = []
        if (
            not a
            and not c
            and olds
            and news
            and re.match(r'#\s', olds[0])
            and re.match(r'#\s', news[0])
        ):
            pairs.append((0, 0))  # The Doc's title paragraph and the desk's title.
        if len(olds) * len(news) <= 40_000:
            # Pair Doc paragraphs with desk lines, never two pairs that cross: a paragraph
            # deleted next to an edited one is never rewritten into it.
            skip = len(pairs)
            pairs += [(i + skip, j + skip) for i, j in _pairs(olds[skip:], news[skip:])]
        pairs.sort()
        for i in range(len(olds)):
            becomes.setdefault(a + i, [])
        for i, j in pairs:
            becomes[a + i].append(c + j)
        paired = {j: i for i, j in pairs}
        onward = False  # A line joined the paragraph after it: the rest before it do too.
        for j in range(len(news)):
            if j in paired:
                onward = False
                continue
            earlier = [i for i, pj in pairs if pj < j]
            later = [i for i, pj in pairs if pj > j]
            behind = a + earlier[-1] if earlier else (a - 1 if a else None)
            ahead = a + later[0] if later else (b if b < len(before) else None)
            line = _styled(news[j])
            if (
                behind is None
                or onward
                or (not anchorable[behind] and ahead is not None and anchorable[ahead])
            ):
                target = ahead if ahead is not None else behind
            elif (
                ahead is not None
                and anchorable[ahead]
                and (
                    _visible(before[ahead]).startswith(_visible(news[j]) or '\0')
                    or (
                        not _joins(_styled(before[behind]), line, True)
                        and _joins(_styled(before[ahead]), line, False)
                    )
                )
            ):
                # A split's first part, or a paragraph that fits the one after it better: a new
                # paragraph takes the kind and style of the one it is split from.
                target = ahead
            else:
                target = behind
            if target is None:
                target = a  # A Doc of only removed paragraphs: the new lines replace the first.
            onward = onward or (target == ahead and ahead is not None)
            becomes.setdefault(target, []).append(c + j)
    return {k: sorted(v) for k, v in becomes.items()}


def google_changes(baseline, body, title=None):
    """Every desk change against the Google Doc, as quoted suggestions and comments, how many
    could not be placed anywhere, and the Doc paragraph each one is in with how many times the
    Doc should show what locates it.

    Each changed paragraph's shown words are compared word by word, and each separate changed
    run is its own suggestion. A paragraph added is inserted after the one before it, and one
    removed is deleted with its break. What the Doc shows no words for (a link's address,
    formatting, an image) is a comment on its words or paragraph, as is a change in a
    paragraph that cannot take a suggestion. The desk's `# Title` line is not a change when
    it is the Doc's name (`title`) or its first heading. A suggestion's id stays the same
    wherever its paragraph moves, so one sent before is known again. Copies are counted in
    the text a reader of the Doc sees, as Google's own search finds it."""
    import difflib
    import json

    import manuscript_editor

    # Paragraphs, without the blank lines between them, so the diff aligns on text. An image's
    # data (a reference definition) is compared by its label, not as a paragraph.
    def split(text):
        lines, images, joined = [], {}, False
        for line in text.splitlines():
            label = DEFINITION.match(line)
            if label:
                images[label.group(1)] = line.strip()
                joined = False
            elif line.strip():
                if joined and lines and not LINE_MARK.match(line):
                    # A line break inside a paragraph (two spaces at a line's end), as the Doc
                    # holds it: one paragraph, its break the Doc's own. A list item or heading
                    # on the next line is a paragraph of its own.
                    lines[-1] = lines[-1].rstrip() + '\x0b' + line.lstrip()
                else:
                    lines.append(line)
                joined = line.endswith('  ') and not line.strip().startswith('|')
            else:
                joined = False
        return lines, images

    before, old_images = split(baseline)
    after, new_images = split(body)
    after, title_note = _without_title(before, after, title)
    styled = [_styled(line) for line in before]
    texts = [
        ''.join(c for c, _ in found['chars']) if _anchorable(found) else None for found in styled
    ]
    opcodes = _aligned(
        before, difflib.SequenceMatcher(None, before, after, autojunk=False).get_opcodes()
    )
    becomes = _attach(before, after, opcodes)
    edits, comments, notes = {}, {}, {}  # By Doc paragraph.

    def note(k, key, text, about=None):
        notes.setdefault(k, []).append((key, text, about))

    if title_note:
        note(0, ('title', title_note[0]), title_note[1])
    # An image the desk takes in gets a label of its own, so data that differs under the same
    # label is the same image read another way (Google's image host or its export), not a
    # change; an image removed or added shows by its reference.
    for k, old_line in enumerate(before):
        lines = [after[j] for j in becomes.get(k, [])]
        if lines == [old_line]:
            continue
        found = styled[k]
        if not _anchorable(found):
            # A paragraph with an image, a table row or no words takes no suggestion: the
            # change goes to the closest paragraph that can take one.
            note(k, ('by-hand', tuple(lines)), _by_hand(old_line, found, lines))
            continue
        found_edits, found_comments, found_notes, flat = _paragraph_change(old_line, lines)
        for key, text in found_notes:
            note(k, key, text, texts[k])
        if flat:
            now = ' / '.join(
                text for text in (_visible(line) for line in lines) if text is not None
            )
            note(
                k,
                ('by-hand', tuple(lines)),
                'Change this paragraph by hand to read ' + _quoted(now, 400) + '.',
                texts[k],
            )
            continue
        edits[k] = found_edits
        comments[k] = found_comments
    found, paragraphs, left = [], {}, 0
    anchorable = [m for m in range(len(before)) if texts[m]]
    # A comment may also sit on the words of a paragraph that holds an image or a chip.
    spoken = [
        texts[m] or ''.join(c for c, _ in (styled[m] or {}).get('chars', [])) or None
        for m in range(len(before))
    ]
    near_by = [m for m in range(len(before)) if spoken[m]]

    def nearest(k):
        return sorted(anchorable, key=lambda m: (abs(m - k), m))

    def nearby(k):
        return [spoken[m] for m in sorted(near_by, key=lambda m: (abs(m - k), m))[:8]]

    def same_lines(k):
        return sum(1 for line in before[:k] if line == before[k])

    # Where a change sits, as a bring-back finds it again: the baseline paragraph's words and
    # how many paragraphs with the same words come before it (headings left out).
    places, counted = {}, {}
    for m, line in enumerate(before):
        if line.lstrip().startswith('#'):
            continue
        key = _line_key(line)
        places[m] = [key, counted.get(key, 0)]
        counted[key] = counted.get(key, 0) + 1

    for k in sorted(set(edits) | set(comments)):
        old, shown = before[k], texts[k]
        now = ' / '.join(
            text for text in (_visible(after[j]) for j in becomes.get(k, [])) if text is not None
        )
        seen = {}
        items = [('edit', e) for e in edits.get(k, [])] + [
            ('comment', c) for c in comments.get(k, [])
        ]
        for kind, change in sorted(items, key=lambda item: item[1]['start']):
            quoted = change['before'] if kind == 'edit' else shown[change['start'] : change['end']]
            context, occurrence, needle, matches, copy = _place(
                texts, k, shown, change['start'], quoted
            )
            if kind == 'edit':
                key = [old, quoted, change['after'], copy] + (
                    ['remove'] if change.get('remove') else []
                )
            else:
                # Its words and what they need, not how the note words it.
                key = ['comment', old, copy, change['key']]
            # The same change twice in one paragraph: each copy is its own.
            seen[json.dumps(key)] = number = seen.get(json.dumps(key), 0) + 1
            if number > 1:
                key.append(number)
            item = {
                'id': 'desk-' + studio.digest(json.dumps(key).encode())[:16],
                'kind': kind,
                'before': quoted,
                'reason': change['reason'],
            }
            if kind == 'edit':
                item['after'] = change['after']
            if context:
                item['context'] = context
            item = manuscript_editor.proposal(item)
            if occurrence:
                item['occurrence'] = occurrence
            if change.get('remove'):
                item['remove'] = True
            elif kind == 'edit' and change['after']:
                item['styles'] = change['styles']
            found.append(item)
            paragraphs[item['id']] = {
                'paragraph': studio.digest(old.encode()),
                'needle': needle,
                'matches': matches,
                'text': shown,  # The paragraph the change is meant for, as shown.
                'near': nearby(k),
                'was': shown,
                'now': now,
                'place': places.get(k),
                # The desk's lines this change carries, as the Doc shows words.
                'lines': [
                    text.strip()
                    for text in (_visible(after[j]) for j in becomes.get(k, []))
                    if text and text.strip()
                ],
            }
    # A note for a paragraph as a whole is a comment of its own, placed when the plan is made
    # on the closest paragraph nothing else in that plan uses, so it never rides on a
    # suggestion and is never dropped with one sent before.
    for k in sorted(notes):
        if not anchorable:
            left += len(notes[k])
            continue
        seen = {}
        for key, text, about in notes[k]:
            ident = json.dumps(['note', before[k], same_lines(k), key])
            # Two equal notes for one paragraph (two equal new lines): each is its own.
            seen[ident] = number = seen.get(ident, 0) + 1
            if number > 1:
                ident = json.dumps(['note', before[k], same_lines(k), key, number])
            item = manuscript_editor.proposal(
                {
                    'id': 'desk-' + studio.digest(ident.encode())[:16],
                    'kind': 'comment',
                    'before': texts[nearest(k)[0]],
                    'reason': _note(text, []),
                }
            )
            found.append(item)
            paragraphs[item['id']] = {
                'paragraph': studio.digest(before[k].encode()),
                'near': nearby(k),
                'about': about,
                'float': True,
                'place': places.get(k),
                # A change made by hand carries the desk's lines it asks for.
                'lines': [
                    text.strip()
                    for text in (_visible(line) for line in key[1])
                    if text and text.strip()
                ]
                if key[0] == 'by-hand'
                else [],
            }
    return found, left, paragraphs


def _line_key(line):
    """A paragraph's words as the Doc shows them; a line with no words (an image) is known
    by itself."""
    shown = _visible(line)
    return shown.strip() if shown and shown.strip() else '\x00' + line.strip()
