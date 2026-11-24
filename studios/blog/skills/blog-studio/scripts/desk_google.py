"""Sending the desk's wording to the blog's Google Doc: the plan, the send, the check, the
Doc's state and what a desk blog waits on.

Part of desk_finish, which keeps every name its callers use.
"""

import re

import studio
from desk_google_changes import (
    _count,
    _note,
    _quoted,
    _restyle,
    _visible,
    google_changes,
)
from desk_proposals import (
    summary,
)


# Before publishing: repurpose into new desk blogs, and send the desk's wording to the
# blog's Google Doc as suggestions. The pre-publish check reads DRAFT.md, which every desk
# write keeps in step.
NO_DOC = (
    'This blog has no Google Doc to send suggestions to. A blog started from a Google Doc can '
    'send its desk changes back to that Doc.'
)


def _sent_path(root, ident):
    return studio.inside(root, '.blog-runs', 'desk-google', studio.identifier(ident) + '.json')


def _sent(root, ident):
    """What this computer sent to the blog's Doc: {'plans': {token: rows}, 'sent': rows, 'name'},
    each row {id, paragraph, base}, with the Doc's name as last read. Kept beside the jobs,
    never in the blog's folder."""
    target = _sent_path(root, ident)
    try:
        found = studio.read_json(target) if target.is_file() and not target.is_symlink() else {}
    except (ValueError, OSError):
        found = {}
    found = found if isinstance(found, dict) else {}
    held = lambda key: found.get(key) if isinstance(found.get(key), dict) else None  # noqa: E731
    return {
        'plans': dict(found.get('plans') or {}),
        'sent': list(found.get('sent') or []),
        'name': found.get('name') if isinstance(found.get('name'), str) else None,
        'own': [name for name in found.get('own') or [] if isinstance(name, str)],
        # What each plan says it sends, and whether it sends every desk change (`whole`).
        'meta': dict(found.get('meta') or {}),
        # The last send and the last bring-back: when, and how much.
        'last': held('last'),
        'brought': held('brought'),
        # The desk lines each verified send carried to this Doc baseline, as suggestions or
        # for the owner to make by hand: [{transfer, how, lines}].
        'carried': [entry for entry in found.get('carried') or [] if isinstance(entry, dict)],
        # This blog's own suggestions waiting in the Doc, as the Doc was last read.
        'waiting': found.get('waiting') if isinstance(found.get('waiting'), int) else None,
    }


def _delivered(root, document, ident):
    """Whether the Google ledger holds a reservation for this suggestion in this Doc."""
    import google_suggestions as suggestions

    marker = suggestions.contained(
        suggestions.ledger(root),
        suggestions.digest(suggestions.encoded([document, ident])) + '.finding',
    )
    return marker.is_file()


def _google_base(root, ident):
    directory, record = studio.item(root, 'articles', ident)
    base = (record.get('google') or {}).get('baselines', {}).get('draft') or {}
    if not base.get('document') or not base.get('transfer'):
        raise ValueError(NO_DOC)
    return directory, record, base


def google_ready(record):
    base = (record.get('google') or {}).get('baselines', {}).get('draft') or {}
    return bool(base.get('document') and base.get('transfer'))


def _google_expected(root, ident):
    directory, record, base = _google_base(root, ident)
    import json

    body = (directory / 'DRAFT.md').read_bytes() if (directory / 'DRAFT.md').is_file() else b''
    return studio.digest(body + json.dumps(base, sort_keys=True).encode())


def _counted(number, one, many):
    return str(number) + ' ' + (one if number == 1 else many)


def _desk_title(body):
    first = next((line for line in body.splitlines() if line.strip()), '')
    return ' '.join((_visible(first) or '').split()) if re.match(r'#\s', first) else None


