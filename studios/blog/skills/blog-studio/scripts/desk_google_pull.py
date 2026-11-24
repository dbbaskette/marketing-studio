"""Bringing the Google Doc's changes back to the desk (google_pull, google_take).

Part of desk_finish, which keeps every name its callers use.
"""

import re

import desk
import desk_images
import studio
from desk_google import (
    _counted,
    _google_base,
    _sent,
    _sent_path,
    _unsent_kinds,
    _waiting,
)
from desk_google_changes import (
    _line_key,
)


def _merge3(base, ours, theirs):
    """A three-way merge of key lists, by place: [(kind, (b0, b1), (o0, o1), (t0, t1))],
    each kind 'same', 'ours' (only the desk changed), 'theirs' (only the Doc changed) or
    'conflict', with the range of the baseline's, the desk's and the Doc's keys it covers (google_workflow.merge_chunks,
    keeping places instead of lines)."""
    import difflib

    def blocks(other):
        return difflib.SequenceMatcher(None, base, other, autojunk=False).get_matching_blocks()

    ours_blocks, theirs_blocks = blocks(ours), blocks(theirs)
    regions, i, j = [], 0, 0
    while i < len(ours_blocks) and j < len(theirs_blocks):
        base_a, start_a, size_a = ours_blocks[i]
        base_b, start_b, size_b = theirs_blocks[j]
        low, high = max(base_a, base_b), min(base_a + size_a, base_b + size_b)
        if low < high:
            regions.append((low, high, start_a + low - base_a, start_b + low - base_b))
        if base_a + size_a < base_b + size_b:
            i += 1
        else:
            j += 1
    regions.append((len(base), len(base), len(ours), len(theirs)))
    chunks, at_base, at_ours, at_theirs = [], 0, 0, 0
    for low, high, in_ours, in_theirs in regions:
        original, mine, yours = (
            base[at_base:low],
            ours[at_ours:in_ours],
            theirs[at_theirs:in_theirs],
        )
        if original and len(original) == len(mine) == len(yours) and len(original) > 1:
            # Neighbouring paragraphs each changed on one side: each is merged on its own.
            for step, (was, one, other) in enumerate(zip(original, mine, yours, strict=True)):
                kind = (
                    'same'
                    if one == other
                    else 'theirs'
                    if one == was
                    else 'ours'
                    if other == was
                    else 'conflict'
                )
                chunks.append(
                    (
                        kind,
                        (at_base + step, at_base + step + 1),
                        (at_ours + step, at_ours + step + 1),
                        (at_theirs + step, at_theirs + step + 1),
                    )
                )
        elif original or mine or yours:
            kind = (
                'same'
                if mine == yours
                else 'theirs'
                if mine == original
                else 'ours'
                if yours == original
                else 'conflict'
            )
            chunks.append((kind, (at_base, low), (at_ours, in_ours), (at_theirs, in_theirs)))
        if high > low:
            chunks.append(
                (
                    'same',
                    (low, high),
                    (in_ours, in_ours + high - low),
                    (in_theirs, in_theirs + high - low),
                )
            )
        at_base, at_ours, at_theirs = high, in_ours + high - low, in_theirs + high - low
    return chunks


def _lines(text):
    """A part's paragraphs (its non-blank lines) and, for each, its key (`_line_key`)."""
    raw = [line for line in (text or '').split('\n') if line.strip()]
    return raw, [_line_key(line) for line in raw]


def _matched(left, right):
    """Pairs of places, left to right, of sections with the same heading, in order."""
    pairs, used = {}, set()
    for at, one in enumerate(left):
        for to, other in enumerate(right):
            if to not in used and desk._same_heading(one['heading'], other['heading']):
                pairs[at] = to
                used.add(to)
                break
    return pairs


PULL_TOO_MUCH = 'The Doc and the desk both changed '


