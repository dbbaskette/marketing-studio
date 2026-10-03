# Bring Google edits back

**Input:** a linked article and a fresh reading of selected accepted Doc text.
**Output:** comparison, or a new saved local/shared revision with prior work
preserved. Apply [adapter](../google/adapter.md), [privacy](../privacy.md), and
[checkpoint contract](../google/checkpoints.md).

For formatted shared editing, load [format-preserving round trips](../google/roundtrip.md).
For pending suggestions or a saved review submission, use runtime 1.9+ capture
with `--include-review`; preserve native threads separately from accepted text.
Store DOCX + Markdown snapshots on return, including formatting-only changes;
use paragraph wording patches for updates to an existing formatted Doc.

1. Resume the article's saved voice, guidance, source and shared-context pins.
   Fetch the linked document and selected tab IDs; inspect structure, accepted
   text, current revision and suggestion state. A renamed tab can retain its ID;
   a different ID/scope requires explicit reconciliation, not a silent baseline
   switch. No baseline: use [start from Google](../google/start.md) for a starting
   manuscript; use source intake for reference material. Do not pretend an unrelated file is the same editing copy.
2. Run `google compare` on a faithful Markdown projection of the provider
   readback. Read just the relevant baseline/local/remote passages to explain
   differences. Retain provider indexes for native work; local Markdown offsets
   are not Docs indexes. A fingerprint-only observation is weaker than a guarded
   provider revision and does not establish structural fidelity.
3. Handle the result:
   - `unchanged`: no manuscript rewrite; still save an inspected formatted snapshot when formatting changed. Report text and formatting separately.
   - `remote-only`: save the returned accepted text with `google accept` and its
     exact comparison fingerprint. A return request authorizes this local save.
   - `local-only`: retain unsent local edits; offer a guarded handoff if wanted.
   - `converged`: accept the refreshed baseline without unnecessary rewriting.
   - `conflict`: show the material differences and keep both versions. Ask for
     keep-local, use-Google, or a proposed merged result. Save a chosen merge to
     a separate resolution file, then accept with the exact comparison hash.
     Never silently prefer the remote or regenerate the author's decision.
4. The helper rechecks local/remote/baseline inputs under the workspace lock. If
   the comparison changed, reread/recompare before accepting. Do not reuse a
   previously approved resolution after new changes without checking its scope.
   Preserve original, draft history, source/voice/guidance pins, notes and stop
   point. A changed manuscript stales affected reviews; rerun only requested
   checks against the new text. Shared Team Hub records retain transfer snapshots.
5. Reopen the saved artifact and summarize the returned changes and unresolved
   items. A merge differing from current Google text stays visibly unsent. A
   later write back is a separate handoff, not an automatic side effect.

Comments remain review context, not manuscript prose. Pending suggestions remain
pending unless the user explicitly asks to accept/reject them and the provider
supports that action. If accepted text cannot be separated, mark return unavailable
and offer an unambiguous export. Access/readback failures preserve local content;
failed checks never become clean reviews. Never report completion based only on
a successful tool call or on text copied from the outgoing draft.