def google_plan(root, ident, mode):
    """Check the desk's latest text against the Google Doc as suggestions and comments;
    nothing is sent."""
    import google_drive as drive
    import google_suggestions as suggestions
    from google_workflow import snapshot_path

    import manuscript_editor

    directory, _, base = _google_base(root, ident)
    if mode not in ('auto', 'native', 'comments'):
        raise ValueError('Choose suggestions, comments or suggestions with comments fallback.')
    baseline = snapshot_path(directory, base['transfer'], 'document').read_text()
    body = (directory / 'DRAFT.md').read_text()
    record = _sent(root, ident)
    # Nothing changed, with the desk's title the Doc's name as last read and nothing sent to
    # this copy of the Doc: Google is not read.
    title = _desk_title(body)
    if (
        not google_changes(baseline, body, title)[0]
        and (title is None or title == record['name'])
        and not any(row.get('base', base['transfer']) == base['transfer'] for row in record['sent'])
    ):
        raise ValueError('Nothing new to send: the desk’s text matches the Google Doc.')
    client = drive.Client(drive.account_for(root))
    # The Doc as it is now: its name is its title, and a suggestion still waiting for its owner
    # holds its paragraph.
    inline, _, _ = suggestions.read_for_review(client, base['document']['document_id'], mode)
    # The Doc's pending suggestions as they are now: one decided in Google drops out.
    import google_pending

    google_pending.keep(
        root,
        ident,
        base['document']['document_id'],
        inline,
        base['document']['tab_ids'],
        own=set(record['own']),
    )
    record['name'] = ' '.join((inline.get('title') or '').split()) or None
    # This blog's own suggestions still waiting in the Doc, for the desk and Home to show.
    import google_roundtrip as rt

    record['waiting'] = _waiting(inline, record, base, rt.suggestion_ids(inline))
    proposals, left, paragraphs = google_changes(baseline, body, inline.get('title'))
    current = {p['id'] for p in proposals}
    # A suggestion sent before stays in the Doc for its owner and is not sent again, whether
    # this computer or another one sent it.
    document = base['document'].get('document_id')
    threads = ' '.join(
        thread.get('headPost', {}).get('content', '') for thread in inline.get('comments', [])
    )
    sent = {row.get('id') for row in record['sent']} | {
        p['id']
        for p in proposals
        if _delivered(root, document, p['id']) or '[Blog Studio ' + p['id'] + ']' in threads
    }
    before = sum(1 for p in proposals if p['id'] in sent)
    # Words a suggestion sent before brought in, formatted otherwise on the desk since: the
    # new look goes as a note, the suggestion staying as it was sent.
    looks = {row.get('id'): row.get('styles') for row in record['sent'] if row.get('styles')}
    restyled = [
        note
        for p in proposals
        if p['id'] in sent and p.get('styles') and looks.get(p['id']) not in (None, p['styles'])
        for note in _restyle_notes(p, looks[p['id']], paragraphs)
    ]
    proposals = [p for p in proposals if p['id'] not in sent] + [
        note for note in restyled if note['id'] not in sent
    ]
    # A suggestion sent before that still waits in the Doc, which the desk no longer makes
    # (reworded again, or undone), holds everything: sending around it could repeat or undo
    # it. Only this blog's own suggestions count, by their markers, never comments or notes,
    # nor a teammate's suggestion. Each such change is counted as waiting.
    # A suggestion that no longer waits (accepted, rejected) never waits again: it is marked
    # settled, so a later suggestion in its paragraph is never taken for it.
    gone = []
    for row in record['sent']:
        if (
            row.get('settled')
            or row.get('base', base['transfer']) != base['transfer']
            or row.get('kind', 'edit') != 'edit'
        ):
            continue
        if not _still_waits(inline, row['id']):
            row['settled'] = True
        elif row.get('id') not in current:
            gone.append(row)
    waiting, covers, later, theirs = 0, {}, 0, 0
    if gone:
        waiting, proposals = len(gone) + len(proposals), []
    if proposals:
        waiting_edits = {
            row['id']
            for row in record['sent']
            if row.get('kind', 'edit') == 'edit'
            and not row.get('settled')
            and row.get('base', base['transfer']) == base['transfer']
        }
        proposals, also, unplaced, covers, later, theirs = _not_pending(
            inline, base['document'], proposals, paragraphs, waiting_edits
        )
        waiting += also
        left += unplaced
    if not proposals:
        studio.write_json(_sent_path(root, ident), record)
        said = []
        if before:
            said.append(_counted(before, 'change was', 'changes were') + ' sent before')
        if waiting:
            said.append(
                _counted(waiting, 'change waits', 'changes wait')
                + ' for the Doc’s owner to decide the earlier suggestion in '
                + ('its paragraph' if waiting == 1 else 'their paragraphs')
            )
        if left:
            said.append(
                _counted(left, 'change', 'changes')
                + ' could not be placed in the Doc; pull the latest Doc and check again'
            )
        if later:
            said.append(
                _counted(later, 'note goes', 'notes go')
                + ' with the next send (nearby paragraphs already have changes)'
            )
        raise ValueError(
            'Nothing new to send'
            + (
                ': ' + '; '.join(said) + '.'
                if said
                else ': the desk’s text matches the Google Doc.'
            )
        )
    if len(proposals) > 100:
        raise ValueError('More than 100 changes to send at once. Send fewer, or share the draft.')
    # Never two findings with one id: Google's plan would refuse them all. A repeat keeps its
    # place's number, so it is the same next time.
    named = {}
    for p in proposals:
        named[p['id']] = number = named.get(p['id'], 0) + 1
        if number > 1:
            paragraphs[p['id'] + '-' + str(number)] = paragraphs[p['id']]
            p['id'] += '-' + str(number)
    plan = manuscript_editor.google_plan(
        client, root, ident, proposals, mode, _google_expected(root, ident), base['document']['url']
    )
    rows = [
        {
            'id': name,
            'paragraph': paragraphs[name]['paragraph'],
            'base': base['transfer'],
            'kind': p['kind'] if name == p['id'] else 'fallback',
            **({'styles': p['styles']} if name == p['id'] and p.get('styles') else {}),
        }
        for p in proposals
        for name in [p['id'], *covers.get(p['id'], [])]
    ]
    record['plans'] = {
        **{token: found for token, found in record['plans'].items() if token != plan['plan']},
        plan['plan']: rows,
    }
    record['plans'] = dict(list(record['plans'].items())[-20:])
    counts = {
        'suggestions': sum(1 for p in proposals if p['kind'] == 'edit'),
        'comments': sum(1 for p in proposals if p['kind'] == 'comment'),
    }
    # Which desk lines this send carries as suggestions its owner decides, and which as
    # comments the owner makes by hand (a fallback beside a teammate's suggestion, Comments
    # only, a Doc that cannot take suggestions, a note).
    carried = [
        {
            'how': 'suggestion'
            if p['kind'] == 'edit' and not covers.get(p['id']) and plan.get('mode') != 'comments'
            else 'hand',
            'lines': (paragraphs.get(p['id']) or {}).get('lines') or [],
            'place': (paragraphs.get(p['id']) or {}).get('place'),
        }
        for p in proposals
    ]
    record['meta'] = {
        **{token: found for token, found in record['meta'].items() if token in record['plans']},
        plan['plan']: {**counts, 'carried': carried},
    }
    studio.write_json(_sent_path(root, ident), record)
    return {
        **plan,
        **counts,
        'left': left,
        'later': later,
        'doc_overlap': theirs,
        'sent_before': before,
        'waiting': waiting,
    }


