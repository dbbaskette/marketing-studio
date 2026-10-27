"""Finishing's proposals: tools propose changes the person previews, then applies or skips.

Nothing changes until Apply. A set of proposals waits on this computer only, in the store's
`local(ident)` folder as `<job>.json`, never in the item's own folder, so a team workspace
records only what Apply writes. Each Apply keeps a `finishing` version of every part it
changes first, and marks the proposals applied only once the item is written.

A set is `{'schema': 1, 'job', 'kind', <owner>: ident, 'made_at', ..., 'items'}`; `owner`
is the key it names its item by (Blog Studio's sets say `blog`). `tools` maps a job kind to
its panel name. A proposal is a text swap by default: `before` once in its part replaced by
`after`, or a whole part (`whole`) while the part is as it was. A studio whose proposals are
not text swaps passes `present(draft, item)` (whether one still fits) and `fit(draft, item,
after, text)` (the part's new text, or a ValueError saying why it no longer fits), or
subclasses `Proposals`.
"""

import json
import re
import shutil
import time

from . import parts as _parts
from .parts import MARKDOWN
from .record import ONE_LINE, TOO_LONG
from .store import require_held

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
OVERLAP = 'Another suggestion applied here covers the same words, so this one was not applied.'
RETIRED = 'This suggestion no longer fits: another change replaced its words.'
FLAGGED = 'It covers words a flagged suggestion still waits on, so Accept all left it for you.'
WORKING = 'A desk job is working on this part. Wait for it, or stop it, then apply.'
GONE_SET = 'These suggestions are no longer here. Run the tool again.'


def once(text, before):
    """Whether `before` occurs in `text` exactly once, counting overlapping occurrences."""
    at = text.find(before) if before else -1
    return at != -1 and text.find(before, at + 1) == -1


def text_present(codec=MARKDOWN):
    """The default `present`: a proposal's text is in its part, once, or the whole part is
    as it was for an alternative to the whole part. A comment needs only its part."""

    def present(draft, item):
        if item.get('part') == 'whole':
            return True
        try:
            text = codec.text_of(draft, item.get('part'))
        except ValueError:
            return False
        if 'comment' in item:
            return True
        if item.get('whole'):
            # A whole part is kept as the job saw it (the codec's `scrub`).
            return codec.scrub(text) == item.get('before')
        return once(text, item.get('before') or '')

    return present


def text_fit(codec=MARKDOWN):
    """The default `fit`: `before` once in the part replaced by `after`, or the whole part
    while it is as the job saw it, then the codec's `landed` shape (for a part that is not
    one line). GONE when it no longer fits."""

    def fit(draft, item, after, text):
        if item.get('whole'):
            fits = codec.scrub(text) == item['before']
        else:
            fits = once(text, item['before'])
        if not fits:
            raise ValueError(GONE)
        if item.get('whole'):
            updated = after.strip()
        else:
            at = text.index(item['before'])
            updated = text[:at] + after + text[at + len(item['before']) :]
        if item['part'] not in codec.single:
            updated = codec.landed(draft, text, updated)
        return updated

    return fit


def span(text, item):
    """Where a suggestion sits in its part's text, (start, end), or None when it is not
    there once. A whole-part alternative covers the whole part."""
    if item.get('whole'):
        return (0, max(1, len(text)))
    before = item.get('before') or ''
    if 'comment' in item or not once(text, before):
        return None
    at = text.index(before)
    return (at, at + len(before))


def covers(spans, found):
    """Whether `found` shares any character with one of `spans`: two suggestions that start
    at the same place overlap too."""
    start, end = found
    return any(start < b and a < end for a, b in spans)


def read_result(content, unreadable):
    """A tool's result as strict JSON, fenced in ```json or not; `unreadable` otherwise."""
    content = (content or '').strip()
    fenced = re.fullmatch(r'```(?:json)?\s*\n(.*)\n```', content, re.S)
    try:
        return json.loads(fenced.group(1) if fenced else content)
    except ValueError:
        raise ValueError(unreadable) from None


