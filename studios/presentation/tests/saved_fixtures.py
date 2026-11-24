"""Saved decks in the original format of the earlier step-by-step flow, kept as static files.

What a caller needs to know
---------------------------
    saved_fixtures.load(case, 'build')                 # a copy of the stored deck, committed
    saved_fixtures.load(case, 'build', title='Other')  # the same deck under another title
    python3 tests/saved_fixtures.py --write [STATE ...]   # capture again from the saved flow

- Each state of `STATES` is one folder under tests/fixtures/saved/<state>/, holding the
  deck's folder by its own name, as the saved flow wrote it: run.json, the shared files,
  and the work/ folder a computer keeps for itself. `load` copies it into the case's own
  disposable workspace and commits it there as one change, so the migration, the
  read-only record and the finished Open on the desk read it as they read a deck that
  was made on this computer.
- Every state was made by running the real saved flow (`StudioCase.saved_start`, then the
  gates decided, a pause taken, a step failed or a question asked as a person or worker
  would) at the commit that added it. Where the stand-ins cannot reach a saved shape, the
  maker edits the record the dispatch saved, and says so (`EDITED`).
- Scrubbed at capture, and put back at load: the deck's own folder (`@DECK@`), the
  stand-in brand skill's temporary folder (`@BRAND@`) and the test's temporary folder
  (`@BASE@`). Nothing else changes: no machine name, home folder or real name is held,
  as the stand-ins and the case's made-up person (Alex) are all a capture sees.
- `load(..., title=)` gives the copy another title and folder name, as two decks of the
  same kind in one workspace have; in a shared workspace the copy is claimed by this
  computer, as `saved_start` claims the deck it constructs.
- tests/test_saved_fixtures.py makes each state again from the saved flow and compares it
  with the stored tree. It is the proof that the stored files are what the flow writes,
  and it goes when the saved flow does (GitHub issue #542).
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
STORE = HERE / 'fixtures' / 'saved'
SCRUBBED = 'scrubbed.json'
PLACES = ('@DECK@', '@BRAND@', '@BASE@')
BRAND_HOME = re.compile(r'/[^"\s`\\]*?/brand-stand-in-[A-Za-z0-9_]+')

PASTE = {'kind': 'paste', 'text': 'Notes on rolling restarts.'}
UPLOAD = {'kind': 'upload', 'name': 'old.pptx'}
QUESTION = 'Which diagram style should the restart batches use?'

# --- the makers: each runs the real saved flow to one saved state ---------------------------


def _existing(case, level, **changes):
    from test_flow_routes import DECK
    return case.saved_start(route='existing', level=level, title='Old ' + level,
                            source=dict(UPLOAD), uploads={'old.pptx': DECK},
                            **({'selected': 'Shorten slide 2'} if level == 'selected' else {}),
                            **changes)


def _waits(case, root, gate):
    shown = case.view(root)
    found = (shown['gate'] or {}).get('name')
    assert found == gate, (root.name, found, shown['sentence'])
    return root


def _delivered(case, review='step_by_step', **changes):
    case.review_level = review
    root = case.gated(**changes)
    case.decide(root, 'gate:build')
    from runner import decks
    assert decks.delivered(root) is not None, case.view(root)['sentence']
    return root


def outline(case):
    return _waits(case, case.saved_start(), 'gate:outline')


def document_outline(case):
    root = case.saved_start(title='Document outline', route='document', source=dict(PASTE))
    case.decide(root, 'gate:classify', extra={'kind': 'material'})
    return _waits(case, root, 'gate:outline')


def look(case):
    root = case.saved_start(title='At the look')
    case.decide(root, 'gate:outline')
    return _waits(case, root, 'gate:look')


def build(case):
    return _waits(case, case.gated(), 'gate:build')


def balanced(case):
    case.review_level = 'balanced'
    return case.saved_start(title='Balanced')


def selected(case):
    return _waits(case, _existing(case, 'selected'), 'gate:classify')


def selected_automatic(case):
    """Selected changes at the Automatic level: its patch planned and drawn, the deck
    waiting at gate:build."""
    from test_desk_words import planned
    case.workers.then('patch', planned(2, '3', [(1, 'in minutes.')]))
    return _waits(case, case.saved_existing_deck('automatic', 'selected', selected='Shorten slide 2'),
                  'gate:build')


def delivered(case):
    return _delivered(case)


def delivered_pptx(case):
    return _delivered(case, output='pptx', title='Rolling restarts file')


def delivered_balanced(case):
    return _delivered(case, 'balanced', title='Rolling restarts balanced')


def delivered_automatic(case):
    return _delivered(case, 'automatic', title='Rolling restarts automatic')


def delivered_document_balanced(case):
    return _delivered(case, 'balanced', title='Notes balanced', route='document',
                      source=dict(PASTE))


def delivered_document_automatic(case):
    return _delivered(case, 'automatic', title='Notes automatic', route='document',
                      source=dict(PASTE))


def delivered_selected(case):
    from test_desk_words import planned
    case.workers.then('patch', planned(2, '3', [(1, 'in minutes.')]))
    root = case.saved_existing_deck('automatic', 'selected',
                                    selected='Shorten the words on slide 2')
    case.decide(root, 'gate:build')
    return root


def paused(case):
    """A real pause: Pause on the page while the outline step works. The step ends after
    it, as a real worker's does, and the runner keeps the pause with the outline made."""
    def pausing(tools, job):
        root = next(path.parent for path in case.space.root.rglob('run.json')
                    if json.loads(path.read_text()).get('title') == 'Paused mid-step')
        assert case.engine.act(root, 'pause')['state'] == 'paused'
        return case.workers.outline(tools, job)
    case.workers.then('outline', pausing)
    root = case.saved_start(title='Paused mid-step')
    assert case.view(root)['state'] == 'paused', case.view(root)['sentence']
    return root


