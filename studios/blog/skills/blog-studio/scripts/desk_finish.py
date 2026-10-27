"""Finishing on the desk: tools that propose changes the person previews, then applies,
edits or skips.

Nothing changes until Apply. A proposal set waits on this computer only, in
.blog-runs/desk-proposals/<blog id>/<job id>.json, never in the blog's own folder, so a team
workspace records only what Apply writes, as a decision. Each Apply keeps a `finishing`
version of every part it changes first. Like desk.py, every function expects the caller to
hold the studio lock.
"""

import re
import shutil

import desk
import desk_images
import studio

# The finishing job kinds and the tool each one is in the panel.
TOOLS = {
    'finish-copyedit': 'copyedit',
    'finish-humanize': 'humanize',
    'finish-facts': 'facts',
    'finish-headline': 'headline',
    'finish-feedback': 'feedback',
    'finish-voice': 'voice',
}
KINDS = tuple(TOOLS)
JOB = re.compile(r'[a-f0-9]{32}')
ITEMS = 200  # proposals in one set
DAY = 86_400  # an older set no longer shown is let go after this long
LATEST = 'latest.json'  # the newest set for each tool, so a poll reads only those
GONE = 'That text is no longer in this part, so the suggestion was not applied. Skip it.'
NONE_LEFT = 'None of these suggestions match the text now, so nothing was applied.'
SAME = (
    'Nothing would change: image references stay as they are, and the rest of this '
    'suggestion is the text already there. Skip it.'
)
EMPTY = (
    'Write the words to use. To cut text, edit the part itself; a suggestion is not applied empty.'
)
RETIRED = 'This suggestion no longer fits: another change replaced its words.'
CHANGED = 'Its words were changed by an accepted suggestion.'
FLAGGED = (
    'It now changes a fact, code or the shape of a part, so Accept all left it for you to check.'
)


def _require_lock():
    if not studio.lock_held():
        raise RuntimeError('Desk writes run under the studio lock.')


def _folder(root, ident):
    return studio.inside(root, '.blog-runs', 'desk-proposals', studio.identifier(ident))


def _path(root, ident, job):
    if not isinstance(job, str) or not JOB.fullmatch(job):
        raise ValueError('Choose a set of suggestions on this blog.')
    return studio.inside(
        root, '.blog-runs', 'desk-proposals', studio.identifier(ident), job + '.json'
    )


def keep(root, ident, job, kind, items, **extra):
    """Keep a set of proposals for the person to preview; nothing in the draft changes."""
    _require_lock()
    if kind not in TOOLS:
        raise ValueError('Choose a finishing tool.')
    record = {
        'schema': 1,
        'job': job,
        'kind': kind,
        'blog': ident,
        'made_at': studio.now(),
        **extra,
        'items': [
            {**item, 'id': 'p' + str(number + 1), 'state': 'open'}
            for number, item in enumerate(items[:ITEMS])
        ],
    }
    studio.write_json(_path(root, ident, job), record)
    newest = _latest(root, ident)
    newest[TOOLS[kind]] = job
    studio.write_json(studio.inside(_folder(root, ident), LATEST), newest)
    _prune(root, ident, set(newest.values()))
    return record


def _latest(root, ident):
    """{tool: job} for the newest set of each tool, rebuilt from the sets when missing."""
    target = studio.inside(_folder(root, ident), LATEST)
    try:
        found = studio.read_json(target) if target.is_file() and not target.is_symlink() else None
    except (ValueError, OSError):
        found = None
    if isinstance(found, dict) and all(
        tool in TOOLS.values() and isinstance(job, str) and JOB.fullmatch(job)
        for tool, job in found.items()
    ):
        return found
    newest = {}
    for value in sets(root, ident):
        newest[TOOLS[value['kind']]] = value['job']
    return newest


def _prune(root, ident, shown):
    """Let go of sets no longer shown once nothing in them is open, or after a day."""
    import time

    folder = _folder(root, ident)
    for target in sorted(folder.glob('*.json')) if folder.is_dir() else []:
        if not JOB.fullmatch(target.stem) or target.stem in shown or target.is_symlink():
            continue
        try:
            value = studio.read_json(target)
            done = not any(item.get('state') == 'open' for item in value.get('items', []))
            if done or time.time() - target.stat().st_mtime > DAY:
                target.unlink()
        except (ValueError, OSError, AttributeError):
            continue


def read(root, ident, job):
    target = _path(root, ident, job)
    if not target.is_file() or target.is_symlink():
        raise ValueError('These suggestions are no longer here. Run the tool again.')
    found = studio.read_json(target)
    if not isinstance(found, dict) or found.get('blog') != ident:
        raise ValueError('These suggestions are no longer here. Run the tool again.')
    return found


def sets(root, ident):
    """Every set kept for this blog, oldest first."""
    folder = _folder(root, ident)
    found = []
    for target in sorted(folder.glob('*.json')) if folder.is_dir() else []:
        if target.is_symlink() or not JOB.fullmatch(target.stem):
            continue
        try:
            value = studio.read_json(target)
        except (ValueError, OSError):
            continue
        if isinstance(value, dict) and value.get('kind') in TOOLS and value.get('blog') == ident:
            found.append(value)
    return sorted(found, key=lambda value: value.get('made_at') or '')


def forget(root, ident):
    """Let a deleted blog's waiting suggestions go: they hold its text."""
    folder = _folder(root, ident)
    if folder.is_dir() and not folder.is_symlink():
        shutil.rmtree(folder)


def _once(text, before):
    """Whether `before` occurs in `text` exactly once, counting overlapping occurrences."""
    at = text.find(before) if before else -1
    return at != -1 and text.find(before, at + 1) == -1


def present(draft, item):
    """Whether a proposal still fits the draft: its text is in its part, once, or the whole
    part is as it was for an alternative to the whole part. A comment needs only its part."""
    if item.get('part') == 'whole':
        return True
    try:
        text = desk.text_of(draft, item.get('part'))
    except ValueError:
        return False
    if 'comment' in item:
        return True
    if item.get('whole'):
        # A whole part is kept as the job saw it: image data kept as text is a token.
        return desk_images.scrub(text) == item.get('before')
    return _once(text, item.get('before') or '')


def summary(root, ident, draft):
    """The newest set for each tool, as the panel shows it. Only those sets are read."""
    newest = {}
    for tool, job in _latest(root, ident).items():
        try:
            value = read(root, ident, job)
        except (ValueError, OSError):
            continue
        if TOOLS.get(value.get('kind')) == tool:
            newest[tool] = value
    return {
        tool: {
            **value,
            'items': [{**item, 'present': present(draft, item)} for item in value['items']],
        }
        for tool, value in newest.items()
    }


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
            or set(entry) - {'id', 'after', 'alternative', 'job'}
            or entry.get('id') not in items
            or (name, entry['id']) in named
        ):
            raise ValueError('Choose suggestions from this set.')
        named.add((name, entry['id']))
        item = items[entry['id']]
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
            if item.get('whole'):
                fits = desk_images.scrub(text) == item['before']
            else:
                fits = _once(text, item['before'])
            if not fits:
                raise ValueError(GONE)
            if item.get('whole'):
                updated = after.strip()
            else:
                at = text.index(item['before'])
                updated = text[:at] + after + text[at + len(item['before']) :]
            if part != 'title':
                # Image data kept as text comes back exactly, and no image reference the
                # part had is lost: one the change left out goes back where it was.
                updated = desk_images.restored(text, updated)
                # Image data typed into the change moves out under a label of its own; the
                # limits are checked when the draft is written (desk._write).
                own = set()
                updated, draft['images'] = desk_images.take(
                    updated, draft.get('images'), rename=True, previous=text, touched=own
                )
                updated = desk_images.kept(text, updated, draft['images'], own)
            # A change that only an image reference made, put back as it was, is no change.
            if updated.strip() == text.strip():
                raise ValueError(SAME)
            desk.checked_text(part, updated, desk.limit(draft))
            if part == 'title' and not updated.strip():
                raise ValueError('Keep the title to one line, up to 500 characters.')
        except ValueError:
            if single:
                raise
            left.append(item['id'])
            continue
        texts[part] = updated
        applied.append(pick)
        touched.add(pick['job'])
        item['state'] = 'applying'  # Marked applied once the draft is written.
        for name, other in watched:
            if other.get('part') != part or other['state'] != 'open':
                continue
            was = other['before']
            if not _reconcile(other, text, updated, item, pick['job'], picks):
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
        desk._write(root, ident, draft, changed)
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
        studio.write_json(_path(root, ident, name), held[name])
    done = {'applied': len(applied), 'left': left}
    if carried:
        done['carried'] = len(carried)
    if retired:
        done['retired'] = len(retired)
    return done


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
    found_sets = [(job, found)]
    if found.get('kind') not in SENTENCES:
        return found_sets
    for tool, other in _latest(root, ident).items():
        kind = next(kind for kind, name in TOOLS.items() if name == tool)
        if kind in SENTENCES and other != job:
            try:
                found_sets.append((other, read(root, ident, other)))
            except (ValueError, OSError):
                continue
    return found_sets


