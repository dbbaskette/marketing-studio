"""The Document Library's records: readable folders, immutable revisions, one lock.

Where it is
-----------
`library.root` in the studios config names the folder. Until a first explicit use (an
upload, or finished work kept), it is `library/` under the shared local work folder
(normally `~/Studios/library`) and nothing is written. The first explicit use saves the
resolved folder into the studios config, under its adjacent lock and with every unrelated
value kept, so a later change to the work folder never moves the library. Opening or
browsing never creates it, and never sets up any studio's workspace.

Layout
------
    <library>/library.json                      # marks the folder as a library
    <library>/.library.lock                     # every write holds it, in every process
    <library>/documents/<id>/document.json      # the document's own record: hidden or not
    <library>/documents/<id>/revisions/<n>/     # one immutable revision
        revision.json                           # written last: what the revision is
        content.md                              # readable Markdown, when there is any
        original<ending>                        # an upload's bytes, as they were sent
                                                # (`original` alone for an ending that is not
                                                # plain letters and digits, or none)
        content.pdf                             # finished work's PDF, once it is saved
                                                # (research: content.md is its report and
                                                # original.zip its whole bundle; research.py)
    <library>/.state/catalog.json               # a search index, rebuilt from records
    <library>/.state/filters.json               # each studio's browsing filters

A revision is made in a hidden folder beside the others and renamed into place whole, so
an interrupted write leaves no half-made revision: the newest complete revision is the
document's head. A document's ID never changes. Finished work is found again by its key
(`<studio>:<project>`), so a repeated Finish or Deliver reuses its document and adds a
revision only when what it keeps changed. An upload's operation ID makes a retry return
what the first attempt kept, and the same file uploaded again (its name, bytes, title and
studio) is the document already kept. Every file is checked against its recorded hash before
it is previewed, downloaded or pinned; a link, a missing file or a changed file is refused.

Remove from library hides a document: `document.json` says so, written atomically under the
lock. A hidden document is left out of the catalog, Select all matching, Update available
and new pins; nothing of it is deleted, a project that pinned it keeps its own copy, and
Restore shows it again. Uploading the same file again restores it too.

An upload of any type is kept: its bytes always, and readable Markdown when its type has
a reader here (READERS) and its text could be read. A file with no reader (a picture, an
archive, an older Office file, anything else) is kept whole with the state `kept`: it is
listed, previewed by name, type and size, downloaded and removed like any other, and never
offered as a source, since it has no text. Nothing in a kept file is opened, run, rendered
or followed, and an original leaves the library only as a download: a known type under its
own media type, any other as `application/octet-stream`.

Verified Harness Research is one more kind, `research`, with one more key form
(`<studio>:<project>:research`) and one more record field (`research`); records written
before read exactly as they did, and nothing is migrated.

The record format is schema 1 throughout. What any type added is one more conversion
state (`kept`), `application/octet-stream` as an original's media type and `original` as
a kept file's name; a record written before reads as it always did, and a reader from
before takes a state it does not know for `unreadable`.

A document's text is never trusted: it is shown as text, never as markup, and is never
sent anywhere by the library. Nothing here uses the network, starts an assistant, runs
OCR or a model, installs a reader, or shares anything with a team.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import secrets
import shutil
import threading
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from studio_core import source_documents, studios_config
from studio_core.process_lock import ProcessRLock


class LibraryError(ValueError):
    """A refusal, in a sentence a person can act on."""


class _NoReader(Exception):
    """An upload of a type the library keeps and does not read."""


SCHEMA = 1
PRODUCT = 'Studios Document Library'
KINDS = {'upload': 'Uploaded document', 'blog': 'Blog', 'presentation': 'Presentation',
         'training': 'Training material', 'infographic': 'Infographic',
         'research': 'Research'}
ORIGINS = {'upload': 'Upload', 'created': 'Created here', 'link': 'Link',
           'google': 'Google document', 'imported': 'Imported'}
STUDIOS = {'marketing': 'Marketing Studio', 'blog': 'Blog Studio',
           'presentation': 'Presentation Studio', 'training': 'Training Studio',
           'infographic': 'Infographic Studio'}
FORMATS = {'markdown': 'Markdown', 'original': 'Original', 'pdf': 'PDF'}
STATES = {'readable': 'Readable', 'needs-text': 'Needs text', 'unreadable': 'Cannot be read',
          'kept': 'Kept as a file', 'missing': 'Files missing'}
# The types whose text is read, by ending: every other file is kept as the file it is.
READERS = {'.txt': 'text', '.md': 'text', '.markdown': 'text', '.html': 'html', '.htm': 'html',
           '.docx': 'docx', '.pdf': 'pdf', '.pptx': 'pptx', '.xlsx': 'xlsx'}
MEDIA = {'.txt': 'text/plain', '.md': 'text/markdown', '.markdown': 'text/markdown',
         '.html': 'text/html', '.htm': 'text/html', '.pdf': 'application/pdf',
         '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
         '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
         '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
UNKNOWN_MEDIA = 'application/octet-stream'     # a file of any other type: only ever a download
TYPES = {'.txt': 'Text', '.md': 'Markdown', '.markdown': 'Markdown', '.html': 'HTML', '.htm': 'HTML',
         '.docx': 'Word', '.pdf': 'PDF', '.pptx': 'PowerPoint', '.xlsx': 'Excel'}
ENDING = re.compile(r'^\.[a-z0-9]{1,16}$')    # an ending a kept file's own name may carry
INDEX = 2                   # the search index's own format: rows say a file's type and size
LIMITS = {'bytes': 8_000_000,       # one original, as the studios' supplied documents take
          'text': 8_000_000,        # bytes of one revision's Markdown
          'documents': 5_000,       # documents a catalog reads
          'revisions': 1_000,       # revisions one document keeps
          'page': 50,               # rows one catalog page gives
          'preview': 20_000,        # characters a preview shows
          'matching': 40,           # documents "all matching" may choose at once
          'pdf': 50_000_000,        # bytes of one finished deck's PDF
          'research': 16_000_000}   # bytes of one research bundle, zipped (Harness Research's
                                    # own import limit); every other original keeps 'bytes'
IDENT = re.compile(r'^[a-z0-9][a-z0-9-]{0,63}$')
KEY = re.compile(r'^(blog|presentation|training|infographic):[A-Za-z0-9][A-Za-z0-9._-]{0,159}$')
# Verified research a studio kept (research.py): `<studio>:<project>:research`. Finished work's
# KEY never holds a second colon, so a project's research is never its finished work.
RESEARCH_KEY = re.compile(r'^(blog|presentation|training|infographic):[A-Za-z0-9][A-Za-z0-9._-]{0,159}:research$')
BUNDLE_FILE = 'original.zip'    # a research revision's bundle, as one archive
OPERATION = re.compile(r'^[a-f0-9]{32}$')
RECORD_LIMIT = 256_000      # bytes of one revision.json
EXCERPT = 4_000             # characters of each document's text the search index keeps
NAME = 120                  # characters in an uploaded file's name
TITLE = 200                 # characters in a title
WAIT = 10.0
STALE = 3600                # seconds before a hidden half-made revision is cleared away
KEPT = ('It is kept as the file it is. The library cannot read text from this type of file, so it '
        'cannot be used as a source. To use its words, add a text, Word, PowerPoint, Excel or PDF '
        'version.')
NO_TEXT = ('It has no readable text yet. Upload a text or Word version of it, then choose '
           'that one. Nothing is read from pictures automatically.')
CHANGED = ('Its files in the library changed after they were kept, so it cannot be used. '
           'Upload it again.')
MISSING = 'Its files are missing from the library folder. Upload it again.'
HIDDEN = ('"{title}" was removed from the library, so it cannot be added. Restore it in '
          'Marketing Studio’s Library first.')
# What this process last parsed of each library's .state/catalog.json:
# {library root: ((st_mtime_ns, st_size, st_ino) of the file, what it held)}. It saves only
# the read and parse of an unchanged file. Whatever it holds is still checked against the
# documents' heads read from disk, so a revision another process (a studio) kept is seen at
# once, and a catalog.json another process wrote has another stat and is read again. A write
# this process makes to a library drops its entry.
_CATALOGS: dict = {}
# When this process last cleared away half-made revisions, by library root: at most once
# every STALE seconds, since nothing younger than that is cleared.
_TIDIED: dict = {}
_REMEMBERING = threading.Lock()


def _forget(root: Path) -> None:
    with _REMEMBERING:
        _CATALOGS.pop(str(root), None)


# --- where the library is ------------------------------------------------------------------

def _saved(values) -> str | None:
    held = values.get('library') if isinstance(values, dict) else None
    root = held.get('root') if isinstance(held, dict) else None
    if isinstance(root, str) and root and Path(root).expanduser().is_absolute():
        return root
    return None


def location() -> dict:
    """Where the library is, or would be made: {'root', 'saved', 'shown', 'problem'}.
    Nothing is written."""
    values, problem = studios_config.read()
    named = os.environ.get('STUDIOS_LIBRARY')
    if named and Path(named).expanduser().is_absolute():
        # Named for this process, as STUDIOS_CONFIG names the config: never saved.
        where = Path(named).expanduser()
        return {'root': where, 'saved': True, 'named': True, 'missing': False,
                'shown': studios_config.shown(where), 'problem': problem}
    saved = _saved(values)
    if saved:
        where = Path(saved).expanduser()
    else:
        base = (values.get('local') or {}).get('root') if isinstance(values.get('local'), dict) else None
        if not (isinstance(base, str) and base and Path(base).expanduser().is_absolute()):
            base = '~/Studios'
        where = Path(base).expanduser() / 'library'
    # A saved folder that is gone (a drive not connected, a folder moved) is said, never
    # quietly made again in its place.
    return {'root': where, 'saved': bool(saved), 'named': False,
            'missing': bool(saved) and not where.exists(),
            'shown': studios_config.shown(where), 'problem': problem}


def _marked(root: Path) -> bool:
    marker = root / 'library.json'
    if root.is_symlink() or not root.is_dir() or marker.is_symlink() or not marker.is_file():
        return False
    try:
        found = json.loads(marker.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return False
    return isinstance(found, dict) and found.get('product') == PRODUCT and found.get('schema') == SCHEMA


def opened(create: bool = False) -> 'Library | None':
    """The library. Without `create`, None when its folder has not been made: browsing
    never makes it. With `create` (an explicit use), its location is saved in the studios
    config the first time and its folder is made."""
    found = location()
    root = found['root']
    if not create:
        return Library(root) if _marked(root) else None
    if found['missing']:
        raise LibraryError(gone(found['shown']))
    if not found['saved']:
        if found['problem']:
            raise LibraryError(found['problem'].split(', so ')[0] + ', so the library location '
                               'could not be saved. Nothing was kept.')
        wanted = str(root)

        def changes(current):
            if _saved(current):
                return {}       # another studio saved it first: that one is used
            return {'library': {'root': wanted}}
        try:
            values = studios_config.update(changes)
        except ValueError as failure:
            raise LibraryError(str(failure)) from None
        root = Path(_saved(values) or wanted).expanduser()
    _make(root)
    return Library(root)


def _make(root: Path) -> None:
    if root.is_symlink():
        raise LibraryError(f'{studios_config.shown(root)} is a link. Choose a library '
                           'folder that is a plain folder.')
    if root.exists() and not root.is_dir():
        raise LibraryError(f'{studios_config.shown(root)} is a file, so the library could not '
                           'be made there.')
    if _marked(root):
        return
    if root.is_dir() and any(name for name in os.listdir(root)
                             if name not in ('.library.lock', '.DS_Store')):
        raise LibraryError(f'{studios_config.shown(root)} already holds other files, so the '
                           'library was not made there. Empty it, or choose another folder.')
    try:
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        _atomic(root / 'library.json', json.dumps(
            {'schema': SCHEMA, 'product': PRODUCT}, indent=2).encode() + b'\n')
    except OSError as failure:
        raise LibraryError(f'{studios_config.shown(root)} could not be made '
                           f'({str(failure.strerror or failure).lower()}).') from None


def gone(shown: str) -> str:
    return (f'The Document Library is saved at {shown}, which is not there now. Connect the '
            'drive it is on, or put the folder back; nothing was kept, and a new library was '
            'not made in its place.')


# --- small helpers -------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic(path: Path, data: bytes) -> None:
    pending = path.with_name(f'.{path.name}.pending-{secrets.token_hex(4)}')
    try:
        with open(pending, 'xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(pending, path)
    finally:
        pending.unlink(missing_ok=True)


def _bounded(path: Path, limit: int) -> bytes:
    """A file's bytes, refused when it is a link, not a file, or larger than `limit`."""
    if path.is_symlink() or not path.is_file():
        raise LibraryError(MISSING)
    with open(path, 'rb') as stream:
        size = os.fstat(stream.fileno()).st_size
        if size > limit:
            raise LibraryError(CHANGED)
        data = stream.read(size + 1)
    if len(data) != size:
        raise LibraryError(CHANGED)
    return data


