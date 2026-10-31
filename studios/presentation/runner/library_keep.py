"""A delivered deck, kept in the shared Document Library (studio_core.document_library).

What a caller needs to know
---------------------------
    library_keep.keep(root, run, delivered)   # after delivery: {'state', ...}, never raises
    library_keep.again(root, run)             # Keep in library again, from deliver.json
    library_keep.status(root)                 # what was kept last, or None

- What is kept is the deck's slide-ordered Markdown (`outline.md`, the outline the
  delivered deck was built from), found again by the deck's own library key: delivering
  again reuses its library document and adds a revision only when what is kept changed.
- The key is the folder's name with a random part, made once and kept in
  `sources/library.json`. A deck's folder name is a slug of its title, so two workspaces
  with a deck of the same title, or a deck deleted and made again under the same title,
  are separate library documents, never revisions of one.
- The PDF is the one Harness Slides already rendered of the delivered deck: a whole-deck
  preview leaves `deck.pdf` beside the `deck.pptx` it rendered, checks that it has a page
  for every slide and draws the slide pictures from it, and the delivered deck is a copy
  of that `deck.pptx`. It is kept as the deck's PDF ('saved') only when everything still
  agrees: deliver.json's `deck_sha256`, the last round's deck, the preview's own record
  and its `deck.pptx`, and the PDF's hash as the round recorded it. Nothing is rendered,
  exported, uploaded or installed for it. Otherwise ('needs-export', with why) only the
  Markdown is kept, and nothing says the PDF was saved: a deck delivered on another
  computer, one pictured without a kept PDF (Selected changes on your own deck), and a
  PDF that changed since it was rendered.
- Delivery never waits on the library. Whatever stops the library is recorded in
  `sources/library.json`, which the workspace never shares, and Keep in library again
  retries it from the delivered record and this computer's own files alone: nothing is
  uploaded to Google again and no slides tool or assistant job runs.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
from pathlib import Path

import home
from workspace import WorkspaceError, write_atomic

from runner import decks
from runner.steps import build
from runner.steps import outline as outlines
from studio_core import document_library

STATUS = Path('sources') / 'library.json'
NO_PDF = ('Harness Slides left no PDF of this delivered deck on this computer, so only its '
          'slide Markdown is kept. The delivered deck itself is unchanged.')
PDF_CHANGED = ('The PDF Harness Slides rendered no longer matches the delivered deck, so only '
               'its slide Markdown is kept. The delivered deck itself is unchanged.')
PDF_LARGE = ('The PDF of this deck is larger than the library keeps, so only its slide '
             'Markdown is kept. The delivered deck itself is unchanged.')
NO_OUTLINE = 'This deck has no slide outline to keep, so nothing was kept in the library.'
SHA = re.compile(r'^[a-f0-9]{64}$')
READ_MOST = 1_000_000    # bytes of a preview's own record that are read


def status(root) -> dict | None:
    try:
        found = json.loads((Path(root) / STATUS).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return found if isinstance(found, dict) else None


def _key(root: Path) -> str:
    """This deck's library key: the one recorded for it, else a new one for this folder."""
    held = (status(root) or {}).get('key')
    if isinstance(held, str) and re.fullmatch(r'presentation:[a-z0-9-]{1,120}-[a-f0-9]{12}', held):
        return held
    plain = re.sub(r'[^a-z0-9-]+', '-', root.name.lower()).strip('-')[:120] or 'deck'
    return f'presentation:{plain}-{secrets.token_hex(6)}'


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _plain_file(path: Path) -> bool:
    return not path.is_symlink() and path.is_file()