# The tools whose sentence suggestions Review mode shows together. They stay independent:
# accepting one changes another only where it changed the other's words.
SENTENCES = ('finish-copyedit', 'finish-humanize')
TOKENS = re.compile(r'\w+|\s+|[^\w\s]')
WORDLIKE = re.compile(r'\w')


def _reconcile(other, old, new, by, job, picks):
    """Keep an open suggestion in step with its part after an accepted one (`by`) turned
    `old` into `new`; say whether the suggestion changed.

    One whose words the change did not touch is left as it is, and still fits while its
    words are in the text once, as whole words where they were (a word added onto its last
    one changes its words too). One with the changed words inside its own takes them in:
    its `before` becomes the new text there, and its wording (each alternative too, and the
    person's own for a pick still to land) takes the same change where it still has the
    earlier words in the same place, or else keeps its own rewrite of them; its flag is read
    again. One whose words are gone, or in the text more than once, retires, naming the
    accepted one."""
    at = old.index(other['before'])
    end = at + len(other['before'])
    start, old_end, new_end = _changed(old, new)
    if start == old_end:
        touches = at < start < end  # Words added, none taken away.
    else:
        touches = start < end and at < old_end
    if not touches and _whole(old, (at, end), new, other['before']):
        return False
    if touches and at <= start and old_end <= end:
        was = other['before']
        other['before'] = new[at : end + len(new) - len(old)]
        swaps = _swaps(old, new, (start, old_end, new_end), (at, end), by)
        if 'after' in other:
            other['after'] = _carried(was, other['after'], swaps)
            other['flag'] = _flags(other['before'], other['after'])
        for alternative in other.get('alternatives') or []:
            alternative['after'] = _carried(was, alternative['after'], swaps)
            alternative['flag'] = _flags(other['before'], alternative['after'])
        for pick in picks:
            if pick['item'] is other and 'own' in pick:
                pick['own'] = _carried(was, pick['own'], swaps)
        other.setdefault('carried', []).append({'job': job, 'id': by['id']})
        wordings = [other.get('after')] + [a['after'] for a in other.get('alternatives') or []]
        fits = _whole(old, (at, end), new, other['before']) and (
            'after' not in other or any(text != other['before'] for text in wordings)
        )
    else:
        fits = _whole(old, (at, end), new, other['before'])
    if not fits:
        other['state'] = 'retired'
        other['reason'] = CHANGED
        other['retired_by'] = {'job': job, 'id': by['id']}
    return True


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
    """(start, end in old, end in new) of the one stretch where `new` differs from `old`."""
    limit = min(len(old), len(new))
    start = 0
    while start < limit and old[start] == new[start]:
        start += 1
    same = 0
    while same < limit - start and old[-1 - same] == new[-1 - same]:
        same += 1
    return start, len(old) - same, len(new) - same


def _swaps(old, new, change, span, by):
    """The earlier and new words of a change inside a suggestion's span, most certain first:
    the changed stretch widened to whole words, at its offset in the suggestion's `before`,
    then the accepted suggestion's own words when they are all inside it."""
    start, old_end, new_end = change
    at, end = span
    if (start < old_end and WORDLIKE.match(old[start])) or (
        start < new_end and WORDLIKE.match(new[start])
    ):
        while start > at and WORDLIKE.match(old[start - 1]):
            start -= 1  # The text before the change is the same in both.
    grown = 0
    if (old_end > start and WORDLIKE.match(old[old_end - 1])) or (
        new_end > start and WORDLIKE.match(new[new_end - 1])
    ):
        while old_end + grown < end and WORDLIKE.match(old[old_end + grown]):
            grown += 1  # And so is the text after it.
    swaps = [(start - at, old[start : old_end + grown], new[start : new_end + grown])]
    before = by.get('before') or ''
    if not by.get('whole') and before and _once(old, before):
        first = old.index(before)
        last = first + len(before)
        if at <= first and last <= end and first <= change[0] and change[1] <= last:
            swaps.append((None, before, new[first : last + len(new) - len(old)]))
    return swaps


def _carried(was, wording, swaps):
    """`wording`, a rewrite of `was`, with a change to `was` taken in: where the rewrite kept
    the changed words in the same place, or, failing that, has the accepted suggestion's
    words just once, as whole words. Otherwise its own rewrite of them stays."""
    if not isinstance(wording, str):
        return wording
    offset, earlier, later = swaps[0]
    if earlier:
        placed = _aligned_at(was, wording, offset, offset + len(earlier))
        if placed is not None:
            first, last, lead, tail = placed
            return wording[:first] + lead + later + tail + wording[last:]
    for _, earlier, later in swaps[1:]:
        found = _whole_words(wording, earlier)
        if len(found) == 1:
            return wording[: found[0]] + later + wording[found[0] + len(earlier) :]
    return wording


def _aligned_at(was, wording, start, end):
    """Where `was[start:end]` sits in `wording` when the rewrite kept those words unchanged
    in the same place: (first, last, lead, tail), the stretch of `wording` and the text of
    `was` around the words inside it; or None."""
    import difflib

    old = [(m.start(), m.end()) for m in TOKENS.finditer(was)]
    new = [(m.start(), m.end()) for m in TOKENS.finditer(wording)]
    first = max(i for i, (a, _) in enumerate(old) if a <= start)
    last = min(i for i, (_, b) in enumerate(old) if b >= end) + 1
    matcher = difflib.SequenceMatcher(
        None, [was[a:b] for a, b in old], [wording[a:b] for a, b in new], autojunk=False
    )
    for op, a0, a1, b0, _ in matcher.get_opcodes():
        if op == 'equal' and a0 <= first and last <= a1:
            lo, hi = old[first][0], old[last - 1][1]
            into = new[b0 + first - a0][0], new[b0 + last - 1 - a0][1]
            return into[0], into[1], was[lo:start], was[end:hi]
    return None


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


def skip(root, ident, job, ids):
    """Set proposals aside. Only this computer's waiting set changes."""
    found = read(root, ident, job)
    if not isinstance(ids, list) or not ids or len(ids) > ITEMS:
        raise ValueError('Choose the suggestions to skip.')
    items = {item['id']: item for item in found['items']}
    if any(not isinstance(name, str) or name not in items for name in ids):
        raise ValueError('Choose suggestions from this set.')
    skipped = 0
    for name in set(ids):
        if items[name]['state'] == 'open':
            items[name]['state'] = 'skipped'
            skipped += 1
    studio.write_json(_path(root, ident, job), found)
    return {'skipped': skipped}