def _restyle_notes(proposal, sent, paragraphs):
    """Notes, each a comment of its own, for the words a suggestion sent before brought in
    whose bold, italic, underline or link the desk has changed since."""
    import json

    def each(runs):
        return [look for length, look in runs for _ in range(length)]

    def desk(look):
        return (
            bool(look.get('bold')),
            bool(look.get('italic')),
            False,
            bool(look.get('underline')),
            None,
            look.get('link') or None,
        )

    was, now, after = each(sent), each(proposal['styles']), proposal['after']
    if len(was) != len(after) or len(now) != len(after):
        return []
    found, group = [], None
    for at, (old, new) in enumerate(zip(was, now, strict=True)):
        if after[at].isspace():
            continue
        if old == new:
            group = None
        elif group and group[2:] == [old, new]:
            group[1] = at + 1
        else:
            group = [at, at + 1, old, new]
            found.append(group)
    place = paragraphs.get(proposal['id']) or {}
    notes = []
    for start, end, old, new in found:
        words = after[start:end]
        # Where the words sit in the replacement too: the same words twice are two notes.
        ident = json.dumps(['restyle', proposal['id'], start, words, new])
        note = {
            'id': 'desk-' + studio.digest(ident.encode())[:16],
            'kind': 'comment',
            'before': place.get('text') or proposal['before'],
            'reason': _note(_restyle(_quoted(words, 80), desk(old), desk(new)), []),
        }
        notes.append(note)
        paragraphs[note['id']] = {
            'paragraph': place.get('paragraph'),
            'near': place.get('near') or [],
            'about': place.get('text'),
            'float': True,
        }
    return notes


def _still_waits(inline, ident):
    """Whether this blog's suggestion sent with this id still waits in the Doc: the comment
    carrying its marker is open, and the paragraph it sits in holds a pending suggestion."""
    import google_roundtrip as rt
    import google_suggestions as suggestions
    from google_drive import GoogleError

    marker = '[Blog Studio ' + ident + ']'
    anchors = {anchor.get('anchorId'): anchor for anchor in suggestions.native_anchors(inline)}
    for thread in inline.get('comments', []):
        if marker not in thread.get('headPost', {}).get('content', ''):
            continue
        if thread.get('status', 'OPEN') != 'OPEN':
            continue
        for found in (anchors.get(thread.get('anchorId')) or {}).get('ranges', []):
            try:
                key, paragraph = rt.paragraph_at(
                    inline,
                    found.get('tabId') or rt.tabs(inline)[0]['tabProperties']['tabId'],
                    found['startIndex'],
                )
            except (GoogleError, KeyError):
                continue
            # Its paragraph holds a suggestion, or a suggested break split it from the one
            # before (a new paragraph the suggestion brings in ahead of it).
            if rt.suggestions(paragraph) or any(
                k == key and not settled for k, _, _, settled in _paragraph_texts(inline, [key[0]])
            ):
                return True
    return False


