# Piece 3, the shared desk: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Blog Studio's desk parts live in `core/studio_core/drafting/` and
`ui-kit/drafting.js`, with the desk styles in `ui-kit/style.css`, and Blog Studio uses them
with nothing a person sees changed, so pieces 5 and 6 build their desks on one copy.

**Architecture:** core never imports a studio. Each shared Python part takes a store
object the studio passes in (the item's folder, this computer's folder, the lock, atomic
writes and the studio's own `write`) and a codec (Markdown now; a slide-as-part codec in
piece 5). The job queues stay per studio; only the basis rule and the settle frame are
shared. The page kit has its own two DOM helpers and takes an adapter for the studio's
controls, requests, words and Finishing tools. Blog's modules keep every name they export,
as aliases and one-line wrappers, so callers and tests are unchanged.

**Tech Stack:** Python 3.11 standard library; plain JavaScript with no build step;
`unittest`; Node's `vm` for the page checks (Blog's `check-management.cjs` and a new core
harness).

**Spec:** `docs/superpowers/specs/2026-10-26-shared-desk-design.md`. Inventory:
`docs/superpowers/specs/2026-10-26-workflow-audit/blog-and-shared.md` Part C, and section 6
of `presentation.md` and `training.md` beside it.

**Before starting:** pieces 1 and 2 have merged. Re-read every file and line named here on
the current `main`; piece 1 changed the Proofread description and the stopped start's
exits, and piece 2 deleted dead Blog page code and CSS. Where this plan quotes a line,
find it by the function it names.

Paths: `B/` is `studios/blog/skills/blog-studio/`, `C/` is `core/studio_core/`.

## Global Constraints

- Pieces are built in order (1 to 6), each merged before the next starts. Line references are at
  main cc53056: re-read every named file on the piece's own base first. Training matrix row
  numbers named here are a guide; each new row takes the next free number on that base.
- Nothing a person sees in Blog Studio changes: the same words, elements, classes, routes
  and files on disk. Each task ends with Blog's whole suite green.
- Blog's tests are not edited. The one exception is the page check's loader line in
  Task 8, which loads `drafting.js` before `desk.js`.
- Every name `desk.py`, `desk_jobs.py`, `desk_finish.py`, `text_checks.py` and `desk.js`
  export today stays, as an alias or a wrapper. A wrapper looks the shared function up
  when called. Names a test patches (`desk._write`, `desk_jobs._apply`, `desk_jobs._guard`,
  `desk_jobs.forget_angles`, `desk_jobs.prune_angles`, `text_checks.lint`) stay real
  module attributes that the code reaches at call time.
- Core reads no settings, imports no studio module and starts no job.
- Python 3.11 or newer, standard library only; no frontend build step.
- Full product names in code, docs and commits. Person-facing sentences never say
  "artifact", "stale" or "lineage".
- Presentation Studio and Training Studio are not changed; their suites still pass.
- Tests use disposable folders, settings and Git identities, scripted results and fakes.
  No provider, Google or assistant job; no worker is started.
- Saved work reads as before: `draft.json`, `versions/*.jsonl`, `removed.json`, proposal
  sets keyed `blog`, `desk-step-times.json`, job records. The one new field is `checks` on
  a desk job.
- Commit messages are plain sentences; end each with the attribution line the session
  gives.

Run commands (from the repository root unless said). `python3` means Python 3.11 or
newer: the regular expressions in `text_checks.py` do not compile on 3.9, which some
Macs still have as `python3`.

- Core: `PYTHONPATH=.:tests python3 -m unittest <module> -v`; all core and home:
  `python3 -m unittest discover -s tests -v`.
- Blog Studio: `python3 studios/blog/scripts/ci/run_tests.py` and
  `(cd studios/blog && node scripts/ci/check-management.cjs)`.
- Blog guidance: `python3 studios/blog/scripts/measure_guidance.py --check`.
- Presentation Studio: `(cd studios/presentation/tests && python3 -m unittest discover -v)`.
  Training Studio: `(cd studios/training/tests && python3 -m unittest discover -v)`.

## Review Focus

1. A test that patches a Blog name still reaches the code: `patch('desk._write')` in
   `test_desk_finish.py` must still stop Apply with the proposals left open (Tasks 3, 6).
2. A section rewrite, revision, first pass or selection lands exactly as before even when
   its guard flags it; the flag is only kept on the job (Task 5).
3. `prompts.edit_rule('blog draft')` is byte for byte the deleted `desk-edit.md` (Task 5).
4. The kit reads no adapter member when `Drafting.kit()` is called, so `desk.js` can build
   its kit before `DESK_TOOLS` is defined, and a page check that swaps a global still
   reaches it (Tasks 8 to 11).
5. `/drafting.js` reaches a phone: it is in `marketing_studio/network.py`'s `STATIC`, in
   Blog's `STATIC`, and its link passes `packaging.shared_link` (Task 8).

---

## Task 1: Text checks in core

**Files:**
- Move: `B/scripts/text_checks.py` to `C/text_checks.py` (`git mv`)
- Create: `B/scripts/text_checks.py` (the shim)
- Test: `tests/test_text_checks.py` (new)

**Interfaces (Produces):**
- `C/text_checks.py`: every function and constant as today (`URL`, `PROTECTED`,
  `EXAMPLE_LIMIT`, `EXAMPLE_CHARS`, `SHINGLE`, `FUNCTION_WORDS`, `COMMON_WORDS`,
  `NOTE_START`, `READER_FACING_NOTE`, `mask_protected`, `lint`, `carried_over`,
  `reader_facing_notes`, `facts`, `preserve`), and `main(product, argv=None)`, whose error
  line is `f'{product} text check: {exc}'`. Its module docstring stays.
- `B/scripts/text_checks.py`: `from studio_core.text_checks import (...)` naming each of
  those, and `def main(): return _shared.main('Blog Studio')` with the
  `if __name__ == '__main__': sys.exit(main())` block.

- [ ] **Step 1: Write the failing tests** in `tests/test_text_checks.py`
  (`import marketing_studio` first, then `from studio_core import text_checks`):
  - `test_lint_finds_a_dash_outside_code_and_quotes`: `lint('A — phrase.',
    {'no_em_dashes': True})['findings']` has one finding with `rule == 'em-dash'`;
    `lint('"A — phrase."', {'no_em_dashes': True})['findings'] == []`.
  - `test_preserve_flags_a_changed_number`: `preserve('20 hours, then 20 hours.',
    '20 hours.')['needs_review']` is true; `preserve('Same.', 'Same.')['needs_review']` is
    false.
  - `test_reader_facing_notes_finds_a_placeholder`: `reader_facing_notes('Intro. [TODO add
    a quote]')` has one finding with `rule == 'reader-facing-note'`;
    `reader_facing_notes('A plain line.') == []`.
  - `test_the_command_line_names_the_product_it_runs_for`: run `main('Test Studio',
    ['lint', '--file', missing])` with stderr captured; it returns 1 and stderr starts
    `Test Studio text check: `.
  - `test_blog_s_command_line_still_runs`: `subprocess.run([sys.executable,
    'studios/blog/skills/blog-studio/scripts/text_checks.py', 'count', '--file', path])`
    on a file of `one two three` prints JSON with `words == 3`; with a missing file it exits
    1 and stderr starts `Blog Studio text check: `.
- [ ] **Step 2: Run them and see them fail**:
  `PYTHONPATH=.:tests python3 -m unittest test_text_checks -v`.
- [ ] **Step 3: Move and shim.** `git mv`, change `main()` to take `product` and `argv`
  (`p.parse_args(argv)`), write the shim. Keep the shebang on both.
- [ ] **Step 4: Run** the new tests, then Blog's suite. `test_blog_studio.py` loads the
  shim by path, `test_performance.py` patches `text_checks.lint` on it, and
  `blog_runner`, `performance`, `manuscript_editor` and `desk_finish` import from it at
  call time: all pass unchanged.
- [ ] **Step 5: Commit**: "Keep Blog Studio's text checks in the shared core, with the
  product named on the command line."

## Task 2: The store and the parts codec

