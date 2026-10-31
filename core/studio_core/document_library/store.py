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
    <library>/documents/<id>/revisions/<n>/     # one immutable revision
        revision.json                           # written last: what the revision is
        content.md                              # readable Markdown, when there is any
        original<ending>                        # an upload's bytes, as they were sent
    <library>/.state/catalog.json               # a search index, rebuilt from records
    <library>/.state/filters.json               # each studio's browsing filters

A revision is made in a hidden folder beside the others and renamed into place whole, so
an interrupted write leaves no half-made revision: the newest complete revision is the
document's head. A document's ID never changes. Finished work is found again by its key
(`<studio>:<project>`), so a repeated Finish or Deliver reuses its document and adds a
revision only when what it keeps changed. An upload's operation ID makes a retry return
what the first attempt kept. Every file is checked against its recorded hash before it is
previewed, downloaded or pinned; a link, a missing file or a changed file is refused.

A document's text is never trusted: it is shown as text, never as markup, and is never
sent anywhere by the library. Nothing here uses the network, starts an assistant, runs
OCR or a model, installs a reader, or shares anything with a team.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from studio_core import source_documents, studios_config
from studio_core.process_lock import ProcessRLock


class LibraryError(ValueError):
    """A refusal, in a sentence a person can act on."""


SCHEMA = 1
PRODUCT = 'Studios Document Library'
KINDS = {'upload': 'Uploaded document', 'blog': 'Blog', 'presentation': 'Presentation',
         'training': 'Training material', 'infographic': 'Infographic'}
ORIGINS = {'upload': 'Upload', 'created': 'Created here', 'link': 'Link',
           'google': 'Google document', 'imported': 'Imported'}
STUDIOS = {'marketing': 'Marketing Studio', 'blog': 'Blog Studio',
           'presentation': 'Presentation Studio', 'training': 'Training Studio',
           'infographic': 'Infographic Studio'}
FORMATS = {'markdown': 'Markdown', 'original': 'Original', 'pdf': 'PDF'}
STATES = {'readable': 'Readable', 'needs-text': 'Needs text', 'unreadable': 'Cannot be read',
          'missing': 'Files missing'}
ENDINGS = {'.txt': 'text', '.md': 'text', '.html': 'html',
           '.htm': 'html', '.docx': 'docx', '.pdf': 'pdf'}
