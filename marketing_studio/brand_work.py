"""Working copies: where each is, its record (work.json), starting, discarding, and the
sources a person adds. marketing_studio.brand_store re-exports every name here."""
from __future__ import annotations

import os
import re
import shutil
import threading
import time
from pathlib import Path

from . import state
from .errors import WorkspaceError

from .brand_files import fingerprint, library_summary, no_links, put, read_json, tree_files
from .brand_git import Storage
from .brand_terms import (
    FILE_NAME, KINDS, LIBRARIES, LIBRARY_KINDS, SCHEMA, SEALS, SLUG, SOURCE_LIMIT)


def _store():
    """marketing_studio.brand_store, read when called. Callers and tests replace names on it
    (LOCK, git, walk, write_json and others), and a call made here reaches what they put there."""
    from . import brand_store
    return brand_store


# The background task running for a working copy: (its thread, its stop). The task's own
# thread removes its entry once its last lines and how it ended are in work.json, which is
# all the page needs to show the outcome; Discard and a finished Save remove what is left.
TASKS: dict[str, tuple[threading.Thread, threading.Event]] = {}
# A running task's lines, by working copy: {'lines', 'kept' (when work.json was last
# written), 'waiting' (lines not yet in it)}. record() always shows these. A burst of lines
# is written to work.json at most once every LINE_WRITES seconds, and always on a change
# of state and when the task ends, so the last lines are never lost.
LIVE: dict[str, dict] = {}
LINE_WRITES = 0.25
# Working copies being saved. Save takes its working copy's mark under LOCK and holds it
# while Harness Brand checks and seals the pack, without LOCK; another Save, an edit, a new
# task or Discard of that working copy is refused meanwhile. Other brands are not held up.
SAVING: set[str] = set()


def root() -> Path:
    return state.data_root() / 'brand-work'


def key_of(kind, ident) -> str:
    return f'{kind}-{ident}'


def folder_of(key: str) -> Path:
    if not isinstance(key, str) or not re.fullmatch(r'(brand|library)-[a-z0-9][a-z0-9-]{0,62}', key):
        raise WorkspaceError('Choose a brand or icon library from this page.')
    return no_links(root() / key)


def inside(work: dict) -> Path:
    """The brand's or library's folder inside the working copy, as it will be in storage."""
    base = folder_of(work['key']) / 'brands'
    return base / work['id'] if work['kind'] == 'brand' else base / LIBRARIES / work['id']


def target(place: Storage, work: dict) -> Path:
    return no_links(place.folder / work['id'] if work['kind'] == 'brand' else place.folder / LIBRARIES / work['id'])


def _read(key: str) -> dict:
    """The working copy's record with its identity checked, and a running task's newest
    lines, without walking its files. Hold LOCK."""
    work = read_json(folder_of(key) / 'work.json')
    if not isinstance(work, dict) or work.get('schema') != SCHEMA:
        raise WorkspaceError('That working copy is not there any more. Start it again from Brands.')
    if work.get('key') != key or work.get('kind') not in KINDS or not isinstance(work.get('id'), str) or not SLUG.fullmatch(work['id']) or key_of(work['kind'], work['id']) != key:
        raise WorkspaceError('That working copy has an invalid identity. Start it again from Brands.')
    _with_lines(work)
    return work


def _with_lines(work: dict) -> None:
    live, task = LIVE.get(work['key']), work.get('task')
    if live is not None and isinstance(task, dict) and task.get('state') == 'running':
        task['lines'] = list(live['lines'])


def _record(key: str) -> tuple[dict, list[tuple[Path, int]]]:
    """record(), and the walk of the working copy it checked."""
    with _store().LOCK:
        work = _read(key)
        walked = _store().walk(folder_of(key))
        task = work.get('task')
        alive = TASKS.get(key)
        if task and task.get('state') == 'running' and not (alive and alive[0].is_alive()):
            task.update(state='stopped', ended=time.time(),
                        detail='Marketing Studio was closed while this ran, so nothing was kept from it. Run it again.')
            keep(work)
        if alive and not alive[0].is_alive() and not (task and task.get('state') == 'running'):
            TASKS.pop(key, None)
        return work, walked


