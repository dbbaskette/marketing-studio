"""One private source-draft API for every studio, with no provider or Google writes."""
from __future__ import annotations

import base64
import hashlib
import html
import json
import os
from pathlib import Path
import re
import secrets
import time
from collections import deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from urllib.parse import unquote, urlsplit

from studio_core import (google_api, google_reference, pptx_slides, public_fetch, source_documents,
                         source_folders, research_sites, xlsx_sheets)
from studio_core.process_lock import ProcessRLock
from studio_core import research_contract as rc

LIMIT = 8_000_000
# Files and pasted texts one source draft holds; links are not counted. Each is kept whole
# in the draft, and each is one research entry, so this stays well inside RESEARCH_ENTRIES.
# Raised from 40 when a whole folder could be added (`source_folders.FOLDER_MOST` at a time).
MOST = 400
LINKS = ('url', 'google-doc', 'google-slides')
# What one research run can take in, as Harness Research 1.2.0 and newer count it: a link is two
# entries (its address and its captured text), anything else is one. Said before Start, never
# after. An older installed Harness Research takes fewer and is named when research starts.
RESEARCH_ENTRIES = 2000


def entries(sources):
    """How many research entries the readable sources come to."""
    return sum(2 if s.get('kind') in LINKS else 1 for s in sources if s.get('status') == 'ready')


def over(sources):
    """Why these sources are too many for one research run, or None."""
    count = entries(sources)
    if count <= RESEARCH_ENTRIES:
        return None
    links = sum(s.get('kind') in LINKS and s.get('status') == 'ready' for s in sources)
    other = count - 2 * links
    return (f'One research run reads at most {RESEARCH_ENTRIES // 2:,} links, or {RESEARCH_ENTRIES:,} files and pasted '
            f'texts; a link counts as two. You have {links} {"link" if links == 1 else "links"}'
            + (f' and {other} other {"source" if other == 1 else "sources"}' if other else '')
            + f', which is {count - RESEARCH_ENTRIES} over. Remove or exclude the ones this work needs least.')
TYPES = {'.txt': 'text', '.md': 'text', '.markdown': 'text', '.pdf': 'pdf', '.docx': 'docx',
         '.pptx': 'pptx', '.xlsx': 'xlsx', '.html': 'html', '.htm': 'html'}
PPTX_UNREADABLE = 'This PowerPoint file could not be read safely. Save it as a PDF and add that copy instead.'
DRIVE_ORIGIN = re.compile(r'https://(?:docs|drive)\.google\.com/(?:document|presentation|spreadsheets|file)/d/([A-Za-z0-9_-]{1,200})')


def read(raw, kind, extract):
    """A document's readable text. A PowerPoint file's slide text and speaker notes are
    read here, with the reader a Google Slides deck's export goes through, and a
    spreadsheet workbook's sheets with `xlsx_sheets`."""
    if kind == 'xlsx':
        return xlsx_sheets.extract(raw)
    if kind != 'pptx':
        return extract(raw, kind)
    try:
        found, _ = google_reference.extract_presentation(pptx_slides.slides(raw))
    except pptx_slides.Unreadable as error:
        raise ValueError(PPTX_UNREADABLE if str(error) == pptx_slides.UNREADABLE else str(error)) from None
    found['extractor'] = 'pptx-slides-v1'
    return found


def same(name):
    return 'It has the same content as “' + str(name)[:200] + '”.' if name else ''


class Skipped(ValueError):
    """One document in a folder that was not taken, and why (`source_folders.REASONS`)."""
    def __init__(self, code, detail='', mark=None):
        super().__init__(detail)
        # `mark` is the SHA-256 of its bytes when they were read before it was left.
        self.code, self.detail, self.mark = code, detail, mark


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def page_name(raw, mime, url):
    """What a fetched page is called in a list: its own title, a document's filename, else its address."""
    if mime == 'text/html':
        found = re.search(rb'<title[^>]*>(.*?)</title>', raw[:200_000], flags=re.I | re.S)
        title = ' '.join(html.unescape(found.group(1).decode('utf-8', errors='ignore')).split()) if found else ''
        if title:
            return title[:200]
    leaf = unquote(urlsplit(url).path.rsplit('/', 1)[-1]).strip()
    return leaf[:200] if mime == 'application/pdf' and leaf else url


