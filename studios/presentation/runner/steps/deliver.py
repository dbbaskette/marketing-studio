"""Delivering a finished deck, and asking for changes to it once it is delivered.

What a caller needs to know
---------------------------
    record = deliver.deliver(root, run, slides, space=None)   # deliver.json, README, index
    made = deliver.upload(root, run, slides)                   # the same in two: the upload,
    record = deliver.record(root, run, made, space)            #   then what is written
    run = deliver.again(root, run, slides, note)               # reopen gate:build with a note

- Output 'google' puts the rendered deck into Google Drive as Google Slides, always as a
  new file: an earlier revision's file is never written over, so one that is gone is no
  matter. When Google cannot be reached the deck is delivered as a PowerPoint file
  instead, and deliver.json says so in `notice` (NOT_CONNECTED). Output 'pptx' copies the
  rendered deck to deck.pptx in the deck's folder (SHARED), which is committed and shared
  with the deck, for the page to offer as a download on any computer; a new PowerPoint
  delivery replaces it. A Google delivery, and changes asked for after delivery, leave it as
  the receipt of the revision it delivered. A delivery made before this recorded
  work/deck.pptx, which stays on the computer that made it.
    deliver.shared_file(root)              # the delivered file, while it is the delivery
    deliver.receipt_file(root, run, n)     # revision n's PowerPoint file, while kept
    deliver.receipts(root, run)            # every revision, as the desk lists them
- deliver.json (decks.DELIVER) is {'output', 'url', 'fileId', 'pptx', 'revision', 'at',
  'deck_sha256'}, with 'notice' when the deck was not delivered as asked. `deck_sha256` is
  the hash of the deck file delivered, which the Document Library's PDF is checked by.
  `revision` counts deliveries: each is added to run['revisions'] as {'revision', 'at',
  'url' or 'pptx', 'sha256'}. The deck's
  README.md and the workspace's index are written again from it.
- `space` is the workspace, for its index. Without it, the deck's folder is taken to be
  in the workspace's own folder, as it always is.
- `again` reopens gate:build with the person's note, as `stages.reopen` does, and has
  every section drawn again with it. deliver.json is set aside, so the deck is no longer
  finished; the earlier link stays in run['revisions']. Returns the run as it now is.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import types
from pathlib import Path

import runner  # noqa: F401  puts the core on the import path
import home
from workspace import WorkspaceError, write_atomic

from runner import decks, desk, stages
from runner.steps import build

GATE = 'gate:build'
SHARED = Path('deck.pptx')   # a PowerPoint delivery, kept beside the deck and shared
NOT_CONNECTED = "Google isn't connected, so this deck was made as a PowerPoint file."
NOTE = 4000
# Why a PowerPoint receipt has no Download: only the last PowerPoint delivery is kept.
REPLACED = 'Its file was replaced by revision {revision}’s PowerPoint file.'
NOT_KEPT_HERE = 'Its file is no longer kept beside the deck.'


def _title(run: dict, revision: int) -> str:
    title = run.get('title') or (run.get('form') or {}).get('title') or 'Deck'
    # A desk deck is never labelled: the Deliver sheet says whether it was reviewed, and
    # deliver.json records it.
    if decks.user_first(run) and not decks.on_desk(run):
        title += ' — first draft, not checked'
    return title if revision == 1 else f'{title} (revision {revision})'


def _rewrite(root: Path, run: dict, record: dict | None, space) -> None:
    write_atomic(root / 'README.md', decks.readme(run, record))
    decks.write_index(space or types.SimpleNamespace(root=root.parent))


def deliver(root, run: dict, slides, space=None) -> dict:
    """Deliver the rendered deck as the form asked: to Google Slides, or as a PowerPoint
    file. Returns what deliver.json records. A caller that must not hold its lock through
    the upload calls `upload`, then `record` under its lock."""
    return record(root, run, upload(root, run, slides), space)


def shared_file(root) -> Path | None:
    """The delivered PowerPoint file shared with the deck, while the deck is delivered as
    one: never a file left from before changes were asked for."""
    found = Path(root) / SHARED
    said = decks.delivered(root) or {}
    return found if found.is_file() and said.get('pptx') == SHARED.as_posix() else None


def receipt_file(root, run: dict, revision) -> Path | None:
    """The PowerPoint file of one delivered revision, while it is still kept beside the deck:
    the last PowerPoint delivery stays there through a Google delivery of the same deck and
    through changes, until another PowerPoint delivery replaces it. It is that revision's
    only when its bytes are the ones the revision recorded; a revision recorded before
    deliveries kept their hash is found only while it is the deck's own delivery."""
    root = Path(root)
    found = root / SHARED
    entry = next((one for one in run.get('revisions') or ()
                  if isinstance(one, dict) and one.get('revision') == revision), None)
    if entry is None or not entry.get('pptx') or found.is_symlink() or not found.is_file():
        return None
    wanted = entry.get('sha256')
    if wanted:
        return found if hashlib.sha256(found.read_bytes()).hexdigest() == wanted else None
    said = decks.delivered(root) or {}
    return shared_file(root) if said.get('revision') == revision else None