def failed(case):
    """A step after the outline and the look fails every try, so the run stops failed."""
    import runner_support
    case.workers.then('section', *[runner_support.fails()] * 12)
    root = case.saved_start(title='Failed drawing')
    case.decide(root, 'gate:outline')
    shown = case.view(root)
    if (shown['gate'] or {}).get('name') == 'gate:look':
        offered = (shown['gate'].get('offered') or (shown['gate'].get('look') or {}).get('offered'))
        case.decide(root, 'gate:look', 'approve', None,
                    {'look': offered['looks'][0]['id']} if offered and not offered['chosen'] else None)
    assert case.view(root)['state'] == 'failed', case.view(root)['sentence']
    return root


def question(case):
    """The person asks for changes to the drafted outline, and the worker drafting it
    again asks them a question: the first draft is kept, the outline step unfinished."""
    import runner_support
    root = _waits(case, case.saved_start(title='Asked'), 'gate:outline')
    case.workers.then('outline', runner_support.asks(QUESTION))
    case.decide(root, 'gate:outline', 'changes', 'Fewer slides on the batches.')
    assert (case.view(root)['question'] or {}).get('text') == QUESTION, case.view(root)['sentence']
    return root


def question_early(case):
    """A worker drafting the outline asks the person a question: nothing is made yet."""
    import runner_support
    case.workers.then('outline', runner_support.asks(QUESTION))
    root = case.saved_start(title='Asked early')
    assert (case.view(root)['question'] or {}).get('text') == QUESTION, case.view(root)['sentence']
    return root


def research_plan(case):
    return _waits(case, case.saved_start(title='Research plan', research=True), 'gate:research-plan')


def research(case):
    root = case.saved_start(title='Research found', research=True)
    case.decide(root, 'gate:research-plan')
    return _waits(case, root, 'gate:research')


def document_classify(case):
    root = case.saved_start(title='Document read', route='document', source=dict(PASTE))
    return _waits(case, root, 'gate:classify')


def existing_brand_only(case):
    return _waits(case, _existing(case, 'brand-only'), 'gate:classify')


