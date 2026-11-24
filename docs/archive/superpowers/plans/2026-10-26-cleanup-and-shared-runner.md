# Piece 2, cleanup and the shared runner: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** delete what no screen or command reaches, correct the stale docs, make the four
saved-work paths retirable (Start refuses without synthesis; `studio saved-work` says who
still needs each path), and move the runner modules Presentation Studio and Training Studio
both copy into `core/studio_core/shared_runner/`, with each studio still runnable on its own
and no saved format changed.

**Architecture:** deletions first, so less code moves. One new core module,
`core/studio_core/saved_work.py`, words the scan; each runner's engine finds what needs each
path with its own readers. The shared runner is a new core package. Whole modules
(`brand_source`, `companion`, `research`, `agents`, `brand`, `team`, `gitstate`,
`documents`) live there once, loaded per product by `for_product` over
`studio_core.modules.fresh_module`, and each `runner/<name>.py` becomes a facade that puts
the shared module in its place in `sys.modules`. The common parts of `page`, `settings`,
`setup`, `slides`, `upkeep` and `worker_tools` live there too and are bound into the studio
module with `studio_core.modules.bind`, which rebuilds each function with the studio
module's globals, so every constant and every test patch still applies.

**Tech Stack:** Python 3.11 standard library; plain JavaScript pages with no build step;
`unittest`; Blog Studio's `check-management.cjs` journeys; the deck studios'
`page_harness.js`.

**Spec:** `docs/superpowers/specs/2026-10-26-cleanup-and-shared-runner-design.md`. Read it
with this plan, and the findings it cites in
`docs/superpowers/specs/2026-10-26-workflow-audit/`.

**Before starting:** piece 1 has merged. Re-read every file and line named here on piece 1's
merge; line numbers are at cc53056. Where a task quotes page words, find the control by the
function named, not by its words. Run the definition comparison again before each
shared-runner task (Task 14 adds it as `scripts/compare_runner.py`): piece 1 may have
changed either copy.

## Global Constraints

- Pieces are built in order (1 to 6), each merged before the next starts. Line references are at
  main cc53056: re-read every named file on the piece's own base first. Training matrix row
  numbers named here are a guide; each new row takes the next free number on that base.
- Python 3.11 or newer, standard library only; no frontend build step.
- Full product names in code, docs and commits: Marketing Studio, Blog Studio,
  Presentation Studio, Training Studio, Harness Research, Harness Slides.
- Person-facing sentences never say "artifact", "stale" or "lineage".
- Research and slide building stay delegated to Harness Research and Harness Slides.
- Presentation Studio names no brand (`tests/test_no_brand_named.py`).
- No saved format changes by a byte: run records, session files, published tags, the
  workspace `README.md`, ignore lines and `hub.json`, the documents index, `runner.json`,
  the upkeep record. Each move pins them first.
- Each studio stays runnable on its own: `studio_core` is the symlink
  `skills/<studio>/scripts/studio_core`; nothing in a studio reaches into another studio.
- No shared-runner file names a product, an item word or a data variable.
- `main` is live. A guidance change that needs a script change raises `minimum_runtime` in
  that studio's `guidance/manifest.json` and its `VERSION` together. This plan changes no
  guidance that needs a script; wording-only guidance passes `validate_package.py`
  (Presentation, Training) or `python3 studios/blog/scripts/measure_guidance.py --check`.
- Training Studio: a change to status, approval, inputs or readiness adds a row to section
  A7 of `studios/training/docs/superpowers/plans/2026-10-12-training-studio-core-pipeline.md`
  and a `test_row_NN` test. Next row at cc53056: 131; take the next free one on the base.
- Tests use disposable settings, workspaces, Git identities and data folders
  (`PRESENTATION_STUDIO_DATA`, `TRAINING_STUDIO_DATA`, `STUDIOS_CONFIG`, `HOME`), stand-ins
  and scripted workers. No provider, Google or assistant job runs.
- Commands. Root: `PYTHONPATH=.:tests python3 -m unittest <module>` from the repository
  root, all of it with `PYTHONPATH=.:tests python3 -m unittest discover -s tests`.
  Presentation: `cd studios/presentation/tests && python3 -m unittest <module> -v`, all of
  it with `python3 studios/presentation/scripts/ci/run_tests.py`. Training:
  `cd studios/training/tests && python3 -m unittest <module> -v`, all of it with
  `python3 studios/training/scripts/ci/run_tests.py`. Blog:
  `python3 studios/blog/scripts/ci/run_tests.py` and
  `node studios/blog/scripts/ci/check-management.cjs`.
- Commit messages are plain sentences; end each with the attribution line the session
  gives.

## Review Focus

1. A bound function that reads a name the studio module lacks fails only when it is called.
   `modules.unresolved` must walk every bound function and method, nested code and
   comprehensions included (Task 14), and each studio's `test_shared_runner_use` must run it.
2. Published tags, the workspace `README.md`, ignore lines and `hub.json`, the documents
   index and `runner.json` are pinned before their module moves and are byte-identical after
   (Tasks 20, 21, 22, 24).
3. Start without synthesis creates nothing: no folder, record, remembered item or commit. A
   deck without research still starts; a run brought in from a conversation is not refused
   (Tasks 8, 9).
4. `worker_tools` still starts as a script by its path under `python -I` and finds its
   shared parts; the existing test that starts the tools server by path passes (Task 28).
5. One module object per name: `sys.modules['runner.team'] is runner.team`, another shared
   module's `from runner import team` gets the same object, and a test's patch on it reaches
   every caller (Tasks 14, 20).

---

## Task 1: Blog Studio's old intake screens go

**Files:**
- Modify: `studios/blog/skills/blog-studio/assets/management/runner.js`
- Modify: `studios/blog/scripts/ci/check-management.cjs`

- [ ] **Step 1: Move the one case worth keeping.** In `check-management.cjs`, add a journey
  `deskStartReopensALinkedDoc` beside the desk-start journeys. It is the "already linked
  Doc reopens" case of `googleReopening` (`:486-528`), on the desk start: `sDeskReadGoogle`
  (`desk.js:189-197`) with `held.url` set and the fixture answering `/api/google-preview`.
  For `{status:'already-linked', id:'existing', ...}` with `/api/desk?id=existing` answering
  a desk view, `studio.screen` ends `'desk'` with `studio.id === 'existing'` and no request
  went to `/api/desk-create`. For the malformed answers `googleReopening` used
  (`{status:'already-linked'}` with no id, `{status:'unrecognized'}`, a preview with no
  `summary`), the start shows `sGooglePreview`'s card and nothing throws. Run it on the
  unchanged page. Expected: pass.
- [ ] **Step 2: Add the address test.** Journey `oldIntakeAddressesOpenTheDeskStart`: for
  each of `?screen=polish`, `?screen=draft` and `?screen=google`, `studioNavigate(screen)`
  ends with `studio.screen === 'desk-start'` and `location.search === '?screen=desk-start'`.
  Run it. Expected: fail (the three screens still open).
- [ ] **Step 3: Delete.** In `runner.js`: `sPolishIntake` (`:359-400`), `sGooglePage`
  (`:142-180`), `sGoogleResult` (`:133-141`), `sGoogleButton` (`:125-127`); keep
  `sGooglePreview`. In `studioNavigate`, send `google`, `draft` and `polish` to `desk-start`
  the way `new` is sent (`:104`), and take the three names out of the screen list (`:105`),
  the three `else if` branches (`:114-116`) and the poll skip list in `sPoll` (`:315`). In
  `check-management.cjs`, delete the rest of `taskJourneys` from `:459`, `googleReopening`,
  `googleIntake` (with its `sGoogleButton` checks at `:566-580`) and the `sRoute('polish')`
  navigation at `:289-290`, and their calls.
- [ ] **Step 4: Check nothing else calls them.** `grep -n "sPolishIntake\|sGooglePage\|sGoogleResult\|sGoogleButton\|'polish'\|'draft'" studios/blog/skills/blog-studio/assets/management/*.js studios/blog/scripts/ci/check-management.cjs`
  lists no caller; a hit on `'draft'` that is a stage name stays.
- [ ] **Step 5: Run** `node studios/blog/scripts/ci/check-management.cjs` and
  `python3 studios/blog/scripts/ci/run_tests.py`. Expected: pass.
- [ ] **Step 6: Commit** "Remove Blog Studio's old Polish and Google Doc intake screens; their
  addresses open the desk start".

## Task 2: The upload's `as_blog` server branch goes

Piece 1 already turned the Upload one file tick into "Then edit it on the desk" and stopped
the page sending `as_blog`. Keep that tick; remove only the server side.

**Files:**
- Modify: `studios/blog/skills/blog-studio/scripts/management.py`
- Modify: `studios/blog/skills/blog-studio/assets/management/runner.js` (only if piece 1 left
  `as_blog:false` in the voice-sample upload)
- Modify: `studios/blog/tests/test_editorial_tools.py`, `test_team_library.py`
- Modify: `studios/blog/docs/editorial-desk.md`, `studios/blog/docs/runner.md`

