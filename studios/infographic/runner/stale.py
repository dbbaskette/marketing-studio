"""Work held out of date after a brief or source change: update it, or keep it as it is.

A brief or source edit keeps the facts, stories, page and artwork built from the earlier
inputs and names each as out of date (contracts.advance). Every part has two actions:
Update makes it again from the current inputs, and Keep as it is clears the mark without
changing it. Approval, prepared files and delivery wait until nothing they show is out of
date (contracts.require_current). Each action is its own saved revision.
"""
from __future__ import annotations

from copy import deepcopy

from .contracts import STALE_PARTS, stale_parts
from .validation import require

# How the page updates each part: the action it runs and what that action makes again.
UPDATES = {'facts': 'suggest', 'stories': 'suggest', 'page': 'refresh-page', 'artwork': 'art-direct'}


def clear(store, ident, parts, *, expected_revision):
    """Clear the out-of-date mark of `parts` (kept as they are, or made again unchanged)."""
    require(isinstance(parts, (list, tuple)) and parts and all(p in STALE_PARTS for p in parts),
            'Choose a part of this infographic: facts, story, page or artwork.')
    with store.locked():
        project = store.read(ident)
        store.expect(project, expected_revision)
        held = stale_parts(project)
        require(any(part in held for part in parts), 'That part is not out of date.')
        result = deepcopy(project)
        remaining = {part: value for part, value in held.items() if part not in parts}
        if remaining:
            result['stale'] = remaining
        else:
            result.pop('stale', None)
        result['revision'] += 1
        result['approval'] = None
        return store.commit_locked(project, result)


def keep(store, ident, part, *, expected_revision):
    """Keep one out-of-date part as it is."""
    require(part in STALE_PARTS, 'Choose a part of this infographic: facts, story, page or artwork.')
    return clear(store, ident, [part], expected_revision=expected_revision)


def refresh_page(engine, ident, *, expected_revision):
    """Lay the page out again from the current brief and story, place the saved artwork on it
    again, and draw it. Local: no assistant or image request."""
    from . import scene
    store = engine.store
    project = store.read(ident)
    store.expect(project, expected_revision)
    require(project['scene'] is not None and project['selected_story'] is not None,
            'Choose a story and build its page first.')
    artwork = next((e['asset_id'] for e in project['scene']['elements'] if e['kind'] == 'artwork'), None)
    engine.progress('Laying out the page again')
    project = scene.adopt_best(store, ident, expected_revision=project['revision'])
    if 'page' in stale_parts(project):
        # Laid out the same as before: it is current all the same.
        project = clear(store, ident, ['page'], expected_revision=project['revision'])
    if artwork and project['scene'].get('art_regions') \
            and not any(e['kind'] == 'artwork' for e in project['scene']['elements']):
        project = engine.compose_asset(ident, artwork, expected_revision=project['revision'])
    return engine.preview(ident, expected_revision=project['revision'])
