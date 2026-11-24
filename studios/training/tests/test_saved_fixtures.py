"""The capture of the stored saved-flow fixtures (`saved_fixtures.py`), and the proof that each
is what the earlier gated flow writes today (GitHub issue #542).

Each state below is made the only way the saved flow makes it: a saved record started with
`saved_start`, then driven by scripted workers and decisions on the page to the stop. The
training's folder is then compared with the stored tree. Times, digests that follow from
times, and activity ids differ from one run to the next, so they are masked before comparing;
every other byte, every file name and every key must match. Nothing is scrubbed: the
workspace has no remote, so no driver (no computer or person name) is written, and the check
below refuses any file that names the disposable folder or a home directory.

To capture the fixtures again (only while the saved flow exists; this module is removed with
it in phase C):

    TRAINING_SAVED_FIXTURES_WRITE=1 python3 scripts/ci/run_tests.py test_saved_fixtures
"""
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

STAMP = re.compile(rb'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?')
DIGEST = re.compile(rb'(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])')
ACTIVITY = re.compile(rb'"id": ?"[0-9a-f]{12}"')
# Seconds measured while the flow ran.
SECONDS = re.compile(rb'("(?:seconds|active_seconds|elapsed_seconds|duration)": ?)[0-9.e-]+')


# A deck's working folders carry a random suffix (work/deck/brand-1a2b3c, start-..., looks-...).
WORKING = re.compile(rb'\b([a-z]+)-[0-9a-f]{6}\b')


def masked(data: bytes) -> bytes:
    for pattern, said in ((STAMP, b'<time>'), (DIGEST, b'<digest>'), (ACTIVITY, b'"id":"<id>"'),
                          (WORKING, rb'\1-<suffix>')):
        data = pattern.sub(said, data)
    return SECONDS.sub(rb'\1<seconds>', data)


def _settled(value):
    """A JSON value with the order the research questions happened to finish in left out: a
    list of entries that each name their step (a run's model jobs) is compared as a set."""
    if isinstance(value, dict):
        return {key: _settled(item) for key, item in value.items()}
    if isinstance(value, list):
        items = [_settled(item) for item in value]
        if items and all(isinstance(item, dict) and 'step' in item for item in items):
            items.sort(key=lambda item: json.dumps(item, sort_keys=True))
        return items
    return value


def comparable(files: dict) -> dict:
    """A tree as it is compared: names and contents masked, an activity log's lines in order,
    and a zip by its members."""
    shown = {}
    for name, data in files.items():
        key = masked(name.encode()).decode()
        value = None
        if data.startswith(b'PK\x03\x04'):
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    value = sorted((item, masked(archive.read(item))) for item in archive.namelist())
            except zipfile.BadZipFile:
                value = None   # the slides stand-in's deck is a few marked bytes, not a zip
        if value is not None:
            pass
        elif name.endswith('.jsonl'):
            value = sorted(masked(line) for line in data.splitlines())
        elif name.endswith('.json'):
            # Research questions finish in any order, and their results are kept by
            # question: the same keys, in the order they finished.
            value = masked(json.dumps(_settled(json.loads(data)), sort_keys=True).encode())
        else:
            value = masked(data)
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
