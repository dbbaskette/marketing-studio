"""The desk record: the per-part check, saves, restores and removed parts.

Every write goes through the store a studio passes in (`store.write`), under the studio's
lock. A form that saw revision `seen` may still change a part nothing else changed after it,
so a rewrite landing in one section never refuses typing in another.
"""

from . import parts as _parts
from .parts import MARKDOWN
from .versions import SOURCES, Versions

REMOVED = 20  # removed sections kept to bring back
TOO_LONG = 'Keep one part under 200,000 characters.'
ONE_LINE = 'Keep the title to one line, up to 500 characters.'


def advance(draft, parts, now):
    """One revision on: the time, and each part in `parts` marked changed at it."""
    draft['revision'] += 1
    draft['updated_at'] = now
    changed = draft.setdefault('changed', {})
    for part in parts:
        changed[part] = draft['revision']
    return draft


def checked(draft, seen, parts=None, thing='draft'):
    """Refuse a form older than the parts it changes.

    With no parts named, the whole item must be as the form saw it. With parts, a form
    that saw revision `seen` may still change a part nothing else changed after it."""
    old = 'This ' + thing + ' changed since you opened it. Reload to see the latest.'
    if type(seen) is not int or not 1 <= seen <= draft['revision']:
        raise ValueError(old)
    if parts is None:
        outdated = seen != draft['revision']
    else:
        changed = draft.get('changed') or {}
        outdated = any(changed.get(part, 1) > seen for part in parts)
    if outdated:
        raise ValueError(old)


def checked_text(part, text, codec=MARKDOWN, deepest=2):
    """Refuse text a part cannot hold. `deepest` is the draft's `codec.deepest`: a heading
    at that level or above would start a new part."""
    if not isinstance(text, str) or len(text) > _parts.LIMIT:
        raise ValueError(TOO_LONG)
    if codec.vet is not None:
        codec.vet(part, text)
    if part in codec.single and (
        not text.strip() or '\n' in text.strip() or len(text.strip()) > 500
    ):
        raise ValueError(ONE_LINE)
    if part not in codec.single and codec.breaks(text, deepest):
        raise ValueError(codec.break_message(deepest))
    return text


class Desk:
    """One studio's desk record, over its store and codec. `versions` replaces the
    part-keyed version files with another store of versions of the same shape."""

    REMOVED = REMOVED

    def __init__(self, store, codec=MARKDOWN, sources=SOURCES, versions=None):
        self.store, self.codec = store, codec
        self.versions = versions if versions is not None else Versions(store, codec, sources)

    def read(self, ident):
        return self.store.read(ident)

    def checked(self, draft, seen, parts=None):
        checked(draft, seen, parts, self.codec.thing)

    def checked_text(self, part, text, deepest=2):
        return checked_text(part, text, self.codec, deepest)

    def save(self, ident, seen, part, text, source='save', session=None):
        """Save one part the form last saw at revision `seen`; an outdated form is refused.
        The same text again, as from a retried save, is not refused."""
        codec = self.codec
        if not isinstance(text, str):
            raise ValueError(TOO_LONG)
        draft = self.read(ident)
        after = draft
        if part not in codec.single and codec.taken is not None:
            # A restored version replaces the part whole: what it carries is its own.
            previous = '' if source == 'restore' else codec.text_of(draft, part)
            text, after = codec.taken(draft, part, text, previous)
        before = codec.text_of(draft, part)
        if before == text.strip() and after is draft:
            return draft
        self.checked(draft, seen, [part])  # An outdated form is told to reload first.
        self.checked_text(part, text, codec.deepest(draft))
        after = dict(after)
        codec.set_text(after, part, text)
        after = codec.fitted(after, draft)
        self.versions.keep(ident, part, before, source, session)
        return self.store.write(ident, after, [part])

    def restore(self, ident, seen, part, index):
        """Bring back a kept version; the text it replaces is kept as a version too."""
        found = self.versions.kept(ident, part)
        if type(index) is not int or not 0 <= index < len(found):
            raise ValueError('Choose a saved version.')
        return self.save(ident, seen, part, found[index]['text'], source='restore')

    def _removed_path(self, ident):
        return self.store.path(ident, 'removed.json')

    def removed(self, ident):
        """Sections taken out of the outline, newest first, each with its text and brief."""
        target = self._removed_path(ident)
        if not target.is_file() or target.is_symlink():
            return []
        try:
            found = self.store.read_json(target)
        except (ValueError, OSError):
            return []
        return [item for item in found if isinstance(item, dict)] if isinstance(found, list) else []

    def keep_removed(self, ident, sections):
        if sections:
            self.store.write_json(
                self._removed_path(ident), (sections + self.removed(ident))[: self.REMOVED]
            )

    def unremove(self, ident, seen, index):
        """Bring a removed section back where it was, with its id, so its History comes too."""
        codec = self.codec
        found = self.removed(ident)
        if type(index) is not int or not 0 <= index < len(found):
            raise ValueError('Choose a removed ' + codec.noun + '.')
        draft = self.read(ident)
        self.checked(draft, seen, ['outline'])
        if len(draft['sections']) >= _parts.SECTIONS:
            raise ValueError(
                'Keep the outline to ' + str(_parts.SECTIONS) + ' ' + codec.noun + 's.'
            )
        item = found[index]
        taken = {section['id'] for section in draft['sections']}
        kept = str(item.get('id') or '')
        part = kept if codec.part.fullmatch(kept) and kept not in taken else _parts.new_id(taken)
        text, after = str(item.get('text') or ''), draft
        if codec.taken is not None:
            text, after = codec.taken(draft, part, text, '')
        section = {
            'id': part,
            'heading': ' '.join(str(item.get('heading') or codec.noun.capitalize()).split())[
                :200
            ],
            'brief': str(item.get('brief') or '')[: _parts.BRIEF],
            'text': text.strip(),
        }
        after = dict(after)
        at = item.get('index') if type(item.get('index')) is int else len(after['sections'])
        after['sections'].insert(max(0, min(at, len(after['sections']))), section)
        after = codec.fitted(after, draft)
        self.store.write_json(self._removed_path(ident), found[:index] + found[index + 1 :])
        return self.store.write(ident, after, [part, 'outline'])
