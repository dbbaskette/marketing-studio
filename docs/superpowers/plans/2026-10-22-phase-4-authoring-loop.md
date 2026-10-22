# Phase 4, finish the authoring loop on the page: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** a training, a blog or a deck can be finished on the page: every deliverable can be
downloaded, a teammate's Google Doc edit can be brought back, a review's findings can be
applied, the three missing Blog starts are on Home, and no review is approved on a look
nobody saw.

**Architecture:** each item is a small change to a studio's runner (Python, standard
library) and its page script (plain JavaScript, no build). Each new address keeps the page
server's rules: reads are GET with the key in a header, changes are POST with JSON from the
page's own origin. Training's grouping change is versioned on the run
(`review_layout = 2`), so runs already under way keep their reviews.

**Tech Stack:** Python 3.11 standard library, `unittest`; plain JavaScript run in each
studio's `page_harness.js` (Training, Presentation) or `scripts/ci/check-management.cjs`
(Blog Studio).

**Spec:** `docs/superpowers/specs/2026-10-22-phase-4-authoring-loop-design.md`. Read it
first: each task's names, sentences and rules come from it.

**Before Task 1:** Phases 2 and 3 are merged first. Pull `main`, then re-find every
`file:line` below by its function name; the line numbers are at main 21a216e. Where Phase 2
renamed a label (the first combined review, the look stop), use the new label and keep the
code names (`review:direction`, `gate:look`, `package`).

## Global Constraints

- Phases 2 to 5 are built in order, each merged before the next starts. Line references are at main
  21a216e: re-read every named file on the phase's own base first. Training matrix row numbers
  named here are a guide; each new row takes the next free number on that base.
- Python 3.11 or newer, standard library only; no frontend build step.
- Full product names in code, docs and commits: Training Studio, Blog Studio, Presentation
  Studio, Marketing Studio, Harness Research, Harness Slides, Tanzu Brand.