def existing_polish(case):
    return _waits(case, _existing(case, 'polish'), 'gate:classify')


def existing_redesign(case):
    return _waits(case, _existing(case, 'redesign'), 'gate:classify')


def existing_rework(case):
    return _waits(case, _existing(case, 'rework'), 'gate:classify')


def parallel_research(case):
    """EDITED: a deck at its research plan, its record then given the parallel research
    collection schema 4 writes (the saved start the stand-ins drive writes schema 1 to 3)."""
    from runner import decks
    from studio_core import research_session
    root = research_plan(case)
    record = case.record(root)
    record.update(schema=4, research_contract={'schema': 2, 'version': '1.0.0', 'digest': '1' * 64},
                  research_execution={'schema': 1, 'protocol': research_session.PROTOCOL,
                                      'workers': 2, 'capability': {
                                          'protocol': research_session.PROTOCOL}})
    decks.write_run(root, record)
    return root


def parallel_outline(case):
    """EDITED: a deck at its drafted outline, its record then given the parallel research
    collection schema 4 writes, with the research contract and collection protocol the
    runner requires of it, and no research done (as `parallel_research`)."""
    from runner import decks
    from studio_core import research_session
    root = case.saved_start(title='Parallel outline')
    _waits(case, root, 'gate:outline')
    record = case.record(root)
    record.update(schema=4, research_contract={'schema': 2, 'version': '1.0.0', 'digest': '1' * 64},
                  research_execution={'schema': 1, 'protocol': research_session.PROTOCOL,
                                      'workers': 2, 'capability': {
                                          'protocol': research_session.PROTOCOL}})
    decks.write_run(root, record)
    return root


def unleveled(case):
    """EDITED: a deck at its outline whose record says schema 2 but has lost its review
    level, which the runner refuses."""
    from runner import decks
    root = case.saved_start(title='Unleveled')
    record = case.record(root)
    record['schema'] = 2
    record.pop('review_policy', None)
    decks.write_run(root, record)
    return root


def corrupt(case):
    """EDITED: a deck at its outline whose run.json no longer parses."""
    root = case.saved_start(title='Corrupt')
    (root / 'run.json').write_text('{not json')
    return root


STATES = {name.replace('_', '-'): maker for name, maker in (
    ('outline', outline), ('document_outline', document_outline), ('look', look),
    ('build', build), ('balanced', balanced), ('selected', selected),
    ('selected_automatic', selected_automatic), ('delivered', delivered),
    ('delivered_pptx', delivered_pptx), ('delivered_balanced', delivered_balanced),
    ('delivered_automatic', delivered_automatic),
    ('delivered_document_balanced', delivered_document_balanced),
    ('delivered_document_automatic', delivered_document_automatic),
    ('delivered_selected', delivered_selected), ('paused', paused), ('failed', failed),
    ('question', question), ('question_early', question_early),
    ('research_plan', research_plan), ('research', research),
    ('document_classify', document_classify), ('existing_brand_only', existing_brand_only),
    ('existing_polish', existing_polish), ('existing_redesign', existing_redesign),
    ('existing_rework', existing_rework), ('parallel_research', parallel_research),
    ('parallel_outline', parallel_outline), ('unleveled', unleveled), ('corrupt', corrupt))}
EDITED = ('parallel-research', 'parallel-outline', 'unleveled', 'corrupt')


# --- capture, compare and load ----------------------------------------------------------------


def _places(case, root):
    return (('@DECK@', str(root)), ('@BRAND@', str(case.brand.run.home)), ('@BASE@', str(case.base)))


