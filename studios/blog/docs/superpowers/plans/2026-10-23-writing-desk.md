# The writing desk: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** new blogs open on one editing desk (section notes, whole-draft notes, selection
edits, versions, optional Finishing) after a short start (type, what you bring, sources and
settings), with voice learning switched off and voice guides as a finishing step.
Spec: `../specs/2026-10-23-writing-desk-design.md`.

**Architecture:** a new `desk.py` owns the desk record (`desk/draft.json`, `desk/versions/`,
`DRAFT.md` kept in step). Desk work runs as new kinds on the existing single-worker tool job
queue (`tool_jobs.py`); a ready job's result is settled into the desk under the studio lock
with a version kept first. Routes are `desk-*` in `management.py`; the page is a new plain
script `desk.js`. Old runs keep `blog_runner.py` and `runner.js` unchanged.

**Tech stack:** Python 3.11 standard library, plain JavaScript and CSS, `unittest`,
`scripts/ci/check-management.cjs` (Node, no packages).

**How this plan is laid out.** Phase 1 is written out in full. Phases 2 to 5 each name their
tasks, files, interfaces and tests; before a phase starts, expand its tasks to the same
step-by-step detail against the code as merged by the phase before it (its files will have
moved). Each phase ends in its own pull request, merged before the next starts.

