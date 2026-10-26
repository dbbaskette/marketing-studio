# Piece 1, workflow fixes: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** no path in Blog Studio, Presentation Studio, Training Studio or Marketing Studio's
setup loses a person's work or leaves them with nothing to do. Every sentence says what the
page does. Every Presentation Studio route is walked at every review level.

**Architecture:** small fixes in place, in each studio's runner, page and core, with no new
module except one test table. Core gains one argument: `deck_flow.stops` and
`review_policy` take the run's gate names, so a combined stop is held where the run has a
stop. Presentation shares the delivered PowerPoint file in the deck's folder. Training adds
an asked-for Google Docs check and a priced research update that reuse
`gdocs.status`, `research_view.price` and the existing research request. Blog's desk gains
the team, recovery, Google and library paths that runs already have, by reusing
`sTeamDecision`, `sTimeWords`, `sCliFailure`, `google_handoff` and `blog_library`.

**Tech Stack:** Python 3.11 standard library; plain JavaScript pages with no build step;
`unittest`; each deck studio's `tests/page_harness.js` journeys; Blog's
`check-management.cjs`; root `tests/settings_page_harness.js`.

**Spec:** `docs/superpowers/specs/2026-10-26-workflow-fixes-design.md`. Read it with this
plan. Evidence: `docs/superpowers/specs/2026-10-26-workflow-audit/`.

## Global Constraints

- Pieces are built in order (1 to 6), each merged before the next starts. Line references are at
  main cc53056: re-read every named file on the piece's own base first. Training matrix row
  numbers named here are a guide; each new row takes the next free number on that base.
- Line references are at main cc53056. Re-read every named file on this piece's base
  first, and find a control by the function named here, not by its label.
- Python 3.11 or newer, standard library only; no frontend build step.
- UI follows `docs/design/golden-gate.md`. New sheets have their submit and Cancel together.
  Forms and reading surfaces stay opaque. No layout restyling: that is piece 4.
- Full product names in code, docs and commits: Marketing Studio, Blog Studio,
  Presentation Studio, Training Studio, Harness Research, Harness Slides.
- Person-facing sentences never say "artifact", "stale" or "lineage". Presentation Studio
  names no brand (`tests/test_no_brand_named.py`).
- Research stays in Harness Research and slide building in Harness Slides. Nothing here
  judges evidence or draws a slide.
- Shared settings are written only through the studios-config file and its lock
  (`core/studio_core/studios_config.py`), changing only the leaves the form changed.
- Saved work keeps working. Stored values (gate ids, `review_policy`, `deliver.json`
  `pptx`, `research_from`, roles, tags) are read as before. New fields are optional on read.
- Tests use disposable settings (`STUDIOS_CONFIG`, `HOME`, `PRESENTATION_STUDIO_DATA`),
  workspaces, Git identities and processes, with scripted workers, the Harness Slides
  stand-in, fake gcloud and Drive transports. No provider, Google or assistant job runs.
- Training Studio: each change to status, approval, inputs or readiness adds a row to the
  numbered matrix in
  `studios/training/docs/superpowers/plans/2026-10-12-training-studio-core-pipeline.md`
  (last row 130 at cc53056) and a `test_row_NNN` test. Rows here take 131 to 136; if the
  base has moved, take the next free numbers.
- `main` is live. Guidance that needs a script change raises `minimum_runtime` in that
  studio's `guidance/manifest.json` and its `VERSION` together. Blog guidance passes
  `python3 studios/blog/scripts/measure_guidance.py --check`. Blog's manifest is read only
  by 1.x installs, so a Blog guidance line raises nothing there.