**Files:**
- Create: `C/drafting/__init__.py`, `C/drafting/store.py`, `C/drafting/parts.py`
- Create: `tests/drafting_fixtures.py`
- Modify: `B/scripts/desk.py` (the codec names become imports)
- Test: `tests/test_drafting_parts.py`, `studios/blog/tests/test_desk_shared.py` (new)

**Interfaces (Produces):**
- `drafting/__init__.py`: a docstring saying what the package is (Blog Studio's desk
  parts, shared) and that core never imports a studio.
- `store.Store`: `product = ''`, `word = ''`; `held()`, `folder(ident)`, `local(ident)`,
  `write(ident, draft, parts)` raise `NotImplementedError`; `read_json(path)`,
  `write_json(path, value)` (two-space indent, `ensure_ascii=False`, trailing newline),
  `atomic(path, data)` (parent made, a hidden temp file, `os.replace`) and `now()` (UTC ISO)
  have standard-library defaults. `store.require_held(store)` raises
  `RuntimeError('Desk writes run under the studio lock.')`.
- `parts.FENCE`, `TITLE`, `HEADING`, `ANY_HEADING`, `ITEM`, `SECTIONS = 60`,
  `BRIEF = 4000`, `LIMIT = 200_000`; `new_id(taken)`, `tidy(lines)`, `split(markdown,
  title='')`, `has_heading(text)`, `outline_from(text)`, `title_line(text)`,
  `join(draft)`, moved from `desk.py:44-202` unchanged except the names.
- `parts.Codec(*, fixed=('title', 'opening'), single=('title',),
  part=re.compile(r'[a-f0-9]{8}'), split=split, join=join, breaks=has_heading,
  thing='draft', noun='section', break_message='A ## heading would start a new section.
  Use ### for a heading inside this part.', added_message='The rewrite added a ## section
  heading, so it was not applied. Run it again.')` with `known(part)`,
  `section(draft, part)` (None for a fixed part; `ValueError(f'Choose a part of this
  {thing}.')` for an unknown one), `text_of(draft, part)` and `set_text(draft, part,
  text)` (stripped). `parts.MARKDOWN = Codec()`.
- `tests/drafting_fixtures.py`: `FolderStore(Store)` with `product = 'Test Studio'`,
  `word = 'item'`, a `lock` flag that `held()` returns, `folder(ident)` =
  `root/'items'/ident/'drafting'` (an ident outside `[a-z0-9-]{1,40}` raises
  `ValueError('Choose an item on the desk.')`), `local(ident)` =
  `root/'local'/'proposals'/ident`, and `write` that runs `record.advance`, writes
  `draft.json` and appends `(ident, list(parts))` to `self.written`. `draft(**extra)`
  returns a two-section draft at revision 1. `make(store, ident, draft)` writes
  `draft.json`. (`record.advance` comes in Task 3; until then `write` is not called.)

