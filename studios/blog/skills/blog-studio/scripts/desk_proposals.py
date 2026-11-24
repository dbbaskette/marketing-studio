"""Finishing proposals on the desk: kept, read, applied, edited or skipped.

Nothing changes until Apply. A proposal set waits on this computer only, in
.blog-runs/desk-proposals/<blog id>/<job id>.json, never in the blog's own folder, so a team
workspace records only what Apply writes, as a decision. Each Apply keeps a `finishing`
version of every part it changes first. Like desk.py, every function expects the caller to
hold the studio lock. Part of desk_finish, which keeps every name its callers use.
"""

import functools
import re

import desk
import desk_images
import studio
from studio_core.drafting import guards
from studio_core.drafting import proposals as shared


# The finishing job kinds and the tool each one is in the panel.
TOOLS = {
    'finish-copyedit': 'copyedit',
    'finish-humanize': 'humanize',
    'finish-facts': 'facts',
    'finish-headline': 'headline',
    'finish-feedback': 'feedback',
    'finish-voice': 'voice',
    'finish-geo': 'geo',
    # Reader aids and AI search additions on request (GEO): each one a proposal, never applied by itself.
    'finish-faq': 'faq',
    'finish-table': 'table',
    'finish-quotes': 'quotes',
    'finish-takeaways': 'takeaways',
    'finish-alt': 'alt',
    'finish-queries': 'queries',
    'finish-opener': 'opener',
}
KINDS = tuple(TOOLS)
# The proposals are kept, read and skipped by the shared desk
# (studio_core.drafting.proposals), with Blog Studio's store and desk record. Apply is Blog
# Studio's own: Review mode's suggestions stay independent (see apply and _reconcile).
JOB = shared.JOB
ITEMS = shared.ITEMS  # proposals in one set
DAY = shared.DAY  # an older set no longer shown is let go after this long
LATEST = shared.LATEST  # the newest set for each tool, so a poll reads only those
GONE = shared.GONE
NONE_LEFT = shared.NONE_LEFT
SAME = shared.SAME
EMPTY = shared.EMPTY
RETIRED = shared.RETIRED
CHANGED = 'Its words were changed by an accepted suggestion.'
EDITED = 'Its words were changed after it was suggested.'
WAITING = (
    'It would change words a suggestion left for you still waits on, so Accept all left it for you.'
)
FLAGGED = (
    'It now changes a fact, code or the shape of a part, so Accept all left it for you to check.'
)


def _require_lock():
    if not studio.lock_held():
        raise RuntimeError('Desk writes run under the studio lock.')


class _BlogProposals(shared.Proposals):
    def sets(self, ident):
        return sets(self.store.root, ident)  # This module's, looked up when called.

    def apply(self, ident, seen, job, chosen, every=False, working=frozenset()):
        # Blog Studio's own Apply, which keeps Review mode's suggestions independent.
        return apply(self.store.root, ident, seen, job, chosen, every)


def _proposals(root):
    """Blog Studio's waiting proposals: sets keyed `blog`, in .blog-runs/desk-proposals."""
    return _BlogProposals(
        desk.BlogStore(root),
        desk._drafting(root),
        TOOLS,
        owner='blog',
        present=lambda draft, item: present(draft, item),
        together=SENTENCES,
    )


def _folder(root, ident):
    return _proposals(root).folder(ident)


def _path(root, ident, job):
    return _proposals(root).path(ident, job)


def keep(root, ident, job, kind, items, **extra):
    """Keep a set of proposals for the person to preview; nothing in the draft changes."""
    return _proposals(root).keep(ident, job, kind, items, **extra)


def _latest(root, ident):
    """{tool: job} for the newest set of each tool, rebuilt from the sets when missing."""
    return _proposals(root).latest(ident)


def _prune(root, ident, shown):
    """Let go of sets no longer shown once nothing in them is open, or after a day."""
    _proposals(root).prune(ident, shown)


def read(root, ident, job):
    return _proposals(root).read(ident, job)


def sets(root, ident):
    """Every set kept for this blog, oldest first."""
    return shared.Proposals.sets(_proposals(root), ident)


def forget(root, ident):
    """Let a deleted blog's waiting suggestions go: they hold its text."""
    _proposals(root).forget(ident)