- This piece deletes nothing that piece 2 owns. Where a fix stops calling code (the
  library upload's `as_blog` branch), the code stays for piece 2.
- Commit messages are plain sentences. End each with the attribution line the session
  gives.

## Review Focus

1. A Redesign deck under Balanced stops at `gate:look`, and no Balanced deck with an outline
   stop gains a second stop. The route table in Task 3 checks every route at every level.
2. A Presentation deck delivered before this piece (`pptx: 'work/deck.pptx'`) still opens,
   downloads on its maker's computer, and says where its file is everywhere else (Task 4).
3. Training's research update and Google Docs check never run unasked, never while a step
   works, and leave approvals as the matrix rows say (Tasks 11 and 12).
4. A Training change at "Review the finished materials" keeps the first drafts approval, and
   a deck drawn again still stops at its own gate (Task 13).
5. Blog's desk take-over and stopped-start exits refuse a desk view that changed. A blog
   driven elsewhere stays read-only until it is taken (Tasks 19 and 20).

---

## Task 1: A combined stop is held where the run has a stop (core)

**Files:**
- Modify: `core/studio_core/deck_flow.py` (`stops`, new `DEFAULT_KEPT`)
- Modify: `core/studio_core/review_policy.py` (`automatic`, `ahead`)
- Test: `tests/test_deck_flow.py`, `tests/test_review_policy.py`

**Interfaces (Produces):**
- `deck_flow.stops(product, level, gate, gates=None) -> bool | None`. `gates` is every
  gate name the run has. When it is given and the level's host for a combined stop is not
  in it, the stop is held at the studio's gate for the last checkpoint of
  `FOLDED[stop]` whose gate is in `gates`. With `gates=None` nothing changes.
- `review_policy.automatic(record, product, gate, last=None, holding=(), first='outline',
  run_gates=None)` passes `run_gates` to `deck_flow.stops`.
- `review_policy.ahead(record, product, gates, last=None, first='outline',
  run_gates=None)` passes `run_gates` through. `gates` stays the gates to filter, which may
  be only those still to come.
- `deck_flow.DEFAULT_KEPT = "The brand's default look, {name}, was used: no look was
  picked in the direction review."` `DEFAULT_WORDS` is unchanged, because Training Studio
  uses it (`studios/training/runner/engine.py:1967`).

- [ ] **Step 1: Write the failing tests.**
  - `tests/test_deck_flow.py`:
    - `test_balanced_holds_the_direction_at_the_look_when_there_is_no_outline_stop`.
      `stops('presentation', 'balanced', 'gate:look', gates=('gate:classify',
      'gate:look', 'gate:build'))` is True. With `'gate:outline'` added it is False. With
      `gates=None` it is False.
    - `test_training_is_unchanged_by_the_gate_names`. For each gate in
      `GATES['training']` with `@101` and each level, the result is the same with and
      without `gates=('review:direction', 'gate:deck-outline@101', 'gate:deck-look@101',
      'gate:deck@101')`.
    - `test_the_kept_default_says_no_look_was_picked`: the `DEFAULT_KEPT` text above,
      exactly.
  - `tests/test_review_policy.py`:
    - `test_balanced_redesign_stops_at_its_look`. For a record at Balanced,
      `automatic(record, 'presentation', 'gate:look', run_gates=['gate:classify',
      'gate:look', 'gate:build'])` is False, and `ahead(record, 'presentation',
      ['gate:look', 'gate:build'], run_gates=[same])` is `['gate:look', 'gate:build']`.
    - `test_still_to_come_does_not_move_the_host`. For a Balanced scratch run with
      `run_gates=['gate:outline', 'gate:look', 'gate:build']` and only `['gate:look',
      'gate:build']` still to come, `ahead` is `['gate:build']`.
    - Extend `test_ahead_agrees_with_automatic` (`:120`) to loop over `run_gates` in
      `(None, those three sets)`.
- [ ] **Step 2: Run to fail.** `PYTHONPATH=.:tests python3 -m unittest test_deck_flow test_review_policy -v`.
- [ ] **Step 3: Implement.** In `stops`, compute `host = hosts.get(stop)`. If `gates` is
  not None and `host` is not in it, set `host` to the last gate in
  `[g for c in FOLDED.get(stop, ()) for g, k in GATES[product].items() if k == c and g in
  bases]`, where `bases` are the gate names without `@level`. Then treat that host as the
  stop. Keep the docstring's sentence and add one sentence for the fallback.
- [ ] **Step 4: Run to pass.** Same command, plus `PYTHONPATH=.:tests python3 -m unittest test_stops test_deck_contract -v`.
- [ ] **Step 5: Commit:** "Hold a combined stop at the look when a deck has no outline stop".

## Task 2: A Redesign deck under Balanced stops for its look (Presentation Studio)

**Files:**
- Modify: `studios/presentation/runner/engine.py` (a helper `_automatic(record, gate)`
  that passes `run_gates=[s.name for s in stages.steps(record)]`, used at `:983`, `:1137`,
  `:2757`; `_still_to_come` at `:3174` passes `run_gates`)
- Modify: `studios/presentation/runner/steps/look.py` (`choose_default(root, brand_skill,
  level)`; `approve` wording for a look the policy chose)
- Modify: `studios/presentation/skills/presentation-studio/scripts/desk/app.js` (`stopsFor`
  at `2886-2910`)
- Test: `studios/presentation/tests/test_review_levels.py`, `test_step_look.py`,
  `test_engine.py`

- [ ] **Step 1: Write the failing tests.**
  - `test_review_levels.py`, `test_balanced_redesign_stops_at_the_look_and_keeps_the_pick`.
    Set the level as `test_balanced_combines_direction_then_deck_and_keeps_snapshot`
    (`:85`) does. An existing deck at `redesign` waits at `gate:look` after `gate:classify`
    passes by policy. Approve with the second look. Then
    `run['gates']['gate:look']['by']` is not `'review-policy'`. `outline.json`'s approval
    note holds `Look chosen:` and `In their words:`. The next stop is `gate:build`.
  - `test_step_look.py`:
    - `test_the_default_look_outside_automatic_says_no_look_was_picked`:
      `choose_default(root, skill, 'balanced')` records `DEFAULT_KEPT` with the default's
      name, and `choose_default(root, skill, 'automatic')` records `DEFAULT_WORDS`.
    - `test_a_look_the_policy_chose_is_not_said_in_the_person_s_words`: with the picked
      look's `by == 'review-policy'`, `approve` writes `Look chosen: … Recorded: "…"` and no
      `In their words`.
  - `test_engine.py`, `test_balanced_redesign_says_it_stops_for_the_look`: the view's
    `ahead` lists `gate:look` and `gate:build` for a new Balanced Redesign deck.
- [ ] **Step 2: Run to fail.** `cd studios/presentation/tests && python3 -m unittest test_review_levels test_step_look test_engine`.
- [ ] **Step 3: Implement.** Engine: replace each direct `review_policy.automatic(record,
  'presentation', name, …)` with `self._automatic(record, name, …)`. `_look_policy` passes
  `review_policy.level(record)` to `choose_default`. `stopsFor`: under Balanced, keep
  `gate:look` when no `gate:outline` was pushed. The line then reads "Balanced: it stops
  for the look and the deck".
- [ ] **Step 4: Run to pass.** Same command, plus `test_desk`.
- [ ] **Step 5: Commit:** "Stop for the look of a Redesign deck under Balanced".

## Task 3: Every route, at every review level (Presentation Studio tests)

**Files:**
- Create: `studios/presentation/tests/route_stops.py`
- Modify: `studios/presentation/tests/runner_support.py` (`:844-847`: the `capture`
  patch returns `getattr(self, 'review_level', 'step_by_step')`)
- Modify: `studios/presentation/tests/test_flow_routes.py`
- Modify: `studios/presentation/tests/test_desk.py`

**Interfaces (Produces):**
- `route_stops.LEVELS = ('step_by_step', 'balanced', 'automatic')`
- `route_stops.STOPS: dict[str, dict[str, list[str]]]`, keyed by case and then level.
  The gates the person decides, in order:

  | Case | step_by_step | balanced | automatic |
  | --- | --- | --- | --- |
  | `scratch` | outline, look, build | outline, build | build |
  | `scratch-research` | research-plan, research, outline, look, build | outline, build | build |
  | `document-script` (research on) | classify, outline, look, build | outline, build | build |
  | `brand-only` | classify, build | build | build |
  | `polish` | classify, build | build | build |
  | `redesign` | classify, look, build | look, build | build |
  | `rework` | classify, outline, look, build | outline, build | build |
  | `selected` | classify, build | build | build |

  Each name is `gate:<name>`. The step-by-step column is today's literal lists in
  `test_flow_routes.py:111-203`.
- `route_stops.FORM = {'scratch': …, 'scratch-research': …, 'document': …, 'brand-only':
  …, 'polish': …, 'redesign': …, 'rework': …, 'selected': …}`. This is the form's line for
  each level, built from `STOPS` with the words `stopsFor` uses: "the kind of document",
  "the slides read from your deck", "the research plan", "the research", "the outline",
  "the direction (… together)", "the look" and "the deck". `document` has research off.
- `route_stops.line(case, level) -> str`, for example `line('redesign', 'balanced') ==
  'Balanced: it stops for the look and the deck'`.

- [ ] **Step 1: Write the table and the tests.**
  - `test_flow_routes.py`:
    - `RouteCase.review_level = 'step_by_step'`.
    - `delivered(path, seen, sheet=True)` asserts that `seen` equals the gates of
      `gates_of(record)` whose receipt `by` is not `'review-policy'`, and that every other
      gate's `by` is `'review-policy'`.
    - Each test method in `ScratchRouteTests`, `DocumentRouteTests.test_a_finished_script`
      and `ExistingRouteTests` asserts `route_stops.STOPS[case][self.review_level]`.
    - Add six subclasses: `BalancedScratchRouteTests`, `AutomaticScratchRouteTests`,
      `BalancedDocumentRouteTests`, `AutomaticDocumentRouteTests`,
      `BalancedExistingRouteTests` and `AutomaticExistingRouteTests`, each setting
      `review_level`.
    - Move `test_raw_material_the_studio_took_for_a_script_is_corrected` and
      `test_selected_with_a_slide_asked_for_at_the_deck` into
      `StepByStepCorrectionTests(RouteCase)`, so they run once. They decide at
      `gate:classify` and `gate:build`.
  - `test_desk.py`, `test_the_form_names_the_stops_the_runner_makes`: for each case in
    `route_stops.FORM` and each level, draw New deck as
    `test_where_this_deck_stops_is_chosen_on_the_form` (`:625`) does, with the route,
    the existing level and research, then press the level. Assert that
    `route_stops.line(case, level)` is in the snapshot text.
- [ ] **Step 2: Run.** `cd studios/presentation/tests && python3 -m unittest test_flow_routes test_desk`.
  With Tasks 1 and 2 in, every walk passes. A failure here is a real route bug: fix the
  runner, not the table, unless the spec says otherwise.
- [ ] **Step 3: Commit:** "Walk every deck route at every review level".

## Task 4: A delivered PowerPoint file reaches the team (Presentation Studio)

**Files:**
- Modify: `studios/presentation/runner/steps/deliver.py` (`upload` `:67-78`, `again` `:98`)
- Modify: `studios/presentation/runner/engine.py` (`_rendered` `:3245-3250`, the view's
  `download` `:3116`, `deliver_again` `:3437-3476`, `_brief` `:3273`)
- Modify: `studios/presentation/runner/page.py` (the download route)
- Modify: `studios/presentation/runner/decks.py` (`_where`, `index`, `:414-418`, `:458-459`)
- Modify: `studios/presentation/skills/presentation-studio/scripts/desk/app.js` (`:1398`,
  `deliveredLine`, `deliverPart`)
- Test: `studios/presentation/tests/test_step_deliver.py`, `test_engine_team.py`,
  `test_desk.py`, `test_runner_page.py`

**Interfaces (Produces):**
- `deliver.SHARED = Path('deck.pptx')`. It is committed: it sits outside
  `gitstate.IGNORED`.
- `deliver.shared_file(root) -> Path | None`: the shared delivered file, if any.
- The view's `delivered.file`: `'shared'`, `'here'` (only `work/` on this computer) or
  `'maker'` (an older delivery made elsewhere). `_brief`'s `pptx_where` takes the same
  values.
- `NOT_HERE = "This delivery's PowerPoint file is on the computer that made it. Deliver it
  again there to share it."`

- [ ] **Step 1: Write the failing tests.**
  - `test_step_deliver.py`:
    - `test_a_powerpoint_delivery_is_kept_beside_the_deck`. After `upload` with output
      `pptx`, `root / 'deck.pptx'` has the bytes of `work/deck.pptx`. `deliver.json`'s
      `pptx` is `'deck.pptx'`. `git check-ignore deck.pptx` exits 1.
    - `test_a_new_delivery_replaces_the_shared_file`: revision 2's bytes replace revision
      1's.
  - `test_engine_team.py`:
    - `test_a_teammate_downloads_the_delivered_powerpoint`. Use two clones, as the team
      tests do. The maker delivers as PowerPoint and shares. The teammate's view has
      `download` True and `delivered.file == 'shared'`, and the page's download returns
      the same bytes.
    - `test_an_older_delivery_says_where_its_file_is`. With `deliver.json` `pptx:
      'work/deck.pptx'` and no file, the view says `delivered.file == 'maker'` and
      `NOT_HERE`.
    - `test_send_to_google_slides_uses_the_shared_file`. On a computer whose `work/` has
      no deck, `deliver_again` uploads `deck.pptx` (fake Drive).
  - `test_desk.py`, `test_home_says_where_an_older_powerpoint_file_is`: a brief with
    `pptx_where: 'maker'` says "A .pptx on the computer that made it." A brief with
    `'shared'` keeps "A .pptx, to download from its own screen."
- [ ] **Step 2: Run to fail.** `cd studios/presentation/tests && python3 -m unittest test_step_deliver test_engine_team test_desk test_runner_page`.
- [ ] **Step 3: Implement.** `upload` copies the file with `shutil.copyfile` after the
  render and records `SHARED`. The commit that records the delivery includes it.
  `_rendered` and the download read `shared_file` first, then the `work/` deck.
- [ ] **Step 4: Run to pass.** Same command, plus `test_flow_routes` (its "nothing under
  work/ is tracked" assertion still holds).
- [ ] **Step 5: Commit:** "Share a delivered PowerPoint file with the team".

## Task 5: Undo only when it can be done (Presentation Studio)

**Files:**
- Modify: `studios/presentation/runner/gitstate.py` (new `can_undo` beside `undo` `:666-678`)
- Modify: `studios/presentation/runner/engine.py` (`Engine.view` `:3083-3121`: `undo`)
- Modify: `studios/presentation/skills/presentation-studio/scripts/desk/app.js` (`:5720-5722`)
- Test: `studios/presentation/tests/test_runner_gitstate.py`, `test_engine_team.py`,
  `test_desk.py`

**Interfaces (Produces):** `gitstate.can_undo(workspace, path) -> bool` checks what `undo`
needs and changes nothing: HEAD touches only this deck, HEAD is ahead of tracking, HEAD~1
exists and nothing is uncommitted. The view gets `undo: bool`.

- [ ] **Step 1: Write the failing tests.**
  - `test_runner_gitstate.py`, `test_can_undo_agrees_with_undo`. An unshared last step
    gives True, and `undo` succeeds. After sharing it gives False, and `undo` raises.
    A dirty tree gives False.
  - `test_engine_team.py`, `test_undo_is_offered_only_while_the_step_is_not_shared`.
    `view['undo']` is True before `share_soon` runs and False after.
  - `test_desk.py`, `test_undo_is_not_offered_once_the_last_step_is_shared`. With
    `undo: false`, no "Undo the last step" button. Set `undo: true` in the fixtures of
    `test_undo_names_the_last_step_with_its_time_and_cost` (`:868`) and
    `test_a_phone_keeps_one_decision_in_the_toolbar` (`:1029`).
- [ ] **Step 2: Run to fail.** `cd studios/presentation/tests && python3 -m unittest test_runner_gitstate test_engine_team test_desk`.
- [ ] **Step 3: Implement.** `undo` calls `can_undo` first and keeps `UNDO_NOT` as its
  refusal.
- [ ] **Step 4: Run to pass.** Same command.
- [ ] **Step 5: Commit:** "Offer Undo only when the last step can be undone".

## Task 6: "That’s wrong" says its price first (Presentation Studio)

**Files:**
- Modify: `studios/presentation/runner/engine.py` (new `_reclassify_price`; `_gate_view`
  near `:2788-2792` adds `gate['reclassify_price']`)
- Modify: `studios/presentation/skills/presentation-studio/scripts/desk/app.js`
  (`classifyLine` `:4516-4531`)
- Test: `studios/presentation/tests/test_engine.py`, `test_desk.py`

**Interfaces (Produces):**
- `Engine._reclassify_price(record) -> dict`: `_redo(record, 'gate:classify')`'s dict.
  When the other reading is material and the form asked for research, `says` gains
  `' ' + FIRST_RESEARCH`.
- `FIRST_RESEARCH = 'The research runs first, for the first time; this computer has no
  record of what it costs.'`

- [ ] **Step 1: Write the failing tests.**
  - `test_engine.py`, `test_the_direction_review_prices_reading_the_document_the_other_way`.
    A Balanced document deck read as a script, with research on, is at the direction
    review. `gate['reclassify_price']['says']` starts with `Drawn again: “` and ends with
    `FIRST_RESEARCH`. With research off it has no `FIRST_RESEARCH`.
  - `test_desk.py`, `test_that_s_wrong_asks_first_and_says_its_price`. Clicking "That’s
    wrong" opens a sheet titled "Read it as material to build from?", with the price text,
    "Read it again" and "Cancel". Cancel posts nothing. "Read it again" posts
    `/api/decide` with `direction_target: 'gate:classify'`. Update
    `test_the_direction_review_shows_the_verdict_and_takes_a_correction` (`test_engine.py:2347`)
    and `test_desk.py:2173` if they click once.
- [ ] **Step 2: Run to fail.** `cd studios/presentation/tests && python3 -m unittest test_engine test_desk`.
- [ ] **Step 3: Implement.** The sheet uses the page's `openSheet` with the submit and
  Cancel together. The classify stop's own chip (`:4022`) is unchanged.
- [ ] **Step 4: Run to pass.** Same command.
- [ ] **Step 5: Commit:** "Say what reading a document the other way redraws before it is sent".

## Task 7: Status says whether Google is signed in (Presentation Studio and Training Studio)

**Files:**
- Modify: `studios/presentation/skills/presentation-studio/scripts/computer.py` and
  `studios/training/skills/training-studio/scripts/computer.py` (`COMMANDS`, a new
  `google(ran, account, optional)` beside `tool`, `check`)
- Modify: Presentation `desk/app.js` (`:5061-5062`, `:5094-5095`) and
  `studios/presentation/runner/steps/existing.py` (`NOT_READY` `:78-79`)
- Test: `studios/presentation/tests/test_runner_page.py`, `test_desk.py`,
  `test_engine.py`; `studios/training/tests/test_runner_page.py`

**Interfaces (Produces):**
- `COMMANDS['gcloud-account'] = ('gcloud', 'auth', 'list', '--filter=status:ACTIVE',
  '--format=value(account)')`. It reads this computer's own gcloud settings and uses no
  network.
- The gcloud item keeps `id: 'gcloud'` and gains a fact `Signed in`: `ok` with the account,
  or `problem` with the fix "Not signed in. In a terminal, run `gcloud auth login
  --enable-gdrive-access`, then check this computer again."
- Page strings:
  - `'Google is not connected on this computer, so approving makes a PowerPoint file. Sign in to Google (Status → Check this computer says how), then choose Send to Google Slides.'`
  - `'Sign in to Google (Status → Check this computer says how) to send this deck to Google Slides later.'`
  - `NOT_READY = 'Sign in to Google first: Status → Check this computer says how. Or download the file and upload it.'`

- [ ] **Step 1: Write the failing tests.**
  - In each studio's `test_runner_page.py`, add a class `GoogleSignInTests`. It patches
    `computer.run` with a dict of results and `computer.reach` to return None.
    - `test_a_signed_in_account_is_named`: `auth list` printing `ana@example.com` gives
      the fact `Signed in` `ok` `ana@example.com`.
    - `test_no_account_says_how_to_sign_in`: an empty output gives the fix above.
    - `test_no_gcloud_asks_nothing_more`: with gcloud not found, the item is today's
      `missing` item and there is no `Signed in` fact.
  - Presentation `test_desk.py:1009`
    `test_google_slides_without_google_says_it_makes_a_powerpoint_file` asserts the new
    first string. `test_engine.py:217` asserts the new `NOT_READY`.
- [ ] **Step 2: Run to fail.** `cd studios/presentation/tests && python3 -m unittest test_runner_page test_desk test_engine`;
  `cd studios/training/tests && python3 -m unittest test_runner_page`.
- [ ] **Step 3: Implement** in both `computer.py` files the same way. Piece 2 merges them.
- [ ] **Step 4: Run to pass.** Same commands.
- [ ] **Step 5: Commit:** "Say on Status whether Google is signed in, and name the real button".

## Task 8: Questions can be added at the research stop (Presentation Studio)

**Files:**
- Modify: `studios/presentation/runner/engine.py` (the research gate's view: `room`)
- Modify: `studios/presentation/skills/presentation-studio/scripts/desk/app.js`
  (`researchPanel` `:4116-4134`; `addedPart` `:5466` takes `gate.room`)
- Test: `studios/presentation/tests/test_engine.py`, `test_desk.py`

**Interfaces (Produces):** the research gate's `room`. For a contract run it is
`worker_tools.PLAN_MOST` minus the planned questions. Otherwise it is
`min(ADDED, worker_tools.QUESTIONS - planned)`. When `room` is 0, `addedPart` says "The
plan holds 8 questions, the most it can." (using the real number).

- [ ] **Step 1: Write the failing tests.**
  - `test_engine.py`, `test_the_synthesis_research_stop_says_how_many_questions_it_takes`.
    A contract run with 5 planned questions has `room == 3`.
  - `test_desk.py`, `test_a_question_can_be_added_at_the_synthesis_research_stop`. The
    synthesis panel has "A question to add". Approve with one added question posts it in
    the marks' `add`. The sheet's price is `research_price.words`. With `room: 0` the
    panel says "The plan holds 8 questions, the most it can."
  - Keep `test_no_more_questions_are_added_than_the_runner_takes_at_once` (`:1181`) with
    the runner's `room`.
- [ ] **Step 2: Run to fail.** `cd studios/presentation/tests && python3 -m unittest test_engine test_desk test_marks`.
- [ ] **Step 3: Implement.** `add(node, addedPart(gate), reviewBar(gate))` in the synthesis
  branch, as the queue branch does at `:4146`.
- [ ] **Step 4: Run to pass.** Same command.
- [ ] **Step 5: Commit:** "Take an added question at the synthesis research stop, priced".

## Task 9: Presentation Studio copy for every level, and one name per thing

**Files:**
- Modify: `studios/presentation/skills/presentation-studio/scripts/desk/app.js`
- Modify: `studios/presentation/runner/stages.py` (`:30`; under Balanced the moved
  `gate:outline` row takes stage `look`, `steps()` `:114-125`)
- Modify: `studios/presentation/runner/engine.py` (`:2757-2760` marks the row
  `automatic: True`)
- Modify: `core/studio_core/review_policy.py` (`:101-104`, "Audit blocker: " becomes
  "Brand check: ", shared with Training Studio)
- Test: `studios/presentation/tests/test_desk.py`, `test_stages.py`, `test_engine.py`;
  `tests/test_review_policy.py`; `studios/training/tests/test_review_levels.py` where it
  quotes "Audit blocker"

**Interfaces (Produces):** each timeline row may carry `automatic: true`. `stepFacts`
(`:3700`) adds "Your decision" only without it.

- [ ] **Step 1: Write the failing tests** in `test_desk.py`, asserting each new string and
  that the old one is absent:
  - Route card and document step (`:116-118`, `:2838-2840`): "It is read first, to tell a
    finished script from material to build from."
  - Research chip (`:3129-3132`), by level:
    - step_by_step: "You approve the research plan, then the findings, before the outline
      is drafted."
    - balanced: "The research is planned and done on its own. You see what it found with
      the outline."
    - automatic: "The research is planned and done on its own. What it found is kept with
      the deck."
  - Start line (`:3185-3186`) and Set-up (`:2514`): "At each stop you see what is made so
    far."
  - Home (`:1437-1439`): "…and stops where its review level says, for your decision."
  - Every step: a row with `automatic: true` has no "Your decision".
  - Revisions: "Published as revision 1." becomes "Published on <date>." (`:5963`,
    `:6919`). "Applies to this displayed revision." becomes "Applies to the slides shown
    here." (`:4849`).
  - Google: "Deliver to Google Slides" is nowhere. `STILL_NOT_CONNECTED`'s "deliver it
    again" becomes "send it to Google Slides again".
  - Assistant: "The agent that does the drafting" becomes "The assistant that does the
    drafting". "An agent is the AI that drafts…" becomes "The assistant drafts…". "A worker
    asks:" becomes "The assistant drawing <section> asks:", falling back to "The assistant
    asks:". The "Working now" card says "Assistant jobs now".
  - Workspace: "Your assistant, workspace, brand and delivery choices apply across all
    studios."
  - We and us: "What you gave", "Confirm what you gave" (stages.py), "Approve, and it
    carries on from what you gave.", "It may tighten, split, merge or reorder content,
    then redesign.", "Say which slides and what to fix."
  - Success in a toast, not `notify()`: "Deck copied into this workspace.", "Slide feedback
    saved."
  - The plan count says "searched on the web" only for items with `search`, and "read from
    your documents" or "read from your sites" for the rest.
  - The progress bead for "Unreviewed" uses `state('working', …)`, not `late`.
  - Research finding buttons: "Ask for changes to this finding" and "Keep it as it is".
    The aria-labels say the same words. "Request changes to the research" becomes "Ask for
    changes to the research". "Send slide feedback" becomes "Ask for changes to this
    slide". "The review has nothing left to raise" becomes "The check has nothing left to
    raise".
  - `test_stages.py`, `test_balanced_puts_the_direction_review_under_the_look`: under
    Balanced the `gate:outline` row's stage is `look`.
  - `tests/test_review_policy.py`: `held` lines start "Brand check: ".
- [ ] **Step 2: Run to fail.** `cd studios/presentation/tests && python3 -m unittest test_desk test_stages test_engine`;
  `PYTHONPATH=.:tests python3 -m unittest test_review_policy`.
- [ ] **Step 3: Implement.** The research chip and the start line read `levelOf(draft)`.
  Update existing assertions of old strings in `test_desk.py`
  (`:509`, `:528`, `:1011`, `:1040`, `:1538`) in the same commit.
- [ ] **Step 4: Run to pass.** Same commands, plus `cd studios/training/tests && python3 -m unittest test_review_levels`.
- [ ] **Step 5: Commit:** "Say in Presentation Studio what each level does, with one name per thing".

## Task 10: A suite install is told how it is updated (Presentation Studio and Training Studio)

**Files:**
- Modify: `studios/presentation/runner/upkeep.py` (`:1424`) and
  `studios/training/runner/upkeep.py` (`:1349`): companion `update.offered` is False when
  `suite_managed()`
- Modify: Presentation `desk/app.js` (`updatesCard` `:6485`, Status `versionsCard`) and
  Training `desk/app.js` (`updatesCard` `:7699-7716`, `versionsBar` `:7670`,
  `versionsCard` `:7719`)
- Test: both `test_runner_upkeep.py` and both `test_desk.py`

**Interfaces (Produces):** both pages define the same constant:
`SUITE_SAYS = 'Marketing Studio installs and updates this studio. To update it, unpack a
newer Marketing Studio release and run marketing-studio update --from <the unpacked
folder> --yes.'` The command is set in `<code>`.

- [ ] **Step 1: Write the failing tests.**
  - Each `test_runner_upkeep.py`, `test_a_suite_install_offers_no_companion_update`.
    With `suite_managed` True and a newer companion, every row's `update.offered` is
    False.
  - Each `test_desk.py`, `test_a_suite_install_says_marketing_studio_updates_it`. With
    `versions.suite: 'marketing-studio'`, Home's Updates card and Status show `SUITE_SAYS`.
    There is no "Update" or "Update the skills" button, and no "Newer versions are ready
    for this computer:".
- [ ] **Step 2: Run to fail.** In each studio: `cd studios/<studio>/tests && python3 -m unittest test_runner_upkeep test_desk`.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run to pass.** Same commands.
- [ ] **Step 5: Commit:** "Tell a suite install that Marketing Studio updates it".

## Task 11: A teammate's Google Doc edits come back (Training Studio)

**Files:**
- Modify: `studios/training/runner/copies.py` (new `check`; `pull` `:188-235` returns
  `unplaced`)
- Modify: `studios/training/runner/engine.py` (new `check_copies` beside `pull_copy`
  `:3885`; the view's copies carry `remote`)
- Modify: `studios/training/runner/page.py` (`copied()` `:778-789`: action `check`)
- Modify: `studios/training/skills/training-studio/scripts/desk/app.js` (copies card; the
  pull button condition `:5573-5576`; the pulled-headings line)
- Modify: the numbered matrix (row 131)
- Test: `studios/training/tests/test_runner_copies.py`, `test_runner_page.py`, `test_desk.py`

**Interfaces (Produces):**
- `copies.check(root, google=None) -> dict[str, str]`: for each linked copy, the state
  `gdocs.status` gives (`'made'`, `'remote changed'` or `'both changed'`). It is kept in
  `record['copies']['remote']` with `checked_at`.
- `Engine.check_copies(path) -> dict` (the view). It is held by `self._held(path)` and
  refused while a dependent worker builds, as `pull_copy` is.
- `copies.pull(...)` returns `{'result', 'beside', 'unplaced': [heading, …]}`.
- Strings:
  - Button: "Look for changes in Google Docs".
  - State: "Changed in Google Docs".
  - Unplaced: "These headings were brought in but not placed in the guide's sections,
    because their hidden note was removed in the Doc: {headings}. Put them back under a
    heading, or ask for changes."
- Row 131: `| 131 | Approved file, unchanged here, its Doc edited elsewhere | Look for
  changes in Google Docs | The copy shows Changed in Google Docs and offers Bring the Doc’s
  changes in; nothing else changes until it is brought in (row 121). Covered by
  \`CheckTests.test_row_131_a_doc_edited_elsewhere_is_found_when_asked\`. |`

- [ ] **Step 1: Write the failing tests.**
  - `test_runner_copies.py`, class `CheckTests`:
    - `test_row_131_a_doc_edited_elsewhere_is_found_when_asked`. A fake transport whose
      export differs from `remote_sha256`, with the local file unchanged, gives
      `remote changed`. Then `pull` is clean: the file holds the Doc's text and is not
      approved, as row 121 says.
    - `test_nothing_asks_google_unasked`: building the view calls no transport method.
    - `test_pulled_headings_without_their_note_are_named`: `unplaced` lists the heading.
  - `test_runner_page.py`, `test_the_page_looks_for_doc_changes_when_asked`: `POST
    /api/copies {action: 'check'}` returns the view with `remote`.
  - `test_desk.py`, `test_a_doc_changed_in_google_offers_to_bring_it_in`. A view with
    `remote: {'101/document.md': 'remote changed'}` shows "Changed in Google Docs" and
    "Bring the Doc's changes in". The button "Look for changes in Google Docs" posts
    `{action: 'check'}`. A pull result with `unplaced` shows the sentence above.
- [ ] **Step 2: Run to fail.** `cd studios/training/tests && python3 -m unittest test_runner_copies test_runner_page test_desk`.
- [ ] **Step 3: Implement.** The button condition becomes `found.conflict ||
  remote[name] === 'remote changed' || remote[name] === 'both changed'`, and the problem
  string match goes. Add row 131.
- [ ] **Step 4: Run to pass.** Same command, plus `test_google`.
- [ ] **Step 5: Commit:** "Look for a teammate's Google Doc edits when asked, and bring them in cleanly".

## Task 12: A document after research is planned, and a priced research update (Training Studio)

**Files:**
- Modify: `studios/training/runner/engine.py` (`supply` `:3779-3816`, `SETTLED` `:300`,
  new `update_research`, the view's `documents`)
- Modify: `studios/training/runner/page.py` (`POST /api/documents` takes action `update`;
  `SUPPLYING` `:267`)
- Modify: `studios/training/skills/training-studio/scripts/desk/app.js` (`documentsCard`
  `:5492-5530`)
- Modify: the numbered matrix (rows 132, 133)
- Test: `studios/training/tests/test_runner_flow.py`, `test_runner_page.py`,
  `test_runner_engine.py`, `test_desk.py`

**Interfaces (Produces):**
- `record['documents']['later'] = [{'name', 'added_at'}]`.
- `Engine.supply(path, 'add', …)` after the plan is settled: allowed when `research_from`
  reads documents and no step of this training is under way. Otherwise:
  - `WORKING = 'Wait for the step in hand to finish, or pause the training, then add it.'`
  - `NO_DOCUMENTS = "This training's research does not read documents, so it takes none.
    Start a new training that reads your documents to use this one."` This replaces the
    public-web sentence (`:3791-3792`) for web-only and sites-only.
- `remove` of a later document is allowed until the update runs. `SETTLED` becomes "The
  research has read the documents already added, so they cannot be removed now. You can
  add another and update the research."
- `Engine.update_research(path) -> dict` records the research request `{'refresh': True,
  'added': [names], 'note': 'Read the documents added since: <names>.'}`. It reopens
  research as **Bring the evidence up to date** does, then empties `later`.
- The view: `documents.later` and `documents.update_price` (`research_view.price` with
  `redone` from `reviews.rewritten(root, session, decks, 'research')`).
- Strings: "Added after the research: not read yet." and the button "Update the research".
- Row 132: `| 132 | Research planned or done, research reads documents | Add a document | Kept and listed as not read yet; research, approvals and readiness unchanged. Covered by \`test_row_132_a_document_added_after_the_plan_is_kept_and_not_read\`. |`
- Row 133: `| 133 | A document added after the research | Update the research | The research request records refresh and the added names; research and everything made from it are out of date and made again under the run's level (row 128). Covered by \`test_row_133_updating_the_research_reads_the_added_documents\`. |`

- [ ] **Step 1: Write the failing tests.**
  - `test_runner_flow.py`:
    - `test_row_132_a_document_added_after_the_plan_is_kept_and_not_read`.
    - `test_row_133_updating_the_research_reads_the_added_documents`. The research task
      carries `refresh: True`, and its document list holds the new file.
    - `test_a_later_document_can_be_removed_until_the_update`.
    - `test_no_document_is_added_while_the_training_works`, with `WORKING`.
    - `test_a_web_only_training_still_takes_no_documents`, with `NO_DOCUMENTS`. Update
      `test_a_training_from_the_public_web_takes_no_documents` (`:1026`) and the
      `'cannot be changed now'` assertion at `:1067`.
  - `test_runner_engine.py`, `test_the_research_update_is_priced_before_it_is_sent`:
    `update_price.words` starts "Asking for changes runs the research again".
  - `test_desk.py`, `test_a_document_added_after_the_research_offers_a_priced_update`.
    The card shows the later document with "Added after the research: not read yet.".
    "Update the research" opens a sheet with the price and Cancel, and confirming posts
    `{action: 'update'}`.
- [ ] **Step 2: Run to fail.** `cd studios/training/tests && python3 -m unittest test_runner_flow test_runner_engine test_runner_page test_desk`.
- [ ] **Step 3: Implement.** Reuse the refresh path (`desk.py:687-693`,
  `workspace.decide` `:1072-1079`, `engine.py:3430`). Add rows 132 and 133.
- [ ] **Step 4: Run to pass.** Same command, plus `test_workspace test_runner_documents`.
- [ ] **Step 5: Commit:** "Take a document after the research is planned, and update the research when asked".

## Task 13: A change at the final review stays in the final review (Training Studio)

**Files:**
- Modify: `studios/training/runner/reviews.py` (`_request` `:343-347` takes the phase; the
  item view `:333-338` adds `returns` and `deck_again`)
- Modify: `studios/training/skills/training-studio/scripts/desk/app.js` (hint `:6325-6326`)
- Modify: the numbered matrix (row 134)
- Test: `studios/training/tests/test_review_levels.py`, `test_desk.py`

**Interfaces (Produces):**
- `_request(self, root, record, decisions, target, note, phase)`. It drops
  `decisions['direction']` only when `phase == 'direction'`.
- Hint: "If it changes, these are written again from it: {series}. They come back to this
  review." With `deck_again`, it adds " The deck is drawn again and stops for you first."
- Row 134: `| 134 | Review the finished materials, Balanced | Ask for changes to a learner guide | The first drafts approval stays; the guide and what is written from it are written again and come back to this review; a deck drawn again is accepted on its outline by the policy and stops at its own gate first. Covered by \`test_row_134_a_final_change_keeps_the_first_drafts_approval\`. |`

- [ ] **Step 1: Write the failing tests.**
  - `test_review_levels.py`, `test_row_134_a_final_change_keeps_the_first_drafts_approval`.
    A Balanced training at the final review asks for a change to the level 101 guide.
    The `direction` decision is still there. The next stops are the deck's gate, then
    the final review, and never "Review the first drafts". The deck outline's receipt
    `by` is `'review-policy'`.
  - Keep `test_final_scenario_revision_does_not_repeat_the_unchanged_direction_review`
    (`:408`) and `test_change_to_direction_regenerates_and_returns_for_review` (`:353`).
  - `test_desk.py`, `test_a_final_change_says_what_comes_back`: the hint strings above.
- [ ] **Step 2: Run to fail.** `cd studios/training/tests && python3 -m unittest test_review_levels test_desk`.
- [ ] **Step 3: Implement**, and add row 134.
- [ ] **Step 4: Run to pass.** Same command, plus `test_runner_engine`.
- [ ] **Step 5: Commit:** "Keep the first drafts approved when a finished material is changed".

## Task 14: Downloads keep the runner's file name (Training Studio)

**Files:**
- Modify: `studios/training/skills/training-studio/scripts/desk/app.js` (`downloadFile`
  `:895-916`; callers `:2123`, `:5276-5277`, `:5580-5581`, `:6309-6310`, `:8212-8213`)
- Modify: `studios/training/tests/page_harness.js`, if its fetch stand-in cannot return
  headers yet: an answer's `headers` is returned by `response.headers.get`
- Test: `studios/training/tests/test_desk.py`

**Interfaces (Produces):** `downloadFile(address, fallback)` names the file from
`Content-Disposition`'s `filename="…"`, else `fallback`. The toast says "Downloaded
{name}.". The final review's fallback is `item.file.split('/').pop()`, not `item.label`.

- [ ] **Step 1: Write the failing tests.**
  - `test_a_download_takes_the_name_the_runner_gives`: a header
    `attachment; filename="rolling-restarts-101-document.md"` gives the toast "Downloaded
    rolling-restarts-101-document.md.".
  - `test_a_final_review_download_has_its_extension`: with no header, the name ends
    `.md` or `.pptx`, never "the level 101 learner guide".
  - Update `test_every_deliverable_can_be_downloaded` (`:1927`) if its answers now carry
    headers.
- [ ] **Step 2: Run to fail.** `cd studios/training/tests && python3 -m unittest test_desk`.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run to pass.** Same command, plus `test_runner_page`.
- [ ] **Step 5: Commit:** "Save Training Studio downloads under the runner's file names".

## Task 15: A deck waiting for a picture leads with the picture (Training Studio)

**Files:**
- Modify: `studios/training/runner/engine.py` (`:2151-2152`: `_problem(…, action='asset')`;
  the label map `:1336` gains `'asset': 'Add the picture'`)
- Modify: Training `desk/app.js` (`actionSays` `:4994-5014`; the action opens the deck
  card's picture form `:5935-5966` and focuses its file field)
- Test: `studios/training/tests/test_runner_deck.py`, `test_desk.py`

**Interfaces (Produces):** the problem's `action == 'asset'`. The hint for `waits ===
'assets'` is "The deck is drawn once its pictures are here. Without one, redesign the deck
or leave it out."

- [ ] **Step 1: Write the failing tests.**
  - `test_runner_deck.py:2853` `test_visual_05_missing_asset_waits` expects `('waiting',
    'asset')`.
  - `test_desk.py`, `test_a_deck_waiting_for_a_picture_leads_with_adding_it`. The filled
    button is "Add the picture", and pressing it moves focus to the picture form's file
    field. The text holds the hint above and no "Try again re-runs".
- [ ] **Step 2: Run to fail.** `cd studios/training/tests && python3 -m unittest test_runner_deck test_desk`.
- [ ] **Step 3: Implement.** This changes no state, so it needs no matrix row.
- [ ] **Step 4: Run to pass.** Same command.
- [ ] **Step 5: Commit:** "Lead a deck's picture wait with Add the picture".

## Task 16: Runner pages never send the person to an assistant (Training Studio, core)

**Files:**
- Modify: `studios/training/runner/copies.py` (`REWORDED` `:63-66`; new `remake(root,
  name, google=None)` that calls `gdocs.unlink` and then makes the copy again)
- Modify: `studios/training/runner/engine.py` (new `remake_copy`; missing-answers `stuck`
  gains actions `new` and `delete`)
- Modify: `studios/training/runner/page.py` (`copied()`: action `remake`)
- Modify: `studios/training/runner/pipeline.py` (`DECK_LEFT`, `DECK_AGAIN` `:98-104`;
  `:1278-1279`)
- Modify: Training `desk/app.js` (`DECK_LEFT` `:200-201`; `folderCard` condition
  `:3106-3107`; `NOTICES` `:21-26`; `WHOSE.you` `:208-211`; the `status` action)
- Modify: `core/studio_core/stops.py` (`unusable` `:156-161` gives the action `status`);
  both deck studios' engines record it; both pages draw **Open Status** for it
- Modify: the numbered matrix (row 135)
- Test: `studios/training/tests/test_runner_copies.py`, `test_runner_pipeline.py`,
  `test_desk.py`; `tests/test_stops.py`; `studios/presentation/tests/test_desk.py`

**Interfaces (Produces):**
- Missing Doc: "Google could not find the Doc. It may have been deleted, or the signed-in
  account cannot open it. Make a new Google Doc from here." The button is "Make a new
  Google Doc".
- `DECK_LEFT`: "Everything but the slide deck is made. A deck cannot be made on this
  computer yet: {why} Put that right and check this computer again, or leave the deck
  out." `DECK_AGAIN` follows the same shape.
- `NOTICES` under the runner (`training.run` or the page's `runner` flag): "…Open Training
  Studio again and use the new link."
- `stops.unusable(...)` returns the same words, and callers record `action: 'status'`
  with the label "Open Status".
- `WHOSE.you`: "A scenario file written in a conversation training's folder is used as it
  is."
- Row 135: `| 135 | A copy whose Doc Google cannot find | Make a new Google Doc | The old link is removed and a new Doc is made from the file as it stands; the copy is made. Covered by \`test_row_135_a_missing_doc_is_made_again\`. |`

- [ ] **Step 1: Write the failing tests.**
  - `test_runner_copies.py`, `test_row_135_a_missing_doc_is_made_again` (fake transport).
  - `test_runner_pipeline.py`, `test_a_deck_left_sends_nobody_to_an_assistant`: neither
    deck sentence holds "assistant" or "conversation".
  - `test_desk.py`:
    - `test_a_finished_runner_training_sends_nobody_to_an_assistant`: no "Carry on with
      your assistant" when `training.run` is set. Keep `:2116` for a training with no
      `run`.
    - `test_runner_notices_name_training_studio`.
    - `test_missing_answers_offer_a_new_training`: buttons "New training" and "Delete
      this training".
  - `tests/test_stops.py:88`: the action is `status`.
  - Each deck studio's `test_desk.py`, `test_an_unusable_assistant_offers_open_status`:
    "Open Status" goes to Status.
- [ ] **Step 2: Run to fail.** `cd studios/training/tests && python3 -m unittest test_runner_copies test_runner_pipeline test_desk`;
  `PYTHONPATH=.:tests python3 -m unittest test_stops`; `cd studios/presentation/tests && python3 -m unittest test_desk`.
- [ ] **Step 3: Implement**, and add row 135.
- [ ] **Step 4: Run to pass.** Same commands, plus `test_runner_engine` in both studios.
- [ ] **Step 5: Commit:** "Give runner pages their own way on instead of an assistant".

## Task 17: Smaller Training Studio dead ends

**Files:**
- Modify: `studios/training/skills/training-studio/scripts/desk.py` (`offered()`
  `:497-514` returns `held_by: 'yoodli'` when it withholds Skip)
- Modify: Training `desk/app.js` (gate menu `:2483-2496`; the research-questions field
  `:4695`; the Stop action's sheet)
- Modify: `studios/training/runner/team.py` (bring-in `:356-358`)
- Modify: `studios/training/runner/engine.py` (`:5034-5035`, only if the test fails)
- Test: `studios/training/tests/test_desk.py`, `test_runner_team.py`, `test_runner_engine.py`

**Interfaces (Produces):**
- Yoodli line: "The brief and the practice scenarios cannot be skipped while Make
  scenarios for Yoodli is on: Yoodli uses both."
- Questions hint: "One question a line, at most 8, each up to 300 characters." Continue
  refuses with the runner's own sentence (`pipeline.py:476-477`).
- Bring-in copies the folder without its top-level `.git`, and still refuses a nested
  `.git`. The sheet adds "Its own Git history stays where it is."
- Stop sheet: title "Stop {step}?", body "Its work so far is lost. Pause lets it finish
  first.", buttons "Stop it" and "Cancel".

- [ ] **Step 1: Write the failing tests.**
  - `test_desk.py`:
    - `test_a_gate_says_why_it_cannot_be_skipped_while_yoodli_is_on`.
    - `test_research_questions_are_checked_before_start`: a 9th line, or a line of 301
      characters, keeps the form on its step with the sentence.
    - `test_stop_asks_first`: nothing is posted until "Stop it".
  - `test_runner_team.py`, `test_bring_in_leaves_the_folder_s_own_history_behind`: a
    folder with `.git/` is brought in without it. A folder with `sub/.git` is still
    refused.
  - `test_runner_engine.py`,
    `test_a_brought_in_training_with_documents_does_not_wait_for_them_again`. Write it
    first. If it passes on the base, keep it as a guard and change nothing else. If it
    fails, mark the documents done from `sources/` when they are brought in, and add row
    136: `| 136 | A conversation training brought in, its plan not started, documents in sources/ | Bring it in | Documents are marked all added with their count; research does not wait for them again. Covered by \`test_row_136_…\`. |`
- [ ] **Step 2: Run to fail.** `cd studios/training/tests && python3 -m unittest test_desk test_runner_team test_runner_engine`.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run to pass.** Same command.
- [ ] **Step 5: Commit:** "Say why a stage cannot be skipped, check questions on the form, and take a folder under Git".

## Task 18: Training Studio copy, and one name per thing

**Files:**
- Modify: Training `desk/app.js`; `studios/training/runner/engine.py` (`:304`, `:1049-1055`,
  `:3791-3792`); `studios/training/runner/pipeline.py` (new `plan_from_form(record) -> bool`,
  used by the stop count and by `engine.py:3257`); `studios/training/runner/reviews.py`
  (`:109`, `:114`, `:312`, `:403-404`); `studios/training/runner/copies.py` (`BOTH` `:183`);
  `studios/training/skills/training-studio/scripts/desk.py` (bead names `:73-76`);
  `studios/training/skills/training-studio/scripts/workspace.py` (labels `:71-84`)
- Test: `studios/training/tests/test_desk.py`, `test_review_levels.py`,
  `test_runner_copies.py`, `test_workspace.py`

- [ ] **Step 1: Write the failing tests**, asserting each new string and the old one gone:
  - `test_review_levels.py`, `test_a_documents_only_balanced_training_promises_one_stop_fewer`:
    `promised` is 2 plus the decks. Update `:86` where it counts.
  - Review level card: `reviewSays(level, planned, deck)` gives:
    - balanced: "Stops to read the research plan, then the first drafts of every level
      together, then each drawn deck, then the finished materials together." With no plan
      stop, it leaves out the research plan.
    - automatic: "Stops for each drawn deck and the finished materials. It costs more
      before you first see anything, and the spending limit still holds." With no deck it
      leaves out "each drawn deck and".
  - Briefs line: "Review the first drafts comes after research, the blueprint and the
    learner guide of each level. Briefs are written after it."
  - Invitation and adopt cards: "…and stops where its review level says, for your
    decision." The adopt sheet adds "A training brought in runs Step by step."
  - Deck cost: "A deck of this size is estimated at about $X (a fixed estimate per slide,
    not this computer's history)."
  - "Approving finishes this training." (`:6060`, `:6244`).
  - Walkthrough hint: "Choose this to see how each slide is drawn, and approve the design
    in one decision."
  - In "Review the first drafts", the look toggle is "Use the brand's default look".
  - Copies card: "A copy that is not made is listed as a limitation. A copy that is out of
    date must be sent again before the training is ready."
  - `copies.BOTH` starts with a capital letter.
  - `DELETE_SAYS`: "…It goes from this computer." For a team workspace it adds " and from
    your team's workspace".
  - The deck change hint (`:50` via `:1394-1395`): "A change to the deck writes its outline
    again and draws every slide again." followed by the price line.
  - Materials summary: "Makes: {list}." with "a slide deck only" when only the deck is
    chosen. The levels summary follows the ticks. "Depth and reference brief" becomes
    "Reference brief".
  - The names in the spec's table: beads "Research plan", "Guide", "Practice", "Index";
    "blueprint" only; "Yoodli scenarios" and "Write the Yoodli scenarios"; "Not ready to
    use yet"; "Leave the deck out"; "the first drafts review" and "the finished materials
    review"; "the deck outline" ("Pick a look for the level 101 deck before you approve the
    first drafts."); "Run by <name>" and "Run by your teammates".
- [ ] **Step 2: Run to fail.** `cd studios/training/tests && python3 -m unittest test_desk test_review_levels test_runner_copies test_workspace`.
- [ ] **Step 3: Implement.** Stored stage ids, file names and gate ids do not change. Run
  `python3 studios/training/skills/training-studio/scripts/validate_package.py` if a label
  in `workspace.py` is shared with guidance.
- [ ] **Step 4: Run to pass.** Same command, plus `test_runner_engine test_runner_flow`.
- [ ] **Step 5: Commit:** "Say in Training Studio what each level does, with one name per thing".

## Task 19: A teammate can take over a desk blog (Blog Studio)

**Files:**
- Modify: `studios/blog/skills/blog-studio/scripts/desk_jobs.py` (`view` `:1649-1717` adds
  `team` and `driver`, as `blog_runner.describe` `:2325`, `:2361-2362` builds them)
- Modify: `studios/blog/skills/blog-studio/scripts/team_workspace.py` (`action` `:385-417`:
  for `desk.on_desk(directory)`, `expected` is compared with `desk_jobs.view(...)['expected']`)
- Modify: `studios/blog/skills/blog-studio/assets/management/desk.js` (`sDeskToolbar`
  `:310-319`; read-only parts while someone else drives)
- Test: `studios/blog/tests/test_desk_team.py`; `studios/blog/scripts/ci/check-management.cjs`

**Interfaces (Produces):** the desk view's `driver: {name, here, since} | None` and `team:
bool`. The toolbar has the line "{name} · driving on another computer" with **Take over**,
"Nobody is running this blog" with **Take this blog**, or **Hand over** when it is ours.
Each calls `sTeamDecision(action, {id, expected: view.expected})`.

- [ ] **Step 1: Write the failing tests.**
  - `test_desk_team.py`:
    - `test_a_teammate_takes_over_a_desk_blog`. With two clones from `hub_fixtures`, A
      drives a desk blog. B's view has `driver.here` False. `team-takeover` with B's desk
      `expected` succeeds, and then B's `desk-save` works.
    - `test_take_over_refuses_a_desk_view_that_changed`: "This blog changed. Reload
      before changing its driver or publishing it."
    - `test_hand_over_from_the_desk`.
  - `check-management.cjs`, a new journey `deskTakeOver`. A desk view with `driver:
    {name: 'Ana', here: false}` shows "Ana · driving on another computer" and "Take
    over". Its sheet posts `/api/team-takeover` with the desk's `expected`. The parts are
    not editable before.
- [ ] **Step 2: Run to fail.** `cd studios/blog && python3 -m unittest discover -s tests -p 'test_desk_team.py' -v`;
  `node studios/blog/scripts/ci/check-management.cjs`.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run to pass.** Same commands, plus `-p 'test_shared_studios.py'`.
- [ ] **Step 5: Commit:** "Let a teammate take over a blog on the writing desk".

## Task 20: A stopped desk start has Phase 1's ways on (Blog Studio)

**Files:**
- Modify: `studios/blog/skills/blog-studio/scripts/tool_jobs.py` (`:222`, `:282` keep
  `reason` and `said` from `WorkerFailure`)
- Modify: `studios/blog/skills/blog-studio/scripts/desk_jobs.py` (new
  `stalled_detail(root, ident, start) -> dict`; `retry(root, ident, seconds=None,
  skip_research=False)` `:1186`; `_start_view` `:1291`)
- Modify: `studios/blog/skills/blog-studio/scripts/desk.py` (`ROUTES` `:1105`: `retry`
  takes optional `seconds` and `skip_research`)
- Modify: `studios/blog/skills/blog-studio/assets/management/desk.js` (`sDeskProgress`
  `:273-291`)
- Test: `studios/blog/tests/test_desk_start.py`; `check-management.cjs`

**Interfaces (Produces):**
- `stalled_detail` returns `{'problem', 'reason': 'cli'|'time-limit'|'research'|None,
  'said', 'step', 'seconds'}`. `stalled` keeps returning the problem string.
- `retry` with `seconds` runs the step with that limit, at most twice the setting, as
  run retries are. With `skip_research`, it drops `research` from the start's steps,
  records no research, and queues the next step.
- The page reuses `sTimeWords`, `sCliFailure` and the Continue without research
  confirmation from `runner.js`. It also offers **Delete this start**, using the existing
  delete sheet.

- [ ] **Step 1: Write the failing tests.**
  - `test_desk_start.py`:
    - `test_a_start_out_of_time_can_try_again_with_more_time`.
    - `test_a_research_step_that_stopped_can_continue_without_research`: the draft job
      is queued and the record says no research.
    - `test_a_cli_failure_on_a_start_keeps_what_the_assistant_said`.
    - `test_more_time_or_no_research_refuses_a_start_under_way`: "Nothing to retry:
      this start is under way or done."
  - `check-management.cjs`, a new journey `deskStartRecovery`. For each reason it shows
    "Try again with more time", "Continue without research", or "Open Status" with "What
    the assistant said", and always "Retry".
- [ ] **Step 2: Run to fail.** `cd studios/blog && python3 -m unittest discover -s tests -p 'test_desk_start.py' -v`;
  `node studios/blog/scripts/ci/check-management.cjs`.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run to pass.** Same commands, plus `-p 'test_desk_jobs.py'`.
- [ ] **Step 5: Commit:** "Give a stopped desk start more time, no research, or Status".

## Task 21: A restored desk blog opens on the desk (Blog Studio)

**Files:**
- Modify: `studios/blog/skills/blog-studio/scripts/blog_delete.py` (`restore`
  `:397-479`; `_shown` `:379` adds `on_desk`)
- Modify: `studios/blog/skills/blog-studio/scripts/management.py` (the `run` route answers
  `{'id', 'on_desk': True}` for a blog on the desk)
- Modify: `studios/blog/skills/blog-studio/scripts/blog_runner.py` (`:564` message)
- Modify: `studios/blog/skills/blog-studio/assets/management/runner.js` (`sDeletedFold`
  `:1067-1069`)
- Test: `studios/blog/tests/test_desk.py`, `test_blog_runner.py`; `check-management.cjs`

**Interfaces (Produces):** `restore` returns `on_desk`. The toast is "Restored {title}.",
and the page routes to `desk`. The `:564` message is "This blog has no step-by-step run.
Open it from Blogs."

- [ ] **Step 1: Write the failing tests.**
  - `test_desk.py`, `test_a_restored_desk_blog_opens_on_the_desk`.
  - `test_blog_runner.py`, `test_the_run_view_of_a_desk_blog_says_it_is_on_the_desk`.
  - `check-management.cjs`: extend `finishAndDelete` (`:1766`) with a desk row whose
    restore routes to the desk, with no "It stays stopped".
- [ ] **Step 2: Run to fail.** `cd studios/blog && python3 -m unittest discover -s tests -p 'test_desk.py' -v` and `-p 'test_blog_runner.py'`; the journeys.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run to pass.** Same commands.
- [ ] **Step 5: Commit:** "Open a restored desk blog on the desk".

## Task 22: A desk blog can get a Google Doc (Blog Studio)

**Files:**
- Modify: `studios/blog/skills/blog-studio/scripts/google_handoff.py` (`open_as_doc(root,
  ident, client=None, capture=None, desk=False)` `:37-49`)
- Modify: `studios/blog/skills/blog-studio/scripts/management.py` (new route
  `desk-google-open`, confirmed, with the desk's `expected`)
- Modify: `studios/blog/skills/blog-studio/assets/management/desk.js` (`sDeskToolbar`
  `:314`; `sDeskGoogleCard` `:872-874`; `sDeskReadGoogle` `:189-197`)
- Modify: `studios/blog/skills/blog-studio/references/page-tools.md` (`:49`)
- Test: `studios/blog/tests/test_google_handoff.py`; `check-management.cjs`

**Interfaces (Produces):**
- With `desk=True`, `open_as_doc` reads the item with `studio.item` and needs `DRAFT.md`.
  It does not call `blog_runner.load` or `survey`. It refuses a desk view whose `expected`
  changed, and is otherwise the same: a private Doc, `editorial.doc_link`, and the draft
  baseline.
- Toolbar **Make a Google Doc**. Its sheet says "A private Google Doc of this draft is made
  in your Drive. Later desk changes are sent to it as suggestions." with "Make the Doc"
  and "Cancel".
- Desk start: on the `:313` refusal for an `already-linked` Doc, show **Open its run**
  (`sRoute('run', found.id)`).
- `page-tools.md:49`: "**Open as a Google Doc:** on Done for an older run, or **Make a
  Google Doc** on the desk; either makes a private Doc of the draft."

- [ ] **Step 1: Write the failing tests.**
  - `test_google_handoff.py`:
    - `test_a_desk_blog_becomes_its_linked_doc_once` (fake Drive client, as
      `test_a_finished_blog_becomes_its_linked_doc_once` `:97`).
    - `test_a_desk_doc_refuses_a_changed_desk_view`.
    - `test_a_desk_doc_needs_google_signed_in`, with `NOT_SIGNED_IN`.
  - `check-management.cjs`, a new journey `deskGoogleDoc`. "Make a Google Doc" and its
    sheet text. After linking, "Google Doc ↗" shows and the Before publishing card offers
    sending suggestions. On the desk start, an `already-linked` Doc of an older run shows
    "Open its run".
- [ ] **Step 2: Run to fail.** `cd studios/blog && python3 -m unittest discover -s tests -p 'test_google_handoff.py' -v`; the journeys.
- [ ] **Step 3: Implement.** Run `python3 studios/blog/scripts/measure_guidance.py --check`.
- [ ] **Step 4: Run to pass.** Same commands, plus `-p 'test_google_suggestions.py'`.
- [ ] **Step 5: Commit:** "Make a Google Doc from a blog on the writing desk".

## Task 23: Mark as published keeps a desk blog in the team library (Blog Studio)

**Files:**
- Modify: `studios/blog/skills/blog-studio/scripts/management.py` (`schedule` route
  `:2005-2016`) or `editorial.schedule(..., desk=True)` (`editorial.py:522`): on stage
  `published`, call `blog_library.keep_written(root, record, text, kind)` with `DRAFT.md`,
  catching its failure as `blog_runner.keep_finished` does (`:1818`)
- Modify: `studios/blog/skills/blog-studio/assets/management/desk.js` (`sDeskPublish`
  `:517-521`)
- Test: `studios/blog/tests/test_team_library.py`, `test_desk.py`; `check-management.cjs`

**Interfaces (Produces):** the sheet's text adds "Its draft is kept in the team library as
a reference and an example of its kind of post. Marking it again updates that item."

- [ ] **Step 1: Write the failing tests.**
  - `test_team_library.py`:
    - `test_a_published_desk_blog_is_kept_once_and_updated_when_marked_again`.
    - `test_publishing_a_desk_blog_is_never_refused_when_the_library_cannot_take_it`.
    - `test_a_team_workspace_shares_the_published_desk_blog`.
  - Keep `test_desk.py:565` `test_a_published_desk_blog_is_finished`.
  - `check-management.cjs`: the Mark as published sheet text.
- [ ] **Step 2: Run to fail.** `cd studios/blog && python3 -m unittest discover -s tests -p 'test_team_library.py' -v`; the journeys.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run to pass.** Same commands.
- [ ] **Step 5: Commit:** "Keep a published desk blog in the team library".

## Task 24: The desk's smaller fixes (Blog Studio)

**Files:**
- Modify: `studios/blog/skills/blog-studio/assets/management/desk.js` (`DESK_TOOLS`
  `:597-605` and `:813`; `:175`; `DESK_START_STEPS` and `:87-88`, `:186`)
- Modify: `studios/blog/skills/blog-studio/assets/management/index.html` (`:43`) and
  `app.js` (`saveUpload` `:640-646`); `runner.js` (`:1100`)
- Test: `check-management.cjs`; `studios/blog/tests/test_editorial_tools.py`

**Interfaces (Produces):**
- `deskTool(key) -> [key, label, says]`. `sDeskProofView` uses `deskTool('proofread')[2]`,
  and no code indexes `DESK_TOOLS` by number.
- Paste field: `max: 200000`, hint "Up to 200,000 characters. Each ## heading starts a
  section."
- Upload: the tick reads "Then edit it on the desk". After the upload saves, the page opens
  the desk start at "What do you have?" with **A draft** and the file's text. The upload no
  longer sends `as_blog`. `runner.js:1100` reads "…or edit it on the desk."
- Start order: 1 What are you writing? 2 What do you have? 3 Sources and settings. Step 3
  shows research and Length for the `have` chosen.
- **Note: the draft path is already one screen.** Polishing or reviewing a draft
  (`have: 'draft'`) is `sDeskPolish`: no step tabs and no kind of post unless the person
  picks **Reshape to fit a kind of post**; first passes **Proofread and tighten** (default),
  **Just give feedback** (`first_pass: 'feedback'`), Reshape and Leave; tone and sources
  folded. Choosing A draft on the steps switches to it. Keep that when reordering: the new
  order is for the topic and outline paths only, and the upload's "edit it on the desk"
  lands on that screen with the file's text. The first pass's name is now "Proofread and
  tighten", not "Tighten and correct" (item 10 of the spec).

- [ ] **Step 1: Write the failing tests** in `check-management.cjs`:
  - `deskFinishing` (`:3278`): the Proofread view holds "Dashes, words that often read as
    machine-written, and repetition, checked at once with no assistant." and not "voice
    guides".
  - `deskPaste`: the field's `maxLength` is 200000, with the hint.
  - `uploadToDesk`: the upload posts without `as_blog` and lands on the desk start with A
    draft filled.
  - The desk start journeys: step 2 is "What do you have?". Choosing A draft hides the
    research ticks in step 3, and A topic shows Length.
  - `test_editorial_tools.py`: keep the `as_blog` server tests, because piece 2 deletes the
    branch.
- [ ] **Step 2: Run to fail.** `node studios/blog/scripts/ci/check-management.cjs`.
- [ ] **Step 3: Implement.** Update the desk start journeys that click by step.
- [ ] **Step 4: Run to pass.** Same command, plus `cd studios/blog && python3 -m unittest discover -s tests -p 'test_desk_start.py' -v`.
- [ ] **Step 5: Commit:** "Describe Proofread, limit the paste, start uploads on the desk, and ask what you have first".

## Task 25: Blog Studio copy, and one name per thing

**Files:**
- Modify: `studios/blog/skills/blog-studio/scripts/management.py` (`:2305`, `:2309`,
  `:2339`, `:2358`; the All blogs details `:1137-1245` for a desk blog)
- Modify: `studios/blog/skills/blog-studio/scripts/desk.py` (`:273`, `:1184`)
- Modify: `studios/blog/skills/blog-studio/assets/management/app.js` (`:126`, `:161`,
  `:384`), `runner.js` (`:65`, `:72`, `:181`, `:186`, `:200`, `:653-796`, `:919`, `:742`,
  `:969`, Tools labels `:539-560`), `desk.js` (`:5`, `:407`), `index.html` (upload roles)
- Test: `check-management.cjs`; `studios/blog/tests/test_management_ui.py`,
  `test_voice_switch.py`

- [ ] **Step 1: Write the failing tests** (journey `oneNameEach`, extended):
  - Page messages: "The page hit an unexpected problem. Reload the page; saved work is
    kept, and you can continue in chat.", "Another change on this page is still
    running…", "Blog Studio's page answers GET and POST requests only.", "This request has
    fields the page does not take.", "Reopen this page's link…", "Blog Studio's page is not
    answering. Ask Blog Studio in chat to open it again.", "This page does not publish
    your blog."
  - "Tighten and correct"; the Default voice hint; "Your documents are always read.
    Choose what else research may use." with no tick; the toast "New decks, trainings and
    blogs run step by step in chat now start at {level}."
  - Sources panel with research: "Research was read for this draft: {n} sources."
  - Desk-blog details: "On the desk" and "Open on the desk", with no "Requested stop" and
    no "Continue in chat".
  - "Pause by closing; resume it from Blogs, with Resume interview."; "Every blog";
    "Open {title}" for a stopped start.
  - Kind of post and voice guide names, as the spec's table lists. The role label is
    "Style sample: to learn a new kind of post from".
  - Tools labels: "History", "Headline and opening", "Feedback without a rewrite", "Check
    facts against sources".
- [ ] **Step 2: Run to fail.** `node studios/blog/scripts/ci/check-management.cjs`;
  `cd studios/blog && python3 -m unittest discover -s tests -p 'test_management_ui.py' -v`.
- [ ] **Step 3: Implement.** Stored roles and route names do not change.
- [ ] **Step 4: Run to pass.** Same commands, plus `-p 'test_voice_switch.py'` and
  `python3 studios/blog/scripts/measure_guidance.py --check`.
- [ ] **Step 5: Commit:** "Name each thing once in Blog Studio, and say what the desk does".

## Task 26: Marketing Studio setup has one title per step and one save

**Files:**
- Modify: `core/studio_core/setup_web/index.html` (`:30`, `:44-46`, `:64-66`, `:69`,
  `:75`, `:79`, `:109-111`), `app.js` (`:36`, `:92-94`, `:102`, the submit `:444-453`,
  `paths-form` `:498-502`)
- Modify: `marketing_studio/catalog.py` (`:6`)
- Test: `tests/test_home.py`, `tests/test_shared_setup.py`, `tests/test_research_sites.py`,
  `tests/test_ui_consistency.py`

**Interfaces (Produces):**
- In setup the large title and `#step-label` are hidden. The progress list reads "1. You
  and your assistant", "2. Your workspace", "3. Brand and delivery". Step 2's card title
  is "Your workspace".
- The installation fields are a card inside `#settings-form`, outside setup. The submit
  sends `api('shared', …)`, then `api('paths', …)` when a folder changed. A folder failure
  after a saved change says "Your shared settings were saved. The installation folders
  were not: {reason}." `#paths-form` is gone.
- Copy:
  - Sub-heading "Where new work stops". Hint adds "A blog on the writing desk has no
    stops: this sets where new decks, trainings and blogs run step by step in chat stop."
  - Share option "After each decision or applied change".
  - Brand line: "Choose the brand new work starts with. You can change it for each
    presentation or training. Blogs written step by step in chat use it too. Existing work
    keeps its saved choice."
  - The models hint adds "Blog Studio uses Main for every job."
  - Blog Studio's card: "Write blogs on one desk, from a topic, notes or a draft."
- When `product === 'Blog Studio'` and the page is a studio's own setup, the review-level
  part and "Delivery and previews" are hidden. Their values are left out of the changed
  leaves, so nothing is written for them.

- [ ] **Step 1: Write the failing tests.**
  - `tests/test_home.py`:
    - `test_a_setup_step_has_one_title`. Under node, step 1 has no "Step 1 of 3" and no
      large title, and its progress item reads "1. You and your assistant". Step 2's
      card title is "Your workspace".
    - `test_one_save_writes_settings_and_folders`. A changed name and a changed folder
      post `shared`, then `paths`, from one Save.
    - `test_a_folder_that_fails_says_the_settings_were_saved`.
  - `tests/test_shared_setup.py`:
    - `test_blog_studio_s_own_setup_asks_only_what_it_uses`: no review level, Deliver as
      or Slide previews, and the changes sent omit `review`, `output` and `render`.
    - Keep `test_saving_a_review_level_another_studio_changed_is_refused` (`:125`).
  - `tests/test_research_sites.py:415`: the hint still says "Save settings to keep the
    list".
- [ ] **Step 2: Run to fail.** `PYTHONPATH=.:tests python3 -m unittest test_home test_shared_setup test_research_sites test_ui_consistency -v`.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run to pass.** Same command, plus `test_suite_link test_suite`.
- [ ] **Step 5: Commit:** "Give each setup step one title, save Shared settings once, and say what each setting governs".

## Task 27: Docs

**Files:**
- Modify:
  - `studios/presentation/README.md` (`:3`, `:32`, `:129`), `studios/presentation/docs/runner.md`
    (`:57`, `:63`, `:227`): Balanced picks the look for Redesign; up to 8 questions; Send to
    Google Slides; a PowerPoint delivery is shared beside the deck.
  - `studios/training/docs/runner.md` (`:192`, `:347`, `:231`),
    `studios/training/docs/how-it-works.md` (`:495`): Look for changes in Google Docs; a document after research, and Update the
    research; a final change stays in the final review.
  - `docs/design/blog-workflows.md` (the start order, the upload, and Make a Google Doc);
    `studios/blog/docs/capabilities.md:45` (Mark as published keeps the library item);
    `studios/blog/docs/runner.md:362-363` and `studios/blog/docs/editorial-desk.md:64`
    (the upload).
  - `docs/shared-setup.md` (`:44`, `:120`, `:137-140`, `:150`): Where new work stops, one
    save, and Blog Studio's own setup.
  - `studios/blog/CHANGELOG.md`, under Unreleased. The deck studios keep no changelog.
- Only what this piece changed. Other stale lines are piece 2's.

- [ ] **Step 1:** Update the docs above. Run
  `python3 studios/training/skills/training-studio/scripts/validate_package.py`,
  `python3 studios/presentation/skills/presentation-studio/scripts/validate_package.py`,
  `python3 studios/blog/scripts/measure_guidance.py --check` and
  `python3 studios/blog/scripts/command_reference.py --check`.
- [ ] **Step 2: Commit:** "Document the workflow fixes".

## Task 28: The full check

- [ ] **Step 1: Run each suite once.**
  - Root: `PYTHONPATH=.:tests python3 -m unittest discover -s tests -v`.
  - Presentation: `cd studios/presentation && python3 scripts/ci/run_tests.py --jobs 4 && python3 skills/presentation-studio/scripts/validate_package.py`.
  - Training: `cd studios/training && python3 scripts/ci/run_tests.py --jobs 4 && python3 skills/training-studio/scripts/validate_package.py`.
  - Blog: `python3 studios/blog/scripts/ci/run_tests.py --jobs 6`,
    `node studios/blog/scripts/ci/check-management.cjs`, and
    `cd studios/blog && ruff format --check . && ruff check .`.
  - Prefer the shared Tart runner on macOS for the whole suite:
    `bash scripts/ci/tart-macos.sh --dry-run`, then without `--dry-run`.
  - Compare any failure with a clean `git archive origin/main` export before calling it
    pre-existing.
- [ ] **Step 2:** Check that no person-facing string added here says "artifact", "stale" or
  "lineage": `git diff origin/main -- '*.js' '*.py' '*.html' | grep -n -i -E '^\+.*(artifact|stale|lineage)'`.
  Read each hit, because code identifiers may say them.
- [ ] **Step 3: Commit** any fixes: "Fix what the full check found in the workflow fixes".
