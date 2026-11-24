"""Saved step-by-step Blog Studio work in its original format, as static fixtures.

Each folder under fixtures/saved/ holds the files the earlier saved flow wrote for one stop,
as a workspace holds them (articles/<id>/..., sources/<id>/..., .blog-runs/<id>.json).
`load` copies one into a test's disposable workspace, byte for byte, so the migration,
saved-state and finished-blog tests read original-format work without running that flow.

`Maker` and `capture` are how the fixtures were made: by running the real saved flow
(blog_runner.create, submit, decide, the page's dispatch, the page runner's own research step
and worker record) in a disposable workspace, with fixed identities and a fixed clock so the
bytes are stable. test_saved_fixtures.py makes each one again and compares it with the stored
tree (`same`): the proof that the fixtures are what the saved flow writes. Both go when the
saved flow is retired.

The stored bytes are the original format as captured (Blog Studio 4.19.0, Harness Research
stand-in 1.5.1). A few fields record what is installed when a blog is saved, not what the
saved flow did (FOLLOWS_INSTALLED); the comparison checks that they are there, not their
values, so a newer installed version never asks for the fixtures to be written again.

The fixture whose research ran (NEEDS_RESEARCH) are made with the pinned Harness
Research stand-in the suites use (STUDIO_TEST_RESEARCH_RUNTIME) and a stand-in assistant that
returns synthetic research; no provider is ever asked. Every other capture runs with no
research helper at all, whatever this computer has installed. A schema 4 run whose parallel
research ran is not kept: that research publishes, as the origin of each selected source,
the absolute path of the temporary folder it drafted in (`blog-research-draft-<random>` in
this computer's temporary folder), inside digested bundle files, so it can be neither stable
nor free of this computer's paths without rewriting digested bytes.

    python3 tests/saved_fixtures.py            # compare every fixture with a fresh capture
    python3 tests/saved_fixtures.py --write    # write them again (review the diff)
"""

import isolation  # noqa: F401  (first: keeps every capture off this computer's own settings)
from contextlib import ExitStack
from datetime import datetime, timezone
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import uuid
from unittest.mock import patch

import blog_runner as runner
import studio
from studio_core import work_summary
from test_blog_runner import FilesCase

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'saved'
# The one clock every fixture was written at.
CLOCK = datetime(2026, 1, 5, 9, 30, tzinfo=timezone.utc)
# Workspace files that are not this blog's saved work: the lock's marker, the last opened
# blog, the save receipts every kind of save leaves at the workspace's top, and this
# computer's log of what the assistant did (read by no reader of saved work).
NOT_WORK = ('.studio.lock', '.active-article.json')
NOT_WORK_FOLDERS = ('.desk-receipts/', '.blog-runs/activity/')
SCRUBBED = b'/synthetic-capture'
RESEARCH_RUNTIME = os.environ.get('STUDIO_TEST_RESEARCH_RUNTIME')
NEEDS_RESEARCH = ('research-ran-schema3',)
# The stand-in Harness Research helper runs in Node; its clock is fixed the same way.
NODE_CLOCK = """'use strict';
const start = Date.parse('2026-01-05T09:30:00Z');
let reads = 0;
const Real = Date;
const now = () => start + reads++;
class CaptureDate extends Real {
  constructor(...args) { if (args.length) super(...args); else super(now()); }
  static now() { return now(); }
}
globalThis.Date = CaptureDate;
"""
# Fields a save takes from what is installed, by file name: compared by presence, not value.
# A '*' stands for every key at that level. The run record's fields are also in the copies
# of it the run keeps in its history (history/editorial-run-*.json).
RUN_FIELDS = (
    ('research_contract', 'version'),  # The Harness Research helper's version,
    ('research_contract', 'digest'),  # the digest of its installed files,
    ('research_execution', 'capability', 'digest'),  # and of its collection capability.
    # Each stage's basis digests the inputs it was written from, the blog record among them,
    # and that record names Blog Studio's version: the basis follows the version too.
    ('stages', '*', 'basis'),
)
FOLLOWS_INSTALLED = {
    'session.json': (('guidance', 'revision'),),  # Blog Studio's own version (hub_store.VERSION)
    'blog-run.json': RUN_FIELDS,
    'editorial-run-*.json': RUN_FIELDS,
}
INSTALLED = '<follows what is installed>'
PLAN = '# Plan\n\n- **capacity**: How does a synthetic restart keep capacity?\n'