_once = shared.once


def present(draft, item):
    """Whether a proposal still fits the draft: its text is in its part, once, or the whole
    part is as it was for an alternative to the whole part. A comment needs only its part.
    A new section (an FAQ or key takeaways) fits while the post is as the job read it and the
    section it goes before is still there."""
    if item.get('insert'):
        return (
            item.get('basis') == basis(draft)
            and (item.get('at') == 'end' or desk.CODEC.section(draft, item.get('at')) is not None)
            and len(draft['sections']) < desk.SECTIONS
        )
    return shared.text_present(desk.CODEC)(draft, item)


def basis(value):
    """A short digest of a post's words, as a finishing job read them (its payload) or as the
    draft is now, so a proposal drawn from the whole post can say the post changed since."""
    rows = [value.get('title') or '', desk_images.scrub(value.get('opening') or '')]
    rows += [
        [section.get('id'), section.get('heading'), desk_images.scrub(section.get('text') or '')]
        for section in value.get('sections') or []
    ]
    return studio.digest(json_text(rows).encode())[:16]


def summary(root, ident, draft):
    """The newest set for each tool, as the panel shows it. Only those sets are read."""
    return _proposals(root).summary(ident, draft)


def _busy_parts(root, ident):
    """The parts a desk job under way may change, so an Apply never races it."""
    import desk_jobs

    parts = set()
    for job in desk_jobs.jobs(root, ident):
        if desk_jobs.busy(job):
            parts.add(((job.get('metadata') or {}).get('desk') or {}).get('part'))
    return parts


