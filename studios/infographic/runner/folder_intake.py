"""A folder or a spreadsheet as supplied information, for the New infographic sheet.

The primary source picker takes, on purpose, a folder on this computer, a Google Drive folder
link, or an uploaded spreadsheet (.xlsx), through the shared studio_core.source_intake.take:
every document it finds becomes an ordinary intake preview (intake.prepare), reviewed and
acknowledged in the sheet before anything is saved, exactly as an uploaded file is. A folder
path on this computer is read only for a caller at this computer (`local`); from a phone a
Google Drive folder link or an uploaded file is still taken. Nothing starts an assistant, a
provider job or research.
"""
from __future__ import annotations

from pathlib import Path

from studio_core import source_intake

from . import intake
from .contracts import Invalid
from .validation import require

# The documents a folder may add, as the upload field takes them. A CSV needs its rows and
# columns confirmed one file at a time, so a folder's CSVs are left out and listed.
KINDS = {'.txt': 'text', '.md': 'markdown', '.pdf': 'pdf', '.docx': 'docx', '.html': 'html', '.htm': 'html'}
MOST = 40                   # the sources one brief may hold
SPARE = 64_000_000


def _previews(found):
    previews = []
    for name, raw in found['uploads'].items():
        kind = KINDS.get(Path(name).suffix.lower())
        if kind is None:
            continue
        try:
            previews.append(intake.prepare(raw, kind=kind, name=name[:200]))
        except (Invalid, ValueError) as failure:
            found['skipped'].append({'name': name, 'code': 'unreadable', 'reason': str(failure)})
    return {'previews': previews, 'skipped': found['skipped'], 'said': found['said'], 'next': found['next']}


def folder(given, *, local, taken=()):
    """Every readable document in a folder on this computer or a Google Drive folder."""
    require(isinstance(given, str) and given.strip() and len(given) <= 2000,
            'Give a folder on this computer or a Google Drive folder link.')
    require(isinstance(taken, list) and len(taken) <= MOST and all(isinstance(n, str) for n in taken),
            'Name the documents already added.')
    try:
        found = source_intake.take(given.strip(), local=local, accepts=set(KINDS), room=MOST - len(taken),
                                   spare=SPARE, taken=tuple(taken))
    except ValueError as failure:
        raise Invalid(str(failure)) from None
    return _previews(found)


def spreadsheet(name, raw, *, local):
    """One uploaded workbook, each sheet read into text under its name."""
    require(isinstance(name, str) and name.lower().endswith('.xlsx'), 'Choose an .xlsx spreadsheet.')
    try:
        found = source_intake.take({'name': name, 'data': raw}, local=local, accepts=set(KINDS),
                                   room=1, spare=SPARE)
    except ValueError as failure:
        raise Invalid(str(failure)) from None
    shown = _previews(found)
    require(shown['previews'], shown['said'] or 'The spreadsheet has no readable text.')
    return shown['previews'][0]