def _pull(root, ident, directory, base, body):
    """What bringing the Doc's accepted text to the desk changes, paragraph by paragraph.

    Each part (the opening, each section, paired by heading) is merged three ways: the Doc
    as the desk and the Doc last agreed (its baseline: when it was linked, or the last
    bring-back), the desk now, and the Doc now. A paragraph only the Doc changed takes the
    Doc's words. A paragraph only the desk changed keeps the desk's, unless the desk sent
    exactly those words as suggestions and the Doc kept its own: the owner rejected them, so
    the Doc's words come back. A paragraph both changed takes the Doc's words only when the
    desk's went as suggestions the owner then decided; otherwise its part is refused, so a
    desk change is never lost. Words that went as comments (Comments only, a Doc that cannot
    take suggestions, beside a teammate's suggestion, by hand) are the owner's to make, so
    the desk keeps them. Sections keep the desk's order: one new in the Doc comes after the
    section before it, one the Doc removed goes when the desk left it alone, and one the desk
    removed or added stays as the desk has it. The title stays the desk's: the Doc's name is
    not its text."""
    import google_workflow as workflow

    draft = desk.read(root, ident)
    doc = desk.split(body, title=draft['title'])
    was = workflow.baseline_text(directory, base)
    linked = desk.split(was, title=draft['title']) if was is not None else None
    sent = _sent(root, ident)
    # What each verified send carried to this baseline, by the paragraph it was in: its
    # words and which copy of them. The newest carried for a place is the one that counts.
    carried = {}
    for entry in sent['carried']:
        place = entry.get('place')
        if (
            entry.get('transfer') == base['transfer']
            and isinstance(place, list)
            and len(place) == 2
        ):
            carried.setdefault(tuple(place), []).append(entry)
    # Each baseline paragraph's place, counted through the whole Doc as the plan counts it.
    counted, places = {}, {}

    def placed(label, keys):
        out = []
        for key in keys:
            out.append((key, counted.get(key, 0)))
            counted[key] = counted.get(key, 0) + 1
        places[label] = out

    if linked is not None:
        placed('opening', _lines(linked['opening'])[1])
        for at, section in enumerate(linked['sections']):
            placed(at, _lines(section['text'])[1])
    changes, refused, pictures, withdrawn = [], [], [], []
    held = {desk_images.key(label): entry for label, entry in (draft.get('images') or {}).items()}
    sent_images = {}

    def images_fit(text, label_of):
        # A Doc image the Doc's words bring that the desk lacks comes with them; one the
        # desk holds under the same label with other data refuses the part, so none is swapped.
        for found in desk_images.REFERENCE.finditer(text or ''):
            label = desk_images.key(found.group(2) or found.group(1))
            theirs = next(
                (
                    (raw, entry)
                    for raw, entry in (doc.get('images') or {}).items()
                    if desk_images.key(raw) == label
                ),
                None,
            )
            ours = held.get(label)
            if theirs is None:
                if ours is None:
                    pictures.append(label_of)
                    return False
                continue
            if ours is not None and desk_images._key_of(ours) != desk_images._key_of(theirs[1]):
                pictures.append(label_of)
                return False
            if ours is None:
                sent_images[theirs[0]] = theirs[1]
        return True

    def name(heading):
        return ' '.join(re.sub(r'^(\*\*|__)(.+)\1$', r'\2', heading.strip()).split())

    def sent_as(where):
        """The lines suggested for these baseline paragraphs, in order, or None unless each
        had its newest carried change go as a suggestion."""
        lines = []
        for spot in where:
            found = carried.get(spot)
            if not found or found[-1].get('how') != 'suggestion':
                return None
            lines += [line.strip() for line in found[-1].get('lines') or []]
        return lines if where else None

    def reaches(spot, key, forward):
        """Whether the newest change carried for this unchanged baseline paragraph also
        carried new lines after it (`forward`) or before it: a line the desk added or put in
        place of a paragraph rides on the paragraph beside it (the one after it at the top
        of the opening or under a heading), so that paragraph is part of what was sent."""
        found = carried.get(spot)
        lines = [line.strip() for line in (found[-1].get('lines') or [])] if found else []
        if key not in lines:
            return False
        return lines[-1] != key if forward else lines[0] != key

    def merged(label, then_at, mine, theirs):
        """The part's text after the merge, or None when it is refused."""
        mine_raw, mine_keys = _lines(mine)
        their_raw, their_keys = _lines(theirs)
        if mine_keys == their_keys:
            return mine
        if then_at not in places:
            refused.append(label)
            return None
        where = places[then_at]
        then_keys = [key for key, _ in where]
        out, took = [], []

        def widened(b0, b1, o0, o1, t0, t1):
            # With a paragraph beside the span, unchanged on both sides, whose sent lines reach
            # into it: a paragraph rewritten outright goes as its deletion and the new words on
            # its neighbour, and only the two together say what the desk sent (#267).
            if (
                b0 > 0
                and o0 > 0
                and t0 > 0
                and then_keys[b0 - 1] == mine_keys[o0 - 1] == their_keys[t0 - 1]
                and reaches(where[b0 - 1], then_keys[b0 - 1], True)
            ):
                b0, o0, t0 = b0 - 1, o0 - 1, t0 - 1
            if (
                b1 < len(then_keys)
                and o1 < len(mine_keys)
                and t1 < len(their_keys)
                and then_keys[b1] == mine_keys[o1] == their_keys[t1]
                and reaches(where[b1], then_keys[b1], False)
            ):
                b1, o1, t1 = b1 + 1, o1 + 1, t1 + 1
            return b0, b1, o0, o1, t0, t1

        def sent_is(span, keys, side):
            """Whether the desk sent exactly these words from the span's baseline paragraphs,
            as suggestions: `keys` as the desk (side 0) or the Doc (side 1) has them now."""
            b0, b1, o0, o1, t0, t1 = span
            suggested = sent_as(where[b0:b1])
            return suggested is not None and suggested == keys[(o0, t0)[side] : (o1, t1)[side]]

        chunks = _merge3(then_keys, mine_keys, their_keys)
        for at, (kind, (b0, b1), (o0, o1), (t0, t1)) in enumerate(chunks):
            if kind == 'same':
                out += mine_raw[o0:o1]
                continue
            # The chunk read alone, with the paragraphs beside it, and as one with the changed
            # paragraphs next to it (a rewrite beside an edit is merged a paragraph at a time).
            first = last = at
            while first > 0 and chunks[first - 1][0] != 'same':
                first -= 1
            while last + 1 < len(chunks) and chunks[last + 1][0] != 'same':
                last += 1
            alone = (b0, b1, o0, o1, t0, t1)
            around = [
                widened(*alone),
                widened(
                    chunks[first][1][0],
                    chunks[last][1][1],
                    chunks[first][2][0],
                    chunks[last][2][1],
                    chunks[first][3][0],
                    chunks[last][3][1],
                ),
            ]
            if kind == 'theirs' and any(sent_is(span, their_keys, 1) for span in [alone, *around]):
                # The owner accepted what the desk sent, all of it or a part, and the desk has
                # since changed it back: neither is taken over the other.
                withdrawn.append(label)
                return None
            if kind == 'theirs' or (
                # The desk's words here are exactly what it sent from these places as
                # suggestions: the owner decided them, so the Doc's words stand. They are never
                # read alone, so a change sent with its neighbour is never taken for a part.
                kind in ('ours', 'conflict') and any(sent_is(span, mine_keys, 0) for span in around)
            ):
                out += their_raw[t0:t1]
                took += their_raw[t0:t1]
            elif kind == 'ours':
                out += mine_raw[o0:o1]
            else:
                refused.append(label)
                return None
        if out == mine_raw:
            return mine
        if not images_fit('\n'.join(took), label):
            return None
        return theirs if out == their_raw else '\n\n'.join(out)

    opening = merged('Opening', 'opening', draft['opening'], doc['opening'])
    if opening is None:
        opening = draft['opening']
    elif opening != draft['opening']:
        changes.append(
            {
                'kind': 'changed',
                'part': 'opening',
                'name': 'Opening',
                'before': draft['opening'],
                'after': opening,
            }
        )
    then_sections = linked['sections'] if linked else []
    to_doc, to_then = (
        _matched(draft['sections'], doc['sections']),
        _matched(draft['sections'], then_sections),
    )
    doc_then = _matched(doc['sections'], then_sections)
    sections = []
    for at, one in enumerate(draft['sections']):
        label = name(one['heading'])
        then = then_sections[to_then[at]]['text'] if at in to_then else None
        if at in to_doc:
            written = doc['sections'][to_doc[at]]
            if at not in to_then and _lines(one['text'])[1] != _lines(written['text'])[1]:
                # New on the desk and in the Doc under one heading, written differently.
                refused.append(label)
                sections.append(one)
                continue
            if at not in to_then:
                sections.append(one)  # New on the desk and in the Doc, written alike.
                continue
            text = merged(label, to_then[at], one['text'], written['text'])
            if text is not None and text != one['text']:
                changes.append(
                    {
                        'kind': 'changed',
                        'part': one['id'],
                        'name': label,
                        'before': one['text'],
                        'after': text,
                    }
                )
                one = {**one, 'text': text}
            sections.append(one)
        elif at in to_then:
            # The Doc removed it: it goes when the desk left it as they agreed.
            if _lines(one['text'])[1] == _lines(then)[1]:
                changes.append(
                    {
                        'kind': 'removed',
                        'part': one['id'],
                        'name': label,
                        'before': one['text'],
                        'after': '',
                    }
                )
            else:
                refused.append(label)
                sections.append(one)
        else:
            sections.append(one)  # New on the desk: kept, and still to send.
    # A section new in the Doc comes after the section before it; one the desk removed stays
    # out when the Doc left it alone, and is refused when the Doc changed it.
    for at, written in enumerate(doc['sections']):
        if at in to_doc.values():
            continue
        label = name(written['heading'])
        if at in doc_then:
            if _lines(written['text'])[1] != _lines(then_sections[doc_then[at]]['text'])[1]:
                refused.append(label)
            continue
        if not images_fit(written['text'], label):
            continue
        changes.append({'kind': 'added', 'name': label, 'before': '', 'after': written['text']})
        previous = next(
            (
                place
                for back in range(at - 1, -1, -1)
                for desk_at, doc_at in to_doc.items()
                if doc_at == back
                for place, kept in enumerate(sections)
                if kept['id'] == draft['sections'][desk_at]['id']
            ),
            None,
        )
        sections.insert(0 if previous is None else previous + 1, {**written, 'id': None})
    markdown = desk.join(
        {
            'title': draft['title'],
            'opening': opening,
            'sections': [
                {key: s[key] for key in ('heading', 'text', 'level', 'mark') if key in s}
                for s in sections
            ],
            'images': sent_images,
        },
    )
    # The parts whose words still differ between the desk, as bringing back leaves it, and
    # the Doc, so a check that brings nothing never reads as the two agreeing.
    differs = ['Opening'] if _lines(opening)[1] != _lines(doc['opening'])[1] else []
    paired = _matched(sections, doc['sections'])
    for at, kept in enumerate(sections):
        if (
            at not in paired
            or _lines(kept['text'])[1] != _lines(doc['sections'][paired[at]]['text'])[1]
        ):
            differs.append(name(kept['heading']))
    differs += [
        name(written['heading'])
        for at, written in enumerate(doc['sections'])
        if at not in paired.values()
    ]
    return {
        'changes': changes,
        'refused': refused,
        'pictures': pictures,
        'withdrawn': withdrawn,
        'differs': differs,
        'markdown': markdown,
    }


