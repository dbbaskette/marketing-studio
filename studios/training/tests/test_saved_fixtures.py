"""The capture of the stored saved-flow fixtures (`saved_fixtures.py`), and the proof that each
is what the earlier gated flow writes today (GitHub issue #542).

Each state below is made the only way the saved flow makes it: a saved record started with
`saved_start`, then driven by scripted workers and decisions on the page to the stop. The
training's folder is then compared with the stored tree. Only what differs from one run to
the next is settled before comparing, each named at STAMP below; digests are matched by what
they are the hash of, so the stored records must name the same files the flow's do. Every
other byte, every file name and every key must match. `StoredTreeTests` also checks each
stored tree against itself: every material and approval digest is the hash of the stored
material, and every content-addressed file is named by its hash. Nothing is scrubbed: the
workspace has no remote, so no driver (no computer or person name) is written, and the check
below refuses any file that names the disposable folder or a home directory.

To capture the fixtures again (only while the saved flow exists; this module is removed with
it in phase C):

    TRAINING_SAVED_FIXTURES_WRITE=1 python3 scripts/ci/run_tests.py test_saved_fixtures
"""
import hashlib
import io
import json
import os
import re
import shutil
import zipfile
from pathlib import Path
from unittest import mock

import saved_fixtures
from runner_support import StudioCase, asks, fails
from studio_core import review_policy
from test_runner_deck import DeckCase

WRITE = os.environ.get('TRAINING_SAVED_FIXTURES_WRITE') == '1'
EVERY = ['document', 'brief', 'scenario']
QUESTION = 'Which platform is this about?'


def _gate(title, gate, **form):
    def make(case):
        root = case.saved_start(title=title, **form)
        case.to_gate(root, gate)
        return root
    return make


def _early(title, script):
    def make(case):
        case.workers.then('research-plan', *script())
        return case.saved_start(title=title)
    return make


def _later(title, script):
    def make(case):
        case.workers.then('document', *script())
        root = case.saved_start(title=title, materials=EVERY)
        case.to_gate(root, 'blueprint')
        case.decide(root, 'blueprint')
        return root
    return make


def _finished(case):
    root = case.saved_start(title='Finished saved', materials=['document'])
    case.to_end(root)
    return root


def _deck_outline(case):
    root = case.saved_begin(title='Deck outline waits')
    case.to_outline(root)
    return root


def _deck_look(case):
    case.brand.offers_looks = True
    root = case.saved_begin(title='Deck look waits')
    case.drawn(root)
    return root


def _deck_gate(case):
    root = case.saved_begin(title='Deck gate waits')
    case.drawn(root)
    case.to_gate(root, 'deck')
    return root


def _google_drawn(case):
    root = case.saved_begin(title='Google deck drawn', deck_target='google')
    case.drawn(root)
    return root


def _finished_level(mode):
    def make(case):
        with mock.patch.object(review_policy, 'capture',
                               return_value={'schema': 1, 'level': mode}):
            root = case.saved_start(levels=['101'], title='Training ' + mode)
        if mode == 'step_by_step':
            case.to_end(root)
        else:
            shown = case.view(root)
            if shown.get('review'):
                case.engine.review_decide(root, shown['review']['expected'], 'approve')
        case.assertEqual(case.state(root), 'done')
        return root
    return make


