"""Other people's pending suggestions in a blog's Google Doc, recorded when the Doc is read.

The desk's text is the Doc without them. Each one is recorded beside it (never in the text):
its kind (insertion, deletion, replacement or style), where it sits in the text the Doc had
(its paragraph and the span or insertion point there), the words it inserts or removes, and
its id. Google gives no authors. Blog Studio's own suggestions are left out: they are its
sends, tracked on their own. The record is kept on this computer only, in
.blog-runs/google-pending/<blog>.json, like the raw Doc it comes from, and a re-read
replaces it, so a suggestion accepted or rejected in Google drops out.

`on_desk` places each recorded suggestion on the desk's parts where its words, with the words
around it, still read exactly so; one whose words changed on the desk is left out of the
marks.
"""

import google_roundtrip as rt
import studio


def _path(root, ident):
    return studio.inside(root, '.blog-runs', 'google-pending', studio.identifier(ident) + '.json')


def record(inline, tabs=None, own=()):
    """Every pending suggestion in a Doc's inline view that is not Blog Studio's own, in
    document order: {id, ids, kind, paragraph, text, start, end, inserted, removed}. `text`
    is the paragraph as the Doc had it, images left out; `start`/`end` are the span in it
    (equal for an insertion point); `copy` counts the Doc's earlier paragraphs with the same
    text. Blog Studio's own suggestions (`own`, the ids its sends made) are left out."""
    # One character stream of the body, each with its index, its suggestions and whether it
    # is an object (an image or chip, which the desk's text does not show).
    chars = []
    for tab in rt.tabs(inline):
        tab_id = tab['tabProperties']['tabId']
        if tabs is not None and tab_id not in tabs:
            continue
        for block in tab.get('documentTab', {}).get('body', {}).get('content', []):
            for element in (block.get('paragraph') or {}).get('elements', []):
                at = element.get('startIndex')
                run = element.get('textRun')
                if run is None:
                    kind = next((k for k in element if k not in ('startIndex', 'endIndex')), '')
                    value = element.get(kind)
                    marks = value if isinstance(value, dict) else {}
                    # A smart chip reads as its text on the desk; an image as nothing.
                    shown = rt.chip_text(kind, marks) if kind != 'inlineObjectElement' else ''
                    for c in shown or ['']:
                        chars.append(
                            {
                                'ch': c,
                                'at': at,
                                'ins': list(marks.get('suggestedInsertionIds') or []),
                                'del': list(marks.get('suggestedDeletionIds') or []),
                                'style': [],
                            }
                        )
                    continue
                styled = [
                    name
                    for name in (run.get('suggestedTextStyleChanges') or {})
                    if isinstance(name, str)
                ]
                position = at
                for c in run.get('content', ''):
                    chars.append(
                        {
                            'ch': c,
                            'at': position,
                            'ins': list(run.get('suggestedInsertionIds') or []),
                            'del': list(run.get('suggestedDeletionIds') or []),
                            'style': styled,
                        }
                    )
                    position = position + rt.utf16(c) if isinstance(position, int) else position
    own = set(own or ())

    # Paragraphs as the Doc had them: a break ends one unless it is a suggested insertion.
    found, paragraph, text, seen = {}, 0, [], []
    order = []
    for item in chars:
        if item['ins']:
            for name in item['ins']:
                entry = found.setdefault(name, _entry(name, paragraph, len(text)))
                entry['inserted'] += item['ch']
                if name not in order:
                    order.append(name)
            continue  # Not in the text the Doc had.
        if item['ch'] == '\n':
            for name in item['del'] + item['style']:
                found.setdefault(name, _entry(name, paragraph, len(text)))
            done = ''.join(text)
            for entry in found.values():
                if entry['paragraph'] == paragraph and entry['text'] is None:
                    entry['text'] = done
                    entry['copy'] = seen.count(done)
            seen.append(done)
            paragraph, text = paragraph + 1, []
            continue
        for name in item['del'] + item['style']:
            entry = found.setdefault(name, _entry(name, paragraph, len(text)))
            entry['kind'] = 'style' if name in item['style'] and not item['del'] else 'deletion'
            entry['removed'] += item['ch']
            entry['end'] = len(text) + len(item['ch'])
            if name not in order:
                order.append(name)
        text.append(item['ch'])
    for entry in found.values():
        if entry['text'] is None:
            entry['text'] = ''.join(text)
            entry['copy'] = seen.count(entry['text'])
    entries = [found[name] for name in order if name not in own]
    # An insertion where a deletion ends, or begins, is one replacement.
    merged = []
    for entry in entries:
        last = merged[-1] if merged else None
        together = last is not None and last['paragraph'] == entry['paragraph']
        if (
            together
            and entry['kind'] == 'insertion'
            and last['kind'] == 'deletion'
            and last['end'] == entry['start']
        ):
            last.update(
                kind='replacement', inserted=entry['inserted'], ids=last['ids'] + entry['ids']
            )
            continue
        if (
            together
            and entry['kind'] == 'deletion'
            and last['kind'] == 'insertion'
            and last['start'] == entry['start']
        ):
            # The words that come in, then the words they replace.
            last.update(
                kind='replacement',
                end=entry['end'],
                removed=entry['removed'],
                ids=last['ids'] + entry['ids'],
            )
            continue
        merged.append(entry)
    return merged