- [ ] **Step 1: Write the failing tests** in `tests/test_drafting_parts.py`:
  - `test_a_draft_splits_into_title_opening_and_sections_and_joins_back`: `split('# T\n\nOpen.\n\n## One\n\nA.\n\n## Two\n\nB.\n')`
    gives title `T`, opening `Open.`, headings `['One', 'Two']`, texts `['A.', 'B.']`,
    8-hex ids; `join` of it is the input.
  - `test_a_heading_in_a_fence_is_text`: a `## Not a section` line inside a ```` ``` ````
    fence stays in the opening; `has_heading` of that text is false and of `'## Yes'` true.
  - `test_an_outline_needs_two_sections`: `outline_from('# T\n\n- One: do a\n- Two')`
    gives headings `['One', 'Two']` and the first brief `do a`; `outline_from('- One')`
    is None.
  - `test_a_codec_finds_a_part_and_refuses_one_it_does_not_have`:
    `MARKDOWN.text_of(draft, 'opening')`, `MARKDOWN.set_text(draft, id, '  x  ')` stores
    `'x'`; `MARKDOWN.section(draft, 'title')` is None; an unknown id raises
    `'Choose a part of this draft.'`.
  - `test_a_codec_with_no_fixed_parts_names_slides`: `Codec(fixed=(), single=(),
    part=re.compile(r's-[0-9]{1,3}'), thing='deck', noun='slide')`: `known('title')` is
    false, `known('s-4')` true, an unknown slide raises `'Choose a part of this deck.'`.
  New Blog file `studios/blog/tests/test_desk_shared.py` (it starts with `import
  isolation`, as every Blog test does; later tasks add to it):
  - `test_the_desk_uses_the_shared_codec`: `desk.split is parts.split`, `desk.join is
    parts.join` and `desk.PARTS == ('title', 'opening')`.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Write `store.py` and `parts.py`.** Move the code; keep each docstring.
- [ ] **Step 4: Switch `desk.py`'s codec names.** Import them and keep the old names as
  aliases: `FENCE`, `TITLE`, `HEADING`, `ANY_HEADING`, `ITEM`, `SECTIONS`, `BRIEF`,
  `LIMIT`, `split`, `join`, `has_heading`, `outline_from`, `_title_line =
  parts.title_line`, `_id = parts.new_id`, `_tidy = parts.tidy`. `PARTS =
  parts.MARKDOWN.fixed`, `PART = parts.MARKDOWN.part`.
- [ ] **Step 5: Run** the new tests and Blog's suite.
- [ ] **Step 6: Commit**: "Split and join a draft's parts in the shared core."

## Task 3: The record: the per-part check, save, versions and removed parts

**Files:**
- Create: `C/drafting/record.py`, `C/drafting/versions.py`
- Modify: `B/scripts/desk.py` (`BlogStore`, `_drafting`, wrappers; `_write` calls
  `record.advance`)
- Test: `tests/test_drafting_record.py`, `tests/test_drafting_versions.py` (new)

**Interfaces (Produces):**
- `record.advance(draft, parts, now) -> dict`: `revision += 1`, `updated_at = now`, and
  `changed[part] = revision` for each part.
- `record.checked(draft, seen, parts=None, thing='draft')`: `desk.py:666-681`; refuses with
  `f'This {thing} changed since you opened it. Reload to see the latest.'`.
- `record.checked_text(part, text, codec=MARKDOWN) -> str`: "Keep one part under 200,000
  characters." for a non-string or over `LIMIT`; "Keep the title to one line, up to 500
  characters." for a `single` part that is empty, multi-line or over 500; then
  `codec.break_message` when `codec.breaks(text)` on a part not in `single`.
- `record.Desk(store, codec=MARKDOWN, sources=versions.SOURCES)` with `REMOVED = 20` and
  `self.versions = versions.Versions(store, codec, sources)`:
  `read(ident)` (`folder/'draft.json'`, a link or a missing file raises
  `f'This {store.word} is not on the desk.'`), `checked(draft, seen, parts=None)`,
  `checked_text(part, text)`, `save(ident, seen, part, text, source='save',
  session=None)` (`desk.py:695-705`, writing through `store.write`), `restore(ident, seen,
  part, index)` ("Choose a saved version."), `removed(ident)`, `keep_removed(ident,
  sections)`, `unremove(ident, seen, index)` (`desk.py:880-927`; "Choose a removed
  section."; `f'Keep the outline to {SECTIONS} {codec.noun}s.'`).
- `versions.KEEP = 20`; `versions.SOURCES = ('save', 'rewrite', 'revise-all',
  'selection', 'first-pass', 'finishing', 'restore', 'draft')`; `versions.entries(path)`;
  `versions.Versions(store, codec=MARKDOWN, sources=SOURCES, keep=KEEP)` with
  `path(ident, part)`, `keep(ident, part, text, source, session=None)`,
  `versions(ident, part)` (newest first) and `counts(ident)` (`desk.py:1005-1071`; the same
  refusals: "Choose a part of this draft.", "Choose a listed kind of change.", "A desk
  versions file is not a plain file. Nothing was changed.").
- `desk.BlogStore(root)`: `product = 'Blog Studio'`, `word = 'blog'`; `held` is
  `studio.lock_held`; `folder(ident)` is `_paths(root, ident)[1].parent`; `local(ident)`
  is `studio.inside(root, '.blog-runs', 'desk-proposals', studio.identifier(ident))`;
  `write` returns `_write(self.root, ident, draft, parts)` (the module global, looked up
  when called); `read_json`, `write_json`, `atomic`, `now` are `studio`'s.
- `desk.SOURCES = versions.SOURCES + ('chat', 'google')`; `desk.KEEP`, `desk.REMOVED`;
  `desk._drafting(root) -> record.Desk` built with `BlogStore(root)` and `SOURCES`.
- `desk.read`, `checked`, `checked_text`, `save`, `keep`, `versions`, `counts`,
  `restore`, `removed`, `_keep_removed`, `unremove`, `_part`, `text_of`, `_set` keep their
  signatures and call the shared parts. `desk._write` keeps its body except the first
  lines, which become `record.advance(draft, parts, studio.now())`.

- [ ] **Step 1: Write the failing tests.** `tests/test_drafting_record.py`, with
  `FolderStore` and `lock = True` unless a test says not:
  - `test_a_form_older_than_one_part_may_still_change_another`: save part A at seen 1
    (revision 2); a save of part B at seen 1 lands; a save of part A at seen 1 raises
    `'This draft changed since you opened it. Reload to see the latest.'`.
  - `test_with_no_parts_named_the_whole_item_must_be_as_seen`: `checked(draft, 1)` at
    revision 2 raises; `checked(draft, 2)` does not; `checked(draft, True)` and
    `checked(draft, 3)` raise.
  - `test_the_same_text_again_is_not_refused`: a save of the current text at an old seen
    returns the draft and writes nothing (`store.written == []`).
  - `test_a_part_keeps_its_text_as_a_version_before_it_changes`: after a save,
    `versions(ident, part)[0]['text']` is the old text with `source == 'save'` and
    `words` its word count.
  - `test_a_one_line_part_and_a_new_heading_are_refused`: `checked_text('title', 'a\nb')`
    raises `'Keep the title to one line, up to 500 characters.'`; `checked_text(id,
    '## New')` raises the codec's `break_message`.
  - `test_a_removed_section_comes_back_where_it_was_with_its_id`: `keep_removed` of the
    second section with `index: 1`, then `unremove(ident, revision, 0)` puts it back at
    index 1 with the same id and empties `removed`.
  - `test_writes_need_the_lock`: with `lock = False`, `save` raises `RuntimeError('Desk
    writes run under the studio lock.')`.
  - `test_a_deck_worded_desk_says_deck`: a `Desk` with `Codec(thing='deck')` refuses an old
    form with `'This deck changed since you opened it. Reload to see the latest.'`.
  `tests/test_drafting_versions.py`:
  - `test_twenty_versions_are_kept_per_part_newest_first`: 25 keeps leave 20; the newest
    is first.
  - `test_saves_from_one_editing_session_keep_only_the_first_text`: two `save` keeps with
    session `'a' * 16` keep one; a `rewrite` keep after them adds one.
  - `test_a_torn_line_hides_no_other_version`: append `'{not json\n'` to the part's file;
    `versions` still lists the others.
  - `test_a_linked_versions_folder_is_refused`: replace `versions/` with a link; `keep`
    raises `'A desk versions file is not a plain file. Nothing was changed.'`.
  - `test_only_listed_sources_and_known_parts`: `keep(..., 'chat')` raises `'Choose a listed
    kind of change.'` with the default sources and lands with `SOURCES + ('chat',)`;
    `path(ident, '../x')` raises `'Choose a part of this draft.'`.
  - `test_counts_name_only_parts_with_versions`.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Write `record.py` and `versions.py`** from `desk.py`'s code.
- [ ] **Step 4: Switch `desk.py`.** Add `BlogStore` and `_drafting`; turn the functions
  above into one-line wrappers; replace the first lines of `_write` with `record.advance`.
  `outline_save`, `reimport`, `create` and the rest keep calling `checked`, `keep`,
  `_keep_removed` and `_write` by their Blog names.
- [ ] **Step 5: Run** the new tests and Blog's suite. `test_desk.py`,
  `test_desk_reimport.py` and `test_desk_finish.py`'s `patch('desk._write')` case pass
  unchanged.
- [ ] **Step 6: Commit**: "Keep the desk's per-part check, versions and removed sections in
  the shared core, with Blog Studio's store passed in."

## Task 4: The guards and Proofread

**Files:**
- Create: `C/drafting/guards.py`, `C/drafting/proofread.py`
- Modify: `B/scripts/desk_finish.py`
- Test: `tests/test_drafting_guards.py`, `tests/test_drafting_proofread.py` (new)

**Interfaces (Produces):**
- `proofread.COMMON_STARTS`, `PROOF_LIMIT = 300`, `BOUNDARY`, `WORD`, `SENTENCE_MAX =
  2000`, `LIST_LINE`, `LIMITATIONS = 'Mechanical matches and repetition hints only; read
  for meaning. Code, links and quotations are left out.'`; `sentences(text)`,
  `sentence(text, start, spans=None)`, `offsets(draft)`, `label(rule, target)`,
  `finding(part, text, rule, start, target, spans=None)`, `mask_indented(text)`,
  `clean(text)`, `units(paragraph)`, `repetition(part, text, starters)`,
  `openers(draft)`, and `check(draft, rules, starters, ident, join=parts.join) ->
  {'id', 'revision', 'findings', 'more', 'limitations'}` (`desk_finish.py:300-538`; the
  rule lists are arguments).
- `guards.STRUCTURE = 'Check the structure: this changes code or the part’s shape.'`,
  `FENCE`, `INLINE_CODE`, `TABLE_LINE`, `QUOTE_LINE`, `NAME`; `names(text)`,
  `named(name, text)`, `changes_facts(before, after, anywhere=False)`, `shape(text,
  paragraphs=True)`, `changes_structure(before, after, paragraphs=True)`, `flags(before,
  after, anywhere=False, paragraphs=True)` (`desk_finish.py:724-836`), using
  `text_checks.preserve` and `proofread.mask_indented`.
- `desk_finish.py` keeps `AI_TELLS`, `_listed`, `proof_rules` and these aliases:
  `COMMON_STARTS`, `PROOF_LIMIT`, `BOUNDARY`, `WORD`, `SENTENCE_MAX`, `LIST_LINE`,
  `_sentences`, `_sentence`, `_offsets`, `_label`, `_finding`, `_mask_indented`, `_clean`,
  `_units`, `_openers`, `STRUCTURE`, `FENCE`, `INLINE_CODE`, `TABLE_LINE`, `QUOTE_LINE`,
  `NAME`, `_names`, `_named`, `changes_facts`, `_shape`, `changes_structure`, `_flags`.
  `_repetition(part, text)` calls `proofread.repetition(part, text,
  _listed('sentence-starters.txt'))`. `proofread(root, ident)` returns
  `proofread.check(desk.read(root, ident), proof_rules(), _listed('sentence-starters.txt'),
  ident)`.

- [ ] **Step 1: Write the failing tests.** `tests/test_drafting_guards.py`:
  - `test_a_changed_number_link_quote_or_dropped_name_is_named`: `changes_facts('In 2024
    Ada wrote.', 'In 2025 Ada wrote.') == 'Check the facts: this changes a number.'`;
    dropping `Ada` mid-sentence gives `'Check the facts: this changes a name.'`; an
    unchanged text gives `''`.
  - `test_anywhere_lets_a_name_move_but_not_go`: `changes_facts('We met Ada today.',
    'Ada met us today.', anywhere=True) == ''`; dropping her gives the name line.
  - `test_code_and_shape_are_kept`: changing a fenced block, an inline code span or the
    paragraph count gives `STRUCTURE`; `changes_structure(a, b, paragraphs=False)` ignores a
    paragraph split.
  - `test_flags_join_both_lines`: a change to a number and to a code span gives both
    sentences joined by one space.
  `tests/test_drafting_proofread.py`:
  - `test_a_dash_is_found_in_its_part_with_its_sentence`: `check` of a draft whose second
    section says `One — two. Three.` with `{'no_em_dashes': True}` gives one finding with
    that section's id, `rule == 'em-dash'` and `sentence == 'One — two.'`.
  - `test_indented_code_is_never_read_as_prose`: `mask_indented('Text.\n\n    x — y\n')`
    keeps the length and blanks the code line.
  - `test_a_listed_opener_and_a_repeated_start_are_found`: starters `['Moreover']`; a part
    `'Moreover, it works. It runs. It stops.'` gives `ai-starter` and `repeated-start`.
  - `test_two_sections_opening_alike_are_named`: two sections opening with the same eight
    words give one `echoed-opener` finding on the second.
  - `test_findings_are_capped_and_counted`: 301 dashes give `len(findings) == 300` and
    `more == 1`; `limitations == proofread.LIMITATIONS`.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Write `guards.py` and `proofread.py`** from `desk_finish.py`'s code.
- [ ] **Step 4: Switch `desk_finish.py`** to the aliases and wrappers above.
- [ ] **Step 5: Run** the new tests and Blog's suite (`test_desk_finish.py` proofread,
  `changes_facts`, `STRUCTURE` and `_mask_indented` cases pass unchanged).