- [ ] **Step 1: Write the failing test.** In `test_editorial_tools.py`, add
  `test_an_upload_that_asks_to_start_a_blog_is_refused`: `management.upload(root,
  {'operation': ..., 'filename': 'draft.md', 'content': <base64 of "# Title\n\nText">,
  'title': 'Draft', 'purpose': 'reference', 'as_blog': True})` raises `ValueError` with
  "Unknown upload field." Run it. Expected: fail.
- [ ] **Step 2: Remove the server branch.** `management.py`: `'as_blog'` from the allowed
  set, the two checks, and the branch that makes a manuscript-editor blog. Remove any helper
  left without a caller (check with grep). Drop `as_blog:false` from the voice-sample upload
  in `runner.js` if it is still there.
- [ ] **Step 3: Fix the tests that sent it.** Drop `'as_blog': False` where tests send it.
  Tests that send `as_blog: True` to build a fixture blog build it the way the desk tests do
  (`desk.create` in `tests/test_desk_start.py`); tests about the editor blog the upload made
  are deleted.
- [ ] **Step 4: Docs.** `editorial-desk.md` and `docs/runner.md` stop describing "Start an
  editable blog": Upload one file summarizes and tags a file, or opens it on the desk start.
- [ ] **Step 5: Run** `python studios/blog/scripts/ci/run_tests.py` and
  `node studios/blog/scripts/ci/check-management.cjs`. Expected: pass.
- [ ] **Step 6: Commit** "Remove the upload's old way to start a blog from the server".

## Task 3: `run-create`, the `stop` default and `source-keep` go

**Files:**
- Modify: `studios/blog/skills/blog-studio/scripts/management.py`, `blog_runner.py`
- Modify: `studios/blog/tests/test_blog_runner.py`, `test_voice_switch.py`,
  `test_desk_start.py`, `test_team_library.py`
- Modify: `studios/blog/scripts/ci/check-management.cjs`

- [ ] **Step 1: Write the failing tests.** In `test_blog_runner.py`:
  `test_the_page_has_no_run_create_route`: an authenticated POST to `/api/run-create`
  through the test server answers 404, as any unknown route does.
  `test_writing_defaults_have_no_stop`: `'stop' not in blog_runner.DEFAULTS`, and
  `blog_runner.settings(root)['defaults']` from a saved `.blog-run-settings.json` holding
  `"stop": "draft"` has no `stop`. `test_the_page_has_no_source_keep_route`: POST
  `/api/source-keep` answers 404. Run. Expected: fail.
- [ ] **Step 2: Remove `run-create`.** `management.py:2154-2155` (the route and its
  voice-switch check) and `'run-create'` in the tuple at `:2272`. `blog_runner.py`: the
  `create` branch of `dispatch` (`:3163-3177`) and the `.blog-runs/creations` ledger it
  writes; the fields `review_level`, `review_seen`, `review_default` and their checks
  (`:1237-1239`, `:1245-1253`, `:1498-1501`, `:1527-1529`). Keep `create()` itself: the CLI's
  `run create` calls it. Check with grep that `creations` has no other reader.
- [ ] **Step 3: Remove `stop`.** `DEFAULTS['stop']` (`:103`) and its check (`:499-500`).
  `create()` keeps `data.get('stop', 'package')` (`:1290`); that is the CLI's.
  `check-management.cjs:442,530` fixtures drop `stop`.
- [ ] **Step 4: Remove `source-keep`.** The route at `management.py:2001-2002`. Keep the
  function `source_keep` (`desk.py:949` calls it).
- [ ] **Step 5: Move or delete the tests.** Delete
  `test_a_blog_keeps_the_level_its_form_chose`,
  `test_the_default_is_written_only_with_the_chip_and_refused_when_stale`,
  `test_an_unreadable_shared_file_still_starts_a_blog_at_its_level`
  (`test_blog_runner.py:1303-1360`), the `dispatch('create')` runner case (`:476-477`) and
  `test_voice_switch.py:285-287`. `test_read_only_hub_cannot_start_page_work` (`:692-695`)
  checks a route that still exists instead (`desk-create`).
  `test_authenticated_http_pipeline_completes_all_gates` (`:710-744`) starts its run with
  the CLI's `blog_runner.create` and keeps every gate check. `test_desk_start.py:1023-1028`
  and `test_team_library.py:1934,1963` call `management.source_keep` directly. Delete the
  dead `/api/run-create` fixture mocks in `check-management.cjs:451,1638,2697`; keep the
  "never called" asserts at `:561` and `:3101`.
- [ ] **Step 6: Comments.** `blog_runner.py:1245-1246` goes with the fields. Rewrite
  `blog_runner.py:396` ("a start form says") and `:2843` ("the wizard still opens"),
  `management.py:826` and `:924`, and `test_blog_runner.py:2198` to say what the code does
  now, without naming a removed screen.
- [ ] **Step 7: Run** both Blog commands. Expected: pass.
- [ ] **Step 8: Commit** "Remove the page's run-create and source-keep routes and the unused
  stop default".

## Task 4: Blog Studio's unused page code, rules and provenance pin go

**Files:**
- Modify: `studios/blog/skills/blog-studio/assets/management/runner.js`, `app.js`,
  `blog.css`
- Delete: `studios/blog/skills/blog-studio/assets/management/training-studio-ui.json`
- Modify: `studios/blog/skills/blog-studio/references/package-notes.md`
- Modify: `studios/blog/scripts/ci/check-management.cjs`

- [ ] **Step 1: Write the failing check.** Journey `noUnusedPageParts`: `typeof sBrandNotice
  === 'undefined'`, `typeof renderRun === 'undefined'`, `views.runs === undefined`, and every
  `BLOG_MODES` entry has length 2. Run. Expected: fail.
- [ ] **Step 2: Delete.** `sBrandNotice` (`runner.js:325-329`) and the Home brand poll that
  feeds only it (`:322`; keep any other use of `studio.brand` found by grep). `renderRun`
  (`:311`); `check-management.cjs:1332,1335` call `sRun(found)` after setting
  `studio.screen='run'`. `views.runs` (`app.js:48`) and the `view==='runs'` branch
  (`app.js:230`), with `renderRuns` if it is then unused. The third field of each
  `BLOG_MODES` entry (`runner.js:5`).
- [ ] **Step 3: Delete the CSS.** In `blog.css`: `.studio-hidden-controls`, `.blog-search`,
  `.stage-link` (both rules), `.file-actions`, `.review-compare`, `.empty-invite`,
  `.blog-facts`, `.manuscript-original`, `.editor-suggestions`, `.finish-summary`. Keep
  `.view-library`: `app.js:242` builds `'view-'+view`. Before each, grep the class in
  `assets/management/`, `scripts/` and the journeys, and grep for a prefix that could build
  it (`'stage-'+`, `'file-'+`, `'review-'+`, `'empty-'+`, `'blog-'+`, `'editor-'+`,
  `'finish-'+`, `'manuscript-'+`); a hit keeps the rule.
- [ ] **Step 4: The pin.** `git rm` `training-studio-ui.json`. `references/package-notes.md:26`
  says the page's stylesheet and Markdown renderer are Marketing Studio's `ui-kit`, linked
  in as `style.css` and `markdown.js`. Keep `training-studio-LICENSE.txt`. Run
  `python3 studios/blog/scripts/measure_guidance.py --check`.
- [ ] **Step 5: Run** both Blog commands. Expected: pass.
- [ ] **Step 6: Commit** "Remove Blog Studio page code and styles nothing uses, and the
  retired UI pin".

## Task 5: Presentation Studio's dead code, and one name for the Markdown renderer

**Files:**
- Modify: `studios/presentation/skills/presentation-studio/scripts/desk/app.js`, `deck.css`
- Modify: `studios/presentation/runner/worker_tools.py`, `brand.py`, `steps/build.py`
- Modify: `studios/presentation/tests/test_runner_brand.py`, `test_step_build.py`,
  `test_page_app.py`
- Modify: `ui-kit/markdown.js`; every reader of `window.TrainingStudioMarkdown`
  (`studios/training/skills/training-studio/scripts/desk/app.js`,
  `studios/blog/skills/blog-studio/assets/management/runner.js`, `desk.js`,
  `studios/blog/scripts/ci/check-management.cjs`)

- [ ] **Step 1: Write the failing test.** `test_page_app.py`
  `test_the_page_reads_the_shared_renderer_by_its_own_name`: `app.js` contains
  `window.StudioMarkdown` and not `TrainingStudioMarkdown`; `ui-kit/markdown.js` (through
  `scripts/desk/markdown.js`) sets `window.StudioMarkdown`. Run. Expected: fail.
- [ ] **Step 2: Page.** Delete `asksFor()` (`app.js:3138-3152`), the `found.at === 'later'`
  branch (`:3685-3686`: draw the `offscreen` span alone), the duplicate section comment
  (`:6912-6914`), and inline `firstDraftChoice()` (`:2873`) and `siteShown()` (`:2977`) at
  their callers. `deck.css:25-32`: the `bead-stage[data-state="later"]` and `.bead-later`
  rules with their comment.
