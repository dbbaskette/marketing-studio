# The Training Studio desk

Conversation can create, inspect and save the same desk records with `studio desk create/show/context/submit/save`. It needs no browser or nested assistant. Requested scope is explicit and finite; a teaching-plan-only request creates no broader materials. Checked acceptance leaves materials Draft. `studio desk take/scope/handoff` are explicit checked ownership and scope changes; restarts and page visits leave conversation-owned work alone. `studio desk answer` records only actual current look/design answers. The existing `training.py desk` command still serves the page.

The desk is where you read, change and finish a new training as Training Studio makes it. Start with **New training**: describe the learning goal and audience, choose materials and research sources, then check the summary and start. You can leave and return while work continues. Progress shows what is being made, time and cost, and anything that needs you; pause, resume or stop work from the run.

## Check the topics, then build

New trainings first research and plan what to teach. **Here’s what this training will
cover** lists the topics, order, depth and timing across all selected levels. Expand
Examples and exercises for more detail. **Ask for changes** revises the plans without
repeating research; describe the emphasis, depth or practical work you want.
**Build the training** generates the selected materials automatically. There is no
sample lesson. If you requested a deck, **Review slide text** shows its words and
speaker notes before design starts. Ask for changes or choose **Approve text & design deck**
for that exact version. Materials remain drafts until
you mark them Ready, and sending to Google or publishing remains your decision.
Older saved trainings keep their original flow.

## Read and change materials

Open the training on the desk. Each level has its own plan and materials; research is shared. Choose a material tab to read it as learners receive it: its formatting is shown, not its Markdown, and **Copy text** copies a section's exact saved text. Teaching details such as the objectives a section covers are folded away. Choose **Edit** to open its parts, and a section tab to edit one part; text you have not saved yet keeps the material open for editing as you move between tabs and levels. Sources has its own tab; the other materials stay available without filling the page. You can type in an editable part, add a note asking for a change, or select a passage and ask for a change to just that passage. Review the result as it arrives. History keeps earlier versions and lets you restore one. Your own typing is saved, and a result does not overwrite a part you changed while it was working.

Sources collects the findings and references used in the training. A guide or brief's Sources section is maintained from its citations; change references in the text instead of typing into that section. You can read the research and plan, and decide how changes should reach the materials that depend on them.

The toolbar's **Download level 101** (or **Download all**) opens a sheet whose **Download level 101 (.zip)** takes every written material of the level in one ZIP, exactly as saved, with the index once it is written. Each file in it is named by its level and what it is, such as `101-learner-guide.md`. Each material can also be downloaded alone, there or from its card. Downloading marks nothing ready and sends nothing.

A Yoodli layout reads as Yoodli takes it: one list of its fields in order, each with its name, the characters it uses of Yoodli's limit, its text, and a **Copy** button named after the field. How to use the fields in Yoodli, and a copy of the whole layout, are folded away above the list.

On a phone the desk keeps out of the way of what you read. The toolbar is one row with the title, the one filled action (such as **Mark ready**) and **More**, which holds Download, Google Doc and Finishing. The material and section tabs are one row that scrolls sideways, and choosing one brings what it shows to the top of the screen. While a sheet is open, Tab and Shift+Tab go round its own controls only.

## The deck

The deck card shows one slide at a time. Choose a slide in **Slide to review**; slides with review suggestions are marked. Expand **Edit slide text and speaker notes** to change its words. Detailed review notes stay collapsed on the deck card. You can edit slide words and speaker notes, choose a look, and request changes to a slide or the whole deck. A slide note redraws its section; other slides are kept. Review findings are proposals: **Apply fix to this slide** requests a change at the displayed price, while **Dismiss suggestion** records that you read the finding. There are no automatic repair rounds on the desk. A grave finding still blocks **Mark ready**, even if skipped.

Harness Slides 0.16 requires your explicit approval of its design questions when a word change affects an approved drawing. The desk shows the questions and submits your answers. A proposal alone does not approve the change. If the change cannot be checked or rendered, the previous deck remains. Speaker notes do not require this design approval.

## Holds and updates

When you change an input, a dependent material can be held because it was built from an earlier version. Choose **Update** to make it from the current input, or **Keep as it is** to retain it. Update or keep an upstream hold first. Where offered, choose a scope for an update, or update a chain of dependent materials. The desk shows the estimated price before you request work. Stopping updates leaves the remaining materials held; a step already working may finish. Materials Training Studio does not remake can be kept or changed by you.

## Add a source

Use **Add a source** to add documents after research. The desk shows the price before you update the research. New or changed findings are marked, and dependent materials may be held for your decision. A change already in progress may need to finish or stop first. Existing documents stay in the training.

**Add from library**, in the same sheet, takes documents already kept in the Document Library without uploading them again. They wait, unread, until you choose **Update the research**, and start nothing before then. A training researched from the public web reads your documents too from then on, as the sheet says first.

## Mark ready and Finishing

Under the level tabs, one line says how many of the level's materials are ready, still to write, drafts to mark ready, or need attention or a decision. A material is ready on its own; a level is complete once all of its materials are, and downloads and Google Docs stay optional. While a deck's slide text waits for you, its tab says **Needs your text approval** and **Review slide text** takes you to it; materials not written yet say **Not written yet**, never Writing, while nothing works on them. Time so far is a detail you open; elapsed time is never an estimate of what is left.

**Mark ready** records your approval of a material. You can also mark a level ready: **Mark this level ready** appears only while one of the level's materials is a draft waiting for it, and it opens a sheet first. The sheet lists each material it will mark as **Opened** or **Not opened yet** (with a way to open it), says which guides and briefs go to the Document Library, and ends with its submit and **Cancel**; Cancel changes nothing and returns you to the button. The desk stops at the first material that needs attention. Settle holds, grave deck findings and other blocking checks first.