- [ ] **Step 6: Commit**: "Check facts, structure and the proofread rules in the shared
  core."

## Task 5: The basis rule and the prompts, with the guards on every rewrite

**Files:**
- Create: `C/drafting/basis.py`, `C/drafting/prompts.py`
- Modify: `B/scripts/desk_jobs.py`
- Delete: `B/references/modules/desk-edit.md`
- Test: `tests/test_drafting_basis.py`, `tests/test_drafting_prompts.py` (new);
  `studios/blog/tests/test_desk_shared.py`

**Interfaces (Produces):**
- `basis.ACTIVE = ('queued', 'working')`, `GAPS = 50`, `EMPTY_RESULT = 'The result was
  empty. Run it again.'`, `MOVED = 'The selected passage changed while this was being
  written. Select it again.'`, `NOT_LISTED = 'The result was not the list of sections asked
  for. Run it again.'`, `UNKNOWN = 'The result named sections this draft does not have. Run
  it again.'`.
- `basis.unsettled(job)`, `busy(job)`, `fingerprint(value)` (SHA-256 hex of
  `json.dumps(value, sort_keys=True, ensure_ascii=False)`), `sections_basis(draft)`,
  `stale(codec=MARKDOWN)` (`f'The {codec.thing} changed while this was being written. Run
  it again.'`), `clean(text, heading=None)`, `no_heading(text, codec=MARKDOWN)`,
  `section_texts(content)`, `merge_gaps(draft, result, most=GAPS)`.
- `basis.land_part(draft, meta, content, codec=MARKDOWN) -> (part, before, text, flag)`:
  an unknown part or `fingerprint(before) != meta['basis']` raises `stale(codec)`; then
  `clean(content, heading)`, `no_heading`, `record.checked_text`; `flag =
  guards.flags(before, text)`.
- `basis.land_selection(draft, meta, content, codec=MARKDOWN) -> (part, whole, updated,
  flag)`: `desk_jobs.py:1469-1494` exactly (start offset while the part is unchanged, else
  a single occurrence, else `MOVED`; the passage's own spaces kept; a `single` part's
  replacement on one line); `flag = guards.flags(whole, updated)`.
- `basis.land_sections(draft, meta, content, codec=MARKDOWN) -> {part: (before, text,
  flag)}`: `desk_jobs.py:1500-1515`; unchanged or empty texts left out.
- `basis.settle(job, apply, now) -> job`: calls `apply()`; sets `applied=True, error=''`;
  a `ValueError` sets `applied=False` and its message (1,000 characters); any other error
  sets `('This result could not be saved: ' + str(error))[:1000] + ' Nothing was changed;
  run it again.'`; then `settled_at = now()`.
- `prompts.ACTIONS`, `ASK = 'Do what the author asks below with the passage.'`,
  `REVISE_ONE`, `WHOLE` (from `desk_jobs.py:40-61`, word for word); `SURGICAL`,
  `SURGICAL_PART`, `FOLLOW`, `ONLY_PASSAGE`, `ALSO_FIX` (the five scope sentences at
  `desk_jobs.py:330-332, 384, 390, 432`); `edit_rule(thing) -> str`;
  `passage_task(line) -> str` (`'\n\nAct on the passage only: ' + line + ' Return only the
  replacement for passage in content; around is its context and is not returned.\n\n'`);
  `request(label, text, scope, product) -> str` (`desk_jobs.py:252-262` with `product`).
- `desk_jobs.py` keeps `ACTIVE`, `ACTIONS`, `WHOLE`, `REVISE_ONE`, `STALE`, `GAPS`,
  `unsettled`, `busy`, `fingerprint`, `_sections_basis`, `_merge_gaps`, `_clean`,
  `_no_heading`, `_section_texts` as aliases; `_request(label, text, scope)` calls
  `prompts.request(..., 'Blog Studio')`; `section`, `selection`, `revise_all` and
  `first_pass` use `prompts.edit_rule('blog draft')` where they read `desk-edit.md`.
  `_apply` calls the three `land_*` functions, then keeps the version, sets the text,
  merges the gaps and writes as now, and sets `job['checks'] = {part: flag}` for the parts
  with a flag (left out when none). `_settle` calls `basis.settle(job, lambda:
  _apply(root, ident, draft, job), studio.now)`. `_row` adds `'checks': job.get('checks')
  or {}`.

- [ ] **Step 1: Keep the rule text exactly.** Copy `B/references/modules/desk-edit.md`
  (14 lines) into `tests/test_drafting_prompts.py` as the literal `DESK_EDIT`, taken with
  `git show HEAD:studios/blog/skills/blog-studio/references/modules/desk-edit.md`, and
  write `test_the_edit_rule_for_a_blog_draft_is_the_desk_edit_guide`:
  `edit_rule('blog draft') == DESK_EDIT.rstrip()`. In `prompts.py`, `EDIT_RULE` is the same
  text with `blog draft` replaced by `{thing}`, and `edit_rule(thing)` fills it in.
- [ ] **Step 2: Write the failing tests.** `tests/test_drafting_prompts.py` also:
  - `test_the_author_s_words_are_fenced_and_name_the_product`: `request('NOTE FOR THIS
    SECTION', 'Add one.', SURGICAL, 'Presentation Studio')` contains
    `'AUTHOR’S NOTE FOR THIS SECTION, from the author through Presentation Studio. '` and
    `'\n"""\nAdd one.\n"""'`.
  - `test_the_actions_are_rephrase_shorten_expand_and_fix`: `sorted(ACTIONS) ==
    ['expand', 'fix', 'rephrase', 'shorten']`; `edit_rule('training guide')` says
    `one part of a training guide for its author`.
  `tests/test_drafting_basis.py`, on synthetic drafts (no store):
  - `test_a_result_lands_only_while_its_part_is_unchanged`: `land_part` with the right
    basis returns the cleaned text without a repeated `## First` heading; with a changed
    part it raises `'The draft changed while this was being written. Run it again.'`; with
    a removed part the same.
  - `test_a_result_that_adds_a_section_is_refused`: content with a `## New` line raises
    `codec.added_message`.
  - `test_a_selection_lands_on_the_word_chosen`: part `'one two one'`, selection `'one'`
    at start 8 with an unchanged basis gives `'one two ONE'`; after the part changed to
    `'zero one two'` it falls back to the single occurrence; with two occurrences it
    raises `MOVED`.
  - `test_a_selection_keeps_its_own_spaces`: passage `' two '` replaced by `'2'` gives
    `'one 2 three'` from `'one two three'`.
  - `test_a_rewrite_that_changes_a_number_is_flagged_and_still_returned`: `land_part`
    from `'In 2024.'` to `'In 2025.'` returns the text and `flag == 'Check the facts: this
    changes a number.'`; `land_selection` the same.
  - `test_a_whole_draft_result_names_only_known_sections`: `land_sections` with an
    unknown id raises `UNKNOWN`; a non-list raises `NOT_LISTED`; fenced JSON is read.
  - `test_a_ready_result_not_yet_landed_is_still_under_way`: `busy({'status': 'ready'})`
    is true, `busy({'status': 'ready', 'settled_at': 'x'})` false.
  - `test_settling_says_what_went_wrong_once`: an `apply` raising `OSError('full')` leaves
    `applied` false, the error starting `'This result could not be saved: full'` and ending
    `' Nothing was changed; run it again.'`, and `settled_at` set.
  `studios/blog/tests/test_desk_shared.py` (a `SettleTests`-style case on
  `test_desk_jobs.DeskJobCase`, with its own `ready` helper as `SettleTests.ready` does):
  - `test_a_flagged_rewrite_still_lands_and_its_job_keeps_the_check`: a section whose text
    is `First text from 2024.`, a note result `First text from 2025.`, then `settle`: the
    text landed, `tool_jobs.read(...)['checks'] == {part: 'Check the facts: this changes a
    number.'}` and `desk_jobs.view(...)['jobs'][-1]['checks']` is the same.
  - `test_the_section_job_reads_the_shared_edit_rule`: a section note's saved guidance
    starts with `prompts.edit_rule('blog draft')`.
  - `test_a_clean_rewrite_keeps_no_checks`: a result changing only wording leaves no
    `checks` on the job.