**Rules for every task** (from `AGENTS.md`): tests first; disposable settings, workspaces and
a fake worker (never the owner's studio, never a provider job); full product names in text;
`ruff format` and `ruff check .` before each commit. Run single test files with
`cd studios/blog/tests && HOME=$TMPDIR/h python3 -m unittest <file> -v`. Port-binding tests
fail inside the sandbox; run them outside it or on the shared Tart runner.

Paths below are relative to `studios/blog/skills/blog-studio/` unless they start with
`studios/` or `tests/` (= `studios/blog/tests/`).

---

## File map

| File | Responsibility |
| --- | --- |
| `scripts/desk.py` (new) | Desk record: split and join, read, save with stale check, versions, restore, create from a manuscript, catalog rows |
| `scripts/desk_jobs.py` (new) | Desk job kinds: build payload and guidance, queue through `tool_jobs`, settle results into the desk |
| `scripts/tool_jobs.py` | Add desk kinds to `KINDS` |
| `scripts/management.py` | `desk-*` POST routes and `desk` GET; team sync of the blog id |
| `scripts/blog_runner.py` | `catalog()` lists desk blogs; finished old run offers Open on the desk |
| `references/modules/desk-edit.md` (new) | The surgical-edit rule for notes and selections |
| `references/modules/desk-write.md` (new) | Writing a section or whole draft from briefs and sources (Phase 2) |
| `assets/management/desk.js` (new) | The desk page |
| `assets/management/index.html` | Load `desk.js` |
| `assets/management/blog.css` | Desk layout (opaque reading surfaces; glass only on toolbars) |
| `assets/management/runner.js` | Route new starts and desk blogs to `desk.js`; Open on the desk button |
| `tests/test_desk.py` (new) | Desk record, versions, stale writes, settle |
| `tests/test_desk_jobs.py` (new) | Job payloads, guidance, one job per blog, settle per kind |
| `scripts/ci/check-management.cjs` | Desk journeys |

---

## Phase 1: the desk with "A draft (edit)"

### Task 1.1: Split and join a draft

**Files:** Create `scripts/desk.py`; Test `tests/test_desk.py`.

- [ ] **Step 1: Write the failing tests**

```python
"""The desk record: a draft as title, opening and sections, with versions."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import tempfile
import unittest
from pathlib import Path

import desk
import studio

DRAFT = """# A synthetic title

An opening paragraph.

## First part

First text.

## Second part

Second text.
"""


class SplitJoinTests(unittest.TestCase):
    def test_split_reads_title_opening_and_sections(self):
        found = desk.split(DRAFT)
        self.assertEqual(found['title'], 'A synthetic title')
        self.assertEqual(found['opening'], 'An opening paragraph.')
        self.assertEqual([s['heading'] for s in found['sections']], ['First part', 'Second part'])
        self.assertEqual(found['sections'][1]['text'], 'Second text.')
        self.assertTrue(all(len(s['id']) == 8 for s in found['sections']))

    def test_join_round_trips(self):
        self.assertEqual(desk.join(desk.split(DRAFT)), DRAFT)

    def test_no_headings_is_one_opening(self):
        found = desk.split('Just prose.\n')
        self.assertEqual(found['sections'], [])
        self.assertEqual(found['opening'], 'Just prose.')

    def test_title_may_be_given_when_the_text_has_none(self):
        found = desk.split('## Only\n\nText.\n', title='Given')
        self.assertEqual(found['title'], 'Given')
```

- [ ] **Step 2: Run them; expect `ModuleNotFoundError: No module named 'desk'`**

Run: `cd studios/blog/tests && HOME=$TMPDIR/h python3 -m unittest test_desk -v`

- [ ] **Step 3: Implement**

```python
"""The writing desk: a blog's draft as title, opening and sections, kept with versions.

DRAFT.md is rewritten on every save so Copy, Download, Google Docs, the team library and the
pre-publish check read the same text as before.
"""

import json
import re
import secrets

import studio

DESK = 'desk'
KEEP = 20  # versions kept per part
PARTS = ('title', 'opening')  # plus each section id


def _id():
    return secrets.token_hex(4)


def split(markdown, title=''):
    text = markdown.replace('\r\n', '\n').strip('\n')
    found = re.match(r'# (?!#)(.+)\n', text + '\n')
    if found:
        title = found.group(1).strip()
        text = text[found.end():]
    pieces = re.split(r'(?m)^## (?!#)(.+)$', text)
    opening = pieces[0].strip()
    sections = [
        {'id': _id(), 'heading': heading.strip(), 'brief': '', 'text': body.strip()}
        for heading, body in zip(pieces[1::2], pieces[2::2])
    ]
    return {'title': title.strip(), 'opening': opening, 'sections': sections}


def join(draft):
    parts = []
    if draft.get('title'):
        parts.append('# ' + draft['title'])
    if draft.get('opening'):
        parts.append(draft['opening'])
    for section in draft['sections']:
        parts.append('## ' + section['heading'] + ('\n\n' + section['text'] if section['text'] else ''))
    return '\n\n'.join(parts) + '\n'
```

- [ ] **Step 4: Run them; expect 4 passed.**
- [ ] **Step 5: Commit** `git commit -m "Split a draft into title, opening and sections"` (with the
      session's co-author line).

### Task 1.2: Create a desk blog from a manuscript, read and save it

**Files:** Modify `scripts/desk.py`; Test `tests/test_desk.py`.

The desk lives in the blog folder `studio.inside(root, 'articles', ident)`:
`desk/draft.json` = `{'revision': int, 'title', 'opening', 'sections', 'style', 'tone',
'length', 'sources': [{source_id, revision, purposes}], 'gaps': [], 'created_at',
'updated_at'}`. The blog's `session.json` comes from `studio.article_record` with
`voice={'mode': 'tone', 'tone': tone}` and `mode='existing'` plus `record['flow'] = 'desk'`.

- [ ] **Step 1: Write the failing tests**

```python
class DeskRecordTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / 'workspace'
        studio.initialize(self.root)

    def make(self):
        return desk.create(self.root, {'title': 'Synthetic', 'manuscript': DRAFT, 'tone': 'Plain'})

    def test_create_writes_the_record_the_draft_and_DRAFT_md(self):
        made = self.make()
        directory = studio.inside(self.root, 'articles', made['id'])
        self.assertEqual((directory / 'DRAFT.md').read_text(), DRAFT)
        record = studio.read_json(directory / 'session.json')
        self.assertEqual(record['flow'], 'desk')
        self.assertEqual(record['voice'], {'mode': 'tone', 'tone': 'Plain'})
        self.assertEqual(desk.read(self.root, made['id'])['revision'], 1)

    def test_save_a_section_bumps_the_revision_and_DRAFT_md(self):
        made = self.make()
        part = made['sections'][0]['id']
        saved = desk.save(self.root, made['id'], 1, part, 'New first text.')
        self.assertEqual(saved['revision'], 2)
        directory = studio.inside(self.root, 'articles', made['id'])
        self.assertIn('New first text.', (directory / 'DRAFT.md').read_text())

    def test_an_outdated_form_is_refused_and_nothing_changes(self):
        made = self.make()
        part = made['sections'][0]['id']
        desk.save(self.root, made['id'], 1, part, 'Second.')
        with self.assertRaisesRegex(ValueError, 'changed since'):
            desk.save(self.root, made['id'], 1, part, 'Stale.')
        self.assertEqual(desk.read(self.root, made['id'])['sections'][0]['text'], 'Second.')

    def test_title_and_opening_are_parts_too(self):
        made = self.make()
        desk.save(self.root, made['id'], 1, 'title', 'Better title')
        self.assertEqual(desk.read(self.root, made['id'])['title'], 'Better title')
        with self.assertRaisesRegex(ValueError, 'Choose a part'):
            desk.save(self.root, made['id'], 2, 'nope', 'x')
```

- [ ] **Step 2: Run; expect failures on `desk.create`.**
- [ ] **Step 3: Implement**

```python
from types import SimpleNamespace

LIMIT = 200_000  # characters in one part


def _paths(root, ident):
    directory = studio.inside(root, 'articles', ident)
    return directory, studio.inside(directory, DESK, 'draft.json')


def create(root, data):
    title = (data.get('title') or '').strip()[:200]
    manuscript = data.get('manuscript') or ''
    if not manuscript.strip():
        raise ValueError('Paste or upload a draft to start on the desk.')
    if len(manuscript) > 1_000_000:
        raise ValueError('Use a draft under one million characters.')
    draft = split(manuscript, title=title)
    if not draft['title']:
        raise ValueError('Give the blog a title.')
    tone = (data.get('tone') or '').strip()[:500]
    args = SimpleNamespace(
        action='create', id=None, title=draft['title'], mode='existing', profile=None,
        author=None, voice='tone', tone=tone, audience=(data.get('audience') or '')[:500],
        blog_type=None, review_folder=None, stop='review', research='supplied-only',
    )
    ident = studio.new_id(draft['title'])
    with studio.locked(root):
        record = studio.article_record(root, args, ident)
        record['voice'] = {'mode': 'tone', 'tone': tone}
        record['flow'] = 'desk'
        directory, target = _paths(root, ident)
        directory.mkdir(parents=True)
        target.parent.mkdir()
        draft.update(
            revision=1, style=data.get('style'), tone=tone, length=data.get('length', 'style'),
            sources=[], gaps=[], created_at=studio.now(), updated_at=studio.now(),
        )
        studio.write_json(target, draft)
        (directory / 'DRAFT.md').write_text(join(draft))
        studio.persist(directory, 'articles', record)
    return {'id': ident, **draft}


def read(root, ident):
    _, target = _paths(root, ident)
    if not target.is_file() or target.is_symlink():
        raise ValueError('This blog is not on the desk.')
    return studio.read_json(target)


def _part(draft, part):
    if part in PARTS:
        return None
    for section in draft['sections']:
        if section['id'] == part:
            return section
    raise ValueError('Choose a part of this draft.')


def _write(root, ident, draft):
    directory, target = _paths(root, ident)
    draft['revision'] += 1
    draft['updated_at'] = studio.now()
    studio.write_json(target, draft)
    (directory / 'DRAFT.md').write_text(join(draft))
    return draft


def save(root, ident, seen, part, text, source='save'):
    if not isinstance(text, str) or len(text) > LIMIT:
        raise ValueError('Keep one part under 200,000 characters.')
    with studio.locked(root):
        draft = read(root, ident)
        if draft['revision'] != seen:
            raise ValueError('This draft changed since you opened it. Reload to see the latest.')
        section = _part(draft, part)
        before = draft[part] if section is None else section['text']
        keep(root, ident, part, before, source)
        if section is None:
            draft[part] = text.strip()
        else:
            section['text'] = text.strip()
        return _write(root, ident, draft)
```

`keep` is added in Task 1.3; for this step define it as a no-op `def keep(*a): pass` and
replace it there.

- [ ] **Step 4: Run; expect all `test_desk` tests to pass.**
- [ ] **Step 5: Commit** "Keep a desk draft and save its parts".

### Task 1.3: Versions and restore

**Files:** Modify `scripts/desk.py`; Test `tests/test_desk.py`.

Versions: `desk/versions/<part>.jsonl`, one JSON object per line
`{'at', 'source', 'text', 'words'}`, newest last, at most `KEEP` lines. `source` is one of
`save`, `rewrite`, `revise-all`, `selection`, `first-pass`, `finishing`, `restore`.

- [ ] **Step 1: Write the failing tests**

```python
class VersionTests(DeskRecordTests):
    def test_each_save_keeps_the_text_before_it(self):
        made = self.make()
        part = made['sections'][0]['id']
        desk.save(self.root, made['id'], 1, part, 'Two.')
        desk.save(self.root, made['id'], 2, part, 'Three.')
        texts = [v['text'] for v in desk.versions(self.root, made['id'], part)]
        self.assertEqual(texts, ['Two.', 'First text.'])  # newest first

    def test_only_twenty_are_kept(self):
        made = self.make()
        part = made['sections'][0]['id']
        for n in range(25):
            desk.save(self.root, made['id'], n + 1, part, 'Text %d.' % n)
        self.assertEqual(len(desk.versions(self.root, made['id'], part)), 20)

    def test_restore_is_itself_a_version(self):
        made = self.make()
        part = made['sections'][0]['id']
        desk.save(self.root, made['id'], 1, part, 'Two.')
        desk.restore(self.root, made['id'], 2, part, 0)  # index 0 = newest kept = 'First text.'
        draft = desk.read(self.root, made['id'])
        self.assertEqual(draft['sections'][0]['text'], 'First text.')
        self.assertEqual(desk.versions(self.root, made['id'], part)[0]['text'], 'Two.')
        self.assertEqual(desk.versions(self.root, made['id'], part)[0]['source'], 'restore')
```

- [ ] **Step 2: Run; expect failures on `desk.versions`.**
- [ ] **Step 3: Implement** (replace the no-op `keep`)

```python
def _versions_path(root, ident, part):
    if part not in PARTS and not re.fullmatch(r'[a-f0-9]{8}', part):
        raise ValueError('Choose a part of this draft.')
    directory, _ = _paths(root, ident)
    return studio.inside(directory, DESK, 'versions', part + '.jsonl')


def keep(root, ident, part, text, source):
    target = _versions_path(root, ident, part)
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = target.read_text().splitlines() if target.is_file() else []
    entry = {'at': studio.now(), 'source': source, 'text': text, 'words': len(text.split())}
    lines = (lines + [json.dumps(entry)])[-KEEP:]
    target.write_text('\n'.join(lines) + '\n')


def versions(root, ident, part):
    target = _versions_path(root, ident, part)
    if not target.is_file():
        return []
    return [json.loads(line) for line in reversed(target.read_text().splitlines()) if line]


def restore(root, ident, seen, part, index):
    found = versions(root, ident, part)
    if not isinstance(index, int) or not 0 <= index < len(found):
        raise ValueError('Choose a saved version.')
    return save(root, ident, seen, part, found[index]['text'], source='restore')
```

- [ ] **Step 4: Run; all pass.** Note `save` keeps the *before* text with the given source,
      so the restore entry records what was replaced.
- [ ] **Step 5: Commit** "Keep versions of each part of a desk draft".

### Task 1.4: Desk job kinds and the surgical-edit guide

**Files:** Create `scripts/desk_jobs.py`, `references/modules/desk-edit.md`; Modify
`scripts/tool_jobs.py` (`KINDS`); Test `tests/test_desk_jobs.py`.

Kinds in Phase 1: `desk-section` (note or write again), `desk-revise-all`, `desk-selection`,
`desk-first-pass`. Each job's `metadata` = `{'article': ident, 'desk': {'part': ..., 'seen':
revision, 'action': ..., 'selection': ...}}`. One desk job per blog at a time.

`references/modules/desk-edit.md`:

```markdown
# Desk edits

