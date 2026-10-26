# Piece 6, the training desk (Training Studio): implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** a new training starts from a three-step sheet with its documents, runs with no
stops, and opens on one desk per training. The desk has a tab per level and a shared
Sources panel. On it the person edits the plan, guide and brief part by part, with notes,
selection edits and History. Each slide of the deck is noted, worded or redrawn on its own.
A change holds what was built from it until the person updates it (priced) or keeps it.
Sources can be added later as a priced research update, and nothing is ready until the
person marks it.

**Architecture:**
- **Desk runs.** A desk run is marked `flow: 'desk'` in `run.json` (schema 4) and in the
  session. The engine continues every gate, outline and look of a desk run with a `by:
  'desk'` receipt instead of stopping.
- **Who approved what.** The workspace tells the desk's acceptance apart from the person's
  Mark ready (`person_statuses`), and readiness and the package read that.
- **Holds.** `pipeline.survey` drops the steps of held materials.
- **New Training modules.** `runner/drafts.py` holds the desk's view, store, codec, holds and
  History. `runner/draft_jobs.py` holds the section, selection and update jobs.
  `runner/draft_finish.py` holds Finishing.
- **The page.** `skills/training-studio/scripts/desk/drafts.js` draws the desk with piece 3's
  `Drafting.kit`.
- **The deck.** Deck work reuses piece 5's slide cards and adds what Training's own deck
  runner lacks: kept sections, a focused section redraw, patch-in-place words and notes, and
  scoped updates.

**Tech Stack:** Python 3.11 standard library, plain JavaScript with no build step,
`unittest`, the Training page harness (`studios/training/tests/page_harness.js`, driven by
`tests/test_desk.py`), scripted workers (`runner_support.Workers`) and the stand-ins in
`tests/stand_ins/`.

**Spec:** `docs/superpowers/specs/2026-10-26-training-desk-design.md`. Read it with this plan,
with the audit summary `docs/superpowers/specs/2026-10-26-workflow-audit.md`, and with the
shared-desk and deck-desk specs (`2026-10-26-shared-desk-design.md`,
`2026-10-26-deck-desk-design.md`).

**Before starting:**
- Pieces 1 to 5 have merged. Re-read every file and line named here on this piece's own
  base: pieces 1 and 2 move and rename runner code.
- Where this plan names a piece 3 member (`drafting.store.Store`, `drafting.parts.Codec`,
  `drafting.record.Desk`, `drafting.versions.Versions`, `drafting.basis.land_part`,
  `land_selection`, `settle`, `drafting.prompts.*`, `drafting.guards.flags`,
  `drafting.proposals.Proposals`, `studio_core.step_times`, `Drafting.kit`), use the name
  piece 3 shipped with that meaning.
- Where it names a piece 5 member (the slide card, the per-slide version store, the words
  patch, `section_price`), use piece 5's code. Port it into Training only where piece 2 or
  piece 5 did not put it in core.

## Global Constraints

- Pieces are built in order (1 to 6), each merged before the next starts. Line references are at
  main cc53056: re-read every named file on the piece's own base first. Training matrix row
  numbers named here are a guide; each new row takes the next free number on that base.
- Python 3.11 or newer, standard library only. No frontend build step.
- Product names are written in full in code, docs and commits: Training Studio, Presentation
  Studio, Blog Studio, Marketing Studio, Harness Research, Harness Slides.
- Person-facing sentences never say "artifact", "stale" or "lineage", and never show a
  hash.
- UI follows `docs/design/golden-gate.md`:
  - one filled action per screen;
  - a `.lede`;
  - what needs the person first;
  - numbered sheet steps with submit and Cancel together;
  - controls at least 44px;
  - glass only on the toolbar, sheets, the selection bar and toasts. Cards stay opaque.
- Research stays in Harness Research and slides in Harness Slides. The studio reads their
  outputs and never judges evidence or draws slides itself.
- **Saved work keeps working.** A run without `flow: 'desk'` keeps today's gates, review
  screens and remaking, byte for byte. The engine branches only on
  `drafts.on_desk(record)`.
- **The state-transition matrix.** Every change to status, approval, inputs or readiness
  adds a row to section A7 of
  `studios/training/docs/superpowers/plans/2026-10-12-training-studio-core-pipeline.md`
  and a `test_row_NNN_*` test.
  - This plan numbers rows 131 to 154 (the spec's D1 to D24).
  - If piece 1 took rows from 131, shift every number here by the same amount.
- **Tests are disposable.** They use disposable data folders (`TRAINING_STUDIO_DATA`),
  studios-config files (`STUDIOS_CONFIG`), Git identities and workspaces, through
  `runner_support.StudioCase` and `helpers.TrainingCase`.
  - No provider job, no Google call and no network.
  - Workers are `runner_support.Workers`; slides and the brand are the stand-ins.
- **`main` is live.** Guidance that needs a script change raises `minimum_runtime` in
  `studios/training/guidance/manifest.json` and `studios/training/VERSION` together. This
  plan changes no guidance file except in Task 27; run `validate_package.py` there.
- **A format lives in four places** (`studios/training/AGENTS.md`). This plan adds no file
  format. The citation check reads the format the guidance already states.
- **Run commands.**
  - Targeted: `cd studios/training/tests && python3 -m unittest <module> -v`.
  - Whole Training Studio suite: `python3 studios/training/scripts/ci/run_tests.py`.
  - Root: `PYTHONPATH=.:tests python -m unittest`.
  - Blog Studio: `python studios/blog/scripts/ci/run_tests.py` and
    `node studios/blog/scripts/ci/check-management.cjs`, when a shared file changes.
- Commit messages are plain sentences. End each with the attribution line the session
  gives.

## Review Focus

1. A saved Balanced, Automatic draft or Step by step run must walk its gates and review
   screens exactly as before. A desk branch must never be reached without `flow: 'desk'`.
   Tests in Tasks 3, 4 and 5 (`test_saved_runs_keep_their_gates`).
2. The desk's acceptance (`by: 'desk'`) must never read as Ready, and never let the package
   step run. Only `decide(..., 'approve', by='page', seen=…)` makes a material Ready. Tests in
   Tasks 1 and 6.
3. A job result lands only while its part is unchanged. A part typed into while a rewrite
   ran keeps the typing. Tests in Task 13.
4. A held material is never remade on its own. A guide edit never redraws a deck until the
   person presses Update, and then only the slides that serve the changed sections. Tests in
   Tasks 5 and 20.
5. History for a training saved before the desk comes from its existing history files, with
   nothing migrated or written on opening. Tests in Task 11.

---

# Pull request 1: new trainings run on the desk

## Task 1: The desk in the workspace: flow, acceptance, person statuses, Keep as it is, save `via`

**Files:**
- Modify: `studios/training/skills/training-studio/scripts/workspace.py` (`init`, `save` at
  about line 553, `_approve` at about 812, `accept_policy` at about 883, `statuses`, new
  functions beside them)
- Modify: `studios/training/skills/training-studio/scripts/checks.py` (`readiness`: the
  `kept-as-is` limitation)
- Modify: `studios/training/docs/superpowers/plans/2026-10-12-training-studio-core-pipeline.md`
  (rows 132 and 139)
- Test: `studios/training/tests/test_workspace.py`

**Interfaces (Produces):**
- `workspace.FLOWS = ('desk',)`.
- `workspace.init(root, title, levels, brief_kind, deck_target, brand, yoodli, copies,
  delivery='live', walkthrough=False, approval='chat', flow=None)`. With `flow='desk'` the
  session gets `'flow': 'desk'`. Any other value is refused with "Choose a listed flow."
- `workspace.on_desk(session: dict) -> bool`: `session.get('flow') == 'desk'`.
- `workspace.VIA = ('save', 'rewrite', 'revise-all', 'selection', 'restore', 'google',
  'finishing', 'update')`.
- `workspace.save(root, name, source=None, built=False, coverage=None, edit=False, via=None,
  session_token=None) -> dict`.
  - The `save` event gains `via` and `session` when given.
  - A `via` outside `VIA` is refused with "Choose a listed kind of change." before anything
    is written.
- `workspace.accept_desk(root, name) -> dict`. It refuses:
  - when the session is not on the desk: "This training is not on the desk.";
  - for `intake`;
  - when the entry's hash is not the file's: "This document changed after its checks.
    Review it before continuing.", the same sentence as `accept_policy`.

  Otherwise it calls `_approve(root, session, name, None, 'desk', policy=True)`, and its log
  event is `continued-on-the-desk`.
- `workspace.DESK_ACCEPTED = ('desk', 'review-policy')`.
- `workspace.PERSON_MARKED = ('blueprint', 'document', 'brief', 'deck', 'scenario',
  'yoodli')`: the bases the person marks ready.
- `workspace.person_statuses(root, session) -> dict[str, str]`.
  - On a session that is not on the desk it is `statuses(root, session)` unchanged.
  - On a desk session, a name whose base (before `:` and `@`) is in `PERSON_MARKED`, whose
    status is `approved`, and whose `approved['by']` is in `DESK_ACCEPTED` reads `draft`.
    The exception is when `session.get('desk_ready', {}).get(name) ==
    approved['sha256']` (Task 15 writes that).
- `workspace.KEPT = 'Kept on the desk.'`.
- `workspace.keep_as_is(root, name, reason=None, by='page', seen=None) -> dict`.
  - It refuses a session not on the desk ("This training is not on the desk.").
  - It refuses a `seen` that differs from the file's hash, with `decide`'s sentence
    "<Label> has changed since it was opened. Read the new version before deciding."
  - It refuses when an upstream's status is `stale`: f"Update or keep {label(upstream)}
    first."
  - It appends `{'at', 'artifact', 'decision': 'kept-as-is', 'from', 'to', 'reason': reason
    or KEPT, 'by'}` to `session['decisions']` and sets `built_from` to the current inputs.
  - If `approved['by'] == 'page'` and `approved['sha256']` is the file's hash, it sets
    `approved['inputs']` to the current inputs, so it stays Ready. Otherwise it calls
    `_approve(…, 'desk', policy=True)`.
  - It logs `kept-as-is`. It returns `{'artifact', 'status'}`.
- `checks.readiness` lists `f"{decision['artifact']} was kept as it was after its inputs
  changed: {decision['reason']}"` for each `kept-as-is` decision, beside today's
  `accepted-stale` line.

- [ ] **Step 1: Write the failing tests** in `test_workspace.py`, using `TrainingCase`'s
  `init` with `flow='desk'` and `approval='page'`:
  - `test_a_desk_session_records_its_flow`: `load(root)['flow'] == 'desk'`. `init(...,
    flow='other')` raises `WorkspaceError` with "Choose a listed flow." A session made
    without `flow` has no `flow` key.
  - `test_row_132_a_desk_acceptance_is_not_the_person_s`:
    - save and `accept_desk` a blueprint;
    - `statuses` says `approved` and `person_statuses` says `draft`;
    - the last event is `{'event': 'continued-on-the-desk', 'artifact': 'blueprint', 'by':
      'desk', …}`;
    - on a session without `flow`, `accept_desk` raises "This training is not on the desk."
  - `test_a_save_records_how_it_was_made`:
    - `save(root, 'document', source=file, edit=True, via='rewrite', session_token='ab12')`
      leaves the last `save` event with `via == 'rewrite'` and `session == 'ab12'`;
    - `via='typed'` raises "Choose a listed kind of change." and leaves `document.md` and the
      session as they were.
  - `test_row_139_keep_as_it_is_takes_the_new_inputs`:
    - approve a blueprint and document by the page, then edit the blueprint; the document
      is `stale`;
    - `keep_as_is(root, 'document')` leaves it `approved` in `person_statuses`, with the
      decision reason "Kept on the desk.";
    - `checks.readiness` limitations include "document was kept as it was after its inputs
      changed: Kept on the desk."
  - `test_keep_as_it_is_waits_for_a_held_input`: with the blueprint out of date because the
    research changed, `keep_as_is(root, 'document')` raises "Update or keep the blueprint
    first." (the exact label `workspace.label('blueprint')` gives, joined as written).
  - `test_keep_as_it_is_refuses_an_older_view`: `keep_as_is(..., seen='0'*64)` raises a
    sentence ending "has changed since it was opened. Read the new version before
    deciding."
- [ ] **Step 2: Run them and see them fail:** `cd studios/training/tests && python3 -m
  unittest test_workspace -k desk -k row_132 -k row_139 -k keep -k records_how -v`.
- [ ] **Step 3: Implement.**
  - `_approve`'s log line becomes `log(session, 'continued-on-the-desk' if by == 'desk'
    else 'continued-automatically' if policy else 'approve', …)`.
  - `accept_desk` mirrors `accept_policy`, without the policy check.
  - `person_statuses` wraps `statuses`.
  - Add the readiness line.
- [ ] **Step 4: Add matrix rows 132 and 139** in A7. They use the spec's D2 and D9 words,
  each ending "Covered by `test_row_132_…`" and "Covered by `test_row_139_…`".
- [ ] **Step 5: Run** `python3 -m unittest test_workspace test_checks -v` and see them pass.
  Then run `python3 -m unittest test_cli -v`: the conversation helper is unchanged.
- [ ] **Step 6: Commit** "Let a training's workspace tell the desk's acceptance from the
  person's, keep a material as it is, and say how each save was made".

## Task 2: A scenario knows its practice plan line, on desk runs only

**Files:**
- Modify: `studios/training/skills/training-studio/scripts/workspace.py` (`artifact` at
  about 390, `inputs` at about 468)
- Test: `studios/training/tests/test_workspace.py`

**Interfaces (Produces):**
- `workspace.practice_line(text: str, ident: str) -> str | None`. It returns the line under
  `## Practice plan` that starts with `- <ident>:` (spaces trimmed), or None.
