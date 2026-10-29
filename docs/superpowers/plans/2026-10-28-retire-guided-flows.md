# Retiring guided flows Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Start and edit desk work in conversation, explicitly migrate eligible unfinished work, and retire current gated creation while preserving supported saved formats.

**Architecture:** Reuse each Studio's desk domain operations and locks. Add read-only inventory completeness and small conversation/migration adapters; retain compatibility dispatch where format evidence prevents removal.

**Tech Stack:** Python 3.11+, standard library, existing JavaScript/CSS, unittest and scripted companions.

**Spec:** [Retire guided flows](../specs/2026-10-28-retire-guided-flows-design.md).

## Global Constraints

- Use full product names; Python 3.11 or newer, standard library only, no frontend build.
- Marketing Studio owns shared settings and launching; each Studio remains independently runnable.
- Use the existing studios-config file and adjacent lock; preserve unrelated values and conflicting-edit guards. Installation folders remain under one Save in Shared settings.
- Preserve original files, history, source and guidance pins, Google baselines, team ownership and readiness. No automatic migration, assistant installation or update, publishing or delivery.
- Only the person approves. Automatic continuation is recorded as continuation, never person approval; new or changed materials are not Ready.
- Follow docs/design/golden-gate.md: material only on navigation, toolbars and transient controls; opaque forms and reading surfaces, one primary action, a lede, 44px controls, no phone overflow.
- Person-facing text never says artifact, stale or lineage, and never exposes hashes.
- Verification uses disposable settings, workspaces, HOME, Git identities and processes. Never launch real Marketing Studio or Studio applications or provider, Google or image jobs. Fake scripted servers are allowed. Do not change workflow files.
- Public issues, PRs and docs contain no credentials, private content or machine-specific operational records.

## Review Focus

- Missing, unreadable, orphaned and unsupported saved records must prevent false unused claims (Task 1).
- A second CLI/page process or teammate changing the input must invalidate a chat save or migration preview (Tasks 2–5).
- Conversation creation must not wake a nested assistant or silently broaden a focused request (Tasks 2–4).
- Migration must preserve real approval history and Google baselines without making unfinished work Ready (Task 5).
- Old installed formats and saved review defaults must remain readable after controls disappear (Task 6).

## Delivery and verification protocol

Tasks 1–6 are sequential independently mergeable PRs; split a task by Studio when
its review surface requires it. Planning ships with Task 1. Task 7 verifies the
combined frozen result. Every implementation is followed by an independent task
review; every PR by a broad fresh review. Fix Important/Critical findings with
meaningful tests. Use bounded SDD fix loops and the private per-plan ledger.

Before every merge: `git fetch origin`, `git merge origin/main`, rerun checks
affected by integration, `git push`, inspect exact `headRefOid` and required checks,
then `gh pr merge --merge --match-head-commit <verified-head>` with normal protection.
If checks are pending use the parent thread's PR watcher and resume on notification.
Link each PR to both owning threads immediately. Do not delete any worktree or branch.

Commands below use `PYTHON` for an available Python >=3.11. For each test invocation,
use a short disposable TMPDIR and HOME, with temporary Studio data/config settings
as existing helpers require. Never set global Git author/committer environment.
Use modest concurrency (`--jobs 2`). Private logs retain the exact interpreter,
commands, outputs, heads, review rounds and rulings; public docs describe synthetic
evidence only. Source must be frozen while full per-class suites run.

### Task 1: Complete read-only inventory across all Studios

**Files:** Modify `core/studio_core/saved_work.py`, both deck `runner/engine.py`
scanners and `runner/studio.py`; create
`studios/blog/skills/blog-studio/scripts/saved_work.py`; wire Blog Studio's
`scripts/studio.py`; modify root `tests/test_saved_work.py`, deck
`tests/test_engine.py` / `tests/test_runner_engine.py`, `tests/test_runner_studio.py`;
create Blog Studio `tests/test_saved_work.py`.

**Interfaces:** Extend `report(ids: tuple, found: dict, *, scope: dict | None=None,
issues: list | None=None, unknown: dict | None=None) -> dict`. Preserve existing
keys and add schema/completeness/status per spec. Add
`gated-flow` to PATHS. `Engine.saved_work(folders=()) -> dict` remains read-only.
Blog Studio exposes `scan(root: Path, folders=()) -> dict` and
`studio.py --root PATH saved-work [--folder PATH]` following its parser conventions.

