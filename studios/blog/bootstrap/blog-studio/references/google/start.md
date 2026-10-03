# Start a blog from an existing Google Doc

Load for “Start from this Google Doc,” “Use this Google Doc as my draft,” or an
existing Google manuscript supplied for proofreading/editing. Runtime 1.11+ adopts
the selected Doc as both the starting manuscript and the working Google copy.
“Use this as a source” remains [reference intake](../modules/blog-google-source.md)
and does not change a blog’s editing destination. Ask only when that role is unclear.

1. Use the [adapter](adapter.md) to read the exact supplied native Doc and enumerate
   its tabs. Reuse the configured account. Resolve ambiguous scope; do not search
   unrelated Drive files. A manuscript import authorizes reads and local storage,
   not Google edits, copying, sharing changes or sending suggestions.
2. Capture a fresh [formatted snapshot](roundtrip.md) using the installed runtime:

   ```text
   python3 <runtime>/google_roundtrip.py capture --file-id <id> --tab-id <tab> --output <new-private-directory>
   ```

   When native suggestions are pending, use `--include-review` to keep accepted
   prose separate from proposals. Inspect Markdown, DOCX and native structure for
   content, headings, links and formatting. Only then mark `structure_verified`
   true in `observation.json`. Never mark it verified solely because export passed.
   The bounded capture requires a single-tab Doc; do not silently export unrelated
   tabs or flatten unsupported content. If faithful capture is unavailable, report
   the limitation and offer source-only intake without claiming a sync baseline.
3. Use the observed title unless the author supplied another. Initialize the writing
   workspace if needed; then save and link in one local operation:

   ```text
   python3 <runtime>/studio.py --root <workspace> google start --title <title> --observation <capture>/observation.json --file <capture>/document.md --snapshot <capture>
   ```

   This preserves `ORIGINAL.md`, initializes `DRAFT.md`, saves DOCX/native history,
   records the original Doc URL, tab IDs, revision and text/formatting baseline,
   and selects the blog. It creates no Google document and performs no Google write.
   Repeating the start selects an already linked blog without replacing its draft
   or baseline; compare/pull current Google changes using the existing return flow.
4. Bind a new article's actual guidance task through the ordinary workspace flow;
   retain pins on a resumed article. Respect the imported author voice and selected
   writing defaults. With a selected Team Hub, the normal article mutation lifecycle
   shares its original, draft, link and formatted history there. Report sync status.
5. Show the imported title and a clickable link to the observed working Google Doc and continue
   any requested proofreading. A plain start stops after intake. “Proofread” stays
   local. “Push as suggestions” loads [suggestions](suggestions.md), refreshes the
   linked original Doc, reconciles changes and sends only selected findings there.
   “Push to Google Docs” also reuses this link; do not create a second Doc unless
   the author asks for a new copy. An import alone never sends edits or comments.

Keep private capture files out of the skill repository. Record accepted text only
in the manuscript; retain pending review separately without accepting/rejecting it.