def _json(path: Path, limit: int = RECORD_LIMIT):
    try:
        return json.loads(_bounded(path, limit).decode('utf-8'))
    except (LibraryError, OSError, ValueError):
        return None


def _plain(value, limit: int) -> str | None:
    """Short printable text, or None."""
    if not isinstance(value, str):
        return None
    value = ' '.join(unicodedata.normalize('NFC', value).split())
    if not value or len(value) > limit or not all(c.isprintable() for c in value):
        return None
    return value


def _slug(value: str) -> str:
    plain = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', plain).strip('-')[:40] or 'document'


def _ending(name: str) -> str:
    return Path(name).suffix.lower()


def _kept_name(ending: str) -> str:
    """The name an original is kept under in its revision's folder: never the name it was
    sent with, and its ending only when that is plain letters and digits."""
    return 'original' + (ending if ENDING.match(ending) else '')


def _original_limit(record: dict) -> int:
    """How large a revision's original may be read: a research bundle's own limit, else
    every other original's."""
    return LIMITS['research'] if record.get('kind') == 'research' else max(LIMITS['bytes'], LIMITS['text'])


def file_type(name) -> str:
    """What kind of file a name says it is, for a person: `PDF`, `PowerPoint`, `PNG file`."""
    ending = _ending(name) if isinstance(name, str) else ''
    if ending in TYPES:
        return TYPES[ending]
    return ending[1:].upper() + ' file' if ENDING.match(ending) else 'File'


def _read(data: bytes, kind: str) -> dict:
    """What a type's reader reads of an upload. A PowerPoint file and a spreadsheet are
    read as the source editor reads them (`research_sources.read`)."""
    if kind in ('pptx', 'xlsx'):
        from studio_core import research_sources
        return research_sources.read(data, kind, source_documents.extract)
    return source_documents.extract(data, kind)


