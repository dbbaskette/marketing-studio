# Phase 2: honest copy and one vocabulary — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** every studio names each thing one way, says where a run stops and what it has
cost before that bites, and says only what the page does.

**Architecture:** two small shared pieces in `core/studio_core` (where a run stops next and
the one write of the shared review level; the words for time and money), then each studio's
form, run screen, Ask for changes sheet and copy. Stored ids, file names and saved values do
not change; only labels, sentences and two new view fields (`ahead`, `previews.pool`).

**Tech Stack:** Python 3.11 standard library; the studios' plain JavaScript pages (no build
step); `unittest`; the page harnesses (`studios/*/tests/page_harness.js`,
`studios/blog/scripts/ci/check-management.cjs`).

**Spec:** `../specs/2026-10-22-phase-2-honest-copy-design.md`

## Global Constraints

- Phases 2 to 5 are built in order, each merged before the next starts. Line references are at main
  21a216e: re-read every named file on the phase's own base first. Training matrix row numbers
  named here are a guide; each new row takes the next free number on that base.
- Python 3.11 or newer, standard library only; no frontend build step.
- Full product names: Marketing Studio, Blog Studio, Presentation Studio, Training Studio,
  Harness Slides, Harness Research, Tanzu Brand.
- Person-facing sentences never say "artifact", "stale" or "lineage".
- Shared settings are written only through the studios-config file and its adjacent lock;
  unrelated values are preserved; an edit from an outdated form is refused.
