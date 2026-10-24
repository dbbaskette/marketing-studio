# Writing and editing a blog

New blogs, and drafts you bring, are written and edited on the
[writing desk](runner.md#the-writing-desk). This page is about **Edit manuscript**, the
editor that blogs started before the desk keep. Its imported original is retained; editing
there changes the local working copy. Nothing is sent to Google until you preview and
confirm a specific delivery.

## Choose the starting point

| Starting material | Route | Next decision |
| --- | --- | --- |
| A topic and point of view | New blog → A topic, with your documents as sources | Type the point, or pick one of three angles |
| An outline or notes | New blog → An outline or notes | Write from it, or shape the outline first |
| A draft, a file or a Google Doc | New blog → A draft | An optional first pass; then notes on the desk |
| Someone else's Google Doc | New blog → A draft → Google Doc | Edit on the desk, then **Finishing → Before publishing → Send to Google Doc** as suggestions |
| A blog in the manuscript editor | Blogs → Continue editing | Choose the precise editing scope |

The brief's audience and purpose matter for technical/product marketing: a
practitioner tutorial, product explanation, comparison, and executive argument
need different evidence and structure. Author preferences override generic house
style. Imported author voice and stance are preserved unless the requested edit
explicitly changes them.

## Work on the manuscript

The local editor accepts Markdown and offers a rendered preview. Save retains
previous versions and checks whether numbers, links or quotations changed. That
mechanical warning is not proof that meaning or technical claims stayed unchanged.
Unsaved text is retained while navigating within the page; save before closing.
Stale pages cannot overwrite a newer saved manuscript.

Choose one focused action:

- **Polish writing — no research:** one pass for proofreading, copy editing and
  natural wording. It applies author rules and house style, addresses repetitive
  or formulaic phrasing, and preserves voice, facts and technical qualifiers.
  Choose which suggestions to apply; this is editorial guidance, not AI detection.
- **Check facts:** exact claims and selected evidence, including unsupported or
  contradicted claims. No readable evidence means unavailable, not passed.
- **Review argument and structure:** audience, reasoning, section contribution,
  qualifications, and technical/product relevance.
- **Make a scoped revision:** apply the requested changes while preserving the
  author's stance and voice, then return feedback.

Polish writing always skips research, including when replacing a stopped
research run. From that run, open **Edit manuscript** and choose **Polish writing**. For other checks, select saved evidence sources beside the check. The default uses saved evidence
without starting a new research pipeline. Choose selected-source research or
public research explicitly when needed. Research receives the manuscript's claims
and requested scope. It cannot reclassify private source permissions.

Feedback records retain the checked inputs and coverage. Editing the draft makes
old results stale. A reviewed research bundle is pinned by digest. Findings remain
assistant assessments unless the record identifies a performed mechanical check.

## Edit another author's Google Doc in the manuscript editor

1. Open a blog already in the editor, imported from a Google Doc, with **Continue
   editing**. A new Doc goes to the writing desk instead (**New blog → A draft → Google
   Doc**), and so does **Polish another document** after you finish. Importing starts no
   model.
2. In **Polish**, optionally name a concern, then choose **Polish writing**.
   This combines proofreading, copy editing and natural wording without research.
   Other editing actions, including fact checking, are in a disclosure.
3. **Choose changes** shows each original passage, its proposed replacement and
   the reason together. Use all the changes in one click, or select individual changes. You can adjust
   a suggested replacement before continuing.
   Questions can be selected as comments. Manual feedback is a secondary tool.
4. In **Finish**, the page checks the current Google Doc and shows the destination
   and selected feedback. Choose **Send feedback to Google** when ready. The result reports the
   actual Google delivery state. Successful delivery replaces the send prompt.
5. Alternatively save the selected edits to your local draft and download the
   revised manuscript. The whole batch is refused if quotes are ambiguous,
   missing or overlapping; no partial changes are saved. Previous versions remain.

The manuscript stays available under **Read or edit the manuscript**. Saved
manual edits can become proposals through **I edited the manuscript myself**.
Structural or formatting changes may still need individually quoted feedback.
Focused editing remains on these screens while the worker runs and when it
finishes. There is no pipeline approval between receiving suggestions and choosing
which to keep. Old focused-review links open the same editor.

| Delivery mode | Behavior |
| --- | --- |
| Suggestions, with comments fallback | Try native suggestions; use readable comments only when Google definitively cannot accept suggestions |
| Suggestions only | Refuse unsupported native suggestions; do not switch to comments |
| Comments only | Send feedback without replacing the author's text |

Google delivery uses the same planning, revision guards, ledger and verification
as the CLI. A changed Google revision blocks the send. A repeated send verifies an
existing attempt rather than blindly duplicating it. An uncertain native write
never triggers a second comment delivery. The page reports the actual outcome.
The author accepts or rejects suggestions in Google Docs. Comments do not imply
permission to apply their proposed replacements.

The preview sends only the selected feedback. Unselected local manuscript changes
are not pushed as a whole-document replacement. For remote/local conflicts, use
the existing Google pull/reconciliation CLI workflow; retain the local draft and
refresh the findings before preparing a new delivery.

## Team repositories

Local writing does not require taking ownership or joining a team. Status
separates the active workspace from a configured shared repository and offers
remembered repository addresses when available. Joining uses a separate workspace;
existing writing stays where it is. Copying existing blogs remains explicit.

## Product-marketing walkthrough assessment

The primary use cases are supported: starting from a topic, choosing an AI-assisted
angle, drafting from a supplied outline, revising an owned draft, and providing
non-destructive editorial feedback on another person's Google Doc. The desk keeps
editing, sources and finishing together.

For technical marketing, fact-check coverage and author control matter more than
an automatic “clean” badge. Unsupported product or performance claims should stay
visible as questions. Prose cleanup must not erase qualifiers or invent customer
experience. Another author's Doc should receive selected suggestions/comments,
not an unrequested rewrite.

Remaining boundaries are deliberate and visible: this is a Markdown editor;
complex formatting/paragraph restructuring may require individual feedback; Google
conflict reconciliation still uses the existing CLI; and synthetic providers do
not establish permissions or capabilities of a particular live Google account.
