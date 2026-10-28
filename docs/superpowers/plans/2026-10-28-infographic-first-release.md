# Infographic Studio first-release implementation ledger

Scope: milestone 2, as specified in
[the execution specification](../specs/2026-10-28-infographic-first-release.md),
[product specification](../../infographic-studio-spec.md) and
[original implementation plan](../../infographic-studio-implementation-plan.md).
This ledger records actual implementation and verification; unchecked means pending.

## Dependency-ordered slices

| Slice | Issues | Files and interfaces | Acceptance and verification owner |
| --- | --- | --- | --- |
| 1. Sources, evidence and story | #149 #153 #156 | Native sources.py, evidence.py, stories.py; checked Store mutations | Exact captured bytes/locations, explicit CSV selection, deterministic calculations, all direction modes; native synthetic tests |
| 2. Brand, scene and art direction | #150 #157 #158 #159 | brand.py, scene.py, svg.py, image_brief.py | Pinned constraints; six forms and three presets; required content, editable SVG, actual raster semantics; native/render tests |
| 3. Provider execution and attempts | #151 #152 #154 #160 | images/*, image_jobs.py, visual_review.py | Bounded injected transports; secret isolation; durable intent, unknown/cancel/stale outcomes; actual inspection, shared repair budget |
| 4. Checked desk engine and exports | #161 #162 #163 #165 | checks.py, exports.py, engine.py, history.py, Store | Resume, exact user approval, last-good assets, restore, source/brand invalidation, PNG/PDF/SVG/text; end-to-end synthetic tests |
| 5. Native/API/browser desk | #164 #166 #168 | studio.py, server.py, web/*, native skill/guidance | Three-step intake; story/edit/check/history/export parity; no browser/nested assistant required in conversation; real-loopback/browser checks |
| 6. Shared setup and distribution | #155 #167 #169 | shared preferences/catalog/lifecycle, native and suite installers/pins | Fourth-studio enumeration audit, explicit setup/install, durable native bundle, rollback and subset compatibility; shared tests/bundle acceptance |
| 7. Integrated release acceptance | #170 #171 #172 | CI entry points, README/docs, acceptance matrix | Full relevant suites once, Tart, platform bundles, accessible phone/desktop journeys; separately requested live providers and owner illustration review |

## State-transition matrix

| Action | Required basis | Outcome / failure invariant |
| --- | --- | --- |
| Capture/change source | Current project revision; confirmed CSV selection | Exact raw and normalized capture; invalidate dependent work; history retained |
| Adopt evidence/story | Current source hashes and expected revision | Reject unlocated claims, bad arithmetic and lost requirements |
| Choose story/change brand | Existing story; pinned resolved brand | New revision; prior approval invalid; no implicit generation |
| Start image job | Current image brief, owned intent, supported selected provider | Save intent first; no automatic duplicate after unknown outcome |
| Cancel/late result | Owned attempt and unchanged basis | Revoke adoption; keep last complete page and delivery |
| Edit text/layout | Named elements, exact revision and locked content | Preserve unaffected artwork; invalidate checks/approval |
| Check/review | Current scene/input identities | Unknown inspection stays incomplete; blocking findings prohibit approval |
| Approve/export | Exact current checked revision; explicit user action | Immutable approved delivery; retry export without regeneration |
| Restore | Existing immutable revision and current revision | New revision; approval never restored |
| Setup/launch/status | Existing settings authority and ownership | Preserve workspace; no provider, download or upgrade side effects |

## Completion record

- [x] Read milestone 2 requirements and foundation contracts.
- [x] Define execution specification and dependency/verification ownership.
- [x] Slice 1 implementation and targeted verification.
- [x] Slice 2 implementation and targeted verification.
- [x] Slice 3 implementation and offline targeted verification (live provider gate remains open).
- [x] Slice 4 implementation and targeted verification.
- [x] Slice 5 implementation and real-loopback/browser targeted verification.
- [x] Slice 6 implementation, setup/launch/installer verification and prepared macOS ARM64 platform acceptance.
- [x] Slice 7 offline integration, accessible browser journey and clean-platform acceptance.
- [ ] Separate live generation/reference-edit/inspection acceptance for both providers.
- [ ] Owner review of meaningful conceptual, process and mixed illustrations.
- [ ] Additional platform acceptance before publishing those platform packages.

No first-release feature or issue is complete merely because it is described here.
Live provider, illustration review, additional-platform and publication gaps remain explicit.

## Current evidence boundary

The full shared suite and existing studio regressions passed at `24cc5b84`:
Marketing Studio 666 tests, Blog Studio 1,575, Presentation Studio 1,952 and
Training Studio 2,863. Final native review/approval repairs and the acceptance
fixture's migration from retired run creation to current desk commands were
then verified at `6e90b3df`, reusing the unchanged suites' passing evidence.

The final disposable macOS ARM64 guest passed all 106 native tests with the pinned
renderer and 11 targeted integration/CLI tests. Coverage includes all six forms
in three presets, signed callouts, invalid images/fonts/overflow, located claims
and exact numeric display, durable job recovery, conflicting settings edits,
focused revisions, newer-review invalidation including concurrent final export,
approval and export. The real browser journey passed intake through approved SVG
with an injected assistant, fit/actual-pixel viewing, history, recheck/reapproval,
320/390/1280 widths, light/dark, reduced transparency/motion, keyboard dialog return
and 44 px controls. The selected installed Tanzu Brand exporter also returned a
valid non-slide snapshot in an isolated local contract check; no provider started.

Real native setup, independent shared setup, protected LAN launch, repeated-open
reuse and owned teardown pass for all four studios. Native install/repeat/rollback/
uninstall and source-independent suite/subset tests passed with disposable homes.
The synthetic Hub journey passed 41 steps; the shared-studio CLI journey passed
39 commands, including cross-clone driver handover, offline saves/retry and local
edit protection. Infographic Studio-only packages omit Research/Slides; other
subsets omit its renderer.

Final Tart environment: macOS 27.0 ARM64, Python 3.13.15, Node 22.23.2. Prepared
macOS ARM64 package acceptance passed with private Python 3.13.16 and headless
Chromium 145.0.7632.6: all four actual exports, extracted download removed,
Marketing Studio uninstalled, native app still operational, no Research/Slides
companions and no provider calls. Each disposable VM was deleted; detailed source,
artifact hashes and operational logs are retained outside this public repository.

Live generation/edit/inspection for both providers and owner illustration-quality
review remain open. macOS x64 and Linux x64 package/runtime acceptance remain
unverified; Linux ARM64/Windows renderer bundles are refused. No first-release
issue has been closed and no release published. Documentation-only clarifications
after the tested code do not change these behavioral results.
