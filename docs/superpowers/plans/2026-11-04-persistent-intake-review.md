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
together where new documented actions require them. Full relevant suites and package
checks use the existing disposable Tart infrastructure; no personal state or providers.
