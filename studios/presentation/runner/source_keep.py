"""Keep in library for a file the start's source editor takes (ui-kit/research.js).

What a caller needs to know
---------------------------
    source_keep.research_sources(store, sent)   # the editor's request, answered

- `store` is the workspace's shared source drafts (studio_core.research_sources.Sources).
  A request without `keep` is the store's own. `keep` comes only with a file capture: with
  True (Keep in library, the editor's default) the file is also kept in the Document
  Library on this computer once the draft accepted it as readable; with False (Only this
  project) nothing more happens. `library-keep` tries again for one source.
- The answer then carries `library_kept`: {'state': 'kept', 'id', 'revision', 'source'} or
  {'state': 'failed', 'problem', 'source'}. The draft keeps the source whatever the library
  does, and nothing is shared with anyone either way.
- The library document is the one Keep in library on the desk makes of the same file
  (desk_actions.library_upload): keeping it at the start and again on the desk adds no
  second document.
"""
from __future__ import annotations

import hashlib

import runner  # noqa: F401  puts the core on the import path
from runner.desk_actions import library_upload
from studio_core import research_contract as rc
from studio_core.document_library import LibraryError

READABLE_ONLY = 'Only a readable uploaded file is kept in the library.'
CHANGED = 'This file changed after it was read. Add it again.'
NOT_KEPT = 'The library could not keep it.'


def _kept(store, ident, source) -> dict:
    """Keep one file the draft holds: its bytes as the draft holds them, checked against
    their hash. Never raises."""
    try:
        with store.lock:
            value = store.load(ident)
            found = next((one for one in value['sources'] if one.get('id') == source), None)
            if found is None or found.get('kind') != 'file' or found.get('status') != 'ready':
                raise LibraryError(READABLE_ONLY)
            data = rc.inside(store.folder(ident), found['original']).read_bytes()
            if hashlib.sha256(data).hexdigest() != found.get('original_sha256'):
                raise LibraryError(CHANGED)
        row = library_upload(found['name'], data)
        return {'state': 'kept', 'id': row['id'], 'revision': row['revision'], 'source': source}
    except (LibraryError, ValueError, OSError, KeyError) as failure:
        return {'state': 'failed', 'problem': str(failure)[:300] or NOT_KEPT, 'source': source}


def research_sources(store, sent) -> dict:
    """The shared source editor's request, with Keep in library for an uploaded file."""
    if not isinstance(sent, dict):
        return store.dispatch(sent)
    sent = dict(sent)
    if sent.get('action') == 'library-keep':
        if set(sent) - {'action', 'id', 'expected', 'source'}:
            raise ValueError('Choose one source to keep in the library.')
        return {**store.read(sent.get('id')),
                'library_kept': _kept(store, sent.get('id'), sent.get('source'))}
    if 'keep' not in sent:
        return store.dispatch(sent)
    keep = sent.pop('keep')
    if type(keep) is not bool or sent.get('action') != 'capture' or sent.get('kind') != 'file':
        raise ValueError('Say whether to keep an uploaded file in the library.')
    before = {one['id'] for one in store.read(sent.get('id'))['sources']}
    answer = store.dispatch(sent)
    added = next((one for one in answer['sources'] if one['id'] not in before), None)
    if not keep or added is None or added.get('status') != 'ready':
        return answer       # Only this project, or not readable: nothing is kept
    return {**answer, 'library_kept': _kept(store, answer['id'], added['id'])}