- [ ] Write tests for a known dependency, clean local scope, explicit missing root,
  corrupt/unsupported record, enumeration failure, excluded symlink, orphan and
  recoverable deleted Blog Studio record. Assert no files/bytes changed, no expiry,
  no worker/network call, `complete == False` and no false unused on unknowns.
- [ ] Run focused tests RED: root `PYTHONPATH=.:tests "$PYTHON" -m unittest test_saved_work -v`;
  Blog Studio `PYTHONPATH=tests "$PYTHON" -m unittest test_saved_work -v`;
  deck Studios `"$PYTHON" scripts/ci/run_tests.py --jobs 2` with the existing
  scanner module names above as positional arguments.
- [ ] Implement schema and enumeration using the existing readers, without
  `catalog()` cleanup side effects or silently filtering unreadable candidates.
- [ ] Run root saved-work and deck scanner/CLI tests plus Blog Studio inventory tests GREEN.
- [ ] Self-review and commit `feat: inventory Marketing Studio saved-work dependencies completely`.

### Task 2: Blog Studio conversation desk and parity

**Files:** Blog Studio `scripts/desk.py`, `desk_jobs.py`, `desk_finish.py`,
`studio.py`, `blog_runner.py`; create `scripts/desk_chat.py`; update
`assets/management/desk.js`, entry guidance and relevant tests; version/manifest.

**Interfaces:** `desk_chat.create(root, data) -> dict`, `read(root, ident) -> dict`,
`save(root, ident, seen, part, text) -> dict` reuse locked desk functions. Expose
`studio.py --root PATH desk create --input FILE`, `desk show --article ID`,
`desk save --article ID --input FILE`; input `-` means stdin. Creation never
calls desk job scheduling; current harness submits content through checked saves. Also expose
`context(root, ident, target) -> dict` and `submit(root, ident, request) -> dict`
as `desk context` / `desk submit --input FILE`, using the envelope below. Blog Studio
supports kinds `text`, `outline`, `part`, `research` and targets `draft`, `outline`,
`research`, or an existing part identifier, with mismatches rejected. Add explicit
`handoff(root, ident, expected_basis, scope)` before full runner continuation;
individually requested page tools remain scoped actions with existing guards.

- [ ] Test conversation creation from supplied draft and scoped topic/outline state,
  checked saves/history, same-part conflict, worker/team refusal, no nested jobs,
  saved author/brand context, Proofread notes/example checks, GEO preview/apply.
- [ ] Run `PYTHONPATH=tests "$PYTHON" -m unittest test_desk_chat test_desk_finish test_desk_start -v` RED.
- [ ] Add the CLI adapter, retain focused scope, pin defaults at creation, carry brand
  through desk context, port safeguards to Proofread and GEO to Finishing.
- [ ] Replace public gated `run create` with an actionable desk-command refusal;
  saved-run operations remain. Update guidance/runtime floors with tested commands.
- [ ] Run focused tests, package validator and `node scripts/ci/check-management.cjs` GREEN; commit.

Task 2 clarification: `set_scope(root, ident, expected_basis, scope)` is exposed as
`desk scope --article ID --input FILE`. Only a person's explicit new request changes
the finite conversation scope. It requires current scope-target context, team and
worker guards under the normal write lock; updates requested scope/provenance only;
and never schedules work, approves or changes material readiness. This permits a
later requested draft in the same conversation article without a browser.

Task 2 outline-edit clarification: `outline_save(root, ident, request)` is exposed as
`desk outline-save --article ID --input FILE` with `{expected_basis, rows}`, using
current `desk context --target outline`. Reuse `desk.outline_save` under normal
team/worker/process/basis guards; existing IDs retain text/History and removals
remain recoverable. Initial outline submission stays restricted to new work.

### Task 3: Presentation Studio conversation desk

Deliver this task in two sequential independently reviewed PRs: **3a** adds the
shared process lock and wires competing writers in both deck Studios without
changing execution ownership; **3b** adds the Presentation Studio conversation
adapter, ownership guards, checked submissions, explicit scope changes and
guidance on top of that reviewed lock. This is a split of Task 3, not added scope.