def apply(root, ident, seen, job, chosen, every=False):
    """Apply chosen proposals, each with its suggested text or the person's own (Edit).

    One proposal that no longer fits is refused with nothing changed. Several at once
    (Apply all) land one by one in reading order, each checked against the text as the ones
    before it left it: one that no longer fits is left out, counted in `left`, and one
    retired meanwhile is left out too. `every` is Review mode's Accept all, which may name
    suggestions from the other waiting set of Copy edit and Humanize too (an entry's `job`),
    and leaves out one that is flagged. Every other open suggestion stays independent unless
    a change it took in changes its words (see _reconcile); the result counts the ones
    `carried` and `retired`, when there are any. Each part changed keeps one `finishing`
    version first."""
    from desk_additions import _alt_fit, _insert  # desk_additions imports this module.

    found = read(root, ident, job)
    if not isinstance(chosen, list) or not chosen or len(chosen) > ITEMS:
        raise ValueError('Choose the suggestions to apply.')
    if type(every) is not bool:
        raise ValueError('Choose suggestions from this set.')
    held = dict(_sentence_sets(root, ident, job, found))
    picks, named, gone = [], set(), []
    for number, entry in enumerate(chosen):
        name = entry.get('job', job) if isinstance(entry, dict) else None
        items = (
            {item['id']: item for item in held[name]['items']}
            if isinstance(name, str) and name in held
            else {}
        )
        if (
            not isinstance(entry, dict)
            or set(entry) - {'id', 'after', 'alternative', 'job', 'at'}
            or entry.get('id') not in items
            or (name, entry['id']) in named
        ):
            raise ValueError('Choose suggestions from this set.')
        named.add((name, entry['id']))
        item = items[entry['id']]
        if item.get('insert') or 'at' in entry:
            # A new section (an FAQ or key takeaways) is added on its own, where it is placed.
            if not item.get('insert') or len(chosen) != 1 or every or name != job:
                raise ValueError('Add a new section on its own.')
            return _insert(root, ident, seen, job, found, item, entry)
        if 'comment' in item:
            raise ValueError('A comment changes nothing. Make it a note, or skip it.')
        if 'after' not in item and 'after' not in entry:
            raise ValueError('Write the wording to use, then apply it.')
        if item['state'] == 'retired':
            if len(chosen) == 1 and not every:
                raise ValueError(RETIRED)
            gone.append(item['id'])  # Another change took its words; the rest still apply.
            continue
        if item['state'] != 'open':
            raise ValueError('This suggestion was already applied or skipped.')
        pick = {'job': name, 'item': item, 'kind': held[name].get('kind'), 'order': number}
        if 'after' in entry:
            pick['own'] = entry['after']
        if 'alternative' in entry:
            # One of a wording fix's alternatives, by its place in the list.
            others = item.get('alternatives') or []
            choice = entry['alternative']
            if 'after' in entry or type(choice) is not int or not 0 <= choice < len(others):
                raise ValueError('Choose one of this suggestion’s alternatives.')
            pick['alternative'] = choice
        if not isinstance(_after(pick), str) or len(_after(pick)) > desk.LIMIT:
            raise ValueError('Keep one part under 200,000 characters.')
        picks.append(pick)
    draft = desk.read(root, ident)
    parts = sorted({pick['item']['part'] for pick in picks})
    desk.checked(draft, seen, parts)
    working = _busy_parts(root, ident)
    if any(part in working or ('sections' in working and part not in desk.PARTS) for part in parts):
        raise ValueError('A desk job is working on this part. Wait for it, or stop it, then apply.')
    single = len(chosen) == 1 and not every  # Accept all never refuses: it leaves out.
    texts = {part: desk.text_of(draft, part) for part in parts}
    picks.sort(key=lambda pick: _reading(draft, texts, pick))
    # Every open suggestion from these sets whose words are in its part once is kept in
    # step with the text as each chosen one lands.
    watched = [
        (name, item)
        for name, value in held.items()
        for item in value['items']
        if item.get('state') == 'open'
        and item.get('part') in texts
        and not item.get('whole')
        and 'comment' not in item
        and _once(texts[item['part']], item.get('before') or '')
    ]
    applied, left, touched, carried, retired = [], gone, set(), set(), set()
    chosen = {id(pick['item']) for pick in picks}
    for pick in picks:
        item = pick['item']
        part = item['part']
        if item['state'] != 'open':
            continue  # Retired by one that landed before it: counted there.
        text = texts[part]
        try:
            after = _after(pick)
            if not after.strip():
                raise ValueError(EMPTY)
            if every and _pick_flag(pick):
                raise ValueError(FLAGGED)  # A change it took in made it one to check.
            # The shared text swap: GONE when its words are not there once; image data and
            # references kept as Blog Studio's codec keeps them (desk._landed). Alt text
            # changes only the words of one image reference, which the codec would put back.
            if item.get('alt'):
                updated = _alt_fit(draft, item, after, text)
            else:
                updated = shared.text_fit(desk.CODEC)(draft, item, after, text)
            # A change that only an image reference made, put back as it was, is no change.
            if updated.strip() == text.strip():
                raise ValueError(SAME)
            desk.checked_text(part, updated, desk.limit(draft))
            if part == 'title' and not updated.strip():
                raise ValueError('Keep the title to one line, up to 500 characters.')
            edits = _word_edits(text, updated)
            if every and _would_retire(held, watched, chosen, part, text, updated, edits):
                raise ValueError(WAITING)
        except ValueError:
            if single:
                raise
            left.append(item['id'])
            continue
        texts[part] = updated
        applied.append(pick)
        touched.add(pick['job'])
        item['state'] = 'applying'  # Marked applied once the draft is written.
        item['landed'] = after
        ref = {'job': pick['job'], 'id': item['id']}
        for name, other in watched:
            if other.get('part') != part or other['state'] != 'open':
                continue
            was = other['before']
            if not _reconcile(other, text, updated, edits, lambda _, ref=ref: ref, picks):
                continue
            touched.add(name)
            if other['state'] == 'retired':
                retired.add(id(other))
                carried.discard(id(other))
            elif other['before'] != was:
                carried.add(id(other))
    if not applied:
        if every:
            return {'applied': 0, 'left': left}  # Each left for the person; nothing changed.
        raise ValueError(NONE_LEFT)
    changed = []
    for part, text in texts.items():
        before = desk.text_of(draft, part)
        if before.strip() == text.strip():
            continue
        desk.keep(root, ident, part, before, 'finishing')
        desk._set(draft, part, text)
        changed.append(part)
    if changed:
        draft = desk._write(root, ident, draft, changed)
    # Only once the draft is written are the proposals marked applied, and the others kept
    # in step with it.
    for pick in applied:
        item = pick['item']
        item['state'] = 'applied'
        carried.discard(id(item))
        if item.get('group'):
            for other in held[pick['job']]['items']:
                if other.get('group') == item['group'] and other['state'] == 'open':
                    other['state'] = 'skipped'  # An alternative to the one chosen.
    for name in sorted(touched):
        if held[name].get('kind') == 'finish-geo' and changed:
            # The review's own changes do not make it out of date (geo_view).
            held[name]['basis'] = basis(draft)
        studio.write_json(_path(root, ident, name), held[name])
    done = {'applied': len(applied), 'left': left}
    if carried:
        done['carried'] = len(carried)
    if retired:
        done['retired'] = len(retired)
    return done