OUTLINE = '# Synthetic outline\n\nOpening brief.\n\n## First\n\nFirst brief.\n\n## Second\n\nSecond brief.\n'
MANUSCRIPT = (
    '# Synthetic draft\n\nAn opening.\n\n## First\n\nSaved words.\n\n## Second\n\nMore words.\n'
)
REVIEW = '# Review\n\n- Tighten the opening.\n'
HANDOFF = '# Handoff\n\nTitle: Synthetic draft\n'
IDEAS = '# Ideas\n\nThree ways in.\n\n## One way\n\nReaders · A point\n\n## Another way\n\nReaders · Another point\n'
FINDINGS = '# Findings\n\nSynthetic evidence.'
NOTES = 'Unstructured notes only, no headings.'
GUIDE = '# Synthetic gateway guide\n\nOpening.\n\n## Why\n\nBecause.\n'


def load(root, state):
    """Copy one saved stop into a disposable workspace and return its blog's ID. A blog of
    the same fixture loaded earlier is replaced, with its worker record; nothing else in the
    workspace changes."""
    root = Path(root)
    temporary, place = Path(tempfile.gettempdir()).resolve(), Path(isolation.PLACE).resolve()
    real = root.resolve()
    if (
        not real.is_relative_to(temporary)
        or real == temporary
        or real.is_relative_to(place)
        or not (root / 'articles').is_dir()
    ):
        # Only a disposable Blog Studio workspace a test made in the temporary folder.
        raise RuntimeError('Load saved fixtures only into a disposable workspace.')
    tree = FIXTURES / state
    if not tree.is_dir():
        raise ValueError('No saved fixture named ' + state)
    (ident,) = [path.name for path in (tree / 'articles').iterdir()]
    if (root / 'articles' / ident).exists():
        shutil.rmtree(root / 'articles' / ident)
    (root / '.blog-runs' / (ident + '.json')).unlink(missing_ok=True)  # Its worker record.
    for path in sorted(tree.rglob('*')):
        if path.is_file():
            target = root / path.relative_to(tree)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
    return ident


class Maker(FilesCase):
    """The saved flow's own writers, as the saved-state tests drove them."""

    def capture_only(self):  # The method a capture case is made with; never a test.
        pass

    def submit(self, found, content=None, page=False, **extra):
        if content is None and not extra:
            return super().submit(found, page=page)  # A claims map quotes its material.
        return runner.submit(
            self.root,
            found['id'],
            found['next'],
            {
                'content': content or '# ' + found['next'] + '\nSynthetic writing.',
                'notes': 'Synthetic worker judgment.',
                **extra,
            },
            found['expected'],
            page=page,
        )

    def written(self, found, stage, content, page=False, **extra):
        """Submit and approve every stage before `stage`, then submit `stage` itself."""
        while found['next'] != stage:
            found = self.approve(self.submit(found, page=page), page=page)
        return self.submit(found, content, page=page, **extra)

    def dispatch(self, action, found, **data):
        with studio.locked(self.root), patch.object(runner.Engine, 'control', return_value={}):
            runner.dispatch(
                self.root, action, {'id': found['id'], 'expected': found['expected'], **data}
            )
        return runner.survey(self.root, found['id'])

    def worker(self, found, state):
        """The page runner's own record of this blog's worker, as it keeps it."""
        runner.engine(self.root).keep_local(found['id'], state)
        return found

    def researched(self):
        """A page run saved with a research execution record (schema 4)."""
        from studio_core import research_contract, research_session

        protocol = research_session.PROTOCOL
        execution = {
            'schema': 1,
            'protocol': protocol,
            'workers': 1,
            'capability': {'protocol': protocol},
        }
        with (
            patch.object(
                research_contract, 'snapshot', return_value={'schema': 2, 'name': 'synthetic'}
            ),
            patch.object(research_contract, 'runtime_for', return_value=Path('synthetic-runtime')),
            patch.object(research_session, 'execution', return_value=execution),
        ):
            return self.create(page=True, research='web-allowed', sources=[self.source()['id']])

    def research_ran(self, schema):
        """A page run whose research really ran with the pinned Harness Research stand-in,
        approved, then drafted and paused. Schema 4 pins the helper's parallel collection;
        schema 3 is the same run where the helper offers no collection (as an older helper
        does), so only that probe answers 'none'."""
        from contextlib import nullcontext

        from studio_core import research_session
        from synthesis_fixture import TEXT

        older = patch.object(research_session, 'execution', return_value=None)
        with older if schema == 3 else nullcontext():
            found = self.create(
                page=True, research='web-allowed', sources=[self.source(TEXT)['id']]
            )
        found = self.approve(self.submit(found, PLAN, page=True), page=True)
        engine = runner.Engine(self.root, research_worker)
        engine.control(found['id'], 'resume')
        engine._once(found['id'])  # The page runner's own research step.
        found = runner.survey(self.root, found['id'])
        if (found['next'], found['awaits']) != ('research', 'decision'):
            raise AssertionError(
                'The research step did not finish: ' + str(engine.local(found['id']))
            )
        found = self.written(self.approve(found, page=True), 'draft', MANUSCRIPT, page=True)
        engine.control(found['id'], 'pause')
        return runner.survey(self.root, found['id'])

    def finished(self, **extra):
        found = self.create(page=True, **extra)
        while not found['complete']:
            content = GUIDE if found['next'] == 'draft' else None
            self.submit(runner.survey(self.root, found['id']), content, page=True)
            found = self.approve(runner.survey(self.root, found['id']), page=True)
        return found

    def balanced(self):
        import studios_config

        studios_config.update({'review': {'level': 'balanced'}})
        found = self.approve(self.submit(self.create(), OUTLINE))
        return self.submit(found, MANUSCRIPT)


