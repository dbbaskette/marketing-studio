# Start a blog from an existing Google Doc

Load for “Start from this Google Doc,” “Use this Google Doc as my draft,” or an
existing Google manuscript supplied for proofreading/editing. The selected Doc
becomes both the starting manuscript and the working Google copy.
“Use this as a source” remains [reference intake](../modules/blog-google-source.md)
and does not change a blog’s editing destination. Ask only when that role is unclear.

1. Take the document ID from the supplied link. Reuse the Google account
   remembered for the workspace ([gcloud access](gcloud.md)). Do not search
   unrelated Drive files. A manuscript import authorizes reads and local storage,
   not Google edits, copying, sharing changes or sending suggestions.
2. Capture the Doc with the installed runtime:

   ```text
   python3 <runtime>/google_roundtrip.py --root <workspace> capture --file-id <id>
   ```

   The capture goes to the workspace's private staging folder and the result
   names it. Pending suggestions, including a teammate's, are detected and kept
   out of the accepted text automatically. Check the returned `summary` against
   the Doc you expect and read only the Markdown passages you need (see
   [formatted snapshots](roundtrip.md)); then set `structure_verified` to true
   in the capture's `observation.json`. Never mark it verified solely because
   export passed. Capture requires a single-tab Doc; do not silently export
   unrelated tabs or flatten unsupported content. If faithful capture is
   unavailable, report the limitation and offer source-only intake without
   claiming a sync baseline.
3. Use the observed title unless the author supplied another. Initialize the writing
   workspace if needed; then save and link in one local operation:

   ```text
   python3 <runtime>/studio.py --root <workspace> google start --title <title> --snapshot <capture>
   ```

   This preserves `ORIGINAL.md`, initializes `DRAFT.md`, saves the DOCX and text
   history, records the original Doc URL, tab IDs, revision and text/formatting
   baseline, selects the blog, and removes the staged capture. Raw native JSON
   stays on this computer. It creates no Google document and performs no Google
   write. Repeating the start selects an already linked blog without replacing
   its draft or baseline; compare/pull current Google changes using the return
   flow.
4. A new article records the installed guidance version itself; a resumed
   article keeps what it recorded. Respect the imported author voice and selected
   writing defaults. With a selected Team Hub, the normal article mutation lifecycle
   shares its original, draft, link and formatted history there. Report sync status.
5. Show the imported title and a clickable link to the observed working Google Doc and continue
   any requested proofreading. A plain start stops after intake. “Proofread” stays
   local and, because the blog is now linked, saves findings rather than
   rewriting the draft ([short commands](../short-commands.md)). “Push as
   suggestions” loads [suggestions](suggestions.md), refreshes the linked
   original Doc, reconciles changes and sends those findings there.
   “Push to Google Docs” also reuses this link; do not create a second Doc unless
   the author asks for a new copy. An import alone never sends edits or comments.

Record accepted text only in the manuscript; pending review stays in Google
without being accepted or rejected.