def _pull_capture(root, ident, base, folder):
    """The Doc's accepted text and formatting, captured into `folder` as the chat's pull
    does; pending suggestions stay in Google, never accepted or rejected."""
    import google_drive as drive
    import google_reconcile as reconcile
    import google_roundtrip as rt
    import google_workflow as workflow
    from types import SimpleNamespace

    client = drive.Client(drive.account_for(root))
    document = base['document']['document_id']
    rt.capture(
        client,
        document,
        reconcile._tab(root, ident),
        folder,
        manuscript=reconcile._manuscript(root, ident),
    )
    observation, body = workflow.observed(
        SimpleNamespace(snapshot=str(folder), observation=None, file=None)
    )
    inline = _doc_inline(client, document)
    return observation, body, _waiting(inline, _sent(root, ident), base, rt.suggestion_ids(inline))


def _doc_inline(client, document):
    """The Doc with its pending suggestions and comment threads, or without the threads where
    Google offers none, as a plan reads it."""
    import google_roundtrip as rt
    import google_suggestions as suggestions
    from google_drive import GoogleError
    from google_review_comments import unavailable

    try:
        return suggestions.review_read(client, document)
    except GoogleError as error:
        if not unavailable(error):
            raise
        return rt.inline_read(client, document)


def _pull_said(found, waiting, unsent=frozenset()):
    """Why nothing can be brought back now, or None when it can. `unsent`: how the desk's
    changes the Doc lacks went (`_unsent_kinds`)."""
    if waiting:
        return (
            _counted(waiting, 'suggestion', 'suggestions')
            + ' sent from the desk '
            + ('still waits' if waiting == 1 else 'still wait')
            + ' for the Doc’s owner. Bring the accepted changes once '
            + ('it is' if waiting == 1 else 'they are')
            + ' decided, so the desk’s text for '
            + ('it is' if waiting == 1 else 'them is')
            + ' not taken back meanwhile.'
        )
    if found['refused']:
        return (
            PULL_TOO_MUCH
            + ', '.join('“' + name + '”' for name in found['refused'])
            + ' since they last agreed. Nothing is brought back, so no desk change is lost: '
            'send the desk’s changes first, or say “Pull from Google Docs” in chat to choose '
            'the wording for each.'
        )
    if found.get('withdrawn'):
        return (
            ', '.join('“' + name + '”' for name in found['withdrawn'])
            + ': you changed this back on the desk after sending it, and the Doc’s owner '
            'accepted the sent version. Nothing is brought back, so neither replaces the other: '
            'send the desk’s words again, or say “Pull from Google Docs” in chat.'
        )
    if found['pictures']:
        return (
            ', '.join('“' + name + '”' for name in found['pictures'])
            + (' uses' if len(found['pictures']) == 1 else ' use')
            + ' an image the desk holds differently, or one the Doc did not send. Nothing is '
            'brought back, so no image is swapped: say “Pull from Google Docs” in chat.'
        )
    if not found['changes']:
        said = 'Nothing to bring back: the desk has every accepted change in the Doc.'
        differs = found.get('differs') or []
        if not differs:
            return said
        said += (
            ' '
            + ', '.join('“' + name + '”' for name in differs)
            + (' reads' if len(differs) == 1 else ' read')
            + ' differently on the desk and in the Doc'
        )
        # What the desk did with what differs: kept changes it never sent, changes that went as
        # comments for the owner to make by hand, or, with neither, suggestions the owner did
        # not accept. Neither side replaces the other.
        why = []
        if 'never' in unsent:
            why.append('some of the desk’s changes have not been sent to the Doc')
        if 'hand' in unsent:
            why.append('some went to the Doc as comments, for its owner to make by hand')
        if not why:
            why.append('the Doc’s owner did not accept what the desk sent')
        said += ': ' + '; '.join(why) + '.'
        if unsent == {'never'}:
            return said + ' Send them when they are ready.'
        return said + ' Say “Pull from Google Docs” in chat to choose the wording for each.'
    return None