Synchronization in 3a defers reconciliation and replay while either deck Studio's
existing step markers or Blog Studio's saved working-status records show active
work anywhere in the repository. Stop or wait for work to finish before sharing;
interrupted markers remain for existing recovery. Unreadable worker scope refuses
replay. Final automatic sharing resumes after the current step releases its marker.
All three Studios acquire the shared repository lock before Blog Studio's existing
repository/workspace locks where applicable. Provider/render work stays outside
these short transactions. Deck locks resolve Git directory indirection; Blog Studio
retains its literal `.git/blog-studio.lock` format. A `.git`-file worktree still
supports deck synchronization and checks copied Blog Studio worker records, but
current Blog Studio cannot start writers there. No alternative Blog lock is invented.

**Files:** `studios/presentation/runner/studio.py`, `engine.py`, `decks.py`,
`desk_actions.py`; create `runner/desk_chat.py`, `tests/test_desk_chat.py`;
update SKILL.md, desk/workspace/route guidance, VERSION and manifest.

**Interfaces:** `desk_chat.create(engine, form, uploads=None) -> dict`,
`show(engine, path) -> dict`, `save(engine, path, request) -> dict` exposed as
`studio desk create --input FILE`, `studio desk show --folder PATH`,
`studio desk save --folder PATH --input FILE`. Add explicit conversation execution
mode to creation; runner scheduling and recovery exclude that mode until explicit handoff.
Conversation scope is an explicit finite material list: `text`, `outline`,
`research`, `drawing`, `part`; normalize/dedupe and reject unknowns. It permits kinds,
while exact target, prerequisites and current basis constrain the operation. Never
add research/drawing to an outline request. `set_scope(engine, path, expected_basis,
scope)` is exposed as `studio desk scope --folder PATH --input FILE` and used only
when the person explicitly changes the request; it changes scope/provenance only.

`take(engine, path, expected_basis, scope)` is exposed as `studio desk take`; target
`ownership` context binds the explicit request to continue an idle existing desk in
chat. Require finite scope when absent and retain an existing requested scope. Team,
worker, pending-job and changed-input guards apply; change execution/provenance only,
leaving materials, History, Google baselines, approvals and readiness untouched.
Gated saved formats retain their existing adoption/migration paths.

Targets: text is `brief`, `classification` or `research-plan`; outline/research/drawing
use their named targets; part names a stable current slide ID and known field.
Drawing accepts bounded section compositions (Selected changes accepts a checked
patch). Existing checker/compile/native-preview/brand contracts run on disposable
copies outside the write lock, then publication rechecks current inputs, scope,
workspace, team and canonical worker state. Context includes absent-target bases.
`answer(engine, path, request)` / `studio desk answer` accepts explicit targets
`look` and `design`, both requiring drawing scope, with
`{target, expected_basis, answer}`. Look context binds current offered IDs and inline
PNG previews; answer requires its questionId, exact offered choice or explicit
brand default, and actual person response. Companion design uses canonical `work/`
with actual design_status question/revision and design_respond four-field reply.
Missing/changed/closed questions refuse; preparation never publishes. Neither path
invents approvals, wakes workers or expands scope. Existing words, History and
pins remain. Explicit look/design answers are never inferred. Handoff honors current scope and
pinned inputs or refuses an incompatible remaining saved plan. Also add
`context(engine, path, target) -> dict`, `submit(engine, path, request) -> dict`,
`handoff(engine, path, expected_basis, scope) -> dict`, exposed under `studio desk`.
`context` returns `{target, expected_basis, scope, inputs, requirements}`; submit
consumes `{kind, target, expected_basis, payload}`. Kinds are `text`, `outline`,
`research`, `drawing`, and `part`; each dispatches to the existing Studio checker
and storage, never arbitrary paths. A missing target still has a basis over its
pinned inputs and requested scope. Submission records dependencies/provenance,
never approval. Task 2 uses the same envelope with Blog Studio's supported kinds.

Add `core/studio_core/process_lock.py: ProcessRLock(path)` where `path` is a
zero-argument callable returning the current lock Path. It supports `with`,
`acquire`, `release`, and `_is_owned` for existing store contracts. Acquire thread
RLock then persistent OS process lock, bounded wait, reentrant per owning thread;
release process lock at outermost exit. Lock location is the workspace's resolved
Git directory / `studios-write.lock`, or product data / `studios-write.lock` when
unconfigured. Wire both deck Engine.files instances and competing synchronization
writers; validate lock call sites for mutations outside existing `with files`.
Use the standard-library OS lock already used by studios-config. Tests belong in
`tests/test_process_lock.py` and each engine's concurrent-write tests. Read-only
inventory must remain lock-free. Task 4 consumes this shared contract.