class _Text(tuple):
    """(key, paragraph, text, settled), with `positions`: the Doc's index of each character."""

    positions = ()


def _base_of(paragraph, start):
    """A Doc paragraph's words as the desk has them (its text as the Doc had it, without
    suggested insertions; a smart chip as its text, an image as nothing) and the Doc's index
    of each character."""
    import google_roundtrip as rt

    text, positions, at = [], [], start
    for element in paragraph.get('elements', []):
        run = element.get('textRun')
        if run is not None:
            for c in run.get('content', ''):
                if not run.get('suggestedInsertionIds'):
                    text.append(c)
                    positions.append(at)
                at += rt.utf16(c)
            continue
        kind = next((k for k in element if k not in ('startIndex', 'endIndex')), '')
        inner = element.get(kind) or {}
        shown = rt.chip_text(kind, inner) if kind != 'inlineObjectElement' else ''
        if not (isinstance(inner, dict) and inner.get('suggestedInsertionIds')):
            text.extend(shown)
            positions.extend([at] * len(shown))
        at += 1
    if text and text[-1] == '\n':
        text.pop()
        positions.pop()
    return ''.join(text), positions


def _paragraph_texts(inline, tabs, manuscript=False):
    """[(key, paragraph, text, settled)] for each Doc body paragraph, in order: its words as
    the Doc had them (without suggested insertions, suggested deletions as they stand), and
    whether nothing waits in it, nor in a paragraph a suggested break split it from. Each
    entry's `positions` gives the Doc's index of each character, around images and chips."""
    import google_roundtrip as rt

    if manuscript:
        from google_manuscript import view

        inline = view(inline)

    found, split = [], False
    for key, paragraph in rt.paragraphs(inline).items():
        elements = paragraph.get('elements', [])
        last = (elements[-1].get('textRun') or {}) if elements else {}
        was_split = split
        split = bool(last.get('suggestedInsertionIds')) and last.get('content', '').endswith('\n')
        if key[0] not in tabs or not elements:
            continue
        text, positions = _base_of(paragraph, key[1])
        entry = _Text((key, paragraph, text, not rt.suggestions(paragraph) and not was_split))
        entry.positions = positions
        found.append(entry)
    return found


def _where(texts, proposal, found):
    """(proposal located in the Doc, its paragraph's key, its paragraph, settled), or None
    when the Doc does not show what locates it as many times as the desk counted, or does not
    show it at all. Copies are counted in the text as the Doc had it, so a suggestion still
    waiting never makes or hides one."""
    before, context = proposal['before'], proposal.get('context')
    needle = context or before
    inner = needle.find(before) if context else 0
    hits = []
    for entry in texts:
        key, paragraph, text, settled = entry
        at = text.find(needle)
        while at != -1:
            hits.append((key, paragraph, entry, at + inner, settled))
            at = text.find(needle, at + 1)
    if (proposal.get('occurrence') or context) and len(hits) != found.get('matches'):
        return None
    occurrence = proposal.get('occurrence')
    if occurrence:
        if not 1 <= occurrence <= len(hits):
            return None
        hits = [hits[occurrence - 1]]
    if len(hits) != 1:
        return None
    key, paragraph, entry, at, settled = hits[0]
    positions = entry.positions or ()
    if at >= len(positions):
        return None
    located = {k: v for k, v in proposal.items() if k not in ('context', 'occurrence')}
    located['tab_id'], located['start_index'] = key[0], positions[at]
    return located, key, paragraph, settled


def _fits(inline, tabs, proposal):
    """Whether Google takes this proposal where it is located: one it would refuse (a style
    the Doc has and its Markdown does not show) goes as a comment instead."""
    import google_suggestions as suggestions
    from google_drive import GoogleError

    try:
        suggestions.validate(inline, [suggestions.locate(inline, proposal, tabs)], tabs)
    except GoogleError:
        return False
    return True