def google_pull(root, ident):
    """Read the Doc's accepted text and say which desk parts bringing it back changes.
    Nothing on the desk changes and nothing is written to Google; the check is kept on this
    computer for `google_take`."""
    import google_drive as drive
    import google_intake
    import google_reconcile as reconcile
    import uuid

    directory, record, base = _google_base(root, ident)
    token = uuid.uuid4().hex
    folder = studio.inside(drive.staging_root(root, create=True), 'desk-pull-' + token)
    folder.mkdir(mode=0o700)
    try:
        observation, body, waiting = _pull_capture(root, ident, base, folder / 'snapshot')
        found = _pull(root, ident, directory, base, body)
        sent = _sent(root, ident)
        sent['waiting'] = waiting
        studio.write_json(_sent_path(root, ident), sent)
        unsent = (
            _unsent_kinds(directory, base, sent)
            if found['differs'] and not found['changes']
            else set()
        )
        said = _pull_said(found, waiting, unsent)
        studio.write_json(
            folder / 'preview.json',
            {
                'id': ident,
                'draft': studio.digest((directory / 'DRAFT.md').read_bytes()),
                'transfer': base['transfer'],
                'account': drive.account_for(root),
                'capture': google_intake.fingerprint(folder / 'snapshot'),
                'remote_guard': reconcile.remote_guard(observation),
                'markdown': studio.digest(found['markdown'].encode()),
                'ready': said is None,
            },
        )
        return {
            'preview': token,
            'changes': found['changes'],
            'refused': found['refused'],
            'waiting': waiting,
            'ready': said is None,
            'said': said,
            'google_written': False,
        }
    except BaseException:
        drive.discard(root, folder)
        raise