- `init(flow='desk')` also writes `session['practice_inputs'] = True`. Opening a saved
  training on the desk (Task 15) never writes it, so its scenarios are never held on
  opening.
- On a session with `practice_inputs` set, `artifact(root, session,
  'scenario:<id>[@level]')['extras'] == ('practice',)`. On any other session it stays `()`.
- `inputs` computes `'practice'` as the SHA-256 of `practice_line(blueprint text, ident)`,
  or the string `'none'` when the line is missing.

- [ ] **Step 1: Write the failing tests.**
  - `test_row_151_a_desk_scenario_knows_its_practice_plan`:
    - on a desk session with the example blueprint and a saved `main` scenario, the
      scenario is `draft`;
    - changing the `- main:` line's objectives makes it `stale`;
    - changing another module's line leaves it `draft`.
  - `test_a_saved_training_s_scenario_has_no_inputs`: the same steps on a session without
    `flow` leave the scenario `draft` throughout, and its `built_from == {}`.
  - `test_the_practice_line_is_found_by_its_id`: `practice_line(BLUEPRINT, 'main')` is the
    example's line 33. `practice_line(BLUEPRINT, 'other')` is None.
- [ ] **Step 2: Run** `python3 -m unittest test_workspace -k practice -k row_151 -v` and see
  them fail.
- [ ] **Step 3: Implement it,** and add matrix row 151 (the spec's D21).
- [ ] **Step 4: Run** `python3 -m unittest test_workspace test_runner_pipeline -v` and see
  them pass.
- [ ] **Step 5: Commit** "Hold a desk training's scenario when its practice plan line
  changes".

## Task 3: The desk start: a schema 4 run with no review level

**Files:**
- Create: `studios/training/runner/drafts.py`. This task adds only its constants and
  `on_desk`.
- Modify: `studios/training/runner/engine.py` (`SCHEMA` at 218, `read_record` at 380,
  `new_record` at 398, `start` at 987)
- Modify: `studios/training/runner/pipeline.py` (`create` at 672: passes `flow`)
- Modify: `studios/training/runner/page.py` (the `/api/trainings` form check: accepts
  `flow`)
- Test: `studios/training/tests/test_drafts.py` (new; a `StudioCase` subclass)

**Interfaces (Produces):**
- `drafts.FLOW = 'desk'`, `drafts.SCHEMA = 4`.
- `drafts.on_desk(record: dict | None) -> bool`.
- `drafts.NEEDS_SYNTHESIS = 'Update Harness Research to start a training on the desk. The
  Status screen says how.'`
- `drafts.ON_DESK = 'This training is on the desk. Change it there.'`
- `drafts.NOT_ON_DESK = 'This training is not on the desk. Use its own screen, or open it on
  the desk once it is finished.'`
- `Engine.start(form)` with `form['flow'] == 'desk'` does the following:
  - it refuses `NEEDS_SYNTHESIS` when `research_contract.snapshot(self.research())` gives
    none, before anything is made;
  - it writes `schema: 4`, `flow: 'desk'` and `drafts: {'jobs': [], 'updates': {},
    'findings_before': None}` into the run record;
  - it writes no `review_policy` or `review_layout`, and never calls `review_policy.change`,
    even with `review_default`;
  - the session gets `flow` and no `review_policy`;
  - it returns `gates: 0`.
- `read_record` accepts schema 4 only with `flow == 'desk'` and a `research_contract` of
  schema 2. Otherwise it raises "This run is missing its saved research contract. Restore
  its run record." `read_record` also accepts `flow == 'desk'` on schemas 1 to 3, for Task 15.

- [ ] **Step 1: Write the failing tests** in `test_drafts.py`:
  - `test_row_131_a_desk_start_saves_no_review_level`:
    - `self.start(flow='desk')` with the synthesis stand-in gives a record with `schema ==
      4`, `flow == 'desk'`, no `review_policy` and no `review_layout`;
    - the session's `flow` is `'desk'`;
    - the intake is approved `by: 'page'`;
    - with `documents` in `source_scope`, no research step has started before
      `engine.supply(root, 'done')`.
  - `test_row_133_a_desk_start_needs_synthesis`: with the research stand-in set to offer no
    synthesis, `start(flow='desk')` raises `NEEDS_SYNTHESIS`. No training folder is left
    and the workspace's git log is unchanged.
  - `test_a_desk_start_writes_no_shared_level`: with `review_default=True` and
    `review_level='automatic'` in the form, the studios-config file is unchanged (its bytes
    before and after).
  - `test_saved_runs_keep_their_gates` (Review Focus 1): a `start()` with no flow at
    `step_by_step`, then `to_gate(root, 'gate:research-plan')`, waits at that gate as
    before. Balanced waits at `gate:research-plan`.
- [ ] **Step 2: Run** `cd studios/training/tests && python3 -m unittest test_drafts -v` and
  see them fail.
- [ ] **Step 3: Implement it.** `pipeline.create` passes `flow=form.get('flow')` to
  `workspace.init`. The page's form check accepts `flow` only as `'desk'` or absent, and
  refuses anything else with "Choose a listed flow."
- [ ] **Step 4: Add matrix rows 131 and 133.**
- [ ] **Step 5: Run** `python3 -m unittest test_drafts test_runner_engine test_review_levels
  -v` and see them pass.
- [ ] **Step 6: Commit** "Start a training on the desk with no review level, and refuse it
  without Harness Research synthesis".

## Task 4: Continuing on the desk: no stops

**Files:**
- Modify: `studios/training/runner/engine.py` (`_work` at 1208-1233: a desk branch before
  the `review_policy.automatic` check; new `_desk_gate`)
- Modify: `studios/training/runner/reviews.py` (`_policy_outline` takes `by`; new
  `_desk_outline` calls it with `'desk'`)
- Modify: `studios/training/runner/pipeline.py` (`survey` at 1220: no `reviews.group` on
  desk runs, around 1249-1251)
- Test: `studios/training/tests/test_drafts.py`

**Interfaces (Produces):**
- `Engine._desk_gate(root, found) -> None`. At `gate`, `wait` or `look`, and at `outline`
  for `gate:deck-outline`, on a desk run:
  - a look gets `_look_default(root, step, by='desk')`, with the receipt words "You chose the
    brand's default look at the start: {name}.";
  - a deck outline gets `_ask` when needed, then `_desk_outline`;
  - any other gate gets `workspace.accept_desk`.

  Each appends `{'gate', 'by': 'desk', 'level': None, 'evidence': fingerprint, 'at',
  'decision': 'continued-on-the-desk'}` to `record['review_events']`, then commits "continue
  <label> on the desk".
- `pipeline.holding(...)` is not consulted on desk runs.
- Problem stops are unchanged: they already end `_work` with `record['problem']`. On a desk
  run nothing else waits.

- [ ] **Step 1: Write the failing tests:**
  - `test_row_132_a_desk_training_reaches_its_end_with_no_stop`:
    - `start(flow='desk', materials=['document', 'brief'])`, then `to_end(root)`;
    - every material exists, and none is in `record['problem']` or waiting;
    - each gate has a `review_events` entry with `by == 'desk'` and `decision ==
      'continued-on-the-desk'`;
    - no step id begins `review:`.
  - `test_a_desk_deck_is_continued_in_the_default_look`: with the slides and brand
    stand-ins, `gate:deck-outline@101`, `gate:deck-look@101` and `gate:deck@101` are all
    continued; the look receipt note is "You chose the brand's default look at the start:
    <the stand-in's default look name>."
  - `test_row_154_a_failed_step_on_the_desk_is_a_problem_not_a_gate`: `self.workers.then(
    'document', fails(), fails(), fails())` leaves `record['problem']['step'] ==
    'document@101'` with `action == 'retry'`. `workspace.load(root)['gate']` is unchanged
    from before the document step.
  - `test_saved_runs_keep_their_gates` gains: an Automatic draft run still waits at
    `gate:deck@101` and at `review:final`.
- [ ] **Step 2: Run** them and see them fail.
- [ ] **Step 3: Implement** `_desk_gate`, the `survey` branch and `by` on `_policy_outline`
  and `_look_default`.
- [ ] **Step 4: Add matrix rows 132 (the engine half) and 154.**
- [ ] **Step 5: Run** `python3 -m unittest test_drafts test_runner_engine test_runner_flow
  test_review_levels test_runner_deck -v` and see them pass.
- [ ] **Step 6: Commit** "Carry a desk training past every gate with a desk receipt, so it
  never stops for review".

## Task 5: Held, not remade: holds, Update and Keep as it is in the engine

**Files:**
- Modify: `studios/training/runner/drafts.py` (holds)
- Modify: `studios/training/runner/pipeline.py` (`survey`: filter held steps; `_done` is
  unchanged)
- Modify: `studios/training/runner/engine.py` (new `update`, `keep`)
- Test: `studios/training/tests/test_drafts.py`

**Interfaces (Produces):**
- `drafts.held(root, session, run) -> frozenset[str]`. On desk runs it returns every name in
  `workspace.artifact_names` that meets three conditions:
  - its status is `stale`;
  - its file exists;
  - it has no open update in `run['drafts']['updates']`.

  On other runs it returns `frozenset()`.
- `drafts.input_of(root, session, name) -> list[str]`: the upstream names, plus `practice`
  and `profile`, whose values differ between `built_from` and `inputs`.
- `drafts.HELD = 'Built from an earlier {what}.'`, `drafts.CHANGED = ' {n} {parts} changed
  since.'`, `drafts.WAITING = 'Waiting for {what} to be updated or kept.'`,
  `drafts.PRACTICE = 'The plan for this practice changed.'`
- `drafts.WHAT = {'blueprint': 'plan', 'document': 'guide', 'brief': 'brief', 'research':
  'research', 'scenario': 'scenario', 'practice': 'practice plan', 'profile': 'Yoodli
  profile'}`. These are piece 1's words for each; use piece 1's where they differ.
- `pipeline.survey(...)` on a desk run removes from `listed` every step whose `artifact` is
  in `drafts.held(...)`. That covers all `DECK_STEPS` of a held deck and the `copies:*`
  steps of a held material.
- `Engine.update(path, name, scope=None) -> dict`.
  - It refuses while a desk job or an update runs (`drafts.BUSY`, Task 13), and for a name
    not held ("This is up to date.").
  - It records `run['drafts']['updates'][name] = {'at', 'by': 'page', 'scope': scope}` and
    commits "update <label> from <what>".
  - Then it calls `carry_on`.
  - `drafts.close_updates(root, session, run)` drops an update once its material is no longer
    `stale`. It is called in `survey`.
- `Engine.keep(path, name, reason=None, seen=None) -> dict` calls `workspace.keep_as_is(...,
  by='page')`, then commits "keep <label> as it is".
- In this pull request, Update remakes the whole material through its own step, as a stale
  material is remade today. Task 14 makes text updates surgical and Task 20 scopes the deck.

- [ ] **Step 1: Write the failing tests:**
  - `test_row_137_a_guide_edit_holds_the_deck`:
    - `to_end` a desk training with a deck, then write a changed `document.md` through
      `workspace.save(edit=True, via='save')` and `accept_desk`;
    - `drafts.held` is `{'deck@101'}`;
    - `to_end` starts no deck step: `Workers.of('outline')` and the Slides stand-in's drawn
      sections are unchanged in count;
    - the view sentence is "Built from an earlier guide."
  - `test_row_138_update_remakes_only_what_was_held`: after `engine.update(root,
    'deck@101')`, `to_end` runs the deck's steps once, the hold is gone, and
    `run['drafts']['updates'] == {}`.
  - `test_row_139_keep_as_it_is_from_the_page`: `engine.keep(root, 'deck@101')` empties
    `drafts.held`, and no deck step runs.
  - `test_a_card_below_a_held_one_waits`: when the plan is held because the research
    changed, the guide's sentence is "Waiting for the plan to be updated or kept." and
    `engine.keep(root, 'document@101')` raises "Update or keep the blueprint first."
  - `test_row_151_the_practice_plan_holds_its_scenario`: changing the `main` line of
    `blueprint.md` on a desk run holds `scenario:main@101` with `drafts.PRACTICE`.
  - `test_saved_runs_still_remake`: on a step-by-step run the same guide edit puts the deck
    back through its steps, as today.
- [ ] **Step 2: Run** them and see them fail.
- [ ] **Step 3: Implement** the holds, the `survey` filter, `update`, `keep` and
  `close_updates`.
- [ ] **Step 4: Add matrix rows 137 and 138, and finish 139 and 151.**
- [ ] **Step 5: Run** `python3 -m unittest test_drafts test_runner_pipeline test_runner_engine
  test_runner_deck -v` and see them pass.
- [ ] **Step 6: Commit** "Hold what a desk change reaches until the person updates it or
  keeps it as it is".

## Task 6: Mark ready, Mark this level ready, readiness, the package and copies

**Files:**
- Modify: `studios/training/runner/drafts.py` (`ready`, `level_ready`, `needs_you`)
- Modify: `studios/training/runner/engine.py` (new `mark_ready`, `mark_level_ready`,
  `send_copy`)
- Modify: `studios/training/skills/training-studio/scripts/assess.py` (`run_checks` uses
  `person_statuses` on desk sessions)
- Modify: `studios/training/runner/pipeline.py` (the `package` step's done check, about line
  941; `copies.wanted` input on desk runs)
- Modify: `studios/training/runner/copies.py` (`make` at 103: on desk runs, `approved` comes
  from `person_statuses` plus `run['drafts']['send']`)
- Test: `studios/training/tests/test_drafts.py`, `studios/training/tests/test_runner_copies.py`

**Interfaces (Produces):**
- `drafts.ORDER = ('blueprint', 'document', 'brief', 'deck', 'scenario', 'yoodli')`.
- `drafts.needs_you(root, found, name) -> list[str]`. For a deck it is the
  `review_policy.held(findings, blockers)` sentences from its last round's review and its
  audit; otherwise `[]`.
- `Engine.mark_ready(path, name, seen) -> dict`. It refuses, in this order:
  - a held name: f"{Label} is built from an earlier {what}. Update it or keep it as it is
    first.";
  - a deck with `needs_you`: f"Settle what needs you on {label} before marking it ready.";
  - otherwise `workspace.decide(root, name, 'approve', by='page', seen=seen)`, whose own
    refusals stand ("has changed since it was opened.").

  Then it commits "mark <label> ready" and calls `carry_on`.
- `Engine.mark_level_ready(path, level, seen: dict[str, str]) -> dict` marks every name of
  that level in `ORDER` (scenarios and Yoodli layouts by ID) that is `draft` in
  `person_statuses`, each with its `seen[name]`. It stops at the first refusal and returns
  `{'marked': [names], 'stopped': {'name', 'said'} | None}`. It commits once.
- `Engine.send_copy(path, name) -> dict` adds `name` to `run['drafts']['send']`. It makes or
  updates that one copy through `copies.make(root, google, word)` with `only=name`, a new
  keyword. It reports `copies.make`'s outcome.
- On a desk run, `package` is done only when `checks.readiness(...)` built from
  `person_statuses` is `ready`. It then runs with no gate.

- [ ] **Step 1: Write the failing tests:**
  - `test_row_140_mark_ready_is_the_person_s_approval`:
    - after `to_end`, `engine.mark_ready(root, 'document@101', seen=<file hash>)` makes
      `person_statuses` say `approved`, with `approved['by'] == 'page'`;
    - with `seen='0'*64` it raises a sentence ending "has changed since it was opened. Read
      the new version before deciding.";
    - an edit afterwards makes it `draft` again.
  - `test_row_141_a_level_is_marked_ready_in_order`: with the deck holding a stand-in
    critical finding, `mark_level_ready` returns `marked == ['blueprint@101',
    'document@101', 'brief@101']` and `stopped['said'] == 'Settle what needs you on the
    level 101 slide deck before marking it ready.'` (the label `workspace.label` gives).
  - `test_row_142_the_index_is_written_once_everything_is_ready`: `to_end` writes no
    `README.md` while one material is a desk draft. After the last `mark_ready`, `to_end`
    writes it, and no gate waits.
  - `test_the_desk_s_acceptance_never_lets_the_package_run` (Review Focus 2): a desk run
    with every material accepted on the desk and none marked has `package` not done, and
    `assess.run_checks(root)['ready'] is False`.
  - `test_copies_follow_mark_ready_on_the_desk` in `test_runner_copies.py`:
    - a desk run with Google copies wanted makes no Doc before `mark_ready`, and one after;
    - `send_copy(root, 'brief@101')` makes the brief's Doc while it is a draft.
- [ ] **Step 2: Run** them and see them fail.
- [ ] **Step 3: Implement it.**
- [ ] **Step 4: Add matrix rows 140, 141 and 142.**
- [ ] **Step 5: Run** `python3 -m unittest test_drafts test_runner_copies test_runner_index
  test_checks -v` and see them pass.
- [ ] **Step 6: Commit** "Make Mark ready the person's approval on the desk, and write the
  index only once every material is ready".

## Task 7: The desk's view and routes, refused both ways

**Files:**
- Modify: `studios/training/runner/drafts.py` (`view`)
- Modify: `studios/training/runner/page.py` (`READS`, `WRITES` at 181-183, `read`, `write`;
  the gate, review, outline, decide and documents routes refuse desk runs)
- Test: `studios/training/tests/test_runner_page.py`

**Interfaces (Produces):**
- `drafts.view(engine, root) -> dict`:
  - `{'flow': 'desk', 'title', 'levels': [level or ''], 'progress', 'needs', 'cards',
    'sources', 'job', 'team'}`.
  - `progress`: `{'running': bool, 'doing': str, 'started_at', 'minutes': int | None,
    'line': str}`. The line is "Nothing needed from you. Each material opens here as it is
    ready, in about {n} minutes." while it runs, and "" afterwards.
  - `drafts.GUESSES = {'research': 6, 'blueprint': 1, 'document': 3, 'brief': 2,
    'scenario': 1, 'yoodli': 1}`, in minutes.
  - `drafts.start_minutes(root, record, found) -> int` sums, over the steps still to run,
    `step_times.expected(store, home.data_root() / 'draft-step-times.json', <stage>,
    GUESSES[stage])`. A deck's guess is `deck.RATE['minutes']` times its slides (8 before
    its outline exists). The engine calls `step_times.note` with each step's seconds when the
    step ends.
  - `cards`: one per name, in `ORDER` within each level. Each is `{'name', 'level',
    'kind', 'label', 'state', 'says', 'checks', 'seen', 'held', 'actions', 'needs'}`.
    - `state` is one of `writing`, `draft`, `ready`, `held`, `needs`, `left-out`.
    - `says` is the sentence for its state.
    - `seen` is the file's hash.
    - `actions` is a subset of `['ready', 'update', 'keep', 'send', 'download']`.
  - `sources`: `{'account': research_view.account(...), 'plan': items, 'documents': listed}`.
  - `needs`: the labels of cards that need the person, then the run's problem or question.