def _would_retire(held, watched, chosen, part, old, new, edits):
    """Whether landing a change would retire an open suggestion Accept all was not sent that
    waits for the person: a flagged one from either tool, or a fix Show hides. Accept all
    leaves such a change for the person; a hidden rewrite may give way to a fix."""
    import copy

    for name, other in watched:
        waits = other.get('flag') or held[name].get('kind') == 'finish-copyedit'
        if (
            other.get('part') == part
            and other['state'] == 'open'
            and id(other) not in chosen
            and waits
        ):
            if not _once(old, other['before']) or not _reaches(other, old, new, edits):
                continue  # Only one the change reaches is tried.
            trial = copy.deepcopy(other)
            _reconcile(trial, old, new, edits, lambda _: None)
            if trial['state'] == 'retired':
                return True
    return False


def _after(pick):
    """The wording a pick lands: the person's own, an alternative, or the suggestion's."""
    item = pick['item']
    if 'own' in pick:
        return pick['own']
    if 'alternative' in pick:
        return item['alternatives'][pick['alternative']]['after']
    return item['after']


def _pick_flag(pick):
    """Why a pick waits to be checked one by one, or '': the person's own wording never does."""
    item = pick['item']
    if 'own' in pick:
        return ''
    if 'alternative' in pick:
        return item['alternatives'][pick['alternative']].get('flag') or ''
    return item.get('flag') or ''


def _reading(draft, texts, pick):
    """A pick's place in reading order, as Review mode numbers them: its part, then where it
    starts, Copy edit before Humanize, the shorter of two that start together, then as
    chosen."""
    item = pick['item']
    order = ['title', 'opening'] + [section['id'] for section in draft['sections']]
    text = texts[item['part']]
    before = item.get('before') or ''
    if item.get('whole'):
        start, end = 0, len(text)
    elif _once(text, before):
        start = text.index(before)
        end = start + len(before)
    else:
        start = end = len(text) + 1  # Not there once: it is left out wherever it goes.
    tool = SENTENCES.index(pick['kind']) if pick['kind'] in SENTENCES else len(SENTENCES)
    part = order.index(item['part']) if item['part'] in order else len(order)
    return (part, start, tool, end, pick['order'])


def _sentence_sets(root, ident, job, found):
    """[(job, set)] for the waiting Copy edit and Humanize sets, this one as it is held."""
    return _proposals(root)._together_sets(ident, job, found)


# The tools whose sentence suggestions Review mode shows together. They stay independent:
# accepting one changes another only where it changed the other's words.
SENTENCES = ('finish-copyedit', 'finish-humanize')
TOKENS = re.compile(r'\w+|\s+|[^\w\s]')
WORDLIKE = re.compile(r'\w')
ALIGN = 300  # characters of unchanged text each side that words are aligned with
CONTEXT = 8  # words of context an item re-anchored by its own change may keep on each side