You are editing one part of a blog draft for its author.

- Change only what the author's note requires. Reproduce every part the note does not
  require changing verbatim, word for word.
- Do not restructure, reorder, rephrase, tighten or otherwise improve parts the note does
  not mention. Keep the part's length and shape unless the note requires otherwise.
- Keep facts, numbers, names, quotations and links. Never invent experience, customers or
  results. Where the note asks for something the sources cannot support, write what they
  support and add the gap to notes.
- Return only the rewritten part in `content`: no heading, no commentary, no source IDs,
  no editorial placeholders. Put anything the author must supply in `notes`.
```

Selection actions, each one line added to the guidance:
`rephrase` "Rewrite the passage in fresh words with the same meaning.",
`shorten` "Tighten the passage; use noticeably fewer words.",
`expand` "Develop the passage further with one concrete detail, example or consequence from the sources.",
`fix` "Fix grammar, clarity and flow only.", `ask` the person's instruction.

- [ ] **Step 1: Write the failing tests**

```python
"""Desk jobs: what each kind sends, one job per blog, and how a result lands."""

import isolation  # noqa: F401
import tempfile
import unittest
from pathlib import Path

import desk
import desk_jobs
import studio
import tool_jobs
from test_desk import DRAFT


class DeskJobTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / 'workspace'
        studio.initialize(self.root)
        self.made = desk.create(self.root, {'title': 'Synthetic', 'manuscript': DRAFT})
        self.part = self.made['sections'][0]['id']

    def test_a_section_note_sends_the_part_its_neighbours_and_the_edit_rule(self):
        job = desk_jobs.section(self.root, self.made['id'], 1, self.part, 'Add an example.')
        saved = tool_jobs.read(self.root, job['id'])
        self.assertEqual(saved['kind'], 'desk-section')
        self.assertEqual(saved['payload']['part']['text'], 'First text.')
        self.assertEqual(saved['payload']['note'], 'Add an example.')
        self.assertIn('verbatim', saved['guidance'])
        self.assertEqual(saved['metadata']['article'], self.made['id'])

    def test_no_note_writes_the_section_again_without_the_edit_rule(self):
        job = desk_jobs.section(self.root, self.made['id'], 1, self.part, '')
        saved = tool_jobs.read(self.root, job['id'])
        self.assertNotIn('verbatim', saved['guidance'])
        self.assertIn('Write this section again', saved['guidance'])

    def test_one_desk_job_per_blog(self):
        desk_jobs.section(self.root, self.made['id'], 1, self.part, 'One.')
        with self.assertRaisesRegex(ValueError, 'already working'):
            desk_jobs.section(self.root, self.made['id'], 1, self.part, 'Two.')

    def test_a_selection_must_be_in_the_part(self):
        with self.assertRaisesRegex(ValueError, 'no longer in'):
            desk_jobs.selection(self.root, self.made['id'], 1, self.part, 'Absent.', 'fix', '')

    def test_ask_needs_an_instruction(self):
        with self.assertRaisesRegex(ValueError, 'what to do'):
            desk_jobs.selection(self.root, self.made['id'], 1, self.part, 'First', 'ask', '')