class Sources:
    def __init__(self, root, *, google=None, fetch=None, account=None, extract=None, drive=None, clock=None):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not (self.root / '.gitignore').exists():
            rc.write(self.root, '.gitignore', '*\n')
        self.google = google or google_reference.capture
        self.fetch = fetch or public_fetch.fetch
        self.account = account
        self.extract = extract or source_documents.extract
        # A folder add lists Google Drive through this client and times itself by this clock.
        self.drive = drive or google_api.Client
        self.clock = clock or time.monotonic
        self.lock = ProcessRLock(lambda: self.root / 'sources.lock', refusal=ValueError)

    def folder(self, ident):
        require(isinstance(ident, str) and re.fullmatch('[a-f0-9]{32}', ident), 'Choose a source draft from this studio.')
        return rc.inside(self.root, ident)

    def load(self, ident):
        try:
            value = json.loads(rc.inside(self.folder(ident), 'draft.json').read_text())
        except (OSError, ValueError) as error:
            raise ValueError('This source draft is unavailable. Create a new one; your saved studio work is kept.') from error
        require(value.get('owner') == 'studio-research-sources' and value.get('schema') == 1,
                'This source draft is not owned by the shared research component.')
        return value

    def save(self, value):
        value['revision'] = secrets.token_hex(16)
        rc.write(self.folder(value['id']), 'draft.json', json.dumps(value))

    @staticmethod
    def shown(value):
        keys = ('id', 'revision', 'external', 'restricted', 'sites', 'workers', 'focus')
        return {**{k: value[k] for k in keys}, 'sources': [{k: s[k] for k in (
            'id', 'name', 'kind', 'origin', 'status', 'warnings', 'problem', 'tabs', 'selected_tabs', 'captured_at', 'sha256', 'characters')
            if k in s} for s in value['sources']], 'formats': list(TYPES), 'over': over(value['sources'])}

    def create(self, *, sites=()):
        with self.lock:
            ident = secrets.token_hex(16)
            self.folder(ident).mkdir(mode=0o700)
            value = {'schema': 1, 'owner': 'studio-research-sources', 'id': ident,
                'revision': '', 'external': False, 'restricted': False,
                'sites': research_sites.sites(list(sites)), 'workers': 3, 'focus': '', 'sources': []}
            self.save(value)
            return self.shown(value)

    def read(self, ident):
        with self.lock:
            return self.shown(self.load(ident))

    def from_inputs(self, item, saved, research_from, *, sites=()):
        """A new draft that holds what an item's research reads now, so the shared editor
        can change it: each saved capture, checked against its manifest first, and where
        research may search (`research_from`, as the item's record pinned it). `sites` are
        the shared ones a draft offers when the item searches no sites of its own. The
        item's own snapshot is only read."""
        item = Path(item)
        rows = []
        if saved:
            sources(item, saved)   # every capture is what its manifest says, or a refusal
            manifest = json.loads(rc.inside(item, 'sources/research-inputs/manifest.json').read_text())
            rows = manifest['sources']
        chosen = research_sites.effective(research_from)
        with self.lock:
            ident = secrets.token_hex(16)
            folder = self.folder(ident)
            folder.mkdir(mode=0o700)
            kept = []
            for row in rows:
                raw = rc.inside(item, row['original']).read_bytes()
                text = rc.inside(item, row['file']).read_text()
                raw_name = 'captures/' + hashlib.sha256(raw).hexdigest() + '.raw'
                text_name = 'captures/' + hashlib.sha256(text.encode()).hexdigest() + '.txt'
                rc.write(folder, raw_name, raw)
                rc.write(folder, text_name, text)
                source = {k: row[k] for k in ('id', 'name', 'kind', 'origin', 'warnings', 'tabs',
                          'selected_tabs', 'captured_at', 'sha256', 'original_sha256') if k in row}
                source.update(status='ready', problem=None, file=text_name, original=raw_name)
                source.setdefault('warnings', [])
                source.setdefault('tabs', [])
                source.setdefault('selected_tabs', [])
                if source.get('kind') in ('url', 'google-doc', 'google-slides'):
                    source['requested_url'] = source.get('origin')
                kept.append(source)
            restricted = bool(chosen['sites'])
            value = {'schema': 1, 'owner': 'studio-research-sources', 'id': ident, 'revision': '',
                     'external': bool(chosen['web'] or chosen['sites']), 'restricted': restricted,
                     'sites': chosen['sites'] if restricted else research_sites.sites(list(sites)),
                     'workers': int((saved or {}).get('workers') or 3),
                     'focus': str((saved or {}).get('focus') or ''), 'sources': kept}
            self.save(value)
            return self.shown(value)

    def check(self, ident, expected):
        value = self.load(ident)
        require(value['revision'] == expected, 'These sources changed in another view. Reload; your entered links and text are kept.')
        return value

    def mutate(self, ident, expected, operation, **data):
        require(operation in ('configure', 'remove', 'exclude', 'capture', 'tabs', 'folder'), 'Choose a supported source action.')
        if operation == 'folder':
            return self.add_folder(ident, expected, data)
        # Network/extraction happens outside the draft lock; adoption rechecks the same revision.
        if operation in ('capture', 'tabs'):
            with self.lock:
                current = self.check(ident, expected)
                old = next((s for s in current['sources'] if s['id'] == data.get('source')), None)
                # Links are not counted: a file of links adds as many as it holds. The ceiling
                # is for uploaded files and pasted text, which are kept whole in the draft.
                held = sum(s.get('kind') not in LINKS for s in current['sources'])
                require(old is not None or (operation == 'capture' and data.get('kind') == 'url') or held < MOST,
                        f'Use at most {MOST} files and pasted texts in one request. Links are not counted.')
                if operation == 'capture' and data.get('source') and data.get('kind') != 'saved':
                    require(old is not None and old.get('requested_url'), 'Choose a saved URL to retry.')
                    data = {'kind': 'url', 'url': old['requested_url']}
                if operation == 'tabs':
                    require(old is not None and old['kind'] in ('google-doc', 'google-slides'), 'Choose a Google source from this draft.')
                    data = {'kind': 'url', 'url': old['requested_url'], 'selected': data.get('selected')}
                    if old['kind'] == 'google-slides':
                        data['previous'] = self.previous(ident, old)
            captured = self.capture(data)
            # A changed choice that cannot be read keeps the earlier capture and says why.
            require(operation != 'tabs' or captured['status'] == 'ready',
                    (captured.get('problem') or 'This source could not be read.') + ' The earlier capture is kept.')
            with self.lock:
                current = self.check(ident, expected)
                captured['id'] = old['id'] if old else secrets.token_hex(16)
                if old and old.get('folder'):   # found in a folder: it keeps the name that says where
                    captured.update(name=old['name'], folder=old['folder'])
                current['sources'] = [s for s in current['sources'] if s['id'] != captured['id']]
                if captured.get('raw') is not None:
                    raw, text = captured.pop('raw'), captured.pop('text')
                    raw_name = 'captures/' + hashlib.sha256(raw).hexdigest() + '.raw'
                    text_name = 'captures/' + hashlib.sha256(text.encode()).hexdigest() + '.txt'
                    rc.write(self.folder(ident), raw_name, raw)
                    rc.write(self.folder(ident), text_name, text)
                    captured.update(original=raw_name, file=text_name,
                                    original_sha256=hashlib.sha256(raw).hexdigest(), sha256=hashlib.sha256(text.encode()).hexdigest())
                current['sources'].append(captured)
                self.save(current)
                if old:
                    used = {s.get(key) for s in current['sources'] for key in ('file', 'original')}
                    for key in ('file', 'original'):
                        if old.get(key) and old[key] not in used:
                            rc.inside(self.folder(ident), old[key]).unlink(missing_ok=True)
                return self.shown(current)
        with self.lock:
            current = self.check(ident, expected)
            if operation == 'configure':
                require(not set(data) - {'external', 'restricted', 'workers', 'focus'}, 'Keep supported research options only.')
                for key in ('external', 'restricted'):
                    if key in data: require(type(data[key]) is bool, 'Choose search permission explicitly.')
                if 'workers' in data: require(type(data['workers']) is int and 1 <= data['workers'] <= 3, 'Choose 1–3 research workers.')
                if 'focus' in data: require(isinstance(data['focus'], str) and len(data['focus']) <= 4000, 'Keep the research focus within 4,000 characters.')
                current.update(data)
                require(not current['restricted'] or current['sites'], 'Add approved sites in shared settings before restricting searches to them.')
            else:
                source = next((s for s in current['sources'] if s['id'] == data.get('source')), None)
                require(source is not None, 'Choose a source in this draft.')
                if operation == 'remove': current['sources'].remove(source)
                else: source['status'] = 'excluded'
            self.save(current)
            return self.shown(current)

    def previous(self, ident, source):
        """An earlier deck read's slide order and Google Drive version, from what is stored."""
        try:
            stored = json.loads(rc.inside(self.folder(ident), source['original']).read_bytes())
            version = stored.get('version')
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            version = None
        return {'version': version, 'slides': [t.get('id') for t in source.get('tabs', []) if isinstance(t, dict)]}

    def saved(self):
        """Bounded inventory of verified local results in this workspace. This never opens
        a folder picker or scans a personal folder or the network; a folder a person names
        on purpose is read by `add_folder`."""
        workspace = self.root.parent
        rows = []
        for category in ('blogs', 'articles', 'presentations', 'trainings', 'projects'):
            parent = workspace / category
            if not parent.is_dir() or parent.is_symlink(): continue
            for item in sorted(parent.iterdir())[:500]:
                if not item.is_dir() or item.is_symlink(): continue
                bundle = item / 'research'
                if not (bundle / 'output.json').is_file(): continue
                try:
                    facts, manifest = rc.read_bundle(bundle)
                    relative = str(bundle.relative_to(workspace))
                    rows.append({'id': digest(relative), 'revision': digest(manifest),
                        'name': facts.get('topic') or item.name, 'purpose': facts.get('purpose') or '',
                        'audience': facts.get('audience') or '', 'scope': facts.get('scope') or '', 'folder': relative})
                except (OSError, ValueError, KeyError): continue
        return rows

    def capture(self, data):
        kind = data.get('kind')
        name = data.get('name') or 'Pasted notes'
        source = {'name': name, 'kind': kind, 'origin': name, 'status': 'ready', 'warnings': [],
                  'tabs': [], 'selected_tabs': [], 'problem': None,
                  'captured_at': datetime.now(timezone.utc).isoformat()}
        try:
            if kind == 'saved':
                selected = next((s for s in self.saved() if s['id'] == data.get('source') and s['revision'] == data.get('revision')), None)
                require(selected is not None, 'This saved research changed or is unavailable. Choose its current reviewed revision.')
                bundle = rc.inside(self.root.parent, selected['folder'])
                facts, manifest = rc.read_bundle(bundle)
                body = {key: rc.inside(bundle, key + '.md').read_text() for key in ('brief', 'evidence', 'report')}
                raw = json.dumps({'research': facts, 'manifest': manifest, **body}, ensure_ascii=False).encode()
                extracted = {'text': '\n\n'.join(body.values()), 'warnings': [
                    'Previously reviewed for: ' + selected['purpose'] + '. Reused as selected reference material; new claims and purpose still need their own check.']}
                source.update(name=selected['name'], origin='Saved local research: ' + selected['folder'])
            elif kind == 'url':
                url = data.get('url')
                require(isinstance(url, str) and len(url) <= 4096, 'Give a document or public page link.')
                source['requested_url'] = url
                source['origin'] = url
                source['name'] = url   # a page that cannot be read is still listed by its address
                if urlsplit(url).hostname == 'docs.google.com':
                    found = self.google(url, account=self.account() if callable(self.account) else self.account,
                                        selected=data.get('selected'),
                                        **({'previous': data['previous']} if data.get('previous') else {}))
                    source.update({k: found[k] for k in ('name', 'kind', 'origin', 'tabs', 'selected_tabs')})
                    raw, extracted = found['raw'], found['extracted']
                else:
                    found = self.fetch(url)
                    raw = found['raw']
                    mime = found['mime'].split(';', 1)[0]
                    source.update(kind='url', name=page_name(raw, mime, found['url']), origin=found['url'])
                    require(mime in ('text/plain', 'text/html', 'application/pdf'), 'Use a readable text, HTML or PDF reference.')
                    extracted = self.extract(raw, {'text/plain': 'text', 'text/html': 'html', 'application/pdf': 'pdf'}[mime])
            elif kind == 'text':
                require(isinstance(data.get('text'), str), 'Paste readable source text.')
                raw = data['text'].encode('utf-8')
                extracted = self.extract(raw, 'text')
            elif kind == 'file':
                require(isinstance(name, str) and Path(name).name == name and '/' not in name and '\\' not in name,
                        'Choose a plain filename.')
                suffix = Path(name).suffix.lower()
                require(suffix in TYPES, 'Choose PDF, DOCX, PPTX, XLSX, text, Markdown or HTML.')
                encoded = data.get('content')
                require(isinstance(encoded, str) and len(encoded) <= 4 * ((LIMIT + 2) // 3), 'Choose a source within 8 MB.')
                try: raw = base64.b64decode(encoded, validate=True)
                except ValueError: raise ValueError('The uploaded file is not valid base64.') from None
                extracted = read(raw, TYPES[suffix], self.extract)
            else:
                raise ValueError('Add a link, file or pasted text.')
            require(type(raw) is bytes and 0 < len(raw) <= LIMIT, 'Choose nonempty source material within 8 MB.')
            text = extracted.get('text', '')
            require(isinstance(text, str) and 0 < len(text.encode()) <= LIMIT and text.strip(),
                    'This source contains no readable text. Use a text copy or exclude it.')
            # How much was read, so a row can say the page's text was fetched and not only its address.
            source.update(raw=raw, text=text, warnings=extracted.get('warnings', []), characters=len(text))
        except (ValueError, OSError) as error:
            source.update(status='needs-attention', problem=str(error))
        return source

    def add_folder(self, ident, expected, data, *, most=None, full=None, seconds=None):
        """Read every document in one folder a person named, as ordinary sources.

        `location` is a folder path on this computer or a Google Drive folder link or
        identity (`source_folders.location`). Each document found becomes a source of an
        existing kind, named by its path below the folder: a local or uploaded file is
        `file`, a Google Docs or Google Slides file is read as its own link is, and a
        Google Sheets file is a `file` named `<its name>.xlsx`: its .xlsx export, every
        sheet read (`xlsx_sheets`). A link to a shortcut is the folder it points to. One
        already here, by Google identity or by the SHA-256 of its bytes or text, is not
        added twice. The answer is the draft plus `folder`: how many were added and each
        one skipped with its reason (`source_folders.report`). Nothing is dropped unsaid.

        Bounds: `source_folders.FOLDER_DEPTH`, `FOLDER_LOOKED`, `FOLDER_MOST` and
        `FOLDER_SECONDS` for one add, LIMIT for one document and MOST for the files and
        pasted texts a draft holds. Adding the folder again continues where a bound stopped.
        A caller with less room gives `most`, the documents this add may take, and `full`,
        the sentence said of each one past it; `seconds` is its own reading time. `again`
        in the answer is True, and `next` a sentence saying so, when adding the same folder
        again reads more: some were not started in time or were past what one add takes.

        Reading is concurrent (`source_folders.FOLDER_WORKERS`), outside the draft lock;
        adoption rechecks the same revision, as `capture` does.
        """
        mine = full is None       # the limit of one add, which adding again gets past
        seconds = source_folders.FOLDER_SECONDS if seconds is None else seconds
        most = source_folders.FOLDER_MOST if most is None else max(0, min(most, source_folders.FOLDER_MOST))
        full = full or f'One folder add takes {most} documents. Add the folder again to read the next ones.'
        require(set(data) == {'location'}, source_folders.ASK)
        where, target = source_folders.location(data['location'])
        began = self.clock()
        with self.lock:
            current = self.check(ident, expected)
            held = sum(s.get('kind') not in LINKS for s in current['sources'])
            hashes = {s[key]: s.get('name') for s in current['sources'] for key in ('sha256', 'original_sha256') if s.get(key)}
            google_ids = {found.group(1) for found in (
                DRIVE_ORIGIN.match(str(s.get('origin') or '')) for s in current['sources']) if found}
        client = account = None
        if where == 'local':
            title = Path(os.path.realpath(target)).name or str(target)
            scan = source_folders.local(target, TYPES, LIMIT)
        else:
            account = self.account() if callable(self.account) else self.account
            client = self.drive(account)
            try:
                top = client.entry(target)
                pointed = top.get('shortcutDetails') if top.get('mimeType') == google_api.SHORTCUT_MIME else None
                if isinstance(pointed, dict) and pointed.get('targetMimeType') == google_api.FOLDER_MIME:
                    # The link is a shortcut to a folder: the folder it points to is scanned.
                    target = google_api.identifier(pointed.get('targetId'))
                    top = client.entry(target)
            except google_api.GoogleError as error:
                require(error.status != 404, 'No Google Drive folder with this link or identity is open to this '
                        'account. For a folder on this computer, give its whole path, starting from / or ~.')
                raise
            require(top.get('id') == target and top.get('mimeType') == google_api.FOLDER_MIME and not top.get('trashed'),
                    'This is not a Google Drive folder this account can open. ' + source_folders.LINK)
            title = source_folders.segment(top.get('name'))
            scan = source_folders.drive(client, target, TYPES, LIMIT)
        folder, taken, written = self.folder(ident), [], set()
        known, again = dict(hashes), False    # what the draft held before this add

        def read(item):
            try:
                return self.found(item, client, account, title, known)
            except Skipped as left:
                return left

        # Documents are read FOLDER_WORKERS at a time and settled one by one in the scan's
        # order, so what is added, what is skipped and which of two alike documents is kept
        # are what reading them one after another gives. A document is started only while
        # every one started before it could still be taken, so nothing is read to be thrown
        # away, and at most FOLDER_AHEAD wait their turn in memory.
        found, waiting, at, late = scan['found'], deque(), 0, False
        with ThreadPoolExecutor(max_workers=source_folders.FOLDER_WORKERS, thread_name_prefix='folder-read') as pool:
            while at < len(found) or waiting:
                while at < len(found):
                    item = found[at]
                    counted = item['kind'] not in ('document', 'presentation')
                    reads = [entry for entry in waiting if entry['read'] is not None]
                    state = None
                    if len(taken) < most:
                        late = late or self.clock() - began > seconds
                        if late:
                            state = 'out-of-time'       # not started in time
                        elif item.get('id') and item['id'] in google_ids:
                            state = 'duplicate'         # known by its Google identity: nothing is fetched
                        elif counted and held >= MOST:
                            state = 'full'
                        elif (len(reads) >= source_folders.FOLDER_AHEAD
                              or sum(not entry['read'].done() for entry in reads) >= source_folders.FOLDER_WORKERS
                              or len(taken) + len(reads) >= most
                              or counted and held + sum(entry['counted'] for entry in reads) >= MOST):
                            break                       # wait for one started earlier
                    waiting.append({'item': item, 'counted': counted, 'state': state,
                                    'read': pool.submit(read, item) if len(taken) < most and state is None else None})
                    at += 1
                entry = waiting[0]
                if entry['read'] is not None and not entry['read'].done():
                    # Its turn has not come: wait until any read still running ends, which
                    # either settles it or makes room to start another.
                    wait([one['read'] for one in waiting if one['read'] is not None and not one['read'].done()],
                         return_when=FIRST_COMPLETED)
                    continue
                waiting.popleft()
                item, counted = entry['item'], entry['counted']
                name = item['name']
                try:
                    if len(taken) >= most:
                        again = again or mine
                        raise Skipped('over-limit', full)
                    if entry['state'] == 'out-of-time':
                        again = True
                        raise Skipped('out-of-time', 'Add the folder again to read the rest.')
                    if entry['state'] == 'duplicate':
                        raise Skipped('duplicate')
                    if entry['state'] == 'full' or counted and held >= MOST:
                        raise Skipped('over-limit', f'These sources hold {MOST} files and pasted texts, the most one request takes.')
                    result = entry['read'].result()
                    if isinstance(result, Skipped):
                        # Bytes another document of this folder already gave are a duplicate
                        # before anything else is said of them, as they are read in order.
                        if result.code != 'duplicate' and result.mark in hashes:
                            raise Skipped('duplicate', same(hashes[result.mark]))
                        raise result
                    source, raw, text = result
                    marks = hashlib.sha256(raw).hexdigest(), hashlib.sha256(text.encode()).hexdigest()
                    for mark in marks:
                        if mark in hashes:
                            raise Skipped('duplicate', same(hashes[mark]))
                    source.update(original='captures/' + marks[0] + '.raw', file='captures/' + marks[1] + '.txt',
                                  original_sha256=marks[0], sha256=marks[1], folder=str(data['location']).strip()[:4096])
                    for kept, value in ((source['original'], raw), (source['file'], text)):
                        if not rc.inside(folder, kept).exists():
                            written.add(kept)
                        rc.write(folder, kept, value)
                except Skipped as left:
                    scan['skipped'].append(source_folders.skip(name, left.code, left.detail))
                    continue
                hashes.update(dict.fromkeys(marks, name))
                google_ids.update(filter(None, [item.get('id')]))
                held += counted
                taken.append(source)
        with self.lock:
            try:
                current = self.check(ident, expected)
            except ValueError:
                # Another view changed these sources while the folder was read: add nothing.
                used = {s.get(key) for s in self.load(ident)['sources'] for key in ('file', 'original')}
                for kept in written - used:
                    rc.inside(folder, kept).unlink(missing_ok=True)
                raise
            for source in taken:
                source['id'] = secrets.token_hex(16)
                current['sources'].append(source)
            if taken:
                self.save(current)
            return {**self.shown(current), 'folder': source_folders.report(
                scan, len(taken), where=where, title=title, again=again)}

    def found(self, item, client, account, title, held=None):
        """One document a folder scan found, read: its source row, original bytes and text.
        Raises Skipped with the reason when it cannot be taken. A file whose bytes are
        already held (`held`, SHA-256) is a duplicate before any text is extracted. Safe
        to call from several threads at once: it changes nothing it is given."""
        marked = []

        def fresh(data):
            mark = hashlib.sha256(data).hexdigest() if type(data) is bytes else None
            marked.append(mark)
            if mark in (held or {}):
                raise Skipped('duplicate', same(held[mark]), mark)
            return data

        def left(code, detail=''):
            return Skipped(code, detail, marked[0] if marked else None)
        kind, name = item['kind'], item['name']
        source = {'name': name, 'status': 'ready', 'warnings': [], 'tabs': [], 'selected_tabs': [],
                  'problem': None, 'captured_at': datetime.now(timezone.utc).isoformat()}
        try:
            if kind == 'local':
                with open(item['path'], 'rb') as handle:
                    raw = handle.read(LIMIT + 1)
                if len(raw) > LIMIT:
                    raise Skipped('too-large')
                extracted = read(fresh(raw), TYPES[item['suffix']], self.extract)
                # The folder's own name and the path below it say where this came from. The
                # whole path on this computer stays in the draft and is never cited.
                source.update(kind='file', origin=title + '/' + name, local_path=str(item['path']))
            elif kind in ('document', 'presentation'):
                url = 'https://docs.google.com/' + kind + '/d/' + item['id'] + '/edit'
                read_link = self.google(url, account=account, selected=None, client=client)
                source.update({key: read_link[key] for key in ('kind', 'origin', 'tabs', 'selected_tabs')},
                              requested_url=url)
                raw, extracted = read_link['raw'], read_link['extracted']
            elif kind == 'sheet':
                raw = client.export_workbook(item['id'])
                extracted = read(raw, 'xlsx', self.extract)
                source.update(kind='file', origin='https://docs.google.com/spreadsheets/d/' + item['id'] + '/edit')
            else:
                size = item.get('size')
                if size is None:   # reached through a shortcut, which does not say its size
                    stated = client.entry(item['id']).get('size')
                    size = int(stated) if isinstance(stated, str) and stated.isdigit() else 0
                if size > LIMIT:
                    raise Skipped('too-large')
                raw = client.download(item['id'])
                if len(raw) > LIMIT:
                    raise Skipped('too-large')
                extracted = read(fresh(raw), TYPES[item['suffix']], self.extract)
                source.update(kind='file', origin='https://drive.google.com/file/d/' + item['id'] + '/view')
            text = extracted.get('text', '')
            if type(raw) is not bytes or not raw:
                raise Skipped('unreadable', 'It is empty.')
            if not isinstance(text, str) or not text.strip():
                raise Skipped('unreadable', 'It contains no readable text.')
            if len(raw) > LIMIT or len(text.encode()) > LIMIT:
                raise Skipped('too-large')
        except Skipped as skipped:
            skipped.mark = skipped.mark or (marked[0] if marked else None)
            raise
        except google_api.GoogleError as error:
            raise left('no-permission' if error.status in (403, 404) else 'unreadable', str(error)) from None
        except PermissionError:
            raise left('no-permission') from None
        except (ValueError, OSError) as error:
            raise left('unreadable', str(error) if isinstance(error, ValueError) else '') from None
        source.update(warnings=extracted.get('warnings', []), characters=len(text))
        return source, raw, text

    def preview(self, ident, source_id):
        with self.lock:
            value = self.load(ident)
            source = next((s for s in value['sources'] if s['id'] == source_id), None)
            require(source is not None and source['status'] == 'ready', 'Choose a readable source to preview.')
            text = rc.inside(self.folder(ident), source['file']).read_text()
            require(hashlib.sha256(text.encode()).hexdigest() == source['sha256'], 'This source capture changed. Read it again.')
            return {'source': source_id, 'text': text[:20_000], 'total': len(text), 'warnings': source['warnings']}

    def prepared(self, ident, expected, *, primary=False):
        """Trusted server-side start handoff; paths/bytes never come from browser IDs."""
        with self.lock:
            value = self.check(ident, expected)
            require(all(s['status'] in ('ready', 'excluded') for s in value['sources']),
                    'Retry, remove or explicitly exclude unreadable sources before starting.')
            ready = [s for s in value['sources'] if s['status'] == 'ready']
            require(primary or ready or value['external'], 'Add a source or allow additional external search.')
            require(over(ready) is None, over(ready))
            offered = []
            for source in ready:
                folder = self.folder(ident)
                text = rc.inside(folder, source['file']).read_text()
                raw = rc.inside(folder, source['original']).read_bytes()
                require(hashlib.sha256(text.encode()).hexdigest() == source['sha256']
                        and hashlib.sha256(raw).hexdigest() == source['original_sha256'],
                        'A selected source changed. Read it again before starting.')
                offered.append({**source, 'title': source['name'], 'text': text, 'permission': 'selected',
                    'path': rc.inside(folder, source['file']), 'original_path': rc.inside(folder, source['original'])})
            choice = {'documents': bool(ready) or primary, 'sites': value['sites'] if value['external'] and value['restricted'] else [],
                      'web': value['external'] and not value['restricted']}
            return {'id': ident, 'revision': expected, 'sources': offered, 'research_from': choice,
                    'workers': value['workers'], 'focus': value['focus']}

    def dispatch(self, sent):
        require(isinstance(sent, dict), 'Send one source request.')
        sent = dict(sent)
        action = sent.pop('action', None)
        if action == 'saved':
            require(not sent, 'List the reviewed local research only.')
            return {'items': [{k:v for k,v in item.items() if k != 'folder'} for item in self.saved()]}
        if action == 'create':
            require(not sent, 'Create the source draft before adding material.')
            from studio_core import studios_config
            shared, _ = studios_config.read()
            return self.create(sites=research_sites.defaults(shared))
        ident = sent.pop('id', None)
        if action == 'read':
            require(not sent, 'Read one source draft.')
            return self.read(ident)
        if action == 'preview':
            require(set(sent) == {'source'}, 'Choose one source to preview.')
            return self.preview(ident, sent['source'])
        expected = sent.pop('expected', None)
        return self.mutate(ident, expected, action, **sent)


def install(prepared, root):
    """Keep an exact private input snapshot with the new studio item, before dispatch."""
    root = Path(root)
    rc.write(root, 'sources/research-inputs/.gitignore', '*\n')
    rows = []
    for source in prepared['sources']:
        ident = source['id']
        suffix = Path(source['name']).suffix.lower() if source['kind'] == 'file' else '.raw'
        suffix = suffix if re.fullmatch(r'\.[a-z0-9]{1,10}', suffix) else '.raw'
        original = 'sources/research-inputs/' + ident + '.original' + suffix
        file = 'sources/research-inputs/' + ident + '.txt'
        raw = Path(source['original_path']).read_bytes()
        text = source['text']
        require(hashlib.sha256(raw).hexdigest() == source['original_sha256']
                and hashlib.sha256(text.encode()).hexdigest() == source['sha256'],
                'The source changed while starting; reload the source preview.')
        rc.write(root, original, raw)
        rc.write(root, file, text)
        rows.append({k: source[k] for k in ('id', 'name', 'kind', 'origin', 'warnings', 'tabs', 'selected_tabs',
            'captured_at', 'sha256', 'original_sha256') if k in source})
        rows[-1].update(file=file, original=original)
    value = {'schema': 1, 'owner': 'studio-research-inputs', 'sources': rows,
             'research_from': prepared['research_from'], 'workers': prepared['workers'], 'focus': prepared['focus']}
    rc.write(root, 'sources/research-inputs/manifest.json', json.dumps(value))
    return {'schema': 1, 'digest': digest(value), 'count': len(rows),
            'workers': prepared['workers'], 'focus': prepared['focus']}


def _manifest_sources(root, saved):
    root = Path(root)
    file = root / 'sources/research-inputs/manifest.json'
    if not file.exists():
        require(not saved, 'This computer does not have the selected research inputs. Add their permitted copies before resuming.')
        return []
    value = json.loads(rc.inside(root, 'sources/research-inputs/manifest.json').read_text())
    require(value.get('schema') == 1 and value.get('owner') == 'studio-research-inputs'
            and (not saved or saved.get('digest') == digest(value)), 'The saved research inputs changed; reload them before starting.')
    return value['sources']


def _verified_sources(root, saved, *, include_text):
    for source in _manifest_sources(root, saved):
        # Text-mode reads preserve the original newline normalization used for these hashes.
        text_digest = hashlib.sha256()
        parts = []
        with rc.inside(root, source['file']).open('r') as stream:
            for chunk in iter(lambda: stream.read(64 * 1024), ''):
                text_digest.update(chunk.encode())
                if include_text:
                    parts.append(chunk)
        original = rc.inside(root, source['original'])
        with original.open('rb') as stream:
            original_digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            size = os.fstat(stream.fileno()).st_size
        require(text_digest.hexdigest() == source['sha256'] and original_digest == source['original_sha256'],
                'A saved source capture changed; read it again.')
        yield source, original, size, ''.join(parts)


def sources(root, saved=None):
    plan, offered = [], []
    for source, original, _, text in _verified_sources(root, saved, include_text=True):
        plan.append({'id': source['id'], 'title': source['name'], 'origin': source['origin'],
            'original_file': source['original'], 'file': source['file'],
            'limits': '; '.join(source['warnings']) or 'none'})
        offered.append({'title': source['name'], 'origin': source['origin'], 'permission': 'selected',
            'text': text, 'file': source['file'], 'original': source['original'],
            'original_path': original, 'supplied': source['id'],
            'accessed_at': source['captured_at']})
    return plan, offered


def document_entries(root, saved):
    """Readable, confirmed captures for native intake/readiness, without copying them.

    Only a recorded input reference grants selection. Recheck its manifest and bytes;
    unavailable private captures must not silently become a web-only request.
    """
    if not saved:
        return []
    try:
        return [{'name': source['name'], 'bytes': size,
                 'readable': True, 'problem': None, 'research_input': True}
                for source, _, size, _ in _verified_sources(root, saved, include_text=False)]
    except (OSError, ValueError) as error:
        return [{'name': 'Previously selected sources', 'readable': False,
                 'problem': str(error), 'research_input_missing': True}]


def prepare_start(workspace, reference, *, primary=False):
    require(isinstance(reference, dict) and set(reference) == {'id', 'expected'}, 'Choose this source draft and its current revision.')
    return Sources(Path(workspace) / '.research-sources').prepared(reference['id'], reference['expected'], primary=primary)


class Start:
    """One source-backed form submission, including reply loss, creates one local item.

    A separate draft-scoped lock spans native creation. The receipt is recorded
    before the native engine dispatches jobs. Source edits keep their own lock.
    """
    def __init__(self, workspace, reference, details):
        self.workspace = Path(workspace).resolve()
        self.sources = Sources(self.workspace / '.research-sources')
        require(isinstance(reference, dict) and set(reference) == {'id', 'expected'},
                'Choose this source draft and its current revision.')
        self.reference = dict(reference)
        self.folder = self.sources.folder(reference['id'])
        self.key = digest([reference['expected'], details])
        self.file = 'starts/' + self.key + '.json'
        self.lock = ProcessRLock(lambda: self.folder / 'starts.lock', refusal=ValueError)

    def __enter__(self):
        require(self.lock.acquire(), 'Another start from these sources is still being recorded. Wait, then retry the same form.')
        try:
            with self.sources.lock:
                self.sources.check(self.reference['id'], self.reference['expected'])
            return self
        except BaseException:
            self.lock.release()
            raise

    def __exit__(self, *args):
        self.lock.release()

    def previous(self):
        path = rc.inside(self.folder, self.file)
        if not path.exists(): return None
        value = json.loads(path.read_text())
        require(value.get('schema') == 1 and value.get('request') == self.key,
                'This source-backed start receipt is unreadable; preserve it before retrying.')
        result = value['result']
        target = Path(result['path'])
        require(target.is_absolute() and target.is_relative_to(self.workspace), 'The saved start belongs to another workspace.')
        target = rc.inside(self.workspace, str(target.relative_to(self.workspace)))
        require(target.is_dir(), 'This request already started an item that is no longer here. Open its workspace or start with a new source draft.')
        return result

    def keep(self, result):
        rc.write(self.folder, self.file, json.dumps({'schema':1,'request':self.key,'result':result}))