def research_worker(engine, data, guidance, **options):
    """A stand-in assistant for the research step: no web, synthetic research from the one
    supplied source, in each shape the helper asks for (synthesis_fixture)."""
    import copy

    from synthesis_fixture import dossier, review

    if set(data) == {'task'}:  # Finding public sources: none.
        return {'content': json.dumps({'urls': []}), 'notes': ''}
    if 'review_template' in data:
        return {'content': json.dumps(review(data['review_template'])), 'notes': ''}
    source = data['sources'][0]
    value = dossier(data['worker'], source['file'], source['origin'], source['permission'])
    if 'questions' in data:  # Collecting evidence (parallel collection).
        if source.get('original_file'):
            value['sources'][0]['original_file'] = source['original_file']
        value = {**{k: value[k] for k in ('schema', 'sources', 'facts')}, 'gaps': []}
    elif 'evidence' in data:  # Combining the collected evidence.
        first = data['evidence']['facts'][0]['id']
        value = dossier(data['worker'])
        value['findings'] = [
            {
                **copy.deepcopy(value['findings'][0]),
                'id': question['id'],
                'summary': {
                    'text': 'More than one instance keeps capacity.',
                    'kind': 'summary',
                    'refs': [first],
                },
                'support': [first],
                'conditions': [],
            }
            for question in data['task']['planning_questions']
        ]
        value['sections'][0]['blocks'][0]['refs'] = [first]
        value['brief'][0]['blocks'][0]['refs'] = [value['findings'][0]['id']]
        value = {k: value[k] for k in ('schema', 'findings', 'sections', 'brief')}
    return {'content': json.dumps(value), 'notes': ''}


def _web(c, page=True):
    return c.create(page=page, research='web-allowed', sources=[c.source()['id']])


def _draft(c):
    return c.written(c.create(page=True), 'draft', MANUSCRIPT, page=True)


