"""Work held out of date after a brief or source change: update it, or keep it as it is.

THE RULE. A mark is cleared only explicitly, in exactly these cases and no other, and
contracts.advance (with _cleared) is the one place that enforces (b) and (c):
 (a) the person chooses Keep as it is for that part on the page (keep / clear below);
 (b) an operation that makes that WHOLE part again says so by name (`remade`): facts and
     stories by adopting a newly suggested set from Find the story (engine._propose); the
     page by being laid out again (scene.adopt / adopt_best: layout, visual layout, Update
     the page); artwork by new artwork, made after the mark, being placed on the page
     (engine.compose_asset);
 (c) nothing of the part is left anywhere in the record (artwork: no asset and no artwork
     element on the page; page: no scene; stories: no stories; facts: no facts). A notice
     naming dropped facts or removed stories stays until (a) or (b).
Editing or revising one story, choosing a story, saving an art direction, editing a text
element, placing the same image again, restoring a revision and every conversation operation
never clear a mark. A revised story still shows as out of date until the person keeps it.

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
    # Laid out again (the same as before, or not), the page is current (scene.adopt_best).
    project = scene.adopt_best(store, ident, expected_revision=project['revision'])
    if artwork and project['scene'].get('art_regions') \
            and not any(e['kind'] == 'artwork' for e in project['scene']['elements']):
        project = engine.compose_asset(ident, artwork, expected_revision=project['revision'])
    return engine.preview(ident, expected_revision=project['revision'])
