"""Blog Studio and the shared Document Library (studio_core.document_library), which every
studio on this computer reads. It is not the team library: nothing here is shared.

What a caller needs to know
---------------------------
    shared_library.BROWSE                  # the page's browsing routes, read without the lock
    shared_library.browse(route, data)     # one of them: catalog, preview, filters, matching
    shared_library.take(root, data)        # under the studio lock: chosen revisions, as files
    shared_library.keep_blog(root, record, text, source)   # a finished blog, kept there too

- Taking a document makes it a file uploaded for one blog: a `material` source in the
  upload area, with the role chosen for it (facts, approved messaging or an example), its
  library ID and revision recorded, and its text copied from the pinned revision. The page
  then uses it as it uses any uploaded file, so the blog's own pins, roles, limits and
  research permissions apply unchanged, and an example stays an example. It is never put
  in the team library or the Team Hub by this.
- A finished blog is kept as Markdown under `blog:<blog id>`: finishing or publishing
  again reuses its document and adds a revision only when the text changed. What happens
  is reported, never raised: the blog's own Finish and publish stand either way.
- Nothing here starts research, an assistant or analysis, or uses the network.
"""

from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace

import studio
from hub_store import encoded, sha
from studio_core import document_library
from studio_core.document_library import context

# The page's routes are these with `document-` in front, so they never meet the team
# library's own `library` routes.
BROWSE = {'document-' + path[len('/api/') :]: path for path in context.ROUTES}
TAKE = 'document-library-take'
ROLES = {
    'facts': ['material'],
    'example': ['material', 'inspiration'],
    'messaging': ['material', 'messaging'],
}
MOST = 20  # files one request adds, as an upload does


def browse(route, data):
    try:
        return context.answer(BROWSE[route], data, 'blog')
    except document_library.LibraryError as error:
        raise ValueError(str(error)) from None


def _picks(data):
    if (
        not isinstance(data, dict)
        or set(data) != {'operation', 'picks'}
        or not isinstance(data['operation'], str)
        or not re.fullmatch(r'[a-f0-9]{32}', data['operation'])
    ):
        raise ValueError('Choose documents from the library with an operation ID.')
    picks = data['picks']
    if not isinstance(picks, list) or not 1 <= len(picks) <= MOST:
        raise ValueError(f'Choose between 1 and {MOST} documents.')
    seen = set()
    for pick in picks:
        if (
            not isinstance(pick, dict)
            or set(pick) != {'id', 'revision', 'role'}
            or not isinstance(pick['id'], str)
            or type(pick['revision']) is not int
            or pick['role'] not in ROLES
        ):
            raise ValueError(
                'Each document needs its library ID, revision and a role: facts, '
                'messaging or example.'
            )
        if pick['id'] in seen:
            raise ValueError('Choose each document once.')
        seen.add(pick['id'])
    return picks


def _file_name(snapshot):
    """A plain file name for the copy: the original's ending, or Markdown for its text."""
    ending = Path(snapshot['name']).suffix.lower() if snapshot['original'] is not None else '.md'
    if ending not in ('.md', '.txt', '.html', '.htm', '.docx', '.pdf'):
        ending = '.md'
    stem = re.sub(r'[^A-Za-z0-9 _-]+', '', snapshot['title']).strip()[:80] or 'Library document'
    return stem + ending


def take(root, data):
    """Copy chosen library revisions into this workspace as files for one blog, all or none.
    Repeating the same operation returns what it made the first time."""
    picks = _picks(data)
    staging = studio.inside(root, '.uploads')
    staging.mkdir(mode=0o700, exist_ok=True)
    ledger = studio.inside(staging, data['operation'] + '.json')
    fingerprint = sha(encoded({'document-library': picks}))
    if ledger.exists():
        saved = studio.read_json(ledger)
        if saved.get('fingerprint') != fingerprint:
            raise ValueError('This operation ID belongs to a different request.')
        if saved.get('result'):
            return saved['result']
        raise ValueError(
            'An earlier attempt with this operation did not finish. Choose the documents again.'
        )
    library = document_library.opened()
    if library is None:
        raise ValueError(context.NOT_MADE)
    try:
        snapshots = [library.snapshot(pick['id'], pick['revision']) for pick in picks]
    except document_library.LibraryError as error:
        raise ValueError(str(error)) from None
    studio.write_json(ledger, {'fingerprint': fingerprint, 'state': 'started'})
    from source_curator import skipping

    rows, made = [], []
    try:
        for pick, snapshot in zip(picks, snapshots, strict=True):
            name = _file_name(snapshot)
            content = (
                snapshot['original']
                if snapshot['original'] is not None
                else snapshot['text'].encode('utf-8')
            )
            with tempfile.TemporaryDirectory(dir=staging) as temp, skipping(True):
                path = Path(temp) / name
                path.write_bytes(content)
                record = studio.source_command(
                    root,
                    SimpleNamespace(
                        action='add',
                        name=snapshot['title'],
                        file=str(path),
                        content=snapshot['text'],
                        text_file=None,
                        origin=f'Document Library: {snapshot["id"]} revision {snapshot["revision"]}',
                        purpose=list(ROLES[pick['role']]),
                        author=None,
                        note='Chosen from the Document Library for one blog.',
                        status='ready',
                        library=None,
                    ),
                )
            made.append(record['id'])
            directory, record = studio.item(root, 'sources', record['id'])
            record['document_library'] = {
                'id': snapshot['id'],
                'revision': snapshot['revision'],
                'content_sha256': snapshot['content_sha256'],
            }
            studio.persist(directory, 'sources', record)
            rows.append(
                {
                    'filename': snapshot['title'],
                    'source': record,
                    'state': 'ready',
                    'chars': len(snapshot['text']),
                    'purpose': 'material',
                    'role': pick['role'],
                    'note': f'From the Document Library, revision {snapshot["revision"]}',
                    'document_library': record['document_library'],
                }
            )
    except BaseException:
        for ident in made:
            shutil.rmtree(studio.material(root, ident), ignore_errors=True)
        ledger.unlink(missing_ok=True)
        raise
    result = {
        'files': rows,
        'state': 'saved',
        'receipts': [],
        'next_step': 'Every document has text. Each is used only by the blog it is added to.',
    }
    studio.write_json(ledger, {'fingerprint': fingerprint, 'state': 'saved', 'result': result})
    return result


def keep_blog(root, record, text, source=None):
    """Keep a finished blog in the Document Library as Markdown: {'state': 'kept',
    'document', 'revision'} or {'state': 'failed', 'reason'}. Never raises."""
    try:
        library = document_library.opened(create=True)
        kept = library.retain(
            key='blog:' + record['id'],
            studio='blog',
            kind='blog',
            title=record.get('title') or record['id'],
            text=text,
            project={
                'id': record['id'],
                'title': record.get('title'),
                'revision': (source or {}).get('revision'),
            },
            author=(record.get('author') or '').strip() or None
            if isinstance(record.get('author'), str)
            else None,
        )
    except Exception as error:  # the blog is finished or published either way
        known = isinstance(error, (ValueError, OSError))
        return {
            'state': 'failed',
            'reason': (str(error)[:200] if known else '')
            or 'The Document Library could not keep it. Finish or publish it again to retry.',
        }
    return {'state': 'kept', 'document': kept['document'], 'revision': kept['revision']}


def describe(found):
    """What the page says of it, in a few words."""
    if not found:
        return None
    if found['state'] == 'kept':
        return 'kept in the Document Library'
    return 'not kept in the Document Library: ' + found['reason']
