"""Presentation Studio's delivered decks, read for Add existing work to library: never changed.

What is offered
---------------
Only a delivered deck: a deck folder in the remembered workspace (`<workspace>/<deck>/`,
marked by `run.json`) with `deliver.json`. What it keeps is what Presentation Studio's
Deliver keeps (`runner/library_keep.py`): the deck's slide Markdown (`outline.md`), titled
as the deck, as a Presentation, Created here.

- Its key is the deck's own: the one `sources/library.json` records, so a deck Deliver
  already kept, or tried to, is that same library document. A deck delivered before
  Presentation Studio kept anything has no recorded key, and gets the one Presentation
  Studio makes for it when it next delivers: its folder's name with a part made from the
  folder and the moment the deck was created (`run.json`'s `created`). Adding it now and
  delivering it later is one library document.
- A PDF comes along only when it is the one Harness Slides rendered of exactly the
  delivered deck, checked as Deliver checks it: deliver.json's `deck_sha256`, the last
  build round's deck, that round's preview record (`preview.json`) and its `deck.pptx`,
  and the PDF's own hash as the round recorded it. Otherwise only the Markdown is added,
  with the reason, and nothing says a PDF was saved. Nothing is rendered or exported.
- What Presentation Studio calls it travels with it, as `native`: the deck's folder, its
  delivery's revision, output and time, and the hash of the delivered deck file.

Left out: decks not delivered, a deck whose record Presentation Studio could not open (an
interrupted Open on the desk, or a desk record that does not match its original), and one
with no slide outline. No record is written, no lock is taken, no Git, network, assistant,
slides tool or renderer is used, and every read is bounded and refuses links.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from studio_core import presentation_migration as migration

from . import reading
from .store import LIMITS, TITLE, _plain

NAME = re.compile(r'^[a-z0-9][a-z0-9-]{0,79}$')
KEY = re.compile(r'presentation:[a-z0-9-]{1,120}-[a-f0-9]{12}')
SHA = re.compile(r'^[a-f0-9]{64}$')
RUN, DELIVER, OUTLINE, STATUS = 'run.json', 'deliver.json', 'outline.md', 'sources/library.json'
BUILD_STATE = 'work/build/state.json'
RECORD = 2_000_000
PREVIEW = 1_000_000      # bytes of a preview's own record that are read, as Deliver reads
ENTRIES = 2_000
KEPT_ONLY = ' Only its slide Markdown is added.'
NO_PDF = ('There is no PDF of this delivered deck on this computer: it was delivered or '
          'previewed elsewhere.' + KEPT_ONLY)
PDF_UNRECORDED = ('It was delivered before Presentation Studio recorded which deck file it '
                  'delivered, so no PDF can be matched to it.' + KEPT_ONLY)
PDF_SELECTED = ('It was delivered with Selected changes: your own deck was changed where it '
                'was, and no PDF of it was rendered.' + KEPT_ONLY)
PDF_REDRAWN = ('It was drawn again after it was delivered, so the PDF here is of another '
               'version of it.' + KEPT_ONLY)
PDF_CHANGED = 'The PDF here no longer matches the delivered deck.' + KEPT_ONLY
PDF_LARGE = 'Its PDF is larger than the library keeps.' + KEPT_ONLY


def _run(folder: Path) -> dict | None:
    """The deck's run record as Presentation Studio reads it (`decks.record_bytes`): the
    desk's effective record when the deck was opened on the desk. Raises ValueError when
    Presentation Studio would refuse to open it."""
    if (folder / migration.PENDING).exists() or (folder / migration.PENDING).is_symlink():
        raise ValueError('opening it on the desk was interrupted')
    original = reading.bounded(folder / RUN, RECORD)
    if original is None:
        return None
    record, receipt = folder / migration.RECORD, folder / migration.ORIGIN
    if not any(path.exists() or path.is_symlink() for path in (record, receipt)):
        try:
            found = json.loads(original)
        except (UnicodeDecodeError, ValueError, RecursionError):
            raise ValueError('its record cannot be read') from None
        if not isinstance(found, dict):
            raise ValueError('its record cannot be read')
        return found
    value = reading.record(record, RECORD)
    origin = reading.record(receipt, 10_000)
    if value is None or origin is None or not reading.unlinked(folder, migration.RECORD):
        raise ValueError('its desk record cannot be verified')
    effective = migration.validated(value, original, folder.name, origin)
    for name in value['required']:
        data = reading.bounded(folder / name, RECORD)
        if data is None:
            raise ValueError('a desk record it needs is missing or linked')
        migration.shared_material(name, data)
    return effective


def _key(folder: Path, run: dict) -> tuple[str | None, str]:
    """(The deck's library key, where it came from): the one `sources/library.json`
    records, else the one Presentation Studio makes from the deck's folder and creation;
    (None, 'unsafe') when that record is there but cannot be read safely: Presentation
    Studio may still read a key from it, so none is made up here."""
    status, safe = reading.kept_record(folder, STATUS, 20_000)
    if not safe:
        return None, 'unsafe'
    held = (status or {}).get('key')
    if isinstance(held, str) and KEY.fullmatch(held):
        return held, 'recorded'
    plain = re.sub(r'[^a-z0-9-]+', '-', folder.name.lower()).strip('-')[:120] or 'deck'
    created = run.get('created')
    if isinstance(created, str) and created:
        part = hashlib.sha256(f'{folder.name}\0{created}'.encode()).hexdigest()[:12]
        return f'presentation:{plain}-{part}', 'deck'
    return None, ''


def _pdf(folder: Path, run: dict, delivered: dict, content: bool
         ) -> tuple[bytes | None, str | None, str | None]:
    """(The PDF's bytes when `content`, its hash, None), or (None, None, why there is none
    to add): the PDF Harness Slides rendered of exactly the delivered deck, checked as
    Presentation Studio's `library_keep.rendered_pdf` checks it."""
    if run.get('route') == 'existing' and (run.get('form') or {}).get('level') == 'selected':
        return None, None, PDF_SELECTED
    wanted = delivered.get('deck_sha256')
    if not isinstance(wanted, str) or not SHA.match(wanted):
        return None, None, PDF_UNRECORDED
    state = reading.record(folder / BUILD_STATE, 20_000_000) if reading.unlinked(folder, BUILD_STATE) else None
    rounds = (state or {}).get('rounds')
    last = rounds[-1] if isinstance(rounds, list) and rounds else None
    if not isinstance(last, dict) or not isinstance(last.get('preview'), str):
        return None, None, NO_PDF
    if last.get('deck') != wanted:
        made_here = any(isinstance(one, dict) and one.get('deck') == wanted for one in rounds)
        return None, None, PDF_REDRAWN if made_here else NO_PDF
    try:
        place = folder / last['preview']
        inside = (folder / 'work').resolve()
        if place.is_symlink() or inside not in place.resolve().parents:
            return None, None, NO_PDF
    except (OSError, RuntimeError, ValueError):
        return None, None, NO_PDF
    deck, pdf, said = place / 'deck.pptx', place / 'deck.pdf', place / 'preview.json'
    if not all(not path.is_symlink() and path.is_file() for path in (deck, pdf, said)):
        return None, None, NO_PDF
    shown = reading.record(said, PREVIEW)
    if shown is None:
        return None, None, NO_PDF
    if shown.get('deckSha256') != wanted \
            or not isinstance(shown.get('slides'), list) \
            or not isinstance(last.get('slides') or [], list) \
            or len(shown['slides']) != len(last.get('slides') or ()) \
            or reading.digest(deck) != wanted:
        return None, None, PDF_CHANGED
    try:
        size = pdf.stat().st_size
        if size > LIMITS['pdf']:
            return None, None, PDF_LARGE
        with open(pdf, 'rb') as stream:
            head = stream.read(5)
            stream.seek(max(0, size - 1024))
            tail = stream.read()
    except OSError:
        return None, None, NO_PDF
    if head != b'%PDF-' or b'%%EOF' not in tail:
        return None, None, PDF_CHANGED
    data = reading.bounded(pdf, LIMITS['pdf']) if content else None
    digest = reading.sha(data) if data is not None else reading.digest(pdf, LIMITS['pdf'])
    if digest is None or ('pdf' in last and last['pdf'] != digest):
        return None, None, PDF_CHANGED
    return data, digest, None


def _candidate(folder: Path, content: bool) -> tuple[dict | None, str | None, bool]:
    """(One delivered deck to add, None, True), (None, why it is left out, True) or
    (None, None, False) for a deck that is not delivered."""
    try:
        run = _run(folder)
    except (ValueError, KeyError, TypeError) as refusal:
        return None, (f'“{folder.name}” was left out: {str(refusal).rstrip(".")}. Open it in '
                      'Presentation Studio first.'), True
    if run is None:
        return None, None, False
    delivered = reading.record(folder / DELIVER, 100_000)
    if delivered is None:
        return None, None, False
    # Titled exactly as Deliver titles it, so the library sees the same title.
    raw = run.get('title') or folder.name
    title = _plain(raw, TITLE) or 'Untitled'
    data = reading.bounded(folder / OUTLINE, LIMITS['text'])
    try:
        text = data.decode('utf-8') if data is not None else ''
    except UnicodeDecodeError:
        text = ''
    if not text.strip():
        return None, (f'“{title[:120]}” was left out: it has no slide outline to add.'), True
    key, came_from = _key(folder, run)
    if came_from == 'unsafe':
        return None, (f'“{title[:120]}” was left out: its Document Library record '
                      '(sources/library.json) is linked, too large or damaged, so its library '
                      'key cannot be read. Put that file right, then preview again.'), True
    if key is None:
        return None, (f'“{title[:120]}” was left out: Presentation Studio has no library key '
                      'for it. Choose Keep in library on its desk in Presentation Studio.'), True
    pdf, pdf_sha, why = _pdf(folder, run, delivered, content)
    revision = delivered.get('revision') if type(delivered.get('revision')) is int else None
    native = {'studio': 'presentation', 'record': 'delivered-deck', 'deck': folder.name,
              'revision': revision,
              'output': delivered.get('output') if isinstance(delivered.get('output'), str) else None,
              'delivered_at': delivered.get('at') if isinstance(delivered.get('at'), str) else None,
              'deck_sha256': delivered.get('deck_sha256')
              if isinstance(delivered.get('deck_sha256'), str) and SHA.match(delivered['deck_sha256']) else None,
              'key': came_from}
    return {'key': key, 'studio': 'presentation', 'kind': 'presentation', 'origin': 'created',
            'title': title, 'author': None, 'text': text if content else None, 'original': None,
            'markdown_sha': reading.sha(text.encode('utf-8')), 'original_sha': None,
            'pdf': pdf, 'pdf_sha': pdf_sha, 'pdf_note': why, 'filename': None,
            'project': {'id': folder.name, 'title': raw if isinstance(raw, str) else title,
                        'revision': revision},
            'native': native, 'gaps': [], 'notes': [why] if why else [], 'note': 'Delivered deck',
            'folder': folder}, None, True


def _checked(folder: Path, content: bool):
    try:
        return _candidate(folder, content)
    except (TypeError, ValueError, AttributeError, KeyError, OSError):
        return None, (f'“{folder.name}” was left out: its record is not in a shape '
                      'Presentation Studio saves.'), True


def load(root, candidate: dict) -> dict:
    """The candidate read again with its text and PDF, refused when either is no longer
    what the preview read."""
    found, _, _ = _checked(candidate['folder'], True)
    if not found or any(found[name] != candidate[name] for name in
                        ('key', 'title', 'markdown_sha', 'original_sha', 'pdf_sha')):
        raise ValueError(f'“{candidate["title"][:120]}” changed in Presentation Studio after '
                         'the preview.')
    return found


def scan(root, content: bool = False) -> dict:
    """{'candidates', 'gaps', 'more', 'readable'}: the workspace's delivered decks, with
    the hashes of their Markdown and PDF as read now, and what was left out and why."""
    root = Path(root)
    folders, more = reading.folders(root, NAME.match, ENTRIES)
    candidates, gaps, waiting = [], [], 0
    for folder in folders:
        if not (folder / RUN).is_file() or (folder / RUN).is_symlink():
            continue
        found, why, finished = _checked(folder, content)
        if found:
            candidates.append(found)
        elif why:
            gaps.append(why)
        elif not finished:
            waiting += 1
    if waiting:
        gaps.append(f'{waiting} deck{" is" if waiting == 1 else "s are"} not delivered yet, so '
                    f'{"it is" if waiting == 1 else "they are"} not offered.')
    if more:
        gaps.append(f'Only the first {ENTRIES} deck folders were looked at.')
    return {'candidates': candidates, 'gaps': gaps, 'more': more, 'readable': True}
