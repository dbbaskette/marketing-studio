# Preserve the team's Google formatting

Load for a linked Doc return, formatting-only save, or wording update. Google Docs
is the live shared editing copy. Store a DOCX export as its formatted Git snapshot,
Markdown as the readable text view, and native structure as fidelity evidence.
DOCX is an export, not a promise to preserve every Google feature or comment.
Never regenerate a formatted working Doc from Markdown merely to change wording.

Use runtime 1.5+ `google_roundtrip.py` beside `google_drive.py`. Existing 1.4
installs need the normal installer update; refreshing guidance alone cannot add
this helper. No extra CLI, credentials or Google permission is introduced.

## Return and snapshot

```text
python3 <runtime>/google_roundtrip.py capture --file-id <id> --tab-id <tab> --output <new-private-directory>
```

Capture reads native content, exports Markdown and DOCX, and checks the document
revision and Drive version again. It writes `document.md`, `document.docx`,
`native.json`, `snapshot.json` and a bounded `observation.json`, without credentials
or expiring image-download URLs. It refuses a changing document, unresolved
suggestions, existing output, or multiple tabs: document exports cannot safely
stand in for a selected-tab return. Use the existing scoped native workflow for
multi-tab documents; do not export other tabs silently.

Inspect the actual Markdown, DOCX and native structure for content, heading levels,
links and formatting. Do not label a capture structurally verified merely because
export succeeded. Mark `structure_verified` in the observation true only after
that inspection when confirming a handoff. Capture does not accept suggestions.

Run the existing `google compare` with `document.md` and `observation.json`; keep
the usual local/remote conflict handling. On `google accept` (or `google confirm`)
pass `--snapshot <directory>`. Exact identity, scope, revision and artifact hashes
must match. The four snapshot files become article history artifacts and sync to
the selected private Team Hub with the checkpoint. They are not added to the skills
repo. Markdown remains the working `DRAFT.md`; DOCX preserves the formatted copy.

If text is unchanged but `format_changed` is true, still accept the inspected
snapshot. This creates a formatting checkpoint without rewriting the manuscript
or staling text-only reviews. A missing earlier formatting fingerprint means the
first capture establishes that baseline. With older Markdown projections, inspect
export-normalization differences once; never hide substantive conflicts as
normalization. No timer or file watcher is added: snapshots happen on requested
returns, formatting saves and verified handoffs.

## Return while suggestions are pending (runtime 1.9+)

For the suggestions workflow use the same capture command with `--include-review`.
It reads current native threads and an explicit suggestions-excluded preview,
exports DOCX, and checks revision/Drive version again. It writes a schema 2
snapshot with `accepted.json` in addition to the four existing artifacts. The
checkpoint retains bounded pending/accepted/rejected/comment counts. Markdown
comes from accepted body text; it never silently includes proposed insertions or
removes proposed deletions. DOCX is the formatted review export and can contain
pending changes; native JSON is the thread/anchor record.

This bounded accepted-text renderer handles body paragraphs, heading levels,
bold/italic, ordinary URL links and unordered lists. It refuses tables, embedded
objects, footnotes and ordered lists rather than losing content or numbering.
For those structures, use the existing scoped native return with explicit
accepted-text inspection. Keep local work intact if no faithful conversion is
available. Inspect export-normalization changes and use normal conflict handling.
Never accept/reject Google suggestions as part of a pull.

## Send wording changes back

First return current Google changes and prepare the frozen local copy using the
existing transfer contract. Read current native paragraph indexes; map only the
requested wording edits into a JSON array, for example:

```json
[{"tab_id":"t.0","start_index":1,"before":"The delay is in handoffs.","after":"The delay comes from handoffs."}]
```

`before` and `after` omit the paragraph's final newline; they are native text, not
Markdown. Include unchanged words inside the chosen paragraph. The helper derives
minimal edits and UTF-16 indexes; the harness does not invent API offsets.

```text
python3 <runtime>/google_roundtrip.py plan --file-id <id> --edits <edits.json> --output <new-plan.json>
python3 <runtime>/google_roundtrip.py apply --plan <plan.json> --receipt <new-receipt.json>
python3 <runtime>/google_roundtrip.py verify --plan <plan.json>
```

Planning is read-only. Check its edits cover the prepared wording and selected
scope before applying under the existing send authorization. Apply rereads,
rebuilds the plan and uses `requiredRevisionId`. It keeps paragraph delimiters,
heading/spacing properties, and unchanged text styles. New text inherits the
replacement's source style. A replacement crossing different styles/links is
refused; split it at style boundaries. It supports plain body paragraphs, including
styled headings and list paragraphs, not table cells, footnotes, inline objects,
new/deleted paragraphs or layout redesign. For these, use explicit scoped native
editing with readback; do not silently fall back to replacing sections.

A receipt is reserved before the single write. On timeout, use read-only `verify`;
do not resubmit with a new receipt. Verification compares native text, character
styles and structure, including other tabs. Any mismatch stays unverified. Capture
fresh exports, inspect fidelity, then confirm the prepared transfer against actual
Markdown readback; `verified` here alone is not a saved Blog Studio checkpoint.
If Google normalized Markdown differently, reconcile using the existing contract.

Keep snapshots out of ordinary prompt context. Read just relevant paragraphs or
format properties; binary exports are stored, not dumped into the conversation.

Provider references: [export formats](https://developers.google.com/workspace/drive/api/guides/ref-export-formats),
[native requests](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/request).
