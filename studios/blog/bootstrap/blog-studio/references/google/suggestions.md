# Send proofreading as suggested edits

Load only for “Push as suggestions” / “Push these as suggestions to Google Docs.”
Use installed runtime 1.9+ `google_suggestions.py` with the existing gcloud account.
Ordinary “Push to Google Docs” keeps its direct-edit route. A proofread request
alone authorizes local review, not Google comments or edits. Requested suggestion
posting authorizes the selected replacements and their explanatory comments;
do not assign people, add mentions, change sharing, or post unrelated notes.

## Refresh first, automatically

1. Resolve the saved article, linked Doc and selected tabs. Before proofreading
   for submission, run the [return workflow](../modules/blog-google-return.md):
   capture current Google accepted text, formatting and pending review state,
   compare with the saved baseline, and bring back remote-only changes. The
   request to send suggestions includes this prerequisite read/local refresh;
   do not ask the author to issue a separate pull command.
2. Preserve unsent local edits. When both copies changed, show the conflict and
   obtain a resolution using the existing compare/accept contract. Never overwrite
   a local draft to make a suggestion fit. For local-only changes, separate the
   requested review findings from other unsent writing.
3. Refresh findings affected by changed wording. Recheck anchors after formatting
   changes too. Keep pending Google suggestions separate from accepted text. This
   helper refuses another batch while pending suggestions exist; report those
   items for review rather than accepting/rejecting them or posting duplicates.
4. Present each selected finding with original wording, proposed wording and
   reason. Keep proposals in the saved review; do not apply them to `DRAFT.md`
   merely to send them. Reuse stable finding IDs on retries. Use a new ID only
   for a genuinely new finding after an earlier decision, not to bypass a receipt.

## Bounded native plan

Read fresh native inline indexes. Save a private JSON array of findings:

```json
[{"id":"proofread-20261003-1","kind":"edit","tab_id":"t.0","start_index":5,"before":"delay","after":"wait","reason":"Use the author's preferred wording."}]
```

For broader feedback use `kind: "comment"` and omit `after`. Every item needs an
exact single-paragraph quote and its observed UTF-16 index; disambiguate repeated
phrases by location. The helper validates native ranges and styles. It supports
body paragraphs, including headings, with replacements inside a uniform style
or link. Combine overlaps. Whole-paragraph deletion, structural edits, table
cells and embedded objects need scoped native review; no whole-body fallback.

```text
python3 <runtime>/google_suggestions.py --root <workspace> plan --id <article-id> --findings <findings.json> --output <new-plan.json>
python3 <runtime>/google_suggestions.py --root <workspace> apply --plan <plan.json>
python3 <runtime>/google_suggestions.py --root <workspace> verify --plan <plan.json>
```

Planning reads Google and requires the saved formatting baseline to match. Apply
rereads Google and local writing, rebuilds the exact plan, and submits once with
`writeMode: SUGGEST` and `requiredRevisionId`. A concurrent edit stops the write;
return/reconcile and refresh findings before making another plan. Selected
replacements become suggested text changes; their reasons become native anchored
comments. Existing heading levels, spacing and paragraph properties are retained.
No direct-edit fallback is allowed if the API/account does not support review.

A private workspace ledger reserves the attempt before submission. On timeout,
partial result or readback failure, keep that ledger and use read-only `verify`.
Never retry the write under a different plan/ID. Report only `verified-pending`
when native comment anchors/quotes, unchanged accepted text, projected accepted
suggestions, and formatting all match at a stable revision. This confirms pending
proposals, not acceptance or publication. Other outcomes need reconciliation.
Google may send its normal collaborator comment notifications; the adapter does
not promise silent delivery.

## Pull after review

Use `google_roundtrip.py capture --include-review` as described in
[round trips](roundtrip.md), then compare/accept the inspected snapshot. The
Markdown working copy contains accepted text only. DOCX preserves the formatted
export; `native.json` retains pending/accepted/rejected suggestion threads and
comments; `accepted.json` records the accepted-text projection. Do not promise
that DOCX alone retains every Google thread. Review counts are saved in the
checkpoint. Nothing accepts or rejects Google suggestions automatically.

Keep native snapshots, private plans and credentials out of ordinary context.
Read just selected findings/paragraphs. Snapshots share only through the selected
private Team Hub; submission ledgers remain local. Never add writing to the skill
repository. Live account support must be demonstrated; fixture tests establish
client behavior only.

Provider contracts: [suggestions and comments](https://developers.google.com/workspace/docs/api/how-tos/suggestions),
[guarded batch updates](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/batchUpdate).
