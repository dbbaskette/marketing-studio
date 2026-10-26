# Blog Studio workflows

## Outcome

The main interface follows a writer's task from starting material to a useful
result. Editing an existing manuscript stays on one workflow; users do not
approve an internal review artifact before choosing edits.

## Paths

| Job | Steps | Result |
| --- | --- | --- |
| Write from a topic or my documents | Kind of post → sources and settings (files, links, Google Docs) → title, reader and point, or three angles → Start | A draft on the writing desk |
| Work from an outline or notes | Kind of post → sources and settings → the outline → write from it, or shape it first | A draft, or an outline to shape, on the desk |
| Edit or polish a draft | One screen, no kind of post: pasted text, a file or a Google Doc → what happens first (check spelling and grammar, just give feedback, reshape to fit a kind of post, or leave it) → optional tone and sources for the fact check → Start | Check spelling and grammar: Review mode, each fix marked in the text to accept or reject, then send the accepted ones to the Google Doc; otherwise the draft on the desk, with notes, selection edits, History and Finishing |
| Polish a blog already in the manuscript editor | Continue editing → polish → choose changes → finish | Google feedback or a revised local draft with retained history; **Polish another document** then opens the polishing screen |

Blogs started before the desk keep their step-by-step run (brief, research, outline,
draft, review, handoff) and the manuscript editor described below.

## Interface contract

Home offers tasks and a compact resume list. Every new blog starts on the writing desk,
including another document polished after one in the editor; nothing stops for the writer
after Start. A draft brought to the desk asks for the input method: pasted text, an
uploaded text/Markdown/Word/PDF file, or a Google Doc link. These are source choices within
one task, rather than separate workflows. Polishing or reviewing a draft never asks for a
kind of post, except to reshape the draft to one; choosing A draft on the stepped start
switches to that one screen. Blogs open the relevant next step.
The editor has three explicit steps: Polish, Choose changes, Finish.
Polish combines proofreading, copy editing and natural wording, without research.
Fact checking, structure review and scoped revision remain available under other
editing actions. Evidence and provider details use progressive disclosure.

Review changes shows original, proposed replacement and reason together. Users
can use all proposed changes in one click or select a batch, then continue. Local application and Google sending remain
separate choices. The Finish screen automatically checks Google and previews the target and selected changes,
requires an explicit send, and reports verified, pending or uncertain outcomes.
Repeated delivery checks use the existing receipt rather than resending.
Stale feedback cannot be silently selected or sent. Manual quoted feedback and
raw manuscript editing remain available as secondary tools.

Review starts with visibly checked changes. Clearing the selection disables
Continue; it never means "use everything." The primary action stays in the
existing toolbar while the writer reads. Skipped changes, adjusted wording and
unfinished feedback survive moving between steps, bound to the manuscript
version. A new version replaces those choices rather than reusing stale quotes.
Local completion summarizes the selection and keeps the full comparison behind
a disclosure. Comments can be downloaded as feedback without applying edits.

Pasted text and uploaded files can supply their own working title. Import
details, raw text editing and failure diagnostics remain secondary. A failed
pass is distinct from a successful review with no suggestions; manual feedback
remains available in either case. Saved edits to a Google copy can be converted
into suggestions without first running an assistant pass.

Moving between editing steps keeps the current document visible during reads.
Late reads and completed saves cannot replace a newer step or force a return
after navigation. Typing that continues during a manuscript save stays in the
local edit buffer. Google preparation has a visible read-only checking state;
delivery still requires an explicit send and reuses uncertain receipts.

Ready outlines and drafts open directly for reading. Back opens progress without
immediately reopening the document. Ideas have one primary "Develop an idea"
action with an explicit choice, alongside saving the angles for later. The
writing flow keeps approvals and stale-version protections; navigating to a
ready document never approves it. Developing a chosen angle makes an outline
and an editable draft; it does not append review-report or export-package stages.

Active and failed editing operations stay in the editor, with progress, stop,
retry and a clear route back to the draft. The editor refreshes when operation
state changes without replacing unsaved text. Existing focused-review links
redirect to the editor. New-writing gates retain their decisions with concrete
labels and the next result explained; detailed stages/history are secondary.

## Implementation and verification

Reuse the authenticated API, existing worker, optimistic tokens, source permissions,
local history, team locks and Google delivery helper. Add only presentation state
needed to resume editing and a guarded batch application for local suggestions.
Use the existing upload-as-blog endpoint for uploaded or pasted manuscripts.

Implement entry points and drafting flow, then the editor/review/finish slice.
Verify task navigation, no-research polishing, batch selection and local apply,
stale/active refusal, Google preview/send/retry, recovery from failure and unsaved
text retention with synthetic documents and providers. Walk the browser at phone
and desktop sizes. Run the full relevant suite and synthetic CLI acceptance through
the existing Tart runner. Preserve real workspaces and do not run live providers.