def record(key: str) -> dict:
    return _record(key)[0]


def keep(work: dict) -> dict:
    with _store().LOCK:
        _with_lines(work)
        _store().write_json(folder_of(work['key']) / 'work.json', work)
        live = LIVE.get(work['key'])
        if live is not None:
            live.update(kept=_store()._clock(), waiting=False)
    return work


def working_copies() -> list[dict]:
    found = []
    folder = root()
    for entry in sorted(folder.iterdir()) if folder.is_dir() else ():
        key = entry.name
        try:
            if key in SAVING:
                # Harness Brand may be writing it: shown as it was last recorded, unwalked.
                with _store().LOCK:
                    work = _read(key)
            else:
                try:
                    work = record(key)
                except OSError:
                    with _store().LOCK:      # it changed while it was walked: as last recorded
                        work = _read(key)
        except (WorkspaceError, OSError):
            continue
        found.append({'key': work['key'], 'kind': work['kind'], 'id': work['id'],
                      'name': work['name'], 'update': work['update'],
                      'task': (work.get('task') or {}).get('state'), 'saving': key in SAVING})
    return found


def check_name(name) -> str:
    if not isinstance(name, str) or not name.strip() or len(name) > 80 \
            or any(ord(c) < 32 for c in name):
        raise WorkspaceError('Give a name of at most 80 characters, such as Tanzu Division.')
    return name.strip()


def start(place: Storage, kind, ident, name=None, library_kind=None, update=False) -> dict:
    """A working copy for a new brand or library, or for updating one in storage."""
    if kind not in KINDS:
        raise WorkspaceError('Choose a brand or an icon library.')
    if not isinstance(ident, str) or not SLUG.match(ident) or ident == LIBRARIES:
        raise WorkspaceError('Give an id of lower-case letters, digits and hyphens, such as '
                             'tanzu, starting with a letter or digit.')
    key = key_of(kind, ident)
    with _store().LOCK:
        if (folder_of(key) / 'work.json').exists():
            raise WorkspaceError(f'{ident} already has a working copy here. Continue it, or '
                                 'discard it first.')
        work = {'schema': SCHEMA, 'key': key, 'kind': kind, 'id': ident, 'update': bool(update),
                'storage': str(place.folder), 'made': time.time(), 'task': None,
                'extracted': None, 'parts': {}, 'notes': [], 'clashes': [], 'checked': None}
        stored = target(place, work)
        here = inside(work)
        if update:
            marker = stored / ('pack/brand.json' if kind == 'brand' else 'library.zip')
            if not marker.is_file():
                raise WorkspaceError(f'There is no {ident} {"brand pack" if kind == "brand" else "icon library"} '
                                     'in storage to update.')
            if kind == 'brand':
                work['name'] = str((read_json(marker, {}) or {}).get('name') or ident)
            else:
                summary = library_summary(marker)
                work['name'], work['libraryKind'] = summary['name'], summary['kind'] or 'glyph'
        else:
            if stored.exists() and any(stored.iterdir()):
                raise WorkspaceError(f'{ident} is already in storage. Update it instead.')
            work['name'] = check_name(name)
            if kind == 'library':
                if library_kind not in LIBRARY_KINDS:
                    raise WorkspaceError('Choose the library\'s kind: glyph (one-colour shapes the brand '
                                         'colours) or picture (artwork kept in its own colours).')
                work['libraryKind'] = library_kind
        work['base'] = fingerprint(stored)
        base = folder_of(key)
        try:
            if update:
                shutil.copytree(stored, here, ignore=shutil.ignore_patterns('.DS_Store'))
                if kind == 'brand':
                    shutil.copytree(stored / 'pack', base / 'current')
                    # The old seal is made again at Save; it would only fail the checks.
                    brand = read_json(here / 'pack/brand.json', {})
                    if isinstance(brand, dict) and any(field in brand for field in SEALS):
                        _store().write_json(here / 'pack/brand.json',
                                   {k: v for k, v in brand.items() if k not in SEALS})
            (here / 'sources').mkdir(parents=True, exist_ok=True)
            if kind == 'brand':
                (here / 'pack').mkdir(parents=True, exist_ok=True)
                shelf = place.folder / LIBRARIES
                for library in sorted(shelf.iterdir()) if shelf.is_dir() else ():
                    tree_files(library)
                    if (library / 'library.zip').is_file():
                        (base / 'brands' / LIBRARIES / library.name).mkdir(parents=True, exist_ok=True)
                        shutil.copy2(library / 'library.zip',
                                     base / 'brands' / LIBRARIES / library.name / 'library.zip')
            keep(work)
        except BaseException:
            shutil.rmtree(base, ignore_errors=True)
            raise
    return work