def _markdown(found: dict, kind: str) -> str:
    """Readable Markdown from what an extractor read: page headings for a PDF, slide
    headings for a PowerPoint file, a spreadsheet's sheets under their names as they were
    read, paragraphs for the rest. Nothing is added that the document did not say."""
    text = found['text']
    if kind in ('text', 'xlsx'):
        return text
    parts = []
    if kind == 'pptx':
        # A slide's shapes are one passage each: gather them under the slide they are on.
        slides = {}
        for place in found['locations']:
            passage = text[place['start']:place['end']].strip()
            if passage:
                slides.setdefault(place['label'].split(' / ')[0], []).append(passage)
        return '\n\n'.join(f'## {slide}\n\n' + '\n\n'.join(said) for slide, said in slides.items()).strip() + '\n'
    for place in found['locations']:
        passage = text[place['start']:place['end']].strip()
        if not passage:
            continue
        parts.append(f"## {place['label']}\n\n{passage}" if kind == 'pdf' else passage)
    return '\n\n'.join(parts).strip() + '\n'


def _pdf_part(pdf, shown: str, files: dict) -> dict | None:
    """The record of finished work's PDF as `retain` and `adopt` take it, its bytes added to
    `files` as `content.pdf` when it is saved. `pdf` is None, {'state': 'needs-export',
    'reason': str} while no PDF exists, or {'state': 'saved', 'data': bytes}: a PDF the
    studio already exported and checked is of exactly this work, up to LIMITS['pdf'] bytes,
    kept as it is, never made or converted here; the library checks only that it is a PDF."""
    if isinstance(pdf, dict) and pdf.get('state') == 'saved':
        data = pdf.get('data')
        if type(data) is not bytes or not data.startswith(b'%PDF-'):
            raise LibraryError('A PDF is kept only once it has been exported.')
        if len(data) > LIMITS['pdf']:
            raise LibraryError(f'The PDF of "{shown}" is larger than the library keeps.')
        files['content.pdf'] = data
        return {'state': 'saved', 'file': 'content.pdf', 'media': MEDIA['.pdf'],
                'bytes': len(data), 'sha256': _sha(data)}
    if pdf is None or (isinstance(pdf, dict) and pdf.get('state') == 'needs-export'
                       and isinstance(pdf.get('reason'), str)):
        return {'state': 'needs-export', 'reason': pdf['reason'][:300]} if pdf else None
    raise LibraryError('A PDF is kept only once it has been exported.')


# --- the library ---------------------------------------------------------------------------