# Each stored state, and how the saved flow makes it. The test class it needs: the plain
# runner, or one with the deck stand-ins.
STUDIO = {
    'research-plan-gate': _gate('Stop research-plan', 'research-plan'),
    'research-gate': _gate('Stop research', 'research'),
    'question-before-plan': _early('Asked early', lambda: [asks(QUESTION)]),
    'failure-before-plan': _early('Failed early', lambda: [fails(), fails(), fails()]),
    'blueprint-gate': _gate('Stop blueprint', 'blueprint', materials=EVERY),
    'document-gate': _gate('Stop document', 'document', materials=EVERY),
    'brief-gate': _gate('Stop brief', 'brief', materials=EVERY),
    'scenario-gate': _gate('Stop scenario main', 'scenario:main', materials=EVERY),
    'failure-after-plan': _later('Failed later', lambda: [fails(), fails(), fails()]),
    'question-after-plan': _later('Asked later', lambda: [asks(QUESTION)]),
    'finished': _finished,
}
DECK = {
    'deck-outline-waiting': _deck_outline,
    'deck-look-waiting': _deck_look,
    'deck-gate-waiting': _deck_gate,
    'google-deck-drawn': _google_drawn,
    'finished-level-step-by-step': _finished_level('step_by_step'),
    'finished-level-automatic': _finished_level('automatic'),
    'level-document-gate': _gate('Waiting at its guide', 'document@101', levels=['101']),
}

# What differs from one run of the saved flow to the next, each by name, and nothing else:
# - the time anything happened (ISO time stamps);
# - seconds measured while it ran (the fields in SECONDS);
# - the random id of each activity-log entry (work/activity-log.jsonl only);
# - the random suffix of a deck's working folders (work/deck/brand-, start-, whole-, looks-,
#   told-);
# - the random id of a worker's question (a 12-hex `id` beside its `text`);
# - the order in which work that runs side by side finished (each research question, each
#   deck section: PARALLEL): their entries in a list of step entries, their lines in the
#   activity log, and the members of a JSON object (members have no order in JSON).
# Digests are not masked: each is replaced by the file in the same tree whose bytes it is the
# hash of (`<sha:path>`), or, for a digest of something else, by the order it is first met,
# so the same relations between records and files must hold on both sides.
STAMP = re.compile(rb'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?')
SECONDS = re.compile(rb'("(?:seconds|active_seconds|elapsed_seconds|duration)": ?)[0-9.e-]+')
ACTIVITY = re.compile(rb'"id": ?"[0-9a-f]{12}"')
WORKING = re.compile(rb'\b(brand|start|whole|looks|told)-[0-9a-f]{6}\b')
DIGEST = re.compile(rb'(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])')
LOG = 'work/activity-log.jsonl'
PARALLEL = ('research:', 'deck-sections:')
QUESTION_ID = re.compile(r'[0-9a-f]{12}')


def _plain(data: bytes) -> bytes:
    data = STAMP.sub(b'<time>', data)
    data = SECONDS.sub(rb'\1<seconds>', data)
    return WORKING.sub(rb'\1-<suffix>', data)


def _research(item) -> bool:
    """Whether a step entry or an activity-log line is one of the side-by-side steps'."""
    if not isinstance(item, dict):
        return False
    named = item.get('step', item.get('unit'))
    return isinstance(named, str) and named.startswith(PARALLEL)


def _in_turn(items: list, key) -> list:
    """`items` with the side-by-side steps' own entries put in one order, in the places they
    held; every other entry keeps its place, and a step's own entries keep their order."""
    places = [index for index, item in enumerate(items) if _research(item)]
    ordered = sorted((items[index] for index in places), key=key)
    result = list(items)
    for index, item in zip(places, ordered):
        result[index] = item
    return result


def _settled(value):
    if isinstance(value, dict):
        if 'text' in value and QUESTION_ID.fullmatch(str(value.get('id'))):
            value = {**value, 'id': '<question>'}
        return {key: _settled(item) for key, item in value.items()}
    if isinstance(value, list):
        items = [_settled(item) for item in value]
        if items and all(isinstance(item, dict) and 'step' in item for item in items):
            items = _in_turn(items, lambda item: str(item.get('step')))
        return items
    return value


class Relabel:
    """Digests by what they are the hash of, the same way for both trees compared."""

    def __init__(self, files: dict):
        self.own = {}
        for name in sorted(files):
            self.own.setdefault(hashlib.sha256(files[name]).hexdigest(), name)
        self.met = {}

    def name(self, name: str) -> str:
        def label(found):
            digest = found.group(0).decode()
            return b'<own>' if self.own.get(digest) == name else self.digest(digest).encode()
        return _plain(DIGEST.sub(label, name.encode())).decode()

    def digest(self, digest: str) -> str:
        if digest in self.own:
            return '<sha:' + self.name(self.own[digest]) + '>'
        return self.met.setdefault(digest, f'<digest:{len(self.met) + 1}>')

    def text(self, data: bytes) -> bytes:
        return _plain(DIGEST.sub(lambda found: self.digest(found.group(0).decode()).encode(), data))