- Person-facing sentences never say "artifact", "stale" or "lineage" (Training's and
  Presentation's page tests enforce `FORBIDDEN_WORDS`).
- One filled button on a screen: every new button here is quiet unless the spec says it
  leads.
- UI follows `docs/design/golden-gate.md`: material only for navigation, toolbars and
  transient controls (sheets, toasts); forms and reading surfaces opaque.
- Tests use disposable settings, workspaces, Git identities and data folders; scripted
  workers; a pretend Drive. No provider job and no real Google call, ever.
- Training: a change to status, approval, inputs or readiness adds a row to the
  state-transition matrix (`studios/training/docs/superpowers/plans/2026-10-12-training-studio-core-pipeline.md`,
  next free row 119) and a `test_row_NNN` test.
- Training and Presentation: guidance that needs a script change raises
  `guidance/manifest.json` `minimum_runtime` and `VERSION` together. This plan changes no
  guidance; if a task finds it must, it does both.
- Blog Studio: `ruff format` and `ruff check .` before each commit; every reference change
  passes `python3 scripts/measure_guidance.py --check` and
  `python3 scripts/command_reference.py --check`.
- Commit messages are one plain sentence, like the repository's history, ending with the
  attribution line the session gives.

## Review Focus

- A download address given a `..`, an absolute path, a symlink out of the training, or an
  artifact name of another training: 403, and no bytes. (Task 1 tests it.)
- Pulling a Google Doc while the file was also edited here: neither text is lost, and the
  person chooses with a confirmation that names what is replaced. (Task 3.)
- A Balanced training already past its first combined review when this ships: it never
  stops at that review again, and its briefs are not written twice. (Task 4.)
- A Presentation outline edited and a look picked in the same approval: the pick is never
  applied to looks drawn after it. (Task 12.)
- Open as a Google Doc pressed twice, or after an upload whose outcome is unknown: one Doc,
  never two; the second press says the first is being reconciled. (Task 8.)

---

## Task 1: Training Studio answers a deliverable's bytes

**Files:**
- Modify: `studios/training/runner/page.py` (`READS`, `RunnerPage.read`, new
  `RunnerPage.download`, module docstring's contract list)
- Test: `studios/training/tests/test_runner_page.py` (new class `DownloadTests(PageCase)`)

**Interfaces:**
- Produces: `GET /api/download?path=<training>&artifact=<name>[&copy=word]` answering
  `(200, <type>, <bytes>, {'Content-Disposition': 'attachment; filename="<name>"'})`.
  `RunnerPage.download(path: str, artifact: str, copy: str | None) -> tuple`.
  Module constant `KINDS = {'.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation', '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', '.pdf': 'application/pdf', '.md': 'text/markdown; charset=utf-8', '.json': 'application/json; charset=utf-8'}`;
  anything else `application/octet-stream`. `NAMED = re.compile(r'[^A-Za-z0-9._-]+')`.

- [ ] **Step 1: Write the failing tests.** `PageCase.answer` decodes JSON and refuses `<`,
  so these call `self.page.answer(target, self.headers(), 'GET')` directly.
  - `test_a_deck_downloads_as_an_attachment`: start a training to its deck as
    `RunTests` does (reuse its helper), write `101/deck.pptx` with `b'PK\x03\x04deck'`;
    GET `/api/download?path=…&artifact=deck@101`. Assert status 200, type is the `.pptx`
    entry of `KINDS`, the body equals the file's bytes, and the header is
    `attachment; filename="<training folder name>-101-deck.pptx"`.
  - `test_a_word_copy_downloads`: record an export through `workspace.export(root,
    'document@101')` after writing `101/document.docx`; `&copy=word` answers its bytes with
    the `.docx` type.
  - `test_the_index_downloads`: write `README.md`; `artifact=README.md` answers it as
    `text/markdown; charset=utf-8`.
  - `test_refusals`: unknown artifact → 403; `copy=pdf` → 400 "Give copy as word.";
    missing file → 404 "101/deck.pptx has not been made yet."; no key → 403; a symlink
    `101/deck.pptx -> /etc/hosts` → 403 with "leads outside the training folder"; a path
    this computer does not know → 403.
- [ ] **Step 2: Run them and see them fail.**
  `cd studios/training/tests && python3 -m unittest test_runner_page.DownloadTests -v`
  Expected: FAIL, 404 "Nothing is served here."
- [ ] **Step 3: Implement.** Add `'/api/download'` to `READS`. In `read`:
  `if path == '/api/download': return self.download(one('path'), one('artifact'), given('copy'))`
  (a local `given` like the one for `deck-draft-ticket`). `download`: `desk.registered(path)`;
  `root = Path(path)`; for `README.md` use `pipeline.INDEX`; else `root, session =
  desk.artifact_of(path, artifact)` and `relative = workspace.artifact(root, session,
  artifact)['file']`; for `copy == 'word'` use `(session['exports'].get(artifact) or
  {}).get('file')` (404 "There is no Word copy of <label> yet." when absent); any other
  `copy` is 400. `file = desk.inside(root, relative)`; not a file → 404. Name:
  `NAMED.sub('-', '-'.join(filter(None, [root.name, level, Path(relative).name])))`.
  Return the four-tuple; `respond` already passes `extra` headers.
- [ ] **Step 4: Run the tests and the module.**
  `cd studios/training/tests && python3 -m unittest test_runner_page -v` → PASS.
- [ ] **Step 5: Commit.** "Let the Training Studio page download what a training made".

## Task 2: Download buttons on Training Studio's page

**Files:**
- Modify: `studios/training/skills/training-studio/scripts/desk/app.js` (new
  `downloadFile`, the gate's `shown.kind === 'file'` branch ~2040, `madeCard` ~4917,
  `copyItem` ~5205, `combinedReview` ~5825, `drawIndex` ~7740)
- Test: `studios/training/tests/test_desk.py` (`PageScriptTests`)

**Interfaces:**
- Consumes: Task 1's address.
- Produces: `async function downloadFile(path, params, name, pressed)` which fetches
  `download?` + `URLSearchParams({path, ...params})` with `TOKEN_HEADER`, saves through
  `URL.createObjectURL` and an offscreen `<a download>`, toasts "Downloaded <name>." or
  "<refusal> Nothing was downloaded.", and disables `pressed` while it works.

- [ ] **Step 1: Write the failing test** `test_every_deliverable_can_be_downloaded`: a
  training with an approved guide, a Word copy and a deck file. Answers: the server's own
  `GET /api/training`, `GET /api/gate` for the deck, and for `GET /api/download` an answer
  `{'status': 200, 'type': 'application/vnd…presentation', 'body': 'PK'}` (the harness's
  blob answer shape, `page_harness.js:659`). Steps: open the deck gate, click
  `Download deck.pptx`, snapshot; open the training, snapshot. Assert the gate text has
  "Download deck.pptx" and still "Copy where it is"; the toast reads "Downloaded
  deck.pptx."; Made so far has a `Download` control named "Download the learner guide";
  the Word copy row has "Download the Word copy"; `shot['filled']` has at most one entry.
- [ ] **Step 2: Run it.** `cd studios/training/tests && python3 -m unittest
  test_desk.PageScriptTests.test_every_deliverable_can_be_downloaded -v` → FAIL.
- [ ] **Step 3: Implement.** Gate file branch: after `copyButton`, add
  `capsule('Download ' + name, 'quiet', (event) => downloadFile(found.path, {artifact:
  found.artifact}, name, event.currentTarget), 'download-file')`. `madeCard`: each made
  row whose status is not `not-started` gets a second quiet capsule "Download" with
  `aria-label` "Download " + lower(file.label). `copyItem`: a Word copy that is made gets
  "Download the Word copy" (`{artifact, copy: 'word'}`); a Google Doc keeps its link.
  `combinedReview` final phase: each material item gets "Download". `drawIndex`:
  "Download the index" (`{artifact: 'README.md'}`).
- [ ] **Step 4: Run** `test_desk` → PASS.
- [ ] **Step 5: Commit.** "Put Download beside every deliverable on the Training Studio page".

## Task 3: Bring a Google Doc's changes in from the page

**Files:**
- Modify: `studios/training/runner/copies.py` (new `pull`, `REWORDED` first entry),
  `studios/training/runner/engine.py` (new `Engine.pull_copy`), `studios/training/runner/page.py`
  (`copied`), `studios/training/tests/runner_support.py` (`Copies.pull`),
  `desk/app.js` (`copyItem`, `copiesCard`, new `pullCopy`)
- Modify: the matrix (rows 119, 120)
- Test: `studios/training/tests/test_runner_copies.py`, `test_runner_page.py`,
  `test_desk.py`

**Interfaces:**
- Produces: `copies.pull(root, name, google=None, choose=None) -> dict` where `choose` is
  `None` (bring the Doc's edit in), `'theirs'` (use the Doc's kept text) or `'ours'` (push
  this version with `force=True`). Returns `{'result': 'pulled' | 'kept' | 'both-changed'
  | 'nothing', 'beside': str | None}`. `Engine.pull_copy(path, artifact, choose) -> dict`
  (the run's view). `POST /api/copies` gains `{"path", "pull", "choose"?}`.
- Sentences: `PULLED = "The Doc's changes are in. Review {label} again; what is built from
  it is made again after you approve."`, `BOTH = "{label} was changed here and in its
  Google Doc. The Doc's text is kept beside it; nothing was replaced. Choose which to
  keep."`, `KEPT_OURS = "This version is sent to the Google Doc, replacing what was changed
  there."`. `REWORDED[0]` becomes "Someone has changed the Google Doc since it was last
  sent, so it was left as it is. Bring the Doc's changes in from here, then {AGAIN}."

- [ ] **Step 1: Failing tests** in `test_runner_copies.py`, class `PullTests`, using
  `test_google.FakeTransport` as `CopiesTests` does:
  - `test_row_119_a_doc_edited_elsewhere_is_brought_in`: approve the guide, make its Doc,
    change the Doc's text in the fake; `copies.pull(root, 'document@101', drive)` returns
    `'pulled'`; the guide's text is the Doc's; `workspace.statuses` says `draft`; the
    deck built from it is `stale`.
  - `test_row_120_both_changed_keeps_both`: also edit `101/document.md` here; `pull`
    returns `'both-changed'` with `beside == '101/document.remote.md'`, and both texts are
    unchanged. Then `choose='theirs'` saves the remote text as an edit; separately
    `choose='ours'` pushes with force and the fake's text equals the local file.
  - Engine/page in `test_runner_page.py`: `post('copies', {'path', 'pull':
    'document@101'})` answers the run; while a worker holds that level it is 409 with
    "It is being worked on. Bring the Doc's changes in once it stops."
  - Page in `test_desk.py`: a copy whose problem starts "Someone has changed the Google
    Doc" shows "Bring the Doc's changes in"; after a `both-changed` answer, "Use the Doc's
    version" and "Keep this version and send it" each open a sheet naming what is
    replaced.
- [ ] **Step 2: Run** `cd studios/training/tests && python3 -m unittest test_runner_copies
  test_runner_page test_desk -v` → FAIL.
- [ ] **Step 3: Implement** `copies.pull`: `google = google or gdocs.GcloudTransport()`;
  `choose == 'ours'` → `gdocs.push(root, name, google, force=True)`; `'theirs'` → read
  `<file>.remote.md`, `workspace.save(root, name, source=<it>, edit=True)`, update the
  link's hashes as `gdocs.pull` does (factor that tail of `gdocs.pull` into
  `gdocs.settle(root, name, entry, text, remote)` and call it from both); else
  `gdocs.pull(root, name, google)`, catching the both-changed `WorkspaceError` (it names
  `.remote.md`) into `'both-changed'`. `Engine.pull_copy` holds `files`, refuses while
  `self._busy_on(root, artifact)`, calls it, `_make`s again, commits "bring the Google
  Doc's changes into <label>, as asked on the page", wakes the run. Stand-in
  `Copies.pull` does the same against `self.drive`. Page: `pullCopy(found, choose,
  pressed)` posts and toasts `PULLED`/`BOTH`/`KEPT_OURS` from the server's `said`.
- [ ] **Step 4: Matrix.** Add rows 119 ("Approved file, its Doc edited elsewhere | Bring
  the Doc's changes in | File holds the Doc's text, not approved; downstream out of date |
  `PullTests.test_row_119…`") and 120 ("File and Doc both changed | Bring in, then choose |
  Both kept until chosen; theirs saved as an edit or ours pushed with force |
  `PullTests.test_row_120…`").
- [ ] **Step 5: Run** the three modules and `test_google` → PASS.
- [ ] **Step 6: Commit.** "Bring a teammate's Google Doc edit back into a training from the page".

## Task 4: Balanced writes the briefs after its first combined review

**Files:**
- Modify: `studios/training/runner/reviews.py` (`PREPARED`, `contents`, `group`,
  `commits`, new `layout(run)` and `preparing(run, step)`), the place a run record is
  created for a browser run (`engine.py` ~402, where `'review_policy':
  review_policy.capture()` is set on a new record, and ~970, where the form's level is
  recorded), matrix row 121
- Test: `studios/training/tests/test_review_levels.py`

**Interfaces:**
- Produces: `reviews.LAYOUT = 2`; `reviews.layout(run) -> int` (`run.get('review_layout',
  1)`); `reviews.preparing(run, step) -> bool` (true for a step `group` puts before a
  combined review under the run's layout); `DIRECTION_PREPARED = ('research-plan',
  'research', 'blueprint', 'document')` used under layout 2, `PREPARED` unchanged for 1.
  `commits(...)['materials']` lists only stages not yet written at the stop.

- [ ] **Step 1: Failing tests:**
  - `test_balanced_reviews_the_direction_before_any_brief_is_written`: a new Balanced
    training with levels 101 and 201, guide, brief and deck; run the scripted workers to
    the first stop. Assert the run waits at `review:direction`; `101/document.md` and
    `201/document.md` exist; no `*-brief.md` exists; the review's items have no `brief@`
    target; `commits` materials are `['brief', 'scenario', 'yoodli']` filtered to those
    wanted, with `deck: True`.
  - `test_row_121_a_run_past_its_direction_review_keeps_it`: a record with no
    `review_layout`, approved direction (its signature from the old `contents`), briefs
    written. Survey: `review:direction` is in `completed`; no new brief job is queued.
  - `test_approving_the_direction_writes_the_briefs_then_builds`: approve; the next jobs
    are the briefs, then the decks.
- [ ] **Step 2: Run** `cd studios/training/tests && python3 -m unittest test_review_levels
  -v` → FAIL.
- [ ] **Step 3: Implement.** New runs get `run['review_layout'] = reviews.LAYOUT` where
  the policy is snapshotted. In `group`, under layout 2, `step.stage == 'brief'` (and its
  `copies:` step) goes to `build`. `contents(..., 'direction')` uses `DIRECTION_PREPARED`
  under layout 2. `commits` filters `pipeline.wanted(session)` to stages with no file
  written yet. `preparing(run, step)` returns whether `group` would place the step in
  `prep`.
- [ ] **Step 4: Matrix row 121** ("Grouped run with no review layout, direction approved |
  Survey after upgrade | Direction stays approved; old grouping kept |
  `test_row_121…`").
- [ ] **Step 5: Run** `test_review_levels test_runner_engine test_runner_flow` → PASS.
- [ ] **Step 6: Commit.** "Write a Balanced training's briefs after its first combined review".

## Task 5: Finish this level where it can be, and a bead for each combined review

**Files:**
- Modify: `studios/training/runner/engine.py` (`_controls` ~4237, new `review_beads`),
  `studios/training/runner/page.py` (`with_run`), `desk/app.js` (`controlsPart` ~5289,
  `STAGE_BEADS` if a new state is needed — it is not), matrix row 122
- Test: `test_review_levels.py`, `test_runner_page.py`, `test_desk.py`

**Interfaces:**
- Consumes: `reviews.preparing` (Task 4).
- Produces: `Engine.review_beads(path, stages: list[dict]) -> list[dict]`, inserting
  `{'stage': 'review:direction' | 'review:final', 'name': <step label>, 'state': 'done' |
  'review' | 'not-started', 'words': desk.STAGE_STATES[state]}`.

- [ ] **Step 1: Failing tests:**
  - `test_row_122_finish_level_waits_for_building` (test_review_levels): Balanced, working
    on `document@101`; `view()['controls']['finish_level']` is None. After the direction
    review is approved and `deck@101` is being built, it is `'101'`.
  - `test_combined_reviews_have_beads` (test_runner_page): a Balanced training waiting at
    `review:direction`; `get('trainings')`'s item has a stage `review:direction` after
    `brief` with state `review`, and `review:final` before `package` with state
    `not-started`; a Step by step training has neither.
  - In `test_desk.py`, the run screen's text has the new bead's name and no
    `bareBeads`; under building, controls say "The final review waits until every level
    is made."
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** `_controls`: `building = ... and not (grouped and
  reviews.preparing(record, ahead))` where `grouped = review_policy.level(record) in
  ('balanced', 'automatic')`; add `'grouped': grouped` to the dict. `review_beads`: survey
  the run, find the boundary steps `reviews.group` returned, compute each state from
  `found.done`/`found.next`, insert after the last of `('blueprint', 'document', 'brief')`
  present (direction) and before `package` (final). `with_run` replaces `item['stages']`
  when the engine returns a row. Page: `controlsPart` appends the sentence when
  `found.grouped`.
- [ ] **Step 4: Matrix row 122.** **Step 5: Run** → PASS.
- [ ] **Step 6: Commit.** "Offer Finish this level only while a level is built, and bead the combined reviews".

## Task 6: What happens after a decision stays, and Yoodli's copy buttons in every review

**Files:**
- Modify: `studios/training/runner/engine.py` (`decide`, the combined review's approval in
  `reviews.Reviewing`, `view`), `desk/app.js` (run intro, `yoodliCopies` ~2135,
  `combinedReview` ~5825, the Done screen's finished part ~5315)
- Test: `test_runner_page.py`, `test_desk.py`

**Interfaces:**
- Produces: `record['last_decision'] = {'label': str, 'decision': 'approve' | 'revise' |
  'accept', 'at': ISO time, 'next': str}`; the view's `decided` is that dict while the
  run is working and has no gate, question or problem recorded after `at`, else None.
  `yoodliCopies({artifact, text})`.
- Sentence: "You approved <label> at <h:mm>. <next>" (the time as the page formats
  others, `clock(at)`), and for a change request "You asked for changes to <label> at
  <h:mm>. <next>".

- [ ] **Step 1: Failing tests:** `test_a_decision_is_said_until_the_next_stop`
  (test_runner_page): approve the guide; `get('run')['decided']['label']` is "the learner
  guide" (Phase 2's label); after the run reaches the next gate, `decided` is None.
  `test_yoodli_fields_copy_from_the_final_review` (test_desk): a Balanced training at
  `review:final` with a Yoodli scenario; the review's text has "Copy into Yoodli" and a
  "Copy Scenario name" control.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** as in Interfaces; the run intro draws
  `decided` as a `p` with `role="status"` above the now-line. **Step 4: Run** → PASS.
- [ ] **Step 5: Commit.** "Keep what a decision set going on the run screen, and offer Yoodli copies in every review".

## Task 7: Blog Studio's missing starts, a full Done card, and ideas that finish

**Files:**
- Modify: `studios/blog/skills/blog-studio/assets/management/runner.js` (`sStartTasks`
  ~311, the start form ~173 for a `revise`/`review` choice, `sDoneCard` ~846),
  `studios/blog/skills/blog-studio/scripts/blog_runner.py` (`develop` ~2411),
  `studios/blog/README.md` (the starts list)
- Test: `studios/blog/tests/test_blog_runner.py`, `studios/blog/scripts/ci/check-management.cjs`

**Interfaces:**
- Produces: start tasks `['Outline only', 'Work out the argument and stop before
  drafting.', () => newBlog('', null, 'outline')]` and `['Revise or review a draft',
  'Bring a manuscript; improve it keeping the original, or get feedback without a
  rewrite.', () => newBlog('', null, 'revise')]`; the form for `revise`/`review` shows a
  segmented choice "Improve it" / "Give feedback only" that sets `draft.mode`.

- [ ] **Step 1: Failing tests.** `test_blog_runner.py`
  `test_a_developed_idea_is_reviewed_and_packaged`: create an `ideas` blog, approve its
  outline, `dispatch(root, 'develop', {...})`; the run's pipeline is `['outline',
  'draft', 'review', 'package']` and `record['stop_point'] == 'package'`. New journey in
  `check-management.cjs`, "starts on Home: Outline only, Revise or review a draft, and
  the Done card's Pre-publish and Repurpose": Home lists both new cards; choosing "Revise
  or review a draft" shows the manuscript upload and the choice; a finished blog's Done
  card has "Pre-publish check" and "Repurpose" enabled with a manuscript. Add its label to
  the journeys list (`check-management.cjs:101`).
- [ ] **Step 2: Run** `cd studios/blog/tests && HOME=$TMPDIR/h python3 -m unittest
  test_blog_runner -v` and `node studios/blog/scripts/ci/check-management.cjs` → FAIL.
- [ ] **Step 3: Implement.** In `develop`: `run['pipeline'] = ['outline', 'draft',
  'review', 'package']`, `record['stop_point'] = 'package'`. Page as in Interfaces;
  `sDoneCard` adds `sButton('Pre-publish check', () => sPrepublishTool(found.id))` and
  `sButton('Repurpose', () => sRepurposeTool(found.id))` to its first bar, disabled
  without `sCanEdit(found)`. README: the starts list names the same cards.
- [ ] **Step 4: Run** → PASS; `ruff format --check . && ruff check .` in `studios/blog`.
- [ ] **Step 5: Commit.** "Put Outline only and Revise or review a draft on Blog Studio's Home, and finish developed ideas".

## Task 8: Open a finished blog as a Google Doc

**Files:**
- Create: `studios/blog/skills/blog-studio/scripts/google_handoff.py`
- Modify: `scripts/google_drive.py` (`Client.import_new`: `.md` as `text/markdown`),
  `scripts/google_workflow.py` (factor the `prepare` and `confirm` branches of `command`
  into `prepare_transfer(root, ident, kind, new_document)` and `confirm_transfer(root,
  ident, kind, transfer, snapshot)`; `command` calls them), `scripts/management.py`
  (route `google-open` in the mutating dispatch beside `google-start`),
  `assets/management/runner.js` (`sDoneCard`), `references/page-tools.md`,
  `references/short-commands.md` (the page now does the first handoff too)
- Test: `studios/blog/tests/test_google_handoff.py` (new), `test_google_drive.py`,
  `check-management.cjs`

**Interfaces:**
- Produces: `google_handoff.open_as_doc(root, ident, client=None, capture=None) -> dict`
  returning `{'url', 'id', 'transfer'}`; `client` defaults to `google_drive.Client(account
  _for(root))`, `capture` to `google_roundtrip.capture`. Refusals (`ValueError`, shown as
  409): `NOT_SIGNED_IN = 'Google is not signed in on this computer. See Status → Check this
  computer, then try again.'`; `NOT_FINISHED = 'Finish the blog first; its approved draft
  is what goes to Google.'`; `RECONCILING = 'The last upload is being checked. Wait for it,
  then look at the blog again.'` (a receipt in `submitting`).
- Page sheet: title "Open as a Google Doc?", body "This makes a new Google Doc of the
  approved draft in your Google Drive, private to you. Nothing is shared.", send "Make the
  Google Doc".

- [ ] **Step 1: Failing tests** in `test_google_handoff.py` with a fake client built from
  `test_google_roundtrip.Provider` plus an `import_new` that records its call and returns
  `{'id': 'doc-1', 'url': 'https://docs.google.com/document/d/doc-1/edit'}`:
  - `test_a_finished_blog_becomes_its_linked_doc`: finished blog; `open_as_doc` returns
    the url; `editorial.doc_link(record)['url']` is it; the transfer is `confirmed`; the
    fake saw one import of `text/markdown` with the draft's bytes.
  - `test_refusals`: unfinished → `NOT_FINISHED`; `active_account` patched to None →
    `NOT_SIGNED_IN`; a receipt left `submitting` → `RECONCILING` and no second import.
  - `test_google_drive.py`: `import_new` of a `.md` file sends `text/markdown`.
  - Journey "Open as a Google Doc, confirmed, private, once" in `check-management.cjs`.
- [ ] **Step 2: Run** `cd studios/blog/tests && HOME=$TMPDIR/h python3 -m unittest
  test_google_handoff test_google_drive test_google_workflow -v` → FAIL.
- [ ] **Step 3: Implement** in the order of the spec's B2 steps 1-4, under the studio's
  workspace lock the dispatch already holds; the receipt path is
  `google_drive.staging_path(root, 'handoff-' + ident, '.json')`.
- [ ] **Step 4: Run** the three modules, `test_google_roundtrip`, the CI journeys, ruff,
  `measure_guidance.py --check`, `command_reference.py --check` → PASS.
- [ ] **Step 5: Commit.** "Open a finished blog as a private Google Doc from the page".

## Task 9: Apply the review's findings

**Files:**
- Modify: `scripts/blog_runner.py` (`dispatch`: action `apply-review`; `decide`'s
  `changes` path reused), `scripts/blog_worker.py` (the draft job's request when
  `run['stages']['draft']['apply_review']`), `assets/management/runner.js` (gate actions
  at `package` and `review`, a confirmation in `sConfirm`)
- Test: `test_blog_runner.py`, `test_run_recovery.py` or the nearest run test,
  `check-management.cjs`

**Interfaces:**
- Produces: run action `apply-review` (fields `id`, `expected`), allowed when `REVIEW.md`
  exists and the run waits at `review` or `package`. It records `{'status': 'pending',
  'request': APPLY_REQUEST, 'apply_review': True}` on `draft` and lets `review` and
  `package` be written again. `APPLY_REQUEST = 'Apply only the findings in the review
  below. Edit only the passages they name; change nothing else. Keep the author's voice,
  qualifiers, numbers, links and quotations.'` followed by `REVIEW.md`'s text.
- Confirmation: title "Apply the review's findings?", body "This edits the draft for the
  review's findings only, then reviews it and writes the handoff notes again: three jobs."
  (Phase 2's price sentence appended where it exists), send "Apply them".

- [ ] **Step 1: Failing tests:** `test_apply_review_edits_only_for_the_findings`: a run
  at `package` with `REVIEW.md`; dispatch `apply-review`; the next job is `draft` and its
  payload's request starts with `APPLY_REQUEST` and contains the review's text; after a
  scripted draft, `review` then `package` run. `test_apply_review_needs_a_review`: no
  `REVIEW.md` → "There is no review to apply yet." Journey "Apply the review's findings,
  confirmed, three jobs".
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS; ruff.
- [ ] **Step 5: Commit.** "Let a blog's review findings be applied as a minimal edit".

## Task 10: The review aside, open, with real checks

**Files:**
- Modify: `scripts/blog_runner.py` (`submit`'s preservation note ~1257 → stage data;
  `document` ~2349 checks), `assets/management/runner.js` (gate aside ~250-254: open, kept
  per blog in `studio.asideOpen[id]`)
- Test: `test_blog_runner.py`, `check-management.cjs`

**Interfaces:**
- Produces: `run['stages']['draft']['preservation'] = text_checks.preserve(...)`;
  `document()['checks']` rows `{'label', 'passed', 'detail'}` built by new
  `gate_checks(stage, content, rules, copied, preservation) -> list[dict]`. Labels:
  "No voice rule broken" / "<n> <rule name>" with detail "line <n>: <target>" (first 5);
  "No paragraph repeats" / "<n> paragraphs repeat"; the example rows as now; "Numbers,
  links and quotations kept" / "Numbers, links or quotations changed" with each changed
  kind. Rule names: `em-dash` → "em dashes", `double-hyphen` → "double hyphens",
  `banished:<term>` → "uses of “<term>”". No rows → `[{'label': 'No automatic checks
  apply to <stage label>.', 'passed': True}]`. `strip_preservation(notes) -> (notes,
  check | None)` for notes saved before this change.

- [ ] **Step 1: Failing tests:** `test_checks_show_what_lint_found` (a draft with two em
  dashes under a voice with `no_em_dashes`: a row "2 em dashes" with "line 3: —");
  `test_old_preservation_notes_are_read_as_a_check` (notes ending `Preservation check:
  {"needs_review": true, "changes": {"numbers": …}}`: the notes shown no longer contain
  "Preservation check:", and a row "Numbers, links or quotations changed" is present);
  `test_no_always_true_rows` ("Saved document contains readable text" is gone).
  Journey: the aside is open on a gate without a click.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS; ruff.
- [ ] **Step 5: Commit.** "Show a blog's real checks in an open review aside".

## Task 11: Keep a file in the team library, or not, by its row

**Files:**
- Modify: `scripts/management.py` (new route `source-keep` beside `source-role` ~1618,
  new `source_keep`), `assets/management/runner.js` (file rows on the files card ~986)
- Test: `test_team_library.py` or `test_management_ui.py`, `check-management.cjs`

**Interfaces:**
- Produces: `source_keep(root, {'id', 'keep': bool}) -> {'id', 'kept': bool, 'receipts'?}`.
  Keep: a material file becomes a reference (`purposes` with `material` replaced by
  `reference`), saved as a library revision and shared as `source_role` shares. Not keep:
  allowed only for a reference with `revision == 1` added by this computer and not yet
  shared (`receipt` absent), turned back into material. A file a started blog read keeps
  its place: "A started blog read this file from <where>; it stays there. Upload it again
  to change that." Row words: "In the team library" / "Just this blog"; actions "Keep in
  the team library" / "Keep it to this blog".

- [ ] **Step 1: Failing tests** for both directions, the started-blog refusal and the
  shared-reference refusal ("It is already shared with your team; remove it from the
  library screen."); journey "keep or not, file by file".
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS; ruff.
- [ ] **Step 5: Commit.** "Move a blog's file into or out of the team library from its row".

## Task 12: Presentation Studio's direction review needs a look nobody else picked

**Files:**
- Modify: `studios/presentation/runner/engine.py` (`_look_picked` ~2114, the
  `gate:outline` Balanced branch ~2104, `_look_policy` ~2131, the look gate's stop rule),
  `studios/presentation/skills/presentation-studio/scripts/desk/app.js` (`reviewOf`
  ~4936, `paintReviewBar`, the toolbar's Approve, the look panel ~4330)
- Test: `studios/presentation/tests/test_review_levels.py`, `test_step_look.py`,
  `test_desk.py`

**Interfaces:**
- Produces: `record['look_picked'] = {'choice', 'words', 'shown': <sha256 of
  work/look/shown.json>}`; `_look_policy` returns `'stop'` when the shown looks changed
  since the pick (the look gate then waits for the person under any level, with
  `record['look_again'] = {'name': <earlier look's name>, 'choice': <id>}`). Sentence
  `LOOK_AGAIN = "What the deck says changed after you picked {name}, so its looks were
  drawn again. Pick again; your earlier pick is marked."`. Page: `reviewOf(gate).blocked`
  = `'Pick a look to approve the direction.'` or `''`; tally gains "1 look to pick".
  `EDITED_LOOKS = 'You edited the outline, so the looks will be drawn again from it. You
  pick from the new ones before the deck is built.'`

- [ ] **Step 1: Failing tests:**
  - `test_balanced_pick_is_bound_to_the_looks_seen` (test_review_levels): Balanced deck at
    the direction review with looks drawn; approve with `edited` (one slide's title
    changed) and `look: <id>`; after the run goes on, the look gate waits for the person,
    its view says `LOOK_AGAIN` with the earlier name, and `looks.chosen(root)` is None.
  - `test_balanced_pick_without_edit_is_applied`: approve with only `look`; the look is
    chosen with the brand and no look stop happens.
  - Page (test_desk): at the direction review with looks offered and none picked, the
    toolbar's Approve is disabled and the tally says "1 look to pick"; after a pick it is
    enabled; after an outline edit the picker says `EDITED_LOOKS` and Approve is enabled.
- [ ] **Step 2: Run** `cd studios/presentation/tests && python3 -m unittest
  test_review_levels test_step_look test_desk -v` → FAIL.
- [ ] **Step 3: Implement** as in Interfaces; `workspace.sha256_file(root / look.SHOWN)`
  for the fingerprint.
- [ ] **Step 4: Run** → PASS, plus `test_engine`.
- [ ] **Step 5: Commit.** "Hold a Presentation deck's direction review until a look is picked from the looks shown".

## Task 13: The scratch route's brief box

**Files:**
- Modify: `studios/presentation/runner/decks.py` (`check_form` ~95-128),
  `desk/app.js` (`aboutStep` ~2879, `formOf` ~3041), `studios/presentation/README.md`
- Test: `test_decks.py`, `test_step_outline.py`, `test_desk.py`

**Interfaces:**
- Produces: `check_form` returns `notes` (trimmed; `''` when absent; refused over 4000 as
  "The brief can be at most 4000 characters."). Field id `new-notes`, label "What should
  it cover? (optional)", hint "Points, examples or a rough order. It goes to the research
  plan and the outline.", shown only for `draft.route === 'scratch'`.

- [ ] **Step 1: Failing tests:** `test_decks.py` `test_notes_are_kept_and_limited`;
  `test_step_outline.py` `test_the_brief_reaches_the_outline` (a scratch deck whose
  form has notes "Cover rollback first."; the outline job's inputs' "The brief" has
  "Notes: Cover rollback first."); page test that the field shows on scratch only and
  `POST /api/decks` carries `form.notes`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit.** "Give a Presentation deck from scratch a place for its brief".

## Task 14: Your delivered deck stays yours, and a PowerPoint deck can go to Google later

**Files:**
- Modify: `studios/presentation/runner/engine.py` (`_deliver` ~1496, `_whose` or `view`
  ~2818 for `mine`, the change-request path on a finished deck, `deliver_again` ~3111),
  `runner/steps/deliver.py` (`upload(..., output=None)`), `desk/app.js` (`deliverPart`,
  the change sheet on a finished deck)
- Test: `test_engine_team.py`, `test_step_deliver.py`, `test_desk.py`

**Interfaces:**
- Produces: `record['delivered_by'] = team.computer()` when the workspace has drivers;
  the view's `mine` is True for a finished deck with no driver and `delivered_by ==
  team.computer()`; a change request on such a deck calls `self._take(root, space)`
  first, in the same request. `delivering.upload(root, run, slides, output=None)` uses
  `output or form output`. `deliver_again` accepts a deck whose `deliver.json` has
  `output == 'pptx'`, whether by fallback or by choice. Sentences: sheet "It runs from
  this computer again, and your team sees that."; button "Send to Google Slides".

- [ ] **Step 1: Failing tests:** `test_engine_team.py`
  `test_my_delivered_deck_is_changed_without_taking_it` (two people on bare repositories
  as the existing team tests do: A delivers; A's view says `mine`; A asks for changes and
  the record's driver is A; B's view still says it is A's);
  `test_a_teammates_delivered_deck_still_needs_taking`; `test_step_deliver.py`
  `test_a_powerpoint_deck_by_choice_goes_to_google_later` (form output `pptx`; after
  delivery, `deliver_again` with a connected stand-in records a revision with a url and
  leaves `form.output == 'pptx'`); page test for the button and the sheet.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS, plus
  `test_engine`, `test_runner_page`.
- [ ] **Step 5: Commit.** "Keep a delivered deck its maker's to change, and send a PowerPoint deck to Google Slides later".

## Task 15: Docs and the full check

**Files:**
- Modify: Training `docs/runner.md`, `docs/how-it-works.md` (download, pull, the brief
  after the first combined review, the beads); Training `runner/page.py` and Presentation
  `runner/page.py` docstrings (new addresses and fields); Blog `README.md`,
  `CHANGELOG.md` (Unreleased), `references/guided-runs.md`, `references/page-tools.md`;
  Presentation `README.md`, `docs/runner.md`; root `docs/` only where these flows are
  described.

- [ ] **Step 1:** Update the docs in plain sentences, no new terms.
- [ ] **Step 2: Full relevant check.** Training: `python3 scripts/ci/run_tests.py` from
  `studios/training`. Presentation: `python3 scripts/ci/run_tests.py` from
  `studios/presentation`. Blog: `python3 studios/blog/scripts/ci/run_tests.py
  --jobs 6`, `node studios/blog/scripts/ci/check-management.cjs`, ruff,
  `measure_guidance.py --check`, `command_reference.py --check`. Root:
  `PYTHONPATH=.:tests python3 -m unittest tests.test_ui_consistency tests.test_review_policy`.
  Prefer `bash scripts/ci/tart-macos.sh` (inspect with `--dry-run` first). Compare any
  failure with a clean `git archive origin/main` export and report both.
- [ ] **Step 3: Commit.** "Document finishing a piece on the page".
