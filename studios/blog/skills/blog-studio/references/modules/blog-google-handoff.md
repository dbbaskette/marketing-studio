# Draft handoff to Google Docs

**Input:** saved selected draft/outline and requested destination.
**Output:** verified editing copy and portable transfer baseline. Apply the
[Google adapter](../google/adapter.md), [privacy](../privacy.md), and
[checkpoint contract](../google/checkpoints.md).

For formatted shared editing, load [format-preserving round trips](../google/roundtrip.md).
Store DOCX + Markdown snapshots on return, including formatting-only changes;
use paragraph wording patches for updates to an existing formatted Doc.

1. Reuse article title, brief, voice and stop point. Select `DRAFT.md` or
   `OUTLINE.md`; an outline-only task must remain an outline. Resolve folder and
   whether this is a new copy or an explicitly targeted working Doc. Inspect
   inherited audience before placing private content in a shared folder. Do not
   attach sources, background, voices, internal notes or rules by default.
2. `google prepare` freezes the selected copy. For a linked working Doc, fetch
   current accepted text/structure and pass its observation. If remote edits
   conflict, follow [return](blog-google-return.md) first. The returned revision
   guard is mandatory for the native write; a hash cannot substitute for it.
   If guarding is unavailable, offer a new copy and retain the working Doc.
3. With a connector, load its installed Google Docs skill and current creation
   route. With gcloud, follow the [local adapter](../google/gcloud.md) import
   route and its operation receipt; no separate Google skill is required.
   A constrained template uses [native template reuse](blog-google-template.md).
   Basic blank creation and polished import routes follow the active provider
   skill. Setup follows the user's selected connection; never install tools merely
   because a handoff was requested.
   Retain native headings, lists, links, tables and requested media. Never
   replace a whole existing Doc to update one section or selected tab.
4. Write only the prepared copy. For an existing Doc, use trusted read/current
   indexes, selected tabs and `requiredRevisionId`. Preserve other tabs, native
   controls and sharing. A stale revision requires reread, not forced overwrite.
   For an uncertain create/import, locate its returned ID before retrying.
5. Read back the actual destination. Verify chosen content and native structure,
   links, complete tab scope, folder and inherited access. Construct the bounded
   observation and `google confirm` it against the prepared transfer. If text
   normalization differs, inspect and resolve that difference; never substitute
   the local text for actual readback to make the hashes match.
6. Return the observed verified link and describe it as the editing copy. If
   readback fails, report the created/updated Doc as unverified and retain the
   pending checkpoint. Do not claim a completed handoff or automatically retry.

A local edit made during Google work remains local and is detected against the
frozen baseline on return. Sharing and publication are separate requested actions.
Review comments, suggested edits and editor permissions do not approve publishing.
An existing Doc can be linked without writing by preparing its matching local
text and confirming actual readback; mismatched text needs source intake or a
reviewed reconciliation first.