# Quick check (the route and functions keep the name proofread): mechanical checks in
# process, no job. Advisory, never an authorship verdict.
AI_TELLS = ('blogforge', 'voice', 'assets', 'ai-tells')
COMMON_STARTS = frozenset({'the', 'a', 'an'})
PROOF_LIMIT = 300  # findings shown at once
BOUNDARY = re.compile(
    r'(?<=[.!?…])["”’)\]]*[ \t]+|\n[ \t]*\n|\n(?=[ \t]*(?:[-*+]|\d{1,3}[.)]|#|>)[ \t])'
)
WORD = re.compile(r'[^\W\d_]+(?:[’\'-][^\W\d_]+)*')
SENTENCE_MAX = 2000  # a passage Fix rewrites; a longer run is cut to its line


def _listed(name):
    import blog_runner

    path = blog_runner.REFERENCES.joinpath(*AI_TELLS, name)
    return [
        line.strip()
        for line in path.read_text(encoding='utf-8').splitlines()
        if line.strip() and not line.lstrip().startswith('#')
    ]


def proof_rules():
    """The desk's mechanical rules: no em dashes or double hyphens, and the words and
    phrases BlogForge listed as reading machine-written. A desk blog has no voice rules."""
    return {
        'no_em_dashes': True,
        'no_ascii_double_hyphen': True,
        'banished_words': _listed('words.txt'),
        'banished_phrases': _listed('phrases.txt'),
    }


def _sentences(text):
    """(start, end) of each sentence-like run in a part, without the spaces around it."""
    spans, at = [], 0
    for cut in [*BOUNDARY.finditer(text), None]:
        end = cut.start() if cut else len(text)
        piece = text[at:end]
        lead = len(piece) - len(piece.lstrip())
        if piece.strip():
            spans.append((at + lead, at + len(piece.rstrip())))
        if cut:
            at = cut.end()
    return spans


def _sentence(text, start, spans=None):
    """The sentence holding `start`, as (its text, where it starts in the part)."""
    for begin, end in spans or _sentences(text):
        if begin <= start < end:
            if end - begin > SENTENCE_MAX:
                line_start = text.rfind('\n', 0, start) + 1
                line_end = text.find('\n', start)
                begin, end = line_start, line_end if line_end != -1 else len(text)
                end = min(end, begin + SENTENCE_MAX)
            return text[begin:end], begin
    return text[start : start + 1], start


def _offsets(draft):
    """Where each part sits in the Markdown desk.join makes, to place findings in it."""
    places, at = [], 0
    if draft.get('title'):
        places.append(('title', at + 2, draft['title']))
        at += 2 + len(draft['title']) + 2
    if draft.get('opening'):
        places.append(('opening', at, draft['opening']))
        at += len(draft['opening']) + 2
    mark = desk.level(draft) + 1  # The heading's marks and its space, as join writes them.
    for section in draft['sections']:
        at += mark + len(section['heading'])
        if section['text']:
            places.append((section['id'], at + 2, section['text']))
            at += 2 + len(section['text'])
        at += 2
    return places


def _label(rule, target):
    if rule == 'em-dash':
        return 'A dash (' + target + '). Many readers take it as machine writing.', (
            'Replace the dash with a comma, a full stop, a colon or brackets.'
        )
    if rule == 'double-hyphen':
        return 'A double hyphen (--).', 'Replace the double hyphen with suitable punctuation.'
    if rule.startswith('banished:'):
        term = rule.partition(':')[2]
        return '“' + target + '” often reads as machine-written.', (
            'Say it without “' + term + '”, in plain words.'
        )
    if rule == 'duplicate-paragraph':
        return 'This paragraph repeats an earlier one.', 'Cut the repetition, or say something new.'
    if rule == 'ai-starter':
        return '“' + target + '” to start a sentence often reads as machine-written.', (
            'Start the sentence without “' + target + '”.'
        )
    if rule == 'repeated-start':
        return 'Two sentences in a row start with “' + target + '”.', (
            'Vary how this sentence starts.'
        )
    if rule == 'repeated-word':
        return '“' + target + '” three times in one paragraph.', (
            'Use “' + target + '” less often here.'
        )
    return 'This section opens the way another one does.', 'Open this section differently.'


def _finding(part, text, rule, start, target, spans=None):
    sentence, at = _sentence(text, start, spans)
    label, fix = _label(rule, target)
    return {
        'part': part,
        'rule': rule,
        'label': label,
        'fix': fix,
        'target': target,
        'sentence': sentence,
        'start': at,
        'at': start,
    }


LIST_LINE = re.compile(r'[ \t]*(?:[-*+]|\d{1,3}[.)])[ \t]')


def _mask_indented(text):
    """Indented code (four spaces or a tab after a blank line, outside a list) as spaces of
    the same length, so findings keep their places and code is never read as prose."""
    out, code, listed, blank = [], False, False, True
    for line in text.split('\n'):
        indented = line.startswith(('    ', '\t'))
        if not line.strip():
            out.append(line)
            blank = True
            continue
        if indented and (code or (blank and not listed)):
            code, blank = True, False
            out.append(' ' * len(line))
            continue
        code = False
        if LIST_LINE.match(line):
            listed = True
        elif not indented:
            listed = False
        out.append(line)
        blank = False
    return '\n'.join(out)


def _clean(text):
    from text_checks import mask_protected

    return mask_protected(_mask_indented(text))


def _units(paragraph):
    """A paragraph, or each item of a list on its own: parallel items repeat by design."""
    starts = [m.start() for m in re.finditer(r'(?m)^' + LIST_LINE.pattern, paragraph)]
    if not starts:
        return [(0, paragraph)]
    cuts = ([0] if starts[0] else []) + starts + [len(paragraph)]
    return [(a, paragraph[a:b]) for a, b in zip(cuts, cuts[1:], strict=False)]


def _repetition(part, text):
    """Within one part: an AI-tell sentence opener, two sentences in a row with the same
    first word, and a long word three times in one paragraph."""
    clean = _clean(text)
    spans = _sentences(text)
    starters = {word.casefold() for word in _listed('sentence-starters.txt')}
    found, previous = [], None
    for begin, end in spans:
        first = WORD.search(clean, begin, end)
        word = first.group() if first and first.start() == begin else None
        if word and word.casefold() in starters:
            found.append(_finding(part, text, 'ai-starter', begin, word, spans))
        elif (
            word
            and previous
            and word.casefold() == previous.casefold()
            and word.casefold() not in COMMON_STARTS
        ):
            found.append(_finding(part, text, 'repeated-start', begin, word, spans))
        previous = word
    for paragraph in re.finditer(r'\S[\s\S]*?(?=\n[ \t]*\n|\Z)', clean):
        for offset, unit in _units(paragraph.group()):
            seen = {}
            for match in WORD.finditer(unit):
                word = match.group().casefold()
                if len(word) < 6:
                    continue
                seen[word] = seen.get(word, 0) + 1
                if seen[word] == 3:
                    start = paragraph.start() + offset + match.start()
                    found.append(_finding(part, text, 'repeated-word', start, match.group(), spans))
    return found


def _openers(draft):
    found, seen = [], {}
    for section in draft['sections']:
        paragraph = _clean(section['text']).strip().split('\n\n')[0]
        opener = ' '.join(paragraph.lower().split()[:8])
        if len(opener.split()) >= 6:
            if opener in seen:
                found.append(_finding(section['id'], section['text'], 'echoed-opener', 0, opener))
            seen[opener] = section['id']
    return found


def proofread(root, ident):
    """Mechanical findings for each part, in draft order, each with the sentence Fix would
    rewrite. Reading only: nothing is written and no job starts."""
    from text_checks import lint

    draft = desk.read(root, ident)
    places = _offsets(draft)
    findings = []
    for hit in lint(_mask_indented(desk.join(draft, images=False)), proof_rules())['findings']:
        if 'start' not in hit:
            continue
        for part, offset, text in places:
            if offset <= hit['start'] < offset + len(text):
                local = hit['start'] - offset
                target = text[local : local + len(hit['target'])].split('\n')[0][:200]
                findings.append(_finding(part, text, hit['rule'], local, target))
                break
    for part, _, text in places:
        findings += _repetition(part, text)
    findings += _openers(draft)
    order = {part: number for number, (part, _, _) in enumerate(places)}
    findings.sort(key=lambda found: (order.get(found['part'], 0), found['at'], found['rule']))
    return {
        'id': ident,
        'revision': draft['revision'],
        'findings': findings[:PROOF_LIMIT],
        'more': max(0, len(findings) - PROOF_LIMIT),
        'limitations': 'Mechanical matches and repetition hints only; read for meaning. Code, '
        'links and quotations are left out.',
    }