- [ ] Test idea/document/existing-deck creation, original preservation, no assistant
  readiness or wake, no duplicate page pickup, checked outline/notes/word edits,
  team and active-worker refusal, unchanged-section preservation and design answers.
  Add a complete synthetic conversation from absent outline through usable checked
  drawing, and reject an upstream change between context and submission. Add real
  two-process competing writes and page recovery while conversation owns work.
- [ ] Run `"$PYTHON" scripts/ci/run_tests.py --jobs 2 test_desk_chat` RED.
- [ ] Reuse validated creation and desk actions with a no-worker execution branch;
  do not bypass drawing/companion checks or delivery approvals. Support local uploads
  without silently reading Google or broadening the requested work.
- [ ] Update conversation guidance, runtime floor and version; run focused desk/CLI
  suites and `"$PYTHON" skills/presentation-studio/scripts/validate_package.py` GREEN; commit.

### Task 4: Training Studio conversation desk

**Files:** `studios/training/runner/studio.py`, `engine.py`, `pipeline.py`,
`drafts.py`; create `runner/desk_chat.py`, `tests/test_desk_chat.py`; update helper
`training.py`, `workspace.py` only where shared write guards require it; guidance/version/manifest.

**Interfaces:** Same `runner/desk_chat.py` signatures and `studio desk` CLI verbs as
Task 3, using Training Studio forms/material identifiers and `draft_card/draft_save`.
Existing `training.py desk` continues to serve the page. Add `context` and `submit`
with the same envelope defined for Task 3. Current harness saves
initial materials through checked domain submissions, never hand-editing session.json.

- [x] Test no-worker creation for requested levels/materials, focused work, checked
  initial and subsequent text saves, holds and history, team/worker conflicts,
  no Ready on acceptance, explicit design answers, no copies or delivery. Complete
  a synthetic conversation from absent materials through checked usable outputs;
  reject changed upstream inputs, and test page recovery leaves chat-owned work alone.
- [x] Run `"$PYTHON" scripts/ci/run_tests.py --jobs 2 test_desk_chat` RED.
- [x] Implement conversation execution and shared checked submissions; runner cannot
  silently consume the conversation queue. Preserve citations, pins and Google baselines.
- [x] Add matrix rows 186–189 below, guidance/version floors; run focused tests and
  `"$PYTHON" skills/training-studio/scripts/validate_package.py` GREEN; commit.

Training Studio uses finite kinds with native material/level targets, checked initial publication and explicit ownership, scope and answer commands. A focused teaching plan may retain a visibly unprovided research input without inventing research or acceptance; later research holds it. Drawing-bound word answers use actual local proposal token/question/revision/seen and part scope; initial design/look uses drawing scope. Conversation checks run in disposable copies and recheck canonical training plus local proposal/project bytes before bounded publication. Google-target edits retain the delivered link/baseline/approval and keep an explicitly pending local PowerPoint draft; Mark ready refuses while the local draft is pending. The supported exit is an explicit return or set-aside to a proven delivered state or prior absence; there is no pending-draft delivery action on the page or CLI. Ordinary later edits remain local; missing or malformed pending drafts refuse safely. Scope/take preserve material bytes and readiness; scope also accepts explicit optional native materials/deck_target/brand/yoodli selections, preserving omissions and refusing saved-deck conversions. Adding a requested material schedules nothing; runner handoff refuses incompatible effective plans, absent runtime pins and delivery/copy work. `training.py desk` retains page-serving meaning. Saved gated work remains unchanged until the separate migration task.

### Task 5: Explicit guarded unfinished migration

Training Studio retains a usable saved teaching plan and checked existing material parts.
Its original session/run pair stays byte-identical; an immutable receipt and paired desk
records carry conversation interpretation. Apply rechecks the exact preview under the
existing lock and raises only the existing workspace floor to 4.7.0, with exact metadata/
index rollback or explicit crash recovery. Early/unsupported/missing/worker-marked work
keeps its saved flow; old configured instances must be closed. No work or person approval
is inferred. Training Studio matrix rows 190–193 cover this boundary.