- GET `/api/drafts?path=` gives `drafts.view`.
- POST `/api/drafts/ready` `{path, name, seen}`.
- POST `/api/drafts/level-ready` `{path, level, seen}`.
- POST `/api/drafts/update` `{path, name}`.
- POST `/api/drafts/keep` `{path, name, reason, seen}`.
- POST `/api/drafts/send` `{path, name}`.
- Each desk route on a run without `flow` refuses with `drafts.NOT_ON_DESK`, status 409.
- On a desk run, `/api/decide`, `/api/review`, `/api/outline`, `/api/look` and `/api/gate`
  refuse with `drafts.ON_DESK`, status 409. `/api/documents` refuses after the documents step
  with today's `SETTLED`. Add a source is Task 22.
- A teammate's view (`team.ours` false) has `actions == ['download']` on every card. Each
  write route refuses with the engine's existing "someone else is running this training"
  sentence.

- [ ] **Step 1: Write the failing tests** in `test_runner_page.py`:
  - `test_row_152_desk_and_review_routes_refuse_each_other`: the five review routes on a
    desk run return 409 with `drafts.ON_DESK`. The five desk routes on a saved run return
    409 with `drafts.NOT_ON_DESK`.
  - `test_the_desk_view_lists_each_level_s_cards_in_order`: a two-level desk training's
    view has, for level 101, cards named `blueprint@101`, `document@101`, `brief@101`,
    `deck@101`, `scenario:main@101`, in that order. Each `seen` is its file's hash, and no
    `says` contains "artifact", "stale" or "lineage".
  - `test_a_teammate_reads_the_desk`: under `TeamCase`, the second person's view has only
    `download` actions, and `/api/drafts/ready` is refused.
  - `test_progress_says_nothing_is_needed`: while a scripted worker blocks in `document`,
    `progress['line']` starts "Nothing needed from you. Each material opens here as it is
    ready, in about".
  - `test_the_start_s_minutes_use_this_computer_s_times`: with no times kept, a guide-and-brief
    training with one level is `6 + 1 + 3 + 2 = 12` minutes before research. After
    `step_times.note` records 120 seconds for `document` three times, its share is 2.
- [ ] **Step 2: Run** `python3 -m unittest test_runner_page -k desk -k row_152 -k teammate -k
  progress -v` and see them fail.
- [ ] **Step 3: Implement it.**
- [ ] **Step 4: Add matrix row 152.**
- [ ] **Step 5: Run** `python3 -m unittest test_runner_page test_drafts -v` and see them
  pass.
- [ ] **Step 6: Commit** "Serve the desk's view and its decisions, and refuse review routes
  on a desk training and desk routes on a saved one".

## Task 8: The page: the start sheet, the progress band and the desk

**Files:**
- Create: `studios/training/skills/training-studio/scripts/desk/drafts.js`
- Create: the link `studios/training/skills/training-studio/scripts/desk/drafting.js ->
  ../../../../../../ui-kit/drafting.js`
- Modify: `studios/training/skills/training-studio/scripts/desk/index.html` (loads
  `drafting.js`, `app.js`, then `drafts.js`)
- Modify: `studios/training/skills/training-studio/scripts/desk.py` (`PAGE` at 33-39 gains
  `/drafting.js` and `/drafts.js`)