```

- [ ] **Step 2: Run; expect `ModuleNotFoundError: desk_jobs`.**
- [ ] **Step 3: Implement `desk_jobs.py` (queueing half)**

```python
"""Desk work on the single-worker tool job queue: queue it, then settle the result."""

import secrets

import desk
import studio
import tool_jobs
from blog_runner import REFERENCES  # the references folder the runner already resolves

KINDS = ('desk-section', 'desk-revise-all', 'desk-selection', 'desk-first-pass')
ACTIONS = {
    'rephrase': 'Rewrite the passage in fresh words with the same meaning.',
    'shorten': 'Tighten the passage; use noticeably fewer words.',
    'expand': 'Develop the passage further with one concrete detail, example or consequence from the sources.',
    'fix': 'Fix grammar, clarity and flow only.',
}
WRITE_AGAIN = (
    'Write this section again from its heading, its brief, the sections before it and the '
    'sources. Keep the kind of post and the tone. Return only the section text.'
)


def _guide(name):
    return (REFERENCES / 'modules' / name).read_text()


def _busy(root, ident):
    for row in tool_jobs.listing(root, ident):
        if row['kind'] in KINDS and row['status'] in ('queued', 'working'):
            raise ValueError('A desk job is already working on this blog. Wait or stop it.')


def _context(root, ident, draft):
    from blog_runner import shared_guidance  # style, tone, length, house guide, as runs use

    return shared_guidance(root, ident, draft)


def _queue(root, ident, kind, payload, guidance, desk_meta):
    with studio.locked(root):
        _busy(root, ident)
    return tool_jobs.create(
        root, secrets.token_hex(16), kind, payload, guidance,
        basis={'desk': desk_meta['seen']}, metadata={'article': ident, 'desk': desk_meta},
    )


def section(root, ident, seen, part, note):
    draft = desk.read(root, ident)
    found = desk._part(draft, part)
    if found is None:
        raise ValueError('Rewrite a section; edit the title and opening directly.')
    note = (note or '').strip()[:4000]
    index = draft['sections'].index(found)
    payload = {
        'title': draft['title'],
        'outline': [{'heading': s['heading'], 'brief': s['brief']} for s in draft['sections']],
        'before': [s['text'] for s in draft['sections'][:index]][-2:],
        'part': found,
        'note': note,
    }
    rule = _guide('desk-edit.md') if note and found['text'] else WRITE_AGAIN
    guidance = rule + '\n\n' + _context(root, ident, draft)
    return _queue(root, ident, 'desk-section', payload, guidance,
                  {'part': part, 'seen': seen, 'action': 'note' if note else 'again'})


def selection(root, ident, seen, part, text, action, instruction):
    draft = desk.read(root, ident)
    found = desk._part(draft, part)
    whole = draft[part] if found is None else found['text']
    if not text or text not in whole:
        raise ValueError('That passage is no longer in this part. Select it again.')
    if action == 'ask':
        instruction = (instruction or '').strip()[:2000]
        if not instruction:
            raise ValueError('Say what to do with the passage.')
        line = instruction
    elif action in ACTIONS:
        line = ACTIONS[action]
    else:
        raise ValueError('Choose rephrase, shorten, expand, fix or ask.')
    payload = {'passage': text[:12_000], 'around': whole[:20_000], 'action': line}
    guidance = _guide('desk-edit.md') + '\n\nAct on the passage only: ' + line
    return _queue(root, ident, 'desk-selection', payload, guidance,
                  {'part': part, 'seen': seen, 'action': action, 'selection': text})