# The tools that propose through a job: what each asks for, and how its result is read.
UNREADABLE = 'The suggestions came back in a shape Blog Studio cannot read. Run it again.'
NO_TEXT = 'Write the draft first: Finishing works on written text.'
NO_SOURCES = 'Add a source first: facts are checked against your sources.'
LEVELS = {
    'light': 'Intensity: light. Smooth the flow and replace formulaic wording only; keep each '
    'sentence’s structure where you can.',
    'medium': 'Intensity: medium. Also vary rhythm and sentence openings, and let the point of '
    'view come through.',
    'strong': 'Intensity: strong. Rework sentences that read as generic so they sound like a '
    'person explaining their own work, keeping every fact.',
}
COPYEDIT = (
    'Copy edit this draft and its title: spelling, grammar, punctuation, consistency (a name, '
    'term, number style or capitalisation written two ways), clarity and concision only. Find '
    'the sentences that need such a fix and suggest the corrected sentence for each, changing '
    'only what the fix needs. Never change a claim, a qualifier or the argument, and never add, '
    'move or cut a point. Preserve the author’s voice and stance, every fact, number and name, '
    'each quotation and link exactly, and every image reference where it is; never change '
    'code. Leave sentences that are already correct alone. Do not research.'
)
COPYEDIT_JSON = (
    'Return JSON in content: {"suggestions": [{"part": ..., "kind": ..., "before": ..., '
    '"after": ..., "why": ...}]}, at most 60. part is "title", "opening" or the id of a section '
    'in sections; kind is "spelling", "grammar", "punctuation", "consistency" or "wording" '
    '(clarity and concision); before is one or two whole sentences copied exactly from that '
    'part, character for character (for the title, the words to change); after replaces '
    'before, on one line for the title; why names the fix in a few words, such as "Subject and '
    'verb agree". A wording suggestion may also have "alternatives": up to three other '
    'replacements for the same before, each a different way to say it. Spelling, grammar, '
    'punctuation and consistency fixes have one right answer and no alternatives.'
)
# The kinds of fix a copy edit names; anything else is read as grammar.
COPYEDIT_KINDS = ('spelling', 'grammar', 'punctuation', 'consistency', 'wording')
ALTERNATIVES = 3  # at most, for one wording suggestion
# The copy-editing guide's lenses a copy edit uses; the others (evidence, structure,
# persuasion and the rest) belong to a fuller edit.
COPYEDIT_LENSES = ('Clarity', 'Voice')
HUMANIZE = (
    'Find the sentences in this draft that read as machine-written: formulaic or stock '
    'wording, monotonous rhythm, repeated entrances, generic stance. Suggest a rewrite for each. '
    'Keep every number, name, quotation and link exactly. Never invent an opinion, experience, '
    'hesitation or anecdote. Leave sentences that already read well alone.'
)
HUMANIZE_JSON = (
    'Return JSON in content: {"suggestions": [{"part": ..., "before": ..., "after": ..., '
    '"why": ...}]}, at most 40. part is "opening" or the id of a section in sections; before is '
    'one or two whole sentences copied exactly from that part, character for character; after '
    'replaces before; why says in a few words what reads as machine-written.'
)
FACTS = (
    'Check each factual claim in the draft against sources and any research. A claim is '
    'supported when a source passage says it, not-in-sources when no source says it, and '
    'contradicted when a source says otherwise. Judge only from what is supplied; do not '
    'research.'
)
FACTS_JSON = (
    'Return JSON in content: {"claims": [{"part": ..., "before": ..., "verdict": ..., '
    '"passage": ..., "source": ..., "after": ..., "why": ...}]}, at most 40. part is "opening" '
    'or the id of a section in sections; before is the claim, copied exactly from that part; '
    'verdict is "supported", "not-in-sources" or "contradicted"; passage is the source passage '
    'it rests on, copied exactly ("" when none); source names that source; after is a rewording '
    'the sources support, for a claim that is not supported ("" when none fits); why says why.'
)
HEADLINE = (
    'Suggest alternatives for the title and the opening of this draft, from the draft itself, '
    'its brief and its sources. The title promises the topic; the opening pulls the reader into '
    'the argument. Make the alternatives meaningfully different from each other and from what '
    'is there. No clickbait, no promise the post cannot keep, no number the draft does not have.'
)
HEADLINE_JSON = (
    'Return JSON in content: {"titles": [{"text": ..., "why": ...}], "openings": [{"text": ..., '
    '"why": ...}]}, with up to five titles of one line each and up to three openings, each a '
    'whole replacement for the opening with no heading; why names what it does differently.'
)
FEEDBACK = (
    'Give editorial feedback on this draft without rewriting it: its shape, its argument, '
    'whether it serves its audience, and claims that need evidence. Quote the passage each '
    'comment is about and say the reader’s difficulty and a specific move. Nothing you say is '
    'applied to the text.'
)
FEEDBACK_JSON = (
    'Return JSON in content: {"summary": ..., "comments": [{"part": ..., "quote": ..., '
    '"aspect": ..., "comment": ...}]}, at most 30 comments. part is "title", "opening", the id '
    'of a section in sections, or "whole" for the draft as a whole; quote is a short passage '
    'copied exactly from that part ("" for none); aspect is "shape", "argument", "audience" or '
    '"claims"; summary is two or three sentences on the draft overall.'
)
VOICE = (
    'Rewrite this draft in the voice described in voice_guide, part by part. Change how it '
    'sounds, never what it says: keep the structure (the same paragraphs, lists, tables and code '
    'in the same order), every fact, number, name, quotation and link exactly, and the author’s '
    'stance. Apply only the supplied voice; preserve the facts and their uncertainty, and invent '
    'no experience, opinion or anecdote. Where the guide and the tone differ, follow the guide. '
    'Leave a part that already reads in this voice as it is.'
)
VOICE_JSON = (
    'Return JSON in content: {"parts": [{"part": ..., "text": ..., "why": ...}]}, one row for '
    'the opening and for each section in sections that has text. part is "opening" or the id of '
    'a section; text is the whole part rewritten, without its heading; why says in a few words '
    'what changed.'
)
NO_GUIDE = 'Choose a voice guide that is not retired.'
VERDICTS = {
    'supported': 'supported',
    'not-in-sources': 'not-in-sources',
    'unsupported': 'not-in-sources',
    'contradicted': 'contradicted',
}
ASPECTS = ('shape', 'argument', 'audience', 'claims')
NAME = re.compile(r'\b[A-Z][A-Za-z0-9]+\b')


def _reference(*path):
    import blog_runner

    return blog_runner.REFERENCES.joinpath(*path).read_text(encoding='utf-8').rstrip()


def _lenses():
    """The copy-editing guide's clarity and voice lenses, as the guide words them."""
    lines, keeping = [], False
    for line in _reference('modules', 'copy-editing.md').splitlines():
        if line.startswith('- **'):
            keeping = any(line.startswith('- **' + name + ':**') for name in COPYEDIT_LENSES)
        elif not line.startswith('  '):
            keeping = False
        if keeping:
            lines.append(line)
    return 'Editing lenses for this copy edit:\n' + '\n'.join(lines)


def _payload(draft, extra):
    return {
        'title': draft['title'],
        'brief': draft.get('brief') or {},
        'opening': draft['opening'],
        'sections': [
            {'id': s['id'], 'heading': s['heading'], 'text': s['text']} for s in draft['sections']
        ],
        **extra,
    }