def comparable(files: dict) -> dict:
    """A tree as it is compared: names and contents with the differences above settled."""
    labels = Relabel(files)
    shown = {}
    for name in sorted(files, key=labels.name):
        key, data = labels.name(name), files[name]
        value = None
        if data.startswith(b'PK\x03\x04'):
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    value = [(item, labels.text(archive.read(item))) for item in archive.namelist()]
            except zipfile.BadZipFile:
                value = None   # the slides stand-in's deck is a few marked bytes, not a zip
        if value is not None:
            pass
        elif name == LOG:
            lines = [json.loads(line) for line in data.splitlines()]
            lines = _in_turn(lines, lambda line: (str(line.get('step', line.get('unit'))),
                                                  line.get('checkpoint') or ''))
            value = [ACTIVITY.sub(b'"id":"<id>"', labels.text(json.dumps(line, sort_keys=True)
                                                              .encode())) for line in lines]
        elif name.endswith('.json'):
            value = labels.text(json.dumps(_settled(json.loads(data)), sort_keys=True).encode())
        else:
            value = labels.text(data)
        shown.setdefault(key, []).append(value)
    return {key: sorted(values, key=repr) for key, values in shown.items()}


class Capture:
    MAKERS: dict = {}

    def captured(self, state):
        root = self.MAKERS[state](self)
        self.assertIsNone(self.view(root)['flow'])   # saved-flow work, not desk work
        files = {path.relative_to(root).as_posix(): path.read_bytes()
                 for path in sorted(root.rglob('*')) if path.is_file()
                 and path.relative_to(root).as_posix() not in saved_fixtures.LEFT_OUT}
        # Scrubbed: a deck's working files name the training's own folder, which is where
        # this disposable workspace happened to be. `saved_fixtures.load` puts back where the
        # training is loaded.
        files = {name: data.replace(str(root).encode(), saved_fixtures.FOLDER)
                 for name, data in files.items()}
        for name, data in files.items():
            for private in (str(self.base), str(Path.home()), '/private/var/', '/Users/'):
                self.assertNotIn(private.encode(), data, f'{name} names a folder on this computer')
        return files

    def check(self, state):
        files = self.captured(state)
        if WRITE:
            folder = saved_fixtures.FIXTURES / state
            shutil.rmtree(folder, ignore_errors=True)
            for name, data in files.items():
                (folder / name).parent.mkdir(parents=True, exist_ok=True)
                (folder / name).write_bytes(data)
        stored = saved_fixtures.tree(state)
        self.assertEqual(sorted(comparable(stored)), sorted(comparable(files)))
        self.assertEqual(comparable(stored), comparable(files))
        # The stored copy loads as the same saved training.
        self.assertEqual(json.loads(stored[saved_fixtures.SESSION])['id'],
                         saved_fixtures.ident(state))


def _tests(makers):
    def test(state):
        return lambda self: self.check(state)
    return {f'test_{state.replace("-", "_")}_is_what_the_saved_flow_writes': test(state)
            for state in makers}


StudioCaptureTests = type('StudioCaptureTests', (Capture, StudioCase),
                          {'MAKERS': STUDIO, **_tests(STUDIO)})
DeckCaptureTests = type('DeckCaptureTests', (Capture, DeckCase),
                        {'MAKERS': DECK, **_tests(DECK)})


class EveryStateTests(StudioCase):
    def test_every_stored_state_has_its_capture(self):
        self.assertEqual(saved_fixtures.names(), sorted({**STUDIO, **DECK}))


