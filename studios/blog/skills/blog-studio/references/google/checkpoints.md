# Local transfer contract

Run `studio.py --root WORKSPACE google ...` from the installed runtime (offline:
packaged scripts). The provider stays in the harness. Do not print whole documents
or shell download logs merely to record a checkpoint. Use untracked workspace
staging files, never the skill repository. Records and transfer text join only
the selected private Team Hub through the normal article/source lifecycle.

## Observation

With the gcloud helper, pass `--snapshot <capture>`: the capture folder from
[round trips](roundtrip.md) supplies the observation, the Markdown and the
formatted snapshot, and nothing is written by hand. A connector-only session
supplies `--file accepted.md --observation observation.json` instead. UTF-8
Markdown with LF newlines must faithfully project **selected accepted text**,
retaining headings, link targets, lists and tables where representable. Use consistent whitespace/Markdown rules
across observations; never manufacture a match by ignoring changed content.
For a writing handoff prefer one selected blog tab; a multi-tab selection needs a
stable, explicit ordered mapping. Do not flatten a template's native structure.

```json
{
  "schema": 1,
  "document_id": "observed-id",
  "url": "https://docs.google.com/document/d/observed-id/edit",
  "tab_ids": ["t.0"],
  "revision_id": "observed-revision",
  "folder_id": "observed-folder",
  "observed_at": "2026-10-01T12:00:00+00:00",
  "content_sha256": "SHA256_OF_ACCEPTED_MARKDOWN_BYTES",
  "suggestions": "excluded",
  "structure_verified": true
}
```

Use actual values. `revision_id` and `folder_id` are optional when genuinely
unavailable; disclose the limitation. `suggestions` is `none` or `excluded` only
after verification. `structure_verified` means provider readback verified the
selected text's headings/links and preservation contract; required for handoff
confirmation. A URL alone, successful write response, or hash does not establish
this. A capture's observation also carries `format_sha256`, `format_version`,
`legacy_format_sha256`, `projection` and, when review is pending, `review_state`;
other extra fields (including credentials/raw responses) are rejected. URL query
and fragment parameters are discarded; selected tabs are explicit metadata.

## Commands

- `source --name NAME --purpose reference --observation OBS --file TEXT` creates
  a provenance-bearing source. Other purposes follow ordinary source roles.
- `prepare --id ARTICLE --kind draft` freezes the selected local artifact and
  returns `transfer` and `file`. For another handoff to its linked Doc also supply
  a fresh observation/file; use `--new-document` only for a requested new copy.
- `confirm --id ARTICLE --kind draft --transfer ID --snapshot CAPTURE` (or
  `--observation OBS --file TEXT`) validates readback against the frozen copy
  and records the baseline. Readback may differ from the frozen copy only in
  incidental whitespace. Failed confirmation retains the pending copy and local
  work. A repeated identical confirmation is idempotent. A newer baseline
  prevents an older confirmation.
- `compare --id ARTICLE --kind draft --snapshot CAPTURE` returns `unchanged`,
  `local-only`, `remote-only`, `converged`, or `conflict`, a comparison
  fingerprint, and paths to the common baseline/current local text. A Doc whose
  formatting fingerprint equals the baseline is unchanged however its Markdown
  is rendered. For `conflict` it also returns `merge`: `clean` when the two
  sides changed different passages, or `conflicts` with a staged file in which
  each passage both sides changed is marked `<<<<<<< local` / `=======` /
  `>>>>>>> google`. It changes no article data.
- `accept --id ARTICLE --kind draft --snapshot CAPTURE --expected-comparison
  HASH` rechecks the comparison and saves the outcome: Google's text for
  `remote-only`, the unchanged local text for `unchanged` and `local-only`
  (unsent local edits are kept, never replaced), and the automatic merge for a
  `conflict` whose merge is `clean`. A conflict with overlapping passages needs
  `--resolution-file FILE`: the merge file with the author's chosen wording in
  place of each marked passage. Show the marked passages and obtain that choice
  first. A resolution that still has markers, or that leaves out text only
  Google changed, is refused; `--discard-remote` records the author's explicit
  decision to drop Google-only text. `--kind outline` preserves an outline-only
  task. Originals, pins, history and stop points survive; affected draft reviews
  become stale. Local text that differs from Google stays visibly unsent.
- Once a blog has a formatted baseline, `accept` and `confirm` require
  `--snapshot`; a hand-built observation would discard that baseline and is
  refused.

Transfer snapshots use article `history/derived-google-TRANSFER-local.md` and
`history/derived-google-TRANSFER-document.md`, which older Team Hub readers
already preserve.
Article metadata holds identity/tabs/revision or fingerprint, direction/time,
verification state and baselines. Source records hold `google_document` metadata.
No credentials, absolute paths, or live capability cache belong in these shared
records. Old workspaces need no destructive migration; metadata is additive.

## Operation receipts

`receipt --id ARTICLE --file RECEIPT` stores only operation, document_id, status
(`verified`, `partial`, `failed`, `unavailable`), requested and observed results.
The helper checks consistency, not remote execution or human authorization.
Use bounded projections, never raw connector responses. Each module specifies
its requested/observed fields. Readback must support any verified status. No
receipt changes publication approval or marks an editorial check passed.

## Formatted snapshots

`start`, `prepare`, `compare`, `confirm` and `accept` take `--snapshot
<directory>` from the [round-trip helper](roundtrip.md). The observation's
`format_sha256` tracks native text/style/structure of the tab content
independently of the Markdown content hash; Doc and tab titles are not part of
it. Compare reports `format_changed`; even unchanged text can receive a snapshot
checkpoint. The bundle must match the observed document, tabs, revision and
Markdown exactly. DOCX, Markdown and the snapshot's hash summary are retained
under article history and shared through the private Hub lifecycle. Raw native
JSON stays on this computer in the blog folder's `.google-native/`.
