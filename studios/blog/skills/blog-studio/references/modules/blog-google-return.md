# Bring Google edits back

**Input:** a linked article and a fresh capture of the linked Doc.
**Output:** comparison, or a new saved local/shared revision with prior work
preserved. Apply [adapter](../google/adapter.md), [privacy](../privacy.md), and
[checkpoint contract](../google/checkpoints.md).

Every pull starts with a capture: load [format-preserving round trips](../google/roundtrip.md)
and run `google_roundtrip.py --root <workspace> capture --file-id <id>` for the
linked Doc. The capture carries accepted text, the DOCX and the formatting
fingerprint together, keeps pending suggestions out of the text by itself, and
is what `compare` and `accept` take as `--snapshot`. A blog with a formatted
baseline cannot be returned from a hand-built observation. Only a connector-only
session without the gcloud helper builds an observation by hand, and only for a
blog that has no formatted baseline yet.

1. Resume the article's saved voice, guidance, source and shared-context pins.
   Take the document ID from the linked Doc's URL and capture it. A renamed Doc
   or tab keeps its ID and is not a change; a different ID/scope requires
   explicit reconciliation, not a silent baseline switch. No baseline: use
   [start from Google](../google/start.md) for a starting manuscript; use source
   intake for reference material. Do not pretend an unrelated file is the same
   editing copy.
2. Run `google compare --id <article> --snapshot <capture>`. Read just the
   relevant baseline/local/remote passages to explain differences. Retain
   provider indexes for native work; local Markdown offsets are not Docs indexes.
3. Handle the result with `google accept --id <article> --snapshot <capture>
   --expected-comparison <hash>`:
   - `unchanged`: no manuscript rewrite; accept when `format_changed` is true so
     the formatted snapshot is saved. Report text and formatting separately.
   - `remote-only`: accept saves the returned accepted text. A return request
     authorizes this local save.
   - `local-only`: unsent local edits are kept as they are; accept only saves the
     snapshot. Offer a guarded handoff if wanted.
   - `converged`: accept the refreshed baseline without unnecessary rewriting.
   - `conflict` with `merge.status` `clean`: the two sides changed different
     passages. Accept without a resolution file; both sets of edits are kept and
     the local ones stay unsent. Tell the author what was merged.
   - `conflict` with `merge.status` `conflicts`: open `merge.file`, show each
     passage marked `<<<<<<< local` … `>>>>>>> google`, and ask for keep-local,
     use-Google, or a merged wording per passage. Put the chosen wording in place
     of the marked passages and accept with `--resolution-file`. Never silently
     prefer one side or regenerate the author's decision. Text that only Google
     changed must stay in the resolution; `--discard-remote` is for an author who
     explicitly chose to drop it.
4. The helper rechecks local/remote/baseline inputs under the workspace lock. If
   the comparison changed, capture and compare again before accepting. Do not
   reuse a previously approved resolution after new changes without checking its
   scope. Preserve original, draft history, source/voice/guidance pins, notes and
   stop point. A changed manuscript stales affected reviews; rerun only requested
   checks against the new text. Shared Team Hub records retain transfer snapshots.
5. Reopen the saved artifact and summarize the returned changes and unresolved
   items. Local text that differs from current Google text stays visibly unsent.
   A later write back is a separate handoff, not an automatic side effect.

Comments remain review context, not manuscript prose. Pending suggestions remain
pending unless the user explicitly asks to accept/reject them and the provider
supports that action. If accepted text cannot be separated, mark return unavailable
and offer an unambiguous export. Access/readback failures preserve local content;
failed checks never become clean reviews. Never report completion based only on
a successful tool call or on text copied from the outgoing draft.