def _reconcile(other, old, new, edits, by, picks=()):
    """Keep an open suggestion independent of an accepted change that turned `old` into
    `new` (`edits`, from _word_edits); say whether the suggestion changed.

    One whose words the change did not touch is left as it is, and still fits while its
    words are in the text once, as whole words. Otherwise it is read by its own change, the
    words it changes (and those each alternative, or the person's own wording for a pick
    still to land, changes), as a three-way merge reads two changes to one text:
    - when the accepted change replaced any of those words, or added words at the same
      place it adds its own, it retires: it would undo or repeat it;
    - otherwise its own change is moved onto the new text. It keeps its whole sentence when
      the accepted change sits among its own changes, as in a rewrite that kept the accepted
      words; else it shrinks to its own change and a little context from the new text, the
      accepted words included, found there once.
    A retired one names the accepted one (`by`, called with the edits that touched it)."""
    before = other['before']
    at = old.index(before)
    end = at + len(before)
    if not _near(old, at, end, edits):
        # No accepted edit is where its own changes could be: it is left as it is.
        return False if _whole(old, (at, end), new, before) else _retired(other, by([]))
    wordings = _wordings(other, picks)
    own, changes, touching = _own(old, at, end, wordings, edits)
    low = min([at] + [change[0] for change in changes])
    high = max([end] + [change[1] for change in changes])
    if not touching:
        if _whole(old, (at, end), new, before):
            return False
        return _retired(other, by(touching))
    owner = by(touching)
    if not changes:
        return False if _whole(old, (at, end), new, before) else _retired(other, owner)
    if any(_meet(a, b, c, d) for a, b, _, _ in touching for c, d, _ in changes):
        return _retired(other, owner)
    first = min(change[0] for change in changes)
    last = max(change[1] for change in changes)

    def moved(p, opens):
        """Where `p` of `old` is in `new`; a change starting there (`opens`) goes after
        words the accepted change added at that place, one ending there before them."""
        shift = 0
        for a, b, c, d in edits:
            if a < p < b:
                return None
            if b < p or (b == p and (a < b or opens)):
                shift += (d - c) - (b - a)
        return p + shift

    placed = []
    for hunks in own:
        row = []
        for a, b, text in hunks:
            start, stop = moved(a, a < b), moved(b, False)
            if start is None or stop is None or new[start:stop] != old[a:b]:
                return _retired(other, owner)
            row.append((start, stop, text))
        placed.append(row)
    among = all(
        (first < a < last) if a == b else (first <= a and b <= last) for a, b, _, _ in touching
    )

    def wordings_in(start, stop):
        """Each wording with its own change made in `new[start:stop]`, or None when one is
        left empty or none changes anything."""
        window = new[start:stop]
        found = []
        for wording, hunks in zip(wordings, placed, strict=True):
            text = window
            for a, b, words in sorted(hunks, reverse=True):
                text = text[: a - start] + words + text[b - start :]
            if '  ' in text and '  ' not in window and '  ' not in wording:
                text = re.sub(r'(?<=\S) {2,}(?=\S)', ' ', text)  # A cut left its space.
            # Nor a space left at an edge, next to the space beside the words.
            if text.endswith(' ') and not window.endswith(' ') and new[stop : stop + 1] == ' ':
                text = text[:-1]
            if (
                text.startswith(' ')
                and not window.startswith(' ')
                and new[start - 1 : start] == ' '
            ):
                text = text[1:]
            found.append(text)
        if any(not text.strip() for text in found) or all(text == window for text in found):
            return None
        return found

    carried = None
    if among:
        start, stop = moved(low, True), moved(high, False)
        if start is not None and stop is not None:
            if _whole(old, (low, high), new, new[start:stop]):
                carried = wordings_in(start, stop)
    else:
        lo = min(row[0] for hunks in placed for row in hunks)
        hi = max(row[1] for hunks in placed for row in hunks)
        span = (_moved_edge(edits, low, new, True), _moved_edge(edits, high, new, False))
        for start, stop in _windows(new, (lo, hi), span):
            carried = wordings_in(start, stop)
            if carried is not None:
                break
    if carried is None:
        return _retired(other, owner)  # Nothing of its own, or nothing at all, is left.
    # A space every wording keeps at an edge is not part of the suggestion, while the
    # words without it are still found once.
    trim, cut = start, list(carried)
    while trim < stop and new[trim].isspace() and all(t[:1] == new[trim] for t in cut):
        trim, cut = trim + 1, [t[1:] for t in cut]
    end_at = stop
    while (
        end_at > trim and new[end_at - 1].isspace() and all(t[-1:] == new[end_at - 1] for t in cut)
    ):
        end_at, cut = end_at - 1, [t[:-1] for t in cut]
    if (trim, end_at) != (start, stop) and _once(new, new[trim:end_at]):
        start, stop, carried = trim, end_at, cut
    window = new[start:stop]
    other['before'] = window
    _set_wordings(other, picks, carried)
    # Read again for what it changes now, and still flagged if it was: it still waits.
    if 'after' in other:
        other['flag'] = _flags(window, other['after']) or other.get('flag') or ''
    for alternative in other.get('alternatives') or []:
        alternative['flag'] = _flags(window, alternative['after']) or alternative.get('flag') or ''
    took = other.setdefault('carried', [])
    if owner:
        took.append(owner)
    return True


