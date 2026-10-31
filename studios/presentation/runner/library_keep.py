"""A delivered deck, kept in the shared Document Library (studio_core.document_library).

What a caller needs to know
---------------------------
    library_keep.keep(root, run, delivered)   # after delivery: {'state', ...}, never raises
    library_keep.status(root)                 # what was kept last, or None

- What is kept is the deck's slide-ordered Markdown (`outline.md`, the outline the
  delivered deck was built from), found again by the deck's own library key: delivering
  again reuses its library document and adds a revision only when the Markdown changed.
- The key is the folder's name with a random part, made once and kept in
  `sources/library.json`. A deck's folder name is a slug of its title, so two workspaces
  with a deck of the same title, or a deck deleted and made again under the same title,
  are separate library documents, never revisions of one.
- No PDF is made: Presentation Studio's slides tool has no PDF export, so the library
  records that the PDF still needs exporting. Nothing is installed or rendered for it.
- Delivery never waits on the library. Whatever stops the library is recorded in
  `sources/library.json`, which the workspace never shares, and Keep in library again
  retries it from the delivered record alone: nothing is uploaded to Google again and no
  slides tool or assistant job runs.
"""
from __future__ import annotations

import json
import re
import secrets
from pathlib import Path

import home
from workspace import WorkspaceError, write_atomic

from runner import decks
from runner.steps import outline as outlines
from studio_core import document_library

STATUS = Path('sources') / 'library.json'
NO_PDF = ('Presentation Studio cannot export a PDF of a delivered deck yet, so only its '
          'slide Markdown is kept. The delivered deck itself is unchanged.')
NO_OUTLINE = 'This deck has no slide outline to keep, so nothing was kept in the library.'


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


def keep(root, run: dict, delivered: dict) -> dict:
    """Keep the delivered deck's Markdown in the library and record how that went."""
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
            library = document_library.opened(create=True)
            kept = library.retain(
                key=done['key'], studio='presentation', kind='presentation',
                title=title, text=text,
                project={'id': root.name, 'title': title, 'revision': revision},
                pdf={'state': 'needs-export', 'reason': NO_PDF})
            done.update(state='kept', document=kept['document'], revision=kept['revision'],
                        pdf='needs-export', pdf_note=NO_PDF)
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