def _guide(root, guide):
    """A saved voice guide that is not retired: {id, name, revision, guide}."""
    import article_tools

    if not isinstance(guide, str) or not guide:
        raise ValueError(NO_GUIDE)
    try:
        chosen = article_tools.profile(root, guide)
    except (ValueError, OSError):
        raise ValueError(NO_GUIDE) from None
    if chosen.get('status') == 'retired':
        raise ValueError(NO_GUIDE)
    if not chosen['guide'].strip():
        raise ValueError('This voice guide has no text yet. Write it on the Voice guides screen.')
    return chosen


def request(root, ident, draft, tool, level=None, guide=None):
    """The kind, payload, guidance and job details for one finishing tool on this draft."""
    import blog_runner
    import desk_jobs
    import manuscript_editor

    kinds = {tool: kind for kind, tool in TOOLS.items()}
    if tool not in kinds:
        raise ValueError('Choose a finishing tool.')
    written = draft['opening'].strip() or any(s['text'].strip() for s in draft['sections'])
    if tool != 'headline' and not written:
        raise ValueError(NO_TEXT)
    extra, shared = desk_jobs._context(root, draft)
    extra.pop('response_kind', None)  # The suggestions are JSON in content.
    extra.pop('gaps', None)
    meta = {}
    if tool == 'copyedit':
        # Only the draft and its tone: no sources, examples or kind of post to edit towards.
        payload = _payload(draft, {'tone': extra.get('tone', '')})
        guidance = COPYEDIT + ' ' + desk_jobs.desk_check('copyedit') + ' '
        guidance += desk_jobs.desk_check('proofread') + '\n\n' + _lenses() + '\n\n'
        guidance += blog_runner.shared_guidance(None, draft.get('tone', ''))
        if draft.get('images'):
            guidance += '\n' + desk_images.GUIDANCE
        guidance += '\n' + COPYEDIT_JSON
    elif tool == 'humanize':
        if level not in LEVELS:
            raise ValueError('Choose light, medium or strong.')
        meta['level'] = level
        payload = {**_payload(draft, extra), 'level': level}
        guidance = (
            HUMANIZE + ' ' + LEVELS[level] + '\n\n' + _reference('modules', 'blog-humanize.md')
        )
        guidance += '\n\n' + shared + '\n' + HUMANIZE_JSON
    elif tool == 'facts':
        research, said = desk_jobs._research_extra(root, ident)
        if not extra['sources'] and not research:
            raise ValueError(NO_SOURCES)
        payload = {**_payload(draft, extra), **research}
        guidance = manuscript_editor.CHECKS['factual-support'] + ' ' + FACTS + '\n\n'
        guidance += _reference('modules', 'blog-fact-check.md') + '\n\n'
        guidance += _reference('review', 'evidence.md') + '\n\n' + shared + said
        guidance += '\nThe sources are in sources, with their names and stance.\n' + FACTS_JSON
    elif tool == 'voice':
        # The guide's text is put in the payload: the desk's own context stays tone-only.
        chosen = _guide(root, guide)
        meta.update(
            guide=chosen['id'], guide_name=chosen['name'], guide_revision=chosen['revision']
        )
        payload = {
            **_payload(draft, extra),
            'voice_guide': {'name': chosen['name'], 'text': chosen['guide']},
        }
        guidance = VOICE + '\n\n' + shared + '\n' + VOICE_JSON
    elif tool == 'headline':
        payload = _payload(draft, extra)
        guidance = HEADLINE + '\n\n' + _reference('headline-lab.md') + '\n\n' + shared
        guidance += '\n' + HEADLINE_JSON
    else:
        payload = _payload(draft, extra)
        guidance = FEEDBACK + '\n\n' + blog_runner.STAGES['review'][2] + ' '
        guidance += manuscript_editor.CHECKS['shape'] + '\n\n' + _reference('review', 'shape.md')
        guidance += '\n\n' + shared + '\n' + FEEDBACK_JSON
    return kinds[tool], payload, guidance, meta


def _text(value, limit):
    return value.strip()[:limit] if isinstance(value, str) else ''


def _names(text):
    """Capitalised words that are not the first word of a sentence: likely names. An image
    reference is not text: its alt and label are left out, and a word after it starts afresh."""
    text = desk_images.REFERENCE.sub('. ', text)
    found = set()
    for match in NAME.finditer(text):
        before = text[: match.start()].rstrip()
        if before and before[-1] not in '.!?:"“(]' and len(match.group()) > 1:
            found.add(match.group())
    return found


def _named(name, text):
    return re.search(r'(?<![A-Za-z0-9])' + re.escape(name) + r'(?![A-Za-z0-9])', text) is not None


def changes_facts(before, after, anywhere=False):
    """What a rewrite changes that it should keep: numbers, links, quotes or names.

    `anywhere` (a whole part rewritten in a voice) compares which names there are, not
    where they sit: a name that only moves to the start of a sentence is kept, and one
    added or dropped is flagged."""
    from text_checks import preserve

    changed = list(preserve(before, after)['changes'])
    if anywhere:
        dropped = {name for name in _names(before) if not _named(name, after)}
        added = {name for name in _names(after) if not _named(name, before)}
        if (dropped | added) - {'I'}:
            changed.append('names')
    elif _names(before) - _names(after) - {'I'}:
        changed.append('names')
    if not changed:
        return ''
    words = {'numbers': 'a number', 'links': 'a link', 'quotes': 'a quotation', 'names': 'a name'}
    return 'Check the facts: this changes ' + ' and '.join(words[key] for key in changed) + '.'


STRUCTURE = 'Check the structure: this changes code or the part’s shape.'
FENCE = re.compile(r'^[ \t]*(```|~~~)')
INLINE_CODE = re.compile(r'(`+)(.+?)\1', re.S)
TABLE_LINE = re.compile(r'^[ \t]*\|')
QUOTE_LINE = re.compile(r'^\s{0,3}>')


def _shape(text, paragraphs=True):
    """The code and quotations a part holds, exactly (fenced blocks with their opening
    line, indented code, inline code spans, blockquote lines), its image references in
    order, and the count of its blocks: paragraphs, list items, fenced blocks and tables."""
    fences, inline, outside = [], [], []
    block, inside = None, False
    for line in text.splitlines():
        if FENCE.match(line):
            if inside:
                fences.append('\n'.join(block))
                inside = False
            else:
                inside, block = True, [line.strip()]  # The language tag is part of the code.
            outside.append('')
            continue
        if inside:
            block.append(line)
        else:
            outside.append(line)
    if inside:
        fences.append('\n'.join(block))
    # Indented code by the same rules the proofread uses: its lines exactly, then masked.
    shown = '\n'.join(outside)
    masked = _mask_indented(shown)
    indented = [
        line
        for line, mask in zip(shown.split('\n'), masked.split('\n'), strict=True)
        if line.strip() and not mask.strip()
    ]
    prose = masked
    inline = [match.group(2) for match in INLINE_CODE.finditer(prose)]
    lines = prose.splitlines()
    quotes = [line.strip() for line in lines if QUOTE_LINE.match(line)]
    items = sum(1 for line in lines if LIST_LINE.match(line))
    tables = sum(
        1
        for at, line in enumerate(lines)
        if TABLE_LINE.match(line) and (at == 0 or not TABLE_LINE.match(lines[at - 1]))
    )
    count = (
        sum(
            1
            for chunk in re.split(r'\n[ \t]*\n', prose)
            if chunk.strip()
            and not all(
                LIST_LINE.match(l) or TABLE_LINE.match(l) for l in chunk.strip().splitlines()
            )
        )
        if paragraphs
        else 0
    )
    images = [match.group(0) for match in desk_images.REFERENCE.finditer(prose)]
    return fences, indented, inline, quotes, images, (count, items, len(fences), tables)


def changes_structure(before, after, paragraphs=True):
    """STRUCTURE when a rewrite changes code (fenced blocks or inline code spans, exactly),
    drops, adds or alters an image reference, or changes the part's block structure; ''
    otherwise."""
    return STRUCTURE if _shape(before, paragraphs) != _shape(after, paragraphs) else ''


