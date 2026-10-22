# Phase 5: the companions, fully used: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** the studios use Harness Slides 0.16.0, Harness Research 1.0.0 and the brand skill
as those tools intend: one version floor, the tools' own review questions and guidance,
the brand's audit and delivery rules, the research handoff explained, pictures on
Presentation decks, previews in parallel, and no instruction that contradicts a companion.

**Architecture:** shared pieces go in `core/studio_core` (a new `critic.py`; new helpers in
`research_contract.py`). Presentation Studio and Training Studio change their near-copy
runner files the same way, task by task. Blog Studio changes only its research handoff and
brand export. Nothing new is installed; companions are read as they are.

**Tech Stack:** Python 3.11 standard library, plain JavaScript pages with no build step,
`unittest`, the studios' stand-ins for Harness Slides, Harness Research and the brand skill.

**Spec:** `../specs/2026-10-22-phase-5-companions-design.md`. Read it first; this plan
argues from it and numbers its items as "spec item N".

## Global Constraints

- Phases 2 to 5 are built in order, each merged before the next starts. Line references are at main
  21a216e: re-read every named file on the phase's own base first. Training matrix row numbers
  named here are a guide; each new row takes the next free number on that base.
- Python 3.11 or newer, standard library only; no frontend build step.
- Harness Slides floor: `0.16.0` (`MINIMUM`, `RELEASE`, `requirement: ">=0.16.0"`).
- Brand skill floor: `>=0.14.0`, tested `0.14.0`, under a top-level `brand_skill` key in
  `pins/companions.json`, never inside `companions`.
- Use full product names: Marketing Studio, Blog Studio, Presentation Studio, Training
  Studio, Harness Research, Harness Slides, Tanzu Brand.
- Presentation Studio names no brand in code or tests (`tests/test_no_brand_named.py`): say
  "the brand skill" and use the name the skill reports.
- Research and slide building stay delegated to Harness Research and Harness Slides; no
  research or drawing logic is added to a studio.
- A file taken from Training Studio into Presentation Studio is recorded in Presentation's
  `vendor.json` with the source file and revision.
- Guidance under `studios/*/guidance/` that needs a script change raises
  `minimum_runtime` in `guidance/manifest.json` and the studio's `VERSION` together.
- Guidance stays harness-neutral and within budget: Training and Presentation
  `validate_package.py`, Blog `scripts/measure_guidance.py --check`.
- Training: a change to status, approval, inputs or readiness adds a row to the
  state-transition matrix and its `test_row_NN` test (`docs/development.md:111`).
- Person-facing sentences never say "artifact", "stale" or "lineage" (Presentation).
- UI follows `docs/design/golden-gate.md`; forms and reading surfaces stay opaque.
- Tests use disposable settings, workspaces, Git identities and the stand-ins. No provider
  job, no image generation, no network, never the person's studio state.
- Never install or update a studio or companion automatically.

## Review Focus

- A computer with Harness Slides 0.15.1 that a deck began on: the next deck step stops with
  the update sentence, and Status says where 0.15.1 came from when the brand's installer
  brings it; nothing is lost or half-built (Task 1).
- A round whose preview folder has no `critic.json`, or one from a newer tool with
  different questions: the round is refused with a sentence, and a reused review from an
  older round is never matched against questions it was not asked (Task 4).
- A brand audit that refuses or times out during a build: the round goes on to review as
  today, with the note, and no repair round is spent on it (Task 5).
- Two decks previewing through Google at once with a pool of 4, while a third renders
  locally: Google previews overlap, local renders never do, and a turn left by a killed
  process is taken (Task 12).
- A training saved before `delivery` existed, reopened mid-deck: it stays `reading`, its
  outline still passes, and changing delivery after the first outline is refused
  (Task 9).

Each of these has its test in the named task.

---

### Task 1: One floor, Harness Slides 0.16.0

Spec items 1 and 17.3 (the version half).

**Files:**
- Modify: `pins/companions.json` (`harness-slides.requirement`), `README.md:43`
- Modify: `studios/presentation/runner/slides.py:187` (`MINIMUM`)
- Modify: `studios/training/runner/slides.py:186-209` (`MINIMUM`, `RELEASE`, `NAMES`, the
  module docstring lines 81-85)
- Modify: `studios/training/runner/engine.py` (the `dated` sentence near line 1452) and
  `studios/presentation/runner/engine.py` (the matching Status line in its check of this
  computer), to add where an old tool came from
- Test: `tests/test_companion_versions.py`, `studios/training/tests/test_runner_slides.py`,
  `studios/presentation/tests/test_runner_slides.py`, `studios/training/tests/test_runner_engine.py`,
  `studios/presentation/tests/test_engine.py`

**Interfaces:**
- Produces: `slides.MINIMUM == '0.16.0'` (both), Training `slides.RELEASE == '0.16.0'`,
  Training `slides.NAMES` covering every name in Harness Slides 0.16.0's list.
- Produces: `engine.brought_by(version) -> str | None` in each deck studio: the brand
  skill's name when `brand_source.bootstraps(<installed brand folder>)['harness-slides']`
  equals `version`, else None.

