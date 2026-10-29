# Infographic Studio conversation and CLI contract

The same validators power the browser and native commands. Application code is
Python 3.11+ with the standard library. Commands print JSON, exit 2 on a refused
request and preserve saved work. Use the current revision from `show`/`inspect`;
never assume it stays unchanged after another tab or assistant action.

## Start with supplied information

```sh
python3 runner/studio.py status
python3 runner/studio.py computer
python3 runner/studio.py setup --workspace /absolute/empty/infographic-workspace
python3 runner/studio.py create 'Restart one instance' --direction direct --preset digital
python3 runner/studio.py source PROJECT_ID --file /absolute/notes.txt --expected-revision 0
python3 runner/studio.py inspect PROJECT_ID
```

Paths above are examples; choose an explicit content folder outside this application.
`serve --open` uses the same saved workspace. `status` does not initialize anything.
Text, Markdown and CSV are UTF-8; URLs remain references. Source bytes and normalized
text are immutable, hash-identified local files. Browser upload is limited to 1 MB;
native source capture allows 16 MB. CSV is never automatically typed:

```sh
python3 runner/studio.py csv-preview --file /absolute/table.csv
python3 runner/studio.py source PROJECT_ID --file /absolute/table.csv \
  --selection /absolute/confirmed-selection.json --expected-revision REVISION
```

Selection JSON is exactly `{"confirmed":true,"sha256":"PREVIEW_HASH","rows":[1,2],
"columns":[{"name":"Count","type":"number","unit":"requests"}]}`. Row numbers
refer to data rows after the header. Types are `text`, `number` or ISO `date`.
Choose exact rows/columns with the user; don't infer types, units or missing values.

`edit-brief ID --file brief.json --expected-revision N` edits the complete existing
brief. Preserve its fields; change title, audience, purpose, must_show `[{id,text}]`,
locked_words, exclusions, direction or preset explicitly. Sources, facts and story
choices are invalidated when their inputs change, while all earlier revisions remain.

## Author directly in this conversation

`facts ID --file facts.json --expected-revision N` accepts an array such as:

```json
[{"id":"f1","statement":"One instance restarts while others serve.",
  "value":"One instance restarts while others serve.","unit":"","status":"supplied",
  "evidence":[{"source_id":"CAPTURED_ID","start":0,"end":46,
               "quote":"One instance restarts while others serve."}]}]
```

Offsets above are illustrative: calculate exact Python Unicode character positions
in the captured normalized text; do not copy guessed offsets. Numeric facts retain
literal `value`, explicit `unit`, `period`, `denominator`, `conditions`, `uncertainty`
and located evidence. Unknown context is an empty string. Derived values use
`calculation:{operator,operands}` with `sum`, `difference`, `ratio` or `percent_change`;
all operand IDs, units and exact arithmetic are checked. Supplied-only facts have
`status:"supplied"`. Missing numeric context blocks misleading charts.

`stories ID --file stories.json --expected-revision N` accepts one directed or
one to three suggested/hybrid stories. Each has `id`, `headline`, `takeaway`,
`rationale`, `qualifications:[]`, `omissions:[]` and one to five `blocks`:

```json
{"id":"b1","kind":"concept","title":"One at a time",
 "text":"The other instances continue serving.","fact_ids":["f1"],
 "required_ids":[],"illustration":true,
 "illustration_role":"Show one restarting instance beside two serving instances."}
```

Kinds are `comparison`, `process`, `timeline`, `numbers`, `parts`, `concept`.
Comparison and parts blocks can describe ideas or components without measurements:
set `quantitative:false` for these unscaled explanations. Set it to `true` for
numeric comparisons or measured proportions; units, periods, denominators and
conditions must then be comparable. Number callouts always need numeric values.
Older blocks without the flag keep their numeric chart behavior when they refer
to numeric facts, and descriptive-only comparisons/components stay qualitative.
Mixed numeric/text facts need an explicit qualitative choice; they never silently
become chart data. No conversion invents a count, percentage or measurement.
Preserve user-required ideas and exact wording. Hybrid cannot omit requirements.
The browser's `suggest` asks a confined assistant to author the same two arrays;
a conversation authors them directly, avoiding a nested planning job.
`--automatic` selects the first valid recommendation; it never approves a page.
An unsuccessful native planning response is saved privately, bound to the same
source, brief and project revision. Repeating `suggest` revalidates that response
locally; use `suggest ID --fresh --expected-revision N` only when you intend a new
assistant request. The action JSON equivalent is `"fresh": true`. Manual `facts`
and `stories` adoption remains strict: it requires literal values, exact captured
locations or reproducible calculations rather than generated-field normalization.

## Compose and edit

```sh
python3 runner/studio.py select ID --story-id STORY --expected-revision N
python3 runner/studio.py brand ID --file /absolute/shared-brand-contract.json --expected-revision N
python3 runner/studio.py layout ID --arrangement stack --expected-revision N
python3 runner/studio.py preview ID --expected-revision N
```

Brand input is the selected installed brand's shared schema-1 contract with explicit
font family and hexadecimal canvas/text/heading colors, not a slide template.
The browser can pin the shared Marketing Studio selection explicitly. Missing fonts
block output. No font, brand or companion is automatically installed.

`build ID --request-id UNIQUE_ID --expected-revision N` performs explicit layout,
renderer preflight, precise art direction and selected-provider generation when the
story calls for artwork. This can consume the selected assistant/provider allowance;
read `computer` and disclose that boundary first. Artwork-free stories make no image
call. Shared Codex uses its built-in image generation; shared Claude Code uses the
Gemini API with an explicit model and adapter-only environment key.