- [ ] **Step 3: Runner.** Delete `worker_tools.as_kept` (`:497`; Training's copy stays, it is
  used), `brand.Brand.look_status` (`:422-425`) with
  `test_runner_brand.py:808`'s test, and `steps/build.guided` (`:529`) with the
  `test_step_build.py` tests at `:202-224` that only call it. Keep `guided_reading`.
- [ ] **Step 4: The renderer's name.** `ui-kit/markdown.js:358` sets `window.StudioMarkdown`.
  Replace every `window.TrainingStudioMarkdown` that `grep -rn TrainingStudioMarkdown --
  studios ui-kit core tests` finds (page scripts, `check-management.cjs`, `test_page_app.py`,
  page harnesses). Do not keep the old name.
- [ ] **Step 5: Run** Presentation's whole suite, Training's `test_desk`, and both Blog
  commands. Expected: pass.
- [ ] **Step 6: Commit** "Remove Presentation Studio code nothing calls, and give the shared
  Markdown renderer a name of its own".

## Task 6: The rehearsal placeholder goes

**Files:**
- Modify: `studios/presentation/runner/stages.py`, `engine.py`, `jobs.py`
- Modify: `studios/presentation/skills/presentation-studio/scripts/desk/app.js`
- Modify: `core/studio_core/review_policy.py`
- Modify: `studios/presentation/tests/test_stages.py`, `test_flow_routes.py`,
  `test_engine.py`; `tests/test_review_policy.py`

- [ ] **Step 1: Write the failing tests.** `test_stages.py`
  `test_no_deck_has_a_rehearse_step`: for each route in `('scratch', 'document',
  'existing')`, `'rehearse' not in [s.name for s in stages.steps(run)]`.
  `test_a_saved_deck_with_a_rehearse_gate_reads_as_before`: a `run.json` dict delivered at
  cc53056's shape, holding `gates: {'rehearse': {'state': 'absent'}}` and
  `steps: {'rehearse': {}}`, gives `stages.survey(run).next is None`, a `stages.timeline(run)`
  with no row named `rehearse` and every other row `done`, and the same status sentence as
  the same record without the key. Run. Expected: the first fails, the second passes.
- [ ] **Step 2: Remove the step.** `stages.py`: the `_s('rehearse', ...)` entry (`:72-73`),
  `'rehearse'` in `_has` (`:94`), the skip in `survey` (`:170`), and the `'later'` case in
  `timeline` (`:213-219`; the docstring loses "rehearse is later"). `engine.py:175,186`
  (the comment and `'rehearse': None`) and `:3141`'s `step.name != 'rehearse'`. `jobs.py:128`'s
  `step.name != 'rehearse'`. `app.js:3643,3723`: the comment and the filter.
  `review_policy.py:124-125`: drop `'rehearse'` from both tuples.
- [ ] **Step 3: Tests that named it.** `test_stages.py:19-51,100`, `test_flow_routes.py:30`,
  `test_engine.py:31,184` and the presentation cases of `tests/test_review_policy.py` stop
  expecting a `rehearse` step. Keep `test_page_app.py:184`, the no-placeholder guard.
- [ ] **Step 4: Run** Presentation's whole suite and
  `PYTHONPATH=.:tests python3 -m unittest test_review_policy -v`. Expected: pass.
- [ ] **Step 5: Commit** "Remove the rehearsal placeholder step; saved decks that hold it
  read as before".

## Task 7: Dead constants in core, and a ui-kit rule nothing uses

**Files:**
- Modify: `core/studio_core/deck_flow.py`, `research_view.py`, `ui-kit/style.css`

- [ ] **Step 1:** `grep -rn "CHECKPOINTS\|research_view.REFRESH\|look-choice"` over the
  repository (code, page scripts, tests) finds only the definitions and the audit
  documents. Delete `deck_flow.CHECKPOINTS` (`:47`), `research_view.REFRESH` (`:107`) and the
  `.looks .look-choice` rule (`ui-kit/style.css:1764-1769`). Keep `DESIGN_SESSION` and
  `SHARED_INPUTS`: the deck contract tests read them.
- [ ] **Step 2: Run** `PYTHONPATH=.:tests python3 -m unittest discover -s tests` (it includes
  `test_ui_consistency`). Expected: pass.
- [ ] **Step 3: Commit** "Remove two core constants and a shared style rule nothing reads".

## Task 8: Presentation Studio refuses to start research without synthesis

**Files:**
- Modify: `studios/presentation/runner/engine.py`
- Modify: `studios/presentation/tests/runner_support.py`
- Test: `studios/presentation/tests/test_engine.py`

**Interfaces (Produces):** `engine.LEGACY_RESEARCH = False`;
`engine.NO_SYNTHESIS = 'Research needs Harness Research 1.0 or newer on this computer, and
the one here cannot do it. Update Harness Research, then start again.'`

- [ ] **Step 1: Write the failing tests** in `test_engine.py`, in a `StudioCase` subclass
  `SynthesisAtStartTests` whose `setUp` patches `engines.LEGACY_RESEARCH` to False:
  - `test_a_deck_with_research_is_refused_without_synthesis`: with the research stand-in
    (no `package.json`, so `research_contract.snapshot` gives None), starting a scratch deck
    with research raises `WorkspaceError` whose text is `engines.NO_SYNTHESIS`; the
    workspace has no new folder, `home.decks()` is unchanged, and `git log` in the workspace
    has no new commit.
  - `test_a_deck_without_research_starts_as_before`: the same form with research off
    starts, and its record has no `research_contract`.
  - `test_a_read_error_is_refused_the_same_way`: `research_contract.snapshot` patched to
    return None while a real-looking runtime is found gives the same refusal.
  - `test_a_deck_brought_in_is_not_refused`: bringing in a conversation deck with no
    contract (the existing bring-in path) still works.
  Run. Expected: the first and third fail.
- [ ] **Step 2: Take the contract first.** In `Engine.start`, before any folder, record or
  remembered entry is made (today the snapshot is at `engine.py:772-778`, after the record
  is written), compute
  `contract = research_contract.snapshot(self.research()) if checked.get('research') else None`,
  catching `WorkspaceError` as None as today. When research is asked for, the contract is
  None and `LEGACY_RESEARCH` is False, raise `WorkspaceError(NO_SYNTHESIS)`. Use the same
  `contract` where the record is written; the schema rules are unchanged. Add above it:

  ```python
  # True lets a new run start on the legacy question queue. Only the test suites that still
  # drive the queue through its stand-in set it; piece 7 removes it with the queue.
  LEGACY_RESEARCH = False
  ```
- [ ] **Step 3: Keep the queue suites running.** `runner_support.StudioCase.setUp` adds
  `mock.patch.object(engines, 'LEGACY_RESEARCH', True)` to its patches, with the comment
  "the research stand-in is the legacy queue CLI". Run the whole suite; any test that now
  fails with `NO_SYNTHESIS` starts a deck outside `StudioCase`: give its class the same patch.
- [ ] **Step 4: Run** Presentation's whole suite. Expected: pass.
- [ ] **Step 5: Commit** "Refuse to start a deck's research on a Harness Research without
  synthesis".

## Task 9: Training Studio refuses to start without synthesis

**Files:**
- Modify: `studios/training/runner/engine.py`
- Modify: `studios/training/tests/runner_support.py`
- Modify: `studios/training/docs/superpowers/plans/2026-10-12-training-studio-core-pipeline.md`
  (section A7)
- Test: `studios/training/tests/test_runner_engine.py`

**Interfaces (Produces):** `engine.LEGACY_RESEARCH = False`; `engine.NO_SYNTHESIS`, the same
sentence as Task 8.

- [ ] **Step 1: Add the matrix row** (next free number, 131 at cc53056): "A new training;
  this computer's Harness Research has no synthesis, or cannot be read | Start it from the
  form | Refused with 'Research needs Harness Research 1.0 or newer on this computer, and the
  one here cannot do it. Update Harness Research, then start again.' Nothing is made. Covered
  by `test_row_131_a_training_is_not_started_without_synthesis`."
- [ ] **Step 2: Write the failing tests** in `test_runner_engine.py`, in a `StudioCase`
  subclass with `engines.LEGACY_RESEARCH` patched False:
  `test_row_131_a_training_is_not_started_without_synthesis`: with the stand-in, Start
  raises `WorkspaceError` with `engines.NO_SYNTHESIS`; `engine.trainings()` is unchanged,
  `home.trainings()` is unchanged, the workspace has no new folder and no new commit, and the
  shared studios config was not written (its bytes are unchanged; Start writes
  `review_level` today at `engine.py:1010-1012`, so the check comes before it).
  `test_a_conversation_training_brought_in_is_not_refused`: the existing bring-in of a
  training with no contract still works. Run. Expected: the first fails.
