"""A brand's Word document templates, as Harness Brand lists them, and each template
file. marketing_studio.brand_store re-exports every name here."""
from __future__ import annotations

from pathlib import Path

from . import brand_skill
from .errors import WorkspaceError

from .brand_files import no_links
from .brand_git import Storage
from .brand_terms import SLUG


def _store():
    """marketing_studio.brand_store, read when called. Callers and tests replace names on it
    (LOCK, git, walk, write_json and others), and a call made here reaches what they put there."""
    from . import brand_store
    return brand_store


# A brand's Word document templates, as Harness Brand's `documents --brand B --json` lists
# them, asked for only when the person opens them on a brand's row. A listing is used again
# for DOCUMENTS_KEPT_FOR seconds while the same skill, brands folder and brand.json stand.
# A template is downloaded by its id in that listing, and only when the file the listing
# names is a Word template inside that brand's pack folder: nothing else is ever served.

DOCUMENT_MEDIA = {'.dotx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.template',
                  '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}
DOCUMENT_LIMIT = 50_000_000
DOCUMENTS_KEPT_FOR = 15
_DOCUMENTS: dict = {}           # (skill, brands folder, brand, brand.json's mark) -> (when, listing)


def _words(value, limit=2000) -> str | None:
    if isinstance(value, list):
        value = ' '.join(str(each) for each in value if isinstance(each, (str, int, float)))
    return ' '.join(value.split())[:limit] if isinstance(value, str) and value.strip() else None


def _documents(found, place: Storage, brand) -> tuple[list[dict], int]:
    """(the templates Harness Brand listed and described, how many it listed undescribed)."""
    if not isinstance(brand, str) or not SLUG.fullmatch(brand):
        raise WorkspaceError('Choose a brand from this page.')
    pack = no_links(place.folder / brand / 'pack')
    try:
        mark = (pack / 'brand.json').stat().st_mtime_ns
    except OSError:
        raise WorkspaceError(f'There is no brand pack {brand} in the brands folder.') from None
    key = (str(found.script), str(place.folder), brand, mark)
    now = _store()._clock()
    with _store().LOCK:
        kept = _DOCUMENTS.get(key)
        if kept is not None and 0 <= now - kept[0] < DOCUMENTS_KEPT_FOR:
            return kept[1]
    _, said = brand_skill.answer(found, ['documents', '--brand', brand, '--json'],
                                 env=brand_skill.environment(place.folder), seconds=brand_skill.ASK_SECONDS)
    listed = said.get('documents') if isinstance(said, dict) else None
    if not isinstance(listed, list):
        raise WorkspaceError(f'{brand_skill.SKILL} did not list the document templates of {brand}.')
    shown, left = [], 0
    for entry in listed[:100]:
        if not isinstance(entry, dict) or not isinstance(entry.get('id'), str) or not SLUG.fullmatch(entry['id']) \
                or not isinstance(entry.get('file'), str) or not isinstance(entry.get('path'), str):
            left += 1      # left out on its own, and counted: the others are still shown
            continue
        shown.append({'id': entry['id'], 'name': _words(entry.get('name'), 200) or entry['id'],
                      'useWhen': _words(entry.get('useWhen')), 'page': _words(entry.get('page'), 80),
                      'notes': _words(entry.get('notes')), 'file': Path(entry['file']).name,
                      'path': entry['path']})
    with _store().LOCK:
        for old in [old for old, (when, _) in _DOCUMENTS.items() if not 0 <= now - when < DOCUMENTS_KEPT_FOR]:
            del _DOCUMENTS[old]
        _DOCUMENTS[key] = (now, (shown, left))
    return shown, left


def documents(found, place: Storage, brand) -> dict:
    """What a brand's row shows: {'brand', 'documents': [{id, name, useWhen, page, notes, file}],
    'left': how many templates Harness Brand listed without describing them, left out}."""
    shown, left = _documents(found, place, brand)
    return {'brand': brand, 'documents': [{k: v for k, v in entry.items() if k != 'path'} for entry in shown],
            'left': left}


def document_file(found, place: Storage, brand, ident) -> tuple[str, str, bytes]:
    """(file name, media type, bytes) of one template the skill listed for this brand."""
    entry = next((each for each in _documents(found, place, brand)[0] if each['id'] == ident), None)
    if entry is None:
        raise WorkspaceError('That is not a document template Harness Brand lists for this brand.')
    pack = (place.folder / brand / 'pack').resolve()
    path = Path(entry['path'])
    try:
        no_links(path)
        where = path.resolve(strict=True)
    except (OSError, RuntimeError):
        raise WorkspaceError(f'{entry["file"]} is not in the brand pack any more.') from None
    if not path.is_absolute() or pack not in where.parents or where.suffix.lower() not in DOCUMENT_MEDIA \
            or not where.is_file():
        raise WorkspaceError(f'{entry["file"]} is not a Word template in the {brand} brand pack, so it is not offered.')
    if where.stat().st_size > DOCUMENT_LIMIT:
        raise WorkspaceError(f'{entry["file"]} is too large to download here. Open it from {where.parent}.')
    return where.name, DOCUMENT_MEDIA[where.suffix.lower()], where.read_bytes()
