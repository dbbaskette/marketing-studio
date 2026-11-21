"""Find the documents in one folder a person named, on this computer or in Google Drive.

A person gives one folder path or one Google Drive folder link, on purpose, in the shared
source editor. This module only lists what the folder holds; `research_sources.Sources`
reads each document found and keeps it as an ordinary source. Nothing here scans on its
own, writes to Google or follows a path the person did not name.

- `location(value)` says which kind of folder was given: `('local', Path)` or
  `('drive', folder id)`.
- `local(root, types, limit)` walks a folder on this computer; `drive(client, id, types,
  limit)` lists a Google Drive folder through the fixed-destination client. Both return
  `{'found', 'skipped', 'hidden', 'looked', 'stopped'}`.
- A found document is `{'name', 'kind', ...}`: `name` is its path below the folder, and
  `kind` is `local`, `document`, `presentation`, `sheet` or `drive-file`.
- Everything not taken is a row in `skipped`: `{'name', 'code', 'reason'}`. Hidden files
  and folders (a leading dot) are not looked at and are only counted.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
from urllib.parse import urlsplit

from studio_core.google_api import (DOC_MIME, DOCX_MIME, FOLDER_MIME, PPTX_MIME, SHEET_MIME,
                                    SHORTCUT_MIME, SLIDES_MIME, XLSX_MIME, GoogleError)

FOLDER_DEPTH = 6       # Folders below the one named that a scan goes into.
FOLDER_MOST = 200      # Documents one folder add takes; adding the folder again takes the next ones.
FOLDER_LOOKED = 2000   # Files and folders one scan looks at before it stops and says so.
FOLDER_SECONDS = 150   # Reading time for one folder add, inside the 240 seconds the phone bridge allows.
FOLDER_WORKERS = 8     # Documents read at the same time; each is a few Google requests or one file.
FOLDER_AHEAD = 16      # Documents started or read and waiting their turn, each held in memory until then.
FOLDER_REPORTED = 500  # Skipped documents listed by name; every one is still counted by reason.

REASONS = {
    'unsupported': 'Not a type that can be read.',
    'too-large': 'Larger than 8 MB.',
    'unreadable': 'Could not be read.',
    'duplicate': 'Already a source here.',
    'repeat': 'Appears more than once in this folder.',
    'over-limit': 'Over the limit.',
    'no-permission': 'No permission to read it.',
    'outside': 'A link that leads outside the folder.',
    'too-deep': 'More than ' + str(FOLDER_DEPTH) + ' folders deep.',
    'out-of-time': 'Not read in time.',
}
ASK = 'Give a folder path on this computer or a Google Drive folder link.'
LINK = ('Paste the link of a Google Drive folder, which starts with '
        'https://drive.google.com/drive/folders/. Add a single document with the links above.')
DRIVE_LINK = re.compile(r'/drive/(?:u/[0-9]+/)?(?:mobile/)?folders/([A-Za-z0-9_-]{10,200})/?')
DRIVE_ID = re.compile(r'[A-Za-z0-9_-]{16,200}')
FILE_ID = re.compile(r'[A-Za-z0-9_-]{1,200}')
GOOGLE = {DOC_MIME: 'document', SLIDES_MIME: 'presentation', SHEET_MIME: 'sheet'}
# An uploaded Drive file named without an extension is read by what Google says it is.
MIMES = {'application/pdf': '.pdf', DOCX_MIME: '.docx', PPTX_MIME: '.pptx', XLSX_MIME: '.xlsx',
         'text/plain': '.txt', 'text/markdown': '.md', 'text/html': '.html'}
LOOP = 'It leads back to a folder already scanned.'


def require(value, message):
    if not value:
        raise ValueError(message)


def skip(name, code, detail=''):
    """One row of what a folder add did not take, with a plain reason."""
    return {'name': name, 'code': code, 'reason': REASONS[code] + (' ' + detail if detail else '')}


def location(value):
    """Which folder a person gave: `('local', Path)` or `('drive', folder id)`."""
    require(isinstance(value, str) and 0 < len(value.strip()) <= 4096 and '\x00' not in value, ASK)
    value = value.strip()
    if len(value) > 1 and value[0] == value[-1] and value[0] in '\'"':
        value = value[1:-1].strip()   # a path copied with its quotation marks
    if re.match(r'https?://', value, re.I):
        try:
            parts = urlsplit(value)
        except ValueError:
            raise ValueError(LINK) from None
        found = DRIVE_LINK.fullmatch(parts.path)
        require(parts.scheme == 'https' and parts.netloc == 'drive.google.com' and found, LINK)
        return 'drive', found.group(1)
    if DRIVE_ID.fullmatch(value):
        return 'drive', value
    try:
        path = Path(value).expanduser()
    except (RuntimeError, ValueError):
        raise ValueError(ASK) from None
    require(path.is_absolute(), 'Give the whole folder path, starting from / or ~, or a Google Drive folder link.')
    try:
        present = path.is_dir()
    except OSError:
        present = False
    require(present, 'This folder was not found on this computer. Check the path and try again.')
    return 'local', path


def started():
    return {'found': [], 'skipped': [], 'hidden': 0, 'looked': 0, 'stopped': False}


def local(root, types, limit, *, depth=FOLDER_DEPTH, looked=FOLDER_LOOKED):
    """Every supported file below `root`, files before subfolders, each in name order.

    Hidden files and folders are not looked at. A link is followed only while it stays
    inside the folder, and a folder is gone into once, so a loop of links ends.
    """
    top = Path(os.path.realpath(root))
    scan = started()
    folders, files = {top}, set()

    def walk(folder, prefix, level):
        try:
            with os.scandir(folder) as listing:
                entries = sorted(listing, key=lambda entry: (entry.name.casefold(), entry.name))
        except OSError as error:
            scan['skipped'].append(skip(prefix or top.name + '/',
                'no-permission' if isinstance(error, PermissionError) else 'unreadable'))
            return
        below = []
        for entry in entries:
            if entry.name.startswith('.'):
                scan['hidden'] += 1
                continue
            if scan['looked'] >= looked:
                scan['stopped'] = True
                return
            scan['looked'] += 1
            name = prefix + entry.name
            try:
                real = Path(os.path.realpath(entry.path))
                if entry.is_symlink() and real != top and top not in real.parents:
                    scan['skipped'].append(skip(name, 'outside'))
                    continue
                if real.is_dir():
                    below.append((name + '/', real))
                    continue
                if not real.is_file():
                    scan['skipped'].append(skip(name, 'unreadable' if entry.is_symlink() else 'unsupported'))
                    continue
                size = real.stat().st_size
            except OSError as error:
                scan['skipped'].append(skip(name,
                    'no-permission' if isinstance(error, PermissionError) else 'unreadable'))
                continue
            suffix = Path(entry.name).suffix.lower()
            if suffix not in types:
                scan['skipped'].append(skip(name, 'unsupported'))
            elif size > limit:
                scan['skipped'].append(skip(name, 'too-large'))
            elif real in files:
                scan['skipped'].append(skip(name, 'repeat'))
            else:
                files.add(real)
                scan['found'].append({'name': name, 'kind': 'local', 'path': real, 'suffix': suffix})
        for name, real in below:
            if scan['stopped']:
                return
            if real in folders:
                scan['skipped'].append(skip(name, 'repeat', LOOP))
            elif level + 1 > depth:
                scan['skipped'].append(skip(name, 'too-deep'))
            else:
                folders.add(real)
                walk(real, name, level + 1)

    walk(top, '', 0)
    return scan


def segment(value):
    """One name in a path below the folder; a slash in a Google Drive name is not a folder."""
    text = ''.join(c for c in str(value or '') if ord(c) >= 32 and ord(c) != 127).strip()
    return (text or 'Untitled')[:200].replace('/', '-').replace('\\', '-')


def drive(client, folder_id, types, limit, *, depth=FOLDER_DEPTH, looked=FOLDER_LOOKED):
    """Every readable document below a Google Drive folder, shared drives included.

    Each folder is listed page by page. A shortcut stands for what it points to: a
    shortcut to a folder is gone into, one to a file is that file. A folder or file is
    taken once by its Google identity, so a loop of shortcuts ends. Listing the named
    folder itself must work; a subfolder that cannot be listed is a skipped row.
    """
    scan = started()
    folders, files = {folder_id}, set()

    def listed(ident):
        items, token = [], None
        while True:
            page = client.children(ident, token)
            items.extend(item for item in page['files'] if isinstance(item, dict))
            token = page.get('nextPageToken')
            if not token or scan['looked'] + len(items) > looked:
                return items

    def walk(ident, prefix, level):
        try:
            items = listed(ident)
        except GoogleError as error:
            if not prefix:
                raise
            scan['skipped'].append(skip(prefix,
                'no-permission' if error.status in (403, 404) else 'unreadable', str(error)))
            return
        items.sort(key=lambda item: (str(item.get('name') or '').casefold(),
                                     str(item.get('name') or ''), str(item.get('id') or '')))
        below = []
        for item in items:
            if scan['looked'] >= looked:
                scan['stopped'] = True
                return
            scan['looked'] += 1
            name = prefix + segment(item.get('name'))
            file_id, mime, size = item.get('id'), item.get('mimeType'), item.get('size')
            if mime == SHORTCUT_MIME:
                target = item.get('shortcutDetails')
                target = target if isinstance(target, dict) else {}
                file_id, mime, size = target.get('targetId'), target.get('targetMimeType'), None
            if not isinstance(file_id, str) or not FILE_ID.fullmatch(file_id) or not isinstance(mime, str):
                scan['skipped'].append(skip(name, 'unreadable', 'Google did not say what it points to.'))
                continue
            if mime == FOLDER_MIME:
                below.append((name + '/', file_id))
                continue
            if file_id in files:
                scan['skipped'].append(skip(name, 'repeat'))
                continue
            kind, suffix = GOOGLE.get(mime), ''
            if kind == 'sheet':     # read from its .xlsx export, and named as that file
                name, suffix = name + '.xlsx', '.xlsx'
            if kind is None:
                if mime.startswith('application/vnd.google-apps.'):
                    scan['skipped'].append(skip(name, 'unsupported',
                        'Among Google files, only Google Docs, Google Slides and Google Sheets are read.'))
                    continue
                suffix = Path(name).suffix.lower()
                if suffix not in types:
                    suffix = MIMES.get(mime.split(';', 1)[0].strip().lower(), '')
                    if suffix not in types:
                        scan['skipped'].append(skip(name, 'unsupported'))
                        continue
                    name += suffix
                size = int(size) if isinstance(size, str) and size.isdigit() else None
                if size is not None and size > limit:
                    scan['skipped'].append(skip(name, 'too-large'))
                    continue
                kind = 'drive-file'
            files.add(file_id)
            scan['found'].append({'name': name, 'kind': kind, 'id': file_id, 'suffix': suffix,
                                  'size': size if kind == 'drive-file' else None})
        for name, child in below:
            if scan['stopped']:
                return
            if child in folders:
                scan['skipped'].append(skip(name, 'repeat', LOOP))
            elif level + 1 > depth:
                scan['skipped'].append(skip(name, 'too-deep'))
            else:
                folders.add(child)
                walk(child, name, level + 1)

    walk(folder_id, '', 0)
    return scan


AGAIN = 'Add the same folder again to read the next ones.'


def report(scan, added, *, where, title, again=False):
    """What one folder add did, for the person: how many were added and every one skipped."""
    skipped = scan['skipped']
    reasons = {}
    for row in skipped:
        reasons[row['code']] = reasons.get(row['code'], 0) + 1
    return {'where': where, 'title': title, 'found': len(scan['found']), 'added': added,
            'skipped': skipped[:FOLDER_REPORTED], 'skipped_count': len(skipped),
            'unlisted': max(0, len(skipped) - FOLDER_REPORTED), 'reasons': reasons,
            'hidden': scan['hidden'], 'again': bool(again), 'next': AGAIN if again else None,
            'stopped': ('The scan stopped after looking at ' + format(scan['looked'], ',')
                        + ' files and folders. Add a smaller folder to read the rest.')
                       if scan['stopped'] else None}
