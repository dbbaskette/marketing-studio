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

CONTEXT = 30  # characters of the text on each side that place a suggestion on the desk


def _path(root, ident):
    return studio.inside(root, '.blog-runs', 'google-pending', studio.identifier(ident) + '.json')


def _ours(inline):
    """Character spans (start, end) of the comments that carry a Blog Studio marker: the
    suggestions sent with them sit inside or beside these words."""
    import google_suggestions as suggestions

    anchors = {anchor.get('anchorId'): anchor for anchor in suggestions.native_anchors(inline)}
    spans = []
    for thread in inline.get('comments', []):
        if '[Blog Studio ' not in thread.get('headPost', {}).get('content', ''):
            continue
        for found in (anchors.get(thread.get('anchorId')) or {}).get('ranges', []):
            if isinstance(found.get('startIndex'), int) and isinstance(found.get('endIndex'), int):
                spans.append((found['startIndex'], found['endIndex']))
    return spans


def record(inline, tabs=None):
    """Every pending suggestion in a Doc's inline view that is not Blog Studio's own, in
    document order: {id, ids, kind, paragraph, text, start, end, inserted, removed}. `text`
    is the paragraph as the Doc had it, images left out; `start`/`end` are the span in it
    (equal for an insertion point)."""
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
                    value = next(
                        (v for k, v in element.items() if k not in ('startIndex', 'endIndex')),
                        {},
                    )
                    marks = value if isinstance(value, dict) else {}
                    chars.append(
                        {
                            'ch': '',
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
    ours = _ours(inline)

    def mine(item):
        at = item['at']
        return isinstance(at, int) and any(a <= at <= b for a, b in ours)

    # Paragraphs as the Doc had them: a break ends one unless it is a suggested insertion.
    found, paragraph, text = {}, 0, []
    order = []
    for item in chars:
        if item['ins']:
            for name in item['ins']:
                entry = found.setdefault(name, _entry(name, paragraph, len(text)))
                entry['inserted'] += item['ch']
                entry['own'] = entry['own'] or mine(item)
                if name not in order:
                    order.append(name)
            continue  # Not in the text the Doc had.
        if item['ch'] == '\n':
            for name in item['del'] + item['style']:
                found.setdefault(name, _entry(name, paragraph, len(text)))
            for entry in found.values():
                if entry['paragraph'] == paragraph and entry['text'] is None:
                    entry['text'] = ''.join(text)
            paragraph, text = paragraph + 1, []
            continue
        for name in item['del'] + item['style']:
            entry = found.setdefault(name, _entry(name, paragraph, len(text)))
            entry['kind'] = 'style' if name in item['style'] and not item['del'] else 'deletion'
            entry['removed'] += item['ch']
            entry['end'] = len(text) + len(item['ch'])
            entry['own'] = entry['own'] or mine(item)
            if name not in order:
                order.append(name)
        text.append(item['ch'])
    for entry in found.values():
        if entry['text'] is None:
            entry['text'] = ''.join(text)
    entries = [found[name] for name in order if not found[name]['own']]
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
    return [{k: v for k, v in entry.items() if k != 'own'} for entry in merged]


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
        'own': False,
    }


def keep(root, ident, document_id, inline, tabs=None):
    """Record the Doc's pending suggestions for this blog, replacing what was there."""
    value = {
        'schema': 1,
        'document_id': document_id,
        'revision_id': inline.get('revisionId'),
        'read_at': studio.now(),
        'suggestions': record(inline, tabs),
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


def on_desk(root, ident, draft):
    """The recorded suggestions placed on the desk's parts: [{part, at, length, kind,
    inserted, removed, id}], each where its words and the words around them read exactly so,
    once, in the desk's text; one whose words changed there is left out."""
    import desk

    parts = ['opening'] + [section['id'] for section in draft.get('sections', [])]
    texts = {}
    for part in parts:
        try:
            texts[part] = desk.text_of(draft, part)
        except ValueError:
            continue
    placed = []
    for entry in read(root, ident):
        if not isinstance(entry, dict) or not isinstance(entry.get('text'), str):
            continue
        base, start, end = entry['text'], entry.get('start', 0), entry.get('end', 0)
        if not (isinstance(start, int) and isinstance(end, int) and 0 <= start <= end <= len(base)):
            continue
        spot = None
        for width in (CONTEXT, 12):
            left, right = base[max(0, start - width) : start], base[end : end + width]
            needle = left + base[start:end] + right
            if not needle.strip():
                break
            hits = [
                (part, at + len(left)) for part, text in texts.items() for at in _all(text, needle)
            ]
            if len(hits) == 1:
                spot = hits[0]
                break
            if hits:
                break  # The same words twice: no telling which one.
        if spot is None:
            continue
        placed.append(
            {
                'id': entry.get('id'),
                'kind': entry.get('kind'),
                'part': spot[0],
                'at': spot[1],
                'length': end - start,
                'inserted': entry.get('inserted') or '',
                'removed': entry.get('removed') or '',
            }
        )
    return placed


def _all(text, needle):
    found, at = [], text.find(needle)
    while at != -1:
        found.append(at)
        at = text.find(needle, at + 1)
    return found