```

`shared_guidance` does not exist yet: add it to `blog_runner.py` by extracting the block in
`job()` that assembles the selected style, tone, length sentence and house guide
(BR around 1993-2005) into `def shared_guidance(root, ident, draft) -> str`, and call it
from `job()` so run output is byte-identical. Add a test in `tests/test_blog_runner.py`
asserting an existing pinned run's guidance is unchanged (compare against the current
function's output captured in the test before the refactor). `REFERENCES` is the
references path the runner already uses; if it is named differently, import that name.

Add the four kinds to `tool_jobs.KINDS`.

- [ ] **Step 4: Run `test_desk_jobs` and `test_blog_runner`; all pass.**
- [ ] **Step 5: Commit** "Queue desk notes and selection edits as tool jobs".

### Task 1.5: Whole-draft note and first pass

**Files:** Modify `scripts/desk_jobs.py`; Test `tests/test_desk_jobs.py`.

`revise_all(root, ident, seen, note)` queues one `desk-revise-all` job whose payload is the
whole draft and the note, with guidance: desk-edit rule plus "Revise every section for this
note with the full draft as context. Return JSON in content: a list of {id, text} for every
section, in order, ids unchanged." (One job, not N: the queue runs one job at a time, and a
single call keeps the sections coherent. Progress is the job's status.)

`first_pass(root, ident, seen, choice)` with `choice` in `('tighten', 'reshape')`:
`tighten` = copy-edit and proofread rule from `manuscript_editor.CHECKS['copyedit']`;
`reshape` = the pinned style's shape. Same JSON return as revise-all. `leave` queues nothing.

- [ ] **Step 1: Tests**: revise-all payload carries every section and the note; an empty note
      is refused ("Write the note for the whole draft."); first pass refuses an unknown
      choice; `leave` returns None and queues nothing.
- [ ] **Step 2: Run; fail.** **Step 3: Implement** following `section()`.
      **Step 4: Run; pass.** **Step 5: Commit** "Queue whole-draft notes and a first pass".

### Task 1.6: Settle a ready job into the desk

**Files:** Modify `scripts/desk_jobs.py`; Test `tests/test_desk_jobs.py`.

`settle(root, ident)` runs on every desk read (GET `desk`), under the lock: for each of this
blog's desk jobs with `status == 'ready'` and not `applied`:

- `desk-section`: if the draft revision still equals `metadata.desk.seen`, save the part
  with `source='rewrite'` and mark `applied=True`; if the draft moved on, set
  `applied=False, error='The draft changed while this was being written. Run it again.'`
  and mark it settled without writing.
- `desk-selection`: same stale check, plus the selection must still occur in the part
  exactly once; replace that occurrence; `source='selection'`.
- `desk-revise-all` and `desk-first-pass`: parse `content` as JSON list of `{id, text}`;
  every id must exist; save each changed section with `source='revise-all'` or
  `'first-pass'` (one version per section), in one revision bump.
- `result.notes` lines become `draft['gaps']` entries (deduplicated, at most 50).

Mark settled jobs by writing `applied` and `settled_at` into the tool job record
(`tool_jobs.write`).

- [ ] **Step 1: Tests** (simulate a finished job by writing `status='ready'` and `result`
      into the saved job, as the existing tool job tests do):
  - a note result lands in the section and keeps the old text as a `rewrite` version;
  - a result for a stale revision is not applied and carries the error;
  - a selection replaces only its passage;
  - a selection whose passage now occurs twice is not applied;
  - revise-all with an unknown id is not applied and nothing changes;
  - notes become gaps.
- [ ] **Step 2: Run; fail.** **Step 3: Implement.** **Step 4: Run; pass.**
- [ ] **Step 5: Commit** "Settle desk job results into the draft with a version kept".

### Task 1.7: Routes

**Files:** Modify `scripts/management.py`; Test `tests/test_desk.py` (route tests use
`management.dispatch` directly, as `test_management_ui.py` does).

POST routes, each taking `{'id', 'seen', ...}`:
`desk-create {title, manuscript | google, sources, style, tone, length, first_pass}`,
`desk-save {part, text}`, `desk-restore {part, index}`, `desk-note {part, note}`,
`desk-revise {note}`, `desk-selection {part, text, action, instruction}`,
`desk-stop {job}` (calls `tool_jobs.control(..., 'cancel', engine)`), `desk-open
{run}` (Task 1.9). GET `desk?id=` returns `desk.read` after `desk_jobs.settle`, plus
`jobs` (this blog's desk jobs, public form) and `versions` counts per part. GET
`desk-versions?id=&part=` returns `desk.versions`.

Wire them like `editor-*`: in `_dispatch`, `if route.startswith('desk-'): import desk_routes`
… keep the routing in a small `desk.dispatch(root, route[5:], data)` function at the bottom
of `desk.py` that validates allowed keys per route (refuse unknown fields with "This request
has fields the desk does not take."). Add `'desk-'` to the two `startswith(('run-',
'editor-'))` checks in `dispatch()` so team `before()` and `saved()` see the blog id, and
`desk-create` joins `run-create` as a route without an id before.

- [ ] **Step 1: Tests**: create then save through `management.dispatch`; unknown fields
      refused; GET `desk` settles a ready job.
- [ ] **Steps 2-5**: fail, implement, pass, commit "Add the desk routes".

### Task 1.8: Desk blogs in the blog list

**Files:** Modify `scripts/blog_runner.py` (`catalog`); Test `tests/test_desk.py`.

In `catalog()`, before the `STATE` check: if `studio.inside(path.parent, 'desk',
'draft.json')` is a file, append `{'id', 'title', 'status': 'desk', 'touched':
draft['updated_at'], 'flow': 'desk', 'jobs': <count queued or working>}` and continue.

- [ ] Test: a desk blog appears in `blog_runner.catalog(root)['items']` with `flow == 'desk'`;
      a deleted one does not (use `blog_delete` as its tests do). Fail, implement, pass,
      commit "List desk blogs with the others".

### Task 1.9: Open a finished old blog on the desk

**Files:** Modify `scripts/desk.py` (`open_run`), `scripts/blog_runner.py` (describe adds
`desk_open: bool`); Test `tests/test_desk.py`.

`open_run(root, ident)`: the blog must be complete with a `DRAFT.md`; if it already has
`desk/draft.json`, return it; otherwise split `DRAFT.md` into `desk/draft.json` with the
run's style and tone, revision 1, and leave the run's own state untouched. `describe()` adds
`desk_open = complete and DRAFT.md exists`.

- [ ] Tests: opening a finished run creates the desk without changing `derived/blog-run.json`;
      opening twice returns the same desk; an unfinished run is refused ("Finish this blog,
      then open it on the desk."). Commit "Open a finished blog on the desk".

### Task 1.10: The desk page

**Files:** Create `assets/management/desk.js`; Modify `index.html` (add
`<script src="/desk.js" defer></script>` after `runner.js`), `runner.js` (route), `blog.css`;
Test `scripts/ci/check-management.cjs`.

Page structure, built with the same `element()`/`sNode` helpers `runner.js` uses (text via
`textContent` only):

- **Toolbar** (glass): back, title, job status ("Rewriting the second section… Stop"),
  Copy, Download, Google Doc, Mark as published, Finishing (disabled until Phase 3).
- **Whole-draft note** card: "Note for the whole draft" textarea and **Revise the draft**.
- **Title** and **opening** as editable cards with **History**.
- **Section cards**: heading, editable text (`contenteditable` plain text, Markdown kept),
  "How should this change?" input with **Rewrite** (or **Write again** when empty), and
  **History**. While a job works on a section, that card shows "Working on this section".
- **Selection bar**: on `selectionchange` inside a section's text, a small floating bar with
  Rephrase, Shorten, Expand, Fix, Ask… (Ask opens an inline input, not `window.prompt`).
- **History sheet**: list of versions (source in words: "Before your edit", "Before a
  rewrite", "Before a restore", …, age, words), **Compare** (word diff, additions and
  removals marked), **Restore**.
- **Sources panel** (side on desktop, folded on phone): the blog's sources and **Needs you
  before publishing** gaps.
- **Autosave**: 1 second after the last keystroke; shows "Saving…/Saved"; on a refused
  stale save, shows "This draft changed. Reload" with a button.
- **Polling**: while a desk job is queued or working, GET `desk` every 3 seconds; stop when
  none are.

`runner.js`: blog list rows and Continue for `flow === 'desk'` open the desk; a finished old
run's page shows **Open on the desk** when `desk_open`; the "Revise or review a draft" and
"Polish a document" start tasks open the desk's edit start (Phase 1 start: title, paste or
upload or Google Doc, kind of post, tone, first pass).

Word diff: a small LCS over words in `desk.js` (`diffWords(a, b) -> [{op, text}]`), capped
at 4,000 words per side (beyond that, show the two texts side by side).

- [ ] **Step 1: Journeys in `check-management.cjs`** (with the existing fake server):
  1. Start "A draft": paste, Start, the desk shows three cards.
  2. Type in a section; after autosave the fake server got `desk-save` with `seen`.
  3. Rewrite with a note posts `desk-note`; the card shows "Working on this section"; when
     the fake job is ready the new text shows.
  4. Select text, Shorten posts `desk-selection` with the exact text.
  5. History lists versions; Compare marks a removed word; Restore posts `desk-restore`.
  6. A stale save shows "This draft changed".
  7. Revise the draft posts `desk-revise`.
  8. A finished old run shows Open on the desk.
- [ ] **Step 2: Run** `node scripts/ci/check-management.cjs`; expect the new journeys to fail.
- [ ] **Step 3: Implement** `desk.js` and the CSS.
- [ ] **Step 4: Run** the checker; `"status":"passed"`. Run root
      `python3 -m unittest tests.test_ui_consistency` from the repository root.
- [ ] **Step 5: Commit** "The desk page".

### Task 1.11: Phase 1 checks and pull request

- [ ] `python3 scripts/ci/run_tests.py --jobs 8` (outside the sandbox), `node
      scripts/ci/check-management.cjs`, `ruff format --check .`, `ruff check .`,
      `python3 scripts/build.py --check`, `scripts/measure_guidance.py --check` (record the
      new `desk-edit.md` in the guidance inventory if the check asks), `command_reference.py
      --check`, `node scripts/ci/check-newcomer.cjs`, root `test_ui_consistency`.
- [ ] CHANGELOG (Unreleased): "Blogs can be edited on the desk: notes per section and for
      the whole draft, selection edits, and versions with compare and restore."
- [ ] Push `claude/writing-desk-1`, open the PR, independent review, merge, restart from the
      checkout launcher for the owner to try.
- [ ] Before the owner's first test, empty the current team library: the owner said on
      2026-10-23 that everything in it is test data and nothing needs to be kept. List what
      will be removed (local library items, and the Team Hub copies if the library is
      shared) and confirm that list with the owner before deleting, since a Team Hub
      deletion reaches every member's workspace.

---

## Phase 2: author and co-author starts

Expanded on 2026-10-23 against the Phase 1 code on `claude/writing-desk` (`desk.py`,
`desk_jobs.py`, `desk.js`). Phase 2 lands on the same branch as Phase 1, one commit per task.

**What a start is.** A start is one desk blog made at **Start** whose draft does not exist
yet. `desk.create` takes a `way`: `draft` (Phase 1, the default), `topic`, `outline` (write
from my outline) or `shape` (shape an outline with me first). For the three new ways it
writes `desk/draft.json` with the title, an empty opening and the sections known so far (none,
or the parsed outline), plus `brief: {point, audience}` and `opening_brief`; DRAFT.md is
written by the first `_write`. Beside it, `desk/start.json` keeps the start itself:

```json
{"schema": 1, "way": "topic", "steps": ["research", "outline", "draft"], "step": "outline",
 "job": "<tool job id>", "started_at": "…", "ended_at": null, "problem": "",
 "open": "draft", "minutes": 6, "notes": "<pasted outline or notes>",
 "research_from": {"documents": true, "sites": [], "web": true}, "contract": {…} | null,
 "phase": "Round 1 of 3, writing the report"}