def discard(key: str) -> None:
    with _store().LOCK:
        running = TASKS.get(key)
        if running and running[0].is_alive():
            raise WorkspaceError('Stop what is running first, then discard the working copy.')
        if key in SAVING:
            raise WorkspaceError('This working copy is being saved. Wait for the save to finish.')
        shutil.rmtree(folder_of(key), ignore_errors=True)
        TASKS.pop(key, None)
        LIVE.pop(key, None)



def source_name(name) -> str:
    if not isinstance(name, str) or not FILE_NAME.match(name) or name.startswith('.') \
            or name.strip() != name or name in ('.', '..'):
        raise WorkspaceError('Give the file a plain name that does not start with a dot.')
    return name


def idle(key: str) -> None:
    running = TASKS.get(key)
    if running and running[0].is_alive():
        raise WorkspaceError('Wait for what is running to finish, or stop it, first.')
    if key in SAVING:
        raise WorkspaceError('This working copy is being saved. Wait for the save to finish.')


def add_source(key: str, name, data: bytes) -> dict:
    """Copy one file into the working copy's sources. A taken name waits for the person."""
    with _store().LOCK:
        work = record(key)
        idle(key)
        name = source_name(name)
        if len(data) > SOURCE_LIMIT:
            raise WorkspaceError(f'{name} is larger than {SOURCE_LIMIT // 1_000_000} MB.')
        if work['kind'] == 'library' and not name.lower().endswith(('.svg', '.json', '.zip')):
            raise WorkspaceError(f'{name} is not an icon source. Add SVG files, an icons.json, '
                                 'or a ZIP archive of them.')
        sources = inside(work) / 'sources'
        if (sources / name).exists():
            put(folder_of(key) / 'incoming' / name, data)
            if name not in work['clashes']:
                work['clashes'].append(name)
            keep(work)
            return {'clash': name}
        put(sources / name, data)
        return {'added': name}


def free_name(folder: Path, name: str) -> str:
    stem, dot, ending = name.rpartition('.') if '.' in name.strip('.') else (name, '', '')
    for number in range(2, 1000):
        candidate = f'{stem} ({number}){dot}{ending}'
        if not (folder / candidate).exists():
            return candidate
    raise WorkspaceError(f'There are too many sources named like {name}.')


def keep_source(key: str, name, which) -> dict:
    """Settle a taken name: keep the one there, the new one, or both (the new one renamed)."""
    with _store().LOCK:
        work = record(key)
        idle(key)
        if name not in work['clashes'] or which not in ('there', 'new', 'both'):
            raise WorkspaceError('Choose which file to keep from this page.')
        incoming = folder_of(key) / 'incoming' / name
        sources = inside(work) / 'sources'
        kept = name
        if which == 'new':
            os.replace(incoming, sources / name)
        elif which == 'both':
            kept = free_name(sources, name)
            os.replace(incoming, sources / kept)
        else:
            incoming.unlink(missing_ok=True)
        work['clashes'].remove(name)
        keep(work)
        return {'kept': kept, 'which': which}