def receipts(root, run: dict) -> list[dict]:
    """Every delivered revision, oldest first, as its receipt: its revision, when, where it
    went ('google' with its link, or 'pptx'), and for a PowerPoint file whether it can still
    be downloaded here, or why not."""
    out, latest = [], None
    for entry in run.get('revisions') or ():
        if not isinstance(entry, dict) or not isinstance(entry.get('revision'), int):
            continue
        shown = {'revision': entry['revision'], 'at': entry.get('at')}
        if entry.get('url'):
            shown.update(format='google', url=entry['url'])
        else:
            kept = receipt_file(root, run, entry['revision']) is not None
            shown.update(format='pptx', download=kept)
            latest = entry['revision']
        out.append(shown)
    for shown in out:
        if shown['format'] == 'pptx' and not shown['download']:
            shown['why'] = (REPLACED.format(revision=latest) if latest != shown['revision']
                            else NOT_KEPT_HERE)
    return out


def upload(root, run: dict, slides, output=None) -> dict:
    """Put the rendered deck where the form asked, and say what deliver.json will record.
    Nothing in the deck's folder is written. On a computer that did not render it, the
    shared delivered file is what is sent."""
    root = Path(root)
    try:
        deck = build.delivered_deck(root, run)
    except WorkspaceError:
        deck = shared_file(root)
        if deck is None:
            raise
    revision, at = len(run.get('revisions') or []) + 1, home.now()
    output = output or (run.get('form') or {}).get('output') or 'google'
    record = {'output': output, 'url': None, 'fileId': None, 'pptx': None,
              'revision': revision, 'at': at, **({'review_status': 'unreviewed'} if decks.user_first(run) else {}),
              'deck_sha256': hashlib.sha256(deck.read_bytes()).hexdigest()}
    if decks.on_desk(run):
        record['review_status'] = 'reviewed' if desk.reviewed(build.read_state(root)) \
            else 'unreviewed'
    if output == 'google':
        if slides.drive_check():
            made = slides.drive_import(deck, _title(run, revision))
            record.update(url=made.get('url'), fileId=made.get('id'))
        else:
            record.update(output='pptx', notice=NOT_CONNECTED)
    if record['output'] == 'pptx':
        record['pptx'] = deck.relative_to(root).as_posix()
    return record


def record(root, run: dict, made: dict, space=None) -> dict:
    """Write deliver.json from what `upload` made, add the revision to the run, and write
    the deck's README and the workspace's index again. Returns what deliver.json holds."""
    root = Path(root)
    revisions = run.setdefault('revisions', [])
    revision, at = len(revisions) + 1, made['at']
    record = {**made, 'revision': revision}
    if record['output'] == 'pptx':
        # Kept beside the deck, so a teammate's computer can download it too.
        made_here = root / record['pptx']
        if made_here.resolve() != (root / SHARED).resolve():
            shutil.copyfile(made_here, root / SHARED)
        record['pptx'] = SHARED.as_posix()
    # A Google delivery leaves the last PowerPoint file where it is: it is that revision's
    # receipt (receipt_file). What is delivered now is said by deliver.json (shared_file).
    write_atomic(root / decks.DELIVER, json.dumps(record, indent=2, ensure_ascii=False)
                 + '\n')
    where = {'url': record['url']} if record['url'] else {'pptx': record['pptx']}
    # Each revision keeps the hash of the file it delivered, so its receipt finds it.
    revisions.append({'revision': revision, 'at': at, **where,
                      **({'sha256': record['deck_sha256']} if record.get('deck_sha256')
                         else {})})
    decks.write_run(root, run)
    _rewrite(root, run, record, space)
    return record


def again(root, run: dict, slides, note: str, space=None, sections=None) -> dict:
    """"Ask for changes" on a delivered deck: gate:build is reopened with the person's note,
    and the deck is built again from there. Returns the run as it now is. `sections`, from
    the desk, are the only ones asked, with no note of their own: their notes say it."""
    root = Path(root)
    note = note.strip() if isinstance(note, str) else ''
    if not note:
        raise WorkspaceError('Say what should change.')
    if len(note) > NOTE:
        raise WorkspaceError(f'Say it in at most {NOTE} characters.')
    if decks.delivered(root) is None:
        raise WorkspaceError('This deck has not been delivered yet, so there is nothing '
                             'to change after delivery.')
    run.setdefault('gates', {})[GATE] = {**run['gates'].get(GATE, {}), 'state': 'changes',
                                         'note': note, 'at': home.now(), 'by': 'page'}
    run = stages.reopen(run, GATE)
    state = build.read_state(root)
    if state.get('start'):
        state.update(asked={'note': None if sections is not None else note,
                            'sections': list(sections) if sections is not None else [
                                entry['id'] for entry in state['start']['sections']],
                            'at': home.now()}, repaired=0)
        build.write_state(root, state)
    (root / decks.DELIVER).unlink(missing_ok=True)
    # The PowerPoint file delivered stays as that revision's receipt: without deliver.json
    # it is never taken for the deck being made again (shared_file).
    decks.write_run(root, run)
    _rewrite(root, run, None, space)
    return run
