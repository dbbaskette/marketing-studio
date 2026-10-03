# Google review suggestions — October 3, 2026

Runtime 1.9 adds the explicit “Push as suggestions” route. Its focused guidance
refreshes the linked Doc and reconciles accepted text/formatting before updating
findings. The helper independently enforces the saved native baseline, exact
quotes, current local writing and the Google revision immediately before writing.
Normal push remains direct editing. A proofread alone never posts to Google.

## Verified locally

- Disposable Tart clone `blog-studio-suggestions-ci-20261003`, macOS 27.0,
  Python 3.13.15: full suite **195 tests passed in 128.860 seconds**.
- After the final Markdown whitespace-boundary fix and missing-manuscript guard,
  the affected Google suite passed **57 tests in 4.117 seconds** and installer
  suite passed **21 tests in 3.512 seconds**, in the same disposable guest with
  a fresh source copy. Unchanged components reuse the full-suite evidence.
- Final offline install/check/uninstall smoke runs passed for Codex, Claude and
  both. Package validation, source integrity, guidance inventory, shell syntax,
  newcomer prompts, skill metadata and whitespace checks passed.
- Tests exercise suggested insertions/deletions, unchanged accepted text, Unicode
  indexes, multiple edits per paragraph, heading/spacing/link preservation,
  exact native comment anchors, partial/uncertain writes, duplicate attempts,
  existing remote finding IDs, changed local/Google inputs and tampered plans.
- Review snapshots keep accepted Markdown and native accepted projection separate
  from the DOCX review export and native thread/anchor record. Tests cover pending
  text exclusion, snapshot hashes, version races, unsupported structures, retained
  unsent local work, checkpoint attachment and Hub artifact retention. Hubs with
  accepted native snapshots require runtime 1.9 even when Google links are present.
- Final logs are local under `/private/tmp/blog-studio-suggestions-ci-results`.
  The disposable CI VM is removed after verification. The signed-in author VM
  is not modified or interrupted.

## Live validation remains separate

No Google account or real document was read or changed. Fixture success does not
prove this account supports the native review API or that Google renders every
suggestion/comment exactly as expected. Use an explicitly selected disposable Doc
and its intended audience for the live pilot, alongside the existing
[G4 live validation](https://github.com/dbbaskette/blog-studio/issues/15).

1. Change heading size/spacing and wording in Google after a local proofread.
   Request “Push as suggestions”; confirm refresh/reconciliation and changed
   findings before submission.
2. Post one replacement, one deletion and one broader comment. Inspect native
   suggestions, exact comment anchors, unchanged accepted text and formatting.
3. Change the Doc after planning. Confirm revision rejection and no direct-edit
   fallback. Never blindly resubmit an uncertain write.
4. Pull with proposals pending, then accept one and reject another in Google and
   pull again. Inspect Markdown, DOCX, native thread states and the Hub snapshot.
   Verify a simultaneous local edit is retained for reconciliation.
5. Inspect account/API restrictions and collaborator notifications. Unsupported
   operations remain unavailable; do not widen access automatically.

Automatic review capture supports one tab and a bounded accepted-text projection:
body paragraphs, headings, bold/italic, ordinary URL links and unordered lists.
Tables, objects, ordered lists, footnotes and embedded line breaks need a scoped
native conversion. DOCX remains the formatting export; native JSON records review
threads. Neither a pull nor a verification call accepts/rejects proposals.

Existing installations need the trusted runtime **1.9 installer update** once;
routine guidance refresh remains separate from executable installation.


## Runtime 1.10 — connector routing and comment review

The installed gcloud adapter already sends native `writeMode: SUGGEST` directly.
Guidance now selects that configured connection when a connector omits the field;
this does not modify the hosted connector or change Google sharing. Automatic
review fallback tries native suggestions, native anchored comments, then ordinary
Drive comments, only after definite rejection or read-only capability evidence.

- Disposable Tart clone `blog-studio-comment-fallback-ci-20261003`, macOS 27.0,
  Python 3.13.15: full suite **216 tests passed in 104.392 seconds**.
- Package/source integrity, guidance inventory, shell syntax, newcomer prompts,
  and real offline install/check/uninstall for Codex, Claude and both passed.
- Twenty new tests cover native-to-comment fallback, quoted Drive comments,
  minor-fix grouping, explicit numbered selections, style preservation, revision
  conflicts, duplicate/resolved comments, partial and uncertain writes, changed
  or ambiguous paragraphs, permission checks and uncertain comment resolution.
- Selected edits are verified before completed comments are resolved. A resolved
  comment alone is never approval; external replies do not authorize edits.
  Uncertain writes are read-only reconciliation cases, never automatic retries.
- Evidence is local under `/private/tmp/blog-studio-comment-fallback-ci-results`.
  No real Google account/document was accessed. The signed-in author VM was
  neither modified nor interrupted.

Extend the separate live pilot above with the following checks:

1. With a connector that omits `writeMode`, confirm the skill selects the already
   configured gcloud adapter for the intended account and document.
2. Inspect both native anchored comments and ordinary Drive comments in All
   Comments. Confirm the latter have readable quotes/sections and are not
   described as native suggestions or sentence highlights.
3. Post several minor fixes in one paragraph. Use “Show review edits,” then apply
   one numbered edit: verify formatting and that the grouped comment stays open.
   Apply the remaining edits and confirm the completed comment resolves.
4. Change wording or resolve a comment manually before applying. Confirm stale
   wording stops the write and resolution is not treated as approval.

Existing installations need the runtime **1.10 installer update** for the new
comment helper. The active review plan and retry ledger remain machine-local.
