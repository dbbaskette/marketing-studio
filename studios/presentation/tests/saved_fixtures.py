"""Saved decks in the original format of the earlier step-by-step flow, kept as static files.

What a caller needs to know
---------------------------
    saved_fixtures.load(case, 'build')                 # a copy of the stored deck, committed
    saved_fixtures.load(case, 'build', title='Other')  # the same deck under another title

- Each state of `STATES` is one folder under tests/fixtures/saved/<state>/, holding the
  deck's folder by its own name, as the saved flow wrote it: run.json, the shared files,
  and the work/ folder a computer keeps for itself. `load` copies it into the case's own
  disposable workspace and commits it there as one change, so the migration, the
  read-only record and the finished Open on the desk read it as they read a deck that
  was made on this computer.
- Every state was made by running the real saved flow (then `StudioCase.saved_start`, the
  gates decided, a pause taken, a step failed or a question asked as a person or worker
  would), with the engine option `at_once=1`, at the commits that added them. Where the
  stand-ins could not reach a saved shape, the record the dispatch saved was edited
  (`EDITED`). That flow, and the capture that ran it, went with GitHub issue #542: the
  stored trees are now the saved work every test reads, and are never written again.
- Scrubbed at capture, and put back at load: the deck's own folder (`@DECK@`), the
  stand-in brand skill's temporary folder (`@BRAND@`) and the test's temporary folder
  (`@BASE@`). Nothing else changes: no machine name, home folder or real name is held,
  as the stand-ins and the case's made-up person (Alex) are all a capture saw. Each
  state's scrubbed.json holds the SHA-256 each scrubbed file had as written.
- `load(..., title=)` gives the copy another title and folder name, as two decks of the
  same kind in one workspace have; in a shared workspace the copy is claimed by this
  computer, as the saved flow claimed the deck it started.
- tests/test_saved_fixtures.py checks the stored trees against themselves: every pin names
  the stored bytes, nothing names this computer, and a loaded copy is the stored deck.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
STORE = HERE / 'fixtures' / 'saved'
SCRUBBED = 'scrubbed.json'
PLACES = ('@DECK@', '@BRAND@', '@BASE@')

QUESTION = 'Which diagram style should the restart batches use?'

STATES = ('outline', 'document-outline', 'look', 'build', 'balanced', 'selected',
          'selected-automatic', 'delivered', 'delivered-pptx', 'delivered-balanced',
          'delivered-automatic', 'delivered-document-balanced',
          'delivered-document-automatic', 'delivered-selected', 'paused', 'failed',
          'question', 'question-early', 'research-plan', 'research', 'document-classify',
          'existing-brand-only', 'existing-polish', 'existing-redesign', 'existing-rework',
          'parallel-research', 'researched', 'researched-parallel', 'unleveled', 'corrupt')
EDITED = ('unleveled', 'corrupt')


# --- load -------------------------------------------------------------------------------------


def _places(case, root):
    return (('@DECK@', str(root)), ('@BRAND@', str(case.brand.run.home)), ('@BASE@', str(case.base)))


def scrubbed(state: str) -> dict:
    """The SHA-256 each scrubbed file of `state` had as the saved flow wrote it."""
    return json.loads((STORE / state / SCRUBBED).read_text())


def stored(state: str) -> tuple[str, dict]:
    folder = STORE / state
    decks = [path for path in folder.iterdir() if path.is_dir()]
    assert len(decks) == 1, f'{folder} holds one deck folder'
    deck = decks[0]
    return deck.name, {path.relative_to(deck).as_posix(): path.read_bytes()
                       for path in sorted(deck.rglob('*')) if path.is_file()}


def _replace(placed: dict, old: str, new: str) -> None:
    if old == new:
        return
    for relative, data in placed.items():
        if old.encode() in data:
            placed[relative] = data.replace(old.encode(), new.encode())


def _rebound(case, stored_files: dict, placed: dict, digests: dict) -> dict:
    """The placed files bound to this case's brand skill and folders, as the deck was bound
    to the capture's. The stand-in brand skill exports a contract that names its own
    temporary folder and the digests of its files, and carries a revision over all of it;
    a drawing pins that contract, and other records pin the files that hold it. So: each
    source digest the contract pinned becomes the digest of the same file here, the
    revision is taken again over the contract as it now reads, and each file another names
    by its SHA-256 is named by what it now holds. Nothing else changes."""
    from stand_ins import slides as slides_stand_in
    contract_name = 'brand/brand-contract.json'
    if contract_name in placed:
        contract = json.loads(placed[contract_name])
        for source in contract.get('sources') or []:
            here = Path(source.get('path') or '')
            if here.is_file():
                _replace(placed, source['sha256'], hashlib.sha256(here.read_bytes()).hexdigest())
        contract = json.loads(placed[contract_name])
        _replace(placed, contract['revision'], slides_stand_in.StandIn.revision(contract))
    named = {relative: digests.get(relative) or hashlib.sha256(data).hexdigest()
             for relative, data in stored_files.items()}
    for _ in range(20):
        moved = False
        for relative, data in placed.items():
            now = hashlib.sha256(data).hexdigest()
            if named[relative] != now:
                _replace(placed, named[relative], now)
                named[relative], moved = now, True
        if not moved:
            break
    return placed


def load(case, state: str, title: str | None = None, engine=None) -> Path:
    """Copy the stored deck `state` into `case`'s workspace, as a deck made there: placed,
    committed, remembered and, in a shared workspace, claimed by this computer."""
    import home
    from runner import decks, gitstate, team
    engine = engine or case.engine
    space = engine.space()
    name, files = stored(state)
    raw = files.get('run.json', b'')
    try:
        record = json.loads(raw)
    except ValueError:
        record = None
    captured = record.get('title') if isinstance(record, dict) else None
    wanted = title or captured or name
    ident = decks.deck_id(space, wanted)
    root = space.deck(ident)
    root.mkdir(parents=True)
    places = dict((mark, place) for mark, place in _places(case, root))
    placed = {}
    for relative, data in files.items():
        try:
            text = data.decode('utf-8')
        except UnicodeDecodeError:
            placed[relative] = data
            continue
        for mark in PLACES:
            text = text.replace(mark, places[mark])
        placed[relative] = text.encode('utf-8')
    for relative, data in _rebound(case, files, placed, scrubbed(state)).items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    if isinstance(record, dict):
        changed = dict(record)
        if ident != name or (title and title != captured):
            changed.update(id=ident, title=wanted)
            if isinstance(changed.get('form'), dict):
                changed['form'] = {**changed['form'], 'title': wanted}
        if space.address:
            changed['driver'] = team.claim(space)
        if changed != record:
            decks.write_run(root, changed)
    gitstate.commit(space, f'{wanted}: saved by the earlier flow', [root])
    home.remember(root, wanted)
    if isinstance(record, dict) and space.address:
        with engine.files:
            engine._claimed(root, space)
    return root
