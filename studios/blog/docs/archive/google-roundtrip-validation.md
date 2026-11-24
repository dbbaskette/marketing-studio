# Google formatting round trips — October 2, 2026

Runtime 1.5 adds native Markdown export; DOCX/Markdown/native snapshot bundles;
formatting-only transfer checkpoints; private Hub retention and readable snapshot
links; and minimal paragraph wording patches with revision guards and readback.
The same release adds the conditional house guide and six-type intake selector.

## Verification

- Full suite in the existing Tart VM, Python 3.13.16: **149 tests, 85.990 seconds,
  passing with one skip**. The skipped newcomer browser-script check needed Node
  on the guest PATH; the actual Node check passed on the host.
- After final input-error and library-link changes, affected Google, Hub browse,
  installer and extracted-bundle tests passed in Tart: **38 + 10 + 21 + 1**
  checks, respectively. CI runs the complete suite on Linux and macOS with Python 3.11 and 3.13 before merge.
- Stateful native-Docs fixtures exercise Unicode/UTF-16 indexes, multiple changed
  paragraphs, heading font size, paragraph spacing, untouched links, and exact
  style readback. Stale/tampered plans, uncertain writes, repeated receipts,
  cross-style replacements and structural changes fail without blind retries.
- Snapshot checks cover export version races, multiple-tab scope, suggestions,
  private local files, hashes, malformed DOCX, and exact document identity/revision.
- An end-to-end local Git fixture saves two formatting-only returns, preserves
  text review freshness, transfers all artifacts to a second member, verifies
  readable DOCX links, and confirms unchanged republishing is idempotent.
- Package source integrity, authored links, skill frontmatter, token inventory,
  shell syntax and whitespace are checked. Both distributable archives are rebuilt.

## Boundaries

These are deterministic local tests with synthetic documents and mocked Google
calls, not a live Google Docs rendering/fidelity test. No real Google document,
account or team draft was read or changed by this implementation. Live validation
remains in [G4 / issue 15](https://github.com/dbbaskette/blog-studio/issues/15).

The live pilot should change heading size and spacing in a selected test Doc,
return it to the Hub, inspect the exported DOCX, edit wording locally, send it back,
and inspect Google formatting. Include a formatting-only return, a concurrent
Google edit, a second Hub member, and an unsupported structural edit. Keep private
document text and credentials out of test reports.

Automatic snapshot export currently requires a single-tab Doc without pending
suggestions. Wording patches preserve existing body paragraphs; table/footnote,
object and structural edits use the scoped native workflow. Binary DOCX is the
formatted stored copy; Markdown is the working text view. Snapshots are taken at
requested save/return/handoff boundaries, not continuously.

Existing managed installations need a one-time **1.5 installer update**. Hubs
containing formatted snapshots require 1.5 clients to prevent older projections
from dropping these artifacts. Skill guidance remains separately updateable.

## Freshness status — runtime 1.6

The linked-article resume route now performs a read-only live comparison and shows
one of five statuses, the last check time, and the last confirmed save to Hub.
The local cache never makes a cached status current. A missing formatted baseline,
failed read, suggestions or changed tab scope stays Not checked. All five states,
formatting changes, cache invalidation and failure behavior have deterministic
fixtures. Hub fixtures cover offline queues, unchanged resyncs, confirmed main
saves, another member's checkout and review-required contributions. Confirmation
timestamps are local observations of remote main, not invented commit times.

Named Google milestones remain a manual version-history action; no title changes,
new Doc copies, approval labels or Google writes are implied by a status check.
Status reads do not publish article revisions or alter transfer baselines. This
slice also ships in the 1.6 installer and is covered by the required CI matrix.
Live Google verification remains in G4, as above.