def _flags(before, after, anywhere=False, paragraphs=True):
    """Every reason a proposal waits to be checked one by one, as one line."""
    return ' '.join(
        flag
        for flag in (
            changes_facts(before, after, anywhere),
            changes_structure(before, after, paragraphs),
        )
        if flag
    )


def _located(draft, part, before):
    """`before` as it occurs once in its part, or None."""
    try:
        text = desk.text_of(draft, part)
    except ValueError:
        return None
    before = before.strip() if isinstance(before, str) else ''
    if not _once(text, before):
        return None
    return before


def _prose_parts(draft):
    return {'opening'} | {s['id'] for s in draft['sections']}


def _rows(found, key, fields):
    """The result's rows, each a dict whose named fields are text. A row of another shape is
    dropped; a result made only of such rows cannot be read."""
    rows = found.get(key) if isinstance(found, dict) else None
    if not isinstance(rows, list):
        raise ValueError(UNREADABLE)
    good = [
        row
        for row in rows[:60]
        if isinstance(row, dict) and all(isinstance(row.get(name), str) for name in fields)
    ]
    if rows and not good:
        raise ValueError(UNREADABLE)
    return good, len(rows[:60]) - len(good)


def _replacement(draft, part, before, after):
    """`after` as a replacement for `before` in its part, stripped, or None when it is not
    one: empty, the same, adding a heading, or more than one line in the title."""
    if not isinstance(after, str) or not after.strip() or len(after) > desk.LIMIT:
        return None
    after = after.strip()
    if (
        after == before
        or desk.has_heading(after, desk.limit(draft))
        or (part == 'title' and '\n' in after)
    ):
        return None
    return after


def _alternatives(draft, part, before, after, found):
    """A wording suggestion's other replacements, read strictly: a list of at most three
    strings, each a replacement for the same `before` that differs from it and from the ones
    before; another shape gives none. Each is flagged as a suggestion is."""
    if not isinstance(found, list) or not found or len(found) > ALTERNATIVES:
        return []
    kept, taken = [], {after}
    for value in found:
        text = _replacement(draft, part, before, value)
        if text is None or text in taken:
            continue
        taken.add(text)
        kept.append({'after': text, 'flag': _flags(before, text)})
    return kept


def _read_humanize(draft, found, title=False, kinds=False):
    """Sentence rewrites (Humanize, and Copy edit with the title too): each `before` found
    once in its part, and an `after` that changes it without adding a heading, on one line
    for the title. Any other row is dropped. With `kinds` (Copy edit), each fix names its
    kind, grammar when it names none it may, and a wording fix may bring alternatives."""
    rows, dropped = _rows(found, 'suggestions', ('part', 'before', 'after'))
    parts = _prose_parts(draft) | ({'title'} if title else set())
    items, seen = [], set()
    for row in rows:
        part = row.get('part')
        before = _located(draft, part, row.get('before')) if part in parts else None
        after = None if before is None else _replacement(draft, part, before, row.get('after'))
        if after is None or (part, before) in seen:
            dropped += 1
            continue
        seen.add((part, before))
        item = {
            'part': part,
            'before': before,
            'after': after,
            'note': _text(row.get('why'), 500),
            'flag': _flags(before, after),
        }
        if kinds:
            kind = row.get('kind')
            item['kind'] = kind if isinstance(kind, str) and kind in COPYEDIT_KINDS else 'grammar'
            others = (
                _alternatives(draft, part, before, after, row.get('alternatives'))
                if item['kind'] == 'wording'
                else []
            )
            if others:
                item['alternatives'] = others
        items.append(item)
    return items, dropped, {}


def _read_facts(draft, found):
    rows, dropped = _rows(found, 'claims', ('part', 'before', 'verdict'))
    items = []
    for row in rows:
        part, verdict = row.get('part'), VERDICTS.get(row.get('verdict'))
        before = _located(draft, part, row.get('before')) if part in _prose_parts(draft) else None
        if before is None or verdict is None:
            dropped += 1
            continue
        item = {
            'part': part,
            'before': before,
            'verdict': verdict,
            'passage': _text(row.get('passage'), 2000),
            'source': _text(row.get('source'), 300),
            'note': _text(row.get('why'), 500),
        }
        after = _text(row.get('after'), desk.LIMIT)
        if (
            verdict != 'supported'
            and after
            and after != before
            and not desk.has_heading(after, desk.limit(draft))
        ):
            item['after'] = after
            item['flag'] = changes_structure(before, after)
        items.append(item)
    order = {'contradicted': 0, 'not-in-sources': 1, 'supported': 2}
    items.sort(key=lambda item: order[item['verdict']])
    return items, dropped, {}


def _read_headline(draft, found):
    if not isinstance(found, dict):
        raise ValueError(UNREADABLE)
    titles, openings = found.get('titles') or [], found.get('openings') or []
    if not isinstance(titles, list) or not isinstance(openings, list) or not titles + openings:
        raise ValueError(UNREADABLE)
    items, dropped = [], 0
    for part, rows, limit in (('title', titles[:5], 500), ('opening', openings[:3], 20_000)):
        for row in rows:
            row = row if isinstance(row, dict) else {}
            text = row.get('text')
            text = text.strip() if isinstance(text, str) else ''
            if part == 'title':
                text = text.lstrip('#').strip()
            if (
                not text
                or len(text) > limit
                or (part == 'title' and '\n' in text)
                or (part == 'opening' and desk.has_heading(text, desk.limit(draft)))
                or text == draft[part]
            ):
                dropped += 1
                continue
            shown = desk_images.scrub(draft[part])
            items.append(
                {
                    'part': part,
                    'before': shown,
                    'after': text,
                    'note': _text(row.get('why'), 500),
                    # An alternative opening may reshape its paragraphs; code and lists stay.
                    'flag': changes_structure(shown, text, paragraphs=False),
                    'whole': True,
                    'group': part,
                }
            )
    return items, dropped, {}


def _read_feedback(draft, found):
    rows = found.get('comments') if isinstance(found, dict) else None
    if not isinstance(rows, list):
        raise ValueError(UNREADABLE)
    parts = _prose_parts(draft) | {'title'}
    items = []
    for row in rows[:40]:
        row = row if isinstance(row, dict) else {}
        comment = _text(row.get('comment'), 2000)
        if not comment:
            continue
        part = row.get('part')
        part = part if isinstance(part, str) and part in parts else 'whole'
        quote = _located(draft, part, row.get('quote')) if part != 'whole' else None
        aspect = row.get('aspect')
        aspect = aspect if isinstance(aspect, str) and aspect in ASPECTS else 'shape'
        items.append({'part': part, 'quote': quote or '', 'aspect': aspect, 'comment': comment})
    summary = _text(found.get('summary'), 2000)
    if not items and not summary:
        raise ValueError(UNREADABLE)
    return items, 0, {'summary': summary}


def _read_voice(draft, found):
    """One proposal per part the voice rewrote: the whole part, before and after. A part the
    guide left as it was is counted as kept; an unknown part, a heading, or a second row for
    one part is dropped."""
    rows, dropped = _rows(found, 'parts', ('part', 'text'))
    order = ['opening'] + [s['id'] for s in draft['sections']]
    items, seen, kept = [], set(), 0
    for row in rows:
        part = row.get('part')
        if part not in _prose_parts(draft) or part in seen:
            dropped += 1
            continue
        seen.add(part)
        before, after = desk_images.scrub(desk.text_of(draft, part)), row['text'].strip()
        if not before.strip():
            dropped += 1
            continue
        if after == before.strip():
            kept += 1
            continue
        try:
            desk_images.restored(desk.text_of(draft, part), after)
        except ValueError:
            dropped += 1  # It lost or changed image data the part keeps as text.
            continue
        if not after or desk.has_heading(after, desk.limit(draft)):
            dropped += 1
            continue
        items.append(
            {
                'part': part,
                'before': before,
                'after': after,
                'note': _text(row.get('why'), 500),
                'flag': _flags(before, after, anywhere=True),
                'whole': True,
            }
        )
    items.sort(key=lambda item: order.index(item['part']))
    return items, dropped, {'kept': kept}