def _elsewhere(inline, tabs, texts, group, found, used):
    """One comment for changes that cannot go where they are meant, on the closest paragraph
    the Doc shows once, as it had it, that nothing else in this plan uses. A note keeps its
    own words; changes are quoted with their paragraph as it was and as the desk has it. It
    carries the marker of every change it stands for, so another computer knows them sent.
    None when no paragraph fits."""
    import json

    if found.get('float'):
        said = [group[0]['reason']]
    else:
        was, now = found.get('was') or '', found.get('now') or ''
        said = [
            'This change could not be placed in the Doc with certainty, so it is here to make '
            'by hand. The paragraph '
            + _quoted(was, 300)
            + ' '
            + ('reads ' + _quoted(now, 300) if now else 'is removed')
            + ' on the writing desk.'
        ] + [p['reason'] for p in group if p['kind'] == 'comment']
    single = len(group) == 1
    ident = (
        group[0]['id']
        if single
        else 'desk-'
        + studio.digest(json.dumps(['elsewhere'] + [p['id'] for p in group]).encode())[:16]
    )
    markers = [] if single else [' '.join('[Blog Studio ' + p['id'] + ']' for p in group)]
    about = found.get('about')
    # First the paragraph's own plain words, then the closest paragraph that is clean.
    own = ' '.join((found.get('text') or '').split())
    if own and not found.get('float'):
        spots = [spot for spot in _spots(inline, tabs) if spot[2] == own]
        if len(spots) == 1 and spots[0][0] not in used and spots[0][3]:
            key, _, _, (start, words) = spots[0]
            comment = {
                'id': ident,
                'kind': 'comment',
                'before': words,
                'reason': _note(' '.join(said), markers),
                'tab_id': key[0],
                'start_index': start,
            }
            if _fits(inline, tabs, comment):
                used.add(key)
                return comment
    for text in found.get('near') or []:
        wanted = ' '.join(text.split())
        exact = [
            number
            for number, (_, _, shown, settled) in enumerate(texts)
            if ' '.join(shown.split()) == wanted
        ]
        if len(exact) != 1 or not texts[exact[0]][3] or texts[exact[0]][0] in used:
            continue
        lead = '' if not about or text == about else 'In the paragraph ' + _quoted(about, 80) + ': '
        comment = {
            'id': ident,
            'kind': 'comment',
            'before': text,
            'reason': _note(lead + ' '.join(said), markers),
        }
        # Every place the Doc shows these words, so this paragraph is named by its place.
        hits = sum(_count(shown, text) for _, _, shown, _ in texts)
        if hits > 1:
            comment['occurrence'] = (
                sum(_count(shown, text) for _, _, shown, _ in texts[: exact[0]]) + 1
            )
        located = _where(texts, comment, {'matches': hits})
        if (
            located is not None
            and located[1] == texts[exact[0]][0]
            and _fits(inline, tabs, located[0])
        ):
            used.add(located[1])
            return located[0]
    # Else on the plain words of the closest paragraph that holds an image, a chip or someone
    # else's suggestion, words no suggestion touches.
    for text in found.get('near') or []:
        wanted = ' '.join(text.split())
        spots = [spot for spot in _spots(inline, tabs) if spot[2] == wanted]
        if len(spots) != 1 or spots[0][0] in used or not spots[0][3]:
            continue
        key, _, _, (start, words) = spots[0]
        lead = '' if not about or text == about else 'In the paragraph ' + _quoted(about, 80) + ': '
        comment = {
            'id': ident,
            'kind': 'comment',
            'before': words,
            'reason': _note(lead + ' '.join(said), markers),
            'tab_id': key[0],
            'start_index': start,
        }
        if _fits(inline, tabs, comment):
            used.add(key)
            return comment
    return None


def _spots(inline, tabs):
    """[(key, paragraph, its base words, (index, plain words) or None)] for every body
    paragraph: its words as the Doc had them, without images, and its longest stretch of
    plain words no suggestion touches, for a comment to sit on."""
    import google_roundtrip as rt
    import google_suggestions as suggestions
    from google_drive import GoogleError

    found = []
    for key, paragraph in rt.paragraphs(inline).items():
        if key[0] not in tabs:
            continue
        try:
            text, quiet = suggestions._quiet_text(paragraph, key[1])
        except GoogleError:
            continue
        base = ''.join(
            element['textRun']['content']
            for element in paragraph.get('elements', [])
            if 'textRun' in element and not element['textRun'].get('suggestedInsertionIds')
        )
        best, at = (0, 0), None
        for position, plain in enumerate([*quiet, False]):
            if plain and text[position] != '\n' and at is None:
                at = position
            elif (not plain or text[position] == '\n') and at is not None:
                if position - at > best[1] - best[0]:
                    best = (at, position)
                at = None
        a, b = best
        while a < b and text[a].isspace():
            a += 1
        while b > a and text[b - 1].isspace():
            b -= 1
        spot = (key[1] + rt.utf16(text[:a]), text[a:b]) if b > a else None
        found.append((key, paragraph, ' '.join(base.split()), spot))
    return found


def _touches_theirs(where):
    """Whether a located change's words overlap someone else's pending suggestion, or sit right
    beside one of their insertions."""
    import google_roundtrip as rt

    located, key, paragraph, _ = where
    at = key[1]

    marks = []
    for element in paragraph.get('elements', []):
        run = element.get('textRun')
        if run is None:
            marks.append((at, at + 1, False))
            at += 1
            continue
        size = rt.utf16(run.get('content', ''))
        touched = bool(run.get('suggestedInsertionIds') or run.get('suggestedDeletionIds'))
        marks.append((at, at + size, touched))
        at += size
    start = located['start_index']
    end = start + rt.utf16(located['before'])
    return any(touched and a <= end and start <= b for a, b, touched in marks)