# Each saved stop: how the saved flow reached it. Rows of the saved-state table.
MAKERS = {
    'angles-unwritten': lambda c: c.from_files(),
    'angles-waiting': lambda c: c.submit(c.from_files(), c.ANGLES, page=True),
    'research-questions': lambda c: c.submit(_web(c), page=True),
    'research-findings': lambda c: c.written(_web(c), 'research', FINDINGS, page=True),
    'claims-map-gate': lambda c: c.submit(
        c.create(sources=[c.source()['id']], research='supplied-only')
    ),
    'brief-only': lambda c: c.create(),
    'page-created': lambda c: c.create(page=True),
    'unstructured-outline': lambda c: c.submit(c.create(), NOTES),
    'unstructured-outline-approved': lambda c: c.approve(c.submit(c.create(), NOTES)),
    'outline-gate': lambda c: c.submit(c.create(page=True), OUTLINE, page=True),
    'outline-approved': lambda c: c.approve(c.submit(c.create(), OUTLINE)),
    'outline-approved-failed': lambda c: c.worker(
        c.approve(c.submit(c.create(page=True), OUTLINE, page=True), page=True),
        {'enabled': False, 'status': 'failed', 'error': 'Synthetic failure.', 'reason': 'cli'},
    ),
    'draft-gate': _draft,
    'draft-gate-chat': lambda c: c.written(c.create(), 'draft', MANUSCRIPT),
    'draft-gate-paused': lambda c: c.worker(_draft(c), {'enabled': False, 'status': 'paused'}),
    'draft-gate-stopped': lambda c: c.worker(_draft(c), {'enabled': False, 'status': 'stopped'}),
    'draft-gate-failed': lambda c: c.worker(
        _draft(c),
        {'enabled': False, 'status': 'failed', 'error': 'Synthetic failure.', 'reason': 'cli'},
    ),
    'draft-gate-queued': lambda c: c.worker(_draft(c), {'enabled': True, 'status': 'queued'}),
    'draft-gate-working': lambda c: c.worker(_draft(c), {'enabled': True, 'status': 'working'}),
    'review-gate': lambda c: c.written(
        c.approve(c.written(c.create(), 'draft', MANUSCRIPT)), 'review', REVIEW
    ),
    'handoff-gate': lambda c: c.written(
        c.approve(c.written(c.create(), 'draft', MANUSCRIPT, gaps=['Supply a release date.'])),
        'package',
        HANDOFF,
        gaps=['Name the owner.'],
    ),
    'balanced-draft': lambda c: c.balanced(),
    'ideas-gate': lambda c: c.submit(c.create(mode='ideas', stop='outline'), IDEAS),
    'author-outline': lambda c: c.create(mode='from-outline', outline_text=OUTLINE),
    'review-supplied': lambda c: c.submit(
        c.create(mode='review', manuscript=c.source(MANUSCRIPT)['id']), REVIEW
    ),
    'revise-supplied': lambda c: c.create(mode='revise', manuscript=c.source(MANUSCRIPT)['id']),
    'skipped-research-drafted': lambda c: c.written(
        c.dispatch('skip-research', _web(c)), 'draft', MANUSCRIPT, page=True
    ),
    'research-execution-drafted': lambda c: c.written(
        c.dispatch('skip-research', c.researched()), 'draft', MANUSCRIPT, page=True
    ),
    'finished-chat': lambda c: c.approve(
        c.written(c.approve(c.written(c.create(), 'draft', MANUSCRIPT)), 'package', HANDOFF)
    ),
    'finished-ideas': lambda c: c.approve(
        c.submit(c.create(page=True, mode='ideas', stop='outline'), IDEAS, page=True), page=True
    ),
    'finished-outline': lambda c: c.approve(
        c.submit(c.create(page=True, mode='outline', stop='outline'), OUTLINE, page=True),
        page=True,
    ),
    'research-ran-schema3': lambda c: c.research_ran(3),
    'finished-page': lambda c: c.finished(),
    'finished-page-warm': lambda c: c.finished(tone='Warm'),
}


def _tree(root):
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob('*')
        if path.is_file()
        and path.name not in NOT_WORK
        and not str(path.relative_to(root)).startswith(NOT_WORK_FOLDERS)
    }


