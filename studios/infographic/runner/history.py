"""Compare immutable content; restore as a new revision with no inherited approval."""
from copy import deepcopy

from .contracts import EDITABLE, digest
from .validation import require


def entries(store, ident, *, before=None):
    """Newest first, each with its exact identity, what it did, its content and when."""
    from .labels import change, _content
    # One older revision explains the oldest entry on this page.
    saved = store.history(ident, before=before, limit=101)
    shown = saved[-100:]
    # Each revision's content fingerprint once; `older` grows as the page is walked.
    contents = [_content(p) for p in saved]
    first = len(saved) - len(shown)
    older = set(contents[:max(0, first - 1)])
    result = []
    for index, p in enumerate(shown):
        position = first + index
        previous = saved[position - 1] if position else None
        if position >= 2:
            older.add(contents[position - 2])
        fingerprint = digest(p)
        result.append({'revision': p['revision'], 'sha256': fingerprint, 'title': p['brief']['title'],
                       'scene_id': (p['scene'] or {}).get('id'), 'approved': p['approval'] is not None,
                       **change(previous, p, older, contents[position]), 'saved_at': store.saved_at(ident, p['revision'], fingerprint)})
    return list(reversed(result))


def version(store, ident, revision, fingerprint=None):
    found = [p for p in store.history(ident, revision=revision) if p['revision'] == revision
             and (fingerprint is None or digest(p) == fingerprint)]
    require(len(found) == 1, 'Choose one intact saved revision by its exact identity.')
    return found[0]


def compare(store, ident, before, after):
    one, two = version(store, ident, before), version(store, ident, after)
    return {key: {'before': one[key], 'after': two[key]} for key in EDITABLE if one[key] != two[key]}


def restore(store, ident, revision, *, expected_revision, fingerprint=None):
    with store.locked():
        current = store.read(ident)
        store.expect(current, expected_revision)
        previous = version(store, ident, revision, fingerprint)
        restored = deepcopy(previous)
        restored.update(revision=current['revision'] + 1, approval=None, checks=[], attempts=[], exports=[])
        return store.commit_locked(current, restored)
