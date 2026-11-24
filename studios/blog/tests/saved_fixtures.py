"""Saved step-by-step Blog Studio work in its original format, as static fixtures.

Each folder under fixtures/saved/ holds the files the earlier saved flow wrote for one stop,
as a workspace holds them (articles/<id>/..., sources/<id>/..., .blog-runs/<id>.json).
`load` copies one into a test's disposable workspace, byte for byte, so the migration,
saved-state and finished-blog tests read original-format work without running that flow.

`Maker` and `capture` are how the fixtures were made: by running the real saved flow
(blog_runner.create, submit, decide, the page's dispatch and the runner's own worker record)
in a disposable workspace, with fixed identities and a fixed clock so the bytes are stable.
test_saved_fixtures.py makes each one again and compares it with the stored tree: the proof
that the fixtures are what the saved flow writes. Both go when the saved flow is retired.

    python3 tests/saved_fixtures.py            # compare every fixture with a fresh capture
    python3 tests/saved_fixtures.py --write    # write them again (review the diff)
"""

import isolation  # noqa: F401  (first: keeps every capture off this computer's own settings)
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
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
# blog, and the save receipts every kind of save leaves at the workspace's top.
NOT_WORK = ('.studio.lock', '.active-article.json')
NOT_WORK_FOLDERS = ('.desk-receipts',)
SCRUBBED = b'/synthetic-capture'

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
    if not root.resolve().is_relative_to(Path(isolation.PLACE).resolve().parent):
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
    'finished-page': lambda c: c.finished(),
    'finished-page-warm': lambda c: c.finished(tone='Warm'),
}


def _tree(root):
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob('*')
        if path.is_file()
        and path.name not in NOT_WORK
        and path.relative_to(root).parts[0] not in NOT_WORK_FOLDERS
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
        stack.enter_context(patch.object(studio, 'datetime', Clock))
        stack.enter_context(patch.object(work_summary, 'datetime', Clock))
        case.setUp()
        try:
            before = _tree(case.root)
            found = MAKERS[state](case)
            made = {name: raw for name, raw in _tree(case.root).items() if before.get(name) != raw}
            # Scrubbed: a supplied file's path names the disposable folder it was added from
            # (a source's `origin`); it is said as SCRUBBED instead. Nothing else may name it.
            place = str(case.base).encode()
            made = {name: raw.replace(place, SCRUBBED) for name, raw in made.items()}
            for name, raw in made.items():
                if place in raw or str(case.base) in name or b'/Users/' in raw:
                    raise AssertionError(state + ': ' + name + ' names this computer')
            if [n.split('/')[1] for n in made if n.startswith('articles/')] and {
                n.split('/')[1] for n in made if n.startswith('articles/')
            } != {found['id']}:
                raise AssertionError(state + ': more than its own blog was written')
            return made
        finally:
            case.doCleanups()


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
        if writing:
            write(name)
        elif capture(name) != stored(name):
            differ.append(name)
    print(json.dumps({'fixtures': len(MAKERS), 'written': writing, 'differ': differ}))
    sys.exit(1 if differ else 0)
