# Review in Google Docs

**Input:** requested comments/replies/resolutions and exact working Doc.
**Output:** verified review actions or an explicit unavailable/partial result.
Follow [adapter](../google/adapter.md), [privacy](../privacy.md) and the installed
Google Drive Comments skill. Load ordinary editorial checks only as requested.

For proofreading replacements posted as native suggested edits, load
[suggestions](../google/suggestions.md), including its automatic fresh pull and
revision guard. Do not turn an ordinary proofread into external comments.

Read the current selected tabs and existing threads. Draft all requested comment
actions using current evidence before sending. A new comment quotes exact text
and names the tab/section in its visible body; resolve duplicate phrases with
nearby text and actual provider ranges. Replies/resolutions use observed thread
IDs. Never guess indexes, author quotes, thread IDs or inline anchors.

For inline comments, verify that the active provider supports a native anchor
for this surface and that it reads back attached to the intended current text.
Drive `anchor` JSON or a `quoted_text` field alone is not proof of an inline
comment. If native anchoring is unavailable, explain that limit and ask whether
a document-level comment with an exact quote is acceptable. Do not silently
substitute an unanchored comment. Once authorized, include the quote plus tab
and section in the body so the recipient can locate it without an anchor.

Perform only requested creates, replies and resolutions, following the current
tool's batch limit. Avoid duplicate retries after partial/uncertain results:
read existing threads first. Before sending, recheck relevant text and revision;
if the comment API has no revision guard, disclose the race and read back both
target text and thread. A moved/deleted target is partial, not verified. Do not
resolve a discussion merely because you revised the text.

Read back each resulting comment/thread and its content, target quote, location,
and requested resolution state. Distinguish native inline verification from
quote-based document comments. Summarize successful and failed actions separately.
An unavailable comment action can remain local review notes. Comments and thread
resolution never approve publication or change an article's editorial status.

Optional [receipt](../google/checkpoints.md): operation `comments`, document ID,
status and requested/observed lists of `{action, location, tab_id, quote,
thread_id}`. Observed creates include their returned `thread_id`; observed inline
actions also require `anchor_verified: true` after native anchor readback. `action` is create/reply/resolve; `location` is inline/document.
Creates require exact quote/tab evidence; replies/resolutions require a live
thread ID. Record only verified provider observations, not guessed anchors or
credentials. Receipts are an audit summary, not substitutes for actual readback.
