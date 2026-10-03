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