def google_take(root, ident, data):
    """Bring the checked Doc text to the desk, once: each part it changes keeps the desk's
    text first in History ("Before Google's accepted text"), as the chat's pull does, and the
    Doc's text becomes the new common baseline. Refused when the desk or the Doc changed since
    the check. Google is read again to be sure, and never written."""
    import google_drive as drive
    import google_intake
    import google_reconcile as reconcile
    import google_workflow as workflow
    from types import SimpleNamespace
    import uuid

    if data.get('confirmed') is not True:
        raise ValueError('Check what the Doc brings back, then confirm it.')
    token = data.get('preview')
    if not isinstance(token, str) or not re.fullmatch('[a-f0-9]{32}', token):
        raise ValueError('Check the Doc again before bringing its changes back.')
    folder = studio.inside(drive.staging_root(root), 'desk-pull-' + token)
    saved = studio.read_json(folder / 'preview.json') if (folder / 'preview.json').is_file() else {}
    if saved.get('id') != ident:
        raise ValueError('Check the Doc again before bringing its changes back.')
    if saved.get('result'):
        return saved['result']
    directory, record, base = _google_base(root, ident)
    if not saved.get('ready'):
        raise ValueError('Check the Doc again before bringing its changes back.')
    if (
        saved['draft'] != studio.digest((directory / 'DRAFT.md').read_bytes())
        or saved['transfer'] != base['transfer']
    ):
        raise ValueError('The desk changed since the check. Check the Doc again; nothing changed.')
    if drive.account_for(root) != saved['account']:
        raise ValueError('The selected Google account changed. Check the Doc again.')
    if google_intake.fingerprint(folder / 'snapshot') != saved['capture']:
        raise ValueError('The saved check changed. Check the Doc again.')
    fresh = folder / ('check-' + uuid.uuid4().hex)
    try:
        observation, body, waiting = _pull_capture(root, ident, base, fresh)
        found = _pull(root, ident, directory, base, body)
        if (
            reconcile.remote_guard(observation) != saved['remote_guard']
            or waiting
            or studio.digest(found['markdown'].encode()) != saved['markdown']
        ):
            raise ValueError(
                'The Google Doc changed since the check. Check it again; nothing changed.'
            )
        observation['structure_verified'] = True
        studio.write_json(fresh / 'observation.json', observation)
        chosen = folder / 'chosen.md'
        studio.atomic(chosen, found['markdown'].encode())
        chosen.chmod(0o600)
        _, record = studio.item(root, 'articles', ident)
        comparison = workflow.compare(directory, record, 'draft', observation, body)['comparison']
        workflow.command(
            root,
            SimpleNamespace(
                action='accept',
                id=ident,
                kind='draft',
                snapshot=str(fresh),
                observation=None,
                file=None,
                expected_comparison=comparison,
                # The parts were chosen above, part by part; the desk keeps its own text only
                # where it already reads as the Doc does.
                resolution_file=str(chosen),
                discard_remote=True,
            ),
        )
        _, record = studio.item(root, 'articles', ident)
        base = record['google']['baselines']['draft']
        sent = _sent(root, ident)
        sent['waiting'] = 0
        sent['brought'] = {'at': studio.now(), 'parts': len(found['changes'])}
        studio.write_json(_sent_path(root, ident), sent)
        result = {'brought': {'parts': [change['name'] for change in found['changes']]}}
        saved['result'] = result
        studio.write_json(folder / 'preview.json', saved)
        drive.discard(root, folder / 'snapshot')
        drive.discard(root, chosen)
        return result
    finally:
        drive.discard(root, fresh)
