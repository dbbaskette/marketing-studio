"""Compare immutable content; restore as a new revision with no inherited approval."""
from copy import deepcopy

from .contracts import EDITABLE, digest
from .validation import require


def entries(store, ident, *, before=None):
    return [{'revision': p['revision'], 'sha256': digest(p), 'title': p['brief']['title'],
             'scene_id': (p['scene'] or {}).get('id'), 'approved': p['approval'] is not None}
            for p in reversed(store.history(ident, before=before))]


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
