# Preserve the team's Google formatting

Load for a linked Doc return, formatting-only save, or wording update. Google Docs
is the live shared editing copy. Store a DOCX export as its formatted Git snapshot
and Markdown as the readable text view; native structure is fidelity evidence that
stays on this computer. DOCX is an export, not a promise to preserve every Google
feature or comment. Never regenerate a formatted working Doc from Markdown merely
to change wording.

Use `google_roundtrip.py` beside `google_drive.py` in the installed runtime. Pass
`--root <workspace>`: the helper then uses the Google account remembered for the
workspace, keeps its files in the workspace's private staging folder, and writes
only to Docs linked to a blog there.

## Return and snapshot

```text
python3 <runtime>/google_roundtrip.py --root <workspace> capture --file-id <id>
```

A single-tab Doc needs no tab ID; `--output <new-directory>` is optional. Capture
reads native content, renders accepted text as Markdown, exports DOCX, and checks
the document revision and Drive version again. It writes `document.md`,
`document.docx`, `native.json`, `snapshot.json` and a bounded `observation.json`,
without credentials or expiring image-download URLs, and returns the folder with a
short `summary`. It refuses a changing document, existing output, or multiple
tabs: document exports cannot safely stand in for a selected-tab return. Use the
scoped native workflow for multi-tab documents; do not export other tabs silently.

Pending suggestions, including a teammate's, do not block a capture and need no
flag. Accepted text comes from Google's suggestions-excluded view; proposed
insertions are never included and proposed deletions are never removed. The
capture then also holds `accepted.json` and pending/accepted/rejected/comment
counts (taken from review threads when Google returns them, otherwise counted
from the inline markers). The DOCX is the formatted review export and can show
pending changes. Never accept/reject Google suggestions as part of a pull.

The Markdown is written by the helper's own renderer, the same with or without
pending review, so the same accepted text always produces the same file. It
handles body paragraphs, title/subtitle/heading levels, bold, italic,
strikethrough, underline, superscript/subscript, code font, ordinary URL links,
bulleted and numbered lists and horizontal rules. For a Doc with tables, images,
footnotes or other structure it cannot represent, capture falls back to Google's
own Markdown export and says so (`projection: google-export`); if suggestions are
pending as well, it stops rather than guess at accepted text. Keep local work
intact and use the scoped native return with explicit accepted-text inspection
for those Docs.

Check the returned `summary` (projection, pending suggestions, counts of
paragraphs, headings, list items, links, tables, images and footnotes) against
what you expect of the Doc, and read only the Markdown passages you need. Do not
load `native.json` or the DOCX into context unless the summary shows something
the Markdown lacks. A successful export alone is not structural verification:
set `structure_verified` to true in `observation.json` after that check when a
start or a handoff confirmation requires it.

Run `google compare --id <article> --snapshot <capture>`, then `google accept`
(or `google confirm`) with the same `--snapshot`. The capture folder supplies the
observation and Markdown; identity, scope, revision and artifact hashes must
match. Once a blog has a formatted baseline, accept and confirm require a
capture: a hand-built observation is refused because it would discard that
baseline. `document.md`, `document.docx` and `snapshot.json` become article
history artifacts and sync to the selected private Team Hub with the checkpoint.
`native.json` and `accepted.json` are raw Docs JSON and can contain reviewers'
comment threads, so they stay in the blog folder's `.google-native/` on this
computer (current baseline only) and are never sent to the Hub. Another Hub
member needs none of them: their live status and their own pull work from the
shared fingerprints. A capture taken into staging is removed once its
checkpoint is saved. Markdown remains the working `DRAFT.md`; DOCX preserves the
formatted copy.

If text is unchanged but `format_changed` is true, still accept the capture.
This creates a formatting checkpoint without rewriting the manuscript or staling
text-only reviews. Renaming the Doc or a tab is not a formatting change. A
missing earlier formatting fingerprint means the first capture establishes that
baseline; a baseline saved by an older runtime keeps comparing correctly and is
brought up to date by the next accepted capture. No timer or file watcher is
added: snapshots happen on requested returns, formatting saves and verified
handoffs.

## Send wording changes back

First return current Google changes and prepare the frozen local copy using the
existing transfer contract. Map only the requested wording edits into a JSON
array of paragraphs, giving each paragraph's exact current text and its new text:

```json
[{"before":"The delay is in handoffs.","after":"The delay comes from handoffs."}]
```

`before` and `after` omit the paragraph's final newline; they are native text, not
Markdown. Include unchanged words inside the chosen paragraph. The helper finds
the paragraph by its text and derives the minimal edits and UTF-16 indexes
itself; the harness never supplies API offsets. Add `tab_id` or `start_index`
only when the same paragraph text occurs more than once.

```text
python3 <runtime>/google_roundtrip.py --root <workspace> plan --file-id <id> --edits <edits.json>
python3 <runtime>/google_roundtrip.py --root <workspace> apply --plan <plan.json>
python3 <runtime>/google_roundtrip.py --root <workspace> verify --plan <plan.json>
```

Planning is read-only and returns the plan's path in staging. Check its edits
cover the prepared wording and selected scope before applying under the existing
send authorization. Plan and apply refuse a Doc that no blog in the workspace is
linked to; `--first-handoff` is the explicit exception for a new editing copy
that is not linked yet. Apply rereads, rebuilds the plan and uses
`requiredRevisionId`. It keeps paragraph delimiters, heading/spacing properties,
and unchanged text styles. Replaced text keeps the style of the text it
replaces; inserted text continues the word it extends or otherwise follows the
character before it, and never lengthens a link. A replacement crossing
different styles/links is refused; split it at style boundaries. It supports
plain body paragraphs, including styled headings and list paragraphs, not table
cells, footnotes, inline objects, new/deleted paragraphs or layout redesign. A
paragraph carrying someone's pending suggestion is refused; other paragraphs
stay editable. For unsupported changes, use explicit scoped native editing with
readback; do not silently fall back to replacing sections.

A receipt is reserved before the single write, one per plan. A write Google
refuses outright releases it. On timeout, use read-only `verify`; the same plan
is never applied twice. Verification compares native text, character styles and
structure, including other tabs. Any mismatch stays unverified. Capture again,
then confirm the prepared transfer with that capture; `verified` here alone is
not a saved Blog Studio checkpoint. Confirmation accepts readback that differs
from the frozen copy only in incidental whitespace; any other difference needs
the existing reconciliation.

Keep snapshots out of ordinary prompt context. Read just relevant paragraphs or
format properties; binary exports are stored, not dumped into the conversation.

Provider references: [export formats](https://developers.google.com/workspace/drive/api/guides/ref-export-formats),
[native requests](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/request).
