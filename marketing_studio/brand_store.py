"""Brand packs and icon libraries in the studios' storage, and the working copies that make them.

What a caller needs to know
---------------------------
    place = brand_store.storage(shared, checkouts)    # where the brands folder is
    brand_store.listing(found, place)                 # packs, libraries, working copies
    work = brand_store.start(place, 'brand', 'tanzu', 'Tanzu Division', update=True)
    brand_store.add_source(work, 'template.pptx', data)   # or {'clash': name}
    brand_store.keep_source(work, name, 'there' | 'new' | 'both')
    brand_store.begin(work, 'extract', lambda line, stop: brand_store.extract(...))
    brand_store.view(work)                            # what the page shows
    brand_store.edit(work, 'guide', text); brand_store.accept(work, 'guide')
    saved = brand_store.save(found, place, work)      # check, seal, copy, commit
    brand_store.push(place)                           # only on the person's yes
    brand_store.discard(work)
    brand_store.documents(found, place, 'example')    # a brand's Word document templates
    name, media, data = brand_store.document_file(found, place, 'example', 'solution-brief')

- Storage is exactly `brand.brands`, resolved through studio_core.brand_data.place.
  A remote copy must already exist after explicit Get brands. Local Git is initialized
  only by Save. Team storage and studio workspace settings never choose a brands folder.
- A working copy is in Marketing Studio's data folder, `brand-work/<kind>-<id>/`, laid out
  as the brands folder is, so that Harness Brand finds sources and icon libraries beside
  the pack. Sources added go into it, and storage changes only on Save. Its record,
  `work.json`, keeps the fingerprint of what storage held when it was made: Save refuses
  when storage changed since.
- One background task (Extract or the assistant's job) runs at a time per working copy.
  Its lines and how it ended are in the record; a task left running by a Marketing Studio
  that has closed is read as stopped. A task that fails or is stopped writes nothing into
  the pack: its work is written only once it has all succeeded.
- Parts are the pack's judgement files as the page shows them. A part is accepted for the
  content it had when it was accepted; on Update a part the same as the current pack's is
  unchanged. Save refuses while any part waits.
"""
from __future__ import annotations

import hashlib
import os
import threading
import time

from studio_core import brand_data
from studio_core.process_lock import ProcessRLock

# Moved into focused modules beside this one. Every name stays importable from here, and
# moved code reads the names callers and tests replace (LOCK, git, walk, ...) from here
# when it runs.
from .brand_terms import (
    SCHEMA, LIBRARIES, SLUG, VARIANT, FILE_NAME, KINDS, LIBRARY_KINDS, SOURCE_LIMIT, LINES,
    SEALS, JUDGEMENT, PARTS, SEEN, MEDIA, PREVIEW_HELP)
from .brand_files import (
    TREE_LIMIT, FILE_LIMIT, no_links, LINKED, FOLDER, NOFOLLOW, open_folder, walk,
    tree_files, read_json, write_json, put, fingerprint, files_in, checked, library_summary,
    canonical, same, decode)
from .brand_git import (
    _REPOS, _REPOS_GUARD, repo_lock, Storage, git, reason, storage, write_lock, identity,
    _owner, unshared_counts, outgoing_commits, push)
from .brand_work import (
    TASKS, LIVE, LINE_WRITES, SAVING, root, key_of, folder_of, inside, target, _read,
    _with_lines, _record, record, keep, working_copies, check_name, start, discard,
    source_name, idle, add_source, free_name, keep_source)
from .brand_tasks import (
    begin, stop, wait, guess_variant, extract_brand, extract_library)
from .brand_parts import (
    judgement, part_content, digest, parts, apply_part, parse_part, edit, accept, view,
    roles, save_ready, file)
from .brand_documents import (
    DOCUMENT_MEDIA, DOCUMENT_LIMIT, DOCUMENTS_KEPT_FOR, _DOCUMENTS, _words, _documents,
    documents, document_file)
from .brand_save import (
    INITIALIZED, GITATTRIBUTES, save, _save)

LOCK = threading.RLock()        # every record read and write in this process


def _clock() -> float:
    return time.monotonic()


def listing(found, place: Storage) -> dict:
    folder = place.folder
    packs, libraries = [], []
    # Each pack's and library's unshared commits (on this checkout, not on its upstream),
    # counted for all of them at once: the upstream's commit, then one Git log.
    push = outgoing_commits(place) if place.team else None
    unshared = unshared_counts(place) if place.team else {}
    if folder.is_dir():
        for entry in sorted(folder.iterdir()):
            no_links(entry)
            pack = entry / 'pack'
            if entry.name == LIBRARIES or entry.name.startswith('.') or not (pack / 'brand.json').is_file():
                continue
            brand = read_json(pack / 'brand.json', {}) or {}
            variants = brand.get('variants') if isinstance(brand.get('variants'), dict) else {}
            packs.append({
                'id': entry.name, 'name': str(brand.get('name') or entry.name),
                'variants': list(variants),
                'slides': any(isinstance(v, dict) and v.get('slides') for v in variants.values()),
                'libraries': [str(each.get('library')) for each in brand.get('icons') or []
                              if isinstance(each, dict)],
                'check': {'ok': None, 'problems': []}, 'unshared': unshared.get(entry.name, 0)})
        shelf = folder / LIBRARIES
        for entry in sorted(shelf.iterdir()) if shelf.is_dir() else ():
            if entry.name.startswith('.') or not (entry / 'library.zip').is_file():
                continue
            libraries.append({'id': entry.name, **library_summary(entry / 'library.zip'),
                              'usedBy': [pack['name'] for pack in packs if entry.name in pack['libraries']],
                              'check': {'ok': None, 'problems': []},
                              'unshared': unshared.get(f'{LIBRARIES}/{entry.name}', 0)})
    return {'packs': packs, 'libraries': libraries, 'work': working_copies(),
            'where': place.where, 'team': place.team, 'push': push, 'skill': {'name': found.name, 'version': found.version}}