def _read_copyedit(draft, found):
    """Located sentence fixes, read as Humanize's are, and the title's too, each with its
    kind and a wording fix with any alternatives."""
    return _read_humanize(draft, found, title=True, kinds=True)


READERS = {
    'finish-copyedit': _read_copyedit,
    'finish-humanize': _read_humanize,
    'finish-facts': _read_facts,
    'finish-headline': _read_headline,
    'finish-feedback': _read_feedback,
    'finish-voice': _read_voice,
}


def settle(root, ident, draft, job):
    """Read a finishing tool's result strictly and keep its proposals for the person. The
    draft is not changed; a result Blog Studio cannot read is refused readably."""
    import json

    content = ((job.get('result') or {}).get('content') or '').strip()
    fenced = re.fullmatch(r'```(?:json)?\s*\n(.*)\n```', content, re.S)
    try:
        found = json.loads(fenced.group(1) if fenced else content)
    except ValueError:
        raise ValueError(UNREADABLE) from None
    try:
        items, dropped, extra = READERS[job['kind']](draft, found)
    except (TypeError, AttributeError, KeyError):
        raise ValueError(UNREADABLE) from None  # A shape no reader expects, said plainly.
    meta = (job.get('metadata') or {}).get('desk') or {}
    if meta.get('level'):
        extra['level'] = meta['level']
    if meta.get('guide_name'):
        extra['guide_name'] = meta['guide_name']  # Which voice guide the set applies.
    return keep(root, ident, job['id'], job['kind'], items, dropped=dropped, **extra)


# Before publishing: repurpose into new desk blogs, and send the desk's wording to the
# blog's Google Doc as suggestions. The pre-publish check reads DRAFT.md, which every desk
# write keeps in step.
NO_DOC = (
    'This blog has no Google Doc to send suggestions to. A blog started from a Google Doc can '
    'send its desk changes back to that Doc.'
)


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
LITERAL = re.compile('(\x00[0-9]+\x00)')
DEFINITION = re.compile(r'\s*\[([^\]^][^\]]*)\]:')
TOKEN = re.compile(r"\w+(?:['’-]\w+)*|[^\S\n]+|.", re.S)
NOTE_LIMIT = 1000  # characters in one suggestion's or comment's reason
NOTE_BYTES = 1800  # and bytes, under Google's 2,048 for a comment with its marker
# A character's style as the Doc shows it: bold, italic, code, underline, raised or lowered,
# and the address it links to.
PLAIN = (False, False, False, False, None, None)
BREAK = ('\n', PLAIN)


def _inline(text, state, link, chars, images):
    """The characters a run of inline Markdown shows, each with its style."""
    at = 0
    for found in INLINE.finditer(text):
        _literal(text[at : found.start()], state, link, chars)
        at = found.end()
        if found['image']:
            images.append(found['image'])
        elif found['url'] is not None:
            target = found['url'].strip().split()[0] if found['url'].strip() else ''
            _inline(found['text'], state, target.strip('<>'), chars, images)
        elif found['auto']:
            _literal(found['auto'], state, found['auto'], chars)
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
    _literal(text[at:], state, link, chars)


def _literal(text, state, link, chars):
    style = (
        state['bold'],
        state['italic'],
        state['code'],
        state['underline'],
        state['script'],
        link or None,
    )
    for piece in LITERAL.split(text):
        if LITERAL.fullmatch(piece):
            chars.append((chr(int(piece[1:-1])), style))  # An escaped mark is the character.
        else:
            chars.extend((character, style) for character in piece)


def _styled(line):
    """A Markdown line as the Doc's body paragraph shows it: its kind of paragraph, each
    character with its style (without the spaces around them), and its images. None for a
    line that is not a paragraph (a table row, a fence, a footnote's or a link's definition,
    such as an image's data)."""
    bare = line.strip()
    if bare.startswith('|') or bare.startswith(('```', '~~~')) or re.match(r'\[[^\]]+\]:', bare):
        return None
    # An escaped mark is the character itself, as Google's Markdown export writes it.
    line = ESCAPED.sub(lambda found: '\x00' + str(ord(found.group(1))) + '\x00', line)
    block, mark = 'text', LINE_MARK.match(line)
    if mark:
        if mark['heading']:
            block = 'heading ' + str(len(mark['heading']))
        elif mark['bullet']:
            block = 'bullet'
        elif '>' in mark.group():
            block = 'quote'
        else:
            block = 'number'
        line = line[mark.end() :]
    chars, images = [], []
    state = {'bold': False, 'italic': False, 'code': False, 'underline': False, 'script': None}
    _inline(line, state, None, chars, images)
    while chars and chars[0][0].isspace():
        chars.pop(0)
    while chars and chars[-1][0].isspace():
        chars.pop()
    return {'block': block, 'chars': chars, 'images': images}


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
            out.append([start, end, text[start:end], added])
            continue
        if start == end:
            # Inserted text starting with the space already there goes in after that space, so
            # it neither starts with a space nor takes a link's or bold style from the left.
            while (
                replacement
                and replacement[0][0].isspace()
                and start < len(text)
                and text[start] == replacement[0][0]
            ):
                replacement = replacement[1:] + replacement[:1]
                start = end = start + 1
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
            out.append([a, b, text[a:b], text[a:start] + added + text[end:b]])
            taken = taken_now + [(a, b)]
            break
        else:
            return None
    return sorted(out)


