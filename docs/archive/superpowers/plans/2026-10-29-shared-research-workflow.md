# Shared studio research workflow implementation plan

Status: approved by the user on 2026-10-29. Execute this plan and
[specification](../specs/2026-10-29-shared-research-workflow.md).

One implementer owns each coherent slice; the primary implementer owns final
integration verification. Delegation follows actual user/host authorization.
Reuse the current isolated worktree, retaining its committed prototype until the
new helper-based path replaces it. Do not modify active app files or restart jobs.

## 1. Adopt the released contract and freeze boundaries

Inspect the actual Harness Research 1.1 tagged source, capability/version checks,
asset/collection schemas and tests. Update `pins/companions.json` explicitly with
its immutable release commit and checksum through existing tooling. Verify all
standalone installer references resolve the same pin. This changes source/package
configuration; installing or updating active studios is a separate action.

Relevant existing paths: `core/studio_core/research_contract.py`,
`core/studio_core/companions.py`, `core/studio_core/packaging.py`,
`core/studio_core/research_sites.py`, `pins/companions.json`,
`studios/*/installer/companions.json`.

Outcome: common request/source/progress/transport contracts, compatibility rules,
per-product record versions, state matrix and disposable fixtures. Old schema-2
serial runs and retained runtime selection remain unchanged. Pin `collection-v1`
only for newly started research. Verify optional workflow support separately from
existing report capability; version strings alone do not imply an installed
complete collection runtime.

Owner verification: real pinned helper fixtures, manifest paths for both layouts,
missing helper/capability refusals, old-run readers and immutable pin checks.

## 2. Consolidate source staging and Google scope

Implement proposed `core/studio_core/research_sources.py` and a shared Google
reference intake boundary; select the module split after inspecting native
extraction dependencies. Reuse `google_api.py`, guarded `public_fetch.py`,
`shared_runner/documents.py`, Infographic Studio `remote_sources.py`, and Blog
Studio native tab-scoped capture/projection behavior. Do not import a whole studio
as another studio's dependency. Product code retains manuscript-specific baselines.

The source draft/preview contract uses host-issued identities and expected snapshot
revisions. Sources can be ready, reading, needs-attention or excluded, with selected
tab IDs and warnings. Keep originals privately and retain provenance/limitations.
Do not broaden file sizes or supported extraction implicitly. Public reference
reads use the selected-only boundary; off-page discovery requires explicit search.

Owner verification: multi-file and multiline URLs; duplicated/invalid/redirected
links; selected versus public scope; unsafe URL/path/DNS refusal; missing converters;
partial capture and retained valid peers; shared Google account resolution;
tab-specific links, all-tab reference links, nested tabs and missing tab IDs;
no unselected content in storage/provider input; primary Blog Studio Doc editing
baselines unchanged. Use synthetic native Google responses and injected clients.

## 3. Build the shared execution controller

Implement proposed `core/studio_core/research_session.py` with a small host
transport interface. Use Harness Research asset/collection operations for input
identity, registration, capture receipts, packets, deterministic assembly and
recovery. Remove/supersede the prototype packet/checkpoint/merge implementation in
`research_parallel.py` rather than maintaining two systems. Reuse only appropriate
reservation/timing/host transport code after its callback guards are reviewed.

Phases: capture → bounded collection → connected synthesis → independent review
→ verified local handoff. Reserve remaining supported per-run allowance across
concurrent jobs, preserve existing time/cost/model settings, observe real invocation
identity/termination, guard generation/ownership and support focused repair. Persist
sufficient host bookkeeping for safe process-restart recovery; never claim the
helper cancels a process. Keep provenance manifests and source sharing policy
separate from the reviewed research digest.

Owner verification: barrier concurrency bounds; actual host registration rather
than model labels; cap reservations and unknown costs; peer failure/checkpoint
reuse; stop/paused dispatch; unconfirmed cancellation occupancy; stale generation,
changed permissions/sources/owner and duplicate starts; source permissions/originals;
located fact repair versus prose-only correction; genuine independent reviewer
transport and helper final-digest refusal. No live providers.

## 4. Build the shared source and progress UI

Add `ui-kit/research.js`, using the existing shared tokens/components. Implement
adapter-bound source list, multiple URLs/files/text, tab selection and preview,
external-search scope, saved research selection, collapsed worker/focus options,
progress, retry and reviewed-result handoff. Thin product adapters provide context,
authenticated endpoints and parent actions, not duplicate state machines.

Update the approved shared-link list in `core/studio_core/packaging.py`, page
resource routes, HTML script loading and standalone package checks so every
installed product serves the same component bytes. Use product accents and opaque
forms. Keep the preview file explicitly non-production.

Owner verification: shared component behavior through DOM/browser fixtures;
keyboard/focus/unsaved draft and disclosure preservation under polling; invalid
rows and partial failures; double taps/reconnects; narrow layouts, long source names,
light/dark and reduced effects. Inspect rendered desktop and phone views. Existing
provider/image/publishing actions must not be invoked by source controls.

## 5. Migrate Blog Studio and Presentation Studio adapters

Blog paths: `studios/blog/skills/blog-studio/assets/management/{desk,runner}.js`,
`scripts/synthesis_research.py`, `scripts/google_intake.py`, relevant management
handlers and source-library code located during implementation. Pass existing
source roles and saved study purpose through the new boundary. Keep proofreading
and direct manuscript editing outside the research coordinator.

