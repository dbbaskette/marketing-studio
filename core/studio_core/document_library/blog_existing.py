"""Blog Studio's existing work, read for Add existing work to library: never changed.

What is offered
---------------
Blog Studio's team library keeps each finished or published blog, and each kept upload,
link, Google Doc and imported post, as a source record with its text (`content.md`), its
original file when it had one, and a revision. Only those records on this computer are read:

    <workspace>/sources/<id>/record.json            # a plain writing folder
    <workspace>/.shared/references/<id>/record.json # a team workspace (hub.json)

- A finished blog (`library.origin_kind` written-here) is offered under `blog:<blog id>`,
  the key Blog Studio's Finish and publish keep it under, so finishing it again later
  reuses the same library document.
- Every other team library item is offered under `blog:reference.<source id>`: an imported
  post as a Blog, everything else as an Uploaded document.
- What Blog Studio calls it travels with it, as `native`: its source ID and revision, its
  purposes and role (facts, approved messaging, an example, a voice or style sample), its
  kind of post, its author and, for a finished blog, the blog's voice and style pins.

Left alone: files uploaded for one blog (material, including copies taken from the Document
Library), pinned Team Hub snapshots, items only the Team Hub holds, items retired in the team
library, records of a shape Blog Studio does not save, and anything whose text or file does
not match its record. (adopt.py also shows a file Keep in library already kept as there.) No record is written, no lock is taken, no Team Hub,
Git, network, assistant or reader program is used, and every read is bounded and refuses
links.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from .store import ENDINGS, LIMITS, TITLE, _plain

NAME = re.compile(r'^[a-z0-9][a-z0-9-]{0,79}$')
RECORD = 256_000
SESSION = 2_000_000
ENTRIES = 2_000           # folders one scan looks at
ORIGINS = {'upload': 'upload', 'link': 'link', 'google-doc': 'google', 'import': 'imported',
           'written-here': 'created'}
ROLES = {'example': 'Example of the kind of post', 'messaging': 'Approved messaging',
         'facts': 'Facts', 'voice-sample': 'Voice sample', 'style-sample': 'Style sample'}


def _bounded(path: Path, limit: int) -> bytes | None:
    """A file's bytes, or None when it is a link, not a file or larger than `limit`."""
    try:
        if path.is_symlink() or not path.is_file():
            return None
        with open(path, 'rb') as stream:
            data = stream.read(limit + 1)
    except OSError:
        return None
    return data if len(data) <= limit else None


def _json(path: Path, limit: int = RECORD):
    data = _bounded(path, limit)
    try:
        found = json.loads(data.decode('utf-8')) if data is not None else None
    except (UnicodeDecodeError, ValueError):
        return None
    return found if isinstance(found, dict) else None


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _role(purposes) -> str:
    """As Blog Studio's team library lists it (blog_library.role_of)."""
    if 'inspiration' in purposes:
        return 'example'
    if 'messaging' in purposes:
        return 'messaging'
    if 'reference' not in purposes:
        for purpose in ('voice-sample', 'style-sample'):
            if purpose in purposes:
                return purpose
    return 'facts'


def layout(root) -> dict | None:
    """Where this workspace keeps its team library and its blogs, or None when it is not a
    Blog Studio workspace this can read."""
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        return None
    marker = _json(root / 'hub.json')
    team = bool(marker and marker.get('tool') == 'blog-studio')
    if team:
        sources, articles = root / '.shared' / 'references', root
    else:
        if not (root / 'studio.json').is_file() and not (root / 'sources').is_dir():
            return None
        sources, articles = root / 'sources', root / 'articles'
    for folder in (sources.parent, sources, articles):
        if folder.is_symlink():
            return None
    return {'root': root, 'team': team, 'sources': sources, 'articles': articles}