```

Each step is one desk job on the tool queue, chained when the previous one settles, so the
one-job-per-blog rule, Stop and the settle-under-lock path from Phase 1 hold unchanged.
`open` is `outline` for **Shape an outline with me first** (no draft step), otherwise
`draft`. `desk_jobs.view` returns `start` (the record with `busy`, `elapsed` and the step
in words) so the page shows the progress screen until `ended_at` is set.

Steps per way (`research` only when sites or the web are ticked):

| Way | Steps |
| --- | --- |
| topic | research?, outline, draft |
| outline, parsed into sections | research?, draft |
| outline, notes without headings or list items | research?, outline, draft |
| shape | research?, outline (then the desk opens on the Outline tab) |

Documents only go straight into each job's payload: `_context` already reads the pinned
sources with their stance, as a from-files run reads its files at every step with no claims
map (`blog_runner.create`: "The files are read at every step; only the web adds research
stages").

### Task 2.1: The start record and the outline parser (server)

**Files:** Modify `scripts/desk.py`; Test `tests/test_desk_start.py` (new).

- [ ] **Step 1: Failing tests**
  - `desk.outline_from('# T\n\nWhy.\n\n## One\n\nBrief one.\n\n## Two\n')` returns title `T`,
    opening brief `Why.` and two sections with headings and briefs, empty text, 8-hex ids.
  - Top-level list items become sections and their indented lines the brief
    (`- One\n  - detail\n- Two`); a numbered list too.
  - Plain notes (paragraphs only) return None; one heading only returns None.
  - `desk.create(way='topic', title, point, audience)` writes `desk/draft.json` with no
    sections, `brief`, and `desk/start.json` with `steps == ['outline', 'draft']`; no
    `DRAFT.md` yet; `session.json` has `flow: desk` and the tone voice.
  - `way='topic'` without a point is refused ("Say the point to make, or pick an angle.").
  - `way='outline'` with a parsed outline keeps its sections and briefs and plans
    `['draft']`; with notes it plans `['outline', 'draft']`; `way='shape'` plans
    `['outline']` with `open == 'outline'`.
  - `research_from={'sites': [...], 'web': True}` adds `research` first and keeps the
    choice on the record (`record['research_from']`); sites alone without Harness Research
    are refused with `blog_runner.NEEDS_HARNESS_RESEARCH`.
  - A manuscript with `way='topic'` is refused; unknown ways are refused.
- [ ] **Step 2: Run** `HOME=$TMPDIR/h python3 -m unittest test_desk_start -v`; expect failures.
- [ ] **Step 3: Implement** `outline_from`, the `way` branch of `create` (record mode
  `first-draft`), `start_path`, `read_start`, `write_start`. `CREATE` gains `way`, `point`,
  `audience`, `outline`, `outline_source`, `research_from`.
- [ ] **Step 4: Run; pass.** **Step 5: Commit** "Keep a desk start: its way, its steps and the outline it was given".

### Task 2.2: `desk-angles` before a blog exists

**Files:** Modify `scripts/desk_jobs.py`, `scripts/tool_jobs.py` (`KINDS`, `DESK`),
`scripts/desk.py` (route), `scripts/management.py` (GET view); Test `tests/test_desk_start.py`.

`desk_jobs.angles(root, data)` with `{operation, title, point, audience, style, tone,
sources, library}` queues one `desk-angles` job keyed by the page operation in
`.blog-runs/desk-angles/<operation>.json` (`{job, fingerprint}`); the same request again
returns the same job, a changed one under the same operation is refused. Metadata
`{'article': None, 'desk': {'operation': …}}`. Its payload is `_context` over the chosen
sources (pinned as `_attach` pins them, nothing written to the library), the title, point
and audience; its guidance is the angles rule, `blog-argument-outline.md` (the guide runs
use for angles) and the shared guidance. The worker settles it (`ended`): content must be
JSON, a list of exactly three `{headline, point, audience}` of non-empty strings; otherwise
the job is settled with "The angles came back in a shape Blog Studio cannot read. Ask
again." `angles_view(root, operation)` returns `{operation, status, busy, angles, error}`.
`tool_jobs.once` skips the team guard for a job with no blog.

- [ ] **Step 1: Failing tests**: the payload carries the chosen sources with their stance
  and the point; the same operation returns the same job; a ready result settles into three
  angles; a malformed result (two angles, missing headline, not JSON) is refused readably;
  the route `desk-angles` and GET `desk-angles?operation=` through `management.dispatch` and
  `management.view`; a fake worker runs it end to end through `tool_jobs.once`.
- [ ] **Steps 2-5**: fail, implement, pass, commit "Suggest three angles before a blog exists".

### Task 2.3: `desk-outline`, `desk-draft` and `references/modules/desk-write.md`

**Files:** Create `references/modules/desk-write.md`; Modify `scripts/desk_jobs.py`,
`scripts/blog_runner.py` (name the from-outline and open-gaps sentences as constants used
by `job()` so run guidance stays byte-identical), `scripts/tool_jobs.py`; Test
`tests/test_desk_start.py`.

`desk-write.md` holds only what is new for the desk: write sections from their briefs, one
`##` per outline section in order, keep the given headings, the opening from the opening
brief, the title is given (no `#` line), and nothing editorial in the prose. The job
guidance adds, by reference rather than copy: `blog-argument-outline.md` (outline) or
`blog-write.md` (draft and a section written from its brief), `blog_runner.shared_guidance`
with the length sentence, `RETURN` (evidence and gaps in notes, never in the prose) and the
worker's own policy, which already carries the approved-messaging stance
(`blog_worker.POLICY`).

