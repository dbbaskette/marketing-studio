---
name: infographic-studio
description: Turn supplied text, Markdown or explicitly selected CSV into a branded one-page infographic; suggest a story, compose editable labels and charts with explanatory artwork, inspect actual pixels, revise, approve and export PNG, PDF, SVG and accessible text.
---

# Infographic Studio

Use the native editing desk, from this conversation or its browser UI. Keep content
outside the application/skill directory. Never fetch a supplied URL, conduct research,
install software or publish as part of this skill. A link is a supplied reference.

Find `runner/studio.py` beside this installed SKILL.md; in a source checkout it is
`../../runner/studio.py`. Use Python 3.11+. `--help`, `status`, `inspect ID`,
`history ID`, `computer` and `csv-preview --file FILE` are read-only and start no
provider. `setup --workspace ABSOLUTE_EMPTY_FOLDER` or `serve --open` explicitly
sets up a missing local workspace. Existing workspaces are preserved. Team storage
and research handoffs are follow-up features.

Read `docs/conversation.md` beside an installed skill (or `../../docs/conversation.md`
in a checkout) for exact action schemas and a synthetic journey. Read only the
reference needed for the current stage. In a conversation, author located facts,
stories and art direction directly through the native `action` command; do not
launch the page's planning assistant again for work you are already doing.

1. Capture supplied information, audience, desired takeaway, must-show ideas, locked
   wording, exclusions and A4, Letter or digital portrait size. Preview CSV and ask
   for exact rows/columns/types/units before capture; never infer numeric types.
2. Choose direct (one user-directed story), suggest (one to three distinct stories)
   or hybrid (preserve every must-show idea). Extract only located supplied claims;
   record unknown period, units, denominator or conditions. Label supplied assertions
   as supplied, not independently corroborated. Block misleading comparisons.
3. Save facts/stories as native actions and select a story. Pin the explicitly chosen
   installed brand's non-slide contract; do not invent an organization or logo.
4. Compose readable editable text/chart geometry. Describe meaningful subjects,
   counts, spatial relationships, reading order and reserved label regions before
   image generation. Never use artwork as the only representation of an exact value.
5. Disclose the provider and usage before an image action. Shared Codex uses its
   signed-in built-in image tool; shared Claude Code uses the Gemini API and an
   explicitly configured model/key. No API-key fallback for Codex, no guessed prices,
   no automatic retry of uncertain work. Inspect status/recovery after interruption.
6. Render the actual page, inspect its PNG and original artwork at intended size,
   record located observations and specific corrections. Generation is not visual
   verification. Focused edits name one text element or preserve the original image
   as a reference. Never treat an older preview as the current revision.
7. Run checks and present the actual current page. Only the user can authorize the
   `approve` action; don't approve because a tool or assistant says it looks correct.
   Approval binds the exact revision, scene and input hashes. Edits/restores clear it.
8. Export approved PNG/PDF/editable SVG/accessible text, or an explicitly labeled
   draft. Artwork in SVG remains raster; text and chart marks stay editable. State
   the font portability limitation. Download files, not workspace JSON, as the deliverable.

Preserve all existing content on failures. Never replay running/unknown image intents.
Reopening is read-only; cancellation revokes adoption and does not promise remote
billing cancellation. Layout/image repairs share at most two automatic attempts;
manual revision and a smaller story remain available after that budget is exhausted.
Live provider and owner illustration acceptance are separate from offline tests.