- [ ] **Step 3: Run them and see them fail.**
- [ ] **Step 4: Write `basis.py` and `prompts.py`.**
- [ ] **Step 5: Switch `desk_jobs.py`** as above and delete `desk-edit.md`. Keep `_guide`
  for `desk-write.md`, `blog-write.md` and the outline guides.
- [ ] **Step 6: Run** the new tests, Blog's suite and
  `python3 studios/blog/scripts/measure_guidance.py --check`.
- [ ] **Step 7: Commit**: "Land a desk result only while its part is unchanged, in the
  shared core, and keep each rewrite's fact and structure check on its job."

## Task 6: The Finishing proposals

**Files:**
- Create: `C/drafting/proposals.py`
- Modify: `B/scripts/desk_finish.py`
- Test: `tests/test_drafting_proposals.py` (new)

**Interfaces (Produces):**
- `proposals.JOB = re.compile(r'[a-f0-9]{32}')`, `ITEMS = 200`, `DAY = 86_400`,
  `LATEST = 'latest.json'`, `GONE`, `NONE_LEFT`, `EMPTY` (from `desk_finish.py:26-34`).
- `proposals.text_present(codec)` and `proposals.text_fit(codec)`: the default hooks,
  `desk_finish.py:147-161` and `:236-251` (an alternative to the whole part needs the part
  as it was; otherwise `before` once in the part, replaced by `after`; `GONE` when it no
  longer fits; `EMPTY` for empty words).
- `proposals.Proposals(store, desk, tools, owner='item', present=None, fit=None)`, where
  `desk` is a `record.Desk`, `tools` maps a job kind to its panel name, and `present` and
  `fit` default to the text hooks:
  `keep(ident, job, kind, items, **extra)`, `latest(ident)`, `prune(ident, shown)`,
  `read(ident, job)`, `sets(ident)`, `forget(ident)`, `present(draft, item)`,
  `summary(ident, draft)`, `apply(ident, seen, job, chosen, working=frozenset())`,
  `skip(ident, job, ids)` (`desk_finish.py:42-296`). A set is
  `{'schema': 1, 'job', 'kind', owner: ident, 'made_at', ..., 'items'}` in
  `store.local(ident)/<job>.json`. "Choose a set of suggestions on this {store.word}."
  `apply` refuses a part in `working`, or any section part while `'sections'` is in
  `working`, with "A desk job is working on this part. Wait for it, or stop it, then
  apply."
- `proposals.read_result(content, unreadable)`, `rows(found, key, fields, unreadable)`,
  `located(draft, part, before, codec=MARKDOWN)`.
- `desk_finish.py` keeps `TOOLS`, `KINDS`, `JOB`, `ITEMS`, `DAY`, `LATEST`, `GONE`,
  `NONE_LEFT`, `EMPTY` as aliases, and `_folder`, `_path`, `keep`, `_latest`, `_prune`,
  `read`, `sets`, `forget`, `present`, `summary`, `apply`, `skip`, `_rows`, `_located` as
  wrappers over `_proposals(root) = Proposals(desk.BlogStore(root), desk._drafting(root),
  TOOLS, owner='blog')`. `apply` passes `_busy_parts(root, ident)`. `settle` uses
  `read_result(content, UNREADABLE)`. The tool prompts, readers, `request`, voice guides,
  Google and Repurpose code stay.

- [ ] **Step 1: Write the failing tests** in `tests/test_drafting_proposals.py`, with
  `FolderStore`, a `Desk` over it, and `tools = {'finish-humanize': 'humanize',
  'finish-headline': 'headline'}`:
  - `test_a_set_waits_on_this_computer_not_in_the_item`: after `keep`, the set is under
    `store.local(ident)` and nothing new is under `store.folder(ident)`; items are numbered
    `p1`, `p2` and `open`.
  - `test_one_proposal_that_no_longer_fits_changes_nothing`: the part changed since; a
    single `apply` raises `GONE` and `store.written == []`.
  - `test_apply_all_applies_what_fits_and_counts_the_rest`: two items, one gone; `apply`
    returns `{'applied': 1, 'left': ['p2']}` and keeps one `finishing` version.
  - `test_a_part_a_job_is_working_on_is_refused`: `working={'sections'}` refuses a
    section part; `working={'title'}` does not refuse a section.
  - `test_choosing_one_alternative_skips_the_others_in_its_group`: two headline items with
    `group: 'title'`; applying `p1` leaves `p2` `skipped`.
  - `test_proposals_are_marked_applied_only_once_the_item_is_written`: a store whose
    `write` raises `OSError` leaves every item `open`.
  - `test_the_newest_set_per_tool_is_read_without_reading_every_set`: with `latest.json`
    present, patch `Proposals.sets` to raise; `summary` still returns the newest set.
  - `test_an_older_set_is_let_go_once_nothing_in_it_is_open`: after `skip` of its only
    item and a newer `keep`, its file is gone.
  - `test_sets_keyed_by_the_owner_word_are_read`: a set written with `owner='blog'` reads
    back with `Proposals(..., owner='blog')` and is refused by `owner='deck'`.
  - `test_a_studio_s_own_fit_decides_what_a_proposal_writes`: `Proposals(..., fit=lambda
    draft, item, after, text: text + ' ' + after)` appends instead of replacing, and a
    `present` that returns false marks every item `present: False` in `summary`.
  - `test_a_result_in_fences_is_read_and_another_shape_is_refused`:
    `read_result('```json\n{"a": 1}\n```', 'X')` is `{'a': 1}`; `read_result('nope', 'X')`
    raises `'X'`.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Write `proposals.py`** from `desk_finish.py`'s code.
- [ ] **Step 4: Switch `desk_finish.py`** to the wrappers above.
- [ ] **Step 5: Run** the new tests and Blog's suite; `test_desk_finish.py` and
  `test_desk_team.py` pass unchanged, including `patch('desk._write')` and
  `patch('desk_finish.sets')`.
- [ ] **Step 6: Commit**: "Keep Finishing's proposals, Apply and Skip in the shared core."

## Task 7: Step-time estimates

**Files:**
- Create: `C/step_times.py`
- Modify: `B/scripts/desk_jobs.py`
- Test: `tests/test_step_times.py` (new)

**Interfaces (Produces):**
- `step_times.TIMES = 20`; `seconds(job) -> float | None` (`finished_at - started_at`);
  `note(store, path, key, seconds)` (best effort; 20 kept per key, newest last, rounded to
  0.1); `expected(store, path, key, guess) -> float` (median of recent runs in minutes, at
  least 1, else `guess`); `left(expected, job, now=None) -> {'minutes_left': int, 'over':
  bool}`, where `expected` is a list of minutes, the step under way first
  (`desk_jobs.py:1270-1288`).
- `desk_jobs.TIMES`, `_seconds`, `_note_time`, `expected_minutes`, `_timing` keep their
  signatures and call `step_times` with `desk.BlogStore(root)` and `_times_path(root)`.

- [ ] **Step 1: Write the failing tests** in `tests/test_step_times.py`, with
  `FolderStore`:
  - `test_the_median_of_recent_runs_is_the_estimate`: notes of 60, 180, 600 seconds give
    `expected(...) == 3`; a key with none gives the guess.
  - `test_twenty_times_are_kept_per_step`: 25 notes keep 20.
  - `test_a_torn_times_file_falls_back_to_the_guess`: a file holding `not json` gives the
    guess and `note` does not raise.
  - `test_time_left_counts_what_is_spent_and_says_when_a_step_overruns`: `left([3, 2],
    {'started_at': now - 1 minute, 'busy': True}, now)` gives `{'minutes_left': 4, 'over':
    False}`; 5 minutes spent gives `over: True` and `minutes_left: 2`.
  - `test_seconds_needs_both_times`: a job with no `finished_at` gives None.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Write `step_times.py`** and switch `desk_jobs.py`.