class Library:
    def __init__(self, root):
        self.root = Path(root)
        self.lock = ProcessRLock(lambda: self.root / '.library.lock', timeout=WAIT,
                                 refusal=LibraryError)

    # where things are
    def _documents(self) -> Path:
        return self.root / 'documents'

    def _state(self) -> Path:
        return self.root / '.state'

    def _folder(self, ident) -> Path:
        if not isinstance(ident, str) or not IDENT.match(ident):
            raise LibraryError('That is not a document in the library.')
        folder = self._documents() / ident
        if folder.is_symlink() or not folder.is_dir():
            raise LibraryError('That document is not in the library.')
        return folder

    # reading revisions
    def _revision(self, folder: Path, number: int) -> dict | None:
        place = folder / 'revisions' / str(number)
        if place.is_symlink() or not place.is_dir():
            return None
        record = _json(place / 'revision.json')
        if not isinstance(record, dict) or record.get('schema') != SCHEMA \
                or record.get('id') != folder.name or record.get('revision') != number \
                or record.get('kind') not in KINDS:
            return None
        return record

    def _numbers(self, folder: Path) -> list[int]:
        revisions = folder / 'revisions'
        if revisions.is_symlink() or not revisions.is_dir():
            return []
        found = []
        with os.scandir(revisions) as entries:
            for entry in entries:
                if entry.name.isdigit() and entry.name == str(int(entry.name)) \
                        and entry.is_dir(follow_symlinks=False):
                    found.append(int(entry.name))
                if len(found) > LIMITS['revisions']:
                    break
        return sorted(found)

    def _head(self, folder: Path) -> dict | None:
        """The newest complete revision. A revision that is not whole is passed over."""
        for number in reversed(self._numbers(folder)):
            record = self._revision(folder, number)
            if record is not None:
                return record
        return None

    def _record(self, ident, revision=None) -> tuple[Path, dict]:
        folder = self._folder(ident)
        if revision is None:
            record = self._head(folder)
        else:
            if type(revision) is not int or revision < 1:
                raise LibraryError('Choose a revision of the document by its number.')
            record = self._revision(folder, revision)
        if record is None:
            raise LibraryError('That revision is not in the library.')
        return folder / 'revisions' / str(record['revision']), record

    def _ids(self):
        documents = self._documents()
        if documents.is_symlink() or not documents.is_dir():
            return []
        found = []
        with os.scandir(documents) as entries:
            for entry in entries:
                if IDENT.match(entry.name) and entry.is_dir(follow_symlinks=False):
                    found.append(entry.name)
                if len(found) >= LIMITS['documents']:
                    break
        return sorted(found)

    @staticmethod
    def _hidden(folder: Path) -> bool:
        """Whether Remove from library hid this document. A damaged record hides nothing."""
        record = folder / 'document.json'
        if not record.is_file():
            return False
        found = _json(record)
        return isinstance(found, dict) and found.get('schema') == SCHEMA \
            and found.get('id') == folder.name and found.get('hidden') is True

    def _whole(self, place: Path, record: dict) -> bool:
        """Whether a revision's kept files are all there and match their hashes."""
        if self._state_of(place, record)[0] == 'missing':
            return False
        try:
            self._checked(place, record.get('markdown'))
            self._checked(place, record.get('original'), _original_limit(record))
        except (LibraryError, OSError):
            return False
        return True

    def _set_hidden(self, folder: Path, hidden: bool) -> None:
        """Write the document's own record whole. Hold the lock."""
        _forget(self.root)
        try:
            _atomic(folder / 'document.json', json.dumps(
                {'schema': SCHEMA, 'id': folder.name, 'hidden': hidden, 'changed_at': _now()},
                indent=2).encode() + b'\n')
        except OSError as failure:
            raise LibraryError(f'The library could not change it ({str(failure.strerror or failure).lower()}). '
                               'Nothing was changed; try again.') from None

    @staticmethod
    def _checked(place: Path, part: dict | None, limit: int | None = None) -> bytes | None:
        """A representation's bytes, refused unless they match the hash it was kept with.
        Only a saved PDF is read up to LIMITS['pdf']; Markdown and originals stay within
        their own limits."""
        if not isinstance(part, dict) or not isinstance(part.get('file'), str):
            return None
        name = part['file']
        if '/' in name or name.startswith('.'):
            raise LibraryError(CHANGED)
        data = _bounded(place / name, limit or max(LIMITS['bytes'], LIMITS['text']))
        if _sha(data) != part.get('sha256'):
            raise LibraryError(CHANGED)
        return data

    # what a person sees of a document
    def _state_of(self, place: Path, record: dict) -> tuple[str, str | None]:
        conversion = record.get('conversion') or {}
        state = conversion.get('state') if conversion.get('state') in STATES else 'unreadable'
        problem = conversion.get('problem') if isinstance(conversion.get('problem'), str) else None
        for part in (record.get('markdown'), record.get('original')):
            if isinstance(part, dict) and isinstance(part.get('file'), str):
                path = place / part['file']
                if path.is_symlink() or not path.is_file():
                    return 'missing', MISSING
        if state == 'kept':
            return state, KEPT
        if state != 'readable':
            return state, problem or NO_TEXT
        return state, None

    def _row(self, place: Path, record: dict, first: str | None = None) -> dict:
        state, problem = self._state_of(place, record)
        original = record.get('original') if isinstance(record.get('original'), dict) else None
        pdf = record.get('pdf') if isinstance(record.get('pdf'), dict) else None
        formats = []
        if isinstance(record.get('markdown'), dict):
            formats.append('markdown')
        if pdf and pdf.get('state') == 'saved':
            formats.append('pdf')
        if original:
            formats.append('original')
        project = record.get('project') if isinstance(record.get('project'), dict) else None
        return {
            'id': record['id'], 'revision': record['revision'],
            'title': record.get('title') or 'Untitled',
            'kind': record['kind'], 'kind_label': KINDS[record['kind']],
            'origin': record.get('origin'), 'origin_label': ORIGINS.get(record.get('origin'), 'Upload'),
            'studio': record.get('studio'), 'studio_label': STUDIOS.get(record.get('studio'), 'Marketing Studio'),
            'author': record.get('author'), 'updated_at': record.get('created_at'),
            'created_at': first or record.get('created_at'),
            'formats': formats, 'format_labels': [FORMATS[name] for name in formats],
            'readable': state == 'readable', 'state': state, 'state_label': STATES[state],
            'problem': problem,
            'gaps': list((record.get('conversion') or {}).get('gaps') or [])[:20],
            'pdf': (pdf or {}).get('state'),
            'pdf_note': (pdf or {}).get('reason') if pdf and pdf.get('state') != 'saved' else None,
            'original_name': (original or {}).get('filename'),
            # What kind of file the original is and how large, so a file kept with no
            # readable text is still told from the others.
            'type': file_type((original or {}).get('filename')) if original else None,
            'bytes': (original or {}).get('bytes') if type((original or {}).get('bytes')) is int else None,
            'project': {'studio': project.get('studio'), 'title': project.get('title'),
                        'revision': project.get('revision')} if project else None,
            'scope': 'local',
        }

    # the search index
    def _index(self) -> list[dict]:
        ids = self._ids()
        heads = []
        for ident in ids:
            folder = self._documents() / ident
            numbers = self._numbers(folder)
            heads.append([ident, numbers[-1] if numbers else 0, self._hidden(folder)])
        cache = self._state() / 'catalog.json'
        # Rows contain bounded display metadata and a case-folded search excerpt.
        # Scale the read budget with the actual catalog; revision files retain their own cap.
        found = self._parsed_catalog(cache, 1024 + len(heads) * 128_000)
        if isinstance(found, dict) and found.get('schema') == SCHEMA and found.get('index') == INDEX \
                and found.get('signature') == heads and isinstance(found.get('entries'), list):
            return found['entries']
        entries = []
        for ident in ids:
            folder = self._documents() / ident
            record = self._head(folder)
            if record is None:
                continue
            place = folder / 'revisions' / str(record['revision'])
            first = self._revision(folder, 1)
            row = self._row(place, record, (first or {}).get('created_at'))
            excerpt = ''
            markdown = record.get('markdown')
            if isinstance(markdown, dict) and isinstance(markdown.get('file'), str) \
                    and '/' not in markdown['file']:
                try:
                    with open(place / markdown['file'], 'rb') as stream:
                        excerpt = stream.read(EXCERPT * 4).decode('utf-8', 'ignore')[:EXCERPT]
                except OSError:
                    excerpt = ''
            row['key'] = record.get('key')
            row['operation'] = record.get('operation')
            row['fingerprint'] = record.get('fingerprint')
            row['adopted'] = bool(record.get('adopted'))
            row['hidden'] = self._hidden(folder)
            row['search'] = ' '.join((row['title'], row.get('author') or '',
                                      row.get('original_name') or '', excerpt)).casefold()
            entries.append(row)
        try:
            self._state().mkdir(exist_ok=True, mode=0o700)
            _atomic(cache, json.dumps({'schema': SCHEMA, 'index': INDEX, 'signature': heads,
                                       'entries': entries}, ensure_ascii=False).encode())
        except OSError:
            pass    # the index is only a convenience: it is rebuilt from the records
        _forget(self.root)
        return entries

    def _parsed_catalog(self, cache: Path, budget: int):
        """catalog.json as parsed, from memory while the file's stat is as it was when this
        process last read it. Its signature is checked by the caller either way."""
        try:
            seen = os.stat(cache, follow_symlinks=False)
        except OSError:
            return None
        key = (seen.st_mtime_ns, seen.st_size, seen.st_ino)
        with _REMEMBERING:
            held = _CATALOGS.get(str(self.root))
        if held is not None and held[0] == key and seen.st_size <= budget:
            return held[1]
        # The stat is taken before the read: a file replaced in between is read again next time.
        found = _json(cache, budget)
        if isinstance(found, dict):
            with _REMEMBERING:
                _CATALOGS[str(self.root)] = (key, found)
        return found

    @staticmethod
    def _public(row: dict) -> dict:
        # A row may be the one this process keeps of catalog.json: nothing inside it leaves.
        return {key: copy.deepcopy(value) for key, value in row.items()
                if key not in ('search', 'key', 'operation', 'fingerprint', 'adopted')}

    def _matches(self, query='', kind=None, studio=None, origin=None, author=None, state=None,
                 hidden=False, rows=None):
        if kind not in (None, '', *KINDS) or studio not in (None, '', *STUDIOS) \
                or origin not in (None, '', *ORIGINS) or state not in (None, '', *STATES):
            raise LibraryError('Choose the filters this page offers.')
        if not isinstance(query or '', str) or len(query or '') > 200 \
                or not isinstance(author or '', str) or len(author or '') > 100:
            raise LibraryError('Search with at most 200 characters.')
        words = (query or '').casefold().split()
        who = (author or '').casefold().strip()
        rows = [row for row in (self._index() if rows is None else rows)
                if (hidden or not row.get('hidden')) and (not kind or row['kind'] == kind) and (not studio or row['studio'] == studio)
                and (not origin or row['origin'] == origin) and (not state or row['state'] == state)
                and (not who or who in (row.get('author') or '').casefold())
                and all(word in row['search'] for word in words)]
        rows.sort(key=lambda row: (row.get('updated_at') or '', row['title'].casefold()), reverse=True)
        return rows

    def catalog(self, query='', kind=None, studio=None, origin=None, author=None, state=None,
                offset=0, limit=25, hidden=False, summary=False) -> dict:
        """One page of documents that match, newest first: {'items', 'total', 'offset',
        'limit'}. Each item is a document's newest revision; no local path is given. A
        hidden document is left out unless `hidden` (Marketing Studio's Show hidden). With
        `summary`, what summary() says is added from the same reading of the index."""
        if type(offset) is not int or offset < 0 or type(limit) is not int \
                or not 1 <= limit <= LIMITS['page']:
            raise LibraryError(f"Ask for at most {LIMITS['page']} documents at a time.")
        every = self._index()
        rows = self._matches(query, kind, studio, origin, author, state, hidden, rows=every)
        return {'items': [self._public(row) for row in rows[offset:offset + limit]],
                'total': len(rows), 'offset': offset, 'limit': limit,
                **(self._summary(every) if summary else {})}

    def matching(self, readable_only=True, **filters) -> list[dict]:
        """Every readable document the filters match, as {'id', 'revision'}: what "Select all
        matching" chooses. A hidden document is never chosen. Refused when more match than
        a project can take at once."""
        rows = [row for row in self._matches(**filters) if row['readable'] or not readable_only]
        if len(rows) > LIMITS['matching']:
            raise LibraryError(f"{len(rows)} documents match. Narrow the filters to at most "
                               f"{LIMITS['matching']} before selecting all of them.")
        return [{'id': row['id'], 'revision': row['revision']} for row in rows]

    def describe(self, ident, revision=None, loaded=None) -> dict:
        """A revision's row with its document's head and revisions. `loaded` is the
        (folder, record) of that revision when the caller has already read it."""
        place, record = loaded if loaded is not None else self._record(ident, revision)
        folder = place.parent.parent
        first = self._revision(folder, 1)
        row = self._row(place, record, (first or {}).get('created_at'))
        head = self._head(folder)
        row['head'] = head['revision'] if head else record['revision']
        row['revisions'] = self._numbers(folder)[-50:]
        row['hidden'] = self._hidden(folder)
        return row

    def hide(self, ident, hidden=True) -> dict:
        """Remove from library (`hidden`) or Restore: the document leaves, or comes back to,
        the catalog and Add from library. No revision or file is deleted or changed, and a
        project that pinned it keeps its own copy. Returns its row."""
        if type(hidden) is not bool:
            raise LibraryError('Say whether to remove the document or restore it.')
        with self.lock:
            folder = self._folder(ident)
            if self._head(folder) is None:
                raise LibraryError('That document has no complete revision in the library, so '
                                   'it cannot be removed or restored. Nothing was changed.')
            if self._hidden(folder) != hidden:
                self._set_hidden(folder, hidden)
        return self.describe(ident)

    def summary(self) -> dict:
        """{'hidden': how many documents are hidden, 'imported': whether any was added as
        existing work}. Nothing is written but the search index."""
        return self._summary(self._index())

    @staticmethod
    def _summary(rows) -> dict:
        return {'hidden': sum(1 for row in rows if row.get('hidden')),
                'imported': any(row.get('adopted') for row in rows)}

    def preview(self, ident, revision=None) -> dict:
        """A revision's readable Markdown, as plain text and bounded. Its hash is checked."""
        place, record = self._record(ident, revision)
        row = self.describe(ident, record['revision'], loaded=(place, record))
        text = ''
        if row['state'] == 'readable':
            data = self._checked(place, record.get('markdown'))
            text = (data or b'').decode('utf-8', 'replace')
        shown = text[:LIMITS['preview']]
        return {**row, 'text': shown, 'truncated': len(text) > len(shown),
                'characters': len(text)}

    def download(self, ident, revision, which) -> tuple[str, str, bytes]:
        """(file name, media type, bytes) of one representation, checked against its hash."""
        place, record = self._record(ident, revision)
        stem = _slug(record.get('title') or 'document')
        if which == 'markdown':
            data = self._checked(place, record.get('markdown'))
            name, media = f'{stem}.md', 'text/markdown'
        elif which == 'original':
            part = record.get('original') or {}
            data = self._checked(place, part, _original_limit(record))
            name = part.get('filename') or f'{stem}{_ending(part.get("file") or "")}'
            # Only a type the library reads goes out under its own media type; whatever
            # else a record says, any other file is a plain download.
            media = part.get('media') if part.get('media') in MEDIA.values() else UNKNOWN_MEDIA
        elif which == 'pdf':
            part = record.get('pdf') or {}
            data = self._checked(place, part, LIMITS['pdf']) if part.get('state') == 'saved' else None
            name, media = f'{stem}.pdf', 'application/pdf'
        else:
            raise LibraryError('Choose Markdown, the original or the PDF.')
        if data is None:
            raise LibraryError(f'This revision has no {FORMATS.get(which, which)} version.')
        return name, media, data

    def snapshot(self, ident, revision) -> dict:
        """What a project pins of one revision: its readable text, its original when it has
        one, and the hashes they were kept with. An unreadable or changed revision is
        refused with why, before the project changes."""
        if type(revision) is not int:
            raise LibraryError('Choose a revision of the document by its number.')
        place, record = self._record(ident, revision)
        state, problem = self._state_of(place, record)
        title = record.get('title') or 'Untitled'
        if self._hidden(place.parent.parent):
            raise LibraryError(HIDDEN.format(title=title))
        if state != 'readable':
            raise LibraryError(f'"{title}" cannot be added: {problem}')
        text = self._checked(place, record.get('markdown')).decode('utf-8')
        original = record.get('original') if isinstance(record.get('original'), dict) else None
        # A research item is taken as its report: its bundle is no studio's source file, and
        # comes out only through research_archive, for a studio importing it.
        if record['kind'] == 'research':
            original = None
        data = self._checked(place, original) if original else None
        name = (original or {}).get('filename') if data is not None else None
        return {'id': record['id'], 'revision': record['revision'], 'title': title,
                'kind': record['kind'], 'studio': record.get('studio'),
                'name': name or f'{_slug(title)}.md', 'original': data, 'text': text,
                'content_sha256': record['markdown']['sha256'],
                'original_sha256': (original or {}).get('sha256') if data is not None else None}

    def heads(self, ids) -> dict:
        """{id: its newest revision, or None when it is no longer in the library or was
        removed from it}."""
        found = {}
        for ident in list(ids)[:200]:
            try:
                folder = self._folder(ident)
                head = None if self._hidden(folder) else self._head(folder)
            except LibraryError:
                head = None
            found[ident] = head['revision'] if head else None
        return found

    # browsing filters, per studio
    FILTERS = {'kind': KINDS, 'studio': STUDIOS, 'origin': ORIGINS, 'state': STATES}

    def filters(self, studio) -> dict:
        """What this studio last browsed with. Never a selection: only filters."""
        if studio not in STUDIOS:
            raise LibraryError('Name a studio.')
        found = _json(self._state() / 'filters.json')
        kept = ((found or {}).get('studios') or {}).get(studio) if isinstance(found, dict) else None
        if not isinstance(kept, dict):
            return {}
        return {key: value for key, value in kept.items()
                if key in self.FILTERS and value in self.FILTERS[key]}

    def remember(self, studio, filters) -> dict:
        if studio not in STUDIOS or not isinstance(filters, dict) \
                or set(filters) - set(self.FILTERS) \
                or any(value not in (None, '', *self.FILTERS[key]) for key, value in filters.items()):
            raise LibraryError('Choose the filters this page offers.')
        clean = {key: value for key, value in filters.items() if value}
        with self.lock:
            path = self._state() / 'filters.json'
            found = _json(path)
            studios = dict(found.get('studios') or {}) if isinstance(found, dict) \
                and isinstance(found.get('studios'), dict) else {}
            studios[studio] = clean
            self._state().mkdir(exist_ok=True, mode=0o700)
            _atomic(path, json.dumps({'schema': SCHEMA, 'studios': studios}, indent=2).encode())
        return clean

    # writing
    def _tidy(self) -> None:
        """Clear away hidden half-made revisions an interrupted write left long ago. Only
        one older than STALE seconds is cleared, so this process looks at most once every
        STALE seconds per library, not on every write."""
        now = time.monotonic()
        with _REMEMBERING:
            last = _TIDIED.get(str(self.root))
            if last is not None and now - last < STALE:
                return
            _TIDIED[str(self.root)] = now
        cutoff = time.time() - STALE
        for parent in [self._documents(), *(self._documents() / ident / 'revisions'
                                             for ident in self._ids())]:
            if not parent.is_dir() or parent.is_symlink():
                continue
            with os.scandir(parent) as entries:
                for entry in entries:
                    if entry.name.startswith('.pending-') and entry.is_dir(follow_symlinks=False) \
                            and entry.stat(follow_symlinks=False).st_mtime < cutoff:
                        shutil.rmtree(entry.path, ignore_errors=True)

    def _write(self, ident: str | None, record: dict, files: dict) -> dict:
        """Keep one revision whole: as a new document when `ident` is None. Hold the lock."""
        _forget(self.root)
        documents = self._documents()
        documents.mkdir(exist_ok=True, mode=0o700)
        if ident is None:
            ident = f"{_slug(record['title'])}-{secrets.token_hex(5)}"
            number, target = 1, documents / ident
            pending = documents / f'.pending-{secrets.token_hex(6)}'
            place = pending / 'revisions' / '1'
        else:
            folder = self._folder(ident)
            numbers = self._numbers(folder)
            if len(numbers) >= LIMITS['revisions']:
                raise LibraryError('This document has as many revisions as the library keeps.')
            number = (numbers[-1] if numbers else 0) + 1
            target = folder / 'revisions' / str(number)
            pending = folder / 'revisions' / f'.pending-{secrets.token_hex(6)}'
            place = pending
        record = {'schema': SCHEMA, 'id': ident, 'revision': number, **record,
                  'created_at': _now(), 'scope': 'local'}
        try:
            place.mkdir(parents=True, mode=0o700)
            for name, data in files.items():
                _atomic(place / name, data)
            _atomic(place / 'revision.json', json.dumps(record, indent=2, ensure_ascii=False).encode())
            os.rename(pending, target)
        except OSError as failure:
            shutil.rmtree(pending, ignore_errors=True)
            raise LibraryError(f'The library could not keep it ({str(failure.strerror or failure).lower()}). '
                               'Nothing was changed; try again.') from None
        return record

    def add_upload(self, name, data, title=None, operation=None, studio='marketing',
                   author=None) -> dict:
        """Keep an uploaded file of any type: its bytes as they were sent, and readable
        Markdown when its type has a reader (READERS) and its text can be read. A file whose
        text cannot be read is kept, marked as needing text, and one of a type with no
        reader is kept as a file (`kept`); neither can be chosen as context. Returns its row.

        The same operation ID returns what it kept. The same file (name, bytes, title and
        studio) under another operation ID is the document already kept, and its row says
        `already`. Either way a hidden document is restored, and its row says `restored`.
        When that document's kept files changed or went missing, a new whole revision of it
        is kept instead, and its row says `repaired`."""
        plain = _plain(name, NAME)
        if plain is None or any(c in plain for c in '/\\:') or plain.startswith('.'):
            raise LibraryError('Add a file by its own name: one with no folder in it, that does not '
                               f'start with a dot and is at most {NAME} characters.')
        if type(data) is not bytes or not data:
            raise LibraryError(f'"{plain}" is empty.')
        if len(data) > LIMITS['bytes']:
            raise LibraryError(f'"{plain}" is larger than 8 MB, the most one document can be.')
        if studio not in STUDIOS:
            raise LibraryError('Name the studio the upload comes from.')
        shown = _plain(title, TITLE) if title else None
        shown = shown or _plain(Path(plain).stem, TITLE) or plain
        who = _plain(author, 100) if author else None
        if operation is not None and (not isinstance(operation, str) or not OPERATION.match(operation)):
            raise LibraryError('An upload needs its operation ID.')
        fingerprint = _sha(json.dumps([plain, _sha(data), shown, studio]).encode())
        ending, kind = _ending(plain), READERS.get(_ending(plain))
        try:
            if kind is None:
                raise _NoReader()
            found = _read(data, kind)
            text = _markdown(found, kind) if found['readable'] else ''
            gaps, method = list(found['warnings']), found['extractor']
            state = 'readable' if text.strip() else 'needs-text'
            problem = None if text.strip() else NO_TEXT
        except _NoReader:
            # No reader for this type: the file is kept whole and nothing in it is opened.
            text, gaps, method, state, problem = '', [], None, 'kept', None
        except ValueError as failure:
            text, gaps, method = '', [], None
            state = 'needs-text' if kind == 'pdf' else 'unreadable'
            problem = str(failure)[:300]
        encoded = text.encode('utf-8')
        if len(encoded) > LIMITS['text']:
            encoded, state, problem = b'', 'unreadable', 'Its text is longer than the library keeps for one document.'
        kept_as = _kept_name(ending)
        files = {kept_as: data}
        record = {'title': shown, 'kind': 'upload', 'origin': 'upload', 'studio': studio,
                  'key': None, 'project': None, 'author': who, 'operation': operation,
                  'fingerprint': fingerprint,
                  'original': {'file': kept_as, 'filename': plain, 'media': MEDIA.get(ending, UNKNOWN_MEDIA),
                               'bytes': len(data), 'sha256': _sha(data)},
                  'markdown': None, 'pdf': None,
                  'conversion': {'method': method, 'state': state, 'gaps': gaps[:20], 'problem': problem}}
        if encoded:
            files['content.md'] = encoded
            record['markdown'] = {'file': 'content.md', 'bytes': len(encoded),
                                  'sha256': _sha(encoded), 'characters': len(text)}
        with self.lock:
            rows = self._index()
            earlier, already = None, False
            if operation:
                for row in rows:
                    if row.get('operation') == operation:
                        _, first = self._record(row['id'], 1)
                        if first.get('fingerprint') != fingerprint:
                            raise LibraryError('This operation ID belongs to a different upload.')
                        earlier = row['id']
                        break
            if earlier is None:
                earlier = next((row['id'] for row in rows if row.get('kind') == 'upload'
                                and row.get('fingerprint') == fingerprint), None)
                already = earlier is not None
            repair = None
            if earlier is not None:
                folder = self._folder(earlier)
                place, head = self._record(earlier)
                if self._whole(place, head):
                    restored = self._hidden(folder)
                    if restored:
                        self._set_hidden(folder, False)
                    return {**self.describe(earlier), 'already': already, 'restored': restored,
                            'repaired': False}
                # Its kept files changed or went missing ("Upload it again"): this upload
                # keeps a whole new revision of the same document, so uploading repairs it.
                repair = earlier
            self._tidy()
            kept = self._write(repair, record, files)
            restored = repair is not None and self._hidden(self._folder(repair))
            if restored:
                self._set_hidden(self._folder(repair), False)
        return {**self.describe(kept['id']), 'already': False, 'restored': restored,
                'repaired': repair is not None}

    def retain(self, key, studio, kind, title, text, project=None, author=None, pdf=None,
               origin='created') -> dict:
        """Keep finished work as readable Markdown, found again by its key: the same key
        reuses the document, and a revision is added only when the text, the title or the
        PDF changed, or when the head's kept PDF went missing or changed (it is kept again).

        `pdf` is None, {'state': 'needs-export', 'reason': str} while no PDF exists, or
        {'state': 'saved', 'data': bytes} with a PDF the studio already exported and checked
        is of exactly this work: up to LIMITS['pdf'] bytes, kept as `content.pdf` as it is,
        never made or converted here; the library checks only that it is a PDF.
        Returns {'document', 'revision', 'changed'}."""
        if not isinstance(key, str) or not KEY.match(key) or key.split(':', 1)[0] != studio:
            raise LibraryError('Name the finished work by its studio and project.')
        # Research is kept with its bundle, by retain_research, never as text alone.
        if kind not in KINDS or kind in ('upload', 'research') or origin not in ORIGINS:
            raise LibraryError('Say what kind of finished work this is.')
        shown = _plain(title, TITLE) or 'Untitled'
        if not isinstance(text, str) or not text.strip():
            raise LibraryError(f'"{shown}" has no text to keep.')
        encoded = text.encode('utf-8')
        if len(encoded) > LIMITS['text']:
            raise LibraryError(f'"{shown}" is longer than the library keeps for one document.')
        files = {'content.md': encoded}
        kept_pdf = _pdf_part(pdf, shown, files)
        held = None
        if isinstance(project, dict):
            held = {'studio': studio, 'id': _plain(project.get('id'), 160),
                    'title': _plain(project.get('title'), TITLE) or shown,
                    'revision': project.get('revision') if type(project.get('revision')) in (int, str) else None}
        record = {'title': shown, 'kind': kind, 'origin': origin, 'studio': studio, 'key': key,
                  'project': held, 'author': _plain(author, 100) if author else None,
                  'operation': None, 'original': None,
                  'markdown': {'file': 'content.md', 'bytes': len(encoded), 'sha256': _sha(encoded),
                               'characters': len(text)},
                  'pdf': kept_pdf,
                  'conversion': {'method': f'{studio}-markdown-v1', 'state': 'readable',
                                 'gaps': [], 'problem': None}}
        with self.lock:
            existing = next((row['id'] for row in self._index() if row.get('key') == key), None)
            if existing:
                place, head = self._record(existing)
                held_pdf, wanted = head.get('pdf') or {}, kept_pdf or {}
                same = (head.get('title') == shown
                        and (head.get('markdown') or {}).get('sha256') == record['markdown']['sha256']
                        and held_pdf.get('state') == wanted.get('state')
                        and held_pdf.get('sha256') == wanted.get('sha256'))
                # a kept PDF that went missing or changed is kept again
                whole = wanted.get('state') != 'saved' or self._pdf_whole(place, held_pdf)
                if same and whole and self._state_of(place, head)[0] == 'readable':
                    return {'document': existing, 'revision': head['revision'], 'changed': False}
            self._tidy()
            kept = self._write(existing, record, files)
        return {'document': kept['id'], 'revision': kept['revision'], 'changed': True}

    def retain_research(self, key, studio, title, text, bundle, project=None, author=None,
                        research=None) -> dict:
        """Keep verified Harness Research (see research.py, which checks it first): its report
        as readable Markdown, so every Add from library can take it as a source, and its whole
        bundle as the original, `original.zip`, so a studio that runs Harness Research can
        import it. Found again by its key, `<studio>:<project>:research`: the same key reuses
        the document, and a revision is added only when the title, the report or the bundle
        changed, or a kept file went missing or changed. `research` is a small record of what
        the bundle is ({'owner', 'digest', 'status', 'files'}), kept as it is given.
        Returns {'document', 'revision', 'changed'}."""
        if not isinstance(key, str) or not RESEARCH_KEY.match(key) or key.split(':', 1)[0] != studio:
            raise LibraryError('Name the research by its studio and project.')
        shown = _plain(title, TITLE) or 'Research'
        if not isinstance(text, str) or not text.strip():
            raise LibraryError(f'"{shown}" has no report to keep.')
        encoded = text.encode('utf-8')
        if len(encoded) > LIMITS['text']:
            raise LibraryError(f'"{shown}" is longer than the library keeps for one document.')
        if type(bundle) is not bytes or not bundle.startswith(b'PK'):
            raise LibraryError(f'"{shown}" has no research bundle to keep.')
        if len(bundle) > LIMITS['research']:
            raise LibraryError(f'The research bundle of "{shown}" is larger than 16 MB zipped, '
                               'the most the library keeps for one research bundle.')
        try:
            described = json.dumps(research if research is not None else {}, ensure_ascii=False)
        except (TypeError, ValueError):
            raise LibraryError('Describe the research with plain values.') from None
        if not isinstance(research, (dict, type(None))) or len(described) > 8_000:
            raise LibraryError('Describe the research in at most 8,000 characters.')
        held = None
        if isinstance(project, dict):
            held = {'studio': studio, 'id': _plain(project.get('id'), 160),
                    'title': _plain(project.get('title'), TITLE) or shown,
                    'revision': project.get('revision') if type(project.get('revision')) in (int, str) else None}
        part = {'file': BUNDLE_FILE, 'filename': f'{_slug(shown)}-research.zip', 'media': UNKNOWN_MEDIA,
                'bytes': len(bundle), 'sha256': _sha(bundle)}
        record = {'title': shown, 'kind': 'research', 'origin': 'created', 'studio': studio, 'key': key,
                  'project': held, 'author': _plain(author, 100) if author else None,
                  'operation': None, 'original': part, 'pdf': None,
                  'markdown': {'file': 'content.md', 'bytes': len(encoded), 'sha256': _sha(encoded),
                               'characters': len(text)},
                  'research': json.loads(described) if research is not None else None,
                  'conversion': {'method': 'harness-research-bundle-v1', 'state': 'readable',
                                 'gaps': [], 'problem': None}}
        files = {'content.md': encoded, BUNDLE_FILE: bundle}
        with self.lock:
            existing = next((row['id'] for row in self._index() if row.get('key') == key), None)
            if existing:
                place, head = self._record(existing)
                # The same research is the same title, report and manifest (whose file hashes
                # name every file): an archive made again by another zlib is not a change.
                manifest = (research or {}).get('manifest_sha256')
                same = (head.get('title') == shown
                        and (head.get('markdown') or {}).get('sha256') == record['markdown']['sha256']
                        and (((head.get('research') or {}).get('manifest_sha256') == manifest and manifest)
                             or (head.get('original') or {}).get('sha256') == part['sha256']))
                if same and self._whole(place, head):
                    return {'document': existing, 'revision': head['revision'], 'changed': False}
            self._tidy()
            kept = self._write(existing, record, files)
        return {'document': kept['id'], 'revision': kept['revision'], 'changed': True}

    def research_archive(self, ident, revision) -> dict:
        """A research revision's bundle as kept, for a studio importing it (research.py):
        {'id', 'revision', 'title', 'studio', 'archive': bytes, 'archive_sha256',
        'content_sha256', 'research'}. The archive and the report are checked against the
        hashes they were kept with; another kind, a removed document or one that is not
        whole is refused with why."""
        if type(revision) is not int:
            raise LibraryError('Choose a revision of the document by its number.')
        place, record = self._record(ident, revision)
        title = record.get('title') or 'Research'
        if record['kind'] != 'research' or not isinstance(record.get('original'), dict):
            raise LibraryError('That document is not research the library kept, so it has no '
                               'research bundle to import.')
        if self._hidden(place.parent.parent):
            raise LibraryError(HIDDEN.format(title=title))
        state, problem = self._state_of(place, record)
        if state != 'readable':
            raise LibraryError(f'"{title}" cannot be imported: {problem}')
        self._checked(place, record.get('markdown'))
        data = self._checked(place, record['original'], LIMITS['research'])
        return {'id': record['id'], 'revision': record['revision'], 'title': title,
                'studio': record.get('studio'), 'archive': data,
                'archive_sha256': record['original']['sha256'],
                'content_sha256': record['markdown']['sha256'],
                'research': copy.deepcopy(record.get('research'))}

    def _pdf_whole(self, place: Path, part: dict, hashed: bool = True) -> bool:
        """Whether a revision's saved PDF is there and is the one it was kept with: checked
        by its hash, or, without `hashed`, only by its size (cheap enough for a preview)."""
        if not isinstance(part, dict) or part.get('state') != 'saved':
            return False
        if not hashed:
            path = place / str(part.get('file') or '')
            return '/' not in str(part.get('file')) and not path.is_symlink() and path.is_file() \
                and path.stat().st_size == part.get('bytes')
        try:
            return self._checked(place, part, LIMITS['pdf']) is not None
        except (LibraryError, OSError):
            return False

    # existing work, added explicitly (adopt.py)
    def keyed(self, keys) -> dict:
        """{key: what the library holds under it now} for the keys it has: the document,
        its newest revision, its title and the hashes of its Markdown, its original and its
        saved PDF (None when it has none, or when that file is gone or another size). Keys
        the library does not hold are left out. Nothing is written."""
        wanted = {key for key in list(keys)[:LIMITS['documents']] if isinstance(key, str)}
        found = {}
        for row in self._index():
            key = row.get('key')
            if key not in wanted or key in found:
                continue
            try:
                place, head = self._record(row['id'])
            except LibraryError:
                continue
            found[key] = {'id': head['id'], 'revision': head['revision'],
                          'title': head.get('title'),
                          'markdown': (head.get('markdown') or {}).get('sha256'),
                          'original': (head.get('original') or {}).get('sha256'),
                          'pdf': head['pdf'].get('sha256')
                          if self._pdf_whole(place, head.get('pdf'), hashed=False) else None,
                          'whole': self._state_of(place, head)[0] != 'missing',
                          'hidden': bool(row.get('hidden'))}
        return found

    def uploaded(self, studio) -> dict:
        """{original's SHA-256: {'id', 'revision'}} for the files this studio kept as uploads
        (Keep in library), newest revision of each. Nothing is written."""
        found = {}
        for row in self._index():
            if row.get('studio') != studio or row.get('kind') != 'upload' or row.get('key'):
                continue
            try:
                _, head = self._record(row['id'])
            except LibraryError:
                continue
            digest = (head.get('original') or {}).get('sha256')
            if isinstance(digest, str):
                found.setdefault(digest, {'id': head['id'], 'revision': head['revision']})
        return found

    def adopt(self, key, studio, kind, origin, title, text='', original=None, filename=None,
              project=None, author=None, native=None, gaps=(), pdf=None) -> dict:
        """Keep existing work a person chose to add, found again by its key as `retain`
        finds finished work: readable Markdown when it has text, its original bytes when it
        has a file, and `native`, what the studio calls it (its own ID, revision, roles,
        voice and style), recorded as it was given. The same key reuses its document and a
        revision is added only when the title, the text, the original or a saved PDF
        changed, so adding again adds nothing. Returns {'document', 'revision', 'changed'}.

        `pdf` is what `retain` takes, and only an adapter that checked the PDF against the
        exact revision it was made from passes it as 'saved' (a delivered deck's PDF by the
        deck file it rendered, an approved infographic's by its export's manifest); every
        other PDF is left out, never passed as the original. Blog Studio and Training Studio
        keep none. Existing work with no saved PDF never takes away one the library already
        keeps of the same text: that is the same work, so nothing is added."""
        if not isinstance(key, str) or not KEY.match(key) or key.split(':', 1)[0] != studio:
            raise LibraryError('Name the existing work by its studio and its own ID.')
        if kind not in KINDS or kind == 'research' or origin not in ORIGINS:
            raise LibraryError('Say what kind of work this is and where it came from.')
        shown = _plain(title, TITLE) or 'Untitled'
        text = text if isinstance(text, str) else ''
        encoded = text.encode('utf-8') if text.strip() else b''
        if len(encoded) > LIMITS['text']:
            raise LibraryError(f'"{shown}" is longer than the library keeps for one document.')
        files, part = {}, None
        if original is not None:
            plain = _plain(filename, NAME)
            if type(original) is not bytes or not original or plain is None \
                    or any(c in plain for c in '/\\:') or plain.startswith('.'):
                raise LibraryError(f'"{shown}" has no file the library can keep.')
            if len(original) > LIMITS['bytes']:
                raise LibraryError(f'"{shown}" is larger than 8 MB, the most one document can be.')
            ending = _ending(plain)
            files[_kept_name(ending)] = original
            part = {'file': _kept_name(ending), 'filename': plain, 'media': MEDIA.get(ending, UNKNOWN_MEDIA),
                    'bytes': len(original), 'sha256': _sha(original)}
        if not encoded and part is None:
            raise LibraryError(f'"{shown}" has no text or file to keep.')
        kept_pdf = _pdf_part(pdf, shown, files)
        try:
            described = json.dumps(native if native is not None else {}, ensure_ascii=False)
        except (TypeError, ValueError):
            raise LibraryError('Describe the existing work with plain values.') from None
        if not isinstance(native, (dict, type(None))) or len(described) > 8_000:
            raise LibraryError('Describe the existing work in at most 8,000 characters.')
        notes = [note for note in (_plain(gap, 300) for gap in list(gaps)[:20]) if note]
        held = None
        if isinstance(project, dict):
            held = {'studio': studio, 'id': _plain(project.get('id'), 160),
                    'title': _plain(project.get('title'), TITLE) or shown,
                    'revision': project.get('revision') if type(project.get('revision')) in (int, str) else None}
        record = {'title': shown, 'kind': kind, 'origin': origin, 'studio': studio, 'key': key,
                  'project': held, 'author': _plain(author, 100) if author else None,
                  'operation': None, 'original': part, 'markdown': None, 'pdf': kept_pdf,
                  'native': json.loads(described) if native is not None else None,
                  'adopted': True,
                  'conversion': {'method': f'{studio}-existing-v1',
                                 'state': 'readable' if encoded else 'needs-text',
                                 'gaps': notes, 'problem': None if encoded else NO_TEXT}}
        if encoded:
            files['content.md'] = encoded
            record['markdown'] = {'file': 'content.md', 'bytes': len(encoded),
                                  'sha256': _sha(encoded), 'characters': len(text)}
        with self.lock:
            existing = next((row['id'] for row in self._index() if row.get('key') == key), None)
            if existing:
                place, head = self._record(existing)
                same = (head.get('title') == shown
                        and (head.get('markdown') or {}).get('sha256') == (record['markdown'] or {}).get('sha256')
                        and (head.get('original') or {}).get('sha256') == (part or {}).get('sha256'))
                held_pdf = head.get('pdf') or {}
                if (kept_pdf or {}).get('state') == 'saved':
                    # a saved PDF is the same only when the head keeps exactly it, whole
                    same = same and held_pdf.get('sha256') == kept_pdf['sha256'] \
                        and self._pdf_whole(place, held_pdf)
                if same and self._state_of(place, head)[0] != 'missing':
                    return {'document': existing, 'revision': head['revision'], 'changed': False}
            self._tidy()
            kept = self._write(existing, record, files)
        return {'document': kept['id'], 'revision': kept['revision'], 'changed': True}