- `outline_job(root, ident)`: payload `{title, brief, notes, sources, examples, style, tone,
  gaps, research_bundle | research}`; returns JSON `{title, opening_brief, sections:
  [{heading, brief}]}`. Settled only while the draft has no written text: sections get new
  ids, the title is kept when the person gave one.
- `draft_job(root, ident, seen)`: payload adds `outline: [{heading, brief}]` and
  `opening_brief`; returns the whole Markdown. Settled with `desk.split`; the result's
  sections take the outline's ids and briefs by heading order; extra sections get new ids;
  outline sections the result left out stay as they were. Each part with text before keeps
  a `draft` version first. Its meta part is `sections`, so section cards are read-only while
  it works. Refused when the outline has no sections.
- `section()` with no note now reads `desk-write.md` and says the brief: "part.brief says
  what this section must do".

- [ ] **Step 1: Failing tests**: outline guidance has the outline guide, the length sentence
  and RETURN; a ready outline lands as sections with briefs; an outline with no sections or a
  heading over one line is refused readably; a draft lands with the outline's ids and briefs
  by order and keeps `draft` versions of text it replaced; a draft that adds a section keeps
  the extra one; the run's own `job()` guidance is unchanged for from-outline runs (an
  existing test pins it).
- [ ] **Steps 2-5**: commit "Write a desk outline and draft from briefs".

### Task 2.4: The start chain and research before the draft

**Files:** Modify `scripts/desk_jobs.py`, `scripts/tool_jobs.py` (`desk-research` runs
through `desk_jobs.research_run` instead of one worker call), `scripts/desk.py` (routes
`retry`); Test `tests/test_desk_start.py`.