- Modify: `marketing_studio/network.py` (`STATIC` gains `/drafts.js`)
- Modify: `core/studio_core/packaging.py` (`shared_link` accepts Training's `drafting.js`)
- Modify: `studios/training/skills/training-studio/scripts/desk/app.js`:
  - `drawNew` and `startTraining` (about 4737, 4775) open the desk start for new trainings;
  - `drawTraining` (3114) opens the desk for a run with `flow == 'desk'`;
  - `REVIEW_SAYS` and `reviewLevelCard` are left for saved-run screens only.
- Modify: `studios/training/tests/page_harness.js` (loads `drafting.js` before `app.js` and
  `drafts.js` after)
- Test: `studios/training/tests/test_desk.py`, `tests/test_network_static.py`,
  `tests/test_packaging_entrypoints.py` (or the file piece 3 put its `shared_link` case in)

**Interfaces (Produces):**
- `drafts.js` defines `paintDesk(fresh)`, `drawDesk(fresh)`, `deskStart()`,
  `startOnDesk(pressed)` and `DESK_WORDS`.
- Its adapter is `deskKit = Drafting.kit({...})`:
  - `ui`: app.js's `button`, `card`, `segmented`, `openSheet`, `closeSheet`, `toast`;
  - `api`: app.js's `call`;
  - `routes`: `view: 'drafts'`, `save: 'drafts/save'`, `versions: 'drafts/versions'`,
    `restore: 'drafts/restore'`, `note: 'drafts/note'`, `revise: 'drafts/revise'`,
    `selection: 'drafts/selection'`, `stop: 'drafts/stop'`, `retry: 'drafts/retry'`,
    `finish: 'drafts/finish'`, `apply: 'drafts/apply'`, `skip: 'drafts/skip'`,
    `proofread: 'drafts/proofread'`;
  - the other members as piece 3's table names them.
  The routes after `view` are served from Tasks 12, 13 and 24.
- **The start sheet.** Steps "1. Goal and audience", "2. Materials and levels" and "3. Sources and
  settings", separated by hairlines. **Start** (filled) and Cancel sit together at the end.
  - **Start** posts `/api/trainings` with `flow: 'desk'`.
  - Then it posts `/api/documents` `add` for each held file.
  - Then it posts `done`.
  - A failed add shows "One document could not be added: {name}. Add it again, or start
    without it." with **Add it again** and **Start without it**.
- **The desk.**
  - The toolbar: the title, Back, **Mark this level ready** (filled), Download, Google Doc,
    Finishing.
  - The lede: "Each level's materials, built from the shared research. Edit any part.
    Nothing is ready until you mark it."
  - Then the needs line, the progress band, the level tabs (`.segmented`), the card column
    and the Sources aside. On a phone, Sources is a tab.

- [ ] **Step 1: Write the failing page journeys** in `test_desk.py` with `run_page`:
  - `test_the_desk_start_has_three_numbered_steps_and_one_start`:
    - the snapshot has the step titles "1. Goal and audience", "2. Materials and levels" and
      "3. Sources and settings";
    - one filled button, "Start", is beside "Cancel";
    - there is no text "Where this training stops".
  - `test_documents_are_added_before_research_starts`: attaching two files and pressing
    Start sends, in order, `POST /api/trainings` (with `flow: 'desk'`), two `POST
    /api/documents` with `action: 'add'`, and one with `action: 'done'`.
  - `test_a_failed_document_says_so_and_offers_both_ways`: the second add answers 400. The
    snapshot shows "One document could not be added: notes.docx. Add it again, or start
    without it." with both buttons.
  - `test_the_desk_opens_with_progress_and_cards`:
    - answers from Task 7's view shape show the lede, "Nothing needed from you. Each
      material opens here as it is ready, in about 12 minutes.", tabs "101" and "201", and
      the cards Plan, Guide, Brief, Deck and Practice in order;
    - exactly one filled button, "Mark this level ready".
  - `test_a_held_deck_offers_update_and_keep`: a card with `state: 'held'` and `says: 'Built
    from an earlier guide. 3 sections changed since.'` shows **Update from the guide** and
    **Keep as it is**. Pressing Keep sends `POST /api/drafts/keep` with the card's `seen`.
  - `test_mark_this_level_ready_names_where_it_stopped`: an answer `stopped: {said: 'Settle
    what needs you on the level 101 slide deck before marking it ready.'}` is shown as a
    notice with that sentence.
  - `test_a_teammate_s_desk_has_no_edit_controls`: with `team.ours` false, there is no
    "Mark ready" and no note box, and "Take over" is shown.
  - `test_the_desk_on_a_phone`: with `narrow: true`, Sources is a tab, and every control in
    the snapshot is a native button or input.
  - In `tests/test_network_static.py`: `/drafts.js` is listed. In `tests/test_packaging_entrypoints.py`
    (beside piece 3's `shared_link` case): the Training `drafting.js` link is accepted.
- [ ] **Step 2: Run** `cd studios/training/tests && python3 -m unittest test_desk -k desk -v`
  and `PYTHONPATH=.:tests python -m unittest test_network_static test_packaging_entrypoints`, and see
  them fail.
- [ ] **Step 3: Implement `drafts.js`.** It is built from app.js's helpers (`make`, `add`,
  `button`, `card`, `segmented`, `openSheet`) and piece 3's kit. It sets no `innerHTML`, so
  the harness's missing HTML parser proves it.
- [ ] **Step 4: Run** the full page suite (`python3 -m unittest test_desk -v`), the root
  suite and `node studios/blog/scripts/ci/check-management.cjs`. Blog Studio's page shares
  `network.py`. See them pass.
- [ ] **Step 5: Commit** "Start new trainings from a three-step sheet and open them on the
  desk, with progress, level tabs, Sources and Mark ready".

**Pull request 1 is usable here.** Run the Training Studio suite
(`python3 studios/training/scripts/ci/run_tests.py`) and open the pull request.

---

# Pull request 2: editing text on the desk

## Task 9: Training's store and codec over piece 3's parts

**Files:**
- Modify: `studios/training/runner/drafts.py` (`TrainingStore`, `CODECS`, `current`,
  `TrainingDesk`)
- Test: `studios/training/tests/test_drafts_parts.py` (new)

**Interfaces (Produces):**
- `drafts.TrainingStore(engine, root)` is a piece 3 store:
  - `product = 'Training Studio'`, `word = 'training'`;
  - `held()` is the engine's `files` lock being held;
  - `folder(name)` is `place(root, level, 'work/drafts') / name.replace(':', '-').replace('@', '-')`;
  - `local(name)` is `home.data_root() / 'draft-proposals' / <training id> / <name>`;
  - `write(name, draft, parts, via='save', session=None)` calls `record.advance`, joins the
    parts, then calls `workspace.save(root, name, source=<joined file in work/drafts>,
    edit=True, via=via, session_token=session)` and `workspace.accept_desk`. It writes
    `draft.json` with `file_sha256`.
- `drafts.CODECS = {'document': GuideCodec(), 'brief': BriefCodec(), 'blueprint':
  PlanCodec()}`, each a piece 3 `Codec`:
  - `GuideCodec`:
    - `fixed = ('opening',)`; the opening is everything before the first `## `;
    - `split` keeps a section's `<!-- covers: … -->` line as `section['covers']` (list of
      IDs), out of `text`;
    - `join` puts it back under the heading, byte for byte;
    - a section headed `Sources` is `section['locked'] = True`.
  - `BriefCodec`:
    - sections must match `checks.BRIEF_SECTIONS[kind]`, in order;
    - `section['findings']` holds the `<!-- findings: … -->` note;
    - "8. Sources" is locked;
    - `breaks(text)` also refuses any `## ` line.
  - `PlanCodec`: the blueprint's `##` sections, with nothing locked.
- `drafts.current(store, codec, name) -> dict`. It returns the draft. When the file's hash is
  not `file_sha256`, it splits again first:
  - ids are kept by heading, then by note, then by position;
  - the revision goes up by one, and every part is marked changed.
- `drafts.TrainingDesk(store, codec)` is piece 3's `Desk` with `HistoryVersions` (Task 11)
  in place of its own `Versions`.

- [ ] **Step 1: Write the failing tests:**
  - `test_every_example_splits_and_joins_back_byte_for_byte`: for `assets/examples/
    document.md`, `product-brief.md`, `competitive-brief.md` and `blueprint.md`,
    `codec.join(codec.split(text)) == text`.
  - `test_a_guide_section_keeps_its_covers_note`: the section "What a rolling restart does"
    has `covers == ['O1', 'K1.1', 'K1.3']`, and its `text` does not contain `<!--`.
  - `test_a_brief_keeps_its_eight_sections`: a draft with a section removed, renamed or moved
    raises "A brief keeps its eight numbered sections, in order." The "8. Sources" part is
    `locked`.
  - `test_the_record_follows_the_file`: after `document.md` is written by
    `workspace.save(built=True)`, `current` returns revision `before + 1`. Every section's
    `changed` is the new revision, and a section whose heading is unchanged keeps its id.
- [ ] **Step 2: Run** `python3 -m unittest test_drafts_parts -v` and see them fail.
- [ ] **Step 3: Implement it.**
- [ ] **Step 4: Run** it again and see it pass.
- [ ] **Step 5: Commit** "Split a training's guide, brief and plan into parts that join back
  to the same file".

## Task 10: The citation check

**Files:**
- Modify: `studios/training/skills/training-studio/scripts/checks.py` (new `citations`,
  `REFERENCE`, `SOURCES_ENTRY`)
- Modify: `studios/training/skills/training-studio/scripts/assess.py` (`run_checks`: adds
  `citations` on desk sessions only)
- Test: `studios/training/tests/test_checks.py`

**Interfaces (Produces):**
- `checks.REFERENCE = re.compile(r'\[(\d{1,3})\]')`.
- `checks.citations(text: str, kind: str, added: list[str] | None = None) -> dict`. `kind`
  is `'document'` or `'brief'`. It returns `result('<kind>.citations', problems)`, whose
  problems are:
  - "Reference [{n}] is not in Sources." for an `[n]` with no `n.` entry under Sources (or
    "8. Sources");
  - "Sources entry {n} is not cited." for an entry no `[n]` names;
  - 'A claim with no reference: "{first 60 characters}…"' for each paragraph in `added`
    that has a digit, a capitalised word not at a sentence start, or a product name from
    intake, and no `[n]`.
- `checks.dropped(before: str, after: str) -> list[int]`: the reference numbers in `before`
  that are not in `after`.

- [ ] **Step 1: Write the failing tests:**
  - `test_the_example_guide_s_references_resolve`: `citations(<example document>,
    'document')['status'] == 'passed'`.
  - `test_a_reference_with_no_source_is_named`: adding "[9]" gives the problem "Reference
    [9] is not in Sources."
  - `test_an_unused_source_is_named`: removing every "[3]" gives "Sources entry 3 is not
    cited."
  - `test_a_new_claim_with_no_reference_is_named`: `added=['Restarts take 40 seconds on
    Tanzu Platform.']` gives one problem starting 'A claim with no reference: "Restarts take
    40 seconds'.
  - `test_dropped_references_are_listed`: `dropped('A [1] and [2].', 'A [1].') == [2]`.
  - `test_saved_trainings_are_not_checked_for_citations`: `assess.run_checks` on a session
    without `flow` has no `document.citations` outcome; on a desk session it has one.
- [ ] **Step 2: Run** `python3 -m unittest test_checks -k citation -k reference -k dropped -k
  claim -v` and see them fail.
- [ ] **Step 3: Implement it.**
- [ ] **Step 4: Run** `python3 -m unittest test_checks test_cli -v` and see them pass.
- [ ] **Step 5: Commit** "Check that a desk training's references resolve, and name a new
  claim with none".

## Task 11: History from the history files

**Files:**
- Modify: `studios/training/runner/drafts.py` (`HistoryVersions`)
- Modify: `studios/training/skills/training-studio/scripts/gdocs.py` (`pull` at 302-342:
  `save(..., edit=True, via='google')`)