def _not_pending(inline, document, proposals, expected, ours=None):
    """The proposals that can go now, read from the Doc: how many wait for a pending
    suggestion in their paragraph, and how many could not be placed anywhere. A change that
    could land somewhere other than the paragraph it is meant for (the Doc shows its quote a
    different number of times than the desk counted, or it resolves to a paragraph with other
    words) goes as a comment on the closest paragraph that is certain instead, and one
    paragraph's changes go, wait or move together. A note for a paragraph as a whole is placed
    last, on a paragraph nothing else uses. Returns (free, waiting, unplaced, covers,
    later): covers names the changes each such comment stands for, and later counts the notes
    with no free paragraph nearby, which go with the next send."""
    import json

    tabs = document['tab_ids']
    from google_manuscript import PROJECTION, view

    if document.get('projection') == PROJECTION:
        inline = view(inline)
    texts = _paragraph_texts(inline, tabs)
    # Only this blog's own suggestions hold their paragraphs: a change in a paragraph that
    # holds only someone else's goes as a comment instead, theirs untouched.
    mine = _ours(inline, texts, ours or ())
    held = {
        ' '.join(text.split()) for key, _, text, settled in texts if not settled and key in mine
    }
    groups, floats = {}, []
    for proposal in proposals:
        found = expected.get(proposal['id']) or {}
        if found.get('float'):
            floats.append(proposal)
            continue
        place = json.dumps([found.get('paragraph'), found.get('near')])
        groups.setdefault(place, []).append(proposal)
    free, waiting, moved, used, stopped, theirs = [], 0, [], set(), set(), 0
    for group in groups.values():
        states = []
        for proposal in group:
            found = expected.get(proposal['id']) or {}
            meant = ' '.join((found.get('text') or '').split())
            where = _where(texts, proposal, found)
            if where is not None and not where[3] and where[1] in mine:
                states.append(('wait', proposal))
                continue
            if where is not None and not where[3] and _touches_theirs(where):
                theirs += 1  # Words or a place someone else's suggestion also changes.
            if (
                where is None
                or (meant and ' '.join(_text_of(texts, where[1]).split()) != meant)
                or not _fits(inline, tabs, where[0])
            ):
                states.append(('wait' if meant in held else 'move', proposal))
            else:
                states.append(('go', where))
        if any(state == 'wait' for state, _ in states):
            waiting += len(group)  # Its paragraph holds an earlier suggestion; it goes next time.
            stopped.add((expected.get(group[0]['id']) or {}).get('paragraph'))
        elif any(state == 'move' for state, _ in states):
            moved.append(group)
        else:
            for _, (located, key, _, _) in states:
                free.append(located)
                used.add(key)
    unplaced, covers, later = 0, {}, 0
    for group in moved:
        found = expected.get(group[0]['id']) or {}
        comment = _elsewhere(inline, tabs, texts, group, found, used)
        if comment is None:
            unplaced += len(group)
            continue
        free.append(comment)
        covers[comment['id']] = [p['id'] for p in group if p['id'] != comment['id']]
        expected.setdefault(comment['id'], {'paragraph': found.get('paragraph')})
    for proposal in floats:
        found = expected.get(proposal['id']) or {}
        if found.get('paragraph') in stopped:
            waiting += 1  # A note for a paragraph that waits goes with it.
            continue
        comment = _elsewhere(inline, tabs, texts, [proposal], found, used)
        if comment is None:
            later += 1  # Every paragraph near it has a change in this plan: it goes next time.
        else:
            free.append(comment)
    return free, waiting, unplaced, covers, later, theirs


def _ours(inline, texts, edits):
    """The Doc paragraphs holding one of this blog's own suggestions still waiting: where the
    open comment that came with one of its edits (`edits`, their ids) sits, and any paragraph a
    suggested break splits from it. A note or other comment of ours holds nothing."""
    import google_roundtrip as rt
    import google_suggestions as suggestions
    from google_drive import GoogleError

    anchors = {anchor.get('anchorId'): anchor for anchor in suggestions.native_anchors(inline)}
    keys = set()
    markers = ['[Blog Studio ' + ident + ']' for ident in edits]
    for thread in inline.get('comments', []):
        content = thread.get('headPost', {}).get('content', '')
        if not any(marker in content for marker in markers):
            continue
        if thread.get('status', 'OPEN') != 'OPEN':
            continue
        for found in (anchors.get(thread.get('anchorId')) or {}).get('ranges', []):
            try:
                key, _ = rt.paragraph_at(
                    inline,
                    found.get('tabId') or rt.tabs(inline)[0]['tabProperties']['tabId'],
                    found['startIndex'],
                )
            except (GoogleError, KeyError):
                continue
            keys.add(key)
    order = [key for key, _, _, _ in texts]
    for at, (key, _, _, settled) in enumerate(texts):
        if at and not settled and order[at - 1] in keys and not texts[at - 1][3]:
            keys.add(key)  # Split from one of ours by a suggested break.
    return keys