def capture(case, state: str) -> tuple[str, dict, dict]:
    """Run the saved flow to `state` in `case`'s disposable workspace: the deck's folder
    name, each of its files by relative path, scrubbed, and the SHA-256 each scrubbed file
    had as written (`load` needs it to find where another file names it)."""
    root = STATES[state](case)
    files, digests = {}, {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink() or not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        data = path.read_bytes()
        try:
            text = data.decode('utf-8')
        except UnicodeDecodeError:
            files[relative] = data
            continue
        for mark, place in _places(case, root):
            text = text.replace(place, mark)
        text = BRAND_HOME.sub('@BRAND@', text)
        files[relative] = text.encode('utf-8')
        if files[relative] != data:
            digests[relative] = hashlib.sha256(data).hexdigest()
    return root.name, files, digests


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


def write(state: str, name: str, files: dict, digests: dict) -> None:
    folder = STORE / state
    if folder.exists():
        shutil.rmtree(folder)
    for relative, data in files.items():
        target = folder / name / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (folder / SCRUBBED).write_text(json.dumps(digests, indent=1, sort_keys=True) + '\n')


# Values that differ on every run of the same flow: when, and for how long; and every
# digest and random name, since what is hashed holds a time (the brand contract's export,
# the outline, a drawing round) or is picked at random (a round's folder, a job's ID).
VOLATILE = [(re.compile(rb'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)?'), b'<when>'),
            (re.compile(rb'"(seconds|elapsed|duration|took)": ?[0-9.]+'), rb'"\1": <seconds>'),
            (re.compile(rb'(?<![0-9A-Za-z])[0-9a-f]{6,64}(?![0-9A-Za-z])'), b'<hex>'),
            # The slides stand-in numbers the Google decks it makes in one process.
            (re.compile(rb"stand-in-deck-\d+"), b"stand-in-deck-<n>")]


def _unzipped(data: bytes) -> bytes:
    """A zip's members and their contents, without the times it keeps."""
    if not data.startswith(b'PK\x03\x04'):
        return data
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as kept:
            return b'\n'.join(sorted(member.encode() + b'\0' + kept.read(member)
                                     for member in kept.namelist()))
    except zipfile.BadZipFile:
        return data


def _sorted(value):
    if isinstance(value, dict):
        return {key: _sorted(item) for key, item in value.items()}
    if isinstance(value, list):
        return sorted((_sorted(item) for item in value), key=lambda item: json.dumps(item, sort_keys=True))
    return value


def _ordered(name: str, data: bytes) -> bytes:
    """The same content whatever order it was written in: sections drawn and questions
    researched side by side finish in either order."""
    if name.endswith('.json'):
        try:
            return json.dumps(_sorted(json.loads(data)), sort_keys=True, indent=1).encode()
        except ValueError:
            return data
    if name.endswith('.jsonl'):
        return b'\n'.join(sorted(data.splitlines()))
    return data


def normal(files: dict) -> list:
    """The files with what differs on every run put aside, to compare two captures: each
    (name, data), in order. Names may repeat once their digests are put aside."""
    shown = []
    for name, data in files.items():
        data = _unzipped(data)
        name = name.encode()
        for pattern, said in VOLATILE:
            data = pattern.sub(said, data)
            name = pattern.sub(said, name)
        shown.append((name.decode(), _ordered(name.decode(), data)))
    return sorted(shown)


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


def _case():
    import runner_support

    class Capture(runner_support.DeskCase):
        def runTest(self):
            pass
    case = Capture()
    case.setUp()
    # One section, or one research question, at a time: the runner's own option, so that
    # what side-by-side jobs record does not depend on which of them finished first.
    case.engine = case.make(at_once=1)
    return case


def main(argv) -> int:
    states = [name for name in argv if not name.startswith('-')] or list(STATES)
    if '--write' not in argv:
        print(__doc__)
        return 2
    for state in states:
        case = _case()
        try:
            name, files, digests = capture(case, state)
        finally:
            case.doCleanups()
        write(state, name, files, digests)
        print(state, name, len(files), 'files', sum(len(data) for data in files.values()), 'bytes')
    return 0


if __name__ == '__main__':
    sys.path[:0] = [str(HERE.parent), str(HERE)]
    import helpers  # noqa: F401  the disposable data folder, as every test has
    sys.exit(main(sys.argv[1:]))