- [ ] **Step 4: Run** the new tests and Blog's suite (`test_desk_start.py` timing cases
  pass unchanged).
- [ ] **Step 5: Commit**: "Estimate a step's time from its recent runs in the shared core,
  beside the stop wording."

## Task 8: The page kit reaches Blog's page

**Files:**
- Create: `ui-kit/drafting.js`
- Create: link `B/assets/management/drafting.js -> ../../../../../../ui-kit/drafting.js`
- Modify: `B/assets/management/index.html` (`<script src="/drafting.js" defer></script>`
  before `/desk.js`), `B/scripts/management.py` (`STATIC['/drafting.js']`),
  `marketing_studio/network.py` (`STATIC`), `C/packaging.py` (`shared_link` accepts
  `drafting.js`), `B/assets/management/desk.js`, `studios/blog/scripts/ci/check-management.cjs`
  (the loader line only)
- Create: `tests/drafting_page_check.js`, `tests/test_drafting_page.py`,
  `tests/test_packaging_links.py`

**Interfaces (Produces):**
- `ui-kit/drafting.js` defines `const Drafting = (() => { 'use strict'; ... })();` with
  `DIFF_LIMIT = 4000`, `SAVE_WAIT = 1000`, `POLL = 3000`; `make(tag, cls, text)` (as
  `sNode`: text set when not `undefined`, class when given); `add(parent, ...children)`
  (as `sAdd`: null and undefined left out); `words(text)`; `diffWords(before, after)`
  (`desk.js:16-32`); `age(at)`; and `kit(a)`, which returns an object of the desk's parts
  bound to the adapter `a`. `kit` reads no member of `a` when called; each part reads
  what it needs when it runs.
- The adapter `a` (all members, used from Task 9 on): `ui` (`button(label, action, kind)`,
  `card(title, ...nodes)`, `pickCard(title, says, action)`, `choice(label, options, held,
  key, changed)`, `disclosure(label, ...nodes)`, `bead(state)`, `openSheet(title,
  ...nodes)`, `closeSheet()`, `toast(text)`, `notice(text, isError)`, `busy(control, label,
  action)`, `narrow()`); `api(route, data)`; `routes` (`view`, `save`, `versions`,
  `restore`, `note`, `revise`, `selection`, `stop`, `retry`, `finish`, `apply`, `skip`,
  `proofread`); `share(id)`; `canEdit()`; `current(held)`; `page()`; `hooks` (`render`,
  `refresh`, `reload`, `beforeJob`); `parts` (`title(view, part)`, `textOf(view, part)`,
  `nameOf(view, part)`, `single(part)`, `noted(view, part)`); `words()` (returns
  `{thing, sources, doing, steps, named, ready(tab)}`); `tools()`; `progress`
  (`actions(held, start)`).
- In this task the kit's parts are `compare(before, after)` (`desk.js:33-39`) and
  `sides(before, after)` (`desk.js:710-722`).
- `desk.js`: `deskWords`, `diffWords`, `deskAge` call `Drafting.words`,
  `Drafting.diffWords`, `Drafting.age`; `deskCompare` and `deskSides` call `DESK_KIT`'s;
  `DESK_DIFF_LIMIT = Drafting.DIFF_LIMIT`, `DESK_SAVE_WAIT = Drafting.SAVE_WAIT`,
  `DESK_POLL = Drafting.POLL`. `const DESK_KIT = Drafting.kit({...})` is the last
  statement of `desk.js`. Each adapter member is an arrow that names Blog's function when
  called: `ui: {button: (...x) => sButton(...x), ...}`, `api: (route, data) => api(route,
  data)`, `canEdit: () => access.actions.edit`, `page: () => $('studio-page')`,
  `share: id => fetch('/api/desk-share', {method: 'POST', keepalive: true, headers:
  {'X-Blog-Studio-Token': token, 'Content-Type': 'application/json'}, body:
  JSON.stringify({id})})`, `words: () => ({thing: 'draft', sources: DESK_SOURCES, doing:
  DESK_DOING, steps: DESK_STEPS, named: ['desk-section', 'desk-selection'], ready:
  tab => tab === 'outline' ? 'The outline is ready. Shape it here, then write the draft.'
  : 'The draft is ready. Edit it here.'})`, `tools: () => DESK_TOOLS`, `routes` with
  Blog's route names (`'desk'`, `'desk-save'`, `'desk-versions'`, `'desk-restore'`,
  `'desk-note'`, `'desk-revise'`, `'desk-selection'`, `'desk-stop'`, `'desk-retry'`,
  `'desk-finish'`, `'desk-apply'`, `'desk-skip'`, `'desk-proofread'`).
- `packaging.shared_link`: `drafting.js` joins `style.css` and `markdown.js` as a name that
  may link to the same name in `ui-kit/`.

- [ ] **Step 1: Write the failing tests.**
  - `tests/test_packaging_links.py`: in a disposable tree (its root taken with
    `.resolve()`, since macOS's temporary folder is itself a link) with
    `core/studio_core/__init__.py`,
    `ui-kit/drafting.js` and a studio folder, a link `assets/drafting.js ->
    ui-kit/drafting.js` passes `shared_link`; `assets/drafting.js -> ui-kit/style.css` and
    `assets/other.js -> ui-kit/drafting.js` do not.
  - `tests/drafting_page_check.js GROUP`: loads `ui-kit/drafting.js` with `vm` into a
    stand-in DOM (elements with `children`, `className`, `textContent`, `attributes`,
    listeners and `append`, as in `check-management.cjs`), and a fake adapter whose `ui`
    builds plain elements and whose `api` records calls and answers from a script. It
    asserts with `node:assert/strict` and exits 1 on failure. Group `diff`:
    `diffWords('one two three', 'one 2 three')` ops are `['same', 'removed', 'added',
    'same']`; `diffWords('a '.repeat(5000), 'b') === null`; `compare` of two texts holds one
    `del.diff-remove` with `two` and one `ins.diff-add` with `2` in a `p.desk-plain` labelled
    `Changes from this version to the current text`; `sides` holds two `.desk-side` with
    `Before` and `After`; `age` of one hour ago is `'1 hour ago'`. Group `lazy`:
    `Drafting.kit(new Proxy({}, {get() { throw new Error('read') }}))` does not throw.
  - `tests/test_drafting_page.py`: one test per group,
    `test_<group>_on_the_page_kit`, each running `node tests/drafting_page_check.js
    <group>` and asserting exit 0 with stderr shown.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Write `drafting.js`'s first part**, the link, the static entries, the
  gateway entry and the packaging case. In `check-management.cjs`, `loadRunner` runs
  `drafting.js` before `desk.js`:
  `vm.runInContext(fs.readFileSync('skills/blog-studio/assets/management/drafting.js','utf8'),context);`.
  Change nothing else in that file.
- [ ] **Step 4: Switch `desk.js`'s** pure functions and build `DESK_KIT`.
- [ ] **Step 5: Run** `node --check ui-kit/drafting.js`, the new tests,
  `PYTHONPATH=.:tests python3 -m unittest test_network_static test_ui_consistency -v`,
  Blog's suite and Blog's page check.
- [ ] **Step 6: Commit**: "Serve the shared desk kit to Blog Studio's page and to a phone,
  starting with the word comparison."

## Task 9: Autosave, the changed-elsewhere banner, History and the selection bar

**Files:**
- Modify: `ui-kit/drafting.js`, `B/assets/management/desk.js`,
  `tests/drafting_page_check.js`, `tests/test_drafting_page.py`

**Interfaces (Produces):** kit parts, each `desk.js:<lines>` moved with Blog's helpers
replaced by `a.ui`, `a.api`, `a.routes`, `a.canEdit`, `a.parts` and `a.words()`:
- `typed(held, part, text)`, `save(held, part)`, `flush(held)`, `counts(held)`,
  `stale(held)`, `share(held)` (`desk.js:422-455`). `save` sends `a.routes.save` with
  `{id, seen: held.view.revision, part, text, session: held.session}`. `stale` writes
  `'This ' + thing + ' changed in another window or job. Reload to see the latest; your
  unsaved text is shown until you do. '` and a filled `Reload` that calls
  `a.hooks.reload(held)`. `share` flushes, then awaits `a.share(held.id)`, and swallows an
  error.
- `history(held, part)` (`desk.js:502-515`): `a.routes.versions` with `{id, part}` as a
  query, labels from `a.words().sources` ("Earlier text" when unknown), Compare and
  Restore, `a.ui.openSheet('History of ' + a.parts.nameOf(view, part), ...)`.
- `selected(held, part, input)`, `selectionBar(held)`, `barContent(held)`
  (`desk.js:479-500`), sending `a.routes.selection` through `job` (Task 10). Until Task 10,
  `barContent` calls `a.hooks.job(held, button, route, data, done)`, which Blog maps to
  `sDeskJob`; Task 10 replaces that with the kit's own `job`.
- `desk.js`: `sDeskTyped`, `sDeskSave`, `sDeskFlush`, `sDeskCounts`, `sDeskStale`,
  `sDeskShare`, `sDeskHistory`, `sDeskSelected`, `sDeskSelectionBar`, `sDeskBarContent`
  become one-line calls into `DESK_KIT`. `hooks.reload` is `held => { held.pending = {};
  held.stale = false; held.saved = ''; return sDesk(held.id); }`.

- [ ] **Step 1: Write the failing groups** in `drafting_page_check.js` and their tests:
  - `autosave`: `typed` sets status `Saving…` and queues one timer of 1000 ms; running it
    sends one save with the revision seen and the session; status becomes `Saved.`; a
    second `typed` during a save sends a second save after the first; an answer
    `Error('This draft changed since you opened it. Reload to see the latest.')` sets
    `held.stale`, gives the status node class `desk-save-state decision-notice desk-stale`
    and a button `Reload`; any other error says `<message> Your text is kept here.`.
  - `history`: two versions (`save`, `rewrite`) give rows titled `Before your edit` and
    `Before a rewrite` from the fake words; Compare puts a `.desk-compare` under
    `This version compared with now`; Restore sends `restore` with `{id, seen, part,
    index: 1}` and toasts `Restored. The text it replaced is in History.`; a refusal that
    says `changed since` closes the sheet and shows the banner.
  - `selection`: in `'  one two  '` a selection of 0 to 11 gives `held.selection ==
    {part, text: 'one two', start: 0}`; buttons are `Rephrase`, `Shorten`, `Expand`,
    `Fix`, `Ask…`; `Ask…` shows an input and `Go` and `Cancel`; `Go` with an empty box
    notices `Say what to do with the passage.`; with `canEdit() === false` the bar stays
    hidden.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Move the code** into the kit and switch `desk.js`.
- [ ] **Step 4: Run** the new tests, Blog's page check (`deskJourneys`,
  `deskLeaveShares`, `manualEditingJourneys` and the History cases pass unchanged) and
  Blog's suite.
