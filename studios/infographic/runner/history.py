"""Compare immutable content; restore as a new revision with no inherited approval."""
from copy import deepcopy

from .contracts import EDITABLE, basis, digest
from .validation import require


class Pages:
    """The page revision of any saved revision: the one number a person is told.

    Checks, reviews, approvals, art direction and image requests save revisions too, but
    they leave the page and what it is built from as they were. A page revision is the
    revision at which that content (its basis) was first saved, in an unbroken run; the
    bookkeeping revisions after it carry the same number. Restoring older content is new
    work, so it starts a run of its own. Read-only: walking back reads saved revisions.
    """

    def __init__(self, store, ident, saved=()):
        self.store, self.ident = store, ident
        self.bases, self.known = {}, {}
        self.seed(saved)

    def seed(self, saved):
        for project in saved:
            self.bases.setdefault(project['revision'], basis(project))

    def _basis(self, revision):
        if revision not in self.bases:
            try:
                found = self.store.history(self.ident, revision=revision)
            except (ValueError, OSError):
                found = []
            self.bases[revision] = basis(found[0]) if len(found) == 1 else None
        return self.bases[revision]

    def of(self, revision):
        walked, here = [], revision
        while here not in self.known:
            walked.append(here)
            content = self._basis(here)
            if here <= 0 or content is None or self._basis(here - 1) != content:
                self.known[here] = here
                break
            here -= 1
        page = self.known[here]
        for one in walked:
            self.known[one] = page
        return page


def entries(store, ident, *, before=None, pages=None):
    """Newest first, each with its exact identity, what it did, its content, when, and the
    page revision it belongs to. `pages` (a Pages) is seeded with what is read here."""
    from .labels import change, _content
    # One older revision explains the oldest entry on this page.
    saved = store.history(ident, before=before, limit=101)
    pages = pages if pages is not None else Pages(store, ident)
    pages.seed(saved)
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
                       'page_revision': pages.of(p['revision']),
                       **change(previous, p, older, contents[position]), 'saved_at': store.saved_at(ident, p['revision'], fingerprint)})
    return list(reversed(result))


def version(store, ident, revision, fingerprint=None):
    found = [p for p in store.history(ident, revision=revision) if p['revision'] == revision
             and (fingerprint is None or digest(p) == fingerprint)]
    require(len(found) == 1, 'Choose one intact saved revision by its exact identity.')
    return found[0]


_ARRANGEMENTS = {'infographic': 'Visual infographic', 'stack': 'Stacked blocks', 'columns': 'Two columns'}


def _words(value):
    if isinstance(value, list):
        return '; '.join(str(item.get('text', item) if isinstance(item, dict) else item) for item in value) or 'None'
    return str(value) if value not in (None, '') else 'None'


def _story(project):
    found = next((s for s in project['stories'] if s['id'] == project['selected_story']), None)
    return found['headline'] if found else 'None chosen'


def _count(number, one, many):
    return str(number) + ' ' + (one if number == 1 else many)