- Modify: `studios/training/runner/copies.py` (`pull` at 188-234: `via='google'` on
  `theirs`)
- Test: `studios/training/tests/test_drafts_history.py` (new)

**Interfaces (Produces):**
- `drafts.HistoryVersions(store, codec)` implements piece 3's `Versions`:
  - `keep(...)` records nothing;
  - `versions(name, part) -> list[{'at': str | None, 'source': str, 'text': str, 'words':
    int}]`, newest first, at most `drafting.versions` cap (20);
  - `counts(name) -> dict[part, int]`.
- **Sources** (labels for the page's `words`): `save` "Saved", `rewrite` "Rewritten",
  `revise-all` "Revised with the whole note", `selection` "Selection", `restore` "Restored",
  `google` "Before Google's text", `finishing` "Finishing", `update` "Updated", none
  "Saved". An entry from a history file with no event is `{'at': None, 'source': 'earlier'}`,
  labelled "An earlier version".

- [ ] **Step 1: Write the failing tests:**
  - `test_history_comes_from_the_history_files` (Review Focus 5):
    - make a training with the core helper (no desk), save `document.md` three times with
      `built=True`, and hand-edit it once and save;
    - `versions('document', <section id>)` lists the section's earlier texts, newest first;
    - the hand edit's replaced file is last, with `at None` and source `earlier`;
    - nothing is written under `.training-studio/` by reading: compare the folder listing
      and bytes before and after.
  - `test_one_editing_session_is_one_version`: three saves with `session_token='ab12'` and
    `via='save'` read as one version.
  - `test_a_section_is_followed_across_a_renamed_heading`: a section renamed in one version
    is matched by its covers note.
  - `test_row_136_a_restore_is_a_version`: restoring index 1 saves with `via='restore'`. The
    text it replaced is then the newest version, labelled "Restored" in the page words.
  - `test_row_149_a_google_pull_lands_as_a_version`: with the `Copies` and `Drive`
    stand-ins, a pull saves with `via='google'`. The newest version's source is `google`.
- [ ] **Step 2: Run** `python3 -m unittest test_drafts_history -v` and see them fail.
- [ ] **Step 3: Implement it.**
- [ ] **Step 4: Add matrix rows 136 and 149.**
- [ ] **Step 5: Run** `python3 -m unittest test_drafts_history test_google test_runner_copies -v`
  and see them pass.
- [ ] **Step 6: Commit** "Give every part of a training History from the versions it already
  keeps, Google's text included".

## Task 12: Typed saves, restore and the versions route

**Files:**
- Modify: `studios/training/runner/drafts.py` (`save_part`, `restore_part`, `versions_of`)
- Modify: `studios/training/runner/engine.py` (`draft_save`, `draft_restore`; the commit
  cadence)
- Modify: `studios/training/runner/page.py` (POST `/api/drafts/save`, `/api/drafts/restore`;
  GET `/api/drafts/versions`; POST `/api/drafts/share`)
- Test: `studios/training/tests/test_drafts.py`, `studios/training/tests/test_runner_page.py`

**Interfaces (Produces):**
- POST `/api/drafts/save` `{path, name, part, seen, text, session}` calls `TrainingDesk.save`
  through the store, holding `engine.files`. It returns the card's new view.
  - A stale form gets piece 3's "This draft changed since you opened it. Reload to see the
    latest."
  - A locked part gets "Sources is kept from the findings cited. Change the references in
    the text instead."
- The commit is deferred. `engine.pending_commit[root]` is set. The engine commits it at
  most once a minute, before any job, on any Mark ready, Update or Keep, and on
  `/api/drafts/share`, with the message "edit <label> on the desk".
- POST `/api/drafts/share` `{path}` commits pending edits and shares them under the team's
  share setting. The page sends it when the person leaves the desk.
- POST `/api/drafts/restore` `{path, name, part, seen, index}`.
- GET `/api/drafts/versions?path=&name=&part=`.

- [ ] **Step 1: Write the failing tests:**
  - `test_row_134_a_typed_save_keeps_the_inputs_and_holds_what_is_below`:
    - typing in a guide section saves `document.md` with `via == 'save'`, and its
      `built_from` is unchanged;
    - the guide is accepted on the desk again;
    - a Ready guide reads `draft`;
    - the deck is held.
  - `test_typed_saves_are_committed_together`:
    - three saves within a second give one commit on `/api/drafts/share`, "edit the level
      101 learner guide on the desk";
    - a Mark ready commits pending edits first, in a commit of their own.
  - `test_a_locked_part_cannot_be_typed_in`: saving the Sources part is refused with the
    sentence above.
- [ ] **Step 2: Run** them and see them fail.
- [ ] **Step 3: Implement it.**
- [ ] **Step 4: Add matrix row 134.**
- [ ] **Step 5: Run** `python3 -m unittest test_drafts test_runner_page test_runner_gitstate -v`
  and see them pass.
- [ ] **Step 6: Commit** "Save typing on the desk part by part, and commit it together".

## Task 13: Section, Write again, whole-note and selection jobs

**Files:**
- Create: `studios/training/runner/draft_jobs.py`
- Create: `studios/training/runner/briefs/part.md` (the worker's guidance for one part)
- Modify: `studios/training/runner/briefs/__init__.py` (`guidance('part', …)`)
- Modify: `studios/training/runner/worker_tools.py` (new `check_part` beside `check_document`
  at 501; `submit_part` offered for kind `part`)
- Modify: `studios/training/runner/engine.py`:
  - `_work`: before surveying, a queued desk job runs when no step is under way;
  - new `_draft_job`;
  - `stop_draft`.
- Modify: `studios/training/runner/page.py`: POST `/api/drafts/note`, `/api/drafts/revise`,
  `/api/drafts/selection`, `/api/drafts/stop` and `/api/drafts/retry`.
- Modify: `studios/training/tests/runner_support.py` (`Workers` answers kind `part`)
- Test: `studios/training/tests/test_draft_jobs.py` (new)

**Interfaces (Produces):**
- `draft_jobs.KINDS = ('section', 'write-again', 'revise-all', 'selection', 'update')`.
- `draft_jobs.BUSY = 'A change is already being made to this training. Wait for it, or stop
  it.'`
- `draft_jobs.NEXT = 'Next, after {doing}.'`, with the doing words lower-cased.
- `draft_jobs.begin(engine, root, kind, name, part=None, note=None, seen=None, action=None,
  passage=None, start=None) -> dict`:
  - it refuses `BUSY` when `drafting.basis.busy(job)` holds for any job in
    `run['drafts']['jobs']`;
  - it refuses a stale `seen` with piece 3's per-part sentence;
  - it appends `{'id', 'kind', 'name', 'part', 'note', 'action', 'passage', 'start',
    'basis': fingerprint of the part text, 'status': 'queued', 'at'}` (the last 20 jobs are
    kept);
  - it commits "ask for a change to <label>" and calls `engine.wake(root)`.
- `draft_jobs.work_for(root, found, job) -> pipeline.Work`:
  - **guidance:** `briefs.guidance('part')`, then `drafting.prompts.edit_rule('training
    material')`;
  - **task:** `drafting.prompts.request('NOTE FOR THIS SECTION', note,
    drafting.prompts.SURGICAL_PART, 'Training Studio')`, or
    `drafting.prompts.ACTIONS[action]` with `passage_task`;
  - **inputs:**
    - `section` (its text);
    - `heading`;
    - `covers`;
    - `plan module`, the blueprint module whose objectives the covers name;
    - `neighbours`, the sections before and after;
    - `findings`, each `{number, id, title, summary}`, numbered after the file's highest
      Sources number for those not yet listed;
    - `earlier levels` (`pipeline._earlier`);
  - **prepared artifact:** `{'part': {'kind': 'part', 'name': name, 'part': part, 'file':
    <the material's file>, 'heading': heading, 'findings': numbers}}`.
- `worker_tools.check_part(text, spec) -> (problems, outcomes, warnings, kept)`. It splices
  the part into the file's text and runs:
  - `check_document` or `check_brief` on the result;
  - `checks.citations(..., added=<new paragraphs>)`.

  It refuses with:
  - "Leave Sources as it is: the studio adds the references you use." when the part
    changes a Sources line;
  - "Keep this section's heading exactly: {heading}." for a brief;
  - "Cite only the references you were given: [{n}] is not one of them." for an unknown
    number.
- `Engine._draft_job(root, run, job)` builds a `pipeline.Step(f"draft:{job['id']}",
  'agent', label, doing, stage, name)` and calls `self._job(root, run, step, work)`.
  - On a kept result it calls `drafting.basis.settle(job, apply, home.now)`, where `apply`
    calls `land_part` or `land_selection` and then `TrainingStore.write(..., via=kind)`.
  - The runner then appends a Sources entry for each handed finding the text cites,
    numbered as handed.
  - It records `job['dropped'] = checks.dropped(before, after)` and `job['checks'] =
    guards.flags(before, after)`.
- `revise-all` jobs carry `sections: [ids]` and `done: [ids]`. They run one worker call per
  section, in order, with `drafting.prompts.REVISE_ONE`. `stop_draft(path, job)` lets the
  section under way finish and then marks the job `stopped`.

- [ ] **Step 1: Teach the scripted workers kind `part`.** By default they hand back the
  given section with " Revised." added to its last paragraph, through `submit_part`.
  `then('part', …)` overrides that, as for other kinds.
- [ ] **Step 2: Write the failing tests** in `test_draft_jobs.py`:
  - `test_row_135_a_section_note_changes_only_its_section`:
    - `begin(engine, root, 'section', 'document@101', part=<id>, note='Shorter.',
      seen=<rev>)`, then `to_end`;
    - only that section's text changed;
    - every other part is byte for byte the same;
    - the save event has `via == 'rewrite'`;
    - the old text is the newest version.
  - `test_a_result_for_a_changed_part_is_set_aside` (Review Focus 3):
    - the scripted worker saves typed text into the same part through `/api/drafts/save`
      before it submits;
    - the typed text stays;
    - the job's `problem` is "The draft changed while this was being written. Run it
      again.";
    - no `rewrite` save event exists.
  - `test_one_desk_job_at_a_time`: a second `begin` while the first is queued raises
    `BUSY`.
  - `test_a_desk_job_waits_for_the_start_s_step`: while the start's `brief@101` step is
    under way, the queued job's card says "Next, after writing the level 101 product
    brief." (the step's own doing words, lower-cased).
  - `test_submit_part_keeps_sources_and_headings`: a part that edits a Sources line, and a
    brief part with a changed heading, are each handed back with the sentences above. The
    third try is kept, and the second problem is counted against `SUBMISSIONS`.
  - `test_a_cited_finding_joins_sources`: the worker cites handed finding `[4]`. Sources
    gains the entry `4.` for that finding, and `checks.citations` passes.
  - `test_a_dropped_reference_is_named`: a result without `[2]` gives `job['dropped'] ==
    [2]`. The card's `says` includes "This change dropped reference [2]."
  - `test_the_whole_guide_note_goes_in_order_and_stops`: over three sections, `stop_draft`
    after the first gives one section with `via == 'revise-all'`, two unchanged, and the job
    `stopped`.
  - `test_a_selection_replaces_only_the_passage`: `action='shorten'` on a repeated phrase
    with its `start` changes only the occurrence at `start`.
- [ ] **Step 3: Run** `python3 -m unittest test_draft_jobs -v` and see them fail.
- [ ] **Step 4: Implement it.**
- [ ] **Step 5: Add matrix row 135.**
- [ ] **Step 6: Run** `python3 -m unittest test_draft_jobs test_runner_worker_tools
  test_runner_briefs test_runner_engine -v` and see them pass.
- [ ] **Step 7: Commit** "Rewrite one section, one passage or the whole guide from a note on
  the desk, keeping references and landing only on unchanged text".

## Task 14: Updates from the plan that keep the person's edits

**Files:**
- Modify: `studios/training/runner/pipeline.py`:
  - `document_work` and `brief_work` (1621, 1647): when `run['drafts']['updates']` holds the
    material, they hand in the plan change;
  - `_again`.
- Modify: `studios/training/runner/worker_tools.py` (`check_document`, `check_brief`: an
  `untouched` spec)
- Modify: `studios/training/runner/drafts.py` (`plan_change`, `touched`, `update_preview`)
- Modify: `studios/training/runner/page.py` (GET `/api/drafts/update-preview`)
- Test: `studios/training/tests/test_draft_jobs.py`

**Interfaces (Produces):**
- `drafts.plan_change(root, session, name) -> dict`: `{'before': text, 'after': text,
  'objectives': [ids whose lines changed], 'added': [ids], 'removed': [ids]}`. The plan the
  material was built from is the history file for `built_from[blueprint@level]`.
- `drafts.touched(codec_draft, objectives) -> list[part ids]`: the sections whose covers
  name one of the objectives, or a key point `K<n>.<m>` of `O<n>`.
- `drafts.UPDATE_RULE = 'The plan changed as "plan change" shows. Change only the sections
  that change needs, and copy every other section exactly, word for word.'`
- `check_document` and `check_brief` take `spec['untouched'] = {heading: text}`. A section
  in it whose text changed is handed back with 'Section "{heading}" is not touched by the
  plan change. Copy it exactly.'
- `drafts.update_preview(root, name) -> {'parts': [headings], 'price': str}`. The price uses
  `stops.redone(label, 1, seconds, dollars)` from the material's last try. With no try it is
  "This computer has no record yet of what it costs."

- [ ] **Step 1: Write the failing tests:**
  - `test_an_update_from_the_plan_keeps_the_person_s_edits`:
    - type into section 1 of the guide, then change objective O2 in the plan and
      `engine.update(root, 'document@101')`;
    - the worker is handed `plan change` and `untouched` holding section 1's typed text;
    - section 1 is unchanged after it lands;
    - the save event has `via == 'update'`.
  - `test_an_untouched_section_that_changed_is_handed_back`: a worker that changes an
    untouched section gets the sentence above, with its heading.
  - `test_the_update_preview_names_the_sections_and_the_price`: changing O2 names "When
    capacity holds". The price sentence begins "Drawn again:" with a recorded try, and is
    "This computer has no record yet of what it costs." without one.
- [ ] **Step 2: Run** them and see them fail.
- [ ] **Step 3: Implement it.**
- [ ] **Step 4: Run** `python3 -m unittest test_draft_jobs test_runner_pipeline
  test_runner_worker_tools -v` and see them pass.
- [ ] **Step 5: Commit** "Update a guide or brief from a changed plan by rewriting only the
  sections the change reaches".

## Task 15: Open a finished saved training on the desk

**Files:**
- Modify: `studios/training/runner/drafts.py` (`open_on_desk`)
- Modify: `studios/training/runner/engine.py` (`open_on_desk`)
- Modify: `studios/training/runner/page.py` (POST `/api/drafts/open`)
- Modify: `studios/training/skills/training-studio/scripts/desk/app.js` (`paintTraining` at
  3071: **Open on the desk** on a finished runner training)
- Test: `studios/training/tests/test_drafts.py`, `studios/training/tests/test_desk.py`

**Interfaces (Produces):**
- `drafts.NOT_FINISHED = 'Open it on the desk once it is finished.'`
- `Engine.open_on_desk(path) -> dict`:
  - it refuses `NOT_FINISHED` unless the run is done with nothing waiting;
  - it refuses a training with no run record ("Bring it in first, then open it on the desk
    once it is finished.");
  - it writes `flow: 'desk'` and `opened_on_desk: {'at', 'was': {'review_policy',
    'review_layout'}}` to the run record, keeping its schema;
  - it writes `flow: 'desk'` to the session, and `desk_ready: {name: sha256}` for each
    material that counts as Ready (see below);
  - it commits "open the training on the desk";
  - opening again returns the same view and writes nothing.
- A material counts as Ready on opening when:
  - it is approved `by: 'page'`, with its approval's hash its file's;
  - or it is approved `by: 'review-policy'` and the run's `review_decisions['final']` is
    `by: 'page'`, with a signature equal to `reviews.signature(root, session, run,
    'final')` at opening.

- [ ] **Step 1: Write the failing tests:**
  - `test_row_150_a_finished_training_opens_on_the_desk_as_it_was`:
    - a Step by step training taken `to_end` with every gate approved by the page opens
      with every card `ready`;
    - an Automatic draft training whose final review the page approved opens all `ready`;
    - one approved by policy with no final review opens them `draft`.
  - `test_a_training_still_waiting_cannot_be_opened`: at `gate:document@101`,
    `open_on_desk` raises `NOT_FINISHED` and the run record's bytes are unchanged.
  - `test_opening_twice_writes_nothing_more`: the git log has one "open the training on the
    desk" commit after two calls.
  - `test_an_opened_training_s_scenarios_are_not_held`: after opening, `drafts.held` is
    empty, and no scenario has `practice` in its extras.
  - In `test_desk.py`: `test_a_finished_training_offers_open_on_the_desk`. The finished
    training screen shows **Open on the desk**, and pressing it posts `/api/drafts/open`
    and opens the desk screen.
- [ ] **Step 2: Run** them and see them fail.
- [ ] **Step 3: Implement it.**
- [ ] **Step 4: Add matrix row 150.**
- [ ] **Step 5: Run** `python3 -m unittest test_drafts test_desk test_review_levels -v` and see
  them pass.
- [ ] **Step 6: Commit** "Open a finished training on the desk, keeping what the person
  approved as ready".

## Task 16: The page: part cards, notes, selection edits and History

**Files:**
- Modify: `studios/training/skills/training-studio/scripts/desk/drafts.js`
- Test: `studios/training/tests/test_desk.py`

**Interfaces (Consumes):** `Drafting.kit`'s:
- `part`, `whole`, `typed`, `save`, `flush`, `share`;
- `history`, `compare`;
- `selected`, `selectionBar`;
- `progress`, `job`, `watch`.

**Interfaces (Produces):** `drafts.js` composes them into the Plan, Guide and Brief cards. It
adds:
- the covers chips ("Covers O1, K1.1");
- the locked Sources part, with the line "Kept from the findings cited.";
- each card's "Checked for you" lines: the checks, the citations, `job.checks` and
  `job.dropped`, with **Restore** beside a dropped reference;
- the plan's whole-plan note;
- the scenario card and the Yoodli card. The Yoodli card has its fields under their
  headings, each with **Copy**;
- **Update from the …** with its preview sheet: the sections it touches and the price, then
  **Update** with Cancel.

- [ ] **Step 1: Write the failing page journeys:**
  - `test_a_section_note_is_sent_with_the_part_s_revision`: typing "Shorter." in the
    section's "How should this change?" box and pressing Rewrite sends `POST
    /api/drafts/note` with `{name: 'document@101', part, seen, note: 'Shorter.'}`.
  - `test_typing_saves_a_second_after_the_last_key`: `{timer: 'save'}` after typing sends one
    `POST /api/drafts/save`. Leaving the desk sends `POST /api/drafts/share`.
  - `test_history_compares_and_restores`: a versions answer with three entries shows
    "Rewritten", "Before Google's text" and "An earlier version". Restore sends `POST
    /api/drafts/restore` with `index: 1`.
  - `test_the_selection_bar_offers_five_actions`: selecting text shows Rephrase, Shorten,
    Expand, Fix and Ask…, and Shorten sends the passage with its `start`.
  - `test_a_dropped_reference_offers_restore`: a card `says` with "This change dropped
    reference [2]." shows **Restore** beside it.
  - `test_sources_cannot_be_typed_in`: the Sources part has no text box, and shows "Kept
    from the findings cited."
  - `test_the_update_preview_names_what_changes`: **Update from the plan** opens a sheet
    listing "When capacity holds" and the price. Update and Cancel sit together.
- [ ] **Step 2: Run** `python3 -m unittest test_desk -k section_note -k typing -k history -k
  selection -k dropped -k sources -k preview -v` and see them fail.
- [ ] **Step 3: Implement it.**
- [ ] **Step 4: Run** `python3 -m unittest test_desk -v` and see them pass.
- [ ] **Step 5: Commit** "Edit a training's plan, guide and brief part by part on the desk,
  with notes, selection edits and History".

**Pull request 2 is usable here.** Run the Training Studio suite and open the pull request.

---

# Pull request 3: the deck on the desk

## Task 17: Keep the sections a desk deck change does not reach

**Files:**
- Modify: `studios/training/runner/deck.py` (new `DRAWN_FROM`, `kept_sections`)
- Modify: `studios/training/runner/engine.py` (`_split` at 2271-2366: line 2357 writes
  `sections=kept` on desk runs instead of `sections={}`)
- Test: `studios/training/tests/test_runner_deck.py`

**Interfaces (Produces):**
- `deck.DRAWN_FROM = ('kind', 'title', 'subtitle', 'understand', 'points', 'caveat',
  'source', 'notes', 'sources')`. If piece 5 or piece 2 shipped a core version of
  Presentation's `_kept`, use it with this field list instead.
- `deck.kept_sections(work: Path, earlier: dict, began: dict, whole: dict, built: dict) ->
  dict[str, dict]`. It returns the earlier start's drawn sections whose slide IDs, file
  names and every `DRAWN_FROM` field are the same, in a deck that is otherwise the same
  (keys other than `slides` and `approval`).
  - Each kept file is copied to `drawn/<id>-kept-<folder>.json`.
  - Each entry is marked `{'kept': True, 'round': 0, 'start': began['folder']}`.
- On runs without `flow: 'desk'`, `_split` is unchanged.

- [ ] **Step 1: Write the failing tests:**
  - `test_a_desk_deck_keeps_its_unchanged_sections`: with the Slides stand-in and a
    two-section deck, changing slide 5's `title` in the outline and running `to_end` draws
    one section. The stand-in's draw count goes up by one, and the other section's drawn
    file is byte for byte the earlier one.
  - `test_a_new_brand_or_look_keeps_nothing`: changing the brand's contract hash draws both
    sections.
  - `test_saved_decks_draw_every_section_as_before`: the same title change on a step-by-step
    run draws both.
- [ ] **Step 2: Run** `python3 -m unittest test_runner_deck -k kept -k keeps -k saved_decks
  -v` and see them fail.
- [ ] **Step 3: Implement it.**
- [ ] **Step 4: Run** `python3 -m unittest test_runner_deck test_runner_deck_whole -v` and see
  them pass.
- [ ] **Step 5: Commit** "Keep a desk deck's unchanged sections when what it says changes".

## Task 18: A slide note redraws only its section

**Files:**
- Modify: `studios/training/runner/pipeline.py` (`section_work` at 1999: desk notes as the
  focus; `Deck` survey: a section with waiting notes is `again`)
- Modify: `studios/training/runner/worker_tools.py` (`submit_section`: frozen slides)
- Modify: `studios/training/runner/drafts.py` (`slide_note`, `section_price`)
- Modify: `studios/training/runner/engine.py` (`slide_note`)
- Modify: `studios/training/runner/page.py` (POST `/api/drafts/slide-note`)
- Test: `studios/training/tests/test_drafts_deck.py` (new)

**Interfaces (Produces):**
- `Engine.slide_note(path, level, slide, note, seen) -> dict`:
  - it appends `{'id', 'slide', 'section', 'note', 'at', 'by': 'page', 'status':
    'waiting'}` to `run['deck'][level or '']['notes']`;
  - it refuses a note for a section being drawn with "Slide {n} is being redrawn now. Your
    note is kept here; send it when that ends.";
  - it refuses a stale `seen` (the deck file's hash) with `decide`'s sentence.
- `section_work` hands waiting notes for its section in as `what the person asked`, with the
  task "Draw section {n} again. The person asked for the changes in "what the person
  asked", on the slides it names. Copy every other slide in your section exactly, including
  its drawing." It hands the other slides in as `frozen`.
- `submit_section` refuses a change to a frozen slide with "this slide has no requested
  repair. Keep its drawing unchanged."
- The kept section marks its notes `done`.
- `drafts.section_price(record, level, section) -> str`. It is piece 5's sentence with
  Training's step names: "Redraws section {n} (slides {a} to {b}); the other slides stay
  exactly as they are. Then the deck is put together, rendered and checked. Last time this
  took {cost}." With no record it ends "This computer has no record yet of what it costs.
  Expect minutes, not seconds."

- [ ] **Step 1: Write the failing tests:**
  - `test_row_144_a_slide_note_redraws_its_section_only`:
    - `slide_note(root, '101', 'slide-5', 'Make the diagram larger.', seen)`, then `to_end`;
    - one `section` job runs, whose inputs hold the note and `frozen` names the other
      slides;
    - the other section's drawn file is unchanged;
    - one review runs, of the changed slides only;
    - the deck is `draft` in `person_statuses`.
  - `test_a_frozen_slide_cannot_change`: a scripted composer that changes a frozen slide is
    handed back the sentence above.
  - `test_a_note_on_a_section_being_drawn_waits`: the second note on the same section, while
    it is drawn, raises "Slide 5 is being redrawn now. Your note is kept here; send it when
    that ends."
  - `test_the_price_says_what_it_redraws`: with one recorded `deck-sections@101` try of 200
    seconds and $0.50, the sentence begins "Redraws section 2 (slides 4 to 6); the other
    slides stay exactly as they are."
- [ ] **Step 2: Run** `python3 -m unittest test_drafts_deck -v` and see them fail.
- [ ] **Step 3: Implement it.**
- [ ] **Step 4: Add matrix row 144.**
- [ ] **Step 5: Run** `python3 -m unittest test_drafts_deck test_runner_deck
  test_runner_worker_tools -v` and see them pass.
- [ ] **Step 6: Commit** "Redraw only the section a slide note is about, keeping its other
  slides exactly".

## Task 19: Slide words and speaker notes, patched in place

**Files:**
- Modify: `studios/training/runner/deck.py` (new `patch_section`)
- Modify: `studios/training/runner/drafts.py` (`slide_words`, `slide_speaker_notes`)
- Modify: `studios/training/runner/engine.py` (`slide_words`, `slide_speaker_notes`; `_whole`
  runs with no worker after a patch)
- Modify: `studios/training/runner/page.py` (POST `/api/drafts/slide-words`,
  `/api/drafts/slide-speaker-notes`)
- Test: `studios/training/tests/test_drafts_deck.py`

**Interfaces (Produces):**
- `deck.patch_section(section: dict, slide: str, field: str, old: str, new: str) -> dict`.
  - `field` is one of `title`, `subtitle`, `caveat`, `source`, `notes`, or `points[i].label`
    or `points[i].text`.
  - It raises "The words are not found once on the slide." when `old` is found zero times
    or more than once.
- `Engine.slide_words(path, level, slide, field, text, seen) -> dict`:
  1. it updates `deck/outline.json` and checks it with `deck.rules`;
  2. it patches the drawn section;
  3. it runs the stand-in-reachable `check_section` (`deck.kept` and the compile without
     output);
  4. on success, `_whole` with no worker, then `_keep`.
  - When the words do not fit, nothing is saved. It returns `{'fits': False, 'said': 'These
    words do not fit the slide as it is drawn.', 'price': section_price(...)}`.
- `Engine.slide_speaker_notes(path, level, slide, text, seen)` patches the outline's and the
  section's `notes` together, then runs `_whole` with no worker.

- [ ] **Step 1: Write the failing tests:**
  - `test_row_147_words_that_fit_are_patched_with_no_worker`:
    - a title change on slide 5 starts no worker (`Workers.jobs` unchanged);
    - the outline and the drawn section both hold the new title;
    - the deck is merged and saved.
  - `test_words_that_do_not_fit_save_nothing`: with the Slides stand-in's compile refusing,
    nothing changes on disk and the answer says "These words do not fit the slide as it is
    drawn."
  - `test_row_145_speaker_notes_need_no_worker`: a notes change starts no worker, and
    `deck.kept(section, spec)` returns `[]` afterwards.
  - `test_words_found_twice_are_refused`: `patch_section` with `old` appearing twice raises
    "The words are not found once on the slide."
- [ ] **Step 2: Run** them and see them fail.
- [ ] **Step 3: Implement it.**
- [ ] **Step 4: Add matrix rows 145 and 147.**
- [ ] **Step 5: Run** `python3 -m unittest test_drafts_deck test_runner_deck_whole -v` and see
  them pass.
- [ ] **Step 6: Commit** "Change a slide's words or speaker notes in place when they fit,
  with no redraw".

## Task 20: Update from the guide, scoped by what each slide serves

**Files:**
- Modify: `studios/training/runner/drafts.py` (`slides_for`, `deck_update`)
- Modify: `studios/training/runner/pipeline.py` (`outline_work` names the slides to word
  again; the `Deck` survey reads `asked['slides']`)
- Modify: `studios/training/runner/worker_tools.py` (`check_outline` at 601: other slides
  unchanged)
- Modify: `studios/training/runner/engine.py` (`update` on a deck uses the scope)
- Test: `studios/training/tests/test_drafts_deck.py`

**Interfaces (Produces):**
- `drafts.slides_for(root, session, level, since: str) -> dict`, where `since` is `'document'`
  or `'blueprint'`. It returns `{'slides': [ids], 'sections': [headings], 'whole': bool}`:
  - the guide's (or plan's) parts that changed between the version the deck was built from
    and now are found with `HistoryVersions` and the codec;
  - their covers IDs are mapped to objectives (`K<n>.<m>` is `O<n>`);
  - the slides are those whose `sources` name one of them;
  - `whole` is true when objectives were added or removed.
- `drafts.NO_SLIDE = 'No slide is built from the sections that changed.'`
- Updating a deck sets `kept['asked'] = {'kind': 'revise', 'note': drafts.DECK_UPDATE, 'slides':
  ids, 'at'}`, with `drafts.DECK_UPDATE = 'The guide changed. Word again only the slides in
  "slides to word again", from the guide as it is now, and copy every other slide
  exactly.'`
- `check_outline` with `spec['frozen']` refuses a changed frozen slide with "Slide {n} is not
  one to word again. Copy it exactly."

- [ ] **Step 1: Write the failing tests:**
  - `test_row_148_update_from_the_guide_rewords_only_the_slides_that_serve_it` (Review
    Focus 4):
    - change "When capacity holds" (covers O2 K1.2) and press Update;
    - the outline job is handed the slides whose `sources` include O1 or O2. These are the
      fixture's slide IDs, listed exactly;
    - every other slide is byte for byte the same in `outline.json`;
    - only the sections holding them are drawn.
  - `test_a_glossary_edit_names_no_slide`: a Glossary change gives `slides == []`, and the
    preview says `NO_SLIDE` with only **Keep as it is**.
  - `test_a_new_objective_rewords_the_whole_outline`: adding O4 to the plan gives `whole is
    True`, and the price is the whole deck's.
  - `test_a_frozen_slide_in_the_outline_is_handed_back`: an outline worker that changes a
    frozen slide gets "Slide 3 is not one to word again. Copy it exactly."
- [ ] **Step 2: Run** them and see them fail.
- [ ] **Step 3: Implement it.**
- [ ] **Step 4: Add matrix row 148.**
- [ ] **Step 5: Run** `python3 -m unittest test_drafts_deck test_runner_deck test_runner_pipeline
  -v` and see them pass.
- [ ] **Step 6: Commit** "Update a deck from a changed guide by wording again only the slides
  that serve the sections that changed".

## Task 21: Slide History, Try another look, and the deck card on the page

**Files:**
- Modify: `studios/training/runner/drafts.py` (`DeckStore`, the slide `Versions`,
  `look_samples`, `look_apply`)
- Modify: `studios/training/runner/engine.py` (`look_samples`, `look_apply`)
- Modify: `studios/training/runner/page.py` (GET `/api/drafts/slide-versions`; POST
  `/api/drafts/slide-restore`, `/api/drafts/look-samples`, `/api/drafts/look`)
- Modify: `studios/training/skills/training-studio/scripts/desk/drafts.js` (the deck card:
  piece 5's slide card with Training's routes)
- Test: `studios/training/tests/test_drafts_deck.py`, `studios/training/tests/test_desk.py`

**Interfaces (Produces):**
- Slide words are kept with piece 3's `Versions` over `DeckStore`, whose `folder` is
  `<level>/deck/versions/` (shared). The sources are piece 5's: `save`, `selection`, `note`,
  `redraw`, `restore`, `outline`, `finishing`, `open`, plus Training's `update`.
- Drawings are kept in `<level>/work/deck/versions/<slide-id>/<at>.json` and `.png`, which
  are not shared.
- Restore is piece 5's: with the drawing, the composition goes back with no worker; without
  it, by the word chain (Task 19).
- `Engine.look_samples(path, level)` runs `deck-look` again. `Engine.look_apply(path, level,
  choice, seen)` records the pick and redraws the deck. The sheet's price is
  `deck.before(slides)` or the last whole draw (`stops.redone`).

- [ ] **Step 1: Write the failing tests:**
  - `test_row_146_another_look_redraws_the_whole_deck`: after `look_apply`, every section is
    drawn again and the deck is `draft`.
  - `test_a_slide_keeps_its_words_and_drawing_as_versions`: a words change keeps one version
    under `deck/versions/` and one drawing under `work/deck/versions/`. Restore puts both
    back with no worker.
  - In `test_desk.py`: `test_the_deck_card_has_a_card_per_slide`. The deck answer shows the
    slide titles, "How should this slide change?" with **Redraw slide 5**, the price line,
    and **Try another look**. On a teammate's computer it has words only, with **Draw it
    here**.
- [ ] **Step 2: Run** them and see them fail.
- [ ] **Step 3: Implement it.**
- [ ] **Step 4: Add matrix row 146.**
- [ ] **Step 5: Run** `python3 -m unittest test_drafts_deck test_desk -v` and see them pass.
- [ ] **Step 6: Commit** "Show each slide on the desk with its History, and let the person try
  another look".

**Pull request 3 is usable here.** Run the Training Studio suite and open the pull request.

---

# Pull request 4: Add a source

## Task 22: Add a source as a priced research update

**Files:**
- Modify: `studios/training/runner/drafts.py` (`add_source`, `source_price`, `marked`)
- Modify: `studios/training/runner/engine.py` (`add_source`; `supply` keeps `SETTLED` for the
  start's documents step only)
- Modify: `studios/training/runner/page.py` (GET `/api/drafts/source-price`; POST
  `/api/drafts/source` with `{path, files: [{name, content (base64)}]}`)
- Modify: `studios/training/skills/training-studio/scripts/desk/drafts.js` (the Add a source
  sheet: "1. Add", "2. What it changes", then **Update the research** and Cancel)
- Test: `studios/training/tests/test_drafts_sources.py` (new), `studios/training/tests/test_desk.py`

**Interfaces (Produces):**
- `drafts.AFTERWARDS = 'Afterwards each level's plan and brief, and any deck without a
  guide, say what changed. Nothing else is rewritten until you update it.'`
- `drafts.WIDENED = 'This training is researched from the public web. From now on it reads
  your documents too.'`
- `drafts.source_price(root, record) -> dict`: `{'words': research_view.price(attempts,
  redone=())['words'], 'afterwards': AFTERWARDS, 'widened': WIDENED or None}`.
- `Engine.add_source(path, files) -> dict`. It refuses `draft_jobs.BUSY` while anything runs.
  Then, holding `engine.files`:
  1. each file is added with `documents.add`;
  2. a public-web-only run gets `record['documents'] = {'scope': 'mixed', 'done': now,
     'count': n}`, and its `research_from` gains documents with `widened_at`;
  3. `run['drafts']['findings_before'] = {id: fingerprint}` is recorded;
  4. `workspace.decide(root, 'research', 'revise', note, by='page')` is called, with the
     note "Sources were added: {titles}. Read them, and update what they change. Keep
     everything else.";
  5. `record['research']['again']` is set as `decided` sets it;
  6. it commits "add {n} source(s) and update the research", and calls `carry_on`.
- `drafts.marked(root, record) -> {id: 'new' | 'changed'}` for the Sources panel.

- [ ] **Step 1: Write the failing tests:**
  - `test_row_143_a_source_added_after_research_updates_it`:
    - after `to_end` on a desk training, `add_source` with one text file runs the research
      step once more (the research stand-in's call count goes up by one), and its sources
      include the file;
    - afterwards `drafts.held` holds every level's `blueprint`, and any `brief`;
    - nothing else is remade.
  - `test_a_public_web_training_reads_documents_too`: a public-web-only run's record has
    `documents.scope == 'mixed'` and `research_from` with `widened_at`. The price's `widened`
    is `WIDENED`.
  - `test_findings_are_marked_new_or_changed`: with the stand-in returning one new finding
    and one with a changed summary, `marked` gives one of each.
  - `test_nothing_is_added_while_a_change_is_made`: with a desk job queued, `add_source`
    raises `BUSY` and the documents list is unchanged.
  - In `test_desk.py`: `test_add_a_source_says_its_price_first`. The sheet has the steps "1.
    Add" and "2. What it changes", shows the price words and `AFTERWARDS`, and sends `POST
    /api/drafts/source` only on **Update the research**.
- [ ] **Step 2: Run** `python3 -m unittest test_drafts_sources -v` and see them fail.
- [ ] **Step 3: Implement it.**
- [ ] **Step 4: Add matrix row 143.**
- [ ] **Step 5: Run** `python3 -m unittest test_drafts_sources test_runner_research
  test_runner_documents test_desk -v` and see them pass.
- [ ] **Step 6: Commit** "Add a source after research as a priced research update that holds
  what it reaches".

## Task 23: Update everything below, and Update every level

**Files:**
- Modify: `studios/training/runner/drafts.py` (`update_all`, `chain_price`)
- Modify: `studios/training/runner/engine.py` (`update_all`, `stop_updates`)
- Modify: `studios/training/runner/page.py` (POST `/api/drafts/update-all`,
  `/api/drafts/stop-updates`)
- Modify: `studios/training/skills/training-studio/scripts/desk/drafts.js` (the Plan card's
  **Update everything below**; the Sources panel's **Update every level**)
- Test: `studios/training/tests/test_drafts_sources.py`

**Interfaces (Produces):**
- `Engine.update_all(path, level=None) -> dict` records an update for every held name of
  that level (every level when None), in `drafts.ORDER`, with one `chain` ID. The survey runs
  them in pipeline order.
- `stop_updates(path, chain)` drops the updates not yet started. The one under way finishes.
- `drafts.chain_price(root, record, names) -> str` is the sum of each name's last try, said
  with `stops.cost`.

- [ ] **Step 1: Write the failing tests:**
  - `test_update_every_level_runs_level_by_level`: after Add a source, `update_all(root)`
    remakes 101's plan, guide and brief before 201's, and leaves nothing held.
  - `test_stop_leaves_the_rest_held`: `stop_updates` after the first plan lands leaves the
    others held and `run['drafts']['updates']` empty.
- [ ] **Step 2: Run** them and see them fail.
- [ ] **Step 3: Implement it.**
- [ ] **Step 4: Run** `python3 -m unittest test_drafts_sources test_drafts -v` and see them pass.
- [ ] **Step 5: Commit** "Update everything a change held, level by level, with Stop".

**Pull request 4 is usable here.** Run the Training Studio suite and open the pull request.

---

# Pull request 5: Finishing

## Task 24: Finishing in process: proofread, coverage, claims, scenario format, Yoodli limits

**Files:**
- Create: `studios/training/runner/draft_finish.py`
- Modify: `studios/training/runner/page.py` (POST `/api/drafts/finish`, `/api/drafts/apply`,
  `/api/drafts/skip`; GET `/api/drafts/proofread`)
- Modify: `studios/training/skills/training-studio/scripts/desk/drafts.js` (the kit's
  `tools`)
- Test: `studios/training/tests/test_draft_finish.py` (new)

**Interfaces (Produces):**
- `draft_finish.TOOLS`, each a piece 3 tool `{key, name, says, run, doing}`:
  - `proofread`, "Proofread": "Mechanical checks, sentence by sentence. Fix rewrites only
    that sentence."
  - `coverage`, "Coverage": "Objectives and key points no section teaches."
  - `claims`, "Claims with no reference": "Sentences that state a fact with no reference."
  - `practice`, "Scenario format": "What each scenario is missing for Yoodli."
  - `yoodli`, "Yoodli limits": "Fields over Yoodli's limits."
- `draft_finish.proposals(engine, root)` is `drafting.proposals.Proposals(TrainingStore,
  TrainingDesk, TOOLS, owner='training')`.
- In-process tools return their findings at once, with no job:
  - proofread uses `drafting.proofread.check` with `studio_core.text_checks`' rules;
  - coverage uses `checks.document_coverage`;
  - claims uses `checks.citations`;
  - scenario format uses `checks.check_scenario`;
  - Yoodli limits uses `checks.check_yoodli`.

  **Apply** on a proofread finding is a `selection` job with `fix`. On a coverage, claims or
  Yoodli finding it opens that part's note prefilled ("Teach O2 here.", "Add the reference
  for this, or cut it.", "Bring this field under {n} characters.").

- [ ] **Step 1: Write the failing tests:**
  - `test_coverage_names_an_objective_no_section_teaches`: removing O2 from every covers note
    gives the proposal "O2 is not taught by any section."
  - `test_row_153_applying_a_proposal_keeps_a_version`: applying a proofread fix saves with
    `via == 'finishing'`, and a skipped item is unchanged.
  - `test_a_proposal_for_a_changed_part_is_refused`: a part typed into after the proposal was
    made refuses Apply with piece 3's sentence, and nothing changes.
- [ ] **Step 2: Run** `python3 -m unittest test_draft_finish -v` and see them fail.
- [ ] **Step 3: Implement it.**
- [ ] **Step 4: Add matrix row 153.**
- [ ] **Step 5: Run** it again and see it pass.
- [ ] **Step 6: Commit** "Offer Finishing checks on the desk that propose a change, with
  nothing changed until Apply".

## Task 25: Finishing jobs: check against sources, fit the time, the answer key, humanize, the level

**Files:**
- Modify: `studios/training/runner/draft_finish.py`
- Modify: `studios/training/runner/draft_jobs.py` (kinds `finish-sources`, `finish-time`,
  `finish-answers`, `finish-humanize`, `finish-level`)
- Create: `studios/training/runner/briefs/finish-sources.md`, `finish-time.md`,
  `finish-answers.md`, `finish-humanize.md`, `finish-level.md`
- Modify: `studios/training/tests/runner_support.py` (`Workers` answers the five kinds with
  one proposal each)
- Test: `studios/training/tests/test_draft_finish.py`

**Interfaces (Produces):**
- Each job hands back JSON read with `drafting.proposals.read_result`: `[{part, quote,
  replacement, reason, verdict?}]`.
  - `finish-sources` adds `verdict` (`supported`, `not in the sources`, `contradicted`) and
    `finding`. It reads the research record and runs no research.
  - `finish-time` reads the intake's Time and proposes cuts or additions per section.
  - `finish-answers` proposes, for each answer, why it is right and why a plausible
    alternative is wrong.
  - `finish-humanize` takes `level` (`light`, `medium`, `strong`) and keeps every `[n]`.
  - `finish-level` names each passage that teaches what `_earlier` says an earlier level
    taught.
- Each is priced before it runs with `step_times.expected` and its guess (2 minutes).

- [ ] **Step 1: Write the failing tests:**
  - `test_check_against_sources_marks_each_claim`: a scripted result with one `contradicted`
    claim gives a proposal with that verdict and its finding's title.
  - `test_humanize_keeps_references`: a scripted proposal that drops `[1]` is shown with
    piece 3's guard line and `dropped == [1]`, and is still offered.
  - `test_a_finishing_job_is_one_desk_job`: starting one while a section note is queued
    raises `BUSY`.
- [ ] **Step 2: Run** them and see them fail.
- [ ] **Step 3: Implement it.**
- [ ] **Step 4: Run** `python3 -m unittest test_draft_finish test_draft_jobs test_runner_briefs
  -v` and see them pass.
- [ ] **Step 5: Commit** "Add Finishing jobs that check a training against its sources, its
  time, its answer key and its levels".

**Pull request 5 is usable here.** Run the Training Studio suite and open the pull request.

---

# Pull request 6: docs

## Task 26: Docs

**Files:**
- Create: `studios/training/docs/the-desk.md`. It covers the start, progress, the desk,
  notes, selection edits, History, the deck, holds and updates, Add a source, Mark ready,
  Finishing, teammates, and Open on the desk.
- Move: `studios/training/docs/desk.md` to `studios/training/docs/page.md` (`git mv`). Update
  every link to it: README, `docs/runner.md`, `docs/how-it-works.md`, `docs/development.md`,
  and the skill's references if any.
- Modify: `studios/training/README.md`. A new user starts on the desk. Review levels are
  mentioned only as "trainings started before the desk".
- Modify: `studios/training/docs/runner.md`:
  - a desk section;
  - review levels for saved runs;
  - remove "Bringing edits back from a Google Doc … are not in the runner yet." (line 348),
    since piece 1 and Task 11 make it true.
- Modify: `studios/training/docs/how-it-works.md` (desk runs: no stops, holds, Mark ready)
- Modify: `studios/training/docs/development.md` (the `drafts` modules and their tests; the
  naming rule)
- Modify: `studios/training/docs/superpowers/plans/2026-10-12-training-studio-core-pipeline.md`.
  Check that rows 131 to 154 are all there, each naming its test.

- [ ] **Step 1: Write the docs.** Use plain short sentences and the full product names.
  Never write "artifact", "stale" or "lineage" in a person-facing doc.
- [ ] **Step 2: Check them:**
  - `cd studios/training && python3 skills/training-studio/scripts/validate_package.py`;
  - `cd studios/training/tests && python3 -m unittest test_package test_disclosure -v`;
  - `grep -rn "docs/desk.md" studios/training` finds nothing.
- [ ] **Step 3: Check the matrix:** `grep -c "Covered by \`test_row_1[3-5][0-9]_"
  studios/training/docs/superpowers/plans/2026-10-12-training-studio-core-pipeline.md`
  counts at least 24 rows. Each named test exists: `grep -rn "def test_row_1[3-5][0-9]_"
  studios/training/tests`.
- [ ] **Step 4: Commit** "Describe the training desk, and rename the page's doc so the desk
  and the page are not confused".

## Task 27: The full check

- [ ] **Step 1:** `python3 studios/training/scripts/ci/run_tests.py`. Everything passes.
- [ ] **Step 2:** `cd studios/presentation/tests && python3 -m unittest discover -v`. Core and
  `network.py` changed under it.
- [ ] **Step 3:** `python studios/blog/scripts/ci/run_tests.py` and `node
  studios/blog/scripts/ci/check-management.cjs`. These cover `network.py`, `packaging.py`
  and the shared `drafting.js` link.
- [ ] **Step 4:** `PYTHONPATH=.:tests python -m unittest`.
- [ ] **Step 5:** on macOS, the shared Tart runner: `studios/training/scripts/ci/tart-macos.sh`.
- [ ] **Step 6: Walk the desk** in a disposable data folder (`TRAINING_STUDIO_DATA` and
  `STUDIOS_CONFIG` set to a new temporary folder) with the stand-ins, at desktop and phone
  widths. Check:
  - one filled button on each screen;
  - the lede;
  - no forbidden word;
  - controls at least 44px.

  Start no provider, Google or assistant job, and touch no real studio state.
- [ ] **Step 7:** record the commands and their results in the pull request description,
  with no machine-specific paths or credentials.