def _folders(parent: Path) -> tuple[list[Path], bool]:
    """Folders named as Blog Studio names its records, sorted; and whether there were more
    than one scan reads."""
    if parent.is_symlink() or not parent.is_dir():
        return [], False
    found, more = [], False
    try:
        with os.scandir(parent) as entries:
            for entry in entries:
                if NAME.match(entry.name) and entry.is_dir(follow_symlinks=False):
                    if len(found) >= ENTRIES:
                        more = True
                        break
                    found.append(Path(entry.path))
    except OSError:
        return [], False
    return sorted(found), more


def _blog(places: dict, ident: str) -> dict:
    """What a finished blog's own record says of its voice and style, when it can be read."""
    if not NAME.match(ident or ''):
        return {}
    folder = places['articles'] / ident
    if folder.is_symlink():
        return {}
    session = _json(folder / 'session.json', SESSION) or {}
    kept = {}
    voice = session.get('voice')
    if isinstance(voice, dict):
        kept['voice'] = {key: voice[key] for key in ('mode', 'profile_id', 'revision', 'tone')
                         if isinstance(voice.get(key), (str, int)) and not isinstance(voice.get(key), bool)}
    style = session.get('style')
    if isinstance(style, dict):
        kept['style'] = {key: style[key] for key in ('style_id', 'revision', 'name')
                         if isinstance(style.get(key), (str, int)) and not isinstance(style.get(key), bool)}
    return kept


def _original(folder: Path, record: dict) -> tuple[bytes | None, str | None, str | None]:
    """(bytes, file name, why it was left out) of a record's original file."""
    name = record.get('original_path')
    if not name:
        return None, None, None
    if not isinstance(name, str) or '/' in name or name.startswith('.') \
            or Path(name).suffix.lower() not in ENDINGS:
        return None, None, 'Its original file is of a kind the library does not keep, so only its text is added.'
    data = _bounded(folder / name, LIMITS['bytes'])
    if data is None:
        return None, None, ('Its original file is missing or larger than 8 MB, so only its '
                            'text is added.')
    if _sha(data) != record.get('original_sha256'):
        return None, None, ('Its original file does not match its record, so only its text '
                            'is added.')
    shown = record.get('original_filename')
    ending = Path(name).suffix.lower()
    if not isinstance(shown, str) or '/' in shown or '\\' in shown or ':' in shown \
            or shown.startswith('.') or Path(shown).suffix.lower() != ending \
            or not 1 <= len(shown) <= 120 or not shown.isprintable():
        shown = 'original' + ending
    return data, shown, None