Blog Studio increment eligibility: supported saved `DRAFT.md`/`ORIGINAL.md` or a
losslessly round-tripping Markdown outline with at least two heading sections.
Brief-only work and early research/angles without these materials, list outlines
and older Team Hub contexts retain their saved flows until lossless material and
ownership transforms are proven. This increment does not remove all gated formats.
Original session/run bytes stay at their original paths after migration and later
checked saves; fixed desk metadata carries live interpretation. The original
`desk migrate --article ID --expected TOKEN` explicitly recovers an interrupted
additive transaction before rechecking/applying; altered or unreadable migration
records refuse and require restoration. Pending metadata excludes worker/recovery
pickup and synchronization replay even beneath structurally recognized caches.

**Files:** Each Studio's `desk_chat.py` adapter; Blog Studio `desk.py`, deck
`desk_actions.py`, Training Studio `drafts.py`/`engine.py`; each page routing/UI;
create per-Studio `tests/test_desk_migration.py` and extend fake page journeys.

**Interfaces:** Each adapter exposes `migration_preview(..., ident/path) -> dict`
and `migrate(..., ident/path, expected: str) -> dict`. CLI verbs
`desk migration-preview` and `desk migrate --expected TOKEN`; page offers
**Open on the desk** with preview then apply. Tokens are opaque machine values,
not displayed hashes. Existing finished adoption remains available. Add pure
`prepare_migration(record, saved_inputs) -> dict` producing `{blockers, retained,
writes}`; writes are a bounded Studio-defined set, not user-supplied paths. Store
old approval/input records unchanged and desk interpretation separately. Apply
under the process lock with rollback/recovery, including failure between session
and run writes; assign conversation execution before registering migrated work.

- [ ] Test interrupted stages with/without usable materials, unchanged file bytes,
  original record/history preservation, real versus automatic approvals, Google
  baselines, cancel, repeated apply, and rollback after a write failure.
- [ ] Test preview invalidation by teammate, worker, content, source and record
  changes, plus unsupported/missing data refusal leaving original flow usable.
- [ ] Run per-Studio `PYTHONPATH=tests "$PYTHON" -m unittest test_desk_migration -v` RED; implement preview and atomic guarded
  metadata changes using the Studio's existing write lock and ownership checks.
- [ ] Add Training Studio matrix rows 190–193; run migration and finished-adoption
  regressions plus desktop/phone fake journeys GREEN; commit per Studio if needed.

Task 5 Presentation Studio clarification: retain immutable original run bytes and use the
fixed effective `desk/migration.json` + immutable `desk/migration-origin.json` pair, local
`work/desk/migration-transaction.json`, and the existing Presentation Studio workspace
`hub.json` floor (at least 4.8.1 for new migration; preserve higher floors/unrelated values). Preview explains
existing-part scope and closing older runtimes; current guards cannot retroactively change
older configured code. Eligibility and retained early/marker-bearing compatibility follow
the design. Explicit `desk ready` and main **Mark ready** use actual checked-material,
drawing/dependency/freshness/blocker/person-response guards without jobs, delivery or
fabricated upstream approvals. Shared metadata and private local inputs have distinct
verification requirements. Missing paired records fail closed; total external deletion of
all migration evidence cannot be detected from an unchanged old run alone.

### Task 5d: Preserve shared committed evidence and Connect ownership

This bounded increment completes Task 5's shared preservation and ownership boundary
alongside Training Studio migration. It does not expand migration eligibility or retire
additional saved formats. Blog Studio's whole-article/local migration semantics remain
unchanged.

- Require Presentation Studio shared retained candidate-deck files and workspace marker
  to match HEAD, ordinary index entries and working bytes. Include tracked ignored files
  and tracked deletions; keep untracked ignored private inputs local. Refuse with the
  existing saved-flow/Git commit correction path instead of committing original edits.
- Bind relevant shared entries in preview, locked apply and explicit recovery without
  invalidating unrelated commits. Preserve unrelated staging. Recovery and exception
  rollback check the current output index against exact prior/prepared entries before
  changing files or removing the journal; uncertain state refuses intact.
- Marketing Studio Connect validates each product's source and copied effective records,
  changes only the copied effective owner and commits originals plus paired metadata.
  Preserve immutable original/session/receipt bytes, History, approvals, pins and Google
  baselines. Unknown, partial, pending or unsupported-runtime records refuse before copy;
  invalid destinations are cleaned up before commit. No automatic migration or update.
- Cover disposable bare-remote/two-clone replay, local-dirty migrated Connect for both
  deck products, staged-then-reverted inputs, tracked ignored/private ignored inputs,
  relevant preview changes, output-index recovery refusal and unrelated staging.