- [ ] **Step 3: Take the contract first.** In `Engine.start`, before
  `review_policy.change(...)` (`:1010`) and `pipeline.create(space, form)` (`:1018`), compute
  `contract = research_contract.snapshot(self.research())`, catching `WorkspaceError` as None.
  When it is None and `LEGACY_RESEARCH` is False, raise `WorkspaceError(NO_SYNTHESIS)`. Use
  it where `record` and `session` take `research_contract` (`:1023-1031`). Add the same
  `LEGACY_RESEARCH` block as Task 8.
- [ ] **Step 4: Keep the queue suites running.** `runner_support.StudioCase.setUp` patches
  `engines.LEGACY_RESEARCH` True, as in Task 8 Step 3. Fix any other class the same way.
- [ ] **Step 5: Run** Training's whole suite. Expected: pass.
- [ ] **Step 6: Commit** "Refuse to start a training on a Harness Research without
  synthesis".

## Task 10: The saved-work scan, and Presentation Studio's `studio saved-work`

**Files:**
- Create: `core/studio_core/saved_work.py`
- Test: `tests/test_saved_work.py`
- Modify: `studios/presentation/runner/engine.py`, `studio.py`
- Test: `studios/presentation/tests/test_runner_studio.py`, `test_engine.py`

**Interfaces (Produces):**
- `saved_work.PATHS: dict[str, str]`, the `about` sentence of each path id:
  - `'research-queue'`: "The legacy research question queue, for a run begun before Harness
    Research could synthesize its research."
  - `'cover-sample'`: "The cover drawn to show a brand skill that offers no looks. Only this
    computer is looked at: what it needs is kept in work/, which is never shared."
  - `'review-layout-1'`: "The first layout of combined reviews, which writes the briefs
    before the first review."
  - `'old-harness-slides'`: "Branches for a Harness Slides that lists no capabilities. No
    saved work needs these. They are reached only by a Harness Slides that lists no
    capabilities."
- `saved_work.needs(path: Path, title: str, why: str) -> dict`, giving
  `{'path': str(path), 'title': title, 'why': why}`.
- `saved_work.report(ids: tuple[str, ...], found: dict[str, list[dict]]) -> dict`, giving
  `{'paths': [{'id', 'about', 'needed_by': [...]}, ...], 'unused': [id, ...]}` in the order
  of `ids`; `needed_by` sorted by path; an id with none is in `unused`.
- `Engine.saved_work(folders=()) -> dict` in Presentation's engine (Task 11 adds Training's).
- CLI: `studio saved-work [--folder PATH]...`, printing the report as JSON with
  `indent=2, sort_keys=True`.

- [ ] **Step 1: Core tests** in `tests/test_saved_work.py`:
  `test_a_path_no_item_needs_is_listed_as_unused`,
  `test_items_are_listed_under_their_path_in_path_order`, and
  `test_every_path_has_its_sentence_and_names_no_studio` (no `PATHS` value contains
  "Presentation Studio" or "Training Studio"). Write `saved_work.py`. Run
  `PYTHONPATH=.:tests python3 -m unittest test_saved_work -v`. Expected: pass.
- [ ] **Step 2: Write the failing engine tests** in `test_engine.py`
  `SavedWorkTests(StudioCase)`, each on a workspace of decks written as files (no run
  started):
  - a deck with `form.research` true, no `research_contract`, and `research` not done is
    listed under `research-queue` with why "Its research has not run, and it was started
    before Harness Research could synthesize.";
  - the same deck with the `research` step done is not listed (its record still reads);
  - an undelivered deck with `look.md` and no `work/look/shown.json` is listed under
    `cover-sample` with why "It was drawn a cover to show its brand.";
  - an undelivered deck with `brand/brand-contract.json` that has not reached `gate:look`
    is listed with why "It may need it: its brand was exported before it reached the look.";
  - a delivered deck is under neither;
  - `old-harness-slides` is always in `unused`;
  - a deck folder given with `folders=(path,)` outside the workspace is looked at too;
  - nothing in the workspace changes (`git status --porcelain` is empty and every file's
    bytes are the same).
  Run. Expected: fail.
- [ ] **Step 3: Write `Engine.saved_work`.** For each root in `self.every()` and each given
  folder that holds `run.json`, read the record with `decks.read_run(root)` (no lock, no
  write) and its survey with `stages.survey(run)`. Research done is `'research' in
  survey.done`; delivered is `'deliver' in survey.done`; reached the look is `'gate:look'` in
  `survey.done` or `survey.waiting == 'gate:look'`. The title is `(run.get('form') or
  {}).get('title')` or the folder's name. Return
  `saved_work.report(('research-queue', 'cover-sample', 'old-harness-slides'), found)`.
- [ ] **Step 4: The command.** `studio.py`: a `saved-work` subparser with
  `--folder`, `action='append'`, `type=Path`, help "a deck folder to look at besides the
  workspace", handled by `saved_work(args, make=engines.Engine, out=None)` printing the JSON.
  Add it to the module docstring: "studio saved-work [--folder PATH] which saved decks
  still need each older path, as JSON; read-only". `test_runner_studio.py`
  `test_saved_work_prints_the_report_and_changes_nothing` runs `studio.main(['saved-work'])`
  on a disposable data folder and workspace and checks the JSON keys `paths` and `unused`.
- [ ] **Step 5: Run** the root test, Presentation's `test_engine` and `test_runner_studio`.
  Expected: pass.
- [ ] **Step 6: Commit** "Say which saved decks still need each older path, with studio
  saved-work".

## Task 11: Training Studio's `studio saved-work`

**Files:**
- Modify: `studios/training/runner/engine.py`, `studio.py`
- Test: `studios/training/tests/test_runner_engine.py`, `test_runner_studio.py`

**Interfaces (Consumes):** `saved_work.report`, `saved_work.needs`, `saved_work.PATHS`.

- [ ] **Step 1: Write the failing tests** `SavedWorkTests(StudioCase)` in
  `test_runner_engine.py`, on trainings written as files:
  - a runner training with no `research_contract` and `'research'` not in
    `engine._survey(root, record).done` is under `research-queue`, why as in Task 10;
  - a conversation training in `home.trainings()` whose `session.json` has no
    `research_contract` and whose `workspace.statuses(root, session)['research']` is
    `not-started` is under `research-queue` with why "A conversation training whose research
    has not started.";
  - a run with no `review_layout`, `review_policy` level `balanced`, and `review:final` not
    in its survey's `done`, is under `review-layout-1` with why "It began before the current
    review layout, and its final review is still to come.";
  - the same run with `review_layout: 2`, or at `step_by_step`, or with `review:final` done,
    is not;
  - `old-harness-slides` is always in `unused`; nothing in the workspace changes.
  Run. Expected: fail.
- [ ] **Step 2: Write `Engine.saved_work(folders=())`** over `self.trainings()`, each given
  folder that holds `.training-studio/run.json`, and `home.trainings()` for conversation
  trainings, with ids `('research-queue', 'review-layout-1', 'old-harness-slides')`. Read
  with `self._load(root)` and `self._survey(root, record)`, and conversation sessions with
  `workspace.load(root)`. Read only.
- [ ] **Step 3: The command**, as Task 10 Step 4, with help "a training folder to look at
  besides the workspace", and `test_saved_work_prints_the_report_and_changes_nothing` in
  `test_runner_studio.py`.
- [ ] **Step 4: Run** Training's `test_runner_engine` and `test_runner_studio`. Expected: pass.
- [ ] **Step 5: Commit** "Say which saved trainings still need each older path, with studio
  saved-work".

## Task 12: Training Studio takes its server helpers from core

**Files:**
- Modify: `studios/training/skills/training-studio/scripts/desk.py`, `cmd_desk.py`
- Test: `studios/training/tests/test_desk.py`

- [ ] **Step 1: Write the test** in `test_desk.py`
  `test_the_server_helpers_come_from_the_shared_core`: `desk.Desk.__mro__[1] is
  desk._security.Desk`; `desk.text is desk._security.text`; `cmd_desk.announce`,
  `cmd_desk.show`, `cmd_desk.port`, `cmd_desk.interrupt` and `cmd_desk.has_a_screen` are
  `studio_core.server`'s functions; `cmd_desk.NOT_A_PERSON == studio_core.server.NOT_A_PERSON`;
  `desk.Desk()` serves Training's page (its `page` is an instance of `desk.Page`). Run.
  Expected: fail.
- [ ] **Step 2: desk.py.** Replace the class `Desk` (`:700-737`) with

  ```python
  class Desk(_security.Desk):
      """The page's server: the shared one, serving this page by default."""

      def __init__(self, port: int = 0, page=Page):
          super().__init__(port, page)
  ```

  and `text()` (`:617`) with `text = _security.text`. Delete the `SECURITY_HEADERS` dict
  (`:41-47`), `HOST` (`:30`) and `JSON` (`:40`) once grep shows no reader in `scripts/`,
  `runner/` or `tests/`, and the blank-line runs at `:89-96`.
- [ ] **Step 3: cmd_desk.py.** Replace `:8-48` with
  `from studio_core.server import NOT_A_PERSON, announce, has_a_screen, interrupt, port, show  # noqa: F401`.
  Keep `import sys` and `import webbrowser`: the tests patch them through this module
  (`test_desk.py:8571-8583`). `serve` is unchanged.