class StoredTreeTests(StudioCase):
    """Each stored tree agrees with itself, so the approvals the migration tests rely on are
    approvals of the stored materials."""

    def test_material_and_approval_digests_are_the_stored_materials(self):
        for state in saved_fixtures.names():
            files = saved_fixtures.tree(state)
            session = json.loads(files[saved_fixtures.SESSION])
            checked = 0
            for name, entry in session['artifacts'].items():
                with self.subTest(state=state, artifact=name):
                    self.assertIn(entry['file'], files)
                    made = hashlib.sha256(files[entry['file']]).hexdigest()
                    self.assertEqual(entry['sha256'], made)
                    if entry.get('approved'):
                        self.assertEqual(entry['approved']['sha256'], made)
                        checked += 1
            # Every stored state past its intake holds at least one real approval.
            self.assertTrue(checked, state)

    def test_every_input_digest_is_the_stored_inputs(self):
        """Each digest a stored tree keeps of what a material was built from, and of what
        its approval was given for, is the digest of that input as stored: a tree whose
        approval inputs no longer match their files fails here."""
        import workspace
        checked = set()
        for state in saved_fixtures.names():
            root = saved_fixtures.load(self, state)
            session = workspace.load(root)
            for name, entry in session['artifacts'].items():
                current = workspace.inputs(root, session, name)
                for where, digests in (('built_from', entry.get('built_from') or {}),
                                       ('approved', (entry.get('approved') or {}).get('inputs') or {})):
                    for key, value in digests.items():
                        with self.subTest(state=state, artifact=name, where=where, input=key):
                            self.assertIn(key, current)
                            self.assertEqual(value, current[key])
                            checked.add(key)
            # A changed input is told apart: the check is not one that always holds.
            if 'blueprint' in session['artifacts']:
                report = root / '.harness-research' / 'research-report.md'
                before = workspace.inputs(root, session, 'blueprint')['research']
                report.write_text(report.read_text() + '\nChanged.\n')
                self.assertNotEqual(workspace.inputs(root, session, 'blueprint')['research'],
                                    before)
        self.assertLessEqual({'intake', 'research', 'blueprint'}, checked)

    def test_the_comparison_tells_a_stale_approval_and_reordered_attempts_apart(self):
        """What the comparison settles is only what varies between runs: an approval digest
        that no longer names its material, or a step's attempts in another order, differ."""
        files = saved_fixtures.tree('failure-after-plan')
        session = json.loads(files[saved_fixtures.SESSION])
        approved = session['artifacts']['blueprint']['approved']
        approved['sha256'] = hashlib.sha256(b'another plan').hexdigest()
        stale = {**files, saved_fixtures.SESSION: json.dumps(session, indent=2).encode()}
        same = {**files, saved_fixtures.SESSION: json.dumps(
            json.loads(files[saved_fixtures.SESSION]), indent=2).encode()}
        self.assertEqual(comparable(same), comparable(files))
        self.assertNotEqual(comparable(stale), comparable(files))
        # A step's own tries (its model jobs, attempt 1, 2, 3) keep their order.
        record = json.loads(files['.training-studio/run.json'])
        jobs = record['model_jobs']
        places = [index for index, job in enumerate(jobs) if job['step'] == 'document']
        self.assertEqual([jobs[index]['attempt'] for index in places], [1, 2, 3])
        for index, job in zip(places, [jobs[index] for index in places][::-1]):
            jobs[index] = job
        reordered = {**files, '.training-studio/run.json': json.dumps(record).encode()}
        self.assertNotEqual(comparable(reordered), comparable(files))

    def test_content_addressed_files_are_named_by_their_bytes(self):
        named = re.compile(r'(?:^|/)history/.+/([0-9a-f]{64})\.[a-z]+$')
        seen = 0
        for state in saved_fixtures.names():
            for name, data in saved_fixtures.tree(state).items():
                found = named.search(name)
                if found:
                    seen += 1
                    with self.subTest(state=state, file=name):
                        self.assertEqual(hashlib.sha256(data).hexdigest(), found.group(1))
        self.assertTrue(seen)