def _moved_edge(edits, p, new, opens):
    """Where an edge `p` of a suggestion is in `new`, taking in the accepted words that run
    across it: they become context it may keep."""
    shift = 0
    for a, b, c, d in edits:
        if a < p < b:
            return c if opens else d
        if b < p or (b == p and (a < b or opens)):
            shift += (d - c) - (b - a)
    return p + shift


def _windows(new, change, span):
    """Each (start, end) in `new` of a suggestion's own change with a little context around
    it, found there once as whole words, best first: up to CONTEXT words each side,
    preferring one on each side from its own sentence (`span`), then more."""
    lo, hi = change
    near = new[max(0, lo - 2000) : hi + 2000]
    base = max(0, lo - 2000)
    words = [
        (m.start() + base, m.end() + base) for m in TOKENS.finditer(near) if WORDLIKE.match(m[0])
    ]
    left = [w for w in reversed(words) if w[1] <= lo][:CONTEXT]
    right = [w for w in words if w[0] >= hi][:CONTEXT]
    inside = (
        min(1, sum(1 for w in left if w[0] >= span[0])),
        min(1, sum(1 for w in right if w[1] <= span[1])),
    )
    tries = sorted(
        ((x, y) for x in range(len(left) + 1) for y in range(len(right) + 1)),
        key=lambda pair: (
            pair[0] < inside[0] or pair[1] < inside[1],
            sum(pair),
            abs(pair[0] - pair[1]),
        ),
    )
    for x, y in tries:
        start = left[x - 1][0] if x else lo
        stop = right[y - 1][1] if y else hi
        while start < lo and new[start].isspace():
            start += 1
        while stop > hi and new[stop - 1].isspace():
            stop -= 1
        # With the marks that hold on to its words, such as a full stop or quotation marks.
        while start > 0 and not new[start - 1].isspace() and not WORDLIKE.match(new[start - 1]):
            start -= 1
        while stop < len(new) and not new[stop].isspace() and not WORDLIKE.match(new[stop]):
            stop += 1
        piece = new[start:stop]
        if WORDLIKE.search(piece) and _once(new, piece) and len(_whole_words(new, piece)) == 1:
            yield start, stop


def _own(old, at, end, wordings, edits):
    """A suggestion's own changes for each wording, read against the whole part as the
    accepted change's are, so two that add words in one gap between words are seen to meet;
    all of them; and the accepted edits that reach them, its words or an edge of them."""
    own = []
    for wording in wordings:
        mine = old[:at] + wording + old[end:]
        own.append([(a, b, mine[c:d]) for a, b, c, d in _word_edits(old, mine)])
    changes = [change for hunks in own for change in hunks]
    low = min([at] + [change[0] for change in changes])
    high = max([end] + [change[1] for change in changes])
    touching = [
        edit
        for edit in edits
        if _meet(edit[0], edit[1], low, high) or edit[0] == edit[1] in (low, high)
    ]
    return own, changes, touching


def _near(old, at, end, edits):
    """Whether any accepted edit falls where a suggestion at `old[at:end]` could have its
    own changes: inside the stretch _word_edits aligns them in, which holds them all."""
    start = max(0, at - ALIGN)
    while start > 0 and not old[start - 1].isspace():
        start -= 1
    stop = min(len(old), end + ALIGN)
    while stop < len(old) and not old[stop].isspace():
        stop += 1
    return any(b >= start and a <= stop for a, b, _, _ in edits)


def _reaches(other, old, new, edits):
    """Whether an accepted change reaches a suggestion at all: _reconcile would change it."""
    at = old.index(other['before'])
    end = at + len(other['before'])
    if not _near(old, at, end, edits):
        return not _whole(old, (at, end), new, other['before'])
    _, _, touching = _own(old, at, end, _wordings(other, ()), edits)
    return bool(touching) or not _whole(old, (at, end), new, other['before'])