- [ ] **Step 4: Run** Training's `test_desk`, `test_runner_studio` and `test_runner_page`,
  then the whole suite. Expected: pass.
- [ ] **Step 5: Commit** "Take Training Studio's page server and command helpers from the
  shared core".

## Task 13: One Claude model list, and `same_address` from core

**Files:**
- Move: `studios/presentation/runner/claude-code-models.json` to
  `core/studio_core/claude-code-models.json` (replacing the link)
- Delete: `studios/training/runner/claude-code-models.json`
- Modify: `studios/presentation/runner/settings.py`, `studios/training/runner/settings.py`,
  both runners' `setup.py`
- Modify: `core/studio_core/packaging.py`, `tests/test_model_catalog.py`
- Modify: both studios' `tests/test_runner_agents.py`, `tests/test_installer.py`;
  `studios/training/docs/runner.md`; `studios/presentation/vendor.json`

- [ ] **Step 1: Write the failing tests.** `tests/test_model_catalog.py`: the assertion at
  `:40-41` becomes `test_the_model_list_is_one_file_in_core`:
  `(ROOT/'core/studio_core/claude-code-models.json')` is a regular file, not a link, and
  neither `studios/*/runner/claude-code-models.json` exists. `:105-107` compares each
  bundle's copy with the core file. Each studio's `test_runner_agents.py` reads the list from
  `Path(studio_core.__file__).with_name('claude-code-models.json')` and checks
  `settings.CLAUDE_MODELS` is that path. Run. Expected: fail.
- [ ] **Step 2: Move the file.** `git rm core/studio_core/claude-code-models.json`, `git mv
  studios/presentation/runner/claude-code-models.json core/studio_core/`, and `git rm
  studios/training/runner/claude-code-models.json` (confirm first with `cmp` that the two were
  the same). In both `settings.py`: `import studio_core` and
  `CLAUDE_MODELS = Path(studio_core.__file__).resolve().with_name('claude-code-models.json')`.
  `packaging.shared_link`: drop the `claude-code-models.json` case (`:19-20`).
- [ ] **Step 3: Installed copies.** Both `test_installer.py`
  `test_the_runner_is_installed_with_the_version_beside_the_helper`: drop
  `'claude-code-models.json'` from the runner names and assert
  `(staged/'scripts'/'studio_core'/'claude-code-models.json').is_file()`. If the installer
  does not stage `scripts/studio_core`, stop and report: the runner already needs it.
- [ ] **Step 4: same_address.** In both runners' `setup.py`, delete `same_address` and add
  `from studio_core.workspace_setup import same_address`. Callers are unchanged.
- [ ] **Step 5: Docs and records.** Training `docs/runner.md:350`: the list is kept in one
  file, `core/studio_core/claude-code-models.json`; the test that pins its wording
  (`test_runner_agents.py:846`) quotes the new path. Do the same for any Presentation doc
  line grep finds. `vendor.json`: remove the `runner/claude-code-models.json` entry.
- [ ] **Step 6: Run** the root suite and both studios' `test_runner_agents`,
  `test_runner_setup` and `test_installer`. Expected: pass.
- [ ] **Step 7: Commit** "Keep one list of Claude Code's models, in the shared core".

## Task 14: The shared runner package, `bind`, and the host contract

**Files:**
- Create: `core/studio_core/shared_runner/__init__.py`
- Modify: `core/studio_core/modules.py`
- Create: `scripts/compare_runner.py`
- Test: `tests/test_shared_runner.py`
- Create: `studios/presentation/tests/test_shared_runner_use.py`,
  `studios/training/tests/test_shared_runner_use.py`

**Interfaces (Produces):**
- `modules.fresh_module(source, name, values)`: as today, but the new module is in
  `sys.modules[name]` before it runs, and the previous entry is put back if it raises.
- `modules.bind(namespace: dict, source, names=(), methods=None) -> None`: for each name,
  a function is rebuilt with `namespace` as its globals (code, name, defaults, keyword
  defaults, closure, docstring, `__module__ = namespace['__name__']`), and any other value
  is copied. `methods` maps a class name in `namespace` to method names on the same-named
  class in `source`; each is rebuilt the same way and set on the studio's class (plain
  functions, `property` with its fget, fset and fdel, `staticmethod`, `classmethod`).
  Refuses with `ValueError` a function whose code has a `__class__` free variable
  (zero-argument `super()`), and a name or method the studio module already defines. Also
  copies each module object `source` imported that `namespace` lacks. Records what it bound
  in `namespace['__shared_parts__']` as `{'source': source.__name__, 'names': [...],
  'methods': {...}}`, appended on each call.
- `modules.unresolved(namespace) -> list[str]`: for every function and method recorded in
  `__shared_parts__`, every name its code loads as a global (`dis` `LOAD_GLOBAL` and
  `LOAD_NAME`, in nested code objects and comprehensions too) that is neither in `namespace`
  nor a builtin, as `'<function>: <name>'`. Empty when all resolve.
- `shared_runner.WHOLE = ('brand_source', 'companion', 'research', 'agents', 'brand', 'team',
  'gitstate', 'documents')` and `shared_runner.PARTS = ('page', 'settings', 'setup', 'slides',
  'upkeep', 'worker_tools')`, filled in as modules arrive.
- `python3 scripts/compare_runner.py <module>`: the definition-by-definition comparison of
  `studios/presentation/runner/<module>.py` and `studios/training/runner/<module>.py`
  (same, words only, different, one side only, with names), as the spec's table was made.

- [ ] **Step 1: Write the failing tests** in `tests/test_shared_runner.py`:
  - `test_a_bound_function_reads_the_studio_module_s_names`: a source module defining
    `GREETING = 'shared'` and `def say(): return GREETING + PRODUCT`; binding `say` into a
    namespace with `PRODUCT = '!'` and `GREETING = 'studio'` gives `'studio!'`, and changing
    the namespace's `GREETING` afterwards changes the answer (a test patch reaches it).
  - `test_methods_and_properties_are_set_on_the_studio_class`.
  - `test_zero_argument_super_is_refused` and `test_a_name_the_studio_defines_is_refused`.
  - `test_unresolved_names_are_found_in_nested_code`: a bound function with a comprehension
    reading `MISSING` gives `['f: MISSING']`.
  - `test_a_fresh_module_is_registered_while_it_runs`: a source whose top level reads
    `sys.modules[__name__]` finds itself; a source that raises leaves the earlier entry.
  - `test_no_shared_runner_file_names_a_product`: no file in `shared_runner/` contains
    "Presentation Studio", "Training Studio", "PRESENTATION_STUDIO", "TRAINING_STUDIO",
    "presentation-studio" or "training-studio".
  - `test_shared_modules_import_each_other_through_runner`: no file in `shared_runner/`
    contains `shared_runner import` or `from studio_core.shared_runner.` except in a
    `for_product` docstring example.
  Run `PYTHONPATH=.:tests python3 -m unittest test_shared_runner -v`. Expected: fail.
- [ ] **Step 2: Write `bind`, `unresolved` and the `fresh_module` change** in
  `modules.py`, and `shared_runner/__init__.py` with the host contract as its docstring: a
  studio using the shared runner has a `runner` package that puts its scripts folder on the
  import path, and the scripts modules `workspace` (with `WorkspaceError`), `home`, `hub`,
  `sync_guidance` and `studios_config`; a shared module imports its fellows only as
  `from runner import <name>`; product, item words, data variables and studio paths are
  values passed in. Write `scripts/compare_runner.py`. Run the root test. Expected: pass.
