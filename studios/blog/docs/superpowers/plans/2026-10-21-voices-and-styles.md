# Voices and Styles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A blog takes a voice (how one person sounds) and a style (the shape of a kind of writing); styles ship as editable starters and can be learned from examples; voices and styles can be learned from uploads, a LinkedIn export, or links to posts.

**Architecture:** Styles get their own group `styles/` beside `profiles/`, built the same way (record, guide, revisions, pin), owned by a new `scripts/styles.py`. Learning reuses the tool-job scheduler with a new `style-learn` kind. Links go through the voice-links work merged from `claude/voice-from-links-wip` (the reference library's `urls` import, a byline check and reuse of saved posts), extended for style samples; a LinkedIn export arrives through the existing `upload` route, checked by a new `scripts/sample_intake.py`. The page gets one **Voices and styles** sheet and a Style select in the wizard. The worker receives the pinned style beside the pinned voice.

**Tech Stack:** Python 3.11 standard library, vanilla browser JavaScript, `unittest`, the Node browser-script check `scripts/ci/check-management.cjs`.

Spec: `docs/superpowers/specs/2026-10-21-voices-styles-and-blog-deletion-design.md`, section 3. Do the deletion plan (`2026-10-21-blog-deletion-fixes.md`) first; it is independent.

All paths are relative to `studios/blog/`. Run commands from that folder. Tests use temporary folders only.

## File structure

| File | Responsibility |
| --- | --- |
| `skills/blog-studio/scripts/styles.py` (new) | Style storage: create, save, show, retire, pin, read a pinned revision, seed starters, catalog and detail for the page, page save and retire. |
| `skills/blog-studio/scripts/studio.py` | Adds the `style-sample` purpose, the `styles` folder (and its `.shared/styles` mapping in team workspaces), `style_pin`, `style_command`, the `style` CLI group and `list styles`. |
| `skills/blog-studio/assets/styles/*.md` (new, 8 files) | Starter styles with `name` and `summary` front matter. |
| `skills/blog-studio/scripts/blog_runner.py` | A run pins a style, the job payload and guidance carry it, listings name the voice and style, options list styles, `run create --style`. |
| `skills/blog-studio/scripts/blog_worker.py` | One policy paragraph on voice versus style. |
| `skills/blog-studio/scripts/hub_workspace.py` | The local style pin stays out of the Hub projection. |
| `skills/blog-studio/scripts/article_tools.py` | `style-learn` job, optional author background for `voice-learn`. |
| `skills/blog-studio/scripts/tool_jobs.py` | Registers `style-learn`. |
| `skills/blog-studio/scripts/advanced_tools.py` | Page actions `style-save` and `style-retire`. |
| `skills/blog-studio/scripts/management.py` | Views `styles` and `style`; `upload` accepts `{url}` and `{linkedin}` entries with per-link failures. |
| `skills/blog-studio/scripts/voice_links.py` (merged from `claude/voice-from-links-wip`) | A list of links, pasted or as a file, imported through the library's `urls` import and marked as voice samples by author; extended here with style samples. |
| `skills/blog-studio/scripts/sample_intake.py` (new) | Checks a LinkedIn export into the upload's checked shape, with its person as author. |
| `skills/blog-studio/scripts/linkedin_import.py` | Also reads the person's name from `Profile.csv`. |
| `skills/blog-studio/assets/management/runner.js`, `index.html` | Voices and styles sheet, learn/edit/detail/import/link sheets, wizard Style select, About card, upload dialog option. |
| `skills/blog-studio/references/workspace/styles.md` (new), `workspace.md`, `voice-flow.md` | Chat guidance. |
| `docs/runner.md`, `README.md`, `CHANGELOG.md`, `docs/commands.md`, `docs/estimates/blog-studio-token-inventory.json` | Documentation and regenerated inventories. |
| `tests/test_styles.py` (new), `tests/test_blog_runner.py`, `tests/test_advanced_tools.py`, `tests/test_sample_intake.py` (new), `tests/test_voice_links.py` (merged, extended), `scripts/ci/check-management.cjs` | Tests. |

---

### Task 1: Style storage and the `style` command

**Files:**
- Create: `skills/blog-studio/scripts/styles.py`
- Modify: `skills/blog-studio/scripts/studio.py` (`PURPOSES` line 16, `inside` line 58, `_initialize` line 198, after `voice_pin` line 243, `parser()` around line 931, `main()` around lines 1098 and 1181)
- Create: `tests/test_styles.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_styles.py`:

```python
"""Styles: starter copies, revisions, pins and the style-sample purpose."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
from pathlib import Path

from test_editorial_tools import Fixture
import studio
import styles


class StyleTests(Fixture):
    def guide(self, text):
        path = self.base / 'guide.md'
        path.write_text(text)
        return str(path)

    def test_starters_are_copied_once_and_edited_or_retired_ones_stay(self):
        found = styles.catalog(self.root)
        ids = [row['id'] for row in found['styles']]
        self.assertIn('product-announcement', ids)
        self.assertEqual(len(ids), len(list(styles.SEEDS.glob('*.md'))))
        self.assertTrue(
            all(row['kind'] == 'seed' and row['status'] == 'confirmed' for row in found['styles'])
        )
        self.assertTrue(all(row['summary'] for row in found['styles']))
        self.command(
            'style', 'save', '--id', 'product-announcement', '--guide-file', self.guide('Edited.')
        )
        self.command('style', 'retire', '--id', 'how-to', '--expected-revision', '1', '--confirmed')
        self.assertEqual(styles.seed(self.root), [], 'nothing is copied back')
        edited = self.command('style', 'show', '--id', 'product-announcement')
        self.assertEqual((edited['revision'], Path(edited['guide']).read_text()), (2, 'Edited.'))
        self.assertEqual(self.command('style', 'show', '--id', 'how-to')['status'], 'retired')
        starter = Path(styles.SEEDS / 'product-announcement.md').read_text()
        self.assertTrue(starter.startswith('---\nname: Product announcement\nsummary: '))

    def test_a_style_pins_a_revision_and_a_retired_style_is_refused_for_new_work(self):
        created = self.command(
            'style',
            'create',
            '--name',
            'Field notes',
            '--guide-file',
            self.guide('Short sections, one observation each.'),
        )
        self.assertEqual(
            (created['revision'], created['status'], created['kind']), (1, 'provisional', 'learned')
        )
        pin = studio.style_pin(self.root, created['id'])
        self.assertEqual(pin, {'style_id': created['id'], 'revision': 1})
        self.command(
            'style',
            'save',
            '--id',
            created['id'],
            '--guide-file',
            self.guide('Revised.'),
            '--status',
            'confirmed',
        )
        self.assertEqual(
            styles.pinned(self.root, pin),
            {'name': 'Field notes', 'guide': 'Short sections, one observation each.'},
        )
        detail = styles.detail(self.root, created['id'])
        self.assertEqual((detail['revision'], detail['guide']), (2, 'Revised.'))
        self.command(
            'style', 'retire', '--id', created['id'], '--expected-revision', '2', '--confirmed'
        )
        with self.assertRaisesRegex(ValueError, 'retired'):
            studio.style_pin(self.root, created['id'])
        self.assertEqual(studio.style_pin(self.root, created['id'], 1), pin)
        with self.assertRaisesRegex(ValueError, 'Unknown style revision'):
            studio.style_pin(self.root, created['id'], 9)

    def test_style_samples_need_the_style_sample_purpose(self):
        reference = self.source()
        with self.assertRaisesRegex(ValueError, 'style-sample'):
            self.command(
                'style',
                'create',
                '--name',
                'Wrong',
                '--guide-file',
                self.guide('x'),
                '--sample',
                reference['id'],
            )
        self.file.write_text('An example announcement.')
        sample = self.command(
            'source',
            'add',
            '--name',
            'Example',
            '--file',
            str(self.file),
            '--purpose',
            'style-sample',
        )
        created = self.command(
            'style',
            'create',
            '--name',
            'Right',
            '--guide-file',
            self.guide('x'),
            '--sample',
            sample['id'],
        )
        self.assertEqual(created['sample_ids'], [sample['id']])
        self.assertEqual(
            [row['id'] for row in styles.catalog(self.root)['samples']], [sample['id']]
        )

    def test_a_team_workspace_keeps_styles_under_the_shared_folder(self):
        team = self.base / 'team' / 'blogs'
        team.mkdir(parents=True)
        (team / 'hub.json').write_text('{"schema":1,"tool":"blog-studio"}')
        self.assertEqual(
            studio.inside(team, 'styles', 'x'), team / '.shared' / 'styles' / 'x'
        )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_styles -v`
Expected: `ModuleNotFoundError: No module named 'styles'`.

- [ ] **Step 3: Create `styles.py`**

Create `skills/blog-studio/scripts/styles.py`:

```python
"""Styles: the shape of a kind of writing, apart from who writes it.

A style lives under styles/<id>/ as record.json, STYLE.md and revisions/<n>/ copies, the
way a voice profile lives under profiles/. Starter styles ship with the skill under
assets/styles/ and are copied into a workspace the first time its styles are read or
pinned. A copied starter that was edited or retired is left alone: a seed is copied only
when its id is absent.
"""

import json
from pathlib import Path
import re
import tempfile
from types import SimpleNamespace

import studio

SEEDS = Path(__file__).resolve().parents[1] / 'assets' / 'styles'


def parse_seed(text):
    """(name, summary, body) from a starter file's front matter."""
    match = re.match(r'---\n(.*?)\n---\n(.*)', text, re.S)
    if not match:
        raise ValueError('A starter style needs front matter with name and summary.')
    fields = dict(line.split(':', 1) for line in match.group(1).splitlines() if ':' in line)
    name, summary = fields.get('name', '').strip(), fields.get('summary', '').strip()
    if not name or not summary:
        raise ValueError('A starter style needs a name and a summary.')
    return name, summary, match.group(2).strip() + '\n'


def seed(root):
    """Copy every starter whose id is absent. Returns the ids copied."""
    copied = []
    for path in sorted(SEEDS.glob('*.md')):
        ident = studio.identifier(path.stem)
        if studio.inside(root, 'styles', ident).exists():
            continue
        name, summary, body = parse_seed(path.read_text(encoding='utf-8'))
        _create(root, ident, name, body, 'confirmed', [], kind='seed', summary=summary)
        copied.append(ident)
    return copied


def validate_samples(root, values):
    for value in values:
        _, source = studio.item(root, 'sources', value)
        if 'style-sample' not in source['purposes']:
            raise ValueError('Style samples must be classified as style-sample material.')
        if source['status'] != 'ready':
            raise ValueError('Style samples must have readable content.')


def snapshot(directory, record):
    rev = studio.inside(directory, 'revisions', str(record['revision']))
    rev.mkdir(parents=True, exist_ok=True)
    studio.write_json(rev / 'record.json', record)
    studio.atomic(rev / 'STYLE.md', (directory / 'STYLE.md').read_bytes())


def _create(root, ident, name, guide, status, samples, kind='learned', summary=''):
    directory = studio.inside(root, 'styles', ident)
    if directory.exists():
        raise ValueError('Style already exists; use save to create a revision.')
    validate_samples(root, samples)
    if status == 'confirmed' and not guide.strip():
        raise ValueError('A confirmed style needs a readable guide.')
    record = {
        'id': ident,
        'name': name,
        'summary': summary,
        'kind': kind,
        'revision': 1,
        'status': status,
        'sample_ids': list(samples),
        'created_at': studio.now(),
    }
    directory.mkdir(parents=True)
    studio.atomic(directory / 'STYLE.md', guide.encode())
    studio.persist(directory, 'styles', record)
    snapshot(directory, record)
    return record


def pin(root, ident, revision=None):
    """{style_id, revision} for new work; a retired style is refused unless a revision is named."""
    seed(root)
    directory, record = studio.item(root, 'styles', ident)
    if revision is None and record['status'] == 'retired':
        raise ValueError('This style is retired. Choose an active style for new work.')
    version = revision or record['revision']
    if not (studio.inside(directory, 'revisions', str(version)) / 'record.json').is_file():
        raise ValueError('Unknown style revision.')
    return {'style_id': ident, 'revision': version}


def pinned(root, selection):
    """The name and guide of a pinned revision, exactly as saved, for a writing job."""
    directory, _ = studio.item(root, 'styles', selection['style_id'])
    rev = studio.inside(directory, 'revisions', str(selection['revision']))
    return {
        'name': studio.read_json(rev / 'record.json')['name'],
        'guide': (rev / 'STYLE.md').read_text(),
    }


def command(root, args):
    """The style CLI: create, save, show, retire. Mirrors studio.profile_command."""
    seed(root)
    if args.action == 'create':
        ident = studio.identifier(args.id) if args.id else studio.new_id(args.name)
        guide = studio.read_text(args.guide_file) if args.guide_file else ''
        return _create(root, ident, args.name, guide, args.status, args.sample)
    directory, record = studio.item(root, 'styles', args.id)
    if args.action == 'show':
        revision = args.revision or record['revision']
        saved = studio.inside(directory, 'revisions', str(revision))
        if not (saved / 'record.json').exists():
            raise ValueError('Unknown style revision.')
        return {**studio.read_json(saved / 'record.json'), 'guide': str(saved / 'STYLE.md')}
    if args.action == 'retire':
        if args.confirmed is not True or args.expected_revision != record['revision']:
            raise ValueError('Confirm the current style revision before retiring it.')
        if record['status'] != 'retired':
            record.update(status='retired', revision=record['revision'] + 1)
            studio.persist(directory, 'styles', record)
            snapshot(directory, record)
        return record
    guide = studio.read_text(args.guide_file)
    if not guide.strip():
        raise ValueError('Style guide cannot be empty.')
    samples = args.sample if args.sample is not None else record['sample_ids']
    validate_samples(root, samples)
    record['revision'] += 1
    if getattr(args, 'name', None):
        record['name'] = args.name
    record['sample_ids'] = samples
    record['status'] = args.status or record['status']
    studio.atomic(directory / 'STYLE.md', guide.encode())
    studio.persist(directory, 'styles', record)
    snapshot(directory, record)
    return record


def detail(root, ident):
    """One style for the page, with the version token its edits are checked against."""
    seed(root)
    directory, record = studio.item(root, 'styles', ident)
    guide = (directory / 'STYLE.md').read_text()
    return {
        **record,
        'guide': guide,
        'expected': studio.digest(json.dumps([record, guide], sort_keys=True).encode()),
    }


def catalog(root):
    """Every style, starters first, and the ready style samples."""
    seed(root)
    found, samples = [], []
    for file in sorted(studio.inside(root, 'styles').glob('*/record.json')):
        try:
            record = studio.read_json(file)
        except (ValueError, OSError):
            continue
        found.append(
            {
                key: record.get(key)
                for key in ('id', 'name', 'summary', 'kind', 'revision', 'status')
            }
        )
    found.sort(key=lambda row: (row['kind'] != 'seed', (row['name'] or '').lower()))
    for file in sorted(studio.inside(root, 'sources').glob('*/record.json')):
        record = studio.read_json(file)
        if 'style-sample' in record.get('purposes', []) and record.get('status') == 'ready':
            samples.append({key: record.get(key) for key in ('id', 'name', 'author', 'revision')})
    return {'styles': found, 'samples': samples}


def save(root, data):
    """The page's style-save: a new style, or a revision of one shown at `expected`."""
    selected = data.get('style')
    current = detail(root, selected) if selected else None
    if current and data.get('expected') != current['expected']:
        raise ValueError('This style changed. Reload before saving a revision.')
    status = data.get('status', 'provisional')
    if (
        status not in ('provisional', 'confirmed')
        or status == 'confirmed'
        and data.get('confirmed') is not True
    ):
        raise ValueError('Confirm the reviewed style guide, or save it as provisional.')
    guide = data.get('guide')
    if not isinstance(guide, str) or not guide.strip() or len(guide) > 40_000:
        raise ValueError('Give a style guide up to 40,000 characters.')
    name = data.get('name', (current or {}).get('name'))
    if not isinstance(name, str) or not name.strip() or len(name) > 200:
        raise ValueError('Give a style name up to 200 characters.')
    chosen = data.get('samples', (current or {}).get('sample_ids', []))
    if not isinstance(chosen, list) or len(chosen) > 10:
        raise ValueError('Choose up to ten examples.')
    with tempfile.TemporaryDirectory(prefix='blog-style-') as scratch:
        file = Path(scratch) / 'STYLE.md'
        file.write_text(guide)
        result = command(
            root,
            SimpleNamespace(
                action='save' if current else 'create',
                id=selected,
                name=name.strip(),
                guide_file=str(file),
                status=status,
                sample=chosen,
            ),
        )
    return {'style': result['id'], 'revision': result['revision'], 'status': result['status']}


def retire(root, data):
    """The page's style-retire, against the version shown."""
    current = detail(root, data.get('style'))
    if current['expected'] != data.get('expected') or data.get('confirmed') is not True:
        raise ValueError('Confirm the current style before retiring it.')
    record = command(
        root,
        SimpleNamespace(
            action='retire', id=current['id'], expected_revision=current['revision'], confirmed=True
        ),
    )
    return {'style': record['id'], 'status': 'retired', 'revision': record['revision']}
```

- [ ] **Step 4: Wire `studio.py`**

In `skills/blog-studio/scripts/studio.py`:

1. `PURPOSES`: add `'style-sample',` directly after `'voice-sample',`.
2. `inside()`: change the condition `parts[0] in ('articles', 'sources', 'profiles')` to `parts[0] in ('articles', 'sources', 'profiles', 'styles')` and add `'styles': ('.shared', 'styles'),` to the `mapped` dict after the `'profiles'` line. (In a team workspace every top-level folder that does not start with a dot is read as a blog, so styles must live under `.shared` like voices.)
3. `_initialize()`: change `for kind in ('profiles', 'sources', 'articles'):` to `for kind in ('profiles', 'sources', 'articles', 'styles'):`.
4. After `voice_pin` (before `validate_samples`), add:

```python
def style_pin(root, style_id, revision=None):
    import styles

    return styles.pin(root, style_id, revision)


def style_command(root, args):
    import styles

    return styles.command(root, args)
```

5. In `parser()`, change the `list` choices to `choices=('profiles', 'sources', 'articles', 'styles')`, and directly after the `profile` group's `retire.add_argument('--confirmed', action='store_true', required=True)` line add:

```python
    style_group = groups.add_parser('style').add_subparsers(dest='action', required=True)
    create = style_group.add_parser('create')
    create.add_argument('--name', required=True)
    create.add_argument('--id')
    create.add_argument('--guide-file')
    create.add_argument('--status', choices=('provisional', 'confirmed'), default='provisional')
    create.add_argument('--sample', action='append', default=[])
    save = style_group.add_parser('save')
    save.add_argument('--id', required=True)
    save.add_argument('--name')
    save.add_argument('--guide-file', required=True)
    save.add_argument('--status', choices=('provisional', 'confirmed'))
    save.add_argument('--sample', action='append')
    show = style_group.add_parser('show')
    show.add_argument('--id', required=True)
    show.add_argument('--revision', type=int)
    retire = style_group.add_parser('retire')
    retire.add_argument('--id', required=True)
    retire.add_argument('--expected-revision', required=True, type=int)
    retire.add_argument('--confirmed', action='store_true', required=True)
```

6. In `main()`, add `'style',` to the `team_mutation = args.group in (...)` tuple after `'profile',`. Then find how `profile` reaches `profile_command` in the group chain at the end of `main()` (`grep -n "profile_command\|_command'](root" skills/blog-studio/scripts/studio.py`). If it is an explicit `elif args.group == 'profile': result = profile_command(root, args)`, add `elif args.group == 'style': result = style_command(root, args)` beside it. If it is a generic `globals()[args.group + '_command'](root, args)` (or `getattr`), nothing more is needed.

- [ ] **Step 5: Create one starter so the seeding test has something to copy**

Create `skills/blog-studio/assets/styles/product-announcement.md` (the other seven come in Task 2):

```markdown
---
name: Product announcement
summary: Lead with what is new and for whom, one proof point, availability, next step.
---
# Product announcement

A short piece that tells a reader what is new, why it matters to them, and what to do
next. It is read fast, often from a feed, by people deciding whether this concerns them.

## Shape

1. **Headline**: the capability in plain words, not a code name.
2. **Opening**: in two or three sentences, what is new, who it is for, and the problem it
   removes. The news is in the first sentence.
3. **Why it matters**: one or two short paragraphs tying the change to work the reader
   already does. One concrete proof point beats three claims: a number, a before-and-after,
   or a named situation.
4. **What it does**: the two to four things a person can now do, each with one sentence
   of how. A screenshot or short example per item if the material supplies one.
5. **Availability**: where it is on, for which plans or versions, from when, and what it
   costs if that changed.
6. **Next step**: one clear action, such as read the guide, turn it on, or join a session.

## Length and register

400 to 800 words. Direct, present tense, second person where natural. Short paragraphs
and plain headings. Confident about what shipped, exact about what did not.

## A reader expects

- The news in the first sentence, and the audience named early.
- To learn whether they can use it today and how.
- Claims that are specific enough to check.

## Does not belong

- Company history or a tour of the whole product.
- Superlatives without a proof point.
- Roadmap promises stated as if shipped.
- Internal names, ticket numbers or team credits.
```

- [ ] **Step 6: Run the tests**

Run: `python3 -m unittest tests.test_styles -v`
Expected: the seeding test still fails on `self.command('style', 'retire', '--id', 'how-to', ...)` with `Unknown styles ID: how-to` (Task 2 adds it); the other three PASS.

- [ ] **Step 7: Commit**

```bash
git add skills/blog-studio/scripts/styles.py skills/blog-studio/scripts/studio.py skills/blog-studio/assets/styles/product-announcement.md tests/test_styles.py
git commit -m "Add styles: the shape of a kind of writing, kept apart from voices

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The starter styles

**Files:**
- Create: seven more files under `skills/blog-studio/assets/styles/`
- Regenerate: `docs/estimates/blog-studio-token-inventory.json`, `docs/commands.md`

- [ ] **Step 1: Create `release-notes.md`**

```markdown
---
name: Release notes and changelog
summary: Grouped, scannable changes with version, dates and upgrade notes.
---
# Release notes and changelog

A reference a reader scans to find out what changed and whether it affects them. It is
read by people upgrading, debugging, or deciding when to move.

## Shape

1. **Heading**: product, version and date.
2. **Highlights**: at most three changes worth a sentence each, when a release has them.
3. **Grouped changes**: short headings such as Added, Changed, Fixed, Deprecated, Removed,
   Security. One line per change: what changed, where, and who notices. Link each to its
   documentation or issue when the material supplies one.
4. **Upgrade notes**: anything a reader must do, in order, with the consequence of
   skipping it. Breaking changes are named as such and listed first.
5. **Known issues**: what is still open, with a workaround when one exists.

## Length and register

As long as the changes require and no longer; most entries are one line. Neutral,
exact, past tense for what changed and imperative for what the reader must do. Same
wording for the same thing across releases.

## A reader expects

- To find their area by scanning headings, not by reading prose.
- Every breaking change flagged and placed first.
- Versions and dates they can match to what they run.

## Does not belong

- Marketing framing or adjectives.
- Internal refactors that change nothing a reader can observe.
- Promises about future releases.
```

- [ ] **Step 2: Create `technical-deep-dive.md`**

```markdown
---
name: Technical deep dive
summary: Problem, approach, trade-offs, what was measured, what is still open.
---
# Technical deep dive

A long read for practitioners who want to understand how something works and why it
was built that way. It earns trust by showing its reasoning and its numbers.

## Shape

1. **Opening**: the problem in concrete terms, why the obvious approaches fall short,
   and what the piece will show. A reader should know in the first screen whether this
   is their problem.
2. **Context**: the constraints that shaped the design: scale, latency, cost, compatibility,
   team. Only what the later decisions depend on.
3. **Approach**: the design, from the whole to the parts. Diagrams or code where they
   carry meaning; prose where they do not. Each section states a decision and the
   alternative it was chosen over.
4. **Trade-offs**: what got worse, what was given up, and where the design does not apply.
5. **What was measured**: the method, the setup, the numbers and their spread. A result
   without its conditions is not a result.
6. **What is still open**: unsolved parts, next experiments, questions for readers.

## Length and register

1,500 to 3,000 words, with headings a reader can jump between. Precise and plain;
technical terms defined on first use; confident where the evidence is, and explicit
where it is not.

## A reader expects

- Decisions with their alternatives, not just a description of the end state.
- Numbers with conditions and units.
- Enough detail to reproduce the thinking, not necessarily the whole system.

## Does not belong

- A product pitch in the conclusion.
- Hand-waving where a measurement was possible.
- Benchmarks against unnamed or misconfigured competitors.
```

- [ ] **Step 3: Create `how-to.md`**

```markdown
---
name: How-to and tutorial
summary: Prerequisites, numbered steps with checkpoints, a finished state, troubleshooting.
---
# How-to and tutorial

A piece a reader follows while doing the task. Success is a working result at the end,
reached without guessing.

## Shape

1. **Title**: the outcome, in the reader's words ("Deploy X to Y").
2. **What you will build**: two or three sentences and, when the material supplies it,
   a picture of the finished state. How long it takes.
3. **Prerequisites**: versions, access, accounts and prior knowledge, each checkable.
4. **Steps**: numbered. Each step is one action with the exact command, setting or click,
   followed by what the reader should now see. Explanations go in a short note after the
   action, not before it.
5. **Finished state**: how to confirm it worked.
6. **Troubleshooting**: the three or four ways it commonly fails, each with its sign and
   its fix.
7. **Next steps**: where to go from here, briefly.

## Length and register

As many steps as the task needs; each step short. Second person, imperative mood. No
step depends on a detail mentioned only later.

## A reader expects

- To copy commands as written and have them work on the stated versions.
- A checkpoint after each risky step.
- To know early whether their setup qualifies.

## Does not belong

- History or opinion about the tools.
- Alternatives explored inside the step list; put them in a note or leave them out.
- "Simply" and "just".
```

- [ ] **Step 4: Create `point-of-view.md`**

```markdown
---
name: Point of view
summary: A stated position, the strongest objection, evidence, what to do differently.
---
# Point of view

An argument. The reader finishes knowing what the writer believes, why, and what it
would change about their own decisions. It persuades by evidence and fair treatment of
the other side, not by volume.

## Shape

1. **Opening**: the position in one or two sentences, and why now.
2. **The situation**: what most people do today and the reasonable reasons they do it.
3. **The case**: two to four supporting points, each with evidence: data, a documented
   example, or first-hand experience labeled as such.
4. **The strongest objection**: stated as its best proponent would state it, then
   answered honestly, including where it still holds.
5. **What to do differently**: concrete, scoped to who should act and when it does not
   apply.
6. **Close**: the position restated in light of the argument, not a new claim.

## Length and register

900 to 1,500 words. Assured but not combative; first person where the writer's own
experience is the evidence. Claims sized to their support.

## A reader expects

- A position they could disagree with, stated plainly.
- The other side treated fairly.
- To be told what the writer would actually do.

## Does not belong

- Straw men or unnamed "some people say".
- A survey of options with no conclusion.
- Evidence that cannot be traced.
```

- [ ] **Step 5: Create `customer-story.md`**

```markdown
---
name: Customer story
summary: Situation, constraint, what changed, measured outcome, the customer's words.
---
# Customer story

A narrative about one team's result, told so another team in the same situation can
judge whether the approach would work for them. Its credibility is the specifics.

## Shape

1. **Title**: who achieved what, with the headline figure when there is one.
2. **Summary box**: the organisation, their situation, the approach, and the result, in
   four short lines.
3. **The situation**: what they were trying to do and what stood in the way, with the
   constraint that made it hard: scale, time, regulation, budget, legacy.
4. **What they did**: the decisions in order, with the reasoning. Named tools and
   practices only where they mattered to the outcome.
5. **What changed**: measured outcomes with their baseline and period. Qualitative
   outcomes in the customer's own words, attributed.
6. **What they would tell others**: advice and caveats from the team itself.

## Length and register

1,000 to 1,800 words. Narrative past tense; the customer is the protagonist, the
product is a supporting character. Every number has a before, an after, and a time span.

## A reader expects

- To recognise their own situation in the first section.
- Numbers they can compare with their own.
- To hear the customer, not only the vendor.

## Does not belong

- Results without a baseline.
- Quotes that read as written by marketing.
- Details the customer has not agreed to share.
```

- [ ] **Step 6: Create `comparison.md`**

```markdown
---
name: Comparison and evaluation guide
summary: Criteria first, fair treatment of each option, a recommendation by situation.
---
# Comparison and evaluation guide

A guide for a reader choosing between options. It is useful only if the criteria are
stated before the options are judged and each option is described as its own users
would describe it.

## Shape

1. **Opening**: the decision being made, who makes it, and the options considered,
   including why some were left out.
2. **Criteria**: the dimensions that matter for this decision and why, before any option
   is discussed. The reader can reweight them.
3. **Each option**: the same structure for every one: what it is, where it is strongest,
   where it falls short, what it costs. Facts dated and sourced.
4. **Side by side**: a table against the criteria, with notes where a cell needs one.
5. **Recommendation by situation**: "If you are X, choose A because Y", for the two to
   four situations the reader is likely in. No single winner unless there is one.
6. **How to check**: the trial or test a reader can run to confirm the fit.

## Length and register

1,200 to 2,500 words. Even-handed, specific, dated. The writer's own interest, if any,
is disclosed up front.

## A reader expects

- The criteria before the verdict.
- Each option's best case, not a caricature.
- A recommendation they can map to their situation.

## Does not belong

- Features listed without saying whether they matter.
- Pricing or limits without a date.
- A verdict that happens to match the writer's product.
```

- [ ] **Step 7: Create `lessons-learned.md`**

```markdown
---
name: Postmortem and lessons learned
summary: Timeline, contributing causes, what changed, without blame.
---
# Postmortem and lessons learned

An account of something that went wrong, written so others can avoid it. It is trusted
when it is specific about causes and generous about people.

## Shape

1. **Summary**: what happened, who was affected, for how long, and the headline lesson,
   in a short paragraph.
2. **Impact**: what users and the business experienced, with numbers and the period.
3. **Timeline**: detection, response and recovery as timestamped entries. What was known
   at each point, not only what was true.
4. **Contributing causes**: several, each a condition in the system or process. The
   question is what made this possible, not who did it.
5. **What went well**: what limited the damage, briefly.
6. **What changed**: each action with an owner and a state (done, in progress, decided
   against and why).
7. **Lessons**: two to five, stated so another team could apply them.

## Length and register

800 to 1,500 words plus the timeline. Calm, factual, past tense, blameless. Names of
systems, not of people.

## A reader expects

- The sequence of events as it unfolded.
- Causes they can look for in their own systems.
- Follow-ups with owners and status, not intentions.

## Does not belong

- A single root cause when there were several.
- Blame, or praise that implies blame elsewhere.
- Reassurance in place of specifics.
```

- [ ] **Step 8: Run the style tests**

Run: `python3 -m unittest tests.test_styles -v`
Expected: all four PASS (eight starters now exist, including `how-to`).

- [ ] **Step 9: Re-record the guidance inventory and the command reference**

The guidance budget counts every `.md` under `skills/blog-studio/`, so the eight starters grow the library total past its margin on purpose. Run:

```bash
python3 scripts/measure_guidance.py
python3 scripts/measure_guidance.py --check
python3 scripts/command_reference.py
python3 scripts/command_reference.py --check
```

Expected: the first regenerates `docs/estimates/blog-studio-token-inventory.json`; the second prints the inventory JSON and exits 0; the third rewrites `docs/commands.md` with the `style` group and `list styles`; the fourth exits 0. Confirm with `git diff --stat docs/`.

- [ ] **Step 10: Commit**

```bash
git add skills/blog-studio/assets/styles docs/estimates/blog-studio-token-inventory.json docs/commands.md
git commit -m "Ship eight starter styles for writing in the tech industry

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: A run pins a style and the worker reads it

**Files:**
- Modify: `skills/blog-studio/scripts/blog_runner.py` (`inputs` line 201, `survey` return dict line 496, `create` lines 569-589 and 652-715, `job` after the house-style line 977, `options` line 1484, `add_parser` line 1765)
- Modify: `skills/blog-studio/scripts/blog_worker.py:72-76` (`POLICY`)
- Modify: `skills/blog-studio/scripts/hub_workspace.py:236-243` (the excluded record keys)
- Test: `tests/test_blog_runner.py` (class `RunnerCase`)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_blog_runner.py`, in `RunnerCase`, after `test_delete_accepts_the_title_as_a_person_types_it` (from the deletion plan) or after `test_delete_needs_the_shown_version_and_the_typed_title`:

```python
    def test_a_run_pins_its_style_and_the_job_carries_it(self):
        self.assertIn(
            'product-announcement', [row['id'] for row in runner.options(self.root)['styles']]
        )
        found = self.create(page=True, style='product-announcement')
        _, record = studio.item(self.root, 'articles', found['id'])
        self.assertEqual(record['style'], {'style_id': 'product-announcement', 'revision': 1})
        self.assertEqual((found['style_name'], found['voice_name']), ('Product announcement', None))
        _, payload, guidance = runner.job(self.root, found['id'])
        self.assertEqual(payload['style']['name'], 'Product announcement')
        self.assertIn('Lead with what is new', payload['style']['guide'])
        self.assertIn('the style wins', guidance)
        self.assertIn('the style wins', blog_worker.POLICY)
        guide = self.base / 'style.md'
        guide.write_text('Changed later.')
        self.command('style', 'save', '--id', 'product-announcement', '--guide-file', str(guide))
        _, payload, _ = runner.job(self.root, found['id'])
        self.assertNotIn('Changed later.', payload['style']['guide'], 'a later save does not move the pin')
        self.command(
            'style', 'retire', '--id', 'product-announcement', '--expected-revision', '2', '--confirmed'
        )
        with self.assertRaisesRegex(ValueError, 'retired'):
            self.create(page=True, style='product-announcement')
        with self.assertRaisesRegex(ValueError, 'Unknown styles'):
            self.create(page=True, style='no-such-style')
        plain = self.create(page=True)
        self.assertNotIn('style', studio.item(self.root, 'articles', plain['id'])[1])
        self.assertIsNone(runner.job(self.root, plain['id'])[1]['style'])
        self.assertIsNone(plain['style_name'])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest tests.test_blog_runner.RunnerCase.test_a_run_pins_its_style_and_the_job_carries_it -v`
Expected: FAIL with `KeyError: 'styles'`.

- [ ] **Step 3: Pin the style in `create()`**

In `blog_runner.create`, add `'style',` to the `allowed` set (after `'profile',`). After

```python
    profile = data.get('profile') or None
    if profile:
        studio.voice_pin(root, profile)
```

add:

```python
    style = data.get('style') or None
    if style:
        studio.style_pin(root, style)  # a retired or unknown style is refused before anything is saved
```

After

```python
    if profile:
        record['voice'] = {'mode': 'profile', **studio.voice_pin(root, profile)}
```

add:

```python
    if style:
        record['style'] = studio.style_pin(root, style)
```

- [ ] **Step 4: Carry the style into the payload, the listing and the guidance**

In `inputs()`, after the `voice` block (the lines ending `voice.pop('revision')`) add:

```python
    style = None
    if record.get('style'):
        import styles

        style = styles.pinned(root, record['style'])
```

and add `'style': style,` to the `payload` dict after `'voice': voice,`.

Add these two functions above `survey()`:

```python
def voice_name(root, record):
    """The pinned voice's current name, for listings; None for a described tone."""
    voice = record.get('voice') or {}
    if voice.get('mode') != 'profile':
        return None
    try:
        return studio.item(root, 'profiles', voice['profile_id'])[1]['name']
    except (ValueError, KeyError):
        return None


def style_name(root, record):
    if not record.get('style'):
        return None
    try:
        return studio.item(root, 'styles', record['style']['style_id'])[1]['name']
    except (ValueError, KeyError):
        return None
```

In the dict `survey()` returns, after `'brief': run['brief'],` add:

```python
        'voice_name': voice_name(root, record),
        'style_name': style_name(root, record),
```

In `job()`, directly after `guidance += '\n\n' + (references / 'style/house.md').read_text()` add:

```python
    if payload.get('style') and stage in ('outline', 'draft', 'review', 'package'):
        guidance += (
            '\n\nSELECTED STYLE: '
            + payload['style']['name']
            + '. Its guide is in style.guide. The style says the shape of this kind of writing: '
            'structure, moves, length, headings and register. The selected voice says how its '
            'author sounds. Where they conflict on wording, the voice wins; where they conflict '
            'on structure, the style wins. Neither invents facts, experience or sources.'
        )
```

In `options()`, add `import styles` beside `import brand_skill` and `'styles': styles.catalog(root)['styles'],` to the returned dict after `'profiles': records('profiles'),`.

In `add_parser()`, add `'style',` to the `for name in (...)` tuple after `'profile',`.

- [ ] **Step 5: The worker policy and the Hub projection**

In `skills/blog-studio/scripts/blog_worker.py`, after the existing `POLICY += """\nWhen a selected brand contract ...` block add:

```python
POLICY += """\nWhen a selected style is supplied in style.guide, it says the shape of this kind of writing:
structure, moves, length, headings and register. The selected voice says how its author sounds.
Where they conflict on wording, the voice wins; where they conflict on structure, the style wins.
Neither invents facts. A style never adds biography or first-person experience."""
```

In `skills/blog-studio/scripts/hub_workspace.py`, in the tuple of record keys left out of `data` (the one containing `'hub_projection'`), add `'style',  # a local pin until styles are shared Hub items` after `'hub_projection',`.

- [ ] **Step 6: Run the tests**

Run: `python3 -m unittest tests.test_blog_runner tests.test_styles -v`
Expected: all PASS, including the new test.

- [ ] **Step 7: Commit**

```bash
git add skills/blog-studio/scripts/blog_runner.py skills/blog-studio/scripts/blog_worker.py skills/blog-studio/scripts/hub_workspace.py tests/test_blog_runner.py
git commit -m "Let a blog take a style beside its voice, pinned by revision

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Learning a style, and a LinkedIn background for a voice

**Files:**
- Modify: `skills/blog-studio/scripts/article_tools.py` (`samples` line 30, `voice_basis` line 85, `request` line 131, `apply` lines 248-300, `job_view` line 455)
- Modify: `skills/blog-studio/scripts/tool_jobs.py:8` (`KINDS`)
- Modify: `skills/blog-studio/scripts/advanced_tools.py:55-85` (`dispatch`)
- Modify: `skills/blog-studio/scripts/management.py:1802-1816` (`view`)
- Test: `tests/test_advanced_tools.py` (class `ContextJobTests`)

- [ ] **Step 1: Write the failing tests**

Add to `ContextJobTests` in `tests/test_advanced_tools.py`, after `test_voice_learning_permission_confirmation_audition_retirement_and_pins`:

```python
    def classified(self, text, purpose):
        source = self.source(text)
        folder, record = studio.item(self.root, 'sources', source['id'])
        record['purposes'] = [purpose]
        studio.persist(folder, 'sources', record)
        return source['id']

    def test_style_learning_saves_a_provisional_style_apart_from_any_voice(self):
        import styles

        example = self.classified('What is new, for whom, and where to get it.', 'style-sample')
        with self.assertRaisesRegex(ValueError, 'Confirm'):
            self.create('style-learn', name='Launch note', samples=[example])
        with self.assertRaisesRegex(ValueError, 'style-sample'):
            self.create('style-learn', name='Launch note', samples=[self.source()['id']], confirmed=True)
        job = self.create('style-learn', name='Launch note', samples=[example], confirmed=True)
        saved = self.jobs.read(self.root, job['id'])
        self.assertEqual(saved['payload']['style_name'], 'Launch note')
        self.assertIn('Ignore who wrote them', saved['guidance'])
        self.assertNotIn('article', saved['metadata'])
        self.jobs.once(self.engine)
        receipt = self.tools.apply(self.root, {'job': job['id']})
        found = styles.detail(self.root, receipt['style'])
        self.assertEqual(
            (found['status'], found['kind'], found['sample_ids'], found['guide']),
            ('provisional', 'learned', [example], 'Prepared synthetic text.'),
        )
        self.assertEqual([row['id'] for row in self.tools.voices(self.root)['profiles']], [])
        with self.assertRaisesRegex(ValueError, 'Confirm'):
            styles.save(self.root, {'style': found['id'], 'expected': found['expected'], 'guide': 'Reviewed', 'status': 'confirmed'})
        receipt = styles.save(
            self.root,
            {'style': found['id'], 'expected': found['expected'], 'guide': 'Reviewed', 'status': 'confirmed', 'confirmed': True},
        )
        self.assertEqual((receipt['revision'], receipt['status']), (2, 'confirmed'))
        with self.assertRaisesRegex(ValueError, 'changed'):
            styles.save(self.root, {'style': found['id'], 'expected': found['expected'], 'guide': 'Stale', 'status': 'provisional'})
        current = styles.detail(self.root, found['id'])
        self.assertEqual(
            advanced_tools.dispatch(self.root, {'action': 'style-retire', 'style': found['id'], 'expected': current['expected'], 'confirmed': True})['status'],
            'retired',
        )
        with self.assertRaisesRegex(ValueError, 'retired'):
            studio.style_pin(self.root, found['id'])

    def test_voice_learning_can_take_an_author_background(self):
        sample = self.classified('Synthetic authored passage with a short rhythm.', 'voice-sample')
        about = self.classified('Platform engineer who writes about rollouts.', 'author-background')
        with self.assertRaisesRegex(ValueError, 'author-background'):
            self.create('voice-learn', name='Synthetic Author', samples=[sample], background=sample, confirmed=True)
        job = self.create('voice-learn', name='Synthetic Author', samples=[sample], background=about, confirmed=True)
        saved = self.jobs.read(self.root, job['id'])
        self.assertEqual(saved['payload']['author_background'], 'Platform engineer who writes about rollouts.')
        self.assertIn('author_background is biography', saved['guidance'])
        self.jobs.once(self.engine)
        receipt = self.tools.apply(self.root, {'job': job['id']})
        folder, _ = studio.item(self.root, 'profiles', receipt['profile'])
        self.assertEqual((folder / 'BACKGROUND.md').read_text(), 'Platform engineer who writes about rollouts.')
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_advanced_tools.ContextJobTests -v`
Expected: the two new tests FAIL (`Choose a supported contextual task.` and a payload without `author_background`).

- [ ] **Step 3: Register the kind**

In `skills/blog-studio/scripts/tool_jobs.py` change `KINDS` to:

```python
KINDS = {
    'voice-learn',
    'voice-audition',
    'style-learn',
    'repurpose',
    'interview-question',
    'interview-outline',
}
```

- [ ] **Step 4: Samples by purpose, background, and the style basis**

In `skills/blog-studio/scripts/article_tools.py`, replace `samples()` with:

```python
def samples(root, selected, purpose='voice-sample'):
    if (
        not isinstance(selected, list)
        or not 1 <= len(selected) <= 10
        or len(set(selected)) != len(selected)
    ):
        raise ValueError(
            'Choose one to ten different authored voice samples.'
            if purpose == 'voice-sample'
            else 'Choose one to ten different examples of this kind of writing.'
        )
    if purpose == 'voice-sample':
        studio.validate_samples(root, selected)
    else:
        import styles

        styles.validate_samples(root, selected)
    from manuscript_preview import text_only

    found = []
    for ident in selected:
        folder, record = studio.item(root, 'sources', ident)
        body = text_only((folder / 'content.md').read_text())
        if len(body) > 80_000:
            raise ValueError('Use shorter samples for learning.')
        found.append({'id': ident, 'revision': record['revision'], 'record': record, 'text': body})
    return found


def background(root, ident):
    """Author background from a readable source classified as author-background."""
    folder, record = studio.item(root, 'sources', ident)
    if 'author-background' not in record['purposes'] or record['status'] != 'ready':
        raise ValueError(
            'Author background must be a readable source classified as author-background.'
        )
    body = (folder / 'content.md').read_text()
    if len(body) > 20_000:
        raise ValueError('Use a shorter author background.')
    return body
```

Replace `voice_basis()` with:

```python
def voice_basis(root, data):
    selected = samples(root, data['samples'])
    current = profile(root, data['profile'])['expected'] if data.get('profile') else None
    parts = [selected, current]
    if data.get('background'):
        parts.append(background(root, data['background']))  # unchanged basis without one
    return fingerprint(parts), selected


def style_basis(root, data):
    import styles

    selected = samples(root, data['samples'], 'style-sample')
    current = styles.detail(root, data['style'])['expected'] if data.get('style') else None
    return fingerprint([selected, current]), selected
```

- [ ] **Step 5: The jobs**

In `request()`, replace the `voice-learn` branch with:

```python
    if kind == 'voice-learn':
        if data.get('confirmed') is not True:
            raise ValueError('Confirm these are permitted authored voice samples before analysis.')
        name = text(data.get('name'), 'an author/profile name', 200)
        metadata = {
            'name': name,
            'samples': data.get('samples'),
            'profile': data.get('profile'),
            'background': data.get('background') or None,
        }
        basis, selected = voice_basis(root, metadata)
        payload = {
            'author': name,
            'authored_samples': selected,
            'author_background': background(root, metadata['background'])
            if metadata['background']
            else '',
        }
        guidance = (
            (REFERENCES / 'blog-voice-profile.md').read_text()
            + '\nInfer a provisional voice guide from these authored samples only. Describe observable style and uncertainty. Separate voice from factual expertise, supplied branding and generic house style. Do not invent biography or anecdotes. Return the editable guide as Markdown, with a short synthetic audition paragraph clearly labeled invented sample text, not author experience. Do not confirm or apply the profile.'
            + '\nauthor_background is biography and expertise supplied by the author for identity; it is not prose to imitate, and career facts are never inferred from the samples.'
        )
    elif kind == 'style-learn':
        if data.get('confirmed') is not True:
            raise ValueError('Confirm you may analyze these examples before starting.')
        name = text(data.get('name'), 'a style name', 200)
        metadata = {'name': name, 'samples': data.get('samples'), 'style': data.get('style')}
        basis, selected = style_basis(root, metadata)
        payload = {'style_name': name, 'examples': selected}
        guidance = (
            'Describe the kind of writing these examples share, as an editable Markdown style '
            'guide named ' + name + '. Cover the structure and order of parts, opening and closing '
            'moves, typical length, heading habits, what every example includes, what varies, the '
            'register a reader of this kind expects, and what does not belong. Ignore who wrote '
            'them: no voice, biography, first person or author preferences. Where the examples '
            'disagree, say so. With a single example, say the guide is thin and provisional. End '
            'with two short lists, "A reader expects" and "Does not belong". Add one short '
            'synthetic audition paragraph clearly labeled invented sample text. Do not confirm '
            'or apply the style.'
        )
```

In `apply()`, change the basis check at the top so it reads:

```python
    if kind == 'voice-learn':
        basis, _ = voice_basis(root, metadata)
    elif kind == 'style-learn':
        basis, _ = style_basis(root, metadata)
    elif kind == 'voice-audition':
```

In the `voice-learn` branch of `apply()`, replace the `with tempfile.TemporaryDirectory(prefix='blog-voice-guide-') as scratch:` block with:

```python
        with tempfile.TemporaryDirectory(prefix='blog-voice-guide-') as scratch:
            guide = Path(scratch) / 'VOICE.md'
            guide.write_text(content)
            about = None
            if metadata.get('background'):
                about = Path(scratch) / 'BACKGROUND.md'
                about.write_text(background(root, metadata['background']))
            result = studio.profile_command(
                root,
                SimpleNamespace(
                    action='save' if metadata.get('profile') else 'create',
                    id=metadata.get('profile'),
                    name=metadata['name'],
                    guide_file=str(guide),
                    background_file=str(about) if about else None,
                    rules_file=None,
                    status=status,
                    sample=metadata['samples'],
                ),
            )
```

Directly after that `voice-learn` branch's `receipt = {...}` add:

```python
    elif kind == 'style-learn':
        import styles

        content = text(content, 'the style guide', 40_000)
        status = data.get('status', 'provisional')
        if (
            status not in ('provisional', 'confirmed')
            or status == 'confirmed'
            and data.get('confirmed') is not True
        ):
            raise ValueError('Explicitly confirm the reviewed style, or save it as provisional.')
        with tempfile.TemporaryDirectory(prefix='blog-style-guide-') as scratch:
            guide = Path(scratch) / 'STYLE.md'
            guide.write_text(content)
            result = styles.command(
                root,
                SimpleNamespace(
                    action='save' if metadata.get('style') else 'create',
                    id=metadata.get('style'),
                    name=metadata['name'],
                    guide_file=str(guide),
                    status=status,
                    sample=metadata['samples'],
                ),
            )
        receipt = {'style': result['id'], 'revision': result['revision'], 'status': result['status']}
```

In `job_view()`, add `elif kind == 'style-learn': basis, _ = style_basis(root, metadata)` after the `voice-learn` line.

- [ ] **Step 6: Page actions and views**

In `skills/blog-studio/scripts/advanced_tools.py`, add `'style-save',` and `'style-retire',` to the action tuple at the top of `dispatch()` and, after the `profile-retire` lines, add:

```python
        if action == 'style-save':
            import styles

            return styles.save(root, data)
        if action == 'style-retire':
            import styles

            return styles.retire(root, data)
```

In `skills/blog-studio/scripts/management.py` `view()`, change the voices condition to `if name in ('voices', 'voice', 'styles', 'style', 'interview', 'tool-job', 'variants', 'variant'):` and inside the `with studio.locked(root):` block add before `if name == 'voices':`:

```python
            if name in ('styles', 'style'):
                import styles

                return styles.catalog(root) if name == 'styles' else styles.detail(root, arg('style'))
```

- [ ] **Step 7: Run the tests**

Run: `python3 -m unittest tests.test_advanced_tools tests.test_styles -v`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add skills/blog-studio/scripts/article_tools.py skills/blog-studio/scripts/tool_jobs.py skills/blog-studio/scripts/advanced_tools.py skills/blog-studio/scripts/management.py tests/test_advanced_tools.py
git commit -m "Learn a style from examples, and let a LinkedIn background inform a voice

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Links through the voice-links branch, LinkedIn exports through upload

**Files:**
- Merge: local branch `claude/voice-from-links-wip` (commit `953be17`, on main `6fdb241`), which adds `skills/blog-studio/scripts/voice_links.py`, the `library voice-links` command, the desk routes `voice-links-preview` and `voice-links-import`, the page flow `sVoiceLinks` and `tests/test_voice_links.py`. Its own plan is `docs/superpowers/plans/2026-10-21-voice-links-from-a-file.md`.
- Modify: `skills/blog-studio/scripts/voice_links.py` (`classify`, `sample_status`, `preview`, `run`, `fingerprint`, `operation_for`, `collection_name`) for style samples
- Create: `skills/blog-studio/scripts/sample_intake.py` (LinkedIn exports only)
- Modify: `skills/blog-studio/scripts/linkedin_import.py:80-90` (`parse`, the Profile.csv fields)
- Modify: `skills/blog-studio/scripts/management.py:418-479` (`upload_files`)
- Create: `tests/test_sample_intake.py`; extend `tests/test_voice_links.py`

**One route for links.** Links go through the branch's `voice_links`, which reads the
list, derives the site scope, and imports through the reference library's own `urls`
import: the same pinned fetch, extraction, size limits, batches of 25, reuse of posts
already in the library (Hub-only ones are checked out) and Hub sharing. It then marks each
post as a sample for the chosen author once its byline agrees, holds back mismatches
until kept, and retries failed links on request. There is no second fetcher: the
`{url}` upload entry and `sample-links` route drafted earlier are dropped. The trade-off,
accepted: imported posts also appear in the reference library, under a collection named
"Published posts by <author>". A LinkedIn export is still one `upload` entry, because it
is a file, not a list of pages.

- [ ] **Step 1: Bring this branch up to date and merge the voice-links branch**

Call the `sync_with_base_branch` tool (it merges `main`, which now has #61 to #63,
on the host); resolve any conflict it reports, then:

```bash
git merge --no-ff claude/voice-from-links-wip -m "Merge the voice-from-links work into the voices and styles branch

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
python3 -m unittest tests.test_voice_links -v
node scripts/ci/check-management.cjs
```

Expected: 14 tests PASS and the browser check exits 0. If the merge conflicts in
`runner.js` with the deletion plan's edits, keep both: they touch different functions.
Do not run the branch's import against the owner's example file here; that fetches
public posts and needs the owner's go-ahead.

- [ ] **Step 2: Write the failing tests for style samples from links**

Add to `tests/test_voice_links.py`, using its own stub fetcher and page builder (read the
top of the file for their names; the branch calls the stub `Pages`). The test below
writes them as `Pages(...)` and `html(title, byline)`; rename to match:

```python
    def test_links_can_become_style_samples_without_a_byline_check(self):
        pages = Pages(
            {
                'https://example.com/news/one': html('One', 'Someone Else'),
                'https://example.com/news/two': html('Two', ''),
            }
        )
        text = 'https://example.com/news/one\nhttps://example.com/news/two\n'
        data = {'text': text, 'author': 'Product announcements', 'purpose': 'style-sample'}
        shown = voice_links.preview(self.root, data)
        result = voice_links.run(
            self.root,
            {**data, 'operation': 'c' * 32, 'expected': shown['expected']},
            reader=pages,
            delay=0,
        )
        samples = [row for row in result['posts'] if row.get('sample')]
        self.assertEqual(len(samples), 2, 'a byline naming someone else does not hold a style sample back')
        for row in samples:
            _, record = studio.item(self.root, 'sources', row['id'])
            self.assertIn('style-sample', record['purposes'])
            self.assertNotIn('voice-sample', record['purposes'])
            self.assertNotEqual(record.get('author'), 'Product announcements', 'the label is not an author')
        import styles

        self.assertEqual(len(styles.catalog(self.root)['samples']), 2)
        with self.assertRaisesRegex(ValueError, 'voice samples or style samples'):
            voice_links.preview(self.root, {**data, 'purpose': 'reference'})
```

Adjust the result shape (`result['posts']`, `row['id']`, `row['sample']`) to what
`voice_links.run` returns on the branch; its existing tests show it.

- [ ] **Step 3: Run it to verify it fails**

Run: `python3 -m unittest tests.test_voice_links -v`
Expected: the new test FAILS with `Unknown voice import field.` from `run` (or from the
desk route's field check).

- [ ] **Step 4: Thread a purpose through `voice_links`**

In `skills/blog-studio/scripts/voice_links.py`:

1. Add near the constants:

```python
PURPOSES = ('voice-sample', 'style-sample')


def purpose_of(data):
    purpose = data.get('purpose', 'voice-sample')
    if purpose not in PURPOSES:
        raise ValueError('Choose voice samples or style samples.')
    return purpose
```

2. `preview`: call `purpose = purpose_of(data)` first, include `purpose` in the returned
   dict and in `expected` (`sha(encoded([author, found['scope'], posts, purpose]))`). For
   a style sample, `author` is the label of the examples (for example "Product
   announcements"); it is still checked with `studio.checked_author` for length.
3. `fingerprint` and `operation_for`: add the purpose as the last element of the
   encoded list (`data.get('purpose', 'voice-sample')`), so a voice import and a style
   import of the same list are different operations.
4. `run`: add `'purpose'` to the allowed field set, read `purpose = purpose_of(data)`,
   save it in the `state` written by `start` (`'purpose': purpose`) and pass it to every
   `sample_status(...)` call.
5. `collection_name(root, author, purpose='voice-sample')`: base name
   `'Published posts by ' + author` for voices and `'Examples: ' + author` for styles;
   pass the purpose from `start`.
6. Replace `classify` and the byline part of `sample_status` with:

```python
def classify(directory, record, author, purpose='voice-sample'):
    """Mark one saved post as a sample. A voice sample takes the author's name; a style
    sample keeps whatever author the post has, since a style is not a person's.
    False when nothing changes."""
    purposes = list(record.get('purposes') or [])
    library = dict(record.get('library') or {})
    if purpose not in purposes:
        purposes.append(purpose)
    voice = purpose == 'voice-sample'
    if purposes == record.get('purposes') and (
        not voice
        or record.get('author') == author
        and (not library or library.get('author') == author)
    ):
        return False
    blog_library.save_revision(directory, record)
    record['purposes'] = purposes
    if voice:
        record['author'] = author
        if library:
            library['author'] = author
            record['library'] = library
    record['revision'] += 1
    studio.persist(directory, 'sources', record)
    return True
```

and in `sample_status(root, ident, author, kept, changed, purpose='voice-sample')`, guard
the mismatch check with the purpose and pass it on:

```python
    if purpose == 'voice-sample' and names and not any(same_author(n, author) for n in names):
        found['mismatch'] = True
        if not kept:
            return found
        found['kept'] = True
    if classify(directory, record, author, purpose):
        changed.append(record['id'])
    return {**found, 'sample': True}
```

7. `management.voice_links_route`: add `'purpose'` to the preview route's allowed fields
   (`{'text', 'author', 'site', 'purpose'}`).
8. `blog_library.add_parser`, the `voice-links` subcommand: add
   `p.add_argument('--purpose', choices=('voice-sample', 'style-sample'), default='voice-sample')`,
   and pass `purpose=args.purpose` into the data `voice_links.command` builds (read
   `command` on the branch; it assembles `text`, `author`, `site`, `keep`, `retry`).

- [ ] **Step 5: Run the voice-links tests**

Run: `python3 -m unittest tests.test_voice_links tests.test_styles -v`
Expected: all PASS, the branch's 14 and the new one.

- [ ] **Step 6: Write the failing LinkedIn tests**

Create `tests/test_sample_intake.py`:

```python
"""Writing samples from a LinkedIn export, by its author."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import base64
import csv
import io
import zipfile

from test_editorial_tools import Fixture
import management
import studio


def export(articles=(('A first article', '<p>One paragraph.</p>'),), headline='Platform engineer', summary='Writes about rollouts.'):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        rows = io.StringIO()
        writer = csv.DictWriter(rows, fieldnames=['First Name', 'Last Name', 'Headline', 'Summary'])
        writer.writeheader()
        writer.writerow({'First Name': 'Synthetic', 'Last Name': 'Author', 'Headline': headline, 'Summary': summary})
        archive.writestr('Profile.csv', rows.getvalue())
        for index, (title, body) in enumerate(articles, 1):
            archive.writestr(
                f'Articles/Articles/{index}.html',
                f'<html><head><title>{title}</title></head><body>{body}</body></html>',
            )
    return base64.b64encode(buffer.getvalue()).decode()



class LinkedInTests(Fixture):
    def upload(self, files, purpose='voice-sample', operation='a' * 32, **extra):
        return management.upload(
            self.root,
            {'operation': operation, 'files': files, 'purpose': purpose, 'analyze': False, **extra},
        )

    def test_a_linkedin_export_becomes_background_and_voice_samples_by_its_author(self):
        result = self.upload([{'linkedin': export()}])
        self.assertEqual(
            [(row['filename'], row['purpose'], row['state'], row['author']) for row in result['files']],
            [
                ('LinkedIn · About', 'author-background', 'ready', 'Synthetic Author'),
                ('LinkedIn · A first article', 'voice-sample', 'ready', 'Synthetic Author'),
            ],
        )
        folder, about = studio.item(self.root, 'sources', result['files'][0]['source']['id'])
        self.assertEqual((about['purposes'], about['author']), (['author-background'], 'Synthetic Author'))
        self.assertIn('Writes about rollouts.', (folder / 'content.md').read_text())
        folder, article = studio.item(self.root, 'sources', result['files'][1]['source']['id'])
        self.assertEqual((article['purposes'], article['status'], article['author']), (['voice-sample'], 'ready', 'Synthetic Author'))
        self.assertIn('One paragraph.', (folder / 'content.md').read_text())
        self.assertEqual(result['next_step'], 'Every file has text.')
        # A colleague's export: the name given for the request wins over the profile's.
        named = self.upload([{'linkedin': export()}], operation='9' * 32, author='Nick Example')
        self.assertEqual({row['author'] for row in named['files']}, {'Nick Example'})

    def test_an_export_without_articles_says_so_and_a_bad_zip_is_refused(self):
        result = self.upload([{'linkedin': export(articles=())}], operation='b' * 32)
        self.assertEqual(len(result['files']), 1)
        self.assertIn('No article samples', result['files'][0]['note'])
        with self.assertRaisesRegex(ValueError, 'LinkedIn export'):
            self.upload([{'linkedin': base64.b64encode(b'not a zip').decode()}], operation='c' * 32)
```

Run: `python3 -m unittest tests.test_sample_intake -v`
Expected: FAIL with `Upload a Markdown, text, HTML, DOCX, or PDF.` (the export entry is
not recognized yet).

- [ ] **Step 7: Read the person's name from the export**

In `skills/blog-studio/scripts/linkedin_import.py`, in `parse()`, add `'name': '',` to the
result dict after `'headline': '',`, and after the line
`result['summary'] = (rows[0].get('Summary') or '').strip()` add:

```python
                result['name'] = ' '.join(
                    part
                    for part in (
                        (rows[0].get('First Name') or '').strip(),
                        (rows[0].get('Last Name') or '').strip(),
                    )
                    if part
                )
```

Change the module docstring to `"""Read only profile background, the person's name and article samples from a supplied LinkedIn ZIP."""`.

- [ ] **Step 8: Create `sample_intake.py`**

```python
"""Writing samples that arrive as a LinkedIn export.

The export becomes the checked rows management.upload saves for files: its About text as
author background and each article as a voice sample, all by its person. Links to posts
are not read here; they go through voice_links and the library import.
"""

import base64
import binascii
import zipfile

import linkedin_import

MAX_ARCHIVE = 10 * 1024 * 1024
NOT_AN_EXPORT = 'That file is not a LinkedIn export zip. Download "Get a copy of your data" again.'


def checked_linkedin(root, entry):
    """The About text and each article of a LinkedIn export, as checked uploads. The
    About text is author background; the articles are authored voice samples."""
    if set(entry) != {'linkedin'} or not isinstance(entry['linkedin'], str):
        raise ValueError('Give the LinkedIn export on its own.')
    try:
        data = base64.b64decode(entry['linkedin'], validate=True)
    except (binascii.Error, ValueError):
        raise ValueError(NOT_AN_EXPORT) from None
    if not data or len(data) > MAX_ARCHIVE:
        raise ValueError('Upload a LinkedIn export of at most 10 MiB; request only Profile and Articles.')
    try:
        found = linkedin_import.parse(data)
    except zipfile.BadZipFile:
        raise ValueError(NOT_AN_EXPORT) from None
    rows = []
    author = found.get('name') or None  # the request's own author name wins over this
    about = '\n\n'.join(part for part in (found['headline'], found['summary']) if part)
    if about:
        rows.append(
            _row('linkedin-about.md', 'LinkedIn · About', about, 'LinkedIn export: Profile.csv', 'author-background', author)
        )
    for index, article in enumerate(found['articles'], 1):
        rows.append(
            _row(
                'linkedin-article-%d.md' % index,
                'LinkedIn · ' + article['title'][:480],
                article['text'],
                'LinkedIn export: ' + article['origin'],
                'voice-sample',
                author,
            )
        )
    if found['limitations']:
        rows[0]['note'] = ' '.join(found['limitations'])
    return rows


def _row(filename, title, text, origin, purpose, author):
    return {
        'filename': filename,
        'shown': title,
        'suffix': '.md',
        'content': text.encode(),
        'text': text,
        'status': 'ready',
        'note': '',
        'title': title,
        'origin': origin,
        'purpose': purpose,
        'author': author,
    }
```

- [ ] **Step 9: Teach `upload_files` the LinkedIn entry and an author for the request**

In `skills/blog-studio/scripts/management.py`, in `upload_files`:

1. Add `import sample_intake` as the first line of the body.
2. Change the field check to `if set(data) - {'operation', 'files', 'purpose', 'keep', 'analyze', 'author'}:`.
3. After the `if data.get('keep') and purpose == 'material':` block add
   `author = studio.checked_author(data['author']) if data.get('author') else None`.
4. Replace the `checked = [...]` comprehension with:

```python
    checked = []
    for entry in (entry if isinstance(entry, dict) else {} for entry in files):
        if 'linkedin' in entry:
            checked.extend(sample_intake.checked_linkedin(root, entry))
        else:
            checked.append((checked_google if 'google' in entry else checked_upload)(root, entry))
```

5. Replace the body of the `for entry in checked:` loop with:

```python
        for entry in checked:
            chosen = entry.get('purpose', purpose)
            whose = author or entry.get('author')
            source = save_upload(
                root, staging, entry, chosen, whose, analyze=data.get('analyze', True)
            )
            saved.append(source['id'])
            if chosen != 'material':
                source = share(root, 'source', source)
                receipts.append(receipt(root, 'Uploaded reference', source, 'source'))
            row = {
                'filename': entry.get('shown', entry['filename']),
                'source': source,
                'state': entry['status'],
                'chars': len(entry['text']) if entry['text'] else 0,
                'note': entry['note'],
                'purpose': chosen,
                'author': whose,
            }
            if entry.get('link'):
                row['link'] = entry['link']
            rows.append(row)
```

Update the docstring's last sentence to: `A LinkedIn export expands into its About text and its articles, and an author named for the request is recorded on every source it saves.`

- [ ] **Step 10: Run the LinkedIn and upload tests**

Run: `python3 -m unittest tests.test_sample_intake tests.test_editorial_tools.MaterialUploadTests tests.test_editorial_tools.ManagementTests tests.test_management_imports tests.test_blog_studio -v`
Expected: all PASS. `test_blog_studio` holds the existing LinkedIn parser test
(`test_profile_only_export_is_not_mistaken_for_writing_samples`); if it compares the
parser's whole result, add `'name'` with the fixture's first and last name to its expected
dict rather than loosening the assertion. Then regenerate the command reference:
`python3 scripts/command_reference.py && python3 scripts/command_reference.py --check`.

- [ ] **Step 11: Commit**

```bash
git add skills/blog-studio/scripts/voice_links.py skills/blog-studio/scripts/blog_library.py skills/blog-studio/scripts/sample_intake.py skills/blog-studio/scripts/linkedin_import.py skills/blog-studio/scripts/management.py tests/test_voice_links.py tests/test_sample_intake.py docs/commands.md
git commit -m "Take style samples from links too, and voice samples from a LinkedIn export

Links keep one route, the voice-links import through the reference library.
A style sample skips the byline check and keeps the post's own author.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: The page

**Files:**
- Modify: `skills/blog-studio/assets/management/runner.js` (`newBlog` line 143, `sWizard` line 158, `sStartBlog` line 165, `sRun` about card line 170, `sToolSamples` line 497, `sVoiceTools` line 500, `sLearnVoice` line 505, `sToolJob` lines 553-561)
- Modify: `skills/blog-studio/assets/management/index.html:40` (the `upload-purpose` select)
- Test: `scripts/ci/check-management.cjs`

- [ ] **Step 1: Write the failing browser checks**

In `scripts/ci/check-management.cjs`:

(a) In the wizard block that begins `f.set('defaults',defaults);f.run("studio.options={settings:{defaults},sources:[],profiles:[],agents:{codex:true}};studio.screen='new';studio.draft={...defaults,step:0,...` (near line 942), change `profiles:[]` to `profiles:[],styles:[{id:'product-announcement',name:'Product announcement',kind:'seed'},{id:'field-notes',name:'Field notes',kind:'learned'}]` and, after the line that asserts `'Start writing'` is on the page, add:

```js
  {
    const select=descendants(f.get('studio-page')).find(e=>e.id==='new-style');
    assert.ok(select,'the second step offers a Style');
    assert.deepEqual(select.children.map(o=>[o.value,o.textContent]),[['','No particular style'],['product-announcement','Product announcement (starter)'],['field-notes','Field notes']]);
    assert.equal(select.value,'','no style by default');
  }
```

(b) Add this function after `filesJourney` and call it with `await voicesAndStyles();` right after `await filesJourney();` inside `check()`:

```js
// Voices and styles: one sheet lists both, a style can be read and learned, and a LinkedIn
// export is sent to the upload route as one entry whose articles become the voice samples.
async function voicesAndStyles(){
  const posts=[];
  const kinds={styles:[{id:'product-announcement',name:'Product announcement',summary:'Lead with what is new.',kind:'seed',revision:1,status:'confirmed'}],samples:[{id:'example',name:'Launch post',author:''}]};
  const f=fixture((url,options)=>{
    if(options?.body)posts.push({url,data:JSON.parse(options.body)});
    if(url.startsWith('/api/voices'))return {profiles:[{id:'voice',name:'Synthetic Author',revision:1,status:'provisional'}],samples:[{id:'sample',name:'Authored passage',author:'Synthetic Author'},{id:'article',name:'LinkedIn · A first article',author:''}]};
    if(url.startsWith('/api/styles'))return kinds;
    if(url.startsWith('/api/style?'))return {...kinds.styles[0],guide:'# Product announcement\n\nLead with what is new.',sample_ids:[],expected:'style-version'};
    if(url==='/api/tool-action')return {id:'b'.repeat(32),kind:'style-learn',status:'queued',metadata:{name:'Launch note',samples:['example']},attempts:0};
    if(url==='/api/upload')return {files:[{filename:'LinkedIn · About',source:{id:'about'},state:'ready',chars:40,note:'',purpose:'author-background',author:'Synthetic Author'},{filename:'LinkedIn · A first article',source:{id:'article'},state:'ready',chars:400,note:'',purpose:'voice-sample',author:'Synthetic Author'}],receipts:[],state:'saved',next_step:'Every file has text.'};
    return {items:[]};
  });f.loadRunner();
  const sheet=()=>descendants(f.get('sheet')),text=()=>sheet().map(e=>e.textContent);
  await f.run('sVoiceTools()');
  for(const label of ['Voices','Styles','Learn a voice from samples','Import a LinkedIn export','Add links to posts','Learn a style from examples','Product announcement'])assert.ok(text().includes(label),label+' in '+text().join('|'));
  // Links open the merged voice-links flow, for voices and, from Styles, for style samples.
  f.run('sVoiceLinks=(found,profile,article,purpose)=>{window.linksOpened=purpose||"voice-sample";}');
  await sheet().find(e=>e.textContent==='Add links to posts').listeners.click();assert.equal(f.run('window.linksOpened'),'voice-sample');
  await f.run('sVoiceTools()');await sheet().find(e=>e.textContent==='Add links to examples').listeners.click();assert.equal(f.run('window.linksOpened'),'style-sample');
  await f.run("sStyleDetail('product-announcement')");
  assert.ok(text().includes('Edit this style guide'));assert.ok(text().includes('Retire this style'));
  // Learning a style needs the permission box, then sends the chosen examples.
  await f.run('sVoiceTools()');await sheet().find(e=>e.textContent==='Learn a style from examples').listeners.click();
  await sheet().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.equal(posts.some(p=>p.url==='/api/tool-action'),false,'nothing starts before the permission box is checked');
  const name=sheet().find(e=>e.id==='learn-style-name');name.value='Launch note';name.listeners.input();
  const example=sheet().find(e=>e.value==='example');example.checked=true;example.listeners.change();
  sheet().find(e=>e.id==='learn-style-permission').checked=true;
  await sheet().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  const learn=posts.find(p=>p.url==='/api/tool-action').data;
  assert.equal(learn.kind,'style-learn');assert.equal(learn.name,'Launch note');assert.deepEqual(learn.samples,['example']);assert.equal(learn.confirmed,true);
  assert.equal(f.get('sheet').children[0].children[0].textContent,'Learn a style');
  // The LinkedIn export goes up as one entry; its articles are preselected as voice samples.
  await f.run('sVoiceTools()');await sheet().find(e=>e.textContent==='Import a LinkedIn export').listeners.click();
  const file=sheet().find(e=>e.id==='linkedin-file');file.files=[{name:'export.zip',size:4,arrayBuffer:async()=>new Uint8Array([80,75,3,4]).buffer}];
  await sheet().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  const sent=posts.find(p=>p.url==='/api/upload').data;
  assert.deepEqual(Object.keys(sent.files[0]),['linkedin']);assert.equal(sent.purpose,'voice-sample');assert.equal(sent.analyze,false);
  assert.ok(text().includes('Learn Synthetic Author’s voice from these articles'),text().join('|'));
  await sheet().find(e=>e.textContent==='Learn Synthetic Author’s voice from these articles').listeners.click();
  assert.deepEqual(sheet().filter(e=>e.type==='checkbox'&&e.checked).map(e=>e.value),['article'],'the About text is background, not a sample');
  assert.equal(sheet().find(e=>e.id==='learn-voice-name').value,'Synthetic Author','the export’s person names the voice');
}
```

- [ ] **Step 2: Run the check to verify it fails**

Run: `node scripts/ci/check-management.cjs`
Expected: `AssertionError: the second step offers a Style`.

- [ ] **Step 3: The wizard, the payload and the About card**

In `runner.js`:

`newBlog`: in the `studio.draft={...}` literal add `style:'',` after `profile:'',`, and add `'style'` to the `for(const key of ['goal','audience','author','tone','profile',...])` list after `'profile'`.

`sWizard`: replace `disclosure('Voice and brand',sField('new-profile','Voice',draft,'profile',{options:[['','Use the described tone'],...studio.options.profiles.map(profile=>[profile.id,profile.name])]}),` with:

```js
disclosure('Voice, style and brand',sField('new-profile','Voice',draft,'profile',{options:[['','Use the described tone'],...studio.options.profiles.map(profile=>[profile.id,profile.name])]}),sField('new-style','Style',draft,'style',{options:[['','No particular style'],...(studio.options.styles||[]).map(style=>[style.id,style.name+(style.kind==='seed'?' (starter)':'')])],hint:'The shape of the piece, such as a product announcement. The voice says how it sounds.'}),
```

`sStartBlog`: in the `payload` literal add `style:draft.style||'',` after `profile:draft.profile,`.

`sRun` about card: in the `sCard('About this blog', ...)` call, after the `found.brand?sNode('p','quiet','Brand: '+...):null,` argument add:

```js
found.voice_name||found.style_name?sNode('p','quiet',[found.voice_name?'Voice: '+found.voice_name:null,found.style_name?'Style: '+found.style_name:null].filter(Boolean).join(' · ')):null,
```

- [ ] **Step 4: The Voices and styles sheet and its sub-sheets**

Replace `sToolSamples` with:

```js
function sToolSamples(found,held,legend='Authored samples permitted for voice analysis'){
  const box=sNode('fieldset'),title=sNode('legend','',legend);box.append(title);
  for(const source of found.samples){const label=sNode('label','check'),input=sNode('input');input.type='checkbox';input.value=source.id;input.checked=held.samples.includes(source.id);input.addEventListener('change',()=>{held.samples=input.checked?[...held.samples,source.id]:held.samples.filter(id=>id!==source.id);});label.append(input,sNode('span','',source.name+(source.author?' · '+source.author:'')));box.append(label);}return box;
}
```

Replace `sVoiceTools` with:

```js
async function sVoiceTools(article=null){
  const found=await sTaskRead('Voices and styles','voices');if(!found)return;
  const kinds=await api('styles');
  const voices=sNode('div');for(const profile of found.profiles)voices.append(sCard(profile.name,sNode('p','quiet',`Revision ${profile.revision} · ${profile.status}`),sButton('Read and manage '+profile.name,()=>sVoiceProfile(profile.id,article))));
  const styles=sNode('div');for(const style of kinds.styles)styles.append(sCard(style.name,sNode('p','quiet',(style.summary?style.summary+' · ':'')+(style.kind==='seed'?'Starter · ':'')+`Revision ${style.revision} · ${style.status}`),sButton('Read and manage '+style.name,()=>sStyleDetail(style.id,article))));
  sOpenSheet('Voices and styles',sNode('p','','A voice is how one person sounds: you, or someone you write for. A style is the shape of a kind of writing. Both stay provisional until confirmed, and choosing one never rewrites a manuscript.'),
    sNode('h3','sheet-part','Voices'),voices,sButton('Learn a voice from samples',()=>sLearnVoice(found)),sButton('Import a LinkedIn export',()=>sLinkedInImport()),sButton('Add links to posts',()=>sVoiceLinks(found,null,article)),sButton('Upload an authored sample',()=>{sCloseSheet();$('upload-purpose').value='voice-sample';$('upload-blog').checked=false;$('upload-analyze').checked=false;$('upload-dialog').showModal();}),sButton('Write a voice guide',()=>sEditVoice({name:'',guide:'',status:'provisional',sample_ids:[]},found)),
    sNode('h3','sheet-part','Styles'),styles,sButton('Learn a style from examples',()=>sLearnStyle(kinds)),sButton('Add links to examples',()=>sVoiceLinks(found,null,article,'style-sample')),sButton('Write a style guide',()=>sEditStyle({name:'',guide:'',status:'provisional',sample_ids:[]},kinds)),
    sButton('Close',sCloseSheet));
}
```

Replace the first two lines of `sLearnVoice` (its signature and the `held` line) so the function begins:

```js
function sLearnVoice(found,profile=null,preselected=[],background=null,author=''){
  studio.voiceLearning||={};const held=studio.voiceLearning[profile?.id||'new']||={name:profile?.name||'',samples:[...(profile?.sample_ids||[])],background:null,operation:operationId()},form=sNode('form'),problem=sNode('p','problem');problem.setAttribute('role','alert');
  if(preselected.length){held.samples=[...preselected];held.background=background;}
  if(author&&!held.name)held.name=author;
```

In the same function change the name field's label from `'Author or profile name'` to `'Whose voice is this?'` and give it `hint:'The author’s name: yours, or the person you write for.'`. Change the permission checkbox text to `'I have permission to analyze this writing with my selected assistant.'`. In its submit handler add `background:held.background||null,` after `profile:profile?.id||null,`.

Add these functions directly after `sLearnVoice`:

```js
function sLearnStyle(kinds,style=null,preselected=[]){
  studio.styleLearning||={};const held=studio.styleLearning[style?.id||'new']||={name:style?.name||'',samples:[...(style?.sample_ids||[])],operation:operationId()},form=sNode('form'),problem=sNode('p','problem');problem.setAttribute('role','alert');
  if(preselected.length)held.samples=[...preselected];
  form.append(sField('learn-style-name','Style name',held,'name',{required:true,max:200,hint:'The kind of writing, such as Product announcement, not a person.'}),sToolSamples(kinds,held,'Examples of this kind of writing'),sNode('p','quiet','Only ready sources classified as style samples are listed. Add links or upload examples first.'),problem);
  const check=sNode('input');check.type='checkbox';check.id='learn-style-permission';const confirm=sNode('label','check');confirm.append(check,sNode('span','','I may analyze these examples with my selected assistant.'));form.append(confirm);const submit=sNode('button','button','Learn a provisional style');submit.type='submit';form.append(submit);
  form.addEventListener('submit',async event=>{event.preventDefault();if(!check.checked){problem.textContent='Confirm you may analyze these examples before starting.';return;}submit.disabled=true;try{const job=await api('tool-action',sTaskPayload(held,{action:'job-create',kind:'style-learn',operation:held.operation,name:held.name,samples:held.samples,style:style?.id||null,confirmed:true}));sToolJob(job);}catch(error){problem.textContent=error.message;}finally{submit.disabled=false;}});
  sOpenSheet('Learn a style from examples',form,sButton('Cancel',sCloseSheet));
}
async function sStyleDetail(id,article){
  const found=await sTaskRead('Style','style?style='+encodeURIComponent(id));if(!found)return;
  const problem=sNode('p','problem');problem.setAttribute('role','alert');
  sOpenSheet(found.name,sNode('p','quiet',(found.kind==='seed'?'Starter style · ':'')+`Revision ${found.revision} · ${found.status}`),sAdd(sNode('article','paper doc'),window.TrainingStudioMarkdown.render(found.guide)),
    sButton('Edit this style guide',async()=>sEditStyle(found,await api('styles'))),
    sButton('Export style guide',()=>sDownload({name:found.id+'-style.md',content:found.guide})),
    found.status!=='retired'?sButton('Retire this style',()=>sOpenSheet('Retire this style?',sNode('p','','It leaves future style choices. Existing blogs keep their pinned revision.'),sButton('Retire it',async button=>busy(button,'Retiring…',async()=>{await api('tool-action',{action:'style-retire',style:id,expected:found.expected,confirmed:true});await sVoiceTools(article);})),sButton('Cancel',sCloseSheet))):null,
    problem,sButton('All voices and styles',()=>sVoiceTools(article)),sButton('Close',sCloseSheet));
}
function sEditStyle(style,kinds){
  studio.styleEdits||={};const held=studio.styleEdits[(style.id||'new')+':'+(style.expected||'')]||={name:style.name,guide:style.guide,samples:[...(style.sample_ids||[])]},form=sNode('form'),problem=sNode('p','problem');problem.setAttribute('role','alert');
  form.append(sField('style-name','Style name',held,'name',{required:true,max:200}),sField('style-guide','Style guide',held,'guide',{long:true,max:40000,required:true}),sToolSamples(kinds,held,'Examples of this kind of writing'));
  const confirm=sNode('input');confirm.type='checkbox';const label=sNode('label','check');label.append(confirm,sNode('span','','I reviewed this guide and confirm it describes the intended kind of writing.'));form.append(label,problem);
  const save=confirmed=>async button=>busy(button,'Saving…',async()=>{try{if(confirmed&&!confirm.checked)throw new Error('Review and confirm the guide first.');await api('tool-action',{action:'style-save',style:style.id||null,expected:style.expected,name:held.name,guide:held.guide,samples:held.samples,status:confirmed?'confirmed':'provisional',confirmed});await sVoiceTools();}catch(error){problem.textContent=error.message;}});
  sOpenSheet('Edit style guide',form,sButton('Save provisional guide',save(false)),sButton('Confirm style guide',save(true)),sButton('Cancel',sCloseSheet));
}
function sIntakeRows(found){const list=sNode('ul','rows');for(const row of found.files)list.append(sAdd(sNode('li','row'),sAdd(sNode('div','row-text'),sNode('h3','row-title',row.filename),sNode('p','quiet',row.state==='failed'?'Not read: '+row.note:row.note||(row.state==='ready'?row.chars+' characters of text':'Saved without text')))));return list;}
function sLinkedInImport(){
  const held={author:'',operation:operationId()},form=sNode('form'),problem=sNode('p','problem'),result=sNode('div');problem.setAttribute('role','alert');
  const steps=sAdd(sNode('ol',''),...['On LinkedIn, open Settings & Privacy, then Data privacy, then Get a copy of your data.','Choose Profile and Articles, request the archive and wait for LinkedIn’s email.','Download the zip and choose it here. Only Profile.csv and the articles are read; connections and messages are not.'].map(words=>sNode('li','',words)));
  const input=sNode('input','input');input.type='file';input.accept='.zip';input.id='linkedin-file';input.setAttribute('aria-label','LinkedIn export zip');
  const submit=sNode('button','button button-filled','Read the export');submit.type='submit';
  form.append(steps,input,sField('linkedin-author','Whose export is this? (optional)',held,'author',{max:200,hint:'Leave it blank to use the name in the export. Give a name when a colleague handed you theirs.'}),problem,result,submit);
  form.addEventListener('submit',async event=>{event.preventDefault();const file=input.files?.[0];if(!file){problem.textContent='Choose the downloaded zip first.';return;}if(file.size>10*1024*1024){problem.textContent='Choose an export up to 10 MiB. Request only Profile and Articles.';return;}submit.disabled=true;problem.textContent='Reading the export…';try{const found=await api('upload',{operation:held.operation,files:[{linkedin:await encodeImportFile(file)}],purpose:'voice-sample',analyze:false,...(held.author.trim()?{author:held.author.trim()}:{})});held.operation=operationId();problem.textContent='';const samples=found.files.filter(row=>row.source&&row.purpose==='voice-sample').map(row=>row.source.id),background=found.files.find(row=>row.purpose==='author-background')?.source?.id||null,who=found.files.find(row=>row.author)?.author||held.author.trim();result.replaceChildren(sNode('p','',(who?'Writing by '+who+'. ':'')+found.next_step),sIntakeRows(found),samples.length?sButton(who?'Learn '+who+'’s voice from these articles':'Learn a voice from these articles',async()=>sLearnVoice(await api('voices'),null,samples,background,who),'filled'):sNode('p','quiet','No articles were in this export, so there is nothing to learn a voice from yet. Add links to posts by this author, or upload samples.'));}catch(error){problem.textContent=error.message;}finally{submit.disabled=false;}});
  sOpenSheet('Import a LinkedIn export',form,sButton('Cancel',sCloseSheet));
}
```

The merged branch also defines `sVoiceTools`; replace it wholesale with the one above.
Its `voiceLinksJourney` in `check-management.cjs` may look for the old button text
`Add published posts from a list of links` in that sheet; change it to `Add links to posts`.
Keep the branch's button in `sVoiceProfile`: there it adds posts to that one voice.

Then give the branch's `sVoiceLinks(found,profile,article)` a fourth parameter,
`purpose='voice-sample'`:

- key its held state by purpose as well (`sVoiceLinksHeld(profile,purpose)` stores under
  `(profile?.id||'new')+':'+purpose`) and keep `purpose` on it;
- send `purpose` with every `voice-links-preview` and `voice-links-import` request;
- for `style-sample`, title the sheet `Add links to examples`, label the name field
  `What kind of writing is this?` with the hint `For example, Product announcements.`,
  do not prefill it from the file name, and leave out the byline wording and the
  `Keep as sample` buttons (style samples have no byline check);
- make the final button open `sLearnStyle(await api('styles'),null,ids)` for style
  samples, and `sLearnVoice(...)` as now for voice samples.

Extend `voiceLinksJourney` with one style pass: open `sVoiceLinks(found,null,null,'style-sample')`,
submit a pasted list, and assert the preview request carries `purpose:'style-sample'` and
the result offers `Learn a style from these`.

- [ ] **Step 5: Tool job results for a learned style**

In `sToolJob`'s `paint`:

- After `if(job.kind==='voice-learn')body.append(sNode('p','quiet','Generated voice guides stay provisional ...'));` add:
  `if(job.kind==='style-learn')body.append(sNode('p','quiet','A learned style stays provisional until you confirm it. It describes a kind of writing, not a person.'));`
- In the `apply` function change `else if(job.kind==='voice-learn')await sVoiceTools();` to `else if(job.kind==='voice-learn'||job.kind==='style-learn')await sVoiceTools();`.
- After the `else if(job.kind==='voice-learn')body.append(sButton('Save provisional voice guide',...` branch add:
  `else if(job.kind==='style-learn')body.append(sButton('Save provisional style guide',apply({status:'provisional'})),sButton('Confirm this style guide',()=>sOpenSheet('Confirm this style?',sNode('p','','Confirm that you reviewed the guide and it describes the intended kind of writing. Existing blogs keep their pinned revision.'),sButton('Confirm and save',apply({status:'confirmed',confirmed:true})),sButton('Cancel',sCloseSheet))));`
- In the sheet-title map add `'style-learn':'Learn a style',`.

- [ ] **Step 6: The upload dialog**

In `skills/blog-studio/assets/management/index.html`, in the `upload-purpose` select, after `<option value="voice-sample">Authored voice sample</option>` add `<option value="style-sample">Example of a kind of writing (style sample)</option>`.

- [ ] **Step 7: Run the check**

Run: `node scripts/ci/check-management.cjs`
Expected: exits 0. Then `python3 -m unittest tests.test_management_ui -v` and expect PASS.

- [ ] **Step 8: Commit**

```bash
git add skills/blog-studio/assets/management/runner.js skills/blog-studio/assets/management/index.html scripts/ci/check-management.cjs
git commit -m "Choose a style in the wizard and manage voices and styles from one sheet

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Chat guidance, documentation, inventories and the full check

**Files:**
- Create: `skills/blog-studio/references/workspace/styles.md`
- Modify: `skills/blog-studio/references/workspace.md:14`, `skills/blog-studio/references/voice-flow.md` (end of the first section)
- Modify: `docs/runner.md` (lines 47-48 and a new section before `## Run and review`), `README.md:70-73`, `CHANGELOG.md`
- Regenerate: `docs/estimates/blog-studio-token-inventory.json`

- [ ] **Step 1: Chat guidance**

Create `skills/blog-studio/references/workspace/styles.md`:

```markdown
# Style storage

Use the [workspace](../workspace.md) command prefix. A style is the shape of a kind of
writing, apart from who writes it; a [profile](profiles.md) is one author's voice. Starter
styles for tech-industry writing are copied into a workspace, confirmed and editable, the
first time a style command runs or the page reads styles; `list styles` shows them after
that.

```text
... style create --name <kind> --guide-file <guide> --sample <source-id>
... style save --id <style-id> --guide-file <revised-guide> --status confirmed
... style show --id <style-id> --revision <number>
... style retire --id <style-id> --expected-revision <number> --confirmed
... run create ... --style <style-id>
```

Samples must be ready and classed `style-sample`; one post may be both a `voice-sample`
and a `style-sample`. Learn a style from examples of the kind by anyone: describe
structure, moves, length, headings and register, never the author. Save it provisional
until the author confirms. A run pins a style revision; later saves do not move it.
Where a style and a voice conflict on wording, the voice wins; on structure, the style
wins.
```

In `skills/blog-studio/references/workspace.md`, after `- [Profiles](workspace/profiles.md)` add `- [Styles](workspace/styles.md)`.

In `skills/blog-studio/references/voice-flow.md`, after the paragraph that ends `Normalize selected articles through source intake before adding them to a profile.` add:

```markdown
A voice belongs to one author, who may be the person you are writing for rather than
the person in the chat: a ghostwriter learns Nick's voice from Nick's posts and starts
a blog with that voice. Name every profile for its author and record the author on
each sample (`--author`); ask whose writing links are before reading them, and keep
the permission to analyze it the person's to give. A voice is not a style. When the
author wants a kind of writing learned, such as how product announcements are shaped,
learn a [style](workspace/styles.md) from examples by anyone and keep it apart from the
voice; a blog takes one of each. Links to public posts arrive through `library voice-links`
(add `--purpose style-sample` for a style) or the page's **Voices and styles** sheet; a
LinkedIn export through the `upload` route, as `author-background` and `voice-sample`
sources.
```

- [ ] **Step 2: User documentation**

In `docs/runner.md`, change

```
Choose **New blog** and work through three steps: topic and audience; mode and
voice and optional brand; sources, assistant and limits.
```

to

```
Choose **New blog** and work through three steps: topic and audience; mode, voice,
style and optional brand; sources, assistant and limits.
```

and insert this section before `## Run and review`:

```markdown
## Voices and styles

A **voice** is how one person sounds; a **style** is the shape of a kind of writing,
such as a product announcement or a how-to. A blog can take one of each: the style
decides the structure, the voice decides the wording. Open **More tools → Voices and
styles** from any blog, or from Home.

A voice belongs to one author, and that author need not be you. If you ghostwrite,
learn a voice for each person you write for, from their published posts, and start a
blog with their voice and, under **Author**, their name. Each voice sample records
whose writing it is, and the sheets ask before reading anything.

Blog Studio ships eight starter styles for writing in the tech industry: product
announcement, release notes and changelog, technical deep dive, how-to and tutorial,
point of view, customer story, comparison and evaluation guide, and postmortem and
lessons learned. They are confirmed and ready to choose, and you can edit, retire or
export each one. **Learn a style from examples** reads examples of a kind of writing
by anyone and proposes a guide, which stays provisional until you confirm it.

Voices are learned from writing the author wrote. Bring samples in three ways:

- **Upload an authored sample**, as before, naming the author.
- **Import a LinkedIn export.** On LinkedIn, open Settings & Privacy, Data privacy,
  then Get a copy of your data; choose Profile and Articles and wait for the email.
  Choose the downloaded zip in the sheet. Only `Profile.csv` and the articles are
  read: the person's name becomes the author, their headline and About text become
  author background, and each article a voice sample. An export is usually your own;
  when a colleague hands you theirs, give their name in the sheet. Nothing signs in
  to LinkedIn, and connections or messages are never read.
- **Add links to posts.** Paste links, or choose a text file with one link per line,
  such as `darin-zook-blog-links.txt`; the author is suggested from the file name and
  you can change it. Blog Studio first shows what it will do: the site, the links
  already in your library and the ones it will fetch. It then reads each new page once,
  in batches, and saves it in your reference library under "Published posts by"
  the author. A post whose byline names someone else is left out unless you keep it,
  and failed links can be tried again without fetching the rest. LinkedIn pages cannot
  be read this way; use the export.

**Add links to examples**, under Styles, does the same for a style, without the byline
check.

Every sample is a source in your reference library, so it follows the same sharing
rules as any other source. Learned voices and styles stay provisional until you
confirm them, and an existing blog keeps the revision it was started with.
```

In `README.md`, in step 2 of "Start your first blog", change `**Review a draft**, a voice and an optional brand;` to `**Review a draft**, a voice, a style and an optional brand;`.

- [ ] **Step 3: Changelog**

In `CHANGELOG.md`, under `## Unreleased` (add the heading above `## 4.3.0 — 2026-10-20` if the deletion plan has not), add:

```
- **Voices and styles.** A blog takes a voice (how you sound) and a style (the shape of a
  kind of writing). Eight starter styles for tech-industry writing ship ready to use; a
  style can also be learned from examples. Voices and styles are managed from one sheet.
- **Bring in writing, yours or an author's you write for.** Import a LinkedIn data
  export (profile and articles only) or paste links to public posts and say whose they
  are; each becomes that author's sample in your references, and the sheet offers to
  learn their voice, or a style, from them.
```

- [ ] **Step 4: Re-record the inventory and run the whole check**

```bash
python3 scripts/measure_guidance.py
bash scripts/ci/check.sh "$(command -v python3)" "$TMPDIR/blog-studio-styles-checks"
```

Expected: the check ends with the unittest summary `OK`. Lint may print `SKIPPED` without ruff installed; if ruff is available and reports formatting, run `ruff format skills/blog-studio/scripts tests` and re-run the check.

- [ ] **Step 5: Try it on the page against a disposable workspace**

Following `docs/development.md` ("To try the skill from a checkout"), open the page on a temporary workspace with `BLOG_STUDIO_DATA`, `STUDIOS_CONFIG` and `HOME` pointed at temporary folders. Confirm: **More tools → Voices and styles** lists the eight starters; **New blog** shows the Style select with "(starter)" entries; a blog started with a style shows "Style: …" in **About this blog**; **Import a LinkedIn export** and **Add links** open and refuse an empty submit with a message. Do not start a provider job. Do not import the owner's example file (`darin-zook-blog-links.txt`, 21 public posts) without the owner's go-ahead; with it, use a disposable workspace and expect 21 rows, bylines matched or flagged, and a voice learned from the samples.

- [ ] **Step 6: Commit**

```bash
git add skills/blog-studio/references docs/runner.md README.md CHANGELOG.md docs/estimates/blog-studio-token-inventory.json
git commit -m "Document voices and styles, the LinkedIn export and links to posts

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Out of scope, by the spec

- Publishing styles to a Team Hub as a new item kind (`GROUP_KIND` is not extended; the article's style pin stays out of the Hub projection).
- Applying a style to an existing blog from its editor (voices have "Use this revision for this article"; styles do not yet).
- Reading LinkedIn pages directly.