- `begin(root, ident)` queues the start's current step; `desk._create` calls it for the new
  ways (a problem is kept on the start and shown, as the first pass's is).
- When a start job settles applied, the next step is queued (`_advance`); after the last,
  `ended_at` is set. A job that failed, was not applied or was stopped keeps the step and
  says why in `problem`; `desk-retry {id}` queues that step again.
- `desk-research` (one job, no gate): the research plan as a run writes it
  (`STAGES['research-plan']` with its guide), then, with a pinned Harness Research
  (`research_contract.snapshot()` at Start), `synthesis_research.generate` in a temporary
  case published into the blog's `research/` under the lock; without it, one research job
  with the assistant's web search (`STAGES['research']`, as a run without the contract),
  saved as `derived/blog-research.md`. Each step gets the job's time limit. Outline and
  draft jobs then read `research_bundle` as runs do, or `research` text.
- [ ] **Step 1: Failing tests** (fake worker; Harness Research patched as
  `test_blog_runner` does): a topic start chains outline then draft and ends with a draft
  on the desk; with the web ticked research runs first and the outline payload reads its
  findings; a failed research stops the start with its readable problem and Retry queues
  research again; Stop ends the start with "Stopped."; documents-only starts have no
  research step and the outline payload carries the sources.
- [ ] **Steps 2-5**: commit "Chain a desk start: research, outline and draft with no stops".

### Task 2.5: Outline saves, Write the draft, Add a source (server)

**Files:** Modify `scripts/desk.py`, `scripts/desk_jobs.py`; Test `tests/test_desk_start.py`.

- `desk-outline-save {id, seen, sections: [{id?, heading, brief}]}`: rename, reorder, add
  (no id) and remove; ids kept; per-part stale check over the sections it changes plus
  `outline` when order, additions or removals change; refused while an outline or draft
  job works on the blog.
- `desk-draft {id, seen}` queues `draft_job`.
- `desk-sources {id, sources, library}` pins new sources (and library items with a role) on
  the blog record and the desk record; later jobs read them.
- [ ] **Step 1: Failing tests**: reorder keeps ids and text; a rename from an outdated form is
  refused; an added section has an id and no text; removing a section keeps the others;
  saving while a draft job works is refused; a later section rewrite payload carries a source
  added on the desk.
- [ ] **Steps 2-5**: commit "Edit the desk outline and add sources at any time".

### Task 2.6: The start screens and the progress screen (page)

**Files:** Modify `assets/management/desk.js`, `runner.js` (Home tasks, New blog, library
"Write a blog from these" and a wizard without a draft go to the new start), `app.js`
(board New blog), `blog.css`; Test `scripts/ci/check-management.cjs`.

- Step 1 **What are you writing?**: a pick card per kind of post (`run-options` styles, from
  `styles.catalog`) with its summary, and **Something else**.
- Step 2 **What do you have?**: Just a topic (title, who it is for, the point, **Suggest
  three angles** with three editable angle cards on the same screen), An outline or notes
  (paste or upload; **Write from my outline** or **Shape an outline with me first**), A draft
  (Phase 1's start fields and first pass).
- Step 3 **Sources and settings**: `sFilesCard` (files, Google Docs, library, roles),
  **Search my sites** (the saved site list, `sSitePicker`) and **Search the web too**, both
  off, for new writing; Length (new writing); Tone; **Start** at the end.
- The progress screen: "Nothing needed from you. The draft opens here when it is ready, in
  about N minutes." (the outline for Shape), the steps with the current one in words, one
  clock, Stop, and on a problem Retry; the desk opens on its own when it ends.
- [ ] **Step 1: Journeys**: each of the three starts reaches Start with the right payload;
  angles shows three cards and a picked, edited card fills the point; the progress screen's
  first line, clock and Stop; the desk opens on its own; Home tasks open the new start.
- [ ] **Steps 2-5**: commit "Start a blog from a topic, an outline or a draft".

### Task 2.7: The Outline tab and Add a source (page)

**Files:** Modify `assets/management/desk.js`, `blog.css`; Test `check-management.cjs`.

- Draft and Outline tabs on the desk. The Outline tab: a card per section with heading and
  brief (autosaved through `desk-outline-save`), Move up, Move down, Remove (confirmed when
  it has text), **Write this section**, Add a section, and **Write the draft**.
- The sources panel's **Add a source** opens a sheet with `sFilesCard` and adds through
  `desk-sources`.
- [ ] **Step 1: Journeys**: reorder posts ids in the new order with `seen`; Write this
  section posts `desk-note` with no note; Write the draft posts `desk-draft`; Add a source
  posts `desk-sources` with the file and the library pick with its role.
- [ ] **Steps 2-5**: commit "Shape the outline on the desk and add sources there".

### Task 2.8: Checks, docs touch-ups and CHANGELOG

- [ ] Docs where the page's start flow is described (`docs/runner.md`, README start lines).
- [ ] CHANGELOG (Unreleased): "New blogs start on the desk from a topic, an outline or a
  draft, with optional angles, research and an Outline tab."
- [ ] Full checks as in Task 1.11; screenshots with synthetic content in a disposable
  workspace. No push or merge on this branch until the owner asks.

## Phase 3: Finishing

- **3.1 Proposals store**: `desk/proposals/<job>.json` with items `{id, part, before,
  after, note, flag}`; `desk-apply {job, items}` swaps text with a `finishing` version and
  refuses items whose `before` is no longer in the part. Tests.
- **3.2 Proofread** in process: `text_checks.lint` plus repetition over each part; **Fix**
  queues `desk-selection` with action `fix` on the sentence. Tests.
- **3.3 `finish-humanize`** (light, medium, strong) from `references/modules/blog-humanize.md`;
  each suggestion's `before` must occur verbatim; a suggestion changing a number, name,
  quote or link (`text_checks.facts`/`preserve`) is flagged. Tests.
- **3.4 `finish-facts`**: reuse `manuscript_editor.CHECKS['factual-support']` with the
  desk's sources; results as supported, not in your sources, contradicted, with passages;
  "Add a source" opens the sources panel. Tests.
- **3.5 `finish-headline`**: title and opening alternatives as proposals. Tests.
- **3.6 Before publishing**: link the existing pre-publish check, Repurpose (new desk blog
  per output) and Send to Google Doc to desk blogs (they read `DRAFT.md`). Tests that each
  reads the desk's latest text.
- **3.7 Finishing panel** in `desk.js`: preview before and after per item, Apply, Edit,
  Skip, Apply all. Journeys. Checks, CHANGELOG, PR, merge, restart.

## Phase 4: voice guides and the switch

- **4.1 The switch**: `features.voice` (default false) in Blog Studio settings
  (`blog_runner.settings`), returned to the page. Tests: default false.
- **4.2 Server enforcement**: while off, refuse `voice-links-*`, `library-voices`,
  `library-author-*`, `job-create` kinds `voice-learn` and `voice-audition`, `voice-apply`,
  default-voice settings and `profile` on run creation, with "Voices are switched off in
  Blog Studio settings."; `create()` and `writing_defaults.for_create` write Tone. Saved
  voices stay on disk. Tests per route; existing voice tests run with the switch on.
- **4.3 Page**: hide the items listed in the spec's "Hidden for now" when off.
  Journeys with the switch off and on.
- **4.4 Voice guides**: `voice-guide` job kind (samples to guide text, reusing the learning
  guidance without author matching) and hand-written guides, saved as profiles
  (`article_tools.save_profile`) so existing voices appear as guides; screen "Voice guides".
  Tests.
- **4.5 `finish-voice`**: apply a guide to the draft as per-section proposals (reuse
  `advanced_tools.apply_voice` guidance), Apply all, some or none. Tests and journey.
- **4.6** Checks, CHANGELOG, PR, merge, restart.

## Phase 5: docs and cleanup

- **5.1** README, `docs/capabilities.md`, `docs/runner.md` (desk section; the step-by-step
  flow described as the path for older blogs), `references/guided-runs.md`,
  `references/page-tools.md`, `docs/commands.md` regenerated.
- **5.2** Remove start-screen code no longer reachable (old wizard steps, files screen start,
  angles-in-run for new blogs) only where no old run can reach it; keep gate screens.
- **5.3** Full check suite, CHANGELOG, PR, merge, restart.

---

## Self-review against the spec

| Spec section | Task |
| --- | --- |
| What are you writing | 2.1 |
| What do you have: topic and three angles | 2.1, 2.2 |
| Outline or notes: write from it, shape with me | 2.1, 2.3, 2.6 |
| A draft with first pass | 1.2, 1.5, 1.10 |
| Sources and settings for all three | 1.7 (`sources` on create), 2.1, 2.4 |
| Progress with no stops | 2.4, 2.5 |
| Desk: edit, section note, write again, whole-draft note, selection, versions | 1.2-1.6, 1.10 |
| Outline tab | 2.6 |
| Sources panel and gaps | 1.6 (gaps), 1.10 |
| Top bar | 1.10, 3.6 |
| One job per blog, Stop | 1.4, 1.7, 1.10 |
| Finishing tools with preview and apply | 3.1-3.7, 4.5 |
| Voice guides | 4.4 |
| Hidden for now, server enforced | 4.1-4.3 |
| Old blogs and Open on the desk | 1.8, 1.9 |
| DRAFT.md kept in step | 1.2 |
| Testing | each task; 1.11, 2.7, 3.7, 4.6, 5.3 |