Ready can be taken back on purpose. The toast after Mark ready offers **Undo** while each version is the one you marked, and puts every material back exactly as it was. A Ready card has a quiet **Return to draft**, bound to the version shown. Neither removes anything from the Document Library: the card then says the library keeps revision N until you mark it ready again, and marking the same words ready again adds no revision. Return to draft is offered for work the runner drives; in a conversation, readiness is decided there.

A later edit makes the material a draft again. Opening a Ready material for editing says so before you type (with the library revision it keeps), and the first save says it is back to Draft. Once all requested materials are ready, Training Studio writes the index. Ready is your approval and sends nothing by itself unless the training was started with Google Docs, which then follow readiness as before. A training made with local copies can make a Google Doc of one guide or brief from **Google Doc**, of exactly the version shown, and update it only when you ask; see [Google Docs](google-docs.md). You can look for changes in Google Docs and bring them back, resolving a conflict if both versions changed.

**Finishing** opens on the material in front of you, beside it on a wide screen and above it on a phone, with its heading in view and focused; **Close** or Escape returns you to the button (to **More** on a phone). **All materials** chooses another one of the level. On the plan, or on Research & sources, which have no Finishing checks, it says so and lets you choose a material that has them. It offers checks and proposals. Review each proposal and choose Apply, Edit or Skip. A proofread fix may request work; other findings can open a note for you to edit. Applied changes keep a version in History. Local checks create proposals without starting a job. When you request an AI check, it runs work to produce proposals; each proposal waits for your decision.

## Working with teammates and older trainings

In a shared workspace, one computer drives a training at a time. A teammate can read what was shared and explicitly take over when needed. Your unshared work is kept aside when a takeover requires it. Share before leaving the desk so teammates can see your work.

Trainings started before the desk keep their original review flow. Once a saved training is finished and nothing is waiting, **Open on the desk** brings it to the desk. Existing person-approved material stays ready where applicable; other material may return as a draft for your decision. Opening it again does not create another copy.

Conversation-owned work supports explicit person Mark ready through the main desk or checked `studio desk ready`, without runner handoff or jobs. Its desk is for reading: each material's Mark ready and downloads, and nothing that only the runner does (no Edit, Finishing, Google Doc, Mark this level ready or Stop). Home, Trainings and Status say **In conversation**, never that it waits for you. A change the page sends anyway, such as a save, is refused with the reason and what to do, and the desk says so.

Once every material is ready and the index is written, the desk offers **Open the index** and **Publish**, which makes the training's next numbered revision as the Published screen describes. Retained helper-page decisions and approval-mode changes refuse conversation ownership under the shared write guard. `studio desk return-delivered` previews and losslessly sets aside an undelivered local deck in History, restoring proven delivered active state or prior absence; it does not publish or invent approval.

Unfinished saved trainings offer **Open on the desk** with a read-only preview and Apply/Cancel. The preview names retained material parts, holds, incomplete work and prerequisites. Apply preserves original records and files and assigns conversation execution; it starts no work and grants no approval or Ready. A known prior paused/stopped runner status stays in History. Later broader work requires explicit checked scope. Early, unsupported, missing-input or worker-marked trainings keep their saved flow; existing saved recovery may discard uncommitted work.

Migration requires Training Studio 4.7.0 or newer and raises the existing workspace requirement. Close older running instances first: older already-configured runtimes may ignore the new requirement. Nothing installs or updates automatically. An interrupted opening requires explicit retry with its original preview token; changed recovery records refuse. Losing one receipt or effective record blocks reading and execution; externally deleting every migration trace cannot be detected from unchanged originals alone. See the [migration commands](../skills/training-studio/references/migration.md).

Shared migration requires original records, retained shared inputs and the existing workspace record to match their committed version and index. Commit those saved inputs through the existing workspace workflow first; migration never includes their edits in its metadata commit. Private source/drawing files stay local. A local-only workspace has no peer-replay prerequisite.

New runner trainings with several research questions use up to three investigators.
Each gathers evidence for part of the approved plan. One writer combines it into a
report and brief, and a separate reviewer checks the captured sources and originals.
The progress band shows which areas are working or kept. If an area fails, Retry
reuses the checked areas. Fact objections revisit their area; wording objections
return to synthesis. Every changed report receives an independent check.

Elapsed time includes waiting and stopped time. Active time counts overlapping
workers once; total assistant time adds their durations. Incomplete older timing
history is identified. Existing trainings continue with their saved workflow.
The existing allowance is shared across workers; parallelism does not raise it.
Providers that do not report dollar cost still cannot supply a precise dollar total.

## The Document Library

**Research & sources** has a **From the Document Library** part when the training's
research reads documents. **Add from library** chooses documents kept on this computer
for this training only. They are listed as not read yet, and **Update the research**
reads them after saying what it changes, as **Add a source** does. A newer revision of
one is shown, and **Use revision N** takes it, also unread until the research is
updated. Nothing is added while a change is being made.

**Add a source** asks where each document is kept: **Keep in library** (a copy for
other projects too) or **Only this project**.

A learner guide or brief you mark ready is kept in the Document Library as Markdown.
Its card says which revision, or that the save failed, with **Keep in library again**.
Returned to draft, by an edit, **Undo** or **Return to draft**, its card says the library
keeps that revision until it is marked ready again; nothing is removed from the library.
A guide or brief that was Ready before the library kept anything offers **Keep in
library**.