def _retired(other, owner):
    other['state'] = 'retired'
    other['reason'] = CHANGED if owner else EDITED
    if owner:
        other['retired_by'] = owner
    return True


def _wordings(other, picks):
    """Every wording a suggestion offers for its `before`: its own, each alternative's, and
    the person's own for a pick still to land."""
    found = [other['after']] if isinstance(other.get('after'), str) else []
    found += [alternative['after'] for alternative in other.get('alternatives') or []]
    found += [pick['own'] for pick in picks if pick['item'] is other and 'own' in pick]
    return found


def _set_wordings(other, picks, texts):
    texts = iter(texts)
    if isinstance(other.get('after'), str):
        other['after'] = next(texts)
    for alternative in other.get('alternatives') or []:
        alternative['after'] = next(texts)
    for pick in picks:
        if pick['item'] is other and 'own' in pick:
            pick['own'] = next(texts)


def _meet(a, b, c, d):
    """Whether stretch [a, b) and stretch [c, d) of one text share words. A point (an
    insertion, a == b) meets a stretch it is strictly inside, or the same point."""
    if a == b and c == d:
        return a == c
    if a == b:
        return c < a < d
    if c == d:
        return a < c < b
    return a < d and c < b


def _spans(text):
    return [(m.start(), m.end()) for m in TOKENS.finditer(text)]


def _word_edits(old, new):
    """[(start, end, new start, new end)]: each stretch of `old`, in whole words and marks,
    that `new` changes, read by aligning their words where they differ."""
    if old == new:
        return []
    # Aligned with the unchanged words around the change too, up to a sentence or two
    # (ALIGN characters each side, ending between words), so the words line up as an
    # alignment of the whole part would line them up.
    start, old_end, new_end = _changed(old, new)
    start = max(0, start - ALIGN)
    grown = min(ALIGN, len(old) - old_end)
    old_end, new_end = old_end + grown, new_end + grown
    while start > 0 and not old[start - 1].isspace():
        start -= 1  # The text before the change is the same in both.
    while old_end < len(old) and not old[old_end].isspace():
        old_end += 1  # And so is the text after it.
        new_end += 1
    return [
        (start + x0, start + x1, start + y0, start + y1)
        for x0, x1, y0, y1 in _aligned_words(old[start:old_end], new[start:new_end])
    ]


@functools.lru_cache(maxsize=4096)
def _aligned_words(was, now):
    """The stretches of `was` that `now` changes, word by word, relative to each. Kept for
    the texts already aligned: an Accept all reads each suggestion again after every change
    it lands, and most of them see the same words each time."""
    import difflib

    a, b = _spans(was), _spans(now)
    old_words, new_words = [was[x:y] for x, y in a], [now[x:y] for x, y in b]
    opcodes = difflib.SequenceMatcher(None, old_words, new_words, autojunk=False).get_opcodes()

    def at(spans, text, i, j):
        if i == j:
            return (spans[i][0], spans[i][0]) if i < len(spans) else (len(text), len(text))
        return spans[i][0], spans[j - 1][1]

    found = []
    for op, i1, i2, j1, j2 in opcodes:
        if op != 'equal':
            found.append((*at(a, was, i1, i2), *at(b, now, j1, j2)))
    return tuple(found)


def _whole(old, span, new, before):
    """Whether `before` is in `new` once, and as whole words on each side where the
    suggestion's words, at `span` in `old`, were whole words."""
    if not _once(new, before):
        return False
    where = new.index(before)

    def clear(text, start, end):
        return (
            start == 0 or not (WORDLIKE.match(text[start - 1]) and WORDLIKE.match(text[start])),
            end == len(text) or not (WORDLIKE.match(text[end - 1]) and WORDLIKE.match(text[end])),
        )

    was, now = clear(old, *span), clear(new, where, where + len(before))
    return (now[0] or not was[0]) and (now[1] or not was[1])


