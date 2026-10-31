"""A project's context from the Document Library, and the library's page routes.

What a caller needs to know
---------------------------
    context.ROUTES                         # the POST routes every studio page answers alike
    context.answer(path, sent, studio)     # one of them: browse, preview, filters, matching
    context.pin(documents, root, picks)    # pin [{'id', 'revision'}] into an item's documents
    context.update(documents, root, ident) # take a document's newest revision, explicitly
    context.marked(entries)                # each pinned entry with its library head

- `documents` is a studio's supplied-documents module (`shared_runner.documents`): the
  pinned text and file become ordinary documents of the item, read by the studio's own
  workers within its own limits and permissions. Nothing here starts research, grants web
  access, sends text anywhere or selects anything the person did not choose.
- Every chosen revision is checked (it exists, is readable and matches its hashes) before
  the item changes; one refusal changes nothing.
- A remembered filter is only a filter: no route here turns one into a selection.
"""
from __future__ import annotations

from .store import KINDS, LIMITS, ORIGINS, STATES, STUDIOS, LibraryError, gone, location, opened

ROUTES = ('/api/library', '/api/library-document', '/api/library-filters',
          '/api/library-matching')
FILTERS = ('query', 'kind', 'studio', 'origin', 'author', 'state')
NOT_MADE = ('The Document Library has nothing in it yet. Add documents from Marketing '
            'Studio’s Library, or finish a blog or deliver a deck, then try again.')


def _filters(sent) -> dict:
    found = sent.get('filters', {}) if isinstance(sent, dict) else None
    if not isinstance(found, dict) or set(found) - set(FILTERS) \
            or any(value is not None and not isinstance(value, str) for value in found.values()):
        raise LibraryError('Choose the filters this page offers.')
    return {key: value or None for key, value in found.items()}


def _labels() -> dict:
    return {'kinds': KINDS, 'studios': STUDIOS, 'origins': ORIGINS, 'states': STATES,
            'limits': {'page': LIMITS['page'], 'matching': LIMITS['matching'],
                       'bytes': LIMITS['bytes']}}


def answer(path: str, sent: dict, studio: str) -> dict:
    """Answer one library route for a studio's page. Raises LibraryError with a sentence."""
    if studio not in STUDIOS:
        raise LibraryError('Name a studio.')
    library = opened()
    if path == '/api/library':
        filters = _filters(sent)
        offset, limit = sent.get('offset', 0), sent.get('limit', 25)
        where = location()
        if library is None:
            return {'available': False, 'items': [], 'total': 0, 'offset': 0,
                    'limit': limit, 'remembered': {}, 'location': where['shown'],
                    'problem': gone(where['shown']) if where['missing'] else None, **_labels()}
        found = library.catalog(offset=offset, limit=limit, **filters)
        return {'available': True, **found, 'remembered': library.filters(studio),
                'location': where['shown'], **_labels()}
    if library is None:
        raise LibraryError(NOT_MADE)
    if path == '/api/library-document':
        revision = sent.get('revision')
        return library.preview(sent.get('id'), revision if revision is not None else None)
    if path == '/api/library-filters':
        remembered = sent.get('filters')
        if not isinstance(remembered, dict):
            raise LibraryError('Choose the filters this page offers.')
        return {'remembered': library.remember(studio, remembered)}
    if path == '/api/library-matching':
        return {'matching': library.matching(**_filters(sent))}
    raise LibraryError('That is not a library route.')


def _picks(picks) -> list[dict]:
    if not isinstance(picks, list) or not picks or len(picks) > LIMITS['matching']:
        raise LibraryError(f"Choose between 1 and {LIMITS['matching']} documents.")
    seen, clean = set(), []
    for pick in picks:
        if not isinstance(pick, dict) or set(pick) != {'id', 'revision'} \
                or not isinstance(pick['id'], str) or type(pick['revision']) is not int:
            raise LibraryError('Choose each document by its library ID and revision.')
        if pick['id'] in seen:
            raise LibraryError('Choose each document once.')
        seen.add(pick['id'])
        clean.append(pick)
    return clean


def pin(documents, root, picks) -> list[dict]:
    """Pin the chosen revisions as the item's documents, all or none."""
    picks = _picks(picks)
    library = opened()
    if library is None:
        raise LibraryError(NOT_MADE)
    snapshots = [library.snapshot(pick['id'], pick['revision']) for pick in picks]
    return documents.add_snapshots(root, snapshots)


def update(documents, root, ident) -> dict:
    """Take the newest revision of one pinned document, when the person asks for it."""
    entry = next((one for one in documents.listed(root)
                  if (one.get('library') or {}).get('id') == ident), None)
    if entry is None:
        raise LibraryError('That library document is not in this project.')
    library = opened()
    head = library.heads([ident]).get(ident) if library else None
    if head is None:
        raise LibraryError('That document is no longer in the Document Library. The '
                           'project keeps the revision it pinned.')
    if head <= entry['library']['revision']:
        raise LibraryError('This project already uses the newest revision.')
    return documents.replace_snapshot(root, library.snapshot(ident, head))


def marked(entries: list[dict]) -> list[dict]:
    """Each entry, and for one pinned from the library: `library_head`, its newest revision
    there (None when it is gone), and `update`, True when a newer one is available. The
    project's own copy is what is read either way."""
    pinned = [entry['library']['id'] for entry in entries if entry.get('library')]
    if not pinned:
        return entries
    try:
        library = opened()
        heads = library.heads(pinned) if library else {}
    except (LibraryError, OSError):
        heads = {}
    shown = []
    for entry in entries:
        if entry.get('library'):
            head = heads.get(entry['library']['id'])
            entry = {**entry, 'library_head': head,
                     'update': bool(head and head > entry['library']['revision'])}
        shown.append(entry)
    return shown