def capture(state):
    """Run the saved flow to one stop in a fresh disposable workspace and return the files it
    wrote there, {workspace path: bytes}. Identities come from the stop's name and the clock
    is fixed, so a capture made again gives the same bytes."""
    case = Maker('capture_only')
    counter = iter(range(1_000_000))

    def fixed_uuid():
        seed = (state + '\0' + str(next(counter))).encode()
        return uuid.UUID(bytes=hashlib.sha256(seed).digest()[:16], version=4)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return CLOCK if tz else CLOCK.replace(tzinfo=None)

    with ExitStack() as stack:
        stack.enter_context(patch('uuid.uuid4', fixed_uuid))
        # Research names its workers with random tokens; they come from the stop's name too.
        tokens = iter(range(1_000_000))

        def fixed_token(size=32):
            seed = (state + '\0token\0' + str(next(tokens))).encode()
            return hashlib.sha256(seed).hexdigest()[: size * 2]

        stack.enter_context(patch('secrets.token_hex', fixed_token))
        stack.enter_context(patch.object(studio, 'datetime', Clock))
        stack.enter_context(patch.object(work_summary, 'datetime', Clock))
        case.setUp()
        try:
            # No research helper unless the stop needs the pinned stand-in.
            research = RESEARCH_RUNTIME if state in NEEDS_RESEARCH else None
            if state in NEEDS_RESEARCH and not research:
                raise RuntimeError('Set STUDIO_TEST_RESEARCH_RUNTIME to make ' + state)
            clock = case.base / 'capture-clock.cjs'
            clock.write_text(NODE_CLOCK)  # Outside the workspace: never captured.
            stack.enter_context(
                patch.dict(
                    os.environ,
                    {
                        'HARNESS_RESEARCH_RUNTIME': research or str(case.base / 'no-research'),
                        'NODE_OPTIONS': '--require ' + str(clock),
                    },
                )
            )
            before = _tree(case.root)
            found = MAKERS[state](case)
            made = {name: raw for name, raw in _tree(case.root).items() if before.get(name) != raw}
            # Scrubbed: a supplied file's path names the disposable folder it was added from
            # (a source's `origin`); it is said as SCRUBBED instead. Nothing else may name it.
            place = str(case.base).encode()
            made = {name: raw.replace(place, SCRUBBED) for name, raw in made.items()}
            elsewhere = [place, b'/Users/', b'/var/folders/', tempfile.gettempdir().encode()]
            if RESEARCH_RUNTIME:
                elsewhere.append(RESEARCH_RUNTIME.encode())
            for name, raw in made.items():
                if any(found in raw for found in elsewhere) or str(case.base) in name:
                    raise AssertionError(state + ': ' + name + ' names this computer')
            if [n.split('/')[1] for n in made if n.startswith('articles/')] and {
                n.split('/')[1] for n in made if n.startswith('articles/')
            } != {found['id']}:
                raise AssertionError(state + ': more than its own blog was written')
            return made
        finally:
            case.doCleanups()


def _mark(held, path):
    if not isinstance(held, dict) or not path:
        return
    keys = list(held) if path[0] == '*' else [path[0]]
    for key in keys:
        if key not in held:
            continue
        if len(path) == 1:
            held[key] = INSTALLED
        else:
            _mark(held[key], path[1:])


def _comparable(name, raw):
    base = name.rsplit('/', 1)[-1]
    fields = next(
        (found for pattern, found in FOLLOWS_INSTALLED.items() if fnmatch.fnmatch(base, pattern)),
        None,
    )
    if not fields:
        return raw
    value = json.loads(raw)
    for path in fields:
        _mark(value, path)
    return json.dumps(value, sort_keys=True).encode()


def same(made, kept):
    """Whether a capture is the stored fixture: the same files and bytes, except that a
    field in FOLLOWS_INSTALLED need only be present on both sides."""
    return sorted(made) == sorted(kept) and all(
        _comparable(name, made[name]) == _comparable(name, kept[name]) for name in made
    )


def stored(state):
    tree = FIXTURES / state
    return {str(p.relative_to(tree)): p.read_bytes() for p in tree.rglob('*') if p.is_file()}


def write(state):
    tree = FIXTURES / state
    if tree.exists():
        shutil.rmtree(tree)
    for name, raw in capture(state).items():
        target = tree / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)


if __name__ == '__main__':
    os.chdir(Path(__file__).resolve().parent)
    writing = '--write' in sys.argv[1:]
    differ = []
    for name in MAKERS:
        if name in NEEDS_RESEARCH and not RESEARCH_RUNTIME:
            continue
        if writing:
            write(name)
        elif not same(capture(name), stored(name)):
            differ.append(name)
    print(json.dumps({'fixtures': len(MAKERS), 'written': writing, 'differ': differ}))
    sys.exit(1 if differ else 0)