def _text_of(texts, key):
    return next((text for k, _, text, _ in texts if k == key), '')


def google_send(root, ident, data):
    """Send a confirmed plan through the existing ledger, once, while the desk text is as
    it was when the plan was made."""
    import google_drive as drive

    import manuscript_editor

    import google_roundtrip as rt

    expected = _google_expected(root, ident)
    client = drive.Client(drive.account_for(root))
    _, _, base = _google_base(root, ident)
    document = base['document']['document_id']
    try:
        earlier = rt.suggestion_ids(rt.inline_read(client, document))
    except Exception:  # noqa: BLE001 (a read that fails leaves the send to say so)
        earlier = None
    result = manuscript_editor.google_send(client, root, ident, data, expected)
    record = _sent(root, ident)
    if earlier is not None and result.get('status') in ('verified-pending', 'verified-comments'):
        # The suggestions this send made are Blog Studio's own, never the Doc's to show.
        try:
            made = rt.suggestion_ids(rt.inline_read(client, document)) - earlier
        except Exception:  # noqa: BLE001
            made = set()
        record['own'] = sorted(set(record.get('own') or []) | made)[-2000:]
        studio.write_json(_sent_path(root, ident), record)
    rows = record['plans'].pop(data.get('plan'), None)
    if rows:
        known = {row.get('id') for row in record['sent']}
        record['sent'] = (record['sent'] + [row for row in rows if row.get('id') not in known])[
            -500:
        ]
        studio.write_json(_sent_path(root, ident), record)
    meta = record['meta'].get(data.get('plan'))
    if meta and result.get('status') in ('verified-pending', 'verified-comments'):
        # The receipt the desk and Home show: what went, when, and what waits for the owner.
        record['meta'].pop(data.get('plan'))
        n, m = meta.get('suggestions', 0), meta.get('comments', 0)
        if result['status'] == 'verified-comments':
            n, m = 0, n + m
        # The plan that went is kept by name, so the send can be verified again later.
        record['last'] = {
            'at': studio.now(),
            'suggestions': n,
            'comments': m,
            'plan': data.get('plan'),
        }
        record['waiting'] = (record['waiting'] or 0) + n
        if result['status'] == 'verified-comments':
            # Every change went as a comment: none is a suggestion that waits or is decided.
            made = {row.get('id') for row in rows or []}
            for row in record['sent']:
                if row.get('id') in made:
                    row['kind'] = 'comment'
        for entry in meta.get('carried') or []:
            how = 'hand' if result['status'] == 'verified-comments' else entry.get('how')
            record['carried'].append(
                {
                    'transfer': base['transfer'],
                    'how': how,
                    'lines': entry.get('lines') or [],
                    'place': entry.get('place'),
                }
            )
        record['carried'] = record['carried'][-2000:]
        studio.write_json(_sent_path(root, ident), record)
    return result


def google_check(root, ident, data):
    """Verify again: read the blog's Doc for a plan this desk sent, and say whether it still
    holds what was sent. Google is only read, the desk is not changed, and the record of the
    send stays as it was: a Doc whose owner has since decided the suggestions differs from
    what was sent, and that is said, never recorded as a send that needs attention."""
    import google_drive as drive

    import manuscript_editor

    _google_base(root, ident)  # A blog with no Doc that takes suggestions is refused here.
    client = drive.Client(drive.account_for(root))
    result = manuscript_editor.google_check(client, root, ident, data)
    return {
        **result,
        'checked_at': result.get('checked_at') or studio.now(),
        'as_sent': result.get('status') in manuscript_editor.VERIFIED,
    }


def google_state(root, ident, directory, record):
    """The Doc as the desk and Home show it, read on this computer only (Google is not read):
    the last send, this blog's own suggestions waiting there as the Doc was last read, the last
    bring-back, and whether the desk has changes the Doc has not been sent as suggestions. None
    without a Doc that takes suggestions."""
    if not google_ready(record):
        return None
    base = record['google']['baselines']['draft']
    sent = _sent(root, ident)
    path = directory / 'DRAFT.md'
    body = path.read_bytes() if path.is_file() else b''
    unsent = studio.digest(body) != base.get('local_sha256') and _unsent(
        directory, base, body.decode('utf-8', 'replace'), sent
    )
    return {
        'last': sent['last'],
        'waiting': sent['waiting'] or 0,
        'brought': sent['brought'],
        'unsent': unsent,
    }