- [ ] **Step 5: Commit**: "Save as you type, keep History and edit a selection through the
  shared desk kit."

## Task 10: Section cards, notes, the job line and the progress line

**Files:**
- Modify: `ui-kit/drafting.js`, `B/assets/management/desk.js`,
  `tests/drafting_page_check.js`, `tests/test_drafting_page.py`

**Interfaces (Produces):**
- `workingIn(view, part)`, `statusWords(held)` (a job with `total` says `Revising section
  n of N…`; a kind in `words().named` adds `a.parts.nameOf`), `problem(held)` (the chain's
  `Revised n of N sections for your note. These were not:` list in `.gap-items`, or the
  last job's error, naming a Finishing tool found in `a.tools()` by `'finish-' + key`),
  `whole(held)`, `part(held, part)` (`a.parts.title`, `a.parts.single` gives an `input`
  with `maxLength = 500`, `a.parts.noted` adds the note box with `How should this
  change?`, `Rewrite` or `Write again`), `job(held, button, route, data, done)` (flushes,
  awaits `a.hooks.beforeJob(held)`, then `a.hooks.refresh` and `watch`), `watch(held)`
  (`desk.js:465-477`; toasts `Suggestions are ready in Finishing.` or `Done. The earlier
  text is in History.`; reruns Proofread when its panel is open).
- `elapsed(start)`, `spent(start)`, `clock(start)`, `estimate(start, what)`,
  `progress(held) -> {actions, above, parts}` and `followStart(held)`
  (`desk.js:268-302`). `progress` gives `above` `Stopped` or `Writing on its own`, the lede
  and steps from `words().steps`, the problem notice with `a.progress.actions(held,
  start)` (Blog: Retry, and what piece 1 added), and the `Progress` card with the clock.
  `followStart` toasts `words().ready(tab)` when the item opens.
- `desk.js`: `sDeskWorkingIn`, `sDeskWorking` (`DESK_KIT.workingIn(held.view, part)`),
  `sDeskStatusWords`, `sDeskProblem`, `sDeskWhole`, `sDeskPart`, `sDeskJob`, `sDeskWatch`,
  `sDeskElapsed`, `sDeskSpent`, `sDeskClock`, `sDeskEstimate`, `sDeskFollowStart` become
  one-line calls. `sDeskProgress` keeps its frame: `const p = DESK_KIT.progress(held);
  sFrame(held.view.title, p.actions, p.above, () => sRoute('blogs')); sPage(...p.parts);
  if (!held.view.start.problem) sDeskFollowStart(held);`. `hooks.beforeJob` is
  `sDeskOutlineFlush`. The `hooks.job` bridge from Task 9 goes.

- [ ] **Step 1: Write the failing groups**:
  - `cards`: a section card holds `History (2)` when two versions are kept and a disabled
    `History` when none; its note box placeholder is `How should this change?`; typing a
    note turns `Write again` into `Rewrite`; while a job works on it the card has class
    `card desk-part desk-working`, a read-only text, `Working on this section` and `Your
    note: <note>`; the title card has an `input` and no note box.
  - `job`: `statusWords` gives `Revising section 2 of 3…` for a chain job at index 1 and
    `Rewriting “Second”…` for a named kind; `job` calls `beforeJob` before it sends; a
    refusal that says `changed since` shows the banner; `watch` toasts `Done. The earlier
    text is in History.` when the last job applied.
  - `progress`: `estimate({minutes_left: 3}, 'The draft') === 'Nothing needed from you.
    The draft opens here when it is ready, in about 3 minutes.'`; with `over: true` and
    `started_at` now it is `'Nothing needed from you. Taking longer than usual; still
    working, under a minute so far. The draft opens here when it is ready.'`;
    `clock({started_at: <two minutes ago>}) === '2 minutes so far, for the whole start.'`;
    a stopped start gives `above === 'Stopped'`, the lede `This start stopped before the
    draft was ready. Retry the step when you are ready.` (or piece 1's words, read from
    `desk.js` on this base), and the adapter's actions in the notice.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Move the code** and switch `desk.js`.
- [ ] **Step 4: Run** the new tests, Blog's page check (`deskProgress`, `deskJourneys`,
  `deskOutlineTab`, `deskTopicStart` pass unchanged) and Blog's suite.
- [ ] **Step 5: Commit**: "Draw the desk's section cards, notes and progress line from the
  shared desk kit."

## Task 11: The Finishing panel, found by name

**Files:**
- Modify: `ui-kit/drafting.js`, `B/assets/management/desk.js`,
  `tests/drafting_page_check.js`, `tests/test_drafting_page.py`

**Interfaces (Produces):**
- A tool, as `a.tools()` lists them in panel order: `{key, name, says}` and, for tools
  that run a job, `run` (the button) and `doing` (the working line); optional
  `options(held, f)` (controls above the run button), `data(f)` (fields the run sends),
  `ready(f)` (whether run is enabled), `opened(held)` (called when the tool opens),
  `view(held)` (a whole view instead of proposals), and the shape flags `verdicts` (facts:
  a tag per item, supported items folded under `Supported (n)`, `Keep it` for Skip),
  `groups` (headline: `Title alternatives`, `Opening alternatives`, `Use this`),
  `comments` (feedback), `applyAll` (humanize, voice), `counted` (`[one, many]`, e.g.
  `[' claim checked', ' claims checked']`) and `empty` (the line for an empty set).
