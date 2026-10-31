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
PRESETS = {
    'a4': {'width': 210 * 72 / 25.4, 'height': 297 * 72 / 25.4, 'unit': 'pt',
           'width_px': 2480, 'height_px': 3508},
    'letter': {'width': 612, 'height': 792, 'unit': 'pt', 'width_px': 2550, 'height_px': 3300},
    'digital': {'width': 1080, 'height': 1350, 'unit': 'px', 'width_px': 1080, 'height_px': 1350},
}
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


class Invalid(ValueError):
    """An invalid or incompatible Infographic Studio record."""


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
    invalidated = {field for key in changed for field in INVALIDATES.get(key, ())}
    for field in invalidated - set(changes):
        result[field] = [] if field in COLLECTIONS else None
    result.update(deepcopy(changes))
    result['revision'] += 1
    result['approval'] = None
    # Old exports are immutable references to older revisions, never current approval.
    validate_project(result)
    return result


def renaming(project: dict, brief) -> bool:
    """True when a sent brief differs from the saved one in its working title alone."""
    if not isinstance(brief, dict) or brief == project['brief'] or 'title' not in brief:
        return False
    rest = lambda value: {key: item for key, item in value.items() if key != 'title'}
    return rest(brief) == rest(project['brief'])


def renamed(project: dict, title: str, review: dict | None = None, *, sequence: int = 0):
    """A rename as the next revision. Only the working title changes, so nothing is cleared:
    the page's pixels and checks are unchanged, and the checks, the latest visual review and
    the approval move to the renamed revision, each marked with the revision the person
    reviewed or approved.
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
            check['basis'] = after
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
