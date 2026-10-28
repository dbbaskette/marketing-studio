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
- [x] Slice 6 implementation and targeted setup/launch/installer verification; prepared-platform acceptance follows.
- [ ] Slice 7 integration and acceptance.

No first-release feature or issue is complete merely because it is described here.
Live provider, illustration review, platform and publication gaps remain explicit.

## Current evidence boundary

The native suite passes 95 tests with the actual pinned macOS ARM64 renderer,
including all six forms in three presets, invalid images/fonts/overflow, located
claims and exact numeric display, durable job recovery, focused revisions, review,
approval and export. The real browser journey passes intake through approved SVG
with an injected assistant, fit/actual-pixel viewing, history, 320/390/1280 widths,
light/dark, reduced transparency/motion and keyboard dialog return. The selected
installed Tanzu Brand exporter returns a valid non-slide snapshot in an isolated
local contract check; no provider is started.

Real native setup, independent shared setup, protected LAN launch, repeated-open
reuse and owned teardown pass for all four studios. Native install/repeat/rollback/
uninstall and source-independent suite/subset tests pass with disposable homes.
Infographic Studio-only packages omit Research/Slides; other subsets omit its renderer.

Final shared Tart and prepared-platform acceptance are pending at this checkpoint.
Live generation/edit/inspection for both providers and owner illustration-quality
review remain open. No first-release issue has been closed and no release published.