- [ ] **Step 1: Write the failing tests**
  - `tests/test_companion_versions.py::test_slides_floor_is_the_pinned_release`: load
    `pins/companions.json`; assert `companions['harness-slides']['requirement'] == '>=0.16.0'`
    and that `README.md` contains `` `>=0.16.0` for Harness Slides `` and not `0.14.1`.
  - Training `test_runner_slides.py::test_release_is_the_pinned_version`: read
    `../installer/companions.json`; assert `slides.RELEASE == pins['companions']['harness-slides']['version'] == '0.16.0'`
    and `slides.MINIMUM == '0.16.0'`.
  - Training `test_runner_slides.py::test_every_capability_has_a_plain_name`: the 28 names
    of 0.16.0, as a literal tuple in the test (`'assets', 'assets-approved-candidates',
    'canonical-digests', 'compose-code-spans', 'compose-icon-assets', 'compose-projects',
    'compose-provenance', 'compose-review', 'compose-section', 'compose-split-point',
    'compose-verified-critique', 'compose-visual-vocabulary', 'design-batch',
    'design-icon-ids', 'design-present-findings', 'design-schema-2', 'google-preview-pool',
    'json-refusals', 'native-charts', 'neutral-native-composition', 'owned-google-previews',
    'preview-repair-clusters', 'relative-records', 'render-bundles', 'review-google-renderer',
    'review-input-refusals', 'review-packets', 'review-sources-from-slide'`); assert each is
    a key of `slides.NAMES` with a value of plain words (no hyphen).
  - Both `test_runner_slides.py::test_older_tool_is_refused`: a stand-in whose `release`
    is `'0.15.1'`; `Slides(...)` raises `WorkspaceError` with exactly
    `'harness-slides 0.15.1 is installed, and a deck needs 0.16.0 or newer. Update it, then try again.'`
  - Training `test_runner_engine.py::test_status_names_the_brand_installer_that_kept_an_old_tool`:
    the stand-in at 0.15.1, a disposable brand folder whose `scripts/lib/harness-install-sources.json`
    is `{"slides": {"version": "0.15.1"}}` and whose skill reports the name `Acme Brand`;
    the computer check's `missing` holds
    `'The slides tool on this computer is version 0.15.1, and a deck needs 0.16.0 or newer. Acme Brand\'s own installer brings 0.15.1. Update it.'`
    With the brand bringing `0.16.0`, the sentence has no installer clause.
  - Presentation `test_engine.py::test_status_names_the_brand_installer_that_kept_an_old_tool`:
    the same, through Presentation's check (brand named `Acme Brand` in the fixture only).
  - Both: a deck already begun whose next step needs the tool, with the stand-in at 0.15.1,
    stops at that step with the same refusal and keeps every file it had (assert the
    deck folder's file list is unchanged).
- [ ] **Step 2: Run them and see them fail**
  `PYTHONPATH=.:tests python3 -m unittest test_companion_versions -v` (from the root);
  `cd studios/training/tests && python3 -m unittest test_runner_slides test_runner_engine -v`;
  `cd studios/presentation/tests && python3 -m unittest test_runner_slides test_engine -v`.
  Expected: FAIL on the versions, the names and the missing installer clause.
- [ ] **Step 3: Implement**
  - Set the three versions; extend `NAMES` with: `compose-code-spans`: 'names and commands
    set as code', `compose-projects`: 'a deck kept as a project', `compose-provenance`:
    'where each slide's words came from', `compose-split-point`: 'a sentence split across
    shapes found in a preview', `compose-verified-critique`: 'a review checked against the
    deck it reviewed', `compose-visual-vocabulary`: 'the drawing words a composition may
    use', `google-preview-pool`: 'a few reusable preview decks in Google Drive',
    `neutral-native-composition`: 'slides drawn as editable shapes',
    `owned-google-previews`: 'preview decks kept as your own', `preview-repair-clusters`:
    'preview problems grouped for repair', `render-bundles`: 'a render kept with what it was
    made from'.
  - Update the Training docstring: "RELEASE is the release a person is told to update to,
    the one `pins/companions.json` pins."
  - Add `brought_by(version)` to each engine (Training reads the brand folder it already
    knows in `_look`; Presentation the same from `self._skill().runtime`), and append
    `f"{name}'s own installer brings {version}. "` before "Update it." when it answers.
  - Set `requirement` and the README sentence.
  - Update the stand-ins only where a test needs a version: their default `release` follows
    `tool.MINIMUM` already.
- [ ] **Step 4: Run the tests again; expect PASS.** Then the two studios' full slides and
  engine modules: `python3 scripts/ci/run_tests.py test_runner_slides test_runner_engine`
  (Training) and `python3 scripts/ci/run_tests.py test_runner_slides test_engine`
  (Presentation). Fix any test that asserted `0.13.1`, `0.14.1` or `0.15.1` as the floor;
  leave tests that use those numbers as brand-skill or installer fixtures alone.
- [ ] **Step 5: Commit** "Take Harness Slides 0.16.0 as the one floor, and say where an older one came from".

### Task 2: A floor for the brand skill

Spec item 2.

**Files:**
- Modify: `pins/companions.json` (new top-level `brand_skill`)
- Modify: `studios/presentation/runner/brand.py`, `studios/training/runner/brand.py` (a
  `BRAND_FLOOR` read and `Brand.version()` if not there)
- Modify: both engines' check of this computer (`_look` / the Presentation equivalent near
  `engine.py:1160`)
- Test: `tests/test_companion_versions.py`, both studios' `test_installer.py`,
  `test_runner_brand.py`, and the engine tests

**Interfaces:**
- Produces: `brand.FLOOR: str` read from `installer/companions.json` `brand_skill.requirement`
  (`'0.14.0'` after stripping `>=`), falling back to `'0.14.0'` when the file is absent.
- Produces: `brand.too_old(version: str) -> str | None`, the Status sentence or None.

- [ ] **Step 1: Write the failing tests**
  - `test_companion_versions.py::test_brand_skill_floor_is_not_installed`: the file has
    `brand_skill == {'requirement': '>=0.14.0', 'tested': '0.14.0', 'note': ...}`;
    `'brand_skill' not in pins['companions']`; `scripts/update_companions.py`'s loader and
    `core/studio_core/companions.py`'s readers run over the file without error and list
    only `harness-research` and `harness-slides`.
  - Both `test_installer.py::test_pins_with_a_brand_floor_install_as_before`: write pins
    with the extra key to the disposable base; `install.read_pins` returns the same two
    companions as without it.
  - Both `test_runner_brand.py::test_too_old`: `brand.too_old('0.13.2')` ==
    `'Your brand skill is 0.13.2. Decks need 0.14.0 or newer, for its look samples and talk-or-handout export. Update it in Settings.'`;
    `brand.too_old('0.14.0') is None`; `brand.too_old('1.2.0') is None`.
  - Both engine tests: a brand stand-in reporting `0.13.2` puts that sentence in the
    check's `missing`; a new deck waits at its brand step with it; one reporting `0.14.0`
    does not.
- [ ] **Step 2: Run them; expect FAIL.**
- [ ] **Step 3: Implement.** Add the entry
  (`"note": "The brand skill is the person's own; Marketing Studio never installs it. Decks need this version or newer."`).
  Read the floor in `brand.py`; compare with the existing version-order helper
  (`brand_source.order`). Call `too_old` with the version the brand skill already reports
  in the check of this computer.
- [ ] **Step 4: Run again; expect PASS.** Add `test_installer` and `test_runner_upkeep` to
  the run in both studios.
- [ ] **Step 5: Commit** "Give the brand skill a floor the studios check, and installers ignore".

### Task 3: Drop the progress-events path

Spec item 3. Presentation Studio only.

**Files:**
- Modify: `studios/presentation/runner/slides.py` (remove `PROGRESS`, `contextvars`
  import if unused, `Slides.progress`, the `each`/`events`/`observing` lines of `preview`,
  and `slide_events` from the import line 184)
- Delete: `studios/presentation/runner/slide_events.py`
- Modify: `studios/presentation/runner/worker_tools.py:748-760` (no `observing`; keep
  `build_progress.Preview` start, `finish` and `failed`)
- Modify: `studios/presentation/runner/build_progress.py` (remove `Preview.event` if
  nothing else calls it)
- Test: `studios/presentation/tests/test_build_progress.py`, `test_runner_slides.py`

**Interfaces:**
- Consumes: nothing. Produces: `Slides.preview(...)` with the same signature and return.

