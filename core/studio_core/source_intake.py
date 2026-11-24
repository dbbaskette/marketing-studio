"""A folder or a spreadsheet as sources, for any studio's primary source picker.

What a caller needs to know
---------------------------
    from studio_core import source_intake
    found = source_intake.take(given, local=not remote, accepts={'.md', '.txt', '.pdf', '.docx'},
                               room=20, spare=40_000_000, taken=('brief.md',))

- `given` is what the person gave the picker, on purpose:
  - a folder: a path on this computer, or a Google Drive folder link or identity (str), as
    `source_folders.location` takes it. The folder is scanned and every document read by the
    shared code the source editor's Add a folder uses (`research_sources.Sources.add_folder`),
    in a disposable source draft removed afterwards;
  - one uploaded file: {'name': str, 'data': bytes}. A spreadsheet workbook (.xlsx) the
    studio does not take as a file is read with `xlsx_sheets` into text, every sheet under
    its name; any other file the studio takes is passed on as it is.
- `accepts` is the file endings the studio keeps as files (lower case, with the dot). A
  document of another type that has text (a Google Docs, Google Slides or Google Sheets file,
  a PowerPoint file, a workbook) is kept as the text read from it, in a Markdown document
  named for it (`Plan.xlsx.md`). Anything with no text is skipped with its reason.
- `room` is how many documents the studio can still take, `spare` how many bytes, and
  `taken` the names it already holds (compared without case). A larger folder is cut there
  and every document left out is listed.
- `name_limit` bounds a document's name; `seconds` is the reading time of one folder
  (source_folders.FOLDER_SECONDS by default, inside the phone bridge's wait).
- `local` says whether the person is at this computer. A folder path on this computer is
  read only when it is True: a page reached over the network (a phone) could otherwise read
  any folder here. A page passes `local=not remote` (its request's own remote flag); with
  False a Google Drive folder link and an uploaded file are still taken. It must be given.

It returns
    {'uploads':   {name: bytes},       # ordinary uploads, in the order found
     'documents': [{'name', 'from', 'origin', 'notes'}],   # one per upload
     'skipped':   [{'name', 'code', 'reason'}],             # every one not taken
     'said':      str,                 # what was found and skipped, in plain words
     'next':      str | None,          # what to do about what was left, when anything was
     'report':    dict}                # the scan's whole report (source_folders.report)

A name says where the document was found: its path below the folder with ` - ` between the
folders (`Compete - Battlecards - EDB battlecard.pdf`), shortened from the left when it is
longer than `name_limit`, and numbered when two would be the same. A refusal of what was
given itself (no such folder, a link that is not a Drive folder, an unreadable workbook)
raises ValueError with a sentence the person can act on.

A folder on this computer uses no network. A Google Drive folder is read over the network
with the existing Google sign-in, only because the person gave its link. Nothing here keeps
anything outside what it returns, starts an assistant or a provider job, or installs anything.
Training Studio's `runner/desk_folder.py` is the same reading for work started in a
conversation; it keeps its own limits and words.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
import unicodedata

from studio_core import research_contract as rc, research_sources, source_folders, xlsx_sheets

NAME = 120              # characters in a document's name, as the studios' supplied documents take
REMOTE = ('A folder on this computer can be added only on this computer. From a phone, add a '
          'Google Drive folder link or upload the files.')
REORDERING = '‪‫‬‭‮⁦⁧⁨⁩'
SPREADSHEET = '.xlsx'


def flat(name, used, most=NAME):
    """A plain file name for a document found at `name` below the folder, not in `used`
    (case-folded names)."""
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


def spreadsheet(data) -> tuple[str, list]:
    """A workbook's sheets as Markdown text, and the warnings of what was cut or not read.
    ValueError (xlsx_sheets' own sentence) when it cannot be read safely."""
    found = xlsx_sheets.extract(data)
    text = found['text'].strip()
    if not text:
        raise ValueError('This spreadsheet has no cells with anything in them.')
    return text + '\n', list(found.get('warnings') or [])


def _plural(count, one, many=None):
    return f'{count} {one if count == 1 else (many or one + "s")}'


def said(report) -> str:
    """What one intake found and skipped, in plain words."""
    where = report.get('title') or 'the folder'
    added, skipped = report.get('added', 0), report.get('skipped_count', 0)
    if report.get('where') == 'file':
        if added:
            return f'Added “{where}”.' + (' It was read as text.' if report.get('read_as_text') else '')
        reason = (report.get('skipped') or [{}])[0].get('reason', '')
        return f'“{where}” was not added. {reason}'.strip()
    words = [f'Added {_plural(added, "document")} from “{where}”'
             + (f'; {skipped} {"was" if skipped == 1 else "were"} not added.' if skipped else '.')]
    if skipped:
        def why(code):
            reason = source_folders.REASONS.get(code, code).rstrip('.')
            return reason[:1].lower() + reason[1:]
        reasons = '; '.join(f'{count} {why(code)}' for code, count in sorted(report.get('reasons', {}).items()))
        words.append(f'Not added: {reasons}.')
    hidden = report.get('hidden') or 0
    if hidden:
        words.append('1 hidden file or folder was not looked at.' if hidden == 1
                     else f'{hidden} hidden files and folders were not looked at.')
    if report.get('stopped'):
        words.append(report['stopped'])
    return ' '.join(words)


def _answer(uploads, documents, report):
    report['said'] = said(report)
    return {'uploads': uploads, 'documents': documents, 'skipped': report['skipped'],
            'said': report['said'], 'next': report.get('next'), 'report': report}


def _file(given, accepts, room, spare, used, name_limit):
    """One uploaded file: a workbook read as text, a taken type passed on, else skipped."""
    name, data = given.get('name'), given.get('data')
    if not isinstance(name, str) or not name.strip() or type(data) is not bytes or not data:
        raise ValueError('Choose a file with something in it.')
    ending = Path(name).suffix.lower()
    report = {'where': 'file', 'title': name, 'found': 1, 'added': 0, 'skipped': [], 'skipped_count': 0,
              'unlisted': 0, 'reasons': {}, 'hidden': 0, 'again': False, 'next': None, 'stopped': None,
              'read_as_text': False}

    def left(code, detail=''):
        report['skipped'].append(source_folders.skip(name, code, detail))
        report['skipped_count'] = 1
        report['reasons'] = {code: 1}
        return _answer({}, [], report)
    if room < 1:
        return left('over-limit', 'There is no room for another document.')
    notes = []
    if ending in accepts:
        shown, kept = flat(name, used, name_limit), data
    elif ending == SPREADSHEET:
        text, notes = spreadsheet(data)
        shown, kept = flat(name + '.md', used, name_limit), text.encode('utf-8')
        report['read_as_text'] = True
    else:
        return left('unsupported')
    if len(kept) > min(spare, research_sources.LIMIT):
        return left('too-large' if len(kept) > research_sources.LIMIT else 'over-limit',
                    '' if len(kept) > research_sources.LIMIT else 'There is no room for a document this large.')
    report['added'] = 1
    return _answer({shown: kept}, [{'name': shown, 'from': name, 'origin': 'upload', 'notes': notes}], report)


def take(given, *, local, accepts, room, spare, taken=(), name_limit=NAME, seconds=None,
         store=None) -> dict:
    """What the person gave a studio's source picker, as ordinary uploads and a report.
    See the module's own description for every argument and the answer's shape. `store`
    is a research_sources.Sources to read in (tests); the draft made in it is removed."""
    if type(local) is not bool:
        raise ValueError('Say whether the person is at this computer (local=not remote).')
    accepts = {ending.lower() for ending in accepts}
    used = {name.casefold() for name in taken}
    room, spare = max(0, int(room)), max(0, int(spare))
    if isinstance(given, dict):
        return _file(given, accepts, room, spare, used, name_limit)
    # Which folder was given is decided before anything is read: never a path here from afar.
    if source_folders.location(given)[0] == 'local' and not local:
        raise ValueError(REMOTE)
    seconds = source_folders.FOLDER_SECONDS if seconds is None else seconds
    full = f'There is room for {_plural(room, "more document")}. Give a smaller folder for the rest.'
    heavy = 'There is no room for this document: the documents added already use the space left.'
    with tempfile.TemporaryDirectory(prefix='studio-source-folder-') as scratch:
        store = store or research_sources.Sources(Path(scratch) / 'sources')
        draft = store.create()
        try:
            return _folder(store, draft, given, accepts, room, spare, used, name_limit, seconds, full, heavy)
        finally:
            # The draft is only a way to read the folder: it never outlives this call, in a
            # store the caller gave as in the scratch one.
            shutil.rmtree(store.folder(draft['id']), ignore_errors=True)


def _folder(store, draft, given, accepts, room, spare, used, name_limit, seconds, full, heavy):
    """Read one folder in the draft and turn what it found into uploads and a report."""
    answer = store.add_folder(draft['id'], draft['revision'], {'location': given},
                              most=room, full=full, seconds=seconds)
    report = answer['folder']
    folder = store.folder(draft['id'])
    uploads, documents, short = {}, [], False
    for source in store.load(draft['id'])['sources']:
        if source['kind'] == 'file' and Path(source['name']).suffix.lower() in accepts:
            name, data = flat(source['name'], used, name_limit), rc.inside(folder, source['original']).read_bytes()
        else:   # kept as the text read from it: a workbook's sheets, a Google file, a deck
            name = flat(source['name'] + '.md', used, name_limit)
            data = rc.inside(folder, source['file']).read_bytes()
        if len(data) > spare:
            report['skipped'].append(source_folders.skip(source['name'], 'over-limit', heavy))
            report['skipped_count'] += 1
            report['reasons']['over-limit'] = report['reasons'].get('over-limit', 0) + 1
            short = True
            continue
        spare -= len(data)
        used.add(name.casefold())
        uploads[name] = data
        documents.append({'name': name, 'from': source['name'], 'origin': source['origin'],
                          'notes': list(source.get('warnings') or [])})
    report.update(added=len(uploads), documents=documents, again=False,
                  next='Not every document was read in time. Give the same folder again to read the rest.'
                  if report['reasons'].get('out-of-time') else
                  'Give a smaller folder for the rest.' if short or report['reasons'].get('over-limit') else None)
    return _answer(uploads, documents, report)


__all__ = ['NAME', 'REMOTE', 'flat', 'said', 'spreadsheet', 'take']