def _changed(old, new):
    """(start, end in old, end in new) of the one stretch where `new` differs from `old`:
    the longest common start, then the longest common end of what is left."""
    limit = min(len(old), len(new))
    start = _longest(limit, lambda n: old[:n] == new[:n])
    rest = limit - start
    same = _longest(rest, lambda n: old[len(old) - n :] == new[len(new) - n :])
    return start, len(old) - same, len(new) - same


def _longest(limit, equal):
    """The largest n up to `limit` for which `equal(n)` holds, where it holds for every
    smaller n too, found by halving."""
    low, high = 0, limit
    while low < high:
        middle = (low + high + 1) // 2
        if equal(middle):
            low = middle
        else:
            high = middle - 1
    return low


def _whole_words(text, words):
    """Where `words` occur in `text` without starting or ending inside a word."""
    found, at = [], text.find(words) if words else -1
    while at != -1:
        clear_start = at == 0 or not (WORDLIKE.match(words[0]) and WORDLIKE.match(text[at - 1]))
        stop = at + len(words)
        clear_end = stop == len(text) or not (
            WORDLIKE.match(words[-1]) and WORDLIKE.match(text[stop])
        )
        if clear_start and clear_end:
            found.append(at)
        at = text.find(words, at + 1)
    return found


def _owner(fixes, part, new):
    """For a set landing after fixes were accepted: the accepted fix in this part whose
    wording, as it landed (an alternative or the person's own too), sits where the edits that
    touched a suggestion are, as {job, id}, or None."""

    def find(touching):
        for job, item in fixes:
            landed = item.get('landed', item.get('after'))
            if item.get('part') != part or not isinstance(landed, str) or not landed.strip():
                continue
            for at in _whole_words(new, landed.strip()):
                stop = at + len(landed.strip())
                if any(at <= c <= stop and at <= d <= stop for _, _, c, d in touching):
                    return {'job': job, 'id': item['id']}
        return None

    return find


def skip(root, ident, job, ids):
    """Set proposals aside. Only this computer's waiting set changes."""
    return _proposals(root).skip(ident, job, ids)


def unskip(root, ident, job, ids):
    """Review mode's Undo after Reject: the suggestions set aside are open again. Only ones
    set aside come back; one applied, retired or open stays as it is. Only this computer's
    waiting set changes, and the text never does."""
    proposals = _proposals(root)
    found = proposals.read(ident, job)
    if not isinstance(ids, list) or not ids or len(ids) > ITEMS:
        raise ValueError('Choose the suggestions to bring back.')
    items = {item['id']: item for item in found['items']}
    if any(not isinstance(name, str) or name not in items for name in ids):
        raise ValueError('Choose suggestions from this set.')
    opened = 0
    for name in set(ids):
        if items[name]['state'] == 'skipped':
            items[name]['state'] = 'open'
            opened += 1
    proposals.store.write_json(proposals.path(ident, job), found)
    return {'opened': opened}


def json_text(value):
    import json

    return json.dumps(value, sort_keys=True)


# Whether a proposal keeps the facts and the part's structure: the shared guards, with an
# image reference read as desk_images reads it.
def _names(text):
    """Capitalised words that are not the first word of a sentence: likely names. An image
    reference is not text: its alt and label are left out, and a word after it starts afresh."""
    return guards.names(text, desk_images.REFERENCE)


_named = guards.named


def changes_facts(before, after, anywhere=False):
    """What a rewrite changes that it should keep: numbers, links, quotes or names."""
    return guards.changes_facts(before, after, anywhere, desk_images.REFERENCE)


STRUCTURE = guards.STRUCTURE
FENCE = guards.FENCE
INLINE_CODE = guards.INLINE_CODE
TABLE_LINE = guards.TABLE_LINE
QUOTE_LINE = guards.QUOTE_LINE


def _shape(text, paragraphs=True):
    return guards.shape(text, paragraphs, desk_images.REFERENCE)


def changes_structure(before, after, paragraphs=True):
    """STRUCTURE when a rewrite changes code, an image reference or the part's blocks."""
    return guards.changes_structure(before, after, paragraphs, desk_images.REFERENCE)


def _flags(before, after, anywhere=False, paragraphs=True):
    """Every reason a proposal waits to be checked one by one, as one line."""
    return guards.flags(before, after, anywhere, paragraphs, desk_images.REFERENCE)