- [ ] **Step 1: Change the tests first.** In `test_build_progress.py` remove the test that
  drives `slide_events.watching` (near line 120) and add
  `test_preview_records_start_and_finish_without_events`: a preview through the stand-in
  writes the progress file with `started` then `finished`, and the stand-in's recorded
  calls contain no `--events`. In `test_runner_slides.py` add
  `test_preview_never_asks_for_events`: even with a stand-in listing `progress-events`,
  no call carries `--events`.
- [ ] **Step 2: Run** `cd studios/presentation/tests && python3 -m unittest test_build_progress test_runner_slides -v`;
  expect the new tests to FAIL.
- [ ] **Step 3: Remove the code** listed above. `grep -rn "slide_events\|PROGRESS\|\.progress(" studios/presentation`
  returns nothing outside `build_progress`'s own names.
- [ ] **Step 4: Run again; expect PASS.** Then `python3 scripts/ci/run_tests.py test_runner_worker_tools test_step_build`.
- [ ] **Step 5: Commit** "Remove the wait for preview events Harness Slides never sends".

### Task 4: The critic's questions from `critic.json`

Spec item 6.

**Files:**
- Create: `core/studio_core/critic.py`
- Modify: `studios/presentation/runner/steps/build.py` (remove `QUESTIONS` and its
  docstring sentence at lines 73-76; `asked`, the findings check near 411, the reuse check
  near 1479 and 1499, `repair` wording near 1583 and the gate text near 1439 read the round's
  questions)
- Modify: `studios/training/runner/deck.py` (remove `QUESTIONS` at 148 and its docstring
  at 68; `asked` 1284, the check at 1130, 1260), `studios/training/runner/pipeline.py`
  `review_work` (1877)
- Test: `tests/test_critic.py` (new), `studios/presentation/tests/test_step_build.py`,
  `studios/training/tests/test_runner_deck.py`, `test_runner_deck_whole.py`

**Interfaces:**
- Produces: `critic.questions(folder: Path) -> tuple[str, ...]`. Reads
  `folder / 'critic.json'`; returns `tuple(packet['questions'])` when it is a list of 1 to
  12 non-empty strings; otherwise raises `ValueError(critic.MISSING)` with
  `MISSING = "The slides tool's review questions are not with this preview. Put the deck together again."`
- Produces: each round record gains `'questions': [...]`, written when the round's whole
  preview is recorded (Presentation `whole`, Training the round record in `deck.py`).
- Produces: `build.round_questions(round: dict) -> tuple[str, ...]` (Presentation) and
  `deck.round_questions(round: dict)` (Training): the round's `questions`; a round saved
  before this change returns the eight 0.16.0 questions held as `critic.LEGACY` for that
  round only.

- [ ] **Step 1: Write the failing tests**
  - `tests/test_critic.py`: `test_reads_the_tools_questions` (a disposable folder with
    `{"schema": 2, "questions": ["A?", "B?"]}` gives `('A?', 'B?')`);
    `test_refuses_a_missing_packet`; `test_refuses_a_malformed_packet` (questions not a
    list, an empty string, 13 questions); each refusal's message equals `critic.MISSING`.
    `critic.LEGACY` equals, word for word, Harness Slides 0.16.0's eight
    (`scripts/lib/compose-preview.mjs:105-114`).
  - Presentation `test_step_build.py::test_reviewer_is_asked_the_rounds_questions`: a
    round whose preview's `critic.json` holds three made-up questions; `review_work(...)`
    inputs "the review" list exactly those three, numbered 1 to 3, and a finding with
    `question: 4` is refused as "`question` is a number from 1 to 3".
  - Presentation `test_step_build.py::test_reuse_needs_the_same_questions`: two rounds
    with different `questions`; `reusable_review` returns `{}`.
  - Training `test_runner_deck.py`: the same two tests through `pipeline.review_work` and
    the round reuse.
  - Both: a round saved without `questions` reads `critic.LEGACY` and a review recorded
    against it is still accepted.
- [ ] **Step 2: Run** `PYTHONPATH=.:tests python3 -m unittest test_critic -v`, then the two
  studios' modules; expect FAIL.