def changes(one, two):
    """What a person can see differs between two saved revisions, in words: the words on the
    page by element label, the sources, the story choice, the layout, the brand, the brief,
    the artwork and the art direction. Each is {'what', 'before', 'after'}."""
    from .labels import _BRIEF, elements
    found = []
    def said(what, before, after):
        found.append({'what': what, 'before': before, 'after': after})
    for key, words in _BRIEF:
        if one['brief'].get(key) != two['brief'].get(key):
            said('Brief: ' + words, _words(one['brief'].get(key)), _words(two['brief'].get(key)))
    before = {s['id']: s for s in one['sources']}
    after = {s['id']: s for s in two['sources']}
    for ident in after.keys() - before.keys():
        said('Source added', None, after[ident].get('name') or 'Supplied information')
    for ident in before.keys() - after.keys():
        said('Source removed', before[ident].get('name') or 'Supplied information', None)
    for ident in before.keys() & after.keys():
        if before[ident] != after[ident]:
            said('Source updated', before[ident].get('name') or 'Supplied information',
                 after[ident].get('name') or 'Supplied information')
    if one['facts'] != two['facts']:
        said('Captured facts', _count(len(one['facts']), 'fact', 'facts'), _count(len(two['facts']), 'fact', 'facts'))
    if one['selected_story'] != two['selected_story'] or _story(one) != _story(two):
        said('Story choice', _story(one), _story(two))
    elif one['stories'] != two['stories']:
        said('Story proposals', _count(len(one['stories']), 'proposal', 'proposals'),
             _count(len(two['stories']), 'proposal', 'proposals'))
    if one['brand'] != two['brand']:
        name = lambda p: ((p['brand'] or {}).get('identity') or {}).get('name') or ('None' if p['brand'] is None else 'Pinned brand')
        said('Brand', name(one), name(two))
    scenes = one['scene'], two['scene']
    if scenes[0] is None or scenes[1] is None:
        if scenes[0] != scenes[1]:
            said('Page', 'No page' if scenes[0] is None else 'Built page', 'No page' if scenes[1] is None else 'Built page')
    elif scenes[0] != scenes[1]:
        listed = len(found)
        if scenes[0].get('arrangement') != scenes[1].get('arrangement'):
            said('Layout', _ARRANGEMENTS.get(scenes[0].get('arrangement'), 'Earlier layout'),
                 _ARRANGEMENTS.get(scenes[1].get('arrangement'), 'Current layout'))
        old = {e['id']: e for e in elements(one)}
        for element in elements(two):
            earlier = old.pop(element['id'], None)
            if earlier is None:
                said('Words added: ' + element['label'], None, element['text'])
            elif earlier['text'] != element['text']:
                said('Words: ' + element['label'], earlier['text'], element['text'])
        for element in old.values():
            said('Words removed: ' + element['label'], element['text'], None)
        art = lambda s: sum(1 for e in s['elements'] if e['kind'] == 'artwork')
        if art(scenes[0]) != art(scenes[1]):
            said('Artwork on the page', _count(art(scenes[0]), 'image', 'images'), _count(art(scenes[1]), 'image', 'images'))
        if len(found) == listed:
            # Sizes, colours or positions changed, but no words, layout or artwork.
            said('Page design', 'Earlier design', 'Changed design')
    if one['assets'] != two['assets']:
        said('Saved artwork', _count(len(one['assets']), 'image', 'images'), _count(len(two['assets']), 'image', 'images'))
    if one['image_briefs'] != two['image_briefs']:
        said('Art direction', _count(len(one['image_briefs']), 'saved brief', 'saved briefs'),
             _count(len(two['image_briefs']), 'saved brief', 'saved briefs'))
    return found


def compare(store, ident, before, after):
    """What changed between two saved revisions, as a person can see it, and the raw saved
    fields for an Advanced view. `same` says nothing visible changed; `since` then names
    what the revisions in between recorded (checks, a review, an approval, an image request).
    `before_export`/`after_export` name a saved rendering of each side, for thumbnails."""
    from .engine import Engine
    from .labels import change
    one, two = version(store, ident, before), version(store, ident, after)
    raw = {key: {'before': one[key], 'after': two[key]} for key in EDITABLE if one[key] != two[key]}
    pages = Pages(store, ident)
    described = changes(one, two)
    since = []
    if not described and before != after:
        low, high = sorted((before, after))
        between = store.history(ident, before=high + 1, limit=min(41, high - low + 1))
        between = [p for p in between if low <= p['revision'] <= high]
        pages.seed(between)
        for previous, current in zip(between, between[1:]):
            summary = change(previous, current)['summary']
            if summary not in since:
                since.append(summary)
    try:
        listed = Engine(store).deliveries(ident)
    except (ValueError, OSError):
        listed = []
    def rendered(project):
        found = next((d for d in listed if d['basis'] == basis(project)
                      and d['scene_digest'] == digest(project['scene'])), None)
        return found['id'] if found else None
    return {'changes': described, 'same': not described, 'since': since,
            'before': {'revision': before, 'page_revision': pages.of(before), 'export': rendered(one)},
            'after': {'revision': after, 'page_revision': pages.of(after), 'export': rendered(two)},
            'advanced': raw}


def restore(store, ident, revision, *, expected_revision, fingerprint=None):
    with store.locked():
        current = store.read(ident)
        store.expect(current, expected_revision)
        previous = version(store, ident, revision, fingerprint)
        restored = deepcopy(previous)
        restored.update(revision=current['revision'] + 1, approval=None, checks=[], attempts=[], exports=[])
        return store.commit_locked(current, restored)