- Kit parts (`desk.js:611-833` and `894-898`): `tool(key)`, `finishOpen(held, tool)`, `finishClose`,
  `finishTool`, `panel`, `panelKey`, `panelShow`, `panelSync`, `toolList`, `toolSays`,
  `toolView`, `proposals`, `proposal`, `apply`, `skip`, `commentKey`, `comments`,
  `comment`, `toNote`, `proofread`, `proofView`, `finding`, `floating`, `layout`. Each
  finds a tool with `a.tools().find(tool => tool.key === key)`; nothing reads a tool by
  position. `proofView` opens with the Proofread tool's own `says`.
- `desk.js`: piece 1 already keyed `DESK_TOOLS` by name and added `deskTool(key)`. Start
  from that shape. `DESK_TOOLS` becomes the list of tool objects above, in today's order
  (humanize, voice, proofread, facts, headline, feedback, publish) with today's words, and
  `deskTool` becomes `key => DESK_KIT.tool(key)` (a kit part: `tool(key)` finds a tool in
  `a.tools()` by `key`). Humanize's
  `options` is `sChoice('Intensity', DESK_LEVELS, f, 'level')` and `data` is `{level}`;
  voice's `opened` is `sDeskGuides`, its `options` the guide field and its "No voice
  guides yet." notice, `data` `{guide}` and `ready` `f => !!f.guide`; facts' `options` the
  "Facts are checked against your sources, and this draft has none yet." notice with Add a
  source; publish's `view` is `sDeskPublishView`. `DESK_RUN` folds into the tools.
  `sDeskFinishOpen` … `sDeskLayout` become one-line calls. `sDeskGuides`,
  `sDeskPublishView` and its cards, `sDeskSheetOpened`, `sDeskSheetClosed` and
  `sDeskResized` stay Blog's.

- [ ] **Step 1: Write the failing groups**:
  - `tools`: a fake tool list in the order publish, proofread, humanize; the tool list
    shows three pick cards in that order; opening `proofread` shows its own `says` first,
    then `Fix rewrites only the sentence a finding is in, and keeps the earlier text in
    History.`; a tool's `opened` is called when it opens.
  - `proposals`: a humanize set of three open items, one flagged, gives `Apply all (2)`
    and `1 flagged suggestion is left for you to check one by one.`; Apply sends `apply`
    with `{id, seen, job, items: [{id: 'p1'}]}` and toasts `Applied. The earlier text is in
    History.`; an answer with `left: ['p2']` adds ` 1 no longer fits and is left for you.`;
    Skip sends `skip`; an item with `present: false` shows `The text changed since this was
    suggested, so it no longer fits.`.
  - `feedback`: a comment on a section shows `Make it a note`; `toNote` puts the comment
    and `(About: “quote”)` into that section's note without replacing what was typed.
  - `layout`: `layout()` is `phone` when `ui.narrow()`, `drawer` under 1100px, else
    `wide`; on a phone the panel has class `desk-finish desk-finish-sheet`.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Move the code** and switch `desk.js`.
- [ ] **Step 4: Run** the new tests, Blog's page check (`deskFinishing` and
  `deskAddSource` pass unchanged) and Blog's suite.
- [ ] **Step 5: Commit**: "Find each Finishing tool by its name in the shared desk kit."

## Task 12: The desk's styles in ui-kit

**Files:**
- Modify: `ui-kit/style.css`, `B/assets/management/blog.css`
- Test: `tests/test_ui_consistency.py` (a new test)

**Interfaces (Produces):** a section `/* --- The desk (drafting.js) --- */` at the end of
`ui-kit/style.css`'s components, holding the rules listed in the spec (item 12) in
ui-kit's one-declaration-per-line form, with the same values and media queries. `blog.css`
keeps `.desk-angles`, `.desk-angle`, `.desk-angle-picked`, `.desk-outline-part` and its
own non-desk rules.

- [ ] **Step 1: Write the failing test** in `tests/test_ui_consistency.py`:
  `test_the_desk_draws_from_ui_kit` lists `DESK = ('.desk-layout', '.desk-column',
  '.desk-aside', '.desk-part-head', '.desk-text', '.desk-note', '.desk-working',
  '.desk-problem', '.desk-stale', '.desk-save-state', '.desk-selection', '.desk-versions',
  '.desk-version', '.desk-compare', '.desk-plain', '.desk-steps', '.desk-clock',
  '.desk-finish', '.desk-finish-head', '.desk-finish-body', '.desk-finish-sheet',
  '.desk-proposal', '.desk-sides', '.desk-side', '.desk-quote', '.desk-edit',
  '.desk-comments', '.desk-comment', '.gap-items', '.diff-add', '.diff-remove')` and
  asserts each class is in a selector of `ui-kit/style.css` and that no selector in
  `blog.css` names it (match whole class tokens, so `.desk-finish` does not match
  `.desk-finish-head`).
- [ ] **Step 2: Run it and see it fail.**
- [ ] **Step 3: Move the rules.** Keep `.desk-selection` with `.glass` on the element, the
  phone rule that lifts it above the tab bar, and `#studio-page>.desk-finish.desk-finish-sheet`.
- [ ] **Step 4: Run** `python3 -m unittest discover -s tests -v`, Blog's page check and
  Blog's suite. Then look: start Blog Studio's page with `BLOG_STUDIO_DATA`,
  `STUDIOS_CONFIG` and `HOME` pointing into a temporary folder, make a desk blog from a
  synthetic draft (no job runs), and compare a desktop and a phone-width window with
  screenshots taken the same way before the move: the same cards, aside, selection bar
  and Finishing panel.
- [ ] **Step 5: Commit**: "Draw the desk from the shared stylesheet."

## Task 13: Docs

**Files:**
- Modify: `docs/core-status.md` (a row: "Desk parts | `core/studio_core/drafting/`,
  `text_checks.py`, `step_times.py`, `ui-kit/drafting.js` | Job queues, kinds and
  writing context; each desk's own screens"), `docs/architecture.md` (the `core/` and
  `ui-kit/` rows name the desk parts), `docs/design/golden-gate.md` (a component row:
  "Desk | `.desk-*` from `drafting.js`"), `studios/blog/CHANGELOG.md` (Unreleased, for
  maintainers: the desk's parts and styles are shared; `desk-edit.md` is now
  `studio_core.drafting.prompts.edit_rule`; `scripts/text_checks.py` is a shim; desk jobs
  keep `checks`), `studios/blog/docs/development.md` (where the desk code lives).
- [ ] **Step 1:** Write the lines. No line says "stale" or "artifact" to a person.
- [ ] **Step 2:** Check links:
  `python3 studios/blog/scripts/measure_guidance.py --check` and
  `PYTHONPATH=.:tests python3 -m unittest test_suite -v`.
- [ ] **Step 3: Commit**: "Say where the shared desk parts live."

## Task 14: Full check

- [ ] **Step 1:** `python3 -m unittest discover -s tests -v` (core and home).
- [ ] **Step 2:** `python3 studios/blog/scripts/ci/run_tests.py` and
  `(cd studios/blog && node scripts/ci/check-management.cjs)`.
- [ ] **Step 3:** Presentation Studio and Training Studio suites, untouched:
  `(cd studios/presentation/tests && python3 -m unittest discover -v)` and
  `(cd studios/training/tests && python3 -m unittest discover -v)`.
- [ ] **Step 4:** The shared Tart runner on macOS: `bash scripts/ci/tart-macos.sh` (the
  full guest run of `scripts/ci/guest-test.sh`). Check that Blog Studio's archive holds
  `skills/blog-studio/assets/management/drafting.js` as a plain file with the same bytes as
  `ui-kit/drafting.js`.
- [ ] **Step 5:** `git grep -n "desk-edit.md"` names only the CHANGELOG and old plans;
  `git grep -n "DESK_TOOLS\[[0-9]"` finds nothing.
- [ ] **Step 6:** Open the pull request: what moved, that Blog Studio looks and works as
  before, the new `checks` field, and that pieces 5 and 6 build on it.
