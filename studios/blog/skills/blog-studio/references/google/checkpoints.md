# Local transfer contract

Run `studio.py --root WORKSPACE google ...` from the installed runtime (offline:
packaged scripts). The provider stays in the harness. Do not print whole documents
or shell download logs merely to record a checkpoint. Use untracked workspace
staging files, never the skill repository. Records and transfer text join only
the selected private Team Hub through the normal article/source lifecycle.

## Observation

Supply `--file accepted.md --observation observation.json`. UTF-8 Markdown with LF newlines must
faithfully project **selected accepted text**, retaining headings, link targets,
lists and tables where representable. Use consistent whitespace/Markdown rules
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
this. Extra fields (including credentials/raw responses) are rejected. URL query
and fragment parameters are discarded; selected tabs are explicit metadata.

## Commands

- `source --name NAME --purpose reference --observation OBS --file TEXT` creates
  a provenance-bearing source. Other purposes follow ordinary source roles.
- `prepare --id ARTICLE --kind draft` freezes the selected local artifact and
  returns `transfer` and `file`. For another handoff to its linked Doc also supply
  a fresh observation/file; use `--new-document` only for a requested new copy.
- `confirm --id ARTICLE --kind draft --transfer ID --observation OBS --file TEXT`
  validates readback against the frozen copy and records the baseline. Failed
  confirmation retains the pending copy and local work. A repeated identical
  confirmation is idempotent. A newer baseline prevents an older confirmation.
- `compare --id ARTICLE --kind draft --observation OBS --file TEXT` returns
  `unchanged`, `local-only`, `remote-only`, `converged`, or `conflict`, a comparison
  fingerprint, and paths to the common baseline/current local text. It saves
  nothing. All subsequent checks remain under the workspace lock.
- `accept --id ARTICLE --kind draft --observation OBS --file TEXT
  --expected-comparison HASH` rechecks the comparison and imports remote-only
  edits. Conflict/local-only overwrite requires `--resolution-file FILE` with
  the author's chosen merged or replacement text. Show differences and obtain
  that choice first; do not use this flag as an automatic conflict bypass.
  `--kind outline` preserves an outline-only task. Originals, pins, history and
  stop points survive; affected draft reviews become stale. A merge differing
  from Google remains visibly local-only until sent back.

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