def _entry(name, paragraph, at):
    return {
        'id': name,
        'ids': [name],
        'kind': 'insertion',
        'paragraph': paragraph,
        'text': None,
        'start': at,
        'end': at,
        'inserted': '',
        'removed': '',
        'copy': 0,
    }


def keep(root, ident, document_id, inline, tabs=None, own=()):
    """Record the Doc's pending suggestions for this blog, replacing what was there."""
    value = {
        'schema': 1,
        'document_id': document_id,
        'revision_id': inline.get('revisionId'),
        'read_at': studio.now(),
        'suggestions': record(inline, tabs, own),
    }
    target = _path(root, ident)
    target.parent.mkdir(parents=True, exist_ok=True)
    studio.write_json(target, value)
    return value


def read(root, ident):
    """The recorded pending suggestions for this blog, or [] when there are none."""
    target = _path(root, ident)
    try:
        value = studio.read_json(target) if target.is_file() and not target.is_symlink() else {}
    except (ValueError, OSError):
        value = {}
    found = value.get('suggestions') if isinstance(value, dict) else None
    return found if isinstance(found, list) else []


def forget(root, ident):
    target = _path(root, ident)
    if target.is_file() and not target.is_symlink():
        target.unlink()


def _paragraphs(text):
    """[(shown words, where each sits in the part's Markdown)] for each paragraph of a part:
    its words as the Doc shows them, a line break inside it as the Doc's own break."""
    import desk_finish

    lines = text.split('\n')
    starts, at = [], 0
    for line in lines:
        starts.append(at)
        at += len(line) + 1
    found, number = [], 0
    while number < len(lines):
        group = [number]
        while (
            lines[group[-1]].endswith('  ')
            and group[-1] + 1 < len(lines)
            and lines[group[-1] + 1].strip()
            and not desk_finish.LINE_MARK.match(lines[group[-1] + 1])
            and not lines[group[-1]].strip().startswith('|')
        ):
            group.append(group[-1] + 1)
        number = group[-1] + 1
        if not lines[group[0]].strip() or desk_finish.DEFINITION.match(lines[group[0]]):
            continue
        shown, places = [], []
        for count, index in enumerate(group):
            styled = desk_finish._styled(lines[index])
            if styled is None:
                shown = None
                break
            if count:
                shown.append('\x0b')
                places.append(starts[index] - 1)
            shown += [c for c, _ in styled['chars']]
            places += [starts[index] + place for place in styled['at']]
        if shown:
            found.append((''.join(shown), places))
    return found


def on_desk(root, ident, draft):
    """The recorded suggestions placed on the desk's parts: [{part, at, length, kind,
    inserted, removed, id}], each in its own paragraph (the one whose words are those of the
    paragraph it sits in, in the Doc) at its place there, mapped back to the Markdown. One
    whose paragraph's words changed on the desk is left out."""
    import desk

    parts = ['opening'] + [section['id'] for section in draft.get('sections', [])]
    paragraphs = []  # (part, shown words, places, its Markdown)
    for part in parts:
        try:
            text = desk.text_of(draft, part)
        except ValueError:
            continue
        paragraphs += [(part, shown, places, text) for shown, places in _paragraphs(text)]
    placed = []
    for entry in read(root, ident):
        if not isinstance(entry, dict) or not isinstance(entry.get('text'), str):
            continue
        base, start, end = entry['text'], entry.get('start', 0), entry.get('end', 0)
        if not (isinstance(start, int) and isinstance(end, int) and 0 <= start <= end <= len(base)):
            continue
        words = base.strip()
        lead = len(base) - len(base.lstrip())
        same = [row for row in paragraphs if row[1] == words]
        copy = entry.get('copy') if isinstance(entry.get('copy'), int) else 0
        if not words or copy >= len(same):
            continue  # Its paragraph's words changed on the desk: not marked.
        part, shown, places, text = same[copy]
        first, last = start - lead, end - lead
        if first < 0 or last > len(shown):
            continue

        def after(k, text=text, shown=shown, places=places):
            # Just after the k-th shown character in the Markdown: an escaped mark is two.
            escaped = text[places[k]] == '\\' and shown[k] != '\\'
            return places[k] + (2 if escaped else 1)

        at = places[first] if first < len(places) else after(len(places) - 1)
        length = after(last - 1) - at if last > first else 0
        placed.append(
            {
                'id': entry.get('id'),
                'kind': entry.get('kind'),
                'part': part,
                'at': at,
                'length': length,
                'inserted': entry.get('inserted') or '',
                'removed': entry.get('removed') or '',
            }
        )
    return placed