_UNSENT = {}  # (folder, DRAFT.md digest, baseline, ledger) -> whether a change is unsent


def _unsent(directory, base, body, sent):
    """Whether the desk has a change for the Doc, as a plan would make it against the Doc's
    baseline, that has not gone to this baseline as a suggestion: never sent, sent as a
    comment for the owner to make by hand, or a title other than the Doc's name as last read.
    Read locally (Google is not), and kept while nothing it reads changes."""
    from google_workflow import snapshot_path

    edits = sorted(
        row.get('id', '')
        for row in sent['sent']
        if row.get('kind', 'edit') == 'edit'
        and row.get('base', base['transfer']) == base['transfer']
    )
    key = (
        str(directory),
        studio.digest(body.encode()),
        base['transfer'],
        tuple(edits),
        sent['name'],
    )
    if key in _UNSENT:
        return _UNSENT[key]
    try:
        baseline = snapshot_path(directory, base['transfer'], 'document').read_text()
    except (OSError, ValueError):
        return True
    title = _desk_title(body)
    gone = set(edits)
    found = any(p['id'] not in gone for p in google_changes(baseline, body, title)[0]) or bool(
        sent['name'] and title is not None and title != sent['name']
    )
    if len(_UNSENT) > 200:
        _UNSENT.clear()
    _UNSENT[key] = found
    return found


def _unsent_kinds(directory, base, sent):
    """How the desk's changes the Doc lacks went, read locally as `_unsent` reads them: 'never'
    for one not sent to this baseline (or a title other than the Doc's name), 'hand' for one
    that went as a comment for the owner to make by hand. Empty when all went as suggestions."""
    from google_workflow import snapshot_path

    path = directory / 'DRAFT.md'
    body = path.read_text(errors='replace') if path.is_file() else ''
    try:
        baseline = snapshot_path(directory, base['transfer'], 'document').read_text()
    except (OSError, ValueError):
        return {'never'}
    how = {
        row.get('id', ''): row.get('kind', 'edit')
        for row in sent['sent']
        if row.get('base', base['transfer']) == base['transfer']
    }
    kinds = set()
    for proposal in google_changes(baseline, body, _desk_title(body))[0]:
        went = how.get(proposal['id'])
        if went is None:
            kinds.add('never')
        elif went != 'edit':
            kinds.add('hand')
    title = _desk_title(body)
    if sent['name'] and title is not None and title != sent['name']:
        kinds.add('never')
    return kinds


# The Finishing tools as the desk names them, in the panel's order, for Home's status line.
NAMES = {
    'copyedit': 'Copy edit',
    'humanize': 'Humanize',
    'facts': 'Check facts',
    'geo': 'GEO',
    'faq': 'FAQ',
    'table': 'Comparison table',
    'quotes': 'Quotes from sources',
    'takeaways': 'Key takeaways',
    'alt': 'Image alt text',
    'opener': 'Definition opening',
    'headline': 'Headline and opening',
    'feedback': 'Feedback',
    'voice': 'Apply a voice',
}


def attention(root, ident, draft, directory, record):
    """What a desk blog waits on, for Home and Blogs, read on this computer only: suggestions
    still open, by tool, its own suggestions waiting in the Doc, and desk changes the Doc has
    not been sent ([] when nothing does), and when the desk last sent to its Doc (`sent`)."""
    said = []
    found = summary(root, ident, draft)
    for tool, name in NAMES.items():
        open_ = sum(
            1 for item in (found.get(tool) or {}).get('items', []) if item.get('state') == 'open'
        )
        if open_:
            said.append(name + ' · ' + str(open_) + ' to review')
    state = google_state(root, ident, directory, record)
    if state and state['waiting']:
        said.append('Doc: ' + str(state['waiting']) + ' waiting')
    if state and state['unsent']:
        said.append('Unsent desk changes')
    return {'needs': said, 'sent': ((state or {}).get('last') or {}).get('at')}


def _waiting(inline, record, base, pending):
    """How many of this blog's sent changes still wait for the Doc's owner: each sent
    suggestion whose marker is open over a pending suggestion, or, where the Doc's comments
    cannot say, how many of the suggestions this blog's sends made are still pending."""
    held = set(pending) & set(record['own'])
    if not held:
        return 0
    rows = [
        row
        for row in record['sent']
        if row.get('kind', 'edit') == 'edit'
        and not row.get('settled')
        and row.get('base', base['transfer']) == base['transfer']
    ]
    return sum(1 for row in rows if _still_waits(inline, row['id'])) or len(held)