- [ ] **Step 3: Implement** `critic.py` (docstring in the house style: "What a caller needs
  to know"). Record `questions` from the round's preview folder where each studio records
  the round; refuse the round with `WorkspaceError(critic.MISSING)` when absent. Replace
  every `QUESTIONS` read with `round_questions(round)`.
- [ ] **Step 4: Run again; expect PASS.** Then `python3 scripts/ci/run_tests.py test_step_build test_engine`
  (Presentation) and `python3 scripts/ci/run_tests.py test_runner_deck test_runner_deck_whole test_runner_engine`
  (Training). The stand-ins already write `critic.json` on a whole preview; if one does
  not, make it write the eight `critic.LEGACY` questions.
- [ ] **Step 5: Commit** "Ask the reviewer the slides tool's own questions, from each preview".

### Task 5: The brand audit before review

Spec item 7.

**Files:**
- Modify: `studios/presentation/runner/steps/build.py` (new `audit_round(root, run, brand)`
  called after `whole` records a round; `repair_sections` takes the audit findings)
- Modify: `studios/presentation/runner/engine.py` (call it in the build loop, before
  `review_work`)
- Modify: `studios/training/runner/engine.py` (`_review` near 2500 and the round's audit;
  the render audit at 2581 stays) and `studios/training/runner/deck.py` (findings)
- Test: `studios/presentation/tests/test_step_build.py`, `test_engine.py`;
  `studios/training/tests/test_runner_deck_whole.py`, `test_runner_engine.py`

**Interfaces:**
- Consumes: `Brand.audit(deck, brand_id, variant) -> dict` with `blockers` and
  `warnings`, each `{'slide': int | None, 'says' | 'code': str}` (as `audited()` reads it).
- Produces: `build.audit_findings(report: dict, slides: list[dict]) -> tuple[list[dict], list[str]]`:
  findings `{'slide': <id>, 'severity': 'critical', 'about': 'drawing', 'question': None,
  'note': "The brand's check: <says>", 'source': 'brand'}` for each blocker on a numbered
  slide, and the warnings as lines. Training's `deck.audit_findings` has the same shape.
- Produces: the round record's `audit` (`audited()` shape) and `audit_findings`.

- [ ] **Step 1: Write the failing tests**
  - Presentation `test_step_build.py::test_a_brand_blocker_sends_its_section_back`: a
    brand stand-in whose audit of the round's deck returns one blocker on slide 3; after
    the round, slide 3's section is in the next `to_draw`, the finding's note starts
    "The brand's check:", and `REPAIRS` counts it.
  - `test_brand_warnings_reach_the_reviewer`: two warnings appear in the reviewer's "the
    review" input under "## What the brand's check noticed".
  - `test_an_audit_that_cannot_run_changes_nothing`: the audit raises `WorkspaceError`;
    the round goes to review, no section is sent back, and the round's `auditNote` is
    "The brand's check of this deck could not be run. <its words>".
  - `test_render_still_audits_the_delivered_deck`: the gate's `audit` is the delivered
    deck's, as now.
  - Training `test_runner_deck_whole.py`: the same four through the training build.
  - Review Focus: `test_audit_refusal_spends_no_repair_round` in both: the refused audit
    leaves the round's repair count where it was.
- [ ] **Step 2: Run; expect FAIL.**
- [ ] **Step 3: Implement.** A finding with `question: None` is shown as "the brand's
  check" wherever the question text is shown (the gate text near build.py:1439 and
  Training's 1260). Findings from the brand are never reused across rounds.
- [ ] **Step 4: Run again; expect PASS**, with `test_step_build test_engine` and
  `test_runner_deck_whole test_runner_engine`.
- [ ] **Step 5: Commit** "Run the brand's check before review, so its blockers are repaired".

### Task 6: The reviewer gets the review guidance and the brand checklist

Spec item 8.

**Files:**
- Modify: `core/studio_core/brand_guidance.py` (new `review_texts(answer)`)
- Modify: `studios/presentation/runner/steps/build.py` `review_work`,
  `studios/presentation/runner/briefs/review.md`
- Modify: `studios/training/runner/pipeline.py` `review_work`,
  `studios/training/runner/briefs/deck-review.md` and `deck-review-design.md`
- Test: `tests/test_brand_guidance.py` (new; the root has none), `studios/presentation/tests/test_step_build.py`,
  `studios/presentation/tests/test_briefs.py`, `studios/training/tests/test_runner_pipeline.py`,
  `test_runner_briefs.py`

**Interfaces:**
- Produces: `brand_guidance.review_texts(answer: dict) -> dict`:
  `{'brand review checklist': <text>}` read from `answer['brand']['review']` when it is an
  absolute path to a regular `.md` file (same rules and `READ_MOST` as `brand_texts`);
  `{}` otherwise.
- Consumes: the snapshot's `'review guidance'` (`brand_guidance.GUIDES`), kept with each
  deck's reading as the composers' is.

- [ ] **Step 1: Write the failing tests**
  - `review_texts`: a disposable `slide-review.md` named by absolute path is read; a
    relative path, a `.txt`, a folder and a symlink to outside are each ignored.
  - Presentation `test_step_build.py::test_reviewer_reads_the_review_guidance`: with a
    kept reading holding `review guidance` and a checklist, `review_work(...).prepared['inputs']`
    has both, under `'review guidance'` and `'brand review checklist'`; without them, the
    inputs hold only "the review".
  - `test_briefs.py::test_review_brief_names_its_reading`: `briefs.guidance('review')`
    contains "Read the review guidance and the brand's review checklist, when you are given
    them, before you look. Judge each slide by the questions in \"the review\"."
  - Training: the same through `pipeline.review_work` and `deck-review.md`.
- [ ] **Step 2: Run; expect FAIL.**
- [ ] **Step 3: Implement.** Keep `review_texts` with each deck's reading where
  `brand_guidance.snapshot(answer)` is kept (Presentation `build.py:519`, Training
  `engine.py:1944`).
- [ ] **Step 4: Run again; expect PASS.** Run `validate_package.py` in both studios if a
  brief under `guidance/` changed (these are runner briefs, so it should not).
- [ ] **Step 5: Commit** "Give the deck reviewer the slides tool's review guidance and the brand's checklist".

### Task 7: The brief lines: code spans, the focal, and what the studio does for the worker

Spec items 4, 17.2 and 17.4.

**Files:**
- Modify: `studios/presentation/runner/briefs/outline-brief.md`, `outline-material.md`,
  `outline-spec.md`, `section.md`, `section-repair.md`
- Modify: `studios/training/runner/briefs/deck-outline.md`, `deck-section.md`,
  `deck-section-design.md`, `deck-repair.md`
- Test: `studios/presentation/tests/test_briefs.py`, `studios/training/tests/test_runner_briefs.py`,
  `studios/training/tests/test_runner_deck.py` (word checks)

**Interfaces:** none new. The briefs are read through `briefs.guidance(name)`.

- [ ] **Step 1: Write the failing tests**
  - Both brief tests: `CODE = 'Write a configuration field, command, API or file name as a code span in backticks, such as `highAvailability`, with plain English first the time it appears. A title names things in words and takes no code span.'`
    appears in every outline and section brief named above.
  - Both: no brief contains "Ignore anything it says about preview files"; both section
    briefs contain `'Your reading speaks of previews, critique, delivery and asking the person. Here: preview with `preview_section`; a separate reviewer answers the critic\'s questions after you, so write no critique; delivery and questions to the person are the studio\'s, and you cannot ask.'`
    (Training's section worker also previews with `preview_section`, `deck-section.md:38`.)
  - Training: no brief contains "even where the brief names it as the point";
    `deck-section.md` and `deck-section-design.md` contain
    `'Equals share one size and weight. Where the outline names a focal, give it the one emphasis on the slide, as the composition guidance says. On a slide that compares equals (`contrast` or `parallel`), set them alike.'`
  - Training `test_runner_deck.py::test_code_spans_are_kept_and_counted_as_words`: a point
    "High availability (`highAvailability`) is off" drawn as the same text is kept by
    `kept`, and counts the same number of words as without the backticks.
  - Presentation `test_step_build.py`: the same `kept` test.
- [ ] **Step 2: Run** `cd studios/presentation/tests && python3 -m unittest test_briefs -v`
  and `cd studios/training/tests && python3 -m unittest test_runner_briefs test_runner_deck -v`;
  expect FAIL.
- [ ] **Step 3: Edit the briefs.** Put the code-span line under each brief's rules for
  words. Keep each brief's length within a few lines of what it was.
- [ ] **Step 4: Run again; expect PASS.**
- [ ] **Step 5: Commit** "Tell slide writers about code spans, and stop contradicting the slides tool".

### Task 8: The research handoff, the author's guide, and comparisons

Spec items 9, 10, 17.1 and 17.5.

**Files:**
- Modify: `core/studio_core/research_contract.py` (`Workflow.run` author `guide` and
  `return`; new `HANDOFF`, `COMPARES`, `purpose()`)
- Modify: `studios/presentation/runner/research_steps.py:262` (`task['purpose']`),
  `studios/presentation/runner/steps/outline.py:371-380` (inputs)
- Modify: `studios/training/runner/engine.py:3269` (`task['purpose']`),
  `studios/training/runner/pipeline.py:1337 findings_text`
- Modify: `studios/blog/skills/blog-studio/scripts/synthesis_research.py:193`,
  `studios/blog/skills/blog-studio/scripts/blog_worker.py` (`POLICY`)
- Test: `tests/test_research_contract.py`, `studios/presentation/tests/test_step_outline.py`,
  `studios/presentation/tests/test_runner_research.py`, `studios/training/tests/test_runner_pipeline.py`,
  `studios/training/tests/test_runner_research.py`, `studios/blog/tests/test_blog_runner.py`
  and the Blog test that reads `POLICY` (`grep -rln "POLICY" studios/blog/tests`)

**Interfaces:**
- Produces: `research_contract.HANDOFF: str`, exactly the spec item 9 sentence.
- Produces: `research_contract.COMPARISON = 'The goal compares options: include a comparison with one criterion per row, and say where something is unknown rather than absent.'`
- Produces: `research_contract.compares(goal: str) -> bool`: True when the lower-cased goal
  contains a word `compare`, `compares`, `comparing`, `comparison`, `versus`, `vs`,
  `vs.`, `alternatives`, or the phrases `choose between`, `which is better`, or matches
  `\b\w+ or \w+\b` where both sides start with a capital letter in the original goal
  ("Redis or Valkey").
- Produces: `research_contract.purpose(kind: str, goal: str, priorities: str) -> str`:
  `f'Inform {kind}: {goal or "explain the topic"}. {priorities}'` plus `' ' + COMPARISON`
  when `compares(goal)`.

- [ ] **Step 1: Write the failing tests**
  - `test_research_contract.py::test_author_is_handed_its_stage_references_only`: with a
    disposable runtime folder holding `references/investigate.md`, `synthesize.md` and
    `studio-handoff.md` (each one line), the author job's `guidance` contains the first two
    and not the third.
  - `test_author_return_line_names_the_tools_captures`: the author payload's `return`
    contains "The studio's tools have saved every capture for you: that is the capture
    `investigate.md` asks for. Cite each source by the file path the tools gave it,
    exactly. Write no files yourself." and not "research/sources/".
  - `test_compares`: True for "Compare Redis and Valkey", "Redis versus Valkey", "Redis vs
    Valkey", "Choose between two caches", "Redis or Valkey for sessions"; False for "Explain
    how caching works", "cache reads or writes" (lower-case sides), "Teach Kubernetes".
  - `test_purpose`: `purpose('a presentation', 'Redis or Valkey', 'Prioritize X.')` ends
    with `COMPARISON`; for "Explain caching" it equals
    `'Inform a presentation: Explain caching. Prioritize X.'`.
  - Presentation `test_runner_research.py`: the research task's `purpose` is built with
    `purpose('a presentation', form['goal'], ...)`; `test_step_outline.py`: the outline
    inputs' "Research selection" starts with `HANDOFF`.
  - Training `test_runner_pipeline.py::test_findings_text_leads_with_the_handoff`: under
    schema 2 the text starts `'# Reviewed research handoff\n\n' + HANDOFF`; "Cite stable
    finding IDs" is not in it. `test_runner_research.py`: the task's purpose comes from
    `purpose('training…', …)`.
  - Blog: `POLICY` contains "`research_bundle`" and `HANDOFF`; the research task's purpose
    comes from `purpose('a blog', …)`.
- [ ] **Step 2: Run; expect FAIL.**
  `PYTHONPATH=.:tests python3 -m unittest test_research_contract -v`; the studios' modules;
  `cd studios/blog/tests && HOME=$TMPDIR/h python3 -m unittest test_blog_runner -v`.
- [ ] **Step 3: Implement.** Keep each studio's priorities text as it is now, passed as
  `priorities`. In Training, move "Cite stable finding IDs" into `briefs/blueprint.md` and
  `briefs/brief.md` if they do not already say it (check first; the format checks in
  `pipeline.py:277-280` need IDs there).
- [ ] **Step 4: Run again; expect PASS**, plus `STUDIO_TEST_RESEARCH_RUNTIME` unset
  integration suites (`test_synthesis_integration` in all three, which skip without it).
  Blog: `ruff format --check .` and `ruff check .` in `studios/blog`.
- [ ] **Step 5: Commit** "Tell writers what the research is, ask for comparisons, and stop contradicting Harness Research".

### Task 9: Training asks once: a talk or a handout

Spec items 5 and 17.3.

**Files:**
- Modify: `studios/training/skills/training-studio/scripts/workspace.py` (`init` takes
  `delivery='live'`; `load` does `session['settings'].setdefault('delivery', 'reading')`
  and checks it is in `DELIVERIES = ('live', 'reading')`)
- Modify: `studios/training/runner/pipeline.py` (`check_form` takes `delivery`, default
  `'live'`; passes it to `workspace.init`; `delivery_of(session) -> str`)
- Modify: `studios/training/runner/deck.py` (lines 94, 372-374, 651: the outline check and
  `complete` take `delivery`)
- Modify: `studios/training/runner/engine.py` (1575, 1644 brand export; look samples at
  1713 and 1733; a refused change after the first outline)
- Modify: `studios/training/runner/briefs/deck-outline.md` (a live deck's notes line)
- Modify: `studios/training/skills/training-studio/scripts/desk/app.js` (the deck step's
  question), the session format's example and guidance where they list settings
  (`grep -rn "deck_target" studios/training/skills/training-studio/references studios/training/skills/training-studio/assets`)
- Test: `studios/training/tests/test_workspace.py` (a matrix row), `test_runner_pipeline.py`,
  `test_runner_deck.py`, `test_runner_engine.py`, `test_desk.py`

**Interfaces:**
- Produces: `pipeline.delivery_of(session: dict) -> str`, `'live'` or `'reading'`.
- Produces: `deck.check_outline(..., delivery: str)` (the function holding line 372; keep
  its name) and `deck.complete(..., delivery)`; `deck.DELIVERY` stays `'reading'` as the
  value for an older session only.
- Produces: the form field `delivery` (`'live'` | `'reading'`).

- [ ] **Step 1: Write the failing tests**
  - `test_workspace.py::test_row_NN_delivery` (next free row number; add the row to the
    matrix in `docs/superpowers/plans/2026-10-20-training-workflows.md`'s matrix or the
    plan the docs name in `docs/development.md:111`): an old session without `delivery`
    loads as `'reading'` and saves unchanged; `init(..., delivery='live')` writes `'live'`;
    `init(..., delivery='spoken')` is refused with "Choose live or reading for the deck."
  - `test_runner_pipeline.py::test_form_delivery_defaults_to_live`: `check_form` without
    `delivery` gives `'live'`; with `'reading'` gives `'reading'`.
  - `test_runner_deck.py::test_outline_delivery_follows_the_training`: a live training's
    outline with `delivery: "reading"` is refused with
    `'This deck is presented in a session: set `delivery` to "live".'`; a reading
    training's with `"live"` with `'This deck is read on its own: set `delivery` to "reading".'`
    No message contains "read alone as well as presented".
  - `test_runner_engine.py::test_brand_is_exported_for_the_trainings_delivery`: the brand
    stand-in's recorded `contract export` call carries `--delivery live` for a live
    training, and `look samples` the same.
  - `test_runner_engine.py::test_delivery_cannot_change_after_the_first_outline` (Review
    Focus): a training whose first deck outline is written refuses a form change of
    delivery with "The deck has been written for a talk. Start the deck again to change it."
  - Review Focus: `test_old_training_mid_deck_stays_reading`: a session saved without
    `delivery`, with an outline in hand, reopens and its outline passes the check unchanged.
  - `test_desk.py`: the deck step shows "How is this deck used?" with "Presented in a
    session" selected and "Read on its own"; the text "A spoken session is presented
    live; choose Read on its own for self-study." under it.
- [ ] **Step 2: Run** `cd studios/training/tests && python3 -m unittest test_workspace test_runner_pipeline test_runner_deck test_runner_engine test_desk -v`;
  expect FAIL.
- [ ] **Step 3: Implement.** Raise Training's `guidance/manifest.json` `minimum_runtime`
  and `VERSION` together if the guidance describes `session.json` settings and changes.
- [ ] **Step 4: Run again; expect PASS.** Then `python3 skills/training-studio/scripts/validate_package.py`
  and `python3 scripts/ci/run_tests.py test_runner_deck_whole test_runner_flow`.
- [ ] **Step 5: Commit** "Ask once whether a training's deck is presented or read, and default to a talk".

### Task 10: Training's design walkthrough only when asked

Spec items 16 (Training) and 17.6.

**Files:**
- Modify: `studios/training/skills/training-studio/scripts/workspace.py` (`walkthrough`
  setting, default False; older sessions `setdefault('walkthrough', True)` only when a
  deck outline was already written with a design, else False — see Step 1)
- Modify: `studios/training/runner/pipeline.py` (`check_form` takes `walkthrough: bool`)
- Modify: `studios/training/runner/engine.py:1952 _designed` and the readiness use of
  `slides.NEEDED`; `studios/training/runner/slides.py` (`NEEDED` becomes the needs of a deck
  without design, `DESIGN_NEEDED` the rest)
- Modify: `studios/training/skills/training-studio/scripts/desk/app.js` (the deck step's
  checkbox)
- Test: `test_workspace.py` (matrix row), `test_runner_engine.py`, `test_runner_deck_whole.py`,
  `test_runner_slides.py`, `test_desk.py`

**Interfaces:**
- Produces: `slides.NEEDED = ('json-refusals',)` and
  `slides.DESIGN_NEEDED = ('design-schema-2', 'design-batch', 'compose-section', 'assets', 'compose-review')`;
  `Slides.lacks(design: bool = False)` names what is missing of `NEEDED`, plus
  `DESIGN_NEEDED` when `design`.
- Produces: `engine._designed(mine)`: a deck already written keeps what it was written
  with (as now); a new deck returns `pipeline.walkthrough_of(session)` and the tool's
  `designs()`.

- [ ] **Step 1: Write the failing tests**
  - `test_workspace.py::test_row_NN_walkthrough`: a new session has `walkthrough: False`;
    an old session with no setting loads as False; a deck already written with a design
    keeps its design (the deck record's `outline.design` decides, not the setting).
  - `test_runner_engine.py::test_new_deck_is_built_without_a_design_session`: with a
    stand-in that has the design session (`stand_in(current=True)`), a new deck's outline
    job is not `designed` and no `design propose` call is made.
  - `test_walkthrough_runs_the_design_session`: the same with `walkthrough: True` makes the
    design calls as today (reuse an existing designed-deck test's assertions).
  - `test_runner_slides.py::test_lacks_by_design`: a stand-in listing only `json-refusals`
    lacks nothing for `lacks()` and all five for `lacks(design=True)`.
  - `test_desk.py`: the deck step has an unchecked "Walk through each slide's design before
    it is built" with the line "Usually the deck is approved on what it says and on its
    look. Choose this to approve how each slide is drawn, one at a time."
- [ ] **Step 2: Run; expect FAIL.**
- [ ] **Step 3: Implement.** Keep every design-session path; only the choice of when it
  runs changes.
- [ ] **Step 4: Run again; expect PASS.** Then `python3 scripts/ci/run_tests.py` for
  `test_runner_deck_whole test_runner_flow test_review_levels`. The Balanced review count
  (`pipeline.gates`) is unchanged: a deck still stops at what it says and at the deck.
- [ ] **Step 5: Commit** "Approve a training deck on its words and look, and walk through slide designs only when asked".

### Task 11: Supplied pictures on Presentation decks

Spec item 11.

**Files:**
- Modify: `studios/presentation/runner/page.py` (`/api/picture` in `WRITES`; handler
  decoding base64 like `/api/decks`, inside `DECKS_LIMIT`)
- Modify: `studios/presentation/runner/engine.py` (new `add_picture`)
- Modify: `studios/presentation/runner/steps/build.py` (the asset project folder,
  `--asset-project` on compile, which slides carry a picture in each section's inputs,
  `asset_check` before the deck stop)
- Modify: `studios/presentation/runner/slides.py` (`compile(..., assets: Path | None = None)`
  passing `--asset-project`)
- Modify: `studios/presentation/runner/briefs/section.md` (one line: "A slide whose brief
  names a picture draws it as an image by its `asset`, in the layout's picture slot, and
  keeps its words native.")
- Modify: `studios/presentation/skills/presentation-studio/scripts/desk/app.js` (on the
  outline gate, "Add a picture" on a cover, section or content slide)
- Test: `test_engine.py`, `test_step_build.py`, `test_runner_slides.py`, `test_runner_page.py`,
  `test_desk.py`, `test_server_security.py` (the new write route)

**Interfaces:**
- Produces: `Engine.add_picture(path, slide: str, filename: str, data: bytes, alt: str,
  source: str, expected: str | None) -> dict` returning `{'asset': <id>, 'slide': slide}`.
  Refuses: not at the outline gate ("Add a picture while the outline is waiting for you."),
  not PNG or JPEG by its first bytes ("A picture is a PNG or a JPEG file."), over 20 MB,
  empty `alt` ("Say what the picture shows, for someone who cannot see it."), empty
  `source`, an unknown slide, a stale `expected`.
- Produces: `build.ASSETS = Path('work') / 'assets'` (the asset project) and the outline
  entry `slide['picture'] = {'asset': <id>}`; the asset ID is `pic-<slide id>`.
- Consumes: `Slides.asset_supplied(project, file, ident, alt, source, ...)` and
  `Slides.asset_check(project, brand)` as wrapped at `slides.py:637-664`.

- [ ] **Step 1: Write the failing tests**
  - `test_engine.py::test_add_picture`: at the outline gate, a 1x1 PNG is recorded
    through the stand-in's `assets add-supplied` with the given alt and source, and the
    outline's slide names `{'asset': 'pic-<id>'}`; each refusal above with its sentence.
  - `test_step_build.py::test_compile_uses_the_asset_project`: a deck with a picture
    compiles with `--asset-project <root>/work/assets`; one without never passes it.
  - `test_step_build.py::test_asset_check_problems_stop_before_the_deck`: the stand-in's
    `assets check` returns a problem; the deck stop shows it in the tool's words and the
    deck is not delivered.
  - `test_runner_page.py`: POST `/api/picture` needs the page's token like every write
    (`test_server_security.py` lists it).
  - `test_desk.py`: "Add a picture" appears on the outline gate's slide rows and the form
    asks for the file, "What it shows" and "Where it came from".
  - No test sets an image provider key, and `images generate` is never called (assert the
    stand-in's calls).
- [ ] **Step 2: Run; expect FAIL.**
- [ ] **Step 3: Implement.** Port nothing from Training without recording it in
  `studios/presentation/vendor.json`.
- [ ] **Step 4: Run again; expect PASS**, with `python3 -m unittest test_no_brand_named`.
- [ ] **Step 5: Commit** "Let a person add their own picture to a Presentation Studio slide".

### Task 12: Previews in parallel through the pool

Spec item 12.

**Files:**
- Modify: `studios/presentation/runner/slides.py` and `studios/training/runner/slides.py`
  (`PREVIEWING` → `turn(renderer)`)
- Modify: `studios/presentation/runner/worker_tools.py:702` and
  `studios/training/runner/worker_tools.py:736` (`one_at_a_time` → `turn(lock, slots)`),
  and their callers (Presentation `build.py` `picture_deck`, `_patched_pictures`,
  `worker_tools.render`; Training `worker_tools.py:773`, `815`, `engine.py:1712`)
- Test: both `test_runner_slides.py` and `test_runner_worker_tools.py`

**Interfaces:**
- Produces: `slides.POOL = int(os.environ.get('HARNESS_PREVIEW_POOL_SIZE') or 4)` (a value
  below 1 or not a number is 4); `Slides.turn(renderer: str)`, a context manager: for
  `'local'` or a tool without `google-preview-pool`, one process-wide `threading.Lock`; for
  `'drive'` on a pooled tool, a process-wide `threading.BoundedSemaphore(POOL)`.
- Produces: `worker_tools.turn(lock: Path, slots: int = 1, wait: float = RENDER_WAIT)`, a
  context manager taking the first free of `lock`, `lock.1`, … `lock.<slots-1>`, with
  today's stale-holder rule for each. `one_at_a_time(lock)` stays as `turn(lock, 1)`.
- Produces: `worker_tools.slots(how: dict, slides) -> int`: `slides.POOL` for a Drive
  render on a pooled tool, else 1.

- [ ] **Step 1: Write the failing tests**
  - Both `test_runner_slides.py::test_google_previews_overlap_on_a_pool`: the stand-in
    lists `google-preview-pool` with `pause = 0.2`; four threads preview with `'drive'`;
    the stand-in's `at_once` is 4. With `HARNESS_PREVIEW_POOL_SIZE=2`, it is 2.
  - `test_local_renders_never_overlap` (Review Focus): two `'local'` previews and two
    `'drive'` ones at once; the stand-in records no two local renders in progress
    together (track per renderer in the test's stand-in subclass).
  - `test_without_a_pool_drive_is_one_at_a_time`: a tool not listing the pool keeps
    `at_once == 1`.
  - Both `test_runner_worker_tools.py::test_turn_slots`: with `slots=2`, two holders
    proceed and a third waits until one leaves; a slot file naming a dead process id is
    taken (Review Focus).
- [ ] **Step 2: Run; expect FAIL.**
- [ ] **Step 3: Implement.** `review_prepare` and `pictures_of` take the same turn as
  `preview`.
- [ ] **Step 4: Run again; expect PASS**, then `python3 scripts/ci/run_tests.py test_step_build test_engine`
  and Training's `test_runner_deck_whole test_runner_flow`.
- [ ] **Step 5: Commit** "Render Google previews side by side through the pool, and local ones one at a time".

### Task 13: The brand's doctor in Status

Spec item 13.

**Files:**
- Modify: `studios/presentation/runner/engine.py` (the check of this computer near 1160)
  and `studios/training/runner/engine.py` (`_look` and the Status lines near 1445)
- Modify: both `runner/brand.py` (`Brand.fonts() -> str | None` from `ready()`)
- Modify: both desk `app.js` only if the Status screen needs a new row kind (it should take
  a line in `missing` as now)
- Test: both `test_runner_brand.py`, Training `test_runner_engine.py`, Presentation
  `test_engine.py`

**Interfaces:**
- Produces: `Brand.fonts() -> str | None`: None when the doctor's `capabilities` entry
  `arial` is `available` or the doctor cannot be run; otherwise
  `'Arial was not found on this computer, so slides may be drawn in another font. Install licensed Arial.'`
- Produces: the check's `fonts` key (that sentence or None), cached with the other looks.

- [ ] **Step 1: Write the failing tests**
  - `test_runner_brand.py::test_fonts`: the brand stand-in's `doctor --profile
    presentation --json` answers `{"capabilities": [{"name": "arial", "status": "unverified"}]}`
    → the sentence; `available` → None; a refused doctor → None.
  - Engine tests: the sentence is in the check's `missing`; with `available`, no line;
    the doctor is asked once within the cache window (count stand-in calls).
- [ ] **Step 2: Run; expect FAIL.**
- [ ] **Step 3: Implement.** Where the doctor reports soffice or Poppler missing, show the
  existing `slides.ready()` line only, not a second.
- [ ] **Step 4: Run again; expect PASS.**
- [ ] **Step 5: Commit** "Say on Status when Arial is missing, as the brand's own check finds".

### Task 14: Blog Studio passes the chosen voice to the brand

Spec items 14 and 17.7.

**Files:**
- Modify: `studios/blog/skills/blog-studio/scripts/studio_brand/brand.py:279 export`
  (`voice_profile: Path | None = None`, passed as `--voice-profile`)
- Modify: `studios/blog/skills/blog-studio/scripts/brand_skill.py:345 snapshot`
  (`voice: dict | None = None`)
- Modify: `studios/blog/skills/blog-studio/scripts/blog_runner.py:1014` (pass the pinned
  voice) and `studio.py` (new `voice_handoff(root, profile_id, revision) -> dict`)
- Modify: `studios/blog/skills/blog-studio/references/brand-handoff.md` only if its
  wording no longer matches
- Test: `studios/blog/tests/test_brand_skill.py`, `test_blog_runner.py`

**Interfaces:**
- Produces: `studio.voice_handoff(root, profile_id, revision) -> {'id', 'revision', 'guide', 'status'}`
  from the pinned revision's record and guide.
- Consumes: `studio.voice_pin(root, profile, revision)` (studio.py:243).

- [ ] **Step 1: Write the failing tests**
  - `test_brand_skill.py::test_export_passes_the_voice_profile`: the brand stand-in
    records `contract export … --voice-profile <file>`, and the file holds the four keys
    with the profile's guide and status; without a voice, no `--voice-profile`.
  - `test_blog_runner.py::test_run_with_a_voice_exports_it_to_the_brand`: a run with a
    pinned profile revision snapshots the brand with that voice; a tone-only run passes
    none; a provisional profile stays `provisional` in the file.
  - `test_brand_refusal_of_a_profile_is_shown`: the brand stand-in refuses with "Portable
    voice needs id, guide and explicit provisional|confirmed status"; the run start fails
    with that sentence and makes no blog folder.
- [ ] **Step 2: Run** `cd studios/blog/tests && HOME=$TMPDIR/h python3 -m unittest test_brand_skill test_blog_runner -v`;
  expect FAIL.
- [ ] **Step 3: Implement.** Write the profile file inside `snapshot`'s temporary folder,
  mode 0600, and never keep it.
- [ ] **Step 4: Run again; expect PASS**, then `ruff format --check .`, `ruff check .`,
  `python3 scripts/measure_guidance.py --check` in `studios/blog`.
- [ ] **Step 5: Commit** "Hand the chosen voice to the brand when a blog's brand is exported".

### Task 15: Bring the research up to date

Spec item 15. Built on whatever sheet asks for changes to the research after Phase 3.

**Files:**
- Modify: `core/studio_core/research_contract.py` (`Workflow.run`: `task.get('refresh')`)
- Modify: the request-changes path at the research gate in each studio: Presentation
  `research_steps.py` (`requested_changes`), Training `engine.py` near 3269
  (`step.request`), Blog `synthesis_research.py` (`requested_changes`); and each page's
  sheet for asking changes to the research (find it with
  `grep -rn "gate:research" studios/*/skills/*/scripts/desk/app.js studios/blog/skills/blog-studio/assets/management/runner.js`)
- Test: `tests/test_research_contract.py`, each studio's research test, each page test

**Interfaces:**
- Produces: `task['refresh']: bool` (not in `TASK_FIELDS`, so never copied into the
  dossier). When True the author guide is `investigate.md`, `synthesize.md` and the
  "## Refresh selected evidence" section of `synthesis-reuse.md` (cut from that heading to
  the next `## `), and the `return` line adds "Bring the evidence up to date: re-read each
  source, save new captures with the date you read them, and update what changed."
- Produces: the change request's `refresh: true`, sent by the sheet's checkbox.

- [ ] **Step 1: Write the failing tests**
  - `test_research_contract.py::test_refresh_hands_the_refresh_section`: a disposable
    runtime with a `synthesis-reuse.md` holding three sections; with `refresh` the author
    guide holds the refresh section and not the others; without it, none.
  - Each studio: a change request with `refresh: true` reaches `native()` as
    `task['refresh'] is True`; without it, False.
  - Each page test: the sheet for asking changes to the research has an unchecked "Bring
    the evidence up to date" with the line "Re-reads the sources and checks the report
    again: about as long and as costly as the research was." and sends `refresh`.
- [ ] **Step 2: Run; expect FAIL.**
- [ ] **Step 3: Implement.** Where Phase 3 shows a price for revising the research, the
  refresh line uses that price in place of "about as long and as costly as the research
  was".
- [ ] **Step 4: Run again; expect PASS.**
- [ ] **Step 5: Commit** "Let a person ask for the research to be brought up to date".

### Task 16: Docs, versions, follow-ups and the full check

Spec items 16 (Presentation), 18, and the follow-ups.

**Files:**
- Modify: `studios/presentation/docs/runner.md`, `studios/presentation/skills/presentation-studio/references/levels.md`
  (the redesign decision, word for word from the spec item 16 Presentation bullet)
- Modify: `studios/presentation/docs/runner.md`, `studios/training/docs/runner.md`,
  `studios/training/docs/how-it-works.md` (the legacy question queue: "Kept for a deck
  begun before the synthesis research contract, so that it finishes as it began. It can go
  once no workspace holds such a run."), `studios/blog/skills/blog-studio/references/modules/blog-deep-research.md`
  ("The page researches with Harness Research. `studio.py research` is the chat
  workflow's command.")
- Modify: `studios/training/docs/runner.md` and `studios/presentation/docs/runner.md`:
  the floor, delivery, the audit before review, the critic's questions, parallel previews,
  pictures, the walkthrough
- Modify: `docs/research-synthesis.md` (the handoff sentence, comparisons, refresh)
- Modify: `studios/blog/CHANGELOG.md` (Unreleased), `studios/presentation/VERSION`,
  `studios/training/VERSION` and their `guidance/manifest.json` `minimum_runtime` where
  guidance changed with a script
- Test: none new

- [ ] **Step 1: Write the docs.** Keep each studio's README for a new user; detail goes in
  `docs/`.
- [ ] **Step 2: Open the follow-up issues in the Tanzu Brand repository** (with `gh issue
  create --repo dbbaskette/tanzu-brand`), after the owner agrees, titled "Pin Harness Slides
  0.16.0 in the installer" (`scripts/lib/harness-install-sources.json` keeps 0.15.1) and
  "Name Training Studio's design session in the Slides handoff"
  (`references/harness-slides.md:121`). Link them from the pull request.
- [ ] **Step 3: Run the full check.**
  - Root: `PYTHONPATH=.:tests python3 -m unittest discover -s tests -v`.
  - Presentation: `cd studios/presentation && python3 scripts/ci/run_tests.py` and
    `python3 skills/presentation-studio/scripts/validate_package.py`.
  - Training: `cd studios/training && python3 scripts/ci/run_tests.py` and
    `python3 skills/training-studio/scripts/validate_package.py`.
  - Blog: `python3 studios/blog/scripts/ci/run_tests.py --jobs 6`, `ruff format --check .`,
    `ruff check .`, `scripts/command_reference.py --check`, `scripts/measure_guidance.py --check`,
    `node scripts/ci/check-management.cjs`.
  - Root `tests/test_ui_consistency.py`.
  - Once: `bash scripts/ci/tart-macos.sh --dry-run`, then `bash scripts/ci/tart-macos.sh`.
  - Compare any failure with a clean `git archive origin/main` export before calling it new.
- [ ] **Step 4: Commit** "Document the companions as the studios now use them".
