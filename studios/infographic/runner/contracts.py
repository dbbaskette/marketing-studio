"""Versioned saved records and deterministic revision identities."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import secrets

SCHEMA = 1
PRODUCT = 'Infographic Studio'
MAX_RECORD_BYTES = 2_000_000
MAX_SOURCE_BYTES = 16_000_000
MAX_ASSET_BYTES = 32_000_000
MAX_ASSET_EDGE = 20_000
MAX_ASSET_PIXELS = 40_000_000
# Every page size, in one table: the scene's own units (`width`, `height`, `unit`), the PNG in
# pixels and the PDF page in points (render.dimensions), and how the page names it. Digital
# sizes print at the CSS ratio of 0.75 pt to a pixel. The two landscape sizes are laid out
# across the page (scene.py, visual_scene.py), not as a squeezed portrait stack.
PRESETS = {
    'a4': {'width': 210 * 72 / 25.4, 'height': 297 * 72 / 25.4, 'unit': 'pt',
           'width_px': 2480, 'height_px': 3508, 'width_pt': 210 * 72 / 25.4, 'height_pt': 297 * 72 / 25.4,
           'label': 'A4 portrait', 'detail': '210 × 297 mm'},
    'letter': {'width': 612, 'height': 792, 'unit': 'pt', 'width_px': 2550, 'height_px': 3300,
               'width_pt': 612, 'height_pt': 792, 'label': 'US Letter portrait', 'detail': '8.5 × 11 in'},
    'digital': {'width': 1080, 'height': 1350, 'unit': 'px', 'width_px': 1080, 'height_px': 1350,
                'width_pt': 810, 'height_pt': 1012.5, 'label': 'Digital portrait', 'detail': '1080 × 1350 px'},
    'widescreen': {'width': 1920, 'height': 1080, 'unit': 'px', 'width_px': 1920, 'height_px': 1080,
                   'width_pt': 1440, 'height_pt': 810, 'label': 'Widescreen 16:9', 'detail': '1920 × 1080 px'},
    'social': {'width': 1200, 'height': 628, 'unit': 'px', 'width_px': 1200, 'height_px': 628,
               'width_pt': 900, 'height_pt': 471, 'label': 'Social landscape', 'detail': '1200 × 628 px'},
}


def landscape(preset: str) -> bool:
    """Whether a page size is wider than it is tall."""
    size = PRESETS[preset]
    return size['width'] > size['height']
COLLECTIONS = ('sources', 'facts', 'stories', 'assets', 'image_briefs', 'attempts', 'checks', 'exports')
BASIS_FIELDS = ('brief', 'sources', 'facts', 'stories', 'selected_story', 'brand', 'scene', 'assets')
EDITABLE = ('brief', 'sources', 'facts', 'stories', 'selected_story', 'brand', 'scene',
            'assets', 'image_briefs')
INVALIDATES = {
    'brief': ('stories', 'selected_story', 'scene', 'image_briefs', 'attempts', 'checks'),
    'sources': ('facts', 'stories', 'selected_story', 'scene', 'image_briefs', 'attempts', 'checks'),
    'facts': ('stories', 'selected_story', 'scene', 'image_briefs', 'attempts', 'checks'),
    'stories': ('selected_story', 'scene', 'image_briefs', 'attempts', 'checks'),
    'selected_story': ('scene', 'image_briefs', 'attempts', 'checks'),
    'brand': ('scene', 'image_briefs', 'attempts', 'checks'),
    'scene': ('image_briefs', 'attempts', 'checks'),
    'assets': ('image_briefs', 'attempts', 'checks'),
    'image_briefs': ('attempts', 'checks'),
}


# Held work: what a brief or source edit keeps rather than clears (HOLDS), the parts of it the
# page names (STALE_PARTS, with the fields whose change makes a part current again), and which
# parts each edit marks out of date (STALE_BY). Checks are still cleared: they are run again.
HOLDS = {
    'brief': ('stories', 'selected_story', 'scene', 'image_briefs', 'attempts'),
    'sources': ('facts', 'stories', 'selected_story', 'scene', 'image_briefs', 'attempts'),
}
STALE_PARTS = {'facts': ('facts',), 'stories': ('stories', 'selected_story'), 'page': ('scene',),
               'artwork': ('image_briefs', 'assets')}
STALE_BY = {'brief': ('stories', 'page', 'artwork'), 'sources': ('facts', 'stories', 'page', 'artwork')}
STALE_WORDS = {'facts': 'the facts', 'stories': 'the story', 'page': 'the page', 'artwork': 'the artwork'}


class Invalid(ValueError):
    """An invalid or incompatible Infographic Studio record."""


class TooDense(Invalid):
    """The chosen story does not fit one page at readable sizes. `over` is how far, in percent."""

    def __init__(self, message, over=None):
        super().__init__(message)
        self.over = over


def canonical(value) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                          allow_nan=False).encode('utf-8')
    except (ValueError, TypeError, UnicodeError, RecursionError) as failure:
        raise Invalid('Save only finite JSON values.') from failure


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def basis(project: dict) -> dict[str, str]:
    return {key: digest(project[key]) for key in BASIS_FIELDS}


def new_project(owner: str, title: str, *, ident: str | None = None,
                preset: str = 'a4', direction: str = 'suggest') -> dict:
    project = {'schema': SCHEMA, 'product': PRODUCT, 'id': ident or secrets.token_hex(12),
               'owner': owner, 'revision': 0,
               'brief': {'title': title, 'audience': '', 'purpose': '', 'direction': direction,
                         'preset': preset, 'must_show': [], 'locked_words': [], 'exclusions': []},
               'selected_story': None, 'brand': None, 'scene': None, 'approval': None,
               **{key: [] for key in COLLECTIONS}}
    from .validation import validate_project
    validate_project(project)
    return project


def advance(project: dict, changes: dict, *, expected_revision: int, owner: str) -> dict:
    from .validation import validate_project
    validate_project(project)
    if type(expected_revision) is not int or expected_revision != project['revision']:
        raise Invalid('This infographic changed. Reload it before saving.')
    if owner != project['owner']:
        raise Invalid('This infographic belongs to another workspace owner.')
    if not isinstance(changes, dict) or not changes or set(changes) - set(EDITABLE):
        raise Invalid('Change only the supported infographic content fields.')
    changed = {key for key, value in changes.items() if value != project[key]}
    if not changed:
        return deepcopy(project)
    result = deepcopy(project)
    # A brief or source edit holds the work built from the earlier inputs rather than clearing
    # it, and marks it out of date (Training Studio's held materials): the person updates each
    # part or keeps it as it is. A change to the working title alone marks nothing.
    marking = {key for key in changed & set(HOLDS)
               if not (key == 'brief' and renaming(project, changes['brief']))}
    held = {field for key in marking for field in HOLDS[key]} - {
        field for key in changed - marking for field in INVALIDATES.get(key, ())}
    invalidated = {field for key in changed for field in INVALIDATES.get(key, ())}
    for field in invalidated - set(changes) - held:
        result[field] = [] if field in COLLECTIONS else None
    result.update(deepcopy(changes))
    result['revision'] += 1
    result['approval'] = None
    if 'attempts' in held:
        # An image request still running was made for the earlier inputs: it can never land.
        result['attempts'] = [a for a in result['attempts'] if a['state'] not in ('queued', 'running')]
    stale = dict(project.get('stale') or {})
    for part, fields in STALE_PARTS.items():
        # A part made again is current; a part that no longer exists is not out of date.
        if part in stale and (any(key in changed for key in fields) or not _holds(result, part)):
            del stale[part]
    because = ' and '.join(key for key in ('brief', 'sources') if key in marking)
    for key in marking:
        for part in STALE_BY[key]:
            if _holds(result, part):
                earlier = stale.get(part, {}).get('because', because)
                both = earlier if earlier == because else 'brief and sources'
                stale[part] = {'because': both, 'revision': result['revision']}
    _set_stale(result, stale)
    # Old exports are immutable references to older revisions, never current approval.
    try:
        validate_project(result)
    except Invalid:
        if not held:
            raise
        # Held work that no longer fits the new inputs (a fact citing a replaced source) is
        # cleared as before, from the page down, until the record is whole again.
        for fields in (('scene', 'image_briefs', 'attempts'), ('stories', 'selected_story'), ('facts',)):
            for field in set(fields) & held:
                result[field] = [] if field in COLLECTIONS else None
            _set_stale(result, {part: value for part, value in stale.items() if _holds(result, part)})
            try:
                validate_project(result)
                break
            except Invalid:
                continue
        else:
            raise
    return result


def _holds(project: dict, part: str) -> bool:
    """Whether a part of the work exists to be out of date."""
    if part == 'facts':
        return bool(project['facts'])
    if part == 'stories':
        return bool(project['stories'])
    if part == 'page':
        return project['scene'] is not None
    return bool(project['image_briefs']) or any(
        e.get('kind') == 'artwork' for e in (project['scene'] or {}).get('elements', []))


def _set_stale(project: dict, stale: dict):
    if stale:
        project['stale'] = stale
    else:
        project.pop('stale', None)


def stale_parts(project: dict) -> dict:
    """The parts of an infographic held out of date after a brief or source change."""
    return dict(project.get('stale') or {})


def require_current(project: dict, doing: str):
    """Refuse approval, export or delivery while work it depends on is out of date."""
    held = stale_parts(project)
    if held:
        named = [STALE_WORDS[part] for part in STALE_PARTS if part in held]
        listed = named[0] if len(named) == 1 else ', '.join(named[:-1]) + ' and ' + named[-1]
        because = {held[p]['because'] for p in held}
        earlier = 'the brief and sources' if len(because) > 1 or 'brief and sources' in because else 'the ' + because.pop()
        raise Invalid(f'{doing} waits for out-of-date work: {listed} {"was" if len(named) == 1 else "were"} '
                      f'made before {earlier} changed. Update each, or keep it as it is, first.')


def renaming(project: dict, brief) -> bool:
    """True when a sent brief differs from the saved one in its working title alone."""
    if not isinstance(brief, dict) or brief == project['brief'] or 'title' not in brief:
        return False
    rest = lambda value: {key: item for key, item in value.items() if key != 'title'}
    return rest(brief) == rest(project['brief'])


def renamed(project: dict, title: str, review: dict | None = None, *, sequence: int = 0):
    """A rename as the next revision. Only the working title changes, so nothing is cleared:
    the page's pixels and checks are unchanged, and the checks, the latest visual review and
    the approval move to the renamed revision. Each records `carried`, naming the revision
    before the first rename (for the approval, the revision the person approved).
    Returns (renamed project, carried review or None). The approved files of the earlier
    revision stay as they are; files with the new title are prepared again on request."""
    from .validation import validate_project
    validate_project(project)
    result = deepcopy(project)
    result['brief']['title'] = title
    result['revision'] += 1
    before, after = basis(project), basis(result)
    moved = {'from_revision': project['revision'], 'reason': 'rename'}
    carried = None
    if review is not None and review.get('basis') == before:
        carried = {**deepcopy(review), 'basis': after, 'carried': review.get('carried') or moved,
                   'sequence': max(sequence, review.get('sequence', 0)) + 1}
    for check in result['checks']:
        if check['basis'] == before:
            check.update(basis=after, carried=check.get('carried') or moved)
            if carried is not None and check.get('review_digest') == digest(review):
                check['review_digest'] = digest(carried)
    if result['approval'] is not None:
        # The revision the person approved stays named across later renames.
        result['approval'].update(revision=result['revision'], basis=after,
                                  carried=result['approval'].get('carried') or moved)
    validate_project(result)
    return result, carried


def can_land(project: dict, *, attempt_id: str, expected_revision: int,
             input_basis: dict[str, str], owner: str) -> bool:
    """A cancelled, outdated, or foreign worker result cannot become current work."""
    from .validation import validate_project
    validate_project(project)
    return (type(expected_revision) is int and expected_revision == project['revision']
            and owner == project['owner'] and input_basis == basis(project)
            and any(attempt['id'] == attempt_id and attempt['state'] == 'running'
                    and attempt['revision'] == expected_revision and attempt['basis'] == input_basis
                    for attempt in project['attempts']))