- Ship Presentation Studio 4.8.1 with its skill/manifest and new migration floor;
  previous 4.8.0 effective metadata remains readable. Marketing Studio 4.5.1 carries
  the Connect correction. Training Studio remains 4.7.0. Close older running instances
  and explicitly update an installed runtime when needed. Local-only dirty migration
  remains usable but is not a complete historical Git backup.

Use focused migration/Connect checks, native package validators and affected frozen
regressions for this increment. The combined frozen suite and retirement review remain
Tasks 6–7; completing this increment does not claim those gates passed.

### Task 6: Retire eligible entry points and document compatibility

**Files:** `core/studio_core/setup_web/{index.html,app.js}`, `preferences.py`,
`review_policy.py`, `shared_runner/setup.py`; each Studio's settings routes/UI,
engine start guards, research stand-ins and relevant tests; current docs/guidance,
versions/manifests; create `docs/saved-work-compatibility.md`.

**Interfaces:** Existing saved policy/layout/research format readers stay supported.
New starts cannot request gated flow. Remove review-level write controls/routes;
unrelated settings Save preserves stored review values. Replace `LEGACY_RESEARCH`
with synthesis for ordinary fixture starts; legacy fixtures load saved formats directly.

- [ ] Test omitted controls preserve review/installation values under one Save,
  conflicting settings edits still refuse, old saved runs still resume, no current
  creation/guidance routes into gates, synthesis fixtures drive normal starts.
- [ ] Run settings, policy, synthesis and legacy fixture tests RED; remove only
  eligible controls/creation/fallback branches. For every deletion document caller
  evidence, saved-format regression and replacement path; retain uncertain paths.
- [ ] Document retained queue/layout/cover/gated compatibility and exact exit
  criteria, local scan limits, migration commands, focused chat behavior and no-worker starts.
- [ ] Run affected suites/journeys/validators GREEN, inspect guidance links and
  person-facing text, update versions/runtime floors and commit.

### Task 7: Frozen combined verification and closure

**Files:** Only corrections justified by combined verification, with independent
review; tracking issue and PR descriptions updated with safe final evidence.

- [ ] Fetch and integrate latest origin/main before final verification. Freeze source.
- [ ] Run root `PYTHONPATH=.:tests "$PYTHON" -m unittest discover -s tests -v`.
- [ ] Run each Studio `"$PYTHON" scripts/ci/run_tests.py --jobs 2`; run each package
  validator, Blog Studio `node scripts/ci/check-management.cjs`, and affected root
  settings/management fake journeys. Run Ruff with the repository's existing rules.
- [ ] Check Tart availability without installing it; use its shared runner when
  available. Never run native-launch acceptance. Use T3 preview for desktop/phone
  journeys on fake servers only; record fake/live interoperability limits.
- [ ] Fresh most-capable final review of combined scope; one fix dispatch and one
  scoped re-review, adjudicate remaining findings per SDD. Recheck integrated exact
  heads and normal protected merges; list/link/unwatch all PRs before handoff.
- [ ] Close the issue only when all authorized work is merged; report PR merge SHAs,
  tests/skips, retained compatibility, rulings/costs and worktree cleanliness.

## Training Studio state-transition matrix additions

Canonical matrix currently ends at 185. Add these rows to
`studios/training/docs/superpowers/plans/2026-10-12-training-studio-core-pipeline.md`
with `test_row_NNN_*` tests. Rebase IDs if another merged change consumes them.

| Row | Given | When | Then / test assertion |
| --- | --- | --- | --- |
| 186 | Explicit conversation start | Create requested scope | Desk run/session, conversation execution, no worker/copy/approval |
| 187 | Unchanged conversation material | Checked save | History and input basis preserved, material Draft, dependents held |
| 188 | Changed part, active worker or other driver | Chat submit | Refused without mutation |
| 189 | Drawing-bound word proposal | Submit without/with explicit design answers | Missing answers refuse; accepted answers checked through existing drawing path |
| 190 | Unfinished old work | Migration preview/cancel | Read-only, consequences and blockers reported |
| 191 | Preview remains current | Apply migration | Desk metadata added, files/history/pins/baselines kept, no new Ready/work |
| 192 | Ownership, worker or source changed | Apply old preview | Refused without mutation |
| 193 | Applied migration or write failure | Repeat/apply fails | Idempotent or safe refusal; rollback preserves original usable work |