Presentation paths: `studios/presentation/runner/{research_steps,engine,page}.py`,
`runner/steps/intake.py`, `skills/presentation-studio/scripts/desk/app.js`.
Preserve primary deck/document routes, research opt-out, shared sites and approval
policy. Both products consume the returned verified manifest paths/digest.

Owner verification: new topic, supplied material, optional external search, later
reference update, saved report reuse, existing serial resume, native CLI operation
and relevant UI recovery. Blog Studio's required disposable two-clone Hub journey
covers source roles, editing/saves, offline/retry and local overwrite protection;
no private GitHub repository or credentials.

## 6. Migrate Training Studio and Infographic Studio adapters

Training paths: `studios/training/runner/{engine,pipeline,page,drafts}.py`,
`skills/training-studio/scripts/desk/{app,drafts}.js`. Replace the current prototype
native path with the shared controller and preserve material/level selection,
existing old-run semantics, pause/stop and explicit Ready actions.

Infographic paths: `studios/infographic/runner/{research,remote_sources,sources,server,engine}.py`,
`runner/web/{app.js,index.html}`. Supply a confined research transport based on the
existing configured assistant, rather than using the image-generation pipeline.
Replace the primary JSON/case-folder handoff with the shared research panel. Keep
advanced explicit bundle import compatible. Preserve direct supplied-information
story planning, chart data, image jobs, visual output and final approval.

Owner verification: multi-level research reuse; no duplicate per-level collection;
all four input types; direct supplied-only infographic creation without a research
job; optional topic research then infographic planning; both supported manifest
layouts; no blind image request retry; no unexpected new library or model setting.

## 7. Integrated verification and completion

When the end-to-end slices are coherent, run targeted regressions at their
boundaries, then the full relevant Marketing Studio/native product suites once via
the existing shared Tart runner and project wrappers. Use a self-contained
disposable source clone: a linked worktree's external Git path is not mounted in
the guest. Retain tested source hashes/environment/logs and delete only owned VMs.
Run package/installer and required synthetic CLI/Hub journeys; use no personal
HOME/Google credentials/provider jobs. Keep remote release gates intact.

Use the real pinned helper for final registry/review/bundle acceptance, and a
controlled equivalent-work serial/concurrent benchmark for scheduling only. Do
not infer live provider speed or content quality from simulated timing. Inspect
representative phone/desktop views in all four products. Document any live Google
or cross-provider coverage limits.

Update user docs and state/compatibility matrices. Keep code implementation,
publication and active installation/restart as separate completion claims. Existing
publication authorization applies only within its established scope; never restart
active jobs to deploy. Preserve current saved work and retained helper versions.

## State-transition coverage

| Trigger | Expected behavior | Verification owner/slice |
| --- | --- | --- |
| Add a file/link/text | Capture/preview only; no provider or Google write | 2, 4 |
| Google tab URL | Exact tab preselected; no all-tab fallback | 2, 4 |
| Full Google reference URL | Visible all-tab scope, editable tab selection | 2, 4 |
| External search off | Only supplied refs; no wider discovery | 2, 3 |
| Shared approved sites present | No implicit enablement; strict path policy retained | 1, 2, 4 |
| Invalid/unreadable peer | Ready sources retained; local decision to retry/remove/exclude | 2, 4 |
| Start with stale revision/double tap | Refuse stale inputs / return same operation | 3, 4 |
| One investigator fails | Keep accepted unaffected packets; targeted retry | 3 |
| Pause / Stop | Prevent dispatch / request cancellation; truthful pending state | 3, 4 |
| Source/permission/ownership changes | Invalidate generation; no late adoption | 3 |
| Final review refuses prose | Repair prose from retained evidence and re-review | 3 |
| Final review refuses fact | Re-investigate affected workstream and re-review whole digest | 3 |
| Complete local research, sync fails | Local result retained; retry sync alone | 5, 6 |
| Existing saved serial run resumes | Same retained helper/execution path | 1, 5, 6 |
| Polish/Edit/direct supplied infographic | Optional research remains optional | 5, 6 |

## Review focus

One implementation of source selection and collection coordination, not four forks.
True selected-source scope and Google tab identity. Host-attested invocation/capture
boundaries. Clear optional research versus optional external discovery. Shared
settings defaults without repeated configuration. Cancellation and reuse that keep
work without false completion. Portable verified handoffs with no implicit sharing.

## Completion record

- 2026-10-29: inspected the four current source/research paths and the released
  Harness Research 1.1 contract; prepared this proposal and an interactive synthetic
  preview. No production research adapters, runtime pins or live workspaces changed.

- Implementation: shared source capture, scoped Google intake, source/progress UI,
  real Harness Research collection coordination and all four product adapters are
  present. The Python packet merger prototype has been removed. Focused real-helper
  checks cover concurrency, peer reuse, located repair, exact-digest handoff and
  unconfirmed termination; the source component uses synthetic captures only.
- Ownership is centralized in Marketing Studio: both the execution modules and
  reusable source/progress UI are shared. Product adapters supply authenticated
  routes, native job accounting and the final authoring action; standalone packages
  carry the shared implementation without requiring a running Marketing Studio.
- Integration verification completed using disposable macOS guests: all five
  relevant full suites ran, followed by affected checks for the regressions they
  exposed. Package validation, authenticated phone research/preview/import, all
  four native setup/launch paths and disposable CLI/Hub journeys passed. The phone
  journey used the real pinned helper with synthetic authors and selected text.
- The scheduling benchmark measures controlled synthetic work only. Live Google
  credentials, provider behavior and live content quality were not tested. No
  active installation was updated or restarted and no provider jobs were started
  for verification. Publication and deployment remain separate actions.
