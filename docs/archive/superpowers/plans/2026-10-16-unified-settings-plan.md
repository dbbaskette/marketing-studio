# Unified settings implementation plan

Status: proposed alongside the [design](../specs/2026-10-16-unified-settings-design.md).
Implement after the combined design is approved; no separate approval per phase.
Keep existing unrelated work, installation pins and release gates intact.

## 1. Shared contract and resolver

Ownership: `core/studio_core/studios_config.py`, a new settings resolver/schema
module, preferences/onboarding, and configuration tests.

Add validated nested path edits and removal under the current adjacent lock,
versioned model/limits/preferences/studio sections, provenance, inheritance,
explicit null
semantics and capability/applicability reporting. Retain legacy global fields and
one config authority. Resolve assistant/model/effort as a bound selection.

Verify with disposable settings: absent versus null versus explicit override,
reset, nested unknown-key preservation, same-leaf and inherited-dependency
conflicts, simultaneous independent studio writes, invalid groups, idempotent
retries, symlink refusal and permissions. One implementer owns these checks.

## 2. Native setup adapters and migration

Ownership: each native `settings.py`/`setup.py`, Blog Studio configuration and
writing settings, workspace adoption, native page APIs and migration tests.

Consume effective settings; default native saves to studio scope. Add explicit
global editing and reset paths. Migrate supported legacy values conservatively,
reconciling global limits once, removing old private limit controls only after a
successful migration, preserving non-limit Blog Studio workspace defaults at
workspace scope and untouched active
workspace bindings. Expose unsupported controls and older-runtime incompatibility.
Standalone setup bundles the same resolver and UI.

Verify all three native consumers, failures/retries and late independent launch
with disposable homes/Git fixtures. Prove that changing a global default cannot
move a workspace or rewrite existing content/run records.

## 3. Real task-model dispatch

Ownership: shared routing policy; Presentation Studio `jobs.py` and structured
step producers; Training Studio `engine.py` and work producers; Blog Studio
`blog_runner.py`, `blog_worker.py`, `source_curator.py`; existing agent adapters.

Add Quick/Main/Complex purpose metadata separate from the current write/research
permission profiles. Snapshot selections at new-run creation and resolve them
centrally per job. Pass actual model/effort arguments, support inherited/provider
defaults, record provenance, honor bounded escalation and reject unavailable
selections. Deterministic tools do not receive a model job. Do not duplicate
Harness Research/Slides logic or modify those independent repositories.

Verify fixture command lines for both assistants and every studio, independent
checking, ordinary-review routing, scoped repair escalation, cancellation,
resume/import, active-run stability and missing catalogs. No live assistant jobs.

## 4. Global limits enforcement

Ownership: a small shared policy/lease module, each native dispatcher, native
limit-control removal, isolated concurrency and migration tests.

Enforce one job timeout, one cross-studio assistant-job concurrency cap and one
retry ceiling. Adapt the existing spending checks into an explicitly reported-cost
checkpoint; add Blog Studio usage parsing where the adapter reports it and expose
unknown cost honestly. All runners consult the same policy; forbid limit overrides
and remove editable native limit copies. Keep existing stricter workspace/render
invariants. Preserve run authorization when limits rise and apply tightened policy
at the next safe boundary. Use private same-user runtime leases with verified dead
owner recovery, bounded queueing and explicit cancellation.

Verify real disposable processes for aggregate concurrency, simultaneous launches,
crashes, cancellation, PID reuse, no slot leaks and no settings-lock hold during a
job. Stub provider reports to check shared spend/attempt accounting, unknown cost,
legacy limits reconciliation and changed policy between job boundaries.

## 5. Central setup and settings UI

Ownership: `core/studio_core/setup_web/`, Marketing Studio page/computer APIs,
native settings links and shared UI styles.

Promote the approved prototype into accessible production components. Keep the
launcher home. Add scoped navigation, per-field source/reset controls, model
catalog/effort choices, brand discovery, native capability summaries, one global
limits page,
Blog Studio defaults, connections and explicit update actions. Keep optional
setup progressive, saving deliberate and unsaved edits protected on navigation.
Use existing provider/native install adapters; do not store provider secrets.

Verify DOM interactions and actual loopback journeys: choose scope, customize,
save, inherit after global change, reset, conflict/reload, unavailable choice,
offline catalog and standalone return to native UI. Inspect desktop/narrow/dark
and reduced-transparency states. Use meaningful behavior checks, not CSS snapshots
that mirror the implementation.

## 6. Integrated verification and delivery

Ownership: final integrator; reuse milestone evidence for unchanged source.

Update settings docs, CLI status/doctor effective-setting reporting, inventory
and compatibility notes. Extend the existing shared setup acceptance to cover
all three scopes and model job arguments. Run the full relevant root/native
suites once through `scripts/ci/tart-macos.sh`, retaining private logs and clean
VM lifecycle; include native package validators, Blog Studio lint and synthetic
Hub/CLI checks required by its working agreements. No real-account/provider work.

Rebuild versioned/subset platform bundles with the final resolver/UI. Verify
source-independent installation, isolated setup, later standalone launch and
deleting the download. Repeat only affected checks after fixes. Other platforms
need native acceptance before publication. Publishing, upgrading a real install,
issue changes and release actions remain separate explicit user actions.

## Sequencing constraints

Contract/resolver precedes migrations and UI writes. Native effective settings
precede model snapshots. Dispatch support precedes enabling By task in production.
The UI must not advertise a working feature based solely on persisted form values.
Keep phases in coherent increments with targeted milestone checks; retain the
current single-model behavior until end-to-end routing is verified.