MEDIA = {'.txt': 'text/plain', '.md': 'text/markdown',
         '.html': 'text/html', '.htm': 'text/html', '.pdf': 'application/pdf',
         '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}
LIMITS = {'bytes': 8_000_000,       # one original, as the studios' supplied documents take
          'text': 8_000_000,        # bytes of one revision's Markdown
          'documents': 5_000,       # documents a catalog reads
          'revisions': 1_000,       # revisions one document keeps
          'page': 50,               # rows one catalog page gives
          'preview': 20_000,        # characters a preview shows
          'matching': 40}           # documents "all matching" may choose at once
IDENT = re.compile(r'^[a-z0-9][a-z0-9-]{0,63}$')
KEY = re.compile(r'^(blog|presentation|training|infographic):[A-Za-z0-9][A-Za-z0-9._-]{0,159}$')
OPERATION = re.compile(r'^[a-f0-9]{32}$')
RECORD_LIMIT = 256_000      # bytes of one revision.json
EXCERPT = 4_000             # characters of each document's text the search index keeps
NAME = 120                  # characters in an uploaded file's name
TITLE = 200                 # characters in a title
WAIT = 10.0
STALE = 3600                # seconds before a hidden half-made revision is cleared away
NO_TEXT = ('It has no readable text yet. Upload a text or Word version of it, then choose '
           'that one. Nothing is read from pictures automatically.')
CHANGED = ('Its files in the library changed after they were kept, so it cannot be used. '
           'Upload it again.')
MISSING = 'Its files are missing from the library folder. Upload it again.'


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
    saved = _saved(values)
    if saved:
        where = Path(saved).expanduser()
    else:
        base = (values.get('local') or {}).get('root') if isinstance(values.get('local'), dict) else None
        if not (isinstance(base, str) and base and Path(base).expanduser().is_absolute()):
            base = '~/Studios'
        where = Path(base).expanduser() / 'library'
    return {'root': where, 'saved': bool(saved), 'shown': studios_config.shown(where),
            'problem': problem}


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
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise LibraryError(CHANGED)
    return data


def _json(path: Path):
    try:
        return json.loads(_bounded(path, RECORD_LIMIT).decode('utf-8'))
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


def _markdown(found: dict, kind: str) -> str:
    """Readable Markdown from what an extractor read: page headings for a PDF, paragraphs
    for the rest. Nothing is added that the document did not say."""
    text = found['text']
    if kind == 'text':
        return text
    parts = []
    for place in found['locations']:
        passage = text[place['start']:place['end']].strip()
        if not passage:
            continue
        parts.append(f"## {place['label']}\n\n{passage}" if kind == 'pdf' else passage)
    return '\n\n'.join(parts).strip() + '\n'


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
    def _checked(place: Path, part: dict | None) -> bytes | None:
        """A representation's bytes, refused unless they match the hash it was kept with."""
        if not isinstance(part, dict) or not isinstance(part.get('file'), str):
            return None
        name = part['file']
        if '/' in name or name.startswith('.'):
            raise LibraryError(CHANGED)
        data = _bounded(place / name, max(LIMITS['bytes'], LIMITS['text']))
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
            'project': {'studio': project.get('studio'), 'title': project.get('title'),
                        'revision': project.get('revision')} if project else None,
            'scope': 'local',
        }

    # the search index
    def _index(self) -> list[dict]:
        ids = self._ids()
        heads = []
        for ident in ids:
            numbers = self._numbers(self._documents() / ident)
            heads.append([ident, numbers[-1] if numbers else 0])
        cache = self._state() / 'catalog.json'
        found = _json(cache)
        if isinstance(found, dict) and found.get('schema') == SCHEMA \
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
            row['search'] = ' '.join((row['title'], row.get('author') or '',
                                      row.get('original_name') or '', excerpt)).casefold()
            entries.append(row)
        try:
            self._state().mkdir(exist_ok=True, mode=0o700)
            _atomic(cache, json.dumps({'schema': SCHEMA, 'signature': heads,
                                       'entries': entries}).encode())
        except OSError:
            pass    # the index is only a convenience: it is rebuilt from the records
        return entries

    @staticmethod
    def _public(row: dict) -> dict:
        return {key: value for key, value in row.items() if key not in ('search', 'key', 'operation')}

    def _matches(self, query='', kind=None, studio=None, origin=None, author=None, state=None):
        if kind not in (None, '', *KINDS) or studio not in (None, '', *STUDIOS) \
                or origin not in (None, '', *ORIGINS) or state not in (None, '', *STATES):
            raise LibraryError('Choose the filters this page offers.')
        if not isinstance(query or '', str) or len(query or '') > 200 \
                or not isinstance(author or '', str) or len(author or '') > 100:
            raise LibraryError('Search with at most 200 characters.')
        words = (query or '').casefold().split()
        who = (author or '').casefold().strip()
        rows = [row for row in self._index()
                if (not kind or row['kind'] == kind) and (not studio or row['studio'] == studio)
                and (not origin or row['origin'] == origin) and (not state or row['state'] == state)
                and (not who or who in (row.get('author') or '').casefold())
                and all(word in row['search'] for word in words)]
        rows.sort(key=lambda row: (row.get('updated_at') or '', row['title'].casefold()), reverse=True)
        return rows

    def catalog(self, query='', kind=None, studio=None, origin=None, author=None, state=None,
                offset=0, limit=25) -> dict:
        """One page of documents that match, newest first: {'items', 'total', 'offset',
        'limit'}. Each item is a document's newest revision; no local path is given."""
        if type(offset) is not int or offset < 0 or type(limit) is not int \
                or not 1 <= limit <= LIMITS['page']:
            raise LibraryError(f"Ask for at most {LIMITS['page']} documents at a time.")
        rows = self._matches(query, kind, studio, origin, author, state)
        return {'items': [self._public(row) for row in rows[offset:offset + limit]],
                'total': len(rows), 'offset': offset, 'limit': limit}

    def matching(self, readable_only=True, **filters) -> list[dict]:
        """Every readable document the filters match, as {'id', 'revision'}: what "Select all
        matching" chooses. Refused when more match than a project can take at once."""
        rows = [row for row in self._matches(**filters) if row['readable'] or not readable_only]
        if len(rows) > LIMITS['matching']:
            raise LibraryError(f"{len(rows)} documents match. Narrow the filters to at most "
                               f"{LIMITS['matching']} before selecting all of them.")
        return [{'id': row['id'], 'revision': row['revision']} for row in rows]

    def describe(self, ident, revision=None) -> dict:
        place, record = self._record(ident, revision)
        folder = place.parent.parent
        first = self._revision(folder, 1)
        row = self._row(place, record, (first or {}).get('created_at'))
        head = self._head(folder)
        row['head'] = head['revision'] if head else record['revision']
        row['revisions'] = self._numbers(folder)[-50:]
        return row

    def preview(self, ident, revision=None) -> dict:
        """A revision's readable Markdown, as plain text and bounded. Its hash is checked."""
        place, record = self._record(ident, revision)
        row = self.describe(ident, record['revision'])
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
            data = self._checked(place, part)
            name = part.get('filename') or f'{stem}{_ending(part.get("file") or "")}'
            media = part.get('media') or 'application/octet-stream'
        elif which == 'pdf':
            part = record.get('pdf') or {}
            data = self._checked(place, part) if part.get('state') == 'saved' else None
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
        if state != 'readable':
            raise LibraryError(f'"{title}" cannot be added: {problem}')
        text = self._checked(place, record.get('markdown')).decode('utf-8')
        original = record.get('original') if isinstance(record.get('original'), dict) else None
        data = self._checked(place, original) if original else None
        name = (original or {}).get('filename') if data is not None else None
        return {'id': record['id'], 'revision': record['revision'], 'title': title,
                'kind': record['kind'], 'studio': record.get('studio'),
                'name': name or f'{_slug(title)}.md', 'original': data, 'text': text,
                'content_sha256': record['markdown']['sha256'],
                'original_sha256': (original or {}).get('sha256') if data is not None else None}

    def heads(self, ids) -> dict:
        """{id: its newest revision, or None when it is no longer in the library}."""
        found = {}
        for ident in list(ids)[:200]:
            try:
                head = self._head(self._folder(ident))
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
        """Clear away hidden half-made revisions an interrupted write left long ago."""
        cutoff = time.time() - STALE
        for parent in [self._documents(), *(self._documents() / ident / 'revisions'
                                             for ident in self._ids())]:
            if not parent.is_dir() or parent.is_symlink():
                continue
            for entry in os.scandir(parent):
                if entry.name.startswith('.pending-') and entry.is_dir(follow_symlinks=False) \
                        and entry.stat(follow_symlinks=False).st_mtime < cutoff:
                    shutil.rmtree(entry.path, ignore_errors=True)

    def _write(self, ident: str | None, record: dict, files: dict) -> dict:
        """Keep one revision whole: as a new document when `ident` is None. Hold the lock."""
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
        """Keep an uploaded file: its bytes as they were sent, and readable Markdown when
        its text can be read. A file whose text cannot be read is kept, marked as needing
        text, and cannot be chosen as context until text is supplied. Returns its row."""
        plain = _plain(name, NAME)
        if plain is None or any(c in plain for c in '/\\:') or plain.startswith('.') \
                or _ending(plain) not in ENDINGS:
            raise LibraryError('Upload a text, Markdown, HTML, Word (.docx) or PDF file by its name.')
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
        ending, kind = _ending(plain), ENDINGS[_ending(plain)]
        try:
            found = source_documents.extract(data, kind)
            text = _markdown(found, kind) if found['readable'] else ''
            gaps, method = list(found['warnings']), found['extractor']
            state = 'readable' if text.strip() else 'needs-text'
            problem = None if text.strip() else NO_TEXT
        except ValueError as failure:
            text, gaps, method = '', [], None
            state = 'needs-text' if kind == 'pdf' else 'unreadable'
            problem = str(failure)[:300]
        encoded = text.encode('utf-8')
        if len(encoded) > LIMITS['text']:
            encoded, state, problem = b'', 'unreadable', 'Its text is longer than the library keeps for one document.'
        files = {f'original{ending}': data}
        record = {'title': shown, 'kind': 'upload', 'origin': 'upload', 'studio': studio,
                  'key': None, 'project': None, 'author': who, 'operation': operation,
                  'fingerprint': fingerprint,
                  'original': {'file': f'original{ending}', 'filename': plain,
                               'media': MEDIA[ending], 'bytes': len(data), 'sha256': _sha(data)},
                  'markdown': None, 'pdf': None,
                  'conversion': {'method': method, 'state': state, 'gaps': gaps[:20], 'problem': problem}}
        if encoded:
            files['content.md'] = encoded
            record['markdown'] = {'file': 'content.md', 'bytes': len(encoded),
                                  'sha256': _sha(encoded), 'characters': len(text)}
        with self.lock:
            if operation:
                for row in self._index():
                    if row.get('operation') == operation:
                        _, earlier = self._record(row['id'], 1)
                        if earlier.get('fingerprint') != fingerprint:
                            raise LibraryError('This operation ID belongs to a different upload.')
                        return self.describe(row['id'])
            self._tidy()
            kept = self._write(None, record, files)
        return self.describe(kept['id'])

    def retain(self, key, studio, kind, title, text, project=None, author=None, pdf=None,
               origin='created') -> dict:
        """Keep finished work as readable Markdown, found again by its key: the same key
        reuses the document, and a revision is added only when the text, the title or the
        PDF's state changed. Returns {'document', 'revision', 'changed'}."""
        if not isinstance(key, str) or not KEY.match(key) or key.split(':', 1)[0] != studio:
            raise LibraryError('Name the finished work by its studio and project.')
        if kind not in KINDS or kind == 'upload' or origin not in ORIGINS:
            raise LibraryError('Say what kind of finished work this is.')
        shown = _plain(title, TITLE) or 'Untitled'
        if not isinstance(text, str) or not text.strip():
            raise LibraryError(f'"{shown}" has no text to keep.')
        encoded = text.encode('utf-8')
        if len(encoded) > LIMITS['text']:
            raise LibraryError(f'"{shown}" is longer than the library keeps for one document.')
        if pdf is not None and not (isinstance(pdf, dict) and pdf.get('state') == 'needs-export'
                                    and isinstance(pdf.get('reason'), str)):
            raise LibraryError('A PDF is kept only once it has been exported.')
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
                  'pdf': {'state': 'needs-export', 'reason': pdf['reason'][:300]} if pdf else None,
                  'conversion': {'method': f'{studio}-markdown-v1', 'state': 'readable',
                                 'gaps': [], 'problem': None}}
        with self.lock:
            existing = next((row['id'] for row in self._index() if row.get('key') == key), None)
            if existing:
                place, head = self._record(existing)
                same = (head.get('title') == shown
                        and (head.get('markdown') or {}).get('sha256') == record['markdown']['sha256']
                        and (head.get('pdf') or {}).get('state') == (record['pdf'] or {}).get('state'))
                if same and self._state_of(place, head)[0] == 'readable':
                    return {'document': existing, 'revision': head['revision'], 'changed': False}
            self._tidy()
            kept = self._write(existing, record, {'content.md': encoded})
        return {'document': kept['id'], 'revision': kept['revision'], 'changed': True}