def _candidate(places: dict, folder: Path) -> tuple[dict | None, str | None]:
    """One team library item as something to add, or (None, why it is left out)."""
    record = _json(folder / 'record.json')
    if record is None:
        return None, None      # not a record this can read: not counted as existing work
    title = _plain(record.get('name'), TITLE) or folder.name
    purposes = record.get('purposes') if isinstance(record.get('purposes'), list) else []
    if record.get('id') != folder.name or 'material' in purposes or record.get('pinned_reference') \
            or record.get('document_library'):
        return None, None      # one blog's own file, a Team Hub snapshot, or a library copy
    held = record.get('library') if isinstance(record.get('library'), dict) else {}
    if held.get('curation') == 'retired':
        return None, (f'“{title[:120]}” was left out: it is retired in Blog Studio’s team '
                      'library. Make it active there to add it.')
    kind_of = held.get('origin_kind') if isinstance(held.get('origin_kind'), str) \
        and held.get('origin_kind') in ORIGINS else None
    revision = record.get('revision') if type(record.get('revision')) is int else None
    text = ''
    content = folder / 'content.md'
    if content.exists() or content.is_symlink():
        data = _bounded(content, LIMITS['text'])
        if data is None:
            return None, f'“{title[:120]}” was left out: its text is missing, linked or too long.'
        if _sha(data) != record.get('content_sha256'):
            return None, (f'“{title[:120]}” was left out: its text does not match its record. '
                          'Open Blog Studio once, then preview again.')
        try:
            text = data.decode('utf-8')
        except UnicodeDecodeError:
            return None, f'“{title[:120]}” was left out: its text could not be read.'
    readable = record.get('status') == 'ready' and bool(text.strip())
    original, filename, problem = _original(folder, record)
    gaps = [problem] if problem else []
    if not readable:
        text = ''
        gaps.append('Blog Studio has no readable text for it, so it needs text before a '
                    'project can use it.')
    if not readable and original is None:
        return None, f'“{title[:120]}” was left out: it has no text or file to add.'
    role = _role(purposes)
    native = {'studio': 'blog', 'record': 'team-library', 'source': folder.name,
              'revision': revision, 'purposes': [p for p in purposes if isinstance(p, str)][:10],
              'role': role, 'origin_kind': kind_of,
              'post_kind': held.get('kind') if isinstance(held.get('kind'), str) else None,
              'author': record.get('author') if isinstance(record.get('author'), str) else None,
              'workspace': 'team' if places['team'] else 'local'}
    article = held.get('article')
    finished = kind_of == 'written-here' and isinstance(article, str) and bool(NAME.match(article))
    if finished:
        blog = _blog(places, held['article'])
        native.update(blog=held['article'], **blog)
        key, kind, origin = 'blog:' + held['article'], 'blog', 'created'
        project = {'id': held['article'], 'title': title, 'revision': revision}
        notes = ['Blog Studio keeps no PDF of a blog, so it is added as Markdown.']
    else:
        key = 'blog:reference.' + folder.name
        kind = 'blog' if kind_of == 'import' else 'upload'
        origin = ORIGINS.get(kind_of or '', 'imported')
        project = None
    note = 'Finished blog' if finished else ROLES[role]
    notes = notes if finished else []
    return {'key': key, 'studio': 'blog', 'kind': kind, 'origin': origin, 'title': title,
            'author': native['author'], 'text': text, 'original': original,
            'markdown_sha': _sha(text.encode('utf-8')) if text else None,
            'original_sha': _sha(original) if original is not None else None,
            'filename': filename, 'project': project, 'native': native, 'gaps': gaps,
            'notes': notes, 'note': note, 'folder': folder}, None


def _checked(places: dict, folder: Path) -> tuple[dict | None, str | None]:
    """_candidate, with a record of an unexpected shape left out and said, never raised:
    one odd record never stops the rest of the preview."""
    try:
        return _candidate(places, folder)
    except (TypeError, ValueError, AttributeError, KeyError, OSError):
        return None, (f'“{folder.name}” was left out: its record is not in a shape Blog '
                      'Studio saves.')


def load(root, candidate: dict) -> dict:
    """The candidate read again with its text and original, refused when either is no
    longer what the preview read."""
    places = layout(root)
    found, _ = _checked(places, candidate['folder']) if places else (None, None)
    if not found or found['key'] != candidate['key'] \
            or found['markdown_sha'] != candidate['markdown_sha'] \
            or found['original_sha'] != candidate['original_sha'] \
            or found['title'] != candidate['title']:
        raise ValueError(f'“{candidate["title"][:120]}” changed in Blog Studio after the preview.')
    return found


def scan(root, content: bool = False) -> dict:
    """{'candidates', 'gaps', 'more', 'readable'}: the workspace's team library items to
    offer, with the hashes of their text and original as read now (and the text and bytes
    themselves only with `content`), and what was left out and why."""
    places = layout(root)
    if places is None:
        return {'candidates': [], 'gaps': ['This folder is not a Blog Studio workspace this '
                                           'computer can read, so nothing in it was offered.'],
                'more': False, 'readable': False}
    folders, more = _folders(places['sources'])
    candidates, gaps = [], []
    for folder in folders:
        found, why = _checked(places, folder)
        if found:
            if not content:
                found['text'], found['original'] = None, None
            candidates.append(found)
        elif why:
            gaps.append(why)
    if places['team']:
        gaps.append('Items only your Team Hub holds, not yet on this computer, are not read. '
                    'Open them in Blog Studio first to add them here.')
    if more:
        gaps.append(f'Only the first {ENTRIES} team library folders were looked at.')
    return {'candidates': candidates, 'gaps': gaps, 'more': more, 'readable': True}