`edit-text ID --element-id ELEMENT --text 'Replacement' --expected-revision N` changes
one named editable label and preserves every other element. It refuses unreadable
fit and changed locked wording. `revise-story` takes `--story-id`, optional `--block-id`
and `--instruction`; a named-block revision refuses any outside-scope change.

`revise-art ID --change 'Exact correction' --preserve 'What stays' --request-id UNIQUE
--expected-revision N` sends the original owned image as a reference. Text/chart
marks remain compositor-owned. The advanced `action` endpoint also accepts
`image-brief` with self-contained direction and optional `edit:{asset_id,change,preserve}`,
`image-start` with provider/brief_id/request_id/operation/parent, `compose-image`
with asset_id, and `art-direct`. Read `runner/image_brief.py` only when authoring a
precise image brief directly: include style, reading_order, acceptance and objects
with id/region_id/count/description/relationships/preserve. Never use inaccessible
file paths or generic decorative prompts.

## Review, approve, export and recover

```sh
python3 runner/studio.py inspect-images ID --expected-revision N
python3 runner/studio.py check ID --expected-revision N
python3 runner/studio.py review ID --export-id EXPORT \
  --observation 'Inspected the actual page at intended size and verified the relationships.' \
  --expected-revision N
python3 runner/studio.py check ID --expected-revision N
python3 runner/studio.py approve ID --expected-revision N
python3 runner/studio.py export ID --expected-revision N
```

Image inspection stages actual composed PNG and original artwork; it returns
located observations and corrections, never approval. If multimodal capability is
unavailable, the user can inspect the actual page and record a manual review.
Checks require current coverage, facts, actual font/layout/asset measurements,
visual review and brand/accessibility. Only explicit user approval authorizes the
`approve` action; assistant tool success is not authorization. Final exports bind
that exact approved revision. `export --draft` is explicitly labeled unapproved.

Exports are immutable PNG, exactly one-page PDF, editable SVG and accessible text.
Embedded artwork remains raster, with exact text and chart marks editable. Font
licenses/availability affect portability; no font binaries are exported. Export
retry reads the existing verified delivery and never regenerates an image.

`history ID` lists immutable versions. `restore ID --revision OLD --sha256 HASH
--expected-revision CURRENT` creates a new revision without restoring approval.
`action ID --file action.json` provides the full checked API. JSON always contains
`action`, `expected_revision` and only that action's fields (see `runner/api.py`).
A `compare` action takes `before` and `after` revision numbers.

`inspect ID` reports pending/unknown image intents even if later content edits
invalidated the visible attempt array. It never resubmits. Cancel with
`image-cancel ID --request-id REQUEST --expected-revision N`; local adoption is
revoked, while remote cancellation and charges can remain unknown. A repeated
request identity cannot spend again. A new explicit attempt needs a new identity.
`repair ID --request-id UNIQUE --expected-revision N` applies a specific recorded
art correction or a layout alternative, within a shared two-attempt automatic
repair budget. Smaller/manual revisions remain possible afterward.


## Follow-up sources and delivery

Local previews never start providers:

```sh
python3 runner/studio.py source-preview --file /absolute/material.docx
python3 runner/studio.py remote-preview --kind google-doc --url https://docs.google.com/document/d/ID/edit
python3 runner/studio.py remote-preview --kind url --url https://public.example.com/page
python3 runner/studio.py source-import ID --capture-id PREVIEW --expected-revision REV
python3 runner/studio.py source-show ID --source-id SOURCE
python3 runner/studio.py handoff-inventory --root /absolute/blogs --studio blog
python3 runner/studio.py handoff-preview --root /absolute/blogs --studio blog --file ITEM/DRAFT.md --expected-sha256 HASH
python3 runner/studio.py research-task ID --source-mode selected
python3 runner/studio.py research-preview ID --case /absolute/reviewed-case --source-mode selected
```

When a preview names extraction gaps, inspect them before adding
`--acknowledge-warnings` to `source-import`. Use `--replace-id SOURCE` for an explicit
refresh. The raw and normalized capture, locations and origin revision are immutable;
replacement clears dependent story/page approval. Google Docs and Slides links use the existing default Google sign-in. `--account` is optional for a deliberate override; import and delivery do not ask for email. Shared Marketing Studio output selects the initial delivery choice. Google tab/slide selection uses repeated
`--tab TAB_ID`; leaving it empty includes all tabs. Pasted links do not trigger a fetch.

After current checks, visual review, user approval and final local export:

```sh
python3 runner/studio.py google-deliver ID --expected-revision REV --export-id EXPORT --request-id UNIQUE_REQUEST
```

Use optional `--folder FOLDER_ID` for a checked explicit destination. Creates a new Doc;
no source write or permission change. PDF remains the exact local render. The Doc has a
page image with alt text, editable text and source notes; Google conversion fidelity is
checked in Docs. A repeated request never blindly resends. Use the original saved values
plus `--reconcile` after uncertainty, including after a local edit; result stays historical.

`team --operation status|connect|sync` reads the local copy or explicitly connects/fetches.
`action ID --file JSON` supports `team-preview` with `export_id`, `include_editable`,
`source_ids`, `asset_ids`; it returns exact files, `inventory_digest`, `expected_head`,
`expected_connection`, `expected_claim`. `team-share` adds those returned values and
`confirm_private: true` for private content. Use the current expected project revision.
Never infer permission to share sources/artwork from importing them. Prompts/job records
are excluded. Native defaults store `team_email`; the name comes from shared settings.

`team --operation claim|take|retry --file JSON` accepts the explicit action fields:
claim/take use `id`, `expected_head`, `expected_claim`; handover adds `new_owner` to claim;
retry uses `expected_commit`. A foreign driver is read-only for sharing until explicit
claim takeover. Local draft edits remain local. A claimed editable import keeps missing
unselected inputs honest, strips approval/checks/jobs and preserves any existing local copy.