- [ ] **Step 3: Each studio's use test.** `test_shared_runner_use.py` in each studio, with
  `test_whole_modules_come_from_core` (for each name in `shared_runner.WHOLE`,
  `Path(importlib.import_module('runner.' + name).__file__).resolve()` is
  `core/studio_core/shared_runner/<name>.py`, and `sys.modules['runner.' + name]` is that
  module) and `test_bound_parts_find_every_name` (for each name in `shared_runner.PARTS`,
  `modules.unresolved(vars(runner.<name>)) == []`, and each bound function's `__globals__` is
  the studio module's dict). Both pass while the tuples are empty.
- [ ] **Step 4: Packaging.** Each deck studio's `test_installer.py`: the staged copy holds
  `scripts/studio_core/shared_runner/__init__.py`. Run both studios' `test_installer` and
  the root `test_packaging_entrypoints`. Expected: pass.
- [ ] **Step 5: Commit** "Add the shared runner package and a way to bind shared parts into a
  studio's module".

## The module moves (Tasks 15 to 22): the recipe

Each whole-module task follows these steps. The task gives what differs, the values passed
in and the tests to write.

1. Run `python3 scripts/compare_runner.py <module>` on the base. If piece 1 or a later task
   changed either copy, carry each change into the shared file with its test.
2. Write the task's pinning tests in both studios and run them on the unchanged code.
   Expected: pass. They must pass again, unchanged, at the end.
3. `git mv studios/presentation/runner/<module>.py core/studio_core/shared_runner/<module>.py`.
   Apply the task's reconciliation: the other copy's later changes, product and item words
   as module values, studio paths as values. Remove `import runner  # puts the core on the
   import path` (the facade is already inside the runner). Add at the end:

   ```python
   def for_product(name, product, **values):
       """This module for one studio, as `sys.modules[name]`. See shared_runner."""
       from studio_core.modules import fresh_module
       return fresh_module(__file__, name, {'PRODUCT': product, **values})
   ```
4. Write both facades, `studios/<studio>/runner/<module>.py`:

   ```python
   """<Studio>'s <module>: the shared runner's, for this studio (core/studio_core/shared_runner)."""
   import sys

   import runner  # noqa: F401  puts the core on the import path
   from studio_core.shared_runner.<module> import for_product

   sys.modules[__name__] = for_product(__name__, '<Studio>', <values>)
   ```

   `<Studio>` is the full product name and `<values>` are the task's values as keywords.
   Training Studio's `team` facade, in the spec's 5.3, is a finished example.
5. Add the name to `shared_runner.WHOLE`. In `vendor.json`, the module's note becomes
   "Original port provenance retained. The implementation now comes from
   `core/studio_core/shared_runner/<module>.py`."
6. Run the module's tests in each studio, both `test_shared_runner_use`, then both whole
   suites and the root suite. Expected: pass.
7. Commit "Keep <module> once, in the shared runner".

## Task 15: `brand_source`

- Differs: one sentence, "The release has no installer {PRODUCT} knows how to run: …"
  (`brand_source.py:346`). Values: none beyond `PRODUCT`.
- [ ] **Pin:** both `test_runner_brand_source.py` already quote the sentence with their
  product; keep them as the pin.
- [ ] Follow the recipe. Commit "Keep brand_source once, in the shared runner".

## Task 16: `companion`

- Differs: Presentation's `run_command(command, cwd, seconds, said, env=None)` passes `env`
  to `supervise`; Training's always passes None. The shared module keeps the `env`
  parameter; Training's callers pass none, so nothing changes for it.
- [ ] **Pin:** Training `test_runner_companion.py`
  `test_run_command_runs_with_this_process_s_environment_by_default`: with no `env`, the
  child sees a variable set in `os.environ` for the test.
- [ ] Follow the recipe. Commit "Keep companion once, in the shared runner".

## Task 17: `research`

- Differs: Presentation omits a null `headline` from a recorded finding (`research.py:134-136`)
  and has longer docstrings naming "deck". Keep the omission; write the docstrings for "a
  run's folder". Training's findings carry no headline, so nothing it sends changes.
- [ ] **Pin:** Training `test_runner_research.py`
  `test_a_finding_without_a_headline_is_recorded_without_the_key`: the stand-in's recorded
  finding has no `headline` key. Presentation keeps its own headline test.
- [ ] Follow the recipe. Commit "Keep research once, in the shared runner".

## Task 18: `agents`

- Differs: Presentation's `_shared(folder)` and `data_shared()` (`agents.py:167-184`), with
  `_safe` using `_shared`; Training's `_safe` loop and its sentence; Training's tool labels
  `submit_judgements` and `submit_coverage` and their kinds (`:228-237`); the docstring
  example. Values: `DATA_VARIABLE` (`'PRESENTATION_STUDIO_DATA'`,
  `'TRAINING_STUDIO_DATA'`). `data_shared` says
  `f"{PRODUCT} keeps its work in {home.data_root()}, inside {shared}, a temporary folder other
  programs share, so no assistant may work there. Set {DATA_VARIABLE} to a folder of your own,
  or unset it, and open {PRODUCT} again."` Keep Presentation's `_safe` sentence; the labels
  are the union.
- [ ] **Pin:** Training `test_runner_agents.py`
  `test_data_shared_names_this_studio_s_variable` (a data folder under a shared temporary
  folder gives a sentence naming "Training Studio" and `TRAINING_STUDIO_DATA`; else None)
  and `test_a_job_folder_in_a_shared_temporary_folder_is_refused` (regex "temporary folder
  other programs share"). Presentation's existing `data_shared` tests are its pin. If a
  Training test quotes "Keep job folders under agents.staging()", change it to the shared
  sentence in this task.
- [ ] Follow the recipe. Commit "Keep agents once, in the shared runner".

## Task 19: `brand`

- Differs: Presentation's `ROOTS` and `told()` (`brand.py:163-181`), with `run_command`
  passing `told()`; Training's `Brand.contracts()` (`:326-333`); a docstring line each.
  `look_status` went in Task 5. Values: `PINS`, the studio's
  `installer/companions.json` (`Path(runner.__file__).resolve().parents[1] / 'installer' /
  'companions.json'`), passed by each facade, because `brand.py:87` builds it from its own
  file.
- Training gains `told()`: its brand skill is told the runner's `HARNESS_SLIDES_ROOT` and
  `HARNESS_RESEARCH_ROOT` unless they are set, as Harness Slides tells a brand adapter to be
  told. Presentation gains `contracts()`, unused.
- [ ] **Pin:** Training `test_runner_brand.py`
  `test_the_brand_skill_is_told_which_companions_to_use`: with the slides and research
  stand-ins found, the brand stand-in's command sees both variables naming them; with one
  already set in `os.environ`, that value is kept. `test_brand_pins_are_this_studio_s`:
  `brand.PINS` is the studio's own `installer/companions.json` in each studio.
- [ ] Follow the recipe. Commit "Keep brand once, in the shared runner".

## Task 20: `team`

- Differs: item words in sentences and docstrings; `REPLACED`, `APP`; the published tag.
  Presentation tags `<folder>/<id>/r<n>` (`_prefix` is `space.folder`; `int(parts[-1][1:])`
  when it starts with `r`; three parts, id at 1). Training tags
  `training-studio/<folder>/<id>/<n>` (`_prefix` is `f'{gitstate.TOOL}/{space.folder}'`;
  four parts, id at 2). `published` calls `space.deck(...)` / `space.training(...)`.
- Values: `ITEM` (`'deck'`, `'training'`), `NOTIFY` (`'PRESENTATION_STUDIO_NOTIFY'`,
  `'TRAINING_STUDIO_NOTIFY'`), `TAG_UNDER_TOOL` (False, True) and `REVISION_MARK`
  (`'r'`, `''`). `_prefix`, the tag name and the parsing read them: the parts count is
  `3 + TAG_UNDER_TOOL` and the id is at `1 + TAG_UNDER_TOOL`; a revision is
  `int(parts[-1][len(REVISION_MARK):])` when it starts with `REVISION_MARK`. `APP = PRODUCT`.
- Before the move, add `Workspace.item(self, ident)` to both runners' `gitstate.py`, the same
  body as `deck` / `training`, and use `space.item(...)` in shared `team`.
- [ ] **Pin:** in each `test_runner_team.py`,
  `test_a_published_revision_keeps_its_tag_shape`: publishing twice in a disposable shared
  workspace makes `presentations/<id>/r1` and `presentations/<id>/r2` (Training:
  `training-studio/trainings/<id>/1` and `/2`), and `team.published(space)` and
  `team.revisions(space, ident)` read them back; a tag written in the shape the code wrote at
  cc53056 by plain `git tag -a` reads the same. `test_notifications_use_this_studio_s_variable`.
  Also: `from runner import gitstate, team`; `team.gitstate is gitstate`, and
  `sys.modules['runner.team'] is team` (Review Focus 5).
- [ ] Follow the recipe. Commit "Keep team once, in the shared runner".

## Task 21: `gitstate`

- Differs: the product, `TOOL`, `FOLDER`, the item words, `README` (its third and fourth
  lines name what an item's folder holds), the ignore line `**/.<tool>/lock`, `IGNORE_NOTE`,
  `Workspace.deck` / `Workspace.training`, and how `studios_config` is imported
  (Presentation: scripts `studios_config`; Training: `runner.studios_config`).
  Presentation has `made_apart` (`:590-598`). Training has `own_share` needing an address
  (`:176-180`) and `share_when` deciding under the lock (`:192-198`).
- Values: `TOOL`, `FOLDER`, `ITEM`, `ITEMS`, `README` (each studio's text exactly as
  today), and `studios_config` (the module). `IGNORE` builds `f'**/.{TOOL}/lock'`;
  `IGNORE_NOTE` is `f'# Kept on each computer and never shared. Written by {PRODUCT}.'`.
  `for_product` sets `setattr(module.Workspace, ITEM, module.Workspace.item)`, so `space.deck`
  and `space.training` keep working.
- Presentation gains `own_share`'s address check and the locked `share_when`; Training gains
  `made_apart`.
- [ ] **Pin:** in each `test_runner_gitstate.py`, `test_a_new_workspace_s_files_are_as_before`:
  setting up a disposable workspace writes `README.md`, `.gitignore` and `hub.json` whose
  bytes equal the literal text the test holds, copied from what the unchanged code writes on
  the base (run once, paste the bytes into the test). Presentation:
  `test_when_to_share_is_written_under_the_lock` (Training's test of `share_when` deciding
  inside `studios_config.update`, ported) and
  `test_an_old_share_without_an_address_is_not_taken`. Training: a `made_apart` test ported
  from Presentation's. `test_runner_gitstate.py:926` (Presentation) and `:948` (Training) read
  `gitstate.__file__`; they now read the shared file, which is what they mean.
- [ ] Follow the recipe. Commit "Keep gitstate once, in the shared runner".

## Task 22: `documents`

- Differs: Presentation has `add_text`, `text_of`, `_titled` and an optional `title` in an
  entry; its own `_managed` and `_write`; `RUN` from `runner.decks` marks a deck's folder.
  Training uses `workspace.managed`, `workspace.write_atomic` and `workspace.session_path`.
- Values: `ITEM`, and `IS_ITEM`, a function `root -> bool` (Presentation
  `lambda root: (root / decks.RUN).is_file()`; Training
  `lambda root: workspace.session_path(root).is_file()`). The shared module keeps
  Presentation's `_managed` and `_write`; its symbolic-link sentence becomes
  `f'{relative} is a symbolic link; a {ITEM}\'s documents must be real files in its folder.'`
  (Training's test matches "symbolic link" only). The refusal for a folder that is not an
  item is `f'There is no {ITEM} in that folder, so it has no documents.'`.
- Training gains `add_text`, `text_of` and titles, unused. The index never holds `title`
  unless `add_text` gave one, so Training's index files are as before.
- [ ] **Pin:** in each `test_runner_documents.py`, `test_the_index_is_written_as_before`:
  adding a Markdown file and a PDF writes an index whose bytes equal the literal the test
  holds, taken from the unchanged code on the base.
- [ ] Follow the recipe. Commit "Keep documents once, in the shared runner".

## The common parts (Tasks 23 to 28): the recipe

1. Run `python3 scripts/compare_runner.py <module>` on the base. The definitions listed as
   "same" or "words only" move; nothing else does.
2. Write the task's pinning tests in both studios; run them on the unchanged code. Expected:
   pass.
3. Create `core/studio_core/shared_runner/<module>.py` holding those definitions, with the
   imports they need, product words as `PRODUCT`, item words as `ITEM` / `ITEMS`, and a
   module docstring: "The parts of the runner's `<module>` both deck studios share. A studio
   binds them into its own module with `studio_core.modules.bind`; they read that module's
   names." End it with `NAMES = (...)` and `METHODS = {...}`, the names `bind` takes.
4. In each studio's `runner/<module>.py`, delete those definitions and add, right after the
   imports,

   ```python
   from studio_core import modules
   from studio_core.shared_runner import <module> as _shared
   PRODUCT, ITEM, ITEMS = '<Studio>', '<item>', '<items>'
   modules.bind(globals(), _shared, _shared.NAMES)
   ```

   and, after each class that takes methods, `modules.bind(globals(), _shared,
   methods={'<Class>': _shared.METHODS['<Class>']})`. A constant a class body or a default
   argument reads must be bound before it, which the first call does. If `PRODUCT` or `ITEM`
   already means something else in the module, use the name the module already has and
   bind under it.
5. Add the name to `shared_runner.PARTS`. In `vendor.json`, the note becomes "Original port
   provenance retained. The parts both deck studios share come from
   `core/studio_core/shared_runner/<module>.py`; the rest is this studio's."
6. Run both `test_shared_runner_use` (every bound name resolves), the module's tests in each
   studio, both whole suites and the root suite. Expected: pass.
7. Commit "Share the common parts of <module> between the deck studios".

## Task 23: `page`

- Moves: `PNG`; `Studio.__init__`, `serve`, `leave`, `start`, `stop`; `RunnerPage.__init__`
  and `RunnerPage.agents`. Both `Studio` classes subclass the shared core `Desk` after
  Task 12.
- [ ] **Pin:** the existing `test_runner_page.py` and `test_runner_studio.py` serving tests in
  each studio.
- [ ] Follow the recipe. Commit "Share the common parts of page between the deck studios".

## Task 24: `settings`

- Moves the "same" set: `SCHEMA`, `AGENTS`, `SECONDS`, `MODEL`, `LEVELS`, `EFFORTS`,
  `CLAUDE_MODELS` (Task 13's path), `PREVIEWS`, `RELEASE`, `path`, `check_agent`,
  `check_model`, `check_effort`, `takes`, `claude_models`, `read_models`, `check_previews`,
  `check_place`, `check_notify`, `check_look`, `check_repository`, `check_release`, `number`,
  `passes`, `_kept`, `load`, `seen`, `_same`, `STALE`, `forget_own`, and the "words only"
  `DOLLARS` and `PARALLEL`. `SHARED`, `Settings`, `check`, `from_shared`, `shared_now`,
  `changes`, `save`, `own` and the one-sided names stay.
- [ ] **Pin:** in each `test_runner_settings.py` (Training: the settings tests in
  `test_runner_agents.py` and `test_runner_setup.py` if it has no such file),
  `test_runner_json_is_written_as_before`: saving the defaults to a disposable data folder
  writes `runner.json` whose bytes equal the literal from the unchanged code.
- [ ] Follow the recipe. Commit "Share the common parts of settings between the deck
  studios".

## Task 25: `setup`

- Moves the "same" set: `WHEN`, `SHARE`, `PLACE`, `BRANCH`, `review_choice`,
  `save_review_level`, `save_brand`, `_same`, `notice_path`, `notice`, `notice_read`, `_words`,
  `_text`, `place`, `whole`, `names`, `_check`, `_identity`, `_unwritable`, `_first_branch`,
  `check`, `read`, `seen`, and the "words only" `PROBE`, `NOBODY`, `moved`, `_local`.
  `same_address` is already core's (Task 13). Everything that differs stays.
- [ ] **Pin:** each `test_runner_setup.py` as it stands, plus
  `test_the_notice_file_is_written_as_before` (bytes of `notice_path()` after `notice(...)`).
- [ ] Follow the recipe. Commit "Share the common parts of setup between the deck studios".

## Task 26: `slides`

- Moves the 65 "same" definitions `compare_runner.py slides` lists, among them `VARIABLE`,
  `MINIMUM`, `TIMEOUT`, `pool_size`, `find_runtime`, `run_command`, `locations`, `TooOld`'s
  and `Refused`'s methods, `read_guidance`, `ready`, and the `Slides` methods `__init__`,
  `_call`, `_json`, `version`, `outline_check`, `outline_start`, `layouts`, `merge`,
  `preview`, `critique`, `render`, `designs`, `sections`, `has`, `capabilities`, `assets` and
  the rest of the list. `compile`, `cited`, `knows`, `review_prepare`, `outline_draft`,
  `_problems`, `LEFT` and the one-sided methods stay. The pre-0.16 branches move or stay as
  they fall; piece 7 removes them.
- [ ] **Pin:** each `test_runner_slides.py` as it stands. `mock.patch.object(slides, ...)`
  in either suite keeps working because bound methods read the studio module.
- [ ] Follow the recipe. Commit "Share the common parts of slides between the deck studios".

## Task 27: `upkeep`

- Moves the 50 "same" and 28 "words only" definitions `compare_runner.py upkeep` lists,
  among them `INSTALLER`'s neighbours `SAVED`, `DAY`, `TAG`, `TOOLS`, the update and
  brand-install messages, and the `Upkeep` methods `__init__`, `start`, `again`, `close`,
  `check`, `due`, `look`, `dismiss`, `releases`, `upgrade`, `restart`, `command`, `versions`,
  `guidance` and the rest of the list. `INSTALLER` (it is built from the studio's own file,
  `upkeep.py:131`) and every definition that differs stay. Product words in the moved
  messages read `PRODUCT`.
- [ ] **Pin:** each `test_runner_upkeep.py` as it stands, plus
  `test_the_saved_look_is_written_as_before` (bytes of the file `Upkeep.saved_path()` names
  after a look with a fake listing).
- [ ] Follow the recipe. Commit "Share the common parts of upkeep between the deck studios".

## Task 28: `worker_tools`

- Moves the 120 "same" definitions `compare_runner.py worker_tools` lists, among them
  `parts`, `tidy`, `word_text`, `slug`, `clip`, `_Page`, `decode`, `page_text`, `pdf_text`,
  `public`, `resolve`, `fetch_once`, `unpacked`, `held`, `as_json`, `turn`, `slots`,
  `pictures`, `serve`, `main`, and the `WorkerTools` methods `__init__`, `call`,
  `list_inputs`, `read_input`, `submit_artifact`, `submit_review`, `check_section`,
  `read_source`, `search_source`, `ask_person` and the rest of the list; and the "words only"
  `check_plan`. `command` stays in each studio: it starts the studio's own file
  (`worker_tools.py:953`). The `if not __package__:` path line and the `__main__` block stay.
- [ ] **Pin:** each `test_runner_worker_tools.py` as it stands, including the test that starts
  the tools server by its path (find it with `grep -n "command(" tests/test_runner_worker_tools.py`);
  add `test_the_tools_server_starts_by_its_path_and_finds_its_shared_parts` if none starts it
  under `-I`: run `worker_tools.command(folder)` on a disposable job folder with `--help` or the
  server's own no-job refusal, and check it exits as the unchanged code does.
- [ ] Follow the recipe. Commit "Share the common parts of worker_tools between the deck
  studios".

## Task 29: Docs, Presentation Studio

**Files:** `studios/presentation/README.md`, `docs/runner.md`, `docs/capabilities.md`,
`docs/development.md`, `docs/acceptance.md`,
`docs/superpowers/specs/2026-10-14-presentation-studio-design.md`,
`skills/presentation-studio/references/workspace.md`, `references/levels.md`,
`references/routes.md`, `runner/__init__.py`

- [ ] **Step 1: README.** `:29` "The page stops at each of these and waits for you" becomes
  what the level does: at Step by step it stops at each; at Balanced and Automatic draft,
  only where the list says. Make the list at `:31-36` say which level stops where, from
  `core/studio_core/deck_flow.py` `GATES` on the base. `:34`: an old brand skill stops the
  deck with a sentence; it does not show the cover. `:129`: the button's name as the page
  has it on the base ("Send to Google Slides" at cc53056). `:145`: the design is "the first
  design, kept as history; `docs/runner.md` says how it works now". Move `:151-164` (after
  "## Licence") into the sections they repeat, dropping the repeats and the line about "the
  live-preview issue". Add "See the first draft before the deck is checked" and "Delivered:
  first draft, not checked" where the README lists what a deck can do.
- [ ] **Step 2: runner.md.** `:61`: the brand step is the look step: the brand draws a slide
  of the outline in each of its looks. `:190`: an older brand skill stops a new deck with
  a sentence. `:125`: the page offers it as "Bring in a deck". `:63`: the button's name as on
  the base. Fold `:135`, `:184` and `:221-227` into `:53` and `:63`. Add the Start refusal
  (Task 8) and `studio saved-work` (Task 10) where research and the command line are
  described.
- [ ] **Step 3: capabilities, development, acceptance, the 2026-10-14 spec.**
  `capabilities.md:17` "cover preview" becomes "look samples"; `:37-38` drops rehearsal.
  `development.md:3` names the 2026-10-14 design and plan as history and says Training
  Studio's code came from its own repository, since retired, and lives in `studios/training`;
  `:89` uses the pinned harness-slides from `pins/companions.json`. Leave `:84`: releases are
  the suite's `vX.Y.Z` tags, as `upkeep.TAG` reads them. `acceptance.md:98`
  gains "A record of a hand test of 0.1.0 on <its date>; it describes the studio as it was
  then." The 2026-10-14 design gains a first line "Superseded: kept as the first design.
  `docs/runner.md` describes the studio now."
- [ ] **Step 4: Skill references** (guidance; wording only). `workspace.md:17` no cover;
  `:31` the schema a run record has (1, 2 or 3, as `engine.py` writes); `:34` `gate:look` is
  the look; add the `review_policy` key, so a deck made in a conversation says its level.
  `levels.md:9-10` and `routes.md:7,23` say "Look" where the stop is the look. Run
  `python3 studios/presentation/skills/presentation-studio/scripts/validate_package.py`.
- [ ] **Step 5: `runner/__init__.py`**'s module list says which modules are the shared
  runner's and where they live.
- [ ] **Step 6: Run** `test_package`, `test_page_app` and `test_no_brand_named`. Expected:
  pass.
- [ ] **Step 7: Commit** "Correct Presentation Studio's docs to what the studio does now".

## Task 30: Docs, Training Studio

**Files:** `studios/training/README.md`, `docs/runner.md`, `docs/how-it-works.md`,
`docs/desk.md`, `docs/development.md`, `docs/acceptance.md`,
`skills/training-studio/references/levels.md`, `runner/engine.py` (module notes),
`runner/__init__.py`

- [ ] **Step 1:** `runner.md:347`: delete "Bringing edits back from a Google Doc, and" (the
  pull is on the page after piece 1); keep the sentence about scenarios and audiences.
  `runner.md:379` and `how-it-works.md:24`: "A new training on a Harness Research without
  synthesis is refused at Start. The legacy question queue is kept for a training begun
  before the synthesis research contract, so that it finishes as it began. `studio
  saved-work` lists any that still need it." Move `runner.md:201-217` after the default path
  that `:221` describes.
- [ ] **Step 2: README.** `:3`'s paragraph on review levels moves to `docs/runner.md` under
  the review levels section; the README keeps one sentence and a link. `:210`'s issue link is
  Marketing Studio's issues. `:121` and `:218` call `docs/desk.md` "The page".
- [ ] **Step 3: desk.md** says the page serves two ways: from `training desk` in a
  conversation, where "It does not start or run a training" and Settings holds notifications
  and where each training is decided; and from the runner (`studio serve`), where it starts
  and runs trainings and Settings holds more (`page.py` on the base). Its title stays "The
  page"; the code names are not renamed here.
- [ ] **Step 4:** `development.md:3` and `how-it-works.md:3` name `docs/runner.md` as current
  and the 2026-10-12 design as history. `acceptance.md:9` gains "A record of runs on
  2026-10-12, on harness-research 0.8.0, before synthesis research; it describes the studio as
  it was then." `engine.py:76-82` notes describe the 0.16.0 floor and say the older branches
  wait for piece 7's removal.
- [ ] **Step 5: Guidance** (wording only). `references/levels.md:22`: "If the levels together
  need more than 8 research questions, propose splitting them…", matching
  `stages/research-plan.md`. Run `validate_package.py`.
- [ ] **Step 6: Run** `test_package`, `test_desk` and `test_runner_agents`. Expected: pass.
- [ ] **Step 7: Commit** "Correct Training Studio's docs to what the studio does now".

## Task 31: Docs, Blog Studio, shared setup and the shared runner's records

**Files:** `docs/design/blog-workflows.md`, `studios/blog/docs/epic-27-validation.md`,
`startup-validation.md`, `google-gcloud-validation.md`, `docs/shared-setup.md`,
`docs/core-status.md`, `studios/presentation/AGENTS.md`, `studios/training/AGENTS.md`,
`studios/presentation/vendor.json`

- [ ] **Step 1: Blog.** In `blog-workflows.md`, move the old-run gate and editor rules of
  "Interface contract" (from line 21: "Ideas have one primary 'Develop an idea' action",
  "New-writing gates retain their decisions" and the rest that hold only for runs) under a
  new heading "## Blogs started before the desk", after the desk's own rules. The three
  validation records get the first line "A record of a check made on <date>; it describes the
  studio as it was then.", the date from each file or its first commit.
- [ ] **Step 2: Shared setup.** `docs/shared-setup.md:137-140`: "A Blog Studio run started in
  chat includes research with the outline…; a blog on the desk has no stops."
- [ ] **Step 3: AGENTS.** `studios/presentation/AGENTS.md:11` becomes:

  > **Shared runner parts live in core.** A runner module both deck studios use lives in
  > `core/studio_core/shared_runner/`, and `runner/<name>.py` passes the product in. Change
  > it there, for both. A file still copied from Training Studio is listed in `vendor.json`
  > with the file it came from and the revision.

  `studios/training/AGENTS.md` gains the first two sentences as a new bullet.
- [ ] **Step 4: Records.** `vendor.json` gains a top-level `"note": "The source repository is
  retired. Training Studio now lives in studios/training of Marketing Studio."`; check each
  moved module's note says where it lives now. `docs/core-status.md` gains a row "Runner
  modules both deck studios use | `core/studio_core/shared_runner/` | Each studio's
  pipeline, engine, jobs and the parts that differ", and its last row names what is still
  per studio.
- [ ] **Step 5: Run** `test_desk` in Presentation (it reads `vendor.json`) and
  `python3 studios/blog/scripts/measure_guidance.py --check`. Expected: pass.
- [ ] **Step 6: Commit** "Say where the shared runner lives, and correct the Blog Studio and
  shared setup docs".

## Task 32: Full check

- [ ] **Step 1:** `grep -rn "Presentation Studio\|Training Studio" core/studio_core/shared_runner`
  finds nothing. `grep -rn "TrainingStudioMarkdown\|github.com/dbbaskette/training-studio"`
  finds only provenance records and dated history.
- [ ] **Step 2:** On a disposable `HOME`, data folders and studios config, run each deck
  studio's `studio status` and `studio saved-work` from its checkout, and from a staged
  install made by its installer tests' helper. Each prints JSON and changes nothing.
- [ ] **Step 3:** `bash scripts/ci/tart-macos.sh --dry-run`, then
  `bash scripts/ci/tart-macos.sh` (it runs `scripts/ci/check.sh`: the root suite, every
  studio's suite and package validator, and the acceptance runs). Where the Tart runner is
  not available, `bash scripts/ci/check.sh python3`. Expected: PASS.
- [ ] **Step 4:** Open the pull request for piece 2 with the task list, the decisions in the
  spec's 5.5 table, and the line "No saved format changed; each was pinned before its module
  moved."