- Tests use disposable `HOME`, `STUDIOS_CONFIG`, workspaces, data roots
  (`PRESENTATION_STUDIO_DATA`, Training's helpers) and Git identities; no provider jobs.
- UI follows `docs/design/golden-gate.md`: forms and reading surfaces stay opaque; new cards
  use the existing `card`, `segmented`/`sChoice` and `chip`/`sCheck` components.
- Stored values stay: stage ids, `derived/blog-package.md`, `research` values,
  `initial_review` values, the `rehearse` gate id, `review_policy` record shape.
- Training: a change to status, approval, inputs or readiness adds a row to the
  state-transition matrix (`studios/training/docs/superpowers/plans/2026-10-20-training-workflows.md`)
  and a `row_NN`-style test.
- Guidance that needs a script change raises `minimum_runtime` in the studio's
  `guidance/manifest.json` and its `VERSION` together. Blog references stay within
  `scripts/measure_guidance.py --check`.
- The stale-level refusal is, word for word: "Another studio changed where new work stops.
  Reload the page and try again."

## Review Focus

- A studios-config file with no `review` key: the form reads Balanced and the chip's write
  must succeed with `seen='balanced'` (not refuse because the key is absent).
- An unreadable studios-config file: every form shows Step by step, the chip and Settings
  refuse with the file's own sentence, and a run still starts at its chosen level.
- A Codex run (no reported cost): the `ahead` line and every change-request price say "the
  assistant reported no cost" instead of "$0.00".
- Saved runs from before this change (Blog run without `jobs`, Presentation run with the
  `rehearse` gate, Training run whose commits listed `document`): their screens draw without
  error and say nothing false.
- A phone-width page (`max-width: 52rem`): the new Where this run stops card and the `ahead`
  line wrap without hiding the toolbar's lead action.

Each line has its test in the task that owns the code (Tasks 1, 2, 5, 9, 10).

## Run commands

- Core: `PYTHONPATH=.:tests python3 -m unittest tests/test_review_policy.py tests/test_stops.py tests/test_ui_consistency.py`
- Blog: `cd studios/blog/tests && HOME=$TMPDIR/h python3 -m unittest <file>`;
  `node studios/blog/scripts/ci/check-management.cjs`;
  `python3 studios/blog/scripts/ci/run_tests.py --jobs 6`.
- Presentation: `cd studios/presentation/tests && python3 -m unittest <file>`.
- Training: `cd studios/training/tests && python3 -m unittest <file>`.

---

## Task 1: Where a run stops next, and the one write of the shared level (core)

**Files:**
- Modify: `core/studio_core/review_policy.py` (add `effective`, `change`, `ahead`, `STALE`)
- Modify: `core/studio_core/preferences.py:158` (`save`'s guard refuses a stale `review`)
- Modify: `core/studio_core/stops.py` (add `cost`, `took`)
- Test: `tests/test_review_policy.py`, `tests/test_stops.py`, `tests/test_shared_setup.py`

**Interfaces:**
- Produces:
  - `review_policy.STALE = 'Another studio changed where new work stops. Reload the page and try again.'`
  - `review_policy.effective(values: dict) -> str`: the level a form shows from what
    `studios_config.read()` returned: `values['review']['level']` when valid, `'balanced'`
    when `review` is absent, `'step_by_step'` when it is present and invalid.
  - `review_policy.change(update, level: str, seen: str) -> dict`: checks `level`, then calls
    `update({'review': {'level': level}}, guard=g)` where `g(current)` raises
    `ValueError(STALE)` when `effective(current) != seen`. Returns what `update` returns.
  - `review_policy.ahead(record: dict, product: str, gates: list[str], last: str | None = None,
    first: str = 'outline') -> list[str]`: the gates of `gates`, in order, that `automatic`
    does not accept with nothing holding.
  - `stops.took(attempts: list[dict]) -> dict`: `{'jobs': int, 'seconds': float,
    'dollars': float | None}`; dollars only when every attempt has a number.
  - `stops.cost(seconds, dollars) -> str`: "12 minutes and about $1.40", or
    "12 minutes; the assistant reported no cost" when `dollars is None`.

- [ ] **Step 1: Write the failing tests** in `tests/test_review_policy.py`:
  - `test_effective_reads_balanced_when_absent_and_step_by_step_when_invalid`:
    `effective({})=='balanced'`, `effective({'review': {'level': 'automatic'}})=='automatic'`,
    `effective({'review': {'level': 'fast'}})=='step_by_step'`.
  - `test_change_writes_the_level_under_the_lock_and_keeps_other_values`: with
    `STUDIOS_CONFIG` in a temp dir holding `{"schema": 1, "share": "asked"}`,
    `review_policy.change(studios_config.update, 'automatic', 'balanced')` leaves
    `share == 'asked'` and `review == {'level': 'automatic'}`.
  - `test_change_refuses_a_level_another_studio_changed`: file holds
    `{"review": {"level": "step_by_step"}}`; `change(update, 'automatic', 'balanced')` raises
    `ValueError` with `STALE` and the file's bytes are unchanged.
  - `test_change_refuses_an_unreadable_file`: file holds `{`; raises `WorkspaceError` whose
    text ends with the `REFUSED` sentence; file unchanged.
  - `test_ahead_agrees_with_automatic_for_every_product_and_level`: for each of
    `review_policy.LEVELS` and products `blog` (`['outline','draft','review','package']`,
    `last='package'`), `presentation`
    (`['gate:classify','gate:research','gate:outline','gate:look','gate:build']`) and
    `training` (`['gate:research-plan','review:direction','gate:deck-outline@101',
    'gate:deck-look@101','gate:deck@101','review:final']`), assert
    `ahead(...) == [g for g in gates if not automatic(record, product, g, last=..)]`.
  - In `tests/test_shared_setup.py`, `test_saving_a_review_level_another_studio_changed_is_refused`:
    `preferences.save(config, {'review': {'level': 'automatic'}}, seen={'review':
    {'level': 'balanced'}})` against a file holding `step_by_step` raises with `STALE`.
- [ ] **Step 2:** in `tests/test_stops.py`, `test_took_and_cost_say_dollars_only_when_every_job_reported`:
  `took([{'seconds': 300, 'dollars': 0.5}, {'seconds': 420, 'dollars': 0.9}]) ==
  {'jobs': 2, 'seconds': 720, 'dollars': 1.4}`; one attempt without dollars gives
  `dollars is None`; `cost(720, 1.4) == '12 minutes and about $1.40'`;
  `cost(720, None) == '12 minutes; the assistant reported no cost'`.
- [ ] **Step 3: Run** the core command; expect failures naming the missing functions.
- [ ] **Step 4: Implement.** `ahead` loops `gates` and calls `automatic(record, product, gate,
  last=last, holding=(), first=first)`. `preferences.save`'s `guard` adds: when `'review' in
  changes` and `review_policy.effective(current) != review_policy.effective(seen)` and
  `effective(current) != changes['review']['level']`, raise `ValueError(review_policy.STALE)`.
  `stops.cost` uses `stops.lasted` and `f'about ${dollars:.2f}'`.
- [ ] **Step 5: Run** the core command; expect PASS.
- [ ] **Step 6: Commit:** "Say where a run stops next, and refuse a review level another studio changed".

## Task 2: Blog Studio — Where this run stops, on the form and in Settings

**Files:**
- Modify: `studios/blog/skills/blog-studio/scripts/studios_config.py:114` (`update(..., guard=None)`;
  call `guard(existing)` under the lock before patching)
- Modify: `studios/blog/skills/blog-studio/scripts/blog_runner.py:1166` (the form's
  `review_level`, `review_seen`, `review_default`), `:411` (options view: `review_level` via
  `review_policy.effective`)
- Modify: `studios/blog/skills/blog-studio/scripts/management.py` (route `review-level`)
- Modify: `studios/blog/skills/blog-studio/assets/management/runner.js:40-43` (`sStops`,
  `sStopsLine` → `sWhereItStops(draft)`), `:156` (Settings card), `:179`, `:1014`
- Test: `studios/blog/tests/test_blog_runner.py`, `studios/blog/tests/test_shared_studios.py`,
  `studios/blog/scripts/ci/check-management.cjs`

**Interfaces:**
- Consumes: `review_policy.change`, `review_policy.effective`, `review_policy.STALE` (Task 1).
- Produces: start payload fields `review_level` (one of `LEVELS`), `review_seen`,
  `review_default` (bool); management route `review-level` taking
  `{'level': str, 'seen': str}` and answering the options view; JS `sWhereItStops(draft)`
  returning the card node.

- [ ] **Step 1: Failing tests** in `test_blog_runner.py`:
  - `test_a_blog_keeps_the_level_its_form_chose`: shared file Balanced; start with
    `review_level='step_by_step', review_seen='balanced'`; the run's
    `review_policy.level(run) == 'step_by_step'`; the shared file still Balanced.
  - `test_the_default_is_written_only_with_the_chip_and_refused_when_stale`: with
    `review_default=True` the file becomes `step_by_step`; with the file changed to
    `automatic` first, the start raises `STALE` and no blog folder is made.
  - `test_review_level_route_saves_and_refuses`: `review-level` with `seen` matching writes;
    mismatched raises `STALE`; unknown level raises "Choose Balanced, Automatic draft, or
    Step by step."
  - In `test_shared_studios.py`, `test_update_guard_sees_the_file_under_the_lock`.
- [ ] **Step 2: Failing page journeys** in `check-management.cjs`, a journey "where this run
  stops": the last form step has a card titled `Where this run stops` with three segments
  `Balanced`, `Automatic draft`, `Step by step`; pressing `Step by step` changes the line to
  `Step by step: it stops for the outline, the draft, the review and the handoff`; the start
  POST body has `review_level:'step_by_step'`, `review_seen:'balanced'`,
  `review_default:false`; no anchor on the page has an `href` starting `/onboarding/`
  except Settings' "Change shared settings"; Settings shows `Where new work stops` and
  saving posts `review-level`. Update the existing assertions at lines 1107, 1137, 1139,
  1336, 2101, 2113, 2123 for "the handoff" (Task 7 owns the word; land the assertion change
  here with the card).
- [ ] **Step 3: Run** both; expect failures.
- [ ] **Step 4: Implement.** Replace `sStopsLine` with the card (`sCard('Where this run
  stops', sChoice('Where this run stops', LEVEL_CHOICES, draft, 'review_level', …),
  sNode('p','quiet stops-line', sStops(draft)), sCheck('review-default', 'Use this for new
  work in every studio', draft, 'review_default', 'Saved when the blog starts.'))`).
  `sStops` reads `draft.review_level`. Delete the `/onboarding/` anchor in the card.
  Settings gets `sCard('Where new work stops', …)` that posts `review-level` at once and
  shows the refusal in its problem line.
- [ ] **Step 5: Run** both; expect PASS.
- [ ] **Step 6: Commit:** "Choose where a blog stops on its own form, and in Settings".

## Task 3: Presentation Studio — Where this run stops, and the stops named right

**Files:**
- Modify: `studios/presentation/runner/engine.py:715-760` (`start`: form `review_level`,
  `review_seen`, `review_default`), `runner/decks.py` (`check_form` accepts the three fields)
- Modify: `studios/presentation/runner/page.py:107` (`/api/review-level` in `WRITES`) and its
  handler; `runner/setup.py:151` (`review_level` from `effective`)
- Modify: `studios/presentation/runner/stages.py:52` (`gate:look` label `Choose the look`,
  doing `Waiting for you to choose the look`)
- Modify: `studios/presentation/skills/presentation-studio/scripts/desk/app.js:69`
  (`['look','Look']`), `:2844-2866` (`stopsFor`, `stopsLine` → `whereItStops(draft)`), the
  Settings screen
- Test: `studios/presentation/tests/test_engine.py`, `test_runner_setup.py`, `test_stages.py`,
  `test_desk.py`, `test_page_app.py`

**Interfaces:**
- Consumes: Task 1.
- Produces: deck form fields `review_level`, `review_seen`, `review_default`; route
  `POST /api/review-level {level, seen}` → `setup.describe(engine)`; JS `whereItStops(draft)`.

- [ ] **Step 1: Failing tests:**
  - `test_engine.py::test_a_deck_keeps_the_level_its_form_chose` and
    `::test_the_shared_default_is_written_only_with_the_chip_and_refused_when_stale` (as Task 2,
    `review_policy.capture` not patched; disposable `STUDIOS_CONFIG`).
  - `test_runner_setup.py::test_review_level_route_saves_and_refuses_a_stale_level`.
  - `test_stages.py::test_the_look_stop_is_named_choose_the_look`: `BY_NAME['gate:look'].label
    == 'Choose the look'`.
  - `test_desk.py::test_where_this_deck_stops_is_chosen_on_the_form`: the card, three
    segments; under Balanced the line reads `Balanced: it stops for the direction (the
    research, the outline and the look together) and the deck`; under Step by step on the
    scratch route with research it reads `Step by step: it stops for the research plan, the
    research, the outline, the look and the deck`; the timeline stage reads `Look`; no
    `/onboarding/` link on the form; the POST body carries the three fields.
  - `test_page_app.py` stays green with `/api/review-level` (every change sent is one the
    server takes).
- [ ] **Step 2: Run** them; expect failures.
- [ ] **Step 3: Implement.** In `stopsFor`, gate words: `gate:look` → `'the look'`; under
  Balanced `gate:outline` → `'the direction (the research, the outline and the look
  together)'`. Settings gets the **Where new work stops** card.
- [ ] **Step 4: Run**; expect PASS.
- [ ] **Step 5: Commit:** "Choose where a deck stops on its own form, and call its look stop Look".

## Task 4: Training Studio — Where this training stops, counted right

**Files:**
- Modify: `studios/training/runner/engine.py:960-971` (`review_default`), `runner/pipeline.py:472`
  (accept `review_default`), `runner/page.py:176` (`/api/review-level`), `runner/setup.py:126`
- Modify: `studios/training/skills/training-studio/scripts/desk/app.js:4192` (`gatesFor`),
  `:4341` (`reviewLevelCard` → "Where this training stops" with the chip), `:4372-4399`
  (`startStep`: drop the Change link; three stops a deck), `:4415` (drop the shared
  sentence), the Settings screen
- Modify: `studios/training/docs/superpowers/plans/2026-10-20-training-workflows.md` (matrix rows)
- Test: `studios/training/tests/test_desk.py:3933,5161,5216`, `test_runner_engine.py`,
  `test_review_levels.py`, `test_workspace.py`

**Interfaces:**
- Consumes: Task 1.
- Produces: form field `review_default`; route `POST /api/review-level`.

- [ ] **Step 1: Failing tests:**
  - `test_desk.py`: change `twice` to `'A deck adds three stops per level: its outline, its
    look and the deck.'`; `test_where_this_training_stops_is_on_the_form`: card title
    `Where this training stops`, chip `Use this for new work in every studio`, no
    `/onboarding/` link, and the text `The review preference is shared with Marketing Studio`
    absent; with levels 101 and 201, Learner guide and Reference brief, and a PowerPoint
    deck under Step by step, the line says `at least 14 decisions` (2 + (1 + 2) × 2 = 8 for
    research and materials, plus 3 deck stops × 2 levels = 6).
  - `test_runner_engine.py::test_the_shared_default_is_written_only_with_the_chip`.
  - `test_workspace.py::row_NN_where_this_training_stops` (next free row number): form with
    `review_level` different from the shared → run keeps it; with `review_default` → file
    written; stale → refused, no folder.
- [ ] **Step 2: Run**; expect failures.
- [ ] **Step 3: Implement.** `gatesFor` adds `3 * levels` when `DECKS[draft.deck][0]`.
  Add two matrix rows: "Where this training stops chosen on the form | Not started | Run keeps
  the chosen level; shared level unchanged | row_NN" and "Use this for new work in every
  studio | Not started | Shared level written under the lock, or refused when stale; nothing
  made | row_NN".
- [ ] **Step 4: Run**; expect PASS.
- [ ] **Step 5: Commit:** "Choose where a training stops on its form, and count three stops a deck".

## Task 5: Next stop, steps left and cost on every run

**Files:**
- Modify: `studios/blog/skills/blog-studio/scripts/blog_runner.py:1928` (wrap `self.worker`
  in `blog_worker.metered()`; append `{'stage', 'seconds', 'tokens', 'dollars'}` to
  `run['jobs']`), `:836` (view `ahead`)
- Modify: `studios/blog/skills/blog-studio/assets/management/runner.js:42` (`sRunStops` →
  `sAhead(found)`), `:227` (drop "cost is not tracked for a CLI account")
- Modify: `studios/presentation/runner/engine.py:2828-2853` (view `ahead`), desk `app.js`
  (line under the beads)
- Modify: `studios/training/runner/engine.py:4198-4213` (view `ahead`), desk `app.js`
- Test: `studios/blog/tests/test_run_recovery.py` (metering), `test_blog_runner.py`,
  `check-management.cjs`; `studios/presentation/tests/test_engine.py`, `test_desk.py`;
  `studios/training/tests/test_runner_engine.py`, `test_desk.py`

**Interfaces:**
- Consumes: `review_policy.ahead`, `stops.took`, `stops.cost` (Task 1).
- Produces: every run view has `ahead = {'steps_left': int, 'next_stop': str | None,
  'seconds': float, 'dollars': float | None}`; `next_stop` is the label of the first gate
  `review_policy.ahead` returns among the steps not done. JS `aheadLine(run)` (deck studios)
  and `sAhead(found)` (Blog) render "4 steps left · Next stop: the outline · So far 12
  minutes and about $1.40".

- [ ] **Step 1: Failing tests:**
  - Blog `test_run_recovery.py::test_every_stage_job_is_metered`: with the scripted CLI that
    reports `total_cost_usd: 0.42`, after the outline job `run['jobs'][-1]` has
    `stage='outline'`, `dollars=0.42`, `seconds>0`; a Codex-scripted job has `dollars None`.
  - Blog `test_blog_runner.py::test_the_view_says_steps_left_and_the_next_stop`: Balanced,
    write mode, nothing approved: `ahead['steps_left']==4`,
    `ahead['next_stop']=='Outline'`.
  - Presentation `test_engine.py::test_the_view_says_steps_left_the_next_stop_and_spent`:
    Balanced scratch deck after research: `next_stop == 'Review the direction'`; dollars sum
    of attempts; one attempt without dollars → `None`.
  - Training `test_runner_engine.py::test_the_view_says_steps_left_the_next_stop_and_spent`.
  - Each page test asserts the line text, and for a Codex run `So far 3 minutes; the
    assistant reported no cost`. Blog asserts `cost is not tracked` is absent. One journey
    per studio at 375 px width asserts the toolbar's lead action is still visible.
  - Review Focus: a saved Blog run with no `jobs` key renders `So far` omitted, no error.
- [ ] **Step 2: Run**; expect failures.
- [ ] **Step 3: Implement.** Server side: `ahead` from the run's remaining steps; seconds and
  dollars through `stops.took` over `run['jobs']` (Blog) or `attempts(record)` (deck
  studios). Page: one `p.quiet.ahead-line` under the beads; no new CSS colour.
- [ ] **Step 4: Run**; expect PASS.
- [ ] **Step 5: Commit:** "Say on every run how many steps are left, where it next stops, and what it has cost".

## Task 6: The price of a change, in its sheet

**Files:**
- Modify: `studios/blog/skills/blog-studio/assets/management/runner.js:263` (`sChanges`),
  `blog_runner.py` (view `redo[stage] = {'stages': [...], 'seconds', 'dollars'}`)
- Modify: `studios/presentation/skills/presentation-studio/scripts/desk/app.js:1255-1262`
  (`noteSheet`: the whole-deck sentence also at `gate:build`), `runner/engine.py` (view
  `redo`)
- Modify: `studios/training/runner/engine.py` (view `redo` per gate and per review item),
  desk `app.js` (the changes sheet and the combined review's per-item note)
- Test: `check-management.cjs`; Presentation `test_desk.py`, `test_engine.py`; Training
  `test_desk.py`, `test_runner_engine.py`

**Interfaces:**
- Consumes: `stops.took`, `stops.cost`.
- Produces: view `redo` for the gate shown: `{'steps': int, 'names': [str], 'seconds': float
  | None, 'dollars': float | None}` from the attempts of the steps `reopen`/`rewritten` would
  run again. Sheet sentence: "Drawn again: the outline and every step after it, 6 steps. Last
  time they took 22 minutes and about $3.10." or "…; this computer has no record of what they
  cost."

- [ ] **Step 1: Failing tests:**
  - Presentation `test_desk.py::test_asking_for_changes_at_the_deck_stop_with_nothing_marked_says_the_whole_deck_is_drawn_again`:
    sheet text includes `No slides marked: the whole deck is drawn again (about $7.20 and 18
    minutes, as the last build took).`
  - Presentation `test_engine.py::test_redo_counts_the_steps_reopen_runs_again`: at
    `gate:outline`, `redo['names'][0] == 'Draft the outline'`, `steps` equals
    `len(stages.reopen(...))` steps not done.
  - Blog journey "change priced": at the draft gate the sheet says `Drawn again: the draft and
    every step after it, 3 steps.`
  - Training `test_desk.py::test_a_change_request_says_what_it_writes_again`.
  - The research gate's sheet text is unchanged (Phase 3 owns it).
- [ ] **Step 2: Run**; expect failures.
- [ ] **Step 3: Implement**; reuse `stages.reopen` (Presentation), `reviews.rewritten`
  (Training), the pipeline slice after the stage (Blog). Never start anything to compute it.
- [ ] **Step 4: Run**; expect PASS.
- [ ] **Step 5: Commit:** "Say what a change request draws again, and what that took last time".

## Task 7: One vocabulary in Blog Studio

**Files:**
- Modify: `studios/blog/skills/blog-studio/scripts/blog_runner.py:63` (`'Handoff'`), `:1001`,
  `:1003`, `:1062` (refusals say "handoff")
- Modify: `studios/blog/skills/blog-studio/assets/management/runner.js:8`
  (`package:'the handoff'`), `:9` (`package:'Writing the handoff'`), `:224`
  (`'Record in team repository'`), `:161`, `:181`, `:397`, `:1014` (research wording),
  `:626` (`'Retire this kind of post'`), `:647`, `:900`, `:968` (role words)
- Modify: `studios/blog/README.md:71`, `:93`; `docs/runner.md:204,209`;
  `skills/blog-studio/references/guided-runs.md:80,127`
- Test: `check-management.cjs`, `test_blog_runner.py`, `test_management_ui.py`

**Interfaces:**
- Produces: JS `RESEARCH_CHOICES = [['none','No research'],['supplied-only','Only what you
  supply'],['web-allowed','What you supply and the public web']]`, used by all three Blog
  research selects; the existing-draft form keeps `none` as `No new research (use saved
  evidence)`.

- [ ] **Step 1: Failing tests:** journeys assert `Handoff` as the stage bead name, the stops
  line `… and the handoff`, `Record in team repository` on a finished team blog (and
  `Publish revision` absent), the three research labels in Settings, new blog and from
  files (`Also research the public web` chip, hint `Off: only what you supply. On: what you
  supply and the public web, before the outline.`), `Example of the kind of post` as the
  one example label (`Examples of the kind of post` and `examples of a kind of writing`
  absent), `Retire this kind of post`. `test_blog_runner.py::test_stage_labels`:
  `STAGES['package'][0] == 'Handoff'`; a saved run's view shows `Handoff`.
- [ ] **Step 2: Run**; expect failures.
- [ ] **Step 3: Implement**; README step 2 lists: Polish a document, Write from a brief, Use
  my outline, Explore ideas, New blog from my files, Interview me.
- [ ] **Step 4: Run**, plus `python3 studios/blog/scripts/measure_guidance.py --check` and
  `python3 studios/blog/scripts/command_reference.py --check`; expect PASS.
- [ ] **Step 5: Commit:** "Give each thing in Blog Studio one name".

## Task 8: One vocabulary in the deck studios

**Files:**
- Modify: `studios/presentation/skills/presentation-studio/scripts/desk/app.js:2873`
  (`'Research the public web first'`), `:2932-2935` (first-draft chip and hint), `:4412`,
  `:4414`, `:4491-4498`, `:4633-4634`, `:5230` (first-draft words), `:160` (pool sentence)
- Modify: `studios/presentation/runner/decks.py:146,148`, `runner/steps/deliver.py:44`
  (`' — first draft, not checked'`), `runner/setup.py:152` (`previews.pool`)
- Modify: `studios/training/skills/training-studio/scripts/desk/app.js:177`
  (`SOURCES` labels), `:214`, `:3371` (pool sentences), `runner/setup.py` (`previews.pool`)
- Test: Presentation `test_desk.py`, `test_decks.py`, `test_step_deliver.py`,
  `test_runner_setup.py`; Training `test_desk.py`, `test_runner_setup`-equivalent in
  `test_runner_studio.py`

**Interfaces:**
- Produces: setup view `previews.pool: bool` = the slides tool `has('google-preview-pool')`.

- [ ] **Step 1: Failing tests** asserting, and asserting the old words absent:
  - Presentation chip `See the first draft before the deck is checked`, hint `It is still
    built and rendered. The check and its repairs run when you ask.`; state `First draft,
    not checked`; button `Use this first draft`; action `Check the deck`; delivered card
    `Delivered: first draft, not checked`; refusal `Choose a checked deck, or the first draft
    before the check.`; deliver title suffix ` — first draft, not checked`.
  - Training sources `The public web only`, `Only what you supply`, `What you supply and the
    public web`.
  - With `previews.pool` true, both studios say `Google Drive: previews are drawn in a few
    shared presentations named “Preview: …” in your Drive, reused by every deck. <Studio>
    never deletes them.`; with false, today's sentence.
- [ ] **Step 2: Run**; expect failures.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run**; expect PASS; run `test_no_brand_named.py`.
- [ ] **Step 5: Commit:** "Give the first draft, the research choice and the preview pool one name in the deck studios".

## Task 9: Training Studio — the first drafts, its sheet, and money that adds up

**Files:**
- Modify: `studios/training/runner/reviews.py:99` (`'Review the first drafts'`), `:137`
  (`materials` leaves out `PREPARED`), `engine.py:301` (`REVIEW_NAMES['direction'] = 'first
  drafts review'`), `engine.py:3199` (no path in the sentence; view `objections_file`),
  `engine.py:4213` (`spent.stops_at = limit + cleared`)
- Modify: desk `app.js:4381`, `:4393` (stops line and lede), `:5653-5673` (`commitsSays`),
  `:767` (`stops at` from `spent.stops_at`), the research stop card (**Read every objection**)
- Modify: the matrix (`2026-10-20-training-workflows.md`)
- Test: `test_review_levels.py`, `test_runner_engine.py`, `test_desk.py`, `test_workspace.py`

**Interfaces:**
- Produces: `reviews.commits(...)['materials']` holds only stages not in `PREPARED`;
  `spent.stops_at: float | None`; view `research.objections_file = 'reviews/research.md'` when
  the stop kept one.

- [ ] **Step 1: Failing tests:**
  - `test_review_levels.py::test_the_first_drafts_sheet_lists_only_what_approving_writes`:
    with guide, brief and scenarios chosen, `commits['materials'] == ['scenario']`.
  - `test_desk.py`: the sheet says `Approving the first drafts writes the practice scenarios
    for each of the 2 levels, and the deck is then drawn: estimated at about $7.20 and 40
    minutes of agent time for a deck of this size (a fixed estimate, not this computer's
    history). It spends from the same limit as the rest of the training.`; with only guide
    and brief: `Nothing more is written for the levels: approving carries on to the deck.`;
    the step and stops line say `Review the first drafts`; `direction review` absent.
  - `test_desk.py`: after Carry on (`cleared: 20`), the now-line says `stops at $40.00`.
  - `test_desk.py`: the research stop shows `Read every objection`, opening
    `reviews/research.md` through `/api/file`; the stop text has no `reviews/research.md`.
  - Review Focus: a saved run whose review payload lists `document` in `materials` still
    renders (the page filters `PREPARED` names too).
  - `test_workspace.py::row_NN_first_drafts_approval` and the matrix row "Approve the first
    drafts | Waiting for the first drafts | Only scenarios, Yoodli and the deck are started;
    the sheet listed only those | row_NN".
- [ ] **Step 2: Run**; expect failures.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run**; expect PASS; `python3 studios/training/skills/training-studio/scripts/validate_package.py`.
- [ ] **Step 5: Commit:** "Call Training Studio's first stop the first drafts, list only what approving writes, and say the limit it stops at".

## Task 10: Presentation Studio — copy that says what the deck does

**Files:**
- Modify: `studios/presentation/runner/stages.py` and desk `app.js:70,3384-3392,3444` (no
  Rehearse row; `STAGES` without `rehearse`; the gate stays in `PIPELINE`)
- Modify: desk `app.js:3755` and `:5229` (Approve reads `Take it as <kind>` while **That’s
  wrong** is on), `:5238` (no Ask for changes at `gate:classify` on the existing route;
  gate line `To read another deck, stop this one and start a new deck from it.`)
- Modify: `runner/engine.py:735` (refuse a document Google link without Google sign-in),
  `runner/steps/existing.py:78` (`NOT_READY = 'Sign in to Google on Status, under Check this
  computer, or download the file and upload it.'`)
- Modify: desk Options and the deck stop (`Google is not connected on this computer, so
  approving makes a PowerPoint file. Sign in on Status and Deliver to Google Slides
  afterwards.`), from setup `google_ready`
- Modify: desk `app.js:4420` (no render hash), `:4469-4474` (receipts and timing in a closed
  `Details for troubleshooting` disclosure), `runner/engine.py:1069` (`The runner could not
  go on: <message>.`; class name logged only)
- Modify: desk `deckActions` (`:5229-5240`): pass the gate's problem line to `decide`
- Test: Presentation `test_desk.py`, `test_engine.py`, `test_stages.py`,
  `test_step_existing.py`, `test_runner_page.py`

- [ ] **Step 1: Failing tests:**
  - `test_desk.py`: no `Rehearse with Yoodli` and no `Coming later` in any deck's timeline;
    with **That’s wrong** pressed the toolbar's first action reads `Take it as raw
    material` (fixture verdict `spec`); the existing route's classify stop has no `Ask for
    changes` and shows the gate line; a Google-not-ready setup with Google Slides chosen
    shows the PowerPoint sentence on the form and at the deck stop; no `Render ` + hex on the
    progress card; `Recent model jobs` sits inside a closed `Details for troubleshooting`;
    a refused Approve puts its message in `#gate-problem` and focuses it, not the toast.
  - `test_engine.py::test_a_google_doc_document_needs_google_before_the_deck_is_made`: no
    folder, refusal equals `NOT_READY`.
  - `test_engine.py::test_an_unexpected_failure_says_its_message_without_its_class`:
    problem text `The runner could not go on: boom.`; `ValueError` absent from the view.
  - `test_stages.py::test_a_saved_deck_with_the_rehearse_gate_still_surveys` (Review Focus).
- [ ] **Step 2: Run**; expect failures.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run**; expect PASS; `test_no_brand_named.py`.
- [ ] **Step 5: Commit:** "Say only what a deck does: no rehearsal placeholder, Google checked at the form, and refusals beside the gate".

## Task 11: Blog Studio — copy that says what the blog does

**Files:**
- Modify: `studios/blog/skills/blog-studio/assets/management/runner.js:179` (Ready to start
  research sentence), `:181` (tone hint), `:254` (gate ledes), `:263` (Ask for changes,
  sent), the Ask for changes sheet (one sentence of what it does)
- Test: `check-management.cjs`

- [ ] **Step 1: Failing journeys** asserting, and the old words absent:
  - Ready to start: `No new research.`; `Research reads only the 2 sources you selected.`;
    `Research reads your selected sources and the public web.`; supplied-only with nothing
    selected: `No research runs: no source is selected.` (`Research uses only the sources you
    allow` absent).
  - Draft gate lede `Read the draft. Use it to go on, or ask for changes.`; review lede
    `Read the review. Its findings go to the handoff; to act on one, ask for changes to the
    draft.` (`polish the wording` and `return to the manuscript` absent).
  - Sent under Step by step at the draft: `Your changes are noted. The next draft comes back
    for your review.`; under Balanced at the review stage: `Your changes are noted. The review
    is written again and the run goes on to the handoff, where you see it.`
  - The sheet says `Ask for changes writes this stage again with your words.`
  - Tone hint `With a voice chosen, the usual tone is left out; a tone you type here is
    added as a nudge.`
- [ ] **Step 2: Run**; expect failures.
- [ ] **Step 3: Implement**; the sent sentence reads `found.ahead.next_stop` (Task 5) and the
  run's level through the same `sStopWords` rule.
- [ ] **Step 4: Run**; expect PASS.
- [ ] **Step 5: Commit:** "Say only what a blog's form and gates do".

## Task 12: Docs

**Files:**
- Modify: `studios/blog/README.md`, `studios/blog/docs/runner.md`,
  `studios/blog/skills/blog-studio/references/guided-runs.md`, `studios/blog/CHANGELOG.md`
  (Unreleased)
- Modify: `studios/presentation/README.md`, `studios/presentation/docs/runner.md`
- Modify: `studios/training/README.md`, `studios/training/docs/runner.md:164`,
  `studios/training/docs/how-it-works.md`
- Modify: `docs/shared-setup.md` (Where this run stops; the stale-level refusal)

- [ ] Replace every old word from the spec's vocabulary table; describe the Where this run
      stops card, the chip, Settings' Where new work stops, the `ahead` line and the price in
      each change sheet; Training's three stops a deck and Review the first drafts.
- [ ] `rg -n -i "export package|publish revision|direction review|Check the brand|Rehearse with Yoodli|AI critique|as-is" studios docs --glob '!**/superpowers/**' --glob '!**/upstream/**' --glob '!**/CHANGELOG.md'`
      returns nothing that a person reads.
- [ ] `measure_guidance.py --check`, each `validate_package.py`, `command_reference.py --check`.
- [ ] Commit: "Document where runs stop, what they cost, and the one name for each thing".

## Task 13: The full check

- [ ] Core: the core command plus `tests/test_shared_setup.py`.
- [ ] Blog: `python3 studios/blog/scripts/ci/run_tests.py --jobs 6`,
      `node studios/blog/scripts/ci/check-management.cjs`, `ruff format --check .`,
      `ruff check .` (from `studios/blog`).
- [ ] Presentation: `python3 studios/presentation/scripts/ci/run_tests.py`.
- [ ] Training: `python3 studios/training/scripts/ci/run_tests.py`.
- [ ] Root: `PYTHONPATH=.:tests python3 -m unittest discover -s tests`.
- [ ] Compare any failure with a clean `git archive origin/main` export run the same way;
      only failures present on both (sandbox port binds, `/tmp` writes) may remain, and they
      are named in the pull request.
- [ ] On macOS, `bash scripts/ci/tart-macos.sh --dry-run`, then the shared runner, when it is
      available.