def _simulated(old, edits):
    """The paragraph's characters and styles once every edit is accepted, as Google makes
    them: kept words keep their style, and inserted text takes the style of the first word
    it replaces, or of the word it follows. Each character says where it came from: ('old',
    position) or ('edit', number)."""
    import google_suggestions

    out, at = [], 0
    for number, (start, end, before, after) in enumerate(edits):
        out += [(old[i][0], old[i][1], ('old', i)) for i in range(at, start)]
        keep_start, keep_end = google_suggestions.trimmed(before, after)
        a, b = start + keep_start, end - keep_end
        style = old[a][1] if a < b else old[max(start, a - 1)][1]
        if a == b and start < a < len(old) and old[a - 1][0].isspace():
            style = old[a][1]  # After a space: the style of the words it comes before.
        out += [(old[i][0], old[i][1], ('old', i)) for i in range(start, a)]
        out += [(c, style, ('edit', number)) for c in after[keep_start : len(after) - keep_end]]
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
    if images:
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
        }
        for start, end, before, after in edits
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
    """Whether the Doc's paragraph can take a suggestion or comment: text, and no image."""
    return bool(styled and not styled['images'] and styled['chars'])


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
        lines, images = [], {}
        for line in text.splitlines():
            label = DEFINITION.match(line)
            if label:
                images[label.group(1)] = line.strip()
            elif line.strip():
                lines.append(line)
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
    for label, line in old_images.items():
        if new_images.get(label, line) != line:
            where = next((k for k, l in enumerate(before) if '][' + label + ']' in l), 0)
            note(
                where,
                ('image', label, studio.digest(new_images.get(label, '').encode())[:16]),
                'The image ' + _quoted(label, 40) + ' changed on the writing desk; '
                'replace it in the Doc by hand.',
            )
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

    def nearest(k):
        return sorted(anchorable, key=lambda m: (abs(m - k), m))

    def same_lines(k):
        return sum(1 for line in before[:k] if line == before[k])

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
            found.append(item)
            paragraphs[item['id']] = {
                'paragraph': studio.digest(old.encode()),
                'needle': needle,
                'matches': matches,
                'text': shown,  # The paragraph the change is meant for, as shown.
                'near': [texts[m] for m in nearest(k)[:8]],
                'was': shown,
                'now': now,
            }
    # A note for a paragraph as a whole is a comment of its own, placed when the plan is made
    # on the closest paragraph nothing else in that plan uses, so it never rides on a
    # suggestion and is never dropped with one sent before.
    for k in sorted(notes):
        if not anchorable:
            left += len(notes[k])
            continue
        for key, text, about in notes[k]:
            ident = json.dumps(['note', before[k], same_lines(k), key])
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
                'near': [texts[m] for m in nearest(k)[:8]],
                'about': about,
                'float': True,
            }
    return found, left, paragraphs


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
    return {
        'plans': dict(found.get('plans') or {}),
        'sent': list(found.get('sent') or []),
        'name': found.get('name') if isinstance(found.get('name'), str) else None,
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
    import google_roundtrip as rt
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
    record['name'] = ' '.join((inline.get('title') or '').split()) or None
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
    proposals = [p for p in proposals if p['id'] not in sent]
    # While the Doc holds suggestions, a change sent before that the desk no longer makes
    # (reworded again, or undone) holds everything: sending around it could repeat or undo a
    # suggestion still waiting for the Doc's owner. Each such change is counted as waiting.
    gone = []
    if rt.suggestions(inline):
        gone = [
            row
            for row in record['sent']
            if row.get('base', base['transfer']) == base['transfer']
            and row.get('id') not in current
        ]
    waiting, covers = 0, {}
    if gone:
        waiting, proposals = len(gone) + len(proposals), []
    if proposals:
        proposals, also, unplaced, covers = _not_pending(
            inline, base['document'], proposals, paragraphs
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
    plan = manuscript_editor.google_plan(
        client, root, ident, proposals, mode, _google_expected(root, ident), base['document']['url']
    )
    rows = [
        {'id': name, 'paragraph': paragraphs[name]['paragraph'], 'base': base['transfer']}
        for p in proposals
        for name in [p['id'], *covers.get(p['id'], [])]
    ]
    record['plans'] = {
        **{token: found for token, found in record['plans'].items() if token != plan['plan']},
        plan['plan']: rows,
    }
    record['plans'] = dict(list(record['plans'].items())[-20:])
    studio.write_json(_sent_path(root, ident), record)
    return {
        **plan,
        'suggestions': sum(1 for p in proposals if p['kind'] == 'edit'),
        'comments': sum(1 for p in proposals if p['kind'] == 'comment'),
        'left': left,
        'sent_before': before,
        'waiting': waiting,
    }


def _paragraph_texts(inline, tabs):
    """[(key, paragraph, text, settled)] for each Doc body paragraph of text, in order: its
    text as the Doc had it (without suggested insertions, suggested deletions as they stand),
    and whether nothing waits in it, nor in a paragraph a suggested break split it from."""
    import google_roundtrip as rt

    found, split = [], False
    for key, paragraph in rt.paragraphs(inline).items():
        runs = [element.get('textRun') for element in paragraph.get('elements', [])]
        last = runs[-1] if runs and runs[-1] else {}
        was_split = split
        split = bool(last.get('suggestedInsertionIds')) and last.get('content', '').endswith('\n')
        if key[0] not in tabs or not runs or not all(runs):
            continue
        text = ''.join(run['content'] for run in runs if not run.get('suggestedInsertionIds'))
        found.append(
            (
                key,
                paragraph,
                text[:-1] if text.endswith('\n') else text,
                not rt.suggestions(paragraph) and not was_split,
            )
        )
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
    for key, paragraph, text, settled in texts:
        at = text.find(needle)
        while at != -1:
            hits.append((key, paragraph, text, at + inner, settled))
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
    key, paragraph, text, at, settled = hits[0]
    import google_roundtrip as rt

    located = {k: v for k, v in proposal.items() if k not in ('context', 'occurrence')}
    located['tab_id'], located['start_index'] = key[0], key[1] + rt.utf16(text[:at])
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
    return None


def _not_pending(inline, document, proposals, expected):
    """The proposals that can go now, read from the Doc: how many wait for a pending
    suggestion in their paragraph, and how many could not be placed anywhere. A change that
    could land somewhere other than the paragraph it is meant for (the Doc shows its quote a
    different number of times than the desk counted, or it resolves to a paragraph with other
    words) goes as a comment on the closest paragraph that is certain instead, and one
    paragraph's changes go, wait or move together. A note for a paragraph as a whole is placed
    last, on a paragraph nothing else uses. Returns (free, waiting, unplaced, covers): covers
    names the changes each such comment stands for."""
    import json

    tabs = document['tab_ids']
    texts = _paragraph_texts(inline, tabs)
    held = {' '.join(text.split()) for _, _, text, settled in texts if not settled}
    groups, floats = {}, []
    for proposal in proposals:
        found = expected.get(proposal['id']) or {}
        if found.get('float'):
            floats.append(proposal)
            continue
        place = json.dumps([found.get('paragraph'), found.get('near')])
        groups.setdefault(place, []).append(proposal)
    free, waiting, moved, used, stopped = [], 0, [], set(), set()
    for group in groups.values():
        states = []
        for proposal in group:
            found = expected.get(proposal['id']) or {}
            meant = ' '.join((found.get('text') or '').split())
            where = _where(texts, proposal, found)
            if where is not None and not where[3]:
                states.append(('wait', proposal))
            elif (
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
    unplaced, covers = 0, {}
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
            unplaced += 1
        else:
            free.append(comment)
    return free, waiting, unplaced, covers


def _text_of(texts, key):
    return next((text for k, _, text, _ in texts if k == key), '')


def google_send(root, ident, data):
    """Send a confirmed plan through the existing ledger, once, while the desk text is as
    it was when the plan was made."""
    import google_drive as drive

    import manuscript_editor

    expected = _google_expected(root, ident)
    client = drive.Client(drive.account_for(root))
    result = manuscript_editor.google_send(client, root, ident, data, expected)
    record = _sent(root, ident)
    rows = record['plans'].pop(data.get('plan'), None)
    if rows:
        known = {row.get('id') for row in record['sent']}
        record['sent'] = (record['sent'] + [row for row in rows if row.get('id') not in known])[
            -500:
        ]
        studio.write_json(_sent_path(root, ident), record)
    return result


def repurpose(root, ident, job_id, title, content):
    """Make a repurpose job's output a new desk blog, once: the job's receipt names it."""
    import tool_jobs

    job = tool_jobs.read(root, job_id)
    if job.get('kind') != 'repurpose' or (job.get('metadata') or {}).get('article') != ident:
        raise ValueError('Choose prepared copy from this blog.')
    if job.get('applied'):
        made = job['applied'].get('desk') if isinstance(job['applied'], dict) else None
        if made:
            return made
        raise ValueError('This copy was already saved. Prepare it again for a new blog.')
    if job.get('status') != 'ready':
        raise ValueError('Wait for the prepared copy before making it a blog.')
    if not isinstance(content, str) or not content.strip() or len(content) > desk.LIMIT:
        raise ValueError('Keep the prepared copy, up to 200,000 characters.')
    if not isinstance(title, str) or not title.strip() or '\n' in title.strip() or len(title) > 500:
        raise ValueError('Give the new blog a title of one line, up to 500 characters.')
    source = desk.read(root, ident)
    data = {'title': title.strip(), 'manuscript': content, 'tone': source.get('tone') or ''}
    if source.get('style'):
        try:
            studio.style_check(root, source['style']['style_id'])
            data['style'] = source['style']['style_id']
        except (ValueError, KeyError, TypeError):
            pass  # A retired kind of post: the copy is a blog of no particular kind.
    # The images the copy names come with it, so the new blog does not open without them.
    images = source.get('images') or {}
    if images and desk_images.REFERENCE.search(content):
        held = desk._data(root, ident)
        named = desk_images.written(
            {'title': '', 'opening': content, 'sections': [], 'images': images}
        )
        lines = desk_images.definitions(
            {
                'title': '',
                'opening': content,
                'sections': [],
                'images': {n: images[n] for n in named},
            },
            held,
        )
        if lines:
            data['manuscript'] = content.rstrip() + '\n\n' + '\n\n'.join(lines) + '\n'
    made = desk.create(root, data)
    job['applied'] = {'desk': {'id': made['id'], 'title': made['title']}, 'posted': False}
    job['saved_content'] = content
    tool_jobs.write(root, job)
    return job['applied']['desk']