def rows(found, key, fields, unreadable):
    """The result's rows, each a dict whose named fields are text. A row of another shape is
    dropped; a result made only of such rows cannot be read."""
    listed = found.get(key) if isinstance(found, dict) else None
    if not isinstance(listed, list):
        raise ValueError(unreadable)
    good = [
        row
        for row in listed[:60]
        if isinstance(row, dict) and all(isinstance(row.get(name), str) for name in fields)
    ]
    if listed and not good:
        raise ValueError(unreadable)
    return good, len(listed[:60]) - len(good)


def located(draft, part, before, codec=MARKDOWN):
    """`before` as it occurs once in its part, or None."""
    try:
        text = codec.text_of(draft, part)
    except ValueError:
        return None
    before = before.strip() if isinstance(before, str) else ''
    if not once(text, before):
        return None
    return before


class Proposals:
    """One studio's waiting proposals over its store and desk record. `together` names the
    tools whose sentence rewrites are shown together: accepting one retires the others,
    from any of them, that covered the same words."""

    def __init__(self, store, desk, tools, owner='item', present=None, fit=None, together=()):
        self.store, self.desk, self.tools, self.owner = store, desk, dict(tools), owner
        self.codec = desk.codec
        self.present = present or text_present(self.codec)
        self.fit = fit or text_fit(self.codec)
        self.together = tuple(together)

    # The sets, on this computer.

    def folder(self, ident):
        return self.store.local(ident)

    def path(self, ident, job):
        if not isinstance(job, str) or not JOB.fullmatch(job):
            raise ValueError('Choose a set of suggestions on this ' + self.store.word + '.')
        return self.store.local(ident, job + '.json')

    def keep(self, ident, job, kind, items, **extra):
        """Keep a set of proposals for the person to preview; nothing in the item changes."""
        require_held(self.store)
        if kind not in self.tools:
            raise ValueError('Choose a finishing tool.')
        value = {
            'schema': 1,
            'job': job,
            'kind': kind,
            self.owner: ident,
            'made_at': self.store.now(),
            **extra,
            'items': [
                {**item, 'id': 'p' + str(number + 1), 'state': 'open'}
                for number, item in enumerate(items[:ITEMS])
            ],
        }
        self.store.write_json(self.path(ident, job), value)
        newest = self.latest(ident)
        newest[self.tools[kind]] = job
        self.store.write_json(self.store.local(ident, LATEST), newest)
        self.prune(ident, set(newest.values()))
        return value

    def latest(self, ident):
        """{tool: job} for the newest set of each tool, rebuilt from the sets when missing."""
        target = self.store.local(ident, LATEST)
        try:
            found = (
                self.store.read_json(target)
                if target.is_file() and not target.is_symlink()
                else None
            )
        except (ValueError, OSError):
            found = None
        if isinstance(found, dict) and all(
            tool in self.tools.values() and isinstance(job, str) and JOB.fullmatch(job)
            for tool, job in found.items()
        ):
            return found
        newest = {}
        for value in self.sets(ident):
            newest[self.tools[value['kind']]] = value['job']
        return newest

    def prune(self, ident, shown):
        """Let go of sets no longer shown once nothing in them is open, or after a day."""
        folder = self.folder(ident)
        for target in sorted(folder.glob('*.json')) if folder.is_dir() else []:
            if not JOB.fullmatch(target.stem) or target.stem in shown or target.is_symlink():
                continue
            try:
                value = self.store.read_json(target)
                done = not any(item.get('state') == 'open' for item in value.get('items', []))
                if done or time.time() - target.stat().st_mtime > DAY:
                    target.unlink()
            except (ValueError, OSError, AttributeError):
                continue

    def read(self, ident, job):
        target = self.path(ident, job)
        if not target.is_file() or target.is_symlink():
            raise ValueError(GONE_SET)
        found = self.store.read_json(target)
        if not isinstance(found, dict) or found.get(self.owner) != ident:
            raise ValueError(GONE_SET)
        return found

    def sets(self, ident):
        """Every set kept for this item, oldest first."""
        folder = self.folder(ident)
        found = []
        for target in sorted(folder.glob('*.json')) if folder.is_dir() else []:
            if target.is_symlink() or not JOB.fullmatch(target.stem):
                continue
            try:
                value = self.store.read_json(target)
            except (ValueError, OSError):
                continue
            if (
                isinstance(value, dict)
                and value.get('kind') in self.tools
                and value.get(self.owner) == ident
            ):
                found.append(value)
        return sorted(found, key=lambda value: value.get('made_at') or '')

    def forget(self, ident):
        """Let a deleted item's waiting suggestions go: they hold its text."""
        folder = self.folder(ident)
        if folder.is_dir() and not folder.is_symlink():
            shutil.rmtree(folder)

    def summary(self, ident, draft):
        """The newest set for each tool, as the panel shows it. Only those sets are read."""
        newest = {}
        for tool, job in self.latest(ident).items():
            try:
                value = self.read(ident, job)
            except (ValueError, OSError):
                continue
            if self.tools.get(value.get('kind')) == tool:
                newest[tool] = value
        return {
            tool: {
                **value,
                'items': [{**item, 'present': self.present(draft, item)} for item in value['items']],
            }
            for tool, value in newest.items()
        }

    # Apply and Skip.

    def apply(self, ident, seen, job, chosen, every=False, working=frozenset()):
        """Apply chosen proposals, each with its suggested text or the person's own (Edit).

        One proposal that no longer fits is refused with nothing changed. Several at once
        (Apply all) apply every one that still fits and leave the rest open, counted in
        `left`; one retired meanwhile is left out too. `every` is Accept all: a suggestion
        that covers words a flagged one of the `together` tools still waits on is left out,
        so the flagged one is never retired without the person deciding on it. `working` is
        the parts a job under way may change (or a function that returns them, asked once
        the request is checked): a part among them, or any section while `sections` is, is
        refused. Each part changed keeps one `finishing` version first."""
        codec, desk = self.codec, self.desk
        found = self.read(ident, job)
        if not isinstance(chosen, list) or not chosen or len(chosen) > ITEMS:
            raise ValueError('Choose the suggestions to apply.')
        if type(every) is not bool:
            raise ValueError('Choose suggestions from this set.')
        items = {item['id']: item for item in found['items']}
        picks, named, gone = [], set(), []
        for entry in chosen:
            if (
                not isinstance(entry, dict)
                or set(entry) - {'id', 'after', 'alternative'}
                or entry.get('id') not in items
                or entry['id'] in named
            ):
                raise ValueError('Choose suggestions from this set.')
            named.add(entry['id'])
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
            after = entry['after'] if 'after' in entry else item['after']
            if 'alternative' in entry:
                # One of a wording fix's alternatives, by its place in the list.
                others = item.get('alternatives') or []
                number = entry['alternative']
                if 'after' in entry or type(number) is not int or not 0 <= number < len(others):
                    raise ValueError('Choose one of this suggestion’s alternatives.')
                after = others[number]['after']
            if not isinstance(after, str) or len(after) > _parts.LIMIT:
                raise ValueError(TOO_LONG)
            picks.append((item, after))
        draft = desk.read(ident)
        parts = sorted({item['part'] for item, _ in picks})
        desk.checked(draft, seen, parts)
        busy = working() if callable(working) else working
        if any(part in busy or ('sections' in busy and part not in codec.fixed) for part in parts):
            raise ValueError(WORKING)
        single = len(chosen) == 1 and not every  # Accept all never refuses: it leaves out.
        texts, applied, left = {}, [], gone
        # Where each applied suggestion sat in its part as it was, so two that cover the same
        # words never both land, and the others it covered are retired once it does.
        originals = {part: codec.text_of(draft, part) for part in parts}
        spans = {part: [] for part in parts}
        waiting = self._flagged_spans(ident, job, found, originals, named) if every else {}
        for item, after in picks:
            part = item['part']
            try:
                if not after.strip():
                    raise ValueError(EMPTY)
                place = span(originals[part], item)
                if place is not None and covers(spans[part], place):
                    raise ValueError(OVERLAP)
                if place is not None and covers(waiting.get(part, []), place):
                    raise ValueError(FLAGGED)
                text = texts[part] if part in texts else codec.text_of(draft, part)
                updated = self.fit(draft, item, after, text)
                # A change that only an image reference made, put back as it was, is no change.
                if updated.strip() == text.strip():
                    raise ValueError(SAME)
                desk.checked_text(part, updated, codec.deepest(draft))
                if part in codec.single and not updated.strip():
                    raise ValueError(ONE_LINE)
            except ValueError:
                if single:
                    raise
                left.append(item['id'])
                continue
            texts[part] = updated
            applied.append(item)
            if place is not None:
                spans[part].append(place)
        if not applied:
            if every:
                return {'applied': 0, 'left': left}  # Each left for the person; nothing changed.
            raise ValueError(NONE_LEFT)
        changed = []
        for part, text in texts.items():
            before = codec.text_of(draft, part)
            if before.strip() == text.strip():
                continue
            desk.versions.keep(ident, part, before, 'finishing')
            codec.set_text(draft, part, text)
            changed.append(part)
        if changed:
            self.store.write(ident, draft, changed)
        # Only once the item is written are the proposals marked applied.
        for item in applied:
            item['state'] = 'applied'
            if item.get('group'):
                for other in found['items']:
                    if other.get('group') == item['group'] and other['state'] == 'open':
                        other['state'] = 'skipped'  # An alternative to the one chosen.
        self.store.write_json(self.path(ident, job), found)
        self._retire(ident, job, found, originals, spans)
        return {'applied': len(applied), 'left': left}

    def _together_sets(self, ident, job, found):
        """[(job, set)] for the waiting sets of the `together` tools, this one as it is held."""
        found_sets = [(job, found)]
        if found.get('kind') not in self.together:
            return found_sets
        for tool, other in self.latest(ident).items():
            kind = next(kind for kind, name in self.tools.items() if name == tool)
            if kind in self.together and other != job:
                try:
                    found_sets.append((other, self.read(ident, other)))
                except (ValueError, OSError):
                    continue
        return found_sets

    def _flagged_spans(self, ident, job, found, originals, named):
        """{part: [span]} of open, flagged suggestions still in the text that Accept all leaves
        for the person, from any of the `together` tools, other than the ones being applied."""
        spans = {}
        for name, value in self._together_sets(ident, job, found):
            for item in value.get('items', []):
                part = item.get('part')
                if (
                    item.get('state') != 'open'
                    or not item.get('flag')
                    or part not in originals
                    or (name == job and item.get('id') in named)
                ):
                    continue
                place = span(originals[part], item)
                if place is not None:
                    spans.setdefault(part, []).append(place)
        return spans

    def _retire(self, ident, job, found, originals, spans):
        """Mark open suggestions that covered words an applied one replaced as retired: they
        no longer fit, whether or not their words still happen to be in the text. Only this
        computer's waiting sets change."""
        if not any(spans.values()):
            return
        for name, value in self._together_sets(ident, job, found):
            changed = False
            for item in value.get('items', []):
                part = item.get('part')
                if item.get('state') != 'open' or part not in spans or not spans[part]:
                    continue
                place = span(originals[part], item)
                if place is not None and covers(spans[part], place):
                    item['state'] = 'retired'
                    changed = True
            if changed:
                self.store.write_json(self.path(ident, name), value)

    def skip(self, ident, job, ids):
        """Set proposals aside. Only this computer's waiting set changes."""
        found = self.read(ident, job)
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
        self.store.write_json(self.path(ident, job), found)
        return {'skipped': skipped}
