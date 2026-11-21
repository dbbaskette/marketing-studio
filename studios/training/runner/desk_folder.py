"""A folder of sources for work started in a conversation (`studio desk create`).

What a caller needs to know
---------------------------
    uploads, report = desk_folder.uploads(location, room=..., spare=..., taken=...)

- `location` is a folder path on this computer or a Google Drive folder link, as the person
  gave it. The folder is scanned and read by the shared code the page's Add a folder uses
  (`studio_core.source_folders`, `research_sources.Sources.add_folder`), in a disposable
  source draft that is removed afterwards. Nothing is kept outside the training.
- `uploads` maps a plain file name to bytes, as `desk_chat.create` takes a single upload:
  each becomes one of the training's own documents (`sources/supplied`). A text, Markdown,
  HTML, Word or PDF file is kept as the file it is. A Google Docs, Google Slides or Google
  Sheets file, a PowerPoint file and a spreadsheet workbook are kept as the text read from
  them, in a Markdown document named for them.
- A name says where the document was found: its path below the folder, with ` - ` between
  the folders (`Compete - Battlecards - EDB battlecard.pdf`), shortened from the left when
  it is longer than a document's name may be, and numbered when two would be the same.
- `room` is how many documents the training can still take and `spare` how many bytes;
  `taken` is the names already chosen. A training takes `desk_chat.MOST_UPLOADS` documents
  and `desk_chat.UPLOAD_BYTES` bytes at its start, so a larger folder is cut there and
  every document left out is listed.
- `report` is the scan's own (`source_folders.report`), with `added` counting what was
  kept, `documents` listing each one ({'name', 'from', 'origin', 'notes'}) and every
  document not taken in `skipped`, each with its reason. `next` is one sentence on what to
  do when some were left for want of room or time, else None.
- A folder on this computer uses no network. A Google Drive folder is read over the
  network with the existing Google sign-in, only because the person gave its link.
"""
from pathlib import Path
import tempfile
import unicodedata

import runner  # noqa: F401  puts the core on the import path
from runner import desk_chat, documents
from studio_core import research_contract as rc, research_sources, source_folders

FULL = (f'A training started in a conversation takes {desk_chat.MOST_UPLOADS} documents. Give a smaller '
        'folder for the rest.')
HEAVY = f'A training started in a conversation takes {desk_chat.UPLOAD_BYTES // 1_000_000} MB of documents in all.'
SECONDS = 600     # Reading time: no page waits on a conversation's command.
LATE = 'Not every document was read in time. Create the work again with the same folder to read them all.'
REORDERING = '‪‫‬‭‮⁦⁧⁨⁩'


def flat(name, used, most=None):
    """A plain file name for a document found at `name` below the folder, not in `used`."""
    most = most or getattr(documents, 'NAME', 120)
    parts = []
    for part in unicodedata.normalize('NFC', name).split('/'):
        shown = ''.join(c for c in part if c.isprintable() and c not in REORDERING)
        shown = shown.replace(':', '-').replace('\\', '-').strip().lstrip('.').strip()
        parts.append(shown or 'Untitled')
    ending = Path(parts[-1]).suffix
    while len(' - '.join(parts)) > most and len(parts) > 1:
        parts.pop(0)       # the nearest folders say most about where it was
    stem = ' - '.join(parts)
    stem = stem[:len(stem) - len(ending)] if ending else stem
    stem = stem[:most - len(ending) - 6].rstrip() or 'document'
    shown, count = stem + ending, 1
    while shown.casefold() in used:
        count += 1
        shown = f'{stem} ({count}){ending}'
    return shown


def uploads(location, *, room, spare, taken=(), store=None):
    """The documents in one folder as named uploads, and what the scan did and left."""
    used = {name.casefold() for name in taken}
    with tempfile.TemporaryDirectory(prefix='training-studio-folder-') as scratch:
        store = store or research_sources.Sources(Path(scratch) / 'sources')
        draft = store.create()
        answer = store.add_folder(draft['id'], draft['revision'], {'location': location},
                                  most=max(0, room), full=FULL, seconds=SECONDS)
        report = answer['folder']
        folder, accepted = store.folder(draft['id']), documents.accepts()
        found, listed, heavy = {}, [], False
        for source in store.load(draft['id'])['sources']:
            if source['kind'] == 'file' and Path(source['name']).suffix.lower() in accepted:
                name, data = flat(source['name'], used), rc.inside(folder, source['original']).read_bytes()
            else:   # kept as the text read from it
                name = flat(source['name'] + '.md', used)
                data = rc.inside(folder, source['file']).read_bytes()
            if len(data) > spare:
                report['skipped'].append(source_folders.skip(source['name'], 'over-limit', HEAVY))
                report['skipped_count'] += 1
                report['reasons']['over-limit'] = report['reasons'].get('over-limit', 0) + 1
                heavy = True
                continue
            spare -= len(data)
            used.add(name.casefold())
            found[name] = data
            listed.append({'name': name, 'from': source['name'], 'origin': source['origin'],
                           'notes': source.get('warnings') or []})
        # What to do about what was left, in this command's own terms: a conversation's work
        # is created once, so there is no adding the folder again.
        report.update(added=len(found), documents=listed, again=False,
                      next=LATE if report['reasons'].get('out-of-time') else
                      HEAVY + ' Give a smaller folder for the rest.' if heavy else
                      FULL if report['reasons'].get('over-limit') else None)
        return found, report