def rendered_pdf(root, delivered: dict) -> tuple[bytes | None, str | None]:
    """The PDF Harness Slides rendered of exactly the delivered deck, found on this computer
    and checked, with nothing rendered now: (its bytes, None), or (None, why there is none
    to keep)."""
    root = Path(root)
    wanted = delivered.get('deck_sha256') if isinstance(delivered, dict) else None
    if not isinstance(wanted, str) or not SHA.match(wanted):
        return None, NO_PDF
    rounds = build.read_state(root).get('rounds') or []
    last = rounds[-1] if isinstance(rounds, list) and rounds else None
    if not isinstance(last, dict) or last.get('deck') != wanted \
            or not isinstance(last.get('preview'), str):
        return None, NO_PDF
    try:
        folder = root / last['preview']
        inside = (root / 'work').resolve()
        if folder.is_symlink() or inside not in folder.resolve().parents:
            return None, NO_PDF
        deck, pdf, said = folder / 'deck.pptx', folder / build.RENDERED_PDF, folder / 'preview.json'
        if not all(_plain_file(path) for path in (deck, pdf, said)):
            return None, NO_PDF
        with said.open('rb') as stream:
            shown = json.loads(stream.read(READ_MOST).decode('utf-8'))
        if not isinstance(shown, dict) or shown.get('deckSha256') != wanted \
                or not isinstance(shown.get('slides'), list) \
                or len(shown['slides']) != len(last.get('slides') or ()) \
                or _sha(deck) != wanted:
            return None, PDF_CHANGED
        if pdf.stat().st_size > document_library.LIMITS['pdf']:
            return None, PDF_LARGE
        data = pdf.read_bytes()
    except (OSError, RuntimeError, ValueError):
        return None, NO_PDF
    if not data.startswith(b'%PDF-') or b'%%EOF' not in data[-1024:]:
        return None, PDF_CHANGED
    # A round made before rounds recorded their PDF has no 'pdf': the preview's record is
    # what binds it then. One that recorded it, or recorded that there was none, must agree.
    if 'pdf' in last and last['pdf'] != hashlib.sha256(data).hexdigest():
        return None, PDF_CHANGED
    return data, None


def keep(root, run: dict, delivered: dict) -> dict:
    """Keep the delivered deck's Markdown, and its PDF when there is one, in the library,
    and record how that went."""
    root = Path(root)
    revision = delivered.get('revision') if isinstance(delivered, dict) else None
    done = {'delivered': revision, 'at': home.now(), 'key': _key(root)}
    try:
        place = root / outlines.OUTLINE_MD
        text = place.read_text(encoding='utf-8') if place.is_file() and not place.is_symlink() else ''
        if not text.strip():
            done.update(state='failed', problem=NO_OUTLINE)
        else:
            title = run.get('title') or root.name
            data, why = rendered_pdf(root, delivered)
            library = document_library.opened(create=True)
            kept = library.retain(
                key=done['key'], studio='presentation', kind='presentation',
                title=title, text=text,
                project={'id': root.name, 'title': title, 'revision': revision},
                pdf={'state': 'saved', 'data': data} if data is not None
                else {'state': 'needs-export', 'reason': why})
            done.update(state='kept', document=kept['document'], revision=kept['revision'],
                        pdf='saved' if data is not None else 'needs-export',
                        **({} if data is not None else {'pdf_note': why}))
    except Exception as failure:     # delivery stands whatever the library does
        known = isinstance(failure, (document_library.LibraryError, OSError, UnicodeDecodeError))
        done.update(state='failed', problem=(str(failure)[:300] if known else '')
                    or 'The library could not keep it. Try Keep in library again.')
    try:
        write_atomic(root / STATUS, json.dumps(done, indent=2) + '\n')
    except (OSError, WorkspaceError):
        pass    # the deck is delivered either way; the next view says nothing was recorded
    return done


def again(root, run: dict) -> dict:
    """Keep in library again, for a delivered deck: from deliver.json, and nothing else."""
    delivered = decks.delivered(root)
    if delivered is None:
        raise WorkspaceError('This deck has not been delivered, so there is nothing to keep '
                             'in the library yet.')
    return keep(root, run, delivered)
