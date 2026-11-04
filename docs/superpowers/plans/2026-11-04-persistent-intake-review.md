# Persistent intake and slide-text review

Implements #338, #339, #340 and #341 under the approved remaining-issue review.
Reuse the private revision-checked intake store and shared slide editor. Saving a
form or corrections never approves output or runs an assistant, researcher or renderer.

| Before | Explicit action / event | After | Verification owner |
| --- | --- | --- | --- |
| Unfinished infographic intake | Type, change step, add a captured source | Private draft saves; no project/job starts | Native draft API + browser reload |
| Saved intake | Reload / New infographic | Restore fields, step, pinned revisions and acknowledgements | Real protected intake browser |
| Draft saved by another tab | Save or final submit | Conflict; preserve both inputs; no duplicate project | Native revision test + two-tab browser |
| Captured source unavailable | Restore / submit | Keep other answers, identify missing capture, request explicit replacement | Missing-capture fixture |
| Partial explicit submission | Save succeeds then connection fails | Durable request/project identity; resume only the expected revision or open the kept project | Idempotency/partial-submit fixture |
| Nonempty intake | Save and close / confirmed Discard draft | Save privately / discard form only; existing work remains | Nested-sheet keyboard journey |
| Pending slide text | Local edit or feedback | Save private corrections against exact outline basis; no pipeline work | Shared store + both native adapters |
| Saved corrections | Reload / navigate | Restore slide, notes and corrections | Both native browser journeys |
| Underlying outline changed | Load earlier corrections | Show conflict and earlier corrections; explicit reconcile/discard before approval | Exact-basis conflict test |
| Current corrected slide text | Approve all slide text | Validate whole outline; design exactly the approved corrected revision | Training Studio transition + Presentation Studio regression |
| Training Studio guide selected | Pending deck decision | Concise notice; Guide/Brief/Plan tabs remain reachable; full review lives in Deck | Six/30-slide phone browser |
| Long slide review | Select, previous/next, keyboard | One slide editor, compact overview, collapsed notes; visiting does not approve | Shared editor + 390/1280 light/dark/reduced effects |

Maintain native ownership, shared settings locks, source scope, final evidence checks,
legacy run decisions and old approved exports. Native runtime/guidance minimums move
together where new documented actions require them. Verification covers the changed shared store/editor modules, native route and approval
modules, bridge limits, package validators and six/thirty-slide protected browser
journeys. Reuse unchanged full-suite evidence from PRs #348–350. No personal state
or providers are used; no repeated four-studio gate is warranted.

## Verification

The complete affected shared draft/editor modules pass (18 cases), Training Studio
slide-text workflow (7), Presentation Studio slide-text workflow (3), native review
API/capability/request-boundary groups (12 Presentation Studio and 9 Training Studio),
and bridge-limit module (3). Both skill package validators pass. Infographic Studio's
private-intake API checks and real captured-source reload journey pass.

Protected native browser journeys pass for both deck studios at six and thirty
slides, 390/1280 widths, light/dark and reduced motion. Edits, notes and selection
survive reload; one editor stays bounded; focus/caret survive polling; private saves
start zero pipeline jobs. Additional six-slide journeys retain older-basis corrections,
block their approval and allow explicit discard without changing the outline or jobs.
All fixtures use disposable state and scripted workers; these checks make no live
model latency, provider-quality or owner-acceptance claim.
